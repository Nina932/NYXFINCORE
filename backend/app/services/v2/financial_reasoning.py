"""
FinAI v2 Financial Reasoning Engine — Decimal-precise, edge-case-safe.
======================================================================
Rewrite of Phase E Financial Cognition with:
- All financial math using Decimal (ROUND_HALF_UP)
- Safe division (no ZeroDivisionError, no None->float comparison)
- pct_change returns None for zero denominators (not 0.0)
- Explicit error handling throughout

Public API (drop-in replacement for v1):
    from app.services.v2.financial_reasoning import reasoning_engine

    chain = reasoning_engine.explain_metric_change(...)
    result = reasoning_engine.simulate_scenario(...)
    liquidity = reasoning_engine.build_liquidity_analysis(...)
    issues = reasoning_engine.detect_accounting_issues(...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.services.v2.decimal_utils import (
    to_decimal, safe_divide, pct_change as _pct_change_util,
    round_fin, apply_pct, is_zero,
)

logger = logging.getLogger(__name__)


# ── Data Structures ────────────────────────────────────────────────────────

@dataclass
class CausalFactor:
    """One contributing factor in a causal chain."""
    factor: str
    impact_direction: str          # "negative" | "positive" | "neutral"
    magnitude: str                 # "large" | "moderate" | "minor"
    impact_pct: Optional[Decimal]  # Estimated % impact on the metric
    explanation: str
    kg_context: Optional[str] = None
    account_codes: List[str] = field(default_factory=list)


@dataclass
class CausalChain:
    """Complete causal analysis for a metric change."""
    metric: str
    from_value: Decimal
    to_value: Decimal
    period_from: str
    period_to: str
    change_absolute: Decimal
    change_pct: Optional[Decimal]  # None if from_value is zero
    severity: str
    primary_cause: str
    factors: List[CausalFactor]
    narrative: str
    recommendations: List[str]
    kg_entities_used: List[str]


@dataclass
class VarianceDecomposition:
    """Price-volume-mix breakdown."""
    metric: str
    total_variance: Decimal
    price_variance: Decimal
    volume_variance: Decimal
    mix_variance: Decimal
    other_variance: Decimal
    dominant_driver: str
    narrative: str


@dataclass
class ScenarioResult:
    """Result of a what-if scenario simulation — all Decimal."""
    scenario_name: str
    base_revenue: Decimal
    base_gross_profit: Decimal
    base_ebitda: Decimal
    base_net_profit: Decimal
    scenario_revenue: Decimal
    scenario_gross_profit: Decimal
    scenario_ebitda: Decimal
    scenario_net_profit: Decimal
    revenue_change_pct: Optional[Decimal]
    gross_profit_change_pct: Optional[Decimal]
    ebitda_change_pct: Optional[Decimal]
    net_profit_change_pct: Optional[Decimal]
    narrative: str
    risk_level: str


# ── Metric metadata ───────────────────────────────────────────────────────

_METRIC_META = {
    "revenue": {
        "label": "Net Revenue", "unit": "GEL", "direction": "higher_better",
        "thresholds": {"critical_drop": -20, "warning_drop": -10, "notable_rise": 20},
    },
    "gross_profit": {
        "label": "Gross Profit", "unit": "GEL", "direction": "higher_better",
        "thresholds": {"critical_drop": -30, "warning_drop": -15, "notable_rise": 30},
    },
    "gross_margin_pct": {
        "label": "Gross Margin %", "unit": "%", "direction": "higher_better",
        "thresholds": {"critical_drop": -5, "warning_drop": -2, "notable_rise": 5},
        "benchmark_low": 1.0, "benchmark_high": 15.0,
    },
    "ebitda": {
        "label": "EBITDA", "unit": "GEL", "direction": "higher_better",
        "thresholds": {"critical_drop": -30, "warning_drop": -15},
    },
    "ebitda_margin_pct": {
        "label": "EBITDA Margin %", "unit": "%", "direction": "higher_better",
        "thresholds": {"critical_drop": -3, "warning_drop": -1},
        "benchmark_low": 2.0, "benchmark_high": 6.0,
    },
    "net_profit": {
        "label": "Net Profit", "unit": "GEL", "direction": "higher_better",
        "thresholds": {"critical_drop": -50, "warning_drop": -20},
    },
    "net_margin_pct": {
        "label": "Net Profit Margin %", "unit": "%", "direction": "higher_better",
        "thresholds": {"critical_drop": -2, "warning_drop": -1},
    },
    "cogs": {
        "label": "Cost of Goods Sold", "unit": "GEL", "direction": "lower_better",
        "thresholds": {"critical_rise": 20, "warning_rise": 10},
    },
    "ga_expenses": {
        "label": "G&A Expenses", "unit": "GEL", "direction": "lower_better",
        "thresholds": {"critical_rise": 30, "warning_rise": 15},
    },
    "wholesale_margin_pct": {
        "label": "Wholesale Margin %", "unit": "%", "direction": "higher_better",
        "thresholds": {"critical_drop": -3, "warning_drop": -1},
        "benchmark_low": 1.0, "benchmark_high": 4.0, "negative_acceptable": True,
    },
    "retail_margin_pct": {
        "label": "Retail Margin %", "unit": "%", "direction": "higher_better",
        "thresholds": {"critical_drop": -5, "warning_drop": -2},
        "benchmark_low": 8.0, "benchmark_high": 15.0,
    },
}


# ── Formatting helpers (Decimal-aware) ─────────────────────────────────────

def _fmt_gel(value: Any) -> str:
    """Format a GEL value with thousands separator."""
    d = to_decimal(value)
    try:
        if abs(d) >= 1_000_000:
            return f"₾{safe_divide(d, Decimal('1000000'), precision=Decimal('0.01'))}M"
        elif abs(d) >= 1_000:
            return f"₾{round_fin(d)}"
        else:
            return f"₾{round_fin(d)}"
    except Exception as e:
        logger.debug("Currency formatting failed for %s: %s", d, e)
        return f"₾{d}"


def _pct_str(pct: Optional[Decimal]) -> str:
    if pct is None:
        return "N/A"
    return f"+{round_fin(pct)}%" if pct >= 0 else f"{round_fin(pct)}%"


class FinancialReasoningEngine:
    """
    Phase E Financial Cognition — v2 with Decimal precision.

    All calculations use Decimal. Division-by-zero returns None (not 0.0).
    """

    def explain_metric_change(
        self,
        metric: str,
        from_value: Any,
        to_value: Any,
        period_from: str = "Previous Period",
        period_to: str = "Current Period",
        context: Optional[Dict[str, Any]] = None,
    ) -> CausalChain:
        """Explain a change in a financial metric with causal analysis."""
        context = context or {}
        fv = to_decimal(from_value)
        tv = to_decimal(to_value)
        change_abs = tv - fv
        change_pct = _pct_change_util(fv, tv)

        meta = _METRIC_META.get(metric, {
            "label": metric, "unit": "", "direction": "higher_better", "thresholds": {}
        })
        severity = self._classify_severity(metric, change_pct, tv, meta)

        explainer = self._get_explainer(metric)
        factors, primary_cause, recommendations, kg_ids = explainer(
            metric, fv, tv, change_abs, change_pct, context, meta
        )

        narrative = self._build_narrative(
            metric, fv, tv, change_abs, change_pct,
            period_from, period_to, severity, primary_cause, factors, meta
        )

        return CausalChain(
            metric=metric, from_value=fv, to_value=tv,
            period_from=period_from, period_to=period_to,
            change_absolute=change_abs, change_pct=change_pct,
            severity=severity, primary_cause=primary_cause,
            factors=factors, narrative=narrative,
            recommendations=recommendations, kg_entities_used=kg_ids,
        )

    def decompose_revenue_variance(
        self,
        revenue_from: Any, revenue_to: Any,
        volume_from: Any, volume_to: Any,
        price_from: Any, price_to: Any,
    ) -> VarianceDecomposition:
        """Decompose revenue change into price, volume, and mix components."""
        rf = to_decimal(revenue_from)
        rt = to_decimal(revenue_to)
        vf = to_decimal(volume_from)
        vt = to_decimal(volume_to)
        pf = to_decimal(price_from)
        pt = to_decimal(price_to)

        total_var = rt - rf
        price_var = (pt - pf) * vt
        vol_var = (vt - vf) * pf
        mix_var = Decimal("0")
        other_var = total_var - price_var - vol_var - mix_var

        dominant = "price" if abs(price_var) >= abs(vol_var) else "volume"

        rev_chg = _pct_change_util(rf, rt)
        narrative = (
            f"Revenue changed by {_fmt_gel(total_var)} ({_pct_str(rev_chg)}).\n"
            f"Price effect: {_fmt_gel(price_var)}. Volume effect: {_fmt_gel(vol_var)}.\n"
            f"Dominant driver: {dominant.upper()} effect."
        )

        return VarianceDecomposition(
            metric="revenue", total_variance=total_var,
            price_variance=price_var, volume_variance=vol_var,
            mix_variance=mix_var, other_variance=other_var,
            dominant_driver=dominant, narrative=narrative,
        )

    def simulate_scenario(
        self,
        scenario_name: str,
        base: Dict[str, Any],
        changes: Dict[str, Any],
    ) -> ScenarioResult:
        """
        Simulate a financial scenario — ALL math in Decimal.

        Args:
            scenario_name: Descriptive name
            base: Base case financials (revenue, cogs, ga_expenses, etc.)
            changes: Parameter changes as percentages (e.g. {"cogs_pct": 5.0})
        """
        rev = to_decimal(base.get("revenue", 0))
        cogs = to_decimal(base.get("cogs", 0))
        ga = to_decimal(base.get("ga_expenses", 0))
        da = to_decimal(base.get("depreciation", 0))
        finance = to_decimal(base.get("finance_expense", 0))
        tax_rate = to_decimal(base.get("tax_rate", "0.15"))

        base_gp = rev - cogs
        base_ebitda = base_gp - ga
        base_ebit = base_ebitda - da
        base_ebt = base_ebit - finance
        base_np = base_ebt * (Decimal("1") - tax_rate)

        # Apply scenario changes (Decimal arithmetic)
        s_rev = apply_pct(rev, to_decimal(changes.get("revenue_pct", 0)))
        s_cogs = apply_pct(cogs, to_decimal(changes.get("cogs_pct", 0)))
        s_ga = apply_pct(ga, to_decimal(changes.get("ga_pct", 0)))
        s_da = apply_pct(da, to_decimal(changes.get("da_pct", 0)))
        s_finance = apply_pct(finance, to_decimal(changes.get("finance_pct", 0)))

        # Absolute changes
        s_rev += to_decimal(changes.get("revenue_abs", 0))
        s_cogs += to_decimal(changes.get("cogs_abs", 0))
        s_ga += to_decimal(changes.get("ga_abs", 0))

        s_gp = s_rev - s_cogs
        s_ebitda = s_gp - s_ga
        s_ebit = s_ebitda - s_da
        s_ebt = s_ebit - s_finance
        s_np = s_ebt * (Decimal("1") - tax_rate)

        gp_chg = _pct_change_util(base_gp, s_gp)
        ebitda_chg = _pct_change_util(base_ebitda, s_ebitda)
        np_chg = _pct_change_util(base_np, s_np)
        rev_chg = _pct_change_util(rev, s_rev)

        # Risk assessment
        risk = "low"
        if ebitda_chg is not None and ebitda_chg < Decimal("-30") or s_ebitda < 0:
            risk = "critical"
        elif ebitda_chg is not None and ebitda_chg < Decimal("-15"):
            risk = "high"
        elif ebitda_chg is not None and ebitda_chg < Decimal("-5"):
            risk = "medium"

        # Build narrative
        change_desc = []
        for k, v in changes.items():
            dv = to_decimal(v)
            if not is_zero(dv):
                label = k.replace("_pct", " (%)").replace("_abs", " (GEL abs)")
                change_desc.append(f"{label}: {_pct_str(dv)}")

        narrative = (
            f"Scenario: {scenario_name}\n"
            f"Changes applied: {', '.join(change_desc) if change_desc else 'none'}\n\n"
            f"Financial Impact:\n"
            f"  Gross Profit: {_fmt_gel(base_gp)} -> {_fmt_gel(s_gp)} ({_pct_str(gp_chg)})\n"
            f"  EBITDA: {_fmt_gel(base_ebitda)} -> {_fmt_gel(s_ebitda)} ({_pct_str(ebitda_chg)})\n"
            f"  Net Profit: {_fmt_gel(base_np)} -> {_fmt_gel(s_np)} ({_pct_str(np_chg)})\n\n"
        )

        if risk == "critical":
            narrative += "CRITICAL: This scenario makes the business EBITDA-negative or near-insolvent."
        elif risk == "high":
            narrative += "WARNING: Significant profitability deterioration. Management action required."
        elif risk == "medium":
            narrative += "CAUTION: Moderate profitability impact. Monitor closely."
        else:
            narrative += "LOW RISK: Business remains profitable with adequate margins."

        return ScenarioResult(
            scenario_name=scenario_name,
            base_revenue=round_fin(rev), base_gross_profit=round_fin(base_gp),
            base_ebitda=round_fin(base_ebitda), base_net_profit=round_fin(base_np),
            scenario_revenue=round_fin(s_rev), scenario_gross_profit=round_fin(s_gp),
            scenario_ebitda=round_fin(s_ebitda), scenario_net_profit=round_fin(s_np),
            revenue_change_pct=rev_chg, gross_profit_change_pct=gp_chg,
            ebitda_change_pct=ebitda_chg, net_profit_change_pct=np_chg,
            narrative=narrative, risk_level=risk,
        )

    def build_liquidity_analysis(self, balance_sheet: Dict[str, Any]) -> Dict[str, Any]:
        """Compute all liquidity ratios — Decimal, with safe division."""
        ca = to_decimal(balance_sheet.get("total_current_assets", 0))
        cl = to_decimal(balance_sheet.get("total_current_liabilities", 0))
        cash = to_decimal(balance_sheet.get("cash", 0))
        rec = to_decimal(balance_sheet.get("receivables", 0))
        total_assets = to_decimal(balance_sheet.get("total_assets", 0))
        total_debt = to_decimal(balance_sheet.get("total_debt", 0))
        equity = to_decimal(
            balance_sheet.get("total_equity", balance_sheet.get("equity", 0))
        )

        # Safe division — returns None if denominator is zero
        current_ratio = safe_divide(ca, cl) if cl != 0 else None
        quick_ratio = safe_divide(ca + rec, cl) if cl != 0 else None
        cash_ratio = safe_divide(cash, cl) if cl != 0 else None
        wc = ca - cl
        dte = safe_divide(total_debt, equity) if equity != 0 else None
        dta = safe_divide(total_debt, total_assets) if total_assets != 0 else None

        flags = []
        if current_ratio is not None and current_ratio < Decimal("1"):
            flags.append({
                "flag": "current_ratio_below_1", "severity": "critical",
                "message": f"Current ratio {current_ratio} < 1.0 — unable to cover short-term liabilities"
            })
        elif current_ratio is not None and current_ratio < Decimal("1.5"):
            flags.append({
                "flag": "current_ratio_low", "severity": "warning",
                "message": f"Current ratio {current_ratio} < 1.5 — limited liquidity buffer"
            })

        if dte is not None and dte > Decimal("3"):
            flags.append({
                "flag": "high_leverage", "severity": "high",
                "message": f"D/E ratio {dte} > 3.0 — excessive leverage"
            })

        if wc < 0:
            flags.append({
                "flag": "negative_working_capital", "severity": "critical",
                "message": f"Negative working capital: {_fmt_gel(wc)}"
            })

        return {
            "ratios": {
                "current_ratio": str(current_ratio) if current_ratio is not None else None,
                "quick_ratio": str(quick_ratio) if quick_ratio is not None else None,
                "cash_ratio": str(cash_ratio) if cash_ratio is not None else None,
                "working_capital": str(round_fin(wc)),
                "debt_to_equity": str(dte) if dte is not None else None,
                "debt_to_assets": str(dta) if dta is not None else None,
            },
            "flags": flags,
            "health": (
                "critical" if any(f["severity"] == "critical" for f in flags)
                else "warning" if flags else "healthy"
            ),
        }

    def detect_accounting_issues(
        self, pl_data: Dict[str, Any], bs_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Run rule-based accounting consistency checks — Decimal-safe."""
        issues = []

        assets = to_decimal(bs_data.get("total_assets", 0))
        liabilities = to_decimal(bs_data.get("total_liabilities", 0))
        equity = to_decimal(bs_data.get("total_equity", bs_data.get("equity", 0)))

        # 1. Balance sheet equation
        if not is_zero(assets):
            imbalance = abs(assets - (liabilities + equity))
            imbalance_pct = safe_divide(imbalance * Decimal("100"), assets)
            if imbalance_pct > Decimal("0.01"):
                issues.append({
                    "type": "balance_sheet_imbalance", "severity": "critical",
                    "message": f"Assets ({_fmt_gel(assets)}) != L+E ({_fmt_gel(liabilities + equity)}). Imbalance: {_fmt_gel(imbalance)}",
                    "impact": "Financial statements cannot be trusted"
                })

        # 2. Revenue negativity
        rev = to_decimal(pl_data.get("revenue", 0))
        if rev < 0:
            issues.append({
                "type": "negative_revenue", "severity": "critical",
                "message": f"Revenue is negative: {_fmt_gel(rev)}. Likely data mapping error.",
                "impact": "All P&L ratios will be inverted"
            })

        # 3. COGS > Revenue (>110%)
        cogs = to_decimal(pl_data.get("cogs", 0))
        if rev > 0:
            cogs_ratio = safe_divide(cogs, rev)
            if cogs_ratio > Decimal("1.10"):
                issues.append({
                    "type": "extreme_cogs_ratio", "severity": "warning",
                    "message": f"COGS/Revenue = {round_fin(cogs_ratio * 100)}% (>110%). Check data mapping.",
                    "impact": "Verify account classification"
                })

        # 4. Negative equity
        if equity < 0:
            issues.append({
                "type": "negative_equity", "severity": "critical",
                "message": f"Shareholders equity is negative: {_fmt_gel(equity)}",
                "impact": "Technical insolvency — liabilities exceed assets"
            })

        # 5. Gross profit > Revenue (impossible)
        gp = to_decimal(pl_data.get("gross_profit", 0))
        if rev > 0 and gp > rev:
            issues.append({
                "type": "gross_profit_exceeds_revenue", "severity": "critical",
                "message": f"Gross profit ({_fmt_gel(gp)}) > Revenue ({_fmt_gel(rev)}). Impossible.",
                "impact": "COGS mapping error"
            })

        # 6. EBITDA > Gross profit
        ebitda = to_decimal(pl_data.get("ebitda", 0))
        if gp > 0 and ebitda > gp:
            issues.append({
                "type": "ebitda_exceeds_gross_profit", "severity": "warning",
                "message": f"EBITDA ({_fmt_gel(ebitda)}) > Gross Profit ({_fmt_gel(gp)}). Implies negative G&A.",
                "impact": "Check G&A classification"
            })

        return issues

    # ── Private: Explainer Dispatch ──────────────────────────────────────

    def _get_explainer(self, metric: str):
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

    def _explain_gross_margin_change(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = []
        kg_ids = ["ratio_gross_margin", "bench_gross_margin_product_mix"]
        declining = change_abs < 0

        rev_from = to_decimal(ctx.get("revenue_from", ctx.get("revenue", 0)))
        rev_to = to_decimal(ctx.get("revenue_to", ctx.get("revenue", 0)))
        cogs_from = to_decimal(ctx.get("cogs_from", ctx.get("cogs", 0)))
        cogs_to = to_decimal(ctx.get("cogs_to", ctx.get("cogs", 0)))

        if not is_zero(cogs_from) and not is_zero(rev_from):
            cogs_ratio_from = safe_divide(cogs_from * 100, rev_from)
            cogs_ratio_to = safe_divide(cogs_to * 100, rev_to) if not is_zero(rev_to) else cogs_ratio_from
            cogs_ratio_change = cogs_ratio_to - cogs_ratio_from
            if abs(cogs_ratio_change) > Decimal("0.5"):
                factors.append(CausalFactor(
                    factor="COGS ratio change",
                    impact_direction="negative" if cogs_ratio_change > 0 else "positive",
                    magnitude="large" if abs(cogs_ratio_change) > 5 else "moderate",
                    impact_pct=-cogs_ratio_change,
                    explanation=(
                        f"COGS as % of revenue moved from {cogs_ratio_from}% to {cogs_ratio_to}% "
                        f"({'higher costs compress margin' if cogs_ratio_change > 0 else 'lower costs improve margin'}). "
                        "Key COGS drivers: fuel purchase price, excise tax, freight."
                    ),
                    kg_context="COGS = Account 6110 + Account 7310 + Account 8230",
                    account_codes=["6110", "7310", "8230"],
                ))
                kg_ids.append("formula_fml_cogs_fuel")

        if not factors:
            factors.append(CausalFactor(
                factor="Margin compression" if declining else "Margin improvement",
                impact_direction="negative" if declining else "positive",
                magnitude="large" if abs(change_abs) > 5 else "moderate",
                impact_pct=change_abs,
                explanation=(
                    f"Gross margin {'fell' if declining else 'rose'} {abs(change_abs)}pp from "
                    f"{fv}% to {tv}%. "
                    "Possible causes: fuel purchase price, excise tax, product mix shift."
                ),
            ))

        primary = max(factors, key=lambda f: abs(f.impact_pct or Decimal("0")))
        primary_cause = f"{primary.factor}: {primary.explanation[:120]}..."

        recommendations = []
        if declining:
            recommendations.extend([
                "Review fuel procurement contracts.",
                "Analyze product mix — shift toward higher-margin retail.",
                "Conduct excise tax reconciliation.",
                "Compare margins to benchmarks (wholesale 1-4%, retail 8-15%).",
            ])
            if tv < 0:
                recommendations.insert(0, "URGENT: Gross margin NEGATIVE. Immediate review required.")

        return factors, primary_cause, recommendations, kg_ids

    def _explain_revenue_change(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = []
        kg_ids = ["bench_bench_fuel_volume_ws", "bench_bench_fuel_price_georgia"]
        declining = change_abs < 0

        if not factors:
            factors.append(CausalFactor(
                factor="Revenue change",
                impact_direction="negative" if declining else "positive",
                magnitude="large" if change_pct is not None and abs(change_pct) > 15 else "moderate",
                impact_pct=change_pct,
                explanation=f"Revenue {'fell' if declining else 'grew'} by {_pct_str(change_pct)}.",
                kg_context="Revenue drivers: commodity price + volume + mix",
            ))

        primary_cause = f"Revenue {'decline' if declining else 'growth'} of {_pct_str(change_pct)}"
        recommendations = []
        if declining:
            recommendations.extend([
                "Decompose change: price vs volume (price-volume-mix analysis).",
                "Check customer concentration.",
                "Seasonal analysis: compare to same period prior year.",
            ])

        return factors, primary_cause, recommendations, kg_ids

    def _explain_ebitda_change(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = []
        kg_ids = ["ratio_ratio_ebitda_margin"]

        gp_change = to_decimal(ctx.get("gross_profit_change", 0))
        ga_change = to_decimal(ctx.get("ga_change", 0))

        if not is_zero(gp_change):
            factors.append(CausalFactor(
                factor="Gross profit change",
                impact_direction="positive" if gp_change > 0 else "negative",
                magnitude="large" if abs(gp_change) > abs(change_abs) * Decimal("0.7") else "moderate",
                impact_pct=safe_divide(gp_change * 100, abs(fv)) if not is_zero(fv) else None,
                explanation=f"Gross profit {'increased' if gp_change > 0 else 'decreased'} by {_fmt_gel(gp_change)}.",
            ))

        if not is_zero(ga_change):
            factors.append(CausalFactor(
                factor="G&A expense change",
                impact_direction="negative" if ga_change > 0 else "positive",
                magnitude="moderate",
                impact_pct=safe_divide(-ga_change * 100, abs(fv)) if not is_zero(fv) else None,
                explanation=f"G&A {'increased' if ga_change > 0 else 'decreased'} by {_fmt_gel(abs(ga_change))}.",
            ))

        if not factors:
            factors.append(CausalFactor(
                factor="Combined operational change",
                impact_direction="negative" if change_abs < 0 else "positive",
                magnitude="large" if change_pct is not None and abs(change_pct) > 20 else "moderate",
                impact_pct=change_pct,
                explanation=f"EBITDA {'fell' if change_abs < 0 else 'rose'} by {_fmt_gel(abs(change_abs))}.",
            ))

        primary_cause = f"EBITDA {'declined' if change_abs < 0 else 'improved'} {_pct_str(change_pct)}"
        if tv < 0:
            primary_cause = "EBITDA turned NEGATIVE"

        recommendations = []
        if change_abs < 0:
            recommendations.extend([
                "Analyze gross margin deterioration.",
                "Review G&A cost structure.",
                "Compare EBITDA margin to benchmark: 2-6%.",
            ])

        return factors, primary_cause, recommendations, kg_ids

    def _explain_net_profit_change(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = []
        kg_ids = ["ratio_ratio_net_margin"]

        for factor_name, key, direction_logic in [
            ("EBITDA change", "ebitda_change", "same"),
            ("D&A change", "da_change", "inverse"),
            ("Finance cost change", "finance_change", "inverse"),
            ("Tax charge change", "tax_change", "inverse"),
        ]:
            chg = to_decimal(ctx.get(key, 0))
            if not is_zero(chg):
                direction = ("positive" if chg > 0 else "negative") if direction_logic == "same" else ("negative" if chg > 0 else "positive")
                factors.append(CausalFactor(
                    factor=factor_name, impact_direction=direction,
                    magnitude="large" if abs(chg) > abs(change_abs) * Decimal("0.5") else "minor",
                    impact_pct=safe_divide(chg * 100, abs(fv)) if not is_zero(fv) else None,
                    explanation=f"{factor_name} by {_fmt_gel(abs(chg))}.",
                ))

        if not factors:
            factors.append(CausalFactor(
                factor="Net profit change",
                impact_direction="negative" if change_abs < 0 else "positive",
                magnitude="large", impact_pct=change_pct,
                explanation=f"Net profit {'fell' if change_abs < 0 else 'rose'} by {_fmt_gel(abs(change_abs))}.",
                kg_context="Georgian CIT: 15% on distributed profits only",
            ))

        primary_cause = f"Net profit change of {_pct_str(change_pct)}"
        recommendations = []
        if change_abs < 0 and tv < 0:
            recommendations.append("Net loss: review EBITDA drivers, then finance costs and D&A.")

        return factors, primary_cause, recommendations, kg_ids

    def _explain_cogs_change(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="COGS movement",
            impact_direction="negative" if change_abs > 0 else "positive",
            magnitude="large" if change_pct is not None and abs(change_pct) > 15 else "moderate",
            impact_pct=change_pct,
            explanation=f"COGS {'increased' if change_abs > 0 else 'decreased'} by {_pct_str(change_pct)}.",
            kg_context="COGS = fuel purchase + excise + freight",
            account_codes=["6110", "7310", "8230"],
        )]
        recommendations = [
            "Verify excise tax classification.",
            "Compare unit cost to prior period.",
            "Check delivery volume proportionality.",
        ]
        return factors, f"COGS change of {_pct_str(change_pct)}", recommendations, ["formula_fml_cogs_fuel"]

    def _explain_ga_change(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="G&A expense change",
            impact_direction="negative" if change_abs > 0 else "positive",
            magnitude="large" if change_pct is not None and abs(change_pct) > 20 else "moderate",
            impact_pct=change_pct,
            explanation=f"G&A {'increased' if change_abs > 0 else 'decreased'} by {_pct_str(change_pct)}.",
            account_codes=["7xxx"],
        )]
        return factors, f"G&A change of {_pct_str(change_pct)}", ["Review staff costs.", "Audit rent/lease contracts."], ["bench_bench_ga_staff_fuel"]

    def _explain_wholesale_margin(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="Wholesale margin shift",
            impact_direction="negative" if change_abs < 0 else "positive",
            magnitude="large" if abs(change_abs) > 3 else "moderate",
            impact_pct=change_abs,
            explanation=f"Wholesale margin moved from {fv}% to {tv}% ({change_abs:+}pp). Benchmark: 1-4%.",
        )]
        recommendations = ["Compare blended margin (wholesale + retail)."]
        if tv < -5:
            recommendations.insert(0, "Wholesale margin very negative (< -5%). Verify if intentional.")
        return factors, f"Wholesale margin {'compression' if change_abs < 0 else 'improvement'}", recommendations, ["ratio_ratio_wholesale_margin"]

    def _explain_retail_margin(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        factors = [CausalFactor(
            factor="Retail margin shift",
            impact_direction="negative" if change_abs < 0 else "positive",
            magnitude="large" if abs(change_abs) > 4 else "moderate",
            impact_pct=change_abs,
            explanation=f"Retail margin moved from {fv}% to {tv}% ({change_abs:+}pp). Benchmark: 8-15%.",
        )]
        recommendations = []
        if tv < 8:
            recommendations.append("Retail margin below 8% benchmark.")
        return factors, f"Retail margin {'compression' if change_abs < 0 else 'improvement'}", recommendations, ["ratio_ratio_retail_margin"]

    def _explain_generic(self, metric, fv, tv, change_abs, change_pct, ctx, meta):
        label = meta.get("label", metric)
        return (
            [CausalFactor(
                factor=f"{label} change",
                impact_direction="negative" if change_abs < 0 else "positive",
                magnitude="large" if change_pct is not None and abs(change_pct) > 20 else "moderate",
                impact_pct=change_pct,
                explanation=f"{label} changed from {fv} to {tv} ({_pct_str(change_pct)}).",
            )],
            f"{label} change of {_pct_str(change_pct)}", [], [],
        )

    def _classify_severity(self, metric: str, change_pct: Optional[Decimal], current_val: Decimal, meta: dict) -> str:
        if change_pct is None:
            return "normal"
        thresh = meta.get("thresholds", {})
        direction = meta.get("direction", "higher_better")

        if direction == "higher_better":
            if change_pct <= Decimal(str(thresh.get("critical_drop", -999))):
                return "critical"
            elif change_pct <= Decimal(str(thresh.get("warning_drop", -999))):
                return "high"
            elif change_pct >= Decimal(str(thresh.get("notable_rise", 999))):
                return "positive"
            return "medium" if change_pct < 0 else "normal"
        else:
            if change_pct >= Decimal(str(thresh.get("critical_rise", 999))):
                return "critical"
            elif change_pct >= Decimal(str(thresh.get("warning_rise", 999))):
                return "high"
            return "medium" if change_pct > 0 else "normal"

    def _build_narrative(self, metric, fv, tv, change_abs, change_pct,
                          period_from, period_to, severity, primary_cause, factors, meta) -> str:
        unit = meta.get("unit", "")
        label = meta.get("label", metric)
        val_fmt = f"{tv}{unit}" if unit == "%" else _fmt_gel(tv)
        from_fmt = f"{fv}{unit}" if unit == "%" else _fmt_gel(fv)

        severity_labels = {
            "critical": "CRITICAL ISSUE", "high": "WARNING",
            "medium": "NOTABLE CHANGE", "normal": "Change within expectations",
            "positive": "Positive development",
        }
        prefix = severity_labels.get(severity, "Change")

        lines = [
            f"[{prefix}] {label}: {from_fmt} -> {val_fmt} ({_pct_str(change_pct)}) | {period_from} -> {period_to}",
            "", f"Primary driver: {primary_cause}", "",
        ]

        if factors:
            lines.append("Contributing factors:")
            for i, f in enumerate(factors[:3], 1):
                icon = {"negative": "v", "positive": "^", "neutral": "-"}.get(f.impact_direction, "-")
                lines.append(f"  {i}. {icon} {f.factor} [{f.magnitude}]: {f.explanation}")
            lines.append("")

        return "\n".join(lines)


# Module-level singleton
reasoning_engine = FinancialReasoningEngine()
