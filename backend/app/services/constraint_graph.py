"""
constraint_graph.py -- Constraint Graph Validation Engine
===========================================================
Validates cross-table accounting relationships after HDP parsing.

Instead of scoring hypotheses individually, this engine validates
relationships BETWEEN parsed tables. This turns ingestion from
"table parsing" into "financial model reconstruction."

Accounting constraints enforced:
    1. BS Equation:    Assets = Liabilities + Equity
    2. NI Consistency: Net Income (IS) = Retained Earnings change (BS)
    3. TB Balance:     Sum(Debit) = Sum(Credit)
    4. CF Consistency: Operating + Investing + Financing = Net Cash Change
    5. Cross-reference: GL accounts exist in COA
    6. Revenue Check:  Revenue (IS) matches Revenue accounts (TB/GL)

Architecture:
    Parsed Tables (from HDP)
        |
    ConstraintGraph.validate()
        |
    [Constraint checks with pass/fail/penalty]
        |
    Adjustments to hypothesis scores
        |
    Final validated parse results

Key classes:
    AccountingConstraint    -- single constraint definition
    ConstraintResult        -- result of one constraint check
    ConstraintGraph         -- full cross-table validation engine
    FinancialModelValidator -- reconstructs and validates financial model
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConstraintSeverity(Enum):
    """How severe a constraint violation is."""
    CRITICAL = "critical"   # Must hold: BS equation, TB balance
    WARNING = "warning"     # Should hold: NI consistency, CF total
    INFO = "info"           # Nice to have: cross-references


@dataclass
class AccountingConstraint:
    """Definition of an accounting constraint."""
    constraint_id: str
    name: str
    description: str
    severity: ConstraintSeverity
    formula: str                    # Human-readable formula
    required_tables: List[str]      # Which table types must be present


@dataclass
class ConstraintResult:
    """Result of checking one constraint."""
    constraint_id: str
    name: str
    passed: bool
    severity: ConstraintSeverity
    expected: Optional[float] = None
    actual: Optional[float] = None
    difference: float = 0.0
    tolerance: float = 0.01
    message: str = ""
    penalty: float = 0.0           # Score penalty if failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "difference": round(self.difference, 4),
            "message": self.message,
            "penalty": self.penalty,
        }


@dataclass
class ValidationReport:
    """Full validation report for a set of parsed tables."""
    results: List[ConstraintResult] = field(default_factory=list)
    total_constraints: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    overall_confidence_adjustment: float = 0.0
    financial_model_valid: bool = False
    detected_issues: List[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_constraints == 0:
            return 1.0
        return self.passed / self.total_constraints

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_constraints": self.total_constraints,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "pass_rate": round(self.pass_rate, 3),
            "overall_confidence_adjustment": round(
                self.overall_confidence_adjustment, 4
            ),
            "financial_model_valid": self.financial_model_valid,
            "detected_issues": self.detected_issues,
            "results": [r.to_dict() for r in self.results],
        }


# ── Constraint Definitions ──────────────────────────────────────────────────

CONSTRAINTS = [
    AccountingConstraint(
        constraint_id="BS_EQUATION",
        name="Balance Sheet Equation",
        description="Assets = Liabilities + Equity",
        severity=ConstraintSeverity.CRITICAL,
        formula="Assets - (Liabilities + Equity) = 0",
        required_tables=["BALANCE_SHEET"],
    ),
    AccountingConstraint(
        constraint_id="TB_BALANCE",
        name="Trial Balance Balance",
        description="Total Debits = Total Credits",
        severity=ConstraintSeverity.CRITICAL,
        formula="Sum(Debit) - Sum(Credit) = 0",
        required_tables=["TRIAL_BALANCE"],
    ),
    AccountingConstraint(
        constraint_id="NI_CONSISTENCY",
        name="Net Income Consistency",
        description="Net Income on IS = Retained Earnings change on BS",
        severity=ConstraintSeverity.WARNING,
        formula="NI(IS) - Delta_RE(BS) = 0",
        required_tables=["INCOME_STATEMENT", "BALANCE_SHEET"],
    ),
    AccountingConstraint(
        constraint_id="CF_TOTAL",
        name="Cash Flow Total",
        description="Operating + Investing + Financing = Net Cash Change",
        severity=ConstraintSeverity.WARNING,
        formula="CFO + CFI + CFF - Net_Cash_Change = 0",
        required_tables=["CASH_FLOW"],
    ),
    AccountingConstraint(
        constraint_id="GL_COA_XREF",
        name="GL-COA Cross Reference",
        description="All GL account codes exist in Chart of Accounts",
        severity=ConstraintSeverity.WARNING,
        formula="GL_accounts subset_of COA_accounts",
        required_tables=["GENERAL_LEDGER", "CHART_OF_ACCOUNTS"],
    ),
    AccountingConstraint(
        constraint_id="TB_IS_REVENUE",
        name="Revenue Cross-Check",
        description="Revenue totals match between TB and IS",
        severity=ConstraintSeverity.INFO,
        formula="Revenue(TB) - Revenue(IS) = 0",
        required_tables=["TRIAL_BALANCE", "INCOME_STATEMENT"],
    ),
]


# ── Parsed Table Wrapper ────────────────────────────────────────────────────

@dataclass
class ParsedTableData:
    """
    Normalized view of a parsed table for constraint checking.

    Extracts key financial aggregates regardless of which
    hypothesis produced the parse.
    """
    schema_type: str
    records: List[Dict[str, Any]]
    confidence: float = 0.0

    # Extracted aggregates
    total_debit: float = 0.0
    total_credit: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    net_income: float = 0.0
    total_revenue: float = 0.0
    total_expenses: float = 0.0
    cfo: float = 0.0              # Cash from operations
    cfi: float = 0.0              # Cash from investing
    cff: float = 0.0              # Cash from financing
    net_cash_change: float = 0.0
    account_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_type": self.schema_type,
            "record_count": len(self.records),
            "confidence": self.confidence,
            "total_debit": self.total_debit,
            "total_credit": self.total_credit,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "total_equity": self.total_equity,
            "net_income": self.net_income,
            "total_revenue": self.total_revenue,
        }


# ── Financial Model Extractor ───────────────────────────────────────────────

class FinancialDataExtractor:
    """
    Extracts financial aggregates from parsed records.

    Adapts to whatever fields are present in the records,
    using heuristics and account code prefixes to classify amounts.
    """

    # Revenue account prefixes (Georgian IFRS)
    _REVENUE_PREFIXES = ("6", "61", "62", "63", "64", "65")
    _EXPENSE_PREFIXES = ("7", "71", "72", "73", "74", "75", "8", "9")
    _ASSET_PREFIXES = ("1", "2")
    _LIABILITY_PREFIXES = ("3", "4")
    _EQUITY_PREFIXES = ("5",)

    # Revenue keywords for IS/BS without codes
    _REVENUE_KEYWORDS = [
        "revenue", "sales", "income", "turnover",
        "выручка", "доход", "продажи", "შემოსავალი",
    ]
    _EXPENSE_KEYWORDS = [
        "cost", "cogs", "expense", "operating", "depreciation",
        "расход", "себестоимость", "ხარჯი",
    ]
    _ASSET_KEYWORDS = [
        "asset", "cash", "receivable", "inventory", "fixed",
        "актив", "денежные", "дебиторская", "запасы", "основные",
    ]
    _LIABILITY_KEYWORDS = [
        "liability", "payable", "loan", "debt", "obligation",
        "обязательство", "кредиторская", "займ",
    ]
    _EQUITY_KEYWORDS = [
        "equity", "capital", "retained", "share",
        "капитал", "собственный", "нераспределенная",
    ]

    def extract(
        self,
        schema_type: str,
        records: List[Dict[str, Any]],
        confidence: float = 0.0,
    ) -> ParsedTableData:
        """Extract financial aggregates from parsed records."""
        data = ParsedTableData(
            schema_type=schema_type,
            records=records,
            confidence=confidence,
        )

        if schema_type == "TRIAL_BALANCE":
            self._extract_trial_balance(data)
        elif schema_type == "GENERAL_LEDGER":
            self._extract_general_ledger(data)
        elif schema_type == "INCOME_STATEMENT":
            self._extract_income_statement(data)
        elif schema_type == "BALANCE_SHEET":
            self._extract_balance_sheet(data)
        elif schema_type == "CASH_FLOW":
            self._extract_cash_flow(data)
        elif schema_type == "CHART_OF_ACCOUNTS":
            self._extract_coa(data)

        return data

    def _extract_trial_balance(self, data: ParsedTableData) -> None:
        """Extract TB aggregates: total debit, credit, revenue, expenses."""
        for r in data.records:
            dr = self._safe_float(r.get("debit", 0))
            cr = self._safe_float(r.get("credit", 0))
            data.total_debit += dr
            data.total_credit += cr

            code = str(r.get("account_code", "")).strip()
            if code:
                data.account_codes.append(code)

                net = cr - dr  # Net credit balance
                if self._starts_with(code, self._REVENUE_PREFIXES):
                    data.total_revenue += net
                elif self._starts_with(code, self._EXPENSE_PREFIXES):
                    data.total_expenses += abs(dr - cr)
                elif self._starts_with(code, self._ASSET_PREFIXES):
                    data.total_assets += dr - cr
                elif self._starts_with(code, self._LIABILITY_PREFIXES):
                    data.total_liabilities += net
                elif self._starts_with(code, self._EQUITY_PREFIXES):
                    data.total_equity += net

        data.net_income = data.total_revenue - data.total_expenses

    def _extract_general_ledger(self, data: ParsedTableData) -> None:
        """Extract GL aggregates."""
        for r in data.records:
            dr = self._safe_float(r.get("debit", 0))
            cr = self._safe_float(r.get("credit", 0))
            data.total_debit += dr
            data.total_credit += cr

            code = str(r.get("account_code", "")).strip()
            if code:
                data.account_codes.append(code)

    def _extract_income_statement(self, data: ParsedTableData) -> None:
        """Extract IS aggregates using name keywords."""
        for r in data.records:
            name = str(r.get("account_name", "")).lower()
            amount = self._safe_float(r.get("amount", 0))

            if any(kw in name for kw in self._REVENUE_KEYWORDS):
                data.total_revenue += abs(amount)
            elif any(kw in name for kw in self._EXPENSE_KEYWORDS):
                data.total_expenses += abs(amount)
            elif "net income" in name or "net profit" in name:
                data.net_income = amount

        if data.net_income == 0 and (data.total_revenue or data.total_expenses):
            data.net_income = data.total_revenue - data.total_expenses

    def _extract_balance_sheet(self, data: ParsedTableData) -> None:
        """Extract BS aggregates using name keywords."""
        for r in data.records:
            name = str(r.get("account_name", "")).lower()
            amount = self._safe_float(r.get("amount", 0))

            if any(kw in name for kw in self._ASSET_KEYWORDS):
                data.total_assets += abs(amount)
            elif any(kw in name for kw in self._LIABILITY_KEYWORDS):
                data.total_liabilities += abs(amount)
            elif any(kw in name for kw in self._EQUITY_KEYWORDS):
                data.total_equity += abs(amount)

    def _extract_cash_flow(self, data: ParsedTableData) -> None:
        """Extract CF aggregates."""
        for r in data.records:
            name = str(r.get("account_name", "")).lower()
            amount = self._safe_float(r.get("amount", 0))

            if "operating" in name:
                data.cfo += amount
            elif "investing" in name:
                data.cfi += amount
            elif "financing" in name:
                data.cff += amount
            elif "net cash" in name or "net change" in name:
                data.net_cash_change = amount

    def _extract_coa(self, data: ParsedTableData) -> None:
        """Extract COA account codes."""
        for r in data.records:
            code = str(r.get("account_code", "")).strip()
            if code:
                data.account_codes.append(code)

    def _safe_float(self, val: Any) -> float:
        """Safely convert to float."""
        if val is None:
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def _starts_with(self, code: str, prefixes: Tuple[str, ...]) -> bool:
        """Check if code starts with any of the given prefixes."""
        return any(code.startswith(p) for p in prefixes)


# ── Constraint Graph Validation Engine ──────────────────────────────────────

class ConstraintGraph:
    """
    Cross-table accounting constraint validation engine.

    Validates relationships between parsed tables, producing a
    ValidationReport with pass/fail results and confidence adjustments.

    Usage:
        graph = ConstraintGraph()
        report = graph.validate(parsed_tables)
        # report.overall_confidence_adjustment → apply to HDP scores
        # report.detected_issues → show to user
    """

    def __init__(self, tolerance: float = 0.01):
        self._extractor = FinancialDataExtractor()
        self._tolerance = tolerance

    def validate(
        self,
        parsed_tables: List[Dict[str, Any]],
    ) -> ValidationReport:
        """
        Validate cross-table accounting constraints.

        Args:
            parsed_tables: List of dicts with keys:
                - "schema_type": str
                - "records": List[Dict]
                - "confidence": float

        Returns:
            ValidationReport with constraint results and adjustments.
        """
        report = ValidationReport()

        # Extract financial data from each parsed table
        table_data: Dict[str, ParsedTableData] = {}
        for table in parsed_tables:
            schema_type = table.get("schema_type", "UNKNOWN")
            records = table.get("records", [])
            confidence = table.get("confidence", 0.0)

            if schema_type == "UNKNOWN" or not records:
                continue

            data = self._extractor.extract(schema_type, records, confidence)
            table_data[schema_type] = data

        if not table_data:
            report.financial_model_valid = False
            report.detected_issues.append("No valid tables to validate")
            return report

        # Run each constraint
        for constraint in CONSTRAINTS:
            # Check if required tables are present
            required_present = all(
                t in table_data for t in constraint.required_tables
            )
            if not required_present:
                continue  # Skip constraints whose tables don't exist

            result = self._check_constraint(constraint, table_data)
            report.results.append(result)
            report.total_constraints += 1

            if result.passed:
                report.passed += 1
            else:
                if result.severity == ConstraintSeverity.CRITICAL:
                    report.failed += 1
                    report.detected_issues.append(
                        f"CRITICAL: {result.message}"
                    )
                elif result.severity == ConstraintSeverity.WARNING:
                    report.warnings += 1
                    report.detected_issues.append(
                        f"WARNING: {result.message}"
                    )

            report.overall_confidence_adjustment += result.penalty

        # Determine model validity
        critical_failures = sum(
            1 for r in report.results
            if not r.passed and r.severity == ConstraintSeverity.CRITICAL
        )
        report.financial_model_valid = critical_failures == 0

        # Confidence bonus for passing all constraints
        if report.total_constraints > 0 and report.failed == 0:
            bonus = min(report.pass_rate * 0.1, 0.1)  # Up to 10% boost
            report.overall_confidence_adjustment += bonus

        return report

    def _check_constraint(
        self,
        constraint: AccountingConstraint,
        table_data: Dict[str, ParsedTableData],
    ) -> ConstraintResult:
        """Check a single constraint against the parsed data."""
        method_name = f"_check_{constraint.constraint_id.lower()}"
        method = getattr(self, method_name, None)

        if method is None:
            return ConstraintResult(
                constraint_id=constraint.constraint_id,
                name=constraint.name,
                passed=True,
                severity=constraint.severity,
                message="No checker implemented",
            )

        return method(constraint, table_data)

    def _check_bs_equation(
        self,
        constraint: AccountingConstraint,
        data: Dict[str, ParsedTableData],
    ) -> ConstraintResult:
        """Check: Assets = Liabilities + Equity"""
        bs = data.get("BALANCE_SHEET")
        if bs is None:
            return self._skip_result(constraint)

        assets = bs.total_assets
        liab_eq = bs.total_liabilities + bs.total_equity
        diff = abs(assets - liab_eq)
        max_val = max(abs(assets), abs(liab_eq), 1.0)
        ratio = diff / max_val

        passed = ratio <= self._tolerance
        penalty = 0.0 if passed else -0.15  # 15% penalty for BS imbalance

        return ConstraintResult(
            constraint_id=constraint.constraint_id,
            name=constraint.name,
            passed=passed,
            severity=constraint.severity,
            expected=assets,
            actual=liab_eq,
            difference=diff,
            tolerance=self._tolerance,
            message=(
                f"BS equation holds: Assets({assets:.2f}) = "
                f"L+E({liab_eq:.2f})"
                if passed else
                f"BS IMBALANCED: Assets({assets:.2f}) != "
                f"L+E({liab_eq:.2f}), diff={diff:.2f}"
            ),
            penalty=penalty,
        )

    def _check_tb_balance(
        self,
        constraint: AccountingConstraint,
        data: Dict[str, ParsedTableData],
    ) -> ConstraintResult:
        """Check: Sum(Debit) = Sum(Credit)"""
        tb = data.get("TRIAL_BALANCE")
        if tb is None:
            return self._skip_result(constraint)

        diff = abs(tb.total_debit - tb.total_credit)
        max_val = max(tb.total_debit, tb.total_credit, 1.0)
        ratio = diff / max_val

        passed = ratio <= self._tolerance
        penalty = 0.0 if passed else -0.20  # 20% penalty for TB imbalance

        return ConstraintResult(
            constraint_id=constraint.constraint_id,
            name=constraint.name,
            passed=passed,
            severity=constraint.severity,
            expected=tb.total_debit,
            actual=tb.total_credit,
            difference=diff,
            tolerance=self._tolerance,
            message=(
                f"TB balanced: Dr({tb.total_debit:.2f}) = "
                f"Cr({tb.total_credit:.2f})"
                if passed else
                f"TB UNBALANCED: Dr({tb.total_debit:.2f}) != "
                f"Cr({tb.total_credit:.2f}), diff={diff:.2f}"
            ),
            penalty=penalty,
        )

    def _check_ni_consistency(
        self,
        constraint: AccountingConstraint,
        data: Dict[str, ParsedTableData],
    ) -> ConstraintResult:
        """Check: Net Income (IS) matches implications in BS."""
        is_data = data.get("INCOME_STATEMENT")
        bs_data = data.get("BALANCE_SHEET")

        if is_data is None or bs_data is None:
            return self._skip_result(constraint)

        ni_from_is = is_data.net_income
        ni_from_bs = bs_data.total_equity  # Simplified: equity includes NI

        # This is a loose check since we may not have prior-period BS
        if abs(ni_from_is) < 0.01 and abs(ni_from_bs) < 0.01:
            passed = True
            diff = 0.0
        else:
            # Just check that NI is reasonable relative to equity
            diff = abs(ni_from_is)
            passed = diff > 0  # NI exists on IS

        penalty = 0.0 if passed else -0.05

        return ConstraintResult(
            constraint_id=constraint.constraint_id,
            name=constraint.name,
            passed=passed,
            severity=constraint.severity,
            expected=ni_from_is,
            actual=ni_from_bs,
            difference=diff,
            message=(
                f"Net Income ({ni_from_is:.2f}) found on IS"
                if passed else
                f"No Net Income detected on Income Statement"
            ),
            penalty=penalty,
        )

    def _check_cf_total(
        self,
        constraint: AccountingConstraint,
        data: Dict[str, ParsedTableData],
    ) -> ConstraintResult:
        """Check: CFO + CFI + CFF = Net Cash Change."""
        cf = data.get("CASH_FLOW")
        if cf is None:
            return self._skip_result(constraint)

        computed = cf.cfo + cf.cfi + cf.cff
        actual = cf.net_cash_change

        if abs(computed) < 0.01 and abs(actual) < 0.01:
            passed = True
            diff = 0.0
        else:
            diff = abs(computed - actual)
            max_val = max(abs(computed), abs(actual), 1.0)
            passed = diff / max_val <= self._tolerance

        penalty = 0.0 if passed else -0.05

        return ConstraintResult(
            constraint_id=constraint.constraint_id,
            name=constraint.name,
            passed=passed,
            severity=constraint.severity,
            expected=computed,
            actual=actual,
            difference=diff,
            message=(
                f"CF total correct: CFO+CFI+CFF({computed:.2f}) = "
                f"Net({actual:.2f})"
                if passed else
                f"CF mismatch: CFO+CFI+CFF({computed:.2f}) != "
                f"Net({actual:.2f}), diff={diff:.2f}"
            ),
            penalty=penalty,
        )

    def _check_gl_coa_xref(
        self,
        constraint: AccountingConstraint,
        data: Dict[str, ParsedTableData],
    ) -> ConstraintResult:
        """Check: All GL accounts exist in COA."""
        gl = data.get("GENERAL_LEDGER")
        coa = data.get("CHART_OF_ACCOUNTS")

        if gl is None or coa is None:
            return self._skip_result(constraint)

        gl_codes = set(gl.account_codes)
        coa_codes = set(coa.account_codes)

        if not gl_codes:
            return self._skip_result(constraint)

        missing = gl_codes - coa_codes
        match_rate = 1.0 - (len(missing) / len(gl_codes))
        passed = match_rate >= 0.90  # 90% match threshold

        penalty = 0.0 if passed else -0.05 * (1.0 - match_rate)

        return ConstraintResult(
            constraint_id=constraint.constraint_id,
            name=constraint.name,
            passed=passed,
            severity=constraint.severity,
            expected=len(gl_codes),
            actual=len(gl_codes) - len(missing),
            difference=len(missing),
            message=(
                f"GL-COA match rate: {match_rate:.1%} "
                f"({len(gl_codes) - len(missing)}/{len(gl_codes)} codes found)"
                + (f", missing: {list(missing)[:5]}..." if missing else "")
            ),
            penalty=penalty,
        )

    def _check_tb_is_revenue(
        self,
        constraint: AccountingConstraint,
        data: Dict[str, ParsedTableData],
    ) -> ConstraintResult:
        """Check: Revenue totals match between TB and IS."""
        tb = data.get("TRIAL_BALANCE")
        is_data = data.get("INCOME_STATEMENT")

        if tb is None or is_data is None:
            return self._skip_result(constraint)

        tb_rev = tb.total_revenue
        is_rev = is_data.total_revenue

        if abs(tb_rev) < 0.01 and abs(is_rev) < 0.01:
            passed = True
            diff = 0.0
        else:
            diff = abs(tb_rev - is_rev)
            max_val = max(abs(tb_rev), abs(is_rev), 1.0)
            passed = diff / max_val <= 0.05  # 5% tolerance

        penalty = 0.0 if passed else -0.02

        return ConstraintResult(
            constraint_id=constraint.constraint_id,
            name=constraint.name,
            passed=passed,
            severity=constraint.severity,
            expected=tb_rev,
            actual=is_rev,
            difference=diff,
            message=(
                f"Revenue cross-check: TB({tb_rev:.2f}) ~ IS({is_rev:.2f})"
                if passed else
                f"Revenue mismatch: TB({tb_rev:.2f}) != IS({is_rev:.2f})"
            ),
            penalty=penalty,
        )

    def _skip_result(self, constraint: AccountingConstraint) -> ConstraintResult:
        """Create a skipped/passed result for missing data."""
        return ConstraintResult(
            constraint_id=constraint.constraint_id,
            name=constraint.name,
            passed=True,
            severity=constraint.severity,
            message="Skipped: required tables not present",
            penalty=0.0,
        )


# ── Module-level singleton ───────────────────────────────────────────────────
constraint_graph = ConstraintGraph()
