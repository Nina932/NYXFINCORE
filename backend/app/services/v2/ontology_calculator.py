"""
Ontology Financial Calculator
==============================
Makes the ontology the SOURCE OF TRUTH for financial calculations.
After any P&L computation, results are written back to ontology KPI objects.
The NYX Core Thinker calculation rules are enforced here:
- GM = Revenue(W+R) - COGS(W+R)
- TGP = GM + Other Revenue
- EBITDA = TGP - GA Expenses
- EBIT = EBITDA - D&A
- Net Profit = EBIT + Finance Net - Tax
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OntologyCalculator:
    """
    Synchronizes P&L calculation results INTO the ontology so KPI objects
    carry REAL values.  After sync, any ontology query for KPI objects
    returns live financial data instead of static placeholders.
    """

    NYX_RULES: Dict[str, Dict[str, str]] = {
        "gross_margin": {
            "formula": "revenue_wholesale + revenue_retail - cogs_wholesale - cogs_retail",
            "description": "Core operating margin",
        },
        "total_gross_profit": {
            "formula": "gross_margin + other_revenue",
            "description": "Including ancillary revenue",
        },
        "ebitda": {
            "formula": "total_gross_profit - ga_expenses",
            "description": "Before depreciation",
        },
        "ebit": {
            "formula": "ebitda - da_expenses",
            "description": "Operating profit",
        },
        "net_profit": {
            "formula": "ebit + finance_net - tax",
            "description": "Bottom line",
        },
        "gross_margin_pct": {
            "formula": "gross_margin / revenue * 100",
            "description": "As % of revenue",
        },
        "net_margin_pct": {
            "formula": "net_profit / revenue * 100",
            "description": "As % of revenue",
        },
        "ebitda_margin_pct": {
            "formula": "ebitda / revenue * 100",
            "description": "EBITDA margin",
        },
    }

    # ── public API ────────────────────────────────────────────────────

    async def sync_to_ontology(self, db) -> Dict[str, Any]:
        """Compute P&L from entity tables and write results to ontology KPI objects."""
        from app.services.v2.pl_comparison import pl_comparison
        from app.models.all_models import Dataset
        from sqlalchemy import select
        from app.services.ontology_engine import ontology_registry

        # Find latest usable dataset
        ds = (
            await db.execute(
                select(Dataset)
                .where(Dataset.record_count > 0, Dataset.record_count < 10000)
                .order_by(Dataset.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not ds:
            ds = (
                await db.execute(
                    select(Dataset)
                    .where(Dataset.record_count > 0)
                    .order_by(Dataset.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if not ds:
            return {"error": "No dataset available", "synced": 0}

        # Compute full P&L
        try:
            pl_data = await pl_comparison.full_pl(ds.id, None, db)
        except Exception as exc:
            logger.warning("ontology_calculator: pl_comparison failed: %s", exc)
            return {"error": str(exc), "synced": 0}

        summary: dict = pl_data.get("summary", {})
        period: str = pl_data.get("period", "unknown")
        now_iso = datetime.now(timezone.utc).isoformat()

        # Ensure KPI type is registered
        self._ensure_kpi_type(ontology_registry)

        # Write each metric into the ontology
        updated = 0
        for metric, value in summary.items():
            if value is None:
                continue
            kpi_id = f"kpi_{metric}"
            props = {
                "metric": metric,
                "value": value,
                "period": period,
                "dataset_id": ds.id,
                "source": "pl_comparison",
                "updated_at": now_iso,
            }
            try:
                existing = ontology_registry.get_object(kpi_id)
                if existing:
                    ontology_registry.update_object(kpi_id, props)
                else:
                    ontology_registry.create_object(
                        "KPI",
                        properties=props,
                        object_id=kpi_id,
                    )
                updated += 1
            except Exception as exc:
                logger.debug("ontology_calculator: failed to sync %s: %s", metric, exc)

        # Also write derived percentage KPIs
        rev = summary.get("revenue", 0) or 0
        gp = summary.get("gross_profit", 0) or 0
        ebitda = summary.get("ebitda", 0) or 0
        np_val = summary.get("net_profit", 0) or 0

        derived = {}
        if rev:
            derived["gross_margin_pct"] = round(gp / rev * 100, 2)
            derived["net_margin_pct"] = round(np_val / rev * 100, 2)
            derived["ebitda_margin_pct"] = round(ebitda / rev * 100, 2)

        for metric, value in derived.items():
            kpi_id = f"kpi_{metric}"
            props = {
                "metric": metric,
                "value": value,
                "period": period,
                "dataset_id": ds.id,
                "source": "ontology_calculator",
                "updated_at": now_iso,
            }
            try:
                existing = ontology_registry.get_object(kpi_id)
                if existing:
                    ontology_registry.update_object(kpi_id, props)
                else:
                    ontology_registry.create_object(
                        "KPI",
                        properties=props,
                        object_id=kpi_id,
                    )
                updated += 1
            except Exception as exc:
                logger.debug("ontology_calculator: derived %s failed: %s", metric, exc)

        logger.info(
            "ontology_calculator: synced %d KPI objects (period=%s, dataset=%d)",
            updated, period, ds.id,
        )
        return {
            "synced": updated,
            "period": period,
            "dataset_id": ds.id,
            "rules": list(self.NYX_RULES.keys()),
            "metrics": {k: v for k, v in {**summary, **derived}.items() if v is not None},
        }

    def validate_calculations(self, financials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate that NYX Core Thinker calculation rules are satisfied.

        Returns a list of violations (empty list means all rules pass).
        Each violation dict has: rule, expected, actual, diff.
        """
        violations: List[Dict[str, Any]] = []
        TOLERANCE = 1000  # GEL — rounding tolerance

        rev = financials.get("revenue", 0) or 0
        cogs = financials.get("cogs", 0) or 0
        gp = financials.get("gross_profit", 0) or 0
        other_rev = financials.get("other_revenue", 0) or 0
        tgp = financials.get("total_gross_profit", 0) or 0
        ga = financials.get("ga_expenses", 0) or 0
        ebitda = financials.get("ebitda", 0) or 0
        da = financials.get("da_expenses", 0) or 0
        ebit = financials.get("ebit", 0) or 0
        finance_net = financials.get("finance_net", 0) or 0
        tax = financials.get("tax", 0) or 0
        np_val = financials.get("net_profit", 0) or 0

        def _check(rule_name: str, expected: float, actual: float):
            diff = abs(actual - expected)
            if diff > TOLERANCE:
                violations.append({
                    "rule": rule_name,
                    "expected": round(expected, 2),
                    "actual": round(actual, 2),
                    "diff": round(diff, 2),
                })

        if rev and cogs:
            _check("GP = Revenue - COGS", rev - cogs, gp)
        if gp and other_rev and tgp:
            _check("TGP = GP + Other Revenue", gp + other_rev, tgp)
        if (gp or tgp) and ga:
            base = tgp if tgp else gp
            _check("EBITDA = TGP/GP - GA Expenses", base - ga, ebitda)
        if ebitda and da:
            _check("EBIT = EBITDA - D&A", ebitda - da, ebit)
        if ebit:
            _check("Net Profit = EBIT + Finance - Tax + OtherInc - OtherExp", ebit + finance_net - tax + financials.get("other_income", 0) - financials.get("other_expense", 0), np_val)

        return violations

    def get_rules(self) -> Dict[str, Dict[str, str]]:
        """Return the NYX Core Thinker calculation rules."""
        return dict(self.NYX_RULES)

    # ── private helpers ───────────────────────────────────────────────

    @staticmethod
    def _ensure_kpi_type(registry) -> None:
        """Make sure the KPI ontology type exists."""
        if registry.get_type("KPI"):
            return
        try:
            from app.services.ontology_engine import OntologyType, PropertyDef, DataType
            registry.register_type(OntologyType(
                type_id="KPI",
                description="Key Performance Indicator — live financial metric",
                icon="trending-up",
                color="#10B981",
                properties_schema={
                    "metric": PropertyDef("metric", DataType.STRING, required=True, description="Metric name"),
                    "value": PropertyDef("value", DataType.FLOAT, description="Current value"),
                    "period": PropertyDef("period", DataType.STRING, description="Reporting period"),
                    "dataset_id": PropertyDef("dataset_id", DataType.INT, description="Source dataset ID"),
                    "source": PropertyDef("source", DataType.STRING, description="Computation source"),
                    "updated_at": PropertyDef("updated_at", DataType.STRING, description="Last update timestamp"),
                },
            ))
        except Exception as exc:
            logger.debug("_ensure_kpi_type failed: %s", exc)


# Singleton
ontology_calculator = OntologyCalculator()
