"""
FinAI Accounting Intelligence Service
══════════════════════════════════════
Central accounting reasoning engine implementing:
  • Hierarchical COA classification with 5-level fallback
  • Financial flow analysis (Inventory→COGS, Revenue→Net, BS identity)
  • Account coverage & unmapped detection
  • Working capital & ratio computation
  • Flow explanation dictionary for AI agent reasoning

Georgian 1C Chart of Accounts hierarchy:
  Class 1: Current Assets      Class 5: Equity
  Class 2: Noncurrent Assets   Class 6: Revenue
  Class 3: Current Liabilities Class 7: Expenses (71=COGS, 73=Selling, 74=Admin)
  Class 4: Noncurrent Liabs    Class 8: Non-operating  Class 9: Other P&L
"""
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import re
import logging

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# ACCOUNT CLASS RULES — first-principles knowledge
# ══════════════════════════════════════════════════════════════

ACCOUNT_CLASS_RULES: Dict[str, Dict] = {
    "1": {"statement": "BS", "category": "Current Assets",        "side": "asset",     "sub": "current",    "bs_side": "asset"},
    "2": {"statement": "BS", "category": "Noncurrent Assets",     "side": "asset",     "sub": "noncurrent", "bs_side": "asset"},
    "3": {"statement": "BS", "category": "Current Liabilities",   "side": "liability", "sub": "current",    "bs_side": "liability"},
    "4": {"statement": "BS", "category": "Noncurrent Liabilities","side": "liability", "sub": "noncurrent", "bs_side": "liability"},
    "5": {"statement": "BS", "category": "Equity",                "side": "equity",    "sub": "equity",     "bs_side": "equity"},
    "6": {"statement": "PL", "category": "Revenue",               "side": "income",    "pl_line": "Revenue"},
    "7": {"statement": "PL", "category": "Expenses",              "side": "expense",   "pl_line": "COGS"},
    "8": {"statement": "PL", "category": "Non-operating",         "side": "expense",   "pl_line": "Other"},
    "9": {"statement": "PL", "category": "Other P&L",             "side": "expense",   "pl_line": "Other"},
}

# Sub-class rules for Class 7 — expenses need finer categorization
EXPENSE_SUBCLASS_RULES: Dict[str, Dict] = {
    "71": {"pl_line": "COGS",    "label": "Cost of Sales",            "label_ka": "რეალიზებული პროდუქციის თვითღირებულება"},
    "72": {"pl_line": "SGA",     "label": "Labour & HR Costs",        "label_ka": "შრომითი ხარჯები",       "sub": "Labour"},
    "73": {"pl_line": "SGA",     "label": "Selling Expenses",         "label_ka": "გაყიდვების ხარჯები",    "sub": "Selling"},
    "74": {"pl_line": "DA",      "label": "General & Admin (incl. D&A)", "label_ka": "ზოგადი ადმინისტრაციული", "sub": "Admin"},
    "75": {"pl_line": "Finance", "label": "Finance Expense",          "label_ka": "ფინანსური ხარჯი"},
    "76": {"pl_line": "Finance", "label": "Finance Income",           "label_ka": "ფინანსური შემოსავალი",   "side": "income"},
    "77": {"pl_line": "Tax",     "label": "Income Tax",               "label_ka": "მოგების გადასახადი"},
}

# Sub-class rules for Class 8 — non-operating items
NON_OPERATING_SUBCLASS_RULES: Dict[str, Dict] = {
    "82": {"pl_line": "Finance", "label": "Interest & FX",            "label_ka": "პროცენტი და საკურსო"},
    "83": {"pl_line": "Other",   "label": "Non-operating Gains/Losses","label_ka": "არასაოპერაციო"},
    "84": {"pl_line": "Other",   "label": "Extraordinary Items",      "label_ka": "საგანგებო მუხლები"},
}

# Key account codes with specific meanings
KEY_ACCOUNTS: Dict[str, Dict] = {
    "1610": {"label": "Inventories",           "label_ka": "მარაგები",            "flow": "inventory"},
    "1411": {"label": "Trade Receivables",     "label_ka": "სავაჭრო მოთხოვნები",   "flow": "working_capital"},
    "1290": {"label": "Cash in Transit",       "label_ka": "ფული გზაში",          "flow": "cash"},
    "6110": {"label": "Sales Revenue",         "label_ka": "გაყიდვების შემოსავალი","flow": "revenue"},
    "6120": {"label": "Sales Returns",         "label_ka": "დაბრუნებები",          "flow": "revenue", "contra": True},
    "7110": {"label": "Cost of Goods Sold",    "label_ka": "თვითღირებულება",       "flow": "cogs"},
    "7310": {"label": "Selling Expenses",      "label_ka": "გაყიდვების ხარჯები",   "flow": "selling"},
    "7410": {"label": "Admin Expenses",        "label_ka": "ადმინისტრაციული",      "flow": "admin"},
    "8220": {"label": "Interest Expense",      "label_ka": "საპროცენტო ხარჯი",     "flow": "finance"},
    "5330": {"label": "Retained Earnings (P&L)","label_ka": "გაუნაწილებელი მოგება", "flow": "equity"},
    "5420": {"label": "Revaluation Reserve",   "label_ka": "გადაფასების რეზერვი",   "flow": "equity"},
}


# ══════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════

@dataclass
class AccountClassification:
    """Result of classifying an account code through the hierarchy."""
    raw_code: str
    normalized_code: str = ""
    matched_prefix: Optional[str] = None
    match_level: str = "unmapped"  # exact | parent | root | class | unmapped
    statement: Optional[str] = None  # BS | PL
    category: Optional[str] = None
    side: Optional[str] = None  # asset | liability | equity | income | expense
    pl_line: Optional[str] = None  # Revenue | COGS | SGA | DA | Finance | Tax | Other
    label_en: Optional[str] = None
    label_ka: Optional[str] = None
    sub: Optional[str] = None  # current | noncurrent | equity | Selling | Admin | Labour
    is_contra: bool = False
    confidence: float = 0.0  # 0.0 to 1.0
    source: str = ""
    key_account_info: Optional[Dict] = None  # extra info for key accounts

    def to_dict(self) -> Dict:
        d = asdict(self)
        d = {k: v for k, v in d.items() if v is not None and v != "" and v != 0.0 and v is not False}
        return d


@dataclass
class FinancialFlowAnalysis:
    """Complete financial flow analysis for a dataset."""
    dataset_id: int
    period: str = "Unknown"
    currency: str = "GEL"

    # Account coverage
    total_accounts: int = 0
    mapped_accounts: int = 0
    unmapped_accounts: int = 0
    coverage_pct: float = 0.0
    unmapped_codes: List[Dict] = field(default_factory=list)

    # Revenue flow: 6110 → 6120 → Net
    gross_revenue: float = 0.0
    returns_allowances: float = 0.0
    net_revenue: float = 0.0
    revenue_by_segment: Dict[str, float] = field(default_factory=dict)

    # COGS formation: 1610 → 7110
    inventory_opening: float = 0.0
    inventory_closing: float = 0.0
    inventory_credit_turnover: float = 0.0  # 1610 credit = outflows
    cogs_col6_total: float = 0.0
    cogs_col7310_total: float = 0.0
    cogs_col8230_total: float = 0.0
    cogs_breakdown_total: float = 0.0  # from COGSItem records
    cogs_tb_71xx_debit: float = 0.0    # from Trial Balance 71xx
    cogs_variance_pct: float = 0.0
    cogs_reconciled: bool = False

    # Operating expenses: 73xx + 74xx
    selling_expenses_73xx: float = 0.0
    admin_expenses_74xx: float = 0.0
    total_opex: float = 0.0

    # Financial burden: 8220
    interest_expense: float = 0.0
    fx_gains_losses: float = 0.0

    # P&L waterfall
    gross_margin: float = 0.0
    ebitda: float = 0.0
    net_income: float = 0.0

    # Balance sheet identity: A = L + E
    total_assets: float = 0.0
    total_current_assets: float = 0.0
    total_noncurrent_assets: float = 0.0
    total_liabilities: float = 0.0
    total_current_liabilities: float = 0.0
    total_noncurrent_liabilities: float = 0.0
    total_equity: float = 0.0
    bs_balanced: bool = False
    bs_variance: float = 0.0

    # Working capital
    inventory_balance: float = 0.0
    receivables_balance: float = 0.0
    prepayments_balance: float = 0.0
    payables_balance: float = 0.0
    working_capital: float = 0.0
    current_ratio: float = 0.0
    inventory_turnover: float = 0.0

    # Warnings & data quality
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    # Internal: TB-derived revenue (used as fallback when no RevenueItems)
    _tb_revenue_gross: float = 0.0
    _tb_revenue_returns: float = 0.0

    def to_dict(self) -> Dict:
        d = asdict(self)
        # Remove internal fields from public output
        d.pop("_tb_revenue_gross", None)
        d.pop("_tb_revenue_returns", None)
        return d


# ══════════════════════════════════════════════════════════════
# ACCOUNTING INTELLIGENCE SERVICE
# ══════════════════════════════════════════════════════════════

class AccountingIntelligence:
    """
    Central accounting intelligence engine.

    Implements hierarchical COA mapping with 5-level fallback,
    financial flow reasoning, and dataset-level analysis.

    The system REASONS about accounting data using:
    1. Georgian Chart of Accounts structure
    2. Parent-child account hierarchy
    3. Account code series logic
    4. Cross-statement flow analysis
    5. Reconciliation & variance detection
    """

    def __init__(self, coa_dict: Optional[Dict] = None):
        if coa_dict is None:
            from app.services.file_parser import GEORGIAN_COA
            coa_dict = GEORGIAN_COA
        self._coa = coa_dict

    # ──────────────────────────────────────────────
    # 1. HIERARCHICAL ACCOUNT CLASSIFICATION
    # ──────────────────────────────────────────────

    def classify_account(self, code: str) -> AccountClassification:
        """
        Classify an account code using 5-level hierarchical fallback.

        Mapping workflow (matches Georgian 1C accounting):
        1. Exact match — full code in COA (e.g., "7110" → COGS)
        2. Parent match — strip sub-account, try parent (e.g., "7110.01" → "7110")
        3. Root match — try first 2-3 digits (e.g., "711" → "71")
        4. Class prefix — use account class rules (e.g., "7" → Expenses)
        5. Unmapped — flag for review

        This is the core of the VALIDATION RULE:
        IF(MAPPING_GRP = ""; VLOOKUP(LEFT(ACCOUNT_CODE, 2), ACCOUNT_GROUPS, 2), MAPPING_GRP)
        """
        result = AccountClassification(raw_code=code)

        if not code:
            result.source = "Empty account code"
            return result

        raw = str(code).strip()
        # Normalize: extract digits for prefix matching
        clean_digits = re.sub(r'[^0-9]', '', raw)
        result.normalized_code = clean_digits

        if not clean_digits:
            result.source = "No numeric content in code"
            return result

        # Check if this is a KEY_ACCOUNT with special meaning
        for key_prefix, key_info in KEY_ACCOUNTS.items():
            if clean_digits.startswith(re.sub(r'[^0-9]', '', key_prefix)):
                result.key_account_info = key_info

        # ── Level 1-3: COA lookup with decreasing prefix length ──
        # For dotted codes like "7110.01/1", we try the full digits first,
        # then progressively shorter prefixes.
        max_len = min(len(clean_digits), 6)  # up to 6 digits
        for length in range(max_len, 0, -1):
            prefix = clean_digits[:length]
            if prefix in self._coa:
                entry = self._coa[prefix]
                self._fill_from_coa(result, entry, prefix)

                if length == len(clean_digits):
                    result.match_level = "exact"
                    result.confidence = 1.0
                elif length >= 4:
                    result.match_level = "parent"
                    result.confidence = 0.95
                elif length >= 3:
                    result.match_level = "root"
                    result.confidence = 0.90
                else:
                    result.match_level = "root"
                    result.confidence = 0.85

                result.source = f"COA match on prefix '{prefix}'"

                # Refine with subclass rules (class 7 expenses or class 8 non-operating)
                two_digit = clean_digits[:2] if len(clean_digits) >= 2 else ""
                if two_digit in EXPENSE_SUBCLASS_RULES:
                    sub_rule = EXPENSE_SUBCLASS_RULES[two_digit]
                    result.pl_line = sub_rule["pl_line"]
                    result.label_en = result.label_en or sub_rule["label"]
                    result.label_ka = result.label_ka or sub_rule.get("label_ka")
                    if sub_rule.get("sub"):
                        result.sub = sub_rule["sub"]
                    if sub_rule.get("side"):
                        result.side = sub_rule["side"]
                elif two_digit in NON_OPERATING_SUBCLASS_RULES:
                    sub_rule = NON_OPERATING_SUBCLASS_RULES[two_digit]
                    result.pl_line = sub_rule["pl_line"]
                    result.label_en = result.label_en or sub_rule["label"]
                    result.label_ka = result.label_ka or sub_rule.get("label_ka")

                return result

        # ── Level 4: Account class prefix rules ──
        first_digit = clean_digits[0]
        if first_digit in ACCOUNT_CLASS_RULES:
            class_rule = ACCOUNT_CLASS_RULES[first_digit]
            result.statement = class_rule["statement"]
            result.category = class_rule["category"]
            result.side = class_rule["side"]
            result.sub = class_rule.get("sub")
            result.pl_line = class_rule.get("pl_line")
            result.match_level = "class"
            result.confidence = 0.5
            result.source = f"Account class rule for class {first_digit}"

            # Sub-class refinement for class 7 expenses
            if len(clean_digits) >= 2:
                two_digit = clean_digits[:2]
                if two_digit in EXPENSE_SUBCLASS_RULES:
                    sub = EXPENSE_SUBCLASS_RULES[two_digit]
                    result.pl_line = sub["pl_line"]
                    result.label_en = sub["label"]
                    result.label_ka = sub.get("label_ka")
                    result.sub = sub.get("sub")
                    if sub.get("side"):
                        result.side = sub["side"]
                    result.confidence = 0.7
                    result.source = f"Expense sub-class rule for prefix '{two_digit}'"

                # Class 8 non-operating refinement
                elif two_digit in NON_OPERATING_SUBCLASS_RULES:
                    sub = NON_OPERATING_SUBCLASS_RULES[two_digit]
                    result.pl_line = sub["pl_line"]
                    result.label_en = sub["label"]
                    result.label_ka = sub.get("label_ka")
                    result.confidence = 0.7
                    result.source = f"Non-operating sub-class rule for prefix '{two_digit}'"

            return result

        # ── Level 5: Unmapped ──
        result.match_level = "unmapped"
        result.confidence = 0.0
        result.source = "No match found — Review Required"
        return result

    def _fill_from_coa(self, result: AccountClassification, entry: Dict, prefix: str):
        """Fill classification fields from a GEORGIAN_COA dict entry."""
        result.matched_prefix = prefix

        # The COA dict may have P&L and/or BS keys
        if entry.get("pl") or entry.get("side") in ("expense", "income"):
            result.statement = "PL"
            result.label_en = entry.get("pl")
            result.label_ka = entry.get("pl_ka")
            result.side = entry.get("side", "expense")
            result.pl_line = entry.get("pl_line")
            result.sub = entry.get("sub")

        if entry.get("bs") or entry.get("bs_side"):
            result.statement = result.statement or "BS"
            result.label_en = result.label_en or entry.get("bs")
            result.label_ka = result.label_ka or entry.get("bs_ka")
            result.side = result.side or entry.get("bs_side")
            result.sub = result.sub or entry.get("bs_sub")
            result.category = entry.get("bs")

        result.is_contra = entry.get("contra", False)

    # ──────────────────────────────────────────────
    # 2. FINANCIAL FLOW ANALYSIS
    # ──────────────────────────────────────────────

    async def analyze_dataset_flows(
        self, db: AsyncSession, dataset_id: int
    ) -> FinancialFlowAnalysis:
        """
        Full financial flow analysis for a dataset.

        Reads TB, BS, Revenue, COGS items and reasons about:
        - Account coverage (mapped vs unmapped)
        - Inventory → COGS flow (1610 → 7110)
        - Revenue composition (gross 6110 → returns 6120 → net)
        - COGS formation (col6 + col7310 + col8230 vs TB 71xx)
        - Operating expense structure (73xx + 74xx)
        - Financial burden (8220 interest)
        - Balance sheet identity (A = L + E)
        - Working capital & ratios
        """
        from app.models.all_models import (
            TrialBalanceItem, BalanceSheetItem,
            RevenueItem, COGSItem, GAExpenseItem, Dataset
        )

        # Get dataset info
        ds = (await db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )).scalar_one_or_none()

        analysis = FinancialFlowAnalysis(
            dataset_id=dataset_id,
            period=ds.period if ds else "Unknown",
            currency=ds.currency if ds else "GEL",
        )

        # ── Fetch all data sources ──
        tb_items = (await db.execute(
            select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == dataset_id)
        )).scalars().all()

        rev_items = (await db.execute(
            select(RevenueItem).where(RevenueItem.dataset_id == dataset_id)
        )).scalars().all()

        cogs_items = (await db.execute(
            select(COGSItem).where(COGSItem.dataset_id == dataset_id)
        )).scalars().all()

        ga_items = (await db.execute(
            select(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id)
        )).scalars().all()

        # ── Account coverage analysis ──
        all_codes = set()
        mapped_codes = set()
        unmapped_list = []

        for tb in tb_items:
            code = tb.account_code or ""
            if not code or (tb.hierarchy_level or 0) > 1:
                continue  # Only analyze top-level accounts
            all_codes.add(code)
            classification = self.classify_account(code)
            if classification.match_level != "unmapped":
                mapped_codes.add(code)
            else:
                total_turnover = abs(float(tb.turnover_debit or 0)) + abs(float(tb.turnover_credit or 0))
                if total_turnover > 0:  # Only flag accounts with actual movement
                    unmapped_list.append({
                        "code": code,
                        "name": tb.account_name or "",
                        "turnover_debit": round(float(tb.turnover_debit or 0), 2),
                        "turnover_credit": round(float(tb.turnover_credit or 0), 2),
                        "total_turnover": round(total_turnover, 2),
                        "suggestion": self._suggest_category(code, tb.account_name),
                    })

        analysis.total_accounts = len(all_codes)
        analysis.mapped_accounts = len(mapped_codes)
        analysis.unmapped_accounts = len(all_codes) - len(mapped_codes)
        analysis.coverage_pct = round(
            len(mapped_codes) / len(all_codes) * 100, 1
        ) if all_codes else 100.0
        analysis.unmapped_codes = sorted(
            unmapped_list, key=lambda x: -x["total_turnover"]
        )[:20]  # Top 20 by turnover

        # ── Trial Balance flow analysis ──
        for tb in tb_items:
            code = tb.account_code or ""
            level = tb.hierarchy_level or 0
            if level != 1:
                continue  # Only top-level for aggregation

            td = float(tb.turnover_debit or 0)
            tc = float(tb.turnover_credit or 0)
            od = float(tb.opening_debit or 0)
            oc = float(tb.opening_credit or 0)
            cd = float(tb.closing_debit or 0)
            cc = float(tb.closing_credit or 0)
            closing_net = cd - cc

            classification = self.classify_account(code)

            # Inventory flow (1610)
            if code == "1610" or code.startswith("1610"):
                analysis.inventory_opening = od - oc
                analysis.inventory_closing = cd - cc
                analysis.inventory_credit_turnover = tc
                analysis.inventory_balance = cd - cc

            # Revenue from TB (6xxx) — credit turnover = gross revenue
            if code.startswith("611") or code == "6110":
                analysis._tb_revenue_gross += tc
            if code.startswith("612") or code == "6120":
                analysis._tb_revenue_returns += td

            # COGS from TB (71xx)
            if code.startswith("71"):
                analysis.cogs_tb_71xx_debit += td

            # Selling expenses (73xx)
            if code.startswith("73"):
                analysis.selling_expenses_73xx += td

            # Admin expenses (74xx)
            if code.startswith("74"):
                analysis.admin_expenses_74xx += td

            # Interest expense (8220)
            if code.startswith("8220") or code == "8220":
                analysis.interest_expense += td

            # Trade receivables (14xx)
            if code.startswith("14"):
                analysis.receivables_balance += closing_net

            # Prepayments (15xx, 17xx)
            if code.startswith("15") or code.startswith("17"):
                analysis.prepayments_balance += closing_net

            # Payables (31xx)
            if code.startswith("31"):
                analysis.payables_balance += abs(closing_net)

            # Balance sheet aggregation
            if classification.side == "asset":
                analysis.total_assets += closing_net
                if classification.sub == "current":
                    analysis.total_current_assets += closing_net
                else:
                    analysis.total_noncurrent_assets += closing_net
            elif classification.side == "liability":
                analysis.total_liabilities += abs(closing_net)
                if classification.sub == "current":
                    analysis.total_current_liabilities += abs(closing_net)
                else:
                    analysis.total_noncurrent_liabilities += abs(closing_net)
            elif classification.side == "equity":
                analysis.total_equity += abs(closing_net)

        # ── Revenue analysis (from Revenue items, fallback to TB 6xxx) ──
        for r in rev_items:
            analysis.gross_revenue += float(r.gross or 0)
            analysis.net_revenue += float(r.net or 0)
            seg = r.segment or "Other"
            analysis.revenue_by_segment[seg] = (
                analysis.revenue_by_segment.get(seg, 0) + float(r.net or 0)
            )
        analysis.returns_allowances = analysis.gross_revenue - analysis.net_revenue

        # Fallback: if no RevenueItems exist, derive revenue from TB 6xxx accounts
        if analysis.gross_revenue == 0 and analysis._tb_revenue_gross > 0:
            analysis.gross_revenue = analysis._tb_revenue_gross
            analysis.returns_allowances = analysis._tb_revenue_returns
            analysis.net_revenue = analysis._tb_revenue_gross - analysis._tb_revenue_returns
            if analysis.net_revenue > 0:
                analysis.revenue_by_segment["Total (from TB)"] = analysis.net_revenue
            logger.info(f"Revenue derived from TB 6xxx: gross={analysis.gross_revenue:,.0f}, "
                        f"returns={analysis.returns_allowances:,.0f}, net={analysis.net_revenue:,.0f}")

        # ── COGS formation (from COGS items) ──
        for c in cogs_items:
            analysis.cogs_col6_total += float(c.col6_amount or 0)
            analysis.cogs_col7310_total += float(c.col7310_amount or 0)
            analysis.cogs_col8230_total += float(c.col8230_amount or 0)
            analysis.cogs_breakdown_total += float(c.total_cogs or 0)

        # COGS reconciliation
        if analysis.cogs_breakdown_total > 0 and analysis.cogs_tb_71xx_debit > 0:
            max_val = max(analysis.cogs_breakdown_total, analysis.cogs_tb_71xx_debit)
            analysis.cogs_variance_pct = round(
                abs(analysis.cogs_breakdown_total - analysis.cogs_tb_71xx_debit) / max_val * 100, 2
            )
            analysis.cogs_reconciled = analysis.cogs_variance_pct < 2.0

        # ── Operating expenses ──
        analysis.total_opex = analysis.selling_expenses_73xx + analysis.admin_expenses_74xx

        # ── P&L waterfall ──
        # Use COGS breakdown if available, otherwise fall back to TB 71xx debit
        effective_cogs = analysis.cogs_breakdown_total if analysis.cogs_breakdown_total > 0 else analysis.cogs_tb_71xx_debit
        analysis.gross_margin = analysis.net_revenue - effective_cogs
        analysis.ebitda = analysis.gross_margin - analysis.total_opex
        analysis.net_income = analysis.ebitda - analysis.interest_expense - analysis.fx_gains_losses

        # ── Balance sheet identity ──
        analysis.bs_variance = round(
            abs(analysis.total_assets - analysis.total_liabilities - analysis.total_equity), 2
        )
        analysis.bs_balanced = analysis.bs_variance < 1.0

        # ── Working capital ──
        analysis.working_capital = analysis.total_current_assets - analysis.total_current_liabilities
        if analysis.total_current_liabilities > 0:
            analysis.current_ratio = round(
                analysis.total_current_assets / analysis.total_current_liabilities, 2
            )
        if analysis.cogs_breakdown_total > 0 and analysis.inventory_balance > 0:
            analysis.inventory_turnover = round(
                analysis.cogs_breakdown_total / analysis.inventory_balance, 2
            )

        # ── Warnings ──
        if analysis.unmapped_accounts > 0:
            analysis.warnings.append(
                f"{analysis.unmapped_accounts} accounts unmapped "
                f"({100 - analysis.coverage_pct:.1f}% of total). "
                f"Top unmapped: {', '.join(u['code'] for u in analysis.unmapped_codes[:5])}"
            )
        if not analysis.bs_balanced and analysis.total_assets > 0:
            analysis.warnings.append(
                f"Balance Sheet imbalance: Assets={analysis.total_assets:,.0f}, "
                f"L+E={analysis.total_liabilities + analysis.total_equity:,.0f}, "
                f"variance={analysis.bs_variance:,.0f}"
            )
        if analysis.cogs_variance_pct > 2 and analysis.cogs_breakdown_total > 0:
            analysis.warnings.append(
                f"COGS variance {analysis.cogs_variance_pct:.1f}%: "
                f"Breakdown={analysis.cogs_breakdown_total:,.0f} vs TB 71xx={analysis.cogs_tb_71xx_debit:,.0f}"
            )
        if analysis.inventory_turnover > 0 and analysis.inventory_turnover < 1.0:
            analysis.info.append(
                f"Inventory turnover = {analysis.inventory_turnover:.2f}x "
                f"(below 1.0 means slow stock rotation — capital tied up in inventory)"
            )
        if analysis.net_revenue > 0:
            interest_pct = analysis.interest_expense / analysis.net_revenue * 100
            if interest_pct > 5:
                analysis.warnings.append(
                    f"High interest burden: {interest_pct:.1f}% of net revenue "
                    f"(₾{analysis.interest_expense:,.0f} / ₾{analysis.net_revenue:,.0f})"
                )
        if analysis.gross_margin < 0:
            analysis.warnings.append(
                f"NEGATIVE gross margin: ₾{analysis.gross_margin:,.0f}. "
                f"COGS exceeds revenue — review pricing strategy."
            )

        # ── Info ──
        if analysis.inventory_credit_turnover > 0 and analysis.cogs_breakdown_total > 0:
            cogs_pct = analysis.cogs_breakdown_total / analysis.inventory_credit_turnover * 100
            analysis.info.append(
                f"COGS = {cogs_pct:.1f}% of 1610 credit turnover. "
                f"Remaining {100 - cogs_pct:.1f}% = internal warehouse transfers (1610→1610)"
            )
        if analysis.net_revenue > 0 and analysis.cogs_breakdown_total > 0:
            margin_pct = (analysis.net_revenue - analysis.cogs_breakdown_total) / analysis.net_revenue * 100
            analysis.info.append(f"Gross margin: {margin_pct:.1f}%")

        return analysis

    def _suggest_category(self, code: str, name: str) -> str:
        """Suggest a category for unmapped accounts based on name heuristics."""
        name_lower = (name or "").lower()
        code_clean = re.sub(r'[^0-9]', '', str(code))

        # Georgian keyword matching
        if any(kw in name_lower for kw in ["სესხ", "loan", "credit", "კრედიტ"]):
            return "Loans / Financial"
        if any(kw in name_lower for kw in ["%", "პროცენტ", "interest"]):
            return "Interest Expense"
        if any(kw in name_lower for kw in ["მარაგ", "inventory", "საწყობ"]):
            return "Inventory"
        if any(kw in name_lower for kw in ["შემოსავ", "revenue", "გაყიდ"]):
            return "Revenue"
        if any(kw in name_lower for kw in ["ხარჯ", "expense", "cost"]):
            return "Expense"
        if any(kw in name_lower for kw in ["ამორტ", "deprec", "ცვეთა"]):
            return "Depreciation & Amortization"

        # Fallback to first-digit rules
        if code_clean and code_clean[0] in ACCOUNT_CLASS_RULES:
            return ACCOUNT_CLASS_RULES[code_clean[0]]["category"]

        return "Uncategorized — needs review"

    # ──────────────────────────────────────────────
    # 3. FLOW EXPLANATION DICTIONARY
    # ──────────────────────────────────────────────

    def explain_financial_flow(self, flow_type: str) -> Dict:
        """
        Explain a financial flow in accounting terms.
        Used by the AI agent to reason about and explain data to users.
        """
        flows = {
            "inventory_to_cogs": {
                "title": "Inventory → COGS Flow",
                "title_ka": "მარაგი → თვითღირებულება",
                "description": (
                    "When goods are sold, inventory (Account 1610) is credited and "
                    "COGS (Account 7110) is debited. The credit on 1610 shows the total "
                    "inventory outflow, but not all of it is COGS — some is internal "
                    "warehouse transfers (1610→1610)."
                ),
                "description_ka": (
                    "პროდუქციის გაყიდვისას მარაგის ანგარიშს (1610) კრედიტდება და "
                    "თვითღირებულება (7110) დებეტდება. 1610-ის კრედიტი აჩვენებს "
                    "მთლიან მარაგის გასვლას, მაგრამ ყველაფერი არ არის COGS — "
                    "ნაწილი შიდა გადაადგილებაა (1610→1610)."
                ),
                "source_accounts": ["1610"],
                "destination_accounts": ["7110", "7310"],
                "journal_entry": "Dr 7110 (COGS)  /  Cr 1610 (Inventory)",
                "verification": (
                    "TB 1610 credit turnover ≈ TB 71xx debit turnover + internal transfers. "
                    "COGS Breakdown total should match TB 71xx debit (tolerance < 2%)."
                ),
                "key_metric": "Inventory Turnover = COGS / Avg Inventory",
            },
            "revenue_formation": {
                "title": "Revenue Formation",
                "title_ka": "შემოსავლების ფორმირება",
                "description": (
                    "Revenue accumulates on 61xx series accounts. "
                    "Gross Revenue (6110 credit) minus Sales Returns (6120 debit) = Net Revenue. "
                    "VAT is excluded from net figures. Intercompany sales are eliminated in consolidation."
                ),
                "description_ka": (
                    "შემოსავალი იკრიბება 61xx სერიის ანგარიშებზე. "
                    "მთლიანი შემოსავალი (6110 კრედიტი) - დაბრუნებები (6120) = წმინდა შემოსავალი. "
                    "დღგ გამოიკლება. შიდა ჯგუფური გაყიდვები ელიმინირდება."
                ),
                "accounts": ["6110", "6120", "6130", "6140"],
                "verification": (
                    "Revenue Breakdown sheet net total should match TB 6xxx credit turnovers."
                ),
            },
            "cogs_formation": {
                "title": "COGS Formation",
                "title_ka": "თვითღირებულების ფორმირება",
                "description": (
                    "COGS = Col K (Account 1610 outflow to sales) + "
                    "Col L (Account 7310 selling expenses) + Col O (Account 8230 other losses). "
                    "This 3-column breakdown comes from the COGS Breakdown sheet. "
                    "The total should reconcile with TB 71xx debit turnover."
                ),
                "description_ka": (
                    "თვითღირებულება = სვეტი K (1610 → გაყიდვა) + "
                    "სვეტი L (7310 გაყიდვების ხარჯი) + სვეტი O (8230 სხვა). "
                    "ეს სამსვეტიანი დაშლა მოდის COGS Breakdown ფურცლიდან."
                ),
                "formula": "COGS = col6 (1610→Sales) + col7310 (Selling) + col8230 (Other)",
                "accounts": ["1610", "7310", "8230"],
                "verification": (
                    "Sum of col6+col7310+col8230 from COGS Breakdown ≈ TB 71xx debit turnover. "
                    "Tolerance < 2% = match, 2-5% = warning, > 5% = critical mismatch."
                ),
            },
            "operating_expenses": {
                "title": "Operating Expense Structure",
                "title_ka": "საოპერაციო ხარჯების სტრუქტურა",
                "description": (
                    "OpEx = Selling Expenses (73xx) + Admin Expenses (74xx). "
                    "73xx includes salaries, rent, utilities for gas stations. "
                    "74xx includes management, insurance, consulting. "
                    "These reduce operating profit (EBITDA) below gross margin."
                ),
                "description_ka": (
                    "საოპერაციო ხარჯი = გაყიდვების ხარჯი (73xx) + ადმინისტრაციული (74xx). "
                    "73xx მოიცავს ხელფასებს, იჯარას, კომუნალურს. "
                    "74xx მოიცავს მენეჯმენტს, დაზღვევას."
                ),
                "accounts": ["73xx", "74xx"],
                "formula": "EBITDA = Gross Margin - Selling (73xx) - Admin (74xx)",
            },
            "financial_burden": {
                "title": "Financial Burden",
                "title_ka": "ფინანსური წნეხი",
                "description": (
                    "Interest expense (8220) and FX gains/losses reduce net income. "
                    "Account 8220 contains loan interest. FX differences appear in "
                    "8220.01.1 sub-accounts. If interest > 5% of revenue, the company "
                    "has a heavy credit burden."
                ),
                "description_ka": (
                    "საპროცენტო ხარჯი (8220) და საკურსო სხვაობები ამცირებს წმინდა მოგებას. "
                    "თუ პროცენტი > შემოსავლის 5%, კომპანიას აქვს მძიმე საკრედიტო ტვირთი."
                ),
                "accounts": ["8220", "8220.01.1"],
            },
            "working_capital": {
                "title": "Working Capital Cycle",
                "title_ka": "საბრუნავი კაპიტალის ციკლი",
                "description": (
                    "Working Capital = Inventory (16xx) + Receivables (14xx) + "
                    "Prepayments (15xx, 17xx) - Payables (31xx) - Accrued (34xx). "
                    "Shows how much cash is 'tied up' in operations. "
                    "A high inventory balance with low turnover means capital is frozen."
                ),
                "description_ka": (
                    "საბრუნავი კაპიტალი = მარაგები (16xx) + მოთხოვნები (14xx) + "
                    "ავანსები (15xx, 17xx) - ვალდებულებები (31xx). "
                    "აჩვენებს რამდენი ფული არის 'გაყინული' ოპერაციებში."
                ),
                "accounts": ["16xx", "14xx", "15xx", "17xx", "31xx", "33xx", "34xx"],
                "key_metrics": [
                    "Current Ratio = Current Assets / Current Liabilities",
                    "Inventory Turnover = COGS / Avg Inventory",
                    "Cash-to-Cash = Days Inventory + Days Receivable - Days Payable",
                ],
            },
            "bs_identity": {
                "title": "Balance Sheet Identity",
                "title_ka": "ბალანსის იგივეობა",
                "description": (
                    "Assets (1xxx + 2xxx) = Liabilities (3xxx + 4xxx) + Equity (5xxx). "
                    "If they don't balance, either an account is unmapped or a trial "
                    "balance entry is missing. Account 5330 holds P&L results (retained earnings)."
                ),
                "description_ka": (
                    "აქტივები (1xxx + 2xxx) = ვალდებულებები (3xxx + 4xxx) + კაპიტალი (5xxx). "
                    "თუ არ ემთხვევა, ან ანგარიში არ არის შესაბამისობაში ან ბრუნვა გამორჩენილია."
                ),
                "formula": "A = L + E",
                "verification": (
                    "If variance > 0, check for unmapped accounts in classes 1-5. "
                    "5330 (Retained Earnings) must include current period P&L result."
                ),
            },
            "intercompany": {
                "title": "Intercompany Eliminations",
                "title_ka": "შიდა ჯგუფური ელიმინაციები",
                "description": (
                    "Revenue and COGS from intercompany transactions (e.g., internal "
                    "services, fuel transfers between entities) must be eliminated in "
                    "consolidated reports. The 'eliminated' flag in Revenue Breakdown "
                    "marks these items. If not eliminated, revenue is artificially inflated."
                ),
                "description_ka": (
                    "შიდა ჯგუფური გარიგებების შემოსავალი და ხარჯი ელიმინირდება "
                    "კონსოლიდირებულ ანგარიშგებაში."
                ),
            },

            # ── Transparency Layer Flow Explanations ──────────────────
            "pl_waterfall": {
                "title": "P&L Waterfall Construction",
                "title_ka": "მოგება-ზარალის კასკადური სტრუქტურა",
                "description": (
                    "The P&L is built as a waterfall: Revenue (6xxx accounts credit) "
                    "minus COGS (71xx debit) = Gross Profit. Gross Profit minus "
                    "Operating Expenses (G&A 73xx+74xx) = EBITDA. EBITDA minus D&A (7410) = EBIT. "
                    "EBIT ± Finance items (8220) = EBT. EBT minus Tax (77xx) = Net Profit. "
                    "Each line is sourced from specific account series in the Trial Balance."
                ),
                "description_ka": (
                    "მოგება-ზარალი აგებულია კასკადურად: შემოსავალი (6xxx კრედიტი) "
                    "მინუს თვითღირებულება (71xx დებეტი) = მთლიანი მოგება. "
                    "მთლიანი მოგება მინუს საოპერაციო ხარჯი (73xx+74xx) = EBITDA. "
                    "EBITDA მინუს ცვეთა (7410) = EBIT. EBIT ± ფინანსური (8220) = EBT. "
                    "EBT მინუს გადასახადი (77xx) = წმინდა მოგება."
                ),
                "formula": "Revenue(6xxx) − COGS(71xx) = GP − OpEx(73xx,74xx) = EBITDA − D&A(7410) = EBIT ± Finance(8220) = EBT − Tax(77xx) = Net Profit",
                "accounts": ["6xxx", "71xx", "73xx", "74xx", "7410", "8220", "77xx"],
                "verification": (
                    "Each P&L line ties to specific account series in the Trial Balance. "
                    "Revenue = TB 6xxx credit turnovers. COGS = COGS Breakdown sheet or TB 71xx debit. "
                    "G&A = GAExpenseItem records. Finance = 8220 accounts."
                ),
            },
            "balance_sheet_structure": {
                "title": "Balance Sheet Construction",
                "title_ka": "ბალანსის აგება",
                "description": (
                    "The Balance Sheet follows the fundamental accounting identity: "
                    "Assets = Liabilities + Equity. Assets come from account classes 1 (current) "
                    "and 2 (non-current). Liabilities from classes 3 (current) and 4 (non-current). "
                    "Equity from class 5. Each account's closing balance (debit minus credit) "
                    "is classified by IFRS line using the GEORGIAN_COA mapping. "
                    "If BS doesn't balance, either an account is unmapped or the current period "
                    "P&L result hasn't been added to Retained Earnings (5330)."
                ),
                "description_ka": (
                    "ბალანსი ეფუძნება ბუღალტრული იგივეობას: აქტივები = ვალდებულებები + კაპიტალი. "
                    "აქტივები მოდის კლასებიდან 1 (მიმდინარე) და 2 (გრძელვადიანი). "
                    "ვალდებულებები — 3 (მიმდინარე) და 4 (გრძელვადიანი). კაპიტალი — 5. "
                    "თუ ბალანსი არ ემთხვევა, ან ანგარიში არ არის შესაბამისობაში, "
                    "ან მიმდინარე პერიოდის მოგება არ დამატებია გაუნაწილებელ მოგებაში (5330)."
                ),
                "formula": "Assets (Class 1+2) = Liabilities (Class 3+4) + Equity (Class 5)",
                "accounts": ["1xxx", "2xxx", "3xxx", "4xxx", "5xxx"],
                "verification": (
                    "A = L + E must hold within ₾1 tolerance. If variance exists, "
                    "check unmapped accounts and whether current P&L result is included in equity."
                ),
            },
            "revenue_recognition": {
                "title": "Revenue Recognition & Breakdown",
                "title_ka": "შემოსავლების აღიარება და დაშლა",
                "description": (
                    "Revenue is recognized from two sources: (1) the Revenue Breakdown sheet "
                    "with per-product Gross, VAT, and Net amounts, or (2) Trial Balance "
                    "6xxx credit turnovers as fallback. Net Revenue = Gross Revenue (6110) "
                    "minus Returns (6120) minus VAT. Products are classified into Wholesale "
                    "and Retail segments using the product classifier. Each product shows "
                    "its contribution as a percentage of total revenue."
                ),
                "description_ka": (
                    "შემოსავალი აღიარდება ორი წყაროდან: (1) შემოსავლების ცხრილი "
                    "პროდუქტების მიხედვით, ან (2) TB 6xxx კრედიტი. "
                    "წმინდა შემოსავალი = მთლიანი (6110) − დაბრუნებები (6120) − დღგ. "
                    "პროდუქტები კლასიფიცირდება საბითუმო და საცალო სეგმენტებად."
                ),
                "formula": "Net Revenue = Gross (6110) − Returns (6120) − VAT",
                "accounts": ["6110", "6120", "6130", "6140", "6149"],
                "verification": (
                    "Revenue Breakdown sheet net total should match TB 6xxx credit turnovers. "
                    "If no Revenue sheet exists, system derives revenue from TB 6xxx accounts."
                ),
            },
            "opex_classification": {
                "title": "Operating Expense Classification",
                "title_ka": "საოპერაციო ხარჯების კლასიფიკაცია",
                "description": (
                    "Operating expenses are classified into: Labour (72xx — salaries, pension), "
                    "Selling (73xx — distribution, fuel, marketing), Admin (74xx — rent, IT, "
                    "consulting), and D&A (7410 — depreciation & amortization). "
                    "Non-operating items like FX differences, CapEx, and VAT pass-through "
                    "are separated into dedicated buckets below the operating line. "
                    "Finance costs (bank commissions, interest) appear below EBITDA."
                ),
                "description_ka": (
                    "საოპერაციო ხარჯები კლასიფიცირდება: შრომითი (72xx), "
                    "გაყიდვების (73xx), ადმინისტრაციული (74xx), ცვეთა (7410). "
                    "არასაოპერაციო (საკურსო, CapEx, დღგ) გამოყოფილია ცალკე. "
                    "ფინანსური ხარჯი (საბანკო, პროცენტი) ჩანს EBITDA-ს ქვემოთ."
                ),
                "formula": "OpEx = Labour(72xx) + Selling(73xx) + Admin(74xx) + D&A(7410)",
                "accounts": ["72xx", "73xx", "74xx", "7410", "75xx", "82xx"],
                "verification": (
                    "G&A total from GAExpenseItem records should match TB 73xx+74xx debit turnovers. "
                    "Semantic classification validates cost_class labels against COA codes."
                ),
            },
            "dashboard_kpis": {
                "title": "Dashboard KPI Derivation",
                "title_ka": "დეშბორდის KPI-ების გამოთვლა",
                "description": (
                    "Dashboard KPIs are derived from the Income Statement engine: "
                    "Revenue comes from RevenueItem records (Revenue Breakdown sheet). "
                    "COGS comes from COGSItem records (COGS Breakdown sheet). "
                    "Gross Margin = Revenue − COGS. G&A from GAExpenseItem records. "
                    "EBITDA = Gross Profit − G&A − D&A. Wholesale and Retail margins "
                    "are calculated separately by segment. Budget comparisons use "
                    "BudgetLine records from the mapping sheet."
                ),
                "description_ka": (
                    "დეშბორდის KPI-ები გამოითვლება Income Statement-ის ძრავით: "
                    "შემოსავალი — RevenueItem ჩანაწერებიდან. თვითღირებულება — COGSItem. "
                    "მთლიანი მარჟა = შემოსავალი − COGS. G&A — GAExpenseItem. "
                    "EBITDA = მთლიანი მოგება − G&A − ცვეთა. საბითუმო და საცალო "
                    "მარჟები ცალ-ცალკე გამოითვლება."
                ),
                "formula": "Revenue(Rev Sheet) − COGS(COGS Sheet) = GP − G&A(TDSheet) = EBITDA",
                "accounts": ["6110-6149", "71xx", "73xx", "74xx"],
                "verification": (
                    "KPI values should reconcile with the P&L page. "
                    "Revenue = sum of RevenueItem.net. COGS = sum of COGSItem.total_cogs. "
                    "G&A = sum of GAExpenseItem.amount (excluding FINANCE/TAX/LABOUR special items)."
                ),
            },
        }

        if flow_type in flows:
            return flows[flow_type]

        return {
            "description": f"Unknown flow type: {flow_type}",
            "available_flows": list(flows.keys()),
        }

    # ──────────────────────────────────────────────
    # 4. ACCOUNT HIERARCHY BROWSER
    # ──────────────────────────────────────────────

    def get_account_hierarchy(self, prefix: str) -> List[Dict]:
        """
        Get all COA entries under a given prefix, organized hierarchically.
        E.g., prefix="71" returns all COGS-related accounts.
        """
        results = []
        clean_prefix = re.sub(r'[^0-9]', '', str(prefix))
        for code in sorted(self._coa.keys()):
            if code.startswith(clean_prefix):
                entry = self._coa[code]
                results.append({
                    "code": code,
                    "label_en": entry.get("pl") or entry.get("bs") or "",
                    "label_ka": entry.get("pl_ka") or entry.get("bs_ka") or "",
                    "depth": len(code) - len(clean_prefix),
                    "side": entry.get("side") or entry.get("bs_side") or "",
                    "pl_line": entry.get("pl_line", ""),
                    "sub": entry.get("sub", ""),
                })
        return results

    def get_all_class_rules(self) -> Dict:
        """Return the full set of classification rules for documentation/debugging."""
        return {
            "account_classes": ACCOUNT_CLASS_RULES,
            "expense_subclasses": EXPENSE_SUBCLASS_RULES,
            "non_operating_subclasses": NON_OPERATING_SUBCLASS_RULES,
            "key_accounts": KEY_ACCOUNTS,
        }


# ══════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETON
# ══════════════════════════════════════════════════════════════

accounting_intelligence = AccountingIntelligence()
