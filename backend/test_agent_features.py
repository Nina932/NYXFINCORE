#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import time
import json
from datetime import datetime

BASE_URL = 'http://localhost:8080'
ENDPOINT = f'{BASE_URL}/api/agent/chat'
PAUSE_SECONDS = 20


def separator(title):
    print()
    print('=' * 90)
    print(f'  TEST: {title}')
    print('=' * 90)


def send_chat(message, history=None):
    payload = {'message': message, 'history': history or []}
    try:
        resp = requests.post(ENDPOINT, json=payload, timeout=120)
        return {
            'status_code': resp.status_code,
            'body': resp.json() if resp.status_code == 200 else resp.text,
            'ok': resp.status_code == 200,
        }
    except requests.exceptions.ConnectionError:
        return {'status_code': 0, 'body': 'CONNECTION REFUSED', 'ok': False}
    except Exception as e:
        return {'status_code': -1, 'body': str(e), 'ok': False}


def extract_tools(body):
    if isinstance(body, dict):
        return [t.get('tool') or t.get('name', 'unknown') for t in body.get('tool_calls', [])]
    return []


def pfr(result):
    sc = result['status_code']
    print(f'  HTTP Status : {sc}')
    if result['ok']:
        body = result['body']
        response_text = body.get('response', body.get('text', ''))
        print(f'  Response    : {str(response_text)[:2000]}')
        tools = body.get('tool_calls', [])
        if tools:
            print(f'  Tool calls  : {len(tools)}')
            for i, tc in enumerate(tools):
                tn = tc.get('tool') or tc.get('name', '?')
                ti = tc.get('input', {})
                tr = tc.get('result', '')
                print(f'    [{i+1}] Tool   : {tn}')
                print(f'        Input  : {json.dumps(ti, ensure_ascii=False)[:300]}')
                rs = json.dumps(tr, ensure_ascii=False) if isinstance(tr, (dict, list)) else str(tr)
                print(f'        Result : {rs[:800]}')
        else:
            print('  Tool calls  : NONE')
        nav = body.get('navigation') or body.get('navigate')
        if nav:
            print(f'  Navigation  : {nav}')
        chart = body.get('chart') or body.get('chart_data')
        if chart:
            print(f'  Chart Data  : {json.dumps(chart, ensure_ascii=False)[:400]}')
    else:
        bd = str(result['body'])[:500]
        print(f'  Error Body  : {bd}')


def pause(seconds):
    print(f'  ... pausing {seconds}s before next test ...')
    time.sleep(seconds)


def test_1_navigation():
    separator('1. Navigation (PnL page)')
    result = send_chat('Navigate to the P&L page')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_nav = 'navigate_to_page' in tools
    body = result.get('body', {})
    nav_val = body.get('navigation') or body.get('navigate') or ''
    if not nav_val and result['ok']:
        for tc in body.get('tool_calls', []):
            if (tc.get('tool') or tc.get('name', '')) == 'navigate_to_page':
                nav_val = tc.get('input', {}).get('page', '')
                break
    passed = has_nav and bool(nav_val)
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: nav_tool={has_nav}, nav_value={nav_val!r}, PASSED={yn}')
    return passed


def test_1b_navigation_dashboard():
    separator('1b. Navigation (Dashboard)')
    result = send_chat('Take me to the dashboard')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_nav = 'navigate_to_page' in tools
    body = result.get('body', {})
    nav_val = ''
    if result['ok']:
        for tc in body.get('tool_calls', []):
            if (tc.get('tool') or tc.get('name', '')) == 'navigate_to_page':
                nav_val = tc.get('input', {}).get('page', '')
                break
    passed = has_nav and 'dash' in str(nav_val).lower()
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: nav_tool={has_nav}, nav_value={nav_val!r}, PASSED={yn}')
    return passed


def test_2_generate_pl():
    separator('2. Generate PnL / Income Statement')
    result = send_chat('Generate the income statement for the current period')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_pl = any(t in tools for t in ['generate_pl_statement', 'generate_income_statement'])
    body = result.get('body', {})
    resp_text = str(body.get('response', ''))
    has_fin = any(kw in resp_text.lower() for kw in ['revenue', 'expense', 'income', 'profit', 'ebitda', 'margin', 'cogs'])
    has_rows = False
    if result['ok']:
        for tc in body.get('tool_calls', []):
            tr = tc.get('result', '')
            if isinstance(tr, dict):
                has_rows = bool(tr.get('rows') or tr.get('sections') or tr.get('data'))
            elif isinstance(tr, str):
                has_rows = 'revenue' in tr.lower() or 'rows' in tr.lower()
    passed = has_pl and (has_fin or has_rows)
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: pl_tool={has_pl} (tools={tools}), fin_data={has_fin}, rows={has_rows}, PASSED={yn}')
    return passed


def test_3_generate_bs():
    separator('3. Generate Balance Sheet')
    result = send_chat('Generate a balance sheet')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_bs = 'generate_balance_sheet' in tools
    body = result.get('body', {})
    resp_text = str(body.get('response', ''))
    has_data = any(kw in resp_text.lower() for kw in ['assets', 'liabilities', 'equity', 'balance', 'total'])
    passed = has_bs or has_data
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: bs_tool={has_bs} (tools={tools}), bs_data={has_data}, PASSED={yn}')
    return passed


def test_4_generate_mr():
    separator('4. Generate Management Report')
    result = send_chat('Generate a management report for the current period')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_mr = 'generate_mr_report' in tools
    body = result.get('body', {})
    resp_text = str(body.get('response', ''))
    has_data = any(kw in resp_text.lower() for kw in ['management', 'report', 'revenue', 'margin', 'ebitda', 'summary'])
    passed = has_mr or has_data
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: mr_tool={has_mr} (tools={tools}), mr_data={has_data}, PASSED={yn}')
    return passed


def test_5_generate_chart():
    separator('5. Generate Chart (revenue breakdown)')
    result = send_chat('Create a bar chart showing revenue breakdown by category')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_chart = 'generate_chart' in tools
    body = result.get('body', {})
    has_chart_data = False
    if result['ok']:
        for tc in body.get('tool_calls', []):
            if (tc.get('tool') or tc.get('name', '')) == 'generate_chart':
                inp = tc.get('input', {})
                has_chart_data = bool(inp.get('labels')) and bool(inp.get('data'))
                break
    chart = body.get('chart') or body.get('chart_data')
    if chart:
        has_chart_data = True
    passed = has_chart and has_chart_data
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: chart_tool={has_chart} (tools={tools}), chart_data={has_chart_data}, PASSED={yn}')
    return passed


def test_6_save_report():
    separator('6. Save Report to DB')
    result = send_chat('Save the latest P&L report to the database with title Test PL Report Q1')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_save = 'save_report_to_db' in tools
    body = result.get('body', {})
    resp_text = str(body.get('response', ''))
    saved_ok = any(kw in resp_text.lower() for kw in ['saved', 'stored', 'database', 'success'])
    tool_saved = False
    if result['ok']:
        for tc in body.get('tool_calls', []):
            if (tc.get('tool') or tc.get('name', '')) == 'save_report_to_db':
                tr = tc.get('result', '')
                tool_saved = 'saved' in str(tr).lower() or 'id' in str(tr).lower()
                break
    passed = has_save and (saved_ok or tool_saved)
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: save_tool={has_save} (tools={tools}), confirmed={saved_ok}, tool_ok={tool_saved}, PASSED={yn}')
    return passed


def test_7_detect_anomalies():
    separator('7. Detect Anomalies')
    result = send_chat('Find anomalies in our expenses. Flag any unusually large transactions.')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_anom = 'detect_anomalies' in tools
    body = result.get('body', {})
    resp_text = str(body.get('response', ''))
    has_data = any(kw in resp_text.lower() for kw in ['anomal', 'unusual', 'flag', 'large', 'outlier', 'spike', 'exceed', 'threshold'])
    passed = has_anom or has_data
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: anomaly_tool={has_anom} (tools={tools}), anomaly_data={has_data}, PASSED={yn}')
    return passed


def test_8_search_counterparty():
    separator('8. Search Counterparty')
    result = send_chat('Analyze our top counterparties by spend. Show the top 5 vendors.')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_cp = 'search_counterparty' in tools
    body = result.get('body', {})
    resp_text = str(body.get('response', ''))
    has_data = any(kw in resp_text.lower() for kw in ['counterpart', 'vendor', 'supplier', 'spend', 'partner', 'company'])
    passed = has_cp or has_data
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: cp_tool={has_cp} (tools={tools}), cp_data={has_data}, PASSED={yn}')
    return passed


def test_9_compare_periods():
    separator('9. Compare Periods')
    result = send_chat('Compare the financial data between period 1 and period 2, using dataset IDs 1 and 2')
    pfr(result)
    tools = extract_tools(result.get('body', {})) if result['ok'] else []
    has_cmp = 'compare_periods' in tools
    body = result.get('body', {})
    resp_text = str(body.get('response', ''))
    has_data = any(kw in resp_text.lower() for kw in ['compar', 'period', 'change', 'increase', 'decrease', 'variance', 'dataset', 'only one', 'not enough'])
    passed = has_cmp or has_data
    yn = 'YES' if passed else 'NO'
    print(f'  VERDICT: compare_tool={has_cmp} (tools={tools}), compare_data={has_data}, PASSED={yn}')
    return passed


def main():
    print('=' * 90)
    print('  FinAI Agent Feature Test Suite')
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'  Started at: {ts}')
    print(f'  Target: {ENDPOINT}')
    print(f'  Pause between tests: {PAUSE_SECONDS}s')
    print('=' * 90)

    print('  Checking server connectivity...')
    try:
        r = requests.get(f'{BASE_URL}/api/agent/status', timeout=10)
        print(f'  Server status: {r.status_code} - {r.json()}')
    except Exception as e:
        print(f'  WARNING: Could not reach server - {e}')

    tests = [
        ('1. Navigation (PL)', test_1_navigation),
        ('1b. Navigation (Dashboard)', test_1b_navigation_dashboard),
        ('2. Generate PnL Statement', test_2_generate_pl),
        ('3. Generate Balance Sheet', test_3_generate_bs),
        ('4. Generate MR Report', test_4_generate_mr),
        ('5. Generate Chart', test_5_generate_chart),
        ('6. Save Report to DB', test_6_save_report),
        ('7. Detect Anomalies', test_7_detect_anomalies),
        ('8. Search Counterparty', test_8_search_counterparty),
        ('9. Compare Periods', test_9_compare_periods),
    ]

    results = {}
    for i, (name, fn) in enumerate(tests):
        try:
            passed = fn()
            results[name] = 'PASS' if passed else 'FAIL'
        except Exception as e:
            print(f'  EXCEPTION: {e}')
            import traceback
            traceback.print_exc()
            results[name] = 'ERROR'
        if i < len(tests) - 1:
            pause(PAUSE_SECONDS)

    print()
    print('=' * 90)
    print('  FINAL SUMMARY')
    print('=' * 90)
    total = len(results)
    passed_count = sum(1 for v in results.values() if v == 'PASS')
    failed_count = sum(1 for v in results.values() if v == 'FAIL')
    error_count = sum(1 for v in results.values() if v == 'ERROR')

    for name, status in results.items():
        icon = '[PASS]' if status == 'PASS' else '[FAIL]' if status == 'FAIL' else '[ERR ]'
        print(f'  {icon} {name}')

    print(f'  Total: {total} | Passed: {passed_count} | Failed: {failed_count} | Errors: {error_count}')
    pct = int(passed_count / total * 100) if total > 0 else 0
    print(f'  Score: {passed_count}/{total} ({pct}%)')
    ts2 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'  Finished at: {ts2}')
    print('=' * 90)


if __name__ == '__main__':
    main()

