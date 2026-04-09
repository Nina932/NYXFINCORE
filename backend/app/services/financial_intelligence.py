"""
FinAI Financial Intelligence Service
=====================================
Provides period-aware orchestration, account mapping intelligence,
proactive contextual suggestions, and intelligent dataset analysis.

Classes:
  PeriodResolver      — parse/navigate period strings ("January 2026" → prior year, YTD, etc.)
  DatasetDiscovery    — find datasets by period in the database
  AccountMapper       — enhanced map_coa with confidence scores and trace explanations
  SuggestionEngine    — generate context-aware suggestions for each page
  DataManifest        — structured description of what a dataset contains and can produce
  DatasetIntelligence — the "brain" that analyzes datasets and applies financial logic
  SmartResolver       — context-aware dataset resolution (replaces dumb _resolve_dataset_id)
"""

import re
import logging
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field, asdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.models.all_models import (
    Dataset, BudgetLine, TrialBalanceItem, RevenueItem,
    COGSItem, GAExpenseItem, BalanceSheetItem, Transaction,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Period Resolution
# ═══════════════════════════════════════════════════════════════════════

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class PeriodResolver:
    """Parse and navigate period strings like 'January 2026'."""

    @staticmethod
    def parse(period: str) -> Optional[Tuple[str, int]]:
        """Parse 'January 2025' -> ('January', 2025). Returns None on failure."""
        if not period:
            return None
        parts = period.strip().split()
        if len(parts) != 2:
            return None
        month_name = parts[0].capitalize()
        try:
            year = int(parts[1])
        except ValueError:
            return None
        if month_name not in MONTH_NAMES:
            return None
        return (month_name, year)

    @staticmethod
    def prior_year_period(period: str) -> Optional[str]:
        """'January 2026' -> 'January 2025'"""
        parsed = PeriodResolver.parse(period)
        if not parsed:
            return None
        month, year = parsed
        return f"{month} {year - 1}"

    @staticmethod
    def prior_month_period(period: str) -> Optional[str]:
        """'February 2026' -> 'January 2026'. December wraps to prior year."""
        parsed = PeriodResolver.parse(period)
        if not parsed:
            return None
        month, year = parsed
        idx = MONTH_NAMES.index(month)
        if idx == 0:
            return f"December {year - 1}"
        return f"{MONTH_NAMES[idx - 1]} {year}"

    @staticmethod
    def ytd_periods(period: str) -> list[str]:
        """'March 2026' -> ['January 2026', 'February 2026', 'March 2026']"""
        parsed = PeriodResolver.parse(period)
        if not parsed:
            return []
        month, year = parsed
        idx = MONTH_NAMES.index(month)
        return [f"{MONTH_NAMES[i]} {year}" for i in range(idx + 1)]

    @staticmethod
    def month_index(period: str) -> int:
        """'March 2026' -> 3. Returns 0 if unparseable."""
        parsed = PeriodResolver.parse(period)
        if not parsed:
            return 0
        return MONTH_NAMES.index(parsed[0]) + 1


# ═══════════════════════════════════════════════════════════════════════
# Dataset Discovery
# ═══════════════════════════════════════════════════════════════════════

class DatasetDiscovery:
    """Find datasets in the database by period relationships."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_period(self, period: str) -> Optional[Dataset]:
        """Find the most recent dataset matching the exact period string."""
        result = await self.db.execute(
            select(Dataset)
            .where(Dataset.period == period, Dataset.status == "ready")
            .order_by(Dataset.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_prior_year_dataset(self, current_period: str) -> Optional[Dataset]:
        """Given 'January 2026', find 'January 2025' dataset."""
        prior_period = PeriodResolver.prior_year_period(current_period)
        if not prior_period:
            return None
        return await self.find_by_period(prior_period)

    async def find_all_periods(self) -> list[dict]:
        """Return all distinct periods with their dataset IDs (for dropdowns)."""
        result = await self.db.execute(
            select(Dataset.id, Dataset.period, Dataset.name)
            .where(Dataset.status == "ready")
            .order_by(Dataset.created_at.desc())
        )
        return [{"id": r[0], "period": r[1], "name": r[2]} for r in result.all()]


# ═══════════════════════════════════════════════════════════════════════
# Account Mapping Intelligence
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MappingResult:
    """Result of intelligent account mapping with confidence and trace."""
    account_code: str
    matched_prefix: str
    ifrs_line: str
    confidence: float       # 1.0=exact, 0.9=4-char, 0.8=3-char, 0.6=2-char, 0.4=1-char
    trace: str              # Human-readable explanation
    source: str             # "coa_master" | "georgian_coa" | "unmapped"

    def to_dict(self) -> dict:
        return {
            "matched_prefix": self.matched_prefix,
            "ifrs_line": self.ifrs_line,
            "confidence": self.confidence,
            "trace": self.trace,
            "source": self.source,
        }


# Confidence score by matched prefix length
_CONFIDENCE_BY_LENGTH = {4: 0.9, 3: 0.8, 2: 0.6, 1: 0.4}


class AccountMapper:
    """Enhanced account mapping with confidence scores and trace explanations.

    Wraps file_parser.map_coa() and adds intelligence layer:
    - Confidence scoring based on match specificity
    - Trace explanations showing the mapping chain
    - Source identification (COA Master vs GEORGIAN_COA vs unmapped)
    """

    @staticmethod
    def map_with_trace(code: str) -> MappingResult:
        """Map account code with full confidence score and trace.

        Confidence levels:
          1.0  — exact match in COA Master (406 curated accounts)
          0.9  — 4-digit prefix match in GEORGIAN_COA
          0.8  — 3-digit prefix match
          0.6  — 2-digit prefix match (account class + subclass)
          0.4  — 1-digit prefix match (account class only)
          0.0  — unmapped
        """
        # Import here to avoid circular imports
        from app.services.file_parser import GEORGIAN_COA

        if not code:
            return MappingResult("", "", "", 0.0, "No code provided", "unmapped")

        raw = str(code).strip()
        clean = re.sub(r'[^0-9]', '', raw)

        if not clean:
            return MappingResult(raw, "", "", 0.0, f"Account {raw}: no digits found", "unmapped")

        # Priority 1: COA Master exact match (highest confidence)
        try:
            from app.services.file_parser import _coa_master_cache
            if clean in _coa_master_cache:
                entry = _coa_master_cache[clean]
                ifrs = entry.get("bs") or entry.get("pl") or entry.get("name_en") or ""
                return MappingResult(
                    raw, clean, ifrs, 1.0,
                    f"Exact match in COA Master: {clean} \u2192 {ifrs}",
                    "coa_master"
                )
        except (ImportError, AttributeError):
            pass

        # Priority 2: GEORGIAN_COA prefix match (longest to shortest)
        for length in range(min(len(clean), 4), 0, -1):
            prefix = clean[:length]
            if prefix in GEORGIAN_COA:
                entry = GEORGIAN_COA[prefix]
                ifrs = entry.get("bs") or entry.get("pl") or ""
                conf = 1.0 if length == len(clean) else _CONFIDENCE_BY_LENGTH.get(length, 0.4)
                return MappingResult(
                    raw, prefix, ifrs, conf,
                    f"Account {raw} \u2192 mapped via prefix '{prefix}' \u2192 {ifrs}",
                    "georgian_coa"
                )

        # Priority 3: Handle dotted/slashed codes (e.g., "7110.01.1", "7110.01/1")
        parts = re.split(r'[./]', raw)
        if len(parts) > 1:
            for num_parts in range(len(parts), 0, -1):
                joined = ''.join(re.sub(r'[^0-9]', '', p) for p in parts[:num_parts])
                for length in range(min(len(joined), 4), 0, -1):
                    prefix = joined[:length]
                    if prefix in GEORGIAN_COA:
                        entry = GEORGIAN_COA[prefix]
                        ifrs = entry.get("bs") or entry.get("pl") or ""
                        conf = _CONFIDENCE_BY_LENGTH.get(length, 0.4)
                        return MappingResult(
                            raw, prefix, ifrs, conf,
                            f"Account {raw} \u2192 split & matched prefix '{prefix}' \u2192 {ifrs}",
                            "georgian_coa"
                        )

        return MappingResult(raw, "", "", 0.0, f"Account {raw}: no mapping found in COA", "unmapped")


# ═══════════════════════════════════════════════════════════════════════
# Suggestion Engine
# ═══════════════════════════════════════════════════════════════════════

class SuggestionEngine:
    """Generate contextual, non-blocking suggestions for each page.

    Suggestions are informational — they guide the user but don't block actions.
    Each suggestion has a type, message, optional action, and can be dismissed.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.discovery = DatasetDiscovery(db)

    async def get_suggestions(self, dataset_id: int, context: str = "dashboard") -> list[dict]:
        """Generate suggestions for the given dataset and page context.

        Args:
            dataset_id: The active dataset ID
            context: Page context — "dashboard", "mr", "tb", "pl", "bs", "cogs", "revenue"

        Returns:
            List of suggestion dicts with keys:
              type (info|warning|tip), icon, message, action, action_data, dismissible
        """
        suggestions = []

        # Fetch the active dataset
        ds = await self._get_dataset(dataset_id)
        if not ds:
            return suggestions

        # ── MR and Dashboard suggestions ──────────────────────────────
        if context in ("mr", "dashboard"):
            await self._suggest_prior_year(ds, suggestions)
            await self._suggest_budget(dataset_id, suggestions)

        # ── Trial Balance suggestions ─────────────────────────────────
        if context in ("tb", "dashboard", "mr"):
            await self._suggest_unmapped_accounts(dataset_id, suggestions)

        # ── Period completeness ───────────────────────────────────────
        if context == "dashboard":
            await self._suggest_data_completeness(dataset_id, ds, suggestions)

        return suggestions

    async def _get_dataset(self, dataset_id: int) -> Optional[Dataset]:
        result = await self.db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        return result.scalar_one_or_none()

    async def _suggest_prior_year(self, ds: Dataset, suggestions: list):
        """Suggest using prior year dataset for comparison."""
        prior_period = PeriodResolver.prior_year_period(ds.period)
        if not prior_period:
            return

        prior_ds = await self.discovery.find_prior_year_dataset(ds.period)
        if prior_ds:
            suggestions.append({
                "type": "info",
                "icon": "calendar",
                "message": (
                    f"Prior year data available: \"{prior_ds.name}\" ({prior_period}). "
                    f"MR Report can auto-populate 'Same period of previous year' column."
                ),
                "action": "use_prior_dataset",
                "action_data": {
                    "prior_dataset_id": prior_ds.id,
                    "prior_period": prior_period,
                    "prior_name": prior_ds.name,
                },
                "dismissible": True,
            })
        else:
            suggestions.append({
                "type": "tip",
                "icon": "upload",
                "message": (
                    f"No {prior_period} dataset found. Upload prior year data "
                    f"to enable year-over-year comparison in MR Reports."
                ),
                "action": "navigate",
                "action_data": {"page": "lib"},
                "dismissible": True,
            })

    async def _suggest_budget(self, dataset_id: int, suggestions: list):
        """Suggest using budget data for plan column."""
        count = await self._count_budget_lines(dataset_id)
        if count > 0:
            suggestions.append({
                "type": "info",
                "icon": "chart",
                "message": (
                    f"Budget data available ({count} line items). "
                    f"MR Report will auto-populate 'Plan' and 'Deviation' columns."
                ),
                "action": "enable_budget",
                "action_data": {"budget_count": count},
                "dismissible": True,
            })

    async def _suggest_unmapped_accounts(self, dataset_id: int, suggestions: list):
        """Warn about unmapped TB accounts."""
        unmapped_count, total_count = await self._count_unmapped_accounts(dataset_id)
        if unmapped_count > 0:
            pct = round(unmapped_count / total_count * 100, 1) if total_count else 0
            suggestions.append({
                "type": "warning",
                "icon": "alert",
                "message": (
                    f"{unmapped_count} of {total_count} TB accounts ({pct}%) have no direct COA mapping. "
                    f"These are matched via parent prefix fallback. "
                    f"View Trial Balance page for mapping confidence per account."
                ),
                "action": "navigate",
                "action_data": {"page": "tb"},
                "dismissible": True,
            })

    async def _suggest_data_completeness(self, dataset_id: int, ds: Dataset, suggestions: list):
        """Check if key data tables are populated."""
        from app.models.all_models import RevenueItem, COGSItem, GAExpenseItem

        # Check for empty Revenue
        rev_count = (await self.db.execute(
            select(func.count()).select_from(
                select(RevenueItem.id).where(RevenueItem.dataset_id == dataset_id).subquery()
            )
        )).scalar() or 0

        tb_count = (await self.db.execute(
            select(func.count()).select_from(
                select(TrialBalanceItem.id).where(TrialBalanceItem.dataset_id == dataset_id).subquery()
            )
        )).scalar() or 0

        if tb_count > 0 and rev_count == 0:
            suggestions.append({
                "type": "tip",
                "icon": "info",
                "message": (
                    "Revenue and COGS are derived from Trial Balance account totals. "
                    "For product-level detail, upload a file with Revenue Breakdown and COGS Breakdown sheets."
                ),
                "action": None,
                "action_data": {},
                "dismissible": True,
            })

    async def _count_budget_lines(self, dataset_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(
                select(BudgetLine.id).where(BudgetLine.dataset_id == dataset_id).subquery()
            )
        )
        return result.scalar() or 0

    async def _count_unmapped_accounts(self, dataset_id: int) -> Tuple[int, int]:
        """Count unmapped leaf TB accounts. Returns (unmapped_count, total_count)."""
        result = await self.db.execute(
            select(TrialBalanceItem.account_code)
            .where(
                TrialBalanceItem.dataset_id == dataset_id,
                TrialBalanceItem.hierarchy_level.in_([1, 2]),
            )
        )
        codes = [r[0] for r in result.all() if r[0]]

        # Deduplicate
        seen = set()
        unique_codes = []
        for code in codes:
            clean = code.strip()
            if clean and clean not in seen and not clean.upper().endswith("X"):
                seen.add(clean)
                unique_codes.append(clean)

        unmapped = 0
        for code in unique_codes:
            mapping = AccountMapper.map_with_trace(code)
            if mapping.confidence == 0.0:
                unmapped += 1

        return unmapped, len(unique_codes)


# ═══════════════════════════════════════════════════════════════════════
# Data Manifest — What does this dataset contain?
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DataManifest:
    """Complete structured description of a dataset's contents, capabilities, and links.

    An experienced financial analyst who opens a file immediately knows:
    'This has a trial balance — I can derive BS and P&L from it.
     There's also a Revenue Breakdown, so I have product-level detail.
     There's a Budget sheet, so I can do plan vs actual.
     And I see January 2025 is already uploaded — that's my prior year comparison.'

    This dataclass captures that same understanding programmatically.
    """
    dataset_id: int
    period: str

    # ── What data EXISTS (boolean flags from record counts) ──────────
    has_trial_balance: bool = False       # Can derive BS + P&L
    has_revenue_detail: bool = False      # Product-level revenue
    has_cogs_detail: bool = False         # Product-level COGS
    has_ga_expenses: bool = False         # G&A + D&A expenses
    has_balance_sheet: bool = False       # Pre-formatted BS items
    has_transactions: bool = False        # Transaction ledger
    has_budget: bool = False              # Plan data
    has_mapping_sheet: bool = False       # MR mapping overrides in TB

    # ── What can be DERIVED (financial logic) ────────────────────────
    can_derive_pl: bool = False           # True if has_trial_balance
    can_derive_bs: bool = False           # True if has_trial_balance
    revenue_source: str = "none"          # "detail" | "derived_from_tb" | "none"
    cogs_source: str = "none"             # "detail" | "derived_from_tb" | "none"

    # ── LINKED datasets (auto-discovered) ────────────────────────────
    prior_year_dataset_id: Optional[int] = None
    prior_year_period: Optional[str] = None
    prior_year_has_data: bool = False     # True if prior dataset actually has usable data
    budget_source_dataset_id: Optional[int] = None  # Which dataset has budget data
    budget_source: str = "none"           # "current" | "prior_year" | "none"

    # ── What REPORTS can this produce? ───────────────────────────────
    report_capabilities: Dict[str, str] = field(default_factory=dict)
    # {report_name: "ready"|"partial"|"unavailable"}

    # ── What's MISSING? ─────────────────────────────────────────────
    missing: List[str] = field(default_factory=list)
    # Human-readable warnings

    # ── Financial TOTALS (GEL) ──────────────────────────────────────
    total_revenue: float = 0.0
    total_cogs: float = 0.0
    total_ga: float = 0.0

    # ── Raw record counts ───────────────────────────────────────────
    record_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON response."""
        return asdict(self)

    @property
    def data_richness_score(self) -> float:
        """0.0–1.0 score of how much data is available (for ranking datasets)."""
        flags = [
            self.has_trial_balance, self.has_revenue_detail, self.has_cogs_detail,
            self.has_ga_expenses, self.has_balance_sheet, self.has_transactions,
            self.has_budget, self.has_mapping_sheet,
        ]
        return sum(1 for f in flags if f) / len(flags)

    def _rc(self, *keys) -> int:
        """Get record count from any of the provided keys (handles naming variants)."""
        for k in keys:
            v = self.record_counts.get(k, 0)
            if v:
                return v
        return 0

    @property
    def summary(self) -> str:
        """One-line human-readable summary."""
        parts = []
        if self.has_trial_balance:
            parts.append(f"TB({self._rc('trial_balance', 'trial_balance_items')})")
        if self.has_revenue_detail:
            parts.append(f"Rev({self._rc('revenue', 'revenue_items')})")
        if self.has_cogs_detail:
            parts.append(f"COGS({self._rc('cogs', 'cogs_items')})")
        if self.has_ga_expenses:
            parts.append(f"G&A({self._rc('ga_expenses', 'ga_expense_items')})")
        if self.has_balance_sheet:
            parts.append(f"BS({self._rc('balance_sheet', 'balance_sheet_items')})")
        if self.has_transactions:
            parts.append(f"Txn({self._rc('transactions')})")
        if self.has_budget:
            parts.append(f"Budget({self._rc('budget', 'budget_lines')})")
        ready = [k for k, v in self.report_capabilities.items() if v == "ready"]
        return f"DS #{self.dataset_id} ({self.period}): {', '.join(parts) or 'empty'} -> Reports: {', '.join(ready) or 'none'}"


# ═══════════════════════════════════════════════════════════════════════
# Report Requirements — Built-in Financial Knowledge
# ═══════════════════════════════════════════════════════════════════════

REPORT_REQUIREMENTS = {
    "income_statement": {
        "label": "Income Statement (P&L)",
        "required_any": ["has_revenue_detail", "has_trial_balance"],
        "enhancers": ["has_cogs_detail", "has_ga_expenses", "has_budget"],
    },
    "balance_sheet": {
        "label": "Balance Sheet",
        "required_any": ["has_balance_sheet", "has_trial_balance"],
        "enhancers": ["has_transactions"],
    },
    "mr_report": {
        "label": "Management Report (Baku)",
        "required_any": ["has_trial_balance"],
        "enhancers": ["has_revenue_detail", "has_cogs_detail", "has_ga_expenses",
                      "has_budget", "has_mapping_sheet", "has_balance_sheet"],
    },
    "cash_flow": {
        "label": "Cash Flow Statement",
        "required_any": ["has_trial_balance", "has_balance_sheet"],
        "enhancers": ["has_transactions"],
    },
    "dashboard": {
        "label": "Financial Dashboard",
        "required_any": ["has_revenue_detail", "has_trial_balance", "has_transactions"],
        "enhancers": ["has_cogs_detail", "has_ga_expenses", "has_budget"],
    },
    "revenue_analysis": {
        "label": "Revenue Analysis",
        "required_any": ["has_revenue_detail"],
        "enhancers": ["has_budget", "has_transactions"],
    },
    "cogs_analysis": {
        "label": "COGS Analysis",
        "required_any": ["has_cogs_detail"],
        "enhancers": ["has_revenue_detail", "has_budget"],
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Dataset Intelligence — The Thinking Layer
# ═══════════════════════════════════════════════════════════════════════

class DatasetIntelligence:
    """The 'brain' that analyzes datasets and applies financial logic.

    An experienced financial analyst who opens a file immediately knows what
    reports they can produce, what data sources to use, and what's missing.
    This class replicates that thinking programmatically.

    Three analysis modes:
      analyze()           — full DB query analysis (most accurate, use on upload)
      analyze_quick()     — from cached parse_metadata (zero extra queries, for hot paths)
      analyze_and_cache() — full analysis + writes to parse_metadata for future quick lookups
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.discovery = DatasetDiscovery(db)

    # ── Full Analysis (live DB queries) ──────────────────────────────

    async def analyze(self, dataset_id: int) -> Optional[DataManifest]:
        """Full analysis of a dataset: count records, apply financial logic,
        discover links, score report capabilities, build warnings.

        This is the most accurate mode — queries every table live.
        Use on upload or when `/capabilities` is called.
        """
        # Step 0: Get the dataset
        ds = (await self.db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )).scalar_one_or_none()
        if not ds:
            return None

        period = ds.period or ""

        # Step 1: Count records per table
        counts = await self._count_all_records(dataset_id)

        # Step 2: Build boolean flags
        manifest = DataManifest(
            dataset_id=dataset_id,
            period=period,
            has_trial_balance=counts.get("trial_balance", 0) > 0,
            has_revenue_detail=counts.get("revenue", 0) > 0,
            has_cogs_detail=counts.get("cogs", 0) > 0,
            has_ga_expenses=counts.get("ga_expenses", 0) > 0,
            has_balance_sheet=counts.get("balance_sheet", 0) > 0,
            has_transactions=counts.get("transactions", 0) > 0,
            has_budget=counts.get("budget", 0) > 0,
            record_counts=counts,
        )

        # Step 3: Check for MR mapping in TB items
        if manifest.has_trial_balance:
            mapped_count = (await self.db.execute(
                select(func.count()).select_from(
                    select(TrialBalanceItem.id).where(
                        TrialBalanceItem.dataset_id == dataset_id,
                        TrialBalanceItem.mr_mapping.isnot(None),
                        TrialBalanceItem.mr_mapping != "",
                    ).subquery()
                )
            )).scalar() or 0
            manifest.has_mapping_sheet = mapped_count > 0

        # Step 4: Apply financial derivation logic
        self._apply_financial_logic(manifest)

        # Step 5: Discover linked datasets (prior year, budget source)
        await self._discover_links(manifest, ds)

        # Step 6: Score report capabilities
        self._score_report_capabilities(manifest)

        # Step 7: Build warnings
        self._build_warnings(manifest)

        # Step 8: Compute financial totals
        await self._compute_totals(manifest, dataset_id)

        logger.info(f"Intelligence: {manifest.summary}")
        return manifest

    # ── Quick Analysis (from cached metadata) ────────────────────────

    async def analyze_quick(self, dataset_id: int) -> Optional[DataManifest]:
        """Fast analysis using cached parse_metadata.record_counts.

        Zero extra DB queries beyond loading the dataset row.
        Falls back to full analyze() if cache is empty.
        """
        ds = (await self.db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )).scalar_one_or_none()
        if not ds:
            return None

        # Check for cached manifest first
        meta = ds.parse_metadata or {}
        cached = meta.get("data_manifest")
        if cached:
            try:
                return DataManifest(**cached)
            except (TypeError, KeyError):
                pass  # Corrupted cache, fall through

        # Try to build from record_counts in parse_metadata
        rc = meta.get("record_counts", {})
        if not rc:
            # No cache at all — do full analysis
            return await self.analyze(dataset_id)

        period = ds.period or ""

        manifest = DataManifest(
            dataset_id=dataset_id,
            period=period,
            has_trial_balance=rc.get("trial_balance", rc.get("trial_balance_items", 0)) > 0,
            has_revenue_detail=rc.get("revenue", rc.get("revenue_items", 0)) > 0,
            has_cogs_detail=rc.get("cogs", rc.get("cogs_items", 0)) > 0,
            has_ga_expenses=rc.get("ga_expenses", rc.get("ga_expense_items", 0)) > 0,
            has_balance_sheet=rc.get("balance_sheet", rc.get("balance_sheet_items", 0)) > 0,
            has_transactions=rc.get("transactions", 0) > 0,
            has_budget=rc.get("budget", rc.get("budget_lines", 0)) > 0,
            record_counts=rc,
        )

        # Apply logic + links
        self._apply_financial_logic(manifest)
        await self._discover_links(manifest, ds)
        self._score_report_capabilities(manifest)
        self._build_warnings(manifest)

        return manifest

    # ── Analyze & Cache ──────────────────────────────────────────────

    async def analyze_and_cache(self, dataset_id: int) -> Optional[DataManifest]:
        """Full analysis + writes result to parse_metadata['data_manifest'].

        Call on upload so all future analyze_quick() calls are instant.
        """
        manifest = await self.analyze(dataset_id)
        if not manifest:
            return None

        # Write to parse_metadata
        ds = (await self.db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )).scalar_one_or_none()
        if ds:
            meta = dict(ds.parse_metadata or {})
            meta["data_manifest"] = manifest.to_dict()
            # Also ensure record_counts are up to date
            meta["record_counts"] = manifest.record_counts
            await self.db.execute(
                update(Dataset)
                .where(Dataset.id == dataset_id)
                .values(parse_metadata=meta)
            )
            await self.db.flush()

        return manifest

    # ── Internal: Count all records ──────────────────────────────────

    async def _count_all_records(self, dataset_id: int) -> Dict[str, int]:
        """Query every financial data table to get record counts."""
        tables = {
            "trial_balance": TrialBalanceItem,
            "revenue": RevenueItem,
            "cogs": COGSItem,
            "ga_expenses": GAExpenseItem,
            "balance_sheet": BalanceSheetItem,
            "transactions": Transaction,
            "budget": BudgetLine,
        }
        counts = {}
        for name, model in tables.items():
            result = await self.db.execute(
                select(func.count()).select_from(
                    select(model.id).where(model.dataset_id == dataset_id).subquery()
                )
            )
            counts[name] = result.scalar() or 0
        return counts

    # ── Internal: Apply financial derivation logic ───────────────────

    @staticmethod
    def _apply_financial_logic(manifest: DataManifest):
        """Apply financial knowledge: what can be derived from what exists.

        Financial logic:
        - Trial Balance → can derive both BS and P&L (accounts 1-5 = BS, 6-9 = P&L)
        - Revenue detail → product-level revenue; else TB can provide totals
        - COGS detail → product-level COGS; else TB can provide totals
        """
        # P&L derivation
        manifest.can_derive_pl = manifest.has_trial_balance
        manifest.can_derive_bs = manifest.has_trial_balance

        # Revenue source resolution
        if manifest.has_revenue_detail:
            manifest.revenue_source = "detail"
        elif manifest.has_trial_balance:
            manifest.revenue_source = "derived_from_tb"
        else:
            manifest.revenue_source = "none"

        # COGS source resolution
        if manifest.has_cogs_detail:
            manifest.cogs_source = "detail"
        elif manifest.has_trial_balance:
            manifest.cogs_source = "derived_from_tb"
        else:
            manifest.cogs_source = "none"

    # ── Internal: Discover linked datasets ───────────────────────────

    async def _discover_links(self, manifest: DataManifest, ds: Dataset):
        """Find prior year dataset and determine budget source.

        Financial logic:
        - Prior year = same month, previous year (for YoY comparison)
        - Budget can come from current dataset or prior year dataset
        """
        period = ds.period or ""
        prior_period = PeriodResolver.prior_year_period(period)

        # Prior year dataset
        if prior_period:
            prior_ds = await self.discovery.find_prior_year_dataset(period)
            if prior_ds:
                manifest.prior_year_dataset_id = prior_ds.id
                manifest.prior_year_period = prior_period

                # Check if prior dataset has ANY usable data
                prior_meta = prior_ds.parse_metadata or {}
                prior_rc = prior_meta.get("record_counts", {})
                if prior_rc:
                    # Quick check from metadata
                    manifest.prior_year_has_data = any(
                        prior_rc.get(k, 0) > 0
                        for k in ["trial_balance", "trial_balance_items",
                                   "revenue", "revenue_items",
                                   "cogs", "cogs_items",
                                   "ga_expenses", "ga_expense_items",
                                   "transactions", "balance_sheet", "balance_sheet_items"]
                    )
                else:
                    # No metadata cache — do a quick count
                    for model in [TrialBalanceItem, RevenueItem, COGSItem, GAExpenseItem, Transaction]:
                        cnt = (await self.db.execute(
                            select(func.count()).select_from(
                                select(model.id).where(model.dataset_id == prior_ds.id).subquery()
                            )
                        )).scalar() or 0
                        if cnt > 0:
                            manifest.prior_year_has_data = True
                            break

        # Budget source resolution
        if manifest.has_budget:
            manifest.budget_source_dataset_id = manifest.dataset_id
            manifest.budget_source = "current"
        elif manifest.prior_year_dataset_id:
            # Check if prior year dataset has budget
            prior_budget_count = (await self.db.execute(
                select(func.count()).select_from(
                    select(BudgetLine.id).where(
                        BudgetLine.dataset_id == manifest.prior_year_dataset_id
                    ).subquery()
                )
            )).scalar() or 0
            if prior_budget_count > 0:
                manifest.budget_source_dataset_id = manifest.prior_year_dataset_id
                manifest.budget_source = "prior_year"
                manifest.has_budget = True  # Available from linked dataset
                manifest.record_counts["budget"] = prior_budget_count

    # ── Internal: Score report capabilities ──────────────────────────

    @staticmethod
    def _score_report_capabilities(manifest: DataManifest):
        """Determine which reports can be produced and how complete they'll be.

        Scoring logic:
        - 'ready': at least one required data source exists
        - 'partial': required data exists but key enhancers are missing
        - 'unavailable': no required data source exists
        """
        capabilities = {}

        for report_name, spec in REPORT_REQUIREMENTS.items():
            required = spec["required_any"]
            enhancers = spec.get("enhancers", [])

            # Check if any required data exists
            has_required = any(getattr(manifest, flag, False) for flag in required)

            if not has_required:
                capabilities[report_name] = "unavailable"
                continue

            # Check enhancers to determine ready vs partial
            enhancer_count = sum(1 for e in enhancers if getattr(manifest, e, False))
            total_enhancers = len(enhancers)

            if total_enhancers == 0 or enhancer_count >= total_enhancers * 0.5:
                capabilities[report_name] = "ready"
            else:
                capabilities[report_name] = "partial"

        manifest.report_capabilities = capabilities

    # ── Internal: Build warnings ─────────────────────────────────────

    @staticmethod
    def _build_warnings(manifest: DataManifest):
        """Generate human-readable warnings about missing data or limitations."""
        warnings = []

        if not manifest.has_trial_balance:
            warnings.append("No Trial Balance found — cannot derive Balance Sheet or P&L from account totals.")

        if manifest.revenue_source == "derived_from_tb":
            warnings.append("Revenue derived from Trial Balance account totals (no product-level detail).")
        elif manifest.revenue_source == "none":
            warnings.append("No revenue data found — revenue analysis unavailable.")

        if manifest.cogs_source == "derived_from_tb":
            warnings.append("COGS derived from Trial Balance account totals (no product-level breakdown).")
        elif manifest.cogs_source == "none":
            warnings.append("No COGS data found — cost analysis unavailable.")

        if not manifest.has_ga_expenses:
            warnings.append("No G&A expenses — operating expense breakdown incomplete.")

        if not manifest.prior_year_dataset_id:
            prior = PeriodResolver.prior_year_period(manifest.period)
            if prior:
                warnings.append(f"No {prior} dataset found — year-over-year comparison unavailable.")
        elif not manifest.prior_year_has_data:
            warnings.append(
                f"Prior year dataset (DS #{manifest.prior_year_dataset_id}) exists "
                f"but contains no usable financial data."
            )

        if not manifest.has_budget:
            warnings.append("No budget data — plan vs actual deviation unavailable.")

        # Note: TB items from local COA (Georgian, Russian, etc.) typically don't
        # carry Baku MR codes.  The system derives them via COA prefix mapping
        # (e.g., 7110→02.A, 8110→03) which is the standard workflow.
        # Only flag if ZERO TB items have any mapping after generation has run.
        if manifest.has_trial_balance and not manifest.has_mapping_sheet:
            warnings.append("MR codes derived from COA prefix mapping (no pre-assigned Baku codes in source data).")

        manifest.missing = warnings

    # ── Internal: Compute financial totals ───────────────────────────

    async def _compute_totals(self, manifest: DataManifest, dataset_id: int):
        """Compute summary financial totals for the manifest."""
        # Revenue total
        if manifest.has_revenue_detail:
            result = await self.db.execute(
                select(func.sum(RevenueItem.net)).where(
                    RevenueItem.dataset_id == dataset_id
                )
            )
            manifest.total_revenue = result.scalar() or 0.0

        # COGS total
        if manifest.has_cogs_detail:
            result = await self.db.execute(
                select(func.sum(COGSItem.total_cogs)).where(
                    COGSItem.dataset_id == dataset_id
                )
            )
            manifest.total_cogs = result.scalar() or 0.0

        # GA total
        if manifest.has_ga_expenses:
            result = await self.db.execute(
                select(func.sum(GAExpenseItem.amount)).where(
                    GAExpenseItem.dataset_id == dataset_id
                )
            )
            manifest.total_ga = result.scalar() or 0.0

    # ── Public: Find best dataset for a report ───────────────────────

    async def find_best_dataset_for_report(self, report_type: str) -> Optional[int]:
        """Find the best dataset for producing a specific report type.

        Scoring: active dataset gets +10 base, each data type needed gets +1.
        This allows the system to prefer datasets that have the richest data
        for the requested report.
        """
        spec = REPORT_REQUIREMENTS.get(report_type)
        if not spec:
            # Unknown report type — just return active dataset
            return await self._get_active_dataset_id()

        # Get all ready datasets
        result = await self.db.execute(
            select(Dataset).where(Dataset.status == "ready").order_by(Dataset.created_at.desc())
        )
        datasets = result.scalars().all()

        if not datasets:
            return None

        best_id = None
        best_score = -1

        for ds in datasets:
            score = 0

            # Active dataset bonus
            if ds.is_active:
                score += 10

            # Analyze from metadata (fast path)
            meta = ds.parse_metadata or {}
            rc = meta.get("record_counts", {})

            # Map data flags to record count keys
            flag_to_rc = {
                "has_trial_balance": ["trial_balance", "trial_balance_items"],
                "has_revenue_detail": ["revenue", "revenue_items"],
                "has_cogs_detail": ["cogs", "cogs_items"],
                "has_ga_expenses": ["ga_expenses", "ga_expense_items"],
                "has_balance_sheet": ["balance_sheet", "balance_sheet_items"],
                "has_transactions": ["transactions"],
                "has_budget": ["budget", "budget_lines"],
            }

            def has_data(flag_name: str) -> bool:
                keys = flag_to_rc.get(flag_name, [])
                return any(rc.get(k, 0) > 0 for k in keys)

            # Check required data
            has_required = any(has_data(f) for f in spec["required_any"])
            if not has_required:
                continue  # Skip — can't produce this report

            # Score enhancers
            for enhancer in spec.get("enhancers", []):
                if has_data(enhancer):
                    score += 1

            # Score required (more required data = better)
            for req in spec["required_any"]:
                if has_data(req):
                    score += 2

            if score > best_score:
                best_score = score
                best_id = ds.id

        return best_id or await self._get_active_dataset_id()

    async def _get_active_dataset_id(self) -> Optional[int]:
        """Get the currently active dataset ID."""
        result = await self.db.execute(
            select(Dataset.id).where(Dataset.is_active == True).limit(1)
        )
        row = result.first()
        return row[0] if row else None


# ═══════════════════════════════════════════════════════════════════════
# Smart Resolver — Context-Aware Dataset Resolution
# ═══════════════════════════════════════════════════════════════════════

class SmartResolver:
    """Replace dumb _resolve_dataset_id with context-aware resolution.

    Old behavior: return provided ID, or active dataset. No thinking.

    New behavior:
    1. If explicit ID provided → use it
    2. Otherwise → find best dataset for this report type/context
    3. Fallback → active dataset regardless

    Backward-compatible: resolve(dataset_id, db) with no context
    defaults to "dashboard" context.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.intel = DatasetIntelligence(db)

    async def resolve(
        self,
        dataset_id: Optional[int] = None,
        context: str = "dashboard",
        period: Optional[str] = None,
    ) -> Optional[int]:
        """Resolve the best dataset ID for the given context.

        Args:
            dataset_id: Explicit ID (if user provided one)
            context: Report/page context — maps to report_type
            period: Optional period filter (e.g., "January 2026")

        Returns:
            Best dataset ID, or None if no datasets exist
        """
        # Priority 1: Explicit ID
        if dataset_id:
            return dataset_id

        # Priority 2: Period-specific resolution
        if period:
            discovery = DatasetDiscovery(self.db)
            ds = await discovery.find_by_period(period)
            if ds:
                return ds.id

        # Priority 3: Context-aware best dataset
        context_to_report = {
            "dashboard": "dashboard",
            "mr": "mr_report",
            "tb": "income_statement",  # TB is used primarily for P&L derivation
            "pl": "income_statement",
            "bs": "balance_sheet",
            "cogs": "cogs_analysis",
            "revenue": "revenue_analysis",
            "cash_flow": "cash_flow",
        }
        report_type = context_to_report.get(context, "dashboard")
        best = await self.intel.find_best_dataset_for_report(report_type)
        if best:
            return best

        # Priority 4: Fallback — any active dataset
        return await self.intel._get_active_dataset_id()
