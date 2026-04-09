"""
Re-upload all TB files to fix admin_expenses=0 bug.
The bug was that account 7410 was in DA_PREFIXES (depreciation) instead of admin expenses.
The fix is already in tb_to_statements.py, but existing data needs to be re-uploaded.

Run: python reupload_tbs.py
"""
import requests
import os
import glob

BASE = 'http://127.0.0.1:9200'

tb_files = glob.glob('C:/Users/Nino/Downloads/TB/SGP *.xls')
print(f"Found {len(tb_files)} TB files to re-upload\n")

all_ok = True
for fpath in sorted(tb_files):
    fname = os.path.basename(fpath)
    with open(fpath, 'rb') as f:
        r = requests.post(
            f'{BASE}/api/agent/agents/smart-upload',
            files={'file': (fname, f)},
            timeout=120,
        )
    if r.status_code != 200:
        print(f"  ERROR {fname}: HTTP {r.status_code}")
        all_ok = False
        continue

    d = r.json()
    admin = d.get('pnl', {}).get('admin_expenses', 0)
    selling = d.get('pnl', {}).get('selling_expenses', 0)
    period = d.get('period', 'unknown')
    status = "OK" if admin != 0 else "STILL ZERO"
    if admin == 0:
        all_ok = False
    print(f"  {fname}: period={period}  admin={admin:,.0f}  selling={selling:,.0f}  [{status}]")

print(f"\n{'ALL GOOD' if all_ok else 'SOME ISSUES'} — {len(tb_files)} files processed")
