"""
Financial Reconstruction Engine v2
====================================
The BRAIN of FinAI. Not a parser — a financial analyst that THINKS.

Given ANY partial financial data, this engine:
1. DETECTS what accounts are present using accounting knowledge
2. UNDERSTANDS what's missing and WHY it matters
3. RECONSTRUCTS partial/full statements from available data
4. REASONS about relationships between signals (cross-logic)
5. CLASSIFIES company character with weighted signal scoring
6. ESTIMATES ranges when data is missing (clearly marked)
7. GENERATES CFO-level insights with impact + consequence
8. TELLS the user exactly what to do next (prioritized options)

STRICT RULES:
- No hallucinated financial values
- No fake completeness — always state uncertainty
- Prefer "I don't know" over wrong answer
- Accuracy > completeness, Clarity > complexity, Truth > impressiveness
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ACCOUNTING KNOWLEDGE BASE (Georgian/IFRS)
# ═══════════════════════════════════════════════════════════════════

ACCOUNT_GROUPS = {
    "cash":              {"prefixes": ["11", "12"], "statement": "bs", "section": "current_assets", "label": "Cash & Bank"},
    "receivables":       {"prefixes": ["14"], "statement": "bs", "section": "current_assets", "label": "Trade Receivables"},
    "inventory":         {"prefixes": ["16"], "statement": "bs", "section": "current_assets", "label": "Inventory"},
    "prepayments":       {"prefixes": ["18"], "statement": "bs", "section": "current_assets", "label": "Prepayments"},
    "fixed_assets":      {"prefixes": ["21"], "statement": "bs", "section": "non_current_assets", "label": "Fixed Assets (Gross)"},
    "accumulated_dep":   {"prefixes": ["22"], "statement": "bs", "section": "non_current_assets", "label": "Accumulated Depreciation"},
    "intangibles":       {"prefixes": ["23"], "statement": "bs", "section": "non_current_assets", "label": "Intangible Assets"},
    "investments":       {"prefixes": ["24", "25"], "statement": "bs", "section": "non_current_assets", "label": "Investments"},
    "trade_payables":    {"prefixes": ["31"], "statement": "bs", "section": "current_liabilities", "label": "Trade Payables"},
    "tax_payables":      {"prefixes": ["33", "34"], "statement": "bs", "section": "current_liabilities", "label": "Tax Payables"},
    "short_term_debt":   {"prefixes": ["35", "36"], "statement": "bs", "section": "current_liabilities", "label": "Short-term Debt"},
    "long_term_debt":    {"prefixes": ["41", "42"], "statement": "bs", "section": "non_current_liabilities", "label": "Long-term Debt"},
    "equity_capital":    {"prefixes": ["51"], "statement": "bs", "section": "equity", "label": "Share Capital"},
    "retained_earnings": {"prefixes": ["52", "53", "54"], "statement": "bs", "section": "equity", "label": "Retained Earnings"},
    "revenue":           {"prefixes": ["61", "62"], "statement": "pl", "section": "revenue", "label": "Revenue"},
    "cogs":              {"prefixes": ["71"], "statement": "pl", "section": "cogs", "label": "Cost of Goods Sold"},
    "selling_expenses":  {"prefixes": ["73"], "statement": "pl", "section": "opex", "label": "Selling & Distribution"},
    "admin_expenses":    {"prefixes": ["74"], "statement": "pl", "section": "opex", "label": "General & Administrative"},
    "other_income":      {"prefixes": ["81"], "statement": "pl", "section": "other", "label": "Other Income"},
    "other_expense":     {"prefixes": ["82", "83"], "statement": "pl", "section": "other", "label": "Other Expenses"},
    "tax_expense":       {"prefixes": ["91"], "statement": "pl", "section": "tax", "label": "Income Tax"},
}

# Industry signal keywords (multilingual: EN/GE/RU)
_FUEL_KEYWORDS = ["fuel", "diesel", "petrol", "gasoline", "gas station", "lpg", "cng", "bitumen",
                  "საწვავ", "დიზელ", "ბენზინ", "აირი", "ბიტუმ", "აგს",
                  "топливо", "дизель", "бензин", "газ", "азс"]
_TRANSPORT_KEYWORDS = ["transport", "logistics", "shipping", "freight", "delivery",
                       "გადაზიდვ", "ტრანსპორტ", "перевозк", "транспорт", "доставк"]
_RENT_KEYWORDS = ["rent", "lease", "იჯარა", "аренда"]
_SECURITY_KEYWORDS = ["security", "guard", "დაცვა", "охран"]


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DataCompleteness:
    completeness_pct: float = 0.0
    data_type: str = "unknown"
    groups_found: List[str] = field(default_factory=list)
    groups_missing: List[str] = field(default_factory=list)
    can_build_pl: bool = False
    can_build_bs: bool = False
    can_compute_profitability: bool = False
    missing_for_pl: List[str] = field(default_factory=list)
    missing_for_bs: List[str] = field(default_factory=list)
    data_quality: str = "unknown"  # high, medium, low, insufficient

    def to_dict(self):
        return self.__dict__


@dataclass
class FinancialInsight:
    category: str       # risk, opportunity, anomaly, structure, missing_data, relationship
    severity: str       # critical, warning, info, positive
    title: str
    explanation: str
    impact: str = ""          # What this MEANS for the business
    consequence: str = ""     # What HAPPENS if ignored
    action: str = ""          # What to DO
    confidence: float = 1.0   # 0-1 how confident we are
    metric: str = ""
    value: float = 0.0
    benchmark: float = 0.0

    def to_dict(self):
        d = {"category": self.category, "severity": self.severity, "title": self.title,
             "explanation": self.explanation}
        if self.impact: d["impact"] = self.impact
        if self.consequence: d["consequence"] = self.consequence
        if self.action: d["action"] = self.action
        if self.confidence < 1.0: d["confidence"] = round(self.confidence, 2)
        if self.metric: d["metric"] = self.metric
        if self.value: d["value"] = round(self.value, 2)
        if self.benchmark: d["benchmark"] = round(self.benchmark, 2)
        return d


@dataclass
class CompanyCharacter:
    industry: str = "unknown"
    industry_confidence: float = 0.0
    business_model: str = "unknown"
    risk_profile: str = "unknown"
    asset_intensity: str = "unknown"
    leverage_level: str = "unknown"
    operational_complexity: str = "unknown"
    signals: List[str] = field(default_factory=list)
    signal_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class RevenueEstimate:
    """Estimated revenue range when actual is missing."""
    low: float = 0.0
    mid: float = 0.0
    high: float = 0.0
    method: str = ""
    disclaimer: str = "ESTIMATE ONLY — based on cost structure assumptions. Upload actual revenue data for accuracy."

    def to_dict(self):
        return self.__dict__


@dataclass
class ReconstructedFinancials:
    accounts: Dict[str, float] = field(default_factory=dict)
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    completeness: DataCompleteness = field(default_factory=DataCompleteness)
    partial_pl: Dict[str, Any] = field(default_factory=dict)
    partial_bs: Dict[str, Any] = field(default_factory=dict)
    insights: List[FinancialInsight] = field(default_factory=list)
    company_character: CompanyCharacter = field(default_factory=CompanyCharacter)
    revenue_estimate: Optional[RevenueEstimate] = None
    user_message: str = ""
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    expense_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self):
        d = {
            "accounts": {k: round(v, 2) for k, v in self.accounts.items()},
            "line_items": self.line_items[:100],
            "completeness": self.completeness.to_dict(),
            "partial_pl": self.partial_pl,
            "partial_bs": self.partial_bs,
            "insights": [i.to_dict() for i in self.insights],
            "company_character": self.company_character.to_dict(),
            "user_message": self.user_message,
            "suggestions": self.suggestions,
            "expense_breakdown": {k: round(v, 2) for k, v in self.expense_breakdown.items()},
        }
        if self.revenue_estimate:
            d["revenue_estimate"] = self.revenue_estimate.to_dict()
        return d


# ═══════════════════════════════════════════════════════════════════
# RECONSTRUCTION ENGINE v2
# ═══════════════════════════════════════════════════════════════════

class FinancialReconstructionEngine:
    """
    Financial analyst brain. Not a parser — a THINKER.
    """

    def reconstruct(self, financials: Dict[str, Any],
                    line_items: Optional[List[Dict]] = None) -> ReconstructedFinancials:
        result = ReconstructedFinancials()
        if line_items:
            result.line_items = line_items

        # 1. Classify accounts into groups
        self._classify_accounts(financials, line_items or [], result)

        # 2. Build expense breakdown from line items
        self._build_expense_breakdown(result)

        # 3. Assess completeness
        self._assess_completeness(result)

        # 4. Reconstruct partial P&L
        self._reconstruct_pl(result)

        # 5. Reconstruct partial BS
        self._reconstruct_bs(result)

        # 6. Estimate revenue if missing
        self._estimate_revenue(result)

        # 7. Detect company character (WEIGHTED SIGNAL SCORING)
        self._detect_company_character(result)

        # 8. Generate insights (with impact + consequence + cross-logic)
        self._generate_insights(result)

        # 9. Cross-signal reasoning
        self._cross_signal_reasoning(result)

        # 10. Build CFO-level user message
        self._build_user_message(result)

        # 11. Generate prioritized suggestions
        self._generate_suggestions(result)

        logger.info("Reconstruction v2: type=%s, completeness=%.0f%%, insights=%d, industry=%s (%.0f%%)",
                     result.completeness.data_type, result.completeness.completeness_pct,
                     len(result.insights), result.company_character.industry,
                     result.company_character.industry_confidence * 100)

        return result

    # ── Step 1: Classify accounts ───────────────────────────────────

    def _classify_accounts(self, financials: Dict[str, Any], line_items: List[Dict], result: ReconstructedFinancials):
        mapping = {
            "revenue": "revenue", "total_revenue": "revenue", "net_revenue": "revenue",
            "cogs": "cogs", "cost_of_goods_sold": "cogs",
            "selling_expenses": "selling_expenses", "ga_expenses": "admin_expenses",
            "admin_expenses": "admin_expenses",
            "other_income": "other_income", "other_expense": "other_expense",
            "interest_expense": "other_expense", "finance_expense": "other_expense",
            "cash": "cash", "receivables": "receivables", "inventory": "inventory",
            "fixed_assets_net": "fixed_assets", "total_equity": "equity_capital",
            "long_term_debt": "long_term_debt",
            "total_current_liabilities": "trade_payables",
        }

        for key, value in financials.items():
            if not isinstance(value, (int, float)) or value == 0:
                continue
            group = mapping.get(key)
            if group:
                result.accounts[group] = result.accounts.get(group, 0) + abs(value)

        for item in line_items:
            code = str(item.get("code", "")).strip()
            amount = item.get("amount", 0)
            if not code or not isinstance(amount, (int, float)) or amount == 0:
                continue
            code_clean = code.replace(" ", "").split("/")[0].split(".")[0]
            if len(code_clean) < 2:
                continue
            prefix = code_clean[:2]
            for group_name, group_def in ACCOUNT_GROUPS.items():
                if prefix in group_def["prefixes"]:
                    result.accounts[group_name] = result.accounts.get(group_name, 0) + abs(amount)
                    break

    # ── Step 2: Expense breakdown by category ───────────────────────

    def _build_expense_breakdown(self, result: ReconstructedFinancials):
        categories = {}
        for item in result.line_items:
            cat = item.get("subcategory") or item.get("category") or "Uncategorized"
            amt = abs(item.get("amount", 0))
            if amt > 0 and cat:
                categories[cat] = categories.get(cat, 0) + amt
        result.expense_breakdown = dict(sorted(categories.items(), key=lambda x: -x[1]))

    # ── Step 3: Completeness ────────────────────────────────────────

    def _assess_completeness(self, result: ReconstructedFinancials):
        comp = DataCompleteness()
        found = set(result.accounts.keys())
        comp.groups_found = sorted(found)

        pl_groups = {g for g, d in ACCOUNT_GROUPS.items() if d["statement"] == "pl"}
        bs_groups = {g for g, d in ACCOUNT_GROUPS.items() if d["statement"] == "bs"}

        comp.missing_for_pl = sorted(pl_groups - found)
        comp.missing_for_bs = sorted(bs_groups - found)

        comp.can_build_pl = "revenue" in found and "cogs" in found
        comp.can_build_bs = len(found & bs_groups) >= 3
        comp.can_compute_profitability = "revenue" in found

        all_groups = pl_groups | bs_groups
        comp.completeness_pct = len(found & all_groups) / max(len(all_groups), 1) * 100
        comp.groups_missing = sorted(all_groups - found)

        has_rev = "revenue" in found
        has_cogs = "cogs" in found
        has_opex = "selling_expenses" in found or "admin_expenses" in found
        has_other = "other_income" in found or "other_expense" in found

        if has_rev and has_cogs and has_opex:
            comp.data_type = "full_pl"
            comp.data_quality = "high"
        elif has_rev and has_cogs:
            comp.data_type = "basic_pl"
            comp.data_quality = "medium"
        elif has_rev:
            comp.data_type = "revenue_only"
            comp.data_quality = "low"
        elif has_opex or has_other:
            comp.data_type = "expenses_only"
            comp.data_quality = "low"
        elif len(found & bs_groups) >= 2:
            comp.data_type = "balance_sheet"
            comp.data_quality = "medium"
        else:
            comp.data_type = "unknown"
            comp.data_quality = "insufficient"

        result.completeness = comp

    # ── Step 4: Reconstruct P&L ─────────────────────────────────────

    def _reconstruct_pl(self, result: ReconstructedFinancials):
        a = result.accounts
        pl = {}

        rev = a.get("revenue")
        cogs = a.get("cogs")
        selling = a.get("selling_expenses", 0)
        admin = a.get("admin_expenses", 0)
        other_inc = a.get("other_income", 0)
        other_exp = a.get("other_expense", 0)
        total_opex = selling + admin

        pl["revenue"] = rev
        pl["cogs"] = cogs

        if rev is not None and cogs is not None:
            gp = rev - cogs
            pl["gross_profit"] = round(gp, 2)
            pl["gross_margin_pct"] = round(gp / rev * 100, 2) if rev > 0 else None
        else:
            pl["gross_profit"] = None
            pl["gross_margin_pct"] = None

        pl["selling_expenses"] = selling if selling > 0 else None
        pl["admin_expenses"] = admin if admin > 0 else None
        pl["total_opex"] = total_opex if total_opex > 0 else None
        pl["other_income"] = other_inc if other_inc > 0 else None
        pl["other_expense"] = other_exp if other_exp > 0 else None

        if pl["gross_profit"] is not None:
            ebitda = pl["gross_profit"] - total_opex
            pl["ebitda"] = round(ebitda, 2)
            pl["net_profit"] = round(ebitda + other_inc - other_exp, 2)
            pl["net_margin_pct"] = round(pl["net_profit"] / rev * 100, 2) if rev and rev > 0 else None
        else:
            pl["ebitda"] = None
            pl["net_profit"] = None
            pl["net_margin_pct"] = None
            if total_opex > 0:
                pl["total_expense_burden"] = round(total_opex + other_exp - other_inc, 2)

        pl["_computed"] = [k for k, v in pl.items() if v is not None and not k.startswith("_")]
        pl["_missing"] = [k for k, v in pl.items() if v is None and not k.startswith("_")]

        result.partial_pl = pl

    # ── Step 5: Reconstruct BS ──────────────────────────────────────

    def _reconstruct_bs(self, result: ReconstructedFinancials):
        a = result.accounts
        bs = {}
        for key in ["cash", "receivables", "inventory", "fixed_assets", "accumulated_dep",
                     "investments", "trade_payables", "short_term_debt", "long_term_debt", "equity_capital"]:
            bs[key] = a.get(key)

        ca = sum(v or 0 for v in [bs["cash"], bs["receivables"], bs["inventory"]])
        nca = (bs["fixed_assets"] or 0) + (bs["investments"] or 0) - (bs["accumulated_dep"] or 0)
        cl = (bs["trade_payables"] or 0) + (bs["short_term_debt"] or 0)
        ncl = bs["long_term_debt"] or 0

        if ca > 0 or nca > 0:
            bs["total_assets"] = round(ca + nca, 2)
        if cl > 0 or ncl > 0:
            bs["total_liabilities"] = round(cl + ncl, 2)

        result.partial_bs = bs

    # ── Step 6: Estimate revenue if missing ─────────────────────────

    def _estimate_revenue(self, result: ReconstructedFinancials):
        if result.accounts.get("revenue"):
            return  # Revenue is known — no estimation needed

        total_opex = result.accounts.get("selling_expenses", 0) + result.accounts.get("admin_expenses", 0)
        other_exp = result.accounts.get("other_expense", 0)
        total_costs = total_opex + other_exp

        if total_costs <= 0:
            return

        # Estimate revenue range based on typical margin assumptions
        # Low margin scenario (fuel distribution ~7-12% net margin):
        #   costs = 88-93% of revenue → revenue = costs / 0.88 to costs / 0.93
        # Medium margin (general business ~15-25%):
        #   costs = 75-85% of revenue
        # High margin (services ~30-50%):
        #   costs = 50-70% of revenue
        # BUT: total_costs here is only OpEx, not COGS. OpEx is typically 5-30% of revenue.

        result.revenue_estimate = RevenueEstimate(
            low=round(total_costs / 0.30, 0),      # OpEx = 30% of revenue (minimum)
            mid=round(total_costs / 0.12, 0),       # OpEx = 12% of revenue (typical)
            high=round(total_costs / 0.05, 0),      # OpEx = 5% of revenue (large company)
            method="Estimated from operating expense structure. "
                   "Low assumes OpEx is 30% of revenue (small company). "
                   "Mid assumes 12% (typical). High assumes 5% (large/commodity).",
        )

    # ── Step 7: Company character (WEIGHTED SIGNAL SCORING) ─────────

    def _detect_company_character(self, result: ReconstructedFinancials):
        char = CompanyCharacter()
        a = result.accounts

        # ── Signal scoring engine ──
        scores = {
            "fuel_energy": 0.0,
            "logistics_transport": 0.0,
            "retail_network": 0.0,
            "manufacturing": 0.0,
            "services": 0.0,
            "infrastructure": 0.0,
        }

        total_opex = a.get("selling_expenses", 0) + a.get("admin_expenses", 0)
        other_exp = a.get("other_expense", 0)
        total_costs = total_opex + other_exp if total_opex + other_exp > 0 else 1

        # Scan line items for signals
        dep_total = 0
        payroll_total = 0
        rent_total = 0
        fuel_transport_total = 0
        security_total = 0
        marketing_total = 0

        for item in result.line_items:
            name = str(item.get("name", "") or "").lower()
            cat = str(item.get("category", "") or "").lower()
            subcat = str(item.get("subcategory", "") or "").lower()
            amt = abs(item.get("amount", 0))
            all_text = f"{name} {cat} {subcat}"

            # Depreciation
            if "depreciation" in all_text or "amortization" in all_text:
                dep_total += amt

            # Payroll
            if "payroll" in all_text or "wages" in all_text or "salary" in all_text:
                payroll_total += amt

            # Fuel/energy
            if any(kw in all_text for kw in _FUEL_KEYWORDS):
                scores["fuel_energy"] += 3
                fuel_transport_total += amt

            # Transport
            if any(kw in all_text for kw in _TRANSPORT_KEYWORDS):
                scores["logistics_transport"] += 2
                fuel_transport_total += amt

            # Rent (gas stations = retail network)
            if any(kw in all_text for kw in _RENT_KEYWORDS):
                rent_total += amt
                if "station" in all_text or "აგს" in all_text or "азс" in all_text:
                    scores["retail_network"] += 3
                    scores["fuel_energy"] += 2

            # Security
            if any(kw in all_text for kw in _SECURITY_KEYWORDS):
                security_total += amt
                scores["infrastructure"] += 1

            # Marketing
            if "marketing" in all_text or "advertising" in all_text or "რეკლამ" in all_text:
                marketing_total += amt

        # ── Weight-based scoring from ratios ──

        # Depreciation intensity
        if total_opex > 0:
            dep_ratio = dep_total / total_opex
            if dep_ratio > 0.30:
                scores["infrastructure"] += 4
                scores["fuel_energy"] += 2
                char.asset_intensity = "heavy"
            elif dep_ratio > 0.15:
                scores["infrastructure"] += 2
                scores["manufacturing"] += 1
                char.asset_intensity = "moderate"
            else:
                scores["services"] += 2
                char.asset_intensity = "light"
        else:
            char.asset_intensity = "unknown"

        # Interest/leverage intensity
        if total_costs > 1:
            interest_ratio = other_exp / total_costs
            if interest_ratio > 0.25:
                char.leverage_level = "critical"
                scores["infrastructure"] += 2
            elif interest_ratio > 0.15:
                char.leverage_level = "high"
                scores["infrastructure"] += 1
            elif interest_ratio > 0.08:
                char.leverage_level = "moderate"
            else:
                char.leverage_level = "low"
        else:
            char.leverage_level = "unknown"

        # Payroll intensity
        if total_opex > 0:
            payroll_ratio = payroll_total / total_opex
            if payroll_ratio > 0.50:
                scores["services"] += 3
            elif payroll_ratio > 0.30:
                scores["services"] += 1

        # Fuel/transport presence amplifier
        if fuel_transport_total > 0 and total_opex > 0:
            ft_ratio = fuel_transport_total / total_opex
            if ft_ratio > 0.05:
                scores["fuel_energy"] += 2
                scores["logistics_transport"] += 1

        # ── Determine winner ──
        char.signal_scores = {k: round(v, 1) for k, v in scores.items() if v > 0}
        max_score = max(scores.values()) if scores else 0
        total_score = sum(scores.values()) if scores else 1

        if max_score == 0:
            char.industry = "unclassified"
            char.industry_confidence = 0.0
        else:
            winner = max(scores, key=scores.get)
            char.industry_confidence = round(max_score / max(total_score, 1), 2)

            industry_labels = {
                "fuel_energy": "fuel_distribution",
                "logistics_transport": "logistics_transport",
                "retail_network": "retail_network",
                "manufacturing": "manufacturing",
                "services": "professional_services",
                "infrastructure": "infrastructure_heavy",
            }
            char.industry = industry_labels.get(winner, winner)

        # Business model description
        model_parts = []
        if scores.get("fuel_energy", 0) > 3:
            model_parts.append("fuel/energy distribution")
        if scores.get("retail_network", 0) > 2:
            model_parts.append("with retail station network")
        if scores.get("logistics_transport", 0) > 2:
            model_parts.append("logistics-intensive")
        if char.asset_intensity == "heavy":
            model_parts.append("asset-heavy infrastructure")
        if char.leverage_level in ("high", "critical"):
            model_parts.append("debt-financed")
        char.business_model = ", ".join(model_parts) if model_parts else "unclassified business model"

        # Risk profile
        risk_score = 0
        if char.leverage_level == "critical": risk_score += 3
        elif char.leverage_level == "high": risk_score += 2
        elif char.leverage_level == "moderate": risk_score += 1

        if char.asset_intensity == "heavy": risk_score += 1

        if risk_score >= 4:
            char.risk_profile = "high"
        elif risk_score >= 2:
            char.risk_profile = "elevated"
        elif risk_score >= 1:
            char.risk_profile = "moderate"
        else:
            char.risk_profile = "conservative"

        # Operational complexity
        unique_categories = len(result.expense_breakdown)
        if unique_categories > 15:
            char.operational_complexity = "high"
        elif unique_categories > 8:
            char.operational_complexity = "moderate"
        else:
            char.operational_complexity = "simple"

        # Signals (human-readable)
        signals = []
        if dep_total > 0:
            signals.append(f"Depreciation {dep_total:,.0f} GEL ({dep_total/max(total_opex,1)*100:.0f}% of OpEx) — {char.asset_intensity} asset base")
        if payroll_total > 0:
            signals.append(f"Payroll {payroll_total:,.0f} GEL ({payroll_total/max(total_opex,1)*100:.0f}% of OpEx)")
        if other_exp > 0:
            signals.append(f"Interest/other expenses {other_exp:,.0f} GEL ({other_exp/max(total_costs,1)*100:.0f}% of total costs) — {char.leverage_level} leverage")
        if fuel_transport_total > 0:
            signals.append(f"Fuel/transport costs detected — energy/logistics sector")
        if rent_total > 0:
            signals.append(f"Rental costs {rent_total:,.0f} GEL — physical infrastructure")
        char.signals = signals

        result.company_character = char

    # ── Step 8: Generate insights ───────────────────────────────────

    def _generate_insights(self, result: ReconstructedFinancials):
        a = result.accounts
        pl = result.partial_pl
        char = result.company_character
        insights = []

        total_opex = a.get("selling_expenses", 0) + a.get("admin_expenses", 0)
        other_exp = a.get("other_expense", 0)
        other_inc = a.get("other_income", 0)
        total_costs = total_opex + other_exp

        # ── Missing data (critical) ──
        if result.completeness.data_type == "expenses_only":
            insights.append(FinancialInsight(
                category="missing_data", severity="critical",
                title="Partial Data — Expenses Only",
                explanation="This file contains only operating expense accounts (73XX, 74XX) and other income/expenses (81XX, 82XX). "
                           "Revenue (61XX) and Cost of Goods Sold (71XX) are NOT present.",
                impact="Profitability analysis, margin calculations, health scoring, and strategic recommendations are NOT possible.",
                consequence="Without revenue data, the system cannot determine if the business is profitable, assess margin trends, or evaluate financial health.",
                action="Upload a Trial Balance or Revenue file to enable full financial analysis.",
            ))

        # ── Interest burden (with impact + consequence) ──
        if other_exp > 0 and total_costs > 0:
            interest_ratio = other_exp / total_costs * 100
            if interest_ratio > 25:
                insights.append(FinancialInsight(
                    category="risk", severity="critical",
                    title="Critical Financial Leverage",
                    explanation=f"Interest and other non-operating expenses ({other_exp:,.0f} GEL) represent "
                               f"{interest_ratio:.0f}% of total cost structure. Industry healthy range is 5-10%.",
                    impact="The company's profitability is extremely sensitive to interest rate changes and revenue fluctuations. "
                           "A small revenue decline could push the company into loss.",
                    consequence="If interest rates rise 1-2%, or if revenue drops 5-10%, the company may face liquidity distress.",
                    action="Immediate review of debt structure. Consider refinancing at lower rates, debt-for-equity swap, or asset disposal to reduce leverage.",
                    metric="interest_to_total_costs_pct", value=interest_ratio, benchmark=10.0,
                ))
            elif interest_ratio > 15:
                insights.append(FinancialInsight(
                    category="risk", severity="warning",
                    title="Elevated Debt Service Costs",
                    explanation=f"Interest/other expenses are {interest_ratio:.0f}% of total costs ({other_exp:,.0f} GEL). "
                               f"This is above the 10-15% caution threshold.",
                    impact="Debt is consuming a significant portion of operating cash flow.",
                    action="Monitor debt covenants and refinancing opportunities.",
                    metric="interest_to_total_costs_pct", value=interest_ratio, benchmark=10.0,
                ))

        # ── Depreciation (asset intensity) ──
        dep_total = sum(abs(item.get("amount", 0)) for item in result.line_items
                       if any(kw in str(item.get("category", "")).lower() + str(item.get("subcategory", "")).lower()
                             for kw in ["depreciation", "amortization"]))

        if dep_total > 0 and total_opex > 0:
            dep_ratio = dep_total / total_opex * 100
            insights.append(FinancialInsight(
                category="structure", severity="info" if dep_ratio < 40 else "warning",
                title=f"{'Heavy' if dep_ratio > 40 else 'Significant'} Fixed Asset Base",
                explanation=f"Depreciation & amortization: {dep_total:,.0f} GEL ({dep_ratio:.0f}% of operating expenses). "
                           f"This indicates {'massive' if dep_ratio > 50 else 'substantial'} capital investment in physical assets.",
                impact="High depreciation means large prior capital investment. Asset utilization efficiency is critical.",
                action="Review asset utilization rates. Ensure return on invested capital exceeds cost of capital." if dep_ratio > 40 else "",
                metric="depreciation_to_opex_pct", value=dep_ratio,
            ))

        # ── Payroll analysis ──
        payroll_total = sum(abs(item.get("amount", 0)) for item in result.line_items
                          if any(kw in str(item.get("category", "")).lower() + str(item.get("subcategory", "")).lower()
                                for kw in ["payroll", "wages", "salary", "bonus", "premium"]))

        if payroll_total > 0 and total_opex > 0:
            payroll_ratio = payroll_total / total_opex * 100
            insights.append(FinancialInsight(
                category="structure", severity="info",
                title="Labor Cost Analysis",
                explanation=f"Total compensation: {payroll_total:,.0f} GEL ({payroll_ratio:.0f}% of OpEx). "
                           f"{'Labor-intensive operation.' if payroll_ratio > 40 else 'Moderate labor costs relative to other expenses.'}",
                metric="payroll_to_opex_pct", value=payroll_ratio,
            ))

        # ── Expense concentration ──
        if result.expense_breakdown:
            sorted_exp = sorted(result.expense_breakdown.items(), key=lambda x: -x[1])
            if len(sorted_exp) >= 3:
                top3_total = sum(v for _, v in sorted_exp[:3])
                all_total = sum(v for _, v in sorted_exp)
                if all_total > 0:
                    concentration = top3_total / all_total * 100
                    top3_names = [k for k, _ in sorted_exp[:3]]
                    insights.append(FinancialInsight(
                        category="structure", severity="info",
                        title="Expense Concentration",
                        explanation=f"Top 3 expense categories ({', '.join(top3_names)}) represent {concentration:.0f}% of total costs. "
                                   f"{'Highly concentrated — risk if any category spikes.' if concentration > 70 else 'Well diversified cost base.'}",
                        metric="top3_concentration_pct", value=concentration,
                    ))

        # ── Revenue insights (if available) ──
        revenue = a.get("revenue", 0)
        cogs = a.get("cogs", 0)
        if revenue > 0 and cogs > 0:
            margin = (revenue - cogs) / revenue * 100
            if margin < 10:
                insights.append(FinancialInsight(
                    category="risk", severity="critical",
                    title="Critically Thin Gross Margins",
                    explanation=f"Gross margin is only {margin:.1f}%. For fuel distribution, 7-12% is typical but below 10% is danger zone.",
                    impact="Very little room to absorb cost increases or revenue declines.",
                    consequence="A 2-3% increase in COGS or decrease in pricing could eliminate profitability entirely.",
                    action="Review pricing strategy, supplier contracts, and volume incentives.",
                    metric="gross_margin_pct", value=margin, benchmark=12.0,
                ))

        result.insights = insights

    # ── Step 9: Cross-signal reasoning ──────────────────────────────

    def _cross_signal_reasoning(self, result: ReconstructedFinancials):
        """Connect signals that individually seem minor but together tell a story."""
        a = result.accounts
        char = result.company_character
        insights = result.insights

        revenue_missing = a.get("revenue") is None
        has_leverage = char.leverage_level in ("high", "critical")
        has_heavy_assets = char.asset_intensity == "heavy"
        total_opex = a.get("selling_expenses", 0) + a.get("admin_expenses", 0)

        # Cross 1: Leverage + missing revenue = CANNOT ASSESS SOLVENCY
        if revenue_missing and has_leverage:
            insights.append(FinancialInsight(
                category="relationship", severity="critical",
                title="Leverage Risk Cannot Be Fully Assessed",
                explanation="Significant debt service costs are detected, but revenue is unknown. "
                           "Without knowing revenue, we cannot determine if the company can service its debt.",
                impact="Interest coverage ratio, debt service capacity, and solvency risk cannot be computed.",
                consequence="Lending decisions, credit assessment, and investment analysis are unreliable without revenue data.",
                action="Obtain revenue data immediately to assess debt sustainability.",
                confidence=0.95,
            ))

        # Cross 2: Heavy assets + missing revenue = EFFICIENCY UNKNOWN
        if revenue_missing and has_heavy_assets:
            insights.append(FinancialInsight(
                category="relationship", severity="warning",
                title="Asset Utilization Cannot Be Determined",
                explanation="Large fixed asset base detected (heavy depreciation), but revenue is missing. "
                           "Cannot determine if these assets are generating adequate returns.",
                impact="Return on assets (ROA), asset turnover, and capital efficiency are unknown.",
                action="Upload revenue data to evaluate asset productivity.",
                confidence=0.90,
            ))

        # Cross 3: High interest + heavy depreciation = CAPITAL-INTENSIVE LEVERAGED BUSINESS
        if has_leverage and has_heavy_assets:
            insights.append(FinancialInsight(
                category="relationship", severity="warning",
                title="Capital-Intensive, Leveraged Business Model",
                explanation="The combination of heavy fixed assets AND high debt service indicates a business "
                           "that financed its asset base with debt. This is common in energy/infrastructure but carries risk.",
                impact="Cash flow must cover both depreciation reinvestment AND debt service — double capital burden.",
                action="Review whether cash generation covers both CAPEX replacement and debt repayment.",
                confidence=0.85,
            ))

        # Cross 4: Fuel signals + depreciation + rent = fuel distribution with station network
        fuel_score = result.company_character.signal_scores.get("fuel_energy", 0)
        retail_score = result.company_character.signal_scores.get("retail_network", 0)
        if fuel_score > 3 and retail_score > 0:
            insights.append(FinancialInsight(
                category="structure", severity="positive",
                title="Fuel Distribution with Retail Infrastructure",
                explanation="Multiple signals confirm this is a fuel/energy distribution business with a physical retail network "
                           "(gas stations, transport fleet, utility costs, security).",
                impact="Revenue is likely driven by fuel volumes and margins, which are commodity-sensitive.",
                confidence=0.90,
            ))

    # ── Step 10: User message (CFO-level) ───────────────────────────

    def _build_user_message(self, result: ReconstructedFinancials):
        comp = result.completeness
        pl = result.partial_pl
        char = result.company_character
        lines = []

        # Header — what kind of data this is
        type_labels = {
            "full_pl": "Complete P&L data detected. Full financial analysis available.",
            "basic_pl": "Basic P&L data found (Revenue + COGS). Detailed expense breakdown not available.",
            "expenses_only": "PARTIAL DATA: This file contains ONLY expense accounts.",
            "revenue_only": "Revenue data found, but cost structure is missing.",
            "balance_sheet": "Balance sheet data detected.",
            "unknown": "Unable to classify this financial data.",
        }
        lines.append(type_labels.get(comp.data_type, comp.data_type))

        # What we found
        if comp.data_type == "expenses_only":
            lines.append("")
            lines.append("What was found:")
            if pl.get("total_opex"):
                lines.append(f"  Operating Expenses: {pl['total_opex']:,.0f} GEL")
                if pl.get("selling_expenses"):
                    lines.append(f"    Selling & Distribution: {pl['selling_expenses']:,.0f} GEL")
                if pl.get("admin_expenses"):
                    lines.append(f"    General & Administrative: {pl['admin_expenses']:,.0f} GEL")
            if pl.get("other_expense"):
                lines.append(f"  Interest/Other Expense: {pl['other_expense']:,.0f} GEL")
            if pl.get("other_income"):
                lines.append(f"  Other Income: {pl['other_income']:,.0f} GEL")

            lines.append("")
            lines.append("What is MISSING:")
            lines.append("  Revenue (accounts 61XX-62XX)")
            lines.append("  Cost of Goods Sold (accounts 71XX)")
            lines.append("")
            lines.append("CONSEQUENCE: Profitability, margins, health score, and strategic analysis CANNOT be performed.")

        # Company character
        if char.industry != "unknown" and char.industry != "unclassified":
            lines.append("")
            lines.append(f"Company Profile: {char.industry.replace('_', ' ').title()}")
            lines.append(f"  Business Model: {char.business_model}")
            lines.append(f"  Asset Intensity: {char.asset_intensity}")
            lines.append(f"  Leverage: {char.leverage_level}")
            lines.append(f"  Risk Profile: {char.risk_profile}")

        # Revenue estimate
        if result.revenue_estimate:
            est = result.revenue_estimate
            lines.append("")
            lines.append(f"Estimated Revenue Range (based on cost structure):")
            lines.append(f"  Low:  {est.low:>15,.0f} GEL (if OpEx is 30% of revenue)")
            lines.append(f"  Mid:  {est.mid:>15,.0f} GEL (if OpEx is 12% of revenue)")
            lines.append(f"  High: {est.high:>15,.0f} GEL (if OpEx is 5% of revenue)")
            lines.append(f"  {est.disclaimer}")

        # Critical insights summary
        critical = [i for i in result.insights if i.severity == "critical"]
        if critical:
            lines.append("")
            lines.append(f"CRITICAL FINDINGS ({len(critical)}):")
            for i in critical:
                lines.append(f"  {i.title}")

        result.user_message = "\n".join(lines)

    # ── Step 11: Prioritized suggestions ────────────────────────────

    def _generate_suggestions(self, result: ReconstructedFinancials):
        comp = result.completeness
        suggestions = []

        if not comp.can_build_pl:
            suggestions.append({
                "priority": "1 (Best)",
                "action": "Upload Trial Balance",
                "detail": "A trial balance contains ALL accounts — revenue, costs, and balance sheet. "
                          "This enables full financial reconstruction in one step.",
            })
            if "revenue" not in comp.groups_found:
                suggestions.append({
                    "priority": "2",
                    "action": "Upload Revenue File",
                    "detail": "Revenue data (accounts 61XX-62XX) enables P&L construction and profitability analysis.",
                })
            if "cogs" not in comp.groups_found:
                suggestions.append({
                    "priority": "2",
                    "action": "Upload COGS File",
                    "detail": "Cost of Goods Sold (accounts 71XX) is needed for gross margin calculation.",
                })

        if not comp.can_build_bs:
            suggestions.append({
                "priority": "3",
                "action": "Upload Balance Sheet",
                "detail": "Balance sheet data enables liquidity, leverage, and solvency analysis.",
            })

        if comp.data_type == "expenses_only":
            suggestions.append({
                "priority": "Now",
                "action": "Review Expense Analysis",
                "detail": "Detailed expense breakdown is available on the Costs & OpEx page. "
                          f"{len(result.expense_breakdown)} expense categories identified.",
            })

        critical_count = sum(1 for i in result.insights if i.severity == "critical")
        if critical_count > 0:
            suggestions.append({
                "priority": "Urgent",
                "action": f"Address {critical_count} Critical Finding(s)",
                "detail": "Review the Insights panel for critical risk signals requiring attention.",
            })

        if comp.can_build_pl:
            suggestions.append({
                "priority": "Ready",
                "action": "Run Full Analysis",
                "detail": "Complete data available. Run the Orchestrator for 7-stage AI intelligence pipeline.",
            })

        result.suggestions = suggestions


# Module-level singleton
reconstruction_engine = FinancialReconstructionEngine()
