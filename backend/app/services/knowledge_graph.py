"""
FinAI Knowledge Graph — Financial entity graph with hierarchical relationships.
================================================================================
Replaces the shallow 9-rule RAG with a comprehensive financial knowledge system.

Indexed knowledge sources:
  1. GEORGIAN_COA (134 prefix rules) with BS/PL classification
  2. ACCOUNT_CLASS_RULES (9 top-level classes)
  3. EXPENSE_SUBCLASS_RULES + NON_OPERATING_SUBCLASS_RULES
  4. KEY_ACCOUNTS (12 special-meaning accounts)
  5. Financial flow explanations from accounting_intelligence.py (12 flows)
  6. Historical dataset patterns (auto-insights from uploads)
  7. User corrections (agent_memory where type="correction")

Architecture:
  - In-memory graph of FinancialEntity nodes with typed relationships
  - Each node produces searchable text documents for vector store indexing
  - Query API returns structured context, not just raw text
  - Integrates with VectorStoreService for persistence

Usage:
    from app.services.knowledge_graph import knowledge_graph

    # Build the graph (call once at startup)
    knowledge_graph.build()

    # Query
    results = knowledge_graph.query("what is account 7310?")
    context = knowledge_graph.get_context_for_account("7310")
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class KnowledgeEntity:
    """A node in the financial knowledge graph."""
    entity_id: str           # Unique ID: "coa_7310", "flow_inventory_to_cogs"
    entity_type: str         # "account", "class_rule", "flow", "concept", "pattern", "correction"
    label_en: str            # English label
    label_ka: str = ""       # Georgian label
    description: str = ""    # Full text description
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: List["KnowledgeRelation"] = field(default_factory=list)

    def to_document(self) -> str:
        """Convert to a searchable text document for vector store indexing."""
        parts = [self.label_en]
        if self.label_ka:
            parts.append(f"({self.label_ka})")
        if self.description:
            parts.append(f"- {self.description}")
        for key, val in self.properties.items():
            if val and key not in ("entity_id", "entity_type"):
                parts.append(f"{key}: {val}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "label_en": self.label_en,
            "label_ka": self.label_ka,
            "description": self.description,
            "properties": self.properties,
            "relationships": [r.to_dict() for r in self.relationships],
        }


@dataclass
class KnowledgeRelation:
    """A directed relationship between two entities."""
    relation_type: str      # "parent_of", "child_of", "flows_to", "part_of", "classifies", "reconciles_with"
    target_id: str          # Target entity ID
    label: str = ""         # Human-readable label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_type": self.relation_type,
            "target_id": self.target_id,
            "label": self.label,
        }


# =============================================================================
# KNOWLEDGE GRAPH
# =============================================================================

class FinancialKnowledgeGraph:
    """
    In-memory financial knowledge graph.

    Indexes all COA accounts, classification rules, financial flows,
    and domain concepts into a queryable graph structure. Each entity
    produces searchable documents for the vector store.
    """

    def __init__(self) -> None:
        self._entities: Dict[str, KnowledgeEntity] = {}
        self._is_built: bool = False
        self._index_by_type: Dict[str, List[str]] = {}  # type -> [entity_ids]
        self._index_by_code: Dict[str, str] = {}        # account_code -> entity_id

    @property
    def is_built(self) -> bool:
        return self._is_built

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    # =========================================================================
    # BUILD
    # =========================================================================

    def build(self) -> int:
        """
        Build the complete knowledge graph from all domain sources.
        Returns total number of entities created.

        PRESERVES dynamic entities (patterns, corrections) across rebuilds.
        Only static domain knowledge is rebuilt from source data.
        """
        # ── Preserve dynamic entities before clearing ─────────────
        dynamic_types = {"pattern", "correction"}
        preserved = {
            eid: entity
            for eid, entity in self._entities.items()
            if entity.entity_type in dynamic_types
        }

        self._entities.clear()
        self._index_by_type.clear()
        self._index_by_code.clear()

        # ── Rebuild static domain knowledge ───────────────────────
        try:
            self._build_coa_entities()
        except Exception as e:
            logger.warning("KG: COA entities failed: %s", e)

        try:
            self._build_class_rules()
        except Exception as e:
            logger.warning("KG: class rules failed: %s", e)

        try:
            self._build_key_accounts()
        except Exception as e:
            logger.warning("KG: key accounts failed: %s", e)

        try:
            self._build_flow_explanations()
        except Exception as e:
            logger.warning("KG: flow explanations failed: %s", e)

        try:
            self._build_domain_concepts()
        except Exception as e:
            logger.warning("KG: domain concepts failed: %s", e)

        try:
            self._build_relationships()
        except Exception as e:
            logger.warning("KG: relationships failed: %s", e)

        # ── Restore preserved dynamic entities ────────────────────
        if preserved:
            for eid, entity in preserved.items():
                self._add_entity(entity)
            logger.info(
                "KG: restored %d dynamic entities (patterns/corrections)",
                len(preserved),
            )

        try:
            self._add_regulatory_knowledge()
        except Exception as e:
            logger.warning("KG: regulatory knowledge failed: %s", e)

        try:
            self._add_financial_ratios()
        except Exception as e:
            logger.warning("KG: financial ratios failed: %s", e)

        try:
            self._add_extended_ifrs()
        except Exception as e:
            logger.warning("KG: extended IFRS failed: %s", e)

        try:
            self._add_audit_signals()
        except Exception as e:
            logger.warning("KG: audit signals failed: %s", e)

        try:
            self._add_fraud_signals()
        except Exception as e:
            logger.warning("KG: fraud signals failed: %s", e)

        try:
            self._add_accounting_formulas()
        except Exception as e:
            logger.warning("KG: accounting formulas failed: %s", e)

        try:
            self._add_extended_benchmarks()
        except Exception as e:
            logger.warning("KG: extended benchmarks failed: %s", e)

        try:
            self._add_onec_coa_accounts()
        except Exception as e:
            logger.warning("KG: 1C COA accounts failed: %s", e)

        try:
            self._add_onec_subkonto_dimensions()
        except Exception as e:
            logger.warning("KG: 1C subkonto dimensions failed: %s", e)

        self._is_built = True
        total = len(self._entities)
        logger.info("KnowledgeGraph built: %d entities", total)
        return total

    # -------------------------------------------------------------------------
    # 1. COA ENTITIES — from GEORGIAN_COA (134 entries)
    # -------------------------------------------------------------------------

    def _build_coa_entities(self) -> None:
        """Index all GEORGIAN_COA entries as account entities."""
        try:
            from app.services.file_parser import GEORGIAN_COA
        except ImportError:
            logger.warning("Could not import GEORGIAN_COA — skipping COA entities")
            return

        for code, entry in GEORGIAN_COA.items():
            label_en = entry.get("pl") or entry.get("bs") or f"Account {code}"
            label_ka = entry.get("pl_ka") or entry.get("bs_ka") or ""

            # Determine statement and side
            statement = "PL" if entry.get("pl") or entry.get("side") in ("income", "expense") else "BS"
            side = entry.get("side") or entry.get("bs_side") or ""
            pl_line = entry.get("pl_line", "")
            sub = entry.get("sub") or entry.get("bs_sub") or ""
            is_contra = entry.get("contra", False) or entry.get("contra_revenue", False)

            # Build description
            desc_parts = [f"Account code {code}"]
            desc_parts.append(f"Statement: {statement}")
            if side:
                desc_parts.append(f"Side: {side}")
            if pl_line:
                desc_parts.append(f"P&L line: {pl_line}")
            if sub:
                desc_parts.append(f"Sub-category: {sub}")
            if is_contra:
                desc_parts.append("(contra account)")
            if entry.get("segment"):
                desc_parts.append(f"Segment: {entry['segment']}")

            entity = KnowledgeEntity(
                entity_id=f"coa_{code}",
                entity_type="account",
                label_en=label_en,
                label_ka=label_ka,
                description=". ".join(desc_parts),
                properties={
                    "code": code,
                    "statement": statement,
                    "side": side,
                    "pl_line": pl_line,
                    "sub": sub,
                    "is_contra": is_contra,
                    "segment": entry.get("segment", ""),
                    "depth": len(code),
                },
            )
            self._add_entity(entity)
            self._index_by_code[code] = entity.entity_id

    # -------------------------------------------------------------------------
    # 2. CLASS RULES — ACCOUNT_CLASS_RULES, EXPENSE_SUBCLASS_RULES, etc.
    # -------------------------------------------------------------------------

    def _build_class_rules(self) -> None:
        """Index account classification rules."""
        from app.services.accounting_intelligence import (
            ACCOUNT_CLASS_RULES,
            EXPENSE_SUBCLASS_RULES,
            NON_OPERATING_SUBCLASS_RULES,
        )

        # Top-level class rules (1-9)
        for digit, rule in ACCOUNT_CLASS_RULES.items():
            entity = KnowledgeEntity(
                entity_id=f"class_rule_{digit}",
                entity_type="class_rule",
                label_en=f"Class {digit}: {rule['category']}",
                description=(
                    f"Account class {digit} represents {rule['category']} "
                    f"on the {rule['statement']} statement. "
                    f"Side: {rule['side']}."
                    + (f" P&L line: {rule['pl_line']}." if rule.get('pl_line') else "")
                ),
                properties={
                    "class_digit": digit,
                    "statement": rule["statement"],
                    "category": rule["category"],
                    "side": rule["side"],
                    "pl_line": rule.get("pl_line", ""),
                    "sub": rule.get("sub", ""),
                },
            )
            self._add_entity(entity)

        # Expense subclass rules (71-77)
        for prefix, rule in EXPENSE_SUBCLASS_RULES.items():
            entity = KnowledgeEntity(
                entity_id=f"expense_sub_{prefix}",
                entity_type="class_rule",
                label_en=f"Expense {prefix}: {rule['label']}",
                label_ka=rule.get("label_ka", ""),
                description=(
                    f"Expense subclass {prefix}: {rule['label']}. "
                    f"P&L line: {rule['pl_line']}."
                    + (f" Sub-category: {rule['sub']}." if rule.get("sub") else "")
                ),
                properties={
                    "prefix": prefix,
                    "pl_line": rule["pl_line"],
                    "sub": rule.get("sub", ""),
                    "side": rule.get("side", "expense"),
                },
            )
            self._add_entity(entity)

        # Non-operating subclass rules (82-84)
        for prefix, rule in NON_OPERATING_SUBCLASS_RULES.items():
            entity = KnowledgeEntity(
                entity_id=f"nonop_sub_{prefix}",
                entity_type="class_rule",
                label_en=f"Non-operating {prefix}: {rule['label']}",
                label_ka=rule.get("label_ka", ""),
                description=(
                    f"Non-operating subclass {prefix}: {rule['label']}. "
                    f"P&L line: {rule['pl_line']}."
                ),
                properties={
                    "prefix": prefix,
                    "pl_line": rule["pl_line"],
                },
            )
            self._add_entity(entity)

    # -------------------------------------------------------------------------
    # 3. KEY ACCOUNTS — special-meaning accounts
    # -------------------------------------------------------------------------

    def _build_key_accounts(self) -> None:
        """Index KEY_ACCOUNTS with their special meanings."""
        from app.services.accounting_intelligence import KEY_ACCOUNTS

        for code, info in KEY_ACCOUNTS.items():
            entity = KnowledgeEntity(
                entity_id=f"key_acct_{code}",
                entity_type="key_account",
                label_en=f"{code}: {info['label']}",
                label_ka=info.get("label_ka", ""),
                description=(
                    f"Key account {code} ({info['label']}). "
                    f"Flow: {info.get('flow', 'N/A')}."
                    + (" This is a contra account." if info.get("contra") else "")
                ),
                properties={
                    "code": code,
                    "flow": info.get("flow", ""),
                    "is_contra": info.get("contra", False),
                },
            )
            self._add_entity(entity)

    # -------------------------------------------------------------------------
    # 4. FINANCIAL FLOW EXPLANATIONS — from accounting_intelligence.py
    # -------------------------------------------------------------------------

    def _build_flow_explanations(self) -> None:
        """Index all financial flow explanations."""
        from app.services.accounting_intelligence import accounting_intelligence

        flow_types = [
            "inventory_to_cogs", "revenue_formation", "cogs_formation",
            "operating_expenses", "financial_burden", "working_capital",
            "bs_identity", "intercompany", "pl_waterfall",
            "balance_sheet_structure", "revenue_recognition",
            "opex_classification", "dashboard_kpis",
        ]

        for flow_type in flow_types:
            flow = accounting_intelligence.explain_financial_flow(flow_type)
            if "title" not in flow:
                continue

            # Build rich description from all flow fields
            desc_parts = [flow.get("description", "")]
            if flow.get("formula"):
                desc_parts.append(f"Formula: {flow['formula']}")
            if flow.get("journal_entry"):
                desc_parts.append(f"Journal entry: {flow['journal_entry']}")
            if flow.get("verification"):
                desc_parts.append(f"Verification: {flow['verification']}")
            if flow.get("key_metric"):
                desc_parts.append(f"Key metric: {flow['key_metric']}")
            if flow.get("key_metrics"):
                desc_parts.append("Key metrics: " + "; ".join(flow["key_metrics"]))

            # Extract related account codes
            accounts = flow.get("accounts", [])
            if flow.get("source_accounts"):
                accounts.extend(flow["source_accounts"])
            if flow.get("destination_accounts"):
                accounts.extend(flow["destination_accounts"])

            entity = KnowledgeEntity(
                entity_id=f"flow_{flow_type}",
                entity_type="flow",
                label_en=flow["title"],
                label_ka=flow.get("title_ka", ""),
                description=" ".join(desc_parts),
                properties={
                    "flow_type": flow_type,
                    "accounts": accounts,
                    "formula": flow.get("formula", ""),
                    "verification": flow.get("verification", ""),
                },
            )
            self._add_entity(entity)

    # -------------------------------------------------------------------------
    # 5. DOMAIN CONCEPTS — analytical frameworks and formulas
    # -------------------------------------------------------------------------

    def _build_domain_concepts(self) -> None:
        """Index high-level financial domain concepts."""
        concepts = [
            {
                "id": "concept_margin_waterfall",
                "label": "Margin Waterfall",
                "desc": (
                    "Revenue -> COGS -> Gross Margin -> G&A -> EBITDA -> D&A -> EBIT "
                    "-> Finance -> EBT -> Tax -> Net Profit. Each step shows value erosion "
                    "from revenue to bottom line."
                ),
            },
            {
                "id": "concept_dupont",
                "label": "DuPont Analysis",
                "desc": (
                    "ROE = Net Margin x Asset Turnover x Equity Multiplier. "
                    "Decomposes return on equity into profitability, efficiency, and leverage."
                ),
            },
            {
                "id": "concept_working_capital_cycle",
                "label": "Working Capital Cycle",
                "desc": (
                    "Cash-to-Cash Cycle = Days Inventory Outstanding + Days Sales Outstanding "
                    "- Days Payable Outstanding. Measures how long cash is tied up in operations."
                ),
            },
            {
                "id": "concept_negative_margin_strategy",
                "label": "Negative Margin Strategy",
                "desc": (
                    "Negative wholesale margins are a strategic market-share play. "
                    "Companies like NYX Core Thinker subsidize wholesale to maintain market dominance "
                    "while earning margins on retail. Cross-subsidy model."
                ),
            },
            {
                "id": "concept_fuel_seasonality",
                "label": "Fuel Seasonality Patterns",
                "desc": (
                    "Diesel peaks winter (heating demand). Petrol peaks summer (driving). "
                    "Bitumen peaks summer (road construction). CNG/LPG relatively stable. "
                    "These patterns affect revenue mix and margins by quarter."
                ),
            },
            {
                "id": "concept_georgian_gel",
                "label": "Georgian Lari (GEL) Currency",
                "desc": (
                    "Georgian Lari (GEL) is the base currency. Financial year = calendar year. "
                    "FX gains/losses appear in account 8220. VAT rate is 18%."
                ),
            },
            {
                "id": "concept_coa_hierarchy",
                "label": "Georgian 1C Chart of Accounts",
                "desc": (
                    "Georgian 1C COA hierarchy: "
                    "Class 1: Current Assets. Class 2: Noncurrent Assets. "
                    "Class 3: Current Liabilities. Class 4: Noncurrent Liabilities. "
                    "Class 5: Equity. Class 6: Revenue. "
                    "Class 7: Expenses (71=COGS, 72=Labour, 73=Selling, 74=Admin, 75=Finance, 77=Tax). "
                    "Class 8: Non-operating. Class 9: Other P&L."
                ),
            },
            {
                "id": "concept_nyx_overview",
                "label": settings.COMPANY_NAME,
                "desc": (
                    f"{settings.COMPANY_NAME} - fuel distribution company. "
                    "Two segments: Wholesale (Petrol, Diesel, Bitumen) and "
                    "Retail (Petrol, Diesel, CNG, LPG). "
                    "Revenue Breakdown and COGS Breakdown sheets are primary data sources."
                ),
            },
            {
                "id": "concept_cogs_formula",
                "label": "COGS Calculation Formula",
                "desc": (
                    "COGS = Col K (account 1610, purchase cost) + Col L (account 7310, "
                    "logistics/transport) + Col O (account 8230, customs/duties). "
                    "Total should reconcile with Trial Balance 71xx debit turnover."
                ),
            },
            {
                "id": "concept_revenue_recognition",
                "label": "Revenue Recognition",
                "desc": (
                    "Gross Revenue (account 6110 credit) minus Sales Returns (6120 debit) "
                    "minus VAT (18%) = Net Revenue. Revenue is classified by product "
                    "into Wholesale and Retail segments."
                ),
            },
            {
                "id": "concept_bs_identity",
                "label": "Balance Sheet Accounting Identity",
                "desc": (
                    "Assets (Classes 1+2) = Liabilities (Classes 3+4) + Equity (Class 5). "
                    "If they don't balance, check for unmapped accounts or missing trial "
                    "balance entries. Account 5330 holds retained earnings."
                ),
            },
            {
                "id": "concept_ga_structure",
                "label": "G&A Expense Account Codes",
                "desc": (
                    "G&A expense accounts: 7110=Salaries, 7150=Depreciation, 7210=Rent, "
                    "7310.01.1=Circulation, 7310.02.1=Production Commercial, "
                    "7430=Transport, 7450=Communications, 7480=Bank fees, 7510=Utilities, "
                    "8130=VAT, 8220.01.1=Non-operating, 9210=Other P&L."
                ),
            },
        ]

        for c in concepts:
            entity = KnowledgeEntity(
                entity_id=c["id"],
                entity_type="concept",
                label_en=c["label"],
                description=c["desc"],
            )
            self._add_entity(entity)

    # -------------------------------------------------------------------------
    # 6. RELATIONSHIPS — hierarchical and cross-references
    # -------------------------------------------------------------------------

    def _build_relationships(self) -> None:
        """Build relationships between entities."""
        # Parent-child for COA hierarchy
        codes = sorted(self._index_by_code.keys(), key=lambda c: (len(c), c))
        for code in codes:
            entity_id = self._index_by_code[code]
            entity = self._entities[entity_id]

            # Find parent: progressively shorter prefix
            for length in range(len(code) - 1, 0, -1):
                parent_code = code[:length]
                if parent_code in self._index_by_code:
                    parent_id = self._index_by_code[parent_code]
                    entity.relationships.append(KnowledgeRelation(
                        relation_type="child_of",
                        target_id=parent_id,
                        label=f"{code} is child of {parent_code}",
                    ))
                    # Add reverse
                    parent = self._entities[parent_id]
                    parent.relationships.append(KnowledgeRelation(
                        relation_type="parent_of",
                        target_id=entity_id,
                        label=f"{parent_code} is parent of {code}",
                    ))
                    break

            # Link COA accounts to class rules
            if code and code[0].isdigit():
                class_rule_id = f"class_rule_{code[0]}"
                if class_rule_id in self._entities:
                    entity.relationships.append(KnowledgeRelation(
                        relation_type="classified_by",
                        target_id=class_rule_id,
                        label=f"Account {code} belongs to class {code[0]}",
                    ))

        # Link flows to their accounts
        for eid, entity in self._entities.items():
            if entity.entity_type == "flow":
                accounts = entity.properties.get("accounts", [])
                for acct in accounts:
                    # Try exact match or pattern match (e.g., "71xx" -> "71")
                    clean = re.sub(r'[xX]+$', '', acct)  # "71xx" -> "71"
                    clean = re.sub(r'[^0-9]', '', clean)
                    if clean in self._index_by_code:
                        coa_id = self._index_by_code[clean]
                        entity.relationships.append(KnowledgeRelation(
                            relation_type="references_account",
                            target_id=coa_id,
                            label=f"Flow references account {clean}",
                        ))

        # Link key accounts to COA entries
        for eid, entity in self._entities.items():
            if entity.entity_type == "key_account":
                code = entity.properties.get("code", "")
                if code in self._index_by_code:
                    entity.relationships.append(KnowledgeRelation(
                        relation_type="same_as",
                        target_id=self._index_by_code[code],
                        label=f"Key account for COA {code}",
                    ))

    # -------------------------------------------------------------------------
    # 7. REGULATORY KNOWLEDGE — IFRS, Georgian tax, fuel benchmarks
    # -------------------------------------------------------------------------

    def _add_regulatory_knowledge(self) -> None:
        """Add IFRS standards and Georgian tax regulations to the knowledge graph."""

        # ── Georgian Tax Regulations ──────────────────────────────────────────
        georgian_tax_rules = [
            {
                "id": "tax_vat_georgia",
                "label_en": "Georgian VAT (Value Added Tax)",
                "label_ka": "დამატებული ღირებულების გადასახადი",
                "description": (
                    "Standard VAT rate in Georgia is 18%. "
                    "Applied to goods and services sold domestically. "
                    "VAT-registered businesses collect VAT and remit to Revenue Service. "
                    "Revenue should always be reported NET of VAT (exclude 18% VAT). "
                    "Account mapping: VAT liability → account 3310 (Tax Payable)."
                ),
                "properties": {
                    "rate": "18%",
                    "account": "3310",
                    "type": "indirect_tax",
                    "authority": "Georgian Revenue Service",
                },
            },
            {
                "id": "tax_income_georgia",
                "label_en": "Georgian Corporate Income Tax",
                "label_ka": "კორპორაციული საშემოსავლო გადასახადი",
                "description": (
                    "Estonian-model profit tax: 15% on distributed profits (dividends). "
                    "Retained earnings are NOT taxed until distributed. "
                    "Effective since 2017 reform. "
                    "Account mapping: tax expense → account 9110 (Income Tax Expense). "
                    "This means EBIT and EBT may be equal for retained earnings periods."
                ),
                "properties": {
                    "rate": "15% on distributed profits",
                    "model": "Estonian-model",
                    "account": "9110",
                    "type": "direct_tax",
                    "effective_year": "2017",
                },
            },
            {
                "id": "tax_withholding_georgia",
                "label_en": "Georgian Withholding Tax",
                "label_ka": "გადახდის წყაროსთან დაკავებული გადასახადი",
                "description": (
                    "5% withholding tax on dividends paid to resident individuals. "
                    "10% on dividends to non-residents. "
                    "Applied at distribution, not at profit recognition. "
                    "Account: deducted from dividend payments (account 3320)."
                ),
                "properties": {
                    "resident_rate": "5%",
                    "non_resident_rate": "10%",
                    "account": "3320",
                    "type": "withholding",
                },
            },
            {
                "id": "tax_excise_fuel",
                "label_en": "Georgian Fuel Excise Tax",
                "label_ka": "საწვავის აქციზი",
                "description": (
                    "Excise tax on petroleum products in Georgia. "
                    "Petrol (91, 95, 98): GEL 0.40 per liter as of 2024. "
                    "Diesel: GEL 0.34 per liter. "
                    "CNG/LPG: GEL 0.19 per cubic meter equivalent. "
                    "Paid by importer/producer, included in COGS for fuel distributors. "
                    "Critical for NYX Core Thinker margin calculations — high excise reduces apparent margin."
                ),
                "properties": {
                    "petrol_rate": "GEL 0.40/liter",
                    "diesel_rate": "GEL 0.34/liter",
                    "type": "excise",
                    "impact": "included_in_cogs",
                },
            },
        ]

        for rule in georgian_tax_rules:
            entity = KnowledgeEntity(
                entity_id=f"tax_{rule['id']}",
                entity_type="regulation",
                label_en=rule["label_en"],
                label_ka=rule["label_ka"],
                description=rule["description"],
                properties={**rule["properties"], "jurisdiction": "Georgia", "category": "tax"},
            )
            self._entities[entity.entity_id] = entity

        # ── IFRS Standards relevant to fuel distribution ──────────────────────
        ifrs_rules = [
            {
                "id": "ifrs15_revenue",
                "label_en": "IFRS 15 — Revenue from Contracts with Customers",
                "description": (
                    "Revenue is recognized when (or as) performance obligations are satisfied. "
                    "For fuel sales: recognize at point of delivery (transfer of control). "
                    "Wholesale: at moment of delivery to buyer's tank. "
                    "Retail: at point of sale to end customer. "
                    "Gross vs Net presentation: if acting as agent, show net; as principal, show gross. "
                    "NYX Core Thinker typically acts as principal → gross revenue recognition."
                ),
                "properties": {"standard": "IFRS 15", "topic": "revenue_recognition"},
            },
            {
                "id": "ias2_inventory",
                "label_en": "IAS 2 — Inventories",
                "description": (
                    "Inventories measured at lower of cost and net realizable value. "
                    "Cost formulas allowed: FIFO or Weighted Average (LIFO prohibited under IFRS). "
                    "For fuel: typically uses weighted average cost method. "
                    "Account: Inventory (account 1310) → at cost including import duties, excise, transport. "
                    "When sold: carrying amount transferred to COGS (account 6xxx). "
                    "Write-down to NRV if market price falls below cost."
                ),
                "properties": {"standard": "IAS 2", "topic": "inventory"},
            },
            {
                "id": "ias16_ppe",
                "label_en": "IAS 16 — Property, Plant and Equipment",
                "description": (
                    "PP&E carried at cost less accumulated depreciation and impairment. "
                    "Depreciation methods: straight-line (most common), reducing balance, units of production. "
                    "Fuel stations: typically 20-40 year useful life for buildings, 5-15 years for equipment. "
                    "Depreciation expense → account 8110 (Depreciation, Non-production assets). "
                    "CapEx (additions) → increases carrying value, NOT an expense. "
                    "Maintenance costs → expense in period incurred (account 7xxx or 8xxx). "
                    "Major overhauls meeting asset recognition criteria → capitalize."
                ),
                "properties": {"standard": "IAS 16", "topic": "fixed_assets"},
            },
            {
                "id": "ias36_impairment",
                "label_en": "IAS 36 — Impairment of Assets",
                "description": (
                    "Assets must not be carried above recoverable amount. "
                    "Recoverable amount = higher of Fair Value Less Costs of Disposal and Value in Use. "
                    "Test annually for intangibles and goodwill, when indicators exist for other assets. "
                    "Impairment loss: difference between carrying amount and recoverable amount. "
                    "Recognized in profit or loss (account 8200 - Impairment losses)."
                ),
                "properties": {"standard": "IAS 36", "topic": "impairment"},
            },
            {
                "id": "ias37_provisions",
                "label_en": "IAS 37 — Provisions, Contingent Liabilities and Assets",
                "description": (
                    "Provision recognized when: present obligation, probable outflow, reliable estimate. "
                    "Common fuel distributor provisions: environmental remediation, decommissioning of fuel stations. "
                    "Environmental provisions → account 3xxx (Long-term provisions). "
                    "Unwinding of discount on provisions → finance cost (account 9220)."
                ),
                "properties": {"standard": "IAS 37", "topic": "provisions"},
            },
        ]

        for rule in ifrs_rules:
            entity = KnowledgeEntity(
                entity_id=f"ifrs_{rule['id']}",
                entity_type="regulation",
                label_en=rule["label_en"],
                label_ka="",
                description=rule["description"],
                properties={**rule["properties"], "jurisdiction": "international"},
            )
            self._entities[entity.entity_id] = entity

        # ── Fuel Industry Benchmarks ─────────────────────────────────────────
        benchmarks = [
            {
                "id": "benchmark_wholesale_margin",
                "label_en": "Wholesale Fuel Distribution — Gross Margin Benchmark",
                "description": (
                    "Industry benchmark for wholesale petroleum distribution gross margin: 1-4%. "
                    "Negative wholesale margins (e.g., -2.3%) are common for large distributors "
                    "using wholesale as a loss-leader to maintain market share and throughput. "
                    "Cross-subsidized by higher retail margins (typically 8-15%). "
                    "NYX Core Thinker operates in this model: wholesale < 0%, retail > 0%."
                ),
                "properties": {
                    "typical_range": "1-4%",
                    "negative_acceptable": True,
                    "context": "loss_leader_strategy",
                },
            },
            {
                "id": "benchmark_retail_margin",
                "label_en": "Retail Fuel Distribution — Gross Margin Benchmark",
                "description": (
                    "Industry benchmark for retail fuel station gross margin: 8-15%. "
                    "Includes throughput revenue + non-fuel revenue (convenience store, services). "
                    "Premium fuels (98 octane, premium diesel) typically carry higher margins. "
                    "CNG/LPG margins vary significantly with infrastructure amortization. "
                    "A retail margin below 5% is concerning; below 0% requires investigation."
                ),
                "properties": {
                    "typical_range": "8-15%",
                    "warning_threshold": "5%",
                    "critical_threshold": "0%",
                },
            },
            {
                "id": "benchmark_cogs_revenue_ratio",
                "label_en": "COGS to Revenue Ratio — Fuel Distribution",
                "description": (
                    "For petroleum fuel distributors, COGS typically represents 85-98% of revenue. "
                    "A ratio above 100% means selling below cost (loss-making on core product). "
                    "COGS includes: product cost + excise tax + import duties + transport. "
                    "A sudden spike in COGS/Revenue ratio warrants investigation: "
                    "price increase not passed through, new cost category, data entry error."
                ),
                "properties": {
                    "normal_range": "85-98%",
                    "above_100_flag": "below_cost_selling",
                },
            },
        ]

        for b in benchmarks:
            entity = KnowledgeEntity(
                entity_id=f"benchmark_{b['id']}",
                entity_type="benchmark",
                label_en=b["label_en"],
                label_ka="",
                description=b["description"],
                properties=b["properties"],
            )
            self._entities[entity.entity_id] = entity

        count = len(georgian_tax_rules) + len(ifrs_rules) + len(benchmarks)
        logger.debug("KnowledgeGraph: added %d regulatory/benchmark entities", count)

    # =========================================================================
    # ADD DYNAMIC KNOWLEDGE
    # =========================================================================

    def add_dataset_pattern(
        self,
        dataset_id: int,
        period: str,
        pattern_type: str,
        description: str,
        properties: Optional[Dict] = None,
    ) -> str:
        """
        Add a historical dataset pattern to the knowledge graph.
        Called after upload/analysis to grow the knowledge base.

        Returns the entity_id of the new pattern.
        """
        entity_id = f"pattern_ds{dataset_id}_{pattern_type}"
        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type="pattern",
            label_en=f"Dataset {dataset_id} ({period}): {pattern_type}",
            description=description,
            properties={
                "dataset_id": dataset_id,
                "period": period,
                "pattern_type": pattern_type,
                **(properties or {}),
            },
        )
        self._add_entity(entity)
        return entity_id

    def add_user_correction(
        self,
        correction_id: int,
        content: str,
        importance: int = 7,
    ) -> str:
        """
        Add a user correction from AgentMemory to the knowledge graph.
        These improve future responses by remembering past mistakes.
        """
        entity_id = f"correction_{correction_id}"
        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type="correction",
            label_en=f"User correction #{correction_id}",
            description=content,
            properties={
                "memory_id": correction_id,
                "importance": importance,
            },
        )
        self._add_entity(entity)
        return entity_id

    # =========================================================================
    # QUERY
    # =========================================================================

    def query(
        self,
        query_text: str,
        entity_types: Optional[List[str]] = None,
        max_results: int = 10,
    ) -> List[KnowledgeEntity]:
        """
        Search the knowledge graph using keyword matching.
        For semantic search, use VectorStoreService which indexes
        these entities as documents.

        Args:
            query_text: Natural language query
            entity_types: Filter by entity type(s)
            max_results: Max entities to return

        Returns:
            List of matching KnowledgeEntity objects, scored by relevance.
        """
        if not self._is_built:
            self.build()

        query_lower = query_text.lower()
        tokens = set(re.findall(r'[\w\u10A0-\u10FF]+', query_lower))

        scored: List[Tuple[float, KnowledgeEntity]] = []

        for entity in self._entities.values():
            if entity_types and entity.entity_type not in entity_types:
                continue

            score = self._score_entity(entity, query_lower, tokens)
            if score > 0:
                scored.append((score, entity))

        scored.sort(key=lambda x: -x[0])
        return [entity for _, entity in scored[:max_results]]

    def get_context_for_account(self, account_code: str) -> Dict[str, Any]:
        """
        Get comprehensive context for an account code.
        Returns the account's classification, parent hierarchy,
        related flows, and key account info.
        """
        if not self._is_built:
            self.build()

        result: Dict[str, Any] = {
            "account_code": account_code,
            "classification": None,
            "hierarchy": [],
            "related_flows": [],
            "key_account_info": None,
        }

        # Find COA entity
        clean = re.sub(r'[^0-9]', '', str(account_code))
        found_entity = None

        # Try exact match first, then progressively shorter
        for length in range(len(clean), 0, -1):
            prefix = clean[:length]
            if prefix in self._index_by_code:
                found_entity = self._entities[self._index_by_code[prefix]]
                break

        if found_entity:
            result["classification"] = {
                "label_en": found_entity.label_en,
                "label_ka": found_entity.label_ka,
                **found_entity.properties,
            }

            # Build hierarchy (walk up parent relationships)
            hierarchy = [found_entity.label_en]
            current = found_entity
            for _ in range(5):  # Max depth 5
                parent_rel = next(
                    (r for r in current.relationships if r.relation_type == "child_of"),
                    None
                )
                if parent_rel and parent_rel.target_id in self._entities:
                    parent = self._entities[parent_rel.target_id]
                    hierarchy.append(parent.label_en)
                    current = parent
                else:
                    break
            result["hierarchy"] = list(reversed(hierarchy))

            # Find related flows
            for eid, entity in self._entities.items():
                if entity.entity_type == "flow":
                    accounts = entity.properties.get("accounts", [])
                    for acct in accounts:
                        acct_clean = re.sub(r'[xX]+$', '', acct)
                        acct_clean = re.sub(r'[^0-9]', '', acct_clean)
                        if clean.startswith(acct_clean) or acct_clean.startswith(clean):
                            result["related_flows"].append({
                                "flow_type": entity.properties.get("flow_type", ""),
                                "title": entity.label_en,
                                "formula": entity.properties.get("formula", ""),
                            })
                            break

        # Check key accounts
        key_id = f"key_acct_{clean}"
        if key_id in self._entities:
            ka = self._entities[key_id]
            result["key_account_info"] = {
                "label": ka.label_en,
                "label_ka": ka.label_ka,
                "flow": ka.properties.get("flow", ""),
            }

        return result

    def get_all_documents(self) -> List[Dict[str, str]]:
        """
        Export all entities as searchable documents for vector store indexing.
        Each document has: content, doc_type, rule_id.
        """
        if not self._is_built:
            self.build()

        documents = []
        for entity in self._entities.values():
            documents.append({
                "content": entity.to_document(),
                "doc_type": f"knowledge_{entity.entity_type}",
                "rule_id": entity.entity_id,
            })
        return documents

    def get_all_llamaindex_documents(self) -> List["Document"]:
        """
        Export all entities as LlamaIndex Document objects for advanced RAG.
        """
        try:
            from llama_index.core import Document
        except ImportError:
            logger.warning("LlamaIndex not available for document creation")
            return []

        if not self._is_built:
            self.build()

        documents = []
        for entity in self._entities.values():
            doc = Document(
                text=entity.to_document(),
                metadata={
                    "doc_type": f"knowledge_{entity.entity_type}",
                    "rule_id": entity.entity_id,
                    "entity_type": entity.entity_type,
                    "label_en": entity.label_en,
                    "label_ka": entity.label_ka,
                }
            )
            documents.append(doc)
        return documents

    def get_entity(self, entity_id: str) -> Optional[KnowledgeEntity]:
        """Get a specific entity by ID."""
        return self._entities.get(entity_id)

    def get_entities_by_type(self, entity_type: str) -> List[KnowledgeEntity]:
        """Get all entities of a given type."""
        ids = self._index_by_type.get(entity_type, [])
        return [self._entities[eid] for eid in ids if eid in self._entities]

    def status(self) -> Dict[str, Any]:
        """Return status summary of the knowledge graph."""
        type_counts = {t: len(ids) for t, ids in self._index_by_type.items()}
        return {
            "is_built": self._is_built,
            "total_entities": len(self._entities),
            "entities_by_type": type_counts,
            "total_relationships": sum(
                len(e.relationships) for e in self._entities.values()
            ),
        }

    # =========================================================================
    # KNOWLEDGE EXPANSION — Financial Ratios, Extended IFRS, Audit & Fraud Signals
    # =========================================================================

    def _add_financial_ratios(self) -> None:
        """Add 35 financial ratio entities with formulas, interpretations, and benchmarks."""
        ratios = [
            # ── Liquidity Ratios ──────────────────────────────────────────────
            ("ratio_current_ratio", "Current Ratio", "Liquidity",
             "Current Assets / Current Liabilities. Measures short-term solvency. "
             "Industry standard: >1.5 is healthy. <1.0 signals liquidity crisis. "
             "Petroleum distributors typically 1.1–1.8 due to high inventory. "
             "Formula: Current Assets ÷ Current Liabilities.",
             {"formula": "Current Assets / Current Liabilities", "benchmark_healthy": ">1.5",
              "benchmark_warning": "<1.0", "type": "liquidity"}),

            ("ratio_quick_ratio", "Quick Ratio (Acid Test)", "Liquidity",
             "Liquid assets excluding inventory / Current Liabilities. "
             "More conservative than Current Ratio — excludes illiquid inventory. "
             "Formula: (Cash + Short-term Investments + Receivables) ÷ Current Liabilities. "
             "Healthy: >1.0. Warning: <0.5 for fuel distributors (high inventory).",
             {"formula": "(Cash + Receivables) / Current Liabilities", "benchmark_healthy": ">1.0",
              "type": "liquidity"}),

            ("ratio_cash_ratio", "Cash Ratio", "Liquidity",
             "Cash and cash equivalents / Current Liabilities. "
             "Most conservative liquidity measure — only counts actual cash. "
             "Formula: Cash ÷ Current Liabilities. Typical range 0.1–0.5.",
             {"formula": "Cash / Current Liabilities", "type": "liquidity"}),

            ("ratio_working_capital", "Working Capital", "Liquidity",
             "Current Assets minus Current Liabilities. Absolute liquidity cushion in GEL. "
             "Positive WC = can meet short-term obligations. "
             "Fuel distributors need large WC due to bulk purchase requirements.",
             {"formula": "Current Assets - Current Liabilities", "type": "liquidity",
              "currency": "GEL"}),

            # ── Profitability Ratios ──────────────────────────────────────────
            ("ratio_gross_margin", "Gross Profit Margin", "Profitability",
             "Gross Profit / Net Revenue × 100. Primary profitability metric. "
             "Wholesale fuel: expected 1–4%. Retail fuel: 8–15%. "
             "Mixed distribution: 5–10% blended. Negative = margin compression. "
             "Formula: (Revenue - COGS) ÷ Revenue × 100.",
             {"formula": "(Revenue - COGS) / Revenue * 100", "wholesale_benchmark": "1-4%",
              "retail_benchmark": "8-15%", "type": "profitability"}),

            ("ratio_ebitda_margin", "EBITDA Margin", "Profitability",
             "EBITDA / Revenue × 100. Operational profitability before financing and tax. "
             "Industry benchmark for petroleum distribution: 2–6%. "
             "Formula: EBITDA ÷ Revenue × 100. Negative EBITDA is a serious warning.",
             {"formula": "EBITDA / Revenue * 100", "benchmark": "2-6%", "type": "profitability"}),

            ("ratio_net_margin", "Net Profit Margin", "Profitability",
             "Net Profit / Revenue × 100. Bottom-line profitability after all costs. "
             "Petroleum distribution: 0.5–3%. Thin margins are expected. "
             "Formula: Net Profit ÷ Revenue × 100.",
             {"formula": "Net Profit / Revenue * 100", "benchmark": "0.5-3%", "type": "profitability"}),

            ("ratio_roe", "Return on Equity (ROE)", "Profitability",
             "Net Profit / Shareholders Equity × 100. "
             "Measures returns generated for shareholders. "
             "Healthy for Georgia: >12%. Formula: Net Profit ÷ Equity × 100.",
             {"formula": "Net Profit / Equity * 100", "benchmark_healthy": ">12%", "type": "profitability"}),

            ("ratio_roa", "Return on Assets (ROA)", "Profitability",
             "Net Profit / Total Assets × 100. "
             "Efficiency of asset utilization. Industry standard: >5%. "
             "Formula: Net Profit ÷ Total Assets × 100.",
             {"formula": "Net Profit / Total Assets * 100", "benchmark_healthy": ">5%", "type": "profitability"}),

            ("ratio_roce", "Return on Capital Employed (ROCE)", "Profitability",
             "EBIT / Capital Employed × 100. Capital Employed = Total Assets - Current Liabilities. "
             "Measures efficiency of capital. Healthy: >10%. "
             "Formula: EBIT ÷ (Total Assets - Current Liabilities) × 100.",
             {"formula": "EBIT / (Total Assets - Current Liabilities) * 100",
              "benchmark_healthy": ">10%", "type": "profitability"}),

            # ── Solvency / Leverage Ratios ────────────────────────────────────
            ("ratio_debt_to_equity", "Debt-to-Equity Ratio", "Solvency",
             "Total Debt / Shareholders Equity. "
             "Measures financial leverage. Healthy: <2.0 for fuel distributors. "
             "High D/E (>3) signals excessive leverage and financial risk. "
             "Formula: Total Debt ÷ Shareholders Equity.",
             {"formula": "Total Debt / Equity", "benchmark_healthy": "<2.0",
              "benchmark_warning": ">3.0", "type": "solvency"}),

            ("ratio_debt_to_assets", "Debt-to-Assets Ratio", "Solvency",
             "Total Debt / Total Assets. What fraction of assets are debt-financed. "
             "Healthy: <0.5 (50%). Warning: >0.7. Formula: Total Debt ÷ Total Assets.",
             {"formula": "Total Debt / Total Assets", "benchmark_healthy": "<0.5",
              "benchmark_warning": ">0.7", "type": "solvency"}),

            ("ratio_interest_coverage", "Interest Coverage Ratio", "Solvency",
             "EBIT / Interest Expense. Ability to service debt from operations. "
             "Healthy: >3.0. Critical: <1.5 (struggling to cover interest). "
             "Formula: EBIT ÷ Finance Costs.",
             {"formula": "EBIT / Finance Expense", "benchmark_healthy": ">3.0",
              "benchmark_critical": "<1.5", "type": "solvency"}),

            ("ratio_equity_multiplier", "Equity Multiplier", "Solvency",
             "Total Assets / Shareholders Equity. Component of DuPont analysis. "
             "Higher multiplier = more leverage. Typical 1.5–3.0 for distributors. "
             "Formula: Total Assets ÷ Equity.",
             {"formula": "Total Assets / Equity", "type": "solvency"}),

            # ── Efficiency Ratios ─────────────────────────────────────────────
            ("ratio_inventory_turnover", "Inventory Turnover", "Efficiency",
             "COGS / Average Inventory. How quickly inventory is sold. "
             "Fuel distributors: 24–36x per year (biweekly to weekly cycles). "
             "Low turnover signals slow-moving stock or overstocking. "
             "Formula: COGS ÷ Average Inventory.",
             {"formula": "COGS / Average Inventory", "benchmark": "24-36x/year", "type": "efficiency"}),

            ("ratio_days_inventory", "Days Inventory Outstanding (DIO)", "Efficiency",
             "365 / Inventory Turnover. Days of inventory on hand. "
             "Fuel: 10–15 days is typical. >30 days signals issues. "
             "Formula: 365 ÷ (COGS ÷ Inventory).",
             {"formula": "365 / Inventory Turnover", "benchmark": "10-15 days", "type": "efficiency"}),

            ("ratio_receivables_turnover", "Accounts Receivable Turnover", "Efficiency",
             "Revenue / Average Accounts Receivable. "
             "How quickly customers pay. Wholesale fuel: 8–12x/year. "
             "Formula: Revenue ÷ Average Receivables.",
             {"formula": "Revenue / Average Receivables", "benchmark": "8-12x/year", "type": "efficiency"}),

            ("ratio_days_receivable", "Days Sales Outstanding (DSO)", "Efficiency",
             "365 / Receivables Turnover. Average collection period in days. "
             "Healthy: 30–45 days for wholesale fuel. >90 days is problematic. "
             "Formula: 365 ÷ (Revenue ÷ Receivables).",
             {"formula": "365 / (Revenue / Receivables)", "benchmark": "30-45 days", "type": "efficiency"}),

            ("ratio_payables_turnover", "Accounts Payable Turnover", "Efficiency",
             "COGS / Average Accounts Payable. How quickly company pays suppliers. "
             "Low turnover = slower payment (better for cash flow, riskier for credit). "
             "Formula: COGS ÷ Average Payables.",
             {"formula": "COGS / Average Payables", "type": "efficiency"}),

            ("ratio_days_payable", "Days Payable Outstanding (DPO)", "Efficiency",
             "365 / Payables Turnover. Average payment period to suppliers. "
             "Typical 30–60 days. High DPO (>90 days) may indicate cash flow stress. "
             "Formula: 365 ÷ (COGS ÷ Payables).",
             {"formula": "365 / (COGS / Payables)", "benchmark": "30-60 days", "type": "efficiency"}),

            ("ratio_asset_turnover", "Asset Turnover Ratio", "Efficiency",
             "Revenue / Total Assets. Revenue generated per GEL of assets. "
             "Fuel distributors: 2–4x (high-volume, low-margin business). "
             "Formula: Revenue ÷ Total Assets.",
             {"formula": "Revenue / Total Assets", "benchmark": "2-4x", "type": "efficiency"}),

            ("ratio_ccc", "Cash Conversion Cycle (CCC)", "Efficiency",
             "DIO + DSO - DPO. Full working capital cycle in days. "
             "Shorter is better — negative CCC means company uses supplier credit. "
             "Formula: Days Inventory + Days Receivable - Days Payable.",
             {"formula": "DIO + DSO - DPO", "type": "efficiency"}),

            # ── DuPont Analysis ───────────────────────────────────────────────
            ("ratio_dupont", "DuPont Analysis", "Profitability",
             "Decomposition of ROE into 3 drivers: Net Margin × Asset Turnover × Equity Multiplier. "
             "Reveals whether ROE comes from profitability, efficiency, or leverage. "
             "Formula: (Net Profit/Revenue) × (Revenue/Assets) × (Assets/Equity).",
             {"formula": "Net Margin × Asset Turnover × Equity Multiplier", "type": "profitability",
              "components": "margin|efficiency|leverage"}),

            # ── Valuation Ratios ──────────────────────────────────────────────
            ("ratio_ev_ebitda", "EV/EBITDA Multiple", "Valuation",
             "Enterprise Value / EBITDA. Common acquisition valuation metric. "
             "Petroleum distribution: 4–8x is typical. >10x is expensive. "
             "EV = Market Cap + Debt - Cash.",
             {"formula": "Enterprise Value / EBITDA", "benchmark": "4-8x", "type": "valuation"}),

            ("ratio_pe", "Price-to-Earnings (P/E) Ratio", "Valuation",
             "Share Price / Earnings Per Share. Market valuation of earnings. "
             "Fuel distribution sector: P/E typically 6–12x due to thin margins. "
             "Formula: Market Price ÷ EPS.",
             {"formula": "Price / EPS", "benchmark": "6-12x", "type": "valuation"}),

            # ── Capital Structure ─────────────────────────────────────────────
            ("ratio_capex_ratio", "CapEx to Revenue Ratio", "Efficiency",
             "Capital Expenditure / Revenue × 100. Investment intensity. "
             "Fuel distributors: 1–3% (tank farms, delivery vehicles). "
             "Formula: CapEx ÷ Revenue × 100.",
             {"formula": "CapEx / Revenue * 100", "benchmark": "1-3%", "type": "efficiency"}),

            ("ratio_free_cash_flow", "Free Cash Flow (FCF)", "Cash Flow",
             "Operating Cash Flow minus Capital Expenditures. "
             "Cash available after sustaining operations. Key health indicator. "
             "Formula: Operating CF - CapEx.",
             {"formula": "Operating CF - CapEx", "type": "cash_flow"}),

            ("ratio_fcf_margin", "Free Cash Flow Margin", "Cash Flow",
             "Free Cash Flow / Revenue × 100. FCF as % of revenue. "
             "Healthy fuel distributor: 1–5%. "
             "Formula: FCF ÷ Revenue × 100.",
             {"formula": "FCF / Revenue * 100", "benchmark": "1-5%", "type": "cash_flow"}),

            # ── Debt Service ──────────────────────────────────────────────────
            ("ratio_dscr", "Debt Service Coverage Ratio (DSCR)", "Solvency",
             "EBITDA / (Principal + Interest). Ability to service all debt. "
             "Lenders require DSCR > 1.25 for petroleum distributors. "
             "<1.0 means cannot service debt from operations. "
             "Formula: EBITDA ÷ (Annual Principal + Annual Interest).",
             {"formula": "EBITDA / Debt Service", "benchmark_lender": ">1.25",
              "benchmark_critical": "<1.0", "type": "solvency"}),

            # ── Operating Efficiency ──────────────────────────────────────────
            ("ratio_opex_ratio", "Operating Expense Ratio", "Efficiency",
             "Operating Expenses (G&A + D&A) / Revenue × 100. "
             "Overhead burden as % of revenue. Target for distributors: <5%. "
             "Formula: Operating Expenses ÷ Revenue × 100.",
             {"formula": "OpEx / Revenue * 100", "benchmark": "<5%", "type": "efficiency"}),

            ("ratio_cogs_ratio", "COGS to Revenue Ratio", "Profitability",
             "Cost of Goods Sold / Revenue × 100. Cost intensity. "
             "Petroleum distribution: 85–98% typical (thin margins). "
             "If COGS > Revenue (>100%), wholesale margin is negative. "
             "Formula: COGS ÷ Revenue × 100.",
             {"formula": "COGS / Revenue * 100", "benchmark": "85-98%",
              "wholesale_warning": ">100%", "type": "profitability"}),

            ("ratio_ga_ratio", "G&A to Revenue Ratio", "Efficiency",
             "General and Administrative Expenses / Revenue × 100. "
             "Administrative overhead burden. Target: <3% for fuel distributors. "
             "Formula: G&A ÷ Revenue × 100.",
             {"formula": "G&A / Revenue * 100", "benchmark": "<3%", "type": "efficiency"}),

            ("ratio_wholesale_margin", "Wholesale Fuel Margin", "Profitability",
             "Wholesale Revenue minus Wholesale COGS, divided by Wholesale Revenue. "
             "Expected range: 1–4%. Can be NEGATIVE (loss-leader strategy). "
             "Negative wholesale margin is acceptable if retail/other compensates. "
             "Formula: (Wholesale Revenue - Wholesale COGS) ÷ Wholesale Revenue × 100.",
             {"formula": "(WS Revenue - WS COGS) / WS Revenue * 100",
              "benchmark": "1-4%", "negative_acceptable": True, "type": "profitability"}),

            ("ratio_retail_margin", "Retail Fuel Margin", "Profitability",
             "Retail Revenue minus Retail COGS, divided by Retail Revenue. "
             "Expected range: 8–15%. Retail margins subsidize wholesale losses. "
             "Formula: (Retail Revenue - Retail COGS) ÷ Retail Revenue × 100.",
             {"formula": "(Retail Revenue - Retail COGS) / Retail Revenue * 100",
              "benchmark": "8-15%", "type": "profitability"}),
        ]

        for eid, label, category, desc, props in ratios:
            entity = KnowledgeEntity(
                entity_id=f"ratio_{eid}",
                entity_type="ratio",
                label_en=label,
                label_ka="",
                description=desc,
                properties={**props, "category": category, "source": "financial_ratios"},
            )
            self._add_entity(entity)

    def _add_extended_ifrs(self) -> None:
        """Add 15 additional IFRS/IAS standards beyond the 5 already in _add_regulatory_knowledge."""
        ifrs_extra = [
            ("ias7_cash_flow", "IAS 7 — Statement of Cash Flows",
             "Requires presentation of cash flows from operating, investing, financing activities. "
             "Operating: receipts from customers, payments to suppliers. "
             "Investing: purchase/sale of PP&E, investments. "
             "Financing: borrowings, dividends, share issuance. "
             "Two methods: Direct (preferred) or Indirect (starting from net profit). "
             "Fuel distributors: high operating CF from sales, investing CF for tank farms.",
             {"standard": "IAS 7", "topic": "cash_flows", "method_preferred": "direct"}),

            ("ias12_income_tax", "IAS 12 — Income Taxes",
             "Accounting for current and deferred income taxes. "
             "Deferred tax arises from temporary differences between accounting and tax bases. "
             "Georgia uses Estonian model — no deferred tax on undistributed profits. "
             "Current tax liability: recognized when profit is distributed.",
             {"standard": "IAS 12", "topic": "income_tax",
              "georgia_note": "Estonian model simplifies deferred tax"}),

            ("ias21_fx", "IAS 21 — Effects of Changes in Foreign Exchange Rates",
             "Translation of foreign currency transactions and financial statements. "
             "Monetary items (cash, receivables, payables) translated at closing rate. "
             "Non-monetary items at historical rate. "
             "FX differences on monetary items go to P&L (finance income/expense). "
             "Petroleum imports: high FX exposure (USD-denominated crude, GEL sales).",
             {"standard": "IAS 21", "topic": "foreign_exchange",
              "relevant_accounts": "finance_income_expense"}),

            ("ias23_borrowing", "IAS 23 — Borrowing Costs",
             "Borrowing costs directly attributable to qualifying assets must be capitalized. "
             "Qualifying assets: assets taking substantial time to prepare for use. "
             "For fuel distributors: large tank farm construction qualifies. "
             "Other borrowing costs expensed as finance costs (account 8410).",
             {"standard": "IAS 23", "topic": "borrowing_costs", "account": "8410"}),

            ("ias24_related_party", "IAS 24 — Related Party Disclosures",
             "Requires disclosure of related party relationships and transactions. "
             "Related parties: parent, subsidiaries, associates, key management, their families. "
             "Transactions: sales, purchases, loans, guarantees, management fees. "
             "Critical for Georgian holding structures with complex intercompany flows.",
             {"standard": "IAS 24", "topic": "related_party",
              "risk": "transfer_pricing"}),

            ("ias32_financial_instruments_pres", "IAS 32 — Financial Instruments: Presentation",
             "Classification of financial instruments as equity or liability. "
             "Compound instruments (e.g. convertible bonds) split into debt and equity components. "
             "Offsetting financial assets and liabilities: only allowed when legally enforceable right and intention to net settle.",
             {"standard": "IAS 32", "topic": "financial_instruments"}),

            ("ifrs9_financial_instruments", "IFRS 9 — Financial Instruments",
             "Classification and measurement of financial assets: amortized cost, FVOCI, FVTPL. "
             "Expected Credit Loss (ECL) model for impairment (replaces incurred loss). "
             "Hedge accounting: fair value, cash flow, and net investment hedges. "
             "Fuel distributors: receivables measured at amortized cost; ECL provision needed.",
             {"standard": "IFRS 9", "topic": "financial_instruments",
              "impairment_model": "ECL", "accounts": "receivables_provision"}),

            ("ifrs16_leases", "IFRS 16 — Leases",
             "Lessees recognize right-of-use asset and lease liability for all leases >12 months. "
             "Eliminates off-balance-sheet leases (old IAS 17 operating leases). "
             "Right-of-use asset: depreciated over lease term (account 1600s). "
             "Lease liability: discounted future payments (account 3400s, 4400s). "
             "Critical for fuel distributors with leased petrol stations and tank farms.",
             {"standard": "IFRS 16", "topic": "leases",
              "rou_asset_account": "1610", "liability_account": "3420"}),

            ("ifrs13_fair_value", "IFRS 13 — Fair Value Measurement",
             "Defines fair value and establishes hierarchy: Level 1 (quoted prices), "
             "Level 2 (observable inputs), Level 3 (unobservable). "
             "Applies whenever another standard requires/permits fair value measurement. "
             "Petroleum assets: Level 2 often used (commodity prices as inputs).",
             {"standard": "IFRS 13", "topic": "fair_value",
              "hierarchy": "Level1_quoted|Level2_observable|Level3_unobservable"}),

            ("ifrs3_business_combinations", "IFRS 3 — Business Combinations",
             "Acquisition method: acquirer recognized at fair value of consideration + identifiable assets/liabilities. "
             "Goodwill = consideration paid minus net identifiable assets at fair value. "
             "No amortization of goodwill — tested annually for impairment (IAS 36). "
             "Georgian M&A: fair value of fuel infrastructure often exceeds book value.",
             {"standard": "IFRS 3", "topic": "business_combinations",
              "goodwill_treatment": "no_amortization_impairment_test"}),

            ("ifrs5_non_current_assets", "IFRS 5 — Non-current Assets Held for Sale",
             "Assets classified as held for sale when: available for immediate sale and sale is highly probable within 12 months. "
             "Measured at lower of carrying amount and fair value less costs to sell. "
             "NOT depreciated once classified as held for sale. "
             "Presented separately in balance sheet.",
             {"standard": "IFRS 5", "topic": "held_for_sale",
              "treatment": "stop_depreciation_lower_of_cost_or_fv"}),

            ("ias38_intangibles", "IAS 38 — Intangible Assets",
             "Recognition criteria: identifiable, controlled by entity, future economic benefits. "
             "Internally generated: R&D. Research phase: expense. Development phase: capitalize if criteria met. "
             "Purchased intangibles: recognize at cost. "
             "Fuel distributors: software, licenses, brand rights capitalized here (account 1720).",
             {"standard": "IAS 38", "topic": "intangibles",
              "account": "1720", "treatment": "capitalize_if_criteria_met"}),

            ("ias10_events_after", "IAS 10 — Events After the Reporting Period",
             "Adjusting events: provide evidence of conditions at reporting date → adjust financials. "
             "Non-adjusting events: new conditions after period → disclose only. "
             "Fuel price spikes after period end: non-adjusting. "
             "Court settlement for pre-period liability: adjusting.",
             {"standard": "IAS 10", "topic": "subsequent_events",
              "adjusting": "conditions_at_reporting_date",
              "non_adjusting": "new_post_period_conditions"}),

            ("ias34_interim", "IAS 34 — Interim Financial Reporting",
             "Minimum components: condensed BS, P&L, OCI, CF, changes in equity + notes. "
             "Same accounting policies as annual. "
             "Seasonal businesses: disclose seasonality. "
             "Fuel distributors: Q1 lower (winter), Q3 higher (summer driving season).",
             {"standard": "IAS 34", "topic": "interim_reporting",
              "seasonality_note": "Q1_lower_Q3_higher"}),

            ("ifrs7_financial_instruments_disc", "IFRS 7 — Financial Instruments: Disclosures",
             "Quantitative and qualitative disclosures about risk exposure. "
             "Credit risk: maximum exposure, concentration, collateral. "
             "Liquidity risk: maturity analysis of financial liabilities. "
             "Market risk: sensitivity analysis (FX, interest rate, commodity price). "
             "Key for fuel distributors: commodity price and FX risk disclosure.",
             {"standard": "IFRS 7", "topic": "risk_disclosures",
              "risks": "credit|liquidity|market|fx|commodity"}),
        ]

        for eid, label, desc, props in ifrs_extra:
            entity = KnowledgeEntity(
                entity_id=f"ifrs_{eid}",
                entity_type="ifrs_standard",
                label_en=label,
                label_ka="",
                description=desc,
                properties={**props, "source": "ifrs_standards"},
            )
            self._add_entity(entity)

    def _add_audit_signals(self) -> None:
        """Add 22 audit red-flag entities — patterns that trigger auditor scrutiny."""
        signals = [
            ("aud_revenue_spike", "Unusual Revenue Spike",
             "Revenue increase >50% MoM without corresponding volume explanation. "
             "May indicate: fictitious revenues, round-tripping, channel stuffing. "
             "Audit test: reconcile to delivery receipts, customer contracts, bank deposits. "
             "Z-score trigger: >2.5 standard deviations above mean.",
             {"severity": "high", "area": "revenue", "z_threshold": 2.5}),

            ("aud_cogs_drop", "COGS Drop Without Revenue Change",
             "COGS decreases significantly while revenue stays flat or grows. "
             "May indicate: deferred cost capitalization, understated inventory consumption, fraud. "
             "Expected: COGS and revenue should move together for fuel distribution.",
             {"severity": "high", "area": "cogs"}),

            ("aud_margin_inconsistency", "Gross Margin Inconsistency",
             "Gross margin varies dramatically between periods without price/mix explanation. "
             "Fuel margins should be relatively stable quarter-to-quarter. "
             "±5 percentage point swing requires explanation.",
             {"severity": "medium", "area": "margin", "threshold": "5pp_swing"}),

            ("aud_round_numbers", "Unusual Round Numbers in Financials",
             "Multiple line items ending in 000 or 0000 (e.g., exactly 500,000.00). "
             "Legitimate transactions rarely produce perfectly round numbers. "
             "Indicator of manual journal entries or estimates that require scrutiny.",
             {"severity": "low", "area": "general", "pattern": "round_numbers"}),

            ("aud_last_day_entries", "Last-Day Journal Entries",
             "Significant journal entries posted on last day of period (month/quarter/year end). "
             "Legitimate: accruals, depreciation. Suspicious: revenue recognition, contra entries. "
             "Audit focus: entries reversing in subsequent period.",
             {"severity": "medium", "area": "journal_entries", "timing": "period_end"}),

            ("aud_related_party_volume", "High Related Party Transaction Volume",
             "Intercompany transactions exceeding 30% of total revenue. "
             "May indicate: transfer pricing manipulation, circular transactions, consolidation issues. "
             "Requires arm's length pricing documentation.",
             {"severity": "high", "area": "related_party", "threshold": "30%_of_revenue"}),

            ("aud_receivables_growth", "Receivables Growing Faster Than Revenue",
             "Accounts receivable growth rate consistently exceeds revenue growth rate. "
             "May indicate: fictitious sales, relaxed credit terms, collection problems. "
             "Formula: (AR growth % - Revenue growth %) > 15pp for 2+ periods is a red flag.",
             {"severity": "high", "area": "receivables", "formula": "AR_growth - Revenue_growth"}),

            ("aud_inventory_discrepancy", "Inventory Count Discrepancy",
             "Physical count differs from book value by >2% for fuel inventory. "
             "For liquid fuel: evaporation loss expected <0.3%. "
             "Larger discrepancy: theft, measurement error, or book fraud. "
             "Requires written-off inventory journal.",
             {"severity": "high", "area": "inventory", "acceptable_loss": "<0.3%_fuel"}),

            ("aud_cash_timing", "Cash Flow vs Profit Timing Mismatch",
             "Net profit growing strongly but operating cash flow declining or negative. "
             "Sustainable businesses should convert profit to cash. "
             "Persistent divergence (>3 periods) suggests earnings quality issues.",
             {"severity": "high", "area": "cash_flow",
              "pattern": "profit_up_cashflow_down"}),

            ("aud_auditor_change", "Frequent Auditor Changes",
             "Changing external auditors every 1–2 years. "
             "May indicate: disagreements with auditor on accounting treatments, 'opinion shopping'. "
             "Continuity of auditor is a quality signal.",
             {"severity": "medium", "area": "governance"}),

            ("aud_going_concern", "Going Concern Indicators",
             "Warning signs: negative working capital, loan covenant breaches, operating losses >3 periods, "
             "inability to refinance maturing debt, supplier payment delays >90 days. "
             "Auditor requires management representation on ability to continue as going concern.",
             {"severity": "critical", "area": "solvency",
              "triggers": "negative_WC|loss_3periods|covenant_breach"}),

            ("aud_depreciation_change", "Depreciation Rate Change",
             "Sudden change in useful life estimates (extending lives to reduce expense). "
             "Example: extending vehicle fleet from 5 to 8 years reduces annual D&A. "
             "Legitimate if supported by technical assessment. Questionable if coincides with profit pressure.",
             {"severity": "medium", "area": "ppe", "test": "compare_to_industry_norms"}),

            ("aud_provision_release", "Provision Release Pattern",
             "Releasing provisions into income to boost profit. "
             "Legitimate: resolution of contingency. Suspicious: releases consistently occur at profit targets. "
             "Doubtful debts: provision should track receivables aging, not profit targets.",
             {"severity": "high", "area": "provisions",
              "pattern": "release_coincides_with_profit_targets"}),

            ("aud_interperiod_shift", "Interperiod Revenue/Cost Shifting",
             "Revenue pulled forward from future periods or costs pushed to future periods. "
             "Example: billing Q4 sales in Q3 to meet annual target. "
             "Test: compare delivery receipts dates to invoice dates.",
             {"severity": "high", "area": "revenue",
              "test": "delivery_date_vs_invoice_date"}),

            ("aud_bank_reconciliation", "Bank Reconciliation Gaps",
             "Unreconciled items in bank reconciliation >30 days old. "
             "Outstanding deposits in transit >5 days for local Georgian banks. "
             "Unidentified credits or debits require investigation.",
             {"severity": "medium", "area": "cash",
              "threshold": "30_days_unreconciled"}),

            ("aud_pa_ratio", "Payables Ageing Concentration",
             "More than 60% of payables in >90 day bucket. "
             "Indicates: cash flow stress, disputes with suppliers, or payment fraud. "
             "Fuel importers: NYX Core Thinker/Rosneft terms typically 30–45 days.",
             {"severity": "high", "area": "payables",
              "fuel_supplier_terms": "30-45 days"}),

            ("aud_loan_terms", "Unusual Loan Terms",
             "Interest-free or below-market loans to directors or related parties. "
             "Required disclosures under IAS 24. Market rate must be imputed as deemed dividend. "
             "Georgian Revenue Service scrutinizes these transactions.",
             {"severity": "high", "area": "related_party",
              "accounting": "impute_market_rate"}),

            ("aud_cogs_classification", "COGS vs Operating Expense Reclassification",
             "Reclassifying items between COGS and operating expenses to improve gross margin. "
             "Example: moving distribution costs from COGS to G&A. "
             "Should reflect economic substance. Test: consistency period-to-period.",
             {"severity": "medium", "area": "classification"}),

            ("aud_fx_translation", "FX Translation Inconsistency",
             "Using different exchange rates for similar transactions. "
             "IAS 21 requires transaction-date rate for recognition, closing rate for monetary items. "
             "Inconsistent rates on NYX Core Thinker GEL/USD fuel invoices: red flag.",
             {"severity": "medium", "area": "fx", "standard": "IAS 21"}),

            ("aud_negative_goodwill", "Negative Goodwill / Bargain Purchase",
             "Acquisition where consideration < net fair value of identifiable assets. "
             "Rare and suspicious: may indicate: overstated target assets, understated consideration. "
             "Under IFRS 3: recognize immediately in P&L with disclosure.",
             {"severity": "medium", "area": "consolidation", "standard": "IFRS 3"}),

            ("aud_revenue_recognition_timing", "Revenue Recognition Timing Issues",
             "Recognizing revenue before performance obligations satisfied (IFRS 15). "
             "Fuel: revenue at delivery point transfer. Bill-and-hold: complex criteria. "
             "Advance payments (contract liabilities) must remain on balance sheet until delivery.",
             {"severity": "high", "area": "revenue", "standard": "IFRS 15"}),

            ("aud_impairment_avoidance", "Impairment Avoidance on Underperforming Assets",
             "Assets showing indicators of impairment (declining revenue, market downturn) "
             "but no impairment test performed (IAS 36). "
             "Triggers: significant market value decline, obsolescence, adverse changes in use. "
             "Management must document rationale for no impairment.",
             {"severity": "high", "area": "ppe_impairment", "standard": "IAS 36"}),
        ]

        for eid, label, desc, props in signals:
            entity = KnowledgeEntity(
                entity_id=f"audit_{eid}",
                entity_type="audit_signal",
                label_en=label,
                label_ka="",
                description=desc,
                properties={**props, "source": "audit_methodology"},
            )
            self._add_entity(entity)

    def _add_fraud_signals(self) -> None:
        """Add 18 fraud detection signals including Beneish M-Score components."""
        signals = [
            # ── Beneish M-Score Components ────────────────────────────────────
            ("fraud_dsri", "Beneish DSRI — Days Sales Receivable Index",
             "Beneish M-Score component: (DSO_t / DSO_{t-1}). "
             "DSRI > 1.465 is a fraud indicator (receivables growing faster than revenue). "
             "Suggests revenue recorded without cash collection = fictitious sales. "
             "Formula: (Receivables_t/Revenue_t) / (Receivables_{t-1}/Revenue_{t-1}).",
             {"beneish_component": True, "threshold": ">1.465",
              "interpretation": "receivables_inflation"}),

            ("fraud_gmi", "Beneish GMI — Gross Margin Index",
             "Beneish M-Score component: Gross_Margin_{t-1} / Gross_Margin_t. "
             "GMI > 1.193 indicates deteriorating gross margins. "
             "Declining margins create pressure to manipulate earnings. "
             "Formula: (Revenue_{t-1}-COGS_{t-1})/Revenue_{t-1} / (Revenue_t-COGS_t)/Revenue_t.",
             {"beneish_component": True, "threshold": ">1.193",
              "interpretation": "margin_deterioration_pressure"}),

            ("fraud_aqi", "Beneish AQI — Asset Quality Index",
             "Beneish M-Score component: (1 - (CA+PP&E)/TA)_t / (1 - (CA+PP&E)/TA)_{t-1}. "
             "AQI > 1.254 signals declining asset quality (growing intangibles/deferred costs). "
             "May indicate: capitalizing costs that should be expensed. "
             "Formula: Non-current non-PP&E assets as % of total.",
             {"beneish_component": True, "threshold": ">1.254",
              "interpretation": "expense_capitalization"}),

            ("fraud_sgi", "Beneish SGI — Sales Growth Index",
             "Beneish M-Score component: Revenue_t / Revenue_{t-1}. "
             "SGI > 1.607 means rapid growth that may not be sustainable. "
             "High growth companies face pressure to maintain trajectory. "
             "Fraud risk increases in high-growth environments.",
             {"beneish_component": True, "threshold": ">1.607",
              "interpretation": "growth_pressure_fraud_risk"}),

            ("fraud_depi", "Beneish DEPI — Depreciation Index",
             "Beneish M-Score component: (Depreciation_{t-1}/(PPE_{t-1}+Dep_{t-1})) / (Depreciation_t/(PPE_t+Dep_t)). "
             "DEPI > 1.0 signals slowing depreciation relative to asset base. "
             "May indicate: useful life extension to reduce expense and inflate earnings.",
             {"beneish_component": True, "threshold": ">1.0",
              "interpretation": "depreciation_manipulation"}),

            ("fraud_sgai", "Beneish SGAI — SG&A Expense Index",
             "Beneish M-Score component: (SGA_t/Revenue_t) / (SGA_{t-1}/Revenue_{t-1}). "
             "SGAI > 1.041 signals disproportionate SG&A growth. "
             "May indicate: aggressive capitalization elsewhere to mask true cost structure.",
             {"beneish_component": True, "threshold": ">1.041",
              "interpretation": "sga_inflation"}),

            ("fraud_lvgi", "Beneish LVGI — Leverage Index",
             "Beneish M-Score component: ((LTD+CL)/TA)_t / ((LTD+CL)/TA)_{t-1}. "
             "LVGI > 1.0 signals increasing leverage. "
             "Higher leverage → more covenant pressure → more motivation to manipulate.",
             {"beneish_component": True, "threshold": ">1.0",
              "interpretation": "leverage_and_covenant_pressure"}),

            ("fraud_tata", "Beneish TATA — Total Accruals to Total Assets",
             "Beneish M-Score component: (Net Profit - Operating CF) / Total Assets. "
             "TATA > 0.031 signals high accruals relative to cash earnings. "
             "High accruals = earnings not backed by cash = lower quality. "
             "Formula: (Net Income - Operating Cash Flow) ÷ Total Assets.",
             {"beneish_component": True, "threshold": ">0.031",
              "interpretation": "accrual_quality",
              "formula": "(Net Income - OCF) / Total Assets"}),

            ("fraud_mscore", "Beneish M-Score (Combined)",
             "8-variable model predicting financial statement manipulation. "
             "M = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + "
             "0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI. "
             "M > -1.78: high probability of manipulation. "
             "M < -2.22: likely non-manipulator. Between: gray zone.",
             {"model": "Beneish_1999", "threshold_manipulator": ">-1.78",
              "threshold_clean": "<-2.22", "interpretation": "manipulation_probability"}),

            # ── Petroleum-Specific Fraud Signals ─────────────────────────────
            ("fraud_fuel_volume_mismatch", "Fuel Volume vs Revenue Mismatch",
             "Revenue per liter calculation inconsistent with declared volume and price. "
             "Test: Reported_Revenue ≠ Volume × Price → potential theft or underreporting. "
             "Common in fuel: skimming from meter readings, phantom deliveries.",
             {"severity": "high", "area": "fuel_specific",
              "test": "revenue = volume × price"}),

            ("fraud_phantom_purchase", "Phantom Purchase Invoice",
             "COGS entries without matching delivery receipts, supplier invoices, or bank payments. "
             "Creates false COGS to inflate expenses (tax fraud) or understate inventory. "
             "Test: COGS journal → supplier invoice → delivery note → bank payment all match.",
             {"severity": "critical", "area": "cogs",
              "test": "4_way_match"}),

            ("fraud_skimming", "Cash Skimming at Petrol Stations",
             "Cash sales collected but not recorded in books. "
             "Indicators: cash receipts consistently below industry average per liter. "
             "Comparison: card vs cash ratio anomaly. "
             "Test: POS system records vs accounting records.",
             {"severity": "high", "area": "revenue",
              "indicator": "card_vs_cash_ratio_anomaly"}),

            ("fraud_inventory_theft", "Fuel Inventory Theft",
             "Physical fuel missing beyond normal evaporation loss (>0.3%). "
             "Meter calibration issues, driver diversion, improper tank measurements. "
             "Test: reconcile opening stock + purchases - sales = closing physical count.",
             {"severity": "high", "area": "inventory",
              "normal_loss": "<0.3%_by_volume"}),

            ("fraud_kickback_payable", "Kickback via Inflated Payables",
             "Payments to suppliers at above-market prices with kickback returned to management. "
             "Indicators: sole-source procurement, price paid > 3 competing quotes. "
             "Test: market price benchmarks for fuel procurement costs.",
             {"severity": "high", "area": "procurement"}),

            ("fraud_related_party_loans", "Unauthorized Related Party Loans",
             "Loans to directors or related entities not authorized by board. "
             "No interest charged (breach of arm's length principle). "
             "May be disguised as 'advances' or 'prepayments'. "
             "Test: all receivables >30 days — verify nature and authorization.",
             {"severity": "critical", "area": "related_party"}),

            ("fraud_transfer_pricing", "Transfer Pricing Manipulation",
             "Intercompany fuel sales at artificially low prices to shift profit to low-tax jurisdiction. "
             "Georgian tax authority requires arm's length documentation for intercompany >GEL 1M. "
             "Test: compare intercompany price to third-party market price.",
             {"severity": "high", "area": "transfer_pricing",
              "threshold": "GEL_1M_intercompany"}),

            ("fraud_fictitious_employee", "Fictitious Employee (Payroll Fraud)",
             "Ghost employees on payroll — salaries paid to non-existent staff. "
             "Indicators: high headcount relative to revenue, employees with no system access. "
             "Test: physical HR verification, tax ID cross-reference with Revenue Service.",
             {"severity": "medium", "area": "payroll"}),

            ("fraud_document_alteration", "Document Alteration / Forgery",
             "Altered delivery notes, invoices, or bank statements to support fictitious entries. "
             "Red flags: different fonts/ink on same document, digital metadata mismatch. "
             "Test: request originals from third parties (bank, supplier) for comparison.",
             {"severity": "critical", "area": "documentation"}),
        ]

        for eid, label, desc, props in signals:
            entity = KnowledgeEntity(
                entity_id=f"fraud_{eid}",
                entity_type="fraud_signal",
                label_en=label,
                label_ka="",
                description=desc,
                properties={**props, "source": "fraud_detection"},
            )
            self._add_entity(entity)

    def _add_accounting_formulas(self) -> None:
        """Add 32 key accounting formulas and financial relationships."""
        formulas = [
            # ── P&L Waterfall ─────────────────────────────────────────────────
            ("fml_pl_waterfall", "P&L Statement Waterfall",
             "Complete P&L calculation chain for petroleum distributors:\n"
             "1. Net Revenue (excl. VAT) = Wholesale Rev + Retail Rev + Other Rev\n"
             "2. COGS = Account 6xxx + Account 7310 + Account 8230\n"
             "3. Gross Profit = Revenue - COGS\n"
             "4. Gross Margin % = Gross Profit / Revenue × 100\n"
             "5. G&A Expenses = Account 7xxx (excl. 7310)\n"
             "6. EBITDA = Gross Profit - G&A\n"
             "7. D&A = Depreciation (Account 8110) + Amortization (Account 8120)\n"
             "8. EBIT = EBITDA - D&A\n"
             "9. Finance Income (Account 8310) - Finance Expense (Account 8410)\n"
             "10. EBT = EBIT + Net Finance\n"
             "11. Income Tax (Account 9110)\n"
             "12. Net Profit = EBT - Tax",
             {"type": "pl_structure", "accounts": "6xxx|7xxx|8xxx|9xxx"}),

            ("fml_gross_profit", "Gross Profit Calculation",
             "Gross Profit = Net Revenue − Cost of Goods Sold\n"
             "COGS components for fuel distributor:\n"
             "  - Purchase cost of fuel (Account 6110)\n"
             "  - Direct delivery costs (Account 7310, classified as COGS)\n"
             "  - Excise tax paid on fuel (Account 8230)\n"
             "Gross Margin % = (Revenue - COGS) / Revenue × 100",
             {"formula": "Revenue - COGS", "cogs_accounts": "6110|7310|8230"}),

            ("fml_ebitda", "EBITDA Calculation",
             "EBITDA = Earnings Before Interest, Tax, Depreciation, Amortization\n"
             "Method 1 (top-down): Revenue - COGS - G&A\n"
             "Method 2 (bottom-up): Net Profit + Tax + Interest + D&A\n"
             "Note: EBITDA excludes D&A which are non-cash charges\n"
             "Better operational metric than Net Profit for capital-intensive businesses",
             {"formula": "Gross Profit - G&A = EBITDA", "alternative": "Net Profit + Tax + Interest + DA"}),

            ("fml_working_capital", "Working Capital Formula",
             "Working Capital = Current Assets - Current Liabilities\n"
             "Current Assets (liquid, <12 months): Cash (1110) + Receivables (1210) + Inventory (1310) + Other CA\n"
             "Current Liabilities (<12 months): Payables (3110) + Short-term debt (3410) + Tax payable (3310)\n"
             "Positive WC → can meet short-term obligations\n"
             "Negative WC → technical insolvency risk",
             {"formula": "Current Assets - Current Liabilities",
              "ca_accounts": "1110|1210|1310", "cl_accounts": "3110|3310|3410"}),

            ("fml_balance_sheet_equation", "Balance Sheet Fundamental Equation",
             "Assets = Liabilities + Equity (MUST balance)\n"
             "Assets = Non-current Assets + Current Assets\n"
             "Liabilities = Non-current Liabilities + Current Liabilities\n"
             "Equity = Share Capital + Retained Earnings + Other Comprehensive Income\n"
             "Test: if Assets ≠ L + E → data integrity error",
             {"formula": "Assets = Liabilities + Equity", "must_balance": True}),

            ("fml_cash_flow_indirect", "Operating Cash Flow (Indirect Method)",
             "Operating CF = Net Profit\n"
             "  + D&A (non-cash expense, add back)\n"
             "  - Increase in Receivables (cash tied up)\n"
             "  + Decrease in Receivables (cash released)\n"
             "  - Increase in Inventory\n"
             "  + Increase in Payables (supplier financing)\n"
             "  ± Other working capital changes",
             {"method": "indirect", "standard": "IAS 7"}),

            ("fml_net_change_cash", "Net Change in Cash",
             "Net Change = Operating CF + Investing CF + Financing CF\n"
             "Operating CF: from core business (customer receipts - supplier payments)\n"
             "Investing CF: purchase/sale of PP&E, investments (-CapEx)\n"
             "Financing CF: debt proceeds/repayment, equity issuance, dividends\n"
             "Closing Cash = Opening Cash + Net Change",
             {"formula": "OCF + ICF + FCF = Net Change", "standard": "IAS 7"}),

            ("fml_depreciation_sl", "Straight-Line Depreciation",
             "Annual Depreciation = (Cost - Residual Value) / Useful Life\n"
             "Example: Vehicle cost GEL 50,000, residual GEL 5,000, life 5 years\n"
             "Annual D&A = (50,000 - 5,000) / 5 = GEL 9,000/year\n"
             "Book Value = Cost - Accumulated Depreciation",
             {"method": "straight_line", "formula": "(Cost - Residual) / Useful Life"}),

            ("fml_cogs_fuel", "COGS for Fuel Distributor",
             "COGS = Opening Inventory + Purchases - Closing Inventory\n"
             "= Purchase cost of fuel (at landed cost incl. excise)\n"
             "+ Delivery costs classified as COGS\n"
             "Landed cost = Import price + Customs + Excise + Freight\n"
             "COGS per liter = (NYX Core Thinker purchase price + GEL 0.40 excise + freight) per liter",
             {"type": "cogs_detail", "includes_excise": True}),

            ("fml_breakeven", "Break-Even Analysis",
             "Break-Even Volume = Fixed Costs / (Price per unit - Variable Cost per unit)\n"
             "Break-Even Revenue = Fixed Costs / Gross Margin %\n"
             "For fuel distributor:\n"
             "Fixed Costs = G&A + D&A + Finance Costs\n"
             "Variable Costs = COGS per liter\n"
             "Break-even = when Total Revenue = Total Costs",
             {"formula": "Fixed Costs / Contribution Margin", "type": "breakeven"}),

            ("fml_irr", "Internal Rate of Return (IRR)",
             "Discount rate at which NPV of project cash flows = 0\n"
             "Decision: IRR > WACC → accept project\n"
             "For new petrol station: IRR typically 15–25% in Georgia\n"
             "Higher IRR = better investment. Compare to cost of capital.",
             {"formula": "NPV=0 solving for r", "type": "capital_budgeting",
              "benchmark": "15-25%_petrol_station"}),

            ("fml_npv", "Net Present Value (NPV)",
             "NPV = Σ (CF_t / (1+r)^t) - Initial Investment\n"
             "r = discount rate (WACC), CF = cash flows\n"
             "NPV > 0 → value-creating investment\n"
             "NPV < 0 → destroys value\n"
             "Common WACC for Georgian fuel companies: 12–18%",
             {"formula": "Sum of discounted CFs - Investment", "type": "capital_budgeting",
              "wacc_benchmark": "12-18%"}),

            ("fml_wacc", "Weighted Average Cost of Capital (WACC)",
             "WACC = (E/V × Re) + (D/V × Rd × (1-T))\n"
             "E = Market value of equity, D = Market value of debt\n"
             "V = E + D, Re = Cost of equity, Rd = Cost of debt, T = Tax rate\n"
             "Georgian fuel sector: WACC typically 12–18%\n"
             "Used as hurdle rate for investment decisions.",
             {"formula": "E/(E+D)*Re + D/(E+D)*Rd*(1-T)",
              "georgia_benchmark": "12-18%", "type": "capital_cost"}),

            ("fml_gordon_growth", "Gordon Growth Model (Dividend Discount)",
             "Stock Value = D1 / (Re - g)\n"
             "D1 = Next dividend, Re = Required return, g = Perpetual growth rate\n"
             "Assumes constant dividend growth. Simple valuation for mature distributors.",
             {"formula": "D1 / (Re - g)", "type": "valuation"}),

            ("fml_price_volume_mix", "Price-Volume-Mix Variance Analysis",
             "Revenue Change = Price Variance + Volume Variance + Mix Variance\n"
             "Price Variance = (New Price - Old Price) × New Volume\n"
             "Volume Variance = (New Volume - Old Volume) × Old Price\n"
             "Mix Variance = Volume change in higher-margin products\n"
             "Critical for understanding fuel revenue changes: price vs volume driven.",
             {"type": "variance_analysis",
              "formula": "ΔRevenue = Price Var + Volume Var + Mix Var"}),

            ("fml_inventory_valuation", "Inventory Valuation Methods",
             "Three permitted methods under IAS 2:\n"
             "1. FIFO (First In First Out): older cost matches against revenue\n"
             "2. Weighted Average Cost: blended average of all purchases\n"
             "3. Specific Identification: for unique high-value items\n"
             "LIFO NOT permitted under IFRS\n"
             "Fuel: Weighted Average most common (blended tank cost)",
             {"standard": "IAS 2", "fuel_method": "weighted_average", "type": "inventory"}),

            ("fml_lower_cost_nrv", "Lower of Cost or Net Realisable Value",
             "Inventory valued at lower of: Cost or Net Realisable Value (NRV)\n"
             "NRV = Estimated selling price - Costs to complete and sell\n"
             "If fuel prices fall sharply: NRV < Cost → write down inventory\n"
             "Write-down = expense in period recognized (goes to COGS)\n"
             "Reversal permitted if NRV recovers (up to original write-down).",
             {"standard": "IAS 2", "formula": "min(Cost, NRV)", "type": "inventory"}),

            ("fml_accrual_basis", "Accrual Basis Principle",
             "Transactions recorded when earned/incurred, not when cash received/paid\n"
             "Revenue: recognized when performance obligation satisfied (IFRS 15)\n"
             "Expenses: recognized in period incurred (matching principle)\n"
             "Creates timing differences: accruals, prepayments, deferred revenue",
             {"principle": "accrual", "type": "accounting_principle"}),

            ("fml_materiality", "Materiality Principle",
             "Information is material if its omission or misstatement could influence decisions.\n"
             "Quantitative threshold: typically 5% of profit or 0.5% of revenue\n"
             "Qualitative: nature of item also matters (e.g., related party, illegal)\n"
             "Auditors design procedures based on materiality level.",
             {"principle": "materiality", "type": "accounting_principle",
              "threshold": "5%_profit_or_0.5%_revenue"}),

            ("fml_going_concern", "Going Concern Assumption",
             "Financial statements prepared assuming entity will continue to operate for 12+ months\n"
             "If doubt exists: disclose in financial statements\n"
             "If cannot continue: liquidation basis accounting required\n"
             "Indicators of doubt: sustained losses, negative equity, loan defaults, legal proceedings",
             {"principle": "going_concern", "type": "accounting_principle",
              "assessment_period": "12_months"}),

            ("fml_substance_over_form", "Substance Over Form",
             "Record economic substance of transactions, not just legal form\n"
             "Example: sale-and-leaseback structured as sale but economically a financing\n"
             "Sale-and-leaseback at market terms: recognize derecognition\n"
             "Sale-and-leaseback below fair value: recognize as financing\n"
             "Critical for assessing complex intercompany transactions.",
             {"principle": "substance_over_form", "type": "accounting_principle"}),

            ("fml_ebit_from_ebitda", "EBIT from EBITDA",
             "EBIT = EBITDA - D&A\n"
             "D&A = Depreciation (Account 8110) + Amortization (Account 8120)\n"
             "EBIT is also called 'Operating Profit'\n"
             "EBIT margin = EBIT / Revenue × 100\n"
             "Benchmark: 0.5–3% for petroleum distributors",
             {"formula": "EBITDA - D&A", "accounts": "8110|8120", "type": "pl_item"}),

            ("fml_net_debt", "Net Debt Calculation",
             "Net Debt = Total Borrowings - Cash and Cash Equivalents\n"
             "Total Borrowings = Short-term debt (3410) + Long-term debt (4410)\n"
             "Net Debt / EBITDA = key leverage metric (lenders limit to 3–4x)\n"
             "Negative Net Debt = net cash position (company has more cash than debt)",
             {"formula": "Total Debt - Cash", "leverage_limit": "3-4x_EBITDA",
              "accounts": "3410|4410|1110"}),

            ("fml_eva", "Economic Value Added (EVA)",
             "EVA = NOPAT - (WACC × Invested Capital)\n"
             "NOPAT = Net Operating Profit After Tax (EBIT × (1-T))\n"
             "Invested Capital = Total Assets - Current Liabilities\n"
             "Positive EVA → creating shareholder value\n"
             "Negative EVA → destroying value despite accounting profit",
             {"formula": "NOPAT - (WACC × Invested Capital)", "type": "value_creation"}),

            ("fml_contribution_margin", "Contribution Margin",
             "Contribution Margin = Revenue - Variable Costs\n"
             "CM per unit = Price - Variable Cost per unit\n"
             "CM Ratio = Contribution Margin / Revenue\n"
             "Shows how much each sale contributes to covering fixed costs and profit\n"
             "Fuel: CM per liter = Selling price/liter - COGS per liter",
             {"formula": "Revenue - Variable Costs", "type": "cost_analysis"}),

            ("fml_leverage_operating", "Operating Leverage",
             "Operating Leverage = Contribution Margin / EBIT\n"
             "High operating leverage: small revenue change → large EBIT impact\n"
             "Fixed-cost-heavy businesses have high operating leverage\n"
             "Fuel distributors: moderate leverage (high variable COGS, some fixed G&A)",
             {"formula": "Contribution Margin / EBIT", "type": "risk_measure"}),

            ("fml_ppe_carrying", "PP&E Carrying Value",
             "Carrying Value = Cost - Accumulated Depreciation - Impairment Losses\n"
             "Revaluation Model (IAS 16 permitted): carrying value = fair value at revaluation date\n"
             "Revaluation surplus in equity (OCI), deficit to P&L\n"
             "Impairment (IAS 36): recoverable amount = max(FV-Costs, Value in Use)",
             {"formula": "Cost - Acc Dep - Impairment", "standard": "IAS 16",
              "type": "ppe_calculation"}),

            ("fml_financial_ratios_pyramid", "Financial Ratios Pyramid (DuPont)",
             "ROE = Net Margin × Asset Turnover × Equity Multiplier\n"
             "= (Net Profit/Revenue) × (Revenue/Assets) × (Assets/Equity)\n"
             "Diagnosis:\n"
             "  Low ROE from low margin → pricing or cost issue\n"
             "  Low ROE from low turnover → asset efficiency issue\n"
             "  Low ROE from low multiplier → underleveraged\n"
             "  Low ROE from all three → systemic operational problems",
             {"formula": "ROE = Margin × Turnover × Multiplier", "type": "analysis_framework"}),

            ("fml_sensitivity_analysis", "Sensitivity Analysis for Fuel Margins",
             "Impact of price changes on profitability:\n"
             "+1 tetri/liter price increase × 1M liters/month = +GEL 10,000/month revenue impact\n"
             "+1 tetri/liter COGS increase × 1M liters/month = -GEL 10,000/month margin impact\n"
             "FX sensitivity: USD/GEL +0.01 change × USD import volume = GEL impact on COGS\n"
             "Use for scenario analysis and stress testing.",
             {"type": "sensitivity", "unit": "tetri_per_liter"}),

            ("fml_inventory_days_coverage", "Inventory Days of Coverage",
             "Days of Coverage = Closing Inventory / Daily COGS\n"
             "Daily COGS = Annual COGS / 365\n"
             "Fuel: 10–15 days optimal. Excess inventory = capital tied up.\n"
             "Below 5 days = stockout risk\n"
             "Safety stock calculation: demand uncertainty × lead time",
             {"formula": "Inventory / (COGS/365)", "benchmark": "10-15 days",
              "stockout_warning": "<5 days"}),

            ("fml_accrued_liabilities", "Accrued Liabilities Calculation",
             "Accrued liabilities = expenses incurred but not yet invoiced\n"
             "Examples: salary accruals, utility accruals, interest accruals\n"
             "Journal: Dr Expense Cr Accrued Liability (Account 3510)\n"
             "Reversal: at start of next period, reverse and record actual invoice\n"
             "Key accounts: 3510 (Accrued Expenses), 3520 (Accrued Interest)",
             {"accounts": "3510|3520", "type": "accruals"}),

            ("fml_tax_provision", "Income Tax Provision (Georgian Context)",
             "Under Estonian model: provision only on dividends declared\n"
             "Tax Provision = Dividends Declared × 15% CIT + 5% WHT (resident)\n"
             "If no dividends: no tax provision needed\n"
             "Deferred tax: minimal under Estonian model (no timing differences for undistributed profits)\n"
             "Account: Dr Tax Expense (9110) Cr Tax Payable (3310)",
             {"standard": "IAS 12", "georgia_model": "Estonian",
              "accounts": "9110|3310", "type": "tax_provision"}),
        ]

        for eid, label, desc, props in formulas:
            entity = KnowledgeEntity(
                entity_id=f"formula_{eid}",
                entity_type="formula",
                label_en=label,
                label_ka="",
                description=desc,
                properties={**props, "source": "accounting_formulas"},
            )
            self._add_entity(entity)

    def _add_extended_benchmarks(self) -> None:
        """Add 20 extended industry benchmarks for Georgian petroleum sector."""
        benchmarks = [
            ("bench_fuel_volume_ws", "Wholesale Fuel Volume Benchmark",
             "Typical wholesale petroleum distributor in Georgia: 50–500M liters/year. "
             "NYX Core Thinker wholesale: ~1.5B liters/year (dominant). "
             "Mid-tier distributor: 100–300M liters/year. "
             "Revenue per liter wholesale: GEL 2.00–3.50 (market price dependent).",
             {"volume_range": "50-500M_liters/year", "revenue_per_liter": "GEL_2.00-3.50"}),

            ("bench_fuel_volume_rt", "Retail Fuel Volume Benchmark",
             "Petrol station average: 1.5–4M liters/month in Tbilisi. "
             "Regional stations: 500K–1.5M liters/month. "
             "Revenue per station/month: GEL 3M–8M. "
             "Gross profit per station/month: GEL 240K–800K at 8–10% margin.",
             {"tbilisi_station": "1.5-4M_liters/month", "regional_station": "0.5-1.5M_liters/month"}),

            ("bench_headcount_ratio", "Revenue per Employee Benchmark",
             "Georgian petroleum distributor: GEL 2M–5M revenue per employee. "
             "Petrol station: 10–20 employees per station. "
             "Head office / wholesale: 1 employee per GEL 5M–10M wholesale revenue. "
             "High headcount-to-revenue suggests inefficiency.",
             {"revenue_per_employee": "GEL_2M-5M", "station_headcount": "10-20"}),

            ("bench_finance_cost_ratio", "Finance Cost as % of Revenue",
             "Petroleum distributors: 0.5–2% of revenue is typical. "
             ">3% signals overleveraged. <0.2% indicates debt-free (unusual for sector). "
             "Georgian bank borrowing rates: 10–16% GEL-denominated, 6–9% USD-denominated.",
             {"ratio": "0.5-2%_of_revenue", "bank_rate_gel": "10-16%", "bank_rate_usd": "6-9%"}),

            ("bench_capex_intensity", "Capital Expenditure Intensity",
             "Annual CapEx as % of revenue for fuel distributors: 1–3% maintenance, 3–8% growth. "
             "Tank farm construction: GEL 5M–20M per site. "
             "Petrol station build: GEL 1.5M–3M per site. "
             "Delivery truck: GEL 80K–120K per vehicle.",
             {"maintenance_capex": "1-3%_revenue", "growth_capex": "3-8%_revenue",
              "tank_farm_cost": "GEL_5M-20M"}),

            ("bench_receivable_days", "Receivables Collection Period",
             "Wholesale fuel (corporate clients): 30–45 days payment terms. "
             "Government/state entities: 45–90 days (payment delays common). "
             "Retail (card/cash): immediate collection. "
             "DSO >60 days for wholesale: collection efficiency warning.",
             {"wholesale_terms": "30-45 days", "government_terms": "45-90 days",
              "warning": "DSO>60_days"}),

            ("bench_inventory_turnover_fuel", "Fuel Inventory Turnover Rate",
             "Petroleum distributor: 20–36x per year (10–18 day supply). "
             "High turnover = efficient working capital. "
             "Low turnover (<15x) suggests overstocking or slow-moving products. "
             "Bulk importers: lower turnover due to ship-load purchasing economics.",
             {"target": "20-36x/year", "supply_days": "10-18 days",
              "warning_low": "<15x/year"}),

            ("bench_ga_staff_fuel", "G&A Cost Benchmarks for Fuel Sector",
             "G&A as % of revenue: 1.5–4% for Georgia-based distributors. "
             "Key G&A components: salaries (50%), rent (20%), IT/systems (10%), other (20%). "
             "Salaries in Tbilisi for finance roles: GEL 1,500–3,500/month. "
             "Logistics manager: GEL 2,000–4,000/month.",
             {"ga_ratio": "1.5-4%_revenue", "salary_tbilisi": "GEL_1500-3500/month"}),

            ("bench_ebitda_fuel", "EBITDA Benchmarks — Petroleum Distribution",
             "Pure wholesale distributor: EBITDA margin 0.5–2%. "
             "Mixed wholesale + retail: EBITDA margin 2–6%. "
             "Pure retail network: EBITDA margin 5–10%. "
             "Negative EBITDA sustained >2 quarters: structural problem.",
             {"wholesale_only": "0.5-2%", "mixed": "2-6%",
              "retail_only": "5-10%", "warning": "negative_EBITDA_2quarters"}),

            ("bench_da_ratio", "D&A as % of Revenue",
             "D&A for fuel distributor: 0.5–2% of revenue. "
             "Asset-heavy (owns tank farms + stations): 2–4%. "
             "Asset-light (rents infrastructure): 0.3–1%. "
             "High D&A relative to EBITDA: asset base may need refreshing.",
             {"asset_heavy": "2-4%", "asset_light": "0.3-1%"}),

            ("bench_fuel_price_georgia", "Retail Fuel Prices Georgia (2024)",
             "Petrol 95: GEL 3.00–3.60/liter (market-priced). "
             "Diesel: GEL 2.80–3.30/liter. "
             "CNG: GEL 1.20–1.50/m3. "
             "Prices volatile: linked to Brent crude (USD) + GEL/USD exchange rate + excise. "
             "Price sensitivity: $10/bbl crude change ≈ GEL 0.05–0.08/liter retail change.",
             {"petrol95": "GEL_3.00-3.60/liter", "diesel": "GEL_2.80-3.30/liter",
              "year": "2024", "driver": "Brent+USD/GEL+excise"}),

            ("bench_market_share_georgia", "Georgian Fuel Market Share",
             "NYX Core Thinker: ~40% market share. "
             "Wissol: ~20% market share. "
             "Gulf/other: ~15%. "
             "Rompetrol: ~10%. "
             "Independent distributors: ~15% combined. "
             "Highly concentrated market — pricing follows NYX Core Thinker leadership.",
             {"nyx_core_thinker": "~40%", "wissol": "~20%", "structure": "oligopolistic"}),

            ("bench_gdp_georgia", "Georgian Macro Benchmarks",
             "GDP (2024): ~USD 30B. "
             "GDP growth: 7–10% (high by European standards). "
             "Inflation: 4–8% GEL-denominated. "
             "GEL/USD: 2.65–2.80 range (2023–2024). "
             "Fuel demand growth: correlated with GDP (+0.8 elasticity). "
             "Implications: growing market, but inflation erodes real margins.",
             {"gdp_usd": "30B", "growth": "7-10%", "gel_usd": "2.65-2.80"}),

            ("bench_nyx_import_price", "NYX Core Thinker Wholesale Import Price Structure",
             "NYX Core Thinker imports at Brent-linked price. "
             "Typical landed cost: Brent crude × 0.95 + refining margin (~$15/bbl) + freight + excise. "
             "FOB Black Sea delivery to Batumi terminal. "
             "Transfer pricing: arm's length required (Georgian tax rules).",
             {"import_source": "NYX_Core_Thinker", "pricing": "Brent_linked",
              "delivery_point": "Batumi_terminal"}),

            ("bench_working_cap_fuel", "Working Capital Requirements",
             "Fuel distributor working capital needs: 10–20% of annual COGS. "
             "Primary driver: inventory financing (bulk purchases). "
             "Secondary: receivables from corporate clients. "
             "Seasonal peaks: Q3 (summer travel, agriculture) requires +20–30% WC.",
             {"wc_ratio": "10-20%_of_COGS", "seasonal_peak": "Q3_plus_20-30%"}),

            ("bench_customer_concentration", "Customer Concentration Risk",
             "Top 10 customers >50% of revenue: concentration risk. "
             "Single customer >20%: major risk (IAS 24 disclosure if related party). "
             "Georgian fuel: corporate fleets often top customers. "
             "Government contracts: high volume but payment delay risk.",
             {"high_risk": ">20%_single_customer", "medium_risk": ">50%_top10"}),

            ("bench_loan_covenant", "Typical Loan Covenants for Georgian Fuel Companies",
             "Common financial covenants from TBC/BoG for fuel distributors:\n"
             "Net Debt/EBITDA: maximum 3.5x\n"
             "DSCR: minimum 1.25x\n"
             "Current Ratio: minimum 1.1x\n"
             "Equity/Total Assets: minimum 30%\n"
             "Covenant breach triggers cross-default on all loans.",
             {"net_debt_ebitda": "max_3.5x", "dscr": "min_1.25x",
              "current_ratio": "min_1.1x", "equity_ratio": "min_30%"}),

            ("bench_gross_margin_product_mix", "Gross Margin by Product Type",
             "Petrol 95 (retail): 10–15% gross margin per liter. "
             "Diesel (retail): 8–12% per liter. "
             "Petrol (wholesale): 1–4% per liter. "
             "Diesel (wholesale): 1–3% per liter. "
             "Lubricants (retail): 15–25% (highest margin product). "
             "Mix shift toward retail → higher blended margin.",
             {"petrol95_retail": "10-15%", "diesel_retail": "8-12%",
              "petrol95_wholesale": "1-4%", "lubricants": "15-25%"}),

            ("bench_station_economics", "Petrol Station Unit Economics",
             "Tbilisi high-traffic station: 3–5M liters/month throughput. "
             "Gross profit per liter: GEL 0.30–0.50. "
             "Monthly gross profit: GEL 900K–2.5M per station. "
             "Operating costs: GEL 150K–300K/month (staff, rent, utilities). "
             "Station EBITDA: GEL 600K–2.0M/month. Payback period: 3–6 years.",
             {"throughput": "3-5M_liters/month_Tbilisi",
              "gp_per_liter": "GEL_0.30-0.50", "payback": "3-6_years"}),

            ("bench_import_lead_time", "Fuel Import Lead Times Georgia",
             "Sea route (Batumi port): 5–10 days from Baku/Odessa. "
             "Rail route (from Azerbaijan/Russia): 7–14 days. "
             "Customs clearance: 1–3 days. "
             "Total cycle: 10–20 days from order to available inventory. "
             "Safety stock requirement: 10–15 days COGS.",
             {"sea_transit": "5-10 days", "rail_transit": "7-14 days",
              "safety_stock": "10-15_days_COGS"}),
        ]

        for eid, label, desc, props in benchmarks:
            entity = KnowledgeEntity(
                entity_id=f"bench_{eid}",
                entity_type="benchmark",
                label_en=label,
                label_ka="",
                description=desc,
                properties={**props, "source": "industry_benchmarks", "sector": "petroleum_georgia"},
            )
            self._add_entity(entity)

    # =========================================================================
    # 1C CHART OF ACCOUNTS — Real 406-Account COA from 1C AccountN.xlsx
    # =========================================================================

    def _add_onec_coa_accounts(self) -> None:
        """
        Load the real 1C Chart of Accounts accounts as KG entities.
        Parses the uploaded 1C AccountN.xlsx if available; otherwise uses
        a representative hardcoded subset of the most important accounts.
        This gives the KG grounded knowledge of the actual account structure.
        """
        import os
        # Check multiple paths for COA file
        default_paths = [
            r"C:\Users\Nino\OneDrive\Desktop\1c AccountN.xlsx",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "1c AccountN.xlsx"),
            "uploads/1c AccountN.xlsx",
        ]
        coa_path = os.environ.get("COA_FILE_PATH", "")
        if not coa_path or not os.path.exists(coa_path):
            for p in default_paths:
                if os.path.exists(p):
                    coa_path = p
                    break

        loaded_from_file = False
        if os.path.exists(coa_path):
            try:
                from app.services.onec_interpreter import OneCInterpreter
                interp = OneCInterpreter()
                tree   = interp.parse_file(coa_path)
                for acct in tree.postable():
                    # Skip corrupted entries and group codes
                    if acct.is_corrupted:
                        continue
                    name_en = acct.name_ru or f"Account {acct.code}"
                    name_ka = acct.name_ka or ""
                    desc_parts = [f"1C Account {acct.code}"]
                    if acct.ifrs_pl_line:
                        desc_parts.append(f"P&L line: {acct.ifrs_pl_line}")
                    if acct.ifrs_bs_line:
                        desc_parts.append(f"BS line: {acct.ifrs_bs_line}")
                    if acct.subkonto:
                        desc_parts.append(f"Dimensions: {', '.join(acct.subkonto[:2])}")
                    desc = " | ".join(desc_parts)

                    entity = KnowledgeEntity(
                        entity_id=f"coa1c_{acct.code_normalized}",
                        entity_type="coa_account",
                        label_en=name_en,
                        label_ka=name_ka,
                        description=desc,
                        properties={
                            "code": acct.code,
                            "account_type": acct.account_type,
                            "normal_balance": acct.normal_balance,
                            "ifrs_section": acct.ifrs_section,
                            "ifrs_pl_line": acct.ifrs_pl_line or "",
                            "ifrs_bs_line": acct.ifrs_bs_line or "",
                            "ifrs_bs_side": acct.ifrs_bs_side or "",
                            "ifrs_bs_sub": acct.ifrs_bs_sub or "",
                            "is_off_balance": str(acct.is_off_balance),
                            "tracks_currency": str(acct.tracks_currency),
                            "tracks_quantity": str(acct.tracks_quantity),
                            "dimensions": ", ".join(acct.subkonto_semantics),
                            "source": "1c_accountn_xlsx",
                        },
                    )
                    self._add_entity(entity)
                    # Also update legacy index by code for backward compatibility
                    self._index_by_code[acct.code_normalized] = entity.entity_id
                loaded_from_file = True
                logger.info("KG: loaded %d 1C COA accounts from file", len(tree.postable()))
            except Exception as e:
                logger.warning("KG: could not load COA from file %s: %s", coa_path, e)

        if not loaded_from_file:
            # Hardcoded representative subset — key accounts for Georgian petroleum sector
            key_accounts = [
                # Cash & Bank (1xxx)
                ("1110", "Cash in Hand", "დასაქ",    "Active", "current_assets",    "Cash & Cash Equivalents", None, ["bank_account"]),
                ("1210", "Bank Account GEL", "",     "Active", "current_assets",    "Bank Accounts",           None, ["bank_account"]),
                ("1220", "Bank Account USD", "",     "Active", "current_assets",    "Bank Accounts",           None, ["bank_account", "currency"]),
                # Receivables
                ("1310", "Trade Receivables", "",    "Mixed",  "current_assets",    "Trade Receivables",       None, ["counterparty", "contract"]),
                ("1410", "Other Receivables", "",    "Mixed",  "current_assets",    "Other Receivables",       None, ["counterparty"]),
                # Inventory
                ("1510", "Fuel Inventory", "",       "Active", "current_assets",    "Inventory",               None, ["product_item", "warehouse"]),
                ("1520", "Lubricants Inventory", "", "Active", "current_assets",    "Inventory",               None, ["product_item", "warehouse"]),
                # Advances
                ("1610", "Advances to Suppliers", "","Active","current_assets",    "Advances Paid",            None, ["counterparty"]),
                # PP&E
                ("2110", "Property, Plant & Equipment", "", "Active", "noncurrent_assets", "PP&E", None, ["fixed_asset"]),
                ("2210", "Accumulated Depreciation", "", "Passive","noncurrent_assets","Accumulated Depreciation",None,[]),
                ("2310", "Intangible Assets", "",    "Active", "noncurrent_assets", "Intangible Assets",       None, ["intangible_asset"]),
                # Payables
                ("3110", "Trade Payables", "",       "Mixed",  "current_liabilities","Trade Payables",          None, ["counterparty", "contract"]),
                ("3210", "Tax Payable (CIT)", "",    "Mixed",  "current_liabilities","Tax Payable",             None, ["budget_payment_type"]),
                ("3310", "VAT Payable", "",          "Mixed",  "current_liabilities","VAT Payable",             None, ["vat_rate"]),
                ("3410", "Advances from Customers","","Mixed", "current_liabilities","Advances Received",        None, ["counterparty"]),
                # Long-term debt
                ("4110", "Long-term Bank Loan", "", "Passive", "noncurrent_liabilities","Long-term Debt",      None, ["counterparty"]),
                # Equity
                ("5110", "Share Capital", "",        "Passive","equity",            "Share Capital",            None, []),
                ("5210", "Additional Capital", "",   "Passive","equity",            "Share Premium",            None, []),
                ("5310", "Retained Earnings", "",    "Passive","equity",            "Retained Earnings",        None, ["profit_loss"]),
                # Revenue (6xxx)
                ("6110", "Wholesale Revenue", "",    "Passive","income_statement",  None, "Revenue",    ["counterparty", "product_group"]),
                ("6120", "Retail Revenue", "",       "Passive","income_statement",  None, "Revenue",    ["product_item", "department"]),
                ("6210", "Other Revenue", "",        "Passive","income_statement",  None, "Revenue",    ["other_income_expense"]),
                # COGS (7xxx)
                ("7110", "Cost of Goods Sold", "",   "Active", "income_statement",  None, "Cost of Sales", ["product_group", "cost_item"]),
                ("7120", "Fuel COGS", "",            "Active", "income_statement",  None, "Cost of Sales", ["product_item", "cost_item"]),
                # Selling expenses
                ("7310", "Selling Expenses", "",     "Active", "income_statement",  None, "Selling Expenses", ["cost_item", "department"]),
                # Admin expenses
                ("7210", "Admin Expenses", "",       "Active", "income_statement",  None, "Admin Expenses", ["cost_item", "department"]),
                # Other income/expense
                ("8110", "Other Operating Income","","Passive","income_statement",   None, "Other Operating Income", ["other_income_expense"]),
                ("8210", "Finance Income", "",       "Passive","income_statement",  None, "Finance Income",  []),
                ("8310", "Finance Costs", "",        "Active", "income_statement",  None, "Finance Costs",   ["counterparty"]),
                # Tax/Net
                ("9110", "Income Tax Expense", "",   "Active", "income_statement",  None, "Income Tax",      []),
            ]

            for code, name_en, name_ka, acct_type, ifrs_section, bs_line, pl_line, dims in key_accounts:
                desc_parts = [f"Account {code}", name_en]
                if pl_line:
                    desc_parts.append(f"P&L: {pl_line}")
                if bs_line:
                    desc_parts.append(f"BS: {bs_line}")
                if dims:
                    desc_parts.append(f"Dims: {', '.join(dims[:2])}")

                entity = KnowledgeEntity(
                    entity_id=f"coa1c_{code}",
                    entity_type="coa_account",
                    label_en=name_en,
                    label_ka=name_ka,
                    description=" | ".join(desc_parts),
                    properties={
                        "code": code,
                        "account_type": acct_type,
                        "ifrs_section": ifrs_section,
                        "ifrs_pl_line": pl_line or "",
                        "ifrs_bs_line": bs_line or "",
                        "dimensions": ", ".join(dims),
                        "source": "hardcoded_key_accounts",
                    },
                )
                self._add_entity(entity)
                self._index_by_code[code] = entity.entity_id

    def _add_onec_subkonto_dimensions(self) -> None:
        """
        Add 1C analytical dimension types (Субконто) as KG entities.
        These enable the system to understand what data is tracked per account.
        """
        dimensions = [
            ("sub_counterparty",      "Counterparty (Контрагент)",
             "Track balances and turnover per business counterparty (customer, vendor, partner). "
             "Required for accounts receivable (1310), payables (3110), advances. "
             "Enables aged debtor/creditor analysis and counterparty exposure reporting.",
             {"semantic": "counterparty", "accounts": "1310,3110,3410,6110,6120"}),

            ("sub_contract",          "Contract (Договор)",
             "Track transactions per specific contract. Second-level analytical dimension. "
             "Used with Counterparty for full AR/AP contract-level analysis. "
             "Enables revenue recognition per contract per IFRS 15.",
             {"semantic": "contract", "ifrs": "IFRS_15_revenue_recognition"}),

            ("sub_product",           "Product / Nomenclature (Номенклатура)",
             "Track inventory movements and COGS per product item. "
             "Used for inventory (1510, 1520) and COGS (7110, 7120). "
             "Enables gross margin analysis by product: petrol95, diesel, lubricants.",
             {"semantic": "product_item", "accounts": "1510,1520,7110,7120"}),

            ("sub_product_group",     "Product Group (Номенклатурные группы)",
             "Higher-level product dimension: Wholesale Fuel, Retail Fuel, Lubricants, Other. "
             "Used for segment reporting and P&L by product category.",
             {"semantic": "product_group", "usage": "revenue_segmentation"}),

            ("sub_department",        "Department (Подразделение)",
             "Track revenues and expenses by internal department or cost center. "
             "Used for management reporting and internal P&L by department.",
             {"semantic": "department", "usage": "cost_center_reporting"}),

            ("sub_warehouse",         "Warehouse / Storage (Склад)",
             "Track inventory by physical location: depot, station, transit. "
             "Used for inventory (1510) to compute stock by location.",
             {"semantic": "warehouse", "accounts": "1510,1520"}),

            ("sub_fixed_asset",       "Fixed Asset (Основные средства)",
             "Track individual PP&E assets for depreciation and disposal. "
             "Used with account 2110. Required by IAS 16.",
             {"semantic": "fixed_asset", "ifrs": "IAS_16_PPE"}),

            ("sub_cost_item",         "Cost Item (Статья затрат)",
             "Classify expenses by cost nature: salary, fuel, rent, utilities, depreciation. "
             "Used with expense accounts (7210, 7310) for cost breakdown analysis.",
             {"semantic": "cost_item", "accounts": "7210,7310,7410"}),

            ("sub_cash_flow",         "Cash Flow Item (Статьи движения ДС)",
             "Classify cash movements per IAS 7 categories. "
             "Used with bank accounts (1210) for indirect cash flow construction.",
             {"semantic": "cash_flow_item", "ifrs": "IAS_7_cash_flows"}),

            ("sub_vat_rate",          "VAT Rate (Ставки НДС)",
             "Track transactions by VAT rate: 18% standard, 0% zero-rated, exempt. "
             "Georgian VAT: 18% standard rate. Export: 0%. Used for VAT return preparation.",
             {"semantic": "vat_rate", "georgian_rate": "18%", "accounts": "3310,1810"}),

            ("sub_employee",          "Employee (Работники организации)",
             "Track advances, salary payable, and expense claims per employee. "
             "Used with payroll payable (3510) and advances (1410).",
             {"semantic": "employee", "accounts": "3510,1410"}),

            ("sub_other_income_exp",  "Other Income/Expense (Прочие доходы и расходы)",
             "Classify non-operating income/expense items: FX gain/loss, asset disposal, penalties. "
             "Required for full IFRS P&L presentation (IAS 1).",
             {"semantic": "other_income_expense", "ifrs": "IAS_1_presentation"}),

            ("sub_deferred_expense",  "Deferred Expense (Расходы будущих периодов)",
             "Track prepaid expenses that will be recognised in future periods. "
             "Used for insurance, maintenance contracts, rent prepayments. IAS 38 / IAS 37.",
             {"semantic": "deferred_expense", "ifrs": "IAS_37_38_provisions"}),
        ]

        for eid, label, desc, props in dimensions:
            entity = KnowledgeEntity(
                entity_id=f"onec_dim_{eid}",
                entity_type="onec_dimension",
                label_en=label,
                label_ka="",
                description=desc,
                properties={**props, "source": "1c_subkonto_taxonomy"},
            )
            self._add_entity(entity)

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _add_entity(self, entity: KnowledgeEntity) -> None:
        """Add entity to graph and update indexes."""
        self._entities[entity.entity_id] = entity
        if entity.entity_type not in self._index_by_type:
            self._index_by_type[entity.entity_type] = []
        self._index_by_type[entity.entity_type].append(entity.entity_id)

    def _score_entity(
        self,
        entity: KnowledgeEntity,
        query_lower: str,
        tokens: Set[str],
    ) -> float:
        """Score an entity's relevance to a query."""
        score = 0.0
        text = (
            f"{entity.label_en} {entity.label_ka} {entity.description} "
            + " ".join(str(v) for v in entity.properties.values())
        ).lower()

        # Exact substring match (highest weight)
        if query_lower in text:
            score += 5.0

        # Token overlap
        text_tokens = set(re.findall(r'[\w\u10A0-\u10FF]+', text))
        overlap = tokens & text_tokens
        if overlap:
            score += len(overlap) * 1.5

        # Account code match (very high for direct lookups)
        code = entity.properties.get("code", "")
        if code:
            for token in tokens:
                if token == code or code.startswith(token):
                    score += 10.0
                    break

        # Boost key_accounts and flows (more informative)
        if entity.entity_type in ("key_account", "flow"):
            score *= 1.3
        elif entity.entity_type == "correction":
            score *= 1.5  # User corrections are high-value

        return score


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

knowledge_graph = FinancialKnowledgeGraph()
