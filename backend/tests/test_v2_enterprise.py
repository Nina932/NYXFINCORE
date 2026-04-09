"""
Test Suite: v2 Enterprise Modules — Assets, Tax, Bank Rec, Aging, Approval, Compliance
========================================================================================
"""
import pytest
from decimal import Decimal
from datetime import date


class TestFixedAssets:
    def test_straight_line_depreciation(self):
        from app.services.v2.fixed_assets import asset_service
        result = asset_service.compute_depreciation(
            acquisition_cost=100000, residual_value=10000,
            useful_life_months=60, months_elapsed=12, method="straight_line",
        )
        assert result["accumulated_depreciation"] == Decimal("18000.00")
        assert result["net_book_value"] == Decimal("82000.00")
        assert result["fully_depreciated"] is False

    def test_fully_depreciated(self):
        from app.services.v2.fixed_assets import asset_service
        result = asset_service.compute_depreciation(
            acquisition_cost=100000, residual_value=10000,
            useful_life_months=60, months_elapsed=60, method="straight_line",
        )
        assert result["fully_depreciated"] is True
        assert result["net_book_value"] == Decimal("10000.00")

    def test_declining_balance(self):
        from app.services.v2.fixed_assets import asset_service
        result = asset_service.compute_depreciation(
            acquisition_cost=100000, residual_value=10000,
            useful_life_months=60, months_elapsed=1, method="declining_balance",
        )
        assert result["current_month_depreciation"] > Decimal("0")
        assert result["net_book_value"] < Decimal("100000")


class TestTaxEngine:
    def test_vat_calculation(self):
        from app.services.v2.tax_engine import tax_engine
        result = tax_engine.calculate_vat(10000, "V18")
        assert result["vat"] == "1800.00"
        assert result["gross"] == "11800.00"

    def test_vat_exempt(self):
        from app.services.v2.tax_engine import tax_engine
        result = tax_engine.calculate_vat(10000, "V0")
        assert result["vat"] == "0.00"

    def test_vat_reverse(self):
        from app.services.v2.tax_engine import tax_engine
        result = tax_engine.extract_vat_from_gross(11800, "V18")
        assert result["net"] == "10000.00"
        assert result["vat"] == "1800.00"

    def test_cit_estonian_model(self):
        from app.services.v2.tax_engine import tax_engine
        result = tax_engine.calculate_cit(1000000)
        assert result["cit_amount"] == "150000.00"
        assert result["net_distribution"] == "850000.00"

    def test_excise_petrol(self):
        from app.services.v2.tax_engine import tax_engine
        result = tax_engine.calculate_excise(100000, "petrol")
        assert result["excise_amount"] == "40000.00"

    def test_excise_diesel(self):
        from app.services.v2.tax_engine import tax_engine
        result = tax_engine.calculate_excise(100000, "diesel")
        assert result["excise_amount"] == "30000.00"

    def test_tax_codes_list(self):
        from app.services.v2.tax_engine import tax_engine
        codes = tax_engine.get_tax_codes()
        assert len(codes) >= 8
        code_names = [c["code"] for c in codes]
        assert "V18" in code_names
        assert "CIT15" in code_names


class TestBankReconciliation:
    def test_exact_match(self):
        from app.services.v2.bank_reconciliation import bank_rec_service
        result = bank_rec_service.reconcile(
            bank_lines=[{"date": "2026-01-15", "amount": 1000, "reference": "INV-001"}],
            gl_entries=[{"date": "2026-01-15", "amount": 1000, "reference": "INV-001"}],
        )
        assert result["summary"]["matched_count"] == 1
        assert result["matched"][0]["match_type"] == "exact_reference"

    def test_fuzzy_match(self):
        from app.services.v2.bank_reconciliation import bank_rec_service
        result = bank_rec_service.reconcile(
            bank_lines=[{"date": "2026-01-15", "amount": 5000, "reference": ""}],
            gl_entries=[{"date": "2026-01-17", "amount": 5000, "reference": ""}],
            date_tolerance_days=3,
        )
        assert result["summary"]["matched_count"] == 1
        assert result["matched"][0]["match_type"] == "fuzzy_date_amount"

    def test_no_match(self):
        from app.services.v2.bank_reconciliation import bank_rec_service
        result = bank_rec_service.reconcile(
            bank_lines=[{"date": "2026-01-15", "amount": 1000, "reference": ""}],
            gl_entries=[{"date": "2026-01-15", "amount": 2000, "reference": ""}],
        )
        assert result["summary"]["matched_count"] == 0
        assert len(result["unmatched_bank"]) == 1

    def test_empty_inputs(self):
        from app.services.v2.bank_reconciliation import bank_rec_service
        result = bank_rec_service.reconcile(bank_lines=[], gl_entries=[])
        assert result["summary"]["matched_count"] == 0


class TestIncomeStatementV2:
    def test_all_decimal(self):
        from app.services.v2.income_statement import build_income_statement
        stmt = build_income_statement(
            revenue_items=[{"product": "Test", "category": "Revenue Whsale Diesel", "net": 1000000}],
            cogs_items=[{"product": "Test", "category": "COGS Whsale Diesel",
                          "col6_amount": 800000, "col7310_amount": 0, "col8230_amount": 0, "total_cogs": 800000}],
            ga_expense_items=[{"account_code": "7310", "amount": 50000}],
        )
        assert isinstance(stmt.total_revenue, Decimal)
        assert isinstance(stmt.net_profit, Decimal)
        assert stmt.total_revenue == Decimal("1000000")

    def test_cogs_enrichment(self):
        from app.services.v2.income_statement import build_income_statement
        stmt = build_income_statement(
            revenue_items=[], cogs_items=[
                {"product": "A", "category": "COGS Whsale Diesel",
                 "col6_amount": 500000, "col7310_amount": 0, "col8230_amount": 0, "total_cogs": 500000},
            ],
            ga_expense_items=[],
            tb_col7310_total=100000,
        )
        assert stmt.cogs_col7310_total == Decimal("100000")


class TestCashFlowV2:
    def test_imports(self):
        from app.services.v2.cash_flow import CashFlowStatement, build_cash_flow
        cfs = CashFlowStatement()
        assert isinstance(cfs.net_income, Decimal)
        assert cfs.net_income == Decimal("0")

    def test_to_rows_returns_strings(self):
        from app.services.v2.cash_flow import CashFlowStatement
        cfs = CashFlowStatement()
        cfs.net_income = Decimal("1000000")
        rows = cfs.to_rows()
        assert len(rows) > 0
        # Check amounts are strings
        for row in rows:
            assert isinstance(row["ac"], str)


class TestComplianceEngine:
    def test_valid_entry_passes(self):
        import asyncio
        from app.services.v2.compliance import compliance_engine

        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                result = await compliance_engine.validate_journal_entry({
                    "description": "Test entry",
                    "posting_date": "2026-01-15",
                    "lines": [
                        {"account_code": "1110", "debit": 1000, "credit": 0},
                        {"account_code": "6110", "debit": 0, "credit": 1000},
                    ],
                }, db)
                assert result["passed"] is True
                assert result["critical_count"] == 0
        asyncio.get_event_loop().run_until_complete(_test())

    def test_unbalanced_entry_fails(self):
        import asyncio
        from app.services.v2.compliance import compliance_engine

        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                result = await compliance_engine.validate_journal_entry({
                    "description": "Bad entry",
                    "lines": [
                        {"account_code": "1110", "debit": 1000, "credit": 0},
                        {"account_code": "6110", "debit": 0, "credit": 500},
                    ],
                }, db)
                assert result["passed"] is False
                assert result["critical_count"] >= 1
        asyncio.get_event_loop().run_until_complete(_test())

    def test_invalid_account_fails(self):
        import asyncio
        from app.services.v2.compliance import compliance_engine

        async def _test():
            from app.database import AsyncSessionLocal, engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                result = await compliance_engine.validate_journal_entry({
                    "description": "Bad account",
                    "lines": [
                        {"account_code": "INVALID", "debit": 100, "credit": 0},
                        {"account_code": "6110", "debit": 0, "credit": 100},
                    ],
                }, db)
                assert result["passed"] is False
        asyncio.get_event_loop().run_until_complete(_test())


class TestLineageService:
    def test_pl_code_resolution(self):
        from app.services.v2.lineage_service import lineage_service
        accounts = lineage_service._resolve_pl_code_to_accounts("REV")
        assert "6" in accounts

        cogs_accounts = lineage_service._resolve_pl_code_to_accounts("COGS")
        assert "7" in cogs_accounts

    def test_unknown_code_returns_empty(self):
        from app.services.v2.lineage_service import lineage_service
        accounts = lineage_service._resolve_pl_code_to_accounts("NONEXISTENT")
        assert accounts == []


class TestTBStatements:
    def test_decimal_conversion(self):
        from app.services.v2.tb_statements import DecimalStatements
        ds = DecimalStatements()
        assert isinstance(ds.revenue, Decimal)
        assert ds.revenue == Decimal("0")

    def test_financials_dict(self):
        from app.services.v2.tb_statements import DecimalStatements
        ds = DecimalStatements()
        ds.revenue = Decimal("50000000")
        ds.total_assets = Decimal("100000000")
        result = ds.to_financials_dict()
        assert result["revenue"] == "50000000.00"
        assert isinstance(result["revenue"], str)
