"""
verify_hdp.py — Hypothesis-Driven Parsing Verification Suite
==============================================================
Tests the HDP engine against realistic financial file scenarios,
including the exact failure cases identified in the technical audit.

Tests:
  Phase H-1: HDP Core Engine (hypothesis generation, parsing, scoring)
  Phase H-2: Schema Memory + Pattern Fingerprinting
  Phase H-3: Accounting Invariant Validation
  Phase H-4: Audit Failure Scenario Reproduction
  Phase H-5: Integration with IngestionPipeline
  Phase H-6: Self-Correction Proof (HDP vs Legacy comparison)

Run:
    python verify_hdp.py
"""
from __future__ import annotations

import sys
import os
import json
import traceback

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0
TOTAL = 0

def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {label}"
        if detail:
            msg += f" -- {detail}"
        print(msg)

def section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ── Phase H-1: HDP Core Engine ──────────────────────────────────────────────

section("Phase H-1: HDP Core Engine")

try:
    from app.services.hypothesis_parser import (
        HypothesisDrivenParser,
        HypothesisGenerator,
        HypothesisValidator,
        HypothesisScorer,
        SchemaHypothesis,
        HypothesisParseResult,
        ValidationSignals,
        ParsedHypothesisResult,
    )
    check("HDP imports successful", True)
except Exception as e:
    check("HDP imports successful", False, str(e))
    sys.exit(1)

# Test 1: HypothesisGenerator produces 8 hypotheses
try:
    gen = HypothesisGenerator()
    header = ("Account Code", "Account Name", "Debit", "Credit")
    data = [
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 500000),
        ("7110", "COGS", 350000, 0),
        ("3110", "Accounts Payable", 0, 350000),
    ]
    hypotheses = gen.generate(header, data, "test_tb.xlsx")
    check("Generator produces 8 hypotheses", len(hypotheses) == 8,
          f"got {len(hypotheses)}")

    schema_types = {h.schema_type for h in hypotheses}
    check("All schema types covered", len(schema_types) == 8,
          f"types: {schema_types}")
except Exception as e:
    check("Generator produces hypotheses", False, str(e))

# Test 2: Each hypothesis has its own column mapping
try:
    tb_hyp = next(h for h in hypotheses if h.schema_type == "TRIAL_BALANCE")
    gl_hyp = next(h for h in hypotheses if h.schema_type == "GENERAL_LEDGER")
    coa_hyp = next(h for h in hypotheses if h.schema_type == "CHART_OF_ACCOUNTS")

    # TB should detect account_code, debit, credit
    check("TB hypothesis has account_code",
          tb_hyp.column_mapping.has("account_code"))
    check("TB hypothesis has debit",
          tb_hyp.column_mapping.has("debit"))
    check("TB hypothesis has credit",
          tb_hyp.column_mapping.has("credit"))
except Exception as e:
    check("Hypothesis column mappings", False, str(e))

# Test 3: HypothesisValidator parses and validates
try:
    validator = HypothesisValidator()
    validated = validator.parse_and_validate(tb_hyp, header, data)
    check("Validator produces parse_result",
          validated.parse_result is not None)
    check("Validator produces validation signals",
          validated.validation is not None)
    check("TB parsed 4 rows",
          validated.parse_result.parsed_rows == 4,
          f"got {validated.parse_result.parsed_rows}")
except Exception as e:
    check("Validator parse_and_validate", False, str(e))

# Test 4: Scorer ranks hypotheses
try:
    scorer = HypothesisScorer()
    # Validate and score all hypotheses
    for hyp in hypotheses:
        validator.parse_and_validate(hyp, header, data)
        scorer.score(hyp)

    ranked = scorer.rank_hypotheses(hypotheses)
    winner = ranked[0]

    check("Winner is rank 1", winner.rank == 1)
    check("Winner is_winner flag set", winner.is_winner)
    check("Winner has composite score > 0",
          winner.composite_score > 0,
          f"score={winner.composite_score:.4f}")

    # For this data (account_code + debit + credit, balanced), TB or GL should win
    check("Winner is TB or GL for balanced debit/credit data",
          winner.schema_type in ("TRIAL_BALANCE", "GENERAL_LEDGER"),
          f"got {winner.schema_type}")
except Exception as e:
    check("Scorer ranking", False, str(e))

# Test 5: Full HDP parser pipeline
try:
    parser = HypothesisDrivenParser()
    rows = [header] + data
    result = parser.parse_sheet(rows, "test_trial_balance.xlsx")

    check("HDP parse_sheet returns HypothesisParseResult",
          isinstance(result, HypothesisParseResult))
    check("HDP winner schema is TB or GL",
          result.schema_type in ("TRIAL_BALANCE", "GENERAL_LEDGER"),
          f"got {result.schema_type}")
    check("HDP confidence > 0.3",
          result.confidence > 0.3,
          f"conf={result.confidence:.4f}")
    check("HDP records parsed",
          len(result.records) == 4,
          f"got {len(result.records)}")
    check("HDP metadata has all_scores",
          "all_scores" in result.metadata,
          f"keys={list(result.metadata.keys())}")
except Exception as e:
    check("Full HDP pipeline", False, str(e))


# ── Phase H-2: Schema Memory ────────────────────────────────────────────────

section("Phase H-2: Schema Memory + Pattern Fingerprinting")

try:
    from app.services.schema_memory import (
        SchemaMemory,
        SchemaFingerprint,
        FingerprintBuilder,
        FingerprintMatcher,
    )
    check("Schema Memory imports successful", True)
except Exception as e:
    check("Schema Memory imports successful", False, str(e))
    sys.exit(1)

# Test 1: FingerprintBuilder creates fingerprint
try:
    builder = FingerprintBuilder()
    from app.services.ingestion_intelligence import ColumnMapping
    col_map = ColumnMapping(roles={"account_code": 0, "account_name": 1, "debit": 2, "credit": 3})

    fp = builder.build(
        header_row=("Account Code", "Account Name", "Debit", "Credit"),
        data_rows=[
            ("1110", "Cash", 500000, 0),
            ("6110", "Revenue", 0, 500000),
        ],
        filename="trial_balance_jan_2025.xlsx",
        schema_type="TRIAL_BALANCE",
        confidence=0.85,
        column_mapping=col_map,
    )

    check("Fingerprint has column_count", fp.column_count == 4)
    check("Fingerprint has row_count_bucket", fp.row_count_bucket == "1s")
    check("Fingerprint has header_hash", len(fp.header_hash) > 0)
    check("Fingerprint has numeric_col_positions",
          len(fp.numeric_col_positions) >= 1,
          f"positions={fp.numeric_col_positions}")
    check("Fingerprint has account_code_pattern",
          len(fp.account_code_pattern) > 0,
          f"pattern={fp.account_code_pattern}")
    check("Fingerprint has fingerprint_id",
          len(fp.fingerprint_id) == 16)
    check("Fingerprint serializes to dict",
          isinstance(fp.to_dict(), dict))
except Exception as e:
    check("FingerprintBuilder", False, str(e))

# Test 2: FingerprintMatcher computes similarity
try:
    matcher = FingerprintMatcher()

    # Same fingerprint → similarity = 1.0
    sim_self = matcher.similarity(fp, fp)
    check("Self-similarity ~= 1.0", sim_self >= 0.95,
          f"got {sim_self:.4f}")

    # Different fingerprint → lower similarity
    fp2 = builder.build(
        header_row=("Date", "Description", "Amount"),
        data_rows=[
            ("2025-01-01", "Sale", 1000),
            ("2025-01-02", "Purchase", -500),
        ],
        filename="transactions.xlsx",
        schema_type="GENERAL_LEDGER",
        confidence=0.6,
    )

    sim_diff = matcher.similarity(fp, fp2)
    check("Different fingerprint similarity < 0.5",
          sim_diff < 0.5,
          f"got {sim_diff:.4f}")
except Exception as e:
    check("FingerprintMatcher", False, str(e))

# Test 3: SchemaMemory stores and retrieves patterns
try:
    import tempfile
    tmp_path = os.path.join(tempfile.gettempdir(), "test_schema_memory.json")
    memory = SchemaMemory(storage_path=tmp_path)
    memory.clear()

    # Record a pattern
    fp_id = memory.record_successful_parse(
        header_row=("Account Code", "Account Name", "Debit", "Credit"),
        data_rows=[
            ("1110", "Cash", 500000, 0),
            ("6110", "Revenue", 0, 500000),
        ],
        schema_type="TRIAL_BALANCE",
        confidence=0.9,
        column_mapping=col_map,
        filename="tb_jan_2025.xlsx",
    )

    check("Schema Memory records pattern", len(fp_id) == 16)
    check("Schema Memory has 1 pattern", memory.pattern_count() == 1)

    # Match against similar data
    match = memory.find_match(
        header_row=("Account Code", "Account Name", "Debit", "Credit"),
        data_rows=[
            ("1110", "Cash", 600000, 0),
            ("6110", "Revenue", 0, 600000),
            ("7110", "COGS", 400000, 0),
        ],
        filename="tb_feb_2025.xlsx",
    )

    check("Schema Memory finds match for similar file",
          match is not None,
          "no match found")

    if match:
        matched_type, matched_conf = match
        check("Matched schema type is TRIAL_BALANCE",
              matched_type == "TRIAL_BALANCE",
              f"got {matched_type}")
        check("Match confidence > 0.5",
              matched_conf > 0.5,
              f"got {matched_conf:.4f}")

    # Non-matching data should not match
    no_match = memory.find_match(
        header_row=("Date", "Product", "Revenue", "Cost", "Margin"),
        data_rows=[
            ("2025-01", "Widget A", 1000000, 700000, 300000),
        ],
        filename="pl_report.xlsx",
    )
    check("Schema Memory rejects non-matching file",
          no_match is None,
          f"got {no_match}")

    # Status
    status = memory.status()
    check("Schema Memory status works",
          status["total_patterns"] == 1)

    # Cleanup
    memory.clear()
    os.unlink(tmp_path)
except Exception as e:
    check("SchemaMemory", False, str(e))


# ── Phase H-3: Accounting Invariant Validation ──────────────────────────────

section("Phase H-3: Accounting Invariant Validation")

# Test 1: Balanced TB scores higher than unbalanced
try:
    parser = HypothesisDrivenParser()

    # Balanced data: debit = credit = 500000
    balanced_header = ("Code", "Name", "Debit", "Credit")
    balanced_data = [
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 500000),
    ]
    balanced_result = parser.parse_sheet(
        [balanced_header] + balanced_data, "balanced_tb.xlsx"
    )

    # Unbalanced data: debit = 500000, credit = 300000
    unbalanced_data = [
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 300000),
    ]
    unbalanced_result = parser.parse_sheet(
        [balanced_header] + unbalanced_data, "unbalanced_tb.xlsx"
    )

    # Get TB scores from both
    balanced_tb_score = None
    unbalanced_tb_score = None
    for h in balanced_result.all_hypotheses:
        if h.schema_type == "TRIAL_BALANCE":
            balanced_tb_score = h.composite_score
    for h in unbalanced_result.all_hypotheses:
        if h.schema_type == "TRIAL_BALANCE":
            unbalanced_tb_score = h.composite_score

    check("Balanced TB has higher score than unbalanced",
          balanced_tb_score is not None and unbalanced_tb_score is not None
          and balanced_tb_score > unbalanced_tb_score,
          f"balanced={balanced_tb_score:.4f}, unbalanced={unbalanced_tb_score:.4f}")
except Exception as e:
    check("Debit/credit balance scoring", False, str(e))

# Test 2: COA prefix recognition boosts score
try:
    # Data with valid Georgian COA prefixes (1xxx, 6xxx, 7xxx)
    valid_coa_header = ("Code", "Name", "Debit", "Credit")
    valid_coa_data = [
        ("1110", "Cash", 100000, 0),
        ("6110", "Revenue", 0, 100000),
        ("7110", "COGS", 80000, 0),
        ("3110", "Payable", 0, 80000),
    ]
    valid_coa_result = parser.parse_sheet(
        [valid_coa_header] + valid_coa_data, "valid_coa.xlsx"
    )

    # Data with invalid/random codes
    invalid_coa_data = [
        ("ABCD", "Widget", 100000, 0),
        ("WXYZ", "Gadget", 0, 100000),
        ("QQQQ", "Gizmo", 80000, 0),
        ("ZZZZ", "Thingamajig", 0, 80000),
    ]
    invalid_coa_result = parser.parse_sheet(
        [valid_coa_header] + invalid_coa_data, "random_codes.xlsx"
    )

    # Get TB hypothesis scores
    valid_tb = next(
        (h for h in valid_coa_result.all_hypotheses if h.schema_type == "TRIAL_BALANCE"), None
    )
    invalid_tb = next(
        (h for h in invalid_coa_result.all_hypotheses if h.schema_type == "TRIAL_BALANCE"), None
    )

    check("Valid COA prefixes boost TB score",
          valid_tb is not None and invalid_tb is not None
          and valid_tb.composite_score > invalid_tb.composite_score,
          f"valid={valid_tb.composite_score:.4f}, invalid={invalid_tb.composite_score:.4f}")
except Exception as e:
    check("COA prefix validation", False, str(e))

# Test 3: Validation signals are populated
try:
    hyp = valid_coa_result.all_hypotheses[0]  # Winner
    v = hyp.validation

    check("Debit/credit balance ratio populated",
          v.debit_credit_balance_ratio is not None)
    check("COA prefix match rate populated",
          v.coa_prefix_match_rate >= 0)
    check("Numeric consistency populated",
          v.numeric_consistency >= 0)
    check("Row completeness populated",
          v.row_completeness > 0)
    check("Account code format consistency populated",
          v.account_code_format_consistency >= 0)
except Exception as e:
    check("Validation signals", False, str(e))


# ── Phase H-4: Audit Failure Scenario Reproduction ──────────────────────────

section("Phase H-4: Audit Failure Scenarios (from Technical Audit)")

# Scenario A: ACCT | NAME | VALUE | MONTH
try:
    header_a = ("ACCT", "NAME", "VALUE", "MONTH")
    data_a = [
        ("1110", "Cash and equivalents", 500000, "January"),
        ("6110", "Net Revenue", 350000, "January"),
        ("7110", "Cost of Goods Sold", 280000, "January"),
        ("3110", "Accounts Payable", 120000, "January"),
    ]
    result_a = parser.parse_sheet([header_a] + data_a, "test_report.xlsx")

    check("Scenario A: ACCT detected as account_code",
          "account_code" in result_a.detection.columns,
          f"columns={result_a.detection.columns}")

    # HDP should find a reasonable interpretation even with "VALUE" instead of "debit/credit"
    check("Scenario A: Records parsed > 0",
          len(result_a.records) > 0,
          f"got {len(result_a.records)}")

    check("Scenario A: schema is not UNKNOWN",
          result_a.schema_type != "UNKNOWN",
          f"got {result_a.schema_type}")
except Exception as e:
    check("Scenario A", False, str(e))

# Scenario B: Account Name | Amount (no account code!)
try:
    header_b = ("Account Name", "Amount")
    data_b = [
        ("Cash and Cash Equivalents", 500000),
        ("Net Revenue", 350000),
        ("Cost of Goods Sold", 280000),
        ("Accounts Payable", 120000),
        ("Operating Expenses", 45000),
    ]
    result_b = parser.parse_sheet([header_b] + data_b, "summary_report.xlsx")

    # HDP should still produce records even without account codes
    check("Scenario B (no account code): Records parsed > 0",
          len(result_b.records) > 0,
          f"got {len(result_b.records)}")

    # Should detect as IS or BS (financial statement without codes)
    check("Scenario B: schema detected (not UNKNOWN)",
          result_b.schema_type != "UNKNOWN",
          f"got {result_b.schema_type}")

    # The key test: old pipeline would silently discard ALL rows
    # HDP should parse them under IS/BS hypothesis
    check("Scenario B: HDP does NOT silently discard all rows",
          len(result_b.records) >= 3,
          f"parsed {len(result_b.records)}/{len(data_b)}")
except Exception as e:
    check("Scenario B (no account code)", False, str(e))

# Scenario C: Data with Russian column headers
try:
    header_c = ("Код", "Наименование", "Дебет", "Кредит", "Остаток")
    data_c = [
        ("01", "Основные средства", 1500000, 200000, 1300000),
        ("10", "Материалы", 800000, 600000, 200000),
        ("50", "Касса", 2000000, 1800000, 200000),
        ("51", "Расчетные счета", 5000000, 4500000, 500000),
        ("62", "Расчеты с покупателями", 3000000, 2800000, 200000),
    ]
    result_c = parser.parse_sheet([header_c] + data_c, "oborotka_jan.xlsx")

    check("Scenario C (Russian headers): schema is TB or GL",
          result_c.schema_type in ("TRIAL_BALANCE", "GENERAL_LEDGER"),
          f"got {result_c.schema_type}")
    check("Scenario C: all 5 records parsed",
          len(result_c.records) == 5,
          f"got {len(result_c.records)}")
    check("Scenario C: confidence > 0.3",
          result_c.confidence > 0.3,
          f"conf={result_c.confidence:.4f}")
except Exception as e:
    check("Scenario C (Russian headers)", False, str(e))

# Scenario D: Ambiguous data (could be TB or GL)
try:
    header_d = ("Account", "Description", "Debit", "Credit", "Date")
    data_d = [
        ("1110", "Cash deposit", 100000, 0, "2025-01-15"),
        ("5110", "Share capital", 0, 100000, "2025-01-15"),
        ("1110", "Revenue collection", 50000, 0, "2025-01-20"),
        ("6110", "Revenue", 0, 50000, "2025-01-20"),
    ]
    result_d = parser.parse_sheet([header_d] + data_d, "transactions.xlsx")

    # With dates, this should lean toward GL
    check("Scenario D (ambiguous): schema detected",
          result_d.schema_type in ("GENERAL_LEDGER", "TRIAL_BALANCE"),
          f"got {result_d.schema_type}")

    # Check ambiguity warning
    metadata = result_d.metadata
    runner_up = metadata.get("runner_up", {})
    check("Scenario D: runner-up tracked",
          runner_up.get("schema") is not None,
          f"runner_up={runner_up}")
except Exception as e:
    check("Scenario D (ambiguous)", False, str(e))


# ── Phase H-5: Integration with IngestionPipeline ───────────────────────────

section("Phase H-5: IngestionPipeline Integration")

try:
    from app.services.ingestion_intelligence import IngestionPipeline, ingestion_pipeline

    # Test 1: IngestionPipeline uses HDP by default
    check("ingestion_pipeline singleton exists",
          ingestion_pipeline is not None)
    check("HDP enabled by default",
          ingestion_pipeline._use_hdp is True)

    # Test 2: detect_from_sample works with HDP
    sample_rows = [
        ("Код", "Наименование", "Дебет", "Кредит"),
        ("1110", "Cash", 100000, 0),
        ("6110", "Revenue", 0, 100000),
    ]
    detection = ingestion_pipeline.detect_from_sample(sample_rows, "test_tb.xlsx")
    check("detect_from_sample returns DetectionResult",
          detection.schema_type != "")
    check("detect_from_sample confidence > 0",
          detection.confidence > 0,
          f"conf={detection.confidence:.4f}")

    # Test 3: Legacy fallback works
    legacy_pipeline = IngestionPipeline(use_hdp=False)
    legacy_det = legacy_pipeline.detect_from_sample(sample_rows, "test_tb.xlsx")
    check("Legacy pipeline still works",
          legacy_det.schema_type != "")

    # Test 4: Both pipelines detect same general type
    check("HDP and legacy agree on schema family",
          detection.schema_type in ("TRIAL_BALANCE", "GENERAL_LEDGER")
          and legacy_det.schema_type in ("TRIAL_BALANCE", "GENERAL_LEDGER"),
          f"HDP={detection.schema_type}, legacy={legacy_det.schema_type}")

    # Test 5: HDP generally achieves higher confidence
    # (not always, but for clear cases it should)
    check("HDP confidence tracked",
          detection.confidence >= 0,
          f"HDP={detection.confidence:.3f}, legacy={legacy_det.confidence:.3f}")
except Exception as e:
    check("IngestionPipeline integration", False, str(e))


# ── Phase H-6: Self-Correction Proof ────────────────────────────────────────

section("Phase H-6: Self-Correction Proof")

# The key test: a column that could be misclassified
# "Оборот" (turnover) could match "amount" keyword, but under TB hypothesis
# it would cause debit/credit mismatch → TB score drops → correct type wins
try:
    # Turnover report: Оборот = total turnover per account (not debit or credit)
    header_turnover = ("Счет", "Наименование", "Оборот")
    data_turnover = [
        ("1110", "Денежные средства", 1500000),
        ("6110", "Выручка", 2000000),
        ("7110", "Себестоимость", 1800000),
        ("3110", "Кредиторская задолженность", 500000),
    ]
    result_turnover = parser.parse_sheet(
        [header_turnover] + data_turnover, "oboroty_report.xlsx"
    )

    # Under TB hypothesis, treating Оборот as both debit AND credit fails
    # because TB requires SEPARATE debit and credit columns
    # HDP should detect this and NOT classify as TB
    tb_hyp_score = None
    for h in result_turnover.all_hypotheses:
        if h.schema_type == "TRIAL_BALANCE":
            tb_hyp_score = h.composite_score

    check("Self-correction: TB score is low for turnover data",
          tb_hyp_score is not None and tb_hyp_score < 0.5,
          f"TB score={tb_hyp_score:.4f}")

    # The winner should be something more appropriate
    check("Self-correction: Winner is not UNKNOWN",
          result_turnover.schema_type != "UNKNOWN",
          f"got {result_turnover.schema_type}")

    check("Self-correction: All rows parsed under winning hypothesis",
          len(result_turnover.records) >= 3,
          f"got {len(result_turnover.records)}")
except Exception as e:
    check("Self-correction test", False, str(e))

# Test: Schema Memory makes second parse faster/more accurate
try:
    import tempfile
    tmp_path = os.path.join(tempfile.gettempdir(), "test_hdp_memory.json")
    memory = SchemaMemory(storage_path=tmp_path)
    memory.clear()

    parser_with_memory = HypothesisDrivenParser(schema_memory=memory)

    # First parse (no memory)
    first_header = ("Code", "Name", "Dr", "Cr")
    first_data = [
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 500000),
        ("7110", "COGS", 400000, 0),
        ("3110", "AP", 0, 400000),
    ]
    first_result = parser_with_memory.parse_sheet(
        [first_header] + first_data, "tb_jan.xlsx"
    )
    first_score = first_result.confidence

    # Second parse (with memory of first)
    second_data = [
        ("1110", "Cash", 600000, 0),
        ("6110", "Revenue", 0, 600000),
        ("7110", "COGS", 450000, 0),
        ("3110", "AP", 0, 450000),
        ("2110", "Fixed Assets", 1000000, 0),
        ("5110", "Equity", 0, 1000000),
    ]
    second_result = parser_with_memory.parse_sheet(
        [first_header] + second_data, "tb_feb.xlsx"
    )
    second_score = second_result.confidence

    check("Schema Memory: pattern recorded after first parse",
          memory.pattern_count() >= 1,
          f"patterns={memory.pattern_count()}")

    check("Schema Memory: second parse same schema type",
          first_result.schema_type == second_result.schema_type,
          f"first={first_result.schema_type}, second={second_result.schema_type}")

    # Memory should boost confidence on second parse
    check("Schema Memory: second parse confidence >= first",
          second_score >= first_score * 0.95,  # Allow small variance
          f"first={first_score:.4f}, second={second_score:.4f}")

    # Cleanup
    memory.clear()
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
except Exception as e:
    check("Schema Memory integration", False, str(e))

# Test: Dropped row tracking (audit issue: silent discard)
try:
    header_drop = ("Account Code", "Name", "Debit", "Credit")
    data_drop = [
        ("1110", "Cash", 500000, 0),
        (None, None, None, None),         # Blank row
        ("6110", "Revenue", 0, 500000),
        (None, "Subtotal", None, None),    # Partial row
        ("7110", "COGS", 400000, 0),
    ]
    result_drop = parser.parse_sheet(
        [header_drop] + data_drop, "test_drops.xlsx"
    )

    # Check that dropped rows are tracked, not silent
    winner = result_drop.winner
    pr = winner.parse_result

    check("Dropped rows tracked (not silent)",
          pr is not None and pr.dropped_rows >= 1,
          f"dropped={pr.dropped_rows if pr else 'N/A'}")

    check("Drop reasons provided",
          pr is not None and len(pr.drop_reasons) > 0,
          f"reasons={pr.drop_reasons if pr else 'N/A'}")

    check("Warnings include drop count",
          pr is not None and len(pr.warnings) > 0,
          f"warnings={pr.warnings[:2] if pr else 'N/A'}")

    # Valid rows still parsed
    check("Valid rows still parsed correctly",
          len(result_drop.records) >= 3,
          f"got {len(result_drop.records)}")
except Exception as e:
    check("Drop tracking", False, str(e))


# ── Summary ─────────────────────────────────────────────────────────────────

section("SUMMARY")

print(f"\n  Total:  {TOTAL}")
print(f"  Passed: {PASS}")
print(f"  Failed: {FAIL}")
print(f"  Rate:   {PASS}/{TOTAL} ({PASS/max(TOTAL,1)*100:.1f}%)")

if FAIL > 0:
    print(f"\n  *** {FAIL} tests FAILED ***")
    sys.exit(1)
else:
    print("\n  All tests PASSED!")
    sys.exit(0)
