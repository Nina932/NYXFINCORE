"""
Test Balance Sheet structural matching — verifies the new approach
correctly classifies all BS codes from Reports.xlsx using bs_side/bs_sub
instead of hardcoded label matching.

Simulates what analytics.py /balance-sheet endpoint does.
"""
import sys
sys.path.insert(0, ".")
from app.services.file_parser import map_coa

# --- Simulate transactions with all BS codes from Reports.xlsx ----------
# Each "transaction" has a DR code and CR code with an amount.
# We simulate realistic double-entry pairs.

SIMULATED_TXNS = [
    # Cash receipts (DR Cash, CR Revenue) — tests 11xx
    {"acct_dr": "1110", "acct_cr": "6110.01.1", "amount": 500000},
    {"acct_dr": "1120", "acct_cr": "6110.01.2", "amount": 300000},
    # Bank deposit (DR Bank, CR Cash) — tests 12xx
    {"acct_dr": "1210", "acct_cr": "1110",      "amount": 400000},
    {"acct_dr": "1220", "acct_cr": "1120",      "amount": 200000},
    # Money in transit
    {"acct_dr": "1294", "acct_cr": "1210",      "amount": 50000},
    # Trade receivables (DR Recv, CR Revenue)
    {"acct_dr": "1410", "acct_cr": "6110.01.1", "amount": 150000},
    {"acct_dr": "1412", "acct_cr": "6110.01.2", "amount": 80000},
    # Advances to suppliers (DR Advance, CR Bank)
    {"acct_dr": "1480", "acct_cr": "1210",      "amount": 25000},
    # Other receivables
    {"acct_dr": "1490", "acct_cr": "1210",      "amount": 10000},
    # Inventory purchases (DR Inventory, CR Payables)
    {"acct_dr": "1605", "acct_cr": "3110",      "amount": 20000},   # Goods in transit
    {"acct_dr": "1610", "acct_cr": "3110",      "amount": 100000},  # Merchandise
    {"acct_dr": "1621", "acct_cr": "3110",      "amount": 50000},   # Raw materials
    {"acct_dr": "1622", "acct_cr": "3110",      "amount": 30000},   # Fuel
    {"acct_dr": "1623", "acct_cr": "3110",      "amount": 15000},   # Spare parts
    {"acct_dr": "1624", "acct_cr": "3110",      "amount": 8000},    # Packaging
    {"acct_dr": "1626", "acct_cr": "3110",      "amount": 5000},    # Other materials
    {"acct_dr": "1630", "acct_cr": "3110",      "amount": 40000},   # WIP
    {"acct_dr": "1640", "acct_cr": "3110",      "amount": 60000},   # Finished goods
    # Prepaid VAT
    {"acct_dr": "1790", "acct_cr": "1210",      "amount": 35000},
    # Dividends & Interest receivable
    {"acct_dr": "1810", "acct_cr": "7610",      "amount": 12000},
    {"acct_dr": "1820", "acct_cr": "7610",      "amount": 8000},
    {"acct_dr": "1821", "acct_cr": "7610",      "amount": 5000},
    # Fixed Assets (DR Fixed Asset, CR Bank)
    {"acct_dr": "2120", "acct_cr": "1210",      "amount": 200000},  # Construction
    {"acct_dr": "2130", "acct_cr": "1210",      "amount": 500000},  # Fixed assets
    {"acct_dr": "2160", "acct_cr": "1210",      "amount": 150000},  # FA acquisition
    # Accumulated Depreciation (DR Expense, CR Acc Depr) — CONTRA asset
    {"acct_dr": "7410", "acct_cr": "2230",      "amount": 80000},
    {"acct_dr": "7410.01", "acct_cr": "2231",   "amount": 20000},
    # Accumulated Amortization — CONTRA
    {"acct_dr": "7410", "acct_cr": "2610",      "amount": 10000},
    # Trade Payables (already created as CR above, also direct)
    {"acct_dr": "3110", "acct_cr": "1210",      "amount": 100000},  # Paying suppliers
    # Wages payable
    {"acct_dr": "7210", "acct_cr": "3130",      "amount": 45000},
    # Short-term debt
    {"acct_dr": "1210", "acct_cr": "3210",      "amount": 80000},   # Borrowing
    # Tax payables
    {"acct_dr": "7710", "acct_cr": "3310",      "amount": 30000},   # Income tax
    {"acct_dr": "6110.01.1", "acct_cr": "3330", "amount": 25000},   # VAT
    # 3340 = Input VAT (ASSET, not liability!)
    {"acct_dr": "3340", "acct_cr": "3110",      "amount": 18000},
    # Accrued liabilities
    {"acct_dr": "7510", "acct_cr": "3410",      "amount": 15000},   # Interest payable
    {"acct_dr": "7310.02.1", "acct_cr": "3490", "amount": 22000},   # Other accrued
    # Noncurrent: Long-term lease
    {"acct_dr": "1210", "acct_cr": "4170",      "amount": 120000},
    # Equity: Retained earnings
    {"acct_dr": "5310", "acct_cr": "1210",      "amount": 50000},   # Dividends paid (reduces equity)
]


def run_bs_test():
    """Simulate the Balance Sheet structural matching logic."""

    # -- Step 1: Compute net DR-CR balance per BS account label --------
    acct_data = {}

    for t in SIMULATED_TXNS:
        amt = abs(float(t.get("amount", 0)))
        if not amt:
            continue
        for acct_code, sign in [(t["acct_dr"], +1), (t["acct_cr"], -1)]:
            m = map_coa(acct_code or "")
            if not m or not m.get("bs_side"):
                continue
            label = m.get("bs", "Other")
            if label not in acct_data:
                acct_data[label] = {
                    "bs_side": m["bs_side"],
                    "bs_sub": m.get("bs_sub", ""),
                    "contra": m.get("contra", False),
                    "bs_ka": m.get("bs_ka", ""),
                    "balance": 0.0,
                }
            acct_data[label]["balance"] += sign * amt

    # -- Step 2: Group into BS sections -------------------------------
    SECTION_MAP = {
        ("asset", "current"):        "ca",
        ("asset", "noncurrent"):     "nca",
        ("liability", "current"):    "cl",
        ("liability", "noncurrent"): "ncl",
        ("equity", "equity"):        "eq",
    }
    sections = {s: {} for s in SECTION_MAP.values()}

    for label, info in acct_data.items():
        sec = SECTION_MAP.get((info["bs_side"], info["bs_sub"]))
        if not sec:
            continue
        bal = info["balance"]
        if info["bs_side"] in ("liability", "equity"):
            bal = -bal
        sections[sec][label] = round(bal)

    # -- Step 3: Compute totals ---------------------------------------
    ca_total  = sum(sections["ca"].values())
    nca_total = sum(sections["nca"].values())
    total_assets = ca_total + nca_total

    cl_total  = sum(sections["cl"].values())
    ncl_total = sum(sections["ncl"].values())
    total_liabilities = cl_total + ncl_total

    eq_total = sum(sections["eq"].values())

    # -- Print results ------------------------------------------------
    print("=" * 90)
    print("BALANCE SHEET — Structural COA Matching Test")
    print("=" * 90)

    sec_labels = {
        "ca":  "CURRENT ASSETS",
        "nca": "NON-CURRENT ASSETS",
        "cl":  "CURRENT LIABILITIES",
        "ncl": "NON-CURRENT LIABILITIES",
        "eq":  "EQUITY",
    }

    for sec_key in ["ca", "nca", "cl", "ncl", "eq"]:
        sec_name = sec_labels[sec_key]
        items = sections[sec_key]
        sec_total = sum(items.values())
        print(f"\n  {sec_name}: {sec_total:>15,.0f}")
        print(f"  {'-' * 55}")
        for label, val in sorted(items.items(), key=lambda x: abs(x[1]), reverse=True):
            contra_mark = " (CONTRA)" if acct_data.get(label, {}).get("contra") else ""
            print(f"    {label:<40} {val:>12,.0f}{contra_mark}")

    print(f"\n{'=' * 90}")
    print(f"  TOTAL ASSETS:       {total_assets:>15,.0f}")
    print(f"  TOTAL LIABILITIES:  {total_liabilities:>15,.0f}")
    print(f"  EQUITY:             {eq_total:>15,.0f}")
    print(f"  A - L - E =         {total_assets - total_liabilities - eq_total:>15,.0f}")
    print(f"  BALANCED:           {'V YES' if abs(total_assets - total_liabilities - eq_total) < 1 else 'X NO'}")
    print(f"{'=' * 90}")

    # -- Assertions ---------------------------------------------------
    errors = 0

    # Check that key codes route correctly
    checks = [
        # (label, expected_section, description)
        ("Cash in Hand (GEL)",      "ca",  "1110 -> current asset"),
        ("Bank Accounts (GEL)",     "ca",  "1210 -> current asset"),
        ("Trade Receivables",       "ca",  "1410 -> current asset"),
        ("Raw Materials & Fuel",    "ca",  "162x -> current asset (NOT noncurrent!)"),
        ("Prepaid VAT",             "ca",  "1790 -> current asset"),
        ("Dividends Receivable",    "ca",  "1810 -> current asset (NOT noncurrent!)"),
        ("Interest Receivable",     "ca",  "182x -> current asset (NOT noncurrent!)"),
        ("Input VAT (Asset)",       "ca",  "3340 -> current ASSET (NOT liability!)"),
        ("Fixed Assets",            "nca", "2130 -> noncurrent asset"),
        ("Acc. Depr. - Fixed Assets","nca","2230 -> noncurrent asset CONTRA"),
        ("Trade Payables",          "cl",  "3110 -> current liability"),
        ("VAT Payable",             "cl",  "3330 -> current liability"),
        ("Interest Payable",        "cl",  "3410 -> current liability"),
        ("Long-term Lease Liability","ncl", "4170 -> noncurrent liability"),
        ("Retained Earnings",       "eq",  "5310 -> equity"),
    ]

    print(f"\n{'-' * 90}")
    print("ROUTING CHECKS:")
    for label, exp_sec, desc in checks:
        found_in = None
        for sec_key, items in sections.items():
            if label in items:
                found_in = sec_key
                break
        ok = found_in == exp_sec
        status = "OK" if ok else f"FAIL (found in {found_in or 'NONE'})"
        if not ok:
            errors += 1
        print(f"  {desc:<50} {status}")

    # Check contra accounts have negative values in their section
    if "Acc. Depr. - Fixed Assets" in sections["nca"]:
        val = sections["nca"]["Acc. Depr. - Fixed Assets"]
        if val >= 0:
            print(f"  Acc. Depr. should be NEGATIVE in assets: {val}  FAIL")
            errors += 1
        else:
            print(f"  Acc. Depr. is correctly negative: {val:,.0f}  OK")

    print(f"\n{'=' * 90}")
    if errors == 0:
        print("ALL ROUTING & STRUCTURAL CHECKS PASSED!")
    else:
        print(f"FIX {errors} ERRORS!")

    return errors


if __name__ == "__main__":
    errors = run_bs_test()
    sys.exit(errors)
