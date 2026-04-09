"""
1C Trial Balance Parser — Parses Оборотно-сальдовая ведомость files.

Handles the standard 1C TB export format:
  - Header: Company name, report title, period
  - Column headers: Счет (Code, Name), Сальдо на начало (Opening Dr/Cr),
    Оборот за период (Turnover Dr/Cr), Сальдо на конец (Closing Dr/Cr)
  - Data rows: Account codes (4-digit Georgian or 2-digit Russian) with balances
  - Sub-account details: Counterparty/station breakdowns (skipped for aggregation)
  - Group headers: Codes ending in XX (e.g., 11XX) — kept for hierarchy context
  - Totals row: Bottom row with balanced totals
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TBRow:
    """A single trial balance account row."""
    account_code: str
    account_name: str
    name_ka: str = ""           # Georgian name
    name_ru: str = ""           # Russian name
    is_group: bool = False      # True for group headers (11XX, 14X, etc.)
    opening_debit: float = 0.0
    opening_credit: float = 0.0
    turnover_debit: float = 0.0
    turnover_credit: float = 0.0
    closing_debit: float = 0.0
    closing_credit: float = 0.0

    @property
    def opening_balance(self) -> float:
        return self.opening_debit - self.opening_credit

    @property
    def turnover_net(self) -> float:
        return self.turnover_debit - self.turnover_credit

    @property
    def closing_balance(self) -> float:
        return self.closing_debit - self.closing_credit

    @property
    def account_class(self) -> str:
        """First digit of account code — determines BS/PL classification."""
        for ch in self.account_code:
            if ch.isdigit():
                return ch
        return "0"


@dataclass
class TBParseResult:
    """Result of parsing a 1C Trial Balance file."""
    detected: bool = False
    rows: List[TBRow] = field(default_factory=list)
    company: str = ""
    period: str = ""
    total_opening_debit: float = 0.0
    total_opening_credit: float = 0.0
    total_turnover_debit: float = 0.0
    total_turnover_credit: float = 0.0
    total_closing_debit: float = 0.0
    total_closing_credit: float = 0.0
    is_balanced: bool = False
    account_count: int = 0
    postable_count: int = 0     # Leaf accounts (not groups)
    warnings: List[str] = field(default_factory=list)
    sheet_name: str = ""

    @property
    def group_rows(self) -> List[TBRow]:
        return [r for r in self.rows if r.is_group]

    @property
    def postable_rows(self) -> List[TBRow]:
        return [r for r in self.rows if not r.is_group]


class TBParser:
    """Parser for 1C Trial Balance (Оборотно-сальдовая ведомость) files."""

    # Column indices for standard 1C TB format (0-indexed)
    # These are auto-detected but these are common defaults
    COL_CODE = 2
    COL_NAME = 3
    COL_SUBACCOUNT = 4

    def detect_and_parse(self, file_path: str) -> Optional[TBParseResult]:
        """Detect if file is a TB and parse it. Returns None if not a TB."""
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            logger.warning("TBParser: cannot open %s: %s", file_path, e)
            return None

        for sheet_name in xls.sheet_names:
            result = self._try_parse_sheet(xls, sheet_name)
            if result and result.detected:
                return result

        return None

    def _try_parse_sheet(self, xls: pd.ExcelFile, sheet_name: str) -> Optional[TBParseResult]:
        """Try to parse a single sheet as a trial balance."""
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        except Exception:
            return None

        # Step 1: Detect TB format by scanning header rows
        header_row, col_map = self._detect_columns(df)
        if header_row < 0:
            return None

        result = TBParseResult(detected=True, sheet_name=sheet_name)

        # Step 2: Extract metadata from header rows
        result.company, result.period = self._extract_metadata(df, header_row)

        # Step 3: Parse data rows
        code_col = col_map.get("code", 2)
        name_col = col_map.get("name", 3)
        sub_col = col_map.get("sub", 4)
        od_col = col_map.get("opening_debit", 6)
        oc_col = col_map.get("opening_credit", 7)
        td_col = col_map.get("turnover_debit", 10)
        tc_col = col_map.get("turnover_credit", 13)
        cd_col = col_map.get("closing_debit", 14)
        cc_col = col_map.get("closing_credit", 16)

        data_start = header_row + 1
        for i in range(data_start, len(df)):
            code = self._safe_str(df, i, code_col)
            name = self._safe_str(df, i, name_col)
            sub = self._safe_str(df, i, sub_col)

            # Skip empty rows
            if not code and not name and not sub:
                continue

            # Skip sub-account detail rows (col 4 populated, col 2 empty)
            if not code and sub:
                continue

            # Skip if this looks like a totals row (no code, just numbers)
            if not code and not name:
                continue

            # Check for totals row (last row with balanced numbers, no code)
            if not code and not name:
                # This might be the totals row
                od = self._safe_float(df, i, od_col)
                oc = self._safe_float(df, i, oc_col)
                if od > 0 and oc > 0 and abs(od - oc) < 1.0:
                    result.total_opening_debit = od
                    result.total_opening_credit = oc
                    result.total_turnover_debit = self._safe_float(df, i, td_col)
                    result.total_turnover_credit = self._safe_float(df, i, tc_col)
                    result.total_closing_debit = self._safe_float(df, i, cd_col)
                    result.total_closing_credit = self._safe_float(df, i, cc_col)
                    continue

            if not code:
                continue

            # Detect group vs postable
            is_group = bool(re.search(r'[Xx]', code))

            # Parse bilingual name
            name_ka, name_ru = self._split_bilingual(name)

            row = TBRow(
                account_code=code.strip(),
                account_name=name.strip(),
                name_ka=name_ka,
                name_ru=name_ru,
                is_group=is_group,
                opening_debit=self._safe_float(df, i, od_col),
                opening_credit=self._safe_float(df, i, oc_col),
                turnover_debit=self._safe_float(df, i, td_col),
                turnover_credit=self._safe_float(df, i, tc_col),
                closing_debit=self._safe_float(df, i, cd_col),
                closing_credit=self._safe_float(df, i, cc_col),
            )
            result.rows.append(row)

        # Step 4: Extract totals from last row if not already found
        if result.total_closing_debit == 0:
            for i in range(len(df) - 1, max(len(df) - 5, 0), -1):
                od = self._safe_float(df, i, od_col)
                oc = self._safe_float(df, i, oc_col)
                cd = self._safe_float(df, i, cd_col)
                cc = self._safe_float(df, i, cc_col)
                if od > 0 and oc > 0:
                    result.total_opening_debit = od
                    result.total_opening_credit = oc
                    result.total_turnover_debit = self._safe_float(df, i, td_col)
                    result.total_turnover_credit = self._safe_float(df, i, tc_col)
                    result.total_closing_debit = cd
                    result.total_closing_credit = cc
                    break

        # Step 5: Compute stats
        result.account_count = len(result.rows)
        result.postable_count = len(result.postable_rows)
        result.is_balanced = (
            abs(result.total_closing_debit - result.total_closing_credit) < 1.0
            if result.total_closing_debit > 0
            else False
        )

        if not result.is_balanced and result.total_closing_debit > 0:
            diff = abs(result.total_closing_debit - result.total_closing_credit)
            result.warnings.append(f"TB not balanced: diff={diff:.2f}")

        logger.info(
            "TBParser: parsed %d accounts (%d postable) for %s period %s, balanced=%s",
            result.account_count, result.postable_count,
            result.company, result.period, result.is_balanced,
        )
        return result

    def _detect_columns(self, df: pd.DataFrame) -> Tuple[int, Dict[str, int]]:
        """Find header row and column mapping. Returns (header_row, col_map) or (-1, {})."""
        for i in range(min(15, len(df))):
            row_text = ""
            for c in range(df.shape[1]):
                v = df.iloc[i, c]
                if pd.notna(v):
                    row_text += " " + str(v).lower()

            # Look for the column header row with "Код" and "Наименование" or "Дебет"/"Кредит"
            if ("код" in row_text and "наименование" in row_text) or \
               ("code" in row_text and "name" in row_text):
                # Found header row — detect column positions
                col_map = {"code": 2, "name": 3, "sub": 4}

                for c in range(df.shape[1]):
                    v = str(df.iloc[i, c]).lower() if pd.notna(df.iloc[i, c]) else ""
                    if v in ("код", "code"):
                        col_map["code"] = c
                    elif v in ("наименование", "name"):
                        col_map["name"] = c

                # Look for debit/credit columns in this row AND the row above
                # Row above has section headers: "Сальдо на начало", "Оборот", "Сальдо на конец"
                if i > 0:
                    for c in range(df.shape[1]):
                        v = str(df.iloc[i, c]).lower() if pd.notna(df.iloc[i, c]) else ""
                        v_above = str(df.iloc[i-1, c]).lower() if pd.notna(df.iloc[i-1, c]) else ""

                        if v == "дебет" or v == "debit":
                            if "начало" in v_above or "opening" in v_above or "сальдо на начало" in v_above:
                                col_map["opening_debit"] = c
                            elif "оборот" in v_above or "turnover" in v_above:
                                col_map["turnover_debit"] = c
                            elif "конец" in v_above or "closing" in v_above or "сальдо на конец" in v_above:
                                col_map["closing_debit"] = c
                            elif "opening_debit" not in col_map:
                                col_map["opening_debit"] = c
                            elif "turnover_debit" not in col_map:
                                col_map["turnover_debit"] = c
                            elif "closing_debit" not in col_map:
                                col_map["closing_debit"] = c

                        if v == "кредит" or v == "credit":
                            if "начало" in v_above or "opening" in v_above or "сальдо на начало" in v_above:
                                col_map["opening_credit"] = c
                            elif "оборот" in v_above or "turnover" in v_above:
                                col_map["turnover_credit"] = c
                            elif "конец" in v_above or "closing" in v_above or "сальдо на конец" in v_above:
                                col_map["closing_credit"] = c
                            elif "opening_credit" not in col_map:
                                col_map["opening_credit"] = c
                            elif "turnover_credit" not in col_map:
                                col_map["turnover_credit"] = c
                            elif "closing_credit" not in col_map:
                                col_map["closing_credit"] = c

                # Use defaults for any missing columns
                col_map.setdefault("opening_debit", 6)
                col_map.setdefault("opening_credit", 7)
                col_map.setdefault("turnover_debit", 10)
                col_map.setdefault("turnover_credit", 13)
                col_map.setdefault("closing_debit", 14)
                col_map.setdefault("closing_credit", 16)

                return i, col_map

        # Fallback: check if "Оборотно-сальдовая" appears anywhere
        for i in range(min(10, len(df))):
            for c in range(df.shape[1]):
                v = str(df.iloc[i, c]).lower() if pd.notna(df.iloc[i, c]) else ""
                if "оборотно-сальдовая" in v or "trial balance" in v:
                    # Found TB title — assume standard 1C layout
                    return max(i + 4, 6), {
                        "code": 2, "name": 3, "sub": 4,
                        "opening_debit": 6, "opening_credit": 7,
                        "turnover_debit": 10, "turnover_credit": 13,
                        "closing_debit": 14, "closing_credit": 16,
                    }

        return -1, {}

    def _extract_metadata(self, df: pd.DataFrame, header_row: int) -> Tuple[str, str]:
        """Extract company and period from rows above the header."""
        company = ""
        period = ""

        for i in range(min(header_row, 10)):
            for c in range(df.shape[1]):
                v = df.iloc[i, c]
                if pd.notna(v):
                    s = str(v)

                    # Company: Georgian text // Russian text
                    if "//" in s and not company:
                        company = s.split("//")[0].strip()

                    # Period: "Период: Январь 2025 г."
                    pm = re.search(
                        r'(?:Период|Period)[:\s]*(Январ[ья]|Феврал[ья]|Март[а]?|Апрел[ья]|Ма[йя]|Июн[ья]|Июл[ья]|Август[а]?|Сентябр[ья]|Октябр[ья]|Ноябр[ья]|Декабр[ья]|'
                        r'January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})',
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

        return company, period

    @staticmethod
    def _safe_str(df: pd.DataFrame, row: int, col: int) -> str:
        if col >= df.shape[1]:
            return ""
        v = df.iloc[row, col]
        return str(v).strip() if pd.notna(v) else ""

    @staticmethod
    def _safe_float(df: pd.DataFrame, row: int, col: int) -> float:
        if col >= df.shape[1]:
            return 0.0
        v = df.iloc[row, col]
        if pd.notna(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    @staticmethod
    def _split_bilingual(name: str) -> Tuple[str, str]:
        """Split 'Georgian // Russian' or 'Georgian / Russian' names."""
        if "//" in name:
            parts = name.split("//", 1)
            return parts[0].strip(), parts[1].strip()
        if " / " in name:
            parts = name.split(" / ", 1)
            return parts[0].strip(), parts[1].strip()
        return name.strip(), ""


# Singleton
tb_parser = TBParser()
