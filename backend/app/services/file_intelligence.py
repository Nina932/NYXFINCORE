"""
File Intelligence Engine — LLM-Powered Financial File Understanding
====================================================================
This is the bridge between "dumb pattern matching" and "real understanding".

Instead of hardcoded regex rules to detect sheet types and column meanings,
this engine sends file samples to the LLM and asks:
  "What type of financial data is this? What do these columns mean?"

The LLM handles UNDERSTANDING (what is this data?).
Deterministic code handles COMPUTATION (extract and calculate).
The LLM NEVER touches the numbers — it only tells us where to find them.

Flow:
  1. Read first N rows of each sheet
  2. Send to LLM: "Classify this sheet and map columns"
  3. LLM returns structured JSON: {sheet_type, column_mapping, account_codes_found}
  4. Deterministic extractor uses this mapping to pull real numbers
  5. AccountHierarchy validates account codes
  6. Computed metrics are 100% deterministic
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# The accounting knowledge prompt — this is what makes it intelligent
ACCOUNTING_BRAIN_PROMPT = """You are a senior financial analyst, chartered accountant, and Big4 audit partner with deep expertise in:
- IFRS and Georgian accounting standards
- 1C Enterprise accounting software (Russian/Georgian)
- Fuel distribution / energy retail industry
- Multi-language financial documents (English, Georgian ქართული, Russian русский)

DETAILED CHART OF ACCOUNTS (Georgian 1C, IFRS-compatible):
  11XX = Cash/Petty Cash (BS: current_assets)
  12XX = Bank Accounts (BS: current_assets)
  14XX = Trade Receivables (BS: current_assets)
  16XX = Inventory/Prepayments (BS: current_assets) — NEVER use as COGS!
  21XX = Fixed Assets / PP&E (BS: noncurrent_assets)
  22XX = Accumulated Depreciation (BS: noncurrent_assets, negative value)
  24XX = Long-term Investments (BS: noncurrent_assets)
  31XX = Current Liabilities / Trade Payables (BS: current_liabilities)
  33XX = VAT / Tax Payables (BS: current_liabilities)
  41XX = Long-term Debt (BS: noncurrent_liabilities)
  51XX = Share Capital (BS: equity)
  54XX = Retained Earnings (BS: equity)
  61XX = Revenue from Sales (P&L: Revenue) — credit balance, appears NEGATIVE in TB
  62XX = Other Revenue (P&L: Other Revenue)
  71XX = Cost of Goods Sold (P&L: COGS) — THE REAL COGS, not 16XX
  73XX = Selling & Distribution Expenses (P&L: OpEx)
  74XX = General & Administrative Expenses (P&L: OpEx)
  81XX = Other Operating Income: FX gains, asset disposal income
  82XX = Other Operating Expenses: interest expense, FX losses
  91XX = Income Tax Expense (P&L: Tax)

CRITICAL KNOWLEDGE:
- Account 1610 turnovers are INVENTORY movements, NOT Cost of Goods Sold
- Account 7110 is the actual COGS (cost of products sold)
- "Обороты счета 1610" means "Turnovers of account 1610" (inventory)
- "Оборотно-сальдовая ведомость" means "Trial Balance"
- "Итог" / "Total" / "სულ" are subtotal rows — skip them in summation
- Revenue (61XX) is negative in trial balance because it's a credit account
- Sub-accounts (e.g. 7310/1, 7310.01.1/1) are line-item details, not totals
- 4-digit or XX-level codes are the parent/total accounts

SHEET TYPE PATTERNS:
- Headers "Product | Amount | VAT | Net Revenue" → revenue_breakdown
- Headers "Субконто | Нач. сальдо | Деб. оборот" → cogs_detail (inventory, NOT P&L COGS)
- Headers "Код | Наименование | Дебет | Кредит" → trial_balance
- Headers "Index | Company | Code | Name | Start Dr | Start Cr" → balance_sheet
- Columns with 61XX/71XX/73XX/74XX codes + amounts → pl_summary (Mapping sheet)

RULES:
- NEVER invent or estimate numbers
- ONLY classify the structure and meaning of data
- Return ONLY valid JSON, nothing else

You will receive sample rows from an Excel sheet. Analyze and return:
{
  "sheet_type": "revenue_breakdown|cogs_detail|pl_summary|trial_balance|balance_sheet|chart_of_accounts|transactions|unknown",
  "confidence": 0.0-1.0,
  "description": "one line explaining what this sheet contains",
  "column_mapping": {
    "0": {"field": "product|account_code|description|date|amount|vat|category|debit|credit|balance|name|index", "label": "original header text"},
    "1": {"field": "...", "label": "..."}
  },
  "account_codes_found": ["6110", "7110", ...],
  "is_summary_or_detail": "summary|detail",
  "contains_totals": true|false,
  "total_row_indicators": ["Итог", "Total", ...],
  "currency": "GEL|USD|EUR|unknown",
  "period_detected": "January 2026|Q1 2026|2025|unknown",
  "company_detected": "company name or unknown",
  "warnings": ["any issues detected"],
  "pl_accounts": {"revenue": ["6110"], "cogs": ["7110"], "opex": ["7310","7410"]},
  "bs_accounts": {"assets": [...], "liabilities": [...], "equity": [...]},
  "key_insight": "one sentence about what an accountant would notice about this data"
}"""


class FileIntelligenceEngine:
    """Uses LLM to understand ANY financial file structure."""

    def __init__(self):
        self._cache: Dict[str, Dict] = {}  # cache sheet analyses

    def analyze_sheet(self, sheet_name: str, sample_rows: List[List], max_rows: int = 15) -> Dict[str, Any]:
        """
        Send sheet sample to LLM for intelligent classification.

        Args:
            sheet_name: Name of the Excel sheet
            sample_rows: First N rows of data (list of lists)
            max_rows: How many rows to send to LLM

        Returns:
            Structured analysis from LLM
        """
        cache_key = f"{sheet_name}:{len(sample_rows)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build the sample text
        sample_text = f"Sheet name: \"{sheet_name}\"\n"
        sample_text += f"Total rows provided: {len(sample_rows)}\n\n"
        for i, row in enumerate(sample_rows[:max_rows]):
            cells = [str(c)[:50] if c is not None else "" for c in row[:10]]
            sample_text += f"Row {i+1}: {' | '.join(cells)}\n"

        # Call LLM
        result = self._call_llm(sample_text)
        self._cache[cache_key] = result
        return result

    def analyze_workbook(self, wb) -> List[Dict[str, Any]]:
        """Analyze all sheets in a workbook using LLM intelligence."""
        analyses = []
        for sname in wb.sheetnames:
            ws = wb[sname]
            # Extract sample rows
            sample_rows = []
            for row in ws.iter_rows(min_row=1, max_row=min(15, ws.max_row or 1), values_only=True):
                sample_rows.append(list(row))

            analysis = self.analyze_sheet(sname, sample_rows)
            analysis["sheet_name"] = sname
            analysis["total_rows"] = ws.max_row or 0
            analysis["total_cols"] = ws.max_column or 0
            analyses.append(analysis)

            logger.info("FileIntelligence: sheet '%s' -> %s (%.0f%% conf): %s",
                        sname, analysis.get("sheet_type", "?"),
                        analysis.get("confidence", 0) * 100,
                        analysis.get("description", "?")[:60])

        return analyses

    def _call_llm(self, sample_text: str) -> Dict[str, Any]:
        """Call LLM (sync) for sheet analysis. Chain: Claude → Ollama → Deterministic."""
        import httpx
        import os

        prompt = f"{ACCOUNTING_BRAIN_PROMPT}\n\nHere is the data to analyze:\n\n{sample_text}"

        # Tier 1: Claude API (best quality — your key is configured)
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            try:
                from app.config import settings
                api_key = str(settings.ANTHROPIC_API_KEY or "")
            except Exception:
                pass

        if api_key and len(api_key) > 20:
            try:
                model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
                with httpx.Client(timeout=30) as client:
                    r = client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": model,
                            "max_tokens": 2048,
                            "system": "You are a world-class chartered accountant. Analyze financial data structure. Return ONLY valid JSON matching the requested schema. No markdown, no explanation — pure JSON only.",
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    if r.status_code == 200:
                        data = r.json()
                        text = data.get("content", [{}])[0].get("text", "")
                        parsed = self._parse_json_response(text)
                        if parsed:
                            parsed["llm_used"] = f"claude:{model}"
                            logger.info("FileIntelligence: Claude analysis succeeded")
                            return parsed
                    else:
                        logger.warning("Claude API returned %d: %s", r.status_code, r.text[:200])
            except Exception as e:
                logger.warning("Claude analysis failed: %s", str(e)[:100])

        # Tier 2: Ollama (free, local)
        try:
            with httpx.Client(timeout=45) as client:
                r = client.post("http://localhost:11434/api/chat", json={
                    "model": "qwen2.5:3b",
                    "messages": [
                        {"role": "system", "content": "You are an expert accountant. Return ONLY valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                })
                if r.status_code == 200:
                    text = r.json().get("message", {}).get("content", "")
                    parsed = self._parse_json_response(text)
                    if parsed:
                        parsed["llm_used"] = "ollama:qwen2.5:3b"
                        return parsed
        except Exception as e:
            logger.warning("Ollama analysis failed: %s", str(e)[:100])

        # Tier 3: Deterministic fallback (no LLM)
        return self._deterministic_fallback(sample_text)

    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response."""
        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try markdown code block
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _deterministic_fallback(self, sample_text: str) -> Dict[str, Any]:
        """Rule-based fallback when LLM is unavailable."""
        text_lower = sample_text.lower()

        # Detect sheet type from keywords
        if any(kw in text_lower for kw in ["revenue breakdown", "net revenue", "product"]):
            return {"sheet_type": "revenue_breakdown", "confidence": 0.7,
                    "description": "Revenue by product", "llm_used": "deterministic"}
        elif any(kw in text_lower for kw in ["1610", "себестоимость", "cogs"]):
            return {"sheet_type": "cogs_detail", "confidence": 0.6,
                    "description": "Inventory/COGS detail (account 1610)", "llm_used": "deterministic"}
        elif any(kw in text_lower for kw in ["оборотно-сальдовая", "trial balance"]):
            return {"sheet_type": "trial_balance", "confidence": 0.7,
                    "description": "Trial balance", "llm_used": "deterministic"}
        elif any(kw in text_lower for kw in ["mapping", "7110", "6110"]):
            return {"sheet_type": "pl_summary", "confidence": 0.7,
                    "description": "P&L account mapping", "llm_used": "deterministic"}
        elif any(kw in text_lower for kw in ["balance", "start dr", "start cr"]):
            return {"sheet_type": "balance_sheet", "confidence": 0.6,
                    "description": "Balance detail", "llm_used": "deterministic"}
        else:
            return {"sheet_type": "unknown", "confidence": 0.3,
                    "description": "Unrecognized structure", "llm_used": "deterministic"}


# Singleton
file_intelligence = FileIntelligenceEngine()
