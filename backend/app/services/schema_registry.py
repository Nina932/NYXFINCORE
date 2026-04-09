"""
schema_registry.py — Deterministic schema registry + strict validators for 1C exports.

Purpose:
- Enforce strict, auditable schemas per file type (TDSheet, BS mapping, Trial Balance, GL).
- Block uploads that don't match expected structure.
- Provide transparent validation results for ETL audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Iterable, Optional
import re


def _norm_header(h: str) -> str:
    h = (h or "").strip().lower()
    h = re.sub(r"\s+", " ", h)
    h = re.sub(r"[^\w\s\.-]", "", h)
    return h


def _norm_headers(headers: Iterable[str]) -> List[str]:
    return [_norm_header(h) for h in headers]


def _has_any(headers: List[str], options: Iterable[str]) -> bool:
    return any(_norm_header(o) in headers for o in options)


def _has_all(headers: List[str], options: Iterable[str]) -> bool:
    return all(_norm_header(o) in headers for o in options)


def _find_first_non_empty_row(rows: List[List]) -> Tuple[int, List[str]]:
    for i, row in enumerate(rows):
        if row and any(str(c).strip() for c in row):
            return i, [str(c) if c is not None else "" for c in row]
    return 0, []


@dataclass
class SheetSchema:
    name: str
    required_all: List[str] = field(default_factory=list)
    required_any_groups: List[List[str]] = field(default_factory=list)
    numeric_columns_any: List[str] = field(default_factory=list)

    def to_singer_schema(self) -> Dict:
        """Convert the sheet definition to a Singer-compatible JSON Schema."""
        properties = {}
        for group in self.required_any_groups:
            primary_header = group[0]
            if primary_header in self.numeric_columns_any:
                properties[primary_header] = {"type": ["null", "number"]}
            else:
                properties[primary_header] = {"type": ["null", "string"]}
        
        return {
            "type": "object",
            "properties": properties
        }

    def validate_headers(self, headers: List[str]) -> List[str]:
        errors = []
        nh = _norm_headers(headers)
        if self.required_all and not _has_all(nh, self.required_all):
            errors.append(f"missing_required_all: {self.required_all}")
        for group in self.required_any_groups:
            if not _has_any(nh, group):
                errors.append(f"missing_required_group: {group}")
        if self.numeric_columns_any and not _has_any(nh, self.numeric_columns_any):
            errors.append(f"missing_numeric_columns: {self.numeric_columns_any}")
        return errors


@dataclass
class SchemaValidationResult:
    ok: bool
    file_type: str
    sheet_results: List[Dict]
    errors: List[str]
    warnings: List[str]


class SchemaRegistry:
    """
    Registry of strict schemas for 1C exports.

    File types covered:
    - TDSheet / Trial Balance
    - Balance Sheet Mapping
    - GL Extract / Transaction Ledger
    - Revenue Breakdown
    - COGS Breakdown
    """

    def __init__(self) -> None:
        self.schemas: Dict[str, List[SheetSchema]] = {
            "trial_balance": [
                SheetSchema(
                    name="Trial Balance",
                    required_all=[],
                    required_any_groups=[
                        ["account code", "account", "счет", "код счета"],
                        ["account name", "account name rus", "наименование счета"],
                        ["opening debit", "opening dr", "сальдо дебет"],
                        ["opening credit", "opening cr", "сальдо кредит"],
                        ["turnover debit", "оборот дебет"],
                        ["turnover credit", "оборот кредит"],
                        ["closing debit", "closing dr", "сальдо дебет конечн"],
                        ["closing credit", "closing cr", "сальдо кредит конечн"],
                    ],
                    numeric_columns_any=[
                        "opening debit", "opening credit",
                        "turnover debit", "turnover credit",
                        "closing debit", "closing credit",
                    ],
                )
            ],
            "balance_sheet_mapping": [
                SheetSchema(
                    name="Balance Sheet Mapping",
                    required_any_groups=[
                        ["account code", "account", "счет", "код счета"],
                        ["ifrs", "mapping grp", "mapping group", "ifrs line", "ifrs mapping"],
                        ["baku", "mapping baku", "mr mapping", "mr code"],
                    ],
                    numeric_columns_any=["opening", "turnover debit", "turnover credit", "closing"],
                )
            ],
            "gl_extract": [
                SheetSchema(
                    name="GL Extract / Transactions",
                    required_any_groups=[
                        ["date", "period", "дата"],
                        ["amount", "amount gel", "сумма", "gel"],
                        ["account dr", "debit", "дебет", "account debit"],
                        ["account cr", "credit", "кредит", "account credit"],
                    ],
                    numeric_columns_any=["amount", "vat"],
                )
            ],
            "revenue_breakdown": [
                SheetSchema(
                    name="Revenue Breakdown",
                    required_any_groups=[
                        ["product", "product name", "номенклатура"],
                        ["gross", "amount", "amount gel", "валовая"],
                        ["net", "net revenue", "чистая"],
                    ],
                    numeric_columns_any=["gross", "net", "vat"],
                )
            ],
            "cogs_breakdown": [
                SheetSchema(
                    name="COGS Breakdown",
                    required_any_groups=[
                        ["product", "product name", "номенклатура"],
                        ["col k", "col6", "account 1610", "purchase cost"],
                        ["col l", "col7310", "transport", "logistics"],
                        ["col o", "col8230", "customs", "duties"],
                    ],
                    numeric_columns_any=["col k", "col l", "col o", "total"],
                )
            ],
        }

    def validate_workbook(self, sheet_rows: Dict[str, List[List]], file_hint: Optional[str] = None) -> SchemaValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        sheet_results: List[Dict] = []

        for sheet_name, rows in sheet_rows.items():
            _, header_row = _find_first_non_empty_row(rows)
            if not header_row:
                sheet_results.append({
                    "sheet": sheet_name,
                    "matched": None,
                    "errors": ["empty_sheet_or_no_header"],
                    "warnings": [],
                })
                continue

            best_match = None
            best_errors = None
            for ftype, schemas in self.schemas.items():
                for schema in schemas:
                    err = schema.validate_headers(header_row)
                    if not err and best_match is None:
                        best_match = ftype
                        best_errors = []
                    elif best_match is None and best_errors is None:
                        best_errors = err

            if best_match is None:
                sheet_results.append({
                    "sheet": sheet_name,
                    "matched": None,
                    "errors": best_errors or ["schema_not_matched"],
                    "warnings": [],
                })
            else:
                sheet_results.append({
                    "sheet": sheet_name,
                    "matched": best_match,
                    "errors": [],
                    "warnings": [],
                })

        matched_types = [r["matched"] for r in sheet_results if r["matched"]]
        file_type = matched_types[0] if matched_types else (file_hint or "unknown")

        for r in sheet_results:
            if r["matched"] is None:
                errors.append(f"Sheet '{r['sheet']}' does not match any registered schema.")

        ok = len(errors) == 0
        return SchemaValidationResult(
            ok=ok,
            file_type=file_type,
            sheet_results=sheet_results,
            errors=errors,
            warnings=warnings,
        )

    def discover_catalog(self, sheet_rows: Dict[str, List[List]]) -> Dict:
        """
        Industrial 'Discovery Mode' — Generates a Singer-compatible Catalog
        document representing the actual structure of the uploaded spreadsheets.
        """
        streams = []
        for sheet_name, rows in sheet_rows.items():
            _, header_row = _find_first_non_empty_row(rows)
            # Find the best matching registered schema to use as a baseline
            matched_schema = None
            for ftype, schemas in self.schemas.items():
                for schema in schemas:
                    if not schema.validate_headers(header_row):
                        matched_schema = schema
                        break
            
            # Generate the stream schema
            schema_json = {}
            if matched_schema:
                schema_json = matched_schema.to_singer_schema()
            else:
                # Dynamic discovery for unknown schemas
                props = {h: {"type": ["null", "string"]} for h in header_row if h}
                schema_json = {"type": "object", "properties": props}

            streams.append({
                "stream": sheet_name,
                "tap_stream_id": sheet_name.lower().replace(" ", "_"),
                "schema": schema_json,
                "metadata": [
                    {
                        "breadcrumb": [],
                        "metadata": {
                            "selected": True,
                            "inclusion": "available"
                        }
                    }
                ]
            })
        
        return {"streams": streams}
