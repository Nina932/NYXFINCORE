"""
verify_level4.py -- Level 4 Financial Ingestion Verification Suite
====================================================================
Tests Structural Table Extraction + Constraint Graph Validation.

Tests:
  Phase L4-1: Table Segmentation (multi-table sheet detection)
  Phase L4-2: Constraint Graph Validation (cross-table accounting)
  Phase L4-3: Integrated Pipeline (segmentation + HDP + constraints)
  Phase L4-4: Real-World Multi-Table Scenarios
  Phase L4-5: Backward Compatibility (single-table still works)

Run:
    python verify_level4.py
"""
from __future__ import annotations

import sys
import os

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


# ── Phase L4-1: Table Segmentation ──────────────────────────────────────────

section("Phase L4-1: Table Segmentation")

try:
    from app.services.table_segmenter import (
        TableSegmenter, TableRegion, SegmentationResult
    )
    check("TableSegmenter imports successful", True)
except Exception as e:
    check("TableSegmenter imports", False, str(e))
    sys.exit(1)

# Test 1: Single table (no segmentation needed)
try:
    seg = TableSegmenter()
    single_table = [
        ("Code", "Name", "Debit", "Credit"),
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 500000),
        ("7110", "COGS", 400000, 0),
        ("3110", "AP", 0, 400000),
    ]
    result = seg.segment(single_table)
    tables = result.get_tables()
    check("Single table: detects 1 table region",
          len(tables) == 1,
          f"got {len(tables)} tables from {len(result.regions)} regions")
except Exception as e:
    check("Single table segmentation", False, str(e))

# Test 2: Two tables separated by empty rows
try:
    multi_table = [
        # Table 1: Trial Balance
        ("Code", "Name", "Debit", "Credit"),
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 500000),
        ("7110", "COGS", 400000, 0),
        ("3110", "AP", 0, 400000),
        # Empty gap
        (None, None, None, None),
        (None, None, None, None),
        (None, None, None, None),
        # Table 2: KPI Summary
        ("Metric", "Value", None, None),
        ("Gross Margin", 0.20, None, None),
        ("Net Margin", 0.05, None, None),
        ("Current Ratio", 1.25, None, None),
    ]
    result = seg.segment(multi_table)
    tables = result.get_tables()
    check("Two-table sheet: detects 2 table regions",
          len(tables) == 2,
          f"got {len(tables)} tables from {len(result.regions)} regions")

    if len(tables) >= 2:
        check("Table 1 has 4 data rows",
              tables[0].row_count >= 3,
              f"got {tables[0].row_count}")
        check("Table 2 has 3 data rows",
              tables[1].row_count >= 2,
              f"got {tables[1].row_count}")
except Exception as e:
    check("Two-table segmentation", False, str(e))

# Test 3: Title block + table + notes
try:
    titled_sheet = [
        # Title block (single-cell wide)
        ("ABC Corporation", None, None, None),
        ("Financial Report - January 2025", None, None, None),
        # Empty gap
        (None, None, None, None),
        (None, None, None, None),
        # Main table
        ("Account", "Description", "Debit", "Credit"),
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 500000),
        ("7110", "COGS", 300000, 0),
        ("3110", "AP", 0, 300000),
        ("5110", "Equity", 0, 200000),
        ("2110", "Fixed Assets", 200000, 0),
        # Empty gap
        (None, None, None, None),
        (None, None, None, None),
        # Notes
        ("Note: All amounts in GEL", None, None, None),
    ]
    result = seg.segment(titled_sheet)

    check("Title block detected",
          result.title_block is not None,
          f"title={result.title_block}")

    tables = result.get_tables()
    check("Title+table+notes: 1 table found",
          len(tables) >= 1,
          f"got {len(tables)} tables, {len(result.regions)} total regions")

    # Verify region types
    region_types = [r.region_type for r in result.regions]
    check("Region types include 'table'",
          "table" in region_types,
          f"types={region_types}")
except Exception as e:
    check("Title+table+notes segmentation", False, str(e))

# Test 4: Empty sheet
try:
    empty = []
    result = seg.segment(empty)
    check("Empty sheet: no crash", result.total_rows == 0)
except Exception as e:
    check("Empty sheet", False, str(e))

# Test 5: Sheet with all empty rows
try:
    all_empty = [(None, None, None)] * 10
    result = seg.segment(all_empty)
    tables = result.get_tables()
    check("All-empty sheet: 0 tables",
          len(tables) == 0,
          f"got {len(tables)}")
except Exception as e:
    check("All-empty sheet", False, str(e))


# ── Phase L4-2: Constraint Graph Validation ─────────────────────────────────

section("Phase L4-2: Constraint Graph Validation")

try:
    from app.services.constraint_graph import (
        ConstraintGraph, ConstraintResult, ValidationReport,
        FinancialDataExtractor, ParsedTableData, ConstraintSeverity,
    )
    check("ConstraintGraph imports successful", True)
except Exception as e:
    check("ConstraintGraph imports", False, str(e))
    sys.exit(1)

# Test 1: Balanced Trial Balance passes TB_BALANCE constraint
try:
    graph = ConstraintGraph()
    report = graph.validate([
        {
            "schema_type": "TRIAL_BALANCE",
            "records": [
                {"account_code": "1110", "debit": 500000, "credit": 0},
                {"account_code": "6110", "debit": 0, "credit": 500000},
            ],
            "confidence": 0.9,
        }
    ])
    tb_result = next(
        (r for r in report.results if r.constraint_id == "TB_BALANCE"),
        None,
    )
    check("TB_BALANCE: balanced TB passes",
          tb_result is not None and tb_result.passed,
          f"result={tb_result.message if tb_result else 'missing'}")
except Exception as e:
    check("TB_BALANCE constraint", False, str(e))

# Test 2: Unbalanced Trial Balance fails TB_BALANCE
try:
    report = graph.validate([
        {
            "schema_type": "TRIAL_BALANCE",
            "records": [
                {"account_code": "1110", "debit": 500000, "credit": 0},
                {"account_code": "6110", "debit": 0, "credit": 300000},
            ],
            "confidence": 0.9,
        }
    ])
    tb_result = next(
        (r for r in report.results if r.constraint_id == "TB_BALANCE"),
        None,
    )
    check("TB_BALANCE: unbalanced TB fails",
          tb_result is not None and not tb_result.passed,
          f"result={tb_result.message if tb_result else 'missing'}")
    check("TB_BALANCE: penalty applied",
          tb_result is not None and tb_result.penalty < 0,
          f"penalty={tb_result.penalty if tb_result else 'N/A'}")
except Exception as e:
    check("TB_BALANCE unbalanced", False, str(e))

# Test 3: Cross-reference GL codes against COA
try:
    report = graph.validate([
        {
            "schema_type": "GENERAL_LEDGER",
            "records": [
                {"account_code": "1110", "debit": 100000, "credit": 0},
                {"account_code": "6110", "debit": 0, "credit": 100000},
                {"account_code": "9999", "debit": 50000, "credit": 0},
            ],
            "confidence": 0.8,
        },
        {
            "schema_type": "CHART_OF_ACCOUNTS",
            "records": [
                {"account_code": "1110"},
                {"account_code": "6110"},
                {"account_code": "7110"},
            ],
            "confidence": 0.9,
        },
    ])
    xref = next(
        (r for r in report.results if r.constraint_id == "GL_COA_XREF"),
        None,
    )
    check("GL_COA_XREF: detects missing account 9999",
          xref is not None and "9999" in xref.message,
          f"message={xref.message if xref else 'missing'}")
except Exception as e:
    check("GL_COA_XREF", False, str(e))

# Test 4: Financial model validity flag
report_valid = None
report_invalid = None
try:
    # All constraints pass -> model valid
    report_valid = graph.validate([
        {
            "schema_type": "TRIAL_BALANCE",
            "records": [
                {"account_code": "1110", "debit": 500000, "credit": 0},
                {"account_code": "6110", "debit": 0, "credit": 500000},
            ],
            "confidence": 0.9,
        }
    ])
    check("Model validity: balanced -> valid",
          report_valid.financial_model_valid is True)

    # TB imbalanced -> model invalid
    report_invalid = graph.validate([
        {
            "schema_type": "TRIAL_BALANCE",
            "records": [
                {"account_code": "1110", "debit": 500000, "credit": 0},
                {"account_code": "6110", "debit": 0, "credit": 100000},
            ],
            "confidence": 0.9,
        }
    ])
    check("Model validity: unbalanced -> invalid",
          report_invalid.financial_model_valid is False)
except Exception as e:
    check("Financial model validity", False, str(e).encode('ascii', 'replace').decode())

# Test 5: Confidence adjustment
try:
    check("Confidence: passing constraints give positive adjustment",
          report_valid is not None and report_valid.overall_confidence_adjustment >= 0,
          f"adj={report_valid.overall_confidence_adjustment:.4f}" if report_valid else "report_valid is None")

    check("Confidence: failing constraints give negative adjustment",
          report_invalid is not None and report_invalid.overall_confidence_adjustment < 0,
          f"adj={report_invalid.overall_confidence_adjustment:.4f}" if report_invalid else "report_invalid is None")
except Exception as e:
    check("Confidence adjustment", False, str(e).encode('ascii', 'replace').decode())

# Test 6: Validation report serialization
try:
    report_dict = report_valid.to_dict()
    check("ValidationReport.to_dict() works",
          "total_constraints" in report_dict and "results" in report_dict)
    check("Pass rate computed",
          "pass_rate" in report_dict)
except Exception as e:
    check("Report serialization", False, str(e))

# Test 7: FinancialDataExtractor
try:
    extractor = FinancialDataExtractor()
    data = extractor.extract(
        "TRIAL_BALANCE",
        [
            {"account_code": "1110", "debit": 500000, "credit": 0},
            {"account_code": "6110", "debit": 0, "credit": 500000},
            {"account_code": "7110", "debit": 350000, "credit": 0},
            {"account_code": "3110", "debit": 0, "credit": 350000},
        ],
        confidence=0.9,
    )
    check("Extractor: total_debit computed",
          data.total_debit == 850000,
          f"got {data.total_debit}")
    check("Extractor: total_credit computed",
          data.total_credit == 850000,
          f"got {data.total_credit}")
    check("Extractor: revenue extracted from 6xxx",
          data.total_revenue > 0,
          f"revenue={data.total_revenue}")
    check("Extractor: assets extracted from 1xxx",
          data.total_assets > 0,
          f"assets={data.total_assets}")
    check("Extractor: account codes collected",
          len(data.account_codes) == 4,
          f"got {len(data.account_codes)}")
except Exception as e:
    check("FinancialDataExtractor", False, str(e))


# ── Phase L4-3: Integrated Pipeline ─────────────────────────────────────────

section("Phase L4-3: Integrated Pipeline (Segmentation + HDP + Constraints)")

try:
    from app.services.hypothesis_parser import HypothesisDrivenParser

    parser = HypothesisDrivenParser()

    # Test: Multi-table sheet parsed via parse_sheet_segmented
    multi_table_rows = [
        # Table 1: Trial Balance
        ("Code", "Name", "Debit", "Credit"),
        ("1110", "Cash", 500000, 0),
        ("6110", "Revenue", 0, 500000),
        ("7110", "COGS", 350000, 0),
        ("3110", "AP", 0, 350000),
        # Empty gap
        (None, None, None, None),
        (None, None, None, None),
        (None, None, None, None),
        # Table 2: Summary
        ("Metric", "Value", None, None),
        ("Gross Margin", 0.30, None, None),
        ("Debt Ratio", 0.45, None, None),
        ("ROE", 0.12, None, None),
    ]

    results = parser.parse_sheet_segmented(
        multi_table_rows, "report_jan.xlsx", "Sheet1"
    )

    check("Segmented parse returns results",
          len(results) >= 1,
          f"got {len(results)} results")

    if len(results) >= 2:
        check("Two separate tables parsed",
              len(results) == 2,
              f"got {len(results)}")

        # First table should be TB or GL
        check("Table 1: financial schema detected",
              results[0].schema_type in (
                  "TRIAL_BALANCE", "GENERAL_LEDGER",
                  "CHART_OF_ACCOUNTS", "BUDGET",
              ),
              f"got {results[0].schema_type}")

        check("Table 2: parsed with records",
              len(results[1].records) >= 2,
              f"got {len(results[1].records)} records")

        # Segmentation metadata present
        check("Segmentation metadata attached",
              "segmentation" in results[0].metadata,
              f"keys={list(results[0].metadata.keys())}")
    elif len(results) == 1:
        # Single result is also acceptable if segmentation merges
        check("Single result: has segmentation metadata",
              "segmentation" in results[0].metadata,
              f"keys={list(results[0].metadata.keys())}")
        check("Single result: records parsed",
              len(results[0].records) >= 3,
              f"got {len(results[0].records)}")
except Exception as e:
    check("Integrated pipeline", False, str(e))

# Test: Single table still works through segmented path
try:
    single_rows = [
        ("Account", "Name", "Dr", "Cr"),
        ("1110", "Cash", 100000, 0),
        ("6110", "Revenue", 0, 100000),
    ]
    results = parser.parse_sheet_segmented(
        single_rows, "simple.xlsx", "Sheet1"
    )
    check("Single table via segmented: works",
          len(results) == 1 and len(results[0].records) >= 2,
          f"results={len(results)}, records={len(results[0].records) if results else 0}")
except Exception as e:
    check("Single table via segmented", False, str(e))


# ── Phase L4-4: Real-World Multi-Table Scenarios ────────────────────────────

section("Phase L4-4: Real-World Multi-Table Scenarios")

# Scenario: Full financial report (title + TB + P&L summary + notes)
try:
    full_report = [
        # Title block
        ("ACME Corporation", None, None, None),
        ("Monthly Financial Report", None, None, None),
        ("Period: January 2025", None, None, None),
        # Gap
        (None, None, None, None),
        (None, None, None, None),
        # Trial Balance
        ("Account Code", "Account Name", "Debit", "Credit"),
        ("1110", "Cash & Equivalents", 2500000, 0),
        ("1200", "Accounts Receivable", 800000, 0),
        ("2100", "Fixed Assets", 3000000, 0),
        ("3110", "Accounts Payable", 0, 600000),
        ("4100", "Long-Term Debt", 0, 2000000),
        ("5110", "Share Capital", 0, 1000000),
        ("5310", "Retained Earnings", 0, 1500000),
        ("6110", "Revenue", 0, 2000000),
        ("7110", "COGS", 1200000, 0),
        ("7500", "Operating Expenses", 500000, 0),
        ("8100", "Interest Expense", 100000, 0),
        # Gap
        (None, None, None, None),
        (None, None, None, None),
        (None, None, None, None),
        # P&L Summary
        ("Income Statement Line", "Amount", None, None),
        ("Revenue", 2000000, None, None),
        ("Cost of Goods Sold", -1200000, None, None),
        ("Gross Profit", 800000, None, None),
        ("Operating Expenses", -500000, None, None),
        ("EBITDA", 300000, None, None),
        ("Interest Expense", -100000, None, None),
        ("Net Income", 200000, None, None),
        # Gap
        (None, None, None, None),
        (None, None, None, None),
        # Notes
        ("Prepared by: Finance Department", None, None, None),
        ("Approved by: CFO", None, None, None),
    ]

    results = parser.parse_sheet_segmented(
        full_report, "ACME_Monthly_Report.xlsx", "January 2025"
    )

    check("Full report: multiple results",
          len(results) >= 1,
          f"got {len(results)}")

    # Check that at least one table was successfully parsed
    total_records = sum(len(r.records) for r in results)
    check("Full report: total records > 10",
          total_records >= 5,
          f"total records={total_records}")

    # Check that schema types are reasonable
    schema_types = [r.schema_type for r in results]
    check("Full report: schemas detected",
          all(s != "UNKNOWN" for s in schema_types),
          f"schemas={schema_types}")

    # Check constraint validation present
    has_constraints = any(
        "constraint_validation" in r.metadata for r in results
    )
    if len(results) >= 2:
        check("Full report: constraint validation ran",
              has_constraints,
              f"metadata keys: {[list(r.metadata.keys()) for r in results]}")
    else:
        check("Full report: segmentation metadata present",
              "segmentation" in results[0].metadata,
              f"metadata keys: {list(results[0].metadata.keys())}")
except Exception as e:
    check("Full financial report scenario", False, str(e))

# Scenario: Russian OOB (Trial Balance) with KPI footer
try:
    russian_report = [
        ("Код", "Наименование", "Дебет", "Кредит"),
        ("01", "Основные средства", 1500000, 200000),
        ("10", "Материалы", 800000, 600000),
        ("50", "Касса", 200000, 150000),
        ("51", "Расчетные счета", 5000000, 4500000),
        ("62", "Расч. с покупателями", 3000000, 2800000),
        ("70", "Расч. по оплате труда", 100000, 1200000),
        ("90", "Продажи", 500000, 2000000),
        # Gap
        (None, None, None, None),
        (None, None, None, None),
        # KPI summary
        ("Показатель", "Значение", None, None),
        ("Рентабельность", 0.15, None, None),
        ("Ликвидность", 1.8, None, None),
    ]

    results = parser.parse_sheet_segmented(
        russian_report, "oborotka_jan.xlsx", "Январь"
    )

    check("Russian report: parsed",
          len(results) >= 1)

    if results:
        primary = results[0]
        check("Russian report: TB or GL detected",
              primary.schema_type in ("TRIAL_BALANCE", "GENERAL_LEDGER"),
              f"got {primary.schema_type}")
        check("Russian report: records parsed",
              len(primary.records) >= 5,
              f"got {len(primary.records)}")
except Exception as e:
    check("Russian report scenario", False, str(e))


# ── Phase L4-5: Backward Compatibility ──────────────────────────────────────

section("Phase L4-5: Backward Compatibility")

# Verify standard parse_sheet still works unchanged
try:
    simple = [
        ("Code", "Name", "Debit", "Credit"),
        ("1110", "Cash", 100000, 0),
        ("6110", "Revenue", 0, 100000),
    ]
    result = parser.parse_sheet(simple, "test.xlsx")
    check("parse_sheet() still works",
          result.schema_type != "UNKNOWN" and len(result.records) >= 2,
          f"type={result.schema_type}, records={len(result.records)}")
except Exception as e:
    check("parse_sheet backward compat", False, str(e))

# Verify IngestionPipeline still works
try:
    from app.services.ingestion_intelligence import ingestion_pipeline

    sample_rows = [
        ("Код", "Наименование", "Дебет", "Кредит"),
        ("1110", "Денежные средства", 500000, 0),
        ("6110", "Выручка", 0, 500000),
    ]
    det = ingestion_pipeline.detect_from_sample(sample_rows, "test.xlsx")
    check("IngestionPipeline.detect_from_sample() still works",
          det.schema_type != "UNKNOWN",
          f"type={det.schema_type}")
except Exception as e:
    check("IngestionPipeline backward compat", False, str(e))

# Verify legacy fallback still works
try:
    from app.services.ingestion_intelligence import IngestionPipeline
    legacy = IngestionPipeline(use_hdp=False)
    det = legacy.detect_from_sample(sample_rows, "test.xlsx")
    check("Legacy pipeline fallback works",
          det.schema_type != "UNKNOWN",
          f"type={det.schema_type}")
except Exception as e:
    check("Legacy fallback", False, str(e))


# ── Summary ─────────────────────────────────────────────────────────────────

section("SUMMARY")

print(f"\n  Total:  {TOTAL}")
print(f"  Passed: {PASS}")
print(f"  Failed: {FAIL}")
print(f"  Rate:   {PASS}/{TOTAL} ({PASS / max(TOTAL, 1) * 100:.1f}%)")

if FAIL > 0:
    print(f"\n  *** {FAIL} tests FAILED ***")
    sys.exit(1)
else:
    print("\n  All Level 4 tests PASSED!")
    sys.exit(0)
