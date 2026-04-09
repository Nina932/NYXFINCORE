"""
income_statement.py — Structured Income Statement builder.
Computes Revenue/COGS/Margins with Wholesale/Retail/Other breakdown,
G&A from account codes, and EBITDA from actual data.
"""
from typing import List, Dict, Any
from dataclasses import dataclass, field
from app.services.file_parser import get_english_name, GA_ACCOUNT_NAMES, DA_ACCOUNT_NAMES, DA_ACCOUNT_CODES, _classify_revenue_product


@dataclass
class IncomeStatement:
    """Full structured income statement with all breakdowns."""
    period: str = ""
    currency: str = "GEL"

    # Revenue breakdown
    revenue_wholesale_petrol: float = 0.0
    revenue_wholesale_diesel: float = 0.0
    revenue_wholesale_bitumen: float = 0.0
    revenue_wholesale_cng: float = 0.0
    revenue_wholesale_lpg: float = 0.0
    revenue_wholesale_total: float = 0.0

    revenue_retail_petrol: float = 0.0
    revenue_retail_diesel: float = 0.0
    revenue_retail_cng: float = 0.0
    revenue_retail_lpg: float = 0.0
    revenue_retail_total: float = 0.0

    other_revenue_total: float = 0.0
    total_revenue: float = 0.0

    # COGS breakdown
    cogs_wholesale_petrol: float = 0.0
    cogs_wholesale_diesel: float = 0.0
    cogs_wholesale_bitumen: float = 0.0
    cogs_wholesale_cng: float = 0.0
    cogs_wholesale_lpg: float = 0.0
    cogs_wholesale_total: float = 0.0

    cogs_retail_petrol: float = 0.0
    cogs_retail_diesel: float = 0.0
    cogs_retail_cng: float = 0.0
    cogs_retail_lpg: float = 0.0
    cogs_retail_total: float = 0.0

    other_cogs_total: float = 0.0
    total_cogs: float = 0.0

    # Margins (per sub-category)
    margin_wholesale_petrol: float = 0.0
    margin_wholesale_diesel: float = 0.0
    margin_wholesale_bitumen: float = 0.0
    margin_wholesale_cng: float = 0.0
    margin_wholesale_lpg: float = 0.0
    margin_wholesale_total: float = 0.0

    margin_retail_petrol: float = 0.0
    margin_retail_diesel: float = 0.0
    margin_retail_cng: float = 0.0
    margin_retail_lpg: float = 0.0
    margin_retail_total: float = 0.0

    total_gross_margin: float = 0.0
    total_gross_profit: float = 0.0  # margin + other revenue

    # Below margin
    ga_expenses: float = 0.0
    ga_breakdown: Dict[str, float] = field(default_factory=dict)
    ebitda: float = 0.0

    # D&A (separated from G&A for proper waterfall)
    da_expenses: float = 0.0
    da_breakdown: Dict[str, float] = field(default_factory=dict)

    # Below EBITDA — full P&L waterfall
    ebit: float = 0.0
    other_income: float = 0.0  # Non-operating income (class 8: FX gains, asset sales, etc.)
    other_income_breakdown: Dict[str, float] = field(default_factory=dict)
    other_expense: float = 0.0  # Non-operating expenses (82xx, 83xx)
    other_expense_breakdown: Dict[str, float] = field(default_factory=dict)
    finance_income: float = 0.0
    finance_expense: float = 0.0
    finance_net: float = 0.0
    ebt: float = 0.0
    tax_expense: float = 0.0
    net_profit: float = 0.0

    # COGS column breakdown totals
    cogs_col6_total: float = 0.0
    cogs_col7310_total: float = 0.0
    cogs_col8230_total: float = 0.0

    # Revenue aggregates
    revenue_gross_total: float = 0.0
    revenue_vat_total: float = 0.0

    # Drill-down data
    revenue_by_product: List[Dict] = field(default_factory=list)
    cogs_by_product: List[Dict] = field(default_factory=list)

    def _get_children(self, category: str, source: str = "revenue") -> List[Dict]:
        """Get product-level children for a category row (for drill-down)."""
        items = self.revenue_by_product if source == "revenue" else self.cogs_by_product
        children = []
        for p in items:
            if p.get("category") == category:
                amt = float(p.get("net", 0) if source == "revenue" else p.get("total_cogs", 0))
                children.append({
                    "product": p.get("product_en") or p.get("product", ""),
                    "product_ka": p.get("product", ""),
                    "amount": round(amt, 2),
                })
        return sorted(children, key=lambda x: -abs(x["amount"]))

    def to_rows(self) -> List[Dict]:
        """Convert to frontend row format {c, l, ac, pl, lvl, bold, sep, s, children}."""
        rows = []

        def add(code, label, actual, plan=0, level=0, bold=False, sep=False, sign=1, children=None):
            row = {
                "c": code, "l": label,
                "ac": round(actual, 2), "pl": round(plan, 2),
                "lvl": level, "bold": bold, "sep": sep, "s": sign,
            }
            if children:
                row["children"] = children
            rows.append(row)

        # ── REVENUE ──────────────────────────────────────────────
        add("REV", "REVENUE", self.total_revenue, 0, 0, True, True, 1)

        add("REV.W", "Revenue Wholesale", self.revenue_wholesale_total, 0, 1, True, False, 1)
        add("REV.W.P", "Revenue Whsale Petrol (Lari)", self.revenue_wholesale_petrol, 0, 2, False, False, 1,
            self._get_children("Revenue Whsale Petrol", "revenue"))
        add("REV.W.D", "Revenue Whsale Diesel (Lari)", self.revenue_wholesale_diesel, 0, 2, False, False, 1,
            self._get_children("Revenue Whsale Diesel", "revenue"))
        add("REV.W.B", "Revenue Whsale Bitumen (Lari)", self.revenue_wholesale_bitumen, 0, 2, False, False, 1,
            self._get_children("Revenue Whsale Bitumen", "revenue"))
        add("REV.W.CNG", "Revenue Whsale CNG (Lari)", self.revenue_wholesale_cng, 0, 2, False, False, 1,
            self._get_children("Revenue Whsale CNG", "revenue"))
        add("REV.W.LPG", "Revenue Whsale LPG (Lari)", self.revenue_wholesale_lpg, 0, 2, False, False, 1,
            self._get_children("Revenue Whsale LPG", "revenue"))

        add("REV.R", "Revenue Retail", self.revenue_retail_total, 0, 1, True, False, 1)
        add("REV.R.P", "Revenue Retial Petrol (Lari)", self.revenue_retail_petrol, 0, 2, False, False, 1,
            self._get_children("Revenue Retial Petrol", "revenue"))
        add("REV.R.D", "Revenue Retial Diesel (Lari)", self.revenue_retail_diesel, 0, 2, False, False, 1,
            self._get_children("Revenue Retial Diesel", "revenue"))
        add("REV.R.CNG", "Revenue Retial CNG (Lari)", self.revenue_retail_cng, 0, 2, False, False, 1,
            self._get_children("Revenue Retial CNG", "revenue"))
        add("REV.R.LPG", "Revenue Retial LPG (Lari)", self.revenue_retail_lpg, 0, 2, False, False, 1,
            self._get_children("Revenue Retial LPG", "revenue"))

        # ── COGS ─────────────────────────────────────────────────
        add("COGS", "COST OF GOODS SOLD", self.total_cogs, 0, 0, True, True, -1)

        add("COGS.W", "COGS Wholesale", self.cogs_wholesale_total, 0, 1, True, False, -1)
        add("COGS.W.P", "COGS Whsale Petrol (Lari)", self.cogs_wholesale_petrol, 0, 2, False, False, -1,
            self._get_children("COGS Whsale Petrol", "cogs"))
        add("COGS.W.D", "COGS Whsale Diesel (Lari)", self.cogs_wholesale_diesel, 0, 2, False, False, -1,
            self._get_children("COGS Whsale Diesel", "cogs"))
        add("COGS.W.B", "COGS Whsale Bitumen (Lari)", self.cogs_wholesale_bitumen, 0, 2, False, False, -1,
            self._get_children("COGS Whsale Bitumen", "cogs"))
        add("COGS.W.CNG", "COGS Whsale CNG (Lari)", self.cogs_wholesale_cng, 0, 2, False, False, -1,
            self._get_children("COGS Whsale CNG", "cogs"))
        add("COGS.W.LPG", "COGS Whsale LPG (Lari)", self.cogs_wholesale_lpg, 0, 2, False, False, -1,
            self._get_children("COGS Whsale LPG", "cogs"))

        add("COGS.R", "COGS Retail", self.cogs_retail_total, 0, 1, True, False, -1)
        add("COGS.R.P", "COGS Retial Petrol (Lari)", self.cogs_retail_petrol, 0, 2, False, False, -1,
            self._get_children("COGS Retial Petrol", "cogs"))
        add("COGS.R.D", "COGS Retial Diesel (Lari)", self.cogs_retail_diesel, 0, 2, False, False, -1,
            self._get_children("COGS Retial Diesel", "cogs"))
        add("COGS.R.CNG", "COGS Retial CNG (Lari)", self.cogs_retail_cng, 0, 2, False, False, -1,
            self._get_children("COGS Retial CNG", "cogs"))
        add("COGS.R.LPG", "COGS Retial LPG (Lari)", self.cogs_retail_lpg, 0, 2, False, False, -1,
            self._get_children("COGS Retial LPG", "cogs"))

        add("COGS.O", "Other COGS", self.other_cogs_total, 0, 1, False, False, -1)

        # ── GROSS MARGIN ─────────────────────────────────────────
        add("GM", "GROSS MARGIN", self.total_gross_margin, 0, 0, True, True, 1)

        add("GM.W", "Gr. Margin Wholesale", self.margin_wholesale_total, 0, 1, True, False,
            1 if self.margin_wholesale_total >= 0 else -1)
        add("GM.W.P", "Gr. Margin Whsale Petrol (Lari)", self.margin_wholesale_petrol, 0, 2, False, False,
            1 if self.margin_wholesale_petrol >= 0 else -1)
        add("GM.W.D", "Gr. Margin Whsale Diesel (Lari)", self.margin_wholesale_diesel, 0, 2, False, False,
            1 if self.margin_wholesale_diesel >= 0 else -1)
        add("GM.W.B", "Gr. Margin Whsale Bitumen (Lari)", self.margin_wholesale_bitumen, 0, 2, False, False,
            1 if self.margin_wholesale_bitumen >= 0 else -1)
        add("GM.W.CNG", "Gr. Margin Whsale CNG (Lari)", self.margin_wholesale_cng, 0, 2, False, False,
            1 if self.margin_wholesale_cng >= 0 else -1)
        add("GM.W.LPG", "Gr. Margin Whsale LPG (Lari)", self.margin_wholesale_lpg, 0, 2, False, False,
            1 if self.margin_wholesale_lpg >= 0 else -1)

        add("GM.R", "Gr. Margin Retail", self.margin_retail_total, 0, 1, True, False, 1)
        add("GM.R.P", "Gr. Margin Retial Petrol (Lari)", self.margin_retail_petrol, 0, 2, False, False, 1)
        add("GM.R.D", "Gr. Margin Retial Diesel (Lari)", self.margin_retail_diesel, 0, 2, False, False, 1)
        add("GM.R.CNG", "Gr. Margin Retial CNG (Lari)", self.margin_retail_cng, 0, 2, False, False, 1)
        add("GM.R.LPG", "Gr. Margin Retial LPG (Lari)", self.margin_retail_lpg, 0, 2, False, False, 1)

        # Other Revenue as separate line
        add("OR", "Other Revenue", self.other_revenue_total, 0, 1, False, False, 1)

        # ── TOTAL GROSS PROFIT ───────────────────────────────────
        add("TGP", "Total Gross Profit", self.total_gross_profit, 0, 0, True, True, 1)

        # ── G&A EXPENSES ─────────────────────────────────────────
        add("GA", "General and Administrative Expenses", self.ga_expenses, 0, 0, True, False, -1)
        for code, amt in sorted(self.ga_breakdown.items(), key=lambda x: -x[1]):
            display_name = GA_ACCOUNT_NAMES.get(code, f"G&A ({code})")
            add(f"GA.{code}", display_name, amt, 0, 2, False, False, -1)

        # ── EBITDA ───────────────────────────────────────────────
        add("EBITDA", "EBITDA", self.ebitda, 0, 0, True, True, 1)

        # ── D&A (Depreciation & Amortization) ──────────────────
        add("DA", "Depreciation & Amortization", self.da_expenses, 0, 0, True, False, -1)
        for code, amt in sorted(self.da_breakdown.items(), key=lambda x: -x[1]):
            display_name = DA_ACCOUNT_NAMES.get(code, f"D&A ({code})")
            add(f"DA.{code}", display_name, amt, 0, 2, False, False, -1)

        # ── EBIT (Operating Profit) ────────────────────────────
        add("EBIT", "EBIT (Operating Profit)", self.ebit, 0, 0, True, True, 1)

        # ── Non-Operating Income (class 8: FX gains, asset sales, etc.) ──
        if self.other_income:
            add("OI", "Other Income (Non-operating)", self.other_income, 0, 0, True, False, 1)
            for name, amt in sorted(self.other_income_breakdown.items(), key=lambda x: -x[1]):
                add(f"OI.{name[:8]}", name, amt, 0, 1, False, False, 1)

        # ── Non-Operating Expenses (82xx, 83xx) ──────────────────
        if self.other_expense:
            add("OE", "Other Expenses (Non-operating)", self.other_expense, 0, 0, True, False, -1)
            for name, amt in sorted(self.other_expense_breakdown.items(), key=lambda x: -x[1]):
                add(f"OE.{name[:8]}", name, amt, 0, 1, False, False, -1)

        # ── Finance Income / Expense ───────────────────────────
        if self.finance_income or self.finance_expense:
            add("FIN", "Finance Income / (Expense)", self.finance_net, 0, 0, True, False,
                1 if self.finance_net >= 0 else -1)
            if self.finance_income:
                add("FIN.I", "Finance Income", self.finance_income, 0, 1, False, False, 1)
            if self.finance_expense:
                add("FIN.E", "Finance Expense", self.finance_expense, 0, 1, False, False, -1)

        # ── EBT (Earnings Before Tax) ──────────────────────────
        add("EBT", "Earnings Before Tax", self.ebt, 0, 0, True, True, 1)

        # ── Income Tax ─────────────────────────────────────────
        add("TAX", "Income Tax", self.tax_expense, 0, 0, True, False, -1)

        # ── Net Profit ─────────────────────────────────────────
        add("NP", "Net Profit", self.net_profit, 0, 0, True, True, 1)

        return rows

    def generate_narrative(self) -> Dict:
        """Generate AI narrative commentary for this income statement.

        Returns a dict with executive_summary, sections, recommendations, warnings.
        Uses the NarrativeEngine for template-based generation (no API call).
        """
        try:
            from app.services.narrative_engine import narrative_engine
            narrative = narrative_engine.generate_income_statement_narrative(
                self.to_dict(), period=self.period
            )
            return narrative.to_dict()
        except Exception:
            return {}

    def to_dict(self) -> Dict:
        """Full dictionary representation for API responses."""
        return {
            "period": self.period,
            "currency": self.currency,
            "revenue": {
                "wholesale": {
                    "total": round(self.revenue_wholesale_total, 2),
                    "petrol": round(self.revenue_wholesale_petrol, 2),
                    "diesel": round(self.revenue_wholesale_diesel, 2),
                    "bitumen": round(self.revenue_wholesale_bitumen, 2),
                    "cng": round(self.revenue_wholesale_cng, 2),
                    "lpg": round(self.revenue_wholesale_lpg, 2),
                },
                "retail": {
                    "total": round(self.revenue_retail_total, 2),
                    "petrol": round(self.revenue_retail_petrol, 2),
                    "diesel": round(self.revenue_retail_diesel, 2),
                    "cng": round(self.revenue_retail_cng, 2),
                    "lpg": round(self.revenue_retail_lpg, 2),
                },
                "other": round(self.other_revenue_total, 2),
                "total": round(self.total_revenue, 2),
            },
            "cogs": {
                "wholesale": {
                    "total": round(self.cogs_wholesale_total, 2),
                    "petrol": round(self.cogs_wholesale_petrol, 2),
                    "diesel": round(self.cogs_wholesale_diesel, 2),
                    "bitumen": round(self.cogs_wholesale_bitumen, 2),
                    "cng": round(self.cogs_wholesale_cng, 2),
                    "lpg": round(self.cogs_wholesale_lpg, 2),
                },
                "retail": {
                    "total": round(self.cogs_retail_total, 2),
                    "petrol": round(self.cogs_retail_petrol, 2),
                    "diesel": round(self.cogs_retail_diesel, 2),
                    "cng": round(self.cogs_retail_cng, 2),
                    "lpg": round(self.cogs_retail_lpg, 2),
                },
                "other": round(self.other_cogs_total, 2),
                "total": round(self.total_cogs, 2),
            },
            "margins": {
                "wholesale": {
                    "total": round(self.margin_wholesale_total, 2),
                    "petrol": round(self.margin_wholesale_petrol, 2),
                    "diesel": round(self.margin_wholesale_diesel, 2),
                    "bitumen": round(self.margin_wholesale_bitumen, 2),
                    "cng": round(self.margin_wholesale_cng, 2),
                    "lpg": round(self.margin_wholesale_lpg, 2),
                },
                "retail": {
                    "total": round(self.margin_retail_total, 2),
                    "petrol": round(self.margin_retail_petrol, 2),
                    "diesel": round(self.margin_retail_diesel, 2),
                    "cng": round(self.margin_retail_cng, 2),
                    "lpg": round(self.margin_retail_lpg, 2),
                },
                "total_gross_margin": round(self.total_gross_margin, 2),
                "total_gross_profit": round(self.total_gross_profit, 2),
            },
            "ga_expenses": round(self.ga_expenses, 2),
            "ga_breakdown": {k: round(v, 2) for k, v in self.ga_breakdown.items()},
            "ebitda": round(self.ebitda, 2),
            "da_expenses": round(self.da_expenses, 2),
            "da_breakdown": {k: round(v, 2) for k, v in self.da_breakdown.items()},
            "ebit": round(self.ebit, 2),
            "other_income": round(self.other_income, 2),
            "other_income_breakdown": {k: round(v, 2) for k, v in self.other_income_breakdown.items()},
            "other_expense": round(self.other_expense, 2),
            "other_expense_breakdown": {k: round(v, 2) for k, v in self.other_expense_breakdown.items()},
            "finance_income": round(self.finance_income, 2),
            "finance_expense": round(self.finance_expense, 2),
            "finance_net": round(self.finance_net, 2),
            "ebt": round(self.ebt, 2),
            "tax_expense": round(self.tax_expense, 2),
            "net_profit": round(self.net_profit, 2),
            "rows": self.to_rows(),
        }


def _get_attr(obj: Any, key: str) -> Any:
    """Get attribute from either a model instance or a dict."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def build_income_statement(
    revenue_items: List[Any],
    cogs_items: List[Any],
    ga_expense_items: List[Any],
    period: str = "January 2025",
    currency: str = "GEL",
    finance_income: float = 0.0,
    finance_expense: float = 0.0,
    tax_expense: float = 0.0,
    labour_costs: float = 0.0,
    tb_col7310_total: float = 0.0,  # COGS enrichment: TB 7310 total for allocation
) -> IncomeStatement:
    """
    Build a structured Income Statement from database records.

    Args:
        revenue_items: List of RevenueItem model instances or dicts
        cogs_items: List of COGSItem model instances or dicts
        ga_expense_items: List of GAExpenseItem model instances or dicts
        finance_income: Finance income from TDSheet (76xx + 81xx accounts)
        finance_expense: Finance expense from TDSheet (75xx accounts)
        tax_expense: Income tax from TDSheet (77xx accounts)
        labour_costs: Labour costs from TDSheet (72xx accounts) — informational
    """
    stmt = IncomeStatement(period=period, currency=currency)
    # Pre-set below-EBITDA figures from parsed TDSheet data.
    # Note: finance_income/expense will be finalized after GA processing
    # to handle reclassification of 8110/8220 (see below).
    _raw_finance_income = finance_income
    _raw_finance_expense = finance_expense
    stmt.tax_expense = tax_expense

    # ── Revenue aggregation ────────────────────────────────────────
    rev_by_category = {}
    for r in revenue_items:
        # Skip eliminated (intercompany) items
        if _get_attr(r, "eliminated"):
            continue
        prod_name = _get_attr(r, "product") or ""
        # Skip summary/total rows (e.g. "Итог", "Total") but allow empty names
        if prod_name.lower() in ('итог', 'итого', 'total'):
            continue
        cat = _get_attr(r, "category")
        # Fallback: if category not set, classify from product name
        if not cat:
            cat = _classify_revenue_product(prod_name)
        net = float(_get_attr(r, "net") or 0)
        gross = float(_get_attr(r, "gross") or 0)
        vat = float(_get_attr(r, "vat") or 0)
        rev_by_category[cat] = rev_by_category.get(cat, 0) + net
        stmt.revenue_gross_total += gross
        stmt.revenue_vat_total += vat
        stmt.revenue_by_product.append({
            "product": prod_name,
            "product_en": _get_attr(r, "product_en") or get_english_name(prod_name),
            "gross": gross,
            "vat": vat,
            "net": net,
            "segment": _get_attr(r, "segment"),
            "category": cat,
        })

    stmt.revenue_wholesale_petrol = rev_by_category.get("Revenue Whsale Petrol", 0)
    stmt.revenue_wholesale_diesel = rev_by_category.get("Revenue Whsale Diesel", 0)
    stmt.revenue_wholesale_bitumen = rev_by_category.get("Revenue Whsale Bitumen", 0)
    stmt.revenue_wholesale_cng = rev_by_category.get("Revenue Whsale CNG", 0)
    stmt.revenue_wholesale_lpg = rev_by_category.get("Revenue Whsale LPG", 0)
    stmt.revenue_wholesale_total = (
        stmt.revenue_wholesale_petrol + stmt.revenue_wholesale_diesel + stmt.revenue_wholesale_bitumen +
        stmt.revenue_wholesale_cng + stmt.revenue_wholesale_lpg
    )

    stmt.revenue_retail_petrol = rev_by_category.get("Revenue Retial Petrol", 0)
    stmt.revenue_retail_diesel = rev_by_category.get("Revenue Retial Diesel", 0)
    stmt.revenue_retail_cng = rev_by_category.get("Revenue Retial CNG", 0)
    stmt.revenue_retail_lpg = rev_by_category.get("Revenue Retial LPG", 0)
    stmt.revenue_retail_total = (
        stmt.revenue_retail_petrol + stmt.revenue_retail_diesel +
        stmt.revenue_retail_cng + stmt.revenue_retail_lpg
    )

    stmt.other_revenue_total = sum(v for k, v in rev_by_category.items()
        if k not in ("Revenue Whsale Petrol", "Revenue Whsale Diesel", "Revenue Whsale Bitumen",
                      "Revenue Whsale CNG", "Revenue Whsale LPG",
                      "Revenue Retial Petrol", "Revenue Retial Diesel",
                      "Revenue Retial CNG", "Revenue Retial LPG"))
    stmt.total_revenue = stmt.revenue_wholesale_total + stmt.revenue_retail_total + stmt.other_revenue_total

    # ── COGS aggregation ───────────────────────────────────────────
    cogs_by_category = {}
    for c in cogs_items:
        cat = _get_attr(c, "category") or "Other COGS"
        col6 = float(_get_attr(c, "col6_amount") or 0)
        col7310 = float(_get_attr(c, "col7310_amount") or 0)
        col8230 = float(_get_attr(c, "col8230_amount") or 0)
        total = float(_get_attr(c, "total_cogs") or 0)
        cogs_by_category[cat] = cogs_by_category.get(cat, 0) + total
        stmt.cogs_col6_total += col6
        stmt.cogs_col7310_total += col7310
        stmt.cogs_col8230_total += col8230
        prod_name_c = _get_attr(c, "product") or ""
        stmt.cogs_by_product.append({
            "product": prod_name_c,
            "product_en": _get_attr(c, "product_en") or get_english_name(prod_name_c),
            "col6": col6,
            "col7310": col7310,
            "col8230": col8230,
            "total_cogs": total,
            "segment": _get_attr(c, "segment"),
            "category": cat,
        })

    # NOTE: TB 7310 (selling expenses) NOT added to COGS per IFRS.
    # Selling expenses are classified as Operating Expenses (GA), not COGS.

    stmt.cogs_wholesale_petrol = cogs_by_category.get("COGS Whsale Petrol", 0)
    stmt.cogs_wholesale_diesel = cogs_by_category.get("COGS Whsale Diesel", 0)
    stmt.cogs_wholesale_bitumen = cogs_by_category.get("COGS Whsale Bitumen", 0)
    stmt.cogs_wholesale_cng = cogs_by_category.get("COGS Whsale CNG", 0)
    stmt.cogs_wholesale_lpg = cogs_by_category.get("COGS Whsale LPG", 0)
    stmt.cogs_wholesale_total = (
        stmt.cogs_wholesale_petrol + stmt.cogs_wholesale_diesel + stmt.cogs_wholesale_bitumen +
        stmt.cogs_wholesale_cng + stmt.cogs_wholesale_lpg
    )

    stmt.cogs_retail_petrol = cogs_by_category.get("COGS Retial Petrol", 0)
    stmt.cogs_retail_diesel = cogs_by_category.get("COGS Retial Diesel", 0)
    stmt.cogs_retail_cng = cogs_by_category.get("COGS Retial CNG", 0)
    stmt.cogs_retail_lpg = cogs_by_category.get("COGS Retial LPG", 0)
    stmt.cogs_retail_total = (
        stmt.cogs_retail_petrol + stmt.cogs_retail_diesel +
        stmt.cogs_retail_cng + stmt.cogs_retail_lpg
    )

    stmt.other_cogs_total = sum(v for k, v in cogs_by_category.items()
        if k not in ("COGS Whsale Petrol", "COGS Whsale Diesel", "COGS Whsale Bitumen",
                      "COGS Whsale CNG", "COGS Whsale LPG",
                      "COGS Retial Petrol", "COGS Retial Diesel",
                      "COGS Retial CNG", "COGS Retial LPG"))
    stmt.total_cogs = stmt.cogs_wholesale_total + stmt.cogs_retail_total + stmt.other_cogs_total

    # ── Margins ────────────────────────────────────────────────────
    stmt.margin_wholesale_petrol = stmt.revenue_wholesale_petrol - stmt.cogs_wholesale_petrol
    stmt.margin_wholesale_diesel = stmt.revenue_wholesale_diesel - stmt.cogs_wholesale_diesel
    stmt.margin_wholesale_bitumen = stmt.revenue_wholesale_bitumen - stmt.cogs_wholesale_bitumen
    stmt.margin_wholesale_cng = stmt.revenue_wholesale_cng - stmt.cogs_wholesale_cng
    stmt.margin_wholesale_lpg = stmt.revenue_wholesale_lpg - stmt.cogs_wholesale_lpg
    stmt.margin_wholesale_total = stmt.revenue_wholesale_total - stmt.cogs_wholesale_total

    stmt.margin_retail_petrol = stmt.revenue_retail_petrol - stmt.cogs_retail_petrol
    stmt.margin_retail_diesel = stmt.revenue_retail_diesel - stmt.cogs_retail_diesel
    stmt.margin_retail_cng = stmt.revenue_retail_cng - stmt.cogs_retail_cng
    stmt.margin_retail_lpg = stmt.revenue_retail_lpg - stmt.cogs_retail_lpg
    stmt.margin_retail_total = stmt.revenue_retail_total - stmt.cogs_retail_total

    stmt.total_gross_margin = stmt.margin_wholesale_total + stmt.margin_retail_total

    # Total Gross Profit = Gross Margin + Other Revenue - Other COGS
    stmt.total_gross_profit = stmt.total_gross_margin + stmt.other_revenue_total - stmt.other_cogs_total

    # ── G&A and D&A Expenses (separated for proper P&L waterfall) ──
    # Special items (finance, tax, labour) are stored alongside G&A in the DB
    # but belong to separate P&L lines — skip them from G&A aggregation.
    _SPECIAL_CODES = {'FINANCE_INCOME', 'FINANCE_EXPENSE', 'TAX_EXPENSE', 'LABOUR_COSTS'}
    for ga in ga_expense_items:
        code = _get_attr(ga, "account_code") or "unknown"
        amt = float(_get_attr(ga, "amount") or 0)
        if code in _SPECIAL_CODES:
            continue  # These are handled via finance_income/expense/tax params
        # Non-operating income (NOI: prefix from TB-derived class 8 income)
        if code.startswith('NOI:'):
            real_code = code[4:]  # strip prefix
            acct_name = _get_attr(ga, "account_name") or real_code
            stmt.other_income += amt
            stmt.other_income_breakdown[acct_name] = stmt.other_income_breakdown.get(acct_name, 0) + amt
            continue
        # Strip any prefix to get raw account code for classification
        raw_code = code

        # ── Non-operating Expenses (82xx, 83xx) → below EBIT ──
        if raw_code.startswith('82') or raw_code.startswith('83'):
            acct_name = _get_attr(ga, "account_name") or GA_ACCOUNT_NAMES.get(raw_code, f"Non-operating ({raw_code})")
            stmt.other_expense += amt
            stmt.other_expense_breakdown[acct_name] = stmt.other_expense_breakdown.get(acct_name, 0) + amt
            continue

        # ── Other P&L / Tax items (92xx) → tax line ──
        if raw_code.startswith('92'):
            stmt.tax_expense += amt
            continue

        # Separate D&A from G&A based on account code (prefix match for TB-derived codes)
        is_da = code in DA_ACCOUNT_CODES or any(code.startswith(da + '.') or code.startswith(da + '/') for da in DA_ACCOUNT_CODES)
        if is_da:
            stmt.da_breakdown[code] = stmt.da_breakdown.get(code, 0) + amt
            stmt.da_expenses += amt
        else:
            stmt.ga_breakdown[code] = stmt.ga_breakdown.get(code, 0) + amt
            stmt.ga_expenses += amt

    # ── EBITDA ─────────────────────────────────────────────────────
    stmt.ebitda = stmt.total_gross_profit - stmt.ga_expenses

    # ── EBIT ───────────────────────────────────────────────────────
    stmt.ebit = stmt.ebitda - stmt.da_expenses

    # ── Finance (from TDSheet-parsed data or default to 0) ─────────
    # Reclassification: in Georgian COA, 81xx = Non-operating Income (not Finance Income).
    # Old parser stored 8110 as FINANCE_INCOME, but it should be other_income.
    # Detect: if finance_income was provided but no other_income from GA items,
    # AND we have other_expense (82xx), the finance_income is likely 8110.
    if _raw_finance_income > 0 and stmt.other_income == 0 and stmt.other_expense > 0:
        # Reclassify as Other Income (Non-operating)
        stmt.other_income = _raw_finance_income
        stmt.other_income_breakdown['Non-operating Income (8110)'] = _raw_finance_income
        stmt.finance_income = 0
    else:
        stmt.finance_income = _raw_finance_income
    # Finance expense: use raw value (already de-duplicated in _extract_special_items)
    stmt.finance_expense = _raw_finance_expense
    stmt.finance_net = stmt.finance_income - stmt.finance_expense

    # ── EBT ────────────────────────────────────────────────────────
    # EBIT + Other Income - Other Expenses + Finance net → EBT
    stmt.ebt = stmt.ebit + stmt.other_income - stmt.other_expense + stmt.finance_net

    # ── Tax (use TDSheet value if provided, else estimate 15%) ────
    if stmt.tax_expense == 0 and stmt.ebt > 0:
        stmt.tax_expense = round(stmt.ebt * 0.15, 2)

    # ── Net Profit ─────────────────────────────────────────────────
    stmt.net_profit = stmt.ebt - stmt.tax_expense

    return stmt
