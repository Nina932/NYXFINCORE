"""
FinAI Local LLM — Hybrid routing with FinAI Captain intelligence.
=================================================================
Provides a tiered fallback when Claude API is unavailable:

  Tier 1: Check response cache (free, instant)
  Tier 2: Try Gemma 4 31B IT via NVIDIA API (primary, Georgian-capable)
  Tier 3: Try Claude API (cloud, when key available)
  Tier 4: Try NVIDIA Nemotron (cloud, deep reasoning + agentic)
  Tier 5: Try Ollama local model (local, good quality for most tasks)
  Tier 6: Template response library (always available, no AI)

FinAI Captain Hybrid Routing:
  - Gemma 4 31B IT: Primary for all tasks including Georgian (ქართული)
  - Nemotron 3 Super 120B: Deep financial reasoning + agentic orchestration
  - Claude Sonnet 4: Fallback when API key is available
  - Qwen3 (local via Ollama): Fast, free fallback with multilingual support

Model selection by task complexity:
  - "fast" (llama3.2:3b / qwen3:8b): classification, short answers
  - "balanced" (llama3.2:3b / qwen3:14b): reasoning, commentary, analysis
  - "capable" (llama3.2:3b / qwen3:14b): complex reasoning, multi-turn chat

Ollama capability by model:
  llama3.2:3b: column classification, account lookup, simple Q&A
  qwen3:8b-instruct: fast multilingual including Georgian
  qwen3:14b-instruct: P&L narratives, root-cause analysis, multi-turn chat
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Literal, Optional

import os

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)

# Ollama default endpoint
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 60  # seconds — local models can be slow on CPU

# NVIDIA Nemotron API (build.nvidia.com)
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# Google Gemma 4 via NVIDIA API (build.nvidia.com — primary LLM, Georgian-capable)
GEMMA4_MODEL = "google/gemma-4-31b-it"
GEMMA4_TIMEOUT = 60  # seconds — fail fast, let CRA fallback handle slow API

# Anthropic Claude API
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_TIMEOUT = 15  # seconds — fail fast so fallback kicks in quickly

# Google Gemini API (free tier: 15 RPM, 1000/day, supports Georgian)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY_PAID = os.getenv("GEMINI_API_KEY_PAID", "")
GEMINI_TIMEOUT = 60

Language = Literal["en", "ka"]

# Keywords that indicate deep reasoning / agentic tasks
AGENTIC_KEYWORDS = [
    "analyze", "explain why", "forecast", "risk", "scenario", "orchestrate",
    "strategy", "sensitivity", "monte carlo", "why", "how", "compare",
    "calculate", "reason", "plan", "evaluate", "assess", "investigate",
]

def _get_nvidia_key() -> str:
    """Get NVIDIA API key from env or settings."""
    key = NVIDIA_API_KEY
    if not key:
        try:
            from app.config import settings
            key = getattr(settings, 'NVIDIA_API_KEY', '')
        except Exception:
            pass
    return key or ""

def _get_nvidia_gemma_key() -> str:
    """Get NVIDIA API key for Gemma 4 (NVIDIA_API_KEY_GEMMA, fallback to NVIDIA_API_KEY)."""
    # Try Gemma-specific key first
    key = os.getenv("NVIDIA_API_KEY_GEMMA", "")
    if key and len(key) > 10:
        return key
    try:
        from app.config import settings
        key = getattr(settings, 'NVIDIA_API_KEY_GEMMA', '')
        if key and len(key) > 10:
            return key
    except Exception:
        pass
    # Fallback to main NVIDIA key
    return _get_nvidia_key()

def _get_gemini_key() -> str:
    """Get Google Gemini API key."""
    # 1. Direct from .env file (override system env which may have stale 'your_key_here')
    try:
        from dotenv import dotenv_values
        env_vals = dotenv_values('.env')
        key = env_vals.get("GEMINI_API_KEY", "")
        if key and key != 'your_key_here' and len(key) > 10:
            return key
    except Exception:
        pass
    # 2. From os.getenv
    import os
    key = os.getenv("GEMINI_API_KEY", "")
    if key and key != 'your_key_here' and len(key) > 10:
        return key
    # 2. From settings
    try:
        from app.config import settings
        key = getattr(settings, 'GEMINI_API_KEY', '')
        if key and key != 'your_key_here' and len(key) > 10:
            return key
    except Exception:
        pass
    # 3. Module-level constant
    if GEMINI_API_KEY and GEMINI_API_KEY != 'your_key_here' and len(GEMINI_API_KEY) > 10:
        return GEMINI_API_KEY
    return ""

def _get_anthropic_key() -> str:
    """Get Anthropic API key from env or settings."""
    try:
        from app.config import settings
        return settings.ANTHROPIC_API_KEY or ""
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY", "")

def _get_anthropic_model() -> str:
    """Get configured Anthropic model."""
    try:
        from app.config import settings
        return settings.ANTHROPIC_MODEL or "claude-sonnet-4-20250514"
    except Exception:
        return "claude-sonnet-4-20250514"

NVIDIA_TIMEOUT = 90  # seconds — cloud API


# ═══════════════════════════════════════════════════════════════════════════════
# FINAI CAPTAIN — Hybrid LLM Router
# ═══════════════════════════════════════════════════════════════════════════════

class FinAICaptainLLM:
    """FinAI Captain — intelligent hybrid routing across Claude, Nemotron, and Qwen3.

    Routing logic:
      - Georgian text or simple chat/intent → Claude (best fluency + tool execution)
      - Deep financial reasoning or agentic tasks → Nemotron (CoT + tool calling)
      - Fast / cost-free fallback → Qwen3 local (via Ollama)
    """

    QWEN_MODEL = "qwen2.5:3b"  # Available locally via Ollama on D:\ollama_models

    def detect_language(self, text: str) -> Language:
        """Detect Georgian (ქართული) vs English."""
        if any('\u10A0' <= char <= '\u10FF' for char in text):
            return "ka"
        return "en"

    async def route_and_call(
        self,
        message: str,
        context: Dict[str, Any] = None,
        use_nemo_retriever: bool = False,
        lang: str = "",
    ) -> Dict[str, Any]:
        """Main routing logic for FinAI Captain.

        Returns dict with: model, language, content, reasoning (optional), action (optional).
        """
        context = context or {}
        if not lang:
            lang = self.detect_language(message)

        msg_lower = message.lower()
        is_agentic_or_deep = any(kw in msg_lower for kw in AGENTIC_KEYWORDS)

        # ── Primary: Gemma 4 (Georgian-native, general purpose) ──
        result = await self._call_gemma4(message, context, lang)
        if result:
            return result

        # ── Deep reasoning: Nemotron (CoT + reasoning budget) ──
        if is_agentic_or_deep:
            result = await self._call_nemotron(message, context, lang if lang != "ka" else "en")
            if result:
                if lang == "ka":
                    result["content"] = "⚠️ Gemma 4 მიუწვდომელია. Nemotron-ის პასუხი ინგლისურად:\n\n" + result.get("content", "")
                return result

        # ── Fallback: Claude ──
        result = await self._call_claude(message, context, lang if lang != "ka" else "en")
        if result:
            if lang == "ka":
                result["content"] = "⚠️ ქართული ენის AI დროებით მიუწვდომელია. პასუხი ინგლისურად:\n\n" + result.get("content", "")
            return result

        # ── Fallback: Gemini (Georgian support) ──
        if _get_gemini_key():
            result = await self._call_gemini(message, context, lang)
            if result:
                return result

        # ── Fallback: Nemotron (if not agentic, try it anyway) ──
        if not is_agentic_or_deep:
            result = await self._call_nemotron(message, context, lang)
            if result:
                return result

        # Qwen3 / Ollama local fallback
        return await self._call_qwen(message, context, lang)

    async def _call_claude(
        self, message: str, context: Dict, lang: Language
    ) -> Optional[Dict[str, Any]]:
        """Call Claude Sonnet 4 for chat, intent, and Georgian fluency.

        Uses the anthropic SDK (same as the rest of the backend) for
        reliable request formatting.
        """
        api_key = _get_anthropic_key()
        if not api_key:
            return None

        # Build financial context block from live data
        ctx_block = ""
        if context:
            ctx_lines = []
            for k, v in context.items():
                if isinstance(v, (int, float)) and v != 0:
                    ctx_lines.append(f"  {k}: {v:,.2f}" if isinstance(v, float) else f"  {k}: {v:,}")
                elif isinstance(v, str) and v:
                    ctx_lines.append(f"  {k}: {v}")
                elif isinstance(v, list) and v:
                    ctx_lines.append(f"  {k}: {v}")
            if ctx_lines:
                ctx_block = "\n\nCURRENT FINANCIAL DATA (from uploaded Trial Balance):\n" + "\n".join(ctx_lines) + "\n\nUse this data to answer the user's question with specific numbers. Do NOT say you don't have access to data — you DO have the data above."

        system_prompt = (
            f"You are FinAI — the intelligent financial assistant for {settings.COMPANY_NAME}.\n"
            f"You speak fluent Georgian and English. Always reply in the user's language ({lang}).\n"
            f"You are a senior CFO-level expert in Georgian COA, 1C accounting, IFRS, "
            f"Baku MR reporting, and {settings.COMPANY_NAME} operations.\n"
            f"When the user asks to do something (show, generate, analyze, update), "
            f"describe the action clearly and offer next steps.\n"
            f"Be precise, proactive, and helpful.\n\n"
            f"IMPORTANT — UI ACTION COMMANDS:\n"
            f"When the user asks you to navigate, switch data, or export, you MUST include "
            f"the action tag at the END of your response:\n"
            f"- Navigate pages: [ACTION:NAVIGATE:/pnl] or [ACTION:NAVIGATE:/balance-sheet] or [ACTION:NAVIGATE:/revenue] or [ACTION:NAVIGATE:/costs] or [ACTION:NAVIGATE:/controls] or [ACTION:NAVIGATE:/reasoning] or [ACTION:NAVIGATE:/warehouse] or [ACTION:NAVIGATE:/mr-reports] or [ACTION:NAVIGATE:/alerts] or [ACTION:NAVIGATE:/ontology] or [ACTION:NAVIGATE:/library] or [ACTION:NAVIGATE:/intelligent-ingest] or [ACTION:NAVIGATE:/journal] or [ACTION:NAVIGATE:/periods]\n"
            f"- Switch dataset: [ACTION:SET_DATASET:14]\n"
            f"- Set period: [ACTION:SET_PERIOD:January 2026]\n"
            f"- Export Excel: [ACTION:EXPORT:pl_comparison] or [ACTION:EXPORT:bs_comparison]\n"
            f"- Send email: [ACTION:EMAIL:pl_comparison]\n"
            f"Always include the tag when the user's request implies a UI action.\n"
            f"{ctx_block}"
        )

        model = _get_anthropic_model()

        try:
            import anthropic
            import httpx
            client = anthropic.AsyncAnthropic(api_key=api_key, timeout=httpx.Timeout(10.0, connect=5.0))
            response = await client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": message}],
            )
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            if content:
                logger.info("Claude response: model=%s, length=%d", model, len(content))
                return {
                    "model": model,
                    "language": lang,
                    "content": content,
                    "action": None,
                }
        except Exception as e:
            logger.warning("Claude API failed: %s", e)

        return None

    async def _call_nemotron(
        self, message: str, context: Dict, lang: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """Call Nemotron for deep financial reasoning + agentic orchestration."""
        api_key = _get_nvidia_key()
        if not api_key:
            return None

        # Language-aware system prompt — VERY explicit for Nemotron
        if lang == "ka":
            lang_instruction = "IMPORTANT: You MUST reply ONLY in Georgian language (ქართული ენა). Do NOT reply in English, Russian, Chinese, or any other language. Every word of your response must be in Georgian."
            user_prefix = "[ქართულად უპასუხე] "
        else:
            lang_instruction = "Reply in English."
            user_prefix = ""
        # Build financial context block from live data
        ctx_block_n = ""
        if context:
            ctx_lines_n = []
            for k, v in context.items():
                if isinstance(v, (int, float)) and v != 0:
                    ctx_lines_n.append(f"  {k}: {v:,.2f}" if isinstance(v, float) else f"  {k}: {v:,}")
                elif isinstance(v, str) and v:
                    ctx_lines_n.append(f"  {k}: {v}")
            if ctx_lines_n:
                ctx_block_n = "\n\nCURRENT FINANCIAL DATA (from uploaded Trial Balance):\n" + "\n".join(ctx_lines_n) + "\n\nUse this data to answer with specific numbers. You DO have access to this data."

        system_msg = (
            f"You are FinAI — a senior CFO-level financial analyst. "
            f"{lang_instruction} "
            f"You are an expert in Georgian 1C accounting, IFRS, financial analysis, and strategic advisory. "
            f"Provide precise, actionable insights with specific numbers and recommendations."
            f"{ctx_block_n}"
        )

        payload = {
            "model": NVIDIA_MODEL,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"{user_prefix}{message}"},
            ],
            "max_tokens": 4096,
            "temperature": 0.6,
            "top_p": 0.95,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": True},
            "reasoning_budget": 4096,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    NVIDIA_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=NVIDIA_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg = data.get("choices", [{}])[0].get("message", {})
                        content = msg.get("content", "")
                        reasoning = msg.get("reasoning_content", "")
                        if content:
                            logger.info("Nemotron Captain response: length=%d", len(content))
                            return {
                                "model": "nemotron-3-super-120b",
                                "language": lang,
                                "content": content,
                                "reasoning": reasoning or None,
                            }
                    else:
                        body = await resp.text()
                        logger.debug("NVIDIA API returned %d: %s", resp.status, body[:200])
        except asyncio.TimeoutError:
            logger.debug("NVIDIA API timeout after %ds", NVIDIA_TIMEOUT)
        except Exception as e:
            logger.debug("NVIDIA API failed: %s", e)

        return None

    async def _call_gemma4(
        self, message: str, context: Dict, lang: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """Call Gemma 4 31B IT via NVIDIA API — primary LLM with Georgian support."""
        api_key = _get_nvidia_gemma_key()
        if not api_key:
            return None

        # Georgian language enforcement — Gemma 4 supports Georgian natively
        if lang == "ka":
            lang_instruction = (
                "CRITICAL: You MUST reply ENTIRELY in Georgian (ქართული ენა). "
                "ALL content, labels, explanations, narratives, summaries, recommendations — "
                "everything must be in Georgian. Do NOT use English, Russian, or any other language. "
                "JSON keys may stay in English but ALL text values MUST be Georgian."
            )
            user_prefix = "[ქართულად უპასუხე] "
        else:
            lang_instruction = "Reply in English."
            user_prefix = ""

        # Build financial context block
        ctx_block = ""
        if context:
            ctx_lines = []
            for k, v in context.items():
                if isinstance(v, (int, float)) and v != 0:
                    ctx_lines.append(f"  {k}: {v:,.2f}" if isinstance(v, float) else f"  {k}: {v:,}")
                elif isinstance(v, str) and v:
                    ctx_lines.append(f"  {k}: {v}")
            if ctx_lines:
                ctx_block = "\n\nCURRENT FINANCIAL DATA:\n" + "\n".join(ctx_lines) + "\n\nUse this data to answer with specific numbers."

        system_msg = (
            f"You are FinAI — a senior CFO-level financial analyst. "
            f"{lang_instruction} "
            f"You are an expert in Georgian 1C accounting, IFRS, financial analysis, and strategic advisory. "
            f"Provide precise, actionable insights with specific numbers and recommendations."
            f"{ctx_block}"
        )

        payload = {
            "model": GEMMA4_MODEL,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"{user_prefix}{message}"},
            ],
            "max_tokens": 16384,
            "temperature": 1.0,
            "top_p": 0.95,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": True},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    NVIDIA_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=GEMMA4_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg = data.get("choices", [{}])[0].get("message", {})
                        content = msg.get("content", "")
                        reasoning = msg.get("reasoning_content", "")
                        if content:
                            logger.info("Gemma 4 response: length=%d, lang=%s", len(content), lang)
                            return {
                                "model": "gemma-4-31b-it",
                                "language": lang,
                                "content": content,
                                "reasoning": reasoning or None,
                            }
                    else:
                        body = await resp.text()
                        logger.debug("Gemma 4 API returned %d: %s", resp.status, body[:200])
        except asyncio.TimeoutError:
            logger.debug("Gemma 4 API timeout after %ds", GEMMA4_TIMEOUT)
        except Exception as e:
            logger.debug("Gemma 4 API failed: %s", e)

        return None

    async def _call_gemini(
        self, message: str, context: Dict, lang: Language = "en"
    ) -> Optional[Dict[str, Any]]:
        """Call Google Gemini 2.0 Flash (free tier, excellent Georgian support).

        Uses systemInstruction for proper system-prompt separation and
        the generativelanguage.googleapis.com v1beta endpoint.
        """
        api_key = _get_gemini_key()
        if not api_key:
            logger.warning("No Gemini API key configured — skipping Gemini call")
            return None

        lang_instruction = "Reply in Georgian (ქართული)." if lang == "ka" else "Reply in English."
        system_msg = (
            f"You are FinAI — a senior CFO-level financial intelligence assistant. "
            f"{lang_instruction} "
            f"You are an expert in Georgian 1C accounting, IFRS, financial analysis, "
            f"and strategic advisory. Be precise, data-driven, and actionable."
        )

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": message}]}],
                "systemInstruction": {"parts": [{"text": system_msg}]},
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=GEMINI_TIMEOUT),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.debug("Gemini API error %d: %s", resp.status, body[:200])
                        return None
                    data = await resp.json()
                    content = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if not content:
                        return None
                    logger.info("Gemini 2.0 Flash response: lang=%s, length=%d", lang, len(content))
                    return {
                        "model": "gemini-2.5-flash",
                        "language": lang,
                        "content": content,
                        "reasoning": None,
                        "action": None,
                    }
        except asyncio.TimeoutError:
            logger.debug("Gemini API timeout after %ds", GEMINI_TIMEOUT)
        except Exception as e:
            logger.debug("Gemini call failed: %s", e)
        return None

    async def _call_qwen(
        self, message: str, context: Dict, lang: Language = "en"
    ) -> Dict[str, Any]:
        """Call Qwen3 via Ollama as fast local fallback."""
        try:
            from app.config import settings
            base_url = getattr(settings, 'OLLAMA_BASE_URL', OLLAMA_BASE_URL)
        except Exception:
            base_url = OLLAMA_BASE_URL

        # Check if Qwen3 is available, fall back to whatever model Ollama has
        model = self.QWEN_MODEL
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
            "options": {"temperature": 0.7},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("message", {}).get("content", "")
                        if content:
                            logger.info("Qwen3 Captain response: length=%d", len(content))
                            return {
                                "model": "qwen3",
                                "language": lang,
                                "content": content,
                            }
        except Exception as e:
            logger.debug("Qwen3/Ollama failed: %s", e)

        # Ultimate fallback — use the existing local_llm
        return {
            "model": "fallback",
            "language": lang,
            "content": "I'm having trouble connecting to the AI models right now. Please try again shortly.",
        }

    def get_status(self) -> Dict[str, Any]:
        """Return Captain routing status."""
        return {
            "captain_enabled": True,
            "claude_configured": bool(_get_anthropic_key()),
            "claude_model": _get_anthropic_model(),
            "gemini_configured": bool(_get_gemini_key()),
            "gemini_model": "gemini-2.0-flash",
            "nvidia_configured": bool(_get_nvidia_key()),
            "nvidia_model": NVIDIA_MODEL,
            "qwen_model": self.QWEN_MODEL,
        }


# Module-level Captain singleton
captain_llm = FinAICaptainLLM()


async def translate_to_georgian(text: str, max_length: int = 4000) -> str:
    """Translate English text to Georgian using Gemini. Returns original if translation fails."""
    key = _get_gemini_key()
    if not key:
        logger.warning("No Gemini API key for translation — returning original text")
        return text
    if not text:
        return text

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": f"Translate to Georgian (ქართული). Only return the translation, no explanations:\n\n{text[:max_length]}"}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translated = data["candidates"][0]["content"]["parts"][0]["text"]
                    return translated
                else:
                    body = await resp.text()
                    logger.debug("Gemini translate error %d: %s", resp.status, body[:200])
    except Exception as e:
        logger.debug(f"Georgian translation failed: {e}")
    return text


class LocalLLMService:
    """Ollama-backed local model service.

    Usage:
        if await local_llm.is_available():
            response = await local_llm.chat(
                system="You are a financial analyst.",
                messages=[{"role": "user", "content": "What is gross margin?"}],
                complexity="balanced"
            )
    """

    MODELS = {
        "fast": "llama3.2:3b",        # 2.0GB — fast reasoning
        "balanced": "llama3.2:3b",    # 2.0GB — available and working
        "capable": "llama3.2:3b",     # 2.0GB — best available
    }

    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self._base_url = base_url.rstrip("/")
        self._available: Optional[bool] = None  # Cache availability check
        self._available_models: List[str] = []
        self._best_available: Optional[str] = None  # Best model that's actually pulled

    # ── Public API ──────────────────────────────────────────────────────────

    async def is_available(self) -> bool:
        """Check if Ollama is running and has at least one model available."""
        if self._available is not None:
            return self._available

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get("models", [])
                        self._available_models = [m["name"] for m in models]
                        self._available = len(self._available_models) > 0
                        if self._available:
                            self._select_best_model()
                            logger.info(
                                "Ollama available: %d models, best=%s",
                                len(self._available_models), self._best_available,
                            )
                        return self._available
        except Exception as e:
            logger.debug("Ollama not available: %s", e)

        self._available = False
        return False

    async def chat(
        self,
        system: str,
        messages: List[Dict[str, str]],
        complexity: str = "balanced",
        max_tokens: int = 2048,
    ) -> Optional[str]:
        """Run a chat completion via NVIDIA Nemotron (preferred) or Ollama (fallback).

        Args:
            system: System prompt
            messages: List of {"role": "user"|"assistant", "content": "..."}
            complexity: "fast" | "balanced" | "capable"
            max_tokens: Maximum response tokens

        Returns:
            Response text, or None if no LLM is available.
        """
        # ── Try Gemma 4 first (cloud, primary LLM, Georgian-capable) ──
        gemma4_result = await self._try_gemma4(system, messages, max_tokens)
        if gemma4_result is not None:
            return gemma4_result

        # ── Try NVIDIA Nemotron (cloud, deep reasoning) ──
        nvidia_result = await self._try_nvidia(system, messages, max_tokens)
        if nvidia_result is not None:
            return nvidia_result

        # ── Fallback: Ollama (local) ──
        if not await self.is_available():
            return None

        model = self._select_model_for_complexity(complexity)
        if not model:
            logger.warning("No suitable local model available for complexity=%s", complexity)
            return None

        # Build Ollama messages format
        ollama_messages = [{"role": "system", "content": system}] + messages

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.0,  # Deterministic
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Try /api/chat first (newer Ollama models)
                async with session.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data.get("message", {}).get("content", "")
                        logger.info(
                            "Ollama chat response: model=%s, length=%d",
                            model, len(text),
                        )
                        return text
                    elif resp.status == 400:
                        # Model doesn't support /api/chat — fall back to /api/generate
                        logger.info("Ollama /api/chat not supported for %s, trying /api/generate", model)
                    else:
                        body = await resp.text()
                        logger.warning("Ollama chat returned %d: %s", resp.status, body[:200])

                # Fallback: /api/generate (works with all models)
                prompt = system + "\n\n"
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        prompt += f"User: {content}\n"
                    elif role == "assistant":
                        prompt += f"Assistant: {content}\n"
                prompt += "Assistant: "

                gen_payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.1,
                    },
                }

                async with session.post(
                    f"{self._base_url}/api/generate",
                    json=gen_payload,
                    timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data.get("response", "")
                        logger.info(
                            "Ollama generate response: model=%s, length=%d",
                            model, len(text),
                        )
                        return text
                    else:
                        body = await resp.text()
                        logger.warning("Ollama generate returned %d: %s", resp.status, body[:200])
                        return None

        except asyncio.TimeoutError:
            logger.warning("Ollama timeout after %ds for model %s", OLLAMA_TIMEOUT, model)
            return None
        except Exception as e:
            logger.warning("Ollama call failed: %s", e)
            return None

    async def _try_gemma4(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
    ) -> Optional[str]:
        """Try Gemma 4 31B IT via NVIDIA API — primary LLM with Georgian support.

        Uses the same NVIDIA API endpoint as Nemotron but with google/gemma-4-31b-it model.
        Gemma 4 supports enable_thinking for chain-of-thought reasoning.
        """
        api_key = _get_nvidia_gemma_key()
        if not api_key:
            return None

        gemma_messages = [{"role": "system", "content": system}] + messages

        payload = {
            "model": GEMMA4_MODEL,
            "messages": gemma_messages,
            "max_tokens": max_tokens,
            "temperature": 1.0,
            "top_p": 0.95,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": True},
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    NVIDIA_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=GEMMA4_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choice = data.get("choices", [{}])[0]
                        msg = choice.get("message", {})
                        text = msg.get("content", "")
                        reasoning = msg.get("reasoning_content", "")
                        if reasoning:
                            logger.info("Gemma 4 reasoning: %d chars", len(reasoning))
                        if text:
                            logger.info(
                                "Gemma 4 response: model=%s, length=%d",
                                GEMMA4_MODEL, len(text),
                            )
                            return text
                    else:
                        body = await resp.text()
                        logger.debug(
                            "Gemma 4 API returned %d: %s", resp.status, body[:200]
                        )
        except asyncio.TimeoutError:
            logger.debug("Gemma 4 API timeout after %ds", GEMMA4_TIMEOUT)
        except Exception as e:
            logger.debug("Gemma 4 API failed: %s", e)

        return None

    async def _try_nvidia(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
    ) -> Optional[str]:
        """Try NVIDIA Nemotron 3 Super API with reasoning mode enabled.

        Uses enable_thinking for chain-of-thought reasoning and returns
        the final content (reasoning_content is internal).
        """
        api_key = _get_nvidia_key()
        if not api_key:
            return None  # No API key configured — skip

        nvidia_messages = [{"role": "system", "content": system}] + messages

        # Nemotron supports reasoning mode with thinking budget
        reasoning_budget = min(max_tokens, 4096)
        payload = {
            "model": NVIDIA_MODEL,
            "messages": nvidia_messages,
            "max_tokens": max_tokens,
            "temperature": 0.6,
            "top_p": 0.95,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": True},
            "reasoning_budget": reasoning_budget,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    NVIDIA_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=NVIDIA_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choice = data.get("choices", [{}])[0]
                        msg = choice.get("message", {})
                        # Content is the final answer; reasoning_content is the chain-of-thought
                        text = msg.get("content", "")
                        reasoning = msg.get("reasoning_content", "")
                        if reasoning:
                            logger.info("NVIDIA Nemotron reasoning: %d chars", len(reasoning))
                        if text:
                            logger.info(
                                "NVIDIA Nemotron response: model=%s, length=%d",
                                NVIDIA_MODEL, len(text),
                            )
                            return text
                    else:
                        body = await resp.text()
                        logger.debug(
                            "NVIDIA API returned %d: %s", resp.status, body[:200]
                        )
        except asyncio.TimeoutError:
            logger.debug("NVIDIA API timeout after %ds", NVIDIA_TIMEOUT)
        except Exception as e:
            logger.debug("NVIDIA API failed: %s", e)

        return None  # Fall through to Ollama

    async def classify(
        self,
        prompt: str,
        options: List[str],
    ) -> Optional[str]:
        """Fast classification using the smallest available model.

        Args:
            prompt: Classification question
            options: List of valid options to choose from

        Returns:
            One of the options, or None.
        """
        system = (
            f"You are a classifier. Respond with EXACTLY one of these options: "
            f"{', '.join(options)}. No explanation. Just the option."
        )
        result = await self.chat(
            system=system,
            messages=[{"role": "user", "content": prompt}],
            complexity="fast",
            max_tokens=20,
        )
        if result:
            # Find which option best matches
            result_lower = result.strip().lower()
            for opt in options:
                if opt.lower() in result_lower:
                    return opt
        return None

    def get_status(self) -> Dict[str, Any]:
        """Return status for monitoring endpoint."""
        nvidia_key = NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", "")
        return {
            "available": self._available or bool(nvidia_key),
            "nvidia_configured": bool(nvidia_key),
            "nvidia_model": NVIDIA_MODEL if nvidia_key else None,
            "ollama_available": self._available,
            "base_url": self._base_url,
            "models_available": self._available_models,
            "best_model": self._best_available,
            "models_configured": self.MODELS,
        }

    # ── Internal helpers ────────────────────────────────────────────────────

    def _select_best_model(self) -> None:
        """Find the most capable model that's actually pulled."""
        # Check in order of preference (most capable first)
        for complexity in ["capable", "balanced", "fast"]:
            model_name = self.MODELS[complexity]
            # Check if model is in available list (partial match for tags like :latest)
            base_name = model_name.split(":")[0]
            for available in self._available_models:
                if available.startswith(base_name):
                    self._best_available = available
                    return
        # No known model — use whatever is first
        if self._available_models:
            self._best_available = self._available_models[0]

    def _select_model_for_complexity(self, complexity: str) -> Optional[str]:
        """Select the best available model for the given complexity level."""
        # Try requested complexity first, then fall up/down
        order = {
            "fast": ["fast", "balanced", "capable"],
            "balanced": ["balanced", "fast", "capable"],
            "capable": ["capable", "balanced", "fast"],
        }.get(complexity, ["balanced", "fast", "capable"])

        for c in order:
            model_name = self.MODELS[c]
            base_name = model_name.split(":")[0]
            for available in self._available_models:
                if available.startswith(base_name):
                    return available

        # Use whatever is available
        return self._best_available or (self._available_models[0] if self._available_models else None)


# Module-level singleton — use this everywhere
local_llm = LocalLLMService()
