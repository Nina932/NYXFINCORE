"""
Phase N-2: SmartPDFExtractor — Financial PDF Table Extraction
==============================================================
Extracts financial data from PDF documents (annual reports, 10-K, etc.)

Approach:
  1. pdfplumber table extraction (primary)
  2. Text-based regex fallback for unstructured PDFs
  3. Reuses SmartExcelParser's fuzzy matching for column mapping
  4. Supports Georgian/Russian/English text (UTF-8)

Returns same normalized Dict format as SmartExcelParser for seamless integration.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber not installed — PDF extraction unavailable")

from app.services.smart_excel_parser import (
    _fuzzy_match_column,
    _detect_header_row,
    compute_derived_metrics,
    ColumnMapping,
    ParsedSheet,
    ParseResult,
)


# ═══════════════════════════════════════════════════════════════════
# STATEMENT TYPE DETECTION
# ═══════════════════════════════════════════════════════════════════

_STATEMENT_KEYWORDS: Dict[str, List[str]] = {
    "income_statement": [
        "income statement", "profit and loss", "p&l", "statement of operations",
        "statement of income", "profit or loss",
        "მოგება-ზარალი", "მოგების ანგარიშგება",
        "отчет о прибылях", "отчет о финансовых результатах",
    ],
    "balance_sheet": [
        "balance sheet", "statement of financial position",
        "ბალანსი", "ფინანსური მდგომარეობა",
        "бухгалтерский баланс", "баланс",
    ],
    "cash_flow": [
        "cash flow", "statement of cash flows",
        "ფულადი ნაკადები",
        "движение денежных средств",
    ],
}


def _detect_statement_type(text: str) -> str:
    """Detect financial statement type from text content."""
    text_lower = text.lower()
    best_type = "unknown"
    best_score = 0

    for stype, keywords in _STATEMENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_type = stype

    return best_type


# ═══════════════════════════════════════════════════════════════════
# TEXT-BASED EXTRACTION (FALLBACK)
# ═══════════════════════════════════════════════════════════════════

# Patterns for line items: "Label    123,456" or "Label ... 123,456"
_LINE_ITEM_PATTERN = re.compile(
    r'^(.+?)\s{2,}[.\s]*'               # label + separator
    r'([\d,.\s]+(?:\.\d{1,2})?)\s*$',   # numeric value
    re.MULTILINE
)

# Known P&L line items for regex extraction
_PL_LINE_PATTERNS: Dict[str, List[str]] = {
    "revenue": [r"(?:total\s+)?(?:net\s+)?(?:revenue|sales|income|turnover)"],
    "cogs": [r"cost\s+of\s+(?:goods\s+)?(?:sold|sales|revenue)", r"cogs"],
    "gross_profit": [r"gross\s+(?:profit|income|margin)"],
    "ga_expenses": [r"(?:g&a|general|admin|operating)\s*(?:expenses|costs)"],
    "ebitda": [r"ebitda"],
    "depreciation": [r"depreciation(?:\s+(?:and|&)\s+amortization)?"],
    "net_profit": [r"net\s+(?:profit|income|earnings)", r"(?:profit|earnings)\s+after\s+tax"],
}


def _extract_from_text(text: str) -> Dict[str, Any]:
    """
    Extract financial data from unstructured text using regex patterns.
    Fallback when table extraction fails.
    """
    result: Dict[str, Any] = {}

    for field_name, patterns in _PL_LINE_PATTERNS.items():
        for pattern in patterns:
            full_pattern = rf'({pattern})\s*[:\s.]*\s*([\d,.\s]+)'
            match = re.search(full_pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(2).strip().replace(",", "").replace(" ", "")
                    value = float(value_str)
                    result[field_name] = value
                except (ValueError, IndexError):
                    pass
                break

    return result


# ═══════════════════════════════════════════════════════════════════
# SMART PDF EXTRACTOR
# ═══════════════════════════════════════════════════════════════════

class SmartPDFExtractor:
    """
    Extracts financial data from PDF documents.

    Strategy:
      1. Try pdfplumber table extraction
      2. If no tables found, fall back to text + regex
      3. Apply fuzzy column matching (same as SmartExcelParser)
      4. Compute derived metrics
    """

    def extract_file(self, path: str) -> ParseResult:
        """Extract from a PDF file on disk."""
        if not PDFPLUMBER_AVAILABLE:
            raise RuntimeError("pdfplumber required. Install: pip install pdfplumber")

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with pdfplumber.open(path) as pdf:
            return self._process_pdf(pdf, p.name)

    def extract_bytes(self, data: bytes, filename: str) -> ParseResult:
        """Extract from PDF bytes (HTTP upload)."""
        if not PDFPLUMBER_AVAILABLE:
            raise RuntimeError("pdfplumber required. Install: pip install pdfplumber")

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return self._process_pdf(pdf, filename)

    def _process_pdf(self, pdf, filename: str) -> ParseResult:
        """Process an opened PDF."""
        all_tables: List[List[List[str]]] = []
        all_text = ""
        warnings: List[str] = []

        for page_num, page in enumerate(pdf.pages):
            # Extract text for statement type detection
            page_text = page.extract_text() or ""
            all_text += page_text + "\n"

            # Extract tables
            tables = page.extract_tables() or []
            for table in tables:
                if table and len(table) > 1:  # need header + data
                    all_tables.append(table)

        # Detect statement type
        statement_type = _detect_statement_type(all_text)

        sheets: List[ParsedSheet] = []

        if all_tables:
            # Process each table as a "sheet"
            for idx, table in enumerate(all_tables):
                parsed = self._process_table(table, f"Table_{idx + 1}")
                if parsed.records:
                    sheets.append(parsed)

        if not sheets:
            # Fallback: regex extraction from text
            warnings.append("No tables found — using text extraction fallback")
            text_data = _extract_from_text(all_text)
            if text_data:
                sheet = ParsedSheet(
                    sheet_name="TextExtraction",
                    header_row=0,
                    column_mappings=[],
                    records=[text_data],
                    warnings=["Extracted via text regex (lower confidence)"],
                )
                sheets.append(sheet)

        return self._build_result(sheets, filename, statement_type, warnings)

    def _process_table(
        self, table: List[List[str]], sheet_name: str
    ) -> ParsedSheet:
        """Process a single extracted table."""
        warnings: List[str] = []

        # Clean table cells
        clean_table = []
        for row in table:
            clean_row = []
            for cell in row:
                if cell is None:
                    clean_row.append(None)
                else:
                    clean_row.append(str(cell).strip())
            clean_table.append(clean_row)

        # Detect header
        header_row = _detect_header_row(clean_table)
        headers = clean_table[header_row] if header_row < len(clean_table) else []

        # Map columns
        mappings: List[ColumnMapping] = []
        mapped_fields: Dict[str, int] = {}

        for i, header in enumerate(headers):
            header_str = str(header).strip() if header else ""
            field_name, confidence = _fuzzy_match_column(header_str)

            if field_name and field_name in mapped_fields:
                existing = mappings[mapped_fields[field_name]]
                if confidence <= existing.confidence:
                    field_name = None
                    confidence = 0

            mapping = ColumnMapping(
                source_index=i,
                source_header=header_str,
                canonical_field=field_name,
                confidence=confidence,
            )
            mappings.append(mapping)

            if field_name:
                mapped_fields[field_name] = i

        # Extract data rows
        records = []
        for row_idx in range(header_row + 1, len(clean_table)):
            row = clean_table[row_idx]
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue

            record: Dict[str, Any] = {}
            for mapping in mappings:
                if not mapping.canonical_field or mapping.source_index >= len(row):
                    continue
                val = row[mapping.source_index]
                if val is None or str(val).strip() == "":
                    continue

                # Try numeric conversion
                if mapping.canonical_field != "period":
                    try:
                        num_str = str(val).strip().replace(",", "").replace(" ", "").replace("\xa0", "")
                        record[mapping.canonical_field] = float(num_str)
                    except ValueError:
                        record[mapping.canonical_field] = val
                else:
                    record[mapping.canonical_field] = val

            # Skip total/summary rows
            first_cell = str(row[0]).strip().lower() if row and row[0] else ""
            if first_cell in ("total", "итого", "სულ", "grand total"):
                continue

            if record:
                records.append(record)

        return ParsedSheet(
            sheet_name=sheet_name,
            header_row=header_row,
            column_mappings=mappings,
            records=records,
            warnings=warnings,
        )

    def _build_result(
        self,
        sheets: List[ParsedSheet],
        filename: str,
        statement_type: str,
        warnings: List[str],
    ) -> ParseResult:
        """Build final result from extracted sheets."""
        all_records = []
        for sheet in sheets:
            all_records.extend(sheet.records)

        if len(all_records) == 1:
            merged = dict(all_records[0])
        elif all_records:
            merged: Dict[str, Any] = {}
            for rec in all_records:
                for k, v in rec.items():
                    if k == "period":
                        merged[k] = v
                    elif isinstance(v, (int, float)):
                        merged[k] = merged.get(k, 0) + v
                    else:
                        merged[k] = v
        else:
            merged = {}

        # Add detected statement type
        merged["_statement_type"] = statement_type

        # Compute derived metrics
        enriched, corrections = compute_derived_metrics(merged)

        # Overall confidence
        all_mappings = []
        for s in sheets:
            all_mappings.extend(s.column_mappings)
        mapped = [m for m in all_mappings if m.canonical_field]
        avg_conf = (sum(m.confidence for m in mapped) / len(mapped)) if mapped else 0

        # Lower confidence for text-extracted data
        if any(s.sheet_name == "TextExtraction" for s in sheets):
            avg_conf = min(avg_conf, 60)

        return ParseResult(
            filename=filename,
            file_type="pdf",
            sheets=sheets,
            normalized_financials=enriched,
            confidence_score=int(avg_conf),
            auto_corrections=corrections,
            warnings=warnings,
        )


# Module-level singleton
pdf_extractor = SmartPDFExtractor()
