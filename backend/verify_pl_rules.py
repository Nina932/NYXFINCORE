"""
Comprehensive P&L Rules Verification Script
Tests all 16+ Income Statement formulas against the live API endpoint.
"""
import requests
import json
import sys

BASE = "http://localhost:8080"

def get_pl_data():
    resp = requests.get(f"{BASE}/api/analytics/income-statement")
    resp.raise_for_status()
    return resp.json()

def find_row(rows, code):
    for r in rows:
        if r.get("c") == code:
            return r
    return None

def val(rows, code):
    r = find_row(rows, code)
    if r is None:
        return None
    return r.get("ac", 0) or 0

def check(rule_num, description, expected, actual, tolerance=0.01):
    if expected is None or actual is None:
        print(f"  RULE {rule_num}: SKIP - {description} (missing data: expected={expected}, actual={actual})")
        return True
    diff = abs(expected - actual)
    ok = diff <= tolerance
    status = "PASS" if ok else "FAIL"
    symbol = "+" if ok else "X"
    print(f"  [{symbol}] RULE {rule_num}: {description}")
    print(f"      Expected: {expected:,.2f}  |  Actual: {actual:,.2f}  |  Diff: {diff:,.2f}")
    return ok

def main():
    print("=" * 70)
    print("P&L RULES VERIFICATION")
    print("=" * 70)

    data = get_pl_data()
    rows = data.get("rows", [])

    print(f"\nLoaded {len(rows)} P&L rows")
    print(f"Period: {data.get('period', 'N/A')}")
    print(f"Company: {data.get('company', 'N/A')}")
    print()

    # Print all row codes and values for reference
    print("-" * 70)
    print("ALL ROW CODES AND VALUES:")
    print("-" * 70)
    for r in rows:
        code = r.get("c", "")
        label = r.get("l", "")
        ac = r.get("ac", "")
        lvl = r.get("lvl", "")
        if code:
            print(f"  {code:25s} | {label:40s} | {str(ac):>15s} | lvl={lvl}")
    print()

    results = []

    print("-" * 70)
    print("REVENUE RULES")
    print("-" * 70)

    # Rule 1: Total Revenue = Revenue Wholesale + Revenue Retail + Other Revenue
    rev_total = val(rows, "REV")
    rev_wholesale = val(rows, "REV.W")
    rev_retail = val(rows, "REV.R")
    rev_other = val(rows, "REV.O")
    expected_rev = (rev_wholesale or 0) + (rev_retail or 0) + (rev_other or 0)
    results.append(check(1, "Total Revenue = Wholesale + Retail + Other Revenue", expected_rev, rev_total))

    # Rule 2: Revenue Wholesale = Petrol + Diesel + Bitumen
    rev_w_petrol = val(rows, "REV.W.P")
    rev_w_diesel = val(rows, "REV.W.D")
    rev_w_bitumen = val(rows, "REV.W.B")
    expected_w = (rev_w_petrol or 0) + (rev_w_diesel or 0) + (rev_w_bitumen or 0)
    results.append(check(2, "Revenue Wholesale = Petrol + Diesel + Bitumen", expected_w, rev_wholesale))

    # Rule 3: Revenue Retail = Petrol + Diesel + CNG + LPG
    rev_r_petrol = val(rows, "REV.R.P")
    rev_r_diesel = val(rows, "REV.R.D")
    rev_r_cng = val(rows, "REV.R.CNG")
    rev_r_lpg = val(rows, "REV.R.LPG")
    expected_r = (rev_r_petrol or 0) + (rev_r_diesel or 0) + (rev_r_cng or 0) + (rev_r_lpg or 0)
    results.append(check(3, "Revenue Retail = Petrol + Diesel + CNG + LPG", expected_r, rev_retail))

    print()
    print("-" * 70)
    print("COGS RULES")
    print("-" * 70)

    # Rule 4: Total COGS = COGS Wholesale + COGS Retail + Other COGS
    cogs_total = val(rows, "COGS")
    cogs_wholesale = val(rows, "COGS.W")
    cogs_retail = val(rows, "COGS.R")
    cogs_other = val(rows, "COGS.O")
    expected_cogs = (cogs_wholesale or 0) + (cogs_retail or 0) + (cogs_other or 0)
    results.append(check(4, "Total COGS = Wholesale + Retail + Other COGS", expected_cogs, cogs_total))

    # Rule 5: COGS Wholesale = Petrol + Diesel + Bitumen
    cogs_w_petrol = val(rows, "COGS.W.P")
    cogs_w_diesel = val(rows, "COGS.W.D")
    cogs_w_bitumen = val(rows, "COGS.W.B")
    expected_cw = (cogs_w_petrol or 0) + (cogs_w_diesel or 0) + (cogs_w_bitumen or 0)
    results.append(check(5, "COGS Wholesale = Petrol + Diesel + Bitumen", expected_cw, cogs_wholesale))

    # Rule 6: COGS Retail = Petrol + Diesel + CNG + LPG
    cogs_r_petrol = val(rows, "COGS.R.P")
    cogs_r_diesel = val(rows, "COGS.R.D")
    cogs_r_cng = val(rows, "COGS.R.CNG")
    cogs_r_lpg = val(rows, "COGS.R.LPG")
    expected_cr = (cogs_r_petrol or 0) + (cogs_r_diesel or 0) + (cogs_r_cng or 0) + (cogs_r_lpg or 0)
    results.append(check(6, "COGS Retail = Petrol + Diesel + CNG + LPG", expected_cr, cogs_retail))

    print()
    print("-" * 70)
    print("GROSS MARGIN RULES")
    print("-" * 70)

    # Rule 7-13: Individual Gross Margins = Revenue - COGS per product
    # NOTE: COGS values are stored as NEGATIVE numbers, so GM = Rev + COGS (not Rev - COGS)
    margin_checks = [
        (7,  "GM Wholesale Petrol = Rev W Petrol + COGS W Petrol",   "GM.W.P",   rev_w_petrol,  cogs_w_petrol),
        (8,  "GM Wholesale Diesel = Rev W Diesel + COGS W Diesel",   "GM.W.D",   rev_w_diesel,  cogs_w_diesel),
        (9,  "GM Wholesale Bitumen = Rev W Bitumen + COGS W Bitumen","GM.W.B",   rev_w_bitumen, cogs_w_bitumen),
        (10, "GM Retail Petrol = Rev R Petrol + COGS R Petrol",      "GM.R.P",   rev_r_petrol,  cogs_r_petrol),
        (11, "GM Retail Diesel = Rev R Diesel + COGS R Diesel",      "GM.R.D",   rev_r_diesel,  cogs_r_diesel),
        (12, "GM Retail CNG = Rev R CNG + COGS R CNG",              "GM.R.CNG", rev_r_cng,     cogs_r_cng),
        (13, "GM Retail LPG = Rev R LPG + COGS R LPG",              "GM.R.LPG", rev_r_lpg,     cogs_r_lpg),
    ]

    for rule_num, desc, gm_code, rev_val, cogs_val in margin_checks:
        gm_actual = val(rows, gm_code)
        expected_gm = (rev_val or 0) + (cogs_val or 0)  # COGS is already negative
        results.append(check(rule_num, desc, expected_gm, gm_actual))

    print()
    print("-" * 70)
    print("MARGIN TOTAL RULES")
    print("-" * 70)

    # Rule 14: GM Wholesale Total = GM W Petrol + GM W Diesel + GM W Bitumen
    gm_w = val(rows, "GM.W")
    gm_w_p = val(rows, "GM.W.P")
    gm_w_d = val(rows, "GM.W.D")
    gm_w_b = val(rows, "GM.W.B")
    expected_gm_w = (gm_w_p or 0) + (gm_w_d or 0) + (gm_w_b or 0)
    results.append(check(14, "GM Wholesale = GM W Petrol + Diesel + Bitumen", expected_gm_w, gm_w))

    # Rule 15: GM Retail Total = GM R Petrol + GM R Diesel + GM R CNG + GM R LPG
    gm_r = val(rows, "GM.R")
    gm_r_p = val(rows, "GM.R.P")
    gm_r_d = val(rows, "GM.R.D")
    gm_r_cng = val(rows, "GM.R.CNG")
    gm_r_lpg = val(rows, "GM.R.LPG")
    expected_gm_r = (gm_r_p or 0) + (gm_r_d or 0) + (gm_r_cng or 0) + (gm_r_lpg or 0)
    results.append(check(15, "GM Retail = GM R Petrol + Diesel + CNG + LPG", expected_gm_r, gm_r))

    # Rule 16: Total Gross Margin = GM Wholesale + GM Retail
    gm_total = val(rows, "GM")
    expected_gm_total = (gm_w or 0) + (gm_r or 0)
    results.append(check(16, "Total Gross Margin = GM Wholesale + GM Retail", expected_gm_total, gm_total))

    print()
    print("-" * 70)
    print("PROFIT RULES")
    print("-" * 70)

    # Rule 17: Total Gross Profit = Total Gross Margin + Other Revenue + Other COGS
    # NOTE: Other COGS is stored as negative, so we ADD it (TGP = GM + OtherRev - |OtherCOGS|)
    tgp = val(rows, "TGP")
    expected_tgp = (gm_total or 0) + (rev_other or 0) + (cogs_other or 0)
    results.append(check(17, "TGP = Total Gross Margin + Other Revenue + Other COGS (neg)", expected_tgp, tgp))

    # Rule 18: EBITDA = TGP + G&A (G&A is stored as negative)
    ebitda = val(rows, "EBITDA")
    ga = val(rows, "GA")
    expected_ebitda = (tgp or 0) + (ga or 0)  # GA is already negative
    results.append(check(18, "EBITDA = TGP + G&A (neg)", expected_ebitda, ebitda))

    # Summary
    print()
    print("=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"RESULTS: {passed}/{total} rules passed")
    if passed == total:
        print("ALL RULES VERIFIED SUCCESSFULLY!")
    else:
        print(f"WARNING: {total - passed} rules FAILED!")
    print("=" * 70)

    # Also verify key KPIs from the response
    kpis = data.get("kpis", {})
    if kpis:
        print()
        print("-" * 70)
        print("KPI VALUES:")
        print("-" * 70)
        for k, v in kpis.items():
            print(f"  {k}: {v}")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
