"""
TB → Financial Statements Converter — Accounting Rules Engine.

Converts a parsed Trial Balance into P&L (Income Statement) and Balance Sheet
using Georgian 1C COA classification rules and IFRS mapping.

Accounting principles applied:
  - Classes 1-5: Balance Sheet accounts
  - Classes 6-9: Income Statement accounts
  - Debit-normal accounts (assets, expenses): positive = debit balance
  - Credit-normal accounts (liabilities, equity, revenue): positive = credit balance
  - Net Income is injected into Equity as Retained Earnings
  - BS equation validated: Assets = Liabilities + Equity
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.tb_parser import TBParseResult, TBRow

logger = logging.getLogger(__name__)

# ── Account classification rules (Georgian 1C COA) ─────────────────

# Map first digit → (section, side, sub_category, normal_balance)
CLASS_RULES = {
    "0": ("off_balance", "off_balance", "off_balance", "debit"),
    "1": ("balance_sheet", "asset", "current", "debit"),
    "2": ("balance_sheet", "asset", "noncurrent", "debit"),
    "3": ("balance_sheet", "liability", "current", "credit"),
    "4": ("balance_sheet", "liability", "noncurrent", "credit"),
    "5": ("balance_sheet", "equity", "equity", "credit"),
    "6": ("income_statement", "revenue", "revenue", "credit"),
    "7": ("income_statement", "expense", "expense", "debit"),
    "8": ("income_statement", "other", "other", "debit"),
    "9": ("income_statement", "other", "other_pl", "debit"),
}

# Map 2-digit prefix → P&L line classification
PL_LINE_RULES = {
    # Revenue (class 6)
    "61": "revenue",
    "62": "revenue",
    "63": "revenue",
    "64": "revenue",
    # COGS (class 7, prefix 71)
    "71": "cogs",
    # Labour costs
    "72": "labour",
    # Selling expenses
    "73": "selling_expenses",
    # Admin / G&A / Depreciation
    "74": "admin_expenses",
    # Finance expense
    "75": "finance_expense",
    # Finance income
    "76": "finance_income",
    # Income tax
    "77": "tax",
    # Other income/expense (class 8)
    "81": "other_income",
    "82": "other_expense",
    "83": "other_expense",
    # Class 9
    "91": "other_pl",
    "92": "other_pl",
}

# Specific 4-digit codes with special treatment
SPECIAL_CODES = {
    "3340": ("balance_sheet", "asset", "current", "debit"),   # Input VAT receivable
    "4210": ("balance_sheet", "asset", "noncurrent", "debit"),  # Deferred Tax Asset
    "4211": ("balance_sheet", "liability", "noncurrent", "credit"),  # Deferred Tax Liability
}

# D&A account prefixes (depreciation & amortization)
DA_PREFIXES = {"7420", "7430", "7440", "7450"}  # D&A accounts (NOT 7410 which is admin)


@dataclass
class ClassificationReason:
    """Explains how and why an account was classified."""
    method: str          # exact_match, learned, semantic, nemotron, prefix_rule, unclassified
    confidence: float    # 0.0-1.0
    explanation: str     # Human-readable reasoning
    alternatives: List[Dict] = field(default_factory=list)  # Other possible classifications


@dataclass
class AccountClassification:
    account_code: str
    section: str        # balance_sheet, income_statement, off_balance
    side: str           # asset, liability, equity, revenue, expense, other
    sub: str            # current, noncurrent, equity, revenue, cogs, etc.
    normal_balance: str  # debit or credit
    pl_line: str = ""   # revenue, cogs, selling_expenses, admin_expenses, etc.
    is_depreciation: bool = False
    reason: ClassificationReason = field(default_factory=lambda: ClassificationReason("unknown", 0.0, ""))


@dataclass
class DerivedStatements:
    """P&L and BS derived from Trial Balance using accounting rules."""
    # P&L
    revenue: float = 0.0
    revenue_wholesale: float = 0.0
    revenue_retail: float = 0.0
    revenue_other: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    selling_expenses: float = 0.0
    admin_expenses: float = 0.0
    labour_costs: float = 0.0
    ga_expenses: float = 0.0
    ebitda: float = 0.0
    depreciation: float = 0.0
    ebit: float = 0.0
    finance_income: float = 0.0
    finance_expense: float = 0.0
    other_income: float = 0.0
    other_expense: float = 0.0
    profit_before_tax: float = 0.0
    tax_expense: float = 0.0
    net_profit: float = 0.0

    # BS
    cash: float = 0.0
    receivables: float = 0.0
    inventory: float = 0.0
    prepayments: float = 0.0
    other_current_assets: float = 0.0
    total_current_assets: float = 0.0
    fixed_assets: float = 0.0
    accumulated_depreciation: float = 0.0
    intangible_assets: float = 0.0
    other_noncurrent_assets: float = 0.0
    total_noncurrent_assets: float = 0.0
    total_assets: float = 0.0
    payables: float = 0.0
    short_term_debt: float = 0.0
    tax_payable: float = 0.0
    other_current_liabilities: float = 0.0
    total_current_liabilities: float = 0.0
    long_term_debt: float = 0.0
    deferred_tax: float = 0.0
    other_noncurrent_liabilities: float = 0.0
    total_noncurrent_liabilities: float = 0.0
    total_liabilities: float = 0.0
    share_capital: float = 0.0
    retained_earnings: float = 0.0
    reserves: float = 0.0
    total_equity: float = 0.0

    # Ratios
    current_ratio: float = 0.0
    debt_to_equity: float = 0.0
    gross_margin: float = 0.0
    ebitda_margin: float = 0.0
    net_margin: float = 0.0

    # Metadata
    account_classifications: List[Dict] = field(default_factory=list)
    unclassified_accounts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    bs_equation_holds: bool = False
    bs_imbalance: float = 0.0

    # Classification intelligence
    classification_summary: Dict = field(default_factory=dict)

    @property
    def pending_approvals(self) -> List[Dict]:
        """Accounts with confidence < 0.7 that need user review."""
        return [c for c in self.account_classifications if c.get("confidence", 1.0) < 0.7]

    @property
    def auto_accepted(self) -> List[Dict]:
        """Accounts with confidence >= 0.7 that were auto-accepted."""
        return [c for c in self.account_classifications if c.get("confidence", 1.0) >= 0.7]


class TBToStatements:
    """Converts Trial Balance into P&L and Balance Sheet using accounting rules."""

    def __init__(self):
        self._onec_tree = None

    def _get_onec_tree(self):
        """Lazy-load the OneCInterpreter account tree."""
        if self._onec_tree is None:
            try:
                from app.services.onec_interpreter import onec_interpreter
                self._onec_tree = onec_interpreter.tree
            except Exception:
                self._onec_tree = None
        return self._onec_tree

    def convert(self, tb: TBParseResult) -> DerivedStatements:
        """Convert a parsed TB into financial statements."""
        result = DerivedStatements()

        # ── Use postable accounts only (no XX groups), deduped for dot-hierarchy ──
        # In 1C TB, group accounts (11XX, 14X) aggregate children — skip them.
        # Among postable accounts, parent codes (1610) and child codes (1610.01)
        # may overlap — parent balance = sum of children. Keep only the deepest leaves.

        rows = tb.postable_rows if tb.postable_rows else tb.rows
        rows = self._deduplicate_hierarchy(rows)

        for row in rows:
            classification = self._classify_account(row)
            cl_entry = {
                "code": row.account_code,
                "name": row.account_name[:60],
                "section": classification.section,
                "side": classification.side,
                "pl_line": classification.pl_line,
                "closing_dr": row.closing_debit,
                "closing_cr": row.closing_credit,
                "turnover_dr": row.turnover_debit,
                "turnover_cr": row.turnover_credit,
                "balance": row.closing_balance,
                "method": classification.reason.method,
                "confidence": classification.reason.confidence,
                "explanation": classification.reason.explanation,
                "alternatives": classification.reason.alternatives,
            }
            result.account_classifications.append(cl_entry)

            if classification.section == "off_balance":
                continue
            elif classification.section == "income_statement":
                self._apply_pl(result, row, classification)
            elif classification.section == "balance_sheet":
                self._apply_bs(result, row, classification)

        # Compute derived P&L metrics (from turnovers — period activity)
        self._compute_pl_totals(result)

        # Compute derived BS metrics (from closing balances — position at period end)
        self._compute_bs_totals(result)

        # CRITICAL FIX: Retained Earnings injection with double-count prevention.
        #
        # In an unclosed 1C TB, P&L accounts (classes 6-9) carry cumulative balances.
        # Account 53xx (Retained Earnings) holds PRIOR year RE only.
        # Current year P&L must be injected to balance BS.
        #
        # BUT if the TB is PARTIALLY CLOSED (account 53 already includes current P&L),
        # injecting P&L closing net again causes DOUBLE-COUNTING.
        #
        # Detection: If account 53 already has a large balance AND P&L accounts have
        # non-zero closing balances, we may be looking at a partially-closed TB.
        # In that case, skip injection to avoid double-count.
        pl_closing_net = 0.0
        for c in result.account_classifications:
            if c.get("section") == "income_statement":
                pl_closing_net += c.get("closing_cr", 0) - c.get("closing_dr", 0)

        if pl_closing_net != 0:
            # Check: does account 53 already have a balance that suggests
            # current-year P&L has been partially closed?
            re_from_accounts = 0.0
            for c in result.account_classifications:
                code = str(c.get("account_code", ""))
                if code.startswith("53"):
                    re_from_accounts += c.get("closing_cr", 0) - c.get("closing_dr", 0)

            # Heuristic: If RE from account 53 is large AND in the same direction
            # as P&L net, the TB is likely partially closed. Skip injection.
            same_direction = (re_from_accounts > 0 and pl_closing_net > 0) or \
                             (re_from_accounts < 0 and pl_closing_net < 0)
            re_is_large = abs(re_from_accounts) > abs(pl_closing_net) * 0.5

            if same_direction and re_is_large:
                logger.warning(
                    "TB appears PARTIALLY CLOSED: account 53 has %.0f, P&L closing net is %.0f. "
                    "SKIPPING P&L injection to prevent double-counting.",
                    re_from_accounts, pl_closing_net,
                )
                # Recalculate total equity from account balances only (no injection)
                result.total_equity = result.share_capital + result.retained_earnings + result.reserves
            else:
                # TB appears truly unclosed — inject P&L closing net into RE
                result.retained_earnings += pl_closing_net
                result.total_equity = result.share_capital + result.retained_earnings + result.reserves
                logger.info(
                    "Injected P&L closing net (%.0f) into RE — TB appears unclosed "
                    "(account 53 has %.0f, P&L net has %.0f).",
                    pl_closing_net, re_from_accounts, pl_closing_net,
                )

        # Validate BS equation — STRICT tolerance
        result.bs_imbalance = abs(result.total_assets - result.total_liabilities - result.total_equity)
        # AUDIT FIX: Previous tolerance was ₾10,000 or 0.5% — for a ₾1B entity,
        # this meant a ₾5M imbalance passed silently. An auditor would reject this.
        # New tolerance: ₾1.00 (absolute) — any imbalance > ₾1 is flagged.
        tolerance = 1.0
        result.bs_equation_holds = result.bs_imbalance < tolerance

        if not result.bs_equation_holds:
            result.warnings.append(
                f"BS equation imbalance: Assets({result.total_assets:.0f}) != "
                f"Liab({result.total_liabilities:.0f}) + Equity({result.total_equity:.0f}), "
                f"diff={result.bs_imbalance:.2f}"
            )

        # Compute ratios
        self._compute_ratios(result)

        # Build classification summary
        methods = {}
        for c in result.account_classifications:
            m = c.get("method", "unknown")
            methods[m] = methods.get(m, 0) + 1
        result.classification_summary = {
            "total": len(result.account_classifications),
            "auto_accepted": len(result.auto_accepted),
            "pending_review": len(result.pending_approvals),
            "methods": methods,
        }

        logger.info(
            "TB→Statements: Revenue=%.0f, COGS=%.0f, GP=%.0f, EBITDA=%.0f, NP=%.0f | "
            "Assets=%.0f, Liab=%.0f, Equity=%.0f, BS_ok=%s | "
            "Classifications: %d auto, %d pending",
            result.revenue, result.cogs, result.gross_profit, result.ebitda, result.net_profit,
            result.total_assets, result.total_liabilities, result.total_equity,
            result.bs_equation_holds,
            len(result.auto_accepted), len(result.pending_approvals),
        )

        return result

    def _classify_account(self, row: TBRow) -> AccountClassification:
        """Classify an account using multi-tier AI reasoning pipeline.

        Tier 1: Special codes (hardcoded exceptions) → confidence 1.0
        Tier 2: Exact match in OneCInterpreter (406 accounts) → confidence 1.0
        Tier 3: LearningEngine cache (user-approved) → confidence 0.95
        Tier 4: Semantic search via VectorStore → confidence 0.7-0.9
        Tier 5: Prefix rules (first/second digit) → confidence 0.5-0.7
        Tier 6: Unclassified → confidence 0.0
        """
        code = row.account_code.strip()
        base_code = code.split(".")[0]

        # ── Tier 1: Special codes (exceptions like 3340=VAT asset) ──
        if base_code in SPECIAL_CODES:
            section, side, sub, normal = SPECIAL_CODES[base_code]
            pl_line = self._get_pl_line(base_code)
            is_da = self._is_depreciation(base_code, row.account_name)
            reason = ClassificationReason(
                method="exact_match",
                confidence=1.0,
                explanation=f"Special code {base_code}: exception rule ({side}/{sub})",
            )
            return AccountClassification(code, section, side, sub, normal, pl_line, is_da, reason)

        # ── Tier 2: OneCInterpreter lookup (406 accounts with IFRS) ──
        tree = self._get_onec_tree()
        if tree:
            acct = tree.get(base_code)
            if acct and acct.ifrs_section:
                section = acct.ifrs_section
                if section == "balance_sheet":
                    side = acct.ifrs_bs_side or "asset"
                    sub = acct.ifrs_bs_sub or "current"
                    normal = acct.normal_balance or ("debit" if side == "asset" else "credit")
                else:
                    side = "revenue" if base_code.startswith("6") else "expense"
                    sub = acct.ifrs_pl_line or ""
                    normal = acct.normal_balance or "debit"
                pl_line = self._get_pl_line(base_code)
                is_da = self._is_depreciation(base_code, row.account_name)
                reason = ClassificationReason(
                    method="exact_match",
                    confidence=1.0,
                    explanation=f"OneCInterpreter: {base_code} '{acct.name_ka or acct.name_ru}' → {section}/{side}/{pl_line}",
                )
                return AccountClassification(code, section, side, sub, normal, pl_line, is_da, reason)

        # ── Tier 3: LearningEngine cache (user-approved classifications) ──
        learned = self._get_learned_classification(code)
        if learned:
            section = learned.get("section", "unknown")
            side = learned.get("side", "unknown")
            sub = learned.get("sub", "")
            normal = learned.get("normal_balance", "debit")
            pl_line = learned.get("pl_line", "")
            is_da = learned.get("is_depreciation", False)
            reason = ClassificationReason(
                method="learned",
                confidence=0.95,
                explanation=f"Previously approved by user: {code} → {section}/{pl_line}",
            )
            return AccountClassification(code, section, side, sub, normal, pl_line, is_da, reason)

        # ── Tier 4: Semantic search via VectorStore ──
        semantic_result = self._semantic_classify(row)
        if semantic_result and semantic_result.reason.confidence >= 0.8:
            return semantic_result

        # ── Tier 5: Prefix rules (first-digit class) ──
        first_digit = ""
        for ch in base_code:
            if ch.isdigit():
                first_digit = ch
                break

        if first_digit in CLASS_RULES:
            section, side, sub, normal = CLASS_RULES[first_digit]
            pl_line = self._get_pl_line(base_code)
            is_da = self._is_depreciation(base_code, row.account_name)
            class_desc = {
                "1": "Current Assets", "2": "Noncurrent Assets",
                "3": "Current Liabilities", "4": "Noncurrent Liabilities",
                "5": "Equity", "6": "Revenue", "7": "Expenses",
                "8": "Other Income/Expense", "9": "Tax/Other P&L",
            }
            # Build alternatives for user review
            alternatives = []
            if section == "income_statement":
                all_pl_lines = ["revenue", "cogs", "selling_expenses", "admin_expenses",
                                "labour", "finance_income", "finance_expense", "tax", "other_income", "other_expense"]
                for alt_line in all_pl_lines:
                    if alt_line != pl_line:
                        alternatives.append({"pl_line": alt_line, "section": section, "side": side})

            # BS accounts (classes 1-5) are well-classified by first digit — high confidence
            # P&L accounts (classes 6-9) need pl_line refinement — lower confidence if "other_pl"
            if section == "balance_sheet":
                # BS classification by first digit is reliable
                confidence = 0.85
                explanation = f"Class {first_digit} → {class_desc.get(first_digit, '?')} ({side}/{sub})"
                pl_line = ""  # BS accounts don't have P&L lines
            elif semantic_result and semantic_result.reason.confidence > 0.0:
                confidence = max(0.6, semantic_result.reason.confidence)
                explanation = (
                    f"Prefix rule: class {first_digit} ({class_desc.get(first_digit, '?')}) → {pl_line}. "
                    f"Semantic hint: {semantic_result.reason.explanation}"
                )
            else:
                confidence = 0.5 if pl_line == "other_pl" else 0.7
                explanation = f"Prefix rule: class {first_digit} ({class_desc.get(first_digit, '?')}), prefix {base_code[:2]} → {pl_line}"

            reason = ClassificationReason(
                method="prefix_rule",
                confidence=confidence,
                explanation=explanation,
                alternatives=alternatives[:5],
            )
            return AccountClassification(code, section, side, sub, normal, pl_line, is_da, reason)

        # ── Tier 6: Unclassified ──
        reason = ClassificationReason(
            method="unclassified",
            confidence=0.0,
            explanation=f"Could not classify account {code} '{row.account_name[:40]}' by any method",
        )
        return AccountClassification(code, "unknown", "unknown", "", "debit", "", False, reason)

    def _get_learned_classification(self, code: str) -> Optional[Dict]:
        """Check LearningEngine for user-approved classifications."""
        try:
            from app.services.learning_engine import learning_engine
            result = learning_engine.get_cached_classification(code)
            # v2 learning_engine returns a coroutine — handle both sync and async
            import asyncio
            if asyncio.iscoroutine(result):
                # In sync context, use the in-memory cache directly
                conf = learning_engine._confidence_cache.get(code.strip(), 0.0)
                if conf >= 0.8:
                    return learning_engine._classification_cache.get(code.strip())
                return None
            return result
        except Exception:
            return None

    def _semantic_classify(self, row: TBRow) -> Optional[AccountClassification]:
        """Use VectorStore semantic search to find nearest known account by name."""
        try:
            from app.services.vector_store import vector_store
            import asyncio

            # Search for similar account names in the knowledge base
            query = f"{row.account_code} {row.name_ka} {row.name_ru}"

            # Run async search synchronously (we're in a sync context)
            try:
                asyncio.get_running_loop()
                # Inside async context — can't block. Return None.
                return None
            except RuntimeError:
                pass

            # No running loop — safe to create one
            results = asyncio.run(vector_store.search(query, n_results=3))

            if not results:
                return None

            best = results[0]
            score = best.get("score", 0)
            content = best.get("content", "")
            metadata = best.get("metadata", {})

            if score < 0.3:
                return None

            # Try to extract classification from the matched entity
            matched_code = metadata.get("account_code", metadata.get("code", ""))
            matched_section = metadata.get("ifrs_section", "")
            matched_pl_line = metadata.get("pl_line", "")

            if not matched_section and matched_code:
                # Try to classify the matched code with prefix rules
                first_digit = ""
                for ch in matched_code:
                    if ch.isdigit():
                        first_digit = ch
                        break
                if first_digit in CLASS_RULES:
                    section, side, sub, normal = CLASS_RULES[first_digit]
                    pl_line = self._get_pl_line(matched_code)
                    is_da = self._is_depreciation(matched_code, content)
                    confidence = min(0.9, score * 0.9)
                    reason = ClassificationReason(
                        method="semantic",
                        confidence=confidence,
                        explanation=f"Semantic match (score={score:.2f}): '{row.account_name[:30]}' ≈ '{content[:50]}' (code {matched_code})",
                    )
                    return AccountClassification(
                        row.account_code, section, side, sub, normal, pl_line, is_da, reason
                    )

            if matched_section:
                side = metadata.get("ifrs_bs_side", "asset" if matched_section == "balance_sheet" else "expense")
                sub = metadata.get("ifrs_bs_sub", "current")
                normal = "credit" if side in ("liability", "equity", "revenue") else "debit"
                pl_line = matched_pl_line or self._get_pl_line(matched_code or row.account_code)
                is_da = self._is_depreciation(row.account_code, row.account_name)
                confidence = min(0.9, score * 0.9)
                reason = ClassificationReason(
                    method="semantic",
                    confidence=confidence,
                    explanation=f"Semantic match (score={score:.2f}): '{row.account_name[:30]}' ≈ '{content[:50]}'",
                )
                return AccountClassification(
                    row.account_code, matched_section, side, sub, normal, pl_line, is_da, reason
                )

            return None
        except Exception as e:
            logger.debug("Semantic classification failed for %s: %s", row.account_code, e)
            return None

    def _get_pl_line(self, code: str) -> str:
        """Get P&L line from 2-digit prefix rules."""
        base = code.split(".")[0]
        prefix2 = base[:2] if len(base) >= 2 else base
        return PL_LINE_RULES.get(prefix2, "other_pl")

    def _is_depreciation(self, code: str, name: str) -> bool:
        """Check if account is D&A."""
        base = code.split(".")[0]
        # Check known D&A codes
        if base in DA_PREFIXES:
            return True
        # Check name for depreciation keywords
        name_lower = name.lower()
        da_keywords = ["ამორტიზაცია", "ცვეთა", "амортизация", "износ", "depreciation", "amortization"]
        return any(kw in name_lower for kw in da_keywords)

    def _deduplicate_hierarchy(self, rows: List[TBRow]) -> List[TBRow]:
        """Remove parent accounts when children exist to avoid double-counting.

        In 1C TB, parent accounts aggregate their children's balances.
        E.g., 7310 (total=61.5M) = 7310.01 (19.2M) + 7310.02 (42.3M).
        We keep ONLY the leaf accounts (most detailed level).

        Also removes exact duplicates (same code appearing twice).
        """
        codes = [r.account_code for r in rows]
        code_set = set(codes)

        # Step 1: Remove parents that have children
        result = []
        removed_parents = []
        for row in rows:
            code = row.account_code
            # Check if ANY other row is a child of this one
            has_children = False
            for other_code in code_set:
                if other_code == code:
                    continue
                # Child patterns: "7310" → "7310.01", "7310.01" → "7310.01.1"
                if other_code.startswith(code + "."):
                    has_children = True
                    break
                # Also: "1610" parent and "1610.01" child (dot-separated)
                # But NOT: "16100" is not a child of "1610"

            if has_children:
                removed_parents.append(code)
            else:
                result.append(row)

        # Step 2: Remove exact duplicates (keep first occurrence)
        seen = set()
        deduped = []
        for row in result:
            key = (row.account_code, row.closing_debit, row.closing_credit)
            if key not in seen:
                seen.add(key)
                deduped.append(row)

        if removed_parents:
            logger.info("Dedup: removed %d parent aggregates: %s",
                        len(removed_parents), removed_parents[:10])
        if len(result) != len(deduped):
            logger.info("Dedup: removed %d exact duplicates", len(result) - len(deduped))
        logger.info("Dedup: %d → %d accounts", len(rows), len(deduped))
        return deduped

    def _apply_pl(self, result: DerivedStatements, row: TBRow, cls: AccountClassification):
        """Apply a P&L account row to the income statement.

        CRITICAL: For P&L accounts in a TB, use TURNOVER (period activity), not
        closing balances. Closing balances in a 1C TB are cumulative year-to-date.
        The turnover columns show the activity for the specific period.
        """
        # Use turnover for P&L (period activity)
        if cls.normal_balance == "credit":
            # Revenue: credit turnover minus debit turnover (returns/adjustments)
            amount = row.turnover_credit - row.turnover_debit
        else:
            # Expenses: debit turnover minus credit turnover (reversals)
            amount = row.turnover_debit - row.turnover_credit

        # If no turnover data, fall back to closing - opening (net change)
        if amount == 0 and (row.closing_debit != 0 or row.closing_credit != 0):
            if cls.normal_balance == "credit":
                amount = (row.closing_credit - row.closing_debit) - (row.opening_credit - row.opening_debit)
            else:
                amount = (row.closing_debit - row.closing_credit) - (row.opening_debit - row.opening_credit)

        amount = abs(amount) if amount != 0 else 0

        if cls.pl_line == "revenue":
            result.revenue += amount
            # Try to split wholesale vs retail
            code_base = row.account_code.split(".")[0]
            if code_base.startswith("613") or "საბითუმო" in row.account_name or "wholesale" in row.account_name.lower():
                result.revenue_wholesale += amount
            elif code_base.startswith("611") or "საცალო" in row.account_name or "retail" in row.account_name.lower():
                result.revenue_retail += amount
            else:
                result.revenue_other += amount
        elif cls.pl_line == "cogs":
            result.cogs += amount
        elif cls.pl_line == "selling_expenses":
            if cls.is_depreciation:
                result.depreciation += amount
            else:
                result.selling_expenses += amount
        elif cls.pl_line == "admin_expenses":
            if cls.is_depreciation:
                result.depreciation += amount
            else:
                result.admin_expenses += amount
        elif cls.pl_line == "labour":
            result.labour_costs += amount
        elif cls.pl_line == "finance_income":
            result.finance_income += amount
        elif cls.pl_line == "finance_expense":
            result.finance_expense += amount
        elif cls.pl_line == "tax":
            result.tax_expense += amount
        elif cls.pl_line in ("other_income",):
            result.other_income += amount
        elif cls.pl_line in ("other_expense",):
            result.other_expense += amount
        else:
            # Other P&L items
            if cls.side == "revenue" or cls.normal_balance == "credit":
                result.other_income += amount
            else:
                result.other_expense += amount

    def _apply_bs(self, result: DerivedStatements, row: TBRow, cls: AccountClassification):
        """Apply a BS account row to the balance sheet."""
        # For BS accounts, use CLOSING balance
        if cls.normal_balance == "debit":
            balance = row.closing_debit - row.closing_credit
        else:
            balance = row.closing_credit - row.closing_debit

        code_base = row.account_code.split(".")[0]
        prefix2 = code_base[:2] if len(code_base) >= 2 else code_base

        if cls.side == "asset" and cls.sub == "current":
            if prefix2 in ("11", "12"):
                result.cash += balance
            elif prefix2 in ("14", "15"):
                result.receivables += balance
            elif prefix2 in ("16", "17"):
                result.inventory += balance
            elif prefix2 in ("18", "19"):
                result.prepayments += balance
            else:
                result.other_current_assets += balance

        elif cls.side == "asset" and cls.sub == "noncurrent":
            if prefix2 in ("21", "23"):
                result.fixed_assets += balance
            elif prefix2 == "22":
                result.accumulated_depreciation += balance  # Contra-asset (negative)
            elif prefix2 in ("25", "26"):
                result.intangible_assets += balance
            else:
                result.other_noncurrent_assets += balance

        elif cls.side == "liability" and cls.sub == "current":
            if prefix2 == "31":
                result.payables += balance
            elif prefix2 == "32":
                result.short_term_debt += balance
            elif prefix2 in ("33", "34"):
                result.tax_payable += balance
            else:
                result.other_current_liabilities += balance

        elif cls.side == "liability" and cls.sub == "noncurrent":
            if prefix2 in ("41", "42"):
                if code_base == "4210":
                    result.other_noncurrent_assets += balance  # DTA is an asset
                elif code_base == "4211":
                    result.deferred_tax += balance
                else:
                    result.long_term_debt += balance
            else:
                result.other_noncurrent_liabilities += balance

        elif cls.side == "equity":
            if prefix2 == "51":
                result.share_capital += balance
            elif prefix2 == "53":
                result.retained_earnings += balance
            elif prefix2 == "54":
                result.reserves += balance
            else:
                result.retained_earnings += balance

    def _compute_pl_totals(self, r: DerivedStatements):
        """Compute derived P&L line items."""
        r.gross_profit = r.revenue - r.cogs
        r.ga_expenses = r.selling_expenses + r.admin_expenses + r.labour_costs
        r.ebitda = r.gross_profit - r.ga_expenses
        r.ebit = r.ebitda - r.depreciation
        r.profit_before_tax = (
            r.ebit
            + r.finance_income - r.finance_expense
            + r.other_income - r.other_expense
        )
        r.net_profit = r.profit_before_tax - r.tax_expense

    def _compute_bs_totals(self, r: DerivedStatements):
        """Compute derived BS totals."""
        r.total_current_assets = r.cash + r.receivables + r.inventory + r.prepayments + r.other_current_assets
        # FIX: Accumulated depreciation is a CONTRA-ASSET — must be SUBTRACTED (IAS 16)
        # accumulated_depreciation is stored as negative (credit balance), so adding it subtracts correctly
        # But if it was stored as positive (absolute value), we need to subtract explicitly
        accum_depr = r.accumulated_depreciation
        if accum_depr > 0:
            accum_depr = -accum_depr  # Ensure it's negative (contra-asset reduces fixed assets)
        r.total_noncurrent_assets = r.fixed_assets + accum_depr + r.intangible_assets + r.other_noncurrent_assets
        r.total_assets = r.total_current_assets + r.total_noncurrent_assets
        r.total_current_liabilities = r.payables + r.short_term_debt + r.tax_payable + r.other_current_liabilities
        r.total_noncurrent_liabilities = r.long_term_debt + r.deferred_tax + r.other_noncurrent_liabilities
        r.total_liabilities = r.total_current_liabilities + r.total_noncurrent_liabilities
        r.total_equity = r.share_capital + r.retained_earnings + r.reserves

    def _compute_ratios(self, r: DerivedStatements):
        """Compute financial ratios."""
        if r.total_current_liabilities > 0:
            r.current_ratio = r.total_current_assets / r.total_current_liabilities
        if r.total_equity > 0:
            r.debt_to_equity = r.total_liabilities / r.total_equity
        if r.revenue > 0:
            r.gross_margin = (r.gross_profit / r.revenue) * 100
            r.ebitda_margin = (r.ebitda / r.revenue) * 100
            r.net_margin = (r.net_profit / r.revenue) * 100

    def to_financials_dict(self, statements: DerivedStatements) -> Dict[str, Any]:
        """Convert to the dict format expected by data_store.save_financials()."""
        d = {
            # P&L
            "revenue": statements.revenue,
            "revenue_wholesale": statements.revenue_wholesale,
            "revenue_retail": statements.revenue_retail,
            "revenue_other": statements.revenue_other,
            "cogs": statements.cogs,
            "gross_profit": statements.gross_profit,
            "selling_expenses": statements.selling_expenses,
            "admin_expenses": statements.admin_expenses,
            "labour_costs": statements.labour_costs,
            "ga_expenses": statements.ga_expenses,
            "total_opex": statements.ga_expenses,
            "ebitda": statements.ebitda,
            "depreciation": statements.depreciation,
            "ebit": statements.ebit,
            "finance_income": statements.finance_income,
            "finance_expense": statements.finance_expense,
            "non_operating_income": statements.other_income + statements.finance_income,
            "non_operating_expense": statements.other_expense + statements.finance_expense,
            "other_income": statements.other_income,
            "other_expense": statements.other_expense,
            "profit_before_tax": statements.profit_before_tax,
            "tax_expense": statements.tax_expense,
            "net_profit": statements.net_profit,
            # BS
            "cash": statements.cash,
            "bs_cash": statements.cash,
            "receivables": statements.receivables,
            "bs_receivables": statements.receivables,
            "inventory": statements.inventory,
            "bs_inventory": statements.inventory,
            "prepayments": statements.prepayments,
            "current_assets": statements.total_current_assets,
            "bs_current_assets": statements.total_current_assets,
            "fixed_assets": statements.fixed_assets,
            "bs_fixed_assets": statements.fixed_assets,
            "accumulated_depreciation": statements.accumulated_depreciation,
            "intangible_assets": statements.intangible_assets,
            "noncurrent_assets": statements.total_noncurrent_assets,
            "bs_noncurrent_assets": statements.total_noncurrent_assets,
            "total_assets": statements.total_assets,
            "bs_total_assets": statements.total_assets,
            "payables": statements.payables,
            "bs_payables": statements.payables,
            "short_term_debt": statements.short_term_debt,
            "bs_short_term_debt": statements.short_term_debt,
            "tax_payable": statements.tax_payable,
            "current_liabilities": statements.total_current_liabilities,
            "bs_current_liabilities": statements.total_current_liabilities,
            "long_term_debt": statements.long_term_debt,
            "bs_long_term_debt": statements.long_term_debt,
            "noncurrent_liabilities": statements.total_noncurrent_liabilities,
            "bs_noncurrent_liabilities": statements.total_noncurrent_liabilities,
            "total_liabilities": statements.total_liabilities,
            "bs_total_liabilities": statements.total_liabilities,
            "share_capital": statements.share_capital,
            "bs_share_capital": statements.share_capital,
            "retained_earnings": statements.retained_earnings,
            "bs_retained_earnings": statements.retained_earnings,
            "total_equity": statements.total_equity,
            "bs_total_equity": statements.total_equity,
            # Ratios
            "current_ratio": statements.current_ratio,
            "debt_to_equity": statements.debt_to_equity,
            "gross_margin": statements.gross_margin,
            "ebitda_margin": statements.ebitda_margin,
            "net_margin": statements.net_margin,
        }
        return d

    def to_pnl_dict(self, s: DerivedStatements) -> Dict[str, float]:
        """Extract P&L fields for the frontend store."""
        return {
            "revenue": s.revenue, "total_revenue": s.revenue,
            "revenue_wholesale": s.revenue_wholesale,
            "revenue_retail": s.revenue_retail,
            "revenue_other": s.revenue_other,
            "cogs": s.cogs, "total_cogs": s.cogs,
            "gross_profit": s.gross_profit,
            "selling_expenses": s.selling_expenses,
            "admin_expenses": s.admin_expenses,
            "labour_costs": s.labour_costs,
            "ga_expenses": s.ga_expenses,
            "ebitda": s.ebitda,
            "depreciation": s.depreciation,
            "ebit": s.ebit,
            "finance_income": s.finance_income,
            "finance_expense": s.finance_expense,
            "other_income": s.other_income,
            "other_expense": s.other_expense,
            "non_operating_income": s.other_income + s.finance_income,
            "non_operating_expense": s.other_expense + s.finance_expense,
            "profit_before_tax": s.profit_before_tax,
            "tax_expense": s.tax_expense,
            "net_profit": s.net_profit,
        }

    def to_bs_dict(self, s: DerivedStatements) -> Dict[str, float]:
        """Extract BS fields for the frontend store."""
        return {
            "cash": s.cash, "receivables": s.receivables,
            "inventory": s.inventory, "prepayments": s.prepayments,
            "current_assets": s.total_current_assets,
            "fixed_assets": s.fixed_assets,
            "accumulated_depreciation": s.accumulated_depreciation,
            "intangible_assets": s.intangible_assets,
            "noncurrent_assets": s.total_noncurrent_assets,
            "total_assets": s.total_assets,
            "payables": s.payables,
            "short_term_debt": s.short_term_debt,
            "tax_payable": s.tax_payable,
            "current_liabilities": s.total_current_liabilities,
            "long_term_debt": s.long_term_debt,
            "deferred_tax": s.deferred_tax,
            "noncurrent_liabilities": s.total_noncurrent_liabilities,
            "total_liabilities": s.total_liabilities,
            "share_capital": s.share_capital,
            "retained_earnings": s.retained_earnings,
            "reserves": s.reserves,
            "total_equity": s.total_equity,
            "current_ratio": s.current_ratio,
            "debt_to_equity": s.debt_to_equity,
        }

    def to_revenue_breakdown(self, s: DerivedStatements) -> List[Dict]:
        """Build revenue breakdown from derived statement totals (turnover-based, not cumulative)."""
        items = []
        # Use the already-computed revenue splits from the P&L derivation
        rev_splits = [
            ("Wholesale Revenue", s.revenue_wholesale, "Wholesale"),
            ("Retail Revenue", s.revenue_retail, "Retail"),
            ("Other Revenue", s.revenue_other, "Other Revenue"),
        ]
        for name, amount, category in rev_splits:
            if amount > 0:
                items.append({
                    "product": name,
                    "category": category,
                    "gross_revenue": amount,
                    "net_revenue": amount,
                    "vat": 0,
                })
        # If no splits, use total revenue as single item
        if not items and s.revenue > 0:
            items.append({
                "product": "Total Revenue",
                "category": "Revenue",
                "gross_revenue": s.revenue,
                "net_revenue": s.revenue,
                "vat": 0,
            })
        return items

    def to_cogs_breakdown(self, s: DerivedStatements) -> List[Dict]:
        """Build COGS breakdown from derived statement totals (turnover-based)."""
        items = []
        if s.cogs > 0:
            items.append({
                "product": "Cost of Goods Sold",
                "category": "COGS",
                "amount": s.cogs,
            })
        return items

    def to_pl_line_items(self, s: DerivedStatements) -> List[Dict]:
        """Build P&L line items from derived statements for frontend display."""
        items = []
        def _add(label: str, value: float, level: int = 0, is_total: bool = False):
            if value != 0 or is_total:
                items.append({"label": label, "amount": value, "level": level, "is_total": is_total})

        _add("Revenue", s.revenue, 0, True)
        if s.revenue_wholesale: _add("  Wholesale Revenue", s.revenue_wholesale, 1)
        if s.revenue_retail: _add("  Retail Revenue", s.revenue_retail, 1)
        if s.revenue_other: _add("  Other Revenue", s.revenue_other, 1)
        _add("Cost of Goods Sold", -s.cogs, 0)
        _add("Gross Profit", s.gross_profit, 0, True)
        if s.selling_expenses: _add("Selling Expenses", -s.selling_expenses, 0)
        if s.admin_expenses: _add("Administrative Expenses", -s.admin_expenses, 0)
        if s.labour_costs: _add("Labour Costs", -s.labour_costs, 0)
        _add("EBITDA", s.ebitda, 0, True)
        if s.depreciation: _add("Depreciation & Amortization", -s.depreciation, 0)
        _add("EBIT", s.ebit, 0, True)
        if s.finance_income: _add("Finance Income", s.finance_income, 0)
        if s.finance_expense: _add("Finance Expense", -s.finance_expense, 0)
        if s.other_income: _add("Other Income", s.other_income, 0)
        if s.other_expense: _add("Other Expense", -s.other_expense, 0)
        _add("Profit Before Tax", s.profit_before_tax, 0, True)
        if s.tax_expense: _add("Income Tax", -s.tax_expense, 0)
        _add("Net Profit", s.net_profit, 0, True)
        return items


# Singleton
tb_to_statements = TBToStatements()
