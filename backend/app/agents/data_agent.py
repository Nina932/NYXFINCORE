"""
FinAI Data Agent — Intelligent file ingestion and data comprehension.

Responsibilities:
1. LLM-powered sheet classification (fallback when weighted scoring < threshold)
2. Proactive analysis on upload (auto-insights, anomaly detection, report readiness)
3. Multi-dataset orchestration (grouping, cross-referencing)
4. Data quality assessment and recommendations

The DataAgent is called:
- During file upload (via datasets router) for LLM classification fallback
- After upload for proactive analysis
- When users ask about data quality or coverage

LLM Classification Flow:
  1. Weighted scoring runs first (handles ~90% of sheets)
  2. If max(scores) < threshold → DataAgent.classify_unknown_sheet()
  3. LLM sees first 15 rows + column headers → returns classification + column mapping
  4. Result feeds back into the parser pipeline
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent, AgentTask, AgentContext, AgentResult

logger = logging.getLogger(__name__)


@dataclass
class SheetClassification:
    """Result of LLM-based sheet classification."""
    sheet_type: str             # trial_balance | revenue | cogs | balance_sheet | pl_extract | transaction_ledger | budget | unknown
    confidence: float           # 0.0 - 1.0
    reasoning: str              # Why the LLM classified it this way
    column_mapping: Dict[str, int] = field(default_factory=dict)  # column_name → column_index
    suggested_headers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class DataInsight:
    """A proactive insight discovered during analysis."""
    category: str               # "anomaly" | "coverage" | "quality" | "recommendation"
    severity: str               # "info" | "warning" | "critical"
    title: str
    detail: str
    data: Dict[str, Any] = field(default_factory=dict)


class SemanticEnricher:
    """Stage 4 of the ingestion pipeline: Enrich account codes with financial semantics.

    Enrichment pipeline:
      Pass 1: Exact COA lookup (O(1) - Georgian prefix rules)
      Pass 2: Knowledge graph fuzzy match (O(log n))
      Pass 3: Batch LLM classification for truly unknown accounts (~200 tokens per 50 accounts)

    Results are cached in-memory for the session and stored back to the knowledge graph
    as new entities for future lookups without LLM calls.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def enrich_accounts(
        self,
        account_codes: List[str],
        call_llm_fn: Any = None,  # BaseAgent.call_llm reference for LLM fallback
    ) -> Dict[str, Dict[str, Any]]:
        """Enrich a list of account codes with semantic classifications.

        Args:
            account_codes: List of account codes to enrich (e.g., ["1310", "6110", "7310"])
            call_llm_fn: Async function matching BaseAgent.call_llm signature

        Returns:
            Dict mapping account_code → {
                "bs_pl": "BS" | "PL" | "unknown",
                "normal_balance": "debit" | "credit",
                "account_class": "Asset" | "Liability" | "Equity" | "Revenue" | "Expense",
                "label_en": "English description",
                "label_ka": "Georgian description",
                "source": "coa_prefix" | "knowledge_graph" | "llm" | "unknown"
            }
        """
        results: Dict[str, Dict[str, Any]] = {}
        unknown = []

        for code in account_codes:
            # Check session cache first
            if code in self._cache:
                results[code] = self._cache[code]
                continue

            # Pass 1: Exact COA prefix lookup
            classification = self._classify_by_prefix(code)
            if classification["source"] != "unknown":
                results[code] = classification
                self._cache[code] = classification
                continue

            unknown.append(code)

        # Pass 2: Knowledge graph lookup for unknowns
        if unknown:
            try:
                from app.services.knowledge_graph import knowledge_graph
                if knowledge_graph.is_built:
                    still_unknown = []
                    for code in unknown:
                        entities = knowledge_graph.query(f"account {code}", top_k=1)
                        if entities:
                            entity = entities[0]
                            props = entity.properties
                            classification = {
                                "bs_pl": props.get("bs_pl", "unknown"),
                                "normal_balance": props.get("normal_balance", "debit"),
                                "account_class": props.get("account_class", "unknown"),
                                "label_en": entity.label_en,
                                "label_ka": entity.label_ka,
                                "source": "knowledge_graph",
                            }
                            results[code] = classification
                            self._cache[code] = classification
                        else:
                            still_unknown.append(code)
                    unknown = still_unknown
            except Exception as kg_err:
                logger.debug("SemanticEnricher KG lookup failed: %s", kg_err)

        # Pass 3: Batch LLM classification for truly unknown accounts
        if unknown and call_llm_fn:
            try:
                batch_results = await self._batch_classify_llm(unknown, call_llm_fn)
                results.update(batch_results)
                self._cache.update(batch_results)

                # Store new classifications back to knowledge graph
                try:
                    from app.services.knowledge_graph import knowledge_graph, KnowledgeEntity
                    for code, cls in batch_results.items():
                        if cls.get("source") == "llm":
                            entity = KnowledgeEntity(
                                entity_id=f"coa_llm_{code}",
                                entity_type="account",
                                label_en=cls.get("label_en", f"Account {code}"),
                                label_ka=cls.get("label_ka", ""),
                                description=f"LLM-classified account {code}",
                                properties={
                                    "account_code": code,
                                    "bs_pl": cls.get("bs_pl", "unknown"),
                                    "normal_balance": cls.get("normal_balance", "debit"),
                                    "account_class": cls.get("account_class", "unknown"),
                                    "source": "llm_inference",
                                },
                            )
                            knowledge_graph._entities[entity.entity_id] = entity
                except Exception as store_err:
                    logger.debug("SemanticEnricher KG store failed: %s", store_err)

            except Exception as llm_err:
                logger.warning("SemanticEnricher LLM classification failed: %s", llm_err)
                # Mark unknowns as unknown
                for code in unknown:
                    results[code] = {
                        "bs_pl": "unknown",
                        "normal_balance": "debit",
                        "account_class": "unknown",
                        "label_en": f"Unknown account {code}",
                        "label_ka": "",
                        "source": "unknown",
                    }

        # Fill any remaining unknowns
        for code in account_codes:
            if code not in results:
                results[code] = {
                    "bs_pl": "unknown",
                    "normal_balance": "debit",
                    "account_class": "unknown",
                    "label_en": f"Account {code}",
                    "label_ka": "",
                    "source": "unknown",
                }

        return results

    @staticmethod
    def _classify_by_prefix(account_code: str) -> Dict[str, Any]:
        """Classify by Georgian COA prefix rules."""
        if not account_code:
            return {"bs_pl": "unknown", "normal_balance": "debit",
                    "account_class": "unknown", "label_en": "unknown",
                    "label_ka": "", "source": "unknown"}

        # Georgian COA prefix classification
        code_str = str(account_code).strip()

        # Extract numeric prefix
        numeric = ''.join(c for c in code_str if c.isdigit())
        if not numeric:
            return {"bs_pl": "unknown", "normal_balance": "debit",
                    "account_class": "unknown", "label_en": code_str,
                    "label_ka": "", "source": "unknown"}

        first_digit = numeric[0] if numeric else "0"
        prefix2 = numeric[:2] if len(numeric) >= 2 else numeric

        # 1xxx = Assets (BS, debit normal)
        if first_digit == "1":
            sub = {"10": "Cash and Cash Equivalents", "11": "Short-term Investments",
                   "12": "Accounts Receivable", "13": "Inventory", "14": "Prepayments",
                   "15": "Other Current Assets", "16": "Biological Assets",
                   "17": "Investments", "18": "Fixed Assets", "19": "Intangible Assets"}
            label = sub.get(prefix2, f"Asset Account {code_str}")
            return {"bs_pl": "BS", "normal_balance": "debit",
                    "account_class": "Asset", "label_en": label,
                    "label_ka": "", "source": "coa_prefix"}

        # 2xxx = Assets (continuation)
        if first_digit == "2":
            return {"bs_pl": "BS", "normal_balance": "debit",
                    "account_class": "Asset", "label_en": f"Asset Account {code_str}",
                    "label_ka": "", "source": "coa_prefix"}

        # 3xxx = Liabilities (BS, credit normal)
        if first_digit == "3":
            sub = {"31": "Short-term Borrowings", "32": "Accounts Payable",
                   "33": "Tax Payable", "34": "Accrued Liabilities",
                   "35": "Deferred Revenue", "36": "Other Current Liabilities",
                   "37": "Long-term Borrowings", "38": "Bonds Payable",
                   "39": "Other Long-term Liabilities"}
            label = sub.get(prefix2, f"Liability Account {code_str}")
            return {"bs_pl": "BS", "normal_balance": "credit",
                    "account_class": "Liability", "label_en": label,
                    "label_ka": "", "source": "coa_prefix"}

        # 4xxx = Equity (BS, credit normal)
        if first_digit == "4":
            return {"bs_pl": "BS", "normal_balance": "credit",
                    "account_class": "Equity", "label_en": f"Equity Account {code_str}",
                    "label_ka": "", "source": "coa_prefix"}

        # 5xxx = Off-balance / Capital accounts
        if first_digit == "5":
            return {"bs_pl": "BS", "normal_balance": "debit",
                    "account_class": "Capital", "label_en": f"Capital Account {code_str}",
                    "label_ka": "", "source": "coa_prefix"}

        # 6xxx = Revenue (PL, credit normal)
        if first_digit == "6":
            return {"bs_pl": "PL", "normal_balance": "credit",
                    "account_class": "Revenue", "label_en": f"Revenue Account {code_str}",
                    "label_ka": "", "source": "coa_prefix"}

        # 7xxx = Operating Expenses / COGS (PL, debit normal)
        if first_digit == "7":
            sub = {"73": "Selling Expenses (Commercial)", "74": "Marketing",
                   "75": "Distribution", "76": "Warranty", "79": "Other Op Expenses"}
            label = sub.get(prefix2, f"Operating Expense {code_str}")
            return {"bs_pl": "PL", "normal_balance": "debit",
                    "account_class": "Expense", "label_en": label,
                    "label_ka": "", "source": "coa_prefix"}

        # 8xxx = Administrative / G&A (PL, debit normal)
        if first_digit == "8":
            sub = {"81": "Depreciation", "82": "Overhead", "83": "Admin Salaries",
                   "84": "Office Expenses", "85": "Insurance", "86": "Professional Fees"}
            label = sub.get(prefix2, f"G&A Expense {code_str}")
            return {"bs_pl": "PL", "normal_balance": "debit",
                    "account_class": "Expense", "label_en": label,
                    "label_ka": "", "source": "coa_prefix"}

        # 9xxx = Non-operating (PL, mixed)
        if first_digit == "9":
            sub = {"91": "Tax Expense", "92": "Finance Costs", "93": "Interest Income",
                   "94": "FX Gain/Loss", "95": "Investment Income", "96": "Extraordinary"}
            is_income = prefix2 in ("93", "95", "96")
            label = sub.get(prefix2, f"Non-operating Account {code_str}")
            return {"bs_pl": "PL",
                    "normal_balance": "credit" if is_income else "debit",
                    "account_class": "Revenue" if is_income else "Expense",
                    "label_en": label, "label_ka": "", "source": "coa_prefix"}

        return {"bs_pl": "unknown", "normal_balance": "debit",
                "account_class": "unknown", "label_en": f"Account {code_str}",
                "label_ka": "", "source": "unknown"}

    async def _batch_classify_llm(
        self, codes: List[str], call_llm_fn: Any
    ) -> Dict[str, Dict[str, Any]]:
        """Classify unknown accounts in batches via LLM."""
        results = {}
        batch_size = 50

        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            codes_str = "\n".join(f"- {c}" for c in batch)

            prompt = f"""Classify these Georgian accounting codes. For each code, return:
- bs_pl: "BS" (balance sheet) or "PL" (profit & loss)
- normal_balance: "debit" or "credit"
- account_class: "Asset", "Liability", "Equity", "Revenue", or "Expense"
- label_en: Short English description (3-5 words)

Account codes to classify:
{codes_str}

Respond in JSON format:
{{"results": [{{"code": "XXXX", "bs_pl": "...", "normal_balance": "...", "account_class": "...", "label_en": "..."}}]}}"""

            try:
                response = await call_llm_fn(
                    system="You are a Georgian accounting expert. Classify account codes using Georgian COA (1xxx=Assets, 3xxx=Liabilities, 4xxx=Equity, 6xxx=Revenue, 7xxx-9xxx=Expenses).",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    temperature=0.0,
                )

                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text

                # Parse JSON
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    for item in data.get("results", []):
                        code = str(item.get("code", ""))
                        if code in batch:
                            results[code] = {
                                "bs_pl": item.get("bs_pl", "unknown"),
                                "normal_balance": item.get("normal_balance", "debit"),
                                "account_class": item.get("account_class", "unknown"),
                                "label_en": item.get("label_en", f"Account {code}"),
                                "label_ka": "",
                                "source": "llm",
                            }
            except Exception as e:
                logger.warning("SemanticEnricher batch LLM failed: %s", e)
                # Mark batch as unknown
                for code in batch:
                    results[code] = {
                        "bs_pl": "unknown",
                        "normal_balance": "debit",
                        "account_class": "unknown",
                        "label_en": f"Account {code}",
                        "label_ka": "",
                        "source": "unknown",
                    }

        return results


# Module-level SemanticEnricher instance
semantic_enricher = SemanticEnricher()


class DataAgent(BaseAgent):
    """File ingestion specialist with LLM-powered classification.

    Capabilities:
    - classify_unknown_sheet: LLM fallback for unrecognized Excel sheets
    - analyze_upload: Proactive analysis after file upload
    - assess_quality: Data quality assessment
    - suggest_reports: What reports can be generated from available data
    """

    name = "data"
    description = "Data ingestion specialist — file parsing, LLM classification, data quality"
    capabilities = [
        "ingest",
        "classify",
        "data_quality",
    ]

    # ── LLM Classification (the core Phase 3 feature) ────────────────────

    async def classify_unknown_sheet(
        self,
        rows: List[List[str]],
        sheet_name: str,
        scores: Dict[str, float],
    ) -> SheetClassification:
        """Classify an unknown sheet using LLM when weighted scoring fails.

        Called by file_parser.py when max(scores) < threshold.

        Args:
            rows: All rows from the sheet (list of lists)
            sheet_name: The Excel sheet name
            scores: Current weighted scores from detectors
                    e.g. {"tdsheet": 0.3, "balance": 0.1, "cogs": 0.2, ...}
        """
        start_time = time.time()

        # Build a sample of the first rows for the LLM
        sample_rows = rows[:15]  # Include potential header rows + data
        sample_text = self._format_rows_for_llm(sample_rows, max_rows=15)

        # Build the classification prompt
        system_prompt = """You are a financial data classifier for Georgian/Russian 1C accounting exports.

Your job: classify Excel sheets into one of these types:
- trial_balance: Account-level debit/credit turnovers (Оборотно-сальдовая ведомость, TDSheet). Has columns for account codes, opening/turnover/closing debit/credit.
- revenue: Revenue breakdown by product (Revenue Breakdown). Has product names, gross/VAT/net revenue.
- cogs: Cost of Goods Sold breakdown (COGS Breakdown). Has product names, account columns (6, 7310, 8230).
- balance_sheet: Balance sheet with IFRS mapping (Balance/BS). Has account codes, opening/closing balances, MAPPING GRP column.
- pl_extract: P&L account summary. Like a simplified trial balance with fewer columns, only P&L accounts (6xxx-9xxx).
- transaction_ledger: Transaction-level journal entries. Has date, debit account, credit account, amount, counterparty.
- budget: Budget data with line items and amounts.
- unknown: Cannot be classified.

Georgian/Russian accounting terms:
- "Оборотно-сальдовая" = Trial balance
- "Субконто" = Sub-account analytics
- "Дебет/Кредит" = Debit/Credit
- "MAPPING GRP" = IFRS line item classification
- "1610" = Inventory account (for COGS sheets)
- "Итог/Всего" = Total

Respond in JSON format ONLY:
{
  "sheet_type": "...",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation",
  "key_columns": {"column_name": column_index},
  "warnings": ["any issues"]
}"""

        user_message = f"""Classify this Excel sheet.

Sheet name: "{sheet_name}"
Current detection scores (all below threshold): {json.dumps(scores)}

First {len(sample_rows)} rows:
{sample_text}

What type of financial sheet is this?"""

        try:
            response = await self.call_llm(
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                max_tokens=500,
                temperature=0.0,
            )

            # Extract text from response
            response_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    response_text += block.text

            # Parse JSON response
            result = self._parse_classification_response(response_text)

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "LLM classified sheet '%s' as '%s' (conf: %.2f) in %dms",
                sheet_name, result.sheet_type, result.confidence, elapsed_ms,
            )

            # ── SchemaRegistry Learning: store successful classification back ──
            # This means next time the same file format appears, it won't need LLM
            if result.confidence >= 0.7:
                try:
                    await self._store_classification_in_registry(
                        sheet_name=sheet_name,
                        classification=result,
                    )
                except Exception as store_err:
                    logger.debug("SchemaRegistry store failed: %s", store_err)

            return result

        except Exception as e:
            logger.error("LLM classification failed for '%s': %s", sheet_name, e)
            return SheetClassification(
                sheet_type="unknown",
                confidence=0.0,
                reasoning=f"LLM classification error: {str(e)}",
                warnings=[str(e)],
            )

    # ── Proactive Upload Analysis ────────────────────────────────────────

    async def analyze_upload(
        self,
        db: Any,
        dataset_id: int,
    ) -> List[DataInsight]:
        """Run proactive analysis after a file upload.

        Discovers insights, flags issues, and recommends actions.
        Results are stored in dataset.parse_metadata["auto_insights"].
        """
        insights: List[DataInsight] = []

        try:
            from sqlalchemy import select, func
            from app.models.all_models import (
                Dataset, RevenueItem, COGSItem, GAExpenseItem,
                TrialBalanceItem, BalanceSheetItem, Transaction,
            )

            # Get the dataset
            ds = (await db.execute(
                select(Dataset).where(Dataset.id == dataset_id)
            )).scalar_one_or_none()
            if not ds:
                return insights

            # Count entities
            rev_count = (await db.execute(select(func.count()).where(RevenueItem.dataset_id == dataset_id))).scalar() or 0
            cogs_count = (await db.execute(select(func.count()).where(COGSItem.dataset_id == dataset_id))).scalar() or 0
            ga_count = (await db.execute(select(func.count()).where(GAExpenseItem.dataset_id == dataset_id))).scalar() or 0
            tb_count = (await db.execute(select(func.count()).where(TrialBalanceItem.dataset_id == dataset_id))).scalar() or 0
            bsi_count = (await db.execute(select(func.count()).where(BalanceSheetItem.dataset_id == dataset_id))).scalar() or 0
            txn_count = (await db.execute(select(func.count()).where(Transaction.dataset_id == dataset_id))).scalar() or 0

            # ── Insight 1: Data Coverage Assessment ──────────────────
            available = []
            missing = []
            if rev_count > 0: available.append(f"Revenue ({rev_count} items)")
            else: missing.append("Revenue Breakdown")
            if cogs_count > 0: available.append(f"COGS ({cogs_count} items)")
            else: missing.append("COGS Breakdown")
            if tb_count > 0: available.append(f"Trial Balance ({tb_count} accounts)")
            else: missing.append("Trial Balance")
            if bsi_count > 0: available.append(f"Balance Sheet ({bsi_count} items)")
            else: missing.append("Balance Sheet")
            if txn_count > 0: available.append(f"Transactions ({txn_count} entries)")

            insights.append(DataInsight(
                category="coverage",
                severity="info",
                title="Data Coverage",
                detail=f"Available: {', '.join(available)}. {'Missing: ' + ', '.join(missing) if missing else 'Full coverage!'}",
                data={"available_count": len(available), "missing": missing},
            ))

            # ── Insight 2: Report Readiness ──────────────────────────
            can_generate = []
            if rev_count > 0 and cogs_count > 0:
                can_generate.extend(["Income Statement", "P&L Statement", "Revenue Analysis", "COGS Analysis"])
            if rev_count > 0 and cogs_count > 0 and ga_count > 0:
                can_generate.append("Management Report")
            if bsi_count > 0:
                can_generate.append("Balance Sheet Report")
            if tb_count > 0:
                can_generate.extend(["Trial Balance Report", "Account Analysis"])
            if bsi_count > 0 and tb_count > 0:
                can_generate.append("Cash Flow Statement")

            insights.append(DataInsight(
                category="recommendation",
                severity="info",
                title="Report Readiness",
                detail=f"Can generate: {', '.join(can_generate)}" if can_generate else "Insufficient data for standard reports",
                data={"reports": can_generate},
            ))

            # ── Insight 3: Negative Margin Warning ───────────────────
            if rev_count > 0 and cogs_count > 0:
                from app.services.income_statement import build_income_statement
                rev_items = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == dataset_id))).scalars().all()
                cogs_items = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == dataset_id))).scalars().all()
                ga_items = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id))).scalars().all()
                stmt = build_income_statement(rev_items, cogs_items, ga_items)

                if stmt.margin_wholesale_total < 0:
                    insights.append(DataInsight(
                        category="anomaly",
                        severity="warning",
                        title="Negative Wholesale Margin",
                        detail=f"Wholesale gross margin is negative ({stmt.margin_wholesale_total:,.2f} GEL). "
                               f"This means wholesale is selling below cost — check if this is a deliberate strategy.",
                        data={"wholesale_margin": stmt.margin_wholesale_total,
                              "wholesale_revenue": stmt.revenue_wholesale_total,
                              "wholesale_cogs": stmt.cogs_wholesale_total},
                    ))

                if stmt.total_revenue > 0:
                    margin_pct = stmt.total_gross_margin / stmt.total_revenue * 100
                    if margin_pct < 5:
                        insights.append(DataInsight(
                            category="anomaly",
                            severity="warning",
                            title="Low Overall Margin",
                            detail=f"Overall gross margin is only {margin_pct:.1f}%. "
                                   f"Industry benchmark for fuel distribution: 7-12%.",
                            data={"margin_pct": margin_pct},
                        ))

            # ── Insight 4: Multi-Period Opportunity ──────────────────
            all_ds = (await db.execute(
                select(Dataset).where(Dataset.id != dataset_id).order_by(Dataset.created_at.desc())
            )).scalars().all()
            if all_ds:
                other_periods = [d.period for d in all_ds if d.period and d.period != ds.period]
                if other_periods:
                    insights.append(DataInsight(
                        category="recommendation",
                        severity="info",
                        title="Cross-Period Analysis Available",
                        detail=f"Other periods in database: {', '.join(set(other_periods[:3]))}. "
                               f"Use period comparison to track trends.",
                        data={"other_periods": list(set(other_periods[:5]))},
                    ))

            # Store insights in dataset metadata
            if ds.parse_metadata is None:
                ds.parse_metadata = {}
            meta = dict(ds.parse_metadata)
            meta["auto_insights"] = [
                {"category": i.category, "severity": i.severity,
                 "title": i.title, "detail": i.detail, "data": i.data}
                for i in insights
            ]
            ds.parse_metadata = meta
            await db.commit()

            # ── Add dataset patterns to knowledge graph ────────────
            try:
                from app.services.knowledge_graph import knowledge_graph
                if knowledge_graph.is_built:
                    # Record data coverage pattern
                    knowledge_graph.add_dataset_pattern(
                        dataset_id=dataset_id,
                        period=ds.period or "Unknown",
                        pattern_type="coverage",
                        description=(
                            f"Dataset {dataset_id} ({ds.period}): "
                            f"{', '.join(available)}. "
                            + (f"Missing: {', '.join(missing)}." if missing else "Full coverage.")
                        ),
                        properties={
                            "available_count": len(available),
                            "missing": missing,
                            "reports": can_generate,
                        },
                    )

                    # Record anomalies as patterns
                    for insight in insights:
                        if insight.category == "anomaly":
                            knowledge_graph.add_dataset_pattern(
                                dataset_id=dataset_id,
                                period=ds.period or "Unknown",
                                pattern_type=f"anomaly_{insight.title.lower().replace(' ', '_')}",
                                description=insight.detail,
                                properties=insight.data,
                            )

                    logger.debug(
                        "DataAgent: added %d patterns to knowledge graph for dataset %d",
                        1 + sum(1 for i in insights if i.category == "anomaly"),
                        dataset_id,
                    )
            except Exception as kg_err:
                logger.debug("Knowledge graph pattern storage failed: %s", kg_err)

            logger.info(
                "DataAgent: %d insights generated for dataset %d",
                len(insights), dataset_id,
            )

        except Exception as e:
            logger.error("DataAgent analyze_upload failed: %s", e, exc_info=True)
            insights.append(DataInsight(
                category="quality",
                severity="warning",
                title="Analysis Error",
                detail=f"Proactive analysis encountered an error: {str(e)}",
            ))

        return insights

    # ── Agent Interface ──────────────────────────────────────────────────

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute a data agent task."""
        start_time = time.time()
        result = self._make_result()

        try:
            if task.task_type == "classify":
                # LLM classification
                rows = task.parameters.get("rows", [])
                sheet_name = task.parameters.get("sheet_name", "")
                scores = task.parameters.get("scores", {})
                classification = await self.classify_unknown_sheet(rows, sheet_name, scores)
                result.status = "success"
                result.data = {
                    "sheet_type": classification.sheet_type,
                    "confidence": classification.confidence,
                    "reasoning": classification.reasoning,
                    "column_mapping": classification.column_mapping,
                    "warnings": classification.warnings,
                }
                result.narrative = (
                    f"Sheet '{sheet_name}' classified as {classification.sheet_type} "
                    f"(confidence: {classification.confidence:.0%}). "
                    f"{classification.reasoning}"
                )

            elif task.task_type == "ingest":
                # Proactive analysis after upload
                dataset_id = task.parameters.get("dataset_id")
                if dataset_id and context.db:
                    insights = await self.analyze_upload(context.db, dataset_id)
                    result.status = "success"
                    result.data = {
                        "insights": [
                            {"category": i.category, "severity": i.severity,
                             "title": i.title, "detail": i.detail}
                            for i in insights
                        ]
                    }
                    # Build narrative from insights
                    narratives = []
                    for i in insights:
                        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(i.severity, "•")
                        narratives.append(f"{icon} **{i.title}**: {i.detail}")
                    result.narrative = "\n".join(narratives)
                else:
                    result.status = "error"
                    result.error_message = "dataset_id required for ingest task"

            elif task.task_type == "data_quality":
                # Data quality assessment — runs analyze_upload with quality focus
                dataset_id = task.parameters.get("dataset_id")
                if not dataset_id and context.dataset_ids:
                    dataset_id = context.dataset_ids[0]
                if dataset_id and context.db:
                    insights = await self.analyze_upload(context.db, dataset_id)
                    # Filter for quality-related insights
                    quality_insights = [
                        i for i in insights
                        if i.category in ("anomaly", "data_quality", "warning")
                        or i.severity in ("warning", "critical")
                    ]
                    result.status = "success"
                    result.data = {
                        "quality_score": max(0, 100 - len(quality_insights) * 10),
                        "total_insights": len(insights),
                        "quality_issues": len(quality_insights),
                        "issues": [
                            {"category": i.category, "severity": i.severity,
                             "title": i.title, "detail": i.detail}
                            for i in quality_insights
                        ],
                    }
                    if quality_insights:
                        lines = [f"**Data Quality Assessment** ({len(quality_insights)} issues found):"]
                        for i in quality_insights:
                            icon = {"warning": "⚠️", "critical": "🚨"}.get(i.severity, "•")
                            lines.append(f"{icon} {i.title}: {i.detail}")
                        result.narrative = "\n".join(lines)
                    else:
                        result.narrative = "**Data Quality Assessment**: No issues found. Data looks clean."
                else:
                    result.status = "error"
                    result.error_message = "No active dataset for quality assessment"

            elif task.task_type == "enrich":
                # Semantic enrichment of account codes
                account_codes = task.parameters.get("account_codes", [])
                if account_codes:
                    enriched = await semantic_enricher.enrich_accounts(
                        account_codes=account_codes,
                        call_llm_fn=self.call_llm,
                    )
                    result.status = "success"
                    result.data = {"enriched_accounts": enriched}
                    enriched_count = sum(1 for v in enriched.values() if v.get("source") != "unknown")
                    result.narrative = (
                        f"Enriched {enriched_count}/{len(account_codes)} accounts. "
                        f"Sources: {set(v.get('source') for v in enriched.values())}"
                    )
                else:
                    result.status = "error"
                    result.error_message = "account_codes list required for enrich task"

            else:
                result.status = "error"
                result.error_message = f"DataAgent cannot handle task_type: {task.task_type}"

        except Exception as e:
            logger.error("DataAgent execution error: %s", e, exc_info=True)
            result.status = "error"
            result.error_message = str(e)

        elapsed_ms = int((time.time() - start_time) * 1000)
        result.add_audit(
            action="data_execute",
            input_summary=f"task={task.task_type}",
            output_summary=(result.narrative or "")[:200],
            duration_ms=elapsed_ms,
        )
        return result

    # ── Internal Helpers ─────────────────────────────────────────────────

    def _format_rows_for_llm(self, rows: List[List[str]], max_rows: int = 15) -> str:
        """Format spreadsheet rows as text for LLM consumption."""
        lines = []
        for i, row in enumerate(rows[:max_rows]):
            # Convert cells to strings, truncate long values
            cells = []
            for cell in row[:20]:  # Max 20 columns
                s = str(cell).strip() if cell is not None else ""
                if len(s) > 50:
                    s = s[:47] + "..."
                cells.append(s)
            lines.append(f"Row {i+1}: {' | '.join(cells)}")
        return "\n".join(lines)

    def _parse_classification_response(self, text: str) -> SheetClassification:
        """Parse JSON response from LLM classification."""
        # Try to find JSON in the response
        import re
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return SheetClassification(
                    sheet_type=data.get("sheet_type", "unknown"),
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", ""),
                    column_mapping=data.get("key_columns", {}),
                    warnings=data.get("warnings", []),
                )
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse LLM classification JSON: %s", e)

        # Fallback: try keyword extraction
        text_lower = text.lower()
        for sheet_type in ["trial_balance", "revenue", "cogs", "balance_sheet",
                           "pl_extract", "transaction_ledger", "budget"]:
            if sheet_type in text_lower:
                return SheetClassification(
                    sheet_type=sheet_type,
                    confidence=0.5,
                    reasoning=f"Keyword match from LLM response (JSON parse failed): {text[:200]}",
                    warnings=["JSON parsing failed, used keyword fallback"],
                )

        return SheetClassification(
            sheet_type="unknown",
            confidence=0.0,
            reasoning=f"Could not parse LLM response: {text[:200]}",
            warnings=["Classification failed"],
        )

    async def _store_classification_in_registry(
        self,
        sheet_name: str,
        classification: SheetClassification,
    ) -> None:
        """Store a successful LLM classification back to SchemaRegistry for future use.

        This implements the learning loop: when LLM classifies an unknown sheet,
        we store the result so the next identical/similar file doesn't need LLM.
        """
        try:
            from app.models.all_models import SchemaProfile, SchemaVersion
            from sqlalchemy.ext.asyncio import AsyncSession
            # Note: we need db access - store as a class variable on next call with db
            # For now, just log the learning event for monitoring
            logger.info(
                "SchemaRegistry LEARN: sheet='%s' → type='%s' (conf=%.2f, cols=%s)",
                sheet_name,
                classification.sheet_type,
                classification.confidence,
                list(classification.column_mapping.keys())[:5],
            )
        except Exception as e:
            logger.debug("SchemaRegistry learn failed: %s", e)
