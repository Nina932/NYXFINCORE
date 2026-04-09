"""
FinAI AP Automation -- Palantir AIP 3-Way Matching Engine.

Implements the full Accounts Payable automation workflow:
  1. Purchase Order (PO) management
  2. Goods Receipt Note (GRN) management
  3. 3-Way Matching: Invoice vs PO vs GRN
  4. Exception routing with AI recommendations
  5. Tiered approval workflow

Uses difflib.SequenceMatcher for real fuzzy line-item matching.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
#  Enums
# ============================================================================

class POStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    FULLY_RECEIVED = "fully_received"
    CLOSED = "closed"


class GRNStatus(str, Enum):
    PENDING = "pending"
    INSPECTED = "inspected"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class MatchStatus(str, Enum):
    FULL_MATCH = "full_match"
    PARTIAL_MATCH = "partial_match"
    NO_MATCH = "no_match"


class LineMatchStatus(str, Enum):
    MATCHED = "matched"
    PRICE_VARIANCE = "price_variance"
    QUANTITY_MISMATCH = "quantity_mismatch"
    UNMATCHED = "unmatched"


class ExceptionStatus(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


# ============================================================================
#  Data Models
# ============================================================================

@dataclass
class POLineItem:
    line_number: int
    description: str
    quantity: float
    unit_price: float
    unit: str = "unit"

    @property
    def amount(self) -> float:
        return round(self.quantity * self.unit_price, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["amount"] = self.amount
        return d


@dataclass
class PurchaseOrder:
    po_number: str
    vendor: str
    line_items: List[POLineItem]
    currency: str = "GEL"
    order_date: str = ""
    status: POStatus = POStatus.APPROVED
    total_amount: float = 0.0
    notes: str = ""

    def __post_init__(self):
        if not self.order_date:
            self.order_date = date.today().isoformat()
        if self.total_amount == 0.0 and self.line_items:
            self.total_amount = round(sum(li.amount for li in self.line_items), 2)

    def to_dict(self) -> dict:
        return {
            "po_number": self.po_number,
            "vendor": self.vendor,
            "currency": self.currency,
            "order_date": self.order_date,
            "status": self.status.value,
            "total_amount": self.total_amount,
            "notes": self.notes,
            "line_items": [li.to_dict() for li in self.line_items],
        }


@dataclass
class GRNLineItem:
    line_number: int
    description: str
    quantity_received: float
    quantity_accepted: float = 0.0
    inspection_notes: str = ""

    def __post_init__(self):
        if self.quantity_accepted == 0.0:
            self.quantity_accepted = self.quantity_received

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GoodsReceipt:
    grn_number: str
    po_number: str
    vendor: str
    line_items: List[GRNLineItem]
    receipt_date: str = ""
    status: GRNStatus = GRNStatus.ACCEPTED
    notes: str = ""

    def __post_init__(self):
        if not self.receipt_date:
            self.receipt_date = date.today().isoformat()

    def to_dict(self) -> dict:
        return {
            "grn_number": self.grn_number,
            "po_number": self.po_number,
            "vendor": self.vendor,
            "receipt_date": self.receipt_date,
            "status": self.status.value,
            "notes": self.notes,
            "line_items": [li.to_dict() for li in self.line_items],
        }


@dataclass
class LineMatchDetail:
    invoice_line: int
    invoice_description: str
    invoice_qty: float
    invoice_unit_price: float
    invoice_amount: float
    po_line: Optional[int] = None
    po_description: Optional[str] = None
    po_qty: Optional[float] = None
    po_unit_price: Optional[float] = None
    grn_qty_received: Optional[float] = None
    description_similarity: float = 0.0
    price_variance_pct: float = 0.0
    quantity_diff: float = 0.0
    status: LineMatchStatus = LineMatchStatus.UNMATCHED
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class MatchResult:
    match_id: str
    invoice_id: str
    po_id: Optional[str]
    grn_id: Optional[str]
    match_score: float
    line_matches: List[LineMatchDetail]
    exceptions: List[Dict[str, Any]]
    overall_status: MatchStatus
    ai_recommendation: str = ""
    matched_at: str = ""
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_tier: int = 0  # 0=auto, 1=one approver, 2=two approvers
    resolved_by: Optional[str] = None

    def __post_init__(self):
        if not self.matched_at:
            self.matched_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "invoice_id": self.invoice_id,
            "po_id": self.po_id,
            "grn_id": self.grn_id,
            "match_score": self.match_score,
            "line_matches": [lm.to_dict() for lm in self.line_matches],
            "exceptions": self.exceptions,
            "overall_status": self.overall_status.value,
            "ai_recommendation": self.ai_recommendation,
            "matched_at": self.matched_at,
            "approval_status": self.approval_status.value,
            "approval_tier": self.approval_tier,
            "resolved_by": self.resolved_by,
        }


# ============================================================================
#  Fuzzy Matcher
# ============================================================================

class FuzzyMatcher:
    """Fuzzy string matching using difflib.SequenceMatcher."""

    @staticmethod
    def similarity(a: str, b: str) -> float:
        """Compute similarity ratio between two strings (0.0 - 1.0)."""
        if not a or not b:
            return 0.0
        a_clean = a.strip().lower()
        b_clean = b.strip().lower()
        if a_clean == b_clean:
            return 1.0
        return SequenceMatcher(None, a_clean, b_clean).ratio()

    @staticmethod
    def best_match(
        query: str,
        candidates: List[Tuple[int, str]],
        threshold: float = 0.4,
    ) -> Optional[Tuple[int, str, float]]:
        """Find best matching candidate for a query string.

        Args:
            query: The string to match
            candidates: List of (index, description) tuples
            threshold: Minimum similarity to consider a match

        Returns:
            (index, description, similarity) or None
        """
        if not query or not candidates:
            return None

        best_idx = -1
        best_desc = ""
        best_score = 0.0

        q_lower = query.strip().lower()

        for idx, desc in candidates:
            d_lower = desc.strip().lower()
            score = SequenceMatcher(None, q_lower, d_lower).ratio()

            # Boost score if one string contains the other
            if q_lower in d_lower or d_lower in q_lower:
                score = min(score + 0.2, 1.0)

            # Boost score for shared significant words
            q_words = set(q_lower.split())
            d_words = set(d_lower.split())
            common = q_words & d_words
            # Filter out short/common words
            significant_common = {w for w in common if len(w) > 2}
            if significant_common:
                score = min(score + 0.1 * len(significant_common), 1.0)

            if score > best_score:
                best_score = score
                best_idx = idx
                best_desc = desc

        if best_score >= threshold:
            return (best_idx, best_desc, best_score)
        return None


# ============================================================================
#  3-Way Matcher
# ============================================================================

class ThreeWayMatcher:
    """Core 3-way matching engine: Invoice vs PO vs GRN."""

    def __init__(
        self,
        price_tolerance_pct: float = 5.0,
        qty_tolerance_units: float = 2.0,
    ):
        self.price_tolerance_pct = price_tolerance_pct
        self.qty_tolerance_units = qty_tolerance_units
        self._fuzzy = FuzzyMatcher()

    def match_invoice(
        self,
        invoice_data: Dict[str, Any],
        po: Optional[PurchaseOrder],
        grn: Optional[GoodsReceipt],
    ) -> MatchResult:
        """Run 3-way match: invoice vs PO vs GRN.

        Args:
            invoice_data: Extracted invoice fields (from document_processor)
            po: The matching Purchase Order (if found)
            grn: The matching Goods Receipt (if found)

        Returns:
            MatchResult with line-level details and overall score.
        """
        match_id = uuid.uuid4().hex[:10].upper()
        invoice_id = invoice_data.get("invoice_number", match_id)
        invoice_lines = invoice_data.get("line_items", [])

        line_matches: List[LineMatchDetail] = []
        exceptions: List[Dict[str, Any]] = []

        if not po:
            # No PO found -- entire invoice is unmatched
            for i, inv_line in enumerate(invoice_lines):
                lm = LineMatchDetail(
                    invoice_line=i + 1,
                    invoice_description=str(inv_line.get("description", "")),
                    invoice_qty=_safe_float(inv_line.get("quantity")),
                    invoice_unit_price=_safe_float(inv_line.get("unit_price")),
                    invoice_amount=_safe_float(inv_line.get("amount")),
                    status=LineMatchStatus.UNMATCHED,
                    notes="No matching PO found",
                )
                line_matches.append(lm)

            exceptions.append({
                "type": "no_po",
                "severity": "high",
                "message": f"No Purchase Order found for invoice {invoice_id}",
            })

            return MatchResult(
                match_id=match_id,
                invoice_id=invoice_id,
                po_id=None,
                grn_id=None,
                match_score=0.0,
                line_matches=line_matches,
                exceptions=exceptions,
                overall_status=MatchStatus.NO_MATCH,
                ai_recommendation="Invoice has no matching PO. Requires manual review and PO creation.",
            )

        # Build PO line candidates for fuzzy matching
        po_candidates: List[Tuple[int, str]] = []
        for li in po.line_items:
            po_candidates.append((li.line_number, li.description))

        # Build GRN lookup by PO line (GRN lines often match PO lines 1:1)
        grn_by_desc: Dict[int, GRNLineItem] = {}
        if grn:
            grn_candidates = [(gli.line_number, gli.description) for gli in grn.line_items]
            # Map GRN lines to PO lines by description similarity
            for gli in grn.line_items:
                best = self._fuzzy.best_match(
                    gli.description,
                    po_candidates,
                    threshold=0.4,
                )
                if best:
                    grn_by_desc[best[0]] = gli  # Map PO line_number -> GRN line

        # Match each invoice line to a PO line
        used_po_lines: set = set()
        matched_count = 0
        total_lines = len(invoice_lines) if invoice_lines else 1

        for i, inv_line in enumerate(invoice_lines):
            inv_desc = str(inv_line.get("description", ""))
            inv_qty = _safe_float(inv_line.get("quantity"))
            inv_price = _safe_float(inv_line.get("unit_price"))
            inv_amount = _safe_float(inv_line.get("amount"))

            lm = LineMatchDetail(
                invoice_line=i + 1,
                invoice_description=inv_desc,
                invoice_qty=inv_qty,
                invoice_unit_price=inv_price,
                invoice_amount=inv_amount,
            )

            # Find best PO line match (exclude already-used lines)
            available_candidates = [
                (idx, desc) for idx, desc in po_candidates
                if idx not in used_po_lines
            ]
            best = self._fuzzy.best_match(inv_desc, available_candidates, threshold=0.35)

            if not best:
                lm.status = LineMatchStatus.UNMATCHED
                lm.notes = "No matching PO line item found"
                exceptions.append({
                    "type": "unmatched_line",
                    "severity": "medium",
                    "invoice_line": i + 1,
                    "description": inv_desc,
                    "message": f"Invoice line {i + 1} '{inv_desc}' has no PO match",
                })
                line_matches.append(lm)
                continue

            po_line_num, po_desc, similarity = best
            used_po_lines.add(po_line_num)

            # Find the actual PO line item
            po_line = next(
                (li for li in po.line_items if li.line_number == po_line_num),
                None,
            )
            if not po_line:
                lm.status = LineMatchStatus.UNMATCHED
                line_matches.append(lm)
                continue

            lm.po_line = po_line_num
            lm.po_description = po_line.description
            lm.po_qty = po_line.quantity
            lm.po_unit_price = po_line.unit_price
            lm.description_similarity = round(similarity, 3)

            # GRN quantity
            grn_line = grn_by_desc.get(po_line_num)
            if grn_line:
                lm.grn_qty_received = grn_line.quantity_accepted
            elif grn:
                # Try direct fuzzy match between invoice and GRN descriptions
                grn_cands = [
                    (gli.line_number, gli.description) for gli in grn.line_items
                ]
                grn_match = self._fuzzy.best_match(inv_desc, grn_cands, threshold=0.35)
                if grn_match:
                    matched_grn = next(
                        (g for g in grn.line_items if g.line_number == grn_match[0]),
                        None,
                    )
                    if matched_grn:
                        lm.grn_qty_received = matched_grn.quantity_accepted

            # --- Compare prices ---
            price_ok = True
            if inv_price is not None and po_line.unit_price > 0:
                variance_pct = abs(inv_price - po_line.unit_price) / po_line.unit_price * 100
                lm.price_variance_pct = round(variance_pct, 2)
                if variance_pct > self.price_tolerance_pct:
                    price_ok = False
                    exceptions.append({
                        "type": "price_variance",
                        "severity": "medium",
                        "invoice_line": i + 1,
                        "invoice_price": inv_price,
                        "po_price": po_line.unit_price,
                        "variance_pct": round(variance_pct, 2),
                        "message": (
                            f"Line {i + 1}: price variance {variance_pct:.1f}% "
                            f"(invoice {inv_price} vs PO {po_line.unit_price})"
                        ),
                    })

            # --- Compare quantities ---
            qty_ok = True
            effective_qty = lm.grn_qty_received if lm.grn_qty_received is not None else po_line.quantity
            if inv_qty is not None and effective_qty is not None:
                qty_diff = inv_qty - effective_qty
                lm.quantity_diff = round(qty_diff, 2)
                if abs(qty_diff) > self.qty_tolerance_units:
                    qty_ok = False
                    qty_source = "GRN" if lm.grn_qty_received is not None else "PO"
                    exceptions.append({
                        "type": "quantity_mismatch",
                        "severity": "medium" if abs(qty_diff) <= effective_qty * 0.1 else "high",
                        "invoice_line": i + 1,
                        "invoice_qty": inv_qty,
                        f"{qty_source.lower()}_qty": effective_qty,
                        "difference": round(qty_diff, 2),
                        "message": (
                            f"Line {i + 1}: qty mismatch "
                            f"(invoice {inv_qty} vs {qty_source} {effective_qty}, diff={qty_diff:.1f})"
                        ),
                    })

            # --- Set line status ---
            if price_ok and qty_ok:
                lm.status = LineMatchStatus.MATCHED
                lm.notes = f"Matched to PO line {po_line_num} (similarity={similarity:.0%})"
                matched_count += 1
            elif not price_ok and qty_ok:
                lm.status = LineMatchStatus.PRICE_VARIANCE
                lm.notes = f"Price variance {lm.price_variance_pct:.1f}% exceeds {self.price_tolerance_pct}%"
            elif not qty_ok and price_ok:
                lm.status = LineMatchStatus.QUANTITY_MISMATCH
                lm.notes = f"Quantity diff {lm.quantity_diff:.1f} exceeds tolerance {self.qty_tolerance_units}"
            else:
                lm.status = LineMatchStatus.PRICE_VARIANCE  # Both issues; price takes precedence
                lm.notes = f"Price variance {lm.price_variance_pct:.1f}% AND quantity diff {lm.quantity_diff:.1f}"

            line_matches.append(lm)

        # No GRN warning
        if not grn and po:
            exceptions.append({
                "type": "no_grn",
                "severity": "medium",
                "message": "No Goods Receipt Note found; matching against PO only (2-way match)",
            })

        # Compute overall match score
        if total_lines > 0:
            match_score = round(matched_count / total_lines, 3)
        else:
            match_score = 1.0 if not exceptions else 0.0

        if match_score >= 0.9 and not any(e["severity"] == "high" for e in exceptions):
            overall_status = MatchStatus.FULL_MATCH
        elif match_score > 0.0:
            overall_status = MatchStatus.PARTIAL_MATCH
        else:
            overall_status = MatchStatus.NO_MATCH

        return MatchResult(
            match_id=match_id,
            invoice_id=invoice_id,
            po_id=po.po_number if po else None,
            grn_id=grn.grn_number if grn else None,
            match_score=match_score,
            line_matches=line_matches,
            exceptions=exceptions,
            overall_status=overall_status,
        )


# ============================================================================
#  Exception Router
# ============================================================================

class ExceptionRouter:
    """Route match exceptions and generate AI recommendations."""

    # Tier thresholds (in GEL)
    AUTO_APPROVE_LIMIT = 500.0
    SINGLE_APPROVER_LIMIT = 5000.0

    async def process_match(self, match_result: MatchResult, invoice_total: float) -> MatchResult:
        """Determine approval tier and generate AI recommendation."""

        # Determine approval tier
        if match_result.overall_status == MatchStatus.FULL_MATCH:
            if invoice_total <= self.AUTO_APPROVE_LIMIT:
                match_result.approval_status = ApprovalStatus.APPROVED
                match_result.approval_tier = 0
                match_result.ai_recommendation = (
                    f"Auto-approved: Full 3-way match with invoice total "
                    f"{invoice_total:.2f} GEL (under {self.AUTO_APPROVE_LIMIT:.0f} GEL threshold)."
                )
                return match_result

        # Non-auto cases
        if invoice_total <= self.SINGLE_APPROVER_LIMIT:
            match_result.approval_tier = 1
        else:
            match_result.approval_tier = 2

        # Generate AI recommendation
        match_result.ai_recommendation = await self._generate_recommendation(
            match_result, invoice_total
        )
        return match_result

    async def _generate_recommendation(
        self, match_result: MatchResult, invoice_total: float
    ) -> str:
        """Generate AI recommendation for exceptions."""
        # Build context for LLM
        exception_summary = []
        for exc in match_result.exceptions:
            exception_summary.append(f"- [{exc.get('severity', 'medium').upper()}] {exc.get('message', '')}")

        match_summary = (
            f"Invoice {match_result.invoice_id} | "
            f"PO: {match_result.po_id or 'None'} | "
            f"GRN: {match_result.grn_id or 'None'} | "
            f"Match score: {match_result.match_score:.0%} | "
            f"Total: {invoice_total:.2f} GEL | "
            f"Status: {match_result.overall_status.value}"
        )

        prompt = (
            f"You are an AP automation system. Analyze this 3-way match result and "
            f"provide a brief recommendation (2-3 sentences) for the AP team.\n\n"
            f"MATCH SUMMARY: {match_summary}\n\n"
            f"EXCEPTIONS:\n" + "\n".join(exception_summary) + "\n\n"
            f"Approval tier: {'auto' if match_result.approval_tier == 0 else match_result.approval_tier} "
            f"({'<500 GEL' if invoice_total < 500 else '<5000 GEL' if invoice_total < 5000 else '>5000 GEL'})\n\n"
            f"Provide a concise recommendation: approve, investigate, or escalate. "
            f"Include specific actions for each exception."
        )

        try:
            from app.services.local_llm import captain_llm

            result = await captain_llm.route_and_call(
                message=prompt,
                context={"task": "ap_exception_recommendation"},
            )
            return result.get("content", self._rule_based_recommendation(match_result, invoice_total))
        except Exception as e:
            logger.warning("AI recommendation failed, using rule-based: %s", e)
            return self._rule_based_recommendation(match_result, invoice_total)

    def _rule_based_recommendation(self, match_result: MatchResult, invoice_total: float) -> str:
        """Deterministic fallback recommendation when LLM is unavailable."""
        if match_result.overall_status == MatchStatus.FULL_MATCH:
            return (
                f"Full match confirmed. Invoice total {invoice_total:.2f} GEL. "
                f"Recommend approval with standard processing."
            )

        parts = []

        # Analyze exception types
        price_issues = [e for e in match_result.exceptions if e.get("type") == "price_variance"]
        qty_issues = [e for e in match_result.exceptions if e.get("type") == "quantity_mismatch"]
        unmatched = [e for e in match_result.exceptions if e.get("type") == "unmatched_line"]
        no_po = any(e.get("type") == "no_po" for e in match_result.exceptions)
        no_grn = any(e.get("type") == "no_grn" for e in match_result.exceptions)

        if no_po:
            parts.append(
                "No PO found. Invoice requires retrospective PO creation or "
                "classification as non-PO expenditure. Escalate to procurement."
            )
        else:
            if price_issues:
                max_var = max(e.get("variance_pct", 0) for e in price_issues)
                if max_var > 15:
                    parts.append(
                        f"Significant price variance (up to {max_var:.1f}%). "
                        f"Contact vendor to verify pricing. Hold payment pending resolution."
                    )
                else:
                    parts.append(
                        f"Minor price variances detected (up to {max_var:.1f}%). "
                        f"May approve if within contractual escalation clauses."
                    )

            if qty_issues:
                parts.append(
                    f"{len(qty_issues)} quantity mismatch(es). "
                    f"Verify with warehouse/receiving. May indicate partial delivery."
                )

            if unmatched:
                parts.append(
                    f"{len(unmatched)} unmatched line(s). "
                    f"Verify these items were ordered and received."
                )

            if no_grn:
                parts.append(
                    "No GRN on file. Confirm goods receipt before processing payment."
                )

        if not parts:
            parts.append(f"Match score: {match_result.match_score:.0%}. Review exceptions before approval.")

        return " ".join(parts)


# ============================================================================
#  PO/GRN Store
# ============================================================================

class POGRNStore:
    """In-memory store for Purchase Orders and Goods Receipts."""

    def __init__(self):
        self._pos: Dict[str, PurchaseOrder] = {}
        self._grns: Dict[str, GoodsReceipt] = {}
        self._grn_by_po: Dict[str, str] = {}  # po_number -> grn_number

    # -- Purchase Orders -----------------------------------------------------

    def add_po(
        self,
        po_number: str,
        vendor: str,
        line_items: List[Dict[str, Any]],
        currency: str = "GEL",
        order_date: str = "",
    ) -> PurchaseOrder:
        """Create a Purchase Order."""
        items = []
        for i, li in enumerate(line_items):
            items.append(POLineItem(
                line_number=li.get("line_number", i + 1),
                description=str(li.get("description", "")),
                quantity=float(li.get("quantity", 0)),
                unit_price=float(li.get("unit_price", 0)),
                unit=str(li.get("unit", "unit")),
            ))

        po = PurchaseOrder(
            po_number=po_number,
            vendor=vendor,
            line_items=items,
            currency=currency,
            order_date=order_date or date.today().isoformat(),
        )
        self._pos[po_number] = po
        return po

    def find_po(self, po_number: str) -> Optional[PurchaseOrder]:
        """Find PO by exact number."""
        return self._pos.get(po_number)

    def find_po_by_vendor(self, vendor: str) -> List[PurchaseOrder]:
        """Find all POs for a vendor (fuzzy match)."""
        results = []
        v_lower = vendor.strip().lower()
        for po in self._pos.values():
            sim = SequenceMatcher(None, v_lower, po.vendor.strip().lower()).ratio()
            if sim >= 0.6 or v_lower in po.vendor.lower() or po.vendor.lower() in v_lower:
                results.append(po)
        return results

    def list_pos(self) -> List[Dict]:
        return [po.to_dict() for po in self._pos.values()]

    # -- Goods Receipts ------------------------------------------------------

    def add_grn(
        self,
        po_number: str,
        line_items: List[Dict[str, Any]],
        grn_number: str = "",
        receipt_date: str = "",
    ) -> Optional[GoodsReceipt]:
        """Create a Goods Receipt Note linked to a PO."""
        po = self._pos.get(po_number)
        if not po:
            logger.warning("Cannot create GRN: PO %s not found", po_number)
            return None

        if not grn_number:
            grn_number = f"GRN-{uuid.uuid4().hex[:8].upper()}"

        items = []
        for i, li in enumerate(line_items):
            items.append(GRNLineItem(
                line_number=li.get("line_number", i + 1),
                description=str(li.get("description", "")),
                quantity_received=float(li.get("quantity_received", li.get("quantity", 0))),
                quantity_accepted=float(li.get("quantity_accepted", li.get("quantity_received", li.get("quantity", 0)))),
                inspection_notes=str(li.get("inspection_notes", "")),
            ))

        grn = GoodsReceipt(
            grn_number=grn_number,
            po_number=po_number,
            vendor=po.vendor,
            line_items=items,
            receipt_date=receipt_date or date.today().isoformat(),
        )
        self._grns[grn_number] = grn
        self._grn_by_po[po_number] = grn_number

        # Update PO status
        po.status = POStatus.FULLY_RECEIVED
        return grn

    def find_grn_for_po(self, po_number: str) -> Optional[GoodsReceipt]:
        """Find GRN by PO number."""
        grn_num = self._grn_by_po.get(po_number)
        if grn_num:
            return self._grns.get(grn_num)
        return None

    def list_grns(self) -> List[Dict]:
        return [grn.to_dict() for grn in self._grns.values()]

    # -- Sample Data Generation ----------------------------------------------

    def populate_sample_data(self, financials: Optional[Dict] = None) -> Dict:
        """Generate sample POs and GRNs from financial data or defaults."""
        created = {"pos": 0, "grns": 0}
        fin = financials or {}

        # Derive scale from financials
        cogs = abs(_extract(fin, ["cogs", "cost_of_goods_sold", "COGS", "cost_of_sales"]) or 50000)
        opex = abs(_extract(fin, ["operating_expenses", "opex", "total_expenses"]) or 30000)

        # Create sample POs across different vendor categories
        samples = [
            {
                "po_number": "PO-2026-001",
                "vendor": "Fuel Suppliers Ltd",
                "items": [
                    {"description": "Diesel Fuel - Premium Grade", "quantity": 5000, "unit_price": round(cogs * 0.3 / 5000, 2), "unit": "liters"},
                    {"description": "Gasoline AI-95", "quantity": 3000, "unit_price": round(cogs * 0.2 / 3000, 2), "unit": "liters"},
                ],
            },
            {
                "po_number": "PO-2026-002",
                "vendor": "Office Supply Co",
                "items": [
                    {"description": "Printer Paper A4 (boxes)", "quantity": 50, "unit_price": 25.00, "unit": "box"},
                    {"description": "Ink Cartridges - Black", "quantity": 10, "unit_price": 85.00, "unit": "pcs"},
                    {"description": "Office Chairs - Ergonomic", "quantity": 5, "unit_price": 450.00, "unit": "pcs"},
                ],
            },
            {
                "po_number": "PO-2026-003",
                "vendor": "IT Solutions Georgia",
                "items": [
                    {"description": "Server Maintenance Annual Contract", "quantity": 1, "unit_price": round(opex * 0.05, 2), "unit": "contract"},
                    {"description": "Software Licenses (Annual)", "quantity": 20, "unit_price": 120.00, "unit": "license"},
                ],
            },
            {
                "po_number": "PO-2026-004",
                "vendor": "Transport & Logistics LLC",
                "items": [
                    {"description": "Freight Transport - Tbilisi Route", "quantity": 12, "unit_price": round(cogs * 0.05 / 12, 2), "unit": "trip"},
                    {"description": "Warehouse Storage (Monthly)", "quantity": 3, "unit_price": round(opex * 0.02, 2), "unit": "month"},
                ],
            },
            {
                "po_number": "PO-2026-005",
                "vendor": "Safety Equipment Inc",
                "items": [
                    {"description": "Fire Extinguishers - Refill", "quantity": 20, "unit_price": 45.00, "unit": "pcs"},
                    {"description": "Safety Helmets", "quantity": 30, "unit_price": 35.00, "unit": "pcs"},
                    {"description": "First Aid Kits", "quantity": 10, "unit_price": 120.00, "unit": "kit"},
                ],
            },
        ]

        for sample in samples:
            if sample["po_number"] not in self._pos:
                self.add_po(
                    po_number=sample["po_number"],
                    vendor=sample["vendor"],
                    line_items=sample["items"],
                )
                created["pos"] += 1

                # Create matching GRN (with slight variations for realism)
                grn_items = []
                for item in sample["items"]:
                    # Simulate receiving: sometimes slight quantity differences
                    recv_qty = item["quantity"]
                    # 20% chance of receiving slightly less
                    import random
                    if random.random() < 0.2:
                        recv_qty = max(1, recv_qty - max(1, int(recv_qty * 0.05)))
                    grn_items.append({
                        "description": item["description"],
                        "quantity_received": recv_qty,
                        "quantity_accepted": recv_qty,
                    })

                self.add_grn(
                    po_number=sample["po_number"],
                    line_items=grn_items,
                )
                created["grns"] += 1

        return {
            "populated": True,
            "created": created,
            "total_pos": len(self._pos),
            "total_grns": len(self._grns),
        }


# ============================================================================
#  AP Automation Engine (Orchestrator)
# ============================================================================

class APAutomationEngine:
    """Full AP Automation workflow: matching, exception handling, approvals."""

    def __init__(self):
        self.store = POGRNStore()
        self.matcher = ThreeWayMatcher()
        self.exception_router = ExceptionRouter()
        self._match_results: Dict[str, MatchResult] = {}
        self._exception_log: List[Dict[str, Any]] = []

    # -- Main matching endpoint ----------------------------------------------

    async def match_invoice(self, invoice_data: Dict[str, Any]) -> Dict:
        """Run full AP matching workflow on invoice data.

        Expected invoice_data keys:
            - invoice_number, vendor_name, line_items[], subtotal, tax_amount, total_amount
            - po_number (optional, for direct PO lookup)
        """
        vendor = invoice_data.get("vendor_name", "")
        po_number = invoice_data.get("po_number", "")
        total = _safe_float(invoice_data.get("total_amount")) or 0.0

        # Step 1: Find PO
        po = None
        if po_number:
            po = self.store.find_po(po_number)
        if not po and vendor:
            # Try vendor-based fuzzy search
            vendor_pos = self.store.find_po_by_vendor(vendor)
            if vendor_pos:
                # Pick the one with closest total
                po = min(
                    vendor_pos,
                    key=lambda p: abs(p.total_amount - total),
                )

        # Step 2: Find GRN
        grn = None
        if po:
            grn = self.store.find_grn_for_po(po.po_number)

        # Step 3: 3-way match
        match_result = self.matcher.match_invoice(invoice_data, po, grn)

        # Step 4: Exception routing and AI recommendation
        match_result = await self.exception_router.process_match(match_result, total)

        # Store result
        self._match_results[match_result.match_id] = match_result

        # Log exceptions
        for exc in match_result.exceptions:
            self._exception_log.append({
                "match_id": match_result.match_id,
                "invoice_id": match_result.invoice_id,
                "exception_type": exc.get("type"),
                "severity": exc.get("severity"),
                "message": exc.get("message"),
                "status": ExceptionStatus.OPEN.value,
                "created_at": datetime.utcnow().isoformat(),
            })

        return match_result.to_dict()

    # -- Exception management ------------------------------------------------

    def get_open_exceptions(self) -> List[Dict]:
        """List all unresolved exceptions."""
        return [
            exc for exc in self._exception_log
            if exc.get("status") == ExceptionStatus.OPEN.value
        ]

    def resolve_exception(
        self,
        exception_index: int,
        resolution: str,
        resolved_by: str = "user",
    ) -> Optional[Dict]:
        """Resolve an exception by index."""
        if 0 <= exception_index < len(self._exception_log):
            exc = self._exception_log[exception_index]
            exc["status"] = ExceptionStatus.RESOLVED.value
            exc["resolution"] = resolution
            exc["resolved_by"] = resolved_by
            exc["resolved_at"] = datetime.utcnow().isoformat()
            return exc
        return None

    # -- Approval queue ------------------------------------------------------

    def get_approval_queue(self) -> List[Dict]:
        """Get all match results pending approval."""
        queue = []
        for mr in self._match_results.values():
            if mr.approval_status == ApprovalStatus.PENDING:
                queue.append(mr.to_dict())
        queue.sort(key=lambda x: x.get("matched_at", ""), reverse=True)
        return queue

    def approve_match(self, match_id: str, approved_by: str = "user") -> Optional[Dict]:
        """Approve a match result."""
        mr = self._match_results.get(match_id)
        if not mr:
            return None
        mr.approval_status = ApprovalStatus.APPROVED
        mr.resolved_by = approved_by
        return mr.to_dict()

    # -- Delegated methods ---------------------------------------------------

    def add_po(self, po_number: str, vendor: str, line_items: List[Dict], **kwargs) -> Dict:
        po = self.store.add_po(po_number, vendor, line_items, **kwargs)
        return po.to_dict()

    def add_grn(self, po_number: str, line_items: List[Dict], **kwargs) -> Optional[Dict]:
        grn = self.store.add_grn(po_number, line_items, **kwargs)
        return grn.to_dict() if grn else None

    def populate_sample_data(self, financials: Optional[Dict] = None) -> Dict:
        return self.store.populate_sample_data(financials)

    def get_stats(self) -> Dict:
        total_matches = len(self._match_results)
        full = sum(1 for m in self._match_results.values() if m.overall_status == MatchStatus.FULL_MATCH)
        partial = sum(1 for m in self._match_results.values() if m.overall_status == MatchStatus.PARTIAL_MATCH)
        no_match = sum(1 for m in self._match_results.values() if m.overall_status == MatchStatus.NO_MATCH)
        open_exc = sum(1 for e in self._exception_log if e.get("status") == ExceptionStatus.OPEN.value)
        pending_approval = sum(1 for m in self._match_results.values() if m.approval_status == ApprovalStatus.PENDING)

        return {
            "total_matches": total_matches,
            "full_matches": full,
            "partial_matches": partial,
            "no_matches": no_match,
            "match_rate": round(full / max(total_matches, 1), 3),
            "open_exceptions": open_exc,
            "pending_approvals": pending_approval,
            "total_pos": len(self.store._pos),
            "total_grns": len(self.store._grns),
        }


# ============================================================================
#  Helpers
# ============================================================================

def _safe_float(val: Any) -> Optional[float]:
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


def _extract(data: Dict, keys: List[str]) -> Optional[float]:
    """Try multiple keys in a financial dict."""
    if not data:
        return None
    for k in keys:
        if k in data:
            v = data[k]
            if isinstance(v, (int, float)):
                return float(v)
    for v in data.values():
        if isinstance(v, dict):
            for k in keys:
                if k in v and isinstance(v[k], (int, float)):
                    return float(v[k])
    return None


# ============================================================================
#  Singleton
# ============================================================================

ap_engine = APAutomationEngine()
