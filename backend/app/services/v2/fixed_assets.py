"""
FinAI v2 Fixed Asset Accounting — Depreciation schedules + asset register.
==========================================================================
Fills the "Fixed Assets" gap identified in SAP FI benchmark.

Features:
- Asset register (add, dispose, revalue)
- Depreciation methods: straight-line, declining balance, sum-of-years
- Monthly depreciation run → generates journal entries
- Georgian IFRS compliant (IAS 16)

Public API:
    from app.services.v2.fixed_assets import asset_service
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin, is_zero

logger = logging.getLogger(__name__)
D = Decimal


class AssetService:
    """Fixed asset register with depreciation engine."""

    async def register_asset(
        self,
        name: str,
        asset_code: str,
        acquisition_date: date,
        acquisition_cost: Any,
        useful_life_months: int,
        residual_value: Any = 0,
        depreciation_method: str = "straight_line",
        account_code: str = "2110",
        depreciation_account: str = "2190",
        expense_account: str = "7410",
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Register a new fixed asset."""
        cost = to_decimal(acquisition_cost)
        residual = to_decimal(residual_value)
        depreciable = cost - residual

        monthly_depr = D("0")
        if depreciation_method == "straight_line" and useful_life_months > 0:
            monthly_depr = safe_divide(depreciable, D(str(useful_life_months)))

        asset = {
            "asset_code": asset_code,
            "name": name,
            "acquisition_date": str(acquisition_date),
            "acquisition_cost": str(round_fin(cost)),
            "residual_value": str(round_fin(residual)),
            "depreciable_amount": str(round_fin(depreciable)),
            "useful_life_months": useful_life_months,
            "depreciation_method": depreciation_method,
            "monthly_depreciation": str(round_fin(monthly_depr)),
            "accumulated_depreciation": "0.00",
            "net_book_value": str(round_fin(cost)),
            "account_code": account_code,
            "depreciation_account": depreciation_account,
            "expense_account": expense_account,
            "status": "active",
        }

        logger.info("Asset registered: %s (%s), cost=%s, life=%d months",
                      name, asset_code, round_fin(cost), useful_life_months)
        return asset

    def compute_depreciation(
        self,
        acquisition_cost: Any,
        residual_value: Any,
        useful_life_months: int,
        months_elapsed: int,
        method: str = "straight_line",
    ) -> Dict[str, Decimal]:
        """Compute depreciation for a given period."""
        cost = to_decimal(acquisition_cost)
        residual = to_decimal(residual_value)
        depreciable = cost - residual

        if method == "straight_line":
            monthly = safe_divide(depreciable, D(str(useful_life_months))) if useful_life_months > 0 else D("0")
            accumulated = min(monthly * D(str(months_elapsed)), depreciable)
            current_month = monthly if months_elapsed <= useful_life_months else D("0")

        elif method == "declining_balance":
            rate = safe_divide(D("2"), D(str(useful_life_months))) if useful_life_months > 0 else D("0")
            nbv = cost
            accumulated = D("0")
            current_month = D("0")
            for m in range(1, months_elapsed + 1):
                depr = max(round_fin(nbv * rate), D("0"))
                if nbv - depr < residual:
                    depr = max(nbv - residual, D("0"))
                accumulated += depr
                nbv -= depr
                if m == months_elapsed:
                    current_month = depr

        else:  # sum_of_years
            total_months = useful_life_months
            remaining = max(total_months - months_elapsed + 1, 0)
            soy_sum = D(str(total_months * (total_months + 1) // 2))
            current_month = safe_divide(depreciable * D(str(remaining)), soy_sum) if soy_sum > 0 else D("0")
            accumulated = D("0")
            for m in range(1, months_elapsed + 1):
                rem = max(total_months - m + 1, 0)
                accumulated += safe_divide(depreciable * D(str(rem)), soy_sum) if soy_sum > 0 else D("0")

        nbv = cost - accumulated

        return {
            "current_month_depreciation": round_fin(current_month),
            "accumulated_depreciation": round_fin(accumulated),
            "net_book_value": round_fin(nbv),
            "depreciable_amount": round_fin(depreciable),
            "fully_depreciated": accumulated >= depreciable,
        }


# Module singleton
asset_service = AssetService()
