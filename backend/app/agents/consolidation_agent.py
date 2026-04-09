"""
FinAI Consolidation Agent -- Signal > Diagnosis > Action for IFRS 10 group consolidation.
=========================================================================================
Wraps consolidation engine with three intelligence layers:
  Signal (anomaly detection) -> Diagnosis (root cause) -> Action (ranked remediation)
Plus impact ranking, CFO-level LLM narrative, and audit-readiness scoring.

Architecture:
  Supervisor -> ConsolidationAgent.execute(task) -> consolidation_engine.consolidate()
             -> signal/diagnosis/action layers -> LLM narrative
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent, AgentTask, AgentContext, AgentResult
from app.agents.registry import registry

logger = logging.getLogger(__name__)

CONSOLIDATION_TOOLS = [
    "run_consolidation_analysis",
    "get_consolidation_signals",
    "get_consolidation_actions",
]

_SEVERITY_URGENCY = {"critical": 1.0, "warning": 0.6, "info": 0.3}


def _gel(amount: float) -> str:
    return f"\u20be{abs(amount):,.0f}"


# ═══════════════════════ DATA MODELS ═══════════════════════

@dataclass
class ConsolidationSignal:
    signal_id: str = ""
    signal_type: str = ""  # ic_mismatch|nci_leakage|fx_translation|bs_imbalance|revenue_concentration|elimination_gap
    severity: str = "info"  # critical|warning|info
    entity_id: str = ""
    entity_b_id: str = ""
    amount: float = 0.0
    threshold: float = 0.0
    description: str = ""

    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = f"SIG-{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return {k: (round(v, 2) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


@dataclass
class ConsolidationDiagnosis:
    diagnosis_id: str = ""
    signal: Optional[ConsolidationSignal] = None
    root_cause: str = ""
    causal_chain: str = ""
    impact_amount: float = 0.0
    impact_pct: float = 0.0
    contagion_risk: float = 0.0
    ifrs_reference: str = ""
    urgency: float = 0.0

    def __post_init__(self):
        if not self.diagnosis_id:
            self.diagnosis_id = f"DX-{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "signal_id": self.signal.signal_id if self.signal else "",
            "signal_type": self.signal.signal_type if self.signal else "",
            "root_cause": self.root_cause, "causal_chain": self.causal_chain,
            "impact_amount": round(self.impact_amount, 2),
            "impact_pct": round(self.impact_pct, 4),
            "contagion_risk": round(self.contagion_risk, 2),
            "ifrs_reference": self.ifrs_reference,
            "urgency": round(self.urgency, 2),
        }


@dataclass
class ConsolidationAction:
    action_id: str = ""
    diagnosis_id: str = ""
    action_type: str = ""  # investigate|reconcile|implement|policy_change|restructure
    timeframe: str = ""    # immediate|short_term|strategic
    description: str = ""
    expected_impact: str = ""
    priority: int = 0
    assignee_role: str = ""  # CFO|Controller|Treasury|Internal Audit

    def __post_init__(self):
        if not self.action_id:
            self.action_id = f"ACT-{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class ConsolidationAnalysis:
    period: str = ""
    timestamp: str = ""
    raw_result: Dict[str, Any] = field(default_factory=dict)
    signals: List[ConsolidationSignal] = field(default_factory=list)
    diagnoses: List[ConsolidationDiagnosis] = field(default_factory=list)
    actions: List[ConsolidationAction] = field(default_factory=list)
    impact_ranking: List[Dict[str, Any]] = field(default_factory=list)
    cfo_narrative: str = ""
    audit_readiness: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period, "timestamp": self.timestamp,
            "raw_result": self.raw_result,
            "signals": [s.to_dict() for s in self.signals],
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "actions": [a.to_dict() for a in self.actions],
            "impact_ranking": self.impact_ranking,
            "cfo_narrative": self.cfo_narrative,
            "audit_readiness": self.audit_readiness,
            "metadata": self.metadata,
        }


# ═══════════════════════ SIGNAL DETECTION ═══════════════════════

def _detect_signals(result: Dict[str, Any]) -> List[ConsolidationSignal]:
    """Analyse ConsolidatedResult dict and return detected signals."""
    signals: List[ConsolidationSignal] = []
    recon = result.get("reconciliation", {})
    pnl = result.get("consolidated_pnl", {})
    bs = result.get("consolidated_bs", {})
    individual = result.get("individual_statements", {})

    # 1. IC Mismatch
    for item in recon.get("unmatched_items", []):
        diff = item.get("difference", 0)
        if abs(diff) < 0.01:
            continue
        sev = "critical" if abs(diff) > 100_000 else ("warning" if abs(diff) > 10_000 else "info")
        signals.append(ConsolidationSignal(
            signal_type="ic_mismatch", severity=sev,
            entity_id=item.get("entity_a", ""), entity_b_id=item.get("entity_b", ""),
            amount=diff, threshold=0.0,
            description=f"IC {item.get('type', 'unknown')} between "
                        f"{item.get('entity_a', '?')} and {item.get('entity_b', '?')}: "
                        f"difference of {_gel(diff)}",
        ))

    # 2. NCI Leakage
    for eid, nci_amount in result.get("minority_interest", {}).items():
        sub_rev = individual.get(eid, {}).get("revenue", 0)
        if sub_rev == 0:
            continue
        ratio = abs(nci_amount) / abs(sub_rev)
        if ratio > 0.30:
            signals.append(ConsolidationSignal(
                signal_type="nci_leakage", severity="warning", entity_id=eid,
                amount=nci_amount, threshold=sub_rev * 0.30,
                description=f"NCI for {eid} is {_gel(nci_amount)} ({ratio:.0%} of subsidiary "
                            f"revenue {_gel(sub_rev)}), exceeding 30% threshold",
            ))

    # 3. FX Translation
    total_equity = bs.get("total_equity", 0)
    for eid, adj in result.get("translation_adjustments", {}).items():
        reserve = adj.get("translation_reserve", 0)
        if total_equity == 0:
            continue
        pct = abs(reserve) / abs(total_equity)
        if pct > 0.02:
            signals.append(ConsolidationSignal(
                signal_type="fx_translation",
                severity="critical" if pct > 0.05 else "warning",
                entity_id=eid, amount=reserve, threshold=total_equity * 0.02,
                description=f"FX translation for {eid}: {_gel(reserve)} ({pct:.1%} of group "
                            f"equity {_gel(total_equity)}), exceeds 2% materiality",
            ))

    # 4. BS Imbalance
    bs_check = recon.get("bs_equation_check", {})
    if bs_check and not bs_check.get("balanced", True):
        ta, tl, te = bs_check.get("total_assets", 0), bs_check.get("total_liabilities", 0), bs_check.get("total_equity", 0)
        gap = abs(ta - tl - te)
        signals.append(ConsolidationSignal(
            signal_type="bs_imbalance", severity="critical", entity_id="GROUP",
            amount=gap, threshold=1.0,
            description=f"BS equation fails: Assets {_gel(ta)} != Liabilities {_gel(tl)} "
                        f"+ Equity {_gel(te)} (gap {_gel(gap)})",
        ))

    # 5. Revenue Concentration
    group_rev = pnl.get("revenue", 0)
    if group_rev > 0:
        for eid, fin in individual.items():
            ent_rev = fin.get("revenue", 0)
            conc = ent_rev / group_rev
            if conc > 0.70:
                signals.append(ConsolidationSignal(
                    signal_type="revenue_concentration", severity="warning", entity_id=eid,
                    amount=ent_rev, threshold=group_rev * 0.70,
                    description=f"{eid} contributes {conc:.0%} of group revenue "
                                f"({_gel(ent_rev)} / {_gel(group_rev)}), exceeds 70% threshold",
                ))

    # 6. Elimination Gap
    elim_s = recon.get("elimination_summary", {})
    total_elim = elim_s.get("ic_revenue_cogs_eliminated", 0) + elim_s.get("ic_dividends_eliminated", 0)
    sum_indiv_rev = recon.get("revenue_proof", {}).get("sum_individual", 0)
    if sum_indiv_rev > 0:
        elim_pct = total_elim / sum_indiv_rev
        if elim_pct > 0.15:
            signals.append(ConsolidationSignal(
                signal_type="elimination_gap",
                severity="critical" if elim_pct > 0.30 else "warning",
                entity_id="GROUP", amount=total_elim, threshold=sum_indiv_rev * 0.15,
                description=f"IC eliminations {_gel(total_elim)} = {elim_pct:.0%} of gross "
                            f"revenue {_gel(sum_indiv_rev)}, exceeds 15% threshold",
            ))

    return signals


# ═══════════════════════ DIAGNOSIS ═══════════════════════

_DX = {
    "ic_mismatch": ("IC transaction timing or recording difference between entities",
                    "Entity A recorded IC sale in different sub-period/amount than Entity B",
                    "IFRS 10.B86 - Intragroup balances shall be eliminated in full", 0.6),
    "nci_leakage": ("Subsidiary performance disproportionately allocated to minority shareholders",
                    "Low parent ownership + high subsidiary income causes material NCI allocation",
                    "IFRS 10.B94 - NCI allocated their share of profit or loss", 0.4),
    "fx_translation": ("Significant currency movement between subsidiary and group currency",
                       "FX rate volatility caused translation adjustments impacting group equity via OCI",
                       "IAS 21.39 - Exchange differences on translation recognised in OCI", 0.7),
    "bs_imbalance": ("Consolidation adjustments introduced a balance sheet imbalance",
                     "Elimination/NCI/translation entries affected only one side of the BS",
                     "IAS 1.10(a) - Balanced financial position required", 1.0),
    "revenue_concentration": ("Group revenue dominated by a single entity",
                              "One subsidiary generates vast majority of external sales, creating concentration risk",
                              "IFRS 8 - Operating segment disclosures; concentration risk", 0.5),
    "elimination_gap": ("Large proportion of group transactions are intercompany",
                        "Extensive intragroup trading inflates gross revenue, indicating TP complexity",
                        "IFRS 10.B86 - All intragroup items shall be eliminated in full", 0.5),
}


def _generate_diagnoses(signals: List[ConsolidationSignal], group_assets: float) -> List[ConsolidationDiagnosis]:
    diagnoses: List[ConsolidationDiagnosis] = []
    for sig in signals:
        root, chain, ifrs, contagion = _DX.get(sig.signal_type, ("Unknown", "Requires investigation", "", 0.3))
        impact_pct = abs(sig.amount) / abs(group_assets) if group_assets else 0.0
        diagnoses.append(ConsolidationDiagnosis(
            signal=sig, root_cause=root, causal_chain=chain,
            impact_amount=abs(sig.amount), impact_pct=impact_pct,
            contagion_risk=contagion, ifrs_reference=ifrs,
            urgency=_SEVERITY_URGENCY.get(sig.severity, 0.3),
        ))
    return diagnoses


# ═══════════════════════ ACTION GENERATION ═══════════════════════

_AT = {
    "ic_mismatch": [
        ("immediate", "investigate", "Investigate IC mismatch between {a} and {b} for {amt} difference",
         "Resolve reconciliation gap and ensure elimination completeness", "Controller"),
        ("short_term", "reconcile", "Implement automated IC reconciliation with daily matching before period close",
         "Prevent IC mismatches at source; reduce consolidation cycle time", "Controller"),
        ("strategic", "policy_change", "Standardise IC pricing policy and settlement terms across all subsidiaries",
         "Eliminate structural causes of IC differences", "CFO"),
    ],
    "nci_leakage": [
        ("immediate", "investigate", "Review NCI allocation for {a}: {amt} to minority shareholders",
         "Confirm NCI calculation accuracy per IFRS 10.B94", "Controller"),
        ("short_term", "restructure", "Assess increasing ownership in {a} to improve parent return",
         "Reduce NCI leakage and increase parent-attributable profit", "CFO"),
    ],
    "fx_translation": [
        ("immediate", "investigate", "Review translation adjustment for {a}: {amt} equity impact",
         "Validate IAS 21 application and rate sources", "Treasury"),
        ("short_term", "implement", "Implement natural hedging or FX forwards for {a} exposures",
         "Reduce translation volatility in consolidated equity", "Treasury"),
        ("strategic", "policy_change", "Establish group FX risk management policy with defined hedge ratios",
         "Systematic FX translation risk reduction across foreign subsidiaries", "CFO"),
    ],
    "bs_imbalance": [
        ("immediate", "investigate", "Trace BS imbalance of {amt} through elimination and NCI workpapers",
         "Identify specific entry causing the imbalance", "Controller"),
        ("immediate", "reconcile", "Post correcting journal entry to restore BS equation balance",
         "Achieve balanced consolidated balance sheet for reporting", "Controller"),
    ],
    "revenue_concentration": [
        ("short_term", "investigate", "Prepare IFRS 8 segment disclosure noting {a} revenue concentration",
         "Ensure operating segment disclosure compliance", "Controller"),
        ("strategic", "restructure", "Diversify revenue across group entities to reduce concentration risk",
         "Lower operational risk and improve group resilience", "CFO"),
    ],
    "elimination_gap": [
        ("immediate", "investigate", "Review IC volume ({amt} eliminated) for transfer-pricing compliance",
         "Confirm arm's-length pricing and tax compliance", "Internal Audit"),
        ("strategic", "restructure", "Simplify group structure to reduce IC transaction volume",
         "Lower consolidation complexity and transfer-pricing risk", "CFO"),
    ],
}


def _generate_actions(diagnoses: List[ConsolidationDiagnosis]) -> List[ConsolidationAction]:
    actions: List[ConsolidationAction] = []
    pri = 0
    for dx in diagnoses:
        sig = dx.signal
        if sig is None:
            continue
        for tf, at, desc_t, impact, role in _AT.get(sig.signal_type, []):
            pri += 1
            desc = desc_t.format(a=sig.entity_id, b=sig.entity_b_id or "GROUP", amt=_gel(sig.amount))
            actions.append(ConsolidationAction(
                diagnosis_id=dx.diagnosis_id, action_type=at, timeframe=tf,
                description=desc, expected_impact=impact, priority=pri, assignee_role=role,
            ))
    return actions


# ═══════════════════════ IMPACT RANKING ═══════════════════════

def _rank_by_impact(diagnoses: List[ConsolidationDiagnosis], group_assets: float) -> List[Dict[str, Any]]:
    """composite = 0.40*fin_norm + 0.25*urgency + 0.20*contagion + 0.15*audit_risk"""
    ranked = []
    for dx in diagnoses:
        fin_norm = min(dx.impact_amount / abs(group_assets), 1.0) if group_assets else 0.0
        audit_risk = 1.0 if dx.urgency >= 1.0 else (0.5 if dx.urgency >= 0.6 else 0.0)
        composite = round(0.40 * fin_norm + 0.25 * dx.urgency + 0.20 * dx.contagion_risk + 0.15 * audit_risk, 4)
        ranked.append({
            "diagnosis_id": dx.diagnosis_id,
            "signal_type": dx.signal.signal_type if dx.signal else "",
            "entity_id": dx.signal.entity_id if dx.signal else "",
            "severity": dx.signal.severity if dx.signal else "",
            "impact_amount": round(dx.impact_amount, 2),
            "impact_pct": round(dx.impact_pct, 4),
            "financial_impact_norm": round(fin_norm, 4),
            "urgency": dx.urgency, "contagion_risk": dx.contagion_risk,
            "audit_risk": audit_risk, "composite_score": composite,
        })
    ranked.sort(key=lambda r: r["composite_score"], reverse=True)
    for i, e in enumerate(ranked):
        e["rank"] = i + 1
    return ranked


# ═══════════════════════ AUDIT READINESS ═══════════════════════

def _assess_audit_readiness(signals: List[ConsolidationSignal], recon: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    ded = 0.0
    crit = sum(1 for s in signals if s.severity == "critical")
    warn = sum(1 for s in signals if s.severity == "warning")
    if crit:
        ded += 0.25 * crit
        issues.append(f"{crit} critical signal(s) require immediate resolution")
    if warn:
        ded += 0.10 * warn
        issues.append(f"{warn} warning signal(s) require review")
    if not recon.get("bs_equation_check", {}).get("balanced", True):
        ded += 0.30; issues.append("Balance sheet equation does not hold")
    if not recon.get("revenue_proof", {}).get("matches", True):
        ded += 0.15; issues.append("Revenue reconciliation proof does not match")
    if not recon.get("assets_proof", {}).get("matches", True):
        ded += 0.15; issues.append("Assets reconciliation proof does not match")
    um = recon.get("unmatched_items", [])
    if um:
        ded += 0.05 * len(um); issues.append(f"{len(um)} unmatched IC item(s)")
    score = max(0.0, round(1.0 - ded, 2))
    return {"ready": score >= 0.70 and crit == 0, "score": score, "issues": issues,
            "critical_count": crit, "warning_count": warn}


# ═══════════════════════ AGENT ═══════════════════════

class ConsolidationAgent(BaseAgent):
    """Multi-entity consolidation with Signal > Diagnosis > Action intelligence.

    Resilience: template fallback on LLM failure, health tracking via safe_execute(),
    graceful degradation (analysis runs even if narrative fails).
    """

    name = "consolidation"
    description = "Multi-entity consolidation intelligence -- signals, diagnosis, actions"
    capabilities = ["consolidation", "group_reporting", "ic_elimination"]
    tools = []

    def can_handle(self, task: AgentTask) -> bool:
        return (task.task_type in self.capabilities
                or task.parameters.get("tool_name") in CONSOLIDATION_TOOLS)

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        tool_name = task.parameters.get("tool_name", "run_consolidation_analysis")
        tool_params = task.parameters.get("tool_params", {})
        try:
            if tool_name == "run_consolidation_analysis":
                return await self._handle_full_analysis(tool_params, context)
            elif tool_name == "get_consolidation_signals":
                return await self._handle_signals_only(tool_params, context)
            elif tool_name == "get_consolidation_actions":
                return await self._handle_actions_only(tool_params, context)
            return self._error_result(f"Unknown consolidation tool: {tool_name}")
        except Exception as e:
            logger.error("ConsolidationAgent error on %s: %s", tool_name, e, exc_info=True)
            return self._error_result(str(e))

    # ── Main pipeline ───────────────────────────────────────────────

    async def run_consolidation_analysis(
        self, period: str, entities: Optional[List[Dict[str, Any]]] = None,
    ) -> ConsolidationAnalysis:
        """Full Signal > Diagnosis > Action pipeline for group consolidation."""
        t0 = time.time()
        from app.services.consolidation import consolidation_engine, Entity

        if entities:
            for ed in entities:
                consolidation_engine.register_entity(Entity(
                    entity_id=ed.get("entity_id", ed.get("id", "")),
                    name=ed.get("name", ""),
                    parent_entity_id=ed.get("parent_entity_id"),
                    ownership_pct=ed.get("ownership_pct", 100.0),
                    currency=ed.get("currency", "GEL"),
                    is_parent=ed.get("is_parent", False),
                    industry=ed.get("industry", "fuel_distribution"),
                ))

        raw = consolidation_engine.consolidate(period)
        raw_dict = raw.to_dict()
        group_assets = raw.consolidated_bs.get("total_assets", 0)

        signals = _detect_signals(raw_dict)
        diagnoses = _generate_diagnoses(signals, group_assets)
        actions = _generate_actions(diagnoses)
        ranking = _rank_by_impact(diagnoses, group_assets)
        audit = _assess_audit_readiness(signals, raw_dict.get("reconciliation", {}))
        narrative = await self._generate_cfo_narrative(raw_dict, signals, diagnoses, actions, ranking)

        crit = sum(1 for s in signals if s.severity == "critical")
        elapsed = int((time.time() - t0) * 1000)

        analysis = ConsolidationAnalysis(
            period=period, timestamp=datetime.now(timezone.utc).isoformat(),
            raw_result=raw_dict, signals=signals, diagnoses=diagnoses,
            actions=actions, impact_ranking=ranking, cfo_narrative=narrative,
            audit_readiness=audit,
            metadata={
                "entity_count": raw_dict.get("reconciliation", {}).get("entity_count", 0),
                "elimination_count": len(raw.eliminations),
                "signal_count": len(signals), "critical_count": crit,
                "warning_count": sum(1 for s in signals if s.severity == "warning"),
                "action_count": len(actions), "processing_time_ms": elapsed,
            },
        )
        logger.info("Consolidation analysis: period=%s signals=%d critical=%d actions=%d %dms",
                     period, len(signals), crit, len(actions), elapsed)
        return analysis

    # ── Execute handlers ────────────────────────────────────────────

    async def _handle_full_analysis(self, params: Dict, ctx: AgentContext) -> AgentResult:
        period = params.get("period", ctx.period or "2024-01")
        analysis = await self.run_consolidation_analysis(period, params.get("entities"))
        return AgentResult(agent_name=self.name, status="success",
                           data=analysis.to_dict(), narrative=analysis.cfo_narrative)

    async def _handle_signals_only(self, params: Dict, ctx: AgentContext) -> AgentResult:
        from app.services.consolidation import consolidation_engine
        last = consolidation_engine.get_last_result()
        if last is None:
            last = consolidation_engine.consolidate(params.get("period", ctx.period or "2024-01"))
        signals = _detect_signals(last.to_dict())
        crit = sum(1 for s in signals if s.severity == "critical")
        return AgentResult(
            agent_name=self.name, status="success",
            data={"signals": [s.to_dict() for s in signals]},
            narrative=f"Detected {len(signals)} signals ({crit} critical).",
        )

    async def _handle_actions_only(self, params: Dict, ctx: AgentContext) -> AgentResult:
        from app.services.consolidation import consolidation_engine
        last = consolidation_engine.get_last_result()
        if last is None:
            last = consolidation_engine.consolidate(params.get("period", ctx.period or "2024-01"))
        raw_dict = last.to_dict()
        signals = _detect_signals(raw_dict)
        group_assets = last.consolidated_bs.get("total_assets", 0)
        diagnoses = _generate_diagnoses(signals, group_assets)
        actions = _generate_actions(diagnoses)
        return AgentResult(
            agent_name=self.name, status="success",
            data={"actions": [a.to_dict() for a in actions]},
            narrative=f"Generated {len(actions)} actions across {len(diagnoses)} diagnoses.",
        )

    # ── CFO Narrative ───────────────────────────────────────────────

    async def _generate_cfo_narrative(
        self, result: Dict, signals: List[ConsolidationSignal],
        diagnoses: List[ConsolidationDiagnosis],
        actions: List[ConsolidationAction],
        ranking: List[Dict[str, Any]],
    ) -> str:
        pnl = result.get("consolidated_pnl", {})
        recon = result.get("reconciliation", {})
        revenue = pnl.get("revenue", 0)
        entity_count = recon.get("entity_count", 0)
        es = recon.get("elimination_summary", {})
        elim_total = es.get("ic_revenue_cogs_eliminated", 0) + es.get("ic_balances_eliminated", 0) + es.get("ic_dividends_eliminated", 0)
        nci_total = sum(result.get("minority_interest", {}).values())
        crit = sum(1 for s in signals if s.severity == "critical")

        top_lines = []
        for e in ranking[:3]:
            top_lines.append(f"  - [{e['severity'].upper()}] {e['signal_type']} "
                             f"(entity: {e['entity_id']}, impact: {_gel(e['impact_amount'])}, "
                             f"score: {e['composite_score']:.3f})")
        top_text = "\n".join(top_lines) or "  (no findings)"

        system = ("You are the CFO of a multi-entity energy group. Speak precisely and "
                  "quantitatively. Use \u20be for currency. Respond in numbered sections.")
        user_msg = (
            f"Analyse consolidation for {result.get('period', 'N/A')}:\n"
            f"- Group Revenue: \u20be{revenue:,.0f}\n"
            f"- Entities: {entity_count}\n"
            f"- IC Eliminations: \u20be{elim_total:,.0f}\n"
            f"- NCI Share: \u20be{nci_total:,.0f}\n"
            f"- {len(signals)} signals, {crit} critical\n\n"
            f"Top findings:\n{top_text}\n\n"
            f"Provide:\n"
            f"1. Executive Summary (2-3 sentences)\n"
            f"2. Key Risk: single biggest risk\n"
            f"3. Required Action: what CFO must do THIS WEEK\n"
            f"4. Audit Readiness: Yes/No + reason"
        )

        try:
            resp = await self.call_llm(
                system=system, messages=[{"role": "user", "content": user_msg}],
                max_tokens=1024, temperature=0.1,
                tool_name_hint="consolidation_cfo_narrative",
            )
            if hasattr(resp, "content") and resp.content:
                return resp.content[0].text
        except Exception as e:
            logger.warning("LLM narrative failed: %s", e)

        # Fallback
        audit = _assess_audit_readiness(signals, recon)
        return (f"Consolidation analysis complete. {len(signals)} signals detected "
                f"({crit} critical). Audit readiness: {audit['score']:.0%}.")


# ═══════════════════════ SINGLETON ═══════════════════════

consolidation_agent = ConsolidationAgent()
registry.register(consolidation_agent)
