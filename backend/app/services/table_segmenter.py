"""
table_segmenter.py -- Structural Table Extraction Engine
==========================================================
Detects multiple table regions within a single Excel sheet.

Real accounting exports often contain:
    - Title blocks / company headers
    - Multiple tables (Trial Balance + KPI summary)
    - Notes / footnotes
    - Empty row separators
    - Decorative borders

This module segments a sheet into distinct table regions
BEFORE hypothesis-driven parsing runs on each one.

Architecture:
    Raw Sheet
        |
    TableSegmenter.segment()
        |
    [Region A, Region B, Region C, ...]
        |
    Each region -> HDP.parse_sheet()
        |
    Constraint Graph validates cross-region consistency

Detection signals:
    1. Empty row gaps (2+ consecutive empty rows = boundary)
    2. Header-like rows mid-sheet (new table starts)
    3. Column structure changes (different column counts)
    4. Data type distribution shifts
    5. Title/note detection (single-cell wide rows)

Key classes:
    TableRegion     -- one contiguous table within a sheet
    TableSegmenter  -- segments sheet into regions
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TableRegion:
    """
    A contiguous table region within a sheet.

    Each region has its own header row and data rows,
    and can be independently parsed by HDP.
    """
    region_id: int = 0
    start_row: int = 0            # Absolute row index in the sheet
    end_row: int = 0              # Absolute row index (inclusive)
    header_row_idx: int = 0       # Absolute index of this region's header
    header_row: tuple = ()        # The actual header tuple
    data_rows: List[tuple] = field(default_factory=list)
    region_type: str = "table"    # "table", "title_block", "notes", "empty"
    column_count: int = 0
    data_density: float = 0.0     # % of non-null cells
    confidence: float = 0.0       # Confidence this is a real table

    @property
    def row_count(self) -> int:
        return len(self.data_rows)

    def to_rows(self) -> List[tuple]:
        """Return header + data as a single row list (for HDP input)."""
        return [self.header_row] + self.data_rows

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_id": self.region_id,
            "start_row": self.start_row,
            "end_row": self.end_row,
            "header_row_idx": self.header_row_idx,
            "region_type": self.region_type,
            "column_count": self.column_count,
            "data_rows": self.row_count,
            "data_density": round(self.data_density, 3),
            "confidence": round(self.confidence, 3),
        }


@dataclass
class SegmentationResult:
    """Result of sheet segmentation."""
    regions: List[TableRegion] = field(default_factory=list)
    total_rows: int = 0
    title_block: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def table_count(self) -> int:
        return sum(1 for r in self.regions if r.region_type == "table")

    def get_tables(self) -> List[TableRegion]:
        """Return only table regions (not title blocks or notes)."""
        return [r for r in self.regions if r.region_type == "table"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "regions": [r.to_dict() for r in self.regions],
            "table_count": self.table_count,
            "title_block": self.title_block,
            "notes_count": len(self.notes),
            "warnings": self.warnings,
        }


class TableSegmenter:
    """
    Segments an Excel sheet into distinct table regions.

    Strategy:
    1. Scan for empty row gaps (potential boundaries)
    2. Within each segment, detect header rows
    3. Classify segments as table, title_block, or notes
    4. Validate each table region has minimum viable structure
    5. Merge adjacent regions if they appear to be one table

    Parameters:
        min_gap_rows: Minimum consecutive empty rows to form a boundary (default: 2)
        min_table_rows: Minimum data rows for a valid table (default: 2)
        min_table_cols: Minimum columns for a valid table (default: 2)
    """

    def __init__(
        self,
        min_gap_rows: int = 2,
        min_table_rows: int = 2,
        min_table_cols: int = 2,
    ):
        self.min_gap_rows = min_gap_rows
        self.min_table_rows = min_table_rows
        self.min_table_cols = min_table_cols

        # Import header keywords from ingestion_intelligence
        try:
            from app.services.ingestion_intelligence import FileStructureDetector
            self._header_detector = FileStructureDetector()
        except ImportError:
            self._header_detector = None

    def segment(self, rows: List[tuple]) -> SegmentationResult:
        """
        Segment a sheet into table regions.

        Returns SegmentationResult with all detected regions.
        """
        if not rows:
            return SegmentationResult(total_rows=0)

        result = SegmentationResult(total_rows=len(rows))

        # Step 1: Find empty row boundaries
        boundaries = self._find_boundaries(rows)

        # Step 2: Split into raw segments
        raw_segments = self._split_at_boundaries(rows, boundaries)

        # Step 3: Classify each segment
        regions: List[TableRegion] = []
        region_id = 0

        for seg_start, seg_end, seg_rows in raw_segments:
            if not seg_rows:
                continue

            classification = self._classify_segment(seg_rows, seg_start)

            if classification == "title_block":
                title_text = self._extract_title_text(seg_rows)
                if title_text:
                    result.title_block = title_text
                region = TableRegion(
                    region_id=region_id,
                    start_row=seg_start,
                    end_row=seg_end,
                    header_row_idx=seg_start,
                    header_row=seg_rows[0] if seg_rows else (),
                    data_rows=[],
                    region_type="title_block",
                    column_count=self._count_cols(seg_rows),
                    data_density=self._compute_density(seg_rows),
                    confidence=0.3,
                )
                regions.append(region)

            elif classification == "notes":
                notes_text = self._extract_notes(seg_rows)
                result.notes.extend(notes_text)
                region = TableRegion(
                    region_id=region_id,
                    start_row=seg_start,
                    end_row=seg_end,
                    header_row_idx=seg_start,
                    header_row=seg_rows[0] if seg_rows else (),
                    data_rows=seg_rows[1:] if len(seg_rows) > 1 else [],
                    region_type="notes",
                    column_count=self._count_cols(seg_rows),
                    data_density=self._compute_density(seg_rows),
                    confidence=0.2,
                )
                regions.append(region)

            elif classification == "table":
                # Find header within this segment
                header_idx = self._find_header_in_segment(seg_rows)
                header_row = seg_rows[header_idx]
                data_rows = seg_rows[header_idx + 1:]

                if len(data_rows) >= self.min_table_rows:
                    col_count = self._count_cols(seg_rows)
                    density = self._compute_density(data_rows)
                    confidence = self._compute_table_confidence(
                        header_row, data_rows, col_count, density
                    )

                    region = TableRegion(
                        region_id=region_id,
                        start_row=seg_start,
                        end_row=seg_end,
                        header_row_idx=seg_start + header_idx,
                        header_row=header_row,
                        data_rows=data_rows,
                        region_type="table",
                        column_count=col_count,
                        data_density=density,
                        confidence=confidence,
                    )
                    regions.append(region)
                else:
                    # Too few rows for a table — treat as notes
                    region = TableRegion(
                        region_id=region_id,
                        start_row=seg_start,
                        end_row=seg_end,
                        header_row_idx=seg_start,
                        header_row=seg_rows[0] if seg_rows else (),
                        data_rows=seg_rows[1:] if len(seg_rows) > 1 else [],
                        region_type="notes",
                        column_count=self._count_cols(seg_rows),
                        data_density=self._compute_density(seg_rows),
                        confidence=0.1,
                    )
                    regions.append(region)

            region_id += 1

        # Step 4: Check for header-like rows within large segments
        # (a single segment might contain two tables without empty gap)
        expanded_regions = []
        for region in regions:
            if region.region_type == "table" and region.row_count > 15:
                sub_regions = self._check_for_subtables(region)
                if len(sub_regions) > 1:
                    expanded_regions.extend(sub_regions)
                    result.warnings.append(
                        f"Region {region.region_id} split into "
                        f"{len(sub_regions)} sub-tables"
                    )
                    continue
            expanded_regions.append(region)

        # Re-number region IDs
        for i, r in enumerate(expanded_regions):
            r.region_id = i

        result.regions = expanded_regions
        return result

    def _find_boundaries(self, rows: List[tuple]) -> List[Tuple[int, int]]:
        """
        Find empty row gap boundaries.

        Returns list of (gap_start, gap_end) indices where
        consecutive empty rows were found.
        """
        boundaries: List[Tuple[int, int]] = []
        i = 0
        n = len(rows)

        while i < n:
            if self._is_empty_row(rows[i]):
                gap_start = i
                while i < n and self._is_empty_row(rows[i]):
                    i += 1
                gap_end = i - 1
                gap_length = gap_end - gap_start + 1

                if gap_length >= self.min_gap_rows:
                    boundaries.append((gap_start, gap_end))
            else:
                i += 1

        return boundaries

    def _split_at_boundaries(
        self,
        rows: List[tuple],
        boundaries: List[Tuple[int, int]],
    ) -> List[Tuple[int, int, List[tuple]]]:
        """
        Split rows at boundary gaps.

        Returns list of (start_idx, end_idx, rows) segments.
        """
        if not boundaries:
            # No boundaries → entire sheet is one segment
            return [(0, len(rows) - 1, rows)]

        segments: List[Tuple[int, int, List[tuple]]] = []
        prev_end = 0

        for gap_start, gap_end in boundaries:
            if gap_start > prev_end:
                seg_rows = rows[prev_end:gap_start]
                if seg_rows and any(any(r) for r in seg_rows):
                    segments.append((prev_end, gap_start - 1, seg_rows))
            prev_end = gap_end + 1

        # Last segment after final boundary
        if prev_end < len(rows):
            seg_rows = rows[prev_end:]
            if seg_rows and any(any(r) for r in seg_rows):
                segments.append((prev_end, len(rows) - 1, seg_rows))

        return segments

    def _classify_segment(
        self,
        seg_rows: List[tuple],
        seg_start: int,
    ) -> str:
        """
        Classify a segment as 'table', 'title_block', or 'notes'.

        Heuristics:
        - Title block: 1-3 rows, mostly single-cell, at top of sheet
        - Notes: text-heavy rows, typically at bottom, few columns used
        - Table: structured data with header + multiple data rows
        """
        if not seg_rows:
            return "notes"

        n_rows = len(seg_rows)
        col_count = self._count_cols(seg_rows)

        # Title block detection: at top of sheet, few rows, wide single cells
        if seg_start < 5 and n_rows <= 4:
            # Check if most rows have only 1-2 cells filled
            single_cell_rows = sum(
                1 for row in seg_rows
                if sum(1 for c in row if c is not None) <= 2
            )
            if single_cell_rows / max(n_rows, 1) > 0.5:
                return "title_block"

        # Notes detection: text-heavy, few columns, at end or few rows
        if n_rows <= 3 and col_count <= 2:
            text_ratio = self._compute_text_ratio(seg_rows)
            if text_ratio > 0.7:
                return "notes"

        # Table: enough rows and columns
        if n_rows >= self.min_table_rows + 1 and col_count >= self.min_table_cols:
            return "table"

        # Short segments with some structure
        if n_rows >= 2 and col_count >= 2:
            density = self._compute_density(seg_rows)
            if density > 0.3:
                return "table"

        return "notes"

    def _find_header_in_segment(self, seg_rows: List[tuple]) -> int:
        """Find the header row within a segment."""
        if self._header_detector is not None:
            return self._header_detector.find_header_row(seg_rows)

        # Fallback: first row with mostly text
        for i, row in enumerate(seg_rows[:5]):
            if not any(row):
                continue
            non_null = sum(1 for c in row if c is not None)
            text = sum(1 for c in row if isinstance(c, str))
            if non_null > 0 and text / non_null > 0.5:
                return i
        return 0

    def _check_for_subtables(self, region: TableRegion) -> List[TableRegion]:
        """
        Check if a single region actually contains multiple tables
        separated by header-like rows (without empty gaps).

        Returns list of sub-regions if split detected, or [region] if not.
        """
        data_rows = region.data_rows
        if len(data_rows) < 10:
            return [region]

        # Look for rows that look like headers within the data
        potential_splits: List[int] = []

        for i, row in enumerate(data_rows):
            if i < 3:  # Skip first few rows
                continue
            if not any(row):
                continue

            score = self._header_likelihood(row)
            if score > 5.0:  # High header probability
                # Verify: rows AFTER this look different from rows BEFORE
                if self._structure_changes_at(data_rows, i):
                    potential_splits.append(i)

        if not potential_splits:
            return [region]

        # Split region at detected header positions
        sub_regions: List[TableRegion] = []
        prev_start = 0
        base_row = region.start_row + 1  # +1 for original header

        for split_idx in potential_splits:
            if split_idx - prev_start < self.min_table_rows:
                continue

            sub_data = data_rows[prev_start:split_idx]
            if len(sub_data) >= self.min_table_rows:
                sub = TableRegion(
                    region_id=0,
                    start_row=base_row + prev_start,
                    end_row=base_row + split_idx - 1,
                    header_row_idx=(
                        region.header_row_idx if prev_start == 0
                        else base_row + prev_start - 1
                    ),
                    header_row=(
                        region.header_row if prev_start == 0
                        else data_rows[prev_start - 1]
                    ),
                    data_rows=sub_data,
                    region_type="table",
                    column_count=self._count_cols(sub_data),
                    data_density=self._compute_density(sub_data),
                    confidence=region.confidence * 0.9,
                )
                sub_regions.append(sub)

            prev_start = split_idx + 1

        # Last sub-region
        remaining = data_rows[prev_start:]
        if len(remaining) >= self.min_table_rows:
            sub = TableRegion(
                region_id=0,
                start_row=base_row + prev_start,
                end_row=region.end_row,
                header_row_idx=base_row + prev_start - 1,
                header_row=data_rows[prev_start - 1] if prev_start > 0 else region.header_row,
                data_rows=remaining,
                region_type="table",
                column_count=self._count_cols(remaining),
                data_density=self._compute_density(remaining),
                confidence=region.confidence * 0.9,
            )
            sub_regions.append(sub)

        return sub_regions if len(sub_regions) >= 2 else [region]

    def _header_likelihood(self, row: tuple) -> float:
        """Score how likely a row is to be a header."""
        if not any(row):
            return -1

        non_null = sum(1 for c in row if c is not None)
        text_cols = sum(1 for c in row if isinstance(c, str))
        num_cols = sum(1 for c in row if isinstance(c, (int, float)))

        if non_null == 0:
            return -1

        text_ratio = text_cols / non_null
        score = text_ratio * 2 - num_cols * 1.0

        # Check for header keywords
        if self._header_detector is not None:
            try:
                score = self._header_detector._header_score(row)
            except Exception:
                pass

        return score

    def _structure_changes_at(self, rows: List[tuple], idx: int) -> bool:
        """Check if the column structure changes around a row index."""
        if idx < 3 or idx >= len(rows) - 3:
            return False

        # Compare column type distribution before vs after
        before_cols = self._col_type_signature(rows[max(0, idx - 3):idx])
        after_cols = self._col_type_signature(rows[idx + 1:min(len(rows), idx + 4)])

        if not before_cols or not after_cols:
            return False

        # If the number of used columns differs significantly
        if abs(len(before_cols) - len(after_cols)) >= 2:
            return True

        # If the type distribution differs
        common_cols = set(before_cols.keys()) & set(after_cols.keys())
        if not common_cols:
            return True

        type_mismatches = 0
        for col in common_cols:
            if before_cols[col] != after_cols[col]:
                type_mismatches += 1

        return type_mismatches / max(len(common_cols), 1) > 0.4

    def _col_type_signature(
        self,
        rows: List[tuple],
    ) -> Dict[int, str]:
        """Get dominant type per column for a set of rows."""
        if not rows:
            return {}

        col_types: Dict[int, Dict[str, int]] = {}
        for row in rows:
            for i, val in enumerate(row):
                if val is None:
                    continue
                if i not in col_types:
                    col_types[i] = {"num": 0, "str": 0, "other": 0}
                if isinstance(val, (int, float)):
                    col_types[i]["num"] += 1
                elif isinstance(val, str):
                    col_types[i]["str"] += 1
                else:
                    col_types[i]["other"] += 1

        result: Dict[int, str] = {}
        for col, counts in col_types.items():
            dominant = max(counts, key=counts.get)
            result[col] = dominant
        return result

    # ── Utility methods ──────────────────────────────────────────────

    def _is_empty_row(self, row: tuple) -> bool:
        """Check if a row is empty (all None or whitespace-only strings)."""
        for cell in row:
            if cell is None:
                continue
            if isinstance(cell, str) and cell.strip() == "":
                continue
            return False
        return True

    def _count_cols(self, rows: List[tuple]) -> int:
        """Count maximum number of non-null columns."""
        if not rows:
            return 0
        max_cols = 0
        for row in rows[:20]:
            count = sum(1 for c in row if c is not None)
            max_cols = max(max_cols, count)
        return max_cols

    def _compute_density(self, rows: List[tuple]) -> float:
        """Compute data density (non-null cell ratio)."""
        if not rows:
            return 0.0
        total = 0
        filled = 0
        for row in rows:
            for cell in row:
                total += 1
                if cell is not None:
                    filled += 1
        return filled / max(total, 1)

    def _compute_text_ratio(self, rows: List[tuple]) -> float:
        """Compute ratio of text cells to total non-null cells."""
        non_null = 0
        text = 0
        for row in rows:
            for cell in row:
                if cell is not None:
                    non_null += 1
                    if isinstance(cell, str):
                        text += 1
        return text / max(non_null, 1)

    def _compute_table_confidence(
        self,
        header_row: tuple,
        data_rows: List[tuple],
        col_count: int,
        density: float,
    ) -> float:
        """Compute confidence that this region is a valid table."""
        confidence = 0.0

        # Column count (more columns = more likely a table)
        if col_count >= 4:
            confidence += 0.3
        elif col_count >= 2:
            confidence += 0.15

        # Data density (denser = more structured)
        confidence += density * 0.3

        # Row count (more rows = more likely)
        if len(data_rows) >= 10:
            confidence += 0.2
        elif len(data_rows) >= 3:
            confidence += 0.1

        # Header quality
        if header_row:
            text_cells = sum(1 for c in header_row if isinstance(c, str))
            total_cells = sum(1 for c in header_row if c is not None)
            if total_cells > 0:
                header_quality = text_cells / total_cells
                confidence += header_quality * 0.2

        return min(confidence, 1.0)

    def _extract_title_text(self, rows: List[tuple]) -> Optional[str]:
        """Extract title text from a title block segment."""
        texts: List[str] = []
        for row in rows:
            for cell in row:
                if isinstance(cell, str) and cell.strip():
                    texts.append(cell.strip())
        return " | ".join(texts) if texts else None

    def _extract_notes(self, rows: List[tuple]) -> List[str]:
        """Extract note text from a notes segment."""
        notes: List[str] = []
        for row in rows:
            text_parts: List[str] = []
            for cell in row:
                if isinstance(cell, str) and cell.strip():
                    text_parts.append(cell.strip())
            if text_parts:
                notes.append(" ".join(text_parts))
        return notes


# ── Module-level singleton ───────────────────────────────────────────────────
table_segmenter = TableSegmenter()
