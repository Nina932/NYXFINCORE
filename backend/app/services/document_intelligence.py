"""
Financial Document Intelligence — Auto-detect document type from any Excel file.

Classifies uploaded files as:
  - trial_balance: 1C Оборотно-сальдовая ведомость
  - transaction_journal: GL journal entries (date, dr, cr, amount)
  - pnl_report: Pre-formatted P&L statement
  - balance_sheet: Pre-formatted Balance Sheet
  - combined_report: Multi-sheet workbook with P&L + BS + breakdowns
  - unknown: Unrecognized format
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Detection keywords ──────────────────────────────────────────

TB_KEYWORDS = [
    "оборотно-сальдовая", "сальдо на начало", "сальдо на конец",
    "trial balance", "оборот за период", "tdsheet",
]
TB_HEADER_KEYWORDS = ["дебет", "кредит", "счет", "код", "наименование"]

TXN_KEYWORDS = [
    "журнал операций", "журнал проводок", "journal entries",
    "transaction", "проводки", "хозяйственные операции",
]

PNL_KEYWORDS = [
    "revenue", "cogs", "gross profit", "ebitda", "net profit",
    "выручка", "себестоимость", "валовая прибыль", "чистая прибыль",
    "income statement", "profit and loss", "p&l",
    "revenue from sale", "operating expenses",
]

BS_KEYWORDS = [
    "total assets", "total liabilities", "equity",
    "активы", "пассивы", "обязательства", "капитал",
    "balance sheet", "statement of financial position",
    "current assets", "noncurrent assets",
]


@dataclass
class SheetAnalysis:
    name: str
    doc_type: str = "unknown"
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    row_count: int = 0
    col_count: int = 0


@dataclass
class DocumentAnalysis:
    doc_type: str  # trial_balance, transaction_journal, pnl_report, balance_sheet, combined_report, unknown
    confidence: float
    sheets: List[SheetAnalysis] = field(default_factory=list)
    detected_company: Optional[str] = None
    detected_period: Optional[str] = None
    primary_sheet: Optional[str] = None


class DocumentIntelligence:
    """Examines any Excel file and determines its financial document type."""

    def analyze(self, file_path: str) -> DocumentAnalysis:
        """Classify the document type of an Excel file."""
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            logger.warning("DocumentIntelligence: cannot open %s: %s", file_path, e)
            return DocumentAnalysis(doc_type="unknown", confidence=0.0)

        sheets: List[SheetAnalysis] = []
        for sheet_name in xls.sheet_names:
            sa = self._analyze_sheet(xls, sheet_name)
            sheets.append(sa)

        # Pick the best-scoring sheet
        best = max(sheets, key=lambda s: s.confidence) if sheets else None

        if not best or best.confidence < 0.3:
            return DocumentAnalysis(doc_type="unknown", confidence=0.0, sheets=sheets)

        # For combined reports: check if multiple sheets have different types
        types_found = {s.doc_type for s in sheets if s.confidence > 0.4}
        if len(types_found) > 1 and "trial_balance" not in types_found:
            doc_type = "combined_report"
        else:
            doc_type = best.doc_type

        # Extract company/period from TB or first sheet
        company, period = self._extract_metadata(xls, best.name if best else xls.sheet_names[0])

        return DocumentAnalysis(
            doc_type=doc_type,
            confidence=best.confidence if best else 0.0,
            sheets=sheets,
            detected_company=company,
            detected_period=period,
            primary_sheet=best.name if best else None,
        )

    def _analyze_sheet(self, xls: pd.ExcelFile, sheet_name: str) -> SheetAnalysis:
        """Score a single sheet against all document type patterns."""
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=20)
        except Exception:
            return SheetAnalysis(name=sheet_name)

        # Flatten all text in first 20 rows to lowercase for keyword matching
        text_blob = ""
        for i in range(min(20, len(df))):
            for c in range(df.shape[1]):
                v = df.iloc[i, c]
                if pd.notna(v):
                    text_blob += " " + str(v).lower()

        sa = SheetAnalysis(name=sheet_name, row_count=len(df), col_count=df.shape[1])

        # Score each type
        tb_score = self._score_trial_balance(text_blob, df, sheet_name)
        txn_score = self._score_transactions(text_blob, df)
        pnl_score = self._score_pnl(text_blob)
        bs_score = self._score_bs(text_blob)

        scores = {
            "trial_balance": tb_score,
            "transaction_journal": txn_score,
            "pnl_report": pnl_score,
            "balance_sheet": bs_score,
        }

        best_type = max(scores, key=scores.get)
        sa.doc_type = best_type
        sa.confidence = scores[best_type]
        sa.signals = [f"{k}={v:.2f}" for k, v in scores.items() if v > 0]

        return sa

    def _score_trial_balance(self, text: str, df: pd.DataFrame, sheet_name: str) -> float:
        score = 0.0
        signals = []

        # Sheet name match
        if "tdsheet" in sheet_name.lower() or "tb" in sheet_name.lower():
            score += 0.3
            signals.append("sheet_name")

        # Keyword matches
        for kw in TB_KEYWORDS:
            if kw in text:
                score += 0.2
                signals.append(f"kw:{kw[:20]}")

        # Header keywords (дебет/кредит pattern)
        header_hits = sum(1 for kw in TB_HEADER_KEYWORDS if kw in text)
        if header_hits >= 3:
            score += 0.3

        # Look for 4-digit account codes in first column data
        account_code_count = 0
        for i in range(min(30, len(df))):
            for c in [0, 1, 2]:
                if c < df.shape[1]:
                    v = str(df.iloc[i, c]) if pd.notna(df.iloc[i, c]) else ""
                    if re.match(r'^\d{4}$', v.strip()) or re.match(r'^\d{2}XX$', v.strip(), re.IGNORECASE):
                        account_code_count += 1
        if account_code_count >= 3:
            score += 0.3

        return min(score, 1.0)

    def _score_transactions(self, text: str, df: pd.DataFrame) -> float:
        score = 0.0
        for kw in TXN_KEYWORDS:
            if kw in text:
                score += 0.25

        # Look for date column + dr/cr account columns
        has_date = any(kw in text for kw in ["дата", "date"])
        has_dr_cr = "дебет" in text and "кредит" in text
        if has_date and has_dr_cr:
            score += 0.3

        return min(score, 1.0)

    def _score_pnl(self, text: str) -> float:
        score = 0.0
        for kw in PNL_KEYWORDS:
            if kw in text:
                score += 0.1
        return min(score, 1.0)

    def _score_bs(self, text: str) -> float:
        score = 0.0
        for kw in BS_KEYWORDS:
            if kw in text:
                score += 0.1
        return min(score, 1.0)

    def _extract_metadata(self, xls: pd.ExcelFile, sheet_name: str) -> tuple:
        """Extract company name and period from header rows."""
        company = None
        period = None
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=10)
            for i in range(min(10, len(df))):
                for c in range(df.shape[1]):
                    v = df.iloc[i, c]
                    if pd.notna(v):
                        s = str(v)
                        # Company: look for Georgian text or known patterns
                        if "//" in s and not company:
                            company = s.split("//")[0].strip()
                        # Period: look for "Период: Январь 2025 г."
                        pm = re.search(
                            r'(?:Период|Period)[:\s]*(Январ[ья]|Феврал[ья]|Март[а]?|Апрел[ьяi]|Ма[йяi]|Июн[ьяi]|Июл[ьяi]|Август[а]?|Сентябр[ьяi]|Октябр[ьяi]|Ноябр[ьяi]|Декабр[ьяi]|January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})',
                            s, re.IGNORECASE
                        )
                        if pm and not period:
                            month_str = pm.group(1).lower()
                            year = pm.group(2)
                            month_map = {
                                "январ": "01", "феврал": "02", "март": "03", "апрел": "04",
                                "ма": "05", "июн": "06", "июл": "07", "август": "08",
                                "сентябр": "09", "октябр": "10", "ноябр": "11", "декабр": "12",
                                "january": "01", "february": "02", "march": "03", "april": "04",
                                "may": "05", "june": "06", "july": "07", "august": "08",
                                "september": "09", "october": "10", "november": "11", "december": "12",
                            }
                            for prefix, mm in month_map.items():
                                if month_str.startswith(prefix):
                                    period = f"{year}-{mm}"
                                    break
        except Exception:
            pass
        return company, period


# Singleton
doc_intelligence = DocumentIntelligence()
