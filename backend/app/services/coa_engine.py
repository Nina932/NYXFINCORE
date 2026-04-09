"""
coa_engine.py — Georgian Chart of Accounts financial computation engine.
Mirrors frontend buildFinancialsFromCOA() exactly.
Used by analytics router to produce P&L, BS, and confidence-scored figures.
"""
from app.services.file_parser import map_coa
from app.services.income_statement import IncomeStatement
from typing import Optional, Dict, List


# ── BS structural mapping ────────────────────────────────────────────────
_BS_SECTION_MAP = {
    ("asset", "current"):        "current_assets",
    ("asset", "noncurrent"):     "noncurrent_assets",
    ("liability", "current"):    "current_liabilities",
    ("liability", "noncurrent"): "noncurrent_liabilities",
    ("equity", "equity"):        "equity",
}

def _BS_BUCKET_KEY(bs_side: str, bs_sub: str) -> Optional[str]:
    """Map (bs_side, bs_sub) to the result['bs'] dict key."""
    return _BS_SECTION_MAP.get((bs_side, bs_sub))


class ConfidenceScore:
    def __init__(self):
        self._scores: dict = {}

    def score(self, key: str, value: float, level: str, source: str, note: str = "") -> float:
        self._scores[key] = {"value": value, "level": level, "source": source, "note": note}
        return value

    def get(self, key: str) -> Optional[dict]:
        return self._scores.get(key)

    def tag(self, key: str) -> str:
        c = self._scores.get(key)
        if not c:
            return ""
        icon = {"HIGH": "[OK HIGH]", "MEDIUM": "[~ MEDIUM]", "LOW": "[! LOW-ESTIMATE]"}
        return icon.get(c["level"], "")

    def all(self) -> dict:
        return dict(self._scores)


def build_financials_from_transactions(transactions: list, revenue: list, budget: dict) -> dict:
    """
    Compute P&L and Balance Sheet from transaction data using Georgian COA.

    Priority waterfall:
    - Revenue: COA account codes 6xx > REV sheet > zero
    - COGS:    COA account codes 71x > budget['COGS'] > hardcoded fallback
    - SG&A:    COA account codes 72x/73x > all expense transactions > zero

    Returns a dict with all P&L lines, BS buckets, and confidence metadata.
    """
    conf = ConfidenceScore()

    result = {
        "revenue": 0.0, "cogs": 0.0, "sga": 0.0,
        "labour": 0.0, "admin": 0.0, "da": 0.0,
        "finance_income": 0.0, "finance_expense": 0.0, "tax": 0.0,
        "gross_margin": 0.0, "ebitda": 0.0, "ebit": 0.0,
        "ebt": 0.0, "net_profit": 0.0, "finance_net": 0.0,
        "bs": {
            "current_assets": {},
            "noncurrent_assets": {},
            "current_liabilities": {},
            "noncurrent_liabilities": {},
            "equity": {},
        },
        "segments": {"Retail": 0.0, "Wholesale": 0.0, "Services": 0.0, "Other": 0.0},
        "lines": {},
        "conf": {"coa_coverage": 0, "revenue_source": None, "cogs_source": None},
    }

    coa_count = 0
    for txn in transactions:
        amt = abs(float(txn.get("amount") or 0))
        if not amt:
            continue

        dr_map = map_coa(txn.get("acct_dr", ""))
        cr_map = map_coa(txn.get("acct_cr", ""))
        classified = False

        if dr_map:
            if dr_map.get("side") == "expense":
                pl_line = dr_map.get("pl_line", "SGA")
                if pl_line == "COGS":
                    result["cogs"] += amt
                elif pl_line == "DA":
                    result["da"] += amt
                elif pl_line == "Finance":
                    result["finance_expense"] += amt
                elif pl_line == "Tax":
                    result["tax"] += amt
                else:
                    result["sga"] += amt
                    sub = dr_map.get("sub", "")
                    if sub == "Labour":
                        result["labour"] += amt
                    elif sub == "Admin":
                        result["admin"] += amt
                label = dr_map.get("pl") or "Other"
                result["lines"][label] = result["lines"].get(label, 0) + amt
                classified = True

            # BS: DR side — proper double-entry (DR=+amt for all BS accounts)
            bs_side = dr_map.get("bs_side")
            bs_sub = dr_map.get("bs_sub")
            if bs_side and bs_sub:
                bucket_key = _BS_BUCKET_KEY(bs_side, bs_sub)
                if bucket_key:
                    label = dr_map.get("bs") or "Other"
                    result["bs"][bucket_key][label] = result["bs"][bucket_key].get(label, 0) + amt
                classified = True

        if cr_map:
            if cr_map.get("side") == "income":
                result["revenue"] += amt
                seg = cr_map.get("segment", "Other")
                result["segments"][seg] = result["segments"].get(seg, 0) + amt
                label = cr_map.get("pl") or "Revenue"
                result["lines"][label] = result["lines"].get(label, 0) + amt
                classified = True
            if cr_map.get("side") == "expense":
                result["cogs"] = max(0, result["cogs"] - amt)

            # BS: CR side — proper double-entry (CR=-amt for all BS accounts)
            bs_side = cr_map.get("bs_side")
            bs_sub = cr_map.get("bs_sub")
            if bs_side and bs_sub:
                bucket_key = _BS_BUCKET_KEY(bs_side, bs_sub)
                if bucket_key:
                    label = cr_map.get("bs") or "Other"
                    result["bs"][bucket_key][label] = result["bs"][bucket_key].get(label, 0) - amt
                classified = True

        if classified:
            coa_count += 1

    total_txns = len(transactions)
    result["conf"]["coa_coverage"] = round(coa_count / total_txns * 100) if total_txns > 0 else 0
    result["conf"]["has_coa"] = coa_count > 0

    # ── Revenue waterfall ─────────────────────────────────────
    if result["revenue"] > 0:
        conf.score("revenue", result["revenue"], "HIGH", f"{coa_count} txns via COA")
        result["conf"]["revenue_source"] = "coa"
    elif revenue:
        rev_total = sum(float(r.get("net") or 0) for r in revenue)
        result["revenue"] = conf.score("revenue", rev_total, "MEDIUM", "Revenue breakdown sheet")
        result["conf"]["revenue_source"] = "rev_sheet"
        for r in revenue:
            seg = r.get("segment", "Other")
            result["segments"][seg] = result["segments"].get(seg, 0) + float(r.get("net") or 0)
    else:
        result["revenue"] = conf.score("revenue", 0, "LOW", "no revenue data")
        result["conf"]["revenue_source"] = "none"

    # ── COGS waterfall ────────────────────────────────────────
    if result["cogs"] > 0:
        conf.score("cogs", result["cogs"], "HIGH", "Account codes 71x in ledger")
        result["conf"]["cogs_source"] = "coa"
    elif budget.get("COGS"):
        result["cogs"] = conf.score("cogs", float(budget["COGS"]), "MEDIUM", "Pre-aggregated budget sheet")
        result["conf"]["cogs_source"] = "bud_sheet"
    else:
        result["cogs"] = conf.score(
            "cogs", 0.0, "LOW",
            "No COGS data found",
            "Upload file with COGS Breakdown sheet to populate"
        )
        result["conf"]["cogs_source"] = "none"

    # ── SG&A fallback ─────────────────────────────────────────
    if result["sga"] == 0:
        expense_txns = [t for t in transactions if t.get("type") == "Expense" and t.get("amount")]
        if expense_txns:
            total_exp = sum(abs(float(t["amount"])) for t in expense_txns)
            result["sga"] = max(0, total_exp - result["da"])
            conf.score("sga", result["sga"], "MEDIUM", "Expense transactions (no COA classification)")

    # ── Cascade derivations ────────────────────────────────────
    result["gross_margin"]  = result["revenue"] - result["cogs"]
    result["ebitda"]        = result["gross_margin"] - result["sga"]
    result["ebit"]          = result["ebitda"] - result["da"]
    result["finance_net"]   = result["finance_income"] - result["finance_expense"]
    result["ebt"]           = result["ebit"] + result["finance_net"]
    result["tax"]           = result["tax"] or max(0, result["ebt"] * 0.15)
    result["net_profit"]    = result["ebt"] - result["tax"]

    result["confidence"] = conf.all()
    return result


def build_pl_rows(fin: dict, budget: dict, period: str = "Current Period") -> list:
    """
    Build P&L rows in the {c, l, ac, pl, lvl, bold, sep, s} format
    matching the frontend's computedRows structure.
    """
    rev = fin["revenue"]
    cogs = fin["cogs"]
    gm = fin["gross_margin"]
    sga = fin["sga"]
    da = fin["da"]
    ebitda = fin["ebitda"]
    ebit = fin["ebit"]
    tax = fin["tax"]
    np_ = fin["net_profit"]
    bud_rev = float(budget.get("Revenue") or 0)
    bud_cogs = float(budget.get("COGS") or cogs)

    return [
        {"c": "01",     "l": "Revenue (Net)",              "ac": round(rev),   "pl": round(bud_rev),   "lvl": 0, "bold": True,  "s": 1},
        {"c": "02",     "l": "Cost of Sales (COGS)",       "ac": -round(cogs), "pl": -round(bud_cogs), "lvl": 0, "bold": True,  "s": 1},
        {"c": "GP",     "l": "Gross Profit",               "ac": round(gm),    "pl": round(rev-cogs),  "lvl": 0, "bold": True,  "sep": True, "s": 1},
        {"c": "SGA",    "l": "SG&A Expenses",              "ac": -round(sga),  "pl": 0,                "lvl": 1, "bold": False, "s": -1},
        {"c": "EBITDA", "l": "EBITDA",                     "ac": round(ebitda),"pl": 0,                "lvl": 0, "bold": True,  "sep": True, "s": 1},
        {"c": "DA",     "l": "Depreciation & Amortization","ac": -round(da),   "pl": 0,                "lvl": 1, "bold": False, "s": -1},
        {"c": "EBIT",   "l": "EBIT (Operating Profit)",    "ac": round(ebit),  "pl": 0,                "lvl": 0, "bold": True,  "s": 1},
        {"c": "TAX",    "l": "Income Tax (est. 15%)",      "ac": -round(tax),  "pl": 0,                "lvl": 1, "bold": False, "s": -1},
        {"c": "NP",     "l": "Net Profit",                 "ac": round(np_),   "pl": 0,                "lvl": 0, "bold": True,  "sep": True, "s": 1},
    ]


def build_structured_pl_rows(income_stmt: IncomeStatement, budget: Dict) -> List[Dict]:
    """
    Enrich Income Statement rows with budget comparison values (pl column).
    Takes an IncomeStatement and a budget dict, returns rows with pl populated.
    """
    rows = income_stmt.to_rows()

    # Map budget keys to row codes for pl values
    budget_map = {
        # Revenue
        "REV":       budget.get("Revenue", 0),
        "REV.W":     budget.get("Revenue Wholesale", 0),
        "REV.W.P":   budget.get("Revenue Whsale Petrol (Lari)", 0),
        "REV.W.D":   budget.get("Revenue Whsale Diesel (Lari)", 0),
        "REV.W.B":   budget.get("Revenue Whsale Bitumen (Lari)", 0),
        "REV.R":     budget.get("Revenue Retial", budget.get("Revenue Retail", 0)),
        "REV.R.P":   budget.get("Revenue Retial Petrol (Lari)", 0),
        "REV.R.D":   budget.get("Revenue Retial Diesel (Lari)", 0),
        "REV.R.CNG": budget.get("Revenue Retial CNG (Lari)", 0),
        "REV.R.LPG": budget.get("Revenue Retial LPG (Lari)", 0),
        # COGS (positive values, sign handled by s:-1)
        "COGS":      abs(float(budget.get("COGS", 0))),
        "COGS.W":    abs(float(budget.get("COGS Wholesale", 0))),
        "COGS.W.P":  abs(float(budget.get("COGS Whsale Petrol (Lari)", 0))),
        "COGS.W.D":  abs(float(budget.get("COGS Whsale Diesel (Lari)", 0))),
        "COGS.W.B":  abs(float(budget.get("COGS Whsale Bitumen (Lari)", 0))),
        "COGS.R":    abs(float(budget.get("COGS Retial", budget.get("COGS Retail", 0)))),
        "COGS.R.P":  abs(float(budget.get("COGS Retial Petrol (Lari)", 0))),
        "COGS.R.D":  abs(float(budget.get("COGS Retial Diesel (Lari)", 0))),
        "COGS.R.CNG":abs(float(budget.get("COGS Retial CNG (Lari)", 0))),
        "COGS.R.LPG":abs(float(budget.get("COGS Retial LPG (Lari)", 0))),
        # Gross Margin
        "GM":        budget.get("Gr. Margin", 0),
        "GM.W":      budget.get("Gr. Margin Wholesale", budget.get("Gr. Margin Whsale", 0)),
        "GM.W.P":    budget.get("Gr. Margin Whsale Petrol (Lari)", 0),
        "GM.W.D":    budget.get("Gr. Margin Whsale Diesel (Lari)", 0),
        "GM.W.B":    budget.get("Gr. Margin Whsale Bitumen (Lari)", 0),
        "GM.R":      budget.get("Gr. Margin Retial", budget.get("Gr. Margin Retail", 0)),
        "GM.R.P":    budget.get("Gr. Margin Retial Petrol (Lari)", 0),
        "GM.R.D":    budget.get("Gr. Margin Retial Diesel (Lari)", 0),
        "GM.R.CNG":  budget.get("Gr. Margin Retial CNG (Lari)", 0),
        "GM.R.LPG":  budget.get("Gr. Margin Retial LPG (Lari)", 0),
        # Other COGS / Other Revenue
        "COGS.O":    abs(float(budget.get("Other COGS", 0))),
        "OR":        budget.get("Other Revenue", 0),
        # Total Gross Profit
        "TGP":       budget.get("Total Gross Profit", budget.get("Gr. Margin", 0)),
        # G&A / EBITDA
        "GA":        abs(float(budget.get("G&A", budget.get("General and Administrative Expenses",
                       budget.get("SG&A", 0))))),
        "EBITDA":    budget.get("EBITDA", 0),
        # Below-EBITDA lines
        "DA":        abs(float(budget.get("D&A", budget.get("Depreciation", 0)))),
        "EBIT":      budget.get("EBIT", budget.get("Operating Profit", 0)),
        "FIN":       budget.get("Finance Net", 0),
        "FIN.I":     budget.get("Finance Income", 0),
        "FIN.E":     abs(float(budget.get("Finance Expense", 0))),
        "EBT":       budget.get("EBT", budget.get("Earnings Before Tax", 0)),
        "TAX":       abs(float(budget.get("Tax", budget.get("Income Tax", 0)))),
        "NP":        budget.get("Net Profit", budget.get("Net Income", 0)),
    }

    for row in rows:
        code = row["c"]
        if code in budget_map:
            row["pl"] = round(float(budget_map[code]), 2)

    return rows
