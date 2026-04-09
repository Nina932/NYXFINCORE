"""
Baku MR Report Template Definitions — V8 Aligned
Defines the exact NYX Core Thinker Baku V8 reporting structure with account code mappings
to the Georgian Chart of Accounts used by NYX Core Thinker.

Aligned with: MR Monthly report template _V_8_ Jan.xlsx
Entity: NYX Core Thinker LLC
Segments: Retail, Wholesales, Gas Distribution

Each template line has:
  code:     Baku hierarchical code (e.g. "10.B.01")
  line:     English line item name
  sign:     "+", "-", or "+/-"
  bold:     True = section header / subtotal row
  level:    Indentation depth (1-4)
  accounts: List of Georgian COA prefix patterns for auto-population
            "*" suffix = prefix match (e.g. "1610*" matches 1610, 1610.01, etc.)
  sum_of:   For subtotal rows — list of child codes to sum (alternative to accounts)
  side:     "dr" or "cr" — which TB side holds the balance (dr=debit, cr=credit)
"""

# ════════════════════════════════════════════════════════════════════════════
# BALANCE SHEET TEMPLATE — matches V8 BS sheet rows 13–166
# ════════════════════════════════════════════════════════════════════════════

BAKU_BS_TEMPLATE = [
    # ── Current Assets ──────────────────────────────────────────────
    {"code": "10.B",        "line": "Current assets",                                      "sign": "+", "bold": True,  "level": 1, "sum_of": ["10.B.01","10.B.02","10.B.03","10.B.04","10.B.05","10.B.06","10.B.07","10.B.08"]},
    {"code": "10.B.01",     "line": "Inventories",                                         "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.B.01.01","10.B.01.03","10.B.01.04","10.B.01.05","10.B.01.06"]},
    {"code": "10.B.01.01",  "line": "Finished goods other than crude oil",                 "sign": "+", "bold": False, "level": 3, "sum_of": ["10.B.01.01.01","10.B.01.01.02"]},
    {"code": "10.B.01.01.01","line": "Finished products",                                  "sign": "+", "bold": False, "level": 4, "accounts": ["1630"], "side": "dr"},
    {"code": "10.B.01.01.02","line": "Products held for resale",                           "sign": "+", "bold": False, "level": 4, "accounts": ["1610","1605"], "side": "dr"},
    {"code": "10.B.01.03",  "line": "Materials and components",                            "sign": "+", "bold": False, "level": 3, "accounts": ["1621","162X"], "side": "dr"},
    {"code": "10.B.01.04",  "line": "Crude oil",                                           "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "10.B.01.05",  "line": "Unfinished production",                               "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "10.B.01.06",  "line": "Other (Inventories)",                                 "sign": "+", "bold": False, "level": 3, "accounts": []},

    {"code": "10.B.02",     "line": "Trade and other receivables",                         "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.B.02.01","10.B.02.02","10.B.02.03"]},
    {"code": "10.B.02.01",  "line": "Financial and non-financial receivables",              "sign": "+", "bold": False, "level": 3, "sum_of": ["10.B.02.01.01","10.B.02.01.02","10.B.02.01.03","10.B.02.01.04"]},
    {"code": "10.B.02.01.01","line": "Trade receivables",                                  "sign": "+", "bold": False, "level": 4, "accounts": ["1410","1412"], "side": "dr"},
    {"code": "10.B.02.01.02","line": "ECL on trade receivables",                           "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "10.B.02.01.03","line": "Other receivables",                                  "sign": "+", "bold": False, "level": 4, "accounts": ["149X","1491","1495","1496"], "side": "dr"},
    {"code": "10.B.02.01.04","line": "ECL on other receivables",                           "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "10.B.02.02",  "line": "Current advances paid (prepayments)",                 "sign": "+", "bold": False, "level": 3, "accounts": ["1430","143X"], "side": "dr"},
    {"code": "10.B.02.03",  "line": "Current tax receivables",                             "sign": "+", "bold": False, "level": 3, "sum_of": ["10.B.02.03.01","10.B.02.03.02","10.B.02.03.03"]},
    {"code": "10.B.02.03.01","line": "Income tax advances",                                "sign": "+", "bold": False, "level": 4, "accounts": []},
    {"code": "10.B.02.03.02","line": "Value added tax",                                    "sign": "+", "bold": False, "level": 4, "accounts": ["1790","3340","3345"], "side": "dr"},
    {"code": "10.B.02.03.03","line": "Other tax receivables",                              "sign": "+", "bold": False, "level": 4, "accounts": []},

    {"code": "10.B.03",     "line": "Cash and cash equivalents",                           "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.B.03.01","10.B.03.02","10.B.03.03"]},
    {"code": "10.B.03.01",  "line": "Cash",                                                "sign": "+", "bold": False, "level": 3, "accounts": ["11XX","1110","12XX","1210","1220","129X","1296"], "side": "dr"},
    {"code": "10.B.03.02",  "line": "Other cash equivalents",                              "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "10.B.03.03",  "line": "ECL for cash and cash equivalents",                   "sign": "-", "bold": False, "level": 3, "accounts": []},

    {"code": "10.B.04",     "line": "Restricted cash",                                     "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.B.05",     "line": "Current deposits",                                    "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.B.06",     "line": "Current contract assets",                             "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.B.07",     "line": "Other current financial assets",                      "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.B.08",     "line": "Other current assets",                                "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.B.08.01","10.B.08.02"]},
    {"code": "10.B.08.01",  "line": "Right of return assets",                              "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "10.B.08.02",  "line": "Other (Other Current assets)",                        "sign": "+", "bold": False, "level": 3, "accounts": ["18XX","1810","1820","1821"], "side": "dr"},

    # ── Non-Current Assets ──────────────────────────────────────────
    {"code": "10.A",        "line": "Non-current assets",                                  "sign": "+", "bold": True,  "level": 1, "sum_of": ["10.A.01","10.A.02","10.A.IP","10.A.03","10.A.04","10.A.05","10.A.06","10.A.07","10.A.08","10.A.09","10.A.10"]},
    {"code": "10.A.01",     "line": "Property, plant and equipment (PPE)",                 "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.A.01.01","10.A.01.02"]},
    {"code": "10.A.01.01",  "line": "PPE: cost",                                           "sign": "+", "bold": False, "level": 3, "accounts": ["2110","2130","2160"], "side": "dr"},
    {"code": "10.A.01.02",  "line": "PPE: total impairment and depreciation amount",       "sign": "-", "bold": False, "level": 3, "sum_of": ["10.A.01.02.01","10.A.01.02.02"]},
    {"code": "10.A.01.02.01","line": "PPE: total impairment amount",                       "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "10.A.01.02.02","line": "PPE: total depreciation amount",                     "sign": "-", "bold": False, "level": 4, "accounts": ["2230"], "side": "cr"},

    {"code": "10.A.02",     "line": "Construction-in-progress (CIP), including impairment adjustments","sign": "+", "bold": True,  "level": 2, "sum_of": ["10.A.02.01","10.A.02.02"]},
    {"code": "10.A.02.01",  "line": "CIP: cost",                                           "sign": "+", "bold": False, "level": 3, "accounts": ["2120"], "side": "dr"},
    {"code": "10.A.02.02",  "line": "CIP: total impairment amount",                        "sign": "-", "bold": False, "level": 3, "accounts": []},

    {"code": "10.A.IP",     "line": "Investment properties",                                "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.A.IP.01","10.A.IP.02"]},
    {"code": "10.A.IP.01", "line": "Investment properties: cost",                           "sign": "+", "bold": False, "level": 3, "accounts": ["2132"], "side": "dr"},
    {"code": "10.A.IP.02", "line": "Investment properties: depreciation",                   "sign": "-", "bold": False, "level": 3, "accounts": ["2232"], "side": "cr"},

    {"code": "10.A.03",     "line": "Intangible assets other than goodwill",               "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.A.03.01","10.A.03.02","10.A.03.03"]},
    {"code": "10.A.03.01",  "line": "Intangible assets: cost",                             "sign": "+", "bold": False, "level": 3, "accounts": ["25XX","2510"], "side": "dr"},
    {"code": "10.A.03.02",  "line": "Intangible assets: total impairment and amortisation","sign": "-", "bold": False, "level": 3, "sum_of": ["10.A.03.02.01","10.A.03.02.02"]},
    {"code": "10.A.03.02.01","line": "Intangible assets: total impairment amount",         "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "10.A.03.02.02","line": "Intangible assets: total amortisation amount",       "sign": "-", "bold": False, "level": 4, "accounts": ["2610"], "side": "cr"},
    {"code": "10.A.03.03",  "line": "Intangible assets - investment in progress",          "sign": "+", "bold": False, "level": 3, "accounts": []},

    {"code": "10.A.04",     "line": "Investments - cost and impairment amount",            "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.A.04.01","10.A.04.02","10.A.04.03"]},
    {"code": "10.A.04.01",  "line": "Investments in Jointly controlled entities",          "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "10.A.04.02",  "line": "Investments in Associates",                           "sign": "+", "bold": False, "level": 3, "accounts": ["24XX","2430"], "side": "dr"},
    {"code": "10.A.04.03",  "line": "Investments in Subsidiaries (standalone only)",       "sign": "+", "bold": False, "level": 3, "accounts": []},

    {"code": "10.A.05",     "line": "Deferred tax assets",                                 "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.A.06",     "line": "Non-current receivables",                             "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.A.07",     "line": "Goodwill",                                            "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.A.08",     "line": "Contract assets",                                     "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.A.09",     "line": "Other non-current financial assets",                  "sign": "+", "bold": True,  "level": 2, "accounts": []},
    {"code": "10.A.10",     "line": "Other non-current assets",                            "sign": "+", "bold": True,  "level": 2, "sum_of": ["10.A.10.01","10.A.10.02","10.A.10.03"]},
    {"code": "10.A.10.01",  "line": "Right-of-use assets",                                 "sign": "+", "bold": False, "level": 3, "sum_of": ["10.A.10.01.C","10.A.10.01.01"]},
    {"code": "10.A.10.01.C","line": "ROU: Cost",                                           "sign": "+", "bold": False, "level": 4, "accounts": ["2131"], "side": "dr"},
    {"code": "10.A.10.01.01","line": "ROU: Depreciation amount",                           "sign": "-", "bold": False, "level": 4, "accounts": ["2231"], "side": "cr"},
    {"code": "10.A.10.02",  "line": "Non-current advance payments",                        "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "10.A.10.03",  "line": "Other (Other non-current assets)",                    "sign": "+", "bold": False, "level": 3, "accounts": []},

    # ── Total Assets ────────────────────────────────────────────────
    {"code": "10",          "line": "Total assets",                                        "sign": "+", "bold": True,  "level": 0, "sum_of": ["10.B","10.A"]},

    # ── Current Liabilities ─────────────────────────────────────────
    {"code": "20.B",        "line": "Current liabilities",                                 "sign": "-", "bold": True,  "level": 1, "sum_of": ["20.B.01","20.B.02","20.B.03","20.B.04","20.B.05","20.B.06","20.B.07","20.B.08","20.B.09","20.B.10","20.B.11"]},
    {"code": "20.B.01",     "line": "Short-term trade and other payables",                 "sign": "-", "bold": True,  "level": 2, "sum_of": ["20.B.01.01","20.B.01.02","20.B.01.03"]},
    {"code": "20.B.01.01",  "line": "Trade payables",                                      "sign": "-", "bold": False, "level": 3, "accounts": ["3110","3111"], "side": "cr"},
    {"code": "20.B.01.02",  "line": "Short-term debts to personnel",                       "sign": "-", "bold": False, "level": 3, "accounts": ["3130"], "side": "cr"},
    {"code": "20.B.01.03",  "line": "Other payables",                                      "sign": "-", "bold": False, "level": 3, "accounts": ["3190","3191","3199","3121"], "side": "cr"},

    {"code": "20.B.02",     "line": "Tax and other liabilities to state",                  "sign": "-", "bold": True,  "level": 2, "sum_of": ["20.B.02.01","20.B.02.02","20.B.02.03","20.B.02.04"]},
    {"code": "20.B.02.01",  "line": "Income tax payable",                                  "sign": "-", "bold": False, "level": 3, "accounts": ["3310"], "side": "cr"},
    {"code": "20.B.02.02",  "line": "VAT payable",                                         "sign": "-", "bold": False, "level": 3, "accounts": ["3330"], "side": "cr"},
    {"code": "20.B.02.03",  "line": "Payables to the Social Protection Fund",              "sign": "-", "bold": False, "level": 3, "accounts": ["337X","3370"], "side": "cr"},
    {"code": "20.B.02.04",  "line": "Other taxes and charges payable",                     "sign": "-", "bold": False, "level": 3, "accounts": ["3320","3380","3390"], "side": "cr"},

    {"code": "20.B.03",     "line": "Short-term and current portion of long term borrowings","sign": "-","bold": True,  "level": 2, "sum_of": ["20.B.03.01"]},
    {"code": "20.B.03.01",  "line": "Short-term loans received (including interest)",       "sign": "-", "bold": False, "level": 3, "sum_of": ["20.B.03.01.01","20.B.03.01.02"]},
    {"code": "20.B.03.01.01","line": "Short-term loans principal amount",                   "sign": "-", "bold": False, "level": 4, "accounts": ["32XX","3210","3211"], "side": "cr"},
    {"code": "20.B.03.01.02","line": "Short-term interest amount (loans)",                  "sign": "-", "bold": False, "level": 4, "accounts": []},

    {"code": "20.B.04",     "line": "Current lease liabilities",                           "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.B.05",     "line": "Provisions",                                          "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.B.06",     "line": "Deferred income",                                     "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.B.07",     "line": "Current contract liabilities",                        "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.B.08",     "line": "Advances received for the sale of Interest in PSA",   "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.B.09",     "line": "Other short-term financial liabilities",              "sign": "-", "bold": True,  "level": 2, "accounts": ["34XX","3410","3411"], "side": "cr"},
    {"code": "20.B.10",     "line": "Deferred acquisition consideration payable",          "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.B.11",     "line": "Other current liabilities",                           "sign": "-", "bold": True,  "level": 2, "accounts": []},

    # ── Non-Current Liabilities ─────────────────────────────────────
    {"code": "20.A",        "line": "Non-current liabilities",                             "sign": "-", "bold": True,  "level": 1, "sum_of": ["20.A.01","20.A.02","20.A.03","20.A.04","20.A.05","20.A.06","20.A.07","20.A.08","20.A.09"]},
    {"code": "20.A.01",     "line": "Non-current trade and other payables",                "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.A.02",     "line": "Long-term borrowings",                                "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.A.03",     "line": "Non-current lease liabilities",                       "sign": "-", "bold": True,  "level": 2, "accounts": ["41XX","4170","4171"], "side": "cr"},
    {"code": "20.A.04",     "line": "Deferred tax liabilities",                            "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.A.05",     "line": "Provisions",                                          "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.A.06",     "line": "Deferred income",                                     "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.A.07",     "line": "Non-current contract liabilities",                    "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.A.08",     "line": "Other long-term financial liabilities",               "sign": "-", "bold": True,  "level": 2, "accounts": []},
    {"code": "20.A.09",     "line": "Other non-current liabilities",                       "sign": "-", "bold": True,  "level": 2, "accounts": []},

    # ── Total Liabilities ───────────────────────────────────────────
    {"code": "20",          "line": "Total liabilities",                                   "sign": "-", "bold": True,  "level": 0, "sum_of": ["20.B","20.A"]},

    # ── Equity ──────────────────────────────────────────────────────
    {"code": "30.A",        "line": "Share capital",                                       "sign": "-", "bold": True,  "level": 1, "sum_of": ["30.A.01","30.A.02"]},
    {"code": "30.A.01",     "line": "Charter capital",                                     "sign": "-", "bold": False, "level": 2, "accounts": ["5150"], "side": "cr"},
    {"code": "30.A.02",     "line": "Additional paid-in capital",                          "sign": "-", "bold": False, "level": 2, "accounts": []},

    {"code": "30.B",        "line": "Retained earnings",                                   "sign": "-/+","bold": True, "level": 1, "sum_of": ["30.B.00","30.B.01","30.B.02","30.B.03","30.B.04","30.B.05"]},
    {"code": "30.B.00",     "line": "Retained earnings at end of previous year",           "sign": "-/+","bold": False,"level": 2, "accounts": []},
    {"code": "30.B.01",     "line": "Retained earnings at beginning of period",            "sign": "-/+","bold": False,"level": 2, "accounts": ["5310"], "side": "cr"},
    {"code": "30.B.02",     "line": "Current year profit/(loss)",                          "sign": "-/+","bold": False,"level": 2, "accounts": ["5330"], "side": "cr"},
    {"code": "30.B.03",     "line": "Distribution to the government",                     "sign": "-/+","bold": False,"level": 2, "accounts": []},
    {"code": "30.B.04",     "line": "Dividends declared",                                  "sign": "-/+","bold": False,"level": 2, "accounts": []},
    {"code": "30.B.05",     "line": "Other changes in retained earnings",                  "sign": "-/+","bold": False,"level": 2, "accounts": []},

    {"code": "30.C",        "line": "Cumulative translation differences",                  "sign": "-/+","bold": True, "level": 1, "accounts": []},
    {"code": "30.D",        "line": "Gain/(loss) from sale/purchase of subsidiary share",  "sign": "-/+","bold": True, "level": 1, "accounts": []},
    {"code": "30.E",        "line": "Put option on company's shares",                      "sign": "-",  "bold": True, "level": 1, "accounts": []},
    {"code": "30.F",        "line": "Other capital reserves",                              "sign": "-/+","bold": True, "level": 1, "accounts": []},

    {"code": "TE",          "line": "Total equity",                                        "sign": "-", "bold": True,  "level": 0, "sum_of": ["30.A","30.B","30.C","30.D","30.E","30.F"]},
    {"code": "30",          "line": "Equity attributable to equity holders of the Group",  "sign": "-/+","bold": True, "level": 0, "sum_of": ["TE"]},

    # ── NCI (Non-controlling interests) — V8 sub-items ─────────────
    {"code": "40",          "line": "Non-controlling interests (NCI)",                     "sign": "-", "bold": True,  "level": 0, "sum_of": ["40.A","40.B","40.C","40.D","40.E"]},
    {"code": "40.A",        "line": "NCI at the beginning of the period",                  "sign": "-", "bold": False, "level": 1, "accounts": []},
    {"code": "40.B",        "line": "Dividends declared by subsidiaries",                  "sign": "+", "bold": False, "level": 1, "accounts": []},
    {"code": "40.C",        "line": "Profit /(loss) to NCI for the year",                  "sign": "+", "bold": False, "level": 1, "accounts": []},
    {"code": "40.D",        "line": "Other comprehensive income / (loss) related to NCI",  "sign": "-/+","bold": False,"level": 1, "accounts": []},
    {"code": "40.E",        "line": "Other change to NCI",                                 "sign": "-/+","bold": False,"level": 1, "accounts": []},

    {"code": "TEL",         "line": "Total equity and liabilities",                        "sign": "-", "bold": True,  "level": 0, "sum_of": ["20","TE","40"]},
]


# ════════════════════════════════════════════════════════════════════════════
# P&L TEMPLATE — matches V8 P&L sheet rows 11–180
# Full V8 structure with depreciation sub-items and complete expense breakdowns
# ════════════════════════════════════════════════════════════════════════════

def _expense_breakdown(prefix, label_suffix="", accounts_parent=None, side="dr"):
    """Generate standard 02.X.01–02.X.16 expense breakdown lines matching V8 P&L."""
    parent_accts = accounts_parent or []
    return [
        {"code": f"{prefix}",     "line": f"{label_suffix}",                                 "sign": "-", "bold": False, "level": 2, "accounts": parent_accts, "side": side},
        {"code": f"{prefix}.01",  "line": "Wages, salaries, SSPF and other employee expenses","sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.02",  "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "-","bold": False,"level": 3, "sum_of": [f"{prefix}.02.01",f"{prefix}.02.02",f"{prefix}.02.03"]},
        {"code": f"{prefix}.02.01","line": "Depreciation (property, plant and equipment)",   "sign": "-", "bold": False, "level": 4, "accounts": []},
        {"code": f"{prefix}.02.02","line": "Depreciation (right-of-use assets)",             "sign": "-", "bold": False, "level": 4, "accounts": []},
        {"code": f"{prefix}.02.03","line": "Amortization (intangible assets)",               "sign": "-", "bold": False, "level": 4, "accounts": []},
        {"code": f"{prefix}.03",  "line": "Raw materials and consumables used",              "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.04",  "line": "Utilities expenses",                              "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.05",  "line": "Repairs and maintenance expenses",                "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.06",  "line": "Taxes other than income",                         "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.07",  "line": "Rent expenses",                                   "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.08",  "line": "Insurance expenses",                              "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.09",  "line": "Business trip expenses",                          "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.10",  "line": "Storage expense",                                 "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.11",  "line": "Security services",                               "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.12",  "line": "Communication and IT services",                   "sign": "-", "bold": False, "level": 3, "accounts": []},
        {"code": f"{prefix}.13",  "line": "Automobile and special machinery services",       "sign": "-", "bold": False, "level": 3, "accounts": []},
    ]


BAKU_PL_TEMPLATE = [
    # ── Revenue ─────────────────────────────────────────────────────
    {"code": "01",      "line": "Revenue (net of tax)",                                    "sign": "+", "bold": True,  "level": 1, "sum_of": ["01.A","01.B"]},
    {"code": "01.A",    "line": "Revenue from the sale of products (net of VAT, export taxes, road tax, excises)","sign": "+","bold": False,"level": 2, "accounts": ["6110","61XX","6XXX"], "side": "cr"},
    {"code": "01.A.01", "line": "Crude liquids",                                           "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "01.A.02", "line": "Oil products",                                            "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "01.A.03", "line": "Petrochemicals",                                          "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "01.A.04", "line": "Natural Gas",                                             "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "01.A.05", "line": "Gas products",                                            "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "01.A.06", "line": "Gases (for retail)",                                      "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "01.A.07", "line": "Other type of products",                                  "sign": "+", "bold": False, "level": 3, "accounts": []},
    {"code": "01.B",    "line": "Revenue from the sale of services",                       "sign": "+", "bold": False, "level": 2, "accounts": []},

    # ── Expenses: Cost of Sales (02.A) — V8 with depreciation sub-items ──
    {"code": "02",      "line": "Expenses",                                                "sign": "-", "bold": True,  "level": 1, "sum_of": ["02.A","02.B","02.C","02.D","02.E","02.F","02.G","02.H"]},
    {"code": "02.A",    "line": "Cost of sales",                                           "sign": "-", "bold": False, "level": 2, "accounts": ["7110"], "side": "dr"},
    {"code": "02.A.01", "line": "Wages, salaries, SSPF and other employee expenses",       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.02", "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "-","bold": False,"level": 3, "sum_of": ["02.A.02.01","02.A.02.02","02.A.02.03"]},
    {"code": "02.A.02.01","line": "Depreciation (property, plant and equipment)",          "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.A.02.02","line": "Depreciation (right-of-use assets)",                    "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.A.02.03","line": "Amortization (intangible assets)",                      "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.A.03", "line": "Raw materials and consumables used",                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.04", "line": "Utilities expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.05", "line": "Repairs and maintenance expenses",                        "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.06", "line": "Taxes other than income (incl. mining tax)",              "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.07", "line": "Rent expenses",                                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.08", "line": "Insurance expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.09", "line": "Business trip expenses",                                  "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.10", "line": "Storage expenses",                                        "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.11", "line": "Security services",                                       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.12", "line": "Communication and IT services",                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.13", "line": "Automobile and special machinery services",               "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.14", "line": "Refining services",                                       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.15", "line": "Transportation of products (cost of sales)",              "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.16", "line": "Consulting and supervision services",                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.17", "line": "Other (Cost of sales)",                                   "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.A.18", "line": "Change in work in progress balance",                      "sign": "+/-","bold": False, "level": 3, "accounts": []},
    {"code": "02.A.19", "line": "Change in finished goods balance",                        "sign": "-/+","bold": False, "level": 3, "accounts": []},

    # ── Gross Profit ────────────────────────────────────────────────
    {"code": "GP",      "line": "Gross profit",                                            "sign": "+", "bold": True,  "level": 0, "formula": "01 - 02.A"},

    # ── Administrative Expenses (02.B) — V8 full breakdown ─────────
    {"code": "02.B",    "line": "Administrative expenses",                                 "sign": "-", "bold": False, "level": 2, "accounts": ["7410"], "side": "dr"},
    {"code": "02.B.01", "line": "Wages, salaries, SSPF and other employee expenses",       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.02", "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "-","bold": False,"level": 3, "sum_of": ["02.B.02.01","02.B.02.02","02.B.02.03"]},
    {"code": "02.B.02.01","line": "Depreciation (property, plant and equipment)",          "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.B.02.02","line": "Depreciation (right-of-use assets)",                    "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.B.02.03","line": "Amortization (intangible assets)",                      "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.B.03", "line": "Raw materials and consumables used",                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.04", "line": "Utilities expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.05", "line": "Repairs and maintenance expenses",                        "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.06", "line": "Taxes other than income",                                 "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.07", "line": "Rent expenses",                                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.08", "line": "Insurance expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.09", "line": "Business trip expenses",                                  "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.10", "line": "Storage expense",                                         "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.11", "line": "Security services",                                       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.12", "line": "Communication and IT services",                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.13", "line": "Automobile and special machinery services",               "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.14", "line": "Management services",                                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.15", "line": "Consulting and supervision services",                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.B.16", "line": "Other (Administrative)",                                  "sign": "-", "bold": False, "level": 3, "accounts": []},

    # ── S&D Expenses (02.C) — V8 with reimbursable transport sub-items ──
    {"code": "02.C",    "line": "S&D expenses",                                            "sign": "-", "bold": False, "level": 2, "accounts": ["7310"], "side": "dr"},
    {"code": "02.C.01", "line": "Wages, salaries, SSPF and other employee expenses",       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.02", "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "-","bold": False,"level": 3, "sum_of": ["02.C.02.01","02.C.02.02","02.C.02.03"]},
    {"code": "02.C.02.01","line": "Depreciation (property, plant and equipment)",          "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.C.02.02","line": "Depreciation (right-of-use assets)",                    "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.C.02.03","line": "Amortization (intangible assets)",                      "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.C.03", "line": "Raw materials and consumables used",                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.04", "line": "Utilities expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.05", "line": "Repairs and maintenance expenses",                        "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.06", "line": "Taxes other than income",                                 "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.07", "line": "Rent expenses",                                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.08", "line": "Insurance expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.09", "line": "Business trip expenses",                                  "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.10", "line": "Storage expense",                                         "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.11", "line": "Security services",                                       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.12", "line": "Communication and IT services",                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.13", "line": "Automobile and special machinery services",               "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.14", "line": "Transportation of products (S&D)",                        "sign": "-", "bold": False, "level": 3, "sum_of": ["02.C.14.01","02.C.14.02","02.C.14.03"]},
    {"code": "02.C.14.01","line": "Reimbursable transportation services",                  "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.C.14.02","line": "Reimbursed transportation services",                    "sign": "+", "bold": False, "level": 4, "accounts": []},
    {"code": "02.C.14.03","line": "Un-reimbursable transportation services",               "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.C.15", "line": "Commission services",                                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.C.16", "line": "Other (S&D)",                                             "sign": "-", "bold": False, "level": 3, "accounts": []},

    # ── Social Expenses (02.D) — V8 full 16-line breakdown ─────────
    {"code": "02.D",    "line": "Social expenses",                                         "sign": "-", "bold": False, "level": 2, "accounts": ["9210"], "side": "dr"},
    {"code": "02.D.01", "line": "Wages, salaries, SSPF and other employee expenses",       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.02", "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "-","bold": False,"level": 3, "sum_of": ["02.D.02.01","02.D.02.02","02.D.02.03"]},
    {"code": "02.D.02.01","line": "Depreciation (property, plant and equipment)",          "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.D.02.02","line": "Depreciation (right-of-use assets)",                    "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.D.02.03","line": "Amortization (intangible assets)",                      "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.D.03", "line": "Raw materials and consumables used",                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.04", "line": "Utilities expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.05", "line": "Repairs and maintenance expenses",                        "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.06", "line": "Taxes other than income",                                 "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.07", "line": "Rent expenses",                                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.08", "line": "Insurance expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.09", "line": "Business trip expenses",                                  "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.10", "line": "Storage expense",                                         "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.11", "line": "Security services",                                       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.12", "line": "Communication and IT services",                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.13", "line": "Automobile and special machinery services",               "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.14", "line": "Management services",                                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.15", "line": "Consulting and supervision services",                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.D.16", "line": "Other (Social expenses)",                                 "sign": "-", "bold": False, "level": 3, "accounts": []},

    # ── Exploration Expenses (02.E) — V8 full breakdown ────────────
    {"code": "02.E",    "line": "Exploration expenses",                                    "sign": "-", "bold": False, "level": 2, "accounts": []},
    {"code": "02.E.01", "line": "Wages, salaries, SSPF and other employee expenses",       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.02", "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "-","bold": False,"level": 3, "sum_of": ["02.E.02.01","02.E.02.02","02.E.02.03"]},
    {"code": "02.E.02.01","line": "Depreciation (property, plant and equipment)",          "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.E.02.02","line": "Depreciation (right-of-use assets)",                    "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.E.02.03","line": "Amortization (intangible assets)",                      "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.E.03", "line": "Raw materials and consumables used",                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.04", "line": "Utilities expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.05", "line": "Repairs and maintenance expenses",                        "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.06", "line": "Taxes other than income",                                 "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.07", "line": "Rent expenses",                                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.08", "line": "Insurance expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.09", "line": "Business trip expenses",                                  "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.10", "line": "Storage expense",                                         "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.11", "line": "Security services",                                       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.12", "line": "Communication and IT services",                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.13", "line": "Automobile and special machinery services",               "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.14", "line": "Management services",                                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.15", "line": "Consulting and supervision services",                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.E.16", "line": "Other (Exploration expenses)",                            "sign": "-", "bold": False, "level": 3, "accounts": []},

    # ── R&D Expenses (02.F) — V8 full breakdown ───────────────────
    {"code": "02.F",    "line": "R&D expenses",                                            "sign": "-", "bold": False, "level": 2, "accounts": []},
    {"code": "02.F.01", "line": "Wages, salaries, SSPF and other employee expenses",       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.02", "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "-","bold": False,"level": 3, "sum_of": ["02.F.02.01","02.F.02.02","02.F.02.03"]},
    {"code": "02.F.02.01","line": "Depreciation (property, plant and equipment)",          "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.F.02.02","line": "Depreciation (right-of-use assets)",                    "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.F.02.03","line": "Amortization (intangible assets)",                      "sign": "-", "bold": False, "level": 4, "accounts": []},
    {"code": "02.F.03", "line": "Raw materials and consumables used",                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.04", "line": "Utilities expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.05", "line": "Repairs and maintenance expenses",                        "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.06", "line": "Taxes other than income",                                 "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.07", "line": "Rent expenses",                                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.08", "line": "Insurance expenses",                                      "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.09", "line": "Business trip expenses",                                  "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.10", "line": "Storage expense",                                         "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.11", "line": "Security services",                                       "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.12", "line": "Communication and IT services",                           "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.13", "line": "Automobile and special machinery services",               "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.14", "line": "Management services",                                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.15", "line": "Consulting and supervision services",                     "sign": "-", "bold": False, "level": 3, "accounts": []},
    {"code": "02.F.16", "line": "Other (R&D expenses)",                                    "sign": "-", "bold": False, "level": 3, "accounts": []},

    # ── ECL & Other Operating ──────────────────────────────────────
    {"code": "02.G",    "line": "Expected credit loss/(reversal)",                         "sign": "-/+","bold": False, "level": 2, "accounts": []},
    {"code": "02.H",    "line": "Other operating expenses",                                "sign": "-", "bold": False, "level": 2, "accounts": ["8220","8230"], "side": "dr"},
    {"code": "02.H.01", "line": "Impairment of property, plant and equipment & intangible assets","sign": "-/+","bold": False,"level": 3, "accounts": []},
    {"code": "02.H.02", "line": "Change in provisions",                                    "sign": "-/+","bold": False, "level": 3, "accounts": []},
    {"code": "02.H.03", "line": "Services for resale (excluding transportation of products services)","sign": "-","bold": False,"level": 3, "accounts": []},
    {"code": "02.H.04", "line": "Other (Other operating expenses)",                        "sign": "-", "bold": False, "level": 3, "accounts": []},

    # ── Other Operating Income ────────────────────────────────────
    {"code": "03",      "line": "Other operating income",                                  "sign": "+", "bold": True,  "level": 1, "accounts": ["8110","81XX"], "side": "cr"},
    {"code": "03.A",    "line": "Government grant",                                        "sign": "+", "bold": False, "level": 2, "accounts": []},
    {"code": "03.B",    "line": "Fair value gain/(loss) on financial instrument at FVPL",  "sign": "+", "bold": False, "level": 2, "accounts": []},
    {"code": "03.C",    "line": "Other (Other operating income)",                          "sign": "+", "bold": False, "level": 2, "accounts": []},

    # ── Gain/Loss on Disposals ────────────────────────────────────
    {"code": "04",      "line": "Gain/(loss) on disposals of property, plant and equipment and intangible assets","sign": "+/-","bold": True,"level": 1, "accounts": []},

    # ── Operating Profit ──────────────────────────────────────────
    {"code": "OP",      "line": "Operating profit",                                        "sign": "+/-","bold": True, "level": 0, "formula": "GP - 02.B - 02.C - 02.D - 02.E - 02.F - 02.G - 02.H + 03 + 04"},

    # ── Other Income & Finance — V8 with sub-items ────────────────
    {"code": "05",      "line": "Other income and dividends",                              "sign": "+", "bold": True,  "level": 1, "sum_of": ["05.A","05.B","05.C","05.D","05.E","05.F"]},
    {"code": "05.A",    "line": "Dividends from joint ventures (for Head office only)",    "sign": "+", "bold": False, "level": 2, "accounts": []},
    {"code": "05.B",    "line": "Dividends from associated entities (for Head office only)","sign": "+","bold": False, "level": 2, "accounts": []},
    {"code": "05.C",    "line": "Dividends from subsidiaries (for stand alone reports only)","sign": "+","bold": False,"level": 2, "accounts": []},
    {"code": "05.D",    "line": "Share of result of joint ventures",                       "sign": "+/-","bold": False, "level": 2, "accounts": []},
    {"code": "05.E",    "line": "Share of result of associates",                           "sign": "+/-","bold": False, "level": 2, "accounts": []},
    {"code": "05.F",    "line": "Other (Other income and dividends)",                      "sign": "+", "bold": False, "level": 2, "accounts": []},

    {"code": "06",      "line": "Net financing cost other than interest",                  "sign": "+/-","bold": True, "level": 1, "sum_of": ["06.A"]},
    {"code": "06.A",    "line": "Other income (expenses) from financing activities",       "sign": "+/-","bold": False, "level": 2, "accounts": []},

    {"code": "07",      "line": "Foreign exchange difference",                             "sign": "+/-","bold": True, "level": 1, "accounts": []},

    # ── Profit Before Tax & Interest ──────────────────────────────
    {"code": "08",      "line": "Profit/(loss) before taxes and interest",                 "sign": "+/-","bold": True, "level": 0, "formula": "OP + 05 + 06 + 07"},
    {"code": "EBITDA",  "line": "For reference: EBITDA",                                   "sign": "+/-","bold": False, "level": 0, "formula": "EBITDA"},

    # ── Net Interest ──────────────────────────────────────────────
    {"code": "09",      "line": "Net interest income (expense)",                           "sign": "+/-","bold": True, "level": 1, "sum_of": ["09.A","09.B"]},
    {"code": "09.A",    "line": "Interest income",                                         "sign": "+", "bold": False, "level": 2, "accounts": []},
    {"code": "09.B",    "line": "Interest expenses",                                       "sign": "-", "bold": False, "level": 2, "accounts": []},

    # ── Bottom Line ───────────────────────────────────────────────
    {"code": "10",      "line": "Profit/(loss) before income tax",                         "sign": "+/-","bold": True, "level": 0, "formula": "08 + 09"},
    {"code": "11",      "line": "Income tax",                                              "sign": "-", "bold": True,  "level": 0, "accounts": []},
    {"code": "12",      "line": "Net income/(loss)",                                       "sign": "+/-","bold": True, "level": 0, "formula": "10 - 11"},
    {"code": "13",      "line": "Comprehensive (loss)/income for the year",                "sign": "+/-","bold": True, "level": 0, "accounts": []},
    {"code": "14",      "line": "Total comprehensive (loss)/income for the year",          "sign": "+/-","bold": True, "level": 0, "formula": "12 + 13"},
]


# ════════════════════════════════════════════════════════════════════════════
# CFS TEMPLATE — V8 Cash Flow Statement (Indirect) codes
# V8 uses: CFI (operating), CF02 (investing), CF03 (financing), CF04–CF10
# ════════════════════════════════════════════════════════════════════════════

BAKU_CFS_TEMPLATE = [
    # ── Operating Activities ──────────────────────────────────────
    {"code": "CFI",          "line": "Cash flows from operating activities",                    "sign": "+/-","bold": True,  "level": 0},
    {"code": "CFI.01.01.01", "line": "Profit/(loss) before income tax",                         "sign": "+/-","bold": False, "level": 1, "pl_ref": "10"},
    {"code": "CFI.01.01.02", "line": "Interest income",                                         "sign": "+/-","bold": False, "level": 1, "pl_ref": "09.A", "negate": True},
    {"code": "CFI.01.01.03", "line": "Interest expense",                                        "sign": "+/-","bold": False, "level": 1, "pl_ref": "09.B", "negate": True},
    {"code": "CFI.01.01.04", "line": "Net financing cost other than interest",                  "sign": "+/-","bold": False, "level": 1, "pl_ref": "06", "negate": True},
    {"code": "CFI.01.01.05", "line": "Foreign exchange difference",                             "sign": "+/-","bold": False, "level": 1, "pl_ref": "07", "negate": True},
    {"code": "CFI.01.01.06", "line": "Share of result of associates and joint ventures",        "sign": "+/-","bold": False, "level": 1},
    {"code": "CFI.01.01.07", "line": "Depreciation (property, plant and equipment and right-of-use assets) and amortization","sign": "+/-","bold": False,"level": 1, "bs_change": ["22XX","2231","2610"]},
    {"code": "CFI.01.01.08", "line": "Impairment",                                              "sign": "+/-","bold": False, "level": 1},
    {"code": "CFI.01.01.09", "line": "Expected Credit Loss/(reversal)",                         "sign": "+/-","bold": False, "level": 1},
    {"code": "CFI.01.01.10", "line": "Gain/(loss) on disposals of property, plant and equipment and intangible assets","sign": "+/-","bold": False,"level": 1},
    {"code": "CFI.01.01.11", "line": "Other non-cash transactions",                             "sign": "+/-","bold": False, "level": 1},
    {"code": "CFI.01.01",    "line": "Cash flows operating activities before changes in working capital","sign": "+/-","bold": True,"level": 0, "sum_of": ["CFI.01.01.01","CFI.01.01.02","CFI.01.01.03","CFI.01.01.04","CFI.01.01.05","CFI.01.01.06","CFI.01.01.07","CFI.01.01.08","CFI.01.01.09","CFI.01.01.10","CFI.01.01.11"]},

    # Working capital changes
    {"code": "CFI.01.02",    "line": "Change in provisions",                                    "sign": "+/-","bold": False, "level": 1},
    {"code": "CFI.01.03",    "line": "Change in trade and other receivables",                   "sign": "+/-","bold": False, "level": 1, "bs_change": ["141X","143X","149X","18XX"]},
    {"code": "CFI.01.04",    "line": "Change in inventories",                                   "sign": "+/-","bold": False, "level": 1, "bs_change": ["1610","1605","1621","162X","1630"]},
    {"code": "CFI.01.05",    "line": "Change in trade and other payables and contract liabilities","sign": "+/-","bold": False,"level": 1, "bs_change": ["31XX","3130","3190"]},
    {"code": "CFI.01.06",    "line": "Change in tax payable other than income tax",             "sign": "+/-","bold": False, "level": 1, "bs_change": ["3310","3320","3330","3380","3390"]},
    {"code": "CFI.01.07",    "line": "Change in other assets and liabilities",                  "sign": "+/-","bold": False, "level": 1},

    {"code": "CFI.01",       "line": "Cash generated from operations",                          "sign": "+/-","bold": True,  "level": 0},
    {"code": "CFI.02",       "line": "Income taxes paid (-)",                                   "sign": "+/-","bold": False, "level": 1},
    {"code": "CFI.03",       "line": "Interest paid",                                           "sign": "+/-","bold": False, "level": 1},
    # CFI total is computed in engine

    # ── Investing Activities ──────────────────────────────────────
    {"code": "CF02",         "line": "Cash flows from investing activities",                    "sign": "+/-","bold": True,  "level": 0},
    {"code": "CF02.01",      "line": "Acquisition of property, plant and equipment and intangible assets","sign": "-","bold": False,"level": 1, "sum_of": ["CF02.01.01","CF02.01.02"]},
    {"code": "CF02.01.01",   "line": "Acquisition of property, plant and equipment",            "sign": "-",  "bold": False, "level": 2},
    {"code": "CF02.01.02",   "line": "Acquisition of intangible assets",                        "sign": "-",  "bold": False, "level": 2},
    {"code": "CF02.02",      "line": "Additional contribution in associates and joint ventures","sign": "-",  "bold": False, "level": 1},
    {"code": "CF02.03",      "line": "Interest received",                                       "sign": "+",  "bold": False, "level": 1},
    {"code": "CF02.04",      "line": "Dividends received",                                      "sign": "+",  "bold": False, "level": 1},
    {"code": "CF02.05",      "line": "Acquisition of subsidiary, net of cash acquired",         "sign": "-",  "bold": False, "level": 1},
    {"code": "CF02.06",      "line": "Proceeds from sale of property, plant and equipment and intangible assets","sign": "+","bold": False,"level": 1},
    {"code": "CF02.07",      "line": "Advances received for sale of Interest in PSA",           "sign": "+",  "bold": False, "level": 1},
    {"code": "CF02.08",      "line": "Purchase of financial instrument",                        "sign": "-",  "bold": False, "level": 1},
    {"code": "CF02.09",      "line": "Sale of financial instrument",                            "sign": "+",  "bold": False, "level": 1},
    {"code": "CF02.10",      "line": "Proceeds from disposal of associates, subsidiaries and JVs","sign": "+","bold": False,"level": 1},
    {"code": "CF02.11",      "line": "Loans issued",                                            "sign": "-",  "bold": False, "level": 1, "sum_of": ["CF02.11.01","CF02.11.02","CF02.11.03","CF02.11.04"]},
    {"code": "CF02.11.01",   "line": "Loans issued to JVs",                                     "sign": "-",  "bold": False, "level": 2},
    {"code": "CF02.11.02",   "line": "Loans issued to Associates",                              "sign": "-",  "bold": False, "level": 2},
    {"code": "CF02.11.03",   "line": "Loans issued to subsidiaries",                            "sign": "-",  "bold": False, "level": 2},
    {"code": "CF02.11.04",   "line": "Loans issued to third parties",                           "sign": "-",  "bold": False, "level": 2},
    {"code": "CF02.12",      "line": "Loans repayed",                                           "sign": "+",  "bold": False, "level": 1, "sum_of": ["CF02.12.01","CF02.12.02","CF02.12.03","CF02.12.04"]},
    {"code": "CF02.12.01",   "line": "Loans repayed from JVs",                                  "sign": "+",  "bold": False, "level": 2},
    {"code": "CF02.12.02",   "line": "Loans repayed from Associates",                           "sign": "+",  "bold": False, "level": 2},
    {"code": "CF02.12.03",   "line": "Loans repayed from subsidiaries",                         "sign": "+",  "bold": False, "level": 2},
    {"code": "CF02.12.04",   "line": "Loans repayed from third parties",                        "sign": "+",  "bold": False, "level": 2},
    {"code": "CF02.13",      "line": "Other investments",                                       "sign": "+/-","bold": False, "level": 1},
    # CF02 total computed in engine

    # ── Financing Activities ──────────────────────────────────────
    {"code": "CF03",         "line": "Cash flows from financing activities",                    "sign": "+/-","bold": True,  "level": 0},
    {"code": "CF03.01",      "line": "Proceeds from borrowings",                                "sign": "+",  "bold": False, "level": 1},
    {"code": "CF03.02",      "line": "Repayment of borrowings",                                 "sign": "-",  "bold": False, "level": 1},
    {"code": "CF03.03",      "line": "Contribution in subsidiary by non-controlling shareholder","sign": "+",  "bold": False, "level": 1},
    {"code": "CF03.04",      "line": "Acquisition of share from non-controlling shareholder",   "sign": "-",  "bold": False, "level": 1},
    {"code": "CF03.05",      "line": "Proceeds from sale of non-controlling interests",         "sign": "+",  "bold": False, "level": 1},
    {"code": "CF03.06",      "line": "Increase in charter capital",                             "sign": "+",  "bold": False, "level": 1},
    {"code": "CF03.07",      "line": "Distribution to the Government",                         "sign": "-",  "bold": False, "level": 1},
    {"code": "CF03.08",      "line": "Contribution from the Government",                       "sign": "+",  "bold": False, "level": 1},
    {"code": "CF03.09",      "line": "Dividends paid (-)",                                      "sign": "-",  "bold": False, "level": 1},
    {"code": "CF03.10",      "line": "Dividend paid to NCI",                                    "sign": "-",  "bold": False, "level": 1},
    {"code": "CF03.11",      "line": "Payment of Lease Liabilities",                            "sign": "-",  "bold": False, "level": 1},
    {"code": "CF03.12",      "line": "Other financings",                                        "sign": "+/-","bold": False, "level": 1},
    # CF03 total computed in engine

    # ── Reconciliation ────────────────────────────────────────────
    {"code": "CF04",         "line": "Deposits",                                                "sign": "+/-","bold": True, "level": 0},
    {"code": "CF05",         "line": "Change in restricted cash",                               "sign": "+/-","bold": True, "level": 0},
    {"code": "CF06",         "line": "Net foreign exchange translation differences",            "sign": "+/-","bold": True, "level": 0},
    {"code": "CF07",         "line": "Expected credit losses (ECL) for cash and cash equivalents","sign": "+/-","bold": True,"level": 0},
    {"code": "CF08",         "line": "Net increase in cash and cash equivalents",               "sign": "+/-","bold": True, "level": 0},
    {"code": "CF09",         "line": "Cash and cash equivalents at the beginning of the period","sign": "+/-","bold": True, "level": 0, "bs_opening": ["11XX","12XX","129X"]},
    {"code": "CF10",         "line": "Cash and cash equivalents at the end of the period",      "sign": "+/-","bold": True, "level": 0, "bs_closing": ["11XX","12XX","129X"]},
]


# ════════════════════════════════════════════════════════════════════════════
# OPEX BREAKDOWN TEMPLATE
# ════════════════════════════════════════════════════════════════════════════

BAKU_OPEX_TEMPLATE = [
    {"segment": "Downstream / Emal",     "line": "Operational expenditures",              "bold": True},
    {"segment": "Downstream / Emal",     "line": "Production cost of oil products",       "bold": False},
    {"segment": "Downstream / Emal",     "line": "Wages, salaries, SSPF",                 "bold": False},
    {"segment": "Downstream / Emal",     "line": "Depreciation and amortization",         "bold": False},
    {"segment": "Downstream / Emal",     "line": "Raw materials and consumables",         "bold": False},
    {"segment": "Downstream / Emal",     "line": "Utilities expenses",                    "bold": False},
    {"segment": "Downstream / Emal",     "line": "Repairs and maintenance",               "bold": False},
    {"segment": "Downstream / Emal",     "line": "Rent expenses",                         "bold": False},
    {"segment": "Downstream / Emal",     "line": "Insurance expenses",                    "bold": False},
    {"segment": "Downstream / Emal",     "line": "Transportation of products",            "bold": False},
    {"segment": "Downstream / Emal",     "line": "Other expenses",                        "bold": False},
    {"segment": "All / Bütün",           "line": "Personnel costs",                       "bold": True},
    {"segment": "All / Bütün",           "line": "Salaries",                              "bold": False},
    {"segment": "All / Bütün",           "line": "Bonuses",                               "bold": False},
    {"segment": "All / Bütün",           "line": "Social security contributions",         "bold": False},
    {"segment": "All / Bütün",           "line": "Training and education",                "bold": False},
    {"segment": "All / Bütün",           "line": "Financial aid",                         "bold": False},
    {"segment": "All / Bütün",           "line": "Meal expenses",                         "bold": False},
    {"segment": "All / Bütün",           "line": "Other personnel costs",                 "bold": False},
]


# ════════════════════════════════════════════════════════════════════════════
# PRODUCTS REVENUE TEMPLATES — V8 hierarchical per-product structure
# Each product has: Revenue | Volume | Price | COGs per unit | Total COGs
# Split into Local / Overseas markets
# ════════════════════════════════════════════════════════════════════════════

def _product_block(product_name, units_rev="thsd / min USD", units_vol="thsd / min ton", units_price="USD / ton"):
    """Generate a standard product block: revenue, volume, price, COGs, total COGs."""
    return [
        {"line": product_name,  "units": units_rev,   "type": "product_revenue"},
        {"line": "Sales volume", "units": units_vol,   "type": "volume"},
        {"line": "Price",        "units": units_price, "type": "price"},
        {"line": "COGs",         "units": units_price, "type": "cogs_per_unit"},
        {"line": "Total COGs",   "units": units_rev,   "type": "total_cogs"},
    ]


BAKU_PRODUCTS_WHOLESALE_TEMPLATE = [
    # Header
    {"code": "01.A", "line": "Products revenue",  "bold": True,  "level": 1, "type": "header", "units": "thsd / min USD"},
    {"code": "",     "line": "COGS",               "bold": False, "level": 1, "type": "cogs_header", "units": "thsd / min USD"},

    # Crude liquids section
    {"code": "", "line": "Crude liquids",                     "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},
    {"code": "", "line": "Local revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    # Crude oil block
    *[{**b, "bold": False, "level": 3, "code": "", "section": "crude_local_oil"} for b in _product_block("Crude oil")],
    # Gas condensate block
    *[{**b, "bold": False, "level": 3, "code": "", "section": "crude_local_condensate"} for b in _product_block("Gas condensate")],
    {"code": "", "line": "Overseas revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "crude_overseas_oil"} for b in _product_block("Crude oil")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "crude_overseas_condensate"} for b in _product_block("Gas condensate")],

    # Oil products section
    {"code": "", "line": "Oil products, net",                 "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},
    {"code": "", "line": "Local revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_diesel"} for b in _product_block("Diesel fuel")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_gasoline"} for b in _product_block("Gasoline (Petrol)")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_gasoil"} for b in _product_block("Gasoil")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_jet"} for b in _product_block("Jet fuel")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_naphtha"} for b in _product_block("Naphtha (all types)")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_reformate"} for b in _product_block("Reformate")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_heavy"} for b in _product_block("Heavy oil products (incl. bitumen, heating oil, etc.)")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_gases"} for b in _product_block("Gases")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_oils"} for b in _product_block("Oils (Lubes)")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_local_other"} for b in _product_block("Other (incl. sulphur, etc.)")],
    {"code": "", "line": "Overseas revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_overseas_diesel"} for b in _product_block("Diesel fuel")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_overseas_gasoline"} for b in _product_block("Gasoline (Petrol)")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_overseas_gasoil"} for b in _product_block("Gasoil")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "oil_overseas_other"} for b in _product_block("Other oil products")],

    # Petrochemicals (empty for SGP)
    {"code": "", "line": "Petrochemicals, net",               "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},

    # Natural Gas
    {"code": "", "line": "Natural gas",                       "bold": True, "level": 1, "type": "section", "units": "thsd / min USD",
     "category_match": ["natural gas","Natural Gas","ბუნებრივი გაზი"]},
    {"code": "", "line": "Local revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "natgas_local"} for b in _product_block("Natural gas", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")],
    {"code": "", "line": "Overseas revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "natgas_overseas"} for b in _product_block("Natural gas", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")],

    # Gas products
    {"code": "", "line": "Gas products",                      "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},

    # Other products
    {"code": "", "line": "Other type of products",            "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},
]


BAKU_PRODUCTS_RETAIL_TEMPLATE = [
    {"code": "01.A", "line": "Products revenue",  "bold": True,  "level": 1, "type": "header", "units": "thsd / min USD"},
    {"code": "",     "line": "COGS",               "bold": False, "level": 1, "type": "cogs_header", "units": "thsd / min USD"},

    # Oil products
    {"code": "", "line": "Oil products, net",                 "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},
    {"code": "", "line": "Local revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_oil_diesel"} for b in _product_block("Diesel fuel")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_oil_gasoline"} for b in _product_block("Gasoline (Petrol)")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_oil_other"} for b in _product_block("Other oil products")],
    {"code": "", "line": "Overseas revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_oil_overseas_diesel"} for b in _product_block("Diesel fuel")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_oil_overseas_gasoline"} for b in _product_block("Gasoline (Petrol)")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_oil_overseas_other"} for b in _product_block("Other oil products")],

    # Gases
    {"code": "", "line": "Gases, net",                        "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},
    {"code": "", "line": "Local revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_gas_lpg"} for b in _product_block("LPG", units_vol="mln m3", units_price="USD / thsd m3")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_gas_cng"} for b in _product_block("CNG", units_vol="mln m3", units_price="USD / thsd m3")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_gas_other"} for b in _product_block("Other", units_vol="mln m3", units_price="USD / thsd m3")],
    {"code": "", "line": "Overseas revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_gas_overseas_lpg"} for b in _product_block("LPG", units_vol="mln m3", units_price="USD / thsd m3")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_gas_overseas_cng"} for b in _product_block("CNG", units_vol="mln m3", units_price="USD / thsd m3")],
    *[{**b, "bold": False, "level": 3, "code": "", "section": "retail_gas_overseas_other"} for b in _product_block("Other", units_vol="mln m3", units_price="USD / thsd m3")],

    # Other products (minimarkets)
    {"code": "", "line": "Other products, net",               "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},
    {"code": "", "line": "Minimarkets",                       "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD",
     "category_match": ["minimarket","Minimarket","shop","mini"]},
    {"code": "", "line": "Total COGs",                        "bold": False,"level": 2, "type": "total_cogs", "units": "thsd / min USD"},
    {"code": "", "line": "Private label products",            "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD"},
    {"code": "", "line": "Total COGs",                        "bold": False,"level": 2, "type": "total_cogs", "units": "thsd / min USD"},
    {"code": "", "line": "Other",                             "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD"},
    {"code": "", "line": "Total COGs",                        "bold": False,"level": 2, "type": "total_cogs", "units": "thsd / min USD"},
]


# ════════════════════════════════════════════════════════════════════════════
# PRODUCTS REVENUE — GAS DISTRIBUTION (NEW for V8)
# ════════════════════════════════════════════════════════════════════════════

BAKU_PRODUCTS_GAS_DISTR_TEMPLATE = [
    {"code": "01.A", "line": "Products revenue",  "bold": True,  "level": 1, "type": "header", "units": "thsd / min USD"},
    {"code": "",     "line": "COGS",               "bold": False, "level": 1, "type": "cogs_header", "units": "thsd / min USD"},

    # Natural gas — main product for gas distribution
    {"code": "", "line": "Natural gas",                       "bold": True, "level": 1, "type": "section", "units": "thsd / min USD"},
    {"code": "", "line": "Local revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},

    # Residential customers
    {"code": "", "line": "Residential customers",             "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD",
     "category_match": ["residential","Residential","საყოფაცხოვრებო"]},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "gasdistr_residential"} for b in _product_block("Residential", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")][1:],  # skip first (revenue already above)

    # Non-residential customers
    {"code": "", "line": "Non-residential customers",         "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD",
     "category_match": ["non-residential","Non-residential","კომერციული"]},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "gasdistr_nonresidential"} for b in _product_block("Non-residential", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")][1:],

    # Other
    {"code": "", "line": "Other",                             "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "gasdistr_other"} for b in _product_block("Other", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")][1:],

    {"code": "", "line": "Overseas revenue (for Entity location)","bold": False,"level": 2, "type": "subsection", "units": "thsd / min USD"},
    # Overseas residential
    {"code": "", "line": "Residential customers",             "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "gasdistr_overseas_residential"} for b in _product_block("Residential", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")][1:],
    # Overseas non-residential
    {"code": "", "line": "Non-residential customers",         "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "gasdistr_overseas_nonresidential"} for b in _product_block("Non-residential", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")][1:],
    # Overseas other
    {"code": "", "line": "Other",                             "bold": False,"level": 2, "type": "product_revenue", "units": "thsd / min USD"},
    *[{**b, "bold": False, "level": 3, "code": "", "section": "gasdistr_overseas_other"} for b in _product_block("Other", units_vol="mln m3", units_price="USD / thsd m3 (min m3)")][1:],
]


# ════════════════════════════════════════════════════════════════════════════
# SHEET METADATA — 13 Baku sheets + MAPPING reference
# Updated for V8 (Gas Distribution added)
# ════════════════════════════════════════════════════════════════════════════

MR_SHEETS = [
    {"name": "BS",                                 "title": "Statement of Financial Position", "color": "38BDF8", "has_data": True},
    {"name": "P&L",                                "title": "Profit and Loss Statement",       "color": "22C55E", "has_data": True},
    {"name": "CFS (ind)",                          "title": "Cash Flow Statement (Indirect)",  "color": "A855F7", "has_data": True},
    {"name": "Service revenue&COGS",               "title": "Service Revenue & COGS",          "color": "F59E0B", "has_data": False},
    {"name": "Products revenue&COGS_WSales_Tr",    "title": "Products Revenue & COGS (Wholesale/Trading)", "color": "EF4444", "has_data": True},
    {"name": "Products revenue&COGS_Retail",       "title": "Products Revenue & COGS (Retail)","color": "EC4899", "has_data": True},
    {"name": "Products revenue&COGS_Gas Distr",    "title": "Products Revenue & COGS (Gas Distribution)","color": "10B981", "has_data": True},
    {"name": "CAPEX&INVESTMENT",                   "title": "CAPEX & Investments",             "color": "6366F1", "has_data": False},
    {"name": "CAPEX_cash basis",                   "title": "CAPEX (Cash Basis)",              "color": "8B5CF6", "has_data": False},
    {"name": "OPEX_breakdown",                     "title": "OPEX Breakdown",                  "color": "F97316", "has_data": True},
    {"name": "Borrowings",                         "title": "Borrowings",                      "color": "14B8A6", "has_data": True},
    {"name": "Receivables",                        "title": "Receivables",                     "color": "06B6D4", "has_data": True},
    {"name": "Payables",                           "title": "Payables",                        "color": "D946EF", "has_data": True},
    {"name": "Prepayments",                        "title": "Prepayments",                     "color": "84CC16", "has_data": True},
]


# ════════════════════════════════════════════════════════════════════════════
# COLUMN HEADERS per sheet type — matching V8 exactly
# ════════════════════════════════════════════════════════════════════════════

BS_COLUMNS = [
    "Code / Kod",
    "Balance Sheet Line",
    "+/-",
    "Opening balance as of beginning of reporting year",
    "Opening balance as of beginning of reporting month",
    "Current period actual",
    "Current period plan",
    "Deviation (absolute)",
    "Deviation (%)",
]

PL_COLUMNS = [
    "Code / Kod",
    "P&L Statement Line",
    "+/-",
    "Same period of the previous year actual",
    "Current period actual",
    "Current period plan",
    "Deviation (absolute)",
    "Deviation (%)",
]

CFS_COLUMNS = [
    "Code / Kod",
    "Cash Flow line",
    "+/-",
    "Same period of the previous year actual",
    "Current period actual",
    "Current period plan",
    "Deviation (absolute)",
    "Deviation (%)",
]

PRODUCTS_COLUMNS = [
    "Code / Kod",
    "Line item",
    "Units of measurement",
    "+/-",
    "Same period of the previous year actual",
    "Current period actual",
    "Current period plan",
    "Deviation (absolute)",
    "Deviation (%)",
]


# ════════════════════════════════════════════════════════════════════════════
# BSI CATEGORY → P&L SUB-ITEM MAPPING
# Maps baku_bs_mapping values from BalanceSheetItem → P&L sub-item suffix.
# Used by MREngine to distribute expenses from BSI data to V8 P&L sub-items.
# ════════════════════════════════════════════════════════════════════════════

# Map baku_bs_mapping (column 5 of user's Excel) → sub-item suffix (01-17)
BAKU_CATEGORY_TO_PL_SUFFIX = {
    # Wages, salaries, SSPF → .01
    "Payroll":           "01",
    "Staff Training":    "01",

    # Depreciation & amortization → .02 (further split by name keywords in engine)
    "Depreciation":      "02",

    # Raw materials → .03
    "Stationery and Hosehold Materials": "03",
    "Office Equipment / Work clothes":  "03",

    # Utilities → .04
    "Utilities Expense": "04",

    # Repairs & maintenance → .05
    "Maintenance/Renovation": "05",

    # Taxes other than income → .06
    "Taxes Other":       "06",

    # Rent → .07
    "Rent":              "07",
    "Rent ":             "07",   # trailing space variant in data

    # Insurance → .08
    "Insurance":         "08",

    # Business trip → .09
    "Business Trip":     "09",
    "Representative":    "09",

    # Storage → .10  (not commonly tagged)
    # Security → .11
    "Security Expense":  "11",

    # Communication & IT → .12
    "IT and communication": "12",

    # Automobile → .13
    "Auto Park Cost":    "13",

    # Transportation → .15
    "Fuel Transportation": "15",

    # Consulting / supervision → .16
    "Consulting":        "16",
    "Legal":             "16",

    # Marketing → allocated to "Other" under S&D
    "Marketing":         "17",

    # Bank commissions → "Other"
    "Bank Commisions":   "17",
    "Bank Commissions":  "17",

    # Quality → "Other"
    "Quality":           "17",
    "Quality ":          "17",

    # Other / catch-all
    "Other G&A":         "17",
}

# Map MAPING ST (from Mapping sheet column E) → sub-item suffix
# These are the IFRS classifications assigned in the user's Mapping sheet
# None = "use keyword matching on account name for further sub-classification"
# "SKIP" = "skip entirely (revenue, COGS handled elsewhere)"
MAPING_ST_TO_PL_SUFFIX = {
    "Wages, benefits and payroll taxes": "01",
    "Depreciation and amortization":     "02",
    "Taxes, other than income tax":      "06",
    "Selling and Distribution costs":    None,  # Use keyword matching for sub-classification
    "Selling and Distribution Costs":    None,  # Case variant
    "Other Cost of sale":                None,  # Use keyword matching
    "Gas purchases":                     None,  # Use keyword matching
    "Other operating expenses":          None,  # Use keyword matching
    "Revenue from sale of products":     "SKIP",  # Revenue, skip
    "COGS":                              "SKIP",  # Already in 02.A
}

# Map MAPING ST → non-operating P&L codes (for items outside 02.A-F)
MAPING_ST_NONOP = {
    "Net FX gain/(loss)":                                 "07",
    "Interest income":                                    "09.A",
    "Interest expense":                                   "09.B",
    "Loss on disposal of property, plant and equipment":  "04",
    "Other Non-operating Income":                         "03.C",
}

# Fallback: map ifrs_line_item (MAPPING GRP) → sub-item suffix
IFRS_LINE_TO_PL_SUFFIX = {
    "Wages, benefits and payroll taxes": "01",
    "Depreciation and amortization":    "02",
    "Taxes, other than income tax":     "06",
}

# ════════════════════════════════════════════════════════════════════════════
# KEYWORD-BASED SUB-CLASSIFICATION for "Other operating expenses"
# When MAPING ST = "Other operating expenses", use Georgian/Russian keywords
# in the account name to assign a specific P&L sub-item suffix.
# Keywords are matched case-insensitively against the account description.
# ════════════════════════════════════════════════════════════════════════════

# Each entry: suffix → list of keyword patterns (Georgian and/or Russian)
EXPENSE_NAME_KEYWORDS = {
    # .03 Raw materials and consumables
    "03": [
        "მასალ", "материал",                  # materials
        "საკანცელარიო", "канцеляр",           # stationery
        "სამეურნეო", "хозяйствен",            # household supplies
        "ინვენტარ", "инвентар",               # inventory write-off
        "სპეცაღჭურვილობა", "спецэкипировк",   # special equipment
    ],
    # .04 Utilities
    "04": [
        "კომუნალ", "коммунал",                # utilities
    ],
    # .05 Repairs and maintenance
    "05": [
        "რემონტ", "ремонт",                   # repair
        "მომსახურება აგს", "обслуживание азс", # gas station maintenance
        "მომსახურება ბაზებ", "обслуживание на базах",  # base maintenance
        "ძირითადი საშუალების მომსახურება", "обслуживание основных средств",  # PPE maintenance
        "გგს მომსახურება", "обслуживание гзс",  # gas distribution station
        "ორგ. ტექნიკის მომსახურება", "обслуживание орг.техники",  # office equipment
        "სამრეცხაო", "мойк",                  # car wash
        "ORPAK",                               # ORPAK services
    ],
    # .06 Taxes other than income
    "06": [
        "ქონების გადასახად", "налог на имущество",    # property tax
        "საგადასახადო", "налоговому назначению",       # tax-related
        "არარეზიდენტის საშემოსავლო", "подоходный налог",  # non-resident income tax
    ],
    # .07 Rent
    "07": [
        "იჯარა", "аренда",                    # rent/lease
        "ნავთობბაზის იჯარა", "аренда нефтебаз",  # fuel depot rent
    ],
    # .08 Insurance
    "08": [
        "დაზღვევა", "страхован",               # insurance
    ],
    # .09 Business trip / representation
    "09": [
        "მივლინება", "командировк",             # business trip
        "წარმომადგენლობითი", "представительск",  # representation
    ],
    # .10 Storage
    "10": [
        "შენახვ", "хранени",                   # storage
    ],
    # .11 Security
    "11": [
        "დაცვა", "охран",                      # security
        "ინკასაცია", "инкассац",               # cash collection (security)
        "ტექნიკური უსაფრთხოება", "тех.безопасность",  # technical safety
    ],
    # .12 Communication & IT
    "12": [
        "ინტერნეტ", "интернет",               # internet
        "კომუნიკაცი", "коммуникац",            # communication
        "პროგრამულ", "програм",                # software
        "თარჯიმან", "бюро переводов",          # translation bureau
    ],
    # .13 Automobile
    "13": [
        "ავტო-ტექ", "авто-техн",              # auto-technical
        "მანქანის საექსპლუატაციო", "эксплуатац",  # vehicle operation
        "კომერც მანქანის", "коммерческой маш",  # commercial vehicle
    ],
    # .15 Transportation
    "15": [
        "სატრანსპორტო", "транспортн",         # transportation
        "საწვავის ავტოგადაზიდვა", "перевозка горючего",  # fuel transportation
        "რკინიგზის", "железнодорожн",          # railway
        "საბაჟო", "таможен",                   # customs
    ],
    # .14 Management / advertising / marketing (for S&D section)
    "14": [
        "სარეკლამო", "реклам",                 # advertising
        "მარკეტინგ", "маркетинг",              # marketing
    ],
    # .16 Consulting / legal / audit
    "16": [
        "საკონსულტაციო", "консультац",         # consulting
        "აუდიტორულ", "аудитор",               # audit
        "იურიდიულ", "юридическ",              # legal
        "ნოტარიუს", "нотариус",               # notary
        "სარეგისტრაციო", "регистрац",          # registration
        "ექსპერტიზ", "экспертиз",             # expertise
        "შემოწმება და დაკალიბრება", "поверка",  # calibration/inspection
        "ინსპექტირება", "инспектирован",       # inspection
        "საფოსტო", "почтов",                   # postal
        "კურიერ", "курьер",                    # courier
    ],
}

# Special keyword overrides for items that MAPING ST already classified
# but keyword further refines them
EXPENSE_NAME_KEYWORDS_DEPRECIATION = {
    "02.01": ["ოს", "ОС", "основн", "საშუალების ამორტიზაცია", "амортизация ос"],   # PPE
    "02.02": ["rou", "right-of-use", "მოხმარების უფლება"],                          # ROU assets
    "02.03": ["არამატერიალ", "НМА", "нематериал", "intangible", "амортизация нма"], # Intangible
}

# Map account code prefix → MR parent code
# Determines which P&L section a mapping sheet item belongs to
ACCOUNT_PREFIX_TO_EXPENSE_CODE = {
    # Expenses (class 7)
    "7110": "02.A",   # Cost of Sales
    "7310": "02.C",   # Selling & Distribution
    "7410": "02.B",   # Administrative
    # Income & Other (class 8)
    "8110": "03",     # Other operating income
    "8120": "03",     # Other operating income (variant)
    "8220": "02.H",   # Other operating expenses
    "8230": "02.H",   # Other operating expenses (variant)
    # Other P&L (class 9)
    "9210": "02.D",   # Social expenses
    # 02.E Exploration and 02.F R&D would need their own prefixes if used
}


# ════════════════════════════════════════════════════════════════════════════
# INCOME SUB-CLASSIFICATION KEYWORDS (for 03 — Other operating income)
# When an account maps to parent "03", use these keywords to determine
# the specific sub-item: 03.A (Government grant), 03.B (Fair value), 03.C (Other)
# ════════════════════════════════════════════════════════════════════════════

INCOME_NAME_KEYWORDS = {
    # 03.A Government grant / subsidy
    "A": [
        "სახელმწიფო", "государств",          # government
        "გრანტ", "грант",                     # grant
        "სუბსიდი", "субсиди",                # subsidy
        "დოტაცი", "дотаци",                  # subsidy/dotation
    ],
    # 03.B Fair value gain/loss on financial instruments
    "B": [
        "რეალური ღირებულება", "справедливая стоимость",  # fair value
        "ფინანსური ინსტრუმენტ", "финансовый инструмент",  # financial instrument
        "FVPL", "FVTPL",
    ],
    # 03.C is the default "Other operating income"
}


# ════════════════════════════════════════════════════════════════════════════
# OTHER OPERATING EXPENSES SUB-CLASSIFICATION (for 02.H)
# When an account maps to parent "02.H", use these keywords to classify into:
# 02.H.01 (Impairment), 02.H.02 (Provisions), 02.H.03 (Services for resale),
# 02.H.04 (Other)
# ════════════════════════════════════════════════════════════════════════════

OTHER_OPEX_NAME_KEYWORDS = {
    # .01 Impairment of PPE & intangible assets
    "01": [
        "გაუფასურება", "обесценивание",       # impairment
        "ჩამოწერა", "списание",               # write-off
    ],
    # .02 Change in provisions
    "02": [
        "პროვიზი", "провизи",                 # provision
        "რეზერვ", "резерв",                   # reserve/provision
    ],
    # .03 Services for resale (excluding transportation)
    "03": [
        "გადაყიდვ", "перепродаж",             # resale
        "გაყიდვისთვის", "для продажи",        # for sale
    ],
    # .04 is default "Other (Other operating expenses)"
}


# ════════════════════════════════════════════════════════════════════════════
# COGS (02.A) SUB-CLASSIFICATION KEYWORDS
# When an account maps to parent "02.A" (Cost of Sales), use account name
# keywords to determine sub-items like Wages, Depreciation, Raw materials, etc.
# Falls back to "17" (Other) if no keyword matches.
# ════════════════════════════════════════════════════════════════════════════

COGS_NAME_KEYWORDS = {
    # .01 Wages / personnel costs
    "01": [
        "ხელფას", "зарплат",                  # salary
        "შრომის ანაზღაურება", "оплата труда",  # labor compensation
        "თანამშრომელ", "сотрудник",            # employee
        "პერსონალ", "персонал",               # personnel
        "სახელფასო", "фонд оплаты",           # payroll
        "SSPF", "სსპფ",                       # social security
    ],
    # .02 Depreciation & amortization (handled via EXPENSE_NAME_KEYWORDS_DEPRECIATION)
    "02": [
        "ცვეთა", "амортизаци",               # depreciation/amortization
        "ამორტიზაცია", "износ",                # amortization/depreciation
    ],
    # .03 Raw materials and consumables
    "03": [
        "ნედლეულ", "сырь",                    # raw materials
        "მასალ", "материал",                   # materials
        "საწვავ", "топлив",                    # fuel
        "ნავთობპროდუქტ", "нефтепродукт",      # petroleum products
        "ბუნებრივი გაზ", "природный газ",      # natural gas
    ],
    # .04 Utilities
    "04": [
        "კომუნალ", "коммунал",                # utilities
        "ელექტროენერგ", "электроэнерг",       # electricity
    ],
    # .05 Repairs and maintenance
    "05": [
        "რემონტ", "ремонт",                   # repairs
    ],
    # .06 Taxes other than income
    "06": [
        "გადასახად", "налог",                  # tax
        "აქციზ", "акциз",                     # excise
    ],
    # .15 Transportation of products
    "15": [
        "ტრანსპორტ", "транспорт",             # transport
        "გადაზიდვ", "перевозк",               # freight/carriage
    ],
    # .17 is default "Other (Cost of sales)"
}


# Legacy aliases (kept for backward compatibility with existing code)
BAKU_NONOP_TO_PL_CODE = MAPING_ST_NONOP
DEPRECIATION_NAME_KEYWORDS = EXPENSE_NAME_KEYWORDS_DEPRECIATION

OPEX_COLUMNS = [
    "Segment / Seqment",
    "Line item",
    "Units of measurement",
    "+/-",
    "Same period of the previous year actual",
    "Current period actual",
    "Current period plan",
    "Deviation (absolute)",
    "Deviation (%)",
]

BORROWINGS_COLUMNS = [
    "Code / Kod",
    "Lender name",
    "Original currency",
    "Start date",
    "Maturity Date",
    "Interest rate (annual)",
    "Outstanding balance (original currency)",
    "Outstanding balance (thsd USD)",
    "Outstanding principal (thsd USD)",
    "Outstanding interest (thsd USD)",
]

RECEIVABLES_COLUMNS = [
    "#",
    "Customer",
    "Type of customer",
    "Balance (year start)",
    "Balance (period start)",
    "Supplied during period",
    "Payments received",
    "Balance (period end)",
    "Overdue 30+ days",
]

PAYABLES_COLUMNS = [
    "#",
    "Supplier",
    "Type of supplier",
    "Annual purchase plan",
    "Balance (year start)",
    "Balance (period start)",
    "Purchases during period",
    "Payments during period",
    "Balance (period end)",
]

PREPAYMENTS_COLUMNS = [
    "#",
    "Supplier",
    "Type of supplier",
    "Balance (year start)",
    "Balance (period start)",
    "Prepayments made",
    "Acceptance of products",
    "Balance (period end)",
    "Change from period start",
]
