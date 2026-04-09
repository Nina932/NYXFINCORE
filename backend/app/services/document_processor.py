"""
FinAI Document Intelligence Engine -- Palantir AIP Document Intelligence pattern.

Two-stage pipeline:
  Stage 1: Text extraction (PDF via PyMuPDF, images via OCR stub, Excel via existing parsers)
  Stage 2: AI-powered structured extraction with schema validation and confidence scoring

Supports: Invoice, Contract, Bank Statement, Receipt document types.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
#  Document Status
# ============================================================================

class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"


# ============================================================================
#  DocumentRecord
# ============================================================================

@dataclass
class DocumentRecord:
    id: str
    filename: str
    file_type: str                                 # pdf, png, jpg, xlsx, csv
    document_type: str                             # invoice, contract, bank_statement, receipt, unknown
    raw_text: str = ""
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    status: DocumentStatus = DocumentStatus.UPLOADED
    created_at: str = ""
    updated_at: str = ""
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# ============================================================================
#  Extraction Schemas
# ============================================================================

EXTRACTION_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "invoice": {
        "fields": {
            "vendor_name": {"type": "string", "required": True, "description": "Name of the vendor/supplier"},
            "invoice_number": {"type": "string", "required": True, "description": "Unique invoice identifier"},
            "date": {"type": "date", "required": True, "description": "Invoice issue date (YYYY-MM-DD)"},
            "due_date": {"type": "date", "required": False, "description": "Payment due date (YYYY-MM-DD)"},
            "currency": {"type": "string", "required": False, "description": "Currency code (e.g. GEL, USD, EUR)"},
            "line_items": {
                "type": "array",
                "required": True,
                "description": "List of line items",
                "item_fields": {
                    "description": "string",
                    "quantity": "number",
                    "unit_price": "number",
                    "amount": "number",
                },
            },
            "subtotal": {"type": "number", "required": True, "description": "Sum of line item amounts before tax"},
            "tax_amount": {"type": "number", "required": False, "description": "Tax amount"},
            "total_amount": {"type": "number", "required": True, "description": "Total amount including tax"},
            "payment_terms": {"type": "string", "required": False, "description": "Payment terms (e.g. Net 30)"},
        },
    },
    "contract": {
        "fields": {
            "parties": {
                "type": "array",
                "required": True,
                "description": "List of contracting parties (names)",
                "item_fields": {"name": "string", "role": "string"},
            },
            "effective_date": {"type": "date", "required": True, "description": "Contract start date (YYYY-MM-DD)"},
            "expiration_date": {"type": "date", "required": False, "description": "Contract end date (YYYY-MM-DD)"},
            "value": {"type": "number", "required": False, "description": "Total contract monetary value"},
            "currency": {"type": "string", "required": False, "description": "Currency code"},
            "key_terms": {
                "type": "array",
                "required": False,
                "description": "Key contractual terms and conditions",
                "item_fields": {"term": "string"},
            },
            "governing_law": {"type": "string", "required": False, "description": "Governing law jurisdiction"},
        },
    },
    "bank_statement": {
        "fields": {
            "bank_name": {"type": "string", "required": True, "description": "Name of the bank"},
            "account_number": {"type": "string", "required": True, "description": "Account number (last 4 digits OK)"},
            "period_start": {"type": "date", "required": True, "description": "Statement period start (YYYY-MM-DD)"},
            "period_end": {"type": "date", "required": True, "description": "Statement period end (YYYY-MM-DD)"},
            "opening_balance": {"type": "number", "required": True, "description": "Opening balance"},
            "closing_balance": {"type": "number", "required": True, "description": "Closing balance"},
            "transactions": {
                "type": "array",
                "required": False,
                "description": "List of transactions",
                "item_fields": {
                    "date": "date",
                    "description": "string",
                    "amount": "number",
                    "type": "string",  # debit or credit
                },
            },
        },
    },
    "receipt": {
        "fields": {
            "merchant": {"type": "string", "required": True, "description": "Merchant/store name"},
            "date": {"type": "date", "required": True, "description": "Transaction date (YYYY-MM-DD)"},
            "items": {
                "type": "array",
                "required": False,
                "description": "Purchased items",
                "item_fields": {
                    "description": "string",
                    "quantity": "number",
                    "unit_price": "number",
                    "amount": "number",
                },
            },
            "subtotal": {"type": "number", "required": False, "description": "Subtotal before tax"},
            "tax": {"type": "number", "required": False, "description": "Tax amount"},
            "total": {"type": "number", "required": True, "description": "Total amount paid"},
            "payment_method": {"type": "string", "required": False, "description": "Payment method (cash, card, etc.)"},
        },
    },
}


# ============================================================================
#  Text Extraction (Stage 1)
# ============================================================================

class TextExtractor:
    """Multi-format text extraction with graceful fallbacks."""

    def extract(self, file_bytes: bytes, filename: str) -> Tuple[str, str]:
        """Extract text from file bytes. Returns (raw_text, file_type)."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext == "pdf":
            return self._extract_pdf(file_bytes), "pdf"
        elif ext in ("png", "jpg", "jpeg", "tiff", "bmp"):
            return self._extract_image(file_bytes), ext
        elif ext in ("xlsx", "xls"):
            return self._extract_excel(file_bytes), ext
        elif ext == "csv":
            return self._extract_csv(file_bytes), "csv"
        elif ext == "txt":
            return file_bytes.decode("utf-8", errors="replace"), "txt"
        else:
            # Try as text
            try:
                return file_bytes.decode("utf-8", errors="replace"), ext or "unknown"
            except Exception:
                return "", ext or "unknown"

    def _extract_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF using PyMuPDF (fitz) with fallback."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
            doc.close()

            if text_parts:
                return "\n\n".join(text_parts)

            # If no text extracted (scanned PDF), try extracting from images
            logger.info("PDF has no extractable text; may be scanned/image-based")
            return "[PDF contains scanned images; OCR required for text extraction]"

        except ImportError:
            logger.warning("PyMuPDF (fitz) not installed; PDF text extraction unavailable")
            return "[PDF extraction requires PyMuPDF: pip install PyMuPDF]"
        except Exception as e:
            logger.error("PDF extraction error: %s", e)
            return f"[PDF extraction error: {e}]"

    def _extract_image(self, file_bytes: bytes) -> str:
        """Extract text from image via OCR with graceful fallback."""
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image, lang="eng+kat+rus")
            if text.strip():
                return text
            return "[Image OCR produced no text; document may be illegible]"

        except ImportError:
            logger.warning("pytesseract/Pillow not installed; image OCR unavailable")
            return "[Image OCR requires: pip install pytesseract Pillow]"
        except Exception as e:
            logger.error("Image OCR error: %s", e)
            return f"[Image OCR error: {e}]"

    def _extract_excel(self, file_bytes: bytes) -> str:
        """Extract text from Excel by reading all sheets into a text representation."""
        try:
            import pandas as pd

            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            text_parts = []
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                text_parts.append(f"--- Sheet: {sheet_name} ---")
                for i in range(len(df)):
                    row_vals = []
                    for c in range(df.shape[1]):
                        v = df.iloc[i, c]
                        if pd.notna(v):
                            row_vals.append(str(v))
                    if row_vals:
                        text_parts.append(" | ".join(row_vals))
            return "\n".join(text_parts)
        except Exception as e:
            logger.error("Excel extraction error: %s", e)
            return f"[Excel extraction error: {e}]"

    def _extract_csv(self, file_bytes: bytes) -> str:
        """Extract text from CSV."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            return text
        except Exception as e:
            return f"[CSV extraction error: {e}]"


# ============================================================================
#  Document Type Detector
# ============================================================================

class DocumentTypeDetector:
    """Classify document type from extracted text using keyword scoring."""

    INVOICE_KEYWORDS = [
        "invoice", "inv #", "inv#", "bill to", "ship to", "subtotal",
        "tax", "total due", "payment terms", "net 30", "net 60",
        "unit price", "quantity", "line item", "amount due",
        "invoice number", "invoice date", "due date",
        # Georgian / Russian
        "ინვოისი", "გადასახადი", "счёт-фактура", "счет-фактура",
        "итого", "сумма", "к оплате",
    ]

    CONTRACT_KEYWORDS = [
        "agreement", "contract", "parties", "hereinafter",
        "effective date", "term", "termination", "governing law",
        "jurisdiction", "obligations", "representations", "warranties",
        "confidential", "indemnif", "force majeure", "amendment",
        "whereas", "hereby", "witnesseth",
        # Georgian
        "ხელშეკრულება", "მხარეები", "ვადა",
    ]

    BANK_STATEMENT_KEYWORDS = [
        "bank statement", "account statement", "opening balance",
        "closing balance", "account number", "iban", "swift",
        "transaction", "credit", "debit", "balance brought forward",
        "statement period", "available balance",
        # Georgian / Russian
        "ბანკის ამონაწერი", "ანგარიშის ნომერი",
        "выписка", "остаток",
    ]

    RECEIPT_KEYWORDS = [
        "receipt", "cash register", "change", "paid",
        "payment method", "card", "cash", "subtotal",
        "thank you", "cashier", "store #", "pos",
        # Georgian
        "ქვითარი", "გადახდა",
    ]

    def detect(self, text: str, filename: str = "") -> Tuple[str, float]:
        """Returns (document_type, confidence)."""
        text_lower = text.lower()
        fn_lower = filename.lower()

        scores = {
            "invoice": self._score(text_lower, fn_lower, self.INVOICE_KEYWORDS, ["invoice", "inv"]),
            "contract": self._score(text_lower, fn_lower, self.CONTRACT_KEYWORDS, ["contract", "agreement"]),
            "bank_statement": self._score(text_lower, fn_lower, self.BANK_STATEMENT_KEYWORDS, ["statement", "bank"]),
            "receipt": self._score(text_lower, fn_lower, self.RECEIPT_KEYWORDS, ["receipt"]),
        }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score < 0.15:
            return "unknown", 0.0

        return best_type, min(best_score, 1.0)

    def _score(self, text: str, filename: str, keywords: List[str], fn_hints: List[str]) -> float:
        score = 0.0
        # Filename hint
        for hint in fn_hints:
            if hint in filename:
                score += 0.2

        # Keyword frequency
        hits = 0
        for kw in keywords:
            if kw in text:
                hits += 1
        # Normalize: 3+ hits = high confidence
        if hits >= 5:
            score += 0.6
        elif hits >= 3:
            score += 0.4
        elif hits >= 1:
            score += 0.2

        return score


# ============================================================================
#  Deterministic Validators
# ============================================================================

class InvoiceValidator:
    """Validates extracted invoice data for arithmetic consistency."""

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []

        line_items = data.get("line_items", [])
        subtotal = _to_float(data.get("subtotal"))
        tax_amount = _to_float(data.get("tax_amount"))
        total_amount = _to_float(data.get("total_amount"))

        # 1. Validate each line item: qty * unit_price == amount
        for i, item in enumerate(line_items):
            qty = _to_float(item.get("quantity"))
            price = _to_float(item.get("unit_price"))
            amount = _to_float(item.get("amount"))
            if qty is not None and price is not None and amount is not None:
                expected = round(qty * price, 2)
                if abs(expected - amount) > 0.02:
                    errors.append(
                        f"Line item {i + 1}: qty({qty}) x price({price}) = {expected}, "
                        f"but amount is {amount}"
                    )

        # 2. Line items sum == subtotal
        if line_items and subtotal is not None:
            items_sum = sum(_to_float(item.get("amount")) or 0.0 for item in line_items)
            items_sum = round(items_sum, 2)
            if abs(items_sum - subtotal) > 0.05:
                errors.append(
                    f"Line items sum ({items_sum}) != subtotal ({subtotal})"
                )

        # 3. Tax rate sanity (0-30%)
        if subtotal is not None and tax_amount is not None and subtotal > 0:
            tax_rate = tax_amount / subtotal
            if tax_rate > 0.30:
                errors.append(
                    f"Tax rate {tax_rate:.1%} exceeds 30% -- possibly incorrect"
                )
            if tax_rate < 0 and tax_amount != 0:
                errors.append(f"Negative tax rate detected: {tax_rate:.1%}")

        # 4. Total == subtotal + tax
        if subtotal is not None and total_amount is not None:
            tax = tax_amount if tax_amount is not None else 0.0
            expected_total = round(subtotal + tax, 2)
            if abs(expected_total - total_amount) > 0.05:
                errors.append(
                    f"subtotal({subtotal}) + tax({tax}) = {expected_total}, "
                    f"but total is {total_amount}"
                )

        return errors


class ArithmeticValidator:
    """Generic arithmetic consistency checker for any extracted data."""

    def validate_sum(self, items: List[Dict], amount_field: str, expected_total: float) -> List[str]:
        """Check that sum of items[amount_field] equals expected_total."""
        errors = []
        actual_sum = 0.0
        for i, item in enumerate(items):
            val = _to_float(item.get(amount_field))
            if val is not None:
                actual_sum += val
        actual_sum = round(actual_sum, 2)
        if abs(actual_sum - expected_total) > 0.05:
            errors.append(
                f"Sum of '{amount_field}' ({actual_sum}) != expected total ({expected_total})"
            )
        return errors

    def validate_bank_statement(self, data: Dict[str, Any]) -> List[str]:
        """Validate bank statement: opening + sum(transactions) == closing."""
        errors = []
        opening = _to_float(data.get("opening_balance"))
        closing = _to_float(data.get("closing_balance"))
        transactions = data.get("transactions", [])

        if opening is not None and closing is not None and transactions:
            net_flow = 0.0
            for txn in transactions:
                amount = _to_float(txn.get("amount"))
                if amount is None:
                    continue
                txn_type = str(txn.get("type", "")).lower()
                if txn_type in ("credit", "cr", "deposit"):
                    net_flow += amount
                elif txn_type in ("debit", "dr", "withdrawal"):
                    net_flow -= amount
                else:
                    # If type unknown, use sign: positive = credit, negative = debit
                    net_flow += amount

            expected_closing = round(opening + net_flow, 2)
            if abs(expected_closing - closing) > 0.10:
                errors.append(
                    f"Opening({opening}) + net transactions({round(net_flow, 2)}) = "
                    f"{expected_closing}, but closing balance is {closing}"
                )

        return errors


class DuplicateDetector:
    """Detects duplicate documents based on key fields."""

    def __init__(self):
        self._seen_invoices: Dict[str, str] = {}  # "vendor|number" -> doc_id

    def check_invoice(self, vendor_name: str, invoice_number: str, doc_id: str) -> Optional[str]:
        """Returns existing doc_id if duplicate, else None. Registers this doc."""
        if not vendor_name or not invoice_number:
            return None
        key = f"{vendor_name.strip().lower()}|{invoice_number.strip().lower()}"
        existing = self._seen_invoices.get(key)
        if existing and existing != doc_id:
            return existing
        self._seen_invoices[key] = doc_id
        return None

    def check_receipt(self, merchant: str, date_str: str, total: float, doc_id: str) -> Optional[str]:
        """Check for duplicate receipt by merchant + date + total."""
        if not merchant or not date_str:
            return None
        key = f"{merchant.strip().lower()}|{date_str}|{total:.2f}"
        existing = self._seen_invoices.get(key)
        if existing and existing != doc_id:
            return existing
        self._seen_invoices[key] = doc_id
        return None


# ============================================================================
#  Confidence Scorer
# ============================================================================

class ConfidenceScorer:
    """Compute per-field confidence by checking if extracted values appear in raw text."""

    def score(self, extracted: Dict[str, Any], raw_text: str, schema_fields: Dict) -> Dict[str, float]:
        """Returns {field_name: confidence_0_to_1}."""
        scores = {}
        text_lower = raw_text.lower()

        for field_name, field_def in schema_fields.items():
            value = extracted.get(field_name)
            if value is None or value == "" or value == []:
                # Missing field
                if isinstance(field_def, dict) and field_def.get("required"):
                    scores[field_name] = 0.0
                else:
                    scores[field_name] = 0.5  # Optional, absence is acceptable
                continue

            if isinstance(value, list):
                # Array field: score based on whether individual items have text matches
                if len(value) == 0:
                    scores[field_name] = 0.3
                else:
                    item_scores = []
                    for item in value:
                        if isinstance(item, dict):
                            item_score = self._score_dict_item(item, text_lower)
                        else:
                            item_score = self._score_value(str(item), text_lower)
                        item_scores.append(item_score)
                    scores[field_name] = round(sum(item_scores) / len(item_scores), 3)
            elif isinstance(value, (int, float)):
                scores[field_name] = self._score_number(value, text_lower)
            else:
                scores[field_name] = self._score_value(str(value), text_lower)

        return scores

    def _score_value(self, value: str, text_lower: str) -> float:
        """Score a string value against the raw text."""
        if not value.strip():
            return 0.3
        val_lower = value.strip().lower()
        # Exact match
        if val_lower in text_lower:
            return 1.0
        # Partial match (first 6+ chars)
        if len(val_lower) >= 6 and val_lower[:6] in text_lower:
            return 0.8
        # Token-level match: at least half the tokens found
        tokens = val_lower.split()
        if tokens:
            found = sum(1 for t in tokens if t in text_lower)
            ratio = found / len(tokens)
            if ratio >= 0.5:
                return 0.5 + ratio * 0.3
        return 0.2

    def _score_number(self, value: float, text_lower: str) -> float:
        """Score a numeric value against the raw text."""
        # Try several string representations
        representations = [
            f"{value:.2f}",
            f"{value:.0f}",
            f"{value:,.2f}",
            f"{value:,.0f}",
            str(int(value)) if value == int(value) else "",
        ]
        for rep in representations:
            if rep and rep in text_lower:
                return 1.0

        # Check without formatting (just digits)
        digits = re.sub(r'[^\d]', '', f"{value:.2f}")
        if len(digits) >= 3 and digits in re.sub(r'[^\d]', '', text_lower):
            return 0.7

        return 0.3

    def _score_dict_item(self, item: dict, text_lower: str) -> float:
        """Score a dict item (e.g., a line item) against raw text."""
        if not item:
            return 0.3
        field_scores = []
        for k, v in item.items():
            if isinstance(v, (int, float)):
                field_scores.append(self._score_number(v, text_lower))
            elif isinstance(v, str):
                field_scores.append(self._score_value(v, text_lower))
        if field_scores:
            return round(sum(field_scores) / len(field_scores), 3)
        return 0.3


# ============================================================================
#  AI Extraction Engine (Stage 2)
# ============================================================================

class AIExtractor:
    """Uses LLM (Nemotron via captain_llm) to extract structured data from text."""

    async def extract(self, raw_text: str, document_type: str) -> Dict[str, Any]:
        """Build prompt from schema, call LLM, parse JSON response."""
        schema = EXTRACTION_SCHEMAS.get(document_type)
        if not schema:
            return {}

        schema_description = self._build_schema_description(schema["fields"])
        prompt = (
            f"You are a financial document data extraction engine. "
            f"Extract the following fields from this {document_type} document.\n\n"
            f"FIELDS TO EXTRACT:\n{schema_description}\n\n"
            f"DOCUMENT TEXT:\n{raw_text[:8000]}\n\n"  # Cap at 8K chars for LLM
            f"INSTRUCTIONS:\n"
            f"- Return ONLY valid JSON with the field names as keys.\n"
            f"- For arrays, return a list of objects with the specified sub-fields.\n"
            f"- For dates, use YYYY-MM-DD format.\n"
            f"- For numbers, return numeric values (not strings).\n"
            f"- If a field cannot be found, use null.\n"
            f"- Do NOT include any text outside the JSON object.\n"
        )

        try:
            from app.services.local_llm import captain_llm

            result = await captain_llm.route_and_call(
                message=prompt,
                context={"task": "document_extraction", "doc_type": document_type},
            )

            content = result.get("content", "")
            extracted = self._parse_json_response(content)
            return extracted

        except Exception as e:
            logger.error("AI extraction failed: %s", e)
            # Fallback: attempt regex-based extraction
            return self._regex_fallback(raw_text, document_type)

    def _build_schema_description(self, fields: Dict) -> str:
        lines = []
        for name, spec in fields.items():
            if isinstance(spec, dict):
                ftype = spec.get("type", "string")
                desc = spec.get("description", "")
                required = "REQUIRED" if spec.get("required") else "optional"
                lines.append(f"  - {name} ({ftype}, {required}): {desc}")
                if ftype == "array" and "item_fields" in spec:
                    for sub_name, sub_type in spec["item_fields"].items():
                        lines.append(f"      - {sub_name} ({sub_type})")
        return "\n".join(lines)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not content:
            return {}

        # Strip markdown code blocks
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Try direct JSON parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
        brace_start = content.find("{")
        brace_end = content.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            try:
                return json.loads(content[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse JSON from LLM response")
        return {}

    def _regex_fallback(self, raw_text: str, document_type: str) -> Dict[str, Any]:
        """Best-effort regex extraction when LLM is unavailable."""
        data: Dict[str, Any] = {}

        if document_type == "invoice":
            data = self._regex_extract_invoice(raw_text)
        elif document_type == "receipt":
            data = self._regex_extract_receipt(raw_text)
        elif document_type == "bank_statement":
            data = self._regex_extract_bank_statement(raw_text)

        return data

    def _regex_extract_invoice(self, text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        # Invoice number
        m = re.search(r'(?:invoice|inv)[#.\s:]*([A-Z0-9\-]+)', text, re.IGNORECASE)
        if m:
            data["invoice_number"] = m.group(1).strip()

        # Dates
        date_pattern = r'(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
        dates = re.findall(date_pattern, text)
        if dates:
            data["date"] = dates[0]
            if len(dates) > 1:
                data["due_date"] = dates[1]

        # Total amount
        m = re.search(r'(?:total|amount\s*due|grand\s*total)[:\s]*[\$\u20BE]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if m:
            data["total_amount"] = float(m.group(1).replace(",", ""))

        # Subtotal
        m = re.search(r'(?:subtotal|sub\s*total)[:\s]*[\$\u20BE]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if m:
            data["subtotal"] = float(m.group(1).replace(",", ""))

        # Tax
        m = re.search(r'(?:tax|vat|gst)[:\s]*[\$\u20BE]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if m:
            data["tax_amount"] = float(m.group(1).replace(",", ""))

        # Currency
        if "\u20BE" in text or "GEL" in text.upper():
            data["currency"] = "GEL"
        elif "$" in text or "USD" in text.upper():
            data["currency"] = "USD"
        elif "\u20AC" in text or "EUR" in text.upper():
            data["currency"] = "EUR"

        data["line_items"] = []
        return data

    def _regex_extract_receipt(self, text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        # Total
        m = re.search(r'(?:total)[:\s]*[\$\u20BE]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if m:
            data["total"] = float(m.group(1).replace(",", ""))

        # Date
        m = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', text)
        if m:
            data["date"] = m.group(1)

        data["items"] = []
        return data

    def _regex_extract_bank_statement(self, text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        m = re.search(r'(?:opening\s*balance)[:\s]*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if m:
            data["opening_balance"] = float(m.group(1).replace(",", ""))

        m = re.search(r'(?:closing\s*balance)[:\s]*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if m:
            data["closing_balance"] = float(m.group(1).replace(",", ""))

        # Account number (masked or full)
        m = re.search(r'(?:account|a/c)[#.\s:]*([A-Z0-9\-*]+\d{4})', text, re.IGNORECASE)
        if m:
            data["account_number"] = m.group(1)

        data["transactions"] = []
        return data


# ============================================================================
#  Document Processor (Main Pipeline)
# ============================================================================

class DocumentProcessor:
    """Two-stage document processing pipeline: Extract Text -> AI Structured Extraction."""

    def __init__(self):
        self._documents: Dict[str, DocumentRecord] = {}
        self._text_extractor = TextExtractor()
        self._type_detector = DocumentTypeDetector()
        self._ai_extractor = AIExtractor()
        self._confidence_scorer = ConfidenceScorer()
        self._invoice_validator = InvoiceValidator()
        self._arithmetic_validator = ArithmeticValidator()
        self._duplicate_detector = DuplicateDetector()

    # -- Main pipeline -------------------------------------------------------

    async def process_document(
        self,
        file_bytes: bytes,
        filename: str,
        document_type: Optional[str] = None,
    ) -> DocumentRecord:
        """Full two-stage pipeline: extract text, then extract structured data."""

        doc_id = uuid.uuid4().hex[:12].upper()
        now = datetime.utcnow().isoformat()

        # Stage 1: Text extraction
        raw_text, file_type = self._text_extractor.extract(file_bytes, filename)

        # Auto-detect document type if not specified
        if not document_type or document_type == "auto":
            detected_type, detect_conf = self._type_detector.detect(raw_text, filename)
            document_type = detected_type
            logger.info(
                "Document type auto-detected: %s (confidence=%.2f) for %s",
                detected_type, detect_conf, filename,
            )

        doc = DocumentRecord(
            id=doc_id,
            filename=filename,
            file_type=file_type,
            document_type=document_type,
            raw_text=raw_text,
            status=DocumentStatus.PROCESSING,
            created_at=now,
            updated_at=now,
        )
        self._documents[doc_id] = doc

        # Stage 2: AI structured extraction
        try:
            extracted = await self._ai_extractor.extract(raw_text, document_type)
            doc.extracted_data = extracted
            doc.status = DocumentStatus.EXTRACTED
            doc.updated_at = datetime.utcnow().isoformat()
        except Exception as e:
            logger.error("Extraction failed for %s: %s", filename, e)
            doc.extracted_data = {}
            doc.status = DocumentStatus.NEEDS_REVIEW
            doc.validation_errors.append(f"Extraction failed: {e}")
            return doc

        # Confidence scoring
        schema = EXTRACTION_SCHEMAS.get(document_type, {})
        schema_fields = schema.get("fields", {})
        doc.confidence_scores = self._confidence_scorer.score(
            doc.extracted_data, raw_text, schema_fields
        )

        # Deterministic validation
        doc.validation_errors = self._validate(doc)

        # Set final status
        if doc.validation_errors:
            doc.status = DocumentStatus.NEEDS_REVIEW
        else:
            doc.status = DocumentStatus.VALIDATED

        doc.updated_at = datetime.utcnow().isoformat()
        logger.info(
            "Document %s processed: type=%s, status=%s, errors=%d, avg_confidence=%.2f",
            doc_id, document_type, doc.status.value,
            len(doc.validation_errors),
            (sum(doc.confidence_scores.values()) / max(len(doc.confidence_scores), 1)),
        )
        return doc

    # -- Validation ----------------------------------------------------------

    def _validate(self, doc: DocumentRecord) -> List[str]:
        """Run all relevant validators on the document."""
        errors: List[str] = []

        if doc.document_type == "invoice":
            errors.extend(self._invoice_validator.validate(doc.extracted_data))

            # Duplicate check
            vendor = doc.extracted_data.get("vendor_name", "")
            inv_num = doc.extracted_data.get("invoice_number", "")
            dup_id = self._duplicate_detector.check_invoice(vendor, inv_num, doc.id)
            if dup_id:
                errors.append(
                    f"Possible duplicate: invoice {inv_num} from {vendor} "
                    f"already exists as document {dup_id}"
                )

        elif doc.document_type == "receipt":
            # Validate items sum == subtotal (if both present)
            items = doc.extracted_data.get("items", [])
            subtotal = _to_float(doc.extracted_data.get("subtotal"))
            if items and subtotal is not None:
                errors.extend(
                    self._arithmetic_validator.validate_sum(items, "amount", subtotal)
                )

            # Validate subtotal + tax == total
            total = _to_float(doc.extracted_data.get("total"))
            tax = _to_float(doc.extracted_data.get("tax")) or 0.0
            if subtotal is not None and total is not None:
                expected = round(subtotal + tax, 2)
                if abs(expected - total) > 0.05:
                    errors.append(
                        f"subtotal({subtotal}) + tax({tax}) = {expected}, but total is {total}"
                    )

            # Duplicate check
            merchant = doc.extracted_data.get("merchant", "")
            date_str = doc.extracted_data.get("date", "")
            total_val = total or 0.0
            dup_id = self._duplicate_detector.check_receipt(merchant, date_str, total_val, doc.id)
            if dup_id:
                errors.append(
                    f"Possible duplicate receipt: {merchant} on {date_str} for {total_val} "
                    f"already exists as document {dup_id}"
                )

        elif doc.document_type == "bank_statement":
            errors.extend(
                self._arithmetic_validator.validate_bank_statement(doc.extracted_data)
            )

        # Low-confidence field warnings
        for field_name, conf in doc.confidence_scores.items():
            if conf < 0.3:
                errors.append(f"Low confidence ({conf:.0%}) for field '{field_name}'")

        return errors

    # -- CRUD ----------------------------------------------------------------

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        return self._documents.get(doc_id)

    def approve_document(self, doc_id: str, approved_by: str = "user") -> Optional[DocumentRecord]:
        doc = self._documents.get(doc_id)
        if doc is None:
            return None
        doc.status = DocumentStatus.APPROVED
        doc.approved_by = approved_by
        doc.approved_at = datetime.utcnow().isoformat()
        doc.updated_at = doc.approved_at
        return doc

    def get_review_queue(self) -> List[Dict]:
        """Return documents that need human review, sorted by creation time."""
        queue = [
            doc.to_dict()
            for doc in self._documents.values()
            if doc.status in (DocumentStatus.NEEDS_REVIEW, DocumentStatus.EXTRACTED, DocumentStatus.VALIDATED)
        ]
        queue.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return queue

    def list_all(self) -> List[Dict]:
        return [doc.to_dict() for doc in self._documents.values()]

    def get_stats(self) -> Dict:
        total = len(self._documents)
        by_status = {}
        by_type = {}
        for doc in self._documents.values():
            s = doc.status.value
            by_status[s] = by_status.get(s, 0) + 1
            t = doc.document_type
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_documents": total,
            "by_status": by_status,
            "by_type": by_type,
        }


# ============================================================================
#  Helpers
# ============================================================================

def _to_float(val: Any) -> Optional[float]:
    """Safely convert to float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace(",", ""))
        except (ValueError, TypeError):
            return None
    return None


# ============================================================================
#  Singleton
# ============================================================================

document_processor = DocumentProcessor()
