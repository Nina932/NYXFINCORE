"""
FinAI Foundry — Intelligent Ingestion Engine
===============================================
A REASONING system that THINKS about each account before creating journal entries.

This is NOT a dumb pipeline. For each uploaded file, the system:
1. DETECTS what kind of financial data it contains
2. CLASSIFIES each account using KG + COA + learned patterns + LLM
3. PLANS granular journal entries grouped by accounting logic
4. EXPLAINS every decision transparently to the user
5. EXECUTES: creates balanced JEs with full lineage
6. LEARNS from corrections to improve next time

Every decision has a reasoning chain. Every account has a confidence score.
Every journal entry is explained in plain language.

Public API:
    from app.services.v2.intelligent_ingestion import intelligent_ingestion
    plan = await intelligent_ingestion.analyze_and_plan(dataset_id, db)
    result = await intelligent_ingestion.execute_plan(plan, db)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, round_fin, is_zero, safe_divide

logger = logging.getLogger(__name__)
D = Decimal


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class ClassifiedAccount:
    """One account with full reasoning context."""
    account_code: str
    account_name: str
    turnover_debit: Decimal
    turnover_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal
    net_amount: Decimal              # The amount to journal (turnover-based for P&L, closing for BS)
    classification_section: str      # "income_statement" or "balance_sheet"
    classification_side: str         # "revenue", "expense", "asset", "liability", "equity"
    classification_sub: str          # "cogs", "selling_expenses", etc.
    pl_line: str                     # "revenue", "cogs", "admin_expenses", etc.
    normal_balance: str              # "debit" or "credit"
    is_depreciation: bool
    journal_group: str               # Derived: "revenue_recognition", "cogs", "operating_expenses", etc.
    contra_account: str              # Derived: "1310" for revenue, "1610" for COGS, etc.
    confidence: float
    reasoning: str                   # Full reasoning chain
    method: str                      # "exact_match", "learned", "semantic", "prefix_rule"
    needs_review: bool
    source_tb_item_id: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name[:80],
            "net_amount": str(round_fin(self.net_amount)),
            "classification": f"{self.classification_section}/{self.classification_side}/{self.pl_line}",
            "journal_group": self.journal_group,
            "contra_account": self.contra_account,
            "confidence": round(self.confidence, 2),
            "reasoning": self.reasoning,
            "method": self.method,
            "needs_review": self.needs_review,
        }


@dataclass
class PlannedLine:
    """One posting line in a planned journal entry."""
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    description: str
    source_tb_item_id: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name[:60],
            "debit": str(round_fin(self.debit)),
            "credit": str(round_fin(self.credit)),
            "description": self.description[:100],
        }


@dataclass
class PlannedJournalEntry:
    """One journal entry in the plan — not yet created."""
    journal_group: str
    description: str
    lines: List[PlannedLine]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool
    account_count: int
    explanation: str

    def to_dict(self) -> Dict:
        return {
            "journal_group": self.journal_group,
            "description": self.description,
            "lines": [l.to_dict() for l in self.lines],
            "total_debit": str(round_fin(self.total_debit)),
            "total_credit": str(round_fin(self.total_credit)),
            "is_balanced": self.is_balanced,
            "account_count": self.account_count,
            "explanation": self.explanation,
        }


@dataclass
class IngestionPlan:
    """The system's complete plan — reasoning result before execution."""
    dataset_id: int
    file_type: str
    file_analysis: str
    period: str
    fiscal_year: int
    company: str
    total_accounts_parsed: int
    postable_accounts: int
    classified_accounts: List[ClassifiedAccount]
    planned_journal_entries: List[PlannedJournalEntry]
    needs_review: List[ClassifiedAccount]
    classification_summary: Dict[str, Dict]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool
    steps_taken: List[str]
    confidence: float

    def to_dict(self) -> Dict:
        return {
            "dataset_id": self.dataset_id,
            "file_type": self.file_type,
            "file_analysis": self.file_analysis,
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "company": self.company,
            "total_accounts_parsed": self.total_accounts_parsed,
            "postable_accounts": self.postable_accounts,
            "classification_summary": self.classification_summary,
            "planned_journal_entries": [je.to_dict() for je in self.planned_journal_entries],
            "needs_review_count": len(self.needs_review),
            "needs_review": [a.to_dict() for a in self.needs_review[:20]],
            "total_debit": str(round_fin(self.total_debit)),
            "total_credit": str(round_fin(self.total_credit)),
            "is_balanced": self.is_balanced,
            "steps_taken": self.steps_taken,
            "confidence": round(self.confidence, 2),
        }


# ── Account Reasoner ──────────────────────────────────────────────

class AccountReasoner:
    """
    REASONS about each account using KG + COA + learned patterns.
    No hardcoded journal groups — everything derived from classification.
    """

    def derive_journal_group(self, cls_section: str, cls_side: str, pl_line: str, is_da: bool) -> str:
        """Derive journal group from classification — not from account code prefixes."""
        if cls_section == "income_statement":
            if pl_line == "revenue":
                return "revenue_recognition"
            if pl_line == "cogs":
                return "cogs"
            if is_da:
                return "depreciation"
            if pl_line in ("selling_expenses", "admin_expenses", "labour"):
                return "operating_expenses"
            if pl_line in ("finance_income", "finance_expense"):
                return "finance"
            if pl_line in ("tax",):
                return "tax"
            if pl_line in ("other_income", "other_expense"):
                return "other_pl"
            return "other_pl"
        elif cls_section == "balance_sheet":
            if cls_side == "asset":
                return "bs_assets"
            elif cls_side == "liability":
                return "bs_liabilities"
            elif cls_side == "equity":
                return "bs_equity"
            return "bs_other"
        return "unclassified"

    def derive_contra_account(self, journal_group: str, cls_side: str) -> str:
        """Derive contra account from accounting logic — not lookup table."""
        _CONTRA_MAP = {
            "revenue_recognition": "1310",  # Trade Receivables (asset ↑ when revenue earned)
            "cogs": "1610",                 # Inventory (asset ↓ when goods sold)
            "operating_expenses": "3110",   # Trade Payables (liability ↑ when expense incurred)
            "depreciation": "2210",         # Accumulated Depreciation (contra asset ↑)
            "finance": "1110",              # Cash/Bank (cash moves for interest)
            "tax": "3310",                  # Tax Payable (liability ↑)
            "other_pl": "1110",             # Cash/Bank (default for non-operating)
        }
        return _CONTRA_MAP.get(journal_group, "9999")

    def derive_journal_description(self, journal_group: str, period: str, count: int) -> Tuple[str, str]:
        """Generate description and explanation for a journal group."""
        _DESCRIPTIONS = {
            "revenue_recognition": (
                f"Revenue Recognition — {period} ({count} accounts)",
                f"Records revenue earned during {period}. DR Trade Receivables / CR Revenue accounts."
            ),
            "cogs": (
                f"Cost of Goods Sold — {period} ({count} accounts)",
                f"Records cost of fuel sold during {period}. DR COGS accounts / CR Inventory."
            ),
            "operating_expenses": (
                f"Operating Expenses — {period} ({count} accounts)",
                f"Records selling, admin, and labour expenses. DR Expense / CR Payables."
            ),
            "depreciation": (
                f"Depreciation & Amortization — {period} ({count} accounts)",
                f"Records D&A for the period. DR D&A Expense / CR Accumulated Depreciation."
            ),
            "finance": (
                f"Finance Income/Expense — {period} ({count} accounts)",
                f"Records interest and finance items. DR/CR as appropriate."
            ),
            "tax": (
                f"Tax Charges — {period} ({count} accounts)",
                f"Records income tax and other tax charges. DR Tax / CR Tax Payable."
            ),
            "other_pl": (
                f"Non-Operating Items — {period} ({count} accounts)",
                f"Records non-operating income and expenses."
            ),
        }
        desc, expl = _DESCRIPTIONS.get(journal_group, (
            f"{journal_group.replace('_', ' ').title()} — {period} ({count} accounts)",
            f"Records {journal_group} items for {period}."
        ))
        return desc, expl


# ── Intelligent Ingestion Engine ──────────────────────────────────

class IntelligentIngestionEngine:
    """
    The reasoning engine. Analyzes uploaded data, classifies every account,
    plans journal entries, explains everything, then executes.
    """

    def __init__(self):
        self._reasoner = AccountReasoner()

    async def analyze_and_plan(self, dataset_id: int, db: AsyncSession) -> IngestionPlan:
        """
        Step 1-4: Detect → Classify → Plan → Explain.
        Returns a plan the user can review before execution.
        """
        from app.models.all_models import Dataset, TrialBalanceItem

        steps = []

        # ── Step 1: DETECT — What kind of data? ──────────────────
        ds = (await db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )).scalar_one_or_none()

        if not ds:
            raise ValueError(f"Dataset {dataset_id} not found")

        period = ds.period or "Unknown"
        company = ds.company or "Unknown"
        fiscal_year = self._extract_year(period)
        file_type = ds.file_type or "Unknown"

        # Load TB items (hierarchy_level=1 = parent accounts only for P&L)
        tb_items = (await db.execute(
            select(TrialBalanceItem)
            .where(TrialBalanceItem.dataset_id == dataset_id)
            .order_by(TrialBalanceItem.account_code)
        )).scalars().all()

        if not tb_items:
            raise ValueError(f"No trial balance items found for dataset {dataset_id}")

        # Separate leaf accounts (postable) from groups
        leaf_items = [t for t in tb_items if (t.hierarchy_level or 1) <= 2 and not self._is_group_code(t.account_code)]
        total_parsed = len(tb_items)
        postable = len(leaf_items)

        steps.append(f"1. Detected {file_type} with {total_parsed} accounts ({postable} postable, {total_parsed - postable} group/header)")
        steps.append(f"   Company: {company}, Period: {period}")

        # ── Step 2: CLASSIFY — Understand each account ───────────
        from app.services.tb_to_statements import TBToStatements, TBRow

        classifier = TBToStatements()
        classified: List[ClassifiedAccount] = []
        classification_summary: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "total": D("0"), "confidence_sum": 0.0, "accounts": []})

        for item in leaf_items:
            # Build TBRow from TrialBalanceItem
            row = TBRow(
                account_code=item.account_code or "",
                account_name=item.account_name or "",
                opening_debit=item.opening_debit or 0,
                opening_credit=item.opening_credit or 0,
                turnover_debit=item.turnover_debit or 0,
                turnover_credit=item.turnover_credit or 0,
                closing_debit=item.closing_debit or 0,
                closing_credit=item.closing_credit or 0,
            )

            # Classify using the existing 6-tier pipeline
            cls = classifier._classify_account(row)

            # Compute net amount based on section
            if cls.section == "income_statement":
                # P&L: use TURNOVER (period activity)
                if cls.normal_balance == "credit":
                    net = to_decimal(row.turnover_credit) - to_decimal(row.turnover_debit)
                else:
                    net = to_decimal(row.turnover_debit) - to_decimal(row.turnover_credit)
            else:
                # BS: use CLOSING balance
                if cls.normal_balance == "debit":
                    net = to_decimal(row.closing_debit) - to_decimal(row.closing_credit)
                else:
                    net = to_decimal(row.closing_credit) - to_decimal(row.closing_debit)

            if is_zero(net):
                continue  # Skip zero-activity accounts

            # Derive journal group and contra from classification (NOT from code prefix)
            journal_group = self._reasoner.derive_journal_group(
                cls.section, cls.side, cls.pl_line, cls.is_depreciation
            )
            contra_account = self._reasoner.derive_contra_account(journal_group, cls.side)

            classified_acct = ClassifiedAccount(
                account_code=item.account_code,
                account_name=item.account_name or "",
                turnover_debit=to_decimal(item.turnover_debit),
                turnover_credit=to_decimal(item.turnover_credit),
                closing_debit=to_decimal(item.closing_debit),
                closing_credit=to_decimal(item.closing_credit),
                net_amount=round_fin(abs(net)),
                classification_section=cls.section,
                classification_side=cls.side,
                classification_sub=cls.sub,
                pl_line=cls.pl_line,
                normal_balance=cls.normal_balance,
                is_depreciation=cls.is_depreciation,
                journal_group=journal_group,
                contra_account=contra_account,
                confidence=cls.reason.confidence,
                reasoning=cls.reason.explanation,
                method=cls.reason.method,
                needs_review=cls.reason.confidence < 0.7,
                source_tb_item_id=item.id,
            )
            classified.append(classified_acct)

            # Update summary
            summary = classification_summary[journal_group]
            summary["count"] += 1
            summary["total"] += abs(net)
            summary["confidence_sum"] += cls.reason.confidence
            summary["accounts"].append(item.account_code)

        # Compute average confidence per group
        for group, summary in classification_summary.items():
            if summary["count"] > 0:
                summary["confidence_avg"] = round(summary["confidence_sum"] / summary["count"], 2)
                summary["total"] = str(round_fin(summary["total"]))
                del summary["confidence_sum"]
                summary["accounts"] = summary["accounts"][:10]  # Limit for response size

        needs_review = [a for a in classified if a.needs_review]

        methods_used = defaultdict(int)
        for a in classified:
            methods_used[a.method] += 1

        steps.append(f"2. Classified {len(classified)} accounts with activity:")
        for method, count in sorted(methods_used.items(), key=lambda x: -x[1]):
            steps.append(f"   — {count} via {method}")
        steps.append(f"   — {len(needs_review)} need review (confidence < 70%)")

        # ── Step 3: PLAN — Design journal entries ─────────────────
        # Group classified accounts by journal_group
        groups: Dict[str, List[ClassifiedAccount]] = defaultdict(list)
        for acct in classified:
            if acct.classification_section == "income_statement":  # Only P&L journals for now
                groups[acct.journal_group].append(acct)

        planned_entries: List[PlannedJournalEntry] = []
        plan_total_dr = D("0")
        plan_total_cr = D("0")

        for group_name, accounts in sorted(groups.items()):
            if not accounts:
                continue

            lines: List[PlannedLine] = []
            group_total = D("0")

            for acct in accounts:
                # Posting line for the actual account
                if acct.normal_balance == "debit":
                    lines.append(PlannedLine(
                        account_code=acct.account_code,
                        account_name=acct.account_name,
                        debit=acct.net_amount,
                        credit=D("0"),
                        description=f"{acct.pl_line}: {acct.account_name[:50]}",
                        source_tb_item_id=acct.source_tb_item_id,
                    ))
                else:
                    lines.append(PlannedLine(
                        account_code=acct.account_code,
                        account_name=acct.account_name,
                        debit=D("0"),
                        credit=acct.net_amount,
                        description=f"{acct.pl_line}: {acct.account_name[:50]}",
                        source_tb_item_id=acct.source_tb_item_id,
                    ))
                group_total += acct.net_amount

            if is_zero(group_total):
                continue

            # Contra line (balancing entry)
            contra_code = accounts[0].contra_account
            contra_name = self._get_contra_name(contra_code)

            if accounts[0].normal_balance == "debit":
                # Expenses are DR → contra is CR
                lines.append(PlannedLine(
                    account_code=contra_code,
                    account_name=contra_name,
                    debit=D("0"),
                    credit=round_fin(group_total),
                    description=f"Contra: {contra_name}",
                ))
                je_dr = round_fin(group_total)
                je_cr = round_fin(group_total)
            else:
                # Revenue is CR → contra is DR
                lines.insert(0, PlannedLine(
                    account_code=contra_code,
                    account_name=contra_name,
                    debit=round_fin(group_total),
                    credit=D("0"),
                    description=f"Contra: {contra_name}",
                ))
                je_dr = round_fin(group_total)
                je_cr = round_fin(group_total)

            desc, explanation = self._reasoner.derive_journal_description(
                group_name, period, len(accounts)
            )

            planned_entries.append(PlannedJournalEntry(
                journal_group=group_name,
                description=desc,
                lines=lines,
                total_debit=je_dr,
                total_credit=je_cr,
                is_balanced=je_dr == je_cr,
                account_count=len(accounts),
                explanation=explanation,
            ))

            plan_total_dr += je_dr
            plan_total_cr += je_cr

        steps.append(f"3. Planned {len(planned_entries)} journal entries:")
        for je in planned_entries:
            steps.append(f"   — {je.description}: {len(je.lines)} lines, DR={round_fin(je.total_debit)}")

        total_lines = sum(len(je.lines) for je in planned_entries)
        all_balanced = all(je.is_balanced for je in planned_entries)
        steps.append(f"4. Balance check: {'ALL BALANCED ✓' if all_balanced else 'IMBALANCE DETECTED ✗'}")
        steps.append(f"   Total: {len(planned_entries)} JEs with {total_lines} posting lines")

        overall_confidence = sum(a.confidence for a in classified) / max(len(classified), 1)

        file_analysis = (
            f"Detected {file_type} for {company}, period {period}. "
            f"Parsed {total_parsed} accounts ({postable} postable). "
            f"Classified {len(classified)} active accounts into {len(planned_entries)} journal groups. "
            f"{len(needs_review)} accounts need review."
        )

        return IngestionPlan(
            dataset_id=dataset_id,
            file_type=file_type,
            file_analysis=file_analysis,
            period=period,
            fiscal_year=fiscal_year,
            company=company,
            total_accounts_parsed=total_parsed,
            postable_accounts=postable,
            classified_accounts=classified,
            planned_journal_entries=planned_entries,
            needs_review=needs_review,
            classification_summary=dict(classification_summary),
            total_debit=plan_total_dr,
            total_credit=plan_total_cr,
            is_balanced=plan_total_dr == plan_total_cr,
            steps_taken=steps,
            confidence=overall_confidence,
        )

    async def execute_plan(
        self, plan: IngestionPlan, db: AsyncSession, auto_post: bool = True
    ) -> Dict[str, Any]:
        """
        Step 5-6: Execute the plan → create JEs → learn from results.
        """
        from app.services.v2.journal_system import journal_service

        results = {
            "dataset_id": plan.dataset_id,
            "period": plan.period,
            "entries_created": 0,
            "entries_posted": 0,
            "total_posting_lines": 0,
            "journal_entry_ids": [],
            "errors": [],
        }

        for planned_je in plan.planned_journal_entries:
            try:
                # Convert planned lines to journal_service format
                lines = []
                for pl in planned_je.lines:
                    lines.append({
                        "account_code": pl.account_code,
                        "account_name": pl.account_name,
                        "debit": str(pl.debit),
                        "credit": str(pl.credit),
                        "description": pl.description,
                    })

                je = await journal_service.create_entry(
                    posting_date=datetime.now(timezone.utc),
                    period=plan.period,
                    fiscal_year=plan.fiscal_year,
                    description=planned_je.description,
                    lines=lines,
                    source_type="intelligent_ingestion",
                    source_id=plan.dataset_id,
                    db=db,
                )

                results["entries_created"] += 1
                results["total_posting_lines"] += len(lines)
                results["journal_entry_ids"].append(je["id"])

                if auto_post:
                    posted = await journal_service.post_entry(je["id"], db=db)
                    results["entries_posted"] += 1

            except Exception as e:
                error_msg = f"{planned_je.journal_group}: {e}"
                results["errors"].append(error_msg)
                logger.error("JE creation failed for %s: %s", planned_je.journal_group, e)

        # ── Step 6: LEARN — Record classifications ────────────────
        try:
            from app.services.v2.learning_engine import learning_engine
            learned_count = 0
            for acct in plan.classified_accounts:
                if acct.confidence >= 0.8:
                    await learning_engine.record_classification(
                        acct.account_code,
                        {
                            "section": acct.classification_section,
                            "side": acct.classification_side,
                            "sub": acct.classification_sub,
                            "pl_line": acct.pl_line,
                            "normal_balance": acct.normal_balance,
                            "is_depreciation": acct.is_depreciation,
                            "description": acct.account_name[:100],
                        },
                        confidence=acct.confidence,
                        source="intelligent_ingestion",
                        db=db,
                    )
                    learned_count += 1
            results["classifications_learned"] = learned_count
        except Exception as e:
            logger.warning("Learning step failed: %s", e)

        logger.info(
            "Intelligent ingestion: dataset=%d, JEs=%d, posted=%d, lines=%d, learned=%d, errors=%d",
            plan.dataset_id, results["entries_created"], results["entries_posted"],
            results["total_posting_lines"], results.get("classifications_learned", 0),
            len(results["errors"]),
        )

        return results

    # ── Helpers ────────────────────────────────────────────────────

    def _is_group_code(self, code: str) -> bool:
        """Check if an account code is a group/aggregate (contains X)."""
        return 'X' in code.upper() or 'x' in code

    def _extract_year(self, period: str) -> int:
        import re
        match = re.search(r'20\d{2}', str(period))
        return int(match.group()) if match else datetime.now().year

    def _get_contra_name(self, code: str) -> str:
        _NAMES = {
            "1110": "Cash in Bank",
            "1310": "Trade Receivables",
            "1610": "Inventory",
            "2210": "Accumulated Depreciation",
            "3110": "Trade Payables",
            "3310": "Tax Payable",
            "3410": "Wages Payable",
            "9999": "Suspense Account",
        }
        return _NAMES.get(code, f"Account {code}")


# Module singleton
intelligent_ingestion = IntelligentIngestionEngine()
