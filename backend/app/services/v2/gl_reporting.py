"""
FinAI Foundry — GL Reporting Service
======================================
THE UNLOCK: Generate financial statements from posted journal entries.

This is what makes the journal system the SINGLE SOURCE OF TRUTH.
All reports (P&L, BS, TB, CF) are computed from posting_lines table.

Before: Dashboard reads from data_store (legacy SQLite) → journals invisible
After:  Dashboard reads from posting_lines (GL) → journals ARE the truth

Public API:
    from app.services.v2.gl_reporting import gl_reporting
    tb = await gl_reporting.trial_balance("2025-12", db)
    pl = await gl_reporting.income_statement("2025-12", db)
    bs = await gl_reporting.balance_sheet("2025-12", db)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, is_zero
from app.config import settings

logger = logging.getLogger(__name__)
D = Decimal


class GLReportingService:
    """Generates financial statements from posted journal entries (the GL)."""

    async def trial_balance(self, period: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Compute Trial Balance from posted journal entries for a period.
        This is the FOUNDATION — P&L and BS are derived from this.
        """
        from app.models.all_models import JournalEntryRecord, PostingLineRecord

        result = await db.execute(
            select(
                PostingLineRecord.account_code,
                PostingLineRecord.account_name,
                func.sum(PostingLineRecord.debit).label("total_debit"),
                func.sum(PostingLineRecord.credit).label("total_credit"),
            )
            .join(JournalEntryRecord, PostingLineRecord.journal_entry_id == JournalEntryRecord.id)
            .where(
                JournalEntryRecord.period == period,
                JournalEntryRecord.status == "posted",
            )
            .group_by(PostingLineRecord.account_code, PostingLineRecord.account_name)
            .order_by(PostingLineRecord.account_code)
        )

        accounts = []
        total_dr = D("0")
        total_cr = D("0")

        for row in result.all():
            dr = to_decimal(row.total_debit)
            cr = to_decimal(row.total_credit)
            net = dr - cr
            total_dr += dr
            total_cr += cr

            accounts.append({
                "account_code": row.account_code,
                "account_name": row.account_name or "",
                "debit": float(round_fin(dr)),
                "credit": float(round_fin(cr)),
                "net": float(round_fin(net)),
            })

        return {
            "period": period,
            "accounts": accounts,
            "total_debit": float(round_fin(total_dr)),
            "total_credit": float(round_fin(total_cr)),
            "is_balanced": abs(total_dr - total_cr) < D("1"),
            "account_count": len(accounts),
        }

    async def income_statement(self, period: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Generate P&L from posted journal entries.
        Revenue (6xxx credit turnovers), COGS (71xx debit), G&A (73-74xx), etc.
        """
        tb = await self.trial_balance(period, db)

        # Classify accounts into P&L lines using first digit(s)
        revenue = D("0")
        cogs = D("0")
        selling_expenses = D("0")
        admin_expenses = D("0")
        depreciation = D("0")
        finance_income = D("0")
        finance_expense = D("0")
        tax_expense = D("0")
        other_income = D("0")
        other_expense = D("0")

        revenue_items = []
        cogs_items = []
        expense_items = []

        for acct in tb["accounts"]:
            code = acct["account_code"]
            name = acct["account_name"]
            net = to_decimal(acct["net"])
            dr = to_decimal(acct["debit"])
            cr = to_decimal(acct["credit"])

            if not code or not code[0].isdigit():
                continue

            first = code[0]
            prefix2 = code[:2] if len(code) >= 2 else code

            # Revenue (class 6) — credit normal → revenue = credit - debit
            if first == "6":
                amt = cr - dr
                revenue += amt
                revenue_items.append({"account_code": code, "account_name": name, "amount": float(round_fin(amt))})

            # COGS (class 71) — debit normal → cogs = debit - credit
            elif prefix2 == "71":
                amt = dr - cr
                cogs += amt
                cogs_items.append({"account_code": code, "account_name": name, "amount": float(round_fin(amt))})

            # Selling expenses (73xx) — includes 7310 which is COGS for NYX Core Thinker
            elif prefix2 == "73":
                amt = dr - cr
                if code.startswith("7310"):
                    cogs += amt  # NYX-specific: 7310 is COGS component
                    cogs_items.append({"account_code": code, "account_name": name, "amount": float(round_fin(amt))})
                else:
                    selling_expenses += amt
                    expense_items.append({"account_code": code, "account_name": name, "amount": float(round_fin(amt)), "category": "selling"})

            # Admin / D&A (74xx)
            elif prefix2 == "74":
                amt = dr - cr
                if "ცვეთა" in name.lower() or "deprec" in name.lower() or "amort" in name.lower() or code.startswith("7410"):
                    depreciation += amt
                else:
                    admin_expenses += amt
                expense_items.append({"account_code": code, "account_name": name, "amount": float(round_fin(amt)), "category": "admin"})

            # Labour (72xx)
            elif prefix2 == "72":
                amt = dr - cr
                admin_expenses += amt
                expense_items.append({"account_code": code, "account_name": name, "amount": float(round_fin(amt)), "category": "labour"})

            # Finance expense (75xx)
            elif prefix2 == "75":
                finance_expense += dr - cr

            # Finance income (76xx)
            elif prefix2 == "76":
                finance_income += cr - dr

            # Tax (77xx, 92xx)
            elif prefix2 in ("77", "92"):
                tax_expense += dr - cr

            # Other income (81xx)
            elif prefix2 == "81":
                other_income += cr - dr

            # Other expense (82xx, 83xx)
            elif prefix2 in ("82", "83"):
                other_expense += dr - cr

            # Account 8230 — customs/duties → COGS
            elif code.startswith("8230"):
                amt = dr - cr
                cogs += amt
                cogs_items.append({"account_code": code, "account_name": name, "amount": float(round_fin(amt))})

        gross_profit = revenue - cogs
        ga_expenses = selling_expenses + admin_expenses
        ebitda = gross_profit - ga_expenses
        ebit = ebitda - depreciation
        finance_net = finance_income - finance_expense
        ebt = ebit + other_income - other_expense + finance_net
        net_profit = ebt - tax_expense

        def _f(v): return float(round_fin(v))

        return {
            "period": period,
            "source": "gl_journal_entries",
            "revenue": _f(revenue),
            "cogs": _f(cogs),
            "gross_profit": _f(gross_profit),
            "gross_margin_pct": float(safe_divide(gross_profit * D("100"), revenue)) if not is_zero(revenue) else 0,
            "selling_expenses": _f(selling_expenses),
            "admin_expenses": _f(admin_expenses),
            "ga_expenses": _f(ga_expenses),
            "ebitda": _f(ebitda),
            "ebitda_margin_pct": float(safe_divide(ebitda * D("100"), revenue)) if not is_zero(revenue) else 0,
            "depreciation": _f(depreciation),
            "ebit": _f(ebit),
            "finance_income": _f(finance_income),
            "finance_expense": _f(finance_expense),
            "other_income": _f(other_income),
            "other_expense": _f(other_expense),
            "ebt": _f(ebt),
            "tax_expense": _f(tax_expense),
            "net_profit": _f(net_profit),
            "net_margin_pct": float(safe_divide(net_profit * D("100"), revenue)) if not is_zero(revenue) else 0,
            "revenue_items": revenue_items,
            "cogs_items": cogs_items,
            "expense_items": expense_items,
            "journal_entry_count": len(tb["accounts"]),
        }

    async def balance_sheet(self, period: str, db: AsyncSession) -> Dict[str, Any]:
        """Generate Balance Sheet from posted journal entries."""
        tb = await self.trial_balance(period, db)

        cash = D("0")
        receivables = D("0")
        inventory = D("0")
        other_current_assets = D("0")
        fixed_assets = D("0")
        accumulated_depreciation = D("0")
        other_noncurrent_assets = D("0")
        payables = D("0")
        short_term_debt = D("0")
        other_current_liabilities = D("0")
        long_term_debt = D("0")
        other_noncurrent_liabilities = D("0")
        share_capital = D("0")
        retained_earnings = D("0")
        reserves = D("0")

        for acct in tb["accounts"]:
            code = acct["account_code"]
            net = to_decimal(acct["net"])  # DR - CR

            if not code or not code[0].isdigit():
                continue

            first = code[0]
            prefix2 = code[:2] if len(code) >= 2 else code

            if first in ("6", "7", "8", "9"):
                continue  # Skip P&L accounts

            # Class 1: Current Assets (debit normal)
            if first == "1":
                if prefix2 in ("11", "12"):
                    cash += net
                elif prefix2 in ("13", "14"):
                    receivables += net
                elif prefix2 in ("16",):
                    inventory += net
                else:
                    other_current_assets += net

            # Class 2: Noncurrent Assets
            elif first == "2":
                if prefix2 in ("21",):
                    fixed_assets += net
                elif prefix2 in ("22",):
                    accumulated_depreciation += net  # Contra (usually negative)
                else:
                    other_noncurrent_assets += net

            # Class 3: Current Liabilities (credit normal → net is negative for liabilities)
            elif first == "3":
                if prefix2 in ("31",):
                    payables += abs(net)
                elif prefix2 in ("32",):
                    short_term_debt += abs(net)
                else:
                    other_current_liabilities += abs(net)

            # Class 4: Noncurrent Liabilities
            elif first == "4":
                long_term_debt += abs(net)

            # Class 5: Equity
            elif first == "5":
                if prefix2 == "51":
                    share_capital += abs(net)
                elif prefix2 == "53":
                    retained_earnings += abs(net)
                elif prefix2 == "54":
                    reserves += abs(net)
                else:
                    retained_earnings += abs(net)

        def _f(v): return float(round_fin(v))

        total_current_assets = cash + receivables + inventory + other_current_assets
        total_noncurrent_assets = fixed_assets + accumulated_depreciation + other_noncurrent_assets
        total_assets = total_current_assets + total_noncurrent_assets
        total_current_liabilities = payables + short_term_debt + other_current_liabilities
        total_noncurrent_liabilities = long_term_debt
        total_liabilities = total_current_liabilities + total_noncurrent_liabilities
        total_equity = share_capital + retained_earnings + reserves

        return {
            "period": period,
            "source": "gl_journal_entries",
            "cash": _f(cash),
            "receivables": _f(receivables),
            "inventory": _f(inventory),
            "other_current_assets": _f(other_current_assets),
            "total_current_assets": _f(total_current_assets),
            "fixed_assets": _f(fixed_assets),
            "accumulated_depreciation": _f(accumulated_depreciation),
            "other_noncurrent_assets": _f(other_noncurrent_assets),
            "total_noncurrent_assets": _f(total_noncurrent_assets),
            "total_assets": _f(total_assets),
            "payables": _f(payables),
            "short_term_debt": _f(short_term_debt),
            "other_current_liabilities": _f(other_current_liabilities),
            "total_current_liabilities": _f(total_current_liabilities),
            "long_term_debt": _f(long_term_debt),
            "total_noncurrent_liabilities": _f(total_noncurrent_liabilities),
            "total_liabilities": _f(total_liabilities),
            "share_capital": _f(share_capital),
            "retained_earnings": _f(retained_earnings),
            "reserves": _f(reserves),
            "total_equity": _f(total_equity),
            "bs_equation_holds": abs(total_assets - total_liabilities - total_equity) < D("1"),
        }

    async def available_periods(self, db: AsyncSession) -> List[str]:
        """Get all periods that have posted journal entries."""
        from app.models.all_models import JournalEntryRecord
        result = await db.execute(
            select(JournalEntryRecord.period)
            .where(JournalEntryRecord.status == "posted")
            .group_by(JournalEntryRecord.period)
            .order_by(JournalEntryRecord.period)
        )
        return [row[0] for row in result.all() if row[0]]

    async def dashboard_from_gl(self, period: Optional[str], db: AsyncSession) -> Optional[Dict]:
        """Build dashboard data from GL. Returns None if no journal data for period."""
        periods = await self.available_periods(db)
        if not periods:
            return None

        target_period = period if period in periods else periods[-1]
        pl = await self.income_statement(target_period, db)
        bs = await self.balance_sheet(target_period, db)

        if pl["revenue"] == 0 and pl["cogs"] == 0:
            return None  # No meaningful data

        return {
            "empty": False,
            "source": "gl_journal_entries",
            "company": {"id": 0, "name": settings.COMPANY_NAME},
            "period": target_period,
            "periods_available": periods,
            "pnl": pl,
            "balance_sheet": bs,
            "revenue_breakdown": pl.get("revenue_items", []),
            "cogs_breakdown": pl.get("cogs_items", []),
            "pl_line_items": [],
            "revenue_by_category": {},
            "financials": pl,
            "intelligence": None,
        }


# Module singleton
gl_reporting = GLReportingService()
