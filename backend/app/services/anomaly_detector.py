"""
Statistical Anomaly Detection for Fuel Distribution Financial Platform.

Provides Z-score, IQR, Benford's Law, and seasonal deviation analysis
to identify suspicious or unusual transactions in financial datasets.
"""

import math
import numpy as np
import pandas as pd
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.all_models import Transaction, Anomaly, Dataset

logger = logging.getLogger(__name__)

# Severity ordering for deduplication (higher index = more severe)
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _to_python(obj):
    """Recursively convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_python(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class AnomalyDetector:
    """Statistical anomaly detection engine for financial transaction data.

    Implements multiple complementary detection methods designed for
    fuel distribution accounting: Z-score outlier detection, IQR
    fence-based outlier detection, Benford's Law digit analysis, and
    seasonal deviation checks.  Results are persisted to the ``anomalies``
    table so downstream dashboards and the AI agent can surface them.
    """

    # ──────────────────────────────────────────────────────────────
    # 1. Z-Score Detection
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def zscore_detection(
        transactions: List[Dict],
        threshold: float = 2.0,
        group_by: str = "cost_class",
    ) -> List[Dict]:
        """Detect anomalies using Z-score analysis within groups.

        For each group defined by *group_by*, the method computes the mean
        and standard deviation of the ``amount`` field, then flags every
        transaction whose absolute Z-score exceeds *threshold*.

        Args:
            transactions: List of transaction dicts, each containing at
                least ``id``, ``amount``, and the field specified by
                *group_by*.
            threshold: Number of standard deviations beyond which a
                transaction is considered anomalous (default 2.0).
            group_by: Field name used to partition transactions into
                groups before computing statistics (default ``cost_class``).

        Returns:
            List of anomaly dicts, each containing ``transaction_id``,
            ``amount``, ``z_score``, ``mean``, ``std``, ``group``,
            ``severity``, and ``anomaly_type``.
        """
        if not transactions:
            return []

        anomalies: List[Dict] = []

        try:
            df = pd.DataFrame(transactions)

            # Ensure required columns exist
            if "amount" not in df.columns or "id" not in df.columns:
                logger.warning("zscore_detection: missing 'amount' or 'id' column")
                return []

            # Fall back to ungrouped analysis when the group_by field is absent
            if group_by not in df.columns:
                logger.info(
                    "zscore_detection: group_by field '%s' not found, "
                    "analysing all transactions as a single group",
                    group_by,
                )
                df[group_by] = "all"

            for group_name, group_df in df.groupby(group_by, dropna=False):
                amounts = group_df["amount"].astype(float)

                if len(amounts) < 3:
                    # Not enough data points for meaningful statistics
                    continue

                mean = float(amounts.mean())
                std = float(amounts.std(ddof=1))

                if std == 0:
                    # All values identical — no outliers possible
                    continue

                for _, row in group_df.iterrows():
                    amount = float(row["amount"])
                    z_score = (amount - mean) / std
                    abs_z = abs(z_score)

                    if abs_z > threshold:
                        if abs_z > 3.0:
                            severity = "critical"
                        elif abs_z > 2.5:
                            severity = "high"
                        else:
                            severity = "medium"

                        anomalies.append({
                            "transaction_id": int(row["id"]),
                            "amount": round(amount, 4),
                            "z_score": round(z_score, 4),
                            "mean": round(mean, 4),
                            "std": round(std, 4),
                            "group": str(group_name) if group_name is not None else "unknown",
                            "severity": severity,
                            "anomaly_type": "zscore",
                        })

        except Exception:
            logger.exception("zscore_detection failed")

        logger.info(
            "zscore_detection complete: %d anomalies from %d transactions",
            len(anomalies),
            len(transactions),
        )
        return anomalies

    # ──────────────────────────────────────────────────────────────
    # 2. IQR Detection
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def iqr_detection(
        transactions: List[Dict],
        multiplier: float = 1.5,
    ) -> List[Dict]:
        """Detect anomalies using the Interquartile Range (IQR) method.

        Computes Q1, Q3, and IQR both globally and per ``cost_class``
        group.  A transaction is flagged when its amount falls below
        ``Q1 - multiplier * IQR`` or above ``Q3 + multiplier * IQR``.

        Args:
            transactions: List of transaction dicts with ``id``,
                ``amount``, and optionally ``cost_class``.
            multiplier: Fence multiplier applied to IQR (default 1.5).

        Returns:
            List of anomaly dicts with ``transaction_id``, ``amount``,
            ``q1``, ``q3``, ``iqr``, ``lower_bound``, ``upper_bound``,
            ``severity``, and ``anomaly_type``.
        """
        if not transactions:
            return []

        anomalies: List[Dict] = []
        seen_ids: set = set()

        try:
            df = pd.DataFrame(transactions)

            if "amount" not in df.columns or "id" not in df.columns:
                logger.warning("iqr_detection: missing 'amount' or 'id' column")
                return []

            def _detect_in_group(group_df: pd.DataFrame) -> None:
                amounts = group_df["amount"].astype(float)

                if len(amounts) < 4:
                    return

                q1 = float(np.percentile(amounts, 25))
                q3 = float(np.percentile(amounts, 75))
                iqr = q3 - q1

                if iqr == 0:
                    return

                lower_bound = q1 - multiplier * iqr
                upper_bound = q3 + multiplier * iqr

                for _, row in group_df.iterrows():
                    txn_id = int(row["id"])
                    if txn_id in seen_ids:
                        continue

                    amount = float(row["amount"])

                    if amount < lower_bound or amount > upper_bound:
                        # Determine severity based on how far outside the fence
                        distance = max(
                            abs(amount - lower_bound) if amount < lower_bound else 0,
                            abs(amount - upper_bound) if amount > upper_bound else 0,
                        )
                        iqr_multiples = distance / iqr if iqr != 0 else 0

                        if iqr_multiples > 3.0 * multiplier:
                            severity = "critical"
                        elif iqr_multiples > 2.0 * multiplier:
                            severity = "high"
                        else:
                            severity = "medium"

                        anomalies.append({
                            "transaction_id": txn_id,
                            "amount": round(amount, 4),
                            "q1": round(q1, 4),
                            "q3": round(q3, 4),
                            "iqr": round(iqr, 4),
                            "lower_bound": round(lower_bound, 4),
                            "upper_bound": round(upper_bound, 4),
                            "severity": severity,
                            "anomaly_type": "iqr",
                        })
                        seen_ids.add(txn_id)

            # Per-group analysis
            if "cost_class" in df.columns:
                for _, group_df in df.groupby("cost_class", dropna=False):
                    _detect_in_group(group_df)

            # Global analysis (catches outliers that groups miss)
            _detect_in_group(df)

        except Exception:
            logger.exception("iqr_detection failed")

        logger.info(
            "iqr_detection complete: %d anomalies from %d transactions",
            len(anomalies),
            len(transactions),
        )
        return anomalies

    # ──────────────────────────────────────────────────────────────
    # 3. Benford's Law Analysis
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def benford_law(transactions: List[Dict]) -> Dict:
        """Analyse first-digit distribution against Benford's Law.

        Benford's Law predicts that in many naturally occurring datasets
        the leading digit *d* appears with probability
        ``P(d) = log10(1 + 1/d)``.  Significant deviation may indicate
        data fabrication, rounding manipulation, or duplicate entries.

        Args:
            transactions: List of transaction dicts each containing an
                ``amount`` field.

        Returns:
            Dict with per-digit expected/actual percentages, chi-squared
            statistic, approximate p-value, conformity flag, list of
            suspicious digits, and ``anomaly_type``.
        """
        result: Dict[str, Any] = {
            "digits": {},
            "chi_squared": 0.0,
            "p_value_approx": 1.0,
            "conforms": True,
            "suspicious_digits": [],
            "anomaly_type": "benford",
        }

        if not transactions:
            return result

        try:
            # Extract valid first digits (ignore zeros, negatives, and amounts < 1)
            first_digits: List[int] = []
            for txn in transactions:
                try:
                    amount = abs(float(txn.get("amount", 0)))
                except (TypeError, ValueError):
                    continue

                if amount < 1:
                    continue

                # Get leading digit from the integer part
                leading = str(int(amount))[0]
                digit = int(leading)
                if 1 <= digit <= 9:
                    first_digits.append(digit)

            total = len(first_digits)
            if total < 10:
                logger.info(
                    "benford_law: only %d usable amounts — too few for analysis",
                    total,
                )
                return result

            # Expected distribution
            expected: Dict[int, float] = {}
            for d in range(1, 10):
                expected[d] = np.log10(1 + 1 / d)

            # Actual distribution
            digit_counts: Dict[int, int] = {d: 0 for d in range(1, 10)}
            for d in first_digits:
                digit_counts[d] += 1

            # Build per-digit stats and chi-squared
            chi_squared = 0.0
            suspicious_digits: List[int] = []
            digits_detail: Dict[str, Dict] = {}

            for d in range(1, 10):
                expected_pct = round(expected[d] * 100, 4)
                actual_count = digit_counts[d]
                actual_pct = round((actual_count / total) * 100, 4) if total > 0 else 0.0

                expected_count = expected[d] * total
                if expected_count > 0:
                    chi_component = ((actual_count - expected_count) ** 2) / expected_count
                    chi_squared += chi_component

                # A digit is suspicious if actual deviates from expected by
                # more than 30% of the expected value (relative threshold)
                if expected_pct > 0:
                    relative_deviation = abs(actual_pct - expected_pct) / expected_pct
                    if relative_deviation > 0.30:
                        suspicious_digits.append(d)

                digits_detail[str(d)] = {
                    "expected_pct": expected_pct,
                    "actual_pct": actual_pct,
                    "count": actual_count,
                }

            chi_squared = round(chi_squared, 4)

            # Approximate p-value using chi-squared CDF for df=8
            # Using the Wilson-Hilferty normal approximation:
            #   Z = ((chi2/df)^(1/3) - (1 - 2/(9*df))) / sqrt(2/(9*df))
            df_chi = 8
            p_value_approx = 1.0
            try:
                if chi_squared > 0:
                    k = df_chi
                    z = ((chi_squared / k) ** (1 / 3) - (1 - 2 / (9 * k))) / np.sqrt(
                        2 / (9 * k)
                    )
                    # Standard normal CDF approximation
                    p_value_approx = float(0.5 * (1 + math.erf(-z / math.sqrt(2))))
                    p_value_approx = round(max(0.0, min(1.0, p_value_approx)), 4)
            except Exception:
                p_value_approx = 0.0

            # Critical value at alpha=0.05 with df=8 is 15.507
            conforms = chi_squared < 15.51

            result.update({
                "digits": digits_detail,
                "chi_squared": chi_squared,
                "p_value_approx": p_value_approx,
                "conforms": conforms,
                "suspicious_digits": suspicious_digits,
                "anomaly_type": "benford",
            })

        except Exception:
            logger.exception("benford_law analysis failed")

        logger.info(
            "benford_law complete: chi2=%.4f, conforms=%s, suspicious=%s",
            result["chi_squared"],
            result["conforms"],
            result["suspicious_digits"],
        )
        return result

    # ──────────────────────────────────────────────────────────────
    # 4. Seasonal Anomaly Detection
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def seasonal_anomaly(
        historical_values: List[float],
        current_value: float,
        period_index: int,
        window: int = 3,
    ) -> Dict:
        """Check whether a current value deviates from seasonal expectations.

        Given a flat list of historical values ordered chronologically, the
        method extracts the values that correspond to the same *period_index*
        (e.g. the same month across years) and checks whether
        *current_value* falls more than 2 standard deviations away from
        the mean of those historical values.

        Args:
            historical_values: Chronological list of period-level values
                (e.g. monthly totals for the last N years).
            current_value: The value to test against the seasonal
                expectation.
            period_index: Zero-based index identifying the seasonal
                position (e.g. 0 = January, 11 = December for monthly
                data).
            window: Minimum number of historical observations required
                at the same period_index before flagging (default 3).

        Returns:
            Dict with ``current``, ``expected``, ``deviation_pct``,
            ``is_anomaly``, ``severity``, and ``anomaly_type``.
        """
        result: Dict[str, Any] = {
            "current": round(current_value, 4),
            "expected": None,
            "deviation_pct": 0.0,
            "is_anomaly": False,
            "severity": "low",
            "anomaly_type": "seasonal",
        }

        try:
            if not historical_values or period_index < 0:
                return result

            # Determine the cycle length.  We assume 12 periods (months)
            # unless the data is shorter, in which case we fall back to
            # the length of the historical list itself.
            cycle_length = 12 if len(historical_values) >= 12 else len(historical_values)

            # Extract values at the same seasonal position
            seasonal_vals: List[float] = []
            for i in range(len(historical_values)):
                if i % cycle_length == period_index % cycle_length:
                    seasonal_vals.append(float(historical_values[i]))

            if len(seasonal_vals) < window:
                # Not enough seasonal observations for a meaningful comparison
                result["expected"] = (
                    round(float(np.mean(seasonal_vals)), 4)
                    if seasonal_vals
                    else None
                )
                return result

            mean = float(np.mean(seasonal_vals))
            std = float(np.std(seasonal_vals, ddof=1))

            result["expected"] = round(mean, 4)

            if std == 0:
                # All historical values identical — flag only exact mismatches
                if current_value != mean:
                    result["is_anomaly"] = True
                    result["severity"] = "medium"
                    result["deviation_pct"] = round(
                        abs(current_value - mean) / abs(mean) * 100 if mean != 0 else 100.0,
                        4,
                    )
                return result

            z = abs(current_value - mean) / std
            deviation_pct = round(
                abs(current_value - mean) / abs(mean) * 100 if mean != 0 else 0.0,
                4,
            )
            result["deviation_pct"] = deviation_pct

            if z > 2.0:
                result["is_anomaly"] = True

                if z > 3.0:
                    result["severity"] = "critical"
                elif z > 2.5:
                    result["severity"] = "high"
                else:
                    result["severity"] = "medium"

        except Exception:
            logger.exception("seasonal_anomaly check failed")

        return result

    # ──────────────────────────────────────────────────────────────
    # 5. Full Detection Pipeline
    # ──────────────────────────────────────────────────────────────
    async def run_full_detection(
        self,
        db: AsyncSession,
        dataset_id: int,
        zscore_threshold: float = 2.0,
        iqr_multiplier: float = 1.5,
    ) -> Dict:
        """Execute all anomaly detection methods on a dataset and persist results.

        This is the main entry point consumed by API routes.  It loads
        every transaction for the given *dataset_id*, runs Z-score, IQR,
        and Benford analyses, deduplicates overlapping flags (keeping the
        highest severity per transaction), and writes new ``Anomaly``
        rows to the database.

        Args:
            db: Active async database session.
            dataset_id: Primary key of the dataset to analyse.
            zscore_threshold: Z-score detection threshold (default 2.0).
            iqr_multiplier: IQR fence multiplier (default 1.5).

        Returns:
            Summary dict with counts, method breakdowns, Benford
            analysis, and the top 20 most severe anomalies.
        """
        summary: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "total_transactions": 0,
            "anomalies_found": 0,
            "by_method": {"zscore": 0, "iqr": 0},
            "by_severity": {"critical": 0, "high": 0, "medium": 0},
            "benford_analysis": {},
            "anomalies": [],
        }

        try:
            # ----------------------------------------------------------
            # 1. Load transactions for the dataset
            # ----------------------------------------------------------
            logger.info(
                "run_full_detection: starting for dataset_id=%d", dataset_id
            )

            stmt = select(Transaction).where(
                Transaction.dataset_id == dataset_id
            )
            result = await db.execute(stmt)
            transactions_orm = result.scalars().all()

            if not transactions_orm:
                logger.warning(
                    "run_full_detection: no transactions found for dataset_id=%d",
                    dataset_id,
                )
                return summary

            # Convert ORM objects to plain dicts
            txn_dicts: List[Dict] = []
            for txn in transactions_orm:
                txn_dicts.append({
                    "id": txn.id,
                    "amount": float(txn.amount) if txn.amount is not None else 0.0,
                    "cost_class": txn.cost_class or "unknown",
                    "counterparty": txn.counterparty or "unknown",
                    "dept": txn.dept or "unknown",
                    "type": txn.type or "Expense",
                    "date": txn.date or "",
                })

            summary["total_transactions"] = len(txn_dicts)
            logger.info(
                "run_full_detection: loaded %d transactions", len(txn_dicts)
            )

            # ----------------------------------------------------------
            # 2. Run detection methods
            # ----------------------------------------------------------
            zscore_anomalies = self.zscore_detection(
                txn_dicts, threshold=zscore_threshold
            )
            iqr_anomalies = self.iqr_detection(
                txn_dicts, multiplier=iqr_multiplier
            )
            benford_result = self.benford_law(txn_dicts)

            summary["benford_analysis"] = benford_result
            summary["by_method"]["zscore"] = len(zscore_anomalies)
            summary["by_method"]["iqr"] = len(iqr_anomalies)

            # ----------------------------------------------------------
            # 3. Deduplicate (same transaction from multiple methods)
            # ----------------------------------------------------------
            # Key: transaction_id -> best anomaly dict (highest severity)
            best_by_txn: Dict[int, Dict] = {}

            all_raw = zscore_anomalies + iqr_anomalies
            for anom in all_raw:
                txn_id = anom["transaction_id"]
                existing = best_by_txn.get(txn_id)

                if existing is None:
                    best_by_txn[txn_id] = anom
                else:
                    # Keep the one with the higher severity; on tie, prefer
                    # whichever has the larger absolute score (z_score or
                    # distance from IQR fence).
                    existing_rank = _SEVERITY_RANK.get(existing["severity"], 0)
                    new_rank = _SEVERITY_RANK.get(anom["severity"], 0)

                    if new_rank > existing_rank:
                        # Merge method info so we know both methods flagged it
                        anom["anomaly_type"] = (
                            f"{existing['anomaly_type']}+{anom['anomaly_type']}"
                            if existing["anomaly_type"] != anom["anomaly_type"]
                            else anom["anomaly_type"]
                        )
                        best_by_txn[txn_id] = anom
                    elif new_rank == existing_rank:
                        # Same severity — just note the additional method
                        if anom["anomaly_type"] not in existing["anomaly_type"]:
                            existing["anomaly_type"] = (
                                f"{existing['anomaly_type']}+{anom['anomaly_type']}"
                            )

            unique_anomalies = list(best_by_txn.values())

            # ----------------------------------------------------------
            # 4. Count by severity
            # ----------------------------------------------------------
            for anom in unique_anomalies:
                sev = anom.get("severity", "medium")
                if sev in summary["by_severity"]:
                    summary["by_severity"][sev] += 1

            summary["anomalies_found"] = len(unique_anomalies)

            # ----------------------------------------------------------
            # 5. Persist to Anomaly table
            # ----------------------------------------------------------
            # Remove existing anomalies for this dataset to avoid duplicates
            # on re-runs.
            from sqlalchemy import delete as sa_delete

            await db.execute(
                sa_delete(Anomaly).where(Anomaly.dataset_id == dataset_id)
            )

            for anom in unique_anomalies:
                # Build a human-readable description
                amount = anom.get("amount", 0)
                severity = anom.get("severity", "medium")
                anomaly_type = anom.get("anomaly_type", "unknown")

                if "zscore" in anomaly_type:
                    score_val = abs(anom.get("z_score", 0))
                    description = (
                        f"Amount {amount:,.2f} deviates {score_val:.2f} "
                        f"standard deviations from group mean "
                        f"{anom.get('mean', 0):,.2f} "
                        f"(group: {anom.get('group', 'N/A')})"
                    )
                elif "iqr" in anomaly_type:
                    description = (
                        f"Amount {amount:,.2f} falls outside IQR fences "
                        f"[{anom.get('lower_bound', 0):,.2f}, "
                        f"{anom.get('upper_bound', 0):,.2f}]"
                    )
                else:
                    description = f"Anomalous amount {amount:,.2f} detected via {anomaly_type}"

                # Determine a numeric score for the Anomaly.score column
                score = abs(anom.get("z_score", 0.0))
                if score == 0.0 and "iqr" in anomaly_type:
                    iqr_val = anom.get("iqr", 1)
                    if iqr_val and iqr_val != 0:
                        lb = anom.get("lower_bound", 0)
                        ub = anom.get("upper_bound", 0)
                        if amount < lb:
                            score = abs(amount - lb) / iqr_val
                        elif amount > ub:
                            score = abs(amount - ub) / iqr_val

                # Strip merged type string to primary method for the DB column
                primary_type = anomaly_type.split("+")[0]

                db_anomaly = Anomaly(
                    dataset_id=dataset_id,
                    transaction_id=anom.get("transaction_id"),
                    anomaly_type=primary_type,
                    severity=severity,
                    score=round(score, 4),
                    description=description,
                    details=json.loads(json.dumps(anom, default=str)),
                    is_acknowledged=False,
                )
                db.add(db_anomaly)

            await db.flush()

            # ----------------------------------------------------------
            # 6. Build response — top 20 most severe anomalies
            # ----------------------------------------------------------
            sorted_anomalies = sorted(
                unique_anomalies,
                key=lambda a: (
                    _SEVERITY_RANK.get(a.get("severity", "medium"), 0),
                    abs(a.get("z_score", 0) or 0),
                ),
                reverse=True,
            )
            summary["anomalies"] = sorted_anomalies[:20]

            logger.info(
                "run_full_detection complete for dataset_id=%d: "
                "%d total anomalies (%d critical, %d high, %d medium)",
                dataset_id,
                summary["anomalies_found"],
                summary["by_severity"]["critical"],
                summary["by_severity"]["high"],
                summary["by_severity"]["medium"],
            )

        except Exception:
            logger.exception(
                "run_full_detection failed for dataset_id=%d", dataset_id
            )
            raise

        return _to_python(summary)
