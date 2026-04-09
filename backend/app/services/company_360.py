"""
Company 360° View — Unified Company Intelligence
==================================================
Aggregates ALL data sources into a single comprehensive view:
  - Financial Core (DataStore snapshots)
  - Proactive Intelligence (health, risks, opportunities)
  - Ontology (KPIs, risk signals, actions)
  - Sub-ledgers (AR aging, AP aging, FA register)
  - Warehouse (historical trends, anomalies)
  - Activity feed (recent events)
  - Workflow executions (recent runs)

Deterministic — no LLM calls. Pure aggregation and computation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Company360Generator:
    """Generates a unified 360-degree company view from all data sources."""

    def generate(
        self,
        company_id: int = 1,
        period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a full 360 view.

        Returns a dict with:
          company, period, health, financials, ratios, risks,
          opportunities, recommendations, kpi_status, subledgers,
          trends, recent_activity, recent_workflows, ai_narrative, causal_drivers
        """
        # ── 1. Company metadata ─────────────────────────────────────
        company_info = self._get_company_info(company_id)
        currency = company_info.get("base_currency", "GEL")
        industry = company_info.get("industry", "fuel_distribution")

        # ── 2. Financial data ───────────────────────────────────────
        financials, period_name = self._get_financials(company_id, period)
        previous = self._get_previous_financials(company_id, period_name)
        balance_sheet = self._extract_balance_sheet(financials)

        # ── 3. Ratios ───────────────────────────────────────────────
        ratios = self._compute_ratios(financials)

        # ── 4. Health assessment ────────────────────────────────────
        health = self._get_health(financials, previous, balance_sheet, industry)

        # ── 5. Risks, opportunities, recommendations ────────────────
        risks = self._get_risks(financials, ratios)
        opportunities = self._get_opportunities(financials, ratios)
        recommendations = self._get_recommendations(financials, previous, balance_sheet)

        # ── 6. KPI status ──────────────────────────────────────────
        kpi_status = self._get_kpi_status(financials)

        # ── 7. Sub-ledger summary ──────────────────────────────────
        subledgers = self._get_subledger_summary()

        # ── 8. Trends ──────────────────────────────────────────────
        trends = self._get_trends(company_id)

        # ── 9. Recent activity ─────────────────────────────────────
        recent_activity = self._get_recent_activity(company_id)

        # ── 10. Recent workflows ───────────────────────────────────
        recent_workflows = self._get_recent_workflows(company_id)

        # ── 11. AI narrative (deterministic) ───────────────────────
        ai_narrative = self._build_narrative(
            company_info, financials, ratios, health, risks
        )

        # ── 12. Causal drivers ─────────────────────────────────────
        causal_drivers = self._get_causal_drivers(financials, previous)

        return {
            "company": {
                "name": company_info.get("name", "Company"),
                "industry": industry,
                "currency": currency,
            },
            "period": period_name,
            "health": health,
            "financials": {
                "revenue": financials.get("revenue", 0),
                "gross_profit": financials.get("gross_profit", 0),
                "ebitda": financials.get("ebitda", 0),
                "net_profit": financials.get("net_profit", 0),
                "total_assets": financials.get("total_assets", balance_sheet.get("total_assets", 0)),
                "total_liabilities": financials.get("total_liabilities", balance_sheet.get("total_liabilities", 0)),
                "total_equity": financials.get("total_equity", balance_sheet.get("total_equity", 0)),
                "cash": financials.get("cash", balance_sheet.get("cash", 0)),
            },
            "ratios": ratios,
            "risks": risks,
            "opportunities": opportunities,
            "recommendations": recommendations,
            "kpi_status": kpi_status,
            "subledgers": subledgers,
            "trends": trends,
            "recent_activity": recent_activity,
            "recent_workflows": recent_workflows,
            "ai_narrative": ai_narrative,
            "causal_drivers": causal_drivers,
        }

    # ── Internal helpers ────────────────────────────────────────────

    def _get_company_info(self, company_id: int) -> Dict[str, Any]:
        try:
            from app.services.data_store import data_store
            info = data_store.get_company(company_id)
            if info:
                return info
        except Exception:
            pass
        return {"id": company_id, "name": "Company", "industry": "fuel_distribution", "base_currency": "GEL"}

    def _get_financials(self, company_id: int, period: Optional[str]) -> tuple:
        try:
            from app.services.data_store import data_store

            # Try the same method the dashboard uses
            if period:
                data = data_store.get_financials(company_id, period)
                if data and data.get("revenue"):
                    return data, period

            # Try all company IDs if company_id=1 returns nothing
            for cid in range(1, 20):
                periods = data_store.get_all_periods(cid)
                if periods:
                    target = period if period and period in periods else periods[-1]
                    data = data_store.get_financials(cid, target)
                    if data and data.get("revenue"):
                        return data, target

            # Fallback: get active dataset financials
            active = data_store.get_active_financials()
            if active and active.get("revenue"):
                return active, active.get("period", period or "unknown")

        except Exception as e:
            logger.debug(f"Company360 _get_financials: {e}")
        return {}, period or "unknown"

    def _get_previous_financials(self, company_id: int, current_period: str) -> Dict[str, float]:
        try:
            from app.services.data_store import data_store
            periods = data_store.get_all_periods(company_id)
            if len(periods) >= 2:
                idx = periods.index(current_period) if current_period in periods else -1
                if idx > 0:
                    return data_store.get_financials(company_id, periods[idx - 1])
        except Exception:
            pass
        return {}

    def _extract_balance_sheet(self, financials: Dict[str, float]) -> Dict[str, float]:
        bs_keys = [
            "total_assets", "total_liabilities", "total_equity", "cash",
            "current_assets", "current_liabilities", "non_current_assets",
            "non_current_liabilities", "receivables", "inventory", "payables",
            "fixed_assets", "intangible_assets",
        ]
        return {k: financials.get(k, 0) for k in bs_keys}

    def _compute_ratios(self, f: Dict[str, float]) -> Dict[str, Any]:
        rev = f.get("revenue", 0)
        gp = f.get("gross_profit", 0)
        ebitda = f.get("ebitda", 0)
        np_ = f.get("net_profit", 0)
        ta = f.get("total_assets", 0)
        tl = f.get("total_liabilities", 0)
        te = f.get("total_equity", 0)
        ca = f.get("current_assets", 0)
        cl = f.get("current_liabilities", 0)

        return {
            "gross_margin": round(gp / rev * 100, 1) if rev else 0,
            "net_margin": round(np_ / rev * 100, 1) if rev else 0,
            "ebitda_margin": round(ebitda / rev * 100, 1) if rev else 0,
            "current_ratio": round(ca / cl, 2) if cl else 0,
            "debt_to_equity": round(tl / te, 2) if te and te != 0 else 0,
            "asset_turnover": round(rev / ta, 2) if ta else 0,
        }

    def _get_health(self, financials, previous, balance_sheet, industry) -> Dict[str, Any]:
        try:
            from app.services.diagnosis_engine import DiagnosisEngine
            engine = DiagnosisEngine()
            report = engine.diagnose(financials, previous, balance_sheet, industry)
            bullets = []
            for d in report.diagnoses[:5]:
                bullets.append(d.root_cause)
            return {
                "score": report.health_score,
                "grade": report.health_grade,
                "bullets": bullets,
            }
        except Exception as e:
            logger.warning("Health assessment failed: %s", e)
            # Fallback deterministic scoring
            score = self._fallback_health_score(financials)
            grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D" if score >= 20 else "F"
            return {"score": round(score, 1), "grade": grade, "bullets": []}

    def _fallback_health_score(self, f: Dict[str, float]) -> float:
        score = 50.0
        rev = f.get("revenue", 0)
        np_ = f.get("net_profit", 0)
        gp = f.get("gross_profit", 0)

        if rev > 0:
            gm = gp / rev * 100
            nm = np_ / rev * 100
            if gm > 30:
                score += 15
            elif gm > 15:
                score += 5
            elif gm < 5:
                score -= 15
            if nm > 5:
                score += 15
            elif nm > 0:
                score += 5
            elif nm < -10:
                score -= 20
        return max(0, min(100, score))

    def _get_risks(self, financials: Dict, ratios: Dict) -> List[Dict[str, Any]]:
        risks = []
        nm = ratios.get("net_margin", 0)
        cr = ratios.get("current_ratio", 0)
        de = ratios.get("debt_to_equity", 0)
        gm = ratios.get("gross_margin", 0)

        if nm < 0:
            risks.append({
                "severity": "critical" if nm < -10 else "warning",
                "title": "Negative profitability",
                "detail": f"Net margin is {nm}%, indicating operating losses.",
                "metric": "net_margin",
            })
        if cr < 1.0 and cr > 0:
            risks.append({
                "severity": "critical",
                "title": "Liquidity risk",
                "detail": f"Current ratio is {cr}, below safe threshold of 1.0.",
                "metric": "current_ratio",
            })
        if de > 3.0:
            risks.append({
                "severity": "warning" if de < 5.0 else "critical",
                "title": "High leverage",
                "detail": f"Debt-to-equity ratio is {de}, exceeding safe levels.",
                "metric": "debt_to_equity",
            })
        if gm < 15:
            risks.append({
                "severity": "warning" if gm > 5 else "critical",
                "title": "Thin gross margins",
                "detail": f"Gross margin of {gm}% leaves little room for operating expenses.",
                "metric": "gross_margin",
            })
        return risks

    def _get_opportunities(self, financials: Dict, ratios: Dict) -> List[Dict[str, Any]]:
        opps = []
        rev = financials.get("revenue", 0)
        gm = ratios.get("gross_margin", 0)
        cogs = financials.get("cogs", 0)

        if cogs > 0 and rev > 0:
            savings_1pct = cogs * 0.01
            opps.append({
                "title": "COGS optimization",
                "detail": f"A 1% reduction in COGS would save {savings_1pct:,.0f} and improve gross margin.",
                "estimated_impact": round(savings_1pct),
                "category": "cost_reduction",
            })
        if gm < 20 and rev > 0:
            target_gp = rev * 0.20
            current_gp = financials.get("gross_profit", 0)
            gap = target_gp - current_gp
            opps.append({
                "title": "Pricing strategy review",
                "detail": f"Reaching 20% gross margin would generate additional {gap:,.0f} in gross profit.",
                "estimated_impact": round(gap),
                "category": "revenue_growth",
            })
        ga = abs(financials.get("ga_expenses", financials.get("admin_expenses", 0)))
        if ga > 0 and rev > 0:
            ga_pct = ga / rev * 100
            if ga_pct > 5:
                savings = ga * 0.10
                opps.append({
                    "title": "G&A cost rationalization",
                    "detail": f"G&A at {ga_pct:.1f}% of revenue. 10% reduction saves {savings:,.0f}.",
                    "estimated_impact": round(savings),
                    "category": "cost_reduction",
                })
        return opps

    def _get_recommendations(self, financials, previous, balance_sheet) -> List[Dict[str, Any]]:
        try:
            from app.services.diagnosis_engine import DiagnosisEngine
            engine = DiagnosisEngine()
            report = engine.diagnose(financials, previous, balance_sheet)
            return [r.to_dict() for r in report.recommendations[:8]]
        except Exception:
            return []

    def _get_kpi_status(self, financials: Dict) -> List[Dict[str, Any]]:
        try:
            from app.services.monitoring_engine import KPIWatcher
            watcher = KPIWatcher()
            statuses = watcher.evaluate(financials)
            return [s.to_dict() if hasattr(s, "to_dict") else {"metric": str(s)} for s in statuses]
        except Exception:
            return []

    def _get_subledger_summary(self) -> Dict[str, Any]:
        result = {
            "ar_total": 0, "ar_overdue": 0,
            "ap_total": 0, "ap_due_30_days": 0,
            "fa_total_nbv": 0, "fa_asset_count": 0,
        }
        try:
            from app.services.subledger import ar_subledger, ap_subledger, fa_register
            # AR
            ar_aging = ar_subledger.get_aging_report()
            result["ar_total"] = ar_aging.get("total_outstanding", 0)
            buckets = ar_aging.get("buckets", {})
            result["ar_overdue"] = (
                buckets.get("1_30", 0) + buckets.get("31_60", 0) +
                buckets.get("61_90", 0) + buckets.get("over_90", 0)
            )
            # AP
            ap_aging = ap_subledger.get_aging_report()
            result["ap_total"] = ap_aging.get("total_outstanding", 0)
            ap_buckets = ap_aging.get("buckets", {})
            result["ap_due_30_days"] = ap_buckets.get("current", 0) + ap_buckets.get("1_30", 0)
            # FA
            fa_summary = fa_register.summary()
            result["fa_total_nbv"] = fa_summary.get("total_nbv", 0)
            result["fa_asset_count"] = fa_summary.get("asset_count", 0)
        except Exception as e:
            logger.debug("Subledger summary partial: %s", e)
        return result

    def _get_trends(self, company_id: int) -> Dict[str, List[Dict]]:
        trends: Dict[str, List[Dict]] = {"revenue": [], "net_profit": []}
        try:
            from app.services.data_store import data_store
            periods = data_store.get_all_periods(company_id)
            for p in periods[-12:]:  # Last 12 periods
                data = data_store.get_financials(company_id, p)
                if data:
                    trends["revenue"].append({"period": p, "value": data.get("revenue", 0)})
                    trends["net_profit"].append({"period": p, "value": data.get("net_profit", 0)})
        except Exception:
            pass
        return trends

    def _get_recent_activity(self, company_id: int) -> List[Dict[str, Any]]:
        events = []
        try:
            from app.services.data_store import data_store
            conn = data_store._conn()
            try:
                rows = conn.execute(
                    "SELECT filename, status, created_at FROM upload_history ORDER BY created_at DESC LIMIT 10"
                ).fetchall()
                for r in rows:
                    events.append({
                        "type": "upload",
                        "description": f"Uploaded {r['filename']}",
                        "status": r["status"],
                        "timestamp": r["created_at"],
                    })
            finally:
                conn.close()
        except Exception:
            pass
        try:
            from app.services.data_store import data_store
            conn = data_store._conn()
            try:
                rows = conn.execute(
                    "SELECT health_grade, health_score, execution_ms, created_at FROM orchestrator_runs ORDER BY created_at DESC LIMIT 5"
                ).fetchall()
                for r in rows:
                    events.append({
                        "type": "analysis",
                        "description": f"Analysis run — Health: {r['health_grade']} ({r['health_score']:.0f})",
                        "status": "completed",
                        "timestamp": r["created_at"],
                    })
            finally:
                conn.close()
        except Exception:
            pass
        # Sort by timestamp desc
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events[:10]

    def _get_recent_workflows(self, company_id: int) -> List[Dict[str, Any]]:
        try:
            from app.services.data_store import data_store
            conn = data_store._conn()
            try:
                rows = conn.execute(
                    "SELECT strategy_name, health_grade, health_score, execution_ms, created_at FROM orchestrator_runs ORDER BY created_at DESC LIMIT 5"
                ).fetchall()
                return [{
                    "type": "orchestrator",
                    "name": r["strategy_name"] or "Full Pipeline",
                    "health_grade": r["health_grade"],
                    "health_score": r["health_score"],
                    "execution_ms": r["execution_ms"],
                    "timestamp": r["created_at"],
                } for r in rows]
            finally:
                conn.close()
        except Exception:
            return []

    def _build_narrative(self, company, financials, ratios, health, risks) -> str:
        name = company.get("name", "The company")
        grade = health.get("grade", "?")
        score = health.get("score", 0)
        rev = financials.get("revenue", 0)
        np_ = financials.get("net_profit", 0)
        nm = ratios.get("net_margin", 0)
        gm = ratios.get("gross_margin", 0)

        parts = []
        parts.append(
            f"{name} has a financial health score of {score:.0f}/100 (Grade {grade})."
        )

        if rev > 0:
            rev_str = f"{rev / 1e6:.1f}M" if rev >= 1e6 else f"{rev:,.0f}"
            np_str = f"{abs(np_) / 1e6:.1f}M" if abs(np_) >= 1e6 else f"{abs(np_):,.0f}"
            if np_ < 0:
                parts.append(
                    f"Revenue stands at {rev_str} with a net loss of {np_str} ({nm:.1f}% net margin)."
                )
            else:
                parts.append(
                    f"Revenue stands at {rev_str} with net profit of {np_str} ({nm:.1f}% net margin)."
                )

        if risks:
            critical = [r for r in risks if r.get("severity") == "critical"]
            if critical:
                parts.append(
                    f"There are {len(critical)} critical risk(s) requiring immediate attention: "
                    + "; ".join(r["title"] for r in critical[:3]) + "."
                )

        return " ".join(parts)

    def _get_causal_drivers(self, financials: Dict, previous: Dict) -> List[Dict[str, Any]]:
        drivers = []
        if not previous:
            return drivers

        key_metrics = [
            ("revenue", "Revenue"),
            ("cogs", "COGS"),
            ("gross_profit", "Gross Profit"),
            ("ebitda", "EBITDA"),
            ("net_profit", "Net Profit"),
        ]
        for key, label in key_metrics:
            cur = financials.get(key, 0)
            prev = previous.get(key, 0)
            if prev != 0:
                change_pct = (cur - prev) / abs(prev) * 100
                if abs(change_pct) > 2:
                    drivers.append({
                        "metric": label,
                        "current": cur,
                        "previous": prev,
                        "change_pct": round(change_pct, 1),
                        "direction": "up" if change_pct > 0 else "down",
                        "impact": "positive" if (
                            (key != "cogs" and change_pct > 0) or
                            (key == "cogs" and change_pct < 0)
                        ) else "negative",
                    })
        return drivers


# ── Singleton ──────────────────────────────────────────────────────
company_360 = Company360Generator()
