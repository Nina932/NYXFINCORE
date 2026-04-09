"""Comprehensive Financial System Test Suite"""
import requests
import json

BASE = 'http://localhost:8080'
results = []
fails = 0

def test(name, condition, detail=''):
    global fails
    status = 'PASS' if condition else 'FAIL'
    if not condition:
        fails += 1
    results.append(f'  [{status}] {name}' + (f' -- {detail}' if detail else ''))

print('=' * 70)
print('COMPREHENSIVE FINANCIAL SYSTEM TEST SUITE')
print('=' * 70)

# --- TEST 1: API Health ---
print('\n1. API HEALTH & ENDPOINTS')
r = requests.get(f'{BASE}/health')
test('Health endpoint', r.status_code == 200)

r = requests.get(f'{BASE}/api/datasets')
datasets = r.json()
test('Datasets endpoint', r.status_code == 200)
test('Multiple datasets exist', len(datasets) >= 2, f'{len(datasets)} datasets')

# --- TEST 2: DS2 P&L Waterfall (Path A) ---
print('\n2. DS2 P&L WATERFALL (Path A - Revenue+COGS sheets)')
pl2 = requests.get(f'{BASE}/api/analytics/income-statement?dataset_id=2').json()
rev = pl2['revenue']['total']
cogs = pl2['cogs']['total']
gp = pl2['margins']['total_gross_profit']
ga = pl2['ga_expenses']
ebitda = pl2['ebitda']
da = pl2['da_expenses']
ebit = pl2['ebit']
oi = pl2.get('other_income', 0)
fn = pl2['finance_net']
ebt = pl2['ebt']
tax = pl2['tax_expense']
np2 = pl2['net_profit']

test('DS2 Revenue > 0', rev > 0, f'{rev:,.0f}')
test('DS2 COGS > 0', cogs > 0, f'{cogs:,.0f}')
test('DS2 GP = Rev - COGS', abs(gp - (rev - cogs)) < 1)
test('DS2 EBITDA = GP - GA', abs(ebitda - (gp - ga)) < 1)
test('DS2 EBIT = EBITDA - DA', abs(ebit - (ebitda - da)) < 1)
test('DS2 EBT = EBIT + OI + Fin', abs(ebt - (ebit + oi + fn)) < 1)
test('DS2 NP = EBT - Tax', abs(np2 - (ebt - tax)) < 1)
test('DS2 GA breakdown matches total', abs(sum(pl2['ga_breakdown'].values()) - ga) < 1)
test('DS2 DA breakdown matches total', abs(sum(pl2['da_breakdown'].values()) - da) < 1)
test('DS2 Finance data from Mapping', fn != 0, f'Finance Net = {fn:,.0f}')

# Check no parent codes (7310, 7410 without dots) in GA
ga_keys_2 = list(pl2['ga_breakdown'].keys())
parent_in_ga = [k for k in ga_keys_2 if k in ('7310', '7410', '7310.01', '7310.02')]
test('DS2 No parent codes in GA', len(parent_in_ga) == 0, f'parents found: {parent_in_ga}' if parent_in_ga else '')

# --- TEST 3: DS3 P&L Waterfall (Path B) ---
print('\n3. DS3 P&L WATERFALL (Path B - TDSheet auto-gen)')
pl3 = requests.get(f'{BASE}/api/analytics/income-statement?dataset_id=3').json()
rev3 = pl3['revenue']['total']
cogs3 = pl3['cogs']['total']
gp3 = pl3['margins']['total_gross_profit']
ga3 = pl3['ga_expenses']
ebitda3 = pl3['ebitda']
da3 = pl3['da_expenses']
ebit3 = pl3['ebit']
oi3 = pl3.get('other_income', 0)
fn3 = pl3['finance_net']
ebt3 = pl3['ebt']
tax3 = pl3['tax_expense']
np3 = pl3['net_profit']

test('DS3 Revenue > 0', rev3 > 0, f'{rev3:,.0f}')
test('DS3 COGS > 0', cogs3 > 0, f'{cogs3:,.0f}')
test('DS3 GP = Rev - COGS', abs(gp3 - (rev3 - cogs3)) < 1)
test('DS3 EBITDA = GP - GA', abs(ebitda3 - (gp3 - ga3)) < 1)
test('DS3 EBIT = EBITDA - DA', abs(ebit3 - (ebitda3 - da3)) < 1)
test('DS3 EBT = EBIT + OI + Fin', abs(ebt3 - (ebit3 + oi3 + fn3)) < 1)
test('DS3 NP = EBT - Tax', abs(np3 - (ebt3 - tax3)) < 1)
test('DS3 Other Income > 0', oi3 > 0, f'{oi3:,.0f}')
test('DS3 OI breakdown matches total', abs(sum(pl3.get('other_income_breakdown', {}).values()) - oi3) < 1)
test('DS3 GA breakdown matches total', abs(sum(pl3['ga_breakdown'].values()) - ga3) < 1)
test('DS3 DA breakdown matches total', abs(sum(pl3['da_breakdown'].values()) - da3) < 1)
parent_in_ga3 = [k for k in pl3['ga_breakdown'].keys() if k in ('7310', '7410', '7310.01', '7310.02')]
test('DS3 No parent codes in GA', len(parent_in_ga3) == 0, f'parents found: {parent_in_ga3}' if parent_in_ga3 else '')

# --- TEST 4: Cross-Dataset Validation ---
print('\n4. CROSS-DATASET VALIDATION')
test('Revenue close (same company)', abs(rev - rev3) / rev < 0.005,
     f'diff={abs(rev - rev3):,.0f} ({abs(rev - rev3) / rev * 100:.2f}%)')
test('COGS within 1%', abs(cogs - cogs3) / cogs < 0.01,
     f'diff={abs(cogs - cogs3):,.0f}')
test('GA within 5%', abs(ga - ga3) / ga < 0.05,
     f'DS2={ga:,.0f} DS3={ga3:,.0f} diff={abs(ga - ga3):,.0f}')

# --- TEST 5: Balance Sheet ---
print('\n5. BALANCE SHEET')
bs2 = requests.get(f'{BASE}/api/analytics/balance-sheet?dataset_id=2').json()
test('DS2 BS has assets > 0', bs2['totals']['assets'] > 0, f"{bs2['totals']['assets']:,.0f}")
test('DS2 BS has liabilities > 0', bs2['totals']['liabilities'] > 0, f"{bs2['totals']['liabilities']:,.0f}")
test('DS2 BS liabilities are positive', bs2['totals']['liabilities'] > 0, 'sign correction working')

cpr = [r for r in bs2['rows'] if 'current period' in r['l'].lower()]
test('DS2 BS has Current Period Result', len(cpr) > 0)
if cpr:
    test('DS2 BS CPR matches P&L NP', abs(cpr[0]['ac'] - np2) < 1,
         f"CPR={cpr[0]['ac']:,.0f} vs NP={np2:,.0f}")

bs3 = requests.get(f'{BASE}/api/analytics/balance-sheet?dataset_id=3').json()
cpr3 = [r for r in bs3['rows'] if 'current period' in r['l'].lower()]
test('DS3 BS has Current Period Result', len(cpr3) > 0)
if cpr3:
    test('DS3 BS CPR matches P&L NP', abs(cpr3[0]['ac'] - np3) < 1,
         f"CPR={cpr3[0]['ac']:,.0f} vs NP={np3:,.0f}")

# --- TEST 6: Trial Balance ---
print('\n6. TRIAL BALANCE')
tb3 = requests.get(f'{BASE}/api/analytics/trial-balance?dataset_id=3').json()
test('DS3 TB has items', tb3['total'] > 0, f"{tb3['total']} items")

# --- TEST 7: COA Mapping ---
print('\n7. COA MAPPING SYSTEM')
coa = requests.get(f'{BASE}/api/analytics/coa').json()
test('COA entries exist', len(coa) > 0 or (isinstance(coa, dict) and len(coa.get('entries', [])) > 0))

coa_test = requests.get(f'{BASE}/api/analytics/coa/test?code=7310.01').json()
test('COA test mapping works', coa_test is not None and len(str(coa_test)) > 5)

coa_cov = requests.get(f'{BASE}/api/analytics/coa/coverage').json()
test('COA coverage endpoint works', coa_cov is not None)

# --- TEST 8: Revenue & Costs ---
print('\n8. REVENUE & COSTS ENDPOINTS')
rev_r = requests.get(f'{BASE}/api/analytics/revenue').json()
test('Revenue endpoint works', rev_r is not None)
costs_r = requests.get(f'{BASE}/api/analytics/costs').json()
test('Costs endpoint works', costs_r is not None)
cogs_r = requests.get(f'{BASE}/api/analytics/cogs').json()
test('COGS endpoint works', cogs_r is not None)

# --- TEST 9: Dashboard ---
print('\n9. DASHBOARD')
dash = requests.get(f'{BASE}/api/analytics/dashboard').json()
test('Dashboard returns data', dash is not None)
dash3 = requests.get(f'{BASE}/api/analytics/dashboard?dataset_id=3').json()
test('Dashboard with dataset_id works', dash3 is not None)

# --- TEST 10: P&L Rows Structure ---
print('\n10. P&L ROWS STRUCTURE')
pl_rows = requests.get(f'{BASE}/api/analytics/pl?dataset_id=3').json()
test('P&L rows endpoint works', 'rows' in pl_rows or isinstance(pl_rows, dict))

# Check P&L row sequence
if 'rows' in pl_rows:
    row_codes = [r.get('c', '') for r in pl_rows['rows']]
    expected_order = ['REV', 'COGS', 'GP', 'GA', 'EBITDA', 'DA', 'EBIT']
    found = [c for c in expected_order if c in row_codes]
    test('P&L has standard waterfall rows', len(found) >= 5, f'Found: {found}')

    # Check Other Income section exists
    oi_rows = [r for r in pl_rows['rows'] if 'other income' in r.get('l', '').lower() or r.get('c', '') == 'OI']
    test('P&L has Other Income section', len(oi_rows) > 0)

# --- SUMMARY ---
print('\n' + '=' * 70)
print('DETAILED RESULTS:')
for r in results:
    print(r)
print('=' * 70)
total = len(results)
passed = total - fails
print(f'\nRESULTS: {passed}/{total} PASSED, {fails} FAILED')
if fails == 0:
    print('ALL TESTS PASSED!')
print('=' * 70)
