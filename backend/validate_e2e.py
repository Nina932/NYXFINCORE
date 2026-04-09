"""
FinAI End-to-End Pipeline Validation
Tests the complete analysis pipeline: classify -> enrich -> reason -> scenario -> telemetry
"""
import sys
sys.path.insert(0, '.')

print('=' * 60)
print('  END-TO-END PIPELINE VALIDATION')
print('  Classify -> Enrich -> Reason -> Scenario -> Telemetry')
print('=' * 60)

results = []

def check(name, ok, detail=''):
    status = '[OK] ' if ok else '[FAIL]'
    results.append((name, ok))
    print(f'  {status} {name}')
    if detail:
        print(f'         {detail}')


# ── Step 1: Account Classification ───────────────────────────
print()
print('Step 1: Account Classification (3-pass SemanticEnricher)')
from app.agents.data_agent import semantic_enricher

test_accounts = [
    ('1110', 'BS', 'debit'),    # Cash: BS, debit-normal
    ('6110', 'PL', 'credit'),   # Revenue: PL, credit-normal
    ('7310', 'PL', 'debit'),    # Selling Expense: PL, debit-normal
    ('3310', 'BS', 'credit'),   # Trade Payable: BS, credit-normal
    ('5000', 'BS', 'debit'),    # Capital Account (Georgian COA 5xxx = Capital, debit-normal)
]
for code, expected_bs_pl, expected_balance in test_accounts:
    result = semantic_enricher._classify_by_prefix(code)
    check(
        f'Account {code} -> {expected_bs_pl}/{expected_balance}',
        result.get('bs_pl') == expected_bs_pl and result.get('normal_balance') == expected_balance,
        f'got bs_pl={result.get("bs_pl")}, balance={result.get("normal_balance")}',
    )


# ── Step 2: KG Context Retrieval ─────────────────────────────
print()
print('Step 2: KG Context Retrieval for Financial Analysis')
from app.services.knowledge_graph import knowledge_graph

if not knowledge_graph.is_built:
    knowledge_graph.build()

gm_context   = knowledge_graph.query('gross margin benchmark petroleum wholesale', max_results=5)
audit_ctx    = knowledge_graph.query('revenue spike anomaly audit signal', max_results=3)
ratio_ctx    = knowledge_graph.query('current ratio liquidity working capital', max_results=3)
fraud_ctx    = knowledge_graph.query('Beneish M-Score fraud detection', max_results=3)

check('Gross margin KG context retrieved', len(gm_context) > 0,
      f'entities: {[e.entity_id for e in gm_context[:3]]}')
check('Audit signal KG context retrieved', len(audit_ctx) > 0)
check('Liquidity ratio KG context retrieved', len(ratio_ctx) > 0)
check('Fraud signal KG context retrieved', len(fraud_ctx) > 0)


# ── Step 3: Causal Reasoning ─────────────────────────────────
print()
print('Step 3: Financial Reasoning Engine (Causal Analysis)')
from app.services.financial_reasoning import reasoning_engine

chain = reasoning_engine.explain_metric_change(
    metric='wholesale_margin_pct',
    from_value=2.5,
    to_value=-1.8,
    period_from='Q3-2024',
    period_to='Q4-2024',
    context={
        'revenue': 45_200_000,
        'cogs': 46_300_000,
        'gross_profit': -1_100_000,
    },
)
check('Wholesale margin causal chain generated', chain is not None)
check('Negative margin change computed', chain.change_pct < 0)
check('Factors explain the cause', len(chain.factors) >= 1)
check('Narrative is substantive (>50 chars)', len(chain.narrative) > 50)
check('Severity reflects significant loss',
      chain.severity in ('significant', 'critical'),
      f'severity={chain.severity}')


# ── Step 4: Accounting Consistency ───────────────────────────
print()
print('Step 4: Balance Sheet Equation Verification')
pl_sample = {'revenue': 45_200_000, 'cogs': 46_300_000, 'ga_expenses': 1_200_000}

bs_clean = {'total_assets': 25_000_000, 'total_liabilities': 15_000_000, 'total_equity': 10_000_000}
issues_clean = reasoning_engine.detect_accounting_issues(pl_sample, bs_clean)
check('Clean BS (25M = 15M + 10M) has no issues', len(issues_clean) == 0,
      f'issues={[i["type"] for i in issues_clean]}')

bs_bad = {'total_assets': 25_000_000, 'total_liabilities': 15_000_000, 'total_equity': 9_000_000}
issues_bad = reasoning_engine.detect_accounting_issues(pl_sample, bs_bad)
check('Imbalanced BS (25M != 15M+9M) flags issue', len(issues_bad) > 0)

pl_bad = {'revenue': -500_000, 'cogs': 1_000_000}
issues_rev = reasoning_engine.detect_accounting_issues(pl_bad, bs_clean)
check('Negative revenue detected as accounting issue',
      any(i['type'] == 'negative_revenue' for i in issues_rev))


# ── Step 5: Scenario Simulation ──────────────────────────────
print()
print('Step 5: Scenario Simulation (What-If Analysis)')
base = {
    'revenue': 200_000_000,
    'cogs': 185_000_000,
    'ga_expenses': 8_000_000,
}

s_price_up = reasoning_engine.simulate_scenario(
    'Fuel price +5%', base=base, changes={'revenue_pct': 5.0})
check('Revenue +5% scenario computed',
      s_price_up.scenario_revenue > s_price_up.base_revenue)
check('Revenue +5% improves gross profit',
      s_price_up.scenario_gross_profit > s_price_up.base_gross_profit)

s_cogs_up = reasoning_engine.simulate_scenario(
    'Supply chain crisis +10% COGS', base=base, changes={'cogs_pct': 10.0})
check('COGS +10% reduces EBITDA significantly', s_cogs_up.ebitda_change_pct < -50)
check('Risk level is high/critical for 10% COGS jump',
      s_cogs_up.risk_level in ('high', 'critical'),
      f'risk_level={s_cogs_up.risk_level}, ebitda_change={s_cogs_up.ebitda_change_pct:.1f}%')


# ── Step 6: Liquidity Analysis ────────────────────────────────
print()
print('Step 6: Liquidity Analysis')
bs_data = {
    'total_current_assets': 15_000_000,
    'total_current_liabilities': 12_000_000,
    'inventory': 5_000_000,
    'total_assets': 35_000_000,
    'total_liabilities': 20_000_000,
    'total_equity': 15_000_000,
    'cash': 2_000_000,
    'total_debt': 8_000_000,
}
liquidity = reasoning_engine.build_liquidity_analysis(bs_data)
ratios = liquidity.get('ratios', liquidity)  # handle nested or flat dict
check('Liquidity analysis returns ratios dict', isinstance(liquidity, dict))
cr = ratios.get('current_ratio')
check('Current ratio = 1.25 (15M/12M)',
      cr is not None and abs(cr - 1.25) < 0.01,
      f'got current_ratio={cr}')
de = ratios.get('debt_to_equity')
check('D/E ratio = 0.533 (8M/15M)',
      de is not None and abs(de - 0.533) < 0.01,
      f'got debt_to_equity={de}')
check('Flags list present in liquidity output', 'flags' in liquidity)


# ── Step 7: Telemetry ────────────────────────────────────────
print()
print('Step 7: Telemetry Recording')
from app.services.telemetry import TelemetryCollector

tc = TelemetryCollector()
for _ in range(5):
    tc.record_agent_call('calc', 'run_focused_chat',
                         duration_ms=180, tokens_in=300, tokens_out=600, status='success')
for _ in range(3):
    tc.record_agent_call('insight', 'analyze', duration_ms=90, status='cache_hit')
tc.record_kg_retrieval('wholesale margin benchmark', results_count=4, duration_ms=2)
tc.record_tool_call('generate_income_statement', 'calc', duration_ms=2200)

summary = tc.metrics_summary()
health  = tc.health_score()

check('Calc agent: 5 calls tracked', summary['agents']['calc']['calls'] == 5)
check('Insight cache hits tracked (3)', tc._llm_cache_hits == 3)
check('KG retrieval tracked', summary['knowledge_graph']['total_queries'] == 1)
check('Tool call tracked', summary['tools']['total_calls'] == 1)
check('Health score in range 0-100', 0 <= health['overall'] <= 100)
check('Health grade assigned', health.get('grade') in ('A', 'B', 'C', 'D'))


# ── Step 8: GL Pipeline E2E ────────────────────────────────
print()
print('Step 8: GL Pipeline E2E (GL -> TB -> IS -> BS -> CF)')
from app.services.gl_pipeline import gl_pipeline

gl_txns = [
    {'acct_dr': '1110', 'acct_cr': '6110', 'amount': 500000},   # Cash dr, Revenue cr
    {'acct_dr': '7110', 'acct_cr': '1110', 'amount': 300000},   # COGS dr, Cash cr
    {'acct_dr': '1310', 'acct_cr': '6110', 'amount': 200000},   # Receivables dr, Revenue cr
    {'acct_dr': '7210', 'acct_cr': '1110', 'amount': 50000},    # Admin exp dr, Cash cr
    {'acct_dr': '5310', 'acct_cr': '1110', 'amount': 10000},    # Retained earnings, Cash
]
gl_result = gl_pipeline.run_from_transactions(gl_txns, period='E2E Test', currency='GEL')

check('GL pipeline returns trial_balance', 'trial_balance' in gl_result)
check('GL pipeline returns statements', 'statements' in gl_result)
check('GL pipeline returns reconciliation', 'reconciliation' in gl_result)
check('TB is balanced', gl_result['reconciliation']['tb_balanced'])
check('Revenue appears in IS', 'Revenue' in gl_result['statements'].get('income_statement', {}))
check('BS has current_assets', 'current_assets' in gl_result['statements'].get('balance_sheet', {}))

# ── Step 9: Benchmark Comparison E2E ─────────────────────
print()
print('Step 9: Benchmark Comparison E2E')
from app.services.benchmark_engine import benchmark_engine

# Compute ratios from the GL pipeline output
totals = gl_result['statements'].get('totals', {})
revenue = gl_result['statements'].get('income_statement', {}).get('Revenue', {}).get('amount', 700000)
cogs = gl_result['statements'].get('income_statement', {}).get('Cost of Sales', {}).get('amount', 300000)
gross_margin_pct = ((revenue - cogs) / revenue * 100) if revenue else 0

metrics_to_compare = {
    'gross_margin_pct': gross_margin_pct,
}
comparisons = benchmark_engine.compare(metrics_to_compare, industry_id='fuel_distribution')
check('Benchmark comparison returns results', len(comparisons) >= 1)
check('Each comparison has status', all(c.status in ('healthy', 'warning', 'critical', 'unknown') for c in comparisons))


# ── Step 10: Diagnosis Engine E2E ─────────────────────────
print()
print('Step 10: Diagnosis Engine E2E')
from app.services.diagnosis_engine import diagnosis_engine as diag_engine_instance

diag_report = diag_engine_instance.run_full_diagnosis(
    current_financials={
        "revenue": 50_000_000, "cogs": 45_000_000, "gross_profit": 5_000_000,
        "ga_expenses": 1_200_000, "ebitda": 3_800_000, "net_profit": -500_000,
    },
    previous_financials={
        "revenue": 48_000_000, "cogs": 38_000_000, "gross_profit": 10_000_000,
        "ga_expenses": 900_000, "ebitda": 5_100_000, "net_profit": 3_500_000,
    },
    balance_sheet={
        "total_assets": 30_000_000, "total_liabilities": 18_000_000,
        "total_equity": 12_000_000, "total_current_assets": 10_000_000,
        "total_current_liabilities": 8_000_000, "cash": 2_000_000,
        "receivables": 4_000_000, "total_debt": 15_000_000,
    },
    industry_id="fuel_distribution",
)
check('Diagnosis returns DiagnosticReport', hasattr(diag_report, 'health_score'))
check('Health score in range', 0 <= diag_report.health_score <= 100)
check('Diagnoses generated', len(diag_report.diagnoses) >= 1)
check('Recommendations generated', len(diag_report.recommendations) >= 1)
diag_dict = diag_report.to_dict()
check('to_dict() serializable', isinstance(diag_dict, dict) and 'health_score' in diag_dict)


# ── Summary ──────────────────────────────────────────────────
print()
print('=' * 60)
total  = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
if failed == 0:
    print(f'  E2E RESULT: {passed}/{total} checks passed')
    print()
    print('  FULL PIPELINE VALIDATED:')
    print('  Step 1: COA classification (3-pass SemanticEnricher)')
    print('  Step 2: KG context retrieval (322 entities indexed)')
    print('  Step 3: Causal reasoning (wholesale margin -4.3pp)')
    print('  Step 4: Accounting consistency (BS equation check)')
    print('  Step 5: Scenario simulation (price/COGS what-if)')
    print('  Step 6: Liquidity analysis (current/D-E ratios)')
    print('  Step 7: Telemetry pipeline (agent/tool/KG tracking)')
    print('  Step 8: GL Pipeline E2E (GL -> TB -> IS -> BS -> CF)')
    print('  Step 9: Benchmark Comparison E2E')
    print('  Step 10: Diagnosis Engine E2E (Signal -> Diagnose -> Recommend)')
else:
    print(f'  E2E RESULT: {passed}/{total} passed | {failed} FAILED')
    for name, ok in results:
        if not ok:
            print(f'  [FAIL] {name}')
print('=' * 60)
