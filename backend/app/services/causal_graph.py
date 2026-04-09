"""
Causal Graph Generator — Visual Cause-Effect Chain Builder
============================================================
Builds a directed graph of financial metric causation:
  Revenue & COGS -> Gross Profit -> EBITDA -> Net Profit -> Health Score

Each node carries: value, change%, type.
Each edge carries: impact direction (positive/negative), strength.

Deterministic — no LLM calls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CausalGraphGenerator:
    """Generate a visual causal graph showing what drives financial health."""

    def generate(
        self,
        financials: Dict[str, float],
        previous: Optional[Dict[str, float]] = None,
        health_score: Optional[float] = None,
        health_grade: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build nodes + edges for P&L waterfall causation.

        Returns:
            {nodes: [...], edges: [...], root_causes: [...], impact_chain: [...]}
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # ── Extract values ──────────────────────────────────────────
        rev = financials.get("revenue", 0)
        cogs = abs(financials.get("cogs", 0))
        gp = financials.get("gross_profit", 0)
        selling = abs(financials.get("selling_expenses", 0))
        ga = abs(financials.get("ga_expenses", financials.get("admin_expenses", 0)))
        ebitda = financials.get("ebitda", 0)
        depr = abs(financials.get("depreciation", 0))
        interest = abs(financials.get("interest_expense", financials.get("finance_costs", 0)))
        other_exp = abs(financials.get("other_expenses", 0))
        other_inc = financials.get("other_income", 0)
        np_ = financials.get("net_profit", 0)

        # ── Compute changes if previous period available ────────────
        def _change(key: str) -> Optional[float]:
            if not previous:
                return None
            prev = previous.get(key, 0)
            cur = financials.get(key, 0)
            if prev == 0:
                return None
            return round((cur - prev) / abs(prev) * 100, 1)

        # ── Build nodes ─────────────────────────────────────────────
        nodes.append({
            "id": "revenue",
            "label": "Revenue",
            "value": rev,
            "change": _change("revenue"),
            "type": "income",
            "level": 0,
        })
        nodes.append({
            "id": "cogs",
            "label": "COGS",
            "value": cogs,
            "change": _change("cogs"),
            "type": "expense",
            "level": 0,
        })
        nodes.append({
            "id": "gross_profit",
            "label": "Gross Profit",
            "value": gp,
            "change": _change("gross_profit"),
            "type": "profit",
            "level": 1,
        })

        if selling > 0:
            nodes.append({
                "id": "selling",
                "label": "Selling Expenses",
                "value": selling,
                "change": _change("selling_expenses"),
                "type": "expense",
                "level": 1,
            })

        if ga > 0:
            nodes.append({
                "id": "ga",
                "label": "G&A Expenses",
                "value": ga,
                "change": _change("ga_expenses"),
                "type": "expense",
                "level": 1,
            })

        nodes.append({
            "id": "ebitda",
            "label": "EBITDA",
            "value": ebitda,
            "change": _change("ebitda"),
            "type": "profit",
            "level": 2,
        })

        if depr > 0:
            nodes.append({
                "id": "depreciation",
                "label": "D&A",
                "value": depr,
                "change": _change("depreciation"),
                "type": "expense",
                "level": 2,
            })

        if interest > 0:
            nodes.append({
                "id": "interest",
                "label": "Interest/Finance",
                "value": interest,
                "change": _change("interest_expense"),
                "type": "expense",
                "level": 2,
            })

        if other_exp > 0:
            nodes.append({
                "id": "other_expenses",
                "label": "Other Expenses",
                "value": other_exp,
                "change": _change("other_expenses"),
                "type": "expense",
                "level": 2,
            })

        if other_inc > 0:
            nodes.append({
                "id": "other_income",
                "label": "Other Income",
                "value": other_inc,
                "change": _change("other_income"),
                "type": "income",
                "level": 2,
            })

        nodes.append({
            "id": "net_profit",
            "label": "Net Profit",
            "value": np_,
            "change": _change("net_profit"),
            "type": "result",
            "level": 3,
        })

        # Health node
        h_score = health_score
        h_grade = health_grade
        if h_score is None:
            h_score = self._estimate_health(financials)
            h_grade = "A" if h_score >= 80 else "B" if h_score >= 60 else "C" if h_score >= 40 else "D" if h_score >= 20 else "F"

        nodes.append({
            "id": "health",
            "label": f"Health: {h_grade}",
            "value": h_score,
            "change": None,
            "type": "health",
            "level": 4,
        })

        # ── Build edges ─────────────────────────────────────────────
        edges.append({"source": "revenue", "target": "gross_profit", "impact": "positive", "strength": "strong"})
        edges.append({"source": "cogs", "target": "gross_profit", "impact": "negative", "strength": "strong"})
        edges.append({"source": "gross_profit", "target": "ebitda", "impact": "positive", "strength": "strong"})

        if selling > 0:
            edges.append({"source": "selling", "target": "ebitda", "impact": "negative", "strength": "moderate"})
        if ga > 0:
            edges.append({"source": "ga", "target": "ebitda", "impact": "negative", "strength": "moderate"})

        edges.append({"source": "ebitda", "target": "net_profit", "impact": "positive", "strength": "strong"})

        if depr > 0:
            edges.append({"source": "depreciation", "target": "net_profit", "impact": "negative", "strength": "moderate"})
        if interest > 0:
            edges.append({"source": "interest", "target": "net_profit", "impact": "negative", "strength": "moderate"})
        if other_exp > 0:
            edges.append({"source": "other_expenses", "target": "net_profit", "impact": "negative", "strength": "weak"})
        if other_inc > 0:
            edges.append({"source": "other_income", "target": "net_profit", "impact": "positive", "strength": "weak"})

        edges.append({"source": "net_profit", "target": "health", "impact": "positive" if np_ >= 0 else "negative", "strength": "strong"})

        # ── Root causes (full waterfall decomposition) ──────────────
        root_causes = []
        if previous:
            # Compute absolute contribution of each component to net profit change
            prev_np = previous.get("net_profit", 0)
            cur_np = financials.get("net_profit", 0)
            np_delta = cur_np - prev_np

            components = [
                ("Revenue", financials.get("revenue", 0) - previous.get("revenue", 0), "income"),
                ("COGS", -(abs(financials.get("cogs", 0)) - abs(previous.get("cogs", 0))), "expense"),
                ("Selling Expenses", -(abs(financials.get("selling_expenses", 0)) - abs(previous.get("selling_expenses", 0))), "expense"),
                ("G&A Expenses", -(abs(financials.get("ga_expenses", financials.get("admin_expenses", 0))) - abs(previous.get("ga_expenses", previous.get("admin_expenses", 0)))), "expense"),
                ("Depreciation", -(abs(financials.get("depreciation", 0)) - abs(previous.get("depreciation", 0))), "expense"),
                ("Interest", -(abs(financials.get("interest_expense", 0)) - abs(previous.get("interest_expense", 0))), "expense"),
                ("Other Income", financials.get("other_income", 0) - previous.get("other_income", 0), "income"),
                ("Other Expenses", -(abs(financials.get("other_expenses", 0)) - abs(previous.get("other_expenses", 0))), "expense"),
            ]

            # Sort by absolute contribution (biggest movers first)
            components.sort(key=lambda x: abs(x[1]), reverse=True)

            for name, delta, comp_type in components:
                if abs(delta) > 0:
                    contribution_pct = round(delta / abs(np_delta) * 100, 1) if np_delta != 0 else 0
                    root_causes.append({
                        "metric": name,
                        "absolute_change": round(delta, 0),
                        "contribution_pct": contribution_pct,
                        "impact": "positive" if delta > 0 else "negative",
                        "type": comp_type,
                        "is_primary": abs(contribution_pct) >= 25,
                    })

            # Keep top 5
            root_causes = root_causes[:5]

        # ── Impact chain (dynamic, data-driven) ────────────────────
        impact_chain = []
        if previous:
            rev_chg = _change("revenue")
            gp_chg = _change("gross_profit")
            ebitda_chg = _change("ebitda")
            np_chg = _change("net_profit")

            def _arrow(val):
                if val is None: return "→"
                return "↑" if val > 0 else "↓" if val < 0 else "→"

            def _fmt(val):
                if val is None: return "N/A"
                return f"{val:+.1f}%"

            impact_chain = [
                {"from": "Revenue", "to": "Gross Profit",
                 "effect": f"Revenue {_arrow(rev_chg)} {_fmt(rev_chg)} → Gross Profit {_arrow(gp_chg)} {_fmt(gp_chg)}",
                 "direction": "positive" if (rev_chg or 0) > 0 else "negative"},
                {"from": "Gross Profit", "to": "EBITDA",
                 "effect": f"After OpEx → EBITDA {_arrow(ebitda_chg)} {_fmt(ebitda_chg)}",
                 "direction": "positive" if (ebitda_chg or 0) > 0 else "negative"},
                {"from": "EBITDA", "to": "Net Profit",
                 "effect": f"After D&A, interest, tax → Net Profit {_arrow(np_chg)} {_fmt(np_chg)}",
                 "direction": "positive" if (np_chg or 0) > 0 else "negative"},
                {"from": "Net Profit", "to": "Health Score",
                 "effect": f"Net margin drives overall health ({h_grade})",
                 "direction": "positive" if np_ >= 0 else "negative"},
            ]
        else:
            # Static fallback when no previous period
            gm_pct = round(gp / rev * 100, 1) if rev else 0
            nm_pct = round(np_ / rev * 100, 1) if rev else 0
            impact_chain = [
                {"from": "Revenue", "to": "Gross Profit", "effect": f"Gross margin: {gm_pct}%", "direction": "positive" if gp > 0 else "negative"},
                {"from": "Gross Profit", "to": "EBITDA", "effect": f"EBITDA: {ebitda:,.0f}", "direction": "positive" if ebitda > 0 else "negative"},
                {"from": "EBITDA", "to": "Net Profit", "effect": f"Net margin: {nm_pct}%", "direction": "positive" if np_ > 0 else "negative"},
                {"from": "Net Profit", "to": "Health Score", "effect": f"Health: {h_grade} ({h_score:.0f}/100)", "direction": "positive" if np_ >= 0 else "negative"},
            ]

        self._compute_elasticities(nodes, edges, financials)

        return {
            "nodes": nodes,
            "edges": edges,
            "root_causes": root_causes,
            "impact_chain": impact_chain,
        }

    def _compute_elasticities(self, nodes: List[Dict], edges: List[Dict], financials: Dict[str, float]) -> None:
        """Add elasticity (sensitivity) data to each edge."""
        rev = financials.get("revenue", 0) or 1
        gp = financials.get("gross_profit", 0) or 1
        ebitda = financials.get("ebitda", 0) or 1
        np_ = financials.get("net_profit", 0) or 1

        # Impact weight = how much does a 1% change in source affect target?
        weight_map = {
            ("revenue", "gross_profit"): abs(rev / gp) if gp != 0 else 1.0,
            ("cogs", "gross_profit"): abs(financials.get("cogs", 0)) / abs(gp) if gp != 0 else 1.0,
            ("gross_profit", "ebitda"): abs(gp / ebitda) if ebitda != 0 else 1.0,
            ("selling", "ebitda"): abs(financials.get("selling_expenses", 0)) / abs(ebitda) if ebitda != 0 else 0.5,
            ("ga", "ebitda"): abs(financials.get("ga_expenses", financials.get("admin_expenses", 0))) / abs(ebitda) if ebitda != 0 else 0.5,
            ("ebitda", "net_profit"): abs(ebitda / np_) if np_ != 0 else 1.0,
            ("depreciation", "net_profit"): abs(financials.get("depreciation", 0)) / abs(np_) if np_ != 0 else 0.3,
            ("interest", "net_profit"): abs(financials.get("interest_expense", 0)) / abs(np_) if np_ != 0 else 0.2,
            ("other_expenses", "net_profit"): abs(financials.get("other_expenses", 0)) / abs(np_) if np_ != 0 else 0.1,
            ("other_income", "net_profit"): abs(financials.get("other_income", 0)) / abs(np_) if np_ != 0 else 0.1,
            ("net_profit", "health"): 1.0,
        }

        for edge in edges:
            key = (edge["source"], edge["target"])
            elasticity = round(weight_map.get(key, 0.5), 2)
            edge["elasticity"] = elasticity
            edge["tooltip"] = f"1% change in {edge['source']} → ~{elasticity:.1f}% change in {edge['target']}"

    def _estimate_health(self, f: Dict[str, float]) -> float:
        score = 50.0
        rev = f.get("revenue", 0)
        np_ = f.get("net_profit", 0)
        gp = f.get("gross_profit", 0)
        if rev > 0:
            gm = gp / rev * 100
            nm = np_ / rev * 100
            if gm > 30: score += 15
            elif gm > 15: score += 5
            elif gm < 5: score -= 15
            if nm > 5: score += 15
            elif nm > 0: score += 5
            elif nm < -10: score -= 20
        return max(0, min(100, score))


# ── Singleton ──────────────────────────────────────────────────────
causal_graph = CausalGraphGenerator()
