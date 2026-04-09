"""
FinAI OS — Period Aggregation Service
======================================
Aggregates monthly financial data into quarterly, half-year, YTD, and annual views.

P&L items are SUMMED across periods (they represent activity).
BS items use the LAST period's values (they are point-in-time snapshots).

Usage:
    from app.services.period_aggregation import period_aggregator
    quarters = period_aggregator.aggregate_quarters(company_id=1, year=2025)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.services.data_store import data_store

import logging

logger = logging.getLogger(__name__)


@dataclass
class AggregatedPeriod:
    period_label: str            # "Q1 2025", "H1 2025", "FY 2025", "YTD 2025-07"
    periods_included: List[str]  # ["2025-01", "2025-02", "2025-03"]
    financials: Dict             # aggregated P&L + last-period BS


class PeriodAggregator:
    """Aggregates monthly financial snapshots into higher-level periods."""

    # P&L items are SUMMED (period activity)
    SUM_FIELDS = [
        'revenue', 'cogs', 'gross_profit', 'selling_expenses', 'admin_expenses',
        'ga_expenses', 'ebitda', 'depreciation', 'ebit', 'finance_income',
        'finance_expense', 'other_income', 'other_expense', 'profit_before_tax',
        'tax_expense', 'net_profit',
    ]

    # BS items use LAST period (point-in-time)
    LAST_FIELDS = [
        'cash', 'receivables', 'inventory', 'total_assets', 'total_liabilities',
        'total_equity', 'fixed_assets', 'payables',
    ]

    def aggregate_quarters(self, company_id: int, year: int) -> List[AggregatedPeriod]:
        """Generate Q1, Q2, Q3, Q4 from monthly data."""
        quarters = {
            'Q1': ['01', '02', '03'],
            'Q2': ['04', '05', '06'],
            'Q3': ['07', '08', '09'],
            'Q4': ['10', '11', '12'],
        }
        results = []
        for q_name, months in quarters.items():
            period_keys = [f'{year}-{m}' for m in months]
            agg = self._aggregate_periods(company_id, period_keys)
            if agg:
                results.append(AggregatedPeriod(
                    period_label=f'{q_name} {year}',
                    periods_included=period_keys,
                    financials=agg,
                ))
        return results

    def aggregate_ytd(self, company_id: int, year: int, through_month: int) -> AggregatedPeriod:
        """YTD through a specific month."""
        period_keys = [f'{year}-{m:02d}' for m in range(1, through_month + 1)]
        agg = self._aggregate_periods(company_id, period_keys)
        return AggregatedPeriod(
            period_label=f'YTD {year}-{through_month:02d}',
            periods_included=period_keys,
            financials=agg or {},
        )

    def aggregate_full_year(self, company_id: int, year: int) -> AggregatedPeriod:
        """Full year aggregate."""
        return self.aggregate_ytd(company_id, year, 12)

    def aggregate_half_years(self, company_id: int, year: int) -> List[AggregatedPeriod]:
        """H1 and H2."""
        h1_keys = [f'{year}-{m:02d}' for m in range(1, 7)]
        h2_keys = [f'{year}-{m:02d}' for m in range(7, 13)]
        h1 = self._aggregate_periods(company_id, h1_keys)
        h2 = self._aggregate_periods(company_id, h2_keys)
        results = []
        if h1:
            results.append(AggregatedPeriod(f'H1 {year}', h1_keys, h1))
        if h2:
            results.append(AggregatedPeriod(f'H2 {year}', h2_keys, h2))
        return results

    def get_summary(self, company_id: int) -> Dict:
        """Return all available aggregations for a company, auto-detecting years."""
        periods = data_store.get_all_periods(company_id)
        if not periods:
            return {"company_id": company_id, "periods": [], "aggregations": {}}

        # Detect available years from period names (format "YYYY-MM")
        years = set()
        for p in periods:
            if '-' in p:
                try:
                    years.add(int(p.split('-')[0]))
                except (ValueError, IndexError):
                    pass

        aggregations = {}
        for year in sorted(years):
            year_periods = [p for p in periods if p.startswith(f'{year}-')]
            months_available = []
            for p in year_periods:
                try:
                    months_available.append(int(p.split('-')[1]))
                except (ValueError, IndexError):
                    pass

            year_data = {
                "months_available": sorted(months_available),
                "quarters": [],
                "half_years": [],
                "ytd": None,
                "annual": None,
            }

            # Quarters
            for ap in self.aggregate_quarters(company_id, year):
                year_data["quarters"].append({
                    "period_label": ap.period_label,
                    "periods_included": ap.periods_included,
                    "financials": ap.financials,
                })

            # Half-years
            for ap in self.aggregate_half_years(company_id, year):
                year_data["half_years"].append({
                    "period_label": ap.period_label,
                    "periods_included": ap.periods_included,
                    "financials": ap.financials,
                })

            # YTD (through latest available month)
            if months_available:
                ytd = self.aggregate_ytd(company_id, year, max(months_available))
                if ytd.financials:
                    year_data["ytd"] = {
                        "period_label": ytd.period_label,
                        "periods_included": ytd.periods_included,
                        "financials": ytd.financials,
                    }

            # Annual (only if all 12 months present)
            if len(months_available) == 12:
                annual = self.aggregate_full_year(company_id, year)
                if annual.financials:
                    year_data["annual"] = {
                        "period_label": annual.period_label,
                        "periods_included": annual.periods_included,
                        "financials": annual.financials,
                    }

            aggregations[str(year)] = year_data

        return {
            "company_id": company_id,
            "periods": periods,
            "aggregations": aggregations,
        }

    def _aggregate_periods(self, company_id: int, period_keys: List[str]) -> Optional[Dict]:
        """Sum P&L items across periods. BS uses last period's values."""
        result = {}
        periods_found = 0
        last_period_data = None

        for pk in sorted(period_keys):
            fin = data_store.get_financials(company_id, pk)
            if not fin:
                continue
            periods_found += 1
            last_period_data = fin

            for field in self.SUM_FIELDS:
                val = fin.get(field, 0) or 0
                result[field] = result.get(field, 0) + val

        if periods_found == 0:
            return None

        # Add BS from last period
        if last_period_data:
            for field in self.LAST_FIELDS:
                result[field] = last_period_data.get(field, 0) or 0

        result['periods_count'] = periods_found
        return result


# Module-level singleton
period_aggregator = PeriodAggregator()
