"""
Proactive Intelligence Service
================================
Generates AUTOMATIC insights from financial data — deterministic, no LLM.

Called after dashboard load; every page gets pre-computed intelligence:
  health_summary, key_risks, opportunities, anomalies, recommendations,
  kpi_alerts, trend_signals, narrative.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Industry-specific health configuration ───────────────────────────────────
# Fuel distribution (thin margins) gets more forgiving margin thresholds
# but stricter liquidity checks. Default is for generic companies.

INDUSTRY_HEALTH_CONFIG = {
    "fuel_distribution": {
        "gross_margin_benchmark": 12.0,     # fuel distribution has thin margins
        "net_margin_benchmark": 3.0,
        "ebitda_margin_benchmark": 5.0,
        "cogs_warning": 90.0,               # higher threshold for fuel (normally 85-92%)
        "current_ratio_min": 0.8,            # fuel companies often operate with lower current ratio
        "de_max": 4.0,                       # higher leverage acceptable
        "scoring_weights": {
            "profitability": 0.35,
            "liquidity": 0.25,
            "leverage": 0.20,
            "efficiency": 0.20,
        },
        "benchmarks": {
            "gross_margin_pct": {"healthy": 12.0, "warning": 8.0, "critical": 3.0, "label": "Gross Margin"},
            "net_margin_pct": {"healthy": 3.0, "warning": 1.0, "critical": 0.0, "label": "Net Margin"},
            "ebitda_margin_pct": {"healthy": 5.0, "warning": 2.0, "critical": 0.0, "label": "EBITDA Margin"},
            "current_ratio": {"healthy": 0.8, "warning": 0.6, "critical": 0.4, "label": "Current Ratio"},
            "debt_to_equity": {"healthy_max": 4.0, "warning_max": 5.0, "critical_max": 6.0, "label": "Debt/Equity"},
            "cogs_to_revenue_pct": {"healthy_max": 90.0, "warning_max": 93.0, "critical_max": 96.0, "label": "COGS/Revenue"},
        },
    },
    "default": {
        "gross_margin_benchmark": 25.0,
        "net_margin_benchmark": 8.0,
        "ebitda_margin_benchmark": 10.0,
        "cogs_warning": 75.0,
        "current_ratio_min": 1.5,
        "de_max": 2.0,
        "scoring_weights": {
            "profitability": 0.30,
            "liquidity": 0.25,
            "leverage": 0.25,
            "efficiency": 0.20,
        },
        "benchmarks": {
            "gross_margin_pct": {"healthy": 25.0, "warning": 15.0, "critical": 5.0, "label": "Gross Margin"},
            "net_margin_pct": {"healthy": 8.0, "warning": 3.0, "critical": 0.0, "label": "Net Margin"},
            "ebitda_margin_pct": {"healthy": 10.0, "warning": 5.0, "critical": 0.0, "label": "EBITDA Margin"},
            "current_ratio": {"healthy": 1.5, "warning": 1.2, "critical": 1.0, "label": "Current Ratio"},
            "debt_to_equity": {"healthy_max": 2.0, "warning_max": 3.0, "critical_max": 4.0, "label": "Debt/Equity"},
            "cogs_to_revenue_pct": {"healthy_max": 75.0, "warning_max": 85.0, "critical_max": 95.0, "label": "COGS/Revenue"},
        },
    },
}


def _get_industry_config(industry: str = None) -> Dict[str, Any]:
    """Get the health configuration for the given industry."""
    if not industry:
        # Try to detect industry from data_store
        try:
            from app.services.data_store import data_store
            companies = data_store.list_companies()
            if companies:
                industry = companies[0].get("industry", "default")
        except Exception:
            industry = "default"
    return INDUSTRY_HEALTH_CONFIG.get(industry or "default", INDUSTRY_HEALTH_CONFIG["default"])


# Backward-compatible alias (used by existing code)
_FUEL_BENCHMARKS = INDUSTRY_HEALTH_CONFIG["fuel_distribution"]["benchmarks"]


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0 or b is None:
        return default
    return a / b


def _safe_pct(a: float, b: float) -> float:
    return round(_safe_div(a, b) * 100, 2)


def _fmt_gel(v: float) -> str:
    """Format a number as GEL currency string."""
    if abs(v) >= 1_000_000:
        return f"₾{v / 1_000_000:,.1f}M"
    if abs(v) >= 1_000:
        return f"₾{v / 1_000:,.0f}K"
    return f"₾{v:,.0f}"


def _compute_ratios(fin: Dict[str, Any]) -> Dict[str, float]:
    """Compute standard ratios from financial dict."""
    rev = fin.get("revenue", 0) or 0
    gp = fin.get("gross_profit", 0) or 0
    np_ = fin.get("net_profit", 0) or 0
    ebitda = fin.get("ebitda", 0) or 0
    cogs = fin.get("cogs", 0) or 0

    # Balance sheet fields (may be prefixed with bs_)
    ta = fin.get("total_assets") or fin.get("bs_total_assets", 0) or 0
    tl = fin.get("total_liabilities") or fin.get("bs_total_liabilities", 0) or 0
    te = fin.get("total_equity") or fin.get("bs_total_equity", 0) or 0
    ca = fin.get("total_current_assets") or fin.get("bs_current_assets", 0) or 0
    cl = fin.get("current_liabilities") or fin.get("bs_current_liabilities", 0) or 0
    cash = fin.get("cash") or fin.get("bs_cash", 0) or 0
    ltd = fin.get("long_term_debt") or fin.get("bs_long_term_debt", 0) or 0

    return {
        "gross_margin_pct": _safe_pct(gp, rev),
        "net_margin_pct": _safe_pct(np_, rev),
        "ebitda_margin_pct": _safe_pct(ebitda, rev),
        "cogs_to_revenue_pct": _safe_pct(cogs, rev),
        "current_ratio": round(_safe_div(ca, cl, 0), 2) if cl else 0,
        "debt_to_equity": round(_safe_div(tl, te, 0), 2) if te else 0,
        "revenue": rev,
        "gross_profit": gp,
        "net_profit": np_,
        "ebitda": ebitda,
        "cogs": cogs,
        "total_assets": ta,
        "total_liabilities": tl,
        "total_equity": te,
        "current_assets": ca,
        "current_liabilities": cl,
        "cash": cash,
        "long_term_debt": ltd,
        "admin_expenses": fin.get("admin_expenses", 0) or fin.get("ga_expenses", 0) or 0,
        "selling_expenses": fin.get("selling_expenses", 0) or 0,
        "depreciation": fin.get("depreciation", 0) or 0,
    }


class ProactiveIntelligence:
    """Generate comprehensive proactive insights from financial data — deterministic, no LLM."""

    def analyze(
        self,
        financials: Dict[str, Any],
        balance_sheet: Dict[str, Any] = None,
        previous: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive proactive insights from financial data."""
        # Merge balance_sheet into financials copy so ratio computation has everything
        merged = dict(financials or {})
        if balance_sheet:
            merged.update(balance_sheet)

        try:
            ratios = _compute_ratios(merged)
        except Exception:
            ratios = {}

        prev_ratios = None
        if previous:
            try:
                prev_ratios = _compute_ratios(previous)
            except Exception:
                pass

        result: Dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat()}

        # Each sub-analysis is wrapped so partial failure returns partial results
        for key, fn in [
            ("health_summary", lambda: self._assess_health(ratios)),
            ("key_risks", lambda: self._detect_risks(ratios, balance_sheet)),
            ("opportunities", lambda: self._find_opportunities(ratios)),
            ("anomalies", lambda: self._detect_anomalies(ratios, prev_ratios)),
            ("recommendations", lambda: self._generate_recommendations(ratios, balance_sheet)),
            ("kpi_alerts", lambda: self._check_kpi_thresholds(ratios)),
            ("trend_signals", lambda: self._analyze_trends(ratios, prev_ratios)),
            ("narrative", lambda: self._generate_narrative(ratios)),
            ("strategic_exposure", lambda: self._assess_strategic_exposure()),
        ]:
            try:
                result[key] = fn()
            except Exception as exc:
                logger.warning("ProactiveIntelligence.%s failed: %s", key, exc)
                result[key] = None

        return result

    # ─── 1. Health Assessment ───────────────────────────────────────

    def _assess_health(self, ratios: Dict[str, float], industry: str = None) -> Dict[str, Any]:
        cfg = _get_industry_config(industry)
        gm_bench = cfg["gross_margin_benchmark"]
        nm_bench = cfg["net_margin_benchmark"]
        cr_min = cfg["current_ratio_min"]
        de_max = cfg["de_max"]
        cogs_warn = cfg["cogs_warning"]

        score = 100
        bullets: List[str] = []

        gm = ratios.get("gross_margin_pct", 0)
        nm = ratios.get("net_margin_pct", 0)
        em = ratios.get("ebitda_margin_pct", 0)
        cr = ratios.get("current_ratio", 0)
        de = ratios.get("debt_to_equity", 0)
        cogs_r = ratios.get("cogs_to_revenue_pct", 0)

        industry_label = industry or "industry"

        # Gross margin — thresholds calibrated to industry
        if gm >= gm_bench:
            bullets.append(f"Healthy gross margin at {gm:.1f}% (benchmark: {gm_bench:.0f}%)")
        elif gm >= gm_bench * 0.65:
            score -= 10
            bullets.append(f"Gross margin ({gm:.1f}%) is below {industry_label} benchmark of {gm_bench:.0f}%")
        elif gm > 0:
            score -= 20
            bullets.append(f"Weak gross margin at {gm:.1f}% — cost pressure vs {gm_bench:.0f}% benchmark")
        else:
            score -= 30
            bullets.append("Negative gross margin — revenue does not cover direct costs")

        # Net margin — calibrated to industry
        if nm >= nm_bench:
            bullets.append(f"Solid net margin at {nm:.1f}% (benchmark: {nm_bench:.0f}%)")
        elif nm >= 0:
            score -= 15
            bullets.append(f"Thin net margin ({nm:.1f}%) vs {nm_bench:.0f}% benchmark — limited room for error")
        else:
            score -= 25
            bullets.append(f"Net loss — net margin is {nm:.1f}%")

        # Current ratio — industry-aware threshold
        if cr >= cr_min * 1.5:
            bullets.append(f"Good liquidity position (current ratio {cr:.2f}, min: {cr_min:.1f})")
        elif cr >= cr_min:
            score -= 10
            bullets.append(f"Adequate liquidity (current ratio {cr:.2f}) but near {industry_label} minimum of {cr_min:.1f}")
        elif cr > 0:
            score -= 20
            bullets.append(f"Liquidity risk — current ratio {cr:.2f} is below {industry_label} minimum of {cr_min:.1f}")

        # Debt/Equity — industry-aware
        if de > 0:
            if de <= de_max:
                bullets.append(f"Acceptable leverage (D/E {de:.2f}, max: {de_max:.1f})")
            elif de <= de_max * 1.5:
                score -= 10
                bullets.append(f"Elevated leverage (D/E {de:.2f}) — above {industry_label} prudent limit of {de_max:.1f}")
            else:
                score -= 20
                bullets.append(f"High leverage risk (D/E {de:.2f}) — far exceeds {industry_label} limit of {de_max:.1f}")

        # COGS efficiency — industry-aware
        if cogs_r > cogs_warn:
            score -= 10
            bullets.append(f"COGS consumes {cogs_r:.1f}% of revenue (warning: >{cogs_warn:.0f}%)")

        score = max(0, min(100, score))

        if score >= 80:
            grade = "A"
        elif score >= 65:
            grade = "B"
        elif score >= 50:
            grade = "C"
        elif score >= 35:
            grade = "D"
        else:
            grade = "F"

        return {
            "health_score": score,
            "grade": grade,
            "bullets": bullets[:5],
            "industry_config": industry_label,
            "data_source": "industry_calibrated_thresholds",
        }

    # ─── 2. Risk Detection ──────────────────────────────────────────

    def _detect_risks(
        self, ratios: Dict[str, float], balance_sheet: Dict[str, Any] = None,
        industry: str = None,
    ) -> List[Dict[str, Any]]:
        cfg = _get_industry_config(industry)
        cogs_warn = cfg["cogs_warning"]
        de_max = cfg["de_max"]

        risks: List[Dict[str, Any]] = []
        np_ = ratios.get("net_profit", 0)
        cogs_r = ratios.get("cogs_to_revenue_pct", 0)
        cash = ratios.get("cash", 0)
        rev = ratios.get("revenue", 0)
        de = ratios.get("debt_to_equity", 0)
        cr = ratios.get("current_ratio", 0)

        if np_ < 0:
            risks.append({
                "signal": "Negative net profit",
                "severity": "critical",
                "detail": f"Net loss of {_fmt_gel(abs(np_))}. The company is unprofitable.",
            })

        if cogs_r > cogs_warn:
            sev = "critical" if cogs_r > cogs_warn + 5 else "warning"
            risks.append({
                "signal": f"COGS exceeds {cogs_warn:.0f}% of revenue",
                "severity": sev,
                "detail": f"COGS at {cogs_r:.1f}% of revenue (industry warning: {cogs_warn:.0f}%).",
            })

        # Cash < 1 month of expenses
        monthly_expenses = rev / 12 if rev > 0 else 0
        if cash > 0 and monthly_expenses > 0 and cash < monthly_expenses:
            risks.append({
                "signal": "Cash below 1 month of expenses",
                "severity": "critical",
                "detail": f"Cash ({_fmt_gel(cash)}) covers less than 1 month of operating expenses ({_fmt_gel(monthly_expenses)}/month).",
            })

        if de > de_max:
            risks.append({
                "signal": "High debt-to-equity ratio",
                "severity": "warning" if de <= de_max * 1.3 else "critical",
                "detail": f"D/E ratio of {de:.2f} exceeds industry threshold of {de_max:.1f}.",
            })

        if cr > 0 and cr < 1.0:
            risks.append({
                "signal": "Current ratio below 1.0",
                "severity": "critical",
                "detail": f"Current ratio of {cr:.2f} — current liabilities exceed current assets.",
            })

        gm = ratios.get("gross_margin_pct", 0)
        if 0 < gm < 5:
            risks.append({
                "signal": "Near-zero gross margin",
                "severity": "warning",
                "detail": f"Gross margin of {gm:.1f}% is dangerously thin.",
            })

        if not risks:
            risks.append({
                "signal": "No critical risks detected",
                "severity": "info",
                "detail": "Financial position is within acceptable parameters.",
            })

        return risks

    # ─── 3. Opportunities ──────────────────────────────────────────

    def _find_opportunities(self, ratios: Dict[str, float]) -> List[Dict[str, Any]]:
        opps: List[Dict[str, Any]] = []
        rev = ratios.get("revenue", 0)
        admin = ratios.get("admin_expenses", 0)
        gm = ratios.get("gross_margin_pct", 0)
        cash = ratios.get("cash", 0)
        selling = ratios.get("selling_expenses", 0)

        # Admin cost reduction
        if rev > 0 and admin > 0:
            admin_pct = admin / rev * 100
            if admin_pct > 8:
                target_pct = 7
                savings = admin - (rev * target_pct / 100)
                opps.append({
                    "opportunity": "Reduce G&A expenses",
                    "detail": f"Admin costs are {admin_pct:.1f}% of revenue (above 8% threshold). Reducing to {target_pct}% saves {_fmt_gel(savings)}.",
                    "estimated_impact_gel": round(savings, 0),
                    "priority": "high",
                })

        # Margin improvement
        if gm >= 12:
            opps.append({
                "opportunity": "Negotiate better supplier terms",
                "detail": f"With gross margin at {gm:.1f}%, there is room to negotiate volume discounts or better payment terms.",
                "estimated_impact_gel": round(rev * 0.005, 0) if rev > 0 else 0,
                "priority": "medium",
            })

        # Cash deployment
        monthly_expenses = rev / 12 if rev > 0 else 0
        if cash > 0 and monthly_expenses > 0 and cash > monthly_expenses * 6:
            excess = cash - (monthly_expenses * 3)
            opps.append({
                "opportunity": "Deploy excess cash",
                "detail": f"Cash position ({_fmt_gel(cash)}) covers {cash / monthly_expenses:.0f} months of expenses. Consider strategic investment of {_fmt_gel(excess)}.",
                "estimated_impact_gel": round(excess * 0.05, 0),
                "priority": "medium",
            })

        # Selling efficiency
        if rev > 0 and selling > 0:
            sell_pct = selling / rev * 100
            if sell_pct > 5:
                savings = selling * 0.15
                opps.append({
                    "opportunity": "Optimize selling expenses",
                    "detail": f"Selling costs at {sell_pct:.1f}% of revenue. A 15% efficiency gain saves {_fmt_gel(savings)}.",
                    "estimated_impact_gel": round(savings, 0),
                    "priority": "medium",
                })

        if not opps:
            opps.append({
                "opportunity": "Maintain current trajectory",
                "detail": "No immediate optimization opportunities identified — focus on execution.",
                "estimated_impact_gel": 0,
                "priority": "low",
            })

        return opps

    # ─── 4. Anomaly Detection ──────────────────────────────────────

    def _detect_anomalies(
        self, ratios: Dict[str, float], prev_ratios: Optional[Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        if not prev_ratios:
            return []

        anomalies: List[Dict[str, Any]] = []
        metrics_to_check = [
            ("revenue", "Revenue"),
            ("gross_profit", "Gross Profit"),
            ("net_profit", "Net Profit"),
            ("ebitda", "EBITDA"),
            ("cogs", "COGS"),
            ("admin_expenses", "Admin Expenses"),
            ("selling_expenses", "Selling Expenses"),
            ("cash", "Cash"),
            ("current_assets", "Current Assets"),
            ("total_liabilities", "Total Liabilities"),
        ]

        for key, label in metrics_to_check:
            curr = ratios.get(key, 0) or 0
            prev = prev_ratios.get(key, 0) or 0
            if prev == 0:
                continue
            change_pct = round((curr - prev) / abs(prev) * 100, 1)
            if abs(change_pct) > 20:
                direction = "increase" if change_pct > 0 else "decrease"
                # Determine if positive or negative
                positive_metrics = {"revenue", "gross_profit", "net_profit", "ebitda", "cash", "current_assets"}
                negative_metrics = {"cogs", "admin_expenses", "selling_expenses", "total_liabilities"}
                if key in positive_metrics:
                    anomaly_type = "positive_anomaly" if change_pct > 0 else "negative_anomaly"
                elif key in negative_metrics:
                    anomaly_type = "negative_anomaly" if change_pct > 0 else "positive_anomaly"
                else:
                    anomaly_type = "positive_anomaly" if change_pct > 0 else "negative_anomaly"

                anomalies.append({
                    "metric": label,
                    "change_pct": change_pct,
                    "direction": direction,
                    "type": anomaly_type,
                    "current": curr,
                    "previous": prev,
                    "detail": f"{label} changed by {change_pct:+.1f}% ({_fmt_gel(prev)} -> {_fmt_gel(curr)})",
                })

        # Sort by absolute change
        anomalies.sort(key=lambda a: abs(a["change_pct"]), reverse=True)
        return anomalies

    # ─── 5. Recommendations ────────────────────────────────────────

    def _generate_recommendations(
        self, ratios: Dict[str, float], balance_sheet: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        rev = ratios.get("revenue", 0)
        np_ = ratios.get("net_profit", 0)
        gm = ratios.get("gross_margin_pct", 0)
        nm = ratios.get("net_margin_pct", 0)
        de = ratios.get("debt_to_equity", 0)
        cr = ratios.get("current_ratio", 0)
        admin = ratios.get("admin_expenses", 0)
        cogs = ratios.get("cogs", 0)

        # Prioritized by severity
        if np_ < 0:
            opex_cut = abs(np_) * 0.5
            recs.append({
                "recommendation": "Address net loss urgently",
                "category": "profitability",
                "priority": 1,
                "detail": f"The company has a net loss of {_fmt_gel(abs(np_))}. Cut operating expenses by at least {_fmt_gel(opex_cut)} to approach breakeven.",
                "estimated_impact_gel": round(opex_cut, 0),
            })

        if gm < 15 and rev > 0 and cogs > 0:
            target_cogs = rev * 0.85
            savings = cogs - target_cogs
            if savings > 0:
                recs.append({
                    "recommendation": "Improve gross margin through procurement optimization",
                    "category": "cost_reduction",
                    "priority": 2,
                    "detail": f"Gross margin ({gm:.1f}%) is below the 15% target. Reducing COGS by {_fmt_gel(savings)} would restore healthy margins.",
                    "estimated_impact_gel": round(savings, 0),
                })

        if de > 3:
            recs.append({
                "recommendation": "Reduce leverage ratio",
                "category": "balance_sheet",
                "priority": 2,
                "detail": f"D/E ratio ({de:.2f}) is above 3.0. Prioritize debt reduction or equity strengthening.",
                "estimated_impact_gel": 0,
            })

        if cr > 0 and cr < 1.2:
            recs.append({
                "recommendation": "Improve working capital management",
                "category": "liquidity",
                "priority": 2,
                "detail": f"Current ratio ({cr:.2f}) is tight. Accelerate receivable collections or renegotiate payable terms.",
                "estimated_impact_gel": 0,
            })

        if admin > 0 and rev > 0 and (admin / rev * 100) > 8:
            savings = admin - (rev * 0.07)
            recs.append({
                "recommendation": "Reduce administrative overhead",
                "category": "operational_efficiency",
                "priority": 3,
                "detail": f"Admin expenses ({admin / rev * 100:.1f}% of revenue) exceed the 8% benchmark. Target: 7%.",
                "estimated_impact_gel": round(max(0, savings), 0),
            })

        if not recs:
            recs.append({
                "recommendation": "Maintain and grow",
                "category": "growth",
                "priority": 3,
                "detail": "Financials are healthy. Focus on top-line growth and market expansion.",
                "estimated_impact_gel": 0,
            })

        recs.sort(key=lambda r: r["priority"])
        return recs[:3]

    # ─── 6. KPI Threshold Checks ───────────────────────────────────

    def _check_kpi_thresholds(self, ratios: Dict[str, float], industry: str = None) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        cfg = _get_industry_config(industry)
        benchmarks = cfg["benchmarks"]

        for metric_key, bench in benchmarks.items():
            value = ratios.get(metric_key)
            if value is None:
                continue

            label = bench["label"]

            if "healthy" in bench:
                # "above" direction
                healthy_v = bench["healthy"]
                warning_v = bench["warning"]
                critical_v = bench["critical"]
                if value >= healthy_v:
                    status = "on_track"
                elif value >= warning_v:
                    status = "at_risk"
                elif value > critical_v:
                    status = "warning"
                else:
                    status = "critical"
            else:
                # "below" direction
                healthy_v = bench["healthy_max"]
                warning_v = bench["warning_max"]
                critical_v = bench["critical_max"]
                if value <= healthy_v:
                    status = "on_track"
                elif value <= warning_v:
                    status = "at_risk"
                elif value <= critical_v:
                    status = "warning"
                else:
                    status = "critical"

            alerts.append({
                "metric": metric_key,
                "label": label,
                "value": round(value, 2),
                "benchmark": healthy_v,
                "status": status,
            })

        return alerts

    # ─── 7. Trend Signals ──────────────────────────────────────────

    def _analyze_trends(
        self, ratios: Dict[str, float], prev_ratios: Optional[Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        if not prev_ratios:
            return []

        signals: List[Dict[str, Any]] = []
        trend_metrics = [
            ("gross_margin_pct", "Gross Margin", "above"),
            ("net_margin_pct", "Net Margin", "above"),
            ("ebitda_margin_pct", "EBITDA Margin", "above"),
            ("current_ratio", "Current Ratio", "above"),
            ("debt_to_equity", "Debt/Equity", "below"),
            ("cogs_to_revenue_pct", "COGS/Revenue", "below"),
        ]

        for key, label, direction in trend_metrics:
            curr = ratios.get(key)
            prev = prev_ratios.get(key)
            if curr is None or prev is None:
                continue

            delta = curr - prev
            if abs(delta) < 0.01:
                trend = "stable"
            elif direction == "above":
                trend = "improving" if delta > 0 else "deteriorating"
            else:
                trend = "improving" if delta < 0 else "deteriorating"

            signals.append({
                "metric": label,
                "current": round(curr, 2),
                "previous": round(prev, 2),
                "delta": round(delta, 2),
                "trend": trend,
            })

        return signals

    # ─── 8. Narrative ──────────────────────────────────────────────

    def _generate_narrative(self, ratios: Dict[str, float]) -> str:
        rev = ratios.get("revenue", 0)
        np_ = ratios.get("net_profit", 0)
        gm = ratios.get("gross_margin_pct", 0)
        nm = ratios.get("net_margin_pct", 0)

        if rev <= 0:
            return "Insufficient financial data to generate a narrative."

        parts = []

        # Sentence 1 — top line
        parts.append(
            f"The company generated {_fmt_gel(rev)} in revenue"
            f" with a gross margin of {gm:.1f}%."
        )

        # Sentence 2 — profitability
        if np_ > 0:
            parts.append(
                f"Net profit reached {_fmt_gel(np_)} ({nm:.1f}% net margin),"
                f" indicating a profitable period."
            )
        elif np_ == 0:
            parts.append("The company broke even this period with zero net profit.")
        else:
            parts.append(
                f"The company posted a net loss of {_fmt_gel(abs(np_))}"
                f" ({nm:.1f}% net margin), requiring immediate attention."
            )

        # Sentence 3 — balance sheet color
        cr = ratios.get("current_ratio", 0)
        de = ratios.get("debt_to_equity", 0)
        if cr > 0 and de > 0:
            if cr >= 1.5 and de <= 2.5:
                parts.append("The balance sheet is healthy with adequate liquidity and conservative leverage.")
            elif cr < 1.0:
                parts.append("Liquidity is a concern — current liabilities exceed current assets.")
            elif de > 3.0:
                parts.append("Leverage is elevated and debt reduction should be prioritized.")
            else:
                parts.append("Balance sheet metrics are within acceptable ranges but warrant monitoring.")

    def _assess_strategic_exposure(self) -> Dict[str, Any]:
        """
        Pulls data from RiskIntelligenceEngine to identify strategic infrastructure exposure.
        """
        try:
            from app.services.risk_intelligence import risk_engine
            risk_data = risk_engine.get_situational_risk_sync() # Assume a sync helper or use run_until_complete logic
            
            # For simplicity in this proactive loop, we pull the cached risk state
            cached = risk_engine._get_cache("risk_full")
            if not cached:
                return {"status": "monitoring", "signals": 0, "message": "Establishing connection to infrastructure feed..."}

            routes = cached.get("routes", [])
            high_risk = [r for r in routes if r.get("risk_score", 0) > 50]
            exposure = sum(r.get("financial_exposure_daily", 0) for r in high_risk)
            
            msg = "Strategic corridor is stable."
            if high_risk:
                msg = f"Alert: {len(high_risk)} critical routes at risk. Total 24h exposure: ₾{exposure/1000:.1f}K."

            return {
                "status": "critical" if any(r.get("risk_score",0) > 75 for r in routes) else "warning" if high_risk else "healthy",
                "affected_routes": [r["name"] for r in high_risk],
                "financial_exposure_gel": exposure,
                "summary": msg,
                "market_sentiment": cached.get("market_pulse", [])[0].get("sentiment", "neutral") if cached.get("market_pulse") else "neutral"
            }
        except Exception as e:
            logger.error("Strategic exposure check failed: %s", e)
            return {"status": "error", "message": "Strategic telemetry unavailable."}

# ── Singleton ──────────────────────────────────────────────────────────

proactive_intelligence = ProactiveIntelligence()
