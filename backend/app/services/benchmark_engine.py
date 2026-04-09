"""
benchmark_engine.py -- Dynamic Industry Benchmark Engine
=========================================================
Replaces hardcoded fuel-distribution benchmarks with a configurable,
multi-industry benchmark system.

Supported industries:
  - fuel_distribution (default, preserves existing benchmarks)
  - retail_general
  - manufacturing
  - services
  - construction
  - agriculture

Phase G-3 of the FinAI Full System Upgrade.
"""
from __future__ import annotations

import logging
import statistics as _stats
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkThreshold:
    """Threshold values for a single benchmark metric."""
    metric: str
    healthy_min: Optional[float] = None
    healthy_max: Optional[float] = None
    warning_min: Optional[float] = None
    warning_max: Optional[float] = None
    critical_below: Optional[float] = None
    critical_above: Optional[float] = None
    unit: str = "%"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "healthy_range": f"{self.healthy_min}-{self.healthy_max}{self.unit}",
            "warning_min": self.warning_min,
            "warning_max": self.warning_max,
            "critical_below": self.critical_below,
            "critical_above": self.critical_above,
            "description": self.description,
        }


@dataclass
class IndustryProfile:
    """Complete benchmark profile for an industry."""
    industry_id: str
    industry_name: str
    region: str = "global"
    benchmarks: Dict[str, BenchmarkThreshold] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "industry_id": self.industry_id,
            "industry_name": self.industry_name,
            "region": self.region,
            "benchmark_count": len(self.benchmarks),
            "benchmarks": {k: v.to_dict() for k, v in self.benchmarks.items()},
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkComparison:
    """Result of comparing actual metrics against benchmarks."""
    industry: str
    metric: str
    actual_value: float
    status: str             # "healthy" | "warning" | "critical" | "unknown"
    benchmark_range: str    # e.g. "1-4%"
    deviation_pct: float    # how far from healthy range center
    narrative: str
    company_avg: Optional[float] = None        # company's own historical average
    trend_vs_own_history: Optional[str] = None  # "improving" | "declining" | "stable" | None
    data_source: str = "industry_profile"       # "industry_profile" | "company_history+industry"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "industry": self.industry,
            "metric": self.metric,
            "actual_value": self.actual_value,
            "status": self.status,
            "benchmark_range": self.benchmark_range,
            "deviation_pct": round(self.deviation_pct, 2),
            "narrative": self.narrative,
            "data_source": self.data_source,
        }
        if self.company_avg is not None:
            d["company_avg"] = round(self.company_avg, 2)
        if self.trend_vs_own_history is not None:
            d["trend_vs_own_history"] = self.trend_vs_own_history
        return d


# ---------------------------------------------------------------------------
# Industry profile definitions
# ---------------------------------------------------------------------------

def _build_fuel_distribution() -> IndustryProfile:
    """Fuel distribution benchmarks (preserves existing hardcoded values)."""
    p = IndustryProfile(
        industry_id="fuel_distribution",
        industry_name="Fuel Distribution & Petroleum",
        region="Georgia/CIS",
        metadata={"examples": ["NYX Core Thinker", "Gulf", "Wissol"], "currency": "GEL"},
    )
    _add = lambda m, hmin, hmax, wmin, wmax, cb, ca, u, d: p.benchmarks.__setitem__(
        m, BenchmarkThreshold(m, hmin, hmax, wmin, wmax, cb, ca, u, d))
    _add("gross_margin_pct",       1.0, 15.0,  0.5, 18.0, 0.0,  25.0, "%", "Wholesale 1-4%, Retail 8-15%")
    _add("wholesale_margin_pct",   1.0,  4.0,  0.5,  6.0, 0.0,  10.0, "%", "Fuel wholesale margin")
    _add("retail_margin_pct",      8.0, 15.0,  5.0, 20.0, 3.0,  25.0, "%", "Fuel retail margin")
    _add("net_margin_pct",         0.5,  3.0,  0.2,  5.0, 0.0,   8.0, "%", "Net profit margin")
    _add("current_ratio",          1.2,  2.5,  1.0,  3.0, 0.8,   4.0, "x", "Current ratio")
    _add("quick_ratio",            0.8,  1.5,  0.6,  2.0, 0.4,   3.0, "x", "Quick ratio")
    _add("debt_to_equity",         0.5,  2.0,  0.3,  3.0, None,  4.0, "x", "Debt-to-equity")
    _add("inventory_turnover",    24.0, 36.0, 18.0, 48.0, 12.0, 60.0, "x/yr", "Inventory turnover")
    _add("days_sales_outstanding", 15.0, 45.0, 10.0, 60.0, None, 90.0, "days", "DSO")
    _add("ebitda_margin_pct",      2.0,  8.0,  1.0, 12.0, 0.0,  15.0, "%", "EBITDA margin")
    _add("roe",                    5.0, 20.0,  3.0, 30.0, 0.0,  40.0, "%", "Return on equity")
    _add("roa",                    2.0, 10.0,  1.0, 15.0, 0.0,  20.0, "%", "Return on assets")
    _add("ga_to_revenue_pct",      1.5,  4.0,  1.0,  6.0, None, 10.0, "%", "G&A / Revenue ratio")
    _add("asset_turnover",         1.5,  4.0,  1.0,  5.0, 0.5,   7.0, "x", "Asset turnover")
    _add("operating_margin_pct",   1.0,  5.0,  0.5,  8.0, 0.0,  12.0, "%", "Operating margin")
    return p


def _build_retail_general() -> IndustryProfile:
    p = IndustryProfile(
        industry_id="retail_general",
        industry_name="General Retail & Consumer Goods",
        region="global",
        metadata={"examples": ["Supermarkets", "Fashion", "Electronics"]},
    )
    _add = lambda m, hmin, hmax, wmin, wmax, cb, ca, u, d: p.benchmarks.__setitem__(
        m, BenchmarkThreshold(m, hmin, hmax, wmin, wmax, cb, ca, u, d))
    _add("gross_margin_pct",       25.0, 45.0, 20.0, 55.0, 15.0, 60.0, "%", "Retail gross margin")
    _add("net_margin_pct",          2.0,  7.0,  1.0, 10.0,  0.0, 15.0, "%", "Net profit margin")
    _add("current_ratio",           1.5,  2.5,  1.2,  3.0,  0.8,  4.0, "x", "Current ratio")
    _add("quick_ratio",             0.5,  1.2,  0.3,  1.5,  0.2,  2.0, "x", "Quick ratio")
    _add("debt_to_equity",          0.5,  1.5,  0.3,  2.5, None,  3.0, "x", "Debt-to-equity")
    _add("inventory_turnover",      6.0, 12.0,  4.0, 15.0,  2.0, 20.0, "x/yr", "Inventory turnover")
    _add("days_sales_outstanding",  20.0, 45.0, 10.0, 60.0, None, 90.0, "days", "DSO")
    _add("ebitda_margin_pct",        4.0, 12.0,  2.0, 15.0,  0.0, 20.0, "%", "EBITDA margin")
    _add("roe",                      8.0, 25.0,  5.0, 35.0,  0.0, 45.0, "%", "Return on equity")
    _add("roa",                      3.0, 12.0,  2.0, 15.0,  0.0, 20.0, "%", "Return on assets")
    _add("ga_to_revenue_pct",        3.0,  8.0,  2.0, 12.0, None, 15.0, "%", "G&A / Revenue")
    _add("asset_turnover",           1.5,  3.5,  1.0,  4.5,  0.5,  6.0, "x", "Asset turnover")
    _add("operating_margin_pct",     3.0, 10.0,  1.5, 13.0,  0.0, 18.0, "%", "Operating margin")
    _add("wholesale_margin_pct",    15.0, 30.0, 10.0, 40.0,  5.0, 50.0, "%", "Wholesale margin")
    _add("retail_margin_pct",       25.0, 45.0, 18.0, 55.0, 12.0, 60.0, "%", "Retail margin")
    return p


def _build_manufacturing() -> IndustryProfile:
    p = IndustryProfile(
        industry_id="manufacturing",
        industry_name="Manufacturing & Industrial",
        region="global",
        metadata={"examples": ["Automotive", "Chemicals", "Electronics"]},
    )
    _add = lambda m, hmin, hmax, wmin, wmax, cb, ca, u, d: p.benchmarks.__setitem__(
        m, BenchmarkThreshold(m, hmin, hmax, wmin, wmax, cb, ca, u, d))
    _add("gross_margin_pct",       15.0, 35.0, 10.0, 45.0,  5.0, 55.0, "%", "Manufacturing gross margin")
    _add("net_margin_pct",          3.0,  8.0,  1.5, 12.0,  0.0, 15.0, "%", "Net profit margin")
    _add("current_ratio",           1.5,  2.5,  1.2,  3.5,  0.8,  4.5, "x", "Current ratio")
    _add("quick_ratio",             0.8,  1.5,  0.5,  2.0,  0.3,  3.0, "x", "Quick ratio")
    _add("debt_to_equity",          0.5,  2.0,  0.3,  3.0, None,  4.0, "x", "Debt-to-equity")
    _add("inventory_turnover",      4.0, 10.0,  2.0, 14.0,  1.0, 18.0, "x/yr", "Inventory turnover")
    _add("days_sales_outstanding",  30.0, 60.0, 20.0, 75.0, None, 120.0, "days", "DSO")
    _add("ebitda_margin_pct",        8.0, 18.0,  5.0, 22.0,  2.0, 28.0, "%", "EBITDA margin")
    _add("roe",                      8.0, 22.0,  4.0, 30.0,  0.0, 40.0, "%", "Return on equity")
    _add("roa",                      3.0, 10.0,  1.5, 14.0,  0.0, 18.0, "%", "Return on assets")
    _add("ga_to_revenue_pct",        2.0,  6.0,  1.5,  8.0, None, 12.0, "%", "G&A / Revenue")
    _add("asset_turnover",           0.8,  2.0,  0.5,  2.5,  0.3,  3.5, "x", "Asset turnover")
    _add("operating_margin_pct",     5.0, 15.0,  3.0, 20.0,  0.0, 25.0, "%", "Operating margin")
    _add("wholesale_margin_pct",    10.0, 25.0,  5.0, 35.0,  2.0, 45.0, "%", "Wholesale margin")
    _add("retail_margin_pct",       20.0, 40.0, 12.0, 50.0,  8.0, 55.0, "%", "Retail margin")
    return p


def _build_services() -> IndustryProfile:
    p = IndustryProfile(
        industry_id="services",
        industry_name="Professional & Business Services",
        region="global",
        metadata={"examples": ["Consulting", "IT", "Legal", "Accounting"]},
    )
    _add = lambda m, hmin, hmax, wmin, wmax, cb, ca, u, d: p.benchmarks.__setitem__(
        m, BenchmarkThreshold(m, hmin, hmax, wmin, wmax, cb, ca, u, d))
    _add("gross_margin_pct",       40.0, 70.0, 30.0, 80.0, 20.0, 90.0, "%", "Services gross margin")
    _add("net_margin_pct",          5.0, 15.0,  3.0, 22.0,  0.0, 30.0, "%", "Net profit margin")
    _add("current_ratio",           1.2,  2.5,  1.0,  3.5,  0.7,  5.0, "x", "Current ratio")
    _add("quick_ratio",             1.0,  2.5,  0.8,  3.5,  0.5,  5.0, "x", "Quick ratio")
    _add("debt_to_equity",          0.2,  1.0,  0.1,  1.5, None,  2.5, "x", "Debt-to-equity")
    _add("inventory_turnover",     None, None,  None, None, None, None, "x/yr", "N/A for services")
    _add("days_sales_outstanding",  25.0, 50.0, 15.0, 70.0, None, 100.0, "days", "DSO")
    _add("ebitda_margin_pct",       10.0, 25.0,  5.0, 35.0,  0.0, 45.0, "%", "EBITDA margin")
    _add("roe",                     12.0, 35.0,  8.0, 45.0,  0.0, 55.0, "%", "Return on equity")
    _add("roa",                      5.0, 18.0,  3.0, 25.0,  0.0, 30.0, "%", "Return on assets")
    _add("ga_to_revenue_pct",        5.0, 15.0,  3.0, 20.0, None, 30.0, "%", "G&A / Revenue")
    _add("asset_turnover",           1.0,  3.0,  0.5,  4.0,  0.3,  5.0, "x", "Asset turnover")
    _add("operating_margin_pct",     8.0, 20.0,  4.0, 28.0,  0.0, 35.0, "%", "Operating margin")
    _add("wholesale_margin_pct",    30.0, 55.0, 20.0, 65.0, 10.0, 75.0, "%", "Wholesale margin")
    _add("retail_margin_pct",       40.0, 70.0, 25.0, 80.0, 15.0, 85.0, "%", "Retail margin")
    return p


def _build_construction() -> IndustryProfile:
    p = IndustryProfile(
        industry_id="construction",
        industry_name="Construction & Real Estate",
        region="global",
        metadata={"examples": ["General contractors", "Developers", "Civil"]},
    )
    _add = lambda m, hmin, hmax, wmin, wmax, cb, ca, u, d: p.benchmarks.__setitem__(
        m, BenchmarkThreshold(m, hmin, hmax, wmin, wmax, cb, ca, u, d))
    _add("gross_margin_pct",       10.0, 25.0,  6.0, 30.0,  3.0, 40.0, "%", "Construction gross margin")
    _add("net_margin_pct",          2.0,  6.0,  1.0,  9.0,  0.0, 12.0, "%", "Net profit margin")
    _add("current_ratio",           1.3,  2.5,  1.0,  3.5,  0.8,  4.5, "x", "Current ratio")
    _add("quick_ratio",             0.8,  1.5,  0.5,  2.0,  0.3,  3.0, "x", "Quick ratio")
    _add("debt_to_equity",          0.8,  2.5,  0.5,  3.5, None,  5.0, "x", "Debt-to-equity")
    _add("inventory_turnover",      4.0,  8.0,  2.0, 12.0,  1.0, 15.0, "x/yr", "Inventory turnover")
    _add("days_sales_outstanding",  40.0, 75.0, 25.0, 90.0, None, 120.0, "days", "DSO")
    _add("ebitda_margin_pct",        5.0, 12.0,  3.0, 16.0,  0.0, 20.0, "%", "EBITDA margin")
    _add("roe",                      6.0, 18.0,  3.0, 25.0,  0.0, 35.0, "%", "Return on equity")
    _add("roa",                      2.0,  8.0,  1.0, 12.0,  0.0, 15.0, "%", "Return on assets")
    _add("ga_to_revenue_pct",        2.0,  6.0,  1.5,  8.0, None, 12.0, "%", "G&A / Revenue")
    _add("asset_turnover",           0.8,  1.8,  0.5,  2.5,  0.3,  3.5, "x", "Asset turnover")
    _add("operating_margin_pct",     3.0, 10.0,  1.5, 14.0,  0.0, 18.0, "%", "Operating margin")
    _add("wholesale_margin_pct",     8.0, 18.0,  4.0, 25.0,  2.0, 30.0, "%", "Wholesale margin")
    _add("retail_margin_pct",       15.0, 30.0, 10.0, 38.0,  5.0, 45.0, "%", "Retail margin")
    return p


def _build_agriculture() -> IndustryProfile:
    p = IndustryProfile(
        industry_id="agriculture",
        industry_name="Agriculture & Agribusiness",
        region="global",
        metadata={"examples": ["Farming", "Food processing", "Livestock"]},
    )
    _add = lambda m, hmin, hmax, wmin, wmax, cb, ca, u, d: p.benchmarks.__setitem__(
        m, BenchmarkThreshold(m, hmin, hmax, wmin, wmax, cb, ca, u, d))
    _add("gross_margin_pct",       15.0, 30.0, 10.0, 40.0,  5.0, 50.0, "%", "Agriculture gross margin")
    _add("net_margin_pct",          3.0,  8.0,  1.5, 12.0,  0.0, 15.0, "%", "Net profit margin")
    _add("current_ratio",           1.2,  2.0,  1.0,  3.0,  0.7,  4.0, "x", "Current ratio")
    _add("quick_ratio",             0.5,  1.0,  0.3,  1.5,  0.2,  2.0, "x", "Quick ratio")
    _add("debt_to_equity",          0.5,  2.0,  0.3,  3.0, None,  4.0, "x", "Debt-to-equity")
    _add("inventory_turnover",      3.0,  8.0,  2.0, 10.0,  1.0, 14.0, "x/yr", "Inventory turnover")
    _add("days_sales_outstanding",  20.0, 50.0, 10.0, 70.0, None, 100.0, "days", "DSO")
    _add("ebitda_margin_pct",        5.0, 15.0,  3.0, 20.0,  0.0, 25.0, "%", "EBITDA margin")
    _add("roe",                      5.0, 18.0,  3.0, 25.0,  0.0, 35.0, "%", "Return on equity")
    _add("roa",                      2.0,  8.0,  1.0, 12.0,  0.0, 16.0, "%", "Return on assets")
    _add("ga_to_revenue_pct",        2.0,  5.0,  1.5,  7.0, None, 10.0, "%", "G&A / Revenue")
    _add("asset_turnover",           0.5,  1.5,  0.3,  2.0,  0.2,  3.0, "x", "Asset turnover")
    _add("operating_margin_pct",     4.0, 12.0,  2.0, 16.0,  0.0, 20.0, "%", "Operating margin")
    _add("wholesale_margin_pct",    10.0, 22.0,  5.0, 30.0,  2.0, 40.0, "%", "Wholesale margin")
    _add("retail_margin_pct",       18.0, 35.0, 12.0, 45.0,  8.0, 50.0, "%", "Retail margin")
    return p


# ---------------------------------------------------------------------------
# BenchmarkEngine
# ---------------------------------------------------------------------------

class BenchmarkEngine:
    """Configurable benchmark engine with multi-industry support."""

    def __init__(self):
        self._profiles: Dict[str, IndustryProfile] = {}
        self._active_industry: str = "fuel_distribution"
        self._build_profiles()

    def _build_profiles(self) -> None:
        builders = [
            _build_fuel_distribution,
            _build_retail_general,
            _build_manufacturing,
            _build_services,
            _build_construction,
            _build_agriculture,
        ]
        for builder in builders:
            profile = builder()
            self._profiles[profile.industry_id] = profile

    def set_industry(self, industry_id: str) -> None:
        if industry_id not in self._profiles:
            raise ValueError(f"Unknown industry: {industry_id}. Available: {list(self._profiles.keys())}")
        self._active_industry = industry_id

    def get_industry(self) -> str:
        return self._active_industry

    def list_industries(self) -> List[Dict[str, str]]:
        return [
            {"industry_id": p.industry_id, "industry_name": p.industry_name, "region": p.region,
             "benchmark_count": len(p.benchmarks)}
            for p in self._profiles.values()
        ]

    def get_profile(self, industry_id: str = None) -> Optional[IndustryProfile]:
        iid = industry_id or self._active_industry
        return self._profiles.get(iid)

    def _compute_company_benchmarks(self, company_id: int = None) -> Dict[str, float]:
        """
        Compute the company's own historical averages as benchmarks.

        Returns a dict of metric_name -> historical average value.
        """
        try:
            from app.services.data_store import data_store

            companies = data_store.list_companies()
            cid = company_id or (companies[0]["id"] if companies else None)
            if not cid:
                return {}

            periods = data_store.get_all_periods(cid)
            metrics_history: Dict[str, List[float]] = {}

            for period in periods:
                fin = data_store.get_financials(cid, period)
                if not fin or not fin.get("revenue"):
                    continue
                rev = fin["revenue"]
                gp = fin.get("gross_profit", 0) or 0
                np_ = fin.get("net_profit", 0) or 0
                ebitda = fin.get("ebitda", 0) or 0
                cogs = fin.get("cogs", 0) or 0
                ga = fin.get("ga_expenses", 0) or fin.get("admin_expenses", 0) or 0

                if rev:
                    metrics_history.setdefault("gross_margin_pct", []).append(gp / rev * 100)
                    metrics_history.setdefault("net_margin_pct", []).append(np_ / rev * 100)
                    metrics_history.setdefault("ebitda_margin_pct", []).append(ebitda / rev * 100)
                    metrics_history.setdefault("cogs_to_revenue_pct", []).append(abs(cogs) / rev * 100)
                    if ga:
                        metrics_history.setdefault("ga_to_revenue_pct", []).append(abs(ga) / rev * 100)

            return {k: _stats.mean(v) for k, v in metrics_history.items() if v}
        except Exception as e:
            logger.warning("Failed to compute company benchmarks: %s", e)
            return {}

    def compare(
        self,
        metrics: Dict[str, float],
        industry_id: str = None,
        company_id: int = None,
    ) -> List[BenchmarkComparison]:
        """Compare actual financial metrics against industry benchmarks + company history."""
        iid = industry_id or self._active_industry
        profile = self._profiles.get(iid)
        if not profile:
            return []

        # Pre-compute company history once for all metrics
        company_avgs = self._compute_company_benchmarks(company_id)

        results = []
        for metric_name, value in metrics.items():
            comparison = self.compare_single(metric_name, value, iid, company_avgs=company_avgs)
            if comparison:
                results.append(comparison)
        return results

    def compare_single(
        self,
        metric: str,
        value: float,
        industry_id: str = None,
        company_avgs: Dict[str, float] = None,
    ) -> Optional[BenchmarkComparison]:
        """
        Compare a single metric against its benchmark.

        Enhanced to include company's own historical average and trend direction.
        """
        iid = industry_id or self._active_industry
        profile = self._profiles.get(iid)
        if not profile:
            return BenchmarkComparison(
                industry=iid, metric=metric, actual_value=value,
                status="unknown", benchmark_range="N/A",
                deviation_pct=0, narrative=f"Industry {iid} not found",
            )
        # Normalize metric name: gross_margin -> gross_margin_pct
        if metric not in profile.benchmarks:
            alternatives = [f"{metric}_pct", metric.replace("_pct", ""), metric.replace("_ratio", "")]
            for alt in alternatives:
                if alt in profile.benchmarks:
                    metric = alt
                    break
        if metric not in profile.benchmarks:
            return BenchmarkComparison(
                industry=iid, metric=metric, actual_value=value,
                status="unknown", benchmark_range="N/A",
                deviation_pct=0.0, narrative=f"No benchmark for {metric} in {iid}",
            )

        b = profile.benchmarks[metric]

        # Skip if benchmark has no range defined
        if b.healthy_min is None and b.healthy_max is None:
            return BenchmarkComparison(
                industry=iid, metric=metric, actual_value=value,
                status="unknown", benchmark_range="N/A",
                deviation_pct=0.0, narrative=f"Benchmark not applicable for {metric} in {iid}",
            )

        hmin = b.healthy_min if b.healthy_min is not None else float("-inf")
        hmax = b.healthy_max if b.healthy_max is not None else float("inf")

        # Determine status
        if hmin <= value <= hmax:
            status = "healthy"
        elif b.critical_below is not None and value < b.critical_below:
            status = "critical"
        elif b.critical_above is not None and value > b.critical_above:
            status = "critical"
        elif (b.warning_min is not None and value < b.warning_min) or \
             (b.warning_max is not None and value > b.warning_max):
            status = "warning"
        else:
            status = "warning"

        # Deviation from healthy center
        center = (hmin + hmax) / 2 if hmin != float("-inf") and hmax != float("inf") else value
        deviation = ((value - center) / center * 100) if center != 0 else 0.0

        benchmark_range = f"{b.healthy_min}-{b.healthy_max}{b.unit}"

        # Company history enrichment
        if company_avgs is None:
            company_avgs = self._compute_company_benchmarks()

        company_avg = company_avgs.get(metric)
        trend = None
        data_source = "industry_profile"

        if company_avg is not None:
            data_source = "company_history+industry"
            # Determine trend: current vs own historical average
            if abs(company_avg) > 0.01:
                delta_pct = (value - company_avg) / abs(company_avg) * 100
                # For metrics where higher is better (margins, ratios)
                higher_is_better = metric not in ("cogs_to_revenue_pct", "debt_to_equity",
                                                   "days_sales_outstanding")
                if abs(delta_pct) < 3:
                    trend = "stable"
                elif delta_pct > 0:
                    trend = "improving" if higher_is_better else "declining"
                else:
                    trend = "declining" if higher_is_better else "improving"

        narrative = self._generate_narrative(metric, value, status, b, iid,
                                              company_avg=company_avg, trend=trend)

        return BenchmarkComparison(
            industry=iid, metric=metric, actual_value=value,
            status=status, benchmark_range=benchmark_range,
            deviation_pct=deviation, narrative=narrative,
            company_avg=company_avg,
            trend_vs_own_history=trend,
            data_source=data_source,
        )

    def _generate_narrative(self, metric: str, value: float, status: str,
                            b: BenchmarkThreshold, industry: str,
                            company_avg: Optional[float] = None,
                            trend: Optional[str] = None) -> str:
        metric_label = metric.replace("_", " ").replace("pct", "%")
        if status == "healthy":
            base = f"{metric_label} of {value:.1f}{b.unit} is within the healthy range ({b.healthy_min}-{b.healthy_max}{b.unit}) for {industry}."
        elif status == "critical":
            base = f"{metric_label} of {value:.1f}{b.unit} is CRITICAL - significantly outside the healthy range ({b.healthy_min}-{b.healthy_max}{b.unit}) for {industry}. Immediate attention required."
        else:
            base = f"{metric_label} of {value:.1f}{b.unit} is in WARNING territory - outside the healthy range ({b.healthy_min}-{b.healthy_max}{b.unit}) for {industry}. Monitor closely."

        # Enrich with company history if available
        if company_avg is not None and trend is not None:
            base += f" Company historical avg: {company_avg:.1f}{b.unit} (trend: {trend})."

        return base

    def to_kg_entities(self, industry_id: str = None) -> List[Dict]:
        """Generate KG-compatible entity dicts for benchmarks of a given industry."""
        iid = industry_id or self._active_industry
        profile = self._profiles.get(iid)
        if not profile:
            return []
        entities = []
        for metric, b in profile.benchmarks.items():
            entities.append({
                "entity_id": f"benchmark_{iid}_{metric}",
                "entity_type": "benchmark",
                "label_en": f"{profile.industry_name}: {b.description}",
                "properties": {
                    "industry": iid,
                    "metric": metric,
                    "healthy_min": b.healthy_min,
                    "healthy_max": b.healthy_max,
                    "warning_min": b.warning_min,
                    "warning_max": b.warning_max,
                    "unit": b.unit,
                    "description": b.description,
                },
            })
        return entities


# Module singleton
benchmark_engine = BenchmarkEngine()
