"""
FinAI v2 Period Comparison — Compare by period name, not dataset ID.
=====================================================================
Fixes the stress test finding: "/pl/compare requires dataset_ids users don't know."

Provides:
- Period name → dataset_id resolution
- Multi-period P&L trend (3+ periods)
- Variance analysis with materiality thresholds

Public API:
    from app.services.v2.period_compare import resolve_period_to_dataset, list_available_periods
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin

logger = logging.getLogger(__name__)


async def list_available_periods(db: AsyncSession) -> List[Dict[str, Any]]:
    """List all available periods with their dataset IDs for UI dropdowns."""
    from app.models.all_models import Dataset

    result = await db.execute(
        select(Dataset.id, Dataset.period, Dataset.name, Dataset.company, Dataset.is_active)
        .order_by(Dataset.id.desc())
    )
    periods = []
    seen = set()
    for row in result.all():
        period = row.period or "Unknown"
        if period not in seen:
            seen.add(period)
            periods.append({
                "dataset_id": row.id,
                "period": period,
                "dataset_name": row.name,
                "company": row.company,
                "is_active": row.is_active,
            })
    return periods


async def resolve_period_to_dataset(
    period_name: str, db: AsyncSession
) -> Optional[int]:
    """Resolve a period name (e.g., 'January 2026') to dataset_id.

    Returns None if no matching dataset found.
    """
    from app.models.all_models import Dataset

    result = await db.execute(
        select(Dataset.id).where(Dataset.period == period_name).limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def compare_periods_by_name(
    period_1: str,
    period_2: str,
    db: AsyncSession,
    materiality_threshold: Decimal = Decimal("5"),
) -> Dict[str, Any]:
    """Compare two periods by name, with variance analysis.

    Args:
        period_1: Prior period name (e.g., "December 2025")
        period_2: Current period name (e.g., "January 2026")
        materiality_threshold: % threshold for flagging material variances

    Returns:
        Dict with prior/current P&L, variances, and material flags.
    """
    ds_1 = await resolve_period_to_dataset(period_1, db)
    ds_2 = await resolve_period_to_dataset(period_2, db)

    if not ds_1:
        return {"error": f"Period '{period_1}' not found. Use /api/analytics/periods to see available periods."}
    if not ds_2:
        return {"error": f"Period '{period_2}' not found. Use /api/analytics/periods to see available periods."}

    # Build P&L for each period
    from app.services.v2.income_statement import build_income_statement
    from app.models.all_models import RevenueItem, COGSItem, GAExpenseItem, TrialBalanceItem

    async def _build_pl(ds_id: int, period: str):
        rev = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == ds_id))).scalars().all()
        cogs = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == ds_id))).scalars().all()
        ga = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id))).scalars().all()

        # TB 7310 enrichment
        tb_7310 = (await db.execute(
            select(TrialBalanceItem).where(
                TrialBalanceItem.dataset_id == ds_id,
                TrialBalanceItem.account_code == '7310',
                TrialBalanceItem.hierarchy_level == 1,
            )
        )).scalars().all()
        tb_col7310 = sum(float(t.turnover_debit or 0) for t in tb_7310)

        return build_income_statement(rev, cogs, ga, period, tb_col7310_total=tb_col7310)

    stmt_1 = await _build_pl(ds_1, period_1)
    stmt_2 = await _build_pl(ds_2, period_2)

    # Compute variances
    variances = []
    key_metrics = [
        ("Revenue", stmt_1.total_revenue, stmt_2.total_revenue),
        ("COGS", stmt_1.total_cogs, stmt_2.total_cogs),
        ("Gross Profit", stmt_1.total_gross_profit, stmt_2.total_gross_profit),
        ("G&A Expenses", stmt_1.ga_expenses, stmt_2.ga_expenses),
        ("EBITDA", stmt_1.ebitda, stmt_2.ebitda),
        ("Net Profit", stmt_1.net_profit, stmt_2.net_profit),
        ("WS Margin", stmt_1.margin_wholesale_total, stmt_2.margin_wholesale_total),
        ("RT Margin", stmt_1.margin_retail_total, stmt_2.margin_retail_total),
    ]

    for label, prior, current in key_metrics:
        change = current - prior
        pct = safe_divide(change * Decimal("100"), abs(prior)) if prior != 0 else None

        is_material = pct is not None and abs(pct) >= materiality_threshold
        variances.append({
            "metric": label,
            "prior": str(round_fin(prior)),
            "current": str(round_fin(current)),
            "change": str(round_fin(change)),
            "change_pct": str(round_fin(pct)) if pct is not None else "N/A",
            "is_material": is_material,
            "direction": "up" if change > 0 else "down" if change < 0 else "flat",
        })

    material_count = sum(1 for v in variances if v["is_material"])

    return {
        "period_1": period_1,
        "period_2": period_2,
        "dataset_id_1": ds_1,
        "dataset_id_2": ds_2,
        "prior_pl": stmt_1.to_rows(),
        "current_pl": stmt_2.to_rows(),
        "variances": variances,
        "material_variances": material_count,
        "materiality_threshold_pct": str(materiality_threshold),
    }
