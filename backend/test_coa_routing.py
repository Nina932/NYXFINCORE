"""Test COA routing with actual Reports.xlsx data codes."""
import sys
sys.path.insert(0, ".")
from app.services.file_parser import map_coa

# All account codes from Reports.xlsx BASE sheet
DATA_CODES = [
    "1110", "1120", "1210", "1220", "1294",
    "1410", "1412", "1480", "1490",
    "1605", "1610", "1621", "1622", "1623", "1624", "1626", "1630", "1640",
    "1790", "1810", "1820", "1821",
    "2120", "2130", "2160", "2230", "2231", "2610",
    "3110", "3130", "3210", "3310", "3330", "3340", "3410", "3490",
    "4170",
    "5310",
    # P&L codes (with dots)
    "6110.01.1", "6110.01.2", "7310.02.1", "7410", "7410.01",
    "8110.01.1", "8220.01.1", "9210",
]

# Expected routing based on AccountN.xlsx
EXPECTED = {
    "1110": ("asset", "current", "Cash"),
    "1120": ("asset", "current", "Cash"),
    "1210": ("asset", "current", "Bank"),
    "1220": ("asset", "current", "Bank"),
    "1294": ("asset", "current", "Money in Transit"),
    "1410": ("asset", "current", "Trade Receivables"),
    "1412": ("asset", "current", "Trade Receivables"),
    "1480": ("asset", "current", "Advances"),
    "1490": ("asset", "current", "Other Receivables"),
    "1605": ("asset", "current", "Goods in Transit"),
    "1610": ("asset", "current", "Merchandise"),
    "1621": ("asset", "current", "Raw Materials"),
    "1622": ("asset", "current", "Raw Materials"),  # Fuel = current!
    "1623": ("asset", "current", "Raw Materials"),
    "1624": ("asset", "current", "Raw Materials"),
    "1626": ("asset", "current", "Raw Materials"),
    "1630": ("asset", "current", "Work in Progress"),
    "1640": ("asset", "current", "Finished Goods"),
    "1790": ("asset", "current", "Prepaid VAT"),
    "1810": ("asset", "current", "Dividends"),      # CURRENT, not noncurrent!
    "1820": ("asset", "current", "Interest"),        # CURRENT!
    "1821": ("asset", "current", "Interest"),        # CURRENT!
    "2120": ("asset", "noncurrent", "Construction"),
    "2130": ("asset", "noncurrent", "Fixed Assets"),
    "2160": ("asset", "noncurrent", "Fixed Asset"),
    "2230": ("asset", "noncurrent", "Acc. Depr"),    # contra
    "2231": ("asset", "noncurrent", "Acc. Depr"),    # contra
    "2610": ("asset", "noncurrent", "Acc. Amort"),   # contra
    "3110": ("liability", "current", "Trade Pay"),
    "3130": ("liability", "current", "Wages"),
    "3210": ("liability", "current", "Short-term"),
    "3310": ("liability", "current", "Income Tax"),
    "3330": ("liability", "current", "VAT"),
    "3340": ("asset", "current", "Input VAT"),       # ASSET, not liability!
    "3410": ("liability", "current", "Interest Pay"),
    "3490": ("liability", "current", "Other Accrued"),
    "4170": ("liability", "noncurrent", "Lease"),
    "5310": ("equity", "equity", "Retained"),
}

print("=" * 90)
print(f"{'CODE':<12} {'BS_SIDE':<12} {'BS_SUB':<12} {'LABEL':<35} {'STATUS'}")
print("=" * 90)

errors = 0
for code in DATA_CODES:
    m = map_coa(code)
    if not m:
        print(f"{code:<12} {'???':<12} {'???':<12} {'UNMAPPED!':<35} FAIL")
        errors += 1
        continue

    bs_side = m.get("bs_side", "")
    bs_sub = m.get("bs_sub", "")
    label = m.get("bs", m.get("pl", "?"))
    side = m.get("side", "")
    prefix = m.get("prefix", "")

    # Check expected routing
    if code in EXPECTED:
        exp_side, exp_sub, exp_label_part = EXPECTED[code]
        ok_side = bs_side == exp_side
        ok_sub = bs_sub == exp_sub
        status = "OK" if (ok_side and ok_sub) else f"FAIL (want {exp_side}/{exp_sub})"
        if not (ok_side and ok_sub):
            errors += 1
    else:
        status = f"P&L: side={side}"

    print(f"{code:<12} {bs_side or side:<12} {bs_sub or '-':<12} {label:<35} {status}")

print("=" * 90)
print(f"\nTotal codes: {len(DATA_CODES)}, Errors: {errors}")
if errors == 0:
    print("ALL ROUTING CORRECT!")
else:
    print(f"FIX {errors} ROUTING ERRORS!")
