"""
Multi-Agent Debate Engine
=========================
Three-agent debate system (Proposer → Critic → Resolver) that uses
the existing local_llm.chat() interface to produce higher-quality
financial recommendations through adversarial reasoning.

This does NOT require LangGraph — it's a simple sequential pipeline
that calls the LLM three times with different system prompts.
The output is a structured decision that's better than a single-pass answer.
"""

import json
import time
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class DebateRound:
    role: str       # proposer | critic | resolver
    content: str
    timestamp: str


@dataclass
class DebateResult:
    proposal: str
    critique: str
    resolution: str
    final_action: Dict[str, Any]
    confidence_score: int
    rounds: List[DebateRound]
    trace_id: str
    execution_time_ms: int

    def to_dict(self) -> Dict:
        return {
            "proposal": self.proposal,
            "critique": self.critique,
            "resolution": self.resolution,
            "final_action": self.final_action,
            "confidence_score": self.confidence_score,
            "rounds": [asdict(r) for r in self.rounds],
            "trace_id": self.trace_id,
            "execution_time_ms": self.execution_time_ms,
        }


# ─── Agent System Prompts ───

PROPOSER_SYSTEM = """You are the Proposer Agent — a senior hedge-fund strategist with 20 years experience.
Given the financial data, propose the SINGLE BEST high-conviction action the company should take RIGHT NOW.

Be bold, data-driven, and quantitative. Include:
- Specific action (not vague)
- Expected ROI estimate (%)
- Timeline (months)
- Risk level (1-10)
- Why this action and not others

Keep your response under 200 words. Be direct."""

CRITIC_SYSTEM = """You are the Critic Agent — an ex-Big4 forensic accountant and risk quantifier.
Your job is to find EVERY flaw in the proposal. Be ruthless but fair.

Evaluate:
1. Is the ROI estimate realistic? (most proposals overestimate by 2-3x)
2. What accounting/IFRS risks does this create?
3. What tail risks are being ignored?
4. What execution barriers exist?
5. Score the proposal 1-100 and explain why

Keep your response under 200 words. Be specific about what's wrong."""

RESOLVER_SYSTEM = """You are the Resolver Agent — the final CFO-level decision maker.
You've seen both the proposal and the critique. Now synthesize.

Produce a FINAL recommendation that accounts for the critique.
Format as JSON:
{
  "action": "specific action",
  "roi_estimate_pct": number,
  "probability_success": number (0-1),
  "risk_score": number (1-10),
  "deadline_months": number,
  "key_risk": "main risk to watch",
  "confidence": number (1-100)
}

Output ONLY the JSON, nothing else."""


class DebateEngine:
    """
    Runs a three-agent debate using the existing local Ollama LLM.
    Falls back to rule-based output if LLM is unavailable.
    """

    def __init__(self):
        self._llm = None

    def _ensure_llm(self):
        if self._llm is None:
            from app.services.local_llm import local_llm
            self._llm = local_llm

    async def run_debate(
        self,
        financials: Dict[str, float],
        balance_sheet: Optional[Dict[str, float]] = None,
        period: str = "",
        company: str = "",
    ) -> DebateResult:
        """
        Run the full 3-round debate.
        """
        start = time.time()
        self._ensure_llm()
        trace_id = f"debate-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Input validation
        if not financials:
            raise ValueError("financials cannot be empty for debate")
        rev = financials.get("revenue", 0)
        if rev == 0:
            logger.warning("Debate initiated with zero revenue — results may be generic")

        rounds: List[DebateRound] = []
        now = datetime.now(timezone.utc).isoformat()

        # Build the financial context string with company ontology
        from app.services.company_ontology import get_company_context
        ontology = get_company_context(company, period)
        context = self._build_context(financials, balance_sheet, period, company)
        full_context = f"{ontology}\n\n--- CURRENT FINANCIALS ---\n{context}"

        # ── Round 1: Proposer ──
        proposal = await self._call_agent(
            PROPOSER_SYSTEM,
            f"Here is the company profile and financial data:\n{full_context}\n\nPropose the best action.",
            "balanced",
        )
        if not proposal:
            proposal = self._fallback_proposal(financials)
        rounds.append(DebateRound(role="proposer", content=proposal, timestamp=now))

        # ── Round 2: Critic ──
        critique = await self._call_agent(
            CRITIC_SYSTEM,
            f"Company context:\n{ontology}\n\nThe Proposer suggested:\n\n{proposal}\n\nFinancial context:\n{context}\n\nCritique this proposal.",
            "balanced",
        )
        if not critique:
            critique = self._fallback_critique(proposal)
        rounds.append(DebateRound(role="critic", content=critique, timestamp=now))

        # ── Round 3: Resolver ──
        resolution_raw = await self._call_agent(
            RESOLVER_SYSTEM,
            f"Company context:\n{ontology}\n\nProposal:\n{proposal}\n\nCritique:\n{critique}\n\nFinancial context:\n{context}\n\nGive your final recommendation as JSON.",
            "capable",
        )
        if not resolution_raw:
            resolution_raw = json.dumps(self._fallback_resolution(financials))
        rounds.append(DebateRound(role="resolver", content=resolution_raw, timestamp=now))

        # Parse the resolver's JSON
        final_action = self._parse_resolution(resolution_raw, financials)
        confidence = final_action.get("confidence", 50)

        elapsed = int((time.time() - start) * 1000)

        return DebateResult(
            proposal=proposal,
            critique=critique,
            resolution=resolution_raw,
            final_action=final_action,
            confidence_score=confidence,
            rounds=rounds,
            trace_id=trace_id,
            execution_time_ms=elapsed,
        )

    async def _call_agent(self, system: str, user_msg: str, complexity: str, timeout_sec: int = 60) -> Optional[str]:
        """Call the local LLM with the given prompts, with timeout protection."""
        import asyncio
        try:
            result = await asyncio.wait_for(
                self._llm.chat(
                    system=system,
                    messages=[{"role": "user", "content": user_msg}],
                    complexity=complexity,
                    max_tokens=1024,
                ),
                timeout=timeout_sec,
            )
            if result and len(result.strip()) < 10:
                logger.warning("Debate agent returned suspiciously short response (%d chars)", len(result))
            return result
        except asyncio.TimeoutError:
            logger.error("Debate agent timed out after %ds", timeout_sec)
            return None
        except Exception as e:
            logger.error("Debate agent LLM call failed: %s", e)
            return None

    def _build_context(self, fin: Dict, bs: Optional[Dict], period: str, company: str) -> str:
        lines = []
        if company:
            lines.append(f"Company: {company}")
        if period:
            lines.append(f"Period: {period}")

        rev = fin.get("revenue", 0)
        cogs = abs(fin.get("cogs", 0))
        gp = fin.get("gross_profit", rev - cogs)
        np_ = fin.get("net_profit", 0)
        ebitda = fin.get("ebitda", 0)
        gm = fin.get("gross_margin_pct", (gp / rev * 100 if rev else 0))

        lines.append(f"Revenue: {rev:,.0f}")
        lines.append(f"COGS: {cogs:,.0f} ({cogs/rev*100:.1f}% of revenue)" if rev else f"COGS: {cogs:,.0f}")
        lines.append(f"Gross Profit: {gp:,.0f} (margin: {gm:.1f}%)")
        lines.append(f"EBITDA: {ebitda:,.0f}")
        lines.append(f"Net Profit: {np_:,.0f}")

        if bs:
            lines.append(f"Total Assets: {bs.get('total_assets', 0):,.0f}")
            lines.append(f"Total Liabilities: {bs.get('total_liabilities', 0):,.0f}")
            lines.append(f"Total Equity: {bs.get('total_equity', 0):,.0f}")
            if bs.get("total_equity", 0) > 0:
                de = bs.get("total_liabilities", 0) / bs["total_equity"]
                lines.append(f"Debt/Equity: {de:.1f}x")

        return "\n".join(lines)

    # ── Fallbacks (when LLM is unavailable) ──

    def _fallback_proposal(self, fin: Dict) -> str:
        rev = fin.get("revenue", 0)
        cogs = abs(fin.get("cogs", 0))
        ratio = cogs / rev if rev else 0
        if ratio > 0.85:
            return (
                f"PROPOSAL: Renegotiate top 5 supplier contracts to reduce COGS ratio "
                f"from {ratio*100:.1f}% toward 80%. Target: 3-5% COGS reduction in 6 months. "
                f"Expected ROI: 2.5x. Risk: 4/10. This is the highest-leverage action because "
                f"COGS is {ratio*100:.1f}% of revenue — even a 2% improvement saves "
                f"₾{rev*0.02:,.0f} annually."
            )
        return f"PROPOSAL: Focus on revenue growth through pricing optimization. Current margins are healthy."

    def _fallback_critique(self, proposal: str) -> str:
        return (
            "CRITIQUE: Score 60/100. The proposal lacks specifics on which suppliers to target. "
            "Renegotiation assumes suppliers have margin to give — not guaranteed in commodity markets. "
            "Timeline of 6 months is optimistic; typical procurement cycles are 9-12 months. "
            "ROI estimate of 2.5x assumes full savings flow to bottom line, ignoring switching costs. "
            "Tail risk: supplier relationship damage could cause supply disruptions."
        )

    def _fallback_resolution(self, fin: Dict) -> Dict:
        rev = fin.get("revenue", 0)
        return {
            "action": "Initiate competitive bidding for top 3 COGS categories",
            "roi_estimate_pct": 1.8,
            "probability_success": 0.65,
            "risk_score": 5,
            "deadline_months": 9,
            "key_risk": "Supplier relationship disruption",
            "confidence": 55,
        }

    def _parse_resolution(self, raw: str, fin: Dict) -> Dict:
        """Try to extract JSON from the resolver's response with robust parsing."""
        if not raw or not raw.strip():
            logger.warning("Empty resolver response — using fallback")
            return self._fallback_resolution(fin)

        # Try direct JSON parse
        try:
            parsed = json.loads(raw.strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to find JSON block in markdown code fences
        import re
        code_block = re.search(r'```(?:json)?\s*(\{[^`]+\})\s*```', raw, re.DOTALL)
        if code_block:
            try:
                parsed = json.loads(code_block.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Try to find any JSON object in the text
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Last resort: try to extract key-value pairs
        logger.warning("Could not parse resolver JSON — using fallback. Raw: %s", raw[:200])
        return self._fallback_resolution(fin)


# Singleton
debate_engine = DebateEngine()
