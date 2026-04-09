"""
schema_memory.py — Schema Memory + Pattern Fingerprinting
==========================================================
The self-learning layer on top of Hypothesis-Driven Parsing.

Every time the system successfully parses a spreadsheet, it stores a
structural fingerprint. When a new file arrives, the system compares
its fingerprint against known patterns and boosts the matching
hypothesis.

This makes the parser self-improving:
    - First time: full hypothesis search
    - Second time same format: instant match + verification
    - N-th time: near-zero ambiguity

Fingerprint dimensions:
    1. Column count & positions
    2. Header keyword signature (sorted set of detected roles)
    3. Data type distribution per column (numeric %, string %, date %)
    4. Account code format pattern (e.g., "d4" = 4-digit codes)
    5. Numeric column positions
    6. Row count bucket (10s, 100s, 1000s)
    7. Filename pattern (normalized)

Pattern matching uses cosine similarity on fingerprint vectors
with schema-type weighting.

Key classes:
    SchemaFingerprint    — structural signature of a spreadsheet
    SchemaMemory         — persistent store + matching engine
    FingerprintMatcher   — similarity computation
"""
from __future__ import annotations

import re
import json
import math
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── SchemaFingerprint ────────────────────────────────────────────────────────

@dataclass
class SchemaFingerprint:
    """
    Structural signature of a spreadsheet sheet.

    Captures the "shape" of the data without the actual values,
    enabling pattern matching across different files of the same format.
    """
    # Structural dimensions
    column_count: int = 0
    row_count_bucket: str = "0"          # "10s", "100s", "1000s", "10000s"
    header_roles: Tuple[str, ...] = ()   # Sorted tuple of detected roles
    header_hash: str = ""                 # SHA256 of normalized header text
    numeric_col_positions: Tuple[int, ...] = ()   # Positions of numeric cols
    text_col_positions: Tuple[int, ...] = ()      # Positions of text cols
    date_col_positions: Tuple[int, ...] = ()      # Positions of date cols

    # Data type distribution (per column index → type ratios)
    col_type_signatures: Dict[int, Dict[str, float]] = field(default_factory=dict)

    # Account code patterns
    account_code_pattern: str = ""        # Dominant pattern like "d4", "d2", "d4xd2"
    account_code_col_idx: Optional[int] = None

    # Filename pattern (normalized)
    filename_pattern: str = ""            # Lowercase, no numbers, no date

    # Metadata
    schema_type: str = ""
    confidence: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    match_count: int = 0
    source_filenames: List[str] = field(default_factory=list)

    @property
    def fingerprint_id(self) -> str:
        """Generate a unique ID from structural dimensions."""
        sig = (
            f"{self.column_count}|"
            f"{','.join(self.header_roles)}|"
            f"{','.join(str(p) for p in self.numeric_col_positions)}|"
            f"{self.account_code_pattern}|"
            f"{self.row_count_bucket}"
        )
        return hashlib.sha256(sig.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint_id": self.fingerprint_id,
            "column_count": self.column_count,
            "row_count_bucket": self.row_count_bucket,
            "header_roles": list(self.header_roles),
            "header_hash": self.header_hash,
            "numeric_col_positions": list(self.numeric_col_positions),
            "text_col_positions": list(self.text_col_positions),
            "date_col_positions": list(self.date_col_positions),
            "account_code_pattern": self.account_code_pattern,
            "account_code_col_idx": self.account_code_col_idx,
            "filename_pattern": self.filename_pattern,
            "schema_type": self.schema_type,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "match_count": self.match_count,
            "source_filenames": self.source_filenames[-5:],  # Keep last 5
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SchemaFingerprint":
        return cls(
            column_count=d.get("column_count", 0),
            row_count_bucket=d.get("row_count_bucket", "0"),
            header_roles=tuple(d.get("header_roles", [])),
            header_hash=d.get("header_hash", ""),
            numeric_col_positions=tuple(d.get("numeric_col_positions", [])),
            text_col_positions=tuple(d.get("text_col_positions", [])),
            date_col_positions=tuple(d.get("date_col_positions", [])),
            account_code_pattern=d.get("account_code_pattern", ""),
            account_code_col_idx=d.get("account_code_col_idx"),
            filename_pattern=d.get("filename_pattern", ""),
            schema_type=d.get("schema_type", ""),
            confidence=d.get("confidence", 0.0),
            first_seen=d.get("first_seen", ""),
            last_seen=d.get("last_seen", ""),
            match_count=d.get("match_count", 0),
            source_filenames=d.get("source_filenames", []),
        )


# ── FingerprintBuilder ───────────────────────────────────────────────────────

class FingerprintBuilder:
    """Builds SchemaFingerprint from raw sheet data."""

    def build(
        self,
        header_row: tuple,
        data_rows: List[tuple],
        filename: str = "",
        schema_type: str = "",
        confidence: float = 0.0,
        column_mapping=None,
    ) -> SchemaFingerprint:
        """Build a fingerprint from raw sheet data."""
        fp = SchemaFingerprint()

        # Column count
        fp.column_count = len(header_row)

        # Row count bucket
        n = len(data_rows)
        if n < 10:
            fp.row_count_bucket = "1s"
        elif n < 100:
            fp.row_count_bucket = "10s"
        elif n < 1000:
            fp.row_count_bucket = "100s"
        elif n < 10000:
            fp.row_count_bucket = "1000s"
        else:
            fp.row_count_bucket = "10000s"

        # Header roles (from column mapping if available)
        if column_mapping is not None:
            roles = sorted(
                r for r, idx in column_mapping.roles.items()
                if idx is not None
            )
            fp.header_roles = tuple(roles)

        # Header hash (normalized text)
        header_text = "|".join(
            str(c).lower().strip() for c in header_row if c is not None
        )
        fp.header_hash = hashlib.sha256(header_text.encode()).hexdigest()[:16]

        # Analyze column types from data
        col_types = self._analyze_column_types(data_rows, len(header_row))
        fp.col_type_signatures = col_types

        numeric_cols = []
        text_cols = []
        date_cols = []

        for col_idx, type_dist in col_types.items():
            if type_dist.get("numeric", 0) > 0.6:
                numeric_cols.append(col_idx)
            if type_dist.get("string", 0) > 0.6:
                text_cols.append(col_idx)
            if type_dist.get("date", 0) > 0.3:
                date_cols.append(col_idx)

        fp.numeric_col_positions = tuple(sorted(numeric_cols))
        fp.text_col_positions = tuple(sorted(text_cols))
        fp.date_col_positions = tuple(sorted(date_cols))

        # Account code pattern detection
        acct_col = None
        if column_mapping is not None:
            acct_col = column_mapping.roles.get("account_code")
        if acct_col is None:
            # Try to find account code column from text columns
            for col_idx in text_cols:
                vals = self._extract_col_values(data_rows, col_idx, str)
                if vals and self._looks_like_account_codes(vals):
                    acct_col = col_idx
                    break

        if acct_col is not None:
            fp.account_code_col_idx = acct_col
            codes = self._extract_col_values(data_rows, acct_col, str)
            fp.account_code_pattern = self._detect_code_pattern(codes)

        # Filename pattern
        fp.filename_pattern = self._normalize_filename(filename)

        # Metadata
        fp.schema_type = schema_type
        fp.confidence = confidence
        now = datetime.now(timezone.utc).isoformat()
        fp.first_seen = now
        fp.last_seen = now
        fp.match_count = 1
        fp.source_filenames = [filename] if filename else []

        return fp

    def _analyze_column_types(
        self,
        data_rows: List[tuple],
        num_cols: int,
    ) -> Dict[int, Dict[str, float]]:
        """Analyze data type distribution for each column."""
        sample = data_rows[:min(50, len(data_rows))]
        result: Dict[int, Dict[str, float]] = {}

        from datetime import datetime as dt

        for col_idx in range(num_cols):
            counts = {"numeric": 0, "string": 0, "date": 0, "null": 0, "other": 0}
            total = 0

            for row in sample:
                if col_idx >= len(row):
                    counts["null"] += 1
                    total += 1
                    continue

                val = row[col_idx]
                total += 1

                if val is None:
                    counts["null"] += 1
                elif isinstance(val, (int, float)):
                    counts["numeric"] += 1
                elif isinstance(val, dt):
                    counts["date"] += 1
                elif isinstance(val, str):
                    # Check if string is actually a number
                    try:
                        float(val.replace(",", "").replace(" ", ""))
                        counts["numeric"] += 1
                    except (ValueError, AttributeError):
                        # Check if string is a date
                        if re.match(r'\d{4}[-/]\d{2}[-/]\d{2}', val):
                            counts["date"] += 1
                        else:
                            counts["string"] += 1
                else:
                    counts["other"] += 1

            if total > 0:
                result[col_idx] = {
                    k: round(v / total, 2) for k, v in counts.items()
                }

        return result

    def _extract_col_values(
        self,
        data_rows: List[tuple],
        col_idx: int,
        type_filter=None,
    ) -> List[str]:
        """Extract column values as strings."""
        vals = []
        for row in data_rows[:100]:
            if col_idx < len(row) and row[col_idx] is not None:
                val = row[col_idx]
                if type_filter is None or isinstance(val, type_filter):
                    vals.append(str(val).strip())
        return vals

    def _looks_like_account_codes(self, values: List[str]) -> bool:
        """Heuristic: do these values look like account codes?"""
        if not values:
            return False
        code_like = sum(
            1 for v in values
            if re.match(r'^[\d.Xx\-]{1,10}$', v)
        )
        return code_like / len(values) > 0.5

    def _detect_code_pattern(self, codes: List[str]) -> str:
        """Detect the dominant account code format pattern."""
        if not codes:
            return ""

        patterns: Dict[str, int] = {}
        for code in codes:
            pat = ""
            i = 0
            while i < len(code):
                if code[i].isdigit():
                    # Count consecutive digits
                    count = 0
                    while i < len(code) and code[i].isdigit():
                        count += 1
                        i += 1
                    pat += f"d{count}"
                elif code[i].isalpha():
                    count = 0
                    while i < len(code) and code[i].isalpha():
                        count += 1
                        i += 1
                    pat += f"a{count}"
                else:
                    pat += code[i]
                    i += 1
            patterns[pat] = patterns.get(pat, 0) + 1

        # Return dominant pattern
        if patterns:
            return max(patterns, key=patterns.get)
        return ""

    def _normalize_filename(self, filename: str) -> str:
        """Normalize filename to a pattern (remove dates, numbers)."""
        name = filename.lower()
        # Remove extension
        name = re.sub(r'\.\w+$', '', name)
        # Remove dates (2024-01, Jan2024, etc.)
        name = re.sub(r'\d{4}[-_./]?\d{2}[-_./]?\d{0,2}', '', name)
        name = re.sub(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*\d{0,4}', '', name)
        # Remove standalone numbers
        name = re.sub(r'\d+', '', name)
        # Normalize whitespace and separators
        name = re.sub(r'[\s_\-./]+', '_', name)
        name = name.strip('_')
        return name


# ── FingerprintMatcher ───────────────────────────────────────────────────────

class FingerprintMatcher:
    """
    Compares fingerprints using weighted similarity.

    Similarity dimensions:
        - Header hash exact match (strongest signal)
        - Header roles overlap (Jaccard similarity)
        - Column count proximity
        - Numeric/text column position overlap
        - Account code pattern match
        - Row count bucket proximity
        - Filename pattern similarity
    """

    # Dimension weights
    _WEIGHTS = {
        "header_hash":          0.30,  # Exact header match is strongest
        "header_roles":         0.20,  # Same detected roles
        "col_positions":        0.15,  # Same numeric/text positions
        "account_code_pattern": 0.15,  # Same code format
        "column_count":         0.10,  # Same number of columns
        "row_bucket":           0.05,  # Similar size
        "filename_pattern":     0.05,  # Similar filename
    }

    def similarity(
        self,
        fp1: SchemaFingerprint,
        fp2: SchemaFingerprint,
    ) -> float:
        """Compute weighted similarity between two fingerprints (0.0 to 1.0)."""
        score = 0.0

        # Header hash exact match
        if fp1.header_hash and fp2.header_hash:
            if fp1.header_hash == fp2.header_hash:
                score += self._WEIGHTS["header_hash"]

        # Header roles Jaccard similarity
        if fp1.header_roles or fp2.header_roles:
            set1 = set(fp1.header_roles)
            set2 = set(fp2.header_roles)
            if set1 or set2:
                jaccard = len(set1 & set2) / len(set1 | set2)
                score += jaccard * self._WEIGHTS["header_roles"]

        # Column position overlap
        num_overlap = self._position_overlap(
            fp1.numeric_col_positions, fp2.numeric_col_positions
        )
        text_overlap = self._position_overlap(
            fp1.text_col_positions, fp2.text_col_positions
        )
        avg_overlap = (num_overlap + text_overlap) / 2
        score += avg_overlap * self._WEIGHTS["col_positions"]

        # Account code pattern match
        if fp1.account_code_pattern and fp2.account_code_pattern:
            if fp1.account_code_pattern == fp2.account_code_pattern:
                score += self._WEIGHTS["account_code_pattern"]

        # Column count proximity
        if fp1.column_count > 0 and fp2.column_count > 0:
            diff = abs(fp1.column_count - fp2.column_count)
            proximity = max(0, 1 - diff / max(fp1.column_count, fp2.column_count))
            score += proximity * self._WEIGHTS["column_count"]

        # Row count bucket
        if fp1.row_count_bucket == fp2.row_count_bucket:
            score += self._WEIGHTS["row_bucket"]

        # Filename pattern
        if fp1.filename_pattern and fp2.filename_pattern:
            if fp1.filename_pattern == fp2.filename_pattern:
                score += self._WEIGHTS["filename_pattern"]

        return round(score, 4)

    def _position_overlap(
        self,
        pos1: Tuple[int, ...],
        pos2: Tuple[int, ...],
    ) -> float:
        """Compute Jaccard overlap of column positions."""
        if not pos1 and not pos2:
            return 0.5  # Neutral
        set1 = set(pos1)
        set2 = set(pos2)
        if not set1 and not set2:
            return 0.5
        union = set1 | set2
        if not union:
            return 0.5
        return len(set1 & set2) / len(union)


# ── SchemaMemory ─────────────────────────────────────────────────────────────

class SchemaMemory:
    """
    Persistent memory of successful parse patterns.

    Stores fingerprints of spreadsheets that were successfully parsed,
    enabling faster and more accurate parsing of similar files in the future.

    Storage:
        - In-memory cache for fast lookups
        - JSON file persistence for cross-session learning
        - Optional KG integration for rich pattern storage

    Usage flow:
        1. After successful parse → record_successful_parse()
        2. Before parsing new file → find_match()
        3. If match found → boost matching hypothesis in HDP
    """

    MAX_PATTERNS = 500  # Maximum stored patterns
    MATCH_THRESHOLD = 0.55  # Minimum similarity for a match

    def __init__(self, storage_path: Optional[str] = None):
        self._patterns: Dict[str, SchemaFingerprint] = {}
        self._builder = FingerprintBuilder()
        self._matcher = FingerprintMatcher()
        self._storage_path = storage_path or self._default_storage_path()
        self._load()

    def _default_storage_path(self) -> str:
        """Default path for schema memory persistence."""
        return str(Path(__file__).parent.parent.parent / "schema_memory.json")

    def record_successful_parse(
        self,
        header_row: tuple,
        data_rows: List[tuple],
        schema_type: str,
        confidence: float,
        column_mapping=None,
        filename: str = "",
    ) -> str:
        """
        Record a successful parse pattern for future matching.
        Returns the fingerprint ID.
        """
        fp = self._builder.build(
            header_row=header_row,
            data_rows=data_rows,
            filename=filename,
            schema_type=schema_type,
            confidence=confidence,
            column_mapping=column_mapping,
        )

        fp_id = fp.fingerprint_id
        existing = self._patterns.get(fp_id)

        if existing:
            # Update existing pattern
            existing.match_count += 1
            existing.last_seen = datetime.now(timezone.utc).isoformat()
            if filename and filename not in existing.source_filenames:
                existing.source_filenames.append(filename)
                existing.source_filenames = existing.source_filenames[-5:]
            # Update confidence to max seen
            if confidence > existing.confidence:
                existing.confidence = confidence
        else:
            # Add new pattern
            self._patterns[fp_id] = fp

        # Evict oldest if over capacity
        self._evict_if_needed()

        # Persist to disk
        self._save()

        logger.info(
            "SchemaMemory: recorded pattern %s (%s, conf=%.2f, total=%d)",
            fp_id, schema_type, confidence, len(self._patterns)
        )

        return fp_id

    def find_match(
        self,
        header_row: tuple,
        data_rows: List[tuple],
        filename: str = "",
    ) -> Optional[Tuple[str, float]]:
        """
        Find the best matching known pattern.

        Returns (schema_type, confidence) if match found, None otherwise.
        """
        if not self._patterns:
            return None

        # Build fingerprint of the incoming sheet
        query_fp = self._builder.build(
            header_row=header_row,
            data_rows=data_rows,
            filename=filename,
        )

        best_match: Optional[SchemaFingerprint] = None
        best_similarity = 0.0

        for fp_id, stored_fp in self._patterns.items():
            sim = self._matcher.similarity(query_fp, stored_fp)
            if sim > best_similarity:
                best_similarity = sim
                best_match = stored_fp

        if best_match and best_similarity >= self.MATCH_THRESHOLD:
            # Boost confidence based on how many times we've seen this pattern
            experience_boost = min(best_match.match_count * 0.02, 0.1)
            match_confidence = min(
                best_similarity + experience_boost,
                1.0
            )

            logger.info(
                "SchemaMemory: matched %s (similarity=%.3f, "
                "confidence=%.3f, seen=%d times)",
                best_match.schema_type, best_similarity,
                match_confidence, best_match.match_count
            )

            return (best_match.schema_type, match_confidence)

        return None

    def get_all_patterns(self) -> List[Dict[str, Any]]:
        """Return all stored patterns as dicts."""
        return [fp.to_dict() for fp in self._patterns.values()]

    def pattern_count(self) -> int:
        """Return number of stored patterns."""
        return len(self._patterns)

    def clear(self) -> None:
        """Clear all stored patterns."""
        self._patterns.clear()
        self._save()

    def status(self) -> Dict[str, Any]:
        """Return schema memory status."""
        type_counts: Dict[str, int] = {}
        total_matches = 0
        for fp in self._patterns.values():
            type_counts[fp.schema_type] = type_counts.get(fp.schema_type, 0) + 1
            total_matches += fp.match_count

        return {
            "total_patterns": len(self._patterns),
            "total_matches": total_matches,
            "by_schema_type": type_counts,
            "storage_path": self._storage_path,
            "max_patterns": self.MAX_PATTERNS,
            "match_threshold": self.MATCH_THRESHOLD,
        }

    def _evict_if_needed(self) -> None:
        """Evict least-used patterns if over capacity."""
        if len(self._patterns) <= self.MAX_PATTERNS:
            return

        # Sort by (match_count ASC, last_seen ASC) → evict least used, oldest first
        sorted_ids = sorted(
            self._patterns.keys(),
            key=lambda fp_id: (
                self._patterns[fp_id].match_count,
                self._patterns[fp_id].last_seen,
            ),
        )

        # Remove bottom 10%
        to_remove = max(1, len(sorted_ids) // 10)
        for fp_id in sorted_ids[:to_remove]:
            del self._patterns[fp_id]

        logger.info(
            "SchemaMemory: evicted %d patterns, %d remaining",
            to_remove, len(self._patterns)
        )

    def _save(self) -> None:
        """Persist patterns to JSON file."""
        try:
            data = {
                "version": "1.0",
                "updated": datetime.now(timezone.utc).isoformat(),
                "patterns": {
                    fp_id: fp.to_dict()
                    for fp_id, fp in self._patterns.items()
                },
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=2)
        except Exception as e:
            logger.warning("SchemaMemory: save failed: %s", e)

    def _load(self) -> None:
        """Load patterns from JSON file."""
        try:
            path = Path(self._storage_path)
            if not path.exists():
                return

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            patterns = data.get("patterns", {})
            for fp_id, fp_dict in patterns.items():
                self._patterns[fp_id] = SchemaFingerprint.from_dict(fp_dict)

            logger.info(
                "SchemaMemory: loaded %d patterns from %s",
                len(self._patterns), self._storage_path
            )
        except Exception as e:
            logger.warning("SchemaMemory: load failed: %s", e)


# ── Module-level singleton ───────────────────────────────────────────────────
schema_memory = SchemaMemory()
