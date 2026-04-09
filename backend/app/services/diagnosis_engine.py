"""
Phase H: Financial Diagnostic Engine
=====================================
Orchestrates existing reasoning components into a unified diagnostic pipeline:
    data -> compute -> INTERPRET -> DIAGNOSE -> RECOMMEND -> report

Components:
    MetricSignalDetector  - Detects meaningful financial deltas
    DiagnosisEngine       - Orchestrates causal analysis + KG + benchmarks
    RecommendationEngine  - Generates prioritized prescriptive actions

Reuses:
    - financial_reasoning.reasoning_engine  (CausalChain, scenarios, liquidity, accounting checks)
    - knowledge_graph.knowledge_graph       (audit_signal, fraud_signal entities)
    - benchmark_engine.benchmark_engine     (industry comparison)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MetricSignal:
    """A detected meaningful change or breach in a financial metric."""
    metric: str
    current_value: float
    previous_value: float
    change_absolute: float
    change_pct: float
    direction: str       # "up" | "down" | "flat"
    severity: str        # "critical" | "high" | "medium" | "low"
    signal_type: str     # "period_change" | "threshold_breach"
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "change_absolute": round(self.change_absolute, 2),
            "change_pct": round(self.change_pct, 2),
            "direction": self.direction,
            "severity": self.severity,
            "signal_type": self.signal_type,
            "description": self.description,
        }


@dataclass
class Diagnosis:
    """Root-cause analysis for a detected metric signal."""
    signal: MetricSignal
    root_cause: str
    causal_chain: Optional[Dict[str, Any]] = None
    matching_audit_signals: List[Dict[str, Any]] = field(default_factory=list)
    matching_fraud_signals: List[Dict[str, Any]] = field(default_factory=list)
    benchmark_status: Optional[str] = None
    business_impact_score: float = 0.0
    category: str = "profitability"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal.to_dict(),
            "root_cause": self.root_cause,
            "causal_chain": self.causal_chain,
            "matching_audit_signals": self.matching_audit_signals,
            "matching_fraud_signals": self.matching_fraud_signals,
            "benchmark_status": self.benchmark_status,
            "business_impact_score": round(self.business_impact_score, 1),
            "category": self.category,
        }


@dataclass
class Recommendation:
    """A prescriptive action derived from diagnosis."""
    action: str
    priority: str        # "critical" | "high" | "medium" | "low"
    expected_impact: str
    effort: str          # "low" | "medium" | "high"
    category: str        # "pricing" | "cost_control" | "operations" | "financing" | "compliance"
    source_metric: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "priority": self.priority,
            "expected_impact": self.expected_impact,
            "effort": self.effort,
            "category": self.category,
            "source_metric": self.source_metric,
        }


@dataclass
class DiagnosticReport:
    """Unified financial health assessment."""
    health_score: float = 100.0
    health_grade: str = "A"
    signal_summary: Dict[str, int] = field(default_factory=lambda: {
        "critical": 0, "high": 0, "medium": 0, "low": 0
    })
    diagnoses: List[Diagnosis] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    accounting_issues: List[Dict[str, Any]] = field(default_factory=list)
    liquidity: Dict[str, Any] = field(default_factory=dict)
    benchmark_summary: Dict[str, int] = field(default_factory=lambda: {
        "healthy": 0, "warning": 0, "critical": 0
    })
    anomaly_summary: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "health_score": round(self.health_score, 1),
            "health_grade": self.health_grade,
            "signal_summary": self.signal_summary,
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "accounting_issues": self.accounting_issues,
            "liquidity": self.liquidity,
            "benchmark_summary": self.benchmark_summary,
            "anomaly_summary": self.anomaly_summary,
            "generated_at": self.generated_at,
        }


# ═══════════════════════════════════════════════════════════════════
# METRIC SIGNAL DETECTOR
# ═══════════════════════════════════════════════════════════════════

class MetricSignalDetector:
    """Detects meaningful financial deltas and threshold breaches."""

    # Thresholds: {metric: {medium, high, critical}} in percentage points or %
    THRESHOLDS = {
        "revenue": {"medium": 5, "high": 15, "critical": 30, "mode": "pct"},
        "gross_margin_pct": {"medium": 3, "high": 5, "critical": 10, "mode": "pp"},
        "ebitda": {"medium": 10, "high": 20, "critical": 35, "mode": "pct"},
        "net_margin_pct": {"medium": 2, "high": 4, "critical": 8, "mode": "pp"},
        "cogs_to_revenue_pct": {"medium": 3, "high": 5, "critical": 10, "mode": "pp"},
        "ga_expenses": {"medium": 10, "high": 20, "critical": 40, "mode": "pct"},
        "ebitda_margin_pct": {"medium": 3, "high": 5, "critical": 10, "mode": "pp"},
        "net_profit": {"medium": 10, "high": 25, "critical": 50, "mode": "pct"},
        "cogs": {"medium": 5, "high": 15, "critical": 30, "mode": "pct"},
        "gross_profit": {"medium": 10, "high": 20, "critical": 40, "mode": "pct"},
    }

    # Friendly labels for metrics
    LABELS = {
        "revenue": "Revenue",
        "gross_margin_pct": "Gross Margin %",
        "ebitda": "EBITDA",
        "net_margin_pct": "Net Margin %",
        "cogs_to_revenue_pct": "COGS-to-Revenue %",
        "ga_expenses": "G&A Expenses",
        "ebitda_margin_pct": "EBITDA Margin %",
        "net_profit": "Net Profit",
        "cogs": "COGS",
        "gross_profit": "Gross Profit",
    }

    def detect_signals(
        self,
        current: Dict[str, float],
        previous: Optional[Dict[str, float]] = None,
    ) -> List[MetricSignal]:
        """
        Detect meaningful financial metric changes and absolute breaches.

        Args:
            current: Current period financial metrics
            previous: Prior period metrics (optional — enables period-over-period)

        Returns:
            List of MetricSignal sorted by severity (critical first)
        """
        signals: List[MetricSignal] = []

        # --- Period-over-period signals ---
        if previous:
            for metric, thresholds in self.THRESHOLDS.items():
                cur_val = current.get(metric)
                prev_val = previous.get(metric)
                if cur_val is None or prev_val is None:
                    continue

                mode = thresholds["mode"]
                if mode == "pp":
                    # Percentage-point change (for ratio metrics)
                    change_abs = cur_val - prev_val
                    change_pct = change_abs  # pp is the change itself
                    magnitude = abs(change_abs)
                elif mode == "pct":
                    # Percentage change (for absolute metrics)
                    change_abs = cur_val - prev_val
                    change_pct = (change_abs / abs(prev_val) * 100) if prev_val != 0 else 0
                    magnitude = abs(change_pct)
                else:
                    continue

                # Classify severity
                severity = self._classify_severity(magnitude, thresholds)
                if severity is None:
                    continue  # Below threshold

                direction = "up" if change_abs > 0 else ("down" if change_abs < 0 else "flat")
                label = self.LABELS.get(metric, metric)
                unit = "pp" if mode == "pp" else "%"
                desc = (
                    f"{label} changed {direction} by "
                    f"{abs(change_pct):.1f}{unit} "
                    f"(from {prev_val:,.1f} to {cur_val:,.1f})"
                )

                signals.append(MetricSignal(
                    metric=metric,
                    current_value=cur_val,
                    previous_value=prev_val,
                    change_absolute=change_abs,
                    change_pct=change_pct,
                    direction=direction,
                    severity=severity,
                    signal_type="period_change",
                    description=desc,
                ))

        # --- Absolute threshold breaches (no previous needed) ---
        gross_profit = current.get("gross_profit", current.get("gross_margin"))
        revenue = current.get("revenue", 0)
        cogs = current.get("cogs", 0)
        net_profit = current.get("net_profit")
        gm_pct = current.get("gross_margin_pct")

        # Negative gross margin
        if gm_pct is not None and gm_pct < 0:
            signals.append(MetricSignal(
                metric="gross_margin_pct",
                current_value=gm_pct, previous_value=0,
                change_absolute=gm_pct, change_pct=gm_pct,
                direction="down", severity="critical",
                signal_type="threshold_breach",
                description=f"Gross margin is NEGATIVE ({gm_pct:.1f}%) - selling below cost",
            ))
        elif gross_profit is not None and gross_profit < 0:
            signals.append(MetricSignal(
                metric="gross_profit",
                current_value=gross_profit, previous_value=0,
                change_absolute=gross_profit, change_pct=-100,
                direction="down", severity="critical",
                signal_type="threshold_breach",
                description=f"Gross profit is NEGATIVE ({gross_profit:,.0f}) - revenue does not cover COGS",
            ))

        # COGS exceeds revenue
        if revenue > 0 and cogs > revenue:
            signals.append(MetricSignal(
                metric="cogs",
                current_value=cogs, previous_value=revenue,
                change_absolute=cogs - revenue, change_pct=(cogs / revenue - 1) * 100,
                direction="up", severity="critical",
                signal_type="threshold_breach",
                description=f"COGS ({cogs:,.0f}) exceeds Revenue ({revenue:,.0f}) - unsustainable cost structure",
            ))

        # Negative net profit — severity scales with magnitude
        if net_profit is not None and net_profit < 0:
            if revenue and revenue > 0:
                loss_pct = abs(net_profit) / revenue * 100
            else:
                loss_pct = 100
            if loss_pct >= 10:
                np_severity = "critical"
            elif loss_pct >= 5:
                np_severity = "high"
            else:
                np_severity = "medium"
            signals.append(MetricSignal(
                metric="net_profit",
                current_value=net_profit, previous_value=0,
                change_absolute=net_profit, change_pct=-100,
                direction="down", severity=np_severity,
                signal_type="threshold_breach",
                description=f"Net profit is NEGATIVE ({net_profit:,.0f}) - company is operating at a loss",
            ))

        # Severely negative net margin
        nm_pct = current.get("net_margin_pct")
        if nm_pct is not None and nm_pct < -5:
            nm_sev = "critical" if nm_pct < -10 else "high"
            signals.append(MetricSignal(
                metric="net_margin_pct",
                current_value=nm_pct, previous_value=0,
                change_absolute=nm_pct, change_pct=nm_pct,
                direction="down", severity=nm_sev,
                signal_type="threshold_breach",
                description=f"Net margin is severely negative ({nm_pct:.1f}%)",
            ))

        # Negative EBITDA — operating loss before depreciation
        ebitda = current.get("ebitda")
        if ebitda is not None and ebitda < 0 and revenue > 0:
            ebitda_loss_pct = abs(ebitda) / revenue * 100
            ebitda_sev = "critical" if ebitda_loss_pct >= 5 else "high"
            signals.append(MetricSignal(
                metric="ebitda",
                current_value=ebitda, previous_value=0,
                change_absolute=ebitda, change_pct=-100,
                direction="down", severity=ebitda_sev,
                signal_type="threshold_breach",
                description=f"EBITDA is NEGATIVE ({ebitda:,.0f}) - operating at a loss before depreciation",
            ))

        # Deduplicate: if same metric has both period_change and threshold_breach, keep higher severity
        seen = {}
        for sig in signals:
            key = sig.metric
            sev_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            if key not in seen or sev_rank.get(sig.severity, 0) > sev_rank.get(seen[key].severity, 0):
                seen[key] = sig
        signals = list(seen.values())

        # Sort by severity (critical first)
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        signals.sort(key=lambda s: sev_order.get(s.severity, 9))

        return signals

    @staticmethod
    def _classify_severity(magnitude: float, thresholds: Dict) -> Optional[str]:
        """Classify change magnitude into severity level."""
        if magnitude >= thresholds["critical"]:
            return "critical"
        elif magnitude >= thresholds["high"]:
            return "high"
        elif magnitude >= thresholds["medium"]:
            return "medium"
        return None


# ═══════════════════════════════════════════════════════════════════
# RECOMMENDATION ENGINE
# ═══════════════════════════════════════════════════════════════════

class RecommendationEngine:
    """Generates prioritized prescriptive actions from diagnoses."""

    # Rule-based recommendation templates keyed by metric pattern
    _TEMPLATES = {
        "gross_margin_pct": {
            "down": {
                "action": "Review supplier pricing contracts and negotiate volume discounts to restore gross margin",
                "category": "pricing",
                "effort": "medium",
            },
            "up": {
                "action": "Investigate gross margin improvement sustainability - verify not due to revenue mix shift",
                "category": "operations",
                "effort": "low",
            },
        },
        "revenue": {
            "down": {
                "action": "Analyze customer segments for churn and develop targeted retention strategy for top 20% clients",
                "category": "operations",
                "effort": "high",
            },
        },
        "ga_expenses": {
            "up": {
                "action": "Conduct G&A expense audit and identify non-essential costs for immediate reduction",
                "category": "cost_control",
                "effort": "medium",
            },
        },
        "net_margin_pct": {
            "down": {
                "action": "Implement emergency cost reduction program targeting top 3 expense categories",
                "category": "cost_control",
                "effort": "medium",
            },
        },
        "net_profit": {
            "down": {
                "action": "Review all cost centers and defer non-critical capital expenditure to preserve cash",
                "category": "cost_control",
                "effort": "medium",
            },
        },
        "cogs": {
            "up": {
                "action": "Evaluate alternative suppliers and implement commodity hedging strategy",
                "category": "pricing",
                "effort": "high",
            },
        },
        "cogs_to_revenue_pct": {
            "up": {
                "action": "COGS growing faster than revenue - review procurement efficiency and pricing pass-through",
                "category": "pricing",
                "effort": "medium",
            },
        },
        "ebitda": {
            "down": {
                "action": "Focus revenue mix on margin-accretive products and segments",
                "category": "operations",
                "effort": "high",
            },
        },
        "ebitda_margin_pct": {
            "down": {
                "action": "Analyze EBITDA margin compression - decompose into gross margin vs operating cost drivers",
                "category": "operations",
                "effort": "medium",
            },
        },
        "gross_profit": {
            "down": {
                "action": "Gross profit declining - urgently review COGS composition and pricing strategy",
                "category": "pricing",
                "effort": "medium",
            },
        },
    }

    # Liquidity-based recommendations
    _LIQUIDITY_RECS = {
        "current_ratio_below_1": {
            "action": "Arrange short-term credit facility or negotiate extended payment terms with suppliers",
            "category": "financing",
            "effort": "high",
        },
        "negative_working_capital": {
            "action": "Restructure current liabilities or inject equity to restore positive working capital",
            "category": "financing",
            "effort": "high",
        },
        "high_leverage": {
            "action": "Reduce debt through asset monetization or equity raise to improve leverage ratio",
            "category": "financing",
            "effort": "high",
        },
    }

    # Accounting issue recommendations
    _COMPLIANCE_RECS = {
        "balance_sheet_imbalance": {
            "action": "Perform full balance sheet reconciliation before period close",
            "category": "compliance",
            "effort": "low",
        },
        "negative_equity": {
            "action": "Evaluate going concern status and prepare management representation letter",
            "category": "compliance",
            "effort": "low",
        },
    }

    def generate_recommendations(
        self,
        diagnoses: List[Diagnosis],
        liquidity: Dict[str, Any],
        accounting_issues: List[Dict],
        current_financials: Dict[str, float],
    ) -> List[Recommendation]:
        """
        Generate ranked recommendations from diagnoses and financial health data.

        Args:
            diagnoses: List of Diagnosis objects from DiagnosisEngine
            liquidity: Liquidity analysis dict from reasoning_engine
            accounting_issues: List of accounting issue dicts
            current_financials: Current P&L metrics for scenario quantification
        """
        recs: List[Recommendation] = []
        seen_actions: set = set()

        # --- From metric diagnoses ---
        for diag in diagnoses:
            metric = diag.signal.metric
            direction = diag.signal.direction
            templates = self._TEMPLATES.get(metric, {})
            tmpl = templates.get(direction)
            if not tmpl:
                continue

            action = tmpl["action"]
            if action in seen_actions:
                continue
            seen_actions.add(action)

            # Try to quantify impact via scenario simulation
            impact = self._quantify_impact(metric, direction, current_financials)

            recs.append(Recommendation(
                action=action,
                priority=diag.signal.severity,
                expected_impact=impact,
                effort=tmpl["effort"],
                category=tmpl["category"],
                source_metric=metric,
            ))

        # --- From liquidity flags ---
        liq_flags = liquidity.get("flags", [])
        liq_ratios = liquidity.get("ratios", {})
        if (liq_ratios.get("current_ratio") or 999) < 1.0 or "current_ratio_below_1" in liq_flags:
            tmpl = self._LIQUIDITY_RECS["current_ratio_below_1"]
            act = tmpl["action"]
            if act not in seen_actions:
                seen_actions.add(act)
                recs.append(Recommendation(
                    action=act, priority="critical",
                    expected_impact=f"Current ratio is {liq_ratios.get('current_ratio', 0):.2f} - below safe threshold of 1.0",
                    effort=tmpl["effort"], category=tmpl["category"], source_metric="current_ratio",
                ))

        if (liq_ratios.get("debt_to_equity") or 0) > 3.0 or "high_leverage" in liq_flags:
            tmpl = self._LIQUIDITY_RECS["high_leverage"]
            act = tmpl["action"]
            if act not in seen_actions:
                seen_actions.add(act)
                recs.append(Recommendation(
                    action=act, priority="high",
                    expected_impact=f"Debt-to-equity ratio is {liq_ratios.get('debt_to_equity', 0):.2f} - elevated financial risk",
                    effort=tmpl["effort"], category=tmpl["category"], source_metric="debt_to_equity",
                ))

        # --- From accounting issues ---
        for issue in accounting_issues:
            issue_type = issue.get("type", "")
            sev = issue.get("severity", "medium")
            for key, tmpl in self._COMPLIANCE_RECS.items():
                if key in issue_type:
                    act = tmpl["action"]
                    if act not in seen_actions:
                        seen_actions.add(act)
                        recs.append(Recommendation(
                            action=act,
                            priority="critical" if sev in ("critical", "high") else "medium",
                            expected_impact=issue.get("message", issue.get("description", "")),
                            effort=tmpl["effort"], category=tmpl["category"],
                            source_metric=issue_type,
                        ))

        # Sort: critical > high > medium > low
        prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recs.sort(key=lambda r: prio_order.get(r.priority, 9))

        return recs

    def _quantify_impact(self, metric: str, direction: str, financials: Dict) -> str:
        """Try to quantify recommendation impact using scenario simulation."""
        try:
            from app.services.financial_reasoning import reasoning_engine
            revenue = financials.get("revenue", 0)
            cogs = financials.get("cogs", 0)
            ga = financials.get("ga_expenses", 0)
            net = financials.get("net_profit", 0)

            if metric in ("cogs", "cogs_to_revenue_pct") and direction == "up" and cogs > 0:
                # Simulate 5% COGS reduction
                result = reasoning_engine.simulate_scenario(
                    "5% COGS reduction",
                    {"revenue": revenue, "cogs": cogs, "ga_expenses": ga},
                    {"cogs_pct": -5.0},
                )
                if result and hasattr(result, 'scenario_net_profit'):
                    improvement = result.scenario_net_profit - result.base_net_profit
                    return f"5% COGS reduction could improve net profit by {improvement:,.0f}"

            if metric == "ga_expenses" and direction == "up" and ga > 0:
                result = reasoning_engine.simulate_scenario(
                    "10% G&A reduction",
                    {"revenue": revenue, "cogs": cogs, "ga_expenses": ga},
                    {"ga_expenses_pct": -10.0},
                )
                if result and hasattr(result, 'scenario_net_profit'):
                    improvement = result.scenario_net_profit - result.base_net_profit
                    return f"10% G&A reduction could improve net profit by {improvement:,.0f}"

            if metric == "revenue" and direction == "down" and revenue > 0:
                return f"Each 1% revenue recovery = ~{revenue * 0.01:,.0f} additional top-line"

            if metric in ("gross_margin_pct", "gross_profit") and direction == "down":
                return f"Restoring gross margin to prior level would improve profitability significantly"

        except Exception:
            pass

        # Default: qualitative impact
        impact_map = {
            "critical": "High financial impact - requires immediate action",
            "high": "Significant financial impact - address within current period",
            "medium": "Moderate impact - plan corrective measures",
            "low": "Minor impact - monitor and review",
        }
        return impact_map.get("medium", "Financial impact to be quantified")


# ═══════════════════════════════════════════════════════════════════
# DIAGNOSIS ENGINE (ORCHESTRATOR)
# ═══════════════════════════════════════════════════════════════════

class DiagnosisEngine:
    """
    Orchestrates the full diagnostic pipeline:
        signals -> causal analysis -> KG matching -> benchmarks -> health score -> recommendations

    Reuses existing components:
        - reasoning_engine.explain_metric_change()
        - reasoning_engine.detect_accounting_issues()
        - reasoning_engine.build_liquidity_analysis()
        - knowledge_graph.query()
        - benchmark_engine.compare()
    """

    def __init__(self):
        self._signal_detector = MetricSignalDetector()
        self._rec_engine = RecommendationEngine()

    def run_full_diagnosis(
        self,
        current_financials: Dict[str, float],
        previous_financials: Optional[Dict[str, float]] = None,
        balance_sheet: Optional[Dict[str, float]] = None,
        industry_id: str = "fuel_distribution",
        anomaly_summary: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticReport:
        """
        Run the complete financial diagnostic pipeline.

        Args:
            current_financials: Flattened P&L metrics {revenue, cogs, gross_profit, ebitda, net_profit, ga_expenses, ...}
            previous_financials: Prior period metrics for comparison (optional)
            balance_sheet: BS data for liquidity/accounting checks (optional)
            industry_id: Industry for benchmark comparison
            anomaly_summary: Pre-computed anomaly detection results (optional)

        Returns:
            DiagnosticReport with health score, diagnoses, and recommendations
        """
        report = DiagnosticReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            anomaly_summary=anomaly_summary or {},
        )

        # Normalize metric keys (strip common prefixes)
        current = self._normalize_keys(current_financials)
        previous = self._normalize_keys(previous_financials) if previous_financials else None

        # Compute derived metrics if missing
        current = self._ensure_derived_metrics(current)
        if previous:
            previous = self._ensure_derived_metrics(previous)

        # ── Step 1: Signal Detection ──
        signals = self._signal_detector.detect_signals(current, previous)
        for sig in signals:
            report.signal_summary[sig.severity] = report.signal_summary.get(sig.severity, 0) + 1

        # ── Step 2: Causal Analysis + KG Matching for each signal ──
        diagnoses = []
        for sig in signals:
            diag = self._build_diagnosis(sig, current, previous)
            diagnoses.append(diag)

        # ── Step 3: Benchmark Comparison ──
        benchmark_comparisons = self._run_benchmarks(current, industry_id)
        for comp in benchmark_comparisons:
            status = comp.get("status", "unknown")
            if status in report.benchmark_summary:
                report.benchmark_summary[status] += 1

        # Enrich diagnoses with benchmark status
        bench_by_metric = {c.get("metric", ""): c for c in benchmark_comparisons}
        for diag in diagnoses:
            bench = bench_by_metric.get(diag.signal.metric)
            if bench:
                diag.benchmark_status = bench.get("status")

        # ── Step 4: Accounting Issues + Liquidity ──
        if balance_sheet:
            report.accounting_issues = self._check_accounting(current, balance_sheet)
            report.liquidity = self._check_liquidity(balance_sheet)
        else:
            report.accounting_issues = []
            report.liquidity = {}

        # ── Step 5: Business Impact Scoring ──
        for diag in diagnoses:
            diag.business_impact_score = self._compute_impact_score(diag)

        # Sort by impact score descending
        diagnoses.sort(key=lambda d: d.business_impact_score, reverse=True)
        report.diagnoses = diagnoses

        # ── Step 6: Recommendations ──
        report.recommendations = self._rec_engine.generate_recommendations(
            diagnoses=diagnoses,
            liquidity=report.liquidity,
            accounting_issues=report.accounting_issues,
            current_financials=current,
        )

        # ── Step 7: Health Score ──
        report.health_score = self._compute_health_score(
            signals=signals,
            accounting_issues=report.accounting_issues,
            benchmark_comparisons=benchmark_comparisons,
            liquidity=report.liquidity,
            anomaly_summary=anomaly_summary,
        )
        report.health_grade = self._grade(report.health_score)

        return report

    # ── Internal Methods ──

    def _normalize_keys(self, data: Dict[str, float]) -> Dict[str, float]:
        """Normalize metric keys: strip 'total_' prefix for compatibility."""
        if not data:
            return {}
        result = {}
        for k, v in data.items():
            # Strip 'total_' prefix (income statement uses total_revenue, etc.)
            clean = k.replace("total_", "") if k.startswith("total_") else k
            result[clean] = v
        # Also keep originals for backward compatibility
        result.update(data)
        return result

    def _ensure_derived_metrics(self, data: Dict[str, float]) -> Dict[str, float]:
        """Compute derived ratio metrics if missing."""
        revenue = data.get("revenue", 0)
        cogs = data.get("cogs", 0)
        gross_profit = data.get("gross_profit", data.get("gross_margin", 0))
        if not gross_profit and revenue and cogs:
            gross_profit = revenue - cogs
        net_profit = data.get("net_profit", 0)

        # Map operating_expenses -> ga_expenses if ga_expenses is missing
        if "ga_expenses" not in data and "operating_expenses" in data:
            data["ga_expenses"] = data["operating_expenses"]
        ga = data.get("ga_expenses", 0) or data.get("admin_expenses", 0)

        # Compute EBITDA if missing
        selling = abs(data.get("selling_expenses", 0))
        ebitda = data.get("ebitda", 0)
        if not ebitda and revenue > 0:
            ebitda = gross_profit - selling - abs(ga)
            data["ebitda"] = ebitda

        if "gross_margin_pct" not in data and revenue > 0:
            data["gross_margin_pct"] = gross_profit / revenue * 100
        if "net_margin_pct" not in data and revenue > 0:
            data["net_margin_pct"] = net_profit / revenue * 100
        if "ebitda_margin_pct" not in data and revenue > 0:
            data["ebitda_margin_pct"] = ebitda / revenue * 100
        if "cogs_to_revenue_pct" not in data and revenue > 0:
            data["cogs_to_revenue_pct"] = cogs / revenue * 100
        if "gross_profit" not in data:
            data["gross_profit"] = gross_profit

        return data

    def _build_diagnosis(
        self,
        signal: MetricSignal,
        current: Dict,
        previous: Optional[Dict],
    ) -> Diagnosis:
        """Build a Diagnosis for a single signal using causal analysis + KG."""
        root_cause = signal.description
        causal_dict = None
        audit_matches = []
        fraud_matches = []

        # Causal chain analysis (for medium+ severity with prior period data)
        if signal.severity in ("critical", "high", "medium") and previous:
            causal_dict = self._run_causal_analysis(signal, current, previous)
            if causal_dict:
                root_cause = causal_dict.get("primary_cause", root_cause)

        # KG signal matching
        audit_matches = self._query_kg_signals(signal.metric, "audit_signal")
        fraud_matches = self._query_kg_signals(signal.metric, "fraud_signal")

        # Determine category
        category = self._categorize(signal.metric)

        return Diagnosis(
            signal=signal,
            root_cause=root_cause,
            causal_chain=causal_dict,
            matching_audit_signals=audit_matches,
            matching_fraud_signals=fraud_matches,
            category=category,
        )

    def _run_causal_analysis(
        self,
        signal: MetricSignal,
        current: Dict,
        previous: Dict,
    ) -> Optional[Dict]:
        """Run CausalChain analysis via reasoning_engine."""
        try:
            from app.services.financial_reasoning import reasoning_engine
            chain = reasoning_engine.explain_metric_change(
                metric=signal.metric,
                from_value=signal.previous_value,
                to_value=signal.current_value,
                period_from="Previous Period",
                period_to="Current Period",
                context=current,
            )
            if chain:
                return {
                    "metric": chain.metric,
                    "severity": chain.severity,
                    "primary_cause": chain.primary_cause,
                    "factors": [
                        {
                            "factor": f.factor,
                            "direction": f.impact_direction,
                            "magnitude": f.magnitude,
                            "impact_pct": f.impact_pct,
                            "explanation": f.explanation,
                        }
                        for f in (chain.factors or [])
                    ],
                    "recommendations": chain.recommendations or [],
                    "narrative": chain.narrative,
                }
        except Exception:
            pass
        return None

    def _query_kg_signals(self, metric: str, entity_type: str) -> List[Dict]:
        """Query knowledge graph for matching audit/fraud signals."""
        try:
            from app.services.knowledge_graph import knowledge_graph
            if not knowledge_graph._is_built:
                knowledge_graph.build()
            # Search using metric name as query
            entities = knowledge_graph.query(
                query_text=metric.replace("_", " "),
                entity_types=[entity_type],
                max_results=3,
            )
            return [
                {
                    "id": getattr(e, "entity_id", ""),
                    "name": getattr(e, "name", getattr(e, "label", "")),
                    "description": getattr(e, "description", ""),
                    "severity": getattr(e, "metadata", {}).get("severity", "medium")
                    if hasattr(e, "metadata") else "medium",
                }
                for e in (entities or [])
            ]
        except Exception:
            return []

    def _run_benchmarks(self, current: Dict, industry_id: str) -> List[Dict]:
        """Compare current metrics against industry benchmarks."""
        try:
            from app.services.benchmark_engine import benchmark_engine
            # Map to benchmark metric names
            bench_metrics = {}
            mapping = {
                "gross_margin_pct": "gross_margin_pct",
                "net_margin_pct": "net_margin_pct",
                "ebitda_margin_pct": "ebitda_margin_pct",
                "cogs_to_revenue_pct": "cogs_to_revenue_pct",
            }
            for our_key, bench_key in mapping.items():
                if our_key in current:
                    bench_metrics[bench_key] = current[our_key]

            if not bench_metrics:
                return []

            comparisons = benchmark_engine.compare(bench_metrics, industry_id=industry_id)
            return [c.to_dict() if hasattr(c, "to_dict") else c for c in (comparisons or [])]
        except Exception:
            return []

    def _check_accounting(self, pl_data: Dict, bs_data: Dict) -> List[Dict]:
        """Run accounting consistency checks."""
        try:
            from app.services.financial_reasoning import reasoning_engine
            issues = reasoning_engine.detect_accounting_issues(pl_data, bs_data)
            return issues if isinstance(issues, list) else []
        except Exception:
            return []

    def _check_liquidity(self, bs_data: Dict) -> Dict:
        """Run liquidity analysis."""
        try:
            from app.services.financial_reasoning import reasoning_engine
            result = reasoning_engine.build_liquidity_analysis(bs_data)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _compute_impact_score(diag: Diagnosis) -> float:
        """Compute business impact score (0-100) for ranking diagnoses."""
        sev_weights = {"critical": 90, "high": 70, "medium": 40, "low": 15}
        base = sev_weights.get(diag.signal.severity, 20)

        # Modifier for large changes (up to +20)
        modifier = min(abs(diag.signal.change_pct) / 50 * 20, 20)

        # Bonus for matching audit/fraud signals
        audit_bonus = 5 if diag.matching_audit_signals else 0
        fraud_bonus = 5 if diag.matching_fraud_signals else 0

        # Benchmark penalty
        bench_penalty = 10 if diag.benchmark_status == "critical" else (
            3 if diag.benchmark_status == "warning" else 0
        )

        return min(base + modifier + audit_bonus + fraud_bonus + bench_penalty, 100)

    @staticmethod
    def _compute_health_score(
        signals: List[MetricSignal],
        accounting_issues: List[Dict],
        benchmark_comparisons: List[Dict],
        liquidity: Dict,
        anomaly_summary: Optional[Dict],
    ) -> float:
        """
        Compute transparent, auditable health score (0-100).

        Formula:
            Start at 100, deduct for each risk factor.
            Deductions scale with severity:
                critical = -20, high = -15, medium = -8, low = -3
        """
        score = 100.0

        # Deduct for metric signals
        for sig in signals:
            if sig.severity == "critical":
                score -= 20
            elif sig.severity == "high":
                score -= 15
            elif sig.severity == "medium":
                score -= 8
            elif sig.severity == "low":
                score -= 3

        # Deduct for accounting issues
        for issue in accounting_issues:
            sev = issue.get("severity", "medium")
            if sev in ("critical", "high"):
                score -= 12
            elif sev in ("warning", "medium"):
                score -= 5

        # Deduct for benchmark deviations
        for comp in benchmark_comparisons:
            status = comp.get("status", "unknown")
            if status == "critical":
                score -= 8
            elif status == "warning":
                score -= 3

        # Deduct for liquidity flags
        liq_health = liquidity.get("health", liquidity.get("overall_health", ""))
        if liq_health == "critical":
            score -= 12
        elif liq_health in ("warning", "caution"):
            score -= 5

        # Deduct for anomalies (capped)
        if anomaly_summary:
            by_sev = anomaly_summary.get("by_severity", {})
            score -= min(by_sev.get("critical", 0) * 4, 16)
            score -= min(by_sev.get("high", 0) * 2, 8)

        # MANDATORY: Penalize negative net profit (Net loss penalty)
        # Any company operating at a loss should not easily achieve an 'A' grade.
        for sig in signals:
            if sig.metric == "net_profit" and sig.current_value < 0:
                score -= 25  # Heavy penalty for being unprofitable
                break

        return max(0.0, min(100.0, score))

    @staticmethod
    def _grade(score: float) -> str:
        """Map health score to letter grade."""
        if score >= 85:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 50:
            return "C"
        elif score >= 30:
            return "D"
        return "F"

    @staticmethod
    def _categorize(metric: str) -> str:
        """Map metric to financial category."""
        profitability = {"revenue", "gross_margin_pct", "gross_profit", "net_margin_pct",
                         "net_profit", "ebitda", "ebitda_margin_pct"}
        efficiency = {"cogs", "cogs_to_revenue_pct", "ga_expenses"}
        if metric in profitability:
            return "profitability"
        elif metric in efficiency:
            return "efficiency"
        return "profitability"


# ═══════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════

diagnosis_engine = DiagnosisEngine()
