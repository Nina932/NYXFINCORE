from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/company-360", tags=["company-360"])


def _gen():
    from app.services.company_360 import company_360
    return company_360


@router.get("/overview")
async def company_overview(
    period: Optional[str] = Query(None, description="Reporting period"),
    company_id: int = Query(1, description="Company ID"),
):
    """Full company 360 overview: financials, KPIs, health, risks, recommendations."""
    try:
        gen = _gen()
        result = gen.generate(company_id=company_id, period=period)
        return result
    except Exception as e:
        logger.error(f"Company 360 overview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpis")
async def company_kpis(
    period: Optional[str] = Query(None, description="Reporting period"),
    company_id: int = Query(1, description="Company ID"),
):
    """Key performance indicators from the 360 view."""
    try:
        gen = _gen()
        full = gen.generate(company_id=company_id, period=period)
        return {
            "period": full.get("period"),
            "ratios": full.get("ratios", {}),
            "kpi_status": full.get("kpi_status", []),
            "financials": full.get("financials", {}),
            "trends": full.get("trends", {}),
        }
    except Exception as e:
        logger.error(f"Company 360 KPIs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def company_health(
    period: Optional[str] = Query(None, description="Reporting period"),
    company_id: int = Query(1, description="Company ID"),
):
    """Company health score, grade, risks, and recommendations."""
    try:
        gen = _gen()
        full = gen.generate(company_id=company_id, period=period)
        return {
            "period": full.get("period"),
            "health": full.get("health", {}),
            "risks": full.get("risks", []),
            "opportunities": full.get("opportunities", []),
            "recommendations": full.get("recommendations", []),
            "ai_narrative": full.get("ai_narrative", ""),
            "causal_drivers": full.get("causal_drivers", []),
        }
    except Exception as e:
        logger.error(f"Company 360 health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
async def seed_company_360():
    """Seed financial data so Company 360 has something to display."""
    try:
        from app.services.subledger import subledger_manager

        # Seed subledger if empty
        sl_result = {}
        if not subledger_manager.ar.list_all():
            sl_result = subledger_manager.populate_from_financials(
                pnl={
                    "revenue": 5_200_000,
                    "cogs": -3_900_000,
                    "gross_profit": 1_300_000,
                    "ebitda": 780_000,
                    "net_profit": 390_000,
                    "depreciation": 120_000,
                    "ga_expenses": 260_000,
                    "selling_expenses": 170_000,
                },
                balance_sheet={
                    "total_assets": 8_500_000,
                    "current_assets": 3_200_000,
                    "non_current_assets": 5_300_000,
                    "fixed_assets": 4_800_000,
                    "accounts_receivable": 980_000,
                    "inventory": 450_000,
                    "cash": 1_770_000,
                    "total_liabilities": 4_100_000,
                    "current_liabilities": 1_800_000,
                    "non_current_liabilities": 2_300_000,
                    "accounts_payable": 720_000,
                    "total_equity": 4_400_000,
                    "accumulated_depreciation": 960_000,
                },
            )

        # Also try to seed data_store with a company + financials
        try:
            from app.services.data_store import data_store
            data_store.save_company(1, {
                "id": 1,
                "name": settings.COMPANY_NAME,
                "industry": "fuel_distribution",
                "base_currency": "GEL",
            })
            data_store.save_financials(1, "2024-12", {
                "revenue": 5_200_000,
                "cogs": -3_900_000,
                "gross_profit": 1_300_000,
                "ebitda": 780_000,
                "net_profit": 390_000,
                "depreciation": 120_000,
                "ga_expenses": 260_000,
                "admin_expenses": 260_000,
                "selling_expenses": 170_000,
                "total_assets": 8_500_000,
                "current_assets": 3_200_000,
                "non_current_assets": 5_300_000,
                "fixed_assets": 4_800_000,
                "receivables": 980_000,
                "inventory": 450_000,
                "cash": 1_770_000,
                "total_liabilities": 4_100_000,
                "current_liabilities": 1_800_000,
                "non_current_liabilities": 2_300_000,
                "payables": 720_000,
                "total_equity": 4_400_000,
            })
            # Also add a prior period for trend / causal drivers
            data_store.save_financials(1, "2024-09", {
                "revenue": 4_800_000,
                "cogs": -3_700_000,
                "gross_profit": 1_100_000,
                "ebitda": 620_000,
                "net_profit": 280_000,
                "total_assets": 7_900_000,
                "current_assets": 2_900_000,
                "non_current_assets": 5_000_000,
                "total_liabilities": 3_800_000,
                "current_liabilities": 1_600_000,
                "total_equity": 4_100_000,
                "cash": 1_400_000,
            })
        except Exception as ds_err:
            logger.debug(f"Data store seeding partial: {ds_err}")

        return {
            "status": "seeded",
            "subledger": sl_result,
            "message": "Company 360 demo data seeded successfully",
        }
    except Exception as e:
        logger.error(f"Company 360 seed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
