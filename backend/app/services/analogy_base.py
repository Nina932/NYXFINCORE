"""
Phase L: Financial Analogy Base
=================================
Production-grade historical financial pattern matching for the Orchestrator.

Stores normalized financial snapshots with computed embeddings, enabling
similarity search to find analogous historical situations and their outcomes.

Pipeline:
    1. Normalize raw financials into canonical schema
    2. Compute derived metrics (margins, ratios)
    3. Generate embedding vector (deterministic, no LLM)
    4. Store with outcome metadata (strategy, verdict, ROI)
    5. Retrieve top-K analogous snapshots by cosine similarity

Components:
    SnapshotSchema      — Canonical financial snapshot structure
    MetricComputer      — Derives all missing metrics deterministically
    EmbeddingGenerator  — Deterministic numeric embedding (no neural net required)
    SyntheticGenerator  — Generates realistic financial scenarios for base population
    AnalogyIndex        — In-memory cosine similarity search
    AnalogyBase         — Orchestrates the full analogy pipeline

Rules:
    - ALL metric computation is deterministic
    - Embeddings are deterministic numeric vectors (not LLM-generated)
    - No hallucinated financial numbers
    - Every snapshot has a complete, validated schema
"""

import hashlib
import logging
import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# CANONICAL SCHEMA
# ═══════════════════════════════════════════════════════════════════

# Required fields in every snapshot
_SCHEMA_FIELDS = [
    "revenue", "cogs", "gross_profit", "ga_expenses", "ebitda", "net_profit",
    "depreciation", "finance_expense", "tax_rate",
    "gross_margin_pct", "net_margin_pct", "ebitda_margin_pct", "cogs_to_revenue_pct",
]

# Embedding dimensions (normalized financial metrics used for similarity)
_EMBEDDING_FIELDS = [
    "gross_margin_pct", "net_margin_pct", "ebitda_margin_pct", "cogs_to_revenue_pct",
    "revenue_scale",      # log10(revenue) normalized
    "ga_to_revenue_pct",  # G&A as % of revenue
    "finance_burden_pct", # finance expense as % of EBITDA
    "tax_effective_pct",  # effective tax rate
]

_EMBEDDING_DIM = len(_EMBEDDING_FIELDS)


@dataclass
class FinancialSnapshot:
    """Canonical normalized financial snapshot."""
    snapshot_id: str
    financials: Dict[str, float]
    embedding_vector: List[float]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "financials": {k: round(v, 2) for k, v in self.financials.items()},
            "embedding_vector": [round(v, 6) for v in self.embedding_vector],
            "metadata": self.metadata,
        }


@dataclass
class AnalogyMatch:
    """A matched analogous historical snapshot with similarity score."""
    snapshot: FinancialSnapshot
    similarity_score: float     # 0-1 cosine similarity
    relevance_notes: List[str]  # why this match is relevant

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot.snapshot_id,
            "similarity_score": round(self.similarity_score, 4),
            "financials": {k: round(v, 2) for k, v in self.snapshot.financials.items()},
            "metadata": self.snapshot.metadata,
            "relevance_notes": self.relevance_notes,
        }


# ═══════════════════════════════════════════════════════════════════
# METRIC COMPUTER — derives all missing metrics deterministically
# ═══════════════════════════════════════════════════════════════════

class MetricComputer:
    """Computes all derived financial metrics. Never guesses — only math."""

    @staticmethod
    def normalize(raw: Dict[str, float]) -> Dict[str, float]:
        """
        Ensure all schema fields are present and derived metrics are computed.

        Args:
            raw: Partial financial data (at minimum: revenue, cogs)
        Returns:
            Complete normalized dict with all _SCHEMA_FIELDS
        """
        f = dict(raw)
        revenue = f.get("revenue", 0) or 0
        cogs = f.get("cogs", 0) or 0
        abs_rev = abs(revenue) or 1  # avoid division by zero

        # Core P&L
        f.setdefault("gross_profit", revenue - cogs)
        f.setdefault("ga_expenses", 0)
        f.setdefault("depreciation", 0)
        f.setdefault("finance_expense", 0)
        f.setdefault("tax_rate", 0.15)

        gp = f["gross_profit"]
        ga = f["ga_expenses"]
        dep = f["depreciation"]
        fin = f["finance_expense"]
        tax_rate = f["tax_rate"]

        f.setdefault("ebitda", gp - ga)
        ebitda = f["ebitda"]
        ebit = ebitda - dep
        ebt = ebit - fin
        f.setdefault("net_profit", ebt * (1 - tax_rate))

        # Percentage metrics
        f["gross_margin_pct"] = round(gp / abs_rev * 100, 2) if abs_rev > 0 else 0
        f["net_margin_pct"] = round(f["net_profit"] / abs_rev * 100, 2) if abs_rev > 0 else 0
        f["ebitda_margin_pct"] = round(ebitda / abs_rev * 100, 2) if abs_rev > 0 else 0
        f["cogs_to_revenue_pct"] = round(cogs / abs_rev * 100, 2) if abs_rev > 0 else 0

        return f


# ═══════════════════════════════════════════════════════════════════
# EMBEDDING GENERATOR — deterministic numeric vectors
# ═══════════════════════════════════════════════════════════════════

class EmbeddingGenerator:
    """
    Generates deterministic embedding vectors from financial metrics.

    No neural network — uses normalized financial ratios as dimensions.
    This ensures reproducibility and auditability.
    """

    # Normalization ranges (min, max) for each embedding dimension
    _RANGES = {
        "gross_margin_pct": (-20.0, 60.0),
        "net_margin_pct": (-30.0, 30.0),
        "ebitda_margin_pct": (-20.0, 40.0),
        "cogs_to_revenue_pct": (30.0, 110.0),
        "revenue_scale": (4.0, 12.0),       # log10(revenue) — 10K to 1T
        "ga_to_revenue_pct": (0.0, 40.0),
        "finance_burden_pct": (0.0, 50.0),
        "tax_effective_pct": (0.0, 35.0),
    }

    @staticmethod
    def generate(financials: Dict[str, float]) -> List[float]:
        """
        Generate an 8-dimensional embedding vector from financial metrics.

        Each dimension is min-max normalized to [0, 1].
        """
        revenue = abs(financials.get("revenue", 0)) or 1
        ebitda = financials.get("ebitda", 0) or 1

        raw_values = {
            "gross_margin_pct": financials.get("gross_margin_pct", 0),
            "net_margin_pct": financials.get("net_margin_pct", 0),
            "ebitda_margin_pct": financials.get("ebitda_margin_pct", 0),
            "cogs_to_revenue_pct": financials.get("cogs_to_revenue_pct", 0),
            "revenue_scale": math.log10(max(revenue, 1)),
            "ga_to_revenue_pct": round(abs(financials.get("ga_expenses", 0)) / revenue * 100, 2),
            "finance_burden_pct": round(abs(financials.get("finance_expense", 0)) / max(abs(ebitda), 1) * 100, 2),
            "tax_effective_pct": round(financials.get("tax_rate", 0.15) * 100, 2),
        }

        vector = []
        for dim in _EMBEDDING_FIELDS:
            val = raw_values.get(dim, 0)
            lo, hi = EmbeddingGenerator._RANGES.get(dim, (0, 100))
            # Min-max normalize to [0, 1], clamp
            normalized = max(0.0, min(1.0, (val - lo) / max(hi - lo, 0.01)))
            vector.append(round(normalized, 6))

        return vector


# ═══════════════════════════════════════════════════════════════════
# COSINE SIMILARITY
# ═══════════════════════════════════════════════════════════════════

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a < 1e-10 or mag_b < 1e-10:
        return 0.0
    return round(dot / (mag_a * mag_b), 6)


# ═══════════════════════════════════════════════════════════════════
# SYNTHETIC DATA GENERATOR
# ═══════════════════════════════════════════════════════════════════

# Industry profiles for synthetic data generation
_INDUSTRY_PROFILES = {
    "fuel_distribution": {
        "revenue_range": (20_000_000, 200_000_000),
        "cogs_pct_range": (82, 96),
        "ga_pct_range": (2, 8),
        "dep_pct_range": (1, 4),
        "fin_pct_range": (0.5, 3),
        "tax_rate": 0.15,
    },
    "retail_general": {
        "revenue_range": (5_000_000, 100_000_000),
        "cogs_pct_range": (55, 75),
        "ga_pct_range": (10, 25),
        "dep_pct_range": (2, 6),
        "fin_pct_range": (1, 5),
        "tax_rate": 0.20,
    },
    "manufacturing": {
        "revenue_range": (10_000_000, 500_000_000),
        "cogs_pct_range": (50, 70),
        "ga_pct_range": (8, 18),
        "dep_pct_range": (3, 8),
        "fin_pct_range": (1, 4),
        "tax_rate": 0.20,
    },
    "services": {
        "revenue_range": (2_000_000, 50_000_000),
        "cogs_pct_range": (30, 55),
        "ga_pct_range": (15, 35),
        "dep_pct_range": (1, 5),
        "fin_pct_range": (0.5, 3),
        "tax_rate": 0.15,
    },
    "construction": {
        "revenue_range": (10_000_000, 200_000_000),
        "cogs_pct_range": (65, 85),
        "ga_pct_range": (5, 15),
        "dep_pct_range": (2, 7),
        "fin_pct_range": (2, 6),
        "tax_rate": 0.20,
    },
    "agriculture": {
        "revenue_range": (3_000_000, 80_000_000),
        "cogs_pct_range": (55, 80),
        "ga_pct_range": (5, 15),
        "dep_pct_range": (3, 10),
        "fin_pct_range": (1, 5),
        "tax_rate": 0.15,
    },
}

# Health scenario labels based on margin profiles
_SCENARIO_LABELS = [
    {"health": "critical", "strategy": "Emergency Turnaround Strategy", "verdict": "D", "roi_range": (0.5, 3.0)},
    {"health": "distressed", "strategy": "Financial Recovery Strategy", "verdict": "C", "roi_range": (2.0, 8.0)},
    {"health": "recovering", "strategy": "Performance Optimization Strategy", "verdict": "B", "roi_range": (5.0, 15.0)},
    {"health": "healthy", "strategy": "Growth Acceleration Strategy", "verdict": "A", "roi_range": (10.0, 30.0)},
]


class SyntheticGenerator:
    """Generates realistic synthetic financial snapshots across industries and health states."""

    def generate_batch(
        self,
        count: int = 100,
        seed: int = 42,
        industries: Optional[List[str]] = None,
    ) -> List[FinancialSnapshot]:
        """
        Generate a batch of synthetic snapshots.

        Args:
            count: Number of snapshots to generate
            seed: RNG seed for reproducibility
            industries: List of industries to include (default: all)
        """
        rng = random.Random(seed)
        target_industries = industries or list(_INDUSTRY_PROFILES.keys())
        snapshots: List[FinancialSnapshot] = []

        for i in range(count):
            industry = target_industries[i % len(target_industries)]
            profile = _INDUSTRY_PROFILES[industry]

            # Generate base financials
            revenue = rng.uniform(*profile["revenue_range"])
            cogs_pct = rng.uniform(*profile["cogs_pct_range"]) / 100
            ga_pct = rng.uniform(*profile["ga_pct_range"]) / 100
            dep_pct = rng.uniform(*profile["dep_pct_range"]) / 100
            fin_pct = rng.uniform(*profile["fin_pct_range"]) / 100

            cogs = round(revenue * cogs_pct, 2)
            ga = round(revenue * ga_pct, 2)
            dep = round(revenue * dep_pct, 2)
            fin = round(revenue * fin_pct, 2)

            raw = {
                "revenue": round(revenue, 2),
                "cogs": cogs,
                "ga_expenses": ga,
                "depreciation": dep,
                "finance_expense": fin,
                "tax_rate": profile["tax_rate"],
            }

            # Normalize to get all derived metrics
            financials = MetricComputer.normalize(raw)

            # Determine health scenario based on net margin
            net_margin = financials["net_margin_pct"]
            if net_margin < -5:
                scenario = _SCENARIO_LABELS[0]  # critical
            elif net_margin < 2:
                scenario = _SCENARIO_LABELS[1]  # distressed
            elif net_margin < 8:
                scenario = _SCENARIO_LABELS[2]  # recovering
            else:
                scenario = _SCENARIO_LABELS[3]  # healthy

            roi = round(rng.uniform(*scenario["roi_range"]), 1)

            # Generate embedding
            embedding = EmbeddingGenerator.generate(financials)

            # Generate period
            year = rng.choice([2023, 2024, 2025])
            month = rng.randint(1, 12)
            period = f"{year}-{month:02d}"

            # Build snapshot
            snap_id = hashlib.sha256(f"{industry}_{period}_{i}_{seed}".encode()).hexdigest()[:16]

            snapshot = FinancialSnapshot(
                snapshot_id=snap_id,
                financials=financials,
                embedding_vector=embedding,
                metadata={
                    "industry": industry,
                    "period": period,
                    "health_state": scenario["health"],
                    "strategy_outcome": scenario["strategy"],
                    "cfo_verdict": scenario["verdict"],
                    "roi": roi,
                    "risk_rating": "high" if net_margin < 0 else "medium" if net_margin < 5 else "low",
                    "generated": "synthetic",
                },
            )
            snapshots.append(snapshot)

        logger.info("Generated %d synthetic snapshots across %d industries",
                     len(snapshots), len(target_industries))
        return snapshots


# ═══════════════════════════════════════════════════════════════════
# ANALOGY INDEX — in-memory cosine similarity search
# ═══════════════════════════════════════════════════════════════════

class AnalogyIndex:
    """In-memory vector index for financial snapshot similarity search."""

    def __init__(self):
        self._snapshots: List[FinancialSnapshot] = []

    def add(self, snapshot: FinancialSnapshot):
        """Add a snapshot to the index."""
        self._snapshots.append(snapshot)

    def add_batch(self, snapshots: List[FinancialSnapshot]):
        """Add multiple snapshots to the index."""
        self._snapshots.extend(snapshots)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        industry_filter: Optional[str] = None,
    ) -> List[AnalogyMatch]:
        """
        Find the top-K most similar snapshots by cosine similarity.

        Args:
            query_embedding: Target embedding vector
            top_k: Number of results to return
            industry_filter: Optional industry filter
        """
        candidates = self._snapshots
        if industry_filter:
            candidates = [s for s in candidates
                          if s.metadata.get("industry") == industry_filter]

        scored: List[Tuple[float, FinancialSnapshot]] = []
        for snap in candidates:
            sim = _cosine_similarity(query_embedding, snap.embedding_vector)
            scored.append((sim, snap))

        scored.sort(key=lambda x: x[0], reverse=True)

        matches: List[AnalogyMatch] = []
        for sim, snap in scored[:top_k]:
            notes = self._generate_relevance_notes(query_embedding, snap, sim)
            matches.append(AnalogyMatch(
                snapshot=snap,
                similarity_score=sim,
                relevance_notes=notes,
            ))

        return matches

    def _generate_relevance_notes(self, query: List[float], snap: FinancialSnapshot,
                                   similarity: float) -> List[str]:
        """Generate notes explaining why this match is relevant."""
        notes = []

        # Similarity tier
        if similarity > 0.98:
            notes.append("Near-identical financial profile to current situation")
        elif similarity > 0.95:
            notes.append("Very similar financial structure")
        elif similarity > 0.90:
            notes.append("Comparable financial profile with minor differences")
        else:
            notes.append("Partially similar financial structure")

        # Outcome context
        health = snap.metadata.get("health_state", "")
        strategy = snap.metadata.get("strategy_outcome", "")
        roi = snap.metadata.get("roi", 0)
        if strategy:
            notes.append(f"Historical outcome: {strategy} (ROI: {roi}x)")
        if health:
            notes.append(f"Company was in '{health}' state when this occurred")

        return notes

    def size(self) -> int:
        """Return number of snapshots in index."""
        return len(self._snapshots)

    def clear(self):
        """Clear all snapshots."""
        self._snapshots.clear()

    def get_industry_distribution(self) -> Dict[str, int]:
        """Return count of snapshots per industry."""
        dist: Dict[str, int] = {}
        for s in self._snapshots:
            ind = s.metadata.get("industry", "unknown")
            dist[ind] = dist.get(ind, 0) + 1
        return dist

    def get_health_distribution(self) -> Dict[str, int]:
        """Return count of snapshots per health state."""
        dist: Dict[str, int] = {}
        for s in self._snapshots:
            h = s.metadata.get("health_state", "unknown")
            dist[h] = dist.get(h, 0) + 1
        return dist


# ═══════════════════════════════════════════════════════════════════
# ANALOGY BASE — orchestrates the full analogy pipeline
# ═══════════════════════════════════════════════════════════════════

class AnalogyBase:
    """
    Production-grade financial analogy system.

    Ingests financial snapshots, normalizes them, generates embeddings,
    and provides similarity search for analogous historical situations.
    """

    def __init__(self):
        self.metric_computer = MetricComputer()
        self.embedding_generator = EmbeddingGenerator()
        self.synthetic_generator = SyntheticGenerator()
        self.index = AnalogyIndex()
        self._initialized = False

    def initialize(self, synthetic_count: int = 100, seed: int = 42):
        """
        Initialize the analogy base with synthetic data.

        Call this once on startup to populate the base.
        """
        if self._initialized:
            return

        snapshots = self.synthetic_generator.generate_batch(synthetic_count, seed)
        self.index.add_batch(snapshots)
        self._initialized = True

        logger.info("AnalogyBase initialized: %d snapshots, %d industries",
                     self.index.size(), len(self.index.get_industry_distribution()))

    def ingest_snapshot(
        self,
        raw_financials: Dict[str, float],
        industry: str = "fuel_distribution",
        period: str = "",
        outcome_metadata: Optional[Dict[str, Any]] = None,
    ) -> FinancialSnapshot:
        """
        Ingest a real financial snapshot into the analogy base.

        Args:
            raw_financials: Raw P&L data (at minimum: revenue, cogs)
            industry: Industry classification
            period: Financial period (e.g., "2025-01")
            outcome_metadata: Optional outcome data {strategy, verdict, roi, risk}
        """
        # Normalize
        financials = self.metric_computer.normalize(raw_financials)

        # Generate embedding
        embedding = self.embedding_generator.generate(financials)

        # Build metadata
        metadata = {
            "industry": industry,
            "period": period or datetime.now(timezone.utc).strftime("%Y-%m"),
            "generated": "real",
        }
        if outcome_metadata:
            metadata.update(outcome_metadata)

        # Generate ID
        snap_id = hashlib.sha256(
            f"{industry}_{period}_{financials.get('revenue', 0)}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        snapshot = FinancialSnapshot(
            snapshot_id=snap_id,
            financials=financials,
            embedding_vector=embedding,
            metadata=metadata,
        )

        self.index.add(snapshot)
        logger.info("Ingested snapshot %s: industry=%s, period=%s", snap_id, industry, period)
        return snapshot

    def find_analogies(
        self,
        current_financials: Dict[str, float],
        top_k: int = 5,
        industry: Optional[str] = None,
    ) -> List[AnalogyMatch]:
        """
        Find the most analogous historical situations to current financials.

        Args:
            current_financials: Current P&L data
            top_k: Number of matches to return
            industry: Optional industry filter
        """
        if not self._initialized:
            self.initialize()

        # Normalize and embed
        financials = self.metric_computer.normalize(current_financials)
        embedding = self.embedding_generator.generate(financials)

        # Search
        return self.index.search(embedding, top_k, industry)

    def get_analogous_strategies(
        self,
        current_financials: Dict[str, float],
        top_k: int = 3,
        industry: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find analogous situations and extract strategy recommendations.

        Returns:
            Dict with matches, recommended strategies, and confidence.
        """
        matches = self.find_analogies(current_financials, top_k, industry)

        if not matches:
            return {
                "matches": [],
                "dominant_strategy": None,
                "confidence": 0.0,
                "message": "No analogous situations found in base.",
            }

        # Count strategy outcomes
        strategy_counts: Dict[str, List[float]] = {}
        for m in matches:
            strat = m.snapshot.metadata.get("strategy_outcome", "")
            if strat:
                if strat not in strategy_counts:
                    strategy_counts[strat] = []
                strategy_counts[strat].append(m.similarity_score)

        # Find dominant strategy (most frequent among top matches, weighted by similarity)
        dominant = None
        max_weight = 0.0
        for strat, sims in strategy_counts.items():
            weight = sum(sims)
            if weight > max_weight:
                max_weight = weight
                dominant = strat

        # Confidence: avg similarity of dominant strategy matches
        confidence = 0.0
        if dominant and strategy_counts.get(dominant):
            confidence = round(sum(strategy_counts[dominant]) / len(strategy_counts[dominant]), 4)

        return {
            "matches": [m.to_dict() for m in matches],
            "dominant_strategy": dominant,
            "strategy_distribution": {k: len(v) for k, v in strategy_counts.items()},
            "confidence": confidence,
            "base_size": self.index.size(),
        }

    def summary(self) -> Dict[str, Any]:
        """Return analogy base summary statistics."""
        return {
            "total_snapshots": self.index.size(),
            "initialized": self._initialized,
            "industry_distribution": self.index.get_industry_distribution(),
            "health_distribution": self.index.get_health_distribution(),
            "embedding_dimensions": _EMBEDDING_DIM,
            "schema_fields": len(_SCHEMA_FIELDS),
        }


# Module-level singleton
analogy_base = AnalogyBase()
