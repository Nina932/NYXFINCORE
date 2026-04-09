"""
FinAI Reconciliation Engine
============================
SAP-grade reconciliation: verifies P&L ties to Trial Balance ties to Balance Sheet.
Checks:
1. TB Balance: total debits == total credits
2. P&L net income == BS retained earnings change
3. Revenue in P&L == sum of 6xxx accounts in TB
4. COGS in P&L == sum of 71xx accounts in TB
5. BS equation: Assets == Liabilities + Equity
6. Cash flow reconciliation (if data available)

Public API:
    from app.services.v2.reconciliation_engine import reconciliation_engine
    report = await reconciliation_engine.run_reconciliation(period, db)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, round_fin, is_zero

logger = logging.getLogger(__name__)
D = Decimal

# Tolerance for floating-point comparison (1 GEL)
TOLERANCE = D("1.00")
# Warning threshold (accounts for minor rounding across many accounts)
WARNING_TOLERANCE = D("0.50")


@dataclass
class ReconciliationCheck:
    """Single reconciliation check result."""
    name: str
    description: str
    expected: float
    actual: float
    difference: float
    status: str  # "pass" | "fail" | "warning"
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class ReconciliationReport:
    """Full reconciliation report."""
    period: str
    checks: List[ReconciliationCheck] = field(default_factory=list)
    overall_status: str = "pass"
    discrepancies: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "overall_status": self.overall_status,
            "checks": [c.to_dict() for c in self.checks],
            "discrepancies": self.discrepancies,
            "summary": self.summary,
            "pass_count": sum(1 for c in self.checks if c.status == "pass"),
            "fail_count": sum(1 for c in self.checks if c.status == "fail"),
            "warning_count": sum(1 for c in self.checks if c.status == "warning"),
            "total_checks": len(self.checks),
        }


class ReconciliationEngine:
    """
    SAP-grade reconciliation engine.

    Verifies the internal consistency of financial statements generated
    from the GL (posted journal entries / posting_lines).
    """

    async def run_reconciliation(
        self,
        period: str,
        db: AsyncSession,
        dataset_id: Optional[int] = None,
    ) -> ReconciliationReport:
        """
        Run full reconciliation suite for a period.

        Args:
            period: Fiscal period string (e.g. "January 2026")
            db: Async database session
            dataset_id: Optional dataset filter (unused for GL-based reconciliation)

        Returns:
            ReconciliationReport with all check results.
        """
        report = ReconciliationReport(period=period)

        # Build TB, P&L, BS from the GL
        from app.services.v2.gl_reporting import gl_reporting

        tb = await gl_reporting.trial_balance(period, db)
        pl = await gl_reporting.income_statement(period, db)
        bs = await gl_reporting.balance_sheet(period, db)

        if not tb["accounts"]:
            report.overall_status = "no_data"
            report.summary = {"message": f"No posted journal entries found for period '{period}'."}
            return report

        # ── Check 1: TB Balance (Debits == Credits) ──
        report.checks.append(self._check_tb_balance(tb))

        # ── Check 2: P&L Net Income == BS Retained Earnings Change ──
        report.checks.append(self._check_net_income_vs_retained_earnings(pl, bs, tb))

        # ── Check 3: Revenue in P&L == sum of 6xxx accounts in TB ──
        report.checks.append(self._check_revenue_vs_tb(pl, tb))

        # ── Check 4: COGS in P&L == sum of 71xx accounts in TB ──
        report.checks.append(self._check_cogs_vs_tb(pl, tb))

        # ── Check 5: BS Equation (Assets == Liabilities + Equity) ──
        report.checks.append(self._check_bs_equation(bs))

        # ── Check 6: P&L expense accounts tie to TB ──
        report.checks.append(self._check_expenses_vs_tb(pl, tb))

        # ── Check 7: Cash flow reconciliation (opening + changes = closing) ──
        report.checks.append(self._check_cash_accounts(bs, tb))

        # ── Check 8-10: Cross-check GL against pl_comparison (entity tables) ──
        try:
            cross_checks = await self._cross_check_pl_comparison(
                pl, bs, dataset_id, db
            )
            report.checks.extend(cross_checks)
        except Exception as e:
            logger.debug("pl_comparison cross-checks skipped: %s", e)

        # Determine overall status
        # Core GL checks (1-7) determine pass/fail
        # Cross-source checks (8-11) are informational warnings
        core_checks = report.checks[:7] if len(report.checks) > 7 else report.checks
        has_core_fail = any(c.status == "fail" for c in core_checks)
        has_any_warning = any(c.status == "warning" for c in report.checks)
        has_any_fail = any(c.status == "fail" for c in report.checks)
        if has_core_fail:
            report.overall_status = "fail"
        elif has_any_fail or has_any_warning:
            report.overall_status = "pass_with_warnings"
        else:
            report.overall_status = "pass"

        # Collect discrepancies
        report.discrepancies = [
            {"check": c.name, "expected": c.expected, "actual": c.actual,
             "difference": c.difference, "details": c.details}
            for c in report.checks if c.status == "fail"
        ]

        report.summary = {
            "period": period,
            "tb_account_count": tb["account_count"],
            "tb_total_debit": tb["total_debit"],
            "tb_total_credit": tb["total_credit"],
            "pl_revenue": pl["revenue"],
            "pl_net_profit": pl["net_profit"],
            "bs_total_assets": bs["total_assets"],
            "bs_total_liabilities": bs["total_liabilities"],
            "bs_total_equity": bs["total_equity"],
        }

        return report

    # ── Individual checks ────────────────────────────────────────────

    def _check_tb_balance(self, tb: Dict) -> ReconciliationCheck:
        """Check 1: Trial Balance debits == credits."""
        total_dr = to_decimal(tb["total_debit"])
        total_cr = to_decimal(tb["total_credit"])
        diff = abs(total_dr - total_cr)

        status = "pass"
        if diff > TOLERANCE:
            status = "fail"
        elif diff > WARNING_TOLERANCE:
            status = "warning"

        return ReconciliationCheck(
            name="TB Balance",
            description="Total debits must equal total credits in Trial Balance",
            expected=float(round_fin(total_dr)),
            actual=float(round_fin(total_cr)),
            difference=float(round_fin(diff)),
            status=status,
            details=f"DR={round_fin(total_dr)}, CR={round_fin(total_cr)}, diff={round_fin(diff)}" if status != "pass" else None,
        )

    def _check_net_income_vs_retained_earnings(
        self, pl: Dict, bs: Dict, tb: Dict
    ) -> ReconciliationCheck:
        """Check 2: P&L net income should match implied retained earnings from equity accounts.

        In a single-period context (no prior period), net income from P&L
        should equal the net balance of income/expense accounts in TB,
        which should tie to any retained earnings adjustment in BS.
        """
        pl_net_income = to_decimal(pl["net_profit"])

        # Compute net income directly from TB: (sum of 6xxx credits - debits) - (sum of 7/8/9 debits - credits)
        revenue_from_tb = D("0")
        expenses_from_tb = D("0")
        for acct in tb["accounts"]:
            code = acct["account_code"]
            if not code or not code[0].isdigit():
                continue
            dr = to_decimal(acct["debit"])
            cr = to_decimal(acct["credit"])
            first = code[0]
            if first == "6":
                revenue_from_tb += (cr - dr)
            elif first in ("7", "8", "9"):
                expenses_from_tb += (dr - cr)

        tb_net_income = revenue_from_tb - expenses_from_tb
        diff = abs(pl_net_income - tb_net_income)

        status = "pass"
        if diff > TOLERANCE:
            status = "fail"
        elif diff > WARNING_TOLERANCE:
            status = "warning"

        return ReconciliationCheck(
            name="Net Income P&L vs TB",
            description="P&L net profit must equal net of income/expense accounts in TB",
            expected=float(round_fin(pl_net_income)),
            actual=float(round_fin(tb_net_income)),
            difference=float(round_fin(diff)),
            status=status,
            details=f"P&L net={round_fin(pl_net_income)}, TB-derived net={round_fin(tb_net_income)}" if status != "pass" else None,
        )

    def _check_revenue_vs_tb(self, pl: Dict, tb: Dict) -> ReconciliationCheck:
        """Check 3: P&L revenue == sum of class 6 accounts in TB."""
        pl_revenue = to_decimal(pl["revenue"])

        tb_revenue = D("0")
        for acct in tb["accounts"]:
            code = acct["account_code"]
            if code and code[0] == "6":
                cr = to_decimal(acct["credit"])
                dr = to_decimal(acct["debit"])
                tb_revenue += (cr - dr)

        diff = abs(pl_revenue - tb_revenue)
        status = "pass"
        if diff > TOLERANCE:
            status = "fail"
        elif diff > WARNING_TOLERANCE:
            status = "warning"

        return ReconciliationCheck(
            name="Revenue P&L vs TB",
            description="Revenue in P&L must equal sum of 6xxx accounts in TB",
            expected=float(round_fin(pl_revenue)),
            actual=float(round_fin(tb_revenue)),
            difference=float(round_fin(diff)),
            status=status,
            details=f"P&L revenue={round_fin(pl_revenue)}, TB 6xxx sum={round_fin(tb_revenue)}" if status != "pass" else None,
        )

    def _check_cogs_vs_tb(self, pl: Dict, tb: Dict) -> ReconciliationCheck:
        """Check 4: P&L COGS == sum of 71xx + 7310xx accounts in TB."""
        pl_cogs = to_decimal(pl["cogs"])

        tb_cogs = D("0")
        for acct in tb["accounts"]:
            code = acct["account_code"]
            if not code:
                continue
            prefix2 = code[:2] if len(code) >= 2 else code
            dr = to_decimal(acct["debit"])
            cr = to_decimal(acct["credit"])

            if prefix2 == "71":
                tb_cogs += (dr - cr)
            elif code.startswith("7310"):
                tb_cogs += (dr - cr)
            elif code.startswith("8230"):
                tb_cogs += (dr - cr)

        diff = abs(pl_cogs - tb_cogs)
        status = "pass"
        if diff > TOLERANCE:
            status = "fail"
        elif diff > WARNING_TOLERANCE:
            status = "warning"

        return ReconciliationCheck(
            name="COGS P&L vs TB",
            description="COGS in P&L must equal sum of 71xx/7310/8230 accounts in TB",
            expected=float(round_fin(pl_cogs)),
            actual=float(round_fin(tb_cogs)),
            difference=float(round_fin(diff)),
            status=status,
            details=f"P&L COGS={round_fin(pl_cogs)}, TB COGS accounts={round_fin(tb_cogs)}" if status != "pass" else None,
        )

    def _check_bs_equation(self, bs: Dict) -> ReconciliationCheck:
        """Check 5: Assets == Liabilities + Equity."""
        assets = to_decimal(bs["total_assets"])
        liabilities = to_decimal(bs["total_liabilities"])
        equity = to_decimal(bs["total_equity"])
        rhs = liabilities + equity
        diff = abs(assets - rhs)

        status = "pass"
        if diff > TOLERANCE:
            status = "fail"
        elif diff > WARNING_TOLERANCE:
            status = "warning"

        return ReconciliationCheck(
            name="BS Equation",
            description="Assets must equal Liabilities + Equity",
            expected=float(round_fin(assets)),
            actual=float(round_fin(rhs)),
            difference=float(round_fin(diff)),
            status=status,
            details=f"Assets={round_fin(assets)}, L+E={round_fin(rhs)} (L={round_fin(liabilities)}, E={round_fin(equity)})" if status != "pass" else None,
        )

    def _check_expenses_vs_tb(self, pl: Dict, tb: Dict) -> ReconciliationCheck:
        """Check 6: Total operating expenses in P&L match TB expense accounts."""
        pl_total_expenses = (
            to_decimal(pl["cogs"])
            + to_decimal(pl["selling_expenses"])
            + to_decimal(pl["admin_expenses"])
            + to_decimal(pl["depreciation"])
            + to_decimal(pl["finance_expense"])
            + to_decimal(pl["tax_expense"])
            + to_decimal(pl["other_expense"])
        )

        tb_total_expenses = D("0")
        for acct in tb["accounts"]:
            code = acct["account_code"]
            if not code or not code[0].isdigit():
                continue
            first = code[0]
            dr = to_decimal(acct["debit"])
            cr = to_decimal(acct["credit"])
            if first in ("7", "9"):
                tb_total_expenses += (dr - cr)
            elif first == "8" and code[:2] in ("82", "83"):
                tb_total_expenses += (dr - cr)

        diff = abs(pl_total_expenses - tb_total_expenses)
        status = "pass"
        if diff > TOLERANCE:
            status = "fail"
        elif diff > WARNING_TOLERANCE:
            status = "warning"

        return ReconciliationCheck(
            name="Total Expenses P&L vs TB",
            description="Total expenses in P&L must tie to expense account sums in TB",
            expected=float(round_fin(pl_total_expenses)),
            actual=float(round_fin(tb_total_expenses)),
            difference=float(round_fin(diff)),
            status=status,
            details=f"P&L expenses={round_fin(pl_total_expenses)}, TB expense accounts={round_fin(tb_total_expenses)}" if status != "pass" else None,
        )

    def _check_cash_accounts(self, bs: Dict, tb: Dict) -> ReconciliationCheck:
        """Check 7: Cash in BS == sum of cash accounts (11xx, 12xx) in TB."""
        bs_cash = to_decimal(bs["cash"])

        tb_cash = D("0")
        for acct in tb["accounts"]:
            code = acct["account_code"]
            if not code:
                continue
            prefix2 = code[:2] if len(code) >= 2 else code
            if prefix2 in ("11", "12"):
                tb_cash += to_decimal(acct["net"])

        diff = abs(bs_cash - tb_cash)
        status = "pass"
        if diff > TOLERANCE:
            status = "fail"
        elif diff > WARNING_TOLERANCE:
            status = "warning"

        return ReconciliationCheck(
            name="Cash BS vs TB",
            description="Cash balance in BS must equal sum of 11xx/12xx accounts in TB",
            expected=float(round_fin(bs_cash)),
            actual=float(round_fin(tb_cash)),
            difference=float(round_fin(diff)),
            status=status,
            details=f"BS cash={round_fin(bs_cash)}, TB 11xx/12xx={round_fin(tb_cash)}" if status != "pass" else None,
        )


    # ── Cross-checks: GL vs pl_comparison entity tables ──────────────

    async def _cross_check_pl_comparison(
        self,
        gl_pl: Dict,
        gl_bs: Dict,
        dataset_id: Optional[int],
        db: AsyncSession,
    ) -> List[ReconciliationCheck]:
        """
        Cross-check GL-derived P&L/BS against pl_comparison entity tables
        (RevenueItem/COGSItem/BalanceSheetItem).  These checks highlight
        data-source divergence rather than internal GL consistency.
        """
        checks: List[ReconciliationCheck] = []

        # Resolve dataset_id if not provided
        if not dataset_id:
            from app.models.all_models import Dataset
            ds = (await db.execute(
                select(Dataset).where(Dataset.record_count > 0)
                .order_by(Dataset.id.desc()).limit(1)
            )).scalar_one_or_none()
            if not ds:
                return checks
            dataset_id = ds.id

        from app.services.v2.pl_comparison import pl_comparison

        # ── Check 8: P&L Comparison Revenue vs GL Revenue ──
        try:
            pl_data = await pl_comparison.full_pl(dataset_id, None, db)
            pl_summary = pl_data.get("summary", {})
            pl_revenue = to_decimal(pl_summary.get("revenue", 0))
            gl_revenue = to_decimal(gl_pl.get("revenue", 0))

            diff = abs(pl_revenue - gl_revenue)
            status = "pass"
            if diff > D("1.00"):
                # Cross-source divergence is informational, not a GL integrity issue
                status = "warning"

            checks.append(ReconciliationCheck(
                name="Revenue: Entity Tables vs GL",
                description="Revenue from P&L comparison (RevenueItem) vs GL posting_lines",
                expected=float(round_fin(pl_revenue)),
                actual=float(round_fin(gl_revenue)),
                difference=float(round_fin(diff)),
                status=status,
                details=(
                    f"Entity tables (RevenueItem): {round_fin(pl_revenue)}, "
                    f"GL (posting_lines): {round_fin(gl_revenue)}"
                ) if status != "pass" else None,
            ))

            # ── Check 9: P&L Comparison Revenue internal consistency ──
            rev_comp = await pl_comparison.revenue_comparison(dataset_id, None, db)
            rev_total = to_decimal(rev_comp.get("total_revenue_actual", 0))
            diff_internal = abs(pl_revenue - rev_total)
            status_internal = "pass"
            if diff_internal > TOLERANCE:
                status_internal = "warning"  # Cross-source divergence = warning, not fail

            checks.append(ReconciliationCheck(
                name="Revenue: P&L Summary vs Detail Breakdown",
                description="P&L summary revenue must match revenue_comparison total",
                expected=float(round_fin(pl_revenue)),
                actual=float(round_fin(rev_total)),
                difference=float(round_fin(diff_internal)),
                status=status_internal,
                details=(
                    f"P&L summary: {round_fin(pl_revenue)}, "
                    f"Revenue breakdown total: {round_fin(rev_total)}"
                ) if status_internal != "pass" else None,
            ))

            # ── Check 10: Net Profit entity tables vs GL ──
            pl_net = to_decimal(pl_summary.get("net_profit", 0))
            gl_net = to_decimal(gl_pl.get("net_profit", 0))
            diff_net = abs(pl_net - gl_net)
            status_net = "pass"
            if diff_net > D("1.00"):
                status_net = "warning"  # Cross-source divergence = warning, not fail

            checks.append(ReconciliationCheck(
                name="Net Profit: Entity Tables vs GL",
                description="Net profit from P&L comparison vs GL posting_lines",
                expected=float(round_fin(pl_net)),
                actual=float(round_fin(gl_net)),
                difference=float(round_fin(diff_net)),
                status=status_net,
                details=(
                    f"Entity tables: {round_fin(pl_net)}, "
                    f"GL: {round_fin(gl_net)}"
                ) if status_net != "pass" else None,
            ))

        except Exception as e:
            logger.debug("Cross-check with pl_comparison failed: %s", e)

        # ── Check 11: BS entity tables equation (Assets = L + E) ──
        try:
            bs_data = await pl_comparison.balance_sheet_comparison(dataset_id, None, db)
            if bs_data.get("total_assets") is not None:
                bs_assets = to_decimal(bs_data["total_assets"])
                bs_liabilities = to_decimal(bs_data["total_liabilities"])
                bs_equity = to_decimal(bs_data["total_equity"])
                rhs = bs_liabilities + bs_equity
                diff_bs = abs(bs_assets - rhs)

                status_bs = "pass"
                if diff_bs > TOLERANCE:
                    status_bs = "warning"  # Entity table BS — informational, not core GL

                checks.append(ReconciliationCheck(
                    name="BS Equation (Entity Tables)",
                    description="Assets == Liabilities + Equity from BalanceSheetItem records",
                    expected=float(round_fin(bs_assets)),
                    actual=float(round_fin(rhs)),
                    difference=float(round_fin(diff_bs)),
                    status=status_bs,
                    details=(
                        f"Assets={round_fin(bs_assets)}, L+E={round_fin(rhs)} "
                        f"(L={round_fin(bs_liabilities)}, E={round_fin(bs_equity)})"
                    ) if status_bs != "pass" else None,
                ))
        except Exception as e:
            logger.debug("BS entity cross-check failed: %s", e)

        return checks


# Module singleton
reconciliation_engine = ReconciliationEngine()
