"""
scenario_engine.py — What-if scenario engine for NYX Core Thinker.

Allows creating financial scenarios by modifying revenue, COGS, and G&A
parameters, then computing the resulting income statement deltas.
Supports percentage changes, absolute overrides, delta adjustments,
volume/price sensitivity, and new retail station modeling.
"""
import logging
import json
import copy
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.all_models import (
    Dataset, RevenueItem, COGSItem, GAExpenseItem, Scenario
)
from app.services.income_statement import build_income_statement, IncomeStatement

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

# Mapping from target-style segment names to the category strings used in the DB
# Note: the codebase uses "Whsale" and "Retial" (intentional legacy spelling)
_SEGMENT_MAP = {
    "wholesale": "Whsale",
    "retail": "Retial",
}

_PRODUCT_MAP = {
    "petrol": "Petrol",
    "diesel": "Diesel",
    "bitumen": "Bitumen",
    "cng": "CNG",
    "lpg": "LPG",
}

# Estimated monthly revenue per new retail station (in GEL)
_NEW_STATION_MONTHLY_REVENUE = 250_000.0

# Key fields to include in scenario comparisons
_COMPARISON_FIELDS = [
    "total_revenue",
    "revenue_wholesale_total", "revenue_wholesale_petrol",
    "revenue_wholesale_diesel", "revenue_wholesale_bitumen",
    "revenue_retail_total", "revenue_retail_petrol",
    "revenue_retail_diesel", "revenue_retail_cng", "revenue_retail_lpg",
    "other_revenue_total",
    "total_cogs",
    "cogs_wholesale_total", "cogs_wholesale_petrol",
    "cogs_wholesale_diesel", "cogs_wholesale_bitumen",
    "cogs_retail_total", "cogs_retail_petrol",
    "cogs_retail_diesel", "cogs_retail_cng", "cogs_retail_lpg",
    "other_cogs_total",
    "total_gross_margin",
    "margin_wholesale_total", "margin_wholesale_petrol",
    "margin_wholesale_diesel", "margin_wholesale_bitumen",
    "margin_retail_total", "margin_retail_petrol",
    "margin_retail_diesel", "margin_retail_cng", "margin_retail_lpg",
    "total_gross_profit",
    "ga_expenses",
    "ebitda",
    "da_expenses",
    "ebit",
    "finance_income", "finance_expense", "finance_net",
    "ebt",
    "tax_expense",
    "net_profit",
]


class ScenarioEngine:
    """
    What-if scenario engine for financial modeling.

    Creates modified copies of financial data, applies user-defined changes,
    builds comparative income statements, and persists results for later
    retrieval and multi-scenario comparison.
    """

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    async def create_scenario(
        db: AsyncSession,
        name: str,
        description: str,
        base_dataset_id: int,
        changes: List[Dict],
    ) -> Dict:
        """
        Create a what-if scenario by applying a list of changes to a base dataset.

        Args:
            db: Async database session.
            name: Human-readable scenario name.
            description: Explanation of what the scenario models.
            base_dataset_id: ID of the Dataset whose financial data is the baseline.
            changes: List of change dicts, each with keys:
                - target: e.g. "revenue_wholesale_diesel", "cogs_retail_petrol",
                          "volume_retail", "price_diesel", "ga_expenses",
                          "new_retail_stations"
                - change_type: "pct_change" | "absolute" | "delta"
                - value: numeric value (percentage points, absolute GEL, or delta GEL)

        Returns:
            Full scenario result dict including base/modified comparison and deltas.

        Raises:
            ValueError: If the base dataset is not found or changes are malformed.
        """
        logger.info(
            "Creating scenario '%s' on dataset %d with %d change(s)",
            name, base_dataset_id, len(changes),
        )

        # ── Step A: Load base dataset items from DB ──────────────────────
        revenue_items, cogs_items, ga_items = await ScenarioEngine._load_dataset_items(
            db, base_dataset_id,
        )
        logger.debug(
            "Loaded %d revenue, %d cogs, %d G&A items",
            len(revenue_items), len(cogs_items), len(ga_items),
        )

        # Fetch dataset metadata for period/currency
        ds_result = await db.execute(select(Dataset).where(Dataset.id == base_dataset_id))
        dataset = ds_result.scalar_one_or_none()
        if dataset is None:
            raise ValueError(f"Dataset {base_dataset_id} not found")
        period = dataset.period or "January 2025"
        currency = dataset.currency or "GEL"

        # ── Step B: Build base income statement ──────────────────────────
        base_is = build_income_statement(revenue_items, cogs_items, ga_items, period, currency)
        logger.debug("Base IS built — total_revenue=%.2f, net_profit=%.2f",
                      base_is.total_revenue, base_is.net_profit)

        # ── Step C: Deep-copy items as dicts and apply changes ───────────
        rev_dicts = [ScenarioEngine._revenue_to_dict(r) for r in revenue_items]
        cogs_dicts = [ScenarioEngine._cogs_to_dict(c) for c in cogs_items]
        ga_dicts = [ScenarioEngine._ga_to_dict(g) for g in ga_items]

        modified_rev, modified_cogs, modified_ga = ScenarioEngine._apply_changes(
            copy.deepcopy(rev_dicts),
            copy.deepcopy(cogs_dicts),
            copy.deepcopy(ga_dicts),
            changes,
        )

        # ── Step D: Build modified income statement ──────────────────────
        modified_is = build_income_statement(modified_rev, modified_cogs, modified_ga, period, currency)
        logger.debug("Modified IS built — total_revenue=%.2f, net_profit=%.2f",
                      modified_is.total_revenue, modified_is.net_profit)

        # ── Step E: Compute comparison deltas ────────────────────────────
        comparison = ScenarioEngine._compute_comparison(base_is, modified_is)

        # ── Step F: Persist scenario to DB ───────────────────────────────
        scenario = Scenario(
            name=name,
            description=description,
            base_dataset_id=base_dataset_id,
            parameters={"changes": changes},
            results=comparison,
            base_snapshot=base_is.to_dict(),
            is_active=True,
        )
        db.add(scenario)
        await db.commit()
        await db.refresh(scenario)
        logger.info("Scenario '%s' saved with id=%d", name, scenario.id)

        # ── Step G: Build full result ────────────────────────────────────
        result = {
            "scenario": scenario.to_dict(),
            "comparison": comparison,
            "base_income_statement": base_is.to_dict(),
            "modified_income_statement": modified_is.to_dict(),
            "changes_applied": changes,
        }
        return result

    @staticmethod
    async def compare_scenarios(
        db: AsyncSession,
        scenario_ids: List[int],
    ) -> Dict:
        """
        Load multiple saved scenarios and build a side-by-side comparison matrix.

        Args:
            db: Async database session.
            scenario_ids: List of Scenario IDs to compare.

        Returns:
            Dict with 'scenarios' list and 'comparison_matrix' for tabular display.

        Raises:
            ValueError: If any scenario ID is not found.
        """
        logger.info("Comparing %d scenarios: %s", len(scenario_ids), scenario_ids)

        scenarios_data: List[Dict] = []
        for sid in scenario_ids:
            result = await db.execute(select(Scenario).where(Scenario.id == sid))
            scenario = result.scalar_one_or_none()
            if scenario is None:
                raise ValueError(f"Scenario {sid} not found")

            # Extract key metrics from stored results
            results = scenario.results or {}
            modified_vals = results.get("modified", {})
            delta_vals = results.get("delta", {})
            delta_pct_vals = results.get("delta_pct", {})

            key_metrics = {
                "total_revenue": modified_vals.get("total_revenue", 0),
                "total_cogs": modified_vals.get("total_cogs", 0),
                "total_gross_margin": modified_vals.get("total_gross_margin", 0),
                "ga_expenses": modified_vals.get("ga_expenses", 0),
                "ebitda": modified_vals.get("ebitda", 0),
                "ebit": modified_vals.get("ebit", 0),
                "ebt": modified_vals.get("ebt", 0),
                "net_profit": modified_vals.get("net_profit", 0),
            }

            scenarios_data.append({
                "id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
                "base_dataset_id": scenario.base_dataset_id,
                "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
                "parameters": scenario.parameters,
                "key_metrics": key_metrics,
                "delta": {k: delta_vals.get(k, 0) for k in key_metrics},
                "delta_pct": {k: delta_pct_vals.get(k, 0) for k in key_metrics},
            })

        # Build comparison matrix — each field across all scenarios
        comparison_matrix: Dict[str, List[Dict]] = {}
        for field_name in _COMPARISON_FIELDS:
            comparison_matrix[field_name] = []
            for sd in scenarios_data:
                results = None
                # Re-fetch full results for matrix
                for sid_check in scenario_ids:
                    if sd["id"] == sid_check:
                        r = await db.execute(select(Scenario).where(Scenario.id == sid_check))
                        s = r.scalar_one_or_none()
                        if s:
                            results = s.results or {}
                        break

                if results:
                    comparison_matrix[field_name].append({
                        "scenario_id": sd["id"],
                        "scenario_name": sd["name"],
                        "base": results.get("base", {}).get(field_name, 0),
                        "modified": results.get("modified", {}).get(field_name, 0),
                        "delta": results.get("delta", {}).get(field_name, 0),
                        "delta_pct": results.get("delta_pct", {}).get(field_name, 0),
                    })

        return {
            "scenarios": scenarios_data,
            "comparison_matrix": comparison_matrix,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internal: Data Loading
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _load_dataset_items(
        db: AsyncSession,
        dataset_id: int,
    ) -> tuple:
        """
        Load all RevenueItem, COGSItem, and GAExpenseItem records for a dataset.

        Returns:
            Tuple of (revenue_items, cogs_items, ga_items) as ORM model lists.
        """
        rev_result = await db.execute(
            select(RevenueItem).where(RevenueItem.dataset_id == dataset_id)
        )
        revenue_items = list(rev_result.scalars().all())

        cogs_result = await db.execute(
            select(COGSItem).where(COGSItem.dataset_id == dataset_id)
        )
        cogs_items = list(cogs_result.scalars().all())

        ga_result = await db.execute(
            select(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id)
        )
        ga_items = list(ga_result.scalars().all())

        if not revenue_items and not cogs_items and not ga_items:
            logger.warning("Dataset %d has no financial items", dataset_id)

        return revenue_items, cogs_items, ga_items

    # ──────────────────────────────────────────────────────────────────────
    # Internal: Model-to-Dict Conversion
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _revenue_to_dict(item: RevenueItem) -> Dict:
        """Convert a RevenueItem ORM instance to a dict compatible with build_income_statement."""
        return {
            "id": item.id,
            "product": item.product,
            "gross": float(item.gross or 0),
            "vat": float(item.vat or 0),
            "net": float(item.net or 0),
            "segment": item.segment,
            "category": item.category,
        }

    @staticmethod
    def _cogs_to_dict(item: COGSItem) -> Dict:
        """Convert a COGSItem ORM instance to a dict compatible with build_income_statement."""
        # build_income_statement uses _get_attr with keys: col6_amount, col7310_amount, col8230_amount
        return {
            "id": item.id,
            "product": item.product,
            "col6_amount": float(item.col6_amount or 0),
            "col7310_amount": float(item.col7310_amount or 0),
            "col8230_amount": float(item.col8230_amount or 0),
            "total_cogs": float(item.total_cogs or 0),
            "segment": item.segment,
            "category": item.category,
        }

    @staticmethod
    def _ga_to_dict(item: GAExpenseItem) -> Dict:
        """Convert a GAExpenseItem ORM instance to a dict compatible with build_income_statement."""
        return {
            "id": item.id,
            "account_code": item.account_code,
            "account_name": item.account_name,
            "amount": float(item.amount or 0),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internal: Apply Changes
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_changes(
        revenue_items: List[Dict],
        cogs_items: List[Dict],
        ga_items: List[Dict],
        changes: List[Dict],
    ) -> tuple:
        """
        Apply a list of what-if changes to deep-copied item dicts.

        Supported target patterns:
            - revenue_<segment>_<product>: modify matching revenue items
            - cogs_<segment>_<product>: modify matching COGS items
            - volume_<segment>: scale both revenue AND cogs for all products in segment
            - price_<product>: scale revenue only (margin expansion), COGS unchanged
            - ga_expenses: modify all G&A expense items
            - new_retail_stations: add estimated revenue/COGS for new stations

        Args:
            revenue_items: List of revenue item dicts (deep-copied).
            cogs_items: List of COGS item dicts (deep-copied).
            ga_items: List of G&A item dicts (deep-copied).
            changes: List of change specification dicts.

        Returns:
            Tuple of (modified_revenue, modified_cogs, modified_ga).
        """
        for change in changes:
            target = change.get("target", "")
            change_type = change.get("change_type", "pct_change")
            value = float(change.get("value", 0))

            logger.debug("Applying change: target=%s, type=%s, value=%s", target, change_type, value)

            try:
                if target.startswith("revenue_"):
                    # e.g. "revenue_wholesale_diesel"
                    indices = ScenarioEngine._match_items(revenue_items, target)
                    ScenarioEngine._apply_revenue_change(revenue_items, indices, change_type, value)

                elif target.startswith("cogs_"):
                    # e.g. "cogs_retail_petrol"
                    indices = ScenarioEngine._match_items(cogs_items, target)
                    ScenarioEngine._apply_cogs_change(cogs_items, indices, change_type, value)

                elif target.startswith("volume_"):
                    # e.g. "volume_retail" — affects both revenue and COGS for segment
                    segment = target.replace("volume_", "")
                    ScenarioEngine._apply_volume_change(
                        revenue_items, cogs_items, segment, change_type, value,
                    )

                elif target.startswith("price_"):
                    # e.g. "price_diesel" — revenue only (margin expansion)
                    product = target.replace("price_", "")
                    ScenarioEngine._apply_price_change(
                        revenue_items, product, change_type, value,
                    )

                elif target == "ga_expenses":
                    ScenarioEngine._apply_ga_change(ga_items, change_type, value)

                elif target == "new_retail_stations":
                    ScenarioEngine._apply_new_stations(
                        revenue_items, cogs_items, int(value),
                    )

                else:
                    logger.warning("Unknown change target: %s — skipping", target)

            except Exception as exc:
                logger.error("Error applying change %s: %s", target, exc, exc_info=True)
                raise ValueError(f"Failed to apply change '{target}': {exc}") from exc

        # Round all values to 2 decimals
        ScenarioEngine._round_items(revenue_items, cogs_items, ga_items)

        return revenue_items, cogs_items, ga_items

    # ──────────────────────────────────────────────────────────────────────
    # Internal: Change Application Helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_revenue_change(
        items: List[Dict],
        indices: List[int],
        change_type: str,
        value: float,
    ) -> None:
        """
        Apply a change to selected revenue items.

        Modifies net, gross, and vat proportionally to preserve their ratios.
        """
        if not indices:
            logger.warning("No revenue items matched for change — skipping")
            return

        if change_type == "pct_change":
            multiplier = 1 + value / 100.0
            for idx in indices:
                items[idx]["net"] *= multiplier
                items[idx]["gross"] *= multiplier
                items[idx]["vat"] *= multiplier

        elif change_type == "absolute":
            # Distribute absolute value proportionally across matched items
            current_total = sum(items[idx]["net"] for idx in indices)
            if current_total == 0:
                # Equal distribution when no existing values
                per_item = value / len(indices)
                for idx in indices:
                    items[idx]["net"] = per_item
                    items[idx]["gross"] = per_item
                    items[idx]["vat"] = 0.0
            else:
                for idx in indices:
                    proportion = items[idx]["net"] / current_total
                    old_net = items[idx]["net"]
                    new_net = value * proportion
                    ratio = new_net / old_net if old_net != 0 else 0
                    items[idx]["net"] = new_net
                    items[idx]["gross"] *= ratio
                    items[idx]["vat"] *= ratio

        elif change_type == "delta":
            # Add delta proportionally across matched items
            current_total = sum(items[idx]["net"] for idx in indices)
            if current_total == 0:
                per_item = value / len(indices)
                for idx in indices:
                    items[idx]["net"] += per_item
                    items[idx]["gross"] += per_item
            else:
                for idx in indices:
                    proportion = items[idx]["net"] / current_total
                    delta_share = value * proportion
                    old_net = items[idx]["net"]
                    new_net = old_net + delta_share
                    ratio = new_net / old_net if old_net != 0 else 1
                    items[idx]["net"] = new_net
                    items[idx]["gross"] *= ratio
                    items[idx]["vat"] *= ratio

    @staticmethod
    def _apply_cogs_change(
        items: List[Dict],
        indices: List[int],
        change_type: str,
        value: float,
    ) -> None:
        """
        Apply a change to selected COGS items.

        Modifies total_cogs, col6_amount, col7310_amount, col8230_amount proportionally.
        """
        if not indices:
            logger.warning("No COGS items matched for change — skipping")
            return

        cogs_fields = ["total_cogs", "col6_amount", "col7310_amount", "col8230_amount"]

        if change_type == "pct_change":
            multiplier = 1 + value / 100.0
            for idx in indices:
                for fld in cogs_fields:
                    items[idx][fld] *= multiplier

        elif change_type == "absolute":
            current_total = sum(items[idx]["total_cogs"] for idx in indices)
            if current_total == 0:
                per_item = value / len(indices)
                for idx in indices:
                    items[idx]["total_cogs"] = per_item
                    items[idx]["col6_amount"] = per_item
                    items[idx]["col7310_amount"] = 0.0
                    items[idx]["col8230_amount"] = 0.0
            else:
                for idx in indices:
                    proportion = items[idx]["total_cogs"] / current_total
                    old_total = items[idx]["total_cogs"]
                    new_total = value * proportion
                    ratio = new_total / old_total if old_total != 0 else 0
                    for fld in cogs_fields:
                        items[idx][fld] *= ratio

        elif change_type == "delta":
            current_total = sum(items[idx]["total_cogs"] for idx in indices)
            if current_total == 0:
                per_item = value / len(indices)
                for idx in indices:
                    items[idx]["total_cogs"] += per_item
                    items[idx]["col6_amount"] += per_item
            else:
                for idx in indices:
                    proportion = items[idx]["total_cogs"] / current_total
                    delta_share = value * proportion
                    old_total = items[idx]["total_cogs"]
                    new_total = old_total + delta_share
                    ratio = new_total / old_total if old_total != 0 else 1
                    for fld in cogs_fields:
                        items[idx][fld] *= ratio

    @staticmethod
    def _apply_volume_change(
        revenue_items: List[Dict],
        cogs_items: List[Dict],
        segment: str,
        change_type: str,
        value: float,
    ) -> None:
        """
        Apply a volume change to an entire segment (e.g. all retail products).

        Volume changes affect BOTH revenue and COGS proportionally — margins
        stay the same in percentage terms since more/fewer units are sold.
        Only pct_change is meaningful for volume; others fall back to pct_change.
        """
        if change_type != "pct_change":
            logger.warning(
                "Volume change only supports pct_change; treating value=%s as pct_change", value,
            )

        multiplier = 1 + value / 100.0
        segment_db = _SEGMENT_MAP.get(segment, segment)

        # Apply to revenue items in this segment
        for item in revenue_items:
            item_segment = (item.get("segment") or "").lower()
            item_category = (item.get("category") or "").lower()
            if segment_db.lower() in item_segment.lower() or segment_db.lower() in item_category.lower():
                item["net"] *= multiplier
                item["gross"] *= multiplier
                item["vat"] *= multiplier

        # Apply to COGS items in this segment
        cogs_segment_prefix = f"COGS {segment_db}"
        for item in cogs_items:
            item_segment = item.get("segment") or ""
            item_category = item.get("category") or ""
            if segment_db.lower() in item_segment.lower() or segment_db.lower() in item_category.lower():
                item["total_cogs"] *= multiplier
                item["col6_amount"] *= multiplier
                item["col7310_amount"] *= multiplier
                item["col8230_amount"] *= multiplier

    @staticmethod
    def _apply_price_change(
        revenue_items: List[Dict],
        product: str,
        change_type: str,
        value: float,
    ) -> None:
        """
        Apply a price change to a product across all segments.

        Price changes affect ONLY revenue — COGS stays constant, so this
        models margin expansion/compression from price adjustments.
        Only pct_change is meaningful for price; others fall back to pct_change.
        """
        if change_type != "pct_change":
            logger.warning(
                "Price change only supports pct_change; treating value=%s as pct_change", value,
            )

        multiplier = 1 + value / 100.0
        product_db = _PRODUCT_MAP.get(product.lower(), product)

        for item in revenue_items:
            item_category = (item.get("category") or "")
            item_product = (item.get("product") or "")
            if product_db.lower() in item_category.lower() or product_db.lower() in item_product.lower():
                item["net"] *= multiplier
                item["gross"] *= multiplier
                item["vat"] *= multiplier

    @staticmethod
    def _apply_ga_change(
        ga_items: List[Dict],
        change_type: str,
        value: float,
    ) -> None:
        """Apply a change to all G&A expense items proportionally."""
        if not ga_items:
            logger.warning("No G&A items to apply change to — skipping")
            return

        if change_type == "pct_change":
            multiplier = 1 + value / 100.0
            for item in ga_items:
                item["amount"] *= multiplier

        elif change_type == "absolute":
            current_total = sum(item["amount"] for item in ga_items)
            if current_total == 0:
                per_item = value / len(ga_items)
                for item in ga_items:
                    item["amount"] = per_item
            else:
                for item in ga_items:
                    proportion = item["amount"] / current_total
                    item["amount"] = value * proportion

        elif change_type == "delta":
            current_total = sum(item["amount"] for item in ga_items)
            if current_total == 0:
                per_item = value / len(ga_items)
                for item in ga_items:
                    item["amount"] += per_item
            else:
                for item in ga_items:
                    proportion = item["amount"] / current_total
                    item["amount"] += value * proportion

    @staticmethod
    def _apply_new_stations(
        revenue_items: List[Dict],
        cogs_items: List[Dict],
        num_stations: int,
    ) -> None:
        """
        Model the impact of adding new retail fuel stations.

        Each new station is estimated to generate ~250,000 GEL/month in revenue,
        distributed proportionally across existing retail product mix. COGS is
        added proportionally based on the current COGS/revenue ratio per product.

        Args:
            revenue_items: Revenue item dicts to modify.
            cogs_items: COGS item dicts to modify.
            num_stations: Number of new stations to add.
        """
        if num_stations <= 0:
            logger.warning("new_retail_stations value must be positive, got %d", num_stations)
            return

        total_new_revenue = _NEW_STATION_MONTHLY_REVENUE * num_stations
        logger.info("Modeling %d new retail stations → +%.2f GEL revenue", num_stations, total_new_revenue)

        # Find existing retail revenue items to determine product mix
        retail_rev_indices = []
        for i, item in enumerate(revenue_items):
            category = (item.get("category") or "").lower()
            segment = (item.get("segment") or "").lower()
            if "retial" in category or "retail" in segment.lower():
                retail_rev_indices.append(i)

        if not retail_rev_indices:
            logger.warning("No retail revenue items found — cannot distribute new station revenue")
            return

        # Compute current retail revenue mix for proportional distribution
        current_retail_total = sum(revenue_items[i]["net"] for i in retail_rev_indices)
        if current_retail_total == 0:
            # Equal distribution if no existing revenue
            per_item = total_new_revenue / len(retail_rev_indices)
            for i in retail_rev_indices:
                revenue_items[i]["net"] += per_item
                revenue_items[i]["gross"] += per_item
        else:
            for i in retail_rev_indices:
                proportion = revenue_items[i]["net"] / current_retail_total
                additional_net = total_new_revenue * proportion
                old_net = revenue_items[i]["net"]
                new_net = old_net + additional_net
                ratio = new_net / old_net if old_net != 0 else 1
                revenue_items[i]["net"] = new_net
                revenue_items[i]["gross"] *= ratio
                revenue_items[i]["vat"] *= ratio

        # Add proportional COGS based on existing COGS/revenue ratio per product
        # Match retail COGS items by category
        retail_cogs_indices = []
        for i, item in enumerate(cogs_items):
            category = (item.get("category") or "").lower()
            segment = (item.get("segment") or "").lower()
            if "retial" in category or "retail" in segment.lower():
                retail_cogs_indices.append(i)

        if not retail_cogs_indices:
            logger.warning("No retail COGS items found — new station revenue added without COGS")
            return

        # For each retail COGS item, compute the ratio to its revenue counterpart
        # and add proportional COGS for the new revenue
        current_retail_cogs_total = sum(cogs_items[i]["total_cogs"] for i in retail_cogs_indices)
        if current_retail_total > 0 and current_retail_cogs_total > 0:
            cogs_to_rev_ratio = current_retail_cogs_total / current_retail_total
            total_new_cogs = total_new_revenue * cogs_to_rev_ratio

            current_cogs_sum = sum(cogs_items[i]["total_cogs"] for i in retail_cogs_indices)
            for i in retail_cogs_indices:
                if current_cogs_sum == 0:
                    break
                proportion = cogs_items[i]["total_cogs"] / current_cogs_sum
                additional_cogs = total_new_cogs * proportion
                old_total = cogs_items[i]["total_cogs"]
                new_total = old_total + additional_cogs
                ratio = new_total / old_total if old_total != 0 else 1
                cogs_items[i]["total_cogs"] = new_total
                cogs_items[i]["col6_amount"] *= ratio
                cogs_items[i]["col7310_amount"] *= ratio
                cogs_items[i]["col8230_amount"] *= ratio

    # ──────────────────────────────────────────────────────────────────────
    # Internal: Item Matching
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _match_items(items: List[Dict], target: str) -> List[int]:
        """
        Find which items (by index) match a target string.

        Target format: "<type>_<segment>_<product>"
            e.g. "revenue_wholesale_diesel", "cogs_retail_petrol"

        Matching logic:
            - Segment: "wholesale" matches categories containing "Whsale",
                        "retail" matches categories containing "Retial"
            - Product: "petrol"/"diesel"/"cng"/"lpg"/"bitumen" matched case-insensitively
                        against the item's category string

        Args:
            items: List of item dicts (revenue or COGS).
            target: Target identifier string.

        Returns:
            List of integer indices into the items list.
        """
        parts = target.split("_")
        if len(parts) < 3:
            logger.warning("Target '%s' has fewer than 3 parts — cannot match segment+product", target)
            return []

        # Extract segment and product from target
        # Format: <type>_<segment>_<product> where type is "revenue" or "cogs"
        item_type = parts[0]  # "revenue" or "cogs"
        segment_raw = parts[1]  # "wholesale" or "retail"
        product_raw = "_".join(parts[2:])  # "diesel", "petrol", etc.

        segment_db = _SEGMENT_MAP.get(segment_raw, segment_raw)
        product_db = _PRODUCT_MAP.get(product_raw.lower(), product_raw)

        matched_indices = []
        for i, item in enumerate(items):
            category = (item.get("category") or "").lower()

            # Check segment match
            segment_match = segment_db.lower() in category

            # Check product match
            product_match = product_db.lower() in category

            if segment_match and product_match:
                matched_indices.append(i)

        logger.debug(
            "Target '%s' matched %d items (segment=%s, product=%s)",
            target, len(matched_indices), segment_db, product_db,
        )
        return matched_indices

    # ──────────────────────────────────────────────────────────────────────
    # Internal: Comparison
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_comparison(
        base: IncomeStatement,
        modified: IncomeStatement,
    ) -> Dict:
        """
        Build a side-by-side comparison between base and modified income statements.

        Returns:
            Dict with keys:
                - base: {field: value} for all comparison fields
                - modified: {field: value} for all comparison fields
                - delta: {field: modified - base}
                - delta_pct: {field: percentage change from base to modified}
        """
        base_vals: Dict[str, float] = {}
        modified_vals: Dict[str, float] = {}
        delta_vals: Dict[str, float] = {}
        delta_pct_vals: Dict[str, float] = {}

        for field_name in _COMPARISON_FIELDS:
            b_val = round(getattr(base, field_name, 0) or 0, 2)
            m_val = round(getattr(modified, field_name, 0) or 0, 2)
            d_val = round(m_val - b_val, 2)

            if b_val != 0:
                d_pct = round((d_val / abs(b_val)) * 100, 2)
            else:
                d_pct = 0.0

            base_vals[field_name] = b_val
            modified_vals[field_name] = m_val
            delta_vals[field_name] = d_val
            delta_pct_vals[field_name] = d_pct

        return {
            "base": base_vals,
            "modified": modified_vals,
            "delta": delta_vals,
            "delta_pct": delta_pct_vals,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internal: Rounding
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _round_items(
        revenue_items: List[Dict],
        cogs_items: List[Dict],
        ga_items: List[Dict],
    ) -> None:
        """Round all numeric values in item dicts to 2 decimal places."""
        for item in revenue_items:
            item["net"] = round(item.get("net", 0), 2)
            item["gross"] = round(item.get("gross", 0), 2)
            item["vat"] = round(item.get("vat", 0), 2)

        for item in cogs_items:
            item["total_cogs"] = round(item.get("total_cogs", 0), 2)
            item["col6_amount"] = round(item.get("col6_amount", 0), 2)
            item["col7310_amount"] = round(item.get("col7310_amount", 0), 2)
            item["col8230_amount"] = round(item.get("col8230_amount", 0), 2)

        for item in ga_items:
            item["amount"] = round(item.get("amount", 0), 2)
