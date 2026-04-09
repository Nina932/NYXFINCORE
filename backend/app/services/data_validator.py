"""
Phase N-4: DataValidator — Financial Data Validation Engine
=============================================================
Rules engine that checks uploaded financial data for:
  1. Critical errors (blocks processing)
  2. Warnings (flags but allows)
  3. Auto-corrections (fills missing computed fields)

All rules are deterministic — no LLM involvement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.smart_excel_parser import compute_derived_metrics

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ValidationIssue:
    """A single validation finding."""
    level: str           # error | warning | info
    field: str
    message: str
    rule: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "field": self.field,
            "message": self.message,
            "rule": self.rule,
        }


@dataclass
class ValidationResult:
    """Complete validation result."""
    valid: bool
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    info: List[ValidationIssue] = field(default_factory=list)
    auto_corrections: List[str] = field(default_factory=list)
    corrected_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "info": [i.to_dict() for i in self.info],
            "auto_corrections": self.auto_corrections,
            "corrected_data": self.corrected_data,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


# ═══════════════════════════════════════════════════════════════════
# VALIDATOR
# ═══════════════════════════════════════════════════════════════════

class DataValidator:
    """
    Financial data validation engine.

    Runs validation rules in order:
      1. Critical checks (any failure → valid=False)
      2. Warning checks (flagged but allowed)
      3. Auto-corrections (fills missing derived fields)
    """

    def validate(
        self,
        data: Dict[str, Any],
        previous_data: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate financial data.

        Args:
            data: Current period financial data
            previous_data: Previous period data (for trend checks)

        Returns:
            ValidationResult with errors, warnings, and corrected data
        """
        errors: List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []
        info: List[ValidationIssue] = []

        def _get(key: str) -> Optional[float]:
            v = data.get(key)
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        # ── CRITICAL ERRORS ─────────────────────────────────────────

        revenue = _get("revenue")
        cogs = _get("cogs")
        gross_profit = _get("gross_profit")
        net_profit = _get("net_profit")

        # Revenue is required
        if revenue is None:
            errors.append(ValidationIssue(
                "error", "revenue", "Revenue is missing (required field)", "required_revenue",
            ))
        elif revenue < 0:
            errors.append(ValidationIssue(
                "error", "revenue", f"Revenue is negative: {revenue:,.0f}", "negative_revenue",
            ))

        # COGS > Revenue * 1.5 (unrealistic)
        if revenue is not None and cogs is not None and revenue > 0:
            if cogs > revenue * 1.5:
                errors.append(ValidationIssue(
                    "error", "cogs",
                    f"COGS ({cogs:,.0f}) exceeds 150% of Revenue ({revenue:,.0f}) — unrealistic",
                    "cogs_excessive",
                ))

        # Balance sheet equation check
        total_assets = _get("total_assets")
        total_liabilities = _get("total_liabilities")
        total_equity = _get("total_equity")
        if all(v is not None for v in [total_assets, total_liabilities, total_equity]):
            diff = abs(total_assets - total_liabilities - total_equity)
            if diff > max(1.0, total_assets * 0.001):  # 0.1% tolerance
                errors.append(ValidationIssue(
                    "error", "balance_sheet",
                    f"BS equation violated: Assets ({total_assets:,.0f}) != "
                    f"Liabilities ({total_liabilities:,.0f}) + Equity ({total_equity:,.0f}), diff={diff:,.0f}",
                    "bs_equation",
                ))

        # ── WARNINGS ────────────────────────────────────────────────

        # Extreme net loss
        if net_profit is not None and revenue is not None and revenue > 0:
            net_margin = net_profit / revenue * 100
            if net_margin < -50:
                warnings.append(ValidationIssue(
                    "warning", "net_profit",
                    f"Net margin is {net_margin:.1f}% — extreme loss",
                    "extreme_loss",
                ))

        # COGS = 0 (suspicious for non-service companies)
        if cogs is not None and cogs == 0 and revenue is not None and revenue > 0:
            warnings.append(ValidationIssue(
                "warning", "cogs",
                "COGS is zero — suspicious unless pure service company",
                "zero_cogs",
            ))

        # Revenue changed > 100% from previous period
        if previous_data and revenue is not None:
            prev_revenue = previous_data.get("revenue")
            if prev_revenue is not None and prev_revenue > 0:
                try:
                    change_pct = abs(float(revenue) - float(prev_revenue)) / float(prev_revenue) * 100
                    if change_pct > 100:
                        warnings.append(ValidationIssue(
                            "warning", "revenue",
                            f"Revenue changed {change_pct:.1f}% from previous period — verify data",
                            "revenue_spike",
                        ))
                except (ValueError, TypeError):
                    pass

        # Depreciation > Revenue * 20%
        depreciation = _get("depreciation")
        if depreciation is not None and revenue is not None and revenue > 0:
            if depreciation > revenue * 0.20:
                warnings.append(ValidationIssue(
                    "warning", "depreciation",
                    f"Depreciation ({depreciation:,.0f}) exceeds 20% of Revenue — verify",
                    "high_depreciation",
                ))

        # GA expenses > Revenue * 50%
        ga = _get("ga_expenses")
        if ga is not None and revenue is not None and revenue > 0:
            if ga > revenue * 0.50:
                warnings.append(ValidationIssue(
                    "warning", "ga_expenses",
                    f"G&A expenses ({ga:,.0f}) exceed 50% of Revenue — verify",
                    "high_ga",
                ))

        # Negative COGS (unlikely)
        if cogs is not None and cogs < 0:
            warnings.append(ValidationIssue(
                "warning", "cogs",
                f"COGS is negative ({cogs:,.0f}) — unusual, verify",
                "negative_cogs",
            ))

        # ── AUTO-CORRECTIONS ────────────────────────────────────────

        corrected, corrections = compute_derived_metrics(data)

        # ── INFO ────────────────────────────────────────────────────

        field_count = sum(1 for v in data.values() if v is not None)
        info.append(ValidationIssue(
            "info", "_meta",
            f"{field_count} fields provided, {len(corrections)} auto-computed",
            "field_count",
        ))

        valid = len(errors) == 0

        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            info=info,
            auto_corrections=corrections,
            corrected_data=corrected,
        )


# Module-level singleton
data_validator = DataValidator()
