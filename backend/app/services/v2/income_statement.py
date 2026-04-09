"""
FinAI v2 Income Statement — 100% Decimal precision.
=====================================================
Port of income_statement.py with all float fields → Decimal.
Uses v2/decimal_utils.py patterns throughout.

Key changes from v1:
- All 70+ financial fields are Decimal (not float)
- to_rows() serializes amounts as strings for JSON precision
- COGS col7310 enrichment uses Decimal arithmetic
- _get_children() returns Decimal amounts

Public API (drop-in for v1):
    from app.services.v2.income_statement import build_income_statement, IncomeStatement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin
from app.services.file_parser import (
    get_english_name, GA_ACCOUNT_NAMES, DA_ACCOUNT_NAMES,
    DA_ACCOUNT_CODES, _classify_revenue_product,
)

D = Decimal  # shorthand


def _get_attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


@dataclass
class IncomeStatement:
    """Full structured income statement — ALL amounts are Decimal."""
    period: str = ""
    currency: str = "GEL"

    # Revenue breakdown
    revenue_wholesale_petrol: Decimal = field(default_factory=lambda: D("0"))
    revenue_wholesale_diesel: Decimal = field(default_factory=lambda: D("0"))
    revenue_wholesale_bitumen: Decimal = field(default_factory=lambda: D("0"))
    revenue_wholesale_cng: Decimal = field(default_factory=lambda: D("0"))
    revenue_wholesale_lpg: Decimal = field(default_factory=lambda: D("0"))
    revenue_wholesale_total: Decimal = field(default_factory=lambda: D("0"))

    revenue_retail_petrol: Decimal = field(default_factory=lambda: D("0"))
    revenue_retail_diesel: Decimal = field(default_factory=lambda: D("0"))
    revenue_retail_cng: Decimal = field(default_factory=lambda: D("0"))
    revenue_retail_lpg: Decimal = field(default_factory=lambda: D("0"))
    revenue_retail_total: Decimal = field(default_factory=lambda: D("0"))

    other_revenue_total: Decimal = field(default_factory=lambda: D("0"))
    total_revenue: Decimal = field(default_factory=lambda: D("0"))

    # COGS breakdown
    cogs_wholesale_petrol: Decimal = field(default_factory=lambda: D("0"))
    cogs_wholesale_diesel: Decimal = field(default_factory=lambda: D("0"))
    cogs_wholesale_bitumen: Decimal = field(default_factory=lambda: D("0"))
    cogs_wholesale_cng: Decimal = field(default_factory=lambda: D("0"))
    cogs_wholesale_lpg: Decimal = field(default_factory=lambda: D("0"))
    cogs_wholesale_total: Decimal = field(default_factory=lambda: D("0"))

    cogs_retail_petrol: Decimal = field(default_factory=lambda: D("0"))
    cogs_retail_diesel: Decimal = field(default_factory=lambda: D("0"))
    cogs_retail_cng: Decimal = field(default_factory=lambda: D("0"))
    cogs_retail_lpg: Decimal = field(default_factory=lambda: D("0"))
    cogs_retail_total: Decimal = field(default_factory=lambda: D("0"))

    other_cogs_total: Decimal = field(default_factory=lambda: D("0"))
    total_cogs: Decimal = field(default_factory=lambda: D("0"))

    # Margins
    margin_wholesale_petrol: Decimal = field(default_factory=lambda: D("0"))
    margin_wholesale_diesel: Decimal = field(default_factory=lambda: D("0"))
    margin_wholesale_bitumen: Decimal = field(default_factory=lambda: D("0"))
    margin_wholesale_cng: Decimal = field(default_factory=lambda: D("0"))
    margin_wholesale_lpg: Decimal = field(default_factory=lambda: D("0"))
    margin_wholesale_total: Decimal = field(default_factory=lambda: D("0"))

    margin_retail_petrol: Decimal = field(default_factory=lambda: D("0"))
    margin_retail_diesel: Decimal = field(default_factory=lambda: D("0"))
    margin_retail_cng: Decimal = field(default_factory=lambda: D("0"))
    margin_retail_lpg: Decimal = field(default_factory=lambda: D("0"))
    margin_retail_total: Decimal = field(default_factory=lambda: D("0"))

    total_gross_margin: Decimal = field(default_factory=lambda: D("0"))
    total_gross_profit: Decimal = field(default_factory=lambda: D("0"))

    # Below margin
    ga_expenses: Decimal = field(default_factory=lambda: D("0"))
    ga_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    ebitda: Decimal = field(default_factory=lambda: D("0"))

    da_expenses: Decimal = field(default_factory=lambda: D("0"))
    da_breakdown: Dict[str, Decimal] = field(default_factory=dict)

    ebit: Decimal = field(default_factory=lambda: D("0"))
    other_income: Decimal = field(default_factory=lambda: D("0"))
    other_income_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    other_expense: Decimal = field(default_factory=lambda: D("0"))
    other_expense_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    finance_income: Decimal = field(default_factory=lambda: D("0"))
    finance_expense: Decimal = field(default_factory=lambda: D("0"))
    finance_net: Decimal = field(default_factory=lambda: D("0"))
    ebt: Decimal = field(default_factory=lambda: D("0"))
    tax_expense: Decimal = field(default_factory=lambda: D("0"))
    net_profit: Decimal = field(default_factory=lambda: D("0"))

    cogs_col6_total: Decimal = field(default_factory=lambda: D("0"))
    cogs_col7310_total: Decimal = field(default_factory=lambda: D("0"))
    cogs_col8230_total: Decimal = field(default_factory=lambda: D("0"))

    revenue_gross_total: Decimal = field(default_factory=lambda: D("0"))
    revenue_vat_total: Decimal = field(default_factory=lambda: D("0"))

    revenue_by_product: List[Dict] = field(default_factory=list)
    cogs_by_product: List[Dict] = field(default_factory=list)

    def _get_children(self, category: str, source: str = "revenue") -> List[Dict]:
        items = self.revenue_by_product if source == "revenue" else self.cogs_by_product
        children = []
        for p in items:
            if p.get("category") == category:
                amt = to_decimal(p.get("net", 0) if source == "revenue" else p.get("total_cogs", 0))
                children.append({
                    "product": p.get("product_en") or p.get("product", ""),
                    "product_ka": p.get("product", ""),
                    "amount": str(round_fin(amt)),
                })
        return sorted(children, key=lambda x: -abs(to_decimal(x["amount"])))

    def to_rows(self) -> List[Dict]:
        """Convert to frontend row format — amounts as strings for precision."""
        rows = []

        def add(code, label, actual, plan=D("0"), level=0, bold=False, sep=False, sign=1, children=None):
            row = {
                "c": code, "l": label,
                "ac": str(round_fin(actual)), "pl": str(round_fin(plan)),
                "lvl": level, "bold": bold, "sep": sep, "s": sign,
            }
            if children:
                row["children"] = children
            rows.append(row)

        # Revenue
        add("REV", "REVENUE", self.total_revenue, D("0"), 0, True, True, 1)
        add("REV.W", "Revenue Wholesale", self.revenue_wholesale_total, D("0"), 1, True, False, 1)
        add("REV.W.P", "Revenue Whsale Petrol (Lari)", self.revenue_wholesale_petrol, D("0"), 2, children=self._get_children("Revenue Whsale Petrol", "revenue"))
        add("REV.W.D", "Revenue Whsale Diesel (Lari)", self.revenue_wholesale_diesel, D("0"), 2, children=self._get_children("Revenue Whsale Diesel", "revenue"))
        add("REV.W.B", "Revenue Whsale Bitumen (Lari)", self.revenue_wholesale_bitumen, D("0"), 2, children=self._get_children("Revenue Whsale Bitumen", "revenue"))
        add("REV.W.CNG", "Revenue Whsale CNG (Lari)", self.revenue_wholesale_cng, D("0"), 2, children=self._get_children("Revenue Whsale CNG", "revenue"))
        add("REV.W.LPG", "Revenue Whsale LPG (Lari)", self.revenue_wholesale_lpg, D("0"), 2, children=self._get_children("Revenue Whsale LPG", "revenue"))

        add("REV.R", "Revenue Retail", self.revenue_retail_total, D("0"), 1, True, False, 1)
        add("REV.R.P", "Revenue Retial Petrol (Lari)", self.revenue_retail_petrol, D("0"), 2, children=self._get_children("Revenue Retial Petrol", "revenue"))
        add("REV.R.D", "Revenue Retial Diesel (Lari)", self.revenue_retail_diesel, D("0"), 2, children=self._get_children("Revenue Retial Diesel", "revenue"))
        add("REV.R.CNG", "Revenue Retial CNG (Lari)", self.revenue_retail_cng, D("0"), 2, children=self._get_children("Revenue Retial CNG", "revenue"))
        add("REV.R.LPG", "Revenue Retial LPG (Lari)", self.revenue_retail_lpg, D("0"), 2, children=self._get_children("Revenue Retial LPG", "revenue"))

        # COGS
        add("COGS", "COST OF GOODS SOLD", self.total_cogs, D("0"), 0, True, True, -1)
        add("COGS.W", "COGS Wholesale", self.cogs_wholesale_total, D("0"), 1, True, False, -1)
        add("COGS.W.P", "COGS Whsale Petrol (Lari)", self.cogs_wholesale_petrol, D("0"), 2, sign=-1, children=self._get_children("COGS Whsale Petrol", "cogs"))
        add("COGS.W.D", "COGS Whsale Diesel (Lari)", self.cogs_wholesale_diesel, D("0"), 2, sign=-1, children=self._get_children("COGS Whsale Diesel", "cogs"))
        add("COGS.W.B", "COGS Whsale Bitumen (Lari)", self.cogs_wholesale_bitumen, D("0"), 2, sign=-1, children=self._get_children("COGS Whsale Bitumen", "cogs"))
        add("COGS.R", "COGS Retail", self.cogs_retail_total, D("0"), 1, True, False, -1)
        add("COGS.O", "Other COGS", self.other_cogs_total, D("0"), 1, sign=-1)

        # Gross Margin
        add("GM", "GROSS MARGIN", self.total_gross_margin, D("0"), 0, True, True, 1 if self.total_gross_margin >= 0 else -1)
        add("GP", "TOTAL GROSS PROFIT", self.total_gross_profit, D("0"), 0, True, False, 1 if self.total_gross_profit >= 0 else -1)

        # G&A
        add("GA", "G&A EXPENSES", self.ga_expenses, D("0"), 0, True, True, -1)
        for code, amt in sorted(self.ga_breakdown.items()):
            name = GA_ACCOUNT_NAMES.get(code, code)
            add(f"GA.{code}", name, amt, D("0"), 1, sign=-1)

        # EBITDA
        add("EBITDA", "EBITDA", self.ebitda, D("0"), 0, True, True, 1 if self.ebitda >= 0 else -1)

        # D&A
        add("DA", "Depreciation & Amortization", self.da_expenses, D("0"), 0, True, False, -1)

        # EBIT
        add("EBIT", "EBIT", self.ebit, D("0"), 0, True, True, 1 if self.ebit >= 0 else -1)

        # Other income/expense
        if self.other_income > 0:
            add("OI", "Other Income", self.other_income, D("0"), 0, False, False, 1)
        if self.other_expense > 0:
            add("OE", "Other Expense", self.other_expense, D("0"), 0, False, False, -1)

        # Finance
        add("FIN", "Finance Net", self.finance_net, D("0"), 0, False, False, 1 if self.finance_net >= 0 else -1)

        # EBT + Tax + Net Profit
        add("EBT", "Earnings Before Tax", self.ebt, D("0"), 0, True, True, 1 if self.ebt >= 0 else -1)
        add("TAX", "Income Tax", self.tax_expense, D("0"), 0, False, False, -1)
        add("NP", "NET PROFIT", self.net_profit, D("0"), 0, True, True, 1 if self.net_profit >= 0 else -1)

        return rows


# ── Builder ───────────────────────────────────────────────────────────

def build_income_statement(
    revenue_items: List[Any],
    cogs_items: List[Any],
    ga_expense_items: List[Any],
    period: str = "January 2025",
    currency: str = "GEL",
    finance_income: Any = 0,
    finance_expense: Any = 0,
    tax_expense: Any = 0,
    labour_costs: Any = 0,
    tb_col7310_total: Any = 0,
) -> IncomeStatement:
    """Build a structured Income Statement — ALL math in Decimal."""
    stmt = IncomeStatement(period=period, currency=currency)
    _raw_fi = to_decimal(finance_income)
    _raw_fe = to_decimal(finance_expense)
    stmt.tax_expense = to_decimal(tax_expense)

    # ── Revenue aggregation ────────────────────────────────────────
    rev_by_category: Dict[str, Decimal] = {}
    for r in revenue_items:
        if _get_attr(r, "eliminated"):
            continue
        prod = _get_attr(r, "product") or ""
        if prod.lower() in ('итог', 'итого', 'total'):
            continue
        cat = _get_attr(r, "category") or _classify_revenue_product(prod)
        net = to_decimal(_get_attr(r, "net") or 0)
        gross = to_decimal(_get_attr(r, "gross") or 0)
        vat = to_decimal(_get_attr(r, "vat") or 0)
        rev_by_category[cat] = rev_by_category.get(cat, D("0")) + net
        stmt.revenue_gross_total += gross
        stmt.revenue_vat_total += vat
        stmt.revenue_by_product.append({
            "product": prod,
            "product_en": _get_attr(r, "product_en") or get_english_name(prod),
            "gross": str(round_fin(gross)),
            "vat": str(round_fin(vat)),
            "net": str(round_fin(net)),
            "segment": _get_attr(r, "segment"),
            "category": cat,
        })

    stmt.revenue_wholesale_petrol = rev_by_category.get("Revenue Whsale Petrol", D("0"))
    stmt.revenue_wholesale_diesel = rev_by_category.get("Revenue Whsale Diesel", D("0"))
    stmt.revenue_wholesale_bitumen = rev_by_category.get("Revenue Whsale Bitumen", D("0"))
    stmt.revenue_wholesale_cng = rev_by_category.get("Revenue Whsale CNG", D("0"))
    stmt.revenue_wholesale_lpg = rev_by_category.get("Revenue Whsale LPG", D("0"))
    stmt.revenue_wholesale_total = (
        stmt.revenue_wholesale_petrol + stmt.revenue_wholesale_diesel +
        stmt.revenue_wholesale_bitumen + stmt.revenue_wholesale_cng + stmt.revenue_wholesale_lpg
    )
    stmt.revenue_retail_petrol = rev_by_category.get("Revenue Retial Petrol", D("0"))
    stmt.revenue_retail_diesel = rev_by_category.get("Revenue Retial Diesel", D("0"))
    stmt.revenue_retail_cng = rev_by_category.get("Revenue Retial CNG", D("0"))
    stmt.revenue_retail_lpg = rev_by_category.get("Revenue Retial LPG", D("0"))
    stmt.revenue_retail_total = (
        stmt.revenue_retail_petrol + stmt.revenue_retail_diesel +
        stmt.revenue_retail_cng + stmt.revenue_retail_lpg
    )
    _ws_cats = {"Revenue Whsale Petrol", "Revenue Whsale Diesel", "Revenue Whsale Bitumen",
                "Revenue Whsale CNG", "Revenue Whsale LPG"}
    _rt_cats = {"Revenue Retial Petrol", "Revenue Retial Diesel", "Revenue Retial CNG", "Revenue Retial LPG"}
    stmt.other_revenue_total = sum(v for k, v in rev_by_category.items() if k not in _ws_cats | _rt_cats)
    stmt.total_revenue = stmt.revenue_wholesale_total + stmt.revenue_retail_total + stmt.other_revenue_total

    # ── COGS aggregation ───────────────────────────────────────────
    cogs_by_category: Dict[str, Decimal] = {}
    for c in cogs_items:
        cat = _get_attr(c, "category") or "Other COGS"
        col6 = to_decimal(_get_attr(c, "col6_amount") or 0)
        col7310 = to_decimal(_get_attr(c, "col7310_amount") or 0)
        col8230 = to_decimal(_get_attr(c, "col8230_amount") or 0)
        total = to_decimal(_get_attr(c, "total_cogs") or 0)
        cogs_by_category[cat] = cogs_by_category.get(cat, D("0")) + total
        stmt.cogs_col6_total += col6
        stmt.cogs_col7310_total += col7310
        stmt.cogs_col8230_total += col8230
        prod = _get_attr(c, "product") or ""
        stmt.cogs_by_product.append({
            "product": prod,
            "product_en": _get_attr(c, "product_en") or get_english_name(prod),
            "col6": str(round_fin(col6)), "col7310": str(round_fin(col7310)),
            "col8230": str(round_fin(col8230)), "total_cogs": str(round_fin(total)),
            "segment": _get_attr(c, "segment"), "category": cat,
        })

    # ── COGS col7310 enrichment (harmonized) ───────────────────────
    tb_7310 = to_decimal(tb_col7310_total)
    if tb_7310 > 0 and stmt.cogs_col7310_total == 0:
        raw_total = sum(to_decimal(p["total_cogs"]) for p in stmt.cogs_by_product)
        if raw_total > 0:
            for p in stmt.cogs_by_product:
                share = safe_divide(to_decimal(p["total_cogs"]), raw_total, precision=D("0.000001"))
                allocated = round_fin(tb_7310 * share)
                p["col7310"] = str(allocated)
                p["total_cogs"] = str(round_fin(to_decimal(p["col6"]) + allocated + to_decimal(p["col8230"])))
            stmt.cogs_col7310_total = tb_7310
            cogs_by_category = {}
            for p in stmt.cogs_by_product:
                cat = p.get("category", "Other COGS")
                cogs_by_category[cat] = cogs_by_category.get(cat, D("0")) + to_decimal(p["total_cogs"])

    stmt.cogs_wholesale_petrol = cogs_by_category.get("COGS Whsale Petrol", D("0"))
    stmt.cogs_wholesale_diesel = cogs_by_category.get("COGS Whsale Diesel", D("0"))
    stmt.cogs_wholesale_bitumen = cogs_by_category.get("COGS Whsale Bitumen", D("0"))
    stmt.cogs_wholesale_cng = cogs_by_category.get("COGS Whsale CNG", D("0"))
    stmt.cogs_wholesale_lpg = cogs_by_category.get("COGS Whsale LPG", D("0"))
    stmt.cogs_wholesale_total = sum([stmt.cogs_wholesale_petrol, stmt.cogs_wholesale_diesel,
                                      stmt.cogs_wholesale_bitumen, stmt.cogs_wholesale_cng, stmt.cogs_wholesale_lpg])
    stmt.cogs_retail_petrol = cogs_by_category.get("COGS Retial Petrol", D("0"))
    stmt.cogs_retail_diesel = cogs_by_category.get("COGS Retial Diesel", D("0"))
    stmt.cogs_retail_cng = cogs_by_category.get("COGS Retial CNG", D("0"))
    stmt.cogs_retail_lpg = cogs_by_category.get("COGS Retial LPG", D("0"))
    stmt.cogs_retail_total = sum([stmt.cogs_retail_petrol, stmt.cogs_retail_diesel,
                                   stmt.cogs_retail_cng, stmt.cogs_retail_lpg])
    _cogs_ws = {"COGS Whsale Petrol", "COGS Whsale Diesel", "COGS Whsale Bitumen", "COGS Whsale CNG", "COGS Whsale LPG"}
    _cogs_rt = {"COGS Retial Petrol", "COGS Retial Diesel", "COGS Retial CNG", "COGS Retial LPG"}
    stmt.other_cogs_total = sum(v for k, v in cogs_by_category.items() if k not in _cogs_ws | _cogs_rt)
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
    stmt.total_gross_profit = stmt.total_gross_margin + stmt.other_revenue_total - stmt.other_cogs_total

    # ── G&A and D&A ────────────────────────────────────────────────
    _SPECIAL_CODES = {'FINANCE_INCOME', 'FINANCE_EXPENSE', 'TAX_EXPENSE', 'LABOUR_COSTS'}
    for ga in ga_expense_items:
        code = _get_attr(ga, "account_code") or "unknown"
        amt = to_decimal(_get_attr(ga, "amount") or 0)
        if code in _SPECIAL_CODES:
            continue
        if code.startswith('NOI:'):
            real_code = code[4:]
            acct_name = _get_attr(ga, "account_name") or real_code
            stmt.other_income += amt
            stmt.other_income_breakdown[acct_name] = stmt.other_income_breakdown.get(acct_name, D("0")) + amt
            continue
        if code.startswith('82') or code.startswith('83'):
            acct_name = _get_attr(ga, "account_name") or GA_ACCOUNT_NAMES.get(code, f"Non-operating ({code})")
            stmt.other_expense += amt
            stmt.other_expense_breakdown[acct_name] = stmt.other_expense_breakdown.get(acct_name, D("0")) + amt
            continue
        if code.startswith('92'):
            stmt.tax_expense += amt
            continue
        is_da = code in DA_ACCOUNT_CODES or any(
            code.startswith(da + '.') or code.startswith(da + '/') for da in DA_ACCOUNT_CODES
        )
        if is_da:
            stmt.da_breakdown[code] = stmt.da_breakdown.get(code, D("0")) + amt
            stmt.da_expenses += amt
        else:
            stmt.ga_breakdown[code] = stmt.ga_breakdown.get(code, D("0")) + amt
            stmt.ga_expenses += amt

    # ── EBITDA → Net Profit waterfall ──────────────────────────────
    stmt.ebitda = stmt.total_gross_profit - stmt.ga_expenses
    stmt.ebit = stmt.ebitda - stmt.da_expenses

    # Finance reclassification
    if _raw_fi > 0 and stmt.other_income == 0 and stmt.other_expense > 0:
        stmt.other_income = _raw_fi
        stmt.other_income_breakdown['Non-operating Income (8110)'] = _raw_fi
        stmt.finance_income = D("0")
    else:
        stmt.finance_income = _raw_fi
    stmt.finance_expense = _raw_fe
    stmt.finance_net = stmt.finance_income - stmt.finance_expense

    stmt.ebt = stmt.ebit + stmt.other_income - stmt.other_expense + stmt.finance_net

    if stmt.tax_expense == 0 and stmt.ebt > 0:
        stmt.tax_expense = round_fin(stmt.ebt * D("0.15"))

    stmt.net_profit = stmt.ebt - stmt.tax_expense

    return stmt
