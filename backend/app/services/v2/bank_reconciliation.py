"""
FinAI v2 Bank Reconciliation — Statement import + auto-matching.
=================================================================
Fills the "Bank Reconciliation" gap from SAP FI benchmark.

Features:
- Import bank statement lines
- Auto-match by: amount + date + reference
- Fuzzy matching with configurable tolerance
- Reconciliation status dashboard
- Unmatched items report

Public API:
    from app.services.v2.bank_reconciliation import bank_rec_service
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.services.v2.decimal_utils import to_decimal, round_fin, is_zero

logger = logging.getLogger(__name__)
D = Decimal


class BankReconciliationService:
    """Bank statement reconciliation engine."""

    def reconcile(
        self,
        bank_lines: List[Dict[str, Any]],
        gl_entries: List[Dict[str, Any]],
        date_tolerance_days: int = 3,
        amount_tolerance: Decimal = D("0.01"),
    ) -> Dict[str, Any]:
        """Match bank statement lines against GL entries.

        Args:
            bank_lines: List of dicts with: date, description, amount, reference
            gl_entries: List of dicts with: date, description, amount, reference, account_code
            date_tolerance_days: Max days difference for matching
            amount_tolerance: Max amount difference for matching

        Returns:
            Dict with matched pairs, unmatched bank items, unmatched GL items.
        """
        matched = []
        unmatched_bank = list(range(len(bank_lines)))
        unmatched_gl = list(range(len(gl_entries)))

        # Pass 1: Exact match (same amount + same reference)
        for bi in list(unmatched_bank):
            bl = bank_lines[bi]
            b_amt = to_decimal(bl.get("amount", 0))
            b_ref = str(bl.get("reference", "")).strip().lower()
            b_date = bl.get("date")

            for gi in list(unmatched_gl):
                gl = gl_entries[gi]
                g_amt = to_decimal(gl.get("amount", 0))
                g_ref = str(gl.get("reference", "")).strip().lower()
                g_date = gl.get("date")

                # Amount match
                if abs(b_amt - g_amt) > amount_tolerance:
                    continue

                # Reference match
                if b_ref and g_ref and b_ref == g_ref:
                    matched.append({
                        "bank_line": bl,
                        "gl_entry": gl,
                        "match_type": "exact_reference",
                        "confidence": "1.00",
                        "amount_diff": str(round_fin(abs(b_amt - g_amt))),
                    })
                    unmatched_bank.remove(bi)
                    unmatched_gl.remove(gi)
                    break

        # Pass 2: Fuzzy match (same amount + date within tolerance)
        for bi in list(unmatched_bank):
            bl = bank_lines[bi]
            b_amt = to_decimal(bl.get("amount", 0))
            b_date = bl.get("date")

            best_match = None
            best_gi = None
            best_date_diff = timedelta(days=999)

            for gi in unmatched_gl:
                gl = gl_entries[gi]
                g_amt = to_decimal(gl.get("amount", 0))
                g_date = gl.get("date")

                if abs(b_amt - g_amt) > amount_tolerance:
                    continue

                if b_date and g_date:
                    try:
                        bd = b_date if isinstance(b_date, date) else datetime.fromisoformat(str(b_date)).date()
                        gd = g_date if isinstance(g_date, date) else datetime.fromisoformat(str(g_date)).date()
                        diff = abs((bd - gd).days)
                        if diff <= date_tolerance_days and timedelta(days=diff) < best_date_diff:
                            best_match = gl
                            best_gi = gi
                            best_date_diff = timedelta(days=diff)
                    except (ValueError, TypeError):
                        continue

            if best_match and best_gi is not None:
                confidence = round_fin(D("1") - D(str(best_date_diff.days)) * D("0.1"))
                matched.append({
                    "bank_line": bl,
                    "gl_entry": best_match,
                    "match_type": "fuzzy_date_amount",
                    "confidence": str(max(confidence, D("0.50"))),
                    "date_diff_days": best_date_diff.days,
                    "amount_diff": str(round_fin(abs(b_amt - to_decimal(best_match.get("amount", 0))))),
                })
                unmatched_bank.remove(bi)
                unmatched_gl.remove(best_gi)

        # Summary
        total_bank = sum(to_decimal(bank_lines[i].get("amount", 0)) for i in range(len(bank_lines)))
        total_gl = sum(to_decimal(gl_entries[i].get("amount", 0)) for i in range(len(gl_entries)))
        total_matched = sum(to_decimal(m["bank_line"].get("amount", 0)) for m in matched)

        return {
            "matched": matched,
            "unmatched_bank": [bank_lines[i] for i in unmatched_bank],
            "unmatched_gl": [gl_entries[i] for i in unmatched_gl],
            "summary": {
                "total_bank_lines": len(bank_lines),
                "total_gl_entries": len(gl_entries),
                "matched_count": len(matched),
                "unmatched_bank_count": len(unmatched_bank),
                "unmatched_gl_count": len(unmatched_gl),
                "match_rate_pct": str(round_fin(
                    D(str(len(matched))) / D(str(max(len(bank_lines), 1))) * D("100")
                )),
                "total_bank_amount": str(round_fin(total_bank)),
                "total_gl_amount": str(round_fin(total_gl)),
                "reconciled_amount": str(round_fin(total_matched)),
                "unreconciled_difference": str(round_fin(total_bank - total_gl)),
            },
        }


# Module singleton
bank_rec_service = BankReconciliationService()
