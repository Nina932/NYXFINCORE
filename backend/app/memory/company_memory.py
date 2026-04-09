"""
Company Memory — Cross-Period Financial Intelligence
=====================================================
Stores and retrieves historical analysis results per company.
Enables cross-period comparison: "interest dropped 20% vs last month".

Uses existing SQLite DataStore for persistence.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CompanyMemory:
    """Persistent memory for cross-period financial intelligence."""

    def __init__(self):
        self._cache: Dict[int, List[Dict]] = {}  # company_id -> [run_results]

    def get_last_n(self, company_id: int, n: int = 5) -> List[Dict]:
        """Get last N analysis runs for a company."""
        try:
            from app.services.data_store import data_store

            periods = data_store.get_all_periods(company_id)
            results = []
            for period in periods[-n:]:
                fin = data_store.get_financials(company_id, period)
                if fin:
                    results.append({"period": period, "financials": fin})
            return results
        except Exception as e:
            logger.warning("Memory retrieval failed: %s", e)
            return self._cache.get(company_id, [])[-n:]

    def get_previous_period(self, company_id: int, current_period: str) -> Optional[Dict]:
        """Get the period immediately before current."""
        try:
            from app.services.data_store import data_store

            periods = data_store.get_all_periods(company_id)
            if current_period in periods:
                idx = periods.index(current_period)
                if idx > 0:
                    prev_period = periods[idx - 1]
                    fin = data_store.get_financials(company_id, prev_period)
                    return {"period": prev_period, "financials": fin}
            elif len(periods) > 0:
                # Current period not stored yet — use latest stored as "previous"
                fin = data_store.get_financials(company_id, periods[-1])
                return {"period": periods[-1], "financials": fin}
        except Exception as e:
            logger.warning("Previous period lookup failed: %s", e)
        return None

    def compute_deltas(self, current: Dict, previous: Optional[Dict]) -> Dict[str, Any]:
        """Compute changes between current and previous period."""
        if not previous or not previous.get("financials"):
            return {"has_comparison": False, "message": "No previous period available for comparison"}

        prev_fin = previous["financials"]
        deltas = {"has_comparison": True, "previous_period": previous["period"], "changes": {}}

        compare_keys = [
            "revenue", "cogs", "gross_profit", "selling_expenses", "admin_expenses",
            "ga_expenses", "ebitda", "net_profit", "other_income", "other_expense",
        ]

        for key in compare_keys:
            curr_val = current.get(key, 0) or 0
            prev_val = prev_fin.get(key, 0) or 0

            if prev_val != 0 and curr_val != 0:
                change_pct = round((curr_val - prev_val) / abs(prev_val) * 100, 1)
                deltas["changes"][key] = {
                    "current": round(curr_val, 2),
                    "previous": round(prev_val, 2),
                    "change_abs": round(curr_val - prev_val, 2),
                    "change_pct": change_pct,
                    "direction": "up" if change_pct > 0 else "down" if change_pct < 0 else "flat",
                }

        return deltas

    def save_run(self, company_id: int, run_result: Dict):
        """Cache a run result in memory (DB save happens in smart-upload)."""
        if company_id not in self._cache:
            self._cache[company_id] = []
        self._cache[company_id].append(run_result)
        # Keep only last 12
        if len(self._cache[company_id]) > 12:
            self._cache[company_id] = self._cache[company_id][-12:]


# Singleton
company_memory = CompanyMemory()
