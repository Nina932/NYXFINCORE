"""
FinAI Foundry — P&L Comparison Service
=========================================
Produces the 7-column P&L format matching the NYX Core Thinker template:
Code | Line Item | Prior Year | Actual | Plan | Variance | Var%

Supports:
- Single period P&L
- Period vs prior year comparison
- Period vs budget comparison
- Multi-period trend (3+ periods)

Reads from BOTH paths:
1. Analytics path (RevenueItem/COGSItem) for product-level detail
2. GL path (posting_lines) for account-level totals

Public API:
    from app.services.v2.pl_comparison import pl_comparison
    result = await pl_comparison.full_pl(period, prior_period, db)
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, is_zero

logger = logging.getLogger(__name__)
D = Decimal


class PLComparisonService:
    """Produces the full 7-column P&L matching NYX Core Thinker template."""

    async def full_pl(
        self,
        dataset_id: int,
        prior_dataset_id: Optional[int] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """
        Generate full P&L with prior year + variance.

        Returns rows in the exact NYX Core Thinker format:
        [{code, label, actual, prior, plan, variance, variance_pct, level, bold, children}]
        """
        if not db:
            raise ValueError("DB session required")

        # Build current period P&L
        current = await self._build_pl_from_dataset(dataset_id, db)

        # Build prior period P&L (if available)
        prior = {}
        if prior_dataset_id:
            prior = await self._build_pl_from_dataset(prior_dataset_id, db)

        # Build comparison rows
        rows = self._build_comparison_rows(current, prior)

        return {
            "period": current.get("_period", ""),
            "prior_period": prior.get("_period", ""),
            "currency": current.get("_currency", "GEL"),
            "company": current.get("_company", ""),
            "rows": rows,
            "summary": {
                "revenue": current.get("total_revenue", 0),
                "cogs": current.get("total_cogs", 0),
                "gross_profit": current.get("gross_profit", 0),
                "ebitda": current.get("ebitda", 0),
                "net_profit": current.get("net_profit", 0),
                "prior_revenue": prior.get("total_revenue", 0),
                "prior_net_profit": prior.get("net_profit", 0),
            },
        }

    async def _build_pl_from_dataset(self, dataset_id: int, db: AsyncSession) -> Dict:
        """Build P&L data from a dataset (using income_statement builder)."""
        from app.models.all_models import Dataset, RevenueItem, COGSItem, GAExpenseItem, TrialBalanceItem
        from app.services.income_statement import build_income_statement

        ds = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
        if not ds:
            return {}

        rev = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == dataset_id))).scalars().all()
        cogs = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == dataset_id))).scalars().all()
        ga = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id))).scalars().all()

        # Get TB 7310 for enrichment
        tb_7310 = (await db.execute(
            select(TrialBalanceItem).where(
                TrialBalanceItem.dataset_id == dataset_id,
                TrialBalanceItem.account_code == '7310',
                TrialBalanceItem.hierarchy_level == 1,
            )
        )).scalars().all()
        tb_col7310 = sum(float(t.turnover_debit or 0) for t in tb_7310)

        stmt = build_income_statement(rev, cogs, ga, ds.period or "", ds.currency or "GEL", tb_col7310_total=tb_col7310)

        # Extract all values into a flat dict
        result = {
            "_period": ds.period, "_currency": ds.currency, "_company": ds.company,
            "total_revenue": float(stmt.total_revenue) if hasattr(stmt.total_revenue, '__float__') else stmt.total_revenue,
        }

        # Map all statement fields
        for attr in ["revenue_wholesale_petrol", "revenue_wholesale_diesel", "revenue_wholesale_bitumen",
                      "revenue_wholesale_cng", "revenue_wholesale_lpg", "revenue_wholesale_total",
                      "revenue_retail_petrol", "revenue_retail_diesel", "revenue_retail_cng",
                      "revenue_retail_lpg", "revenue_retail_total", "other_revenue_total", "total_revenue",
                      "cogs_wholesale_petrol", "cogs_wholesale_diesel", "cogs_wholesale_bitumen",
                      "cogs_wholesale_cng", "cogs_wholesale_lpg", "cogs_wholesale_total",
                      "cogs_retail_petrol", "cogs_retail_diesel", "cogs_retail_cng",
                      "cogs_retail_lpg", "cogs_retail_total", "other_cogs_total", "total_cogs",
                      "margin_wholesale_petrol", "margin_wholesale_diesel", "margin_wholesale_bitumen",
                      "margin_wholesale_cng", "margin_wholesale_lpg", "margin_wholesale_total",
                      "margin_retail_petrol", "margin_retail_diesel", "margin_retail_cng",
                      "margin_retail_lpg", "margin_retail_total", "total_gross_margin", "total_gross_profit",
                      "ga_expenses", "ebitda", "da_expenses", "ebit",
                      "finance_income", "finance_expense", "finance_net",
                      "ebt", "tax_expense", "net_profit"]:
            val = getattr(stmt, attr, 0)
            result[attr] = float(val) if hasattr(val, '__float__') else (float(str(val)) if val else 0)

        # G&A breakdown
        result["ga_breakdown"] = {}
        for code, amt in (stmt.ga_breakdown if hasattr(stmt, 'ga_breakdown') else {}).items():
            result["ga_breakdown"][code] = float(amt) if hasattr(amt, '__float__') else (float(str(amt)) if amt else 0)

        # D&A breakdown
        result["da_breakdown"] = {}
        for code, amt in (stmt.da_breakdown if hasattr(stmt, 'da_breakdown') else {}).items():
            result["da_breakdown"][code] = float(amt) if hasattr(amt, '__float__') else (float(str(amt)) if amt else 0)

        # Gross profit calculation
        result["gross_profit"] = result["total_gross_profit"]

        return result

    def _build_comparison_rows(self, current: Dict, prior: Dict) -> List[Dict]:
        """Build the 7-column comparison rows matching NYX Core Thinker P&L template."""
        rows = []

        def add(code, label, cur_key, level=0, bold=False, sep=False, sign=1):
            actual = current.get(cur_key, 0)
            prior_val = prior.get(cur_key, 0)
            variance = actual - prior_val if prior_val else 0
            var_pct = (variance / abs(prior_val) * 100) if prior_val and prior_val != 0 else 0

            rows.append({
                "c": code, "l": label,
                "ac": round(actual, 2),
                "pr": round(prior_val, 2),
                "pl": 0,  # Budget (future)
                "var": round(variance, 2),
                "var_pct": round(var_pct, 1),
                "lvl": level, "bold": bold, "sep": sep, "s": sign,
            })

        # Revenue
        add("REV", "REVENUE", "total_revenue", 0, True, True, 1)
        add("REV.W", "Revenue Wholesale", "revenue_wholesale_total", 1, True)
        add("REV.W.P", "Revenue Whsale Petrol (Lari)", "revenue_wholesale_petrol", 2)
        add("REV.W.D", "Revenue Whsale Diesel (Lari)", "revenue_wholesale_diesel", 2)
        add("REV.W.B", "Revenue Whsale Bitumen (Lari)", "revenue_wholesale_bitumen", 2)
        add("REV.W.CNG", "Revenue Whsale CNG (Lari)", "revenue_wholesale_cng", 2)
        add("REV.W.LPG", "Revenue Whsale LPG (Lari)", "revenue_wholesale_lpg", 2)
        add("REV.R", "Revenue Retail", "revenue_retail_total", 1, True)
        add("REV.R.P", "Revenue Retial Petrol (Lari)", "revenue_retail_petrol", 2)
        add("REV.R.D", "Revenue Retial Diesel (Lari)", "revenue_retail_diesel", 2)
        add("REV.R.CNG", "Revenue Retial CNG (Lari)", "revenue_retail_cng", 2)
        add("REV.R.LPG", "Revenue Retial LPG (Lari)", "revenue_retail_lpg", 2)

        # COGS
        add("COGS", "COST OF GOODS SOLD", "total_cogs", 0, True, True, -1)
        add("COGS.W", "COGS Wholesale", "cogs_wholesale_total", 1, True, False, -1)
        add("COGS.W.P", "COGS Whsale Petrol (Lari)", "cogs_wholesale_petrol", 2, False, False, -1)
        add("COGS.W.D", "COGS Whsale Diesel (Lari)", "cogs_wholesale_diesel", 2, False, False, -1)
        add("COGS.W.B", "COGS Whsale Bitumen (Lari)", "cogs_wholesale_bitumen", 2, False, False, -1)
        add("COGS.W.CNG", "COGS Whsale CNG (Lari)", "cogs_wholesale_cng", 2, False, False, -1)
        add("COGS.W.LPG", "COGS Whsale LPG (Lari)", "cogs_wholesale_lpg", 2, False, False, -1)
        add("COGS.R", "COGS Retail", "cogs_retail_total", 1, True, False, -1)
        add("COGS.R.P", "COGS Retial Petrol (Lari)", "cogs_retail_petrol", 2, False, False, -1)
        add("COGS.R.D", "COGS Retial Diesel (Lari)", "cogs_retail_diesel", 2, False, False, -1)
        add("COGS.R.CNG", "COGS Retial CNG (Lari)", "cogs_retail_cng", 2, False, False, -1)
        add("COGS.R.LPG", "COGS Retial LPG (Lari)", "cogs_retail_lpg", 2, False, False, -1)
        add("COGS.O", "Other COGS", "other_cogs_total", 1, False, False, -1)

        # Gross Margin
        add("GM", "GROSS MARGIN", "total_gross_margin", 0, True, True)
        add("GM.W", "Gr. Margin Wholesale", "margin_wholesale_total", 1, True)
        add("GM.W.P", "Gr. Margin Whsale Petrol", "margin_wholesale_petrol", 2)
        add("GM.W.D", "Gr. Margin Whsale Diesel", "margin_wholesale_diesel", 2)
        add("GM.W.B", "Gr. Margin Whsale Bitumen", "margin_wholesale_bitumen", 2)
        add("GM.W.CNG", "Gr. Margin Whsale CNG", "margin_wholesale_cng", 2)
        add("GM.W.LPG", "Gr. Margin Whsale LPG", "margin_wholesale_lpg", 2)
        add("GM.R", "Gr. Margin Retail", "margin_retail_total", 1, True)
        add("GM.R.P", "Gr. Margin Retial Petrol", "margin_retail_petrol", 2)
        add("GM.R.D", "Gr. Margin Retial Diesel", "margin_retail_diesel", 2)
        add("GM.R.CNG", "Gr. Margin Retial CNG", "margin_retail_cng", 2)
        add("GM.R.LPG", "Gr. Margin Retial LPG", "margin_retail_lpg", 2)
        add("OR", "Other Revenue", "other_revenue_total", 1)
        add("TGP", "Total Gross Profit", "total_gross_profit", 0, True, True)

        # G&A breakdown
        add("GA", "General and Administrative Expenses", "ga_expenses", 0, True, False, -1)
        for code, amt in sorted(current.get("ga_breakdown", {}).items()):
            from app.services.file_parser import GA_ACCOUNT_NAMES
            name = GA_ACCOUNT_NAMES.get(code, code)
            actual_val = amt
            prior_val = prior.get("ga_breakdown", {}).get(code, 0)
            variance = actual_val - prior_val if prior_val else 0
            var_pct = (variance / abs(prior_val) * 100) if prior_val and prior_val != 0 else 0
            rows.append({
                "c": f"GA.{code}", "l": name,
                "ac": round(actual_val, 2), "pr": round(prior_val, 2),
                "pl": 0, "var": round(variance, 2), "var_pct": round(var_pct, 1),
                "lvl": 1, "bold": False, "sep": False, "s": -1,
            })

        # EBITDA → Net Profit
        add("EBITDA", "EBITDA", "ebitda", 0, True, True)

        add("DA", "Depreciation & Amortization", "da_expenses", 0, True, False, -1)
        da_breakdown = current.get("da_breakdown", {})
        # Only show child breakdown if there are multiple items (avoid visual duplication)
        if len(da_breakdown) > 1:
            for code, amt in sorted(da_breakdown.items()):
                actual_val = amt
                prior_val = prior.get("da_breakdown", {}).get(code, 0)
                variance = actual_val - prior_val if prior_val else 0
                var_pct = (variance / abs(prior_val) * 100) if prior_val and prior_val != 0 else 0
                # Use account code as label to differentiate from parent
                label = f"D&A — {code}" if code else "Depreciation & Amortization"
                rows.append({
                    "c": f"DA.{code}", "l": label,
                    "ac": round(actual_val, 2), "pr": round(prior_val, 2),
                    "pl": 0, "var": round(variance, 2), "var_pct": round(var_pct, 1),
                    "lvl": 1, "bold": False, "sep": False, "s": -1,
                })

        add("EBIT", "EBIT (Operating Profit)", "ebit", 0, True, True)
        add("FIN", "Finance Income / (Expense)", "finance_net", 0)
        add("FIN.I", "Finance Income", "finance_income", 1)
        add("FIN.E", "Finance Expense", "finance_expense", 1, False, False, -1)
        add("EBT", "Earnings Before Tax", "ebt", 0, True, True)
        add("TAX", "Income Tax", "tax_expense", 0, False, False, -1)
        add("NP", "Net Profit", "net_profit", 0, True, True)

        return rows

    async def multi_period_trend(
        self, dataset_ids: List[int], db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate trend data across multiple periods."""
        periods_data = []
        for ds_id in dataset_ids:
            pl = await self._build_pl_from_dataset(ds_id, db)
            if pl:
                periods_data.append({
                    "dataset_id": ds_id,
                    "period": pl.get("_period", ""),
                    "revenue": pl.get("total_revenue", 0),
                    "cogs": pl.get("total_cogs", 0),
                    "gross_profit": pl.get("total_gross_profit", 0),
                    "ga_expenses": pl.get("ga_expenses", 0),
                    "ebitda": pl.get("ebitda", 0),
                    "net_profit": pl.get("net_profit", 0),
                })
        return {"periods": periods_data, "count": len(periods_data)}

    # ── COGS Breakdown Comparison ─────────────────────────────────

    async def cogs_comparison(
        self, dataset_id: int, prior_dataset_id: Optional[int], db: AsyncSession
    ) -> Dict[str, Any]:
        """COGS breakdown with prior year + variance, by product and cost component."""
        from app.models.all_models import Dataset, COGSItem

        ds = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()

        # Current COGS
        items = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == dataset_id))).scalars().all()
        prior_items = []
        if prior_dataset_id:
            prior_items = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == prior_dataset_id))).scalars().all()

        # Index by category
        current_by_cat = {}
        for c in items:
            cat = c.category or "Other"
            current_by_cat[cat] = {
                "product": c.product or cat,
                "col6": float(c.col6_amount or 0),
                "col7310": float(c.col7310_amount or 0),
                "col8230": float(c.col8230_amount or 0),
                "total": float(c.total_cogs or 0),
                "segment": c.segment or "",
            }

        prior_by_cat = {}
        for c in prior_items:
            cat = c.category or "Other"
            prior_by_cat[cat] = {"total": float(c.total_cogs or 0), "col6": float(c.col6_amount or 0)}

        rows = []
        total_current = 0
        total_prior = 0

        for cat in sorted(set(list(current_by_cat.keys()) + list(prior_by_cat.keys()))):
            cur = current_by_cat.get(cat, {})
            pri = prior_by_cat.get(cat, {})
            actual = cur.get("total", 0)
            prior = pri.get("total", 0)
            variance = actual - prior
            var_pct = (variance / abs(prior) * 100) if prior else 0
            total_current += actual
            total_prior += prior

            rows.append({
                "category": cat,
                "product": cur.get("product", cat),
                "segment": cur.get("segment", ""),
                "col6_material": cur.get("col6", 0),
                "col7310_selling": cur.get("col7310", 0),
                "col8230_other": cur.get("col8230", 0),
                "actual": round(actual, 2),
                "prior": round(prior, 2),
                "variance": round(variance, 2),
                "variance_pct": round(var_pct, 1),
            })

        return {
            "period": ds.period if ds else "",
            "rows": sorted(rows, key=lambda r: -abs(r["actual"])),
            "total_actual": round(total_current, 2),
            "total_prior": round(total_prior, 2),
            "total_variance": round(total_current - total_prior, 2),
            "product_count": len(rows),
        }

    # ── Balance Sheet Comparison ──────────────────────────────────

    async def balance_sheet_comparison(
        self, dataset_id: int, prior_dataset_id: Optional[int], db: AsyncSession
    ) -> Dict[str, Any]:
        """Balance Sheet with prior year + variance."""
        from app.models.all_models import Dataset, BalanceSheetItem
        from sqlalchemy import func, Float as SAFloat

        ds = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()

        items = (await db.execute(
            select(BalanceSheetItem).where(BalanceSheetItem.dataset_id == dataset_id)
        )).scalars().all()

        prior_items = []
        if prior_dataset_id:
            prior_items = (await db.execute(
                select(BalanceSheetItem).where(BalanceSheetItem.dataset_id == prior_dataset_id)
            )).scalars().all()

        # Group by IFRS line item (raw values from DB — assets positive, L&E negative)
        current_by_ifrs = {}
        for b in items:
            ifrs = b.ifrs_line_item or b.account_code or "Other"
            if ifrs not in current_by_ifrs:
                current_by_ifrs[ifrs] = {"balance": 0, "code": b.account_code, "name": b.account_name or ""}
            current_by_ifrs[ifrs]["balance"] += float(b.closing_balance or 0)

        prior_by_ifrs = {}
        for b in prior_items:
            ifrs = b.ifrs_line_item or b.account_code or "Other"
            if ifrs not in prior_by_ifrs:
                prior_by_ifrs[ifrs] = {"balance": 0}
            prior_by_ifrs[ifrs]["balance"] += float(b.closing_balance or 0)

        # ── Equity fallback: if no 5xxx items in BalanceSheetItem, query GL posting_lines ──
        has_equity_items = any(
            (b.account_code or "").startswith("5") for b in items
        )
        equity_ifrs_keys = {"Share capital", "Retained earnings", "Other reserves"}
        has_equity_ifrs = bool(equity_ifrs_keys & set(current_by_ifrs.keys()))

        if not has_equity_items and not has_equity_ifrs:
            # Pull equity balances from posted journal entry lines (5xxx accounts)
            from app.models.all_models import JournalEntryRecord, PostingLineRecord
            equity_lines = (await db.execute(
                select(
                    PostingLineRecord.account_code,
                    PostingLineRecord.account_name,
                    func.sum(func.cast(PostingLineRecord.credit, SAFloat) - func.cast(PostingLineRecord.debit, SAFloat)).label("balance"),
                )
                .join(JournalEntryRecord, PostingLineRecord.journal_entry_id == JournalEntryRecord.id)
                .where(JournalEntryRecord.status == "posted")
                .where(PostingLineRecord.account_code.like("5%"))
                .group_by(PostingLineRecord.account_code, PostingLineRecord.account_name)
            )).all()

            _equity_ifrs_map = {
                "5110": "Share capital",
                "5210": "Retained earnings",
            }
            for row in equity_lines:
                code = row.account_code
                name = row.account_name or code
                balance = float(row.balance or 0)
                if balance == 0:
                    continue
                ifrs = _equity_ifrs_map.get(code, "Other reserves")
                # Store as negative (credit balance convention for L&E in raw data)
                if ifrs not in current_by_ifrs:
                    current_by_ifrs[ifrs] = {"balance": 0, "code": code, "name": name}
                current_by_ifrs[ifrs]["balance"] += balance  # already correctly signed from SQL (credit - debit for equity)
            logger.info("BS equity fallback: injected %d GL equity accounts", len(equity_lines))

        rows = []
        # Standard BS sections
        sections = {
            "Current Assets": ["Cash and cash equivalents", "Trade and other receivables", "Inventories", "Prepayments", "Other current assets"],
            "Non-Current Assets": ["Property, plant and equipment", "Intangible assets", "Deferred tax assets", "Other non-current assets"],
            "Current Liabilities": ["Trade and other payables", "Short-term borrowings", "Current tax liabilities", "Other current liabilities"],
            "Non-Current Liabilities": ["Long-term borrowings", "Deferred tax liabilities", "Other non-current liabilities"],
            "Equity": ["Share capital", "Retained earnings", "Other reserves"],
        }

        # Liability and equity are stored as negative (credit balances) in raw data.
        # For BS display, flip their sign so they show as positive and
        # the equation Assets = Liabilities + Equity holds.
        _credit_sections = {"Current Liabilities", "Non-Current Liabilities", "Equity"}

        grand_totals = {}  # section_name -> cur_total for equation check

        for section_name, ifrs_lines in sections.items():
            section_total_cur = 0
            section_total_pri = 0
            sign = -1 if section_name in _credit_sections else 1

            for ifrs in ifrs_lines:
                raw_cur = current_by_ifrs.get(ifrs, {}).get("balance", 0)
                raw_pri = prior_by_ifrs.get(ifrs, {}).get("balance", 0)
                cur_val = raw_cur * sign
                pri_val = raw_pri * sign
                if cur_val == 0 and pri_val == 0:
                    continue
                var = cur_val - pri_val
                var_pct = (var / abs(pri_val) * 100) if pri_val else 0
                section_total_cur += cur_val
                section_total_pri += pri_val

                rows.append({
                    "section": section_name,
                    "ifrs_line": ifrs,
                    "actual": round(cur_val, 2),
                    "prior": round(pri_val, 2),
                    "variance": round(var, 2),
                    "variance_pct": round(var_pct, 1),
                    "level": 1,
                })

            # Section total
            var = section_total_cur - section_total_pri
            var_pct = (var / abs(section_total_pri) * 100) if section_total_pri else 0
            rows.append({
                "section": section_name,
                "ifrs_line": f"TOTAL {section_name.upper()}",
                "actual": round(section_total_cur, 2),
                "prior": round(section_total_pri, 2),
                "variance": round(var, 2),
                "variance_pct": round(var_pct, 1),
                "level": 0,
                "bold": True,
            })
            grand_totals[section_name] = section_total_cur

        # Compute grand totals for BS equation
        total_assets = grand_totals.get("Current Assets", 0) + grand_totals.get("Non-Current Assets", 0)
        total_liabilities = grand_totals.get("Current Liabilities", 0) + grand_totals.get("Non-Current Liabilities", 0)
        total_equity = grand_totals.get("Equity", 0)

        # Add TOTAL ASSETS and TOTAL L+E rows
        rows.append({
            "section": "Total",
            "ifrs_line": "TOTAL ASSETS",
            "actual": round(total_assets, 2),
            "prior": 0,
            "variance": 0, "variance_pct": 0,
            "level": 0, "bold": True,
        })
        rows.append({
            "section": "Total",
            "ifrs_line": "TOTAL LIABILITIES + EQUITY",
            "actual": round(total_liabilities + total_equity, 2),
            "prior": 0,
            "variance": 0, "variance_pct": 0,
            "level": 0, "bold": True,
        })

        # Unmatched items (not in standard sections)
        matched = set()
        for lines in sections.values():
            matched.update(lines)
        for ifrs, data in current_by_ifrs.items():
            if ifrs not in matched and data["balance"] != 0:
                rows.append({
                    "section": "Other",
                    "ifrs_line": ifrs,
                    "actual": round(data["balance"], 2),
                    "prior": round(prior_by_ifrs.get(ifrs, {}).get("balance", 0), 2),
                    "variance": 0, "variance_pct": 0, "level": 1,
                })

        bs_balanced = abs(total_assets - (total_liabilities + total_equity)) < 1.0

        return {
            "period": ds.period if ds else "",
            "rows": rows,
            "item_count": len(rows),
            "bs_items_current": len(items),
            "bs_items_prior": len(prior_items),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "total_equity": round(total_equity, 2),
            "bs_equation_balanced": bs_balanced,
        }

    # ── Revenue Analysis Comparison ───────────────────────────────

    async def revenue_comparison(
        self, dataset_id: int, prior_dataset_id: Optional[int], db: AsyncSession
    ) -> Dict[str, Any]:
        """Revenue breakdown by product/segment with prior + variance."""
        from app.models.all_models import Dataset, RevenueItem

        ds = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()

        items = (await db.execute(
            select(RevenueItem).where(RevenueItem.dataset_id == dataset_id, RevenueItem.eliminated == False)
        )).scalars().all()
        prior_items = []
        if prior_dataset_id:
            prior_items = (await db.execute(
                select(RevenueItem).where(RevenueItem.dataset_id == prior_dataset_id, RevenueItem.eliminated == False)
            )).scalars().all()

        # Index by product
        current_by_prod = {}
        for r in items:
            prod = r.product or "Other"
            if prod.lower() in ('итог', 'итого', 'total'):
                continue
            current_by_prod[prod] = {
                "gross": float(r.gross or 0),
                "vat": float(r.vat or 0),
                "net": float(r.net or 0),
                "segment": r.segment or "",
                "category": r.category or "",
            }

        prior_by_prod = {}
        for r in prior_items:
            prod = r.product or "Other"
            if prod.lower() in ('итог', 'итого', 'total'):
                continue
            prior_by_prod[prod] = {"net": float(r.net or 0)}

        rows = []
        total_cur = 0
        total_pri = 0

        for prod in sorted(set(list(current_by_prod.keys()) + list(prior_by_prod.keys()))):
            cur = current_by_prod.get(prod, {})
            pri = prior_by_prod.get(prod, {})
            actual = cur.get("net", 0)
            prior = pri.get("net", 0)
            variance = actual - prior
            var_pct = (variance / abs(prior) * 100) if prior else 0
            total_cur += actual
            total_pri += prior

            rows.append({
                "product": prod,
                "segment": cur.get("segment", ""),
                "category": cur.get("category", ""),
                "gross": cur.get("gross", 0),
                "vat": cur.get("vat", 0),
                "actual_net": round(actual, 2),
                "prior_net": round(prior, 2),
                "variance": round(variance, 2),
                "variance_pct": round(var_pct, 1),
                "pct_of_total": round(actual / total_cur * 100, 1) if total_cur else 0,
            })

        # Sort by actual descending
        rows.sort(key=lambda r: -abs(r["actual_net"]))

        # Recalculate pct_of_total after sorting
        for r in rows:
            r["pct_of_total"] = round(r["actual_net"] / total_cur * 100, 1) if total_cur else 0

        return {
            "period": ds.period if ds else "",
            "rows": rows,
            "total_revenue_actual": round(total_cur, 2),
            "total_revenue_prior": round(total_pri, 2),
            "total_variance": round(total_cur - total_pri, 2),
            "product_count": len(rows),
            "by_segment": self._group_by_segment(rows),
        }

    def _group_by_segment(self, rows: List[Dict]) -> Dict[str, Dict]:
        """Group revenue rows by segment."""
        segments = {}
        for r in rows:
            seg = r.get("segment", "Other") or "Other"
            if seg not in segments:
                segments[seg] = {"total": 0, "prior": 0, "count": 0}
            segments[seg]["total"] += r["actual_net"]
            segments[seg]["prior"] += r["prior_net"]
            segments[seg]["count"] += 1
        return segments


# Module singleton
pl_comparison = PLComparisonService()
