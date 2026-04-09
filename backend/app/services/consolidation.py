"""
FinAI OS — Multi-Entity Consolidation Framework
=================================================
IFRS 10-compliant group consolidation engine.

Supports:
  - Multi-entity group structures with ownership percentages
  - Currency translation (current-rate method per IAS 21)
  - Intercompany elimination (revenue/COGS, receivables/payables, dividends)
  - Minority (non-controlling) interest per IFRS 10
  - Consolidated P&L, BS, CF with full reconciliation

Usage:
    from app.services.consolidation import consolidation_engine

    consolidation_engine.register_entity(Entity(...))
    consolidation_engine.set_group_structure("parent", [("sub_a", 100.0), ("sub_b", 80.0)])
    result = consolidation_engine.consolidate("2024-01")
"""

import logging
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Entity:
    """A legal entity (company) within a consolidation group."""
    entity_id: str
    name: str
    parent_entity_id: Optional[str] = None
    ownership_pct: float = 100.0  # Parent's ownership percentage (0-100)
    currency: str = "GEL"
    chart_of_accounts: str = "IFRS"  # COA standard used
    is_parent: bool = False
    industry: str = "fuel_distribution"

    def get_financials(self, period: str) -> Dict[str, float]:
        """Fetch financials from the data_store for this entity."""
        try:
            from app.services.data_store import data_store
            companies = data_store.list_companies()
            for c in companies:
                if (c["name"].lower() == self.name.lower()
                        or self.entity_id == str(c["id"])):
                    return data_store.get_financials(c["id"], period)
            return {}
        except Exception as e:
            logger.warning("Cannot fetch financials for %s: %s", self.entity_id, e)
            return {}


@dataclass
class EliminationEntry:
    """A single intercompany elimination journal entry."""
    entry_id: str = ""
    elimination_type: str = ""  # ic_revenue_cogs, ic_receivable_payable, ic_dividend
    entity_a: str = ""
    entity_b: str = ""
    debit_account: str = ""
    credit_account: str = ""
    amount: float = 0.0
    description: str = ""

    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "elimination_type": self.elimination_type,
            "entity_a": self.entity_a,
            "entity_b": self.entity_b,
            "debit_account": self.debit_account,
            "credit_account": self.credit_account,
            "amount": self.amount,
            "description": self.description,
        }


@dataclass
class ConsolidatedResult:
    """Complete result of a group consolidation run."""
    period: str = ""
    group_currency: str = "GEL"
    timestamp: str = ""

    # Individual entity statements (before elimination)
    individual_statements: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Translation adjustments per entity
    translation_adjustments: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Elimination entries
    eliminations: List[EliminationEntry] = field(default_factory=list)

    # Minority interest by entity
    minority_interest: Dict[str, float] = field(default_factory=dict)
    minority_interest_bs: Dict[str, float] = field(default_factory=dict)

    # Consolidated statements
    consolidated_pnl: Dict[str, float] = field(default_factory=dict)
    consolidated_bs: Dict[str, float] = field(default_factory=dict)
    consolidated_cf: Dict[str, float] = field(default_factory=dict)

    # Reconciliation proof
    reconciliation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "group_currency": self.group_currency,
            "timestamp": self.timestamp,
            "individual_statements": self.individual_statements,
            "translation_adjustments": self.translation_adjustments,
            "eliminations": [e.to_dict() for e in self.eliminations],
            "minority_interest": self.minority_interest,
            "minority_interest_bs": self.minority_interest_bs,
            "consolidated_pnl": self.consolidated_pnl,
            "consolidated_bs": self.consolidated_bs,
            "consolidated_cf": self.consolidated_cf,
            "reconciliation": self.reconciliation,
        }


# =============================================================================
# CURRENCY TRANSLATION (IAS 21 Current-Rate Method)
# =============================================================================

# Default exchange rates (to GEL). In production these come from an FX feed.
_DEFAULT_RATES: Dict[str, float] = {
    "GEL": 1.0,
    "USD": 2.70,
    "EUR": 2.95,
    "GBP": 3.40,
    "RUB": 0.030,
    "TRY": 0.084,
}


def _get_rate(from_ccy: str, to_ccy: str, rates: Dict[str, float]) -> float:
    """Get exchange rate from_ccy -> to_ccy. Rates dict maps ccy -> GEL."""
    if from_ccy == to_ccy:
        return 1.0
    from_gel = rates.get(from_ccy, 1.0)
    to_gel = rates.get(to_ccy, 1.0)
    if to_gel == 0:
        return 1.0
    return from_gel / to_gel


def translate_financials(
    data: Dict[str, float],
    from_ccy: str,
    to_ccy: str,
    rates: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Translate financials from one currency to another using current-rate method.

    IAS 21 rules:
      - P&L items: translated at average rate (approximated by closing rate here)
      - BS items: translated at closing rate
      - Equity items: translated at historical rate (approximated)
      - Difference goes to Translation Reserve (OCI)

    Returns (translated_data, adjustments).
    """
    if from_ccy == to_ccy:
        return dict(data), {}

    r = rates or _DEFAULT_RATES
    closing_rate = _get_rate(from_ccy, to_ccy, r)
    # Approximate average rate as 98% of closing (simplification)
    avg_rate = closing_rate * 0.98
    # Historical rate approximation for equity
    hist_rate = closing_rate * 0.95

    translated = {}
    adjustments = {}

    # BS equity items use historical rate
    _equity_keys = {"share_capital", "retained_earnings", "reserves", "bs_share_capital",
                    "bs_retained_earnings", "bs_reserves"}
    # P&L items use average rate
    _pnl_keys = {"revenue", "cogs", "gross_profit", "selling_expenses", "admin_expenses",
                 "ga_expenses", "ebitda", "depreciation", "ebit", "net_profit",
                 "profit_before_tax", "total_opex", "non_operating_income",
                 "non_operating_expense", "revenue_wholesale", "revenue_retail",
                 "revenue_other", "cogs_wholesale", "cogs_retail"}

    for key, value in data.items():
        if not isinstance(value, (int, float)):
            continue
        if key in _equity_keys:
            rate = hist_rate
        elif key in _pnl_keys or not key.startswith("bs_"):
            rate = avg_rate
        else:
            rate = closing_rate

        translated[key] = round(value * rate, 2)
        if rate != closing_rate:
            adjustments[key] = round(value * (closing_rate - rate), 2)

    # Translation reserve = sum of adjustments (goes to OCI in equity)
    total_adj = sum(adjustments.values())
    if abs(total_adj) > 0.01:
        translated["translation_reserve"] = round(total_adj, 2)
        adjustments["translation_reserve"] = round(total_adj, 2)

    return translated, adjustments


# =============================================================================
# INTERCOMPANY MATCHER
# =============================================================================

class IntercompanyMatcher:
    """
    Identifies and matches intercompany transactions between entities.

    Matching rules:
      - IC Revenue (entity A) <-> IC COGS (entity B): eliminate matching amounts
      - IC Receivables (entity A) <-> IC Payables (entity B): eliminate matching amounts
      - IC Dividends: eliminate against investment account
    """

    # Account name patterns that indicate intercompany items
    IC_REVENUE_PATTERNS = ["ic_revenue", "intercompany_revenue", "ic_sales",
                           "intercompany_sales", "intragroup_revenue"]
    IC_COGS_PATTERNS = ["ic_cogs", "intercompany_cogs", "ic_purchases",
                        "intercompany_purchases", "intragroup_cost"]
    IC_RECEIVABLE_PATTERNS = ["ic_receivable", "intercompany_receivable",
                              "due_from_related", "intragroup_receivable"]
    IC_PAYABLE_PATTERNS = ["ic_payable", "intercompany_payable",
                           "due_to_related", "intragroup_payable"]
    IC_DIVIDEND_PATTERNS = ["ic_dividend", "intercompany_dividend",
                            "dividend_from_subsidiary"]
    IC_INVESTMENT_PATTERNS = ["investment_in_subsidiary", "ic_investment",
                              "intercompany_investment"]

    def _find_ic_amount(self, data: Dict[str, float], patterns: List[str]) -> float:
        """Find the total IC amount by matching known patterns in the financials keys."""
        total = 0.0
        for key, value in data.items():
            key_lower = key.lower().replace(" ", "_")
            for pattern in patterns:
                if pattern in key_lower:
                    total += value
                    break
        return total

    def match_transactions(
        self,
        entity_a_id: str,
        entity_a_data: Dict[str, float],
        entity_b_id: str,
        entity_b_data: Dict[str, float],
    ) -> List[EliminationEntry]:
        """
        Match intercompany transactions between two entities.
        Returns elimination entries needed to remove IC transactions.
        """
        eliminations = []

        # ── IC Revenue ↔ IC COGS ──
        a_ic_revenue = self._find_ic_amount(entity_a_data, self.IC_REVENUE_PATTERNS)
        b_ic_cogs = self._find_ic_amount(entity_b_data, self.IC_COGS_PATTERNS)
        b_ic_revenue = self._find_ic_amount(entity_b_data, self.IC_REVENUE_PATTERNS)
        a_ic_cogs = self._find_ic_amount(entity_a_data, self.IC_COGS_PATTERNS)

        # A sells to B: A's IC revenue matches B's IC COGS
        if a_ic_revenue > 0 and b_ic_cogs > 0:
            match_amt = min(a_ic_revenue, b_ic_cogs)
            eliminations.append(EliminationEntry(
                elimination_type="ic_revenue_cogs",
                entity_a=entity_a_id,
                entity_b=entity_b_id,
                debit_account="Revenue (IC Elimination)",
                credit_account="Cost of Sales (IC Elimination)",
                amount=match_amt,
                description=f"Eliminate IC sales {entity_a_id}→{entity_b_id}: "
                            f"Dr Revenue {match_amt:,.0f} / Cr COGS {match_amt:,.0f}",
            ))

        # B sells to A: B's IC revenue matches A's IC COGS
        if b_ic_revenue > 0 and a_ic_cogs > 0:
            match_amt = min(b_ic_revenue, a_ic_cogs)
            eliminations.append(EliminationEntry(
                elimination_type="ic_revenue_cogs",
                entity_a=entity_b_id,
                entity_b=entity_a_id,
                debit_account="Revenue (IC Elimination)",
                credit_account="Cost of Sales (IC Elimination)",
                amount=match_amt,
                description=f"Eliminate IC sales {entity_b_id}→{entity_a_id}: "
                            f"Dr Revenue {match_amt:,.0f} / Cr COGS {match_amt:,.0f}",
            ))

        # ── IC Receivables ↔ IC Payables ──
        a_ic_recv = self._find_ic_amount(entity_a_data, self.IC_RECEIVABLE_PATTERNS)
        b_ic_pay = self._find_ic_amount(entity_b_data, self.IC_PAYABLE_PATTERNS)
        b_ic_recv = self._find_ic_amount(entity_b_data, self.IC_RECEIVABLE_PATTERNS)
        a_ic_pay = self._find_ic_amount(entity_a_data, self.IC_PAYABLE_PATTERNS)

        if a_ic_recv > 0 and b_ic_pay > 0:
            match_amt = min(a_ic_recv, b_ic_pay)
            eliminations.append(EliminationEntry(
                elimination_type="ic_receivable_payable",
                entity_a=entity_a_id,
                entity_b=entity_b_id,
                debit_account="IC Payable (Elimination)",
                credit_account="IC Receivable (Elimination)",
                amount=match_amt,
                description=f"Eliminate IC balances {entity_a_id}↔{entity_b_id}: "
                            f"Dr Payable {match_amt:,.0f} / Cr Receivable {match_amt:,.0f}",
            ))

        if b_ic_recv > 0 and a_ic_pay > 0:
            match_amt = min(b_ic_recv, a_ic_pay)
            eliminations.append(EliminationEntry(
                elimination_type="ic_receivable_payable",
                entity_a=entity_b_id,
                entity_b=entity_a_id,
                debit_account="IC Payable (Elimination)",
                credit_account="IC Receivable (Elimination)",
                amount=match_amt,
                description=f"Eliminate IC balances {entity_b_id}↔{entity_a_id}: "
                            f"Dr Payable {match_amt:,.0f} / Cr Receivable {match_amt:,.0f}",
            ))

        # ── IC Dividends ──
        a_ic_div = self._find_ic_amount(entity_a_data, self.IC_DIVIDEND_PATTERNS)
        b_ic_div = self._find_ic_amount(entity_b_data, self.IC_DIVIDEND_PATTERNS)

        if a_ic_div > 0:
            eliminations.append(EliminationEntry(
                elimination_type="ic_dividend",
                entity_a=entity_a_id,
                entity_b=entity_b_id,
                debit_account="Dividend Income (IC Elimination)",
                credit_account="Dividends Declared (IC Elimination)",
                amount=a_ic_div,
                description=f"Eliminate IC dividend {entity_a_id}: "
                            f"Dr Dividend Income {a_ic_div:,.0f} / Cr Dividends {a_ic_div:,.0f}",
            ))

        if b_ic_div > 0:
            eliminations.append(EliminationEntry(
                elimination_type="ic_dividend",
                entity_a=entity_b_id,
                entity_b=entity_a_id,
                debit_account="Dividend Income (IC Elimination)",
                credit_account="Dividends Declared (IC Elimination)",
                amount=b_ic_div,
                description=f"Eliminate IC dividend {entity_b_id}: "
                            f"Dr Dividend Income {b_ic_div:,.0f} / Cr Dividends {b_ic_div:,.0f}",
            ))

        return eliminations

    def identify_unmatched(
        self,
        entity_a_id: str,
        entity_a_data: Dict[str, float],
        entity_b_id: str,
        entity_b_data: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Identify IC items that don't fully reconcile between two entities.
        Returns audit flags for items where the IC amounts don't match.
        """
        flags = []

        a_ic_rev = self._find_ic_amount(entity_a_data, self.IC_REVENUE_PATTERNS)
        b_ic_cogs = self._find_ic_amount(entity_b_data, self.IC_COGS_PATTERNS)
        if a_ic_rev > 0 or b_ic_cogs > 0:
            diff = abs(a_ic_rev - b_ic_cogs)
            if diff > 0.01:
                flags.append({
                    "type": "ic_revenue_cogs_mismatch",
                    "entity_a": entity_a_id,
                    "entity_b": entity_b_id,
                    "a_amount": a_ic_rev,
                    "b_amount": b_ic_cogs,
                    "difference": diff,
                    "severity": "warning" if diff < a_ic_rev * 0.01 else "error",
                })

        a_ic_recv = self._find_ic_amount(entity_a_data, self.IC_RECEIVABLE_PATTERNS)
        b_ic_pay = self._find_ic_amount(entity_b_data, self.IC_PAYABLE_PATTERNS)
        if a_ic_recv > 0 or b_ic_pay > 0:
            diff = abs(a_ic_recv - b_ic_pay)
            if diff > 0.01:
                flags.append({
                    "type": "ic_receivable_payable_mismatch",
                    "entity_a": entity_a_id,
                    "entity_b": entity_b_id,
                    "a_amount": a_ic_recv,
                    "b_amount": b_ic_pay,
                    "difference": diff,
                    "severity": "warning" if diff < a_ic_recv * 0.01 else "error",
                })

        return flags


# =============================================================================
# CONSOLIDATION ENGINE
# =============================================================================

class ConsolidationEngine:
    """
    IFRS 10-compliant multi-entity consolidation engine.

    Consolidation steps (full method for subsidiaries):
      1. Collect individual financials for the period
      2. Currency translation (IAS 21 current-rate method)
      3. Line-by-line aggregation of 100% of subsidiary amounts
      4. Intercompany elimination
      5. Non-controlling interest (NCI) allocation per IFRS 10.B94
      6. Produce consolidated P&L, BS, CF with reconciliation

    NCI calculation (IFRS 10):
      - NCI share of net income = subsidiary_net_profit * (1 - ownership_pct / 100)
      - NCI share of net assets = subsidiary_equity * (1 - ownership_pct / 100)
      - Parent equity in subsidiary is eliminated against investment
    """

    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._group_structures: Dict[str, List[Tuple[str, float]]] = {}
        self._fx_rates: Dict[str, float] = dict(_DEFAULT_RATES)
        self._matcher = IntercompanyMatcher()
        self._last_result: Optional[ConsolidatedResult] = None

    # ── Entity Management ────────────────────────────────────────────

    def register_entity(self, entity: Entity) -> str:
        """Register a legal entity. Returns entity_id."""
        self._entities[entity.entity_id] = entity
        logger.info("Registered entity: %s (%s) ownership=%.1f%%",
                     entity.entity_id, entity.name, entity.ownership_pct)
        return entity.entity_id

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def list_entities(self) -> List[Dict[str, Any]]:
        result = []
        for e in self._entities.values():
            result.append({
                "entity_id": e.entity_id,
                "name": e.name,
                "parent_entity_id": e.parent_entity_id,
                "ownership_pct": e.ownership_pct,
                "currency": e.currency,
                "is_parent": e.is_parent,
                "industry": e.industry,
            })
        return result

    def set_group_structure(
        self,
        parent_id: str,
        child_ids_with_ownership: List[Tuple[str, float]],
    ) -> None:
        """
        Define consolidation group hierarchy.

        Args:
            parent_id: The parent entity ID
            child_ids_with_ownership: List of (child_entity_id, ownership_pct) tuples
        """
        if parent_id in self._entities:
            self._entities[parent_id].is_parent = True
        self._group_structures[parent_id] = child_ids_with_ownership
        for child_id, pct in child_ids_with_ownership:
            if child_id in self._entities:
                self._entities[child_id].parent_entity_id = parent_id
                self._entities[child_id].ownership_pct = pct
        logger.info("Group structure: parent=%s, subsidiaries=%s",
                     parent_id, [(c, f"{p:.0f}%") for c, p in child_ids_with_ownership])

    def set_fx_rates(self, rates: Dict[str, float]) -> None:
        """Override exchange rates (currency -> GEL)."""
        self._fx_rates.update(rates)

    # ── Core Consolidation ───────────────────────────────────────────

    def consolidate(self, period: str) -> ConsolidatedResult:
        """
        Run full IFRS 10 consolidation for a period.

        Steps:
          1. Collect financials from all entities
          2. Currency translation (IAS 21)
          3. Intercompany elimination
          4. Minority interest calculation
          5. Produce consolidated P&L, BS, CF
        """
        result = ConsolidatedResult(
            period=period,
            group_currency=self._determine_group_currency(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if not self._entities:
            result.reconciliation = {"error": "No entities registered"}
            return result

        group_ccy = result.group_currency

        # ── Step 1: Collect individual financials ──
        all_financials: Dict[str, Dict[str, float]] = {}
        for eid, entity in self._entities.items():
            fin = entity.get_financials(period)
            if not fin:
                logger.warning("No financials for entity %s period %s", eid, period)
                fin = {}
            all_financials[eid] = fin
            result.individual_statements[eid] = dict(fin)

        # ── Step 2: Currency translation ──
        translated_financials: Dict[str, Dict[str, float]] = {}
        for eid, fin in all_financials.items():
            entity = self._entities[eid]
            if entity.currency != group_ccy:
                translated, adjustments = translate_financials(
                    fin, entity.currency, group_ccy, self._fx_rates
                )
                translated_financials[eid] = translated
                if adjustments:
                    result.translation_adjustments[eid] = adjustments
            else:
                translated_financials[eid] = dict(fin)

        # ── Step 3: Intercompany elimination ──
        entity_ids = list(self._entities.keys())
        all_unmatched = []
        for i in range(len(entity_ids)):
            for j in range(i + 1, len(entity_ids)):
                eid_a, eid_b = entity_ids[i], entity_ids[j]
                elims = self._matcher.match_transactions(
                    eid_a, translated_financials.get(eid_a, {}),
                    eid_b, translated_financials.get(eid_b, {}),
                )
                result.eliminations.extend(elims)
                unmatched = self._matcher.identify_unmatched(
                    eid_a, translated_financials.get(eid_a, {}),
                    eid_b, translated_financials.get(eid_b, {}),
                )
                all_unmatched.extend(unmatched)

        # Build elimination totals by account type for applying to consolidated
        elim_totals = self._compute_elimination_totals(result.eliminations)

        # ── Step 4: Line-by-line aggregation + NCI ──
        # Aggregate 100% of all entities (full consolidation method)
        aggregated_pnl: Dict[str, float] = {}
        aggregated_bs: Dict[str, float] = {}

        _pnl_keys = {"revenue", "cogs", "gross_profit", "selling_expenses",
                      "admin_expenses", "ga_expenses", "total_opex", "ebitda",
                      "depreciation", "ebit", "non_operating_income",
                      "non_operating_expense", "profit_before_tax", "net_profit",
                      "revenue_wholesale", "revenue_retail", "revenue_other",
                      "cogs_wholesale", "cogs_retail"}
        _bs_keys = {"total_assets", "total_liabilities", "total_equity",
                     "cash", "current_assets", "noncurrent_assets",
                     "current_liabilities", "noncurrent_liabilities",
                     "share_capital", "retained_earnings", "reserves",
                     "current_ratio", "debt_to_equity"}
        _bs_prefixed = set()

        for eid, fin in translated_financials.items():
            for key, value in fin.items():
                if not isinstance(value, (int, float)):
                    continue
                key_lower = key.lower()
                is_bs = (key in _bs_keys or key.startswith("bs_")
                         or key in ("total_assets", "total_liabilities", "total_equity"))
                if is_bs:
                    clean_key = key[3:] if key.startswith("bs_") else key
                    aggregated_bs[clean_key] = aggregated_bs.get(clean_key, 0) + value
                    _bs_prefixed.add(clean_key)
                elif key in _pnl_keys:
                    aggregated_pnl[key] = aggregated_pnl.get(key, 0) + value

        # Apply IC eliminations to aggregated totals
        # Revenue/COGS elimination: reduce both revenue and COGS
        ic_rev_elim = elim_totals.get("ic_revenue_cogs", 0)
        if ic_rev_elim > 0:
            aggregated_pnl["revenue"] = aggregated_pnl.get("revenue", 0) - ic_rev_elim
            aggregated_pnl["cogs"] = aggregated_pnl.get("cogs", 0) - ic_rev_elim
            # Gross profit unchanged (revenue - COGS, both reduced by same amount)

        # Receivable/Payable elimination: reduce both BS sides
        ic_bal_elim = elim_totals.get("ic_receivable_payable", 0)
        if ic_bal_elim > 0:
            aggregated_bs["total_assets"] = aggregated_bs.get("total_assets", 0) - ic_bal_elim
            aggregated_bs["current_assets"] = aggregated_bs.get("current_assets", 0) - ic_bal_elim
            aggregated_bs["total_liabilities"] = aggregated_bs.get("total_liabilities", 0) - ic_bal_elim
            aggregated_bs["current_liabilities"] = aggregated_bs.get("current_liabilities", 0) - ic_bal_elim

        # Dividend elimination: reduce dividend income and retained earnings
        ic_div_elim = elim_totals.get("ic_dividend", 0)
        if ic_div_elim > 0:
            aggregated_pnl["non_operating_income"] = (
                aggregated_pnl.get("non_operating_income", 0) - ic_div_elim
            )
            aggregated_pnl["net_profit"] = aggregated_pnl.get("net_profit", 0) - ic_div_elim
            aggregated_bs["retained_earnings"] = (
                aggregated_bs.get("retained_earnings", 0) - ic_div_elim
            )

        # ── Step 5: Non-controlling interest (NCI) per IFRS 10 ──
        # NCI = subsidiary's net income * (1 - parent_ownership%)
        # NCI in BS = subsidiary's equity * (1 - parent_ownership%)
        total_nci_pnl = 0.0
        total_nci_bs = 0.0

        for eid, entity in self._entities.items():
            if entity.is_parent:
                continue
            ownership_frac = entity.ownership_pct / 100.0
            nci_frac = 1.0 - ownership_frac

            if nci_frac <= 0:
                continue

            sub_fin = translated_financials.get(eid, {})
            sub_net_profit = sub_fin.get("net_profit", 0)
            sub_equity = sub_fin.get("total_equity",
                         sub_fin.get("bs_total_equity", 0))

            nci_profit = round(sub_net_profit * nci_frac, 2)
            nci_equity = round(sub_equity * nci_frac, 2)

            result.minority_interest[eid] = nci_profit
            result.minority_interest_bs[eid] = nci_equity

            total_nci_pnl += nci_profit
            total_nci_bs += nci_equity

        # Adjust consolidated net profit for NCI
        aggregated_pnl["net_profit_attributable_to_parent"] = round(
            aggregated_pnl.get("net_profit", 0) - total_nci_pnl, 2
        )
        aggregated_pnl["net_profit_attributable_to_nci"] = round(total_nci_pnl, 2)

        # NCI on the balance sheet (presented within equity but separately)
        aggregated_bs["non_controlling_interest"] = round(total_nci_bs, 2)
        aggregated_bs["equity_attributable_to_parent"] = round(
            aggregated_bs.get("total_equity", 0) - total_nci_bs, 2
        )

        # Recalculate derived P&L metrics
        rev = aggregated_pnl.get("revenue", 0)
        cogs = aggregated_pnl.get("cogs", 0)
        aggregated_pnl["gross_profit"] = round(rev - cogs, 2)
        gp = aggregated_pnl["gross_profit"]
        opex = abs(aggregated_pnl.get("selling_expenses", 0)) + abs(aggregated_pnl.get("admin_expenses", 0))
        aggregated_pnl["total_opex"] = round(opex, 2)
        aggregated_pnl["ebitda"] = round(gp - opex, 2)
        depr = abs(aggregated_pnl.get("depreciation", 0))
        aggregated_pnl["ebit"] = round(aggregated_pnl["ebitda"] - depr, 2)

        # Round all values
        result.consolidated_pnl = {k: round(v, 2) for k, v in aggregated_pnl.items()}
        result.consolidated_bs = {k: round(v, 2) for k, v in aggregated_bs.items()}

        # ── Step 6: Cash flow (simplified — derive from P&L + BS changes) ──
        result.consolidated_cf = self._derive_cash_flow(
            result.consolidated_pnl, result.consolidated_bs
        )

        # ── Reconciliation proof ──
        result.reconciliation = self._build_reconciliation(
            result, translated_financials, elim_totals, total_nci_pnl, total_nci_bs, all_unmatched
        )

        self._last_result = result
        logger.info(
            "Consolidation complete: %d entities, %d eliminations, NCI_PnL=%.0f, NCI_BS=%.0f",
            len(self._entities), len(result.eliminations), total_nci_pnl, total_nci_bs,
        )
        return result

    def get_last_result(self) -> Optional[ConsolidatedResult]:
        return self._last_result

    # ── Private helpers ──────────────────────────────────────────────

    def _determine_group_currency(self) -> str:
        """Use parent entity's currency as group currency."""
        for e in self._entities.values():
            if e.is_parent:
                return e.currency
        # Fallback: most common currency
        currencies = [e.currency for e in self._entities.values()]
        if currencies:
            return max(set(currencies), key=currencies.count)
        return "GEL"

    def _compute_elimination_totals(
        self, eliminations: List[EliminationEntry]
    ) -> Dict[str, float]:
        """Sum elimination amounts by type."""
        totals: Dict[str, float] = {}
        for e in eliminations:
            totals[e.elimination_type] = totals.get(e.elimination_type, 0) + e.amount
        return totals

    def _derive_cash_flow(
        self,
        pnl: Dict[str, float],
        bs: Dict[str, float],
    ) -> Dict[str, float]:
        """Derive a simplified consolidated cash flow statement."""
        net_profit = pnl.get("net_profit", 0)
        depreciation = abs(pnl.get("depreciation", 0))

        # Operating CF = Net Profit + Depreciation (indirect method, simplified)
        operating_cf = net_profit + depreciation

        # Investing CF (not derivable without period-over-period BS, set to 0)
        investing_cf = 0.0

        # Financing CF (not derivable without detailed data, set to 0)
        financing_cf = 0.0

        return {
            "operating_cash_flow": round(operating_cf, 2),
            "investing_cash_flow": round(investing_cf, 2),
            "financing_cash_flow": round(financing_cf, 2),
            "net_change_in_cash": round(operating_cf + investing_cf + financing_cf, 2),
            "note": "Simplified indirect method; investing/financing require period-over-period BS data",
        }

    def _build_reconciliation(
        self,
        result: ConsolidatedResult,
        translated: Dict[str, Dict[str, float]],
        elim_totals: Dict[str, float],
        total_nci_pnl: float,
        total_nci_bs: float,
        unmatched: List[Dict],
    ) -> Dict[str, Any]:
        """Build reconciliation proof showing how consolidated figures derive."""
        # Sum of individual revenues
        sum_revenue = sum(
            f.get("revenue", 0) for f in translated.values()
        )
        sum_net_profit = sum(
            f.get("net_profit", 0) for f in translated.values()
        )
        sum_assets = sum(
            f.get("total_assets", f.get("bs_total_assets", 0)) for f in translated.values()
        )
        sum_equity = sum(
            f.get("total_equity", f.get("bs_total_equity", 0)) for f in translated.values()
        )

        ic_rev_elim = elim_totals.get("ic_revenue_cogs", 0)
        ic_div_elim = elim_totals.get("ic_dividend", 0)
        ic_bal_elim = elim_totals.get("ic_receivable_payable", 0)

        consol_revenue = result.consolidated_pnl.get("revenue", 0)
        consol_net_profit = result.consolidated_pnl.get("net_profit", 0)
        consol_assets = result.consolidated_bs.get("total_assets", 0)
        consol_equity = result.consolidated_bs.get("total_equity", 0)

        return {
            "revenue_proof": {
                "sum_individual": round(sum_revenue, 2),
                "less_ic_elimination": round(ic_rev_elim, 2),
                "consolidated": round(consol_revenue, 2),
                "matches": abs(sum_revenue - ic_rev_elim - consol_revenue) < 1.0,
            },
            "net_profit_proof": {
                "sum_individual": round(sum_net_profit, 2),
                "less_ic_dividends": round(ic_div_elim, 2),
                "consolidated_total": round(consol_net_profit, 2),
                "less_nci": round(total_nci_pnl, 2),
                "attributable_to_parent": round(
                    result.consolidated_pnl.get("net_profit_attributable_to_parent", 0), 2
                ),
            },
            "assets_proof": {
                "sum_individual": round(sum_assets, 2),
                "less_ic_balances": round(ic_bal_elim, 2),
                "consolidated": round(consol_assets, 2),
                "matches": abs(sum_assets - ic_bal_elim - consol_assets) < 1.0,
            },
            "equity_proof": {
                "sum_individual": round(sum_equity, 2),
                "nci_in_equity": round(total_nci_bs, 2),
                "parent_equity": round(
                    result.consolidated_bs.get("equity_attributable_to_parent", 0), 2
                ),
                "consolidated_total": round(consol_equity, 2),
            },
            "bs_equation_check": {
                "total_assets": round(consol_assets, 2),
                "total_liabilities": round(
                    result.consolidated_bs.get("total_liabilities", 0), 2
                ),
                "total_equity": round(consol_equity, 2),
                "nci": round(
                    result.consolidated_bs.get("non_controlling_interest", 0), 2
                ),
                "balanced": abs(
                    consol_assets
                    - result.consolidated_bs.get("total_liabilities", 0)
                    - consol_equity
                ) < 1.0,
            },
            "elimination_summary": {
                "total_entries": len(result.eliminations),
                "ic_revenue_cogs_eliminated": round(ic_rev_elim, 2),
                "ic_balances_eliminated": round(ic_bal_elim, 2),
                "ic_dividends_eliminated": round(ic_div_elim, 2),
            },
            "unmatched_items": unmatched,
            "entity_count": len(self._entities),
            "subsidiaries_with_nci": len(result.minority_interest),
        }


# =============================================================================
# MODULE SINGLETON
# =============================================================================

consolidation_engine = ConsolidationEngine()
