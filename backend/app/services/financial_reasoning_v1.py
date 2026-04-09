"""
FinAI Financial Reasoning Engine — Phase E: Financial Cognition.
=================================================================
Provides causal analysis, trend decomposition, and scenario simulation
grounded in the Knowledge Graph.

This is the "why" layer — translating raw numbers into financial reasoning:
  - WHY did gross margin drop from 32% to 18%?
  - WHAT caused the EBITDA spike in Q3?
  - IF COGS rises 5%, WHAT happens to net profit?

Architecture:
  - FinancialReasoningEngine: main entry point
  - CausalChain: structured representation of cause → effect
  - VarianceDecomposition: price/volume/mix breakdown
  - ScenarioSimulator: what-if analysis
  - TrendAnalyzer: period-over-period decomposition

Usage:
    from app.services.financial_reasoning import reasoning_engine

    chain = reasoning_engine.explain_metric_change(
        metric="gross_margin_pct",
        from_value=32.0,
        to_value=18.0,
        context={"revenue": 50_000_000, "cogs": 41_000_000, ...},
    )
    print(chain.narrative)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class CausalFactor:
    """One contributing factor in a causal chain."""
    factor: str                    # e.g. "COGS increase"
    impact_direction: str          # "negative" | "positive" | "neutral"
    magnitude: str                 # e.g. "large" | "moderate" | "minor"
    impact_pct: Optional[float]    # Estimated % impact on the metric
    explanation: str               # Human-readable explanation
    kg_context: Optional[str] = None  # Related KG entity description
    account_codes: List[str] = field(default_factory=list)


@dataclass
class CausalChain:
    """Complete causal analysis for a metric change."""
    metric: str
    from_value: float
    to_value: float
    period_from: str
    period_to: str
    change_absolute: float
    change_pct: float
    severity: str                  # "critical" | "high" | "medium" | "low" | "normal"
    primary_cause: str             # One-sentence summary
    factors: List[CausalFactor]    # Contributing factors, ranked by impact
    narrative: str                 # Multi-paragraph explanation
    recommendations: List[str]     # Actionable recommendations
    kg_entities_used: List[str]    # KG entity IDs that informed the analysis


@dataclass
class VarianceDecomposition:
    """Price-volume-mix breakdown of revenue or margin change."""
    metric: str
    total_variance: float
    price_variance: float
    volume_variance: float
    mix_variance: float
    other_variance: float
    dominant_driver: str           # "price" | "volume" | "mix"
    narrative: str


@dataclass
class ScenarioResult:
    """Result of a what-if scenario simulation."""
    scenario_name: str
    base_revenue: float
    base_gross_profit: float
    base_ebitda: float
    base_net_profit: float
    scenario_revenue: float
    scenario_gross_profit: float
    scenario_ebitda: float
    scenario_net_profit: float
    revenue_change_pct: float
    gross_profit_change_pct: float
    ebitda_change_pct: float
    net_profit_change_pct: float
    narrative: str
    risk_level: str                # "low" | "medium" | "high" | "critical"


# ── Metric metadata ───────────────────────────────────────────────────────────

_METRIC_META = {
    "revenue": {
        "label": "Net Revenue",
        "unit": "GEL",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -20, "warning_drop": -10, "notable_rise": 20},
    },
    "gross_profit": {
        "label": "Gross Profit",
        "unit": "GEL",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -30, "warning_drop": -15, "notable_rise": 30},
    },
    "gross_margin_pct": {
        "label": "Gross Margin %",
        "unit": "%",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -5, "warning_drop": -2, "notable_rise": 5},
        "benchmark_low": 1.0,
        "benchmark_high": 15.0,
    },
    "ebitda": {
        "label": "EBITDA",
        "unit": "GEL",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -30, "warning_drop": -15},
    },
    "ebitda_margin_pct": {
        "label": "EBITDA Margin %",
        "unit": "%",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -3, "warning_drop": -1},
        "benchmark_low": 2.0,
        "benchmark_high": 6.0,
    },
    "net_profit": {
        "label": "Net Profit",
        "unit": "GEL",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -50, "warning_drop": -20},
    },
    "net_margin_pct": {
        "label": "Net Profit Margin %",
        "unit": "%",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -2, "warning_drop": -1},
    },
    "cogs": {
        "label": "Cost of Goods Sold",
        "unit": "GEL",
        "direction": "lower_better",
        "thresholds": {"critical_rise": 20, "warning_rise": 10},
    },
    "ga_expenses": {
        "label": "G&A Expenses",
        "unit": "GEL",
        "direction": "lower_better",
        "thresholds": {"critical_rise": 30, "warning_rise": 15},
    },
    "wholesale_margin_pct": {
        "label": "Wholesale Margin %",
        "unit": "%",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -3, "warning_drop": -1},
        "benchmark_low": 1.0,
        "benchmark_high": 4.0,
        "negative_acceptable": True,
    },
    "retail_margin_pct": {
        "label": "Retail Margin %",
        "unit": "%",
        "direction": "higher_better",
        "thresholds": {"critical_drop": -5, "warning_drop": -2},
        "benchmark_low": 8.0,
        "benchmark_high": 15.0,
    },
}


class FinancialReasoningEngine:
    """
    Phase E Financial Cognition — Causal analysis and scenario simulation.

    Provides grounded financial reasoning using:
    1. Rule-based causal logic (for known patterns)
    2. Knowledge Graph context (for regulatory and benchmark grounding)
    3. Structured output (CausalChain, ScenarioResult)

    The LLM uses this as a structured reasoning scaffold — it receives
    pre-computed causal factors with KG context, reducing hallucination.
    """

    def explain_metric_change(
        self,
        metric: str,
        from_value: float,
        to_value: float,
        period_from: str = "Previous Period",
        period_to: str = "Current Period",
        context: Optional[Dict[str, Any]] = None,
    ) -> CausalChain:
        """
        Explain a change in a financial metric with causal analysis.

        Args:
            metric: Key from _METRIC_META (e.g. "gross_margin_pct")
            from_value: Previous period value
            to_value: Current period value
            period_from: Label for the previous period
            period_to: Label for the current period
            context: Dict with supporting financial data for the analysis

        Returns:
            CausalChain with factors, narrative, and recommendations
        """
        context = context or {}
        change_abs = to_value - from_value
        change_pct = (change_abs / abs(from_value) * 100) if from_value != 0 else 0.0

        meta = _METRIC_META.get(metric, {"label": metric, "unit": "", "direction": "higher_better",
                                          "thresholds": {}})
        severity = self._classify_severity(metric, change_pct, to_value, meta)

        # Route to specific explainer
        explainer = self._get_explainer(metric)
        factors, primary_cause, recommendations, kg_ids = explainer(
            metric, from_value, to_value, change_abs, change_pct, context, meta
        )

        narrative = self._build_narrative(
            metric, from_value, to_value, change_abs, change_pct,
            period_from, period_to, severity, primary_cause, factors, meta
        )

        return CausalChain(
            metric=metric,
            from_value=from_value,
            to_value=to_value,
            period_from=period_from,
            period_to=period_to,
            change_absolute=change_abs,
            change_pct=change_pct,
            severity=severity,
            primary_cause=primary_cause,
            factors=factors,
            narrative=narrative,
            recommendations=recommendations,
            kg_entities_used=kg_ids,
        )

    def decompose_revenue_variance(
        self,
        revenue_from: float,
        revenue_to: float,
        volume_from: float,
        volume_to: float,
        price_from: float,
        price_to: float,
    ) -> VarianceDecomposition:
        """Decompose revenue change into price, volume, and mix components."""
        total_variance = revenue_to - revenue_from

        # Classic price-volume decomposition
        price_variance = (price_to - price_from) * volume_to
        volume_variance = (volume_to - volume_from) * price_from
        mix_variance = 0.0  # Simplified — full mix needs product breakdown
        other_variance = total_variance - price_variance - volume_variance - mix_variance

        abs_pv = abs(price_variance)
        abs_vv = abs(volume_variance)
        dominant = "price" if abs_pv >= abs_vv else "volume"

        pct = lambda v: f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"
        narrative = (
            f"Revenue changed by {_fmt_gel(total_variance)} ({pct(total_variance/revenue_from*100 if revenue_from else 0)}).\n"
            f"Price effect: {_fmt_gel(price_variance)} "
            f"({'price increased' if price_variance > 0 else 'price declined'} "
            f"from {_fmt_gel(price_from)}/unit to {_fmt_gel(price_to)}/unit).\n"
            f"Volume effect: {_fmt_gel(volume_variance)} "
            f"({'volume grew' if volume_variance > 0 else 'volume declined'} "
            f"from {volume_from:,.0f} to {volume_to:,.0f} units).\n"
            f"Dominant driver: {dominant.upper()} effect ({pct(abs(price_variance if dominant == 'price' else volume_variance)/abs(total_variance)*100 if total_variance else 0)} of total change)."
        )

        return VarianceDecomposition(
            metric="revenue",
            total_variance=total_variance,
            price_variance=price_variance,
            volume_variance=volume_variance,
            mix_variance=mix_variance,
            other_variance=other_variance,
            dominant_driver=dominant,
            narrative=narrative,
        )

    def simulate_scenario(
        self,
        scenario_name: str,
        base: Dict[str, float],
        changes: Dict[str, float],
    ) -> ScenarioResult:
        """
        Simulate a financial scenario by applying parameter changes to a base case.

        Args:
            scenario_name: Descriptive name (e.g. "10% COGS increase")
            base: Dict with base case financials (revenue, cogs, ga_expenses, etc.)
            changes: Dict of parameter changes as percentages (e.g. {"cogs_pct": 5.0})

        Returns:
            ScenarioResult comparing base to scenario financials
        """
        # Extract base case
        rev = base.get("revenue", 0.0)
        cogs = base.get("cogs", 0.0)
        ga = base.get("ga_expenses", 0.0)
        da = base.get("depreciation", 0.0)
        finance = base.get("finance_expense", 0.0)
        tax_rate = base.get("tax_rate", 0.15)

        base_gp = rev - cogs
        base_ebitda = base_gp - ga
        base_ebit = base_ebitda - da
        base_ebt = base_ebit - finance
        base_np = base_ebt * (1 - tax_rate)

        # Apply scenario changes
        s_rev = rev * (1 + changes.get("revenue_pct", 0) / 100)
        s_cogs = cogs * (1 + changes.get("cogs_pct", 0) / 100)
        s_ga = ga * (1 + changes.get("ga_pct", 0) / 100)
        s_da = da * (1 + changes.get("da_pct", 0) / 100)
        s_finance = finance * (1 + changes.get("finance_pct", 0) / 100)

        # Also allow absolute changes
        s_rev += changes.get("revenue_abs", 0)
        s_cogs += changes.get("cogs_abs", 0)
        s_ga += changes.get("ga_abs", 0)

        s_gp = s_rev - s_cogs
        s_ebitda = s_gp - s_ga
        s_ebit = s_ebitda - s_da
        s_ebt = s_ebit - s_finance
        s_np = s_ebt * (1 - tax_rate)

        def pct_chg(new, old):
            return (new - old) / abs(old) * 100 if old != 0 else 0.0

        gp_chg = pct_chg(s_gp, base_gp)
        ebitda_chg = pct_chg(s_ebitda, base_ebitda)
        np_chg = pct_chg(s_np, base_np)

        risk = "low"
        if ebitda_chg < -30 or s_ebitda < 0:
            risk = "critical"
        elif ebitda_chg < -15:
            risk = "high"
        elif ebitda_chg < -5:
            risk = "medium"

        # Build narrative
        change_desc = []
        for k, v in changes.items():
            if v != 0:
                label = k.replace("_pct", " (%)").replace("_abs", " (GEL abs)")
                change_desc.append(f"{label}: {'+' if v >= 0 else ''}{v:,.1f}")

        narrative = (
            f"Scenario: {scenario_name}\n"
            f"Changes applied: {', '.join(change_desc) if change_desc else 'none'}\n\n"
            f"Financial Impact:\n"
            f"  Gross Profit: {_fmt_gel(base_gp)} → {_fmt_gel(s_gp)} ({_pct_str(gp_chg)})\n"
            f"  EBITDA: {_fmt_gel(base_ebitda)} → {_fmt_gel(s_ebitda)} ({_pct_str(ebitda_chg)})\n"
            f"  Net Profit: {_fmt_gel(base_np)} → {_fmt_gel(s_np)} ({_pct_str(np_chg)})\n\n"
        )

        if risk == "critical":
            narrative += "⚠ CRITICAL: This scenario makes the business EBITDA-negative or near-insolvent."
        elif risk == "high":
            narrative += "WARNING: Significant profitability deterioration. Management action required."
        elif risk == "medium":
            narrative += "CAUTION: Moderate profitability impact. Monitor closely."
        else:
            narrative += "LOW RISK: Business remains profitable with adequate margins."

        return ScenarioResult(
            scenario_name=scenario_name,
            base_revenue=rev, base_gross_profit=base_gp,
            base_ebitda=base_ebitda, base_net_profit=base_np,
            scenario_revenue=s_rev, scenario_gross_profit=s_gp,
            scenario_ebitda=s_ebitda, scenario_net_profit=s_np,
            revenue_change_pct=pct_chg(s_rev, rev),
            gross_profit_change_pct=gp_chg,
            ebitda_change_pct=ebitda_chg,
            net_profit_change_pct=np_chg,
            narrative=narrative,
            risk_level=risk,
        )

    def build_liquidity_analysis(self, balance_sheet: Dict[str, float]) -> Dict[str, Any]:
        """Compute all liquidity ratios and flag any issues."""
        ca = balance_sheet.get("total_current_assets", 0)
        cl = balance_sheet.get("total_current_liabilities", 0)
        cash = balance_sheet.get("cash", 0)
        rec = balance_sheet.get("receivables", 0)
        inv = balance_sheet.get("inventory", 0)
        total_assets = balance_sheet.get("total_assets", 0)
        total_debt = balance_sheet.get("total_debt", 0)
        equity = balance_sheet.get("total_equity", balance_sheet.get("equity", 0))

        current_ratio = ca / cl if cl else None
        quick_ratio = (cash + rec) / cl if cl else None
        cash_ratio = cash / cl if cl else None
        wc = ca - cl
        debt_to_equity = total_debt / equity if equity else None
        debt_to_assets = total_debt / total_assets if total_assets else None

        flags = []
        if current_ratio is not None and current_ratio < 1.0:
            flags.append({"flag": "current_ratio_below_1", "severity": "critical",
                          "message": f"Current ratio {current_ratio:.2f} < 1.0 — unable to cover short-term liabilities"})
        elif current_ratio is not None and current_ratio < 1.5:
            flags.append({"flag": "current_ratio_low", "severity": "warning",
                          "message": f"Current ratio {current_ratio:.2f} < 1.5 — limited liquidity buffer"})

        if debt_to_equity is not None and debt_to_equity > 3.0:
            flags.append({"flag": "high_leverage", "severity": "high",
                          "message": f"D/E ratio {debt_to_equity:.2f} > 3.0 — excessive leverage"})

        if wc < 0:
            flags.append({"flag": "negative_working_capital", "severity": "critical",
                          "message": f"Negative working capital: {_fmt_gel(wc)}"})

        return {
            "ratios": {
                "current_ratio": round(current_ratio, 3) if current_ratio is not None else None,
                "quick_ratio": round(quick_ratio, 3) if quick_ratio is not None else None,
                "cash_ratio": round(cash_ratio, 3) if cash_ratio is not None else None,
                "working_capital": round(wc),
                "debt_to_equity": round(debt_to_equity, 3) if debt_to_equity is not None else None,
                "debt_to_assets": round(debt_to_assets, 3) if debt_to_assets is not None else None,
            },
            "flags": flags,
            "health": "critical" if any(f["severity"] == "critical" for f in flags)
                      else "warning" if flags else "healthy",
        }

    def detect_accounting_issues(self, pl_data: Dict[str, float],
                                  bs_data: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Run rule-based accounting consistency checks.
        Checks: BS equation, negative equity, impossible margins, etc.
        """
        issues = []

        # 1. Balance sheet equation
        assets = bs_data.get("total_assets", 0)
        liabilities = bs_data.get("total_liabilities", 0)
        equity = bs_data.get("total_equity", bs_data.get("equity", 0))
        if assets != 0:
            imbalance = abs(assets - (liabilities + equity))
            imbalance_pct = imbalance / assets * 100
            if imbalance_pct > 0.01:  # Allow tiny rounding
                issues.append({
                    "type": "balance_sheet_imbalance",
                    "severity": "critical",
                    "message": f"Assets ({_fmt_gel(assets)}) ≠ Liabilities + Equity ({_fmt_gel(liabilities+equity)}). Imbalance: {_fmt_gel(imbalance)}",
                    "impact": "Financial statements cannot be trusted"
                })

        # 2. Revenue negativity
        rev = pl_data.get("revenue", 0)
        if rev < 0:
            issues.append({
                "type": "negative_revenue",
                "severity": "critical",
                "message": f"Revenue is negative: {_fmt_gel(rev)}. Likely data mapping error.",
                "impact": "All P&L ratios will be inverted"
            })

        # 3. COGS > Revenue (wholesale loss-leader is acceptable, but >110% is suspicious)
        cogs = pl_data.get("cogs", 0)
        if rev > 0 and cogs / rev > 1.10:
            issues.append({
                "type": "extreme_cogs_ratio",
                "severity": "warning",
                "message": f"COGS/Revenue = {cogs/rev*100:.1f}% (>{110}%). Extreme loss. Check data mapping.",
                "impact": "Verify account classification — ensure COGS accounts are correctly mapped"
            })

        # 4. Negative equity
        if equity < 0:
            issues.append({
                "type": "negative_equity",
                "severity": "critical",
                "message": f"Shareholders equity is negative: {_fmt_gel(equity)}",
                "impact": "Technical insolvency — liabilities exceed assets"
            })

        # 5. Gross profit > Revenue (impossible)
        gp = pl_data.get("gross_profit", 0)
        if rev > 0 and gp > rev:
            issues.append({
                "type": "gross_profit_exceeds_revenue",
                "severity": "critical",
                "message": f"Gross profit ({_fmt_gel(gp)}) > Revenue ({_fmt_gel(rev)}). Impossible — negative COGS.",
                "impact": "COGS mapping error — some cost accounts assigned to revenue"
            })

        # 6. EBITDA > Gross profit (impossible without negative G&A)
        ebitda = pl_data.get("ebitda", 0)
        if gp > 0 and ebitda > gp:
            issues.append({
                "type": "ebitda_exceeds_gross_profit",
                "severity": "warning",
                "message": f"EBITDA ({_fmt_gel(ebitda)}) > Gross Profit ({_fmt_gel(gp)}). Implies negative G&A.",
                "impact": "Check G&A classification — some G&A items may be mapped as revenue"
            })

        return issues

    # ── Private: Explainer Dispatch ───────────────────────────────────────────

    def _get_explainer(self, metric: str):
        """Return the appropriate explainer function for the metric."""
        explainers = {
            "gross_margin_pct": self._explain_gross_margin_change,
            "gross_profit": self._explain_gross_margin_change,
            "revenue": self._explain_revenue_change,
            "ebitda": self._explain_ebitda_change,
            "ebitda_margin_pct": self._explain_ebitda_change,
            "net_profit": self._explain_net_profit_change,
            "cogs": self._explain_cogs_change,
            "ga_expenses": self._explain_ga_change,
            "wholesale_margin_pct": self._explain_wholesale_margin,
            "retail_margin_pct": self._explain_retail_margin,
        }
        return explainers.get(metric, self._explain_generic)

    def _explain_gross_margin_change(
        self, metric, from_val, to_val, change_abs, change_pct, ctx, meta
    ) -> Tuple[List[CausalFactor], str, List[str], List[str]]:
        """Explain gross margin / gross profit change with causal factors."""
        factors = []
        kg_ids = ["ratio_gross_margin", "bench_gross_margin_product_mix"]

        # Analyze from context
        rev_from = ctx.get("revenue_from", ctx.get("revenue", 0))
        rev_to = ctx.get("revenue_to", ctx.get("revenue", 0))
        cogs_from = ctx.get("cogs_from", ctx.get("cogs", 0))
        cogs_to = ctx.get("cogs_to", ctx.get("cogs", 0))
        ws_margin_from = ctx.get("wholesale_margin_pct_from")
        ws_margin_to = ctx.get("wholesale_margin_pct_to")
        rt_margin_from = ctx.get("retail_margin_pct_from")
        rt_margin_to = ctx.get("retail_margin_pct_to")

        declining = change_abs < 0

        # Factor 1: COGS movement
        if cogs_from and cogs_to and rev_from:
            cogs_ratio_from = cogs_from / rev_from * 100
            cogs_ratio_to = cogs_to / rev_to * 100 if rev_to else cogs_ratio_from
            cogs_ratio_change = cogs_ratio_to - cogs_ratio_from
            if abs(cogs_ratio_change) > 0.5:
                factors.append(CausalFactor(
                    factor="COGS ratio change",
                    impact_direction="negative" if cogs_ratio_change > 0 else "positive",
                    magnitude="large" if abs(cogs_ratio_change) > 5 else "moderate",
                    impact_pct=-cogs_ratio_change,
                    explanation=(
                        f"COGS as % of revenue moved from {cogs_ratio_from:.1f}% to {cogs_ratio_to:.1f}% "
                        f"({'higher costs compress margin' if cogs_ratio_change > 0 else 'lower costs improve margin'}). "
                        "Key COGS drivers: fuel purchase price (NYX Core Thinker landing cost), excise tax, freight."
                    ),
                    kg_context="COGS = Account 6110 + Account 7310 + Account 8230 (per KG formula)",
                    account_codes=["6110", "7310", "8230"],
                ))
                kg_ids.append("formula_fml_cogs_fuel")

        # Factor 2: Wholesale margin compression
        if ws_margin_from is not None and ws_margin_to is not None:
            ws_change = ws_margin_to - ws_margin_from
            factors.append(CausalFactor(
                factor="Wholesale margin shift",
                impact_direction="negative" if ws_change < 0 else "positive",
                magnitude="large" if abs(ws_change) > 3 else "moderate" if abs(ws_change) > 1 else "minor",
                impact_pct=ws_change * ctx.get("wholesale_revenue_pct", 0.6),
                explanation=(
                    f"Wholesale margin {'compressed' if ws_change < 0 else 'improved'} "
                    f"from {ws_margin_from:.1f}% to {ws_margin_to:.1f}% "
                    f"({ws_change:+.1f}pp). Industry benchmark: 1–4%. "
                    + ("Negative wholesale margin is acceptable if retail compensates."
                       if ws_margin_to < 0 else "")
                ),
                kg_context="Wholesale benchmark: 1-4% (KG: bench_benchmark_wholesale_margin)",
                account_codes=["6110"],
            ))
            kg_ids.extend(["bench_benchmark_wholesale_margin", "ratio_ratio_wholesale_margin"])

        # Factor 3: Retail margin
        if rt_margin_from is not None and rt_margin_to is not None:
            rt_change = rt_margin_to - rt_margin_from
            if abs(rt_change) > 1:
                factors.append(CausalFactor(
                    factor="Retail margin shift",
                    impact_direction="negative" if rt_change < 0 else "positive",
                    magnitude="large" if abs(rt_change) > 4 else "moderate",
                    impact_pct=rt_change * ctx.get("retail_revenue_pct", 0.4),
                    explanation=(
                        f"Retail margin {'declined' if rt_change < 0 else 'improved'} "
                        f"from {rt_margin_from:.1f}% to {rt_margin_to:.1f}% "
                        f"({rt_change:+.1f}pp). Industry benchmark: 8–15%."
                    ),
                    kg_context="Retail benchmark: 8-15% (KG: bench_benchmark_retail_margin)",
                    account_codes=["6110", "6120"],
                ))

        # Factor 4: Revenue mix shift (if data available)
        ws_rev_pct_from = ctx.get("ws_rev_pct_from")
        ws_rev_pct_to = ctx.get("ws_rev_pct_to")
        if ws_rev_pct_from and ws_rev_pct_to:
            mix_change = ws_rev_pct_to - ws_rev_pct_from
            if abs(mix_change) > 3:
                factors.append(CausalFactor(
                    factor="Product mix shift (wholesale vs retail)",
                    impact_direction="negative" if mix_change > 0 else "positive",
                    magnitude="moderate",
                    impact_pct=None,
                    explanation=(
                        f"Wholesale share of revenue {'increased' if mix_change > 0 else 'decreased'} "
                        f"from {ws_rev_pct_from:.0f}% to {ws_rev_pct_to:.0f}%. "
                        "Higher wholesale % lowers blended margin (wholesale margin 1–4% vs retail 8–15%)."
                    ),
                    kg_context="DuPont mix effect (KG: formula_fml_price_volume_mix)",
                ))
                kg_ids.append("formula_fml_price_volume_mix")

        # Default factor if no context
        if not factors:
            factors.append(CausalFactor(
                factor="Margin compression" if declining else "Margin improvement",
                impact_direction="negative" if declining else "positive",
                magnitude="large" if abs(change_abs) > 5 else "moderate",
                impact_pct=change_abs,
                explanation=(
                    f"Gross margin {'fell' if declining else 'rose'} {abs(change_abs):.1f}pp from "
                    f"{from_val:.1f}% to {to_val:.1f}%. "
                    "Possible causes: fuel purchase price increase, excise tax change, product mix shift, "
                    "or competitive pricing pressure."
                ),
            ))

        # Determine primary cause
        if factors:
            primary = max(factors, key=lambda f: abs(f.impact_pct or 0) if f.impact_pct else 0)
            primary_cause = f"{primary.factor}: {primary.explanation[:120]}..."
        else:
            primary_cause = f"Gross margin {'declined' if declining else 'improved'} by {abs(change_abs):.1f}pp"

        # Recommendations
        recommendations = []
        if declining:
            recommendations.extend([
                "Review fuel procurement contracts — negotiate landed cost reduction with NYX Core Thinker/suppliers.",
                "Analyze product mix — shift volume toward higher-margin retail if possible.",
                "Conduct excise tax reconciliation to verify correct cost classification.",
                "Compare margins to industry benchmarks (wholesale 1–4%, retail 8–15%).",
            ])
            if to_val < 0:
                recommendations.insert(0, "URGENT: Gross margin is NEGATIVE — selling below cost. Immediate management review required.")

        return factors, primary_cause, recommendations, kg_ids

    def _explain_revenue_change(
        self, metric, from_val, to_val, change_abs, change_pct, ctx, meta
    ) -> Tuple[List[CausalFactor], str, List[str], List[str]]:
        factors = []
        kg_ids = ["bench_bench_fuel_volume_ws", "bench_bench_fuel_price_georgia"]

        declining = change_abs < 0

        # Price vs volume driver
        price_from = ctx.get("price_per_unit_from")
        price_to = ctx.get("price_per_unit_to")
        vol_from = ctx.get("volume_from")
        vol_to = ctx.get("volume_to")

        if price_from and price_to:
            price_chg = (price_to - price_from) / price_from * 100
            factors.append(CausalFactor(
                factor="Fuel price change",
                impact_direction="negative" if price_chg < 0 else "positive",
                magnitude="large" if abs(price_chg) > 10 else "moderate",
                impact_pct=price_chg,
                explanation=(
                    f"Average price per liter {'declined' if price_chg < 0 else 'increased'} "
                    f"from {_fmt_gel(price_from)} to {_fmt_gel(price_to)} ({price_chg:+.1f}%). "
                    "Fuel prices are linked to Brent crude (USD) and GEL/USD exchange rate."
                ),
                kg_context="Price sensitivity: $10/bbl Brent ≈ GEL 0.05-0.08/liter",
            ))
            kg_ids.append("bench_bench_gdp_georgia")

        if vol_from and vol_to:
            vol_chg = (vol_to - vol_from) / vol_from * 100
            factors.append(CausalFactor(
                factor="Sales volume change",
                impact_direction="negative" if vol_chg < 0 else "positive",
                magnitude="large" if abs(vol_chg) > 15 else "moderate",
                impact_pct=vol_chg,
                explanation=(
                    f"Volume {'declined' if vol_chg < 0 else 'grew'} "
                    f"from {vol_from:,.0f} to {vol_to:,.0f} liters ({vol_chg:+.1f}%). "
                    "Volume drivers: seasonal demand, market share, new contracts."
                ),
            ))

        if not factors:
            factors.append(CausalFactor(
                factor="Revenue change",
                impact_direction="negative" if declining else "positive",
                magnitude="large" if abs(change_pct) > 15 else "moderate",
                impact_pct=change_pct,
                explanation=(
                    f"Revenue {'fell' if declining else 'grew'} by {abs(change_pct):.1f}%. "
                    "Key drivers: fuel price changes (Brent/USD), sales volume, customer mix changes."
                ),
                kg_context="Revenue drivers: commodity price + volume + mix",
            ))

        primary_cause = f"Revenue {'decline' if declining else 'growth'} of {abs(change_pct):.1f}% driven by {factors[0].factor.lower()}"
        recommendations = []
        if declining:
            recommendations.extend([
                "Decompose change: price effect vs volume effect (price-volume-mix analysis).",
                "Check customer concentration — top 3 clients account changes.",
                "Seasonal analysis: compare to same period prior year.",
                "Review wholesale contract renewals and pricing.",
            ])

        return factors, primary_cause, recommendations, kg_ids

    def _explain_ebitda_change(
        self, metric, from_val, to_val, change_abs, change_pct, ctx, meta
    ) -> Tuple[List[CausalFactor], str, List[str], List[str]]:
        factors = []
        kg_ids = ["ratio_ratio_ebitda_margin", "bench_bench_ebitda_fuel"]

        gp_change = ctx.get("gross_profit_change", 0)
        ga_change = ctx.get("ga_change", 0)

        if gp_change:
            factors.append(CausalFactor(
                factor="Gross profit change",
                impact_direction="positive" if gp_change > 0 else "negative",
                magnitude="large" if abs(gp_change) > abs(change_abs) * 0.7 else "moderate",
                impact_pct=gp_change / abs(from_val) * 100 if from_val else None,
                explanation=f"Gross profit {'increased' if gp_change > 0 else 'decreased'} by {_fmt_gel(gp_change)}.",
            ))

        if ga_change:
            factors.append(CausalFactor(
                factor="G&A expense change",
                impact_direction="negative" if ga_change > 0 else "positive",
                magnitude="moderate",
                impact_pct=-ga_change / abs(from_val) * 100 if from_val else None,
                explanation=f"G&A expenses {'increased' if ga_change > 0 else 'decreased'} by {_fmt_gel(abs(ga_change))}.",
                account_codes=["7xxx"],
            ))

        if not factors:
            factors.append(CausalFactor(
                factor="Combined operational change",
                impact_direction="negative" if change_abs < 0 else "positive",
                magnitude="large" if abs(change_pct) > 20 else "moderate",
                impact_pct=change_pct,
                explanation=(
                    f"EBITDA {'fell' if change_abs < 0 else 'rose'} by {_fmt_gel(abs(change_abs))} ({abs(change_pct):.1f}%). "
                    "EBITDA = Gross Profit - G&A. Changes driven by margin compression or overhead growth."
                ),
            ))

        if to_val < 0:
            primary_cause = "EBITDA turned NEGATIVE — business burning cash from operations"
        else:
            primary_cause = f"EBITDA {'declined' if change_abs < 0 else 'improved'} {abs(change_pct):.1f}% due to {factors[0].factor.lower()}"

        recommendations = []
        if change_abs < 0:
            recommendations.extend([
                "Analyze gross margin deterioration: procurement cost review.",
                "Review G&A cost structure for overhead reduction opportunities.",
                "Compare EBITDA margin to industry benchmark: 2–6% for mixed distribution.",
            ])
        if to_val < 0:
            recommendations.insert(0, "CRITICAL: Negative EBITDA — immediately review cost structure and pricing.")

        return factors, primary_cause, recommendations, kg_ids

    def _explain_net_profit_change(self, metric, from_val, to_val, change_abs, change_pct, ctx, meta):
        factors = []
        kg_ids = ["ratio_ratio_net_margin"]

        ebitda_chg = ctx.get("ebitda_change", 0)
        da_chg = ctx.get("da_change", 0)
        finance_chg = ctx.get("finance_change", 0)
        tax_chg = ctx.get("tax_change", 0)

        for factor_name, chg, direction_logic, accs in [
            ("EBITDA change", ebitda_chg, "same", []),
            ("D&A change", da_chg, "inverse", ["8110", "8120"]),
            ("Finance cost change", finance_chg, "inverse", ["8410"]),
            ("Tax charge change", tax_chg, "inverse", ["9110"]),
        ]:
            if chg:
                direction = ("positive" if chg > 0 else "negative") if direction_logic == "same" else ("negative" if chg > 0 else "positive")
                factors.append(CausalFactor(
                    factor=factor_name,
                    impact_direction=direction,
                    magnitude="large" if abs(chg) > abs(change_abs) * 0.5 else "minor",
                    impact_pct=chg / abs(from_val) * 100 if from_val else None,
                    explanation=f"{factor_name} {'increased' if chg > 0 else 'decreased'} by {_fmt_gel(abs(chg))}.",
                    account_codes=accs,
                ))

        if not factors:
            factors.append(CausalFactor(
                factor="Net profit change",
                impact_direction="negative" if change_abs < 0 else "positive",
                magnitude="large",
                impact_pct=change_pct,
                explanation=(
                    f"Net profit {'fell' if change_abs < 0 else 'rose'} by {_fmt_gel(abs(change_abs))}. "
                    "Under Georgian Estonian model, CIT only applies to distributed profits."
                ),
                kg_context="Georgian CIT: 15% on distributed profits only",
            ))
            kg_ids.append("tax_tax_income_georgia")

        primary_cause = f"Net profit change of {_pct_str(change_pct)} driven by {factors[0].factor.lower()}"
        recommendations = []
        if change_abs < 0 and to_val < 0:
            recommendations.append("Net loss: review EBITDA drivers, then finance costs and D&A.")

        return factors, primary_cause, recommendations, kg_ids

    def _explain_cogs_change(self, metric, from_val, to_val, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="COGS movement",
            impact_direction="negative" if change_abs > 0 else "positive",
            magnitude="large" if abs(change_pct) > 15 else "moderate",
            impact_pct=change_pct,
            explanation=(
                f"COGS {'increased' if change_abs > 0 else 'decreased'} by {abs(change_pct):.1f}%. "
                "Key COGS drivers: (1) Brent crude price, (2) GEL/USD exchange rate, "
                "(3) Georgian fuel excise (GEL 0.40/liter petrol), (4) delivery volume."
            ),
            kg_context="COGS = fuel purchase + excise + freight (KG: formula_fml_cogs_fuel)",
            account_codes=["6110", "7310", "8230"],
        )]
        recommendations = [
            "Verify excise tax classification — GEL 0.40/liter should be in COGS.",
            "Compare unit cost to prior period and NYX Core Thinker benchmark prices.",
            "Check delivery volume — COGS should move proportionally with revenue.",
        ]
        return factors, f"COGS change of {_pct_str(change_pct)}", recommendations, ["formula_fml_cogs_fuel", "tax_tax_excise_fuel"]

    def _explain_ga_change(self, metric, from_val, to_val, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="G&A expense change",
            impact_direction="negative" if change_abs > 0 else "positive",
            magnitude="large" if abs(change_pct) > 20 else "moderate",
            impact_pct=change_pct,
            explanation=(
                f"G&A {'increased' if change_abs > 0 else 'decreased'} by {abs(change_pct):.1f}%. "
                "Major G&A components: staff costs (~50%), rent (~20%), IT/utilities (~30%). "
                "Industry benchmark: G&A should be 1.5–4% of revenue."
            ),
            account_codes=["7xxx"],
        )]
        recommendations = [
            "Review staff cost growth — headcount changes or salary increases.",
            "Audit rent/lease contracts for IAS 16 right-of-use asset impact.",
            f"Compare G&A/Revenue ratio to benchmark: 1.5–4%.",
        ]
        return factors, f"G&A change of {_pct_str(change_pct)}", recommendations, ["bench_bench_ga_staff_fuel"]

    def _explain_wholesale_margin(self, metric, from_val, to_val, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="Wholesale margin shift",
            impact_direction="negative" if change_abs < 0 else "positive",
            magnitude="large" if abs(change_abs) > 3 else "moderate",
            impact_pct=change_abs,
            explanation=(
                f"Wholesale margin moved from {from_val:.1f}% to {to_val:.1f}% ({change_abs:+.1f}pp). "
                "Industry benchmark: 1–4%. NEGATIVE wholesale margin is common and acceptable "
                "in loss-leader wholesale strategy where retail network compensates."
            ),
            kg_context="Wholesale benchmark 1-4%: KG ratio_ratio_wholesale_margin",
        )]
        recommendations = []
        if to_val < -5:
            recommendations.append(
                "Wholesale margin is very negative (< -5%). Verify if this is intentional loss-leader or a data mapping error."
            )
        recommendations.append("Compare blended margin (wholesale + retail) — retail should offset wholesale loss.")
        return factors, f"Wholesale margin {'compression' if change_abs < 0 else 'improvement'}", recommendations, ["ratio_ratio_wholesale_margin", "bench_bench_gross_margin_product_mix"]

    def _explain_retail_margin(self, metric, from_val, to_val, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="Retail margin shift",
            impact_direction="negative" if change_abs < 0 else "positive",
            magnitude="large" if abs(change_abs) > 4 else "moderate",
            impact_pct=change_abs,
            explanation=(
                f"Retail margin moved from {from_val:.1f}% to {to_val:.1f}% ({change_abs:+.1f}pp). "
                "Industry benchmark: 8–15%. Retail margins are the primary profit driver."
            ),
            kg_context="Retail benchmark 8-15%: KG ratio_ratio_retail_margin",
        )]
        recommendations = []
        if to_val < 8:
            recommendations.append("Retail margin below 8% benchmark. Review retail pricing strategy.")
        return factors, f"Retail margin {'compression' if change_abs < 0 else 'improvement'}", recommendations, ["ratio_ratio_retail_margin"]

    def _explain_generic(self, metric, from_val, to_val, change_abs, change_pct, ctx, meta):
        return (
            [CausalFactor(
                factor=f"{meta.get('label', metric)} change",
                impact_direction="negative" if change_abs < 0 else "positive",
                magnitude="large" if abs(change_pct) > 20 else "moderate",
                impact_pct=change_pct,
                explanation=f"{meta.get('label', metric)} changed from {from_val:.2f} to {to_val:.2f} ({_pct_str(change_pct)}).",
            )],
            f"{meta.get('label', metric)} change of {_pct_str(change_pct)}",
            [],
            [],
        )

    # ── Private: Severity + Narrative ─────────────────────────────────────────

    def _classify_severity(self, metric: str, change_pct: float, current_val: float, meta: dict) -> str:
        thresh = meta.get("thresholds", {})
        direction = meta.get("direction", "higher_better")

        if direction == "higher_better":
            if change_pct <= thresh.get("critical_drop", -999):
                return "critical"
            elif change_pct <= thresh.get("warning_drop", -999):
                return "high"
            elif change_pct >= thresh.get("notable_rise", 999):
                return "positive"
            else:
                return "medium" if change_pct < 0 else "normal"
        else:
            if change_pct >= thresh.get("critical_rise", 999):
                return "critical"
            elif change_pct >= thresh.get("warning_rise", 999):
                return "high"
            else:
                return "medium" if change_pct > 0 else "normal"

    def _build_narrative(self, metric, from_val, to_val, change_abs, change_pct,
                          period_from, period_to, severity, primary_cause, factors, meta) -> str:
        unit = meta.get("unit", "")
        label = meta.get("label", metric)
        val_fmt = f"{to_val:.1f}{unit}" if unit == "%" else _fmt_gel(to_val)
        from_fmt = f"{from_val:.1f}{unit}" if unit == "%" else _fmt_gel(from_val)

        severity_labels = {
            "critical": "CRITICAL ISSUE",
            "high": "WARNING",
            "medium": "NOTABLE CHANGE",
            "normal": "Change within expectations",
            "positive": "Positive development",
        }
        prefix = severity_labels.get(severity, "Change")

        lines = [
            f"[{prefix}] {label}: {from_fmt} → {val_fmt} ({_pct_str(change_pct)}) | {period_from} → {period_to}",
            "",
            f"Primary driver: {primary_cause}",
            "",
        ]

        if factors:
            lines.append("Contributing factors:")
            for i, f in enumerate(factors[:3], 1):
                direction_icon = "↓" if f.impact_direction == "negative" else "↑" if f.impact_direction == "positive" else "→"
                lines.append(f"  {i}. {direction_icon} {f.factor} [{f.magnitude}]: {f.explanation}")
            lines.append("")

        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_gel(value: float) -> str:
    """Format a GEL value with thousands separator."""
    try:
        if abs(value) >= 1_000_000:
            return f"₾{value/1_000_000:.2f}M"
        elif abs(value) >= 1_000:
            return f"₾{value:,.0f}"
        else:
            return f"₾{value:.2f}"
    except Exception:
        return f"₾{value}"


def _pct_str(pct: float) -> str:
    return f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"


# ── Module-level singleton ────────────────────────────────────────────────────
reasoning_engine = FinancialReasoningEngine()
