"""
Transaction / Journal Entry Parser — Parses GL journal entries from Excel files.

Detects and parses files with transaction-level data:
  - Date, Dr Account, Cr Account, Amount
  - Or: Date, Account, Debit, Credit (single-line format)

Feeds parsed transactions into GLPipeline for TB → Statements conversion.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ParsedTransaction:
    date: str = ""
    acct_dr: str = ""
    acct_cr: str = ""
    amount: float = 0.0
    description: str = ""


@dataclass
class TransactionParseResult:
    detected: bool = False
    transactions: List[ParsedTransaction] = field(default_factory=list)
    company: str = ""
    period: str = ""
    warnings: List[str] = field(default_factory=list)

    @property
    def as_gl_input(self) -> List[Dict]:
        """Convert to GLPipeline input format."""
        return [
            {"acct_dr": t.acct_dr, "acct_cr": t.acct_cr, "amount": t.amount}
            for t in self.transactions
            if t.acct_dr and t.acct_cr and t.amount > 0
        ]


class TransactionParser:
    """Parser for GL journal entry / transaction files."""

    # Keywords that indicate a transaction/journal file
    DETECT_KEYWORDS = [
        "журнал операций", "журнал проводок", "journal entries",
        "хозяйственные операции", "проводки", "transaction log",
    ]

    # Column name patterns
    DATE_PATTERNS = ["дата", "date", "period"]
    DR_PATTERNS = ["дебет", "дт", "debit", "dr", "счет дт", "account dr"]
    CR_PATTERNS = ["кредит", "кт", "credit", "cr", "счет кт", "account cr"]
    AMOUNT_PATTERNS = ["сумма", "amount", "sum"]
    DESC_PATTERNS = ["описание", "содержание", "description", "memo", "назначение"]

    def detect_and_parse(self, file_path: str) -> Optional[TransactionParseResult]:
        """Try to detect and parse a transaction file."""
        try:
            xls = pd.ExcelFile(file_path)
        except Exception:
            return None

        for sheet_name in xls.sheet_names:
            result = self._try_parse_sheet(xls, sheet_name)
            if result and result.detected:
                return result

        return None

    def _try_parse_sheet(self, xls: pd.ExcelFile, sheet_name: str) -> Optional[TransactionParseResult]:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=20)
        except Exception:
            return None

        # Check for transaction keywords
        text = ""
        for i in range(min(10, len(df))):
            for c in range(df.shape[1]):
                v = df.iloc[i, c]
                if pd.notna(v):
                    text += " " + str(v).lower()

        if not any(kw in text for kw in self.DETECT_KEYWORDS):
            # Also check if columns look like date + dr + cr + amount
            has_date = any(p in text for p in self.DATE_PATTERNS)
            has_dr = any(p in text for p in self.DR_PATTERNS)
            has_cr = any(p in text for p in self.CR_PATTERNS)
            has_amount = any(p in text for p in self.AMOUNT_PATTERNS)
            if not (has_date and has_dr and has_cr and has_amount):
                return None

        # Find header row and column mapping
        header_row, col_map = self._detect_columns(df)
        if header_row < 0:
            return None

        # Read full sheet
        df_full = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        result = TransactionParseResult(detected=True)

        date_col = col_map.get("date", 0)
        dr_col = col_map.get("dr", 1)
        cr_col = col_map.get("cr", 2)
        amount_col = col_map.get("amount", 3)
        desc_col = col_map.get("desc")

        for i in range(header_row + 1, len(df_full)):
            dr = self._safe_str(df_full, i, dr_col)
            cr = self._safe_str(df_full, i, cr_col)
            amount = self._safe_float(df_full, i, amount_col)

            if not dr or not cr or amount == 0:
                continue

            txn = ParsedTransaction(
                date=self._safe_str(df_full, i, date_col),
                acct_dr=dr,
                acct_cr=cr,
                amount=abs(amount),
                description=self._safe_str(df_full, i, desc_col) if desc_col is not None else "",
            )
            result.transactions.append(txn)

        if len(result.transactions) < 2:
            return None

        logger.info("TransactionParser: parsed %d transactions from sheet '%s'",
                     len(result.transactions), sheet_name)
        return result

    def _detect_columns(self, df: pd.DataFrame):
        """Find header row and column positions."""
        for i in range(min(15, len(df))):
            col_map = {}
            for c in range(df.shape[1]):
                v = str(df.iloc[i, c]).lower() if pd.notna(df.iloc[i, c]) else ""
                if any(p in v for p in self.DATE_PATTERNS):
                    col_map["date"] = c
                elif any(p in v for p in self.DR_PATTERNS) and "dr" not in col_map:
                    col_map["dr"] = c
                elif any(p in v for p in self.CR_PATTERNS) and "cr" not in col_map:
                    col_map["cr"] = c
                elif any(p in v for p in self.AMOUNT_PATTERNS):
                    col_map["amount"] = c
                elif any(p in v for p in self.DESC_PATTERNS):
                    col_map["desc"] = c

            if "dr" in col_map and "cr" in col_map and "amount" in col_map:
                return i, col_map

        return -1, {}

    @staticmethod
    def _safe_str(df, row, col):
        if col >= df.shape[1]:
            return ""
        v = df.iloc[row, col]
        return str(v).strip() if pd.notna(v) else ""

    @staticmethod
    def _safe_float(df, row, col):
        if col >= df.shape[1]:
            return 0.0
        v = df.iloc[row, col]
        try:
            return float(v) if pd.notna(v) else 0.0
        except (ValueError, TypeError):
            return 0.0


# Singleton
transaction_parser = TransactionParser()
