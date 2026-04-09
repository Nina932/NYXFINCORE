"""
LLM Reasoning Chain — 4-Tier Fallback
========================================
Production-grade LLM integration for CFO-level financial reasoning.

Chain (tries in order, falls back on failure):
1. Claude Opus 4.6 (Anthropic) — deepest reasoning, best CFO insights
2. Grok 4.1 Fast (xAI) — fast, low hallucination, tool-use capable
3. Mistral Large (Mistral AI) — cost-effective backup
4. Ollama Local (llama3.2:3b / mistral:7b) — offline fallback, zero cost
5. Template (deterministic) — always works, no LLM needed

STRICT RULES:
- LLMs NEVER generate financial numbers
- LLMs ONLY explain, reason, and generate insights
- All numbers come from deterministic computation
- If ALL LLMs fail, template fallback provides structured response
"""

import httpx
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# CORRECT MODEL NAMES (verified March 2026)
# ═══════════════════════════════════════════════════════════════════

MODELS = {
    "claude": {
        "name": "Claude Sonnet 4",
        "model_id": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        "api_url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "max_tokens": 4096,
    },
    "grok": {
        "name": "Grok 4.1 Fast",
        "model_id": "grok-4-1-fast-non-reasoning",
        "api_url": "https://api.x.ai/v1/chat/completions",
        "api_key_env": "XAI_GROK_API_KEY",
        "max_tokens": 4096,
    },
    "mistral": {
        "name": "Mistral Large",
        "model_id": "mistral-large-latest",
        "api_url": "https://api.mistral.ai/v1/chat/completions",
        "api_key_env": "MISTRAL_API_KEY",
        "max_tokens": 4096,
    },
    "ollama": {
        "name": "Qwen 2.5 3B (Local)",
        "model_id": "qwen2.5:3b",
        "api_url": "http://localhost:11434/api/chat",
        "api_key_env": None,
        "max_tokens": 4096,
    },
}

# System prompt for ALL LLMs
from app.services.accounting_knowledge import get_knowledge_for_context as _get_knowledge

CFO_SYSTEM_PROMPT = """You are a world-class CFO, Big4 senior audit partner, and financial analyst combined.
You have deep expertise in Georgian 1C accounting, IFRS standards, and fuel distribution industry.

""" + _get_knowledge(max_chars=30000) + """

STRICT RULES:
- NEVER generate, estimate, or modify financial numbers. All numbers are pre-computed and given to you.
- ONLY explain, reason, generate insights, and provide strategic guidance.
- Always state uncertainty when data is incomplete.
- Use precise financial language (EBITDA, leverage, coverage, etc.)
- Be concise but thorough. No filler text.
- When you don't know something, say "insufficient data" — never guess.

OUTPUT FORMAT (JSON):
{
  "summary": "2-3 sentence executive summary",
  "insights": [
    {"severity": "critical|warning|info|positive", "title": "...", "explanation": "...", "impact": "...", "action": "..."}
  ],
  "strategy_recommendations": ["..."],
  "risk_assessment": "...",
  "confidence": 0.0-1.0
}"""


# ═══════════════════════════════════════════════════════════════════
# LLM CHAIN
# ═══════════════════════════════════════════════════════════════════

class LLMReasoningChain:
    """
    4-tier LLM chain for CFO-level financial reasoning.
    Tries each LLM in order, falls back on failure.
    """

    def __init__(self):
        self._last_model_used = "none"
        self._available_models = self._detect_available()

    def _detect_available(self) -> List[str]:
        """Detect which LLMs have API keys configured."""
        # Load keys from settings (which reads .env) if not in os.environ
        try:
            from app.config import settings
            if settings.ANTHROPIC_API_KEY and not os.getenv("ANTHROPIC_API_KEY"):
                os.environ["ANTHROPIC_API_KEY"] = str(settings.ANTHROPIC_API_KEY)
        except Exception:
            pass

        available = []
        for key, config in MODELS.items():
            if key == "ollama":
                available.append(key)  # Always try Ollama
            elif config["api_key_env"] and os.getenv(config["api_key_env"]):
                available.append(key)
        logger.info("LLM chain available: %s", available)
        return available

    @property
    def last_model_used(self) -> str:
        return self._last_model_used

    async def reason(self, financial_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run CFO reasoning on financial context through the LLM chain.

        Args:
            financial_context: Pre-computed financial data (numbers are final, LLM only explains)

        Returns:
            Dict with summary, insights, strategy, risk assessment
        """
        user_prompt = self._build_prompt(financial_context)

        # Try each LLM in chain order
        for model_key in ["claude", "grok", "mistral", "ollama"]:
            if model_key not in self._available_models and model_key != "ollama":
                continue

            try:
                result = await self._call_model(model_key, user_prompt)
                if result:
                    self._last_model_used = MODELS[model_key]["name"]
                    logger.info("LLM chain: %s succeeded", model_key)
                    return result
            except Exception as e:
                logger.warning("LLM chain: %s failed (%s), trying next", model_key, str(e)[:100])
                continue

        # Tier 5: Template fallback (always works)
        self._last_model_used = "Template (deterministic)"
        logger.info("LLM chain: all models failed, using template fallback")
        return self._template_fallback(financial_context)

    def _build_prompt(self, ctx: Dict) -> str:
        """Build a structured prompt from financial context."""
        lines = ["Analyze the following financial data and provide CFO-level insights:", ""]

        # Company info
        company = ctx.get("company", "Unknown Company")
        period = ctx.get("period", "Unknown Period")
        data_type = ctx.get("data_type", "unknown")
        lines.append(f"Company: {company}")
        lines.append(f"Period: {period}")
        lines.append(f"Data Type: {data_type}")
        lines.append("")

        # P&L data (if available)
        pnl = ctx.get("pnl", {})
        if pnl:
            lines.append("P&L Statement:")
            for key in ["revenue", "cogs", "gross_profit", "gross_margin_pct", "total_opex",
                         "selling_expenses", "admin_expenses", "ebitda", "net_profit", "net_margin_pct"]:
                val = pnl.get(key)
                if val is not None:
                    if isinstance(val, float) and abs(val) > 1000:
                        lines.append(f"  {key}: {val:,.0f} GEL")
                    elif isinstance(val, float):
                        lines.append(f"  {key}: {val:.1f}%")
                    else:
                        lines.append(f"  {key}: {val}")
                else:
                    lines.append(f"  {key}: NOT AVAILABLE")

        # Balance sheet (if available)
        bs = ctx.get("balance_sheet", {})
        if bs:
            lines.append("\nBalance Sheet:")
            for key in ["total_assets", "total_liabilities", "total_equity", "cash",
                         "long_term_debt", "total_current_liabilities"]:
                val = bs.get(key)
                if val is not None:
                    lines.append(f"  {key}: {val:,.0f} GEL")

        # Company character
        char = ctx.get("company_character", {})
        if char:
            lines.append(f"\nCompany Profile: {char.get('industry', '?')} ({char.get('business_model', '?')})")
            lines.append(f"  Leverage: {char.get('leverage_level', '?')}")
            lines.append(f"  Asset Intensity: {char.get('asset_intensity', '?')}")
            lines.append(f"  Risk: {char.get('risk_profile', '?')}")

        # Expense breakdown
        exp = ctx.get("expense_breakdown", {})
        if exp:
            lines.append("\nExpense Categories:")
            for cat, amt in sorted(exp.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"  {cat}: {amt:,.0f} GEL")

        # Insights already detected (from reconstruction engine)
        insights = ctx.get("insights", [])
        if insights:
            lines.append(f"\nPre-detected signals ({len(insights)}):")
            for i in insights[:5]:
                lines.append(f"  [{i.get('severity', '?').upper()}] {i.get('title', '?')}")

        # Missing data
        missing = ctx.get("missing_data", [])
        if missing:
            lines.append(f"\nMissing data: {', '.join(missing)}")

        lines.append("\nProvide your analysis as JSON matching the specified schema.")
        return "\n".join(lines)

    async def _call_model(self, model_key: str, prompt: str) -> Optional[Dict]:
        """Call a specific LLM model."""
        config = MODELS[model_key]
        api_key = os.getenv(config["api_key_env"]) if config["api_key_env"] else None

        if model_key != "ollama" and not api_key:
            return None

        timeout = httpx.Timeout(60.0, connect=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            if model_key == "claude":
                response = await client.post(
                    config["api_url"],
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": config["model_id"],
                        "max_tokens": config["max_tokens"],
                        "system": CFO_SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = response.json()
                text = data.get("content", [{}])[0].get("text", "")

            elif model_key == "ollama":
                response = await client.post(
                    config["api_url"],
                    json={
                        "model": config["model_id"],
                        "messages": [
                            {"role": "system", "content": CFO_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                    },
                )
                data = response.json()
                text = data.get("message", {}).get("content", "")

            else:  # OpenAI-compatible (Grok, Mistral)
                response = await client.post(
                    config["api_url"],
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config["model_id"],
                        "messages": [
                            {"role": "system", "content": CFO_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": config["max_tokens"],
                        "temperature": 0.3,
                    },
                )
                data = response.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not text:
                return None

            # Parse JSON from LLM response
            return self._parse_llm_response(text)

    def _parse_llm_response(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        # Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in text
        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        # Return as plain text insight
        return {
            "summary": text[:500],
            "insights": [],
            "strategy_recommendations": [],
            "risk_assessment": "",
            "confidence": 0.5,
        }

    def _template_fallback(self, ctx: Dict) -> Dict:
        """Deterministic template when all LLMs are unavailable."""
        pnl = ctx.get("pnl", {})
        char = ctx.get("company_character", {})
        data_type = ctx.get("data_type", "unknown")
        insights_from_engine = ctx.get("insights", [])

        summary_parts = []
        if data_type == "expenses_only":
            summary_parts.append("Partial financial data analyzed — expenses only.")
            summary_parts.append("Revenue and COGS are not available. Profitability cannot be assessed.")
        elif data_type in ("full_pl", "basic_pl"):
            rev = pnl.get("revenue", 0)
            margin = pnl.get("gross_margin_pct", 0)
            summary_parts.append(f"Revenue {rev:,.0f} GEL with {margin:.1f}% gross margin.")
            if margin < 10:
                summary_parts.append("Margins are critically thin — review pricing immediately.")
            elif margin < 20:
                summary_parts.append("Margins below industry average — optimization opportunities exist.")

        if char.get("leverage_level") in ("high", "critical"):
            summary_parts.append(f"Leverage is {char['leverage_level']} — debt service is a significant burden.")

        if char.get("industry", "unknown") != "unknown":
            summary_parts.append(f"Company profile: {char['industry'].replace('_', ' ').title()}.")

        return {
            "summary": " ".join(summary_parts) if summary_parts else "Financial data received. Analysis available.",
            "insights": [i if isinstance(i, dict) else i.to_dict() if hasattr(i, 'to_dict') else {"title": str(i)} for i in insights_from_engine[:5]],
            "strategy_recommendations": [
                "Review and optimize cost structure",
                "Assess debt refinancing opportunities",
                "Upload complete financial data for full analysis",
            ],
            "risk_assessment": f"Data completeness: {data_type}. " +
                              (f"Leverage: {char.get('leverage_level', 'unknown')}. " if char else "") +
                              (f"Asset intensity: {char.get('asset_intensity', 'unknown')}." if char else ""),
            "confidence": 0.70,
            "model_used": "Template (deterministic)",
        }

    def get_status(self) -> Dict[str, Any]:
        """Return LLM chain status for frontend display."""
        status = {
            "chain": [],
            "last_used": self._last_model_used,
            "available_count": len(self._available_models),
        }
        for key, config in MODELS.items():
            has_key = key == "ollama" or bool(os.getenv(config.get("api_key_env", "") or ""))
            status["chain"].append({
                "name": config["name"],
                "model_id": config["model_id"],
                "available": has_key,
                "position": list(MODELS.keys()).index(key) + 1,
            })
        # Template fallback always available
        status["chain"].append({
            "name": "Template (deterministic)",
            "model_id": "template",
            "available": True,
            "position": 5,
        })
        return status


    def reason_sync(self, financial_context: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for reason() — for use in non-async contexts."""
        import asyncio
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're inside a running async event loop — use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    # Create a fresh coroutine in the thread context via lambda
                    future = pool.submit(lambda: asyncio.run(self.reason(financial_context)))
                    return future.result(timeout=60)
            else:
                # No running loop — safe to use asyncio.run()
                return asyncio.run(self.reason(financial_context))
        except Exception as e:
            logger.warning("reason_sync failed: %s", e)
            return {"summary": "LLM reasoning unavailable", "insights": [], "model_used": "none"}


# Module-level singleton
llm_chain = LLMReasoningChain()
