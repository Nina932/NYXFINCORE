"""
FinAI Analytics Router — field names match Transaction/RevenueItem/BudgetLine models
All queries use: Transaction.type (not txn_type), RevenueItem.net (not net_amount)
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.database import get_db
from app.models.all_models import Transaction, RevenueItem, BudgetLine, Dataset, COGSItem, GAExpenseItem, BalanceSheetItem, TrialBalanceItem, DataLineage
from app.services.income_statement import build_income_statement
from app.services.v2.decimal_utils import to_decimal, round_fin
import json as _json
import logging
import os
from app.services.file_parser import parse_file
from app.config import settings

# Helper: drop-in replacement for float() on financial values
_d = lambda v: float(to_decimal(v))  # Returns float for backward compat with JSON serialization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def fgel(v):
    if v is None: return "—"
    if abs(v) >= 1e6: return f"₾{v/1e6:.3f}M"
    if abs(v) >= 1e3: return f"₾{v/1e3:.1f}K"
    return f"₾{v:.2f}"


def _extract_special_items(ga_items):
    """Extract finance/tax/labour from special GAExpenseItem entries stored from TDSheet.

    De-duplication: if the GA table has BOTH marker entries (FINANCE_EXPENSE) AND
    explicit account items (82xx), skip the markers to avoid double-counting.
    This handles data parsed by older versions of the parser that accumulated
    8220→FINANCE_EXPENSE while also storing 8220 as individual line items.
    """
    fin_inc = 0.0
    fin_exp = 0.0
    tax_exp = 0.0
    labour = 0.0

    # Detect whether explicit account items exist for each marker category
    has_explicit_82xx = False  # Non-operating expenses (8220, 8230)
    has_explicit_81xx = False  # Non-operating income (8110)
    has_explicit_92xx = False  # Tax/other P&L (9210)
    for g in ga_items:
        code = getattr(g, 'account_code', '') or ''
        if code.startswith('82') or code.startswith('83'):
            has_explicit_82xx = True
        if code.startswith('81') or code.startswith('NOI:'):
            has_explicit_81xx = True
        if code.startswith('92'):
            has_explicit_92xx = True

    for g in ga_items:
        code = getattr(g, 'account_code', '') or ''
        amt = _d(getattr(g, 'amount', 0) or 0)
        if code == 'FINANCE_INCOME':
            # Skip if explicit 81xx items exist (they'll be routed by build_income_statement)
            if not has_explicit_81xx:
                fin_inc += amt
        elif code == 'FINANCE_EXPENSE':
            # Skip if explicit 82xx items exist (they'll be routed by build_income_statement)
            if not has_explicit_82xx:
                fin_exp += amt
        elif code == 'TAX_EXPENSE':
            if not has_explicit_92xx:
                tax_exp += amt
        elif code == 'LABOUR_COSTS':
            labour += amt
    return fin_inc, fin_exp, tax_exp, labour


# ═══════════════════════════════════════════════════════════════════
# TRANSPARENCY LAYER — methodology cards, data quality, pipeline
# ═══════════════════════════════════════════════════════════════════

async def _build_transparency(ds_id: int, db: AsyncSession, flow_type: str,
                               sources: dict = None, reconciliation: dict = None) -> dict:
    """Build standard transparency metadata block (methodology + data_quality + sources + pipeline).
    Follows the COGS gold-standard pattern for all report pages."""
    from app.services.file_parser import map_coa
    transparency = {}

    # 1. Methodology — flow explanation
    try:
        from app.services.accounting_intelligence import AccountingIntelligence
        ai = AccountingIntelligence()
        transparency["methodology"] = ai.explain_financial_flow(flow_type)
    except Exception:
        transparency["methodology"] = {"title": flow_type, "description": ""}

    # 2. Data Quality — COA coverage from TB items
    data_quality = {"total_tb_accounts": 0, "mapped_accounts": 0, "unmapped_accounts": 0,
                    "coverage_pct": 100.0, "confidence_level": "high",
                    "confidence_label": "High", "confidence_label_ka": "მაღალი"}
    if ds_id:
        try:
            tb_items = (await db.execute(
                select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == ds_id)
            )).scalars().all()
            seen_codes = set()
            mapped_count = 0
            for t in tb_items:
                code = (t.account_code or "").strip()
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    if map_coa(code) is not None:
                        mapped_count += 1
            total = len(seen_codes)
            cov = round(mapped_count / total * 100, 1) if total else 100.0
            data_quality = {
                "total_tb_accounts": total,
                "mapped_accounts": mapped_count,
                "unmapped_accounts": total - mapped_count,
                "coverage_pct": cov,
                "confidence_level": "high" if cov >= 95 else "medium" if cov >= 80 else "low",
                "confidence_label": "High" if cov >= 95 else "Medium" if cov >= 80 else "Low",
                "confidence_label_ka": "მაღალი" if cov >= 95 else "საშუალო" if cov >= 80 else "დაბალი",
            }
        except Exception:
            pass
    transparency["data_quality"] = data_quality

    # 3. Sources — passed in per endpoint
    transparency["sources"] = sources or {}

    # 4. Pipeline — from Dataset.parse_metadata
    transparency["pipeline"] = []
    if ds_id:
        try:
            ds = (await db.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one_or_none()
            if ds and ds.parse_metadata:
                meta = ds.parse_metadata if isinstance(ds.parse_metadata, dict) else _json.loads(ds.parse_metadata)
                transparency["pipeline"] = meta.get("processing_pipeline", [])
        except Exception:
            pass

    # 5. Reconciliation — optional
    if reconciliation:
        transparency["reconciliation"] = reconciliation

    return transparency


@router.get("/lineage")
async def get_lineage(
    entity_type: str = Query(..., description="transaction|revenue_item|cogs_item|ga_expense"),
    entity_id: int = Query(...),
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Query DataLineage records for drill-down traceability."""
    q = select(DataLineage).where(
        DataLineage.entity_type == entity_type,
        DataLineage.entity_id == entity_id,
    )
    if dataset_id:
        q = q.where(DataLineage.dataset_id == dataset_id)
    result = await db.execute(q)
    records = result.scalars().all()
    return {"lineage": [r.to_dict() for r in records]}


@router.get("/lineage/by-account")
async def get_lineage_by_account(
    account_code: str = Query(...),
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get DataLineage records for a given account code."""
    q = select(DataLineage)
    if dataset_id:
        q = q.where(DataLineage.dataset_id == dataset_id)
    q = q.where(DataLineage.classification_rule.contains(account_code))
    result = await db.execute(q)
    records = result.scalars().all()
    return {"lineage": [r.to_dict() for r in records], "account_code": account_code}


@router.get("/dashboard")
async def get_dashboard(dataset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """Full dashboard KPIs and chart data matching frontend dashboard layout."""
    ds_id = await _resolve_dataset_id(dataset_id, db, context="dashboard")

    def ds_filter(q, model):
        return q.where(model.dataset_id == ds_id) if ds_id else q

    # Build Income Statement from active dataset for all KPIs
    rev_items = (await db.execute(ds_filter(select(RevenueItem), RevenueItem))).scalars().all()
    cogs_items = (await db.execute(ds_filter(select(COGSItem), COGSItem))).scalars().all()
    ga_items = (await db.execute(ds_filter(select(GAExpenseItem), GAExpenseItem))).scalars().all()

    # Extract special finance/tax items from GAExpenseItem (stored from TDSheet)
    fin_inc, fin_exp, tax_exp, labour = _extract_special_items(ga_items)

    stmt = build_income_statement(rev_items, cogs_items, ga_items,
                                  finance_income=fin_inc, finance_expense=fin_exp,
                                  tax_expense=tax_exp, labour_costs=labour)
    rev_net = stmt.total_revenue
    rev_gross = sum(_d(getattr(r, 'gross', 0) or 0) for r in rev_items)

    # Budget for comparison
    q_bud = select(BudgetLine)
    if ds_id:
        q_bud = q_bud.where(BudgetLine.dataset_id == ds_id)
    bud_result = await db.execute(q_bud)
    budget = {b.line_item: b.actual_amount if b.actual_amount is not None else b.budget_amount for b in bud_result.scalars().all()}
    bud_rev = budget.get("Revenue", 0)
    rev_vs_bud_pct = (rev_net - bud_rev) / bud_rev * 100 if bud_rev else 0

    # Expenses — prefer G&A + D&A from income statement, fallback to transaction total
    exp_total_txn = (await db.execute(ds_filter(
        select(func.sum(Transaction.amount)).where(Transaction.type == "Expense"), Transaction))).scalar() or 0
    exp_count = (await db.execute(ds_filter(
        select(func.count()).where(Transaction.type == "Expense"), Transaction))).scalar() or 0
    # Use G&A+D&A from parsed TDSheet if available (transaction-based may be 0)
    exp_total = (stmt.ga_expenses + stmt.da_expenses) if (stmt.ga_expenses + stmt.da_expenses) > 0 else exp_total_txn

    # Revenue by segment — use category (from product classifier) for consistency
    # with Income Statement KPIs. Map detailed categories to main segments.
    segments = {}
    for r in rev_items:
        cat = getattr(r, 'category', None) or 'Other Revenue'
        if 'Whsale' in cat:
            seg_key = 'Revenue Wholesale'
        elif 'Retial' in cat:
            seg_key = 'Revenue Retail'
        else:
            seg_key = 'Other Revenue'
        segments[seg_key] = segments.get(seg_key, 0) + _d(getattr(r, 'net', 0) or 0)
    segments = {k: round(v, 2) for k, v in sorted(segments.items(), key=lambda x: -x[1])}

    # Top expense categories
    cat_result = await db.execute(ds_filter(
        select(Transaction.cost_class, func.sum(Transaction.amount))
        .where(Transaction.type == "Expense")
        .group_by(Transaction.cost_class)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(10), Transaction))
    top_categories = [{"category": r[0] or "Other", "amount": round(r[1] or 0, 2)} for r in cat_result]

    # Top departments
    dept_result = await db.execute(ds_filter(
        select(Transaction.dept, func.sum(Transaction.amount))
        .where(Transaction.type == "Expense")
        .where(Transaction.dept.isnot(None))
        .where(Transaction.dept != "#N/A")
        .group_by(Transaction.dept)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(8), Transaction))
    top_departments = [{"dept": r[0], "amount": round(r[1] or 0, 2)} for r in dept_result]

    # Build alerts from actual data
    alerts = []
    if stmt.margin_wholesale_total < 0:
        alerts.append({"severity":"critical","message":f"Wholesale gross margin NEGATIVE: {fgel(stmt.margin_wholesale_total)}","action":"Review wholesale pricing strategy immediately"})
    if bud_rev and rev_net < bud_rev:
        alerts.append({"severity":"warning","message":f"Revenue below budget by {fgel(bud_rev - rev_net)} ({abs(rev_vs_bud_pct):.1f}%)","action":"Investigate shortfall by product segment"})

    # COGS ↔ TB reconciliation alert (PRIMARY: Breakdown vs TB 71xx)
    try:
        cogs_total_db = sum(_d(c.total_cogs or 0) for c in (await db.execute(select(COGSItem).where(COGSItem.dataset_id == ds_id))).scalars().all())
        if cogs_total_db > 0:
            tb_items_all = (await db.execute(select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == ds_id))).scalars().all()
            tb_71xx = sum(_d(t.turnover_debit or 0) for t in tb_items_all
                         if t.account_code and t.account_code.startswith('71') and (t.hierarchy_level or 0) == 1)
            # Primary check: COGS Breakdown vs TB 71xx (both measure actual COGS)
            if tb_71xx > 0:
                var_pct = abs(cogs_total_db - tb_71xx) / max(cogs_total_db, tb_71xx) * 100
                if var_pct >= 2:
                    alerts.append({
                        "severity": "critical" if var_pct >= 5 else "warning",
                        "message": f"COGS reconciliation variance: {var_pct:.1f}% — Breakdown ({fgel(cogs_total_db)}) vs TB 71xx ({fgel(tb_71xx)})",
                        "action": "Cross-check COGS Breakdown against Trial Balance 71xx accounts"
                    })
    except Exception as e:
        logger.warning(f"COGS reconciliation alert skipped: {e}")

    # ── Transparency ──
    transparency = await _build_transparency(ds_id, db, "dashboard_kpis",
        sources={
            "net_revenue": "RevenueItem.net (Revenue Breakdown sheet, 6xxx accounts)",
            "cogs": "COGSItem.total_cogs (COGS Breakdown sheet, 71xx accounts)",
            "gross_margin": "Revenue − COGS (calculated)",
            "ga_expenses": "GAExpenseItem.amount (TDSheet, 73xx+74xx accounts)",
            "ebitda": "Gross Profit − G&A − D&A (calculated)",
            "budget": "BudgetLine records (Mapping sheet)",
        })

    return {
        "kpis": {
            "net_revenue":       round(rev_net, 2),
            "gross_revenue":     round(rev_gross, 2),
            "cogs":              round(stmt.total_cogs, 2),
            "gross_margin":      round(stmt.total_gross_margin, 2),
            "gross_margin_pct":  round(stmt.total_gross_margin / rev_net * 100, 2) if rev_net else 0,
            "total_opex":        round(exp_total, 2),
            "opex_count":        exp_count,
            "retail_revenue":    round(stmt.revenue_retail_total, 2),
            "retail_margin":     round(stmt.margin_retail_total, 2),
            "wholesale_revenue": round(stmt.revenue_wholesale_total, 2),
            "wholesale_margin":  round(stmt.margin_wholesale_total, 2),
            "budget_revenue":    round(bud_rev, 2),
            "rev_vs_budget_pct": round(rev_vs_bud_pct, 2),
            "ga_expenses":       round(stmt.ga_expenses, 2),
            "ebitda":            round(stmt.ebitda, 2),
            "total_gross_profit": round(stmt.total_gross_profit, 2),
        },
        "charts": {
            "revenue_by_segment": segments,
            "top_categories":     top_categories,
            "top_departments":    top_departments,
        },
        "alerts": alerts,
        "transparency": transparency,
    }


@router.get("/transactions")
async def get_transactions(
    type:         Optional[str] = None,     # Expense | Income | Transfer
    dept:         Optional[str] = None,
    category:     Optional[str] = None,
    counterparty: Optional[str] = None,
    min_amount:   Optional[float] = None,
    max_amount:   Optional[float] = None,
    search:       Optional[str] = None,
    dataset_id:   Optional[int] = None,
    period:       Optional[str] = None,
    limit: int    = Query(default=500, le=2000),
    offset: int   = 0,
    db: AsyncSession = Depends(get_db)
):
    """Filter and paginate transactions. Uses Transaction.type field (not txn_type)."""
    ds_id = await _resolve_dataset_id(dataset_id, db)
    q = select(Transaction)
    if ds_id:        q = q.where(Transaction.dataset_id == ds_id)
    if type:         q = q.where(Transaction.type == type)
    if dept:         q = q.where(Transaction.dept.ilike(f"%{dept}%"))
    if category:     q = q.where(Transaction.cost_class.ilike(f"%{category}%"))
    if counterparty: q = q.where(Transaction.counterparty.ilike(f"%{counterparty}%"))
    if min_amount is not None: q = q.where(Transaction.amount >= min_amount)
    if max_amount is not None: q = q.where(Transaction.amount <= max_amount)
    if search:       q = q.where(
        Transaction.dept.ilike(f"%{search}%") |
        Transaction.counterparty.ilike(f"%{search}%") |
        Transaction.cost_class.ilike(f"%{search}%"))
    if period:       q = q.where(Transaction.period == period)

    total_count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result      = await db.execute(q.order_by(Transaction.amount.desc()).offset(offset).limit(limit))
    txns        = result.scalars().all()

    return {
        "total": total_count, "offset": offset, "limit": limit,
        "transactions": [t.to_dict() for t in txns]
    }


@router.get("/trial-balance")
async def get_trial_balance(
    dataset_id: Optional[int] = None,
    search: Optional[str] = None,
    account_class: Optional[str] = None,
    hierarchy_level: Optional[int] = None,
    sort_by: Optional[str] = "id",
    sort_dir: Optional[str] = "asc",
    limit: int = 2000,
    db: AsyncSession = Depends(get_db),
):
    """Trial Balance data with search, filter, sort."""
    ds_id = await _resolve_dataset_id(dataset_id, db, context="tb")
    q = select(TrialBalanceItem)
    if ds_id:
        q = q.where(TrialBalanceItem.dataset_id == ds_id)
    if account_class:
        q = q.where(TrialBalanceItem.account_class == account_class)
    if hierarchy_level is not None:
        q = q.where(TrialBalanceItem.hierarchy_level == hierarchy_level)
    else:
        # CRITICAL FIX: Only use hierarchy_level=1 (parent accounts) by default.
        # Georgian 1C COA uses hierarchical rollup:
        #   Level 1: Parent accounts with FULL balance (e.g., 1610 = ₾100M)
        #   Level 2: Child sub-movements (already INCLUDED in parent balance)
        #   Level 3: Counterparty/sub-account detail (already in level 2)
        # Including level 2 alongside level 1 causes DOUBLE-COUNTING.
        # Previous bug: summing levels 1+2 inflated TB by ₾189M.
        q = q.where(TrialBalanceItem.hierarchy_level == 1)
    if search:
        # When searching, include all levels so users can find sub-account detail
        q = select(TrialBalanceItem)
        if ds_id:
            q = q.where(TrialBalanceItem.dataset_id == ds_id)
        if account_class:
            q = q.where(TrialBalanceItem.account_class == account_class)
        q = q.where(
            TrialBalanceItem.account_code.ilike(f"%{search}%") |
            TrialBalanceItem.account_name.ilike(f"%{search}%") |
            TrialBalanceItem.sub_account_detail.ilike(f"%{search}%")
        )

    # Sorting
    SORT_COLS = {
        "id": TrialBalanceItem.id,
        "account_code": TrialBalanceItem.account_code,
        "account_name": TrialBalanceItem.account_name,
        "opening_debit": TrialBalanceItem.opening_debit,
        "opening_credit": TrialBalanceItem.opening_credit,
        "turnover_debit": TrialBalanceItem.turnover_debit,
        "turnover_credit": TrialBalanceItem.turnover_credit,
        "closing_debit": TrialBalanceItem.closing_debit,
        "closing_credit": TrialBalanceItem.closing_credit,
        "net_pl_impact": TrialBalanceItem.net_pl_impact,
        "account_class": TrialBalanceItem.account_class,
        "hierarchy_level": TrialBalanceItem.hierarchy_level,
    }
    sort_col = SORT_COLS.get(sort_by, TrialBalanceItem.account_code)
    if sort_dir == "desc":
        sort_col = sort_col.desc()

    result = await db.execute(q.order_by(sort_col).limit(limit))
    items = result.scalars().all()

    total_debit = sum(i.turnover_debit or 0 for i in items)
    total_credit = sum(i.turnover_credit or 0 for i in items)
    classes = sorted(set(i.account_class or "" for i in items if i.account_class))

    # ── Transparency ──
    transparency = await _build_transparency(ds_id, db, "balance_sheet_structure",
        sources={
            "data_source": "TDSheet (Trial Balance / ТДЛист)",
            "records": f"{len(items)} TB line items across classes {', '.join(classes)}",
        })

    # ── Mapping Intelligence — enrich each item with COA mapping info ──
    from app.services.financial_intelligence import AccountMapper
    enriched_items = []
    for i in items:
        item_dict = i.to_dict()
        code = (i.account_code or "").strip()
        if code:
            mapping = AccountMapper.map_with_trace(code)
            item_dict["mapping_info"] = mapping.to_dict()
        else:
            item_dict["mapping_info"] = {
                "matched_prefix": "",
                "ifrs_line": "",
                "confidence": 0.0,
                "trace": "No account code",
                "source": "unmapped",
            }
        enriched_items.append(item_dict)

    return {
        "total": len(items),
        "items": enriched_items,
        "summary": {
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "classes": classes,
        },
        "transparency": transparency,
    }


@router.get("/revenue")
async def get_revenue(segment: Optional[str] = None, dataset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """Revenue breakdown with English product names and category organization."""
    from app.services.file_parser import get_english_name
    ds_id = await _resolve_dataset_id(dataset_id, db, context="revenue")
    q = select(RevenueItem).order_by(RevenueItem.net.desc())
    if segment:    q = q.where(RevenueItem.segment.ilike(f"%{segment}%"))
    if ds_id:      q = q.where(RevenueItem.dataset_id == ds_id)
    result = await db.execute(q)
    items  = result.scalars().all()
    total_net   = sum(r.net   or 0 for r in items)
    total_gross = sum(r.gross or 0 for r in items)
    segs = {}
    by_category = {}
    for r in items:
        segs[r.segment or "Other"] = segs.get(r.segment or "Other", 0) + (r.net or 0)
        cat = r.category or "Other Revenue"
        if cat not in by_category:
            by_category[cat] = {"category": cat, "products": [], "total": 0}
        by_category[cat]["products"].append({
            **r.to_dict(),
            "product_en": get_english_name(r.product),
            "pct_of_total": round(r.net/total_net*100, 2) if total_net else 0,
        })
        by_category[cat]["total"] += (r.net or 0)
    # Sort categories and round totals
    organized = sorted(by_category.values(), key=lambda x: -x["total"])
    for cat in organized:
        cat["total"] = round(cat["total"], 2)
    # ── Transparency ──
    # Revenue reconciliation: compare sheet total vs TB 6xxx if possible
    rev_reconciliation = None
    if ds_id and total_net > 0:
        try:
            tb_items_rev = (await db.execute(
                select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == ds_id)
            )).scalars().all()
            tb_6xxx_credit = sum(_d(t.turnover_credit or 0) for t in tb_items_rev
                                 if t.account_code and t.account_code.startswith('6')
                                 and (t.hierarchy_level or 0) == 1
                                 and not t.account_code.startswith('612'))
            tb_6120_debit = sum(_d(t.turnover_debit or 0) for t in tb_items_rev
                                if t.account_code and t.account_code.startswith('612')
                                and (t.hierarchy_level or 0) == 1)
            tb_net_rev = tb_6xxx_credit - tb_6120_debit
            if tb_net_rev > 0:
                var_pct = abs(total_net - tb_net_rev) / max(total_net, tb_net_rev) * 100
                rev_reconciliation = {
                    "check": "Revenue Sheet vs TB 6xxx",
                    "revenue_sheet_net": round(total_net, 2),
                    "tb_6xxx_net": round(tb_net_rev, 2),
                    "variance_pct": round(var_pct, 2),
                    "status": "match" if var_pct < 2 else "warning" if var_pct < 5 else "mismatch",
                }
        except Exception:
            pass
    transparency = await _build_transparency(ds_id, db, "revenue_recognition",
        sources={
            "data_source": "Revenue Breakdown Sheet" if items else "TB-Derived (6xxx accounts)",
            "product_count": len(items),
            "segments": list(segs.keys()),
        },
        reconciliation=rev_reconciliation)

    return {
        "totals":   {"gross": round(total_gross,2), "net": round(total_net,2), "vat": round(total_gross-total_net,2)},
        "segments": {k: round(v,2) for k,v in sorted(segs.items(), key=lambda x:-x[1])},
        "by_category": organized,
        "products": [{**r.to_dict(), "product_en": get_english_name(r.product), "pct_of_total": round(r.net/total_net*100,2) if total_net else 0} for r in items],
        "transparency": transparency,
    }


@router.get("/costs")
async def get_costs(dataset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """
    Cost/OpEx breakdown — hybrid approach:
    1. COA account codes for top-level financial classification (G&A accounts)
    2. Semantic layer for proper cost_class categorization within each G&A account
    3. Filters out non-operating items (FX, CapEx, VAT) from true OpEx
    """
    from app.services.file_parser import map_coa, GA_ACCOUNT_CODES, GA_ACCOUNT_NAMES
    from app.services.semantic_layer import classify_cost_class as sem_classify

    ds_id = await _resolve_dataset_id(dataset_id, db)
    q = select(Transaction).where(Transaction.type == "Expense")
    if ds_id: q = q.where(Transaction.dataset_id == ds_id)
    result = await db.execute(q)
    txns = result.scalars().all()

    # Also fetch G&A items for the dedicated G&A account section
    q_ga = select(GAExpenseItem)
    if ds_id: q_ga = q_ga.where(GAExpenseItem.dataset_id == ds_id)
    ga_items = (await db.execute(q_ga)).scalars().all()
    ga_total = sum(_d(g.amount or 0) for g in ga_items)

    # ── Semantic cost_class classification ─────────────────────────
    # Within each G&A account, classify using cost_class text into proper buckets
    # Non-OpEx labels that should be separated from operating expenses
    NON_OPEX_COST_CLASSES = {"fx", "fixed additions", "vat", "no need"}

    SEMANTIC_CATEGORIES = {
        # cost_class label → (display_name, financial_type)
        # financial_type: "opex" | "finance" | "da" | "non_opex" | "labour"
        "fx":                           ("Foreign Exchange",           "non_opex"),
        "finance costs":                ("Finance Costs",              "finance"),
        "salary expense":               ("Salary Expense",             "labour"),
        "depreciation and amortization":("Depreciation & Amortization","da"),
        "no need":                      ("Unclassified (No Need)",     "non_opex"),
        "other telecommunication":      ("Telecommunications",         "opex"),
        "fixed additions":              ("Capital Expenditure",        "non_opex"),
        "vat":                          ("VAT (Tax Pass-through)",     "non_opex"),
        "staff training":               ("Staff Training",             "opex"),
        "consulting":                   ("Consulting",                 "opex"),
        "consulting cost":              ("Consulting",                 "opex"),
        "business trip":                ("Business Travel",            "opex"),
        "fuel":                         ("Fuel (Operational)",         "opex"),
        "pension":                      ("Pension Contributions",      "labour"),
        "mobile communication":         ("Mobile Communication",       "opex"),
        "marketing":                    ("Marketing & PR",             "opex"),
        "household materials":          ("Household Materials",        "opex"),
        "security expense":             ("Security",                   "opex"),
        "membership cost":              ("Memberships & Subscriptions","opex"),
        "internet/tv/fixed":            ("Internet & Fixed Lines",     "opex"),
        "representative":               ("Representative Expenses",    "opex"),
        "medical insurance":            ("Medical Insurance",          "labour"),
        "it inventory":                 ("IT Equipment",               "opex"),
        "registration/notary":          ("Legal & Registration",       "opex"),
        "service":                      ("Services",                   "opex"),
        "stationary goods":             ("Office Supplies",            "opex"),
        "rent":                         ("Rent",                       "opex"),
        "bank commissions":             ("Bank Commissions",           "finance"),
        "other g&a":                    ("Other G&A",                  "opex"),
    }

    # Buckets
    opex_items = {}     # True operating expenses
    labour_items = {}   # Personnel-related (salary, pension, insurance)
    da_items = {}       # Depreciation & Amortization
    finance_items = {}  # Finance costs (below EBITDA)
    non_opex_items = {} # Non-operating (FX, CapEx, VAT)
    depts = {}

    total_all = 0.0
    total_true_opex = 0.0

    for t in txns:
        amt = abs(_d(t.amount or 0))
        if amt == 0:
            continue
        total_all += amt

        cost_cls = str(t.cost_class or "").strip()
        cost_cls_lower = cost_cls.lower()
        dept = str(t.dept or "").strip()

        # Classify by cost_class using semantic map
        if cost_cls_lower in SEMANTIC_CATEGORIES:
            display_name, fin_type = SEMANTIC_CATEGORIES[cost_cls_lower]
        else:
            # Fallback: use semantic layer NLP analysis
            sem_result = sem_classify(cost_cls)
            if sem_result:
                pl_line = sem_result["pl_line"]
                sub = sem_result.get("sub", "")
                if pl_line == "DA":
                    display_name = cost_cls or "Depreciation"
                    fin_type = "da"
                elif pl_line == "Finance":
                    display_name = cost_cls or "Finance"
                    fin_type = "finance"
                elif sub == "Labour":
                    display_name = cost_cls or "Personnel"
                    fin_type = "labour"
                else:
                    display_name = cost_cls or "Other Operating"
                    fin_type = "opex"
            else:
                display_name = cost_cls if cost_cls and cost_cls_lower not in ("0", "???", "-", "") else "Unclassified"
                fin_type = "opex"

        # Route to bucket
        bucket = opex_items
        if fin_type == "labour":
            bucket = labour_items
            total_true_opex += amt
        elif fin_type == "da":
            bucket = da_items
            total_true_opex += amt
        elif fin_type == "finance":
            bucket = finance_items
        elif fin_type == "non_opex":
            bucket = non_opex_items
        else:
            total_true_opex += amt

        if display_name not in bucket:
            bucket[display_name] = {"amount": 0, "count": 0}
        bucket[display_name]["amount"] += amt
        bucket[display_name]["count"] += 1

        # Department tracking (only for true OpEx + labour + DA)
        if fin_type in ("opex", "labour", "da") and dept and dept not in ("#N/A", "Unknown", "0", "???", ""):
            depts[dept] = depts.get(dept, 0) + amt

    # ── Build G&A section from dedicated table ────────────────────
    ga_breakdown = []
    for g in ga_items:
        ga_breakdown.append({
            "account_code": g.account_code,
            "account_name": g.account_name or f"G&A ({g.account_code})",
            "amount": round(_d(g.amount or 0), 2),
        })
    ga_breakdown.sort(key=lambda x: x["amount"], reverse=True)

    # ── Format output ─────────────────────────────────────────────
    def _to_list(d, total_ref):
        return sorted(
            [{"category": k, "amount": round(v["amount"], 2),
              "pct": round(v["amount"] / total_ref * 100, 2) if total_ref else 0,
              "count": v["count"]}
             for k, v in d.items()],
            key=lambda x: x["amount"], reverse=True
        )

    # ── TDSheet-derived cost data (when no transactions) ──────────
    tb_cost_breakdown = []
    if not txns and ds_id:
        # Query TrialBalanceItem for expense accounts (72xx-92xx)
        q_tb = select(TrialBalanceItem).where(
            TrialBalanceItem.dataset_id == ds_id,
            TrialBalanceItem.account_class >= 7,
            TrialBalanceItem.account_class <= 9,
        )
        tb_items = (await db.execute(q_tb)).scalars().all()

        # Deduplicate: only leaf-level accounts
        tb_by_code = {}
        for item in tb_items:
            code = item.account_code or ''
            amt = abs(_d(item.turnover_debit or 0))
            if amt > 10:
                tb_by_code[code] = {
                    'code': code,
                    'name': item.account_name or '',
                    'amount': amt,
                    'class': item.account_class,
                }
        # Remove parent accounts
        all_codes = sorted(tb_by_code.keys())
        leaf_codes = set(all_codes)
        for code in all_codes:
            for other in all_codes:
                if other != code and other.startswith(code + '.'):
                    leaf_codes.discard(code)
                    break
        for code in sorted(leaf_codes):
            entry = tb_by_code[code]
            tb_cost_breakdown.append({
                "account_code": entry['code'],
                "account_name": entry['name'],
                "amount": round(entry['amount'], 2),
                "account_class": entry['class'],
            })
        tb_cost_breakdown.sort(key=lambda x: x["amount"], reverse=True)

        # Update totals from TB data
        if not ga_items:
            ga_total = sum(e['amount'] for e in tb_cost_breakdown if e['account_class'] in (7, 8))
        total_true_opex = ga_total

    # ── Transparency ──
    data_src = "Trial Balance (TDSheet)" if tb_cost_breakdown else "Transaction ledger"
    transparency = await _build_transparency(ds_id, db, "opex_classification",
        sources={
            "data_source": data_src,
            "ga_source": "GAExpenseItem records (TDSheet 73xx+74xx accounts)",
            "classification": "Semantic layer + COA account codes",
        })

    return {
        "total_opex": round(total_true_opex, 2),
        "total_all_expenses": round(total_all, 2),
        "transaction_count": len(txns),
        "ga_total": round(ga_total, 2),
        "ga_breakdown": ga_breakdown,
        "tb_cost_breakdown": tb_cost_breakdown,
        "by_category": _to_list(opex_items, total_true_opex),
        "labour_items": _to_list(labour_items, total_true_opex),
        "da_items": _to_list(da_items, total_true_opex),
        "finance_items": _to_list(finance_items, total_all),
        "non_opex_items": _to_list(non_opex_items, total_all),
        "by_department": sorted(
            [{"dept": k, "amount": round(v, 2),
              "pct": round(v / total_true_opex * 100, 2) if total_true_opex else 0}
             for k, v in depts.items()],
            key=lambda x: x["amount"], reverse=True),
        "data_source": data_src,
        "transparency": transparency,
    }


@router.get("/cogs")
async def get_cogs(
    dataset_id: Optional[int] = None,
    segment: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    period: Optional[str] = None,
    sort_by: Optional[str] = Query(default="total_cogs"),
    sort_dir: Optional[str] = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
):
    """Enhanced COGS breakdown with filtering, search, reconciliation, and flow explanation."""
    from app.services.file_parser import get_english_name
    from app.services.accounting_intelligence import accounting_intelligence

    ds_id = await _resolve_dataset_id(dataset_id, db, context="cogs")

    # Build filtered query
    q = select(COGSItem)
    if ds_id:
        q = q.where(COGSItem.dataset_id == ds_id)
    if segment:
        q = q.where(COGSItem.segment.ilike(f"%{segment}%"))
    if category:
        q = q.where(COGSItem.category.ilike(f"%{category}%"))
    # NOTE: search is applied post-query to also match English translated names
    if period:
        q = q.where(COGSItem.period.ilike(f"%{period}%"))

    # Sorting
    sort_col = getattr(COGSItem, sort_by, COGSItem.total_cogs)
    q = q.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    result = await db.execute(q)
    items = result.scalars().all()

    # Post-query search: match both Georgian product name AND English translation
    if search:
        search_lower = search.lower()
        filtered = []
        for c in items:
            georgian_name = (c.product or '').lower()
            english_name = get_english_name(c.product).lower()
            cat_name = (c.category or '').lower()
            if (search_lower in georgian_name or search_lower in english_name
                    or search_lower in cat_name):
                filtered.append(c)
        items = filtered

    total_cogs = 0.0
    wholesale_total = 0.0
    retail_total = 0.0
    by_segment = {}
    by_category = {}
    products = []

    for c in items:
        total = _d(c.total_cogs or 0)
        col6 = _d(c.col6_amount or 0)
        col7310 = _d(c.col7310_amount or 0)
        col8230 = _d(c.col8230_amount or 0)
        total_cogs += total
        seg = c.segment or 'Other'
        cat = c.category or 'Other COGS'
        by_segment[seg] = by_segment.get(seg, 0) + total

        if 'wholesale' in seg.lower() or 'whsale' in seg.lower():
            wholesale_total += total
        elif 'retail' in seg.lower() or 'retial' in seg.lower():
            retail_total += total

        if cat not in by_category:
            by_category[cat] = {"category": cat, "products": [], "total": 0}
        prod_data = {
            "product": c.product,
            "product_en": get_english_name(c.product),
            "segment": seg,
            "category": cat,
            "col6_amount": round(col6, 2),
            "col7310_amount": round(col7310, 2),
            "col8230_amount": round(col8230, 2),
            "total_cogs": round(total, 2),
            "pct_of_total": 0,
        }
        by_category[cat]["products"].append(prod_data)
        by_category[cat]["total"] += total
        products.append(prod_data)

    for p in products:
        p["pct_of_total"] = round(p["total_cogs"] / total_cogs * 100, 2) if total_cogs else 0

    organized = sorted(by_category.values(), key=lambda x: -x["total"])
    for cat in organized:
        cat["total"] = round(cat["total"], 2)
        cat["products"].sort(key=lambda x: -x["total_cogs"])

    # ── COGS ↔ Inventory Reconciliation ──────────────────────────────
    reconciliation = {"checks": [], "has_mismatch": False, "sources": {}}
    if ds_id and total_cogs > 0:
        try:
            tb_all = (await db.execute(select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == ds_id))).scalars().all()
            tb_71xx = sum(_d(t.turnover_debit or 0) for t in tb_all
                         if t.account_code and t.account_code.startswith('71') and (t.hierarchy_level or 0) == 1)
            inv_16xx = sum(_d(t.turnover_credit or 0) for t in tb_all
                          if t.account_code and t.account_code == '1610' and (t.hierarchy_level or 0) == 1)

            reconciliation["sources"] = {
                "cogs_breakdown_total": round(total_cogs, 2),
                "total_cogs_tb": round(tb_71xx, 2),
                "total_inventory_credit_tb": round(inv_16xx, 2),
            }

            if total_cogs > 0 and tb_71xx > 0:
                var = abs(total_cogs - tb_71xx)
                pct = (var / max(total_cogs, tb_71xx)) * 100
                reconciliation["checks"].append({
                    "check": "COGS Breakdown vs TB 71xx", "check_ka": "COGS Breakdown vs ბრუნვა 71xx",
                    "source_a": {"label": "COGS Breakdown Sheet", "label_ka": "COGS Breakdown ფურცელი", "value": round(total_cogs, 2)},
                    "source_b": {"label": "TB 71xx Debit", "label_ka": "ბრუნვა 71xx დებეტი", "value": round(tb_71xx, 2)},
                    "variance": round(var, 2), "variance_pct": round(pct, 2),
                    "severity": "info" if pct < 2 else "warning" if pct < 5 else "critical",
                    "status": "match" if pct < 2 else "mismatch",
                })

            if total_cogs > 0 and inv_16xx > 0:
                cogs_pct = (total_cogs / inv_16xx) * 100
                internal_transfers = round(inv_16xx - total_cogs, 2)
                reconciliation["checks"].append({
                    "check": "1610 Inventory Movement", "check_ka": "1610 მარაგის მოძრაობა",
                    "source_a": {"label": "COGS (actual sales)", "label_ka": "COGS (რეალური გაყიდვა)", "value": round(total_cogs, 2)},
                    "source_b": {"label": "1610 Total Credit", "label_ka": "1610 ჯამური კრედიტი", "value": round(inv_16xx, 2)},
                    "variance": internal_transfers, "variance_pct": round(cogs_pct, 2),
                    "severity": "info",
                    "status": "component",
                    "is_component_check": True,
                    "note": f"COGS = {cogs_pct:.1f}% of total 1610 credit. Internal transfers (1610→1610) = {100-cogs_pct:.1f}%",
                    "note_ka": f"COGS = 1610 კრედიტის {cogs_pct:.1f}%. შიდა ტრანსფერები (1610→1610) = {100-cogs_pct:.1f}%",
                })

            reconciliation["has_mismatch"] = any(c["status"] == "mismatch" for c in reconciliation["checks"])
        except Exception as e:
            logger.warning(f"COGS reconciliation in /cogs endpoint failed: {e}")

    # ── COGS flow explanation (for UI info card) ──
    flow_explanation = accounting_intelligence.explain_financial_flow("cogs_formation")

    # ── Data quality from accounting intelligence ──
    data_quality = {}
    try:
        if ds_id:
            tb_all_for_dq = (await db.execute(
                select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == ds_id)
            )).scalars().all()
            unmapped_71 = []
            for t in tb_all_for_dq:
                if t.account_code and t.account_code.startswith('71') and (t.hierarchy_level or 0) == 1:
                    cls = accounting_intelligence.classify_account(t.account_code)
                    if cls.match_level == "unmapped":
                        unmapped_71.append({"code": t.account_code, "name": t.account_name or ""})
            data_quality["unmapped_71xx"] = unmapped_71
            data_quality["total_tb_accounts"] = len(set(
                t.account_code for t in tb_all_for_dq
                if t.account_code and (t.hierarchy_level or 0) == 1
            ))
            mapped_count = sum(
                1 for t in tb_all_for_dq
                if t.account_code and (t.hierarchy_level or 0) == 1
                and accounting_intelligence.classify_account(t.account_code).match_level != "unmapped"
            )
            data_quality["coverage_pct"] = round(
                mapped_count / data_quality["total_tb_accounts"] * 100, 1
            ) if data_quality["total_tb_accounts"] else 100.0
    except Exception as e:
        logger.warning(f"COGS data quality check failed: {e}")

    # ── Enrich col7310 from TB when COGS sheet lacks per-product 7310 data ──
    # Selling expenses (7310) are often charged directly (not through inventory 1610),
    # so the COGS Breakdown sheet has 0 for col7310. We proportionally allocate the
    # total 7310 from the Trial Balance to products based on their COGS share.
    col7310_enriched = False
    tb_7310_total = 0.0
    if ds_id and total_cogs > 0:
        all_7310_zero = all(p.get("col7310_amount", 0) == 0 for p in products)
        if all_7310_zero:
            try:
                # Get TB 7310 parent-level turnover_debit (total selling expenses)
                tb_7310_rows = (await db.execute(
                    select(TrialBalanceItem).where(
                        TrialBalanceItem.dataset_id == ds_id,
                        TrialBalanceItem.account_code == '7310',
                        TrialBalanceItem.hierarchy_level == 1,
                    )
                )).scalars().all()
                tb_7310_total = sum(_d(t.turnover_debit or 0) for t in tb_7310_rows)

                if tb_7310_total > 0:
                    # Proportionally allocate 7310 to products based on COGS share
                    for p in products:
                        share = p["total_cogs"] / total_cogs if total_cogs else 0
                        p["col7310_amount"] = round(tb_7310_total * share, 2)
                        # Recompute total (original col6 + allocated 7310 + col8230)
                        p["total_cogs"] = round(p["col6_amount"] + p["col7310_amount"] + p["col8230_amount"], 2)

                    # Update by_category and totals
                    total_cogs_enriched = sum(p["total_cogs"] for p in products)
                    for cat_data in organized:
                        cat_data["total"] = round(sum(
                            p["total_cogs"] for p in cat_data["products"]
                        ), 2)

                    # Recompute pct_of_total
                    for p in products:
                        p["pct_of_total"] = round(p["total_cogs"] / total_cogs_enriched * 100, 2) if total_cogs_enriched else 0
                    total_cogs = total_cogs_enriched
                    col7310_enriched = True
                    logger.info(f"COGS col7310 enriched from TB: {tb_7310_total:,.2f} GEL allocated to {len(products)} products")
            except Exception as e:
                logger.warning(f"COGS col7310 enrichment failed: {e}")

    # ── Available filter options (for frontend dropdowns) ──
    all_items_q = select(COGSItem)
    if ds_id:
        all_items_q = all_items_q.where(COGSItem.dataset_id == ds_id)
    all_items_res = await db.execute(all_items_q)
    all_items_list = all_items_res.scalars().all()
    available_segments = sorted(set(c.segment for c in all_items_list if c.segment))
    available_categories = sorted(set(c.category for c in all_items_list if c.category))

    return {
        "totals": {
            "total_cogs": round(total_cogs, 2),
            "wholesale_cogs": round(wholesale_total, 2),
            "retail_cogs": round(retail_total, 2),
            "product_count": len(items),
            "col7310_source": "tb_proportional" if col7310_enriched else "cogs_sheet",
            "tb_7310_total": round(tb_7310_total, 2) if col7310_enriched else None,
        },
        "segments": {k: round(v, 2) for k, v in sorted(by_segment.items(), key=lambda x: -x[1])},
        "by_category": organized,
        "products": sorted(products, key=lambda x: -x["total_cogs"]),
        "reconciliation": reconciliation,
        "flow_explanation": flow_explanation,
        "data_quality": data_quality,
        "filters_applied": {
            "segment": segment, "category": category,
            "search": search, "period": period,
            "sort_by": sort_by, "sort_dir": sort_dir,
        },
        "available_filters": {
            "segments": available_segments,
            "categories": available_categories,
        },
    }


@router.get("/cogs/compare")
async def compare_cogs(
    dataset_ids: str = Query(..., description="Comma-separated dataset IDs"),
    db: AsyncSession = Depends(get_db),
):
    """Compare COGS across multiple datasets/periods."""
    from app.services.file_parser import get_english_name
    ids = [int(x.strip()) for x in dataset_ids.split(",") if x.strip().isdigit()]
    if len(ids) < 2:
        raise HTTPException(400, "Provide at least 2 dataset IDs")

    datasets_info = []
    datasets_data = {}
    all_products = set()

    for ds_id in ids:
        ds = (await db.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one_or_none()
        if not ds:
            continue
        datasets_info.append({"id": ds.id, "name": ds.name, "period": ds.period or "Unknown"})

        items = (await db.execute(
            select(COGSItem).where(COGSItem.dataset_id == ds_id).order_by(COGSItem.total_cogs.desc())
        )).scalars().all()

        ds_totals = {"total_cogs": 0, "wholesale_cogs": 0, "retail_cogs": 0, "product_count": len(items)}
        ds_products = {}
        ds_segments = {}

        for c in items:
            total = _d(c.total_cogs or 0)
            ds_totals["total_cogs"] += total
            seg = c.segment or "Other"
            if 'wholesale' in seg.lower() or 'whsale' in seg.lower():
                ds_totals["wholesale_cogs"] += total
            elif 'retail' in seg.lower() or 'retial' in seg.lower():
                ds_totals["retail_cogs"] += total
            ds_segments[seg] = ds_segments.get(seg, 0) + total
            prod_key = c.product or "Unknown"
            all_products.add(prod_key)
            ds_products[prod_key] = {
                "product": prod_key,
                "product_en": get_english_name(prod_key),
                "segment": seg,
                "category": c.category or "Other",
                "total_cogs": round(total, 2),
                "col6_amount": round(_d(c.col6_amount or 0), 2),
                "col7310_amount": round(_d(c.col7310_amount or 0), 2),
                "col8230_amount": round(_d(c.col8230_amount or 0), 2),
            }

        for k in ds_totals:
            if isinstance(ds_totals[k], float):
                ds_totals[k] = round(ds_totals[k], 2)

        datasets_data[ds_id] = {
            "totals": ds_totals,
            "segments": {k: round(v, 2) for k, v in ds_segments.items()},
            "products": ds_products,
        }

    # Build comparison rows with deltas
    comparison = []
    for prod in sorted(all_products):
        row = {"product": prod}
        values = []
        for ds_id in ids:
            ds_prod = datasets_data.get(ds_id, {}).get("products", {}).get(prod)
            val = ds_prod["total_cogs"] if ds_prod else 0.0
            row[f"ds_{ds_id}"] = val
            values.append(val)
        if len(values) >= 2 and values[0] > 0:
            row["delta"] = round(values[-1] - values[0], 2)
            row["delta_pct"] = round((values[-1] - values[0]) / values[0] * 100, 2)
        comparison.append(row)

    return {
        "datasets": datasets_info,
        "datasets_data": datasets_data,
        "comparison": sorted(comparison, key=lambda x: -abs(x.get("delta", 0))),
    }


@router.get("/accounting-analysis")
async def get_accounting_analysis(
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Full accounting intelligence analysis — account flows, coverage, BS identity, warnings."""
    from app.services.accounting_intelligence import accounting_intelligence
    ds_id = await _resolve_dataset_id(dataset_id, db)
    if not ds_id:
        raise HTTPException(400, "No active dataset found")
    analysis = await accounting_intelligence.analyze_dataset_flows(db, ds_id)
    return analysis.to_dict()


@router.get("/budget")
async def get_budget(dataset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """Budget vs actual variance."""
    ds_id = await _resolve_dataset_id(dataset_id, db)
    q = select(BudgetLine)
    if ds_id: q = q.where(BudgetLine.dataset_id == ds_id)
    result = await db.execute(q)
    lines  = result.scalars().all()
    items  = []
    for b in lines:
        actual   = b.actual_amount if b.actual_amount is not None else b.budget_amount
        variance = actual - b.budget_amount
        var_pct  = variance / abs(b.budget_amount) * 100 if b.budget_amount else 0
        items.append({
            "line_item":    b.line_item,
            "actual":       round(actual,2),
            "budget":       round(b.budget_amount,2),
            "variance":     round(variance,2),
            "variance_pct": round(var_pct,2),
            "category":     b.category or "OTHER",
        })
    return {"items": items, "count": len(items)}


@router.get("/pl")
async def get_pl(period: str = "January 2025", currency: str = "GEL", dataset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """P&L Statement — structured Income Statement with Wholesale/Retail/Other breakdown."""
    ds_id = await _resolve_dataset_id(dataset_id, db, context="pl")

    # Validate period against actual dataset — reject fake periods
    if ds_id and period != "January 2025":  # Skip validation for default
        ds_period = await _resolve_period(ds_id, db)
        if ds_period and period != ds_period:
            # Check if this period exists in ANY dataset
            period_check = await db.execute(
                select(Dataset.id).where(Dataset.period == period).limit(1)
            )
            if not period_check.scalar_one_or_none():
                raise HTTPException(400, f"Period '{period}' not found in any dataset. "
                                         f"Available: {ds_period}")

    q_rev = select(RevenueItem)
    q_cogs = select(COGSItem)
    q_ga = select(GAExpenseItem)
    q_bud = select(BudgetLine)
    if ds_id:
        q_rev = q_rev.where(RevenueItem.dataset_id == ds_id)
        q_cogs = q_cogs.where(COGSItem.dataset_id == ds_id)
        q_ga = q_ga.where(GAExpenseItem.dataset_id == ds_id)
        q_bud = q_bud.where(BudgetLine.dataset_id == ds_id)

    rev_items = (await db.execute(q_rev)).scalars().all()
    cogs_items = (await db.execute(q_cogs)).scalars().all()
    ga_items = (await db.execute(q_ga)).scalars().all()
    bud_result = await db.execute(q_bud)
    budget = {b.line_item: b.actual_amount if b.actual_amount is not None else b.budget_amount for b in bud_result.scalars().all()}

    # Extract special finance/tax items from GAExpenseItem (stored from TDSheet)
    fin_inc, fin_exp, tax_exp, labour = _extract_special_items(ga_items)

    # ── COGS enrichment: fetch TB 7310 total for P&L harmonization ──
    # Fixes ₾4.9M COGS gap between P&L and COGS endpoints.
    # When COGS sheet has col7310=0 (selling expenses booked separately),
    # we need to allocate TB account 7310 to match the COGS endpoint.
    tb_col7310_total = 0.0
    if ds_id:
        try:
            tb_7310_rows = (await db.execute(
                select(TrialBalanceItem).where(
                    TrialBalanceItem.dataset_id == ds_id,
                    TrialBalanceItem.account_code == '7310',
                    TrialBalanceItem.hierarchy_level == 1,
                )
            )).scalars().all()
            tb_col7310_total = sum(_d(t.turnover_debit or 0) for t in tb_7310_rows)
        except Exception:
            pass  # TB may not be loaded

    stmt = build_income_statement(rev_items, cogs_items, ga_items, period, currency,
                                  finance_income=fin_inc, finance_expense=fin_exp,
                                  tax_expense=tax_exp, labour_costs=labour,
                                  tb_col7310_total=tb_col7310_total)

    from app.services.coa_engine import build_structured_pl_rows
    rows = build_structured_pl_rows(stmt, budget)

    # ── Transparency ──
    transparency = await _build_transparency(ds_id, db, "pl_waterfall",
        sources={
            "REV": "Revenue Breakdown Sheet → RevenueItem (accounts 6110-6149)",
            "COGS": "COGS Breakdown Sheet → COGSItem (accounts 71xx via 1610→7110)",
            "GA": "TDSheet → GAExpenseItem (accounts 73xx + 74xx)",
            "DA": "TDSheet → D&A items (account 7410)",
            "FIN": "TDSheet → Finance items (accounts 8220, 76xx)",
            "TAX": "TDSheet → Tax items (accounts 77xx)",
        })

    return {
        "period": period, "currency": currency, "rows": rows,
        "kpis": {
            "revenue": stmt.total_revenue,
            "gross_margin": stmt.total_gross_margin,
            "total_gross_profit": stmt.total_gross_profit,
            "ga_expenses": stmt.ga_expenses,
            "da_expenses": stmt.da_expenses,
            "ebitda": stmt.ebitda,
            "ebit": stmt.ebit,
            "finance_income": stmt.finance_income,
            "finance_expense": stmt.finance_expense,
            "ebt": stmt.ebt,
            "tax_expense": stmt.tax_expense,
            "net_profit": stmt.net_profit,
            "wholesale_margin": stmt.margin_wholesale_total,
            "retail_margin": stmt.margin_retail_total,
        },
        "transparency": transparency,
    }


async def _resolve_dataset_id(
    dataset_id: Optional[int],
    db: AsyncSession,
    context: str = "dashboard",
) -> Optional[int]:
    """Smart dataset resolution — context-aware, backward-compatible.

    Uses SmartResolver to find the best dataset for the given context.
    If an explicit dataset_id is provided, it's used directly.
    Otherwise, considers report type requirements and data richness.
    """
    try:
        from app.services.financial_intelligence import SmartResolver
        resolver = SmartResolver(db)
        resolved = await resolver.resolve(dataset_id=dataset_id, context=context)
        if resolved:
            return resolved
    except Exception:
        pass

    # Fallback to simple logic
    if dataset_id:
        # VALIDATION FIX: Verify the dataset actually exists
        from app.models.all_models import Dataset as DatasetModel
        ds = await db.execute(
            select(DatasetModel.id).where(DatasetModel.id == dataset_id)
        )
        if not ds.scalar_one_or_none():
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {dataset_id} not found"
            )
        return dataset_id

    result = await db.execute(select(Dataset.id).where(Dataset.is_active == True).limit(1))
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No active dataset found. Upload a dataset first."
        )
    return row[0]


async def _resolve_period(dataset_id: Optional[int], db: AsyncSession, fallback: str = "January 2025") -> str:
    """Resolve the period string from the Dataset record instead of using a hardcoded default."""
    if not dataset_id:
        dataset_id = await _resolve_dataset_id(None, db)
    if dataset_id:
        result = await db.execute(select(Dataset.period).where(Dataset.id == dataset_id))
        row = result.first()
        if row and row[0]:
            return row[0]
    return fallback


@router.get("/income-statement")
async def get_income_statement(
    period: Optional[str] = None,
    currency: str = "GEL",
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Full structured Income Statement with Wholesale/Retail/Other breakdown."""
    ds_id = await _resolve_dataset_id(dataset_id, db)
    if not period:
        period = await _resolve_period(ds_id, db)
    q_rev = select(RevenueItem)
    q_cogs = select(COGSItem)
    q_ga = select(GAExpenseItem)
    if ds_id:
        q_rev = q_rev.where(RevenueItem.dataset_id == ds_id)
        q_cogs = q_cogs.where(COGSItem.dataset_id == ds_id)
        q_ga = q_ga.where(GAExpenseItem.dataset_id == ds_id)

    rev_items = (await db.execute(q_rev)).scalars().all()
    cogs_items = (await db.execute(q_cogs)).scalars().all()
    ga_items = (await db.execute(q_ga)).scalars().all()

    fin_inc, fin_exp, tax_exp, labour = _extract_special_items(ga_items)
    stmt = build_income_statement(rev_items, cogs_items, ga_items, period, currency,
                                  finance_income=fin_inc, finance_expense=fin_exp,
                                  tax_expense=tax_exp, labour_costs=labour)
    return stmt.to_dict()


@router.get("/pl/compare")
async def compare_pl(
    dataset_id_1: int = Query(..., description="Prior period dataset ID"),
    dataset_id_2: int = Query(..., description="Current period dataset ID"),
    currency: str = "GEL",
    db: AsyncSession = Depends(get_db),
):
    """Compare two periods' P&L. Returns rows with ac=current, pr=prior, pl=budget."""
    async def _build_stmt(ds_id):
        rev = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == ds_id))).scalars().all()
        cogs = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == ds_id))).scalars().all()
        ga = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id))).scalars().all()
        ds = (await db.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one_or_none()
        period = ds.period if ds else "Unknown"
        fi, fe, te, lb = _extract_special_items(ga)
        return build_income_statement(rev, cogs, ga, period, currency,
                                      finance_income=fi, finance_expense=fe,
                                      tax_expense=te, labour_costs=lb), period

    stmt1, period1 = await _build_stmt(dataset_id_1)  # prior
    stmt2, period2 = await _build_stmt(dataset_id_2)  # current

    # Budget from current dataset
    bud_result = await db.execute(select(BudgetLine).where(BudgetLine.dataset_id == dataset_id_2))
    budget = {b.line_item: b.actual_amount if b.actual_amount is not None else b.budget_amount for b in bud_result.scalars().all()}

    from app.services.coa_engine import build_structured_pl_rows
    rows_current = build_structured_pl_rows(stmt2, budget)
    rows_prior = {r["c"]: r["ac"] for r in stmt1.to_rows()}

    # Merge: add pr (prior) column to current rows
    for row in rows_current:
        row["pr"] = round(rows_prior.get(row["c"], 0), 2)

    return {
        "period1": period1, "period2": period2, "currency": currency,
        "rows": rows_current,
        "kpis": {
            "current": {"revenue": stmt2.total_revenue, "ebitda": stmt2.ebitda, "gross_margin": stmt2.total_gross_margin},
            "prior": {"revenue": stmt1.total_revenue, "ebitda": stmt1.ebitda, "gross_margin": stmt1.total_gross_margin},
        },
    }


@router.get("/balance-sheet")
async def get_balance_sheet(period: Optional[str] = None, dataset_id: Optional[int] = None,
                            include_mappings: bool = False, db: AsyncSession = Depends(get_db)):
    """
    Balance Sheet — priority waterfall:
    1. Parsed BalanceSheetItem records (IFRS-mapped from Balance/BS sheets) → preferred
    2. Fall back to transaction-based BS derivation (COA structural matching)
    When include_mappings=True, also returns mapping_table + valid_ifrs_lines for editing.
    """
    ds_id = await _resolve_dataset_id(dataset_id, db, context="bs")
    # Resolve period from dataset instead of hardcoded default
    if not period:
        period = await _resolve_period(ds_id, db)

    # ── Priority 1: IFRS-mapped BalanceSheetItem records ──────────────
    q_bsi = select(BalanceSheetItem)
    if ds_id:
        q_bsi = q_bsi.where(BalanceSheetItem.dataset_id == ds_id)
    bsi_result = await db.execute(q_bsi)
    bsi_items = bsi_result.scalars().all()

    if bsi_items:
        result = _build_bs_from_parsed_items(bsi_items, period)
    else:
        result = await _build_bs_from_transactions(ds_id, period, db)

    # ── Synthetically add current-period Net Profit to Retained Earnings ──
    # In a mid-period TB, P&L accounts (classes 6-9) have turnovers but haven't closed
    # to Retained Earnings (53xx). The BS won't balance without this adjustment.
    try:
        from app.services.income_statement import build_income_statement
        rev_q = select(RevenueItem)
        cogs_q = select(COGSItem)
        ga_q = select(GAExpenseItem)
        if ds_id:
            rev_q = rev_q.where(RevenueItem.dataset_id == ds_id)
            cogs_q = cogs_q.where(COGSItem.dataset_id == ds_id)
            ga_q = ga_q.where(GAExpenseItem.dataset_id == ds_id)
        rev_items = (await db.execute(rev_q)).scalars().all()
        cogs_items = (await db.execute(cogs_q)).scalars().all()
        ga_items = (await db.execute(ga_q)).scalars().all()
        if rev_items:
            fi, fe, te, lb = _extract_special_items(ga_items)
            pl_stmt = build_income_statement(rev_items, cogs_items, ga_items, period, "GEL",
                                             finance_income=fi, finance_expense=fe,
                                             tax_expense=te, labour_costs=lb)
            net_profit = pl_stmt.net_profit
            if abs(net_profit) > 0.01:
                # Inject into result rows and totals
                eq_rows = [r for r in result["rows"] if r.get("c") == "EQ"]
                eq_idx = next((i for i, r in enumerate(result["rows"]) if r.get("c") == "EQ"), None)
                if eq_idx is not None:
                    result["rows"].insert(eq_idx + 1, {
                        "c": "EQ00", "l": "Current Period Result",
                        "ac": round(net_profit, 2), "pl": 0, "lvl": 2, "s": 1
                    })
                if eq_rows:
                    eq_rows[0]["ac"] = round(eq_rows[0]["ac"] + net_profit)
                result["totals"]["equity"] = round(result["totals"]["equity"] + net_profit)

        # CRITICAL FIX: DO NOT inject phantom "Unallocated P&L Variance" line.
        # The old code hid data quality issues by injecting a fake equity line (EQVAR)
        # to force-balance the BS. This is audit fraud — hiding a ₾19.4M gap inside
        # a phantom line item and reporting "balanced: true".
        #
        # Instead: log the imbalance clearly and report it to the user.
        remaining = result["totals"]["assets"] - result["totals"]["liabilities"] - result["totals"]["equity"]
        if abs(remaining) > 1:
            import logging as _log
            _log.getLogger(__name__).warning(
                "BALANCE SHEET IMBALANCE: ₾%.2f | Assets=%.2f, L=%.2f, E=%.2f | "
                "Likely causes: TB hierarchy double-counting, missing P&L accounts, "
                "or retained earnings injection error.",
                remaining, result["totals"]["assets"],
                result["totals"]["liabilities"], result["totals"]["equity"],
            )
            # Surface the imbalance to the user — do NOT hide it
            result["data_quality_warnings"] = result.get("data_quality_warnings", [])
            result["data_quality_warnings"].append({
                "type": "balance_sheet_imbalance",
                "severity": "critical",
                "imbalance_amount": round(abs(remaining), 2),
                "message": (
                    f"Balance Sheet does not balance by ₾{abs(remaining):,.2f}. "
                    f"This may be caused by TB hierarchy double-counting or "
                    f"retained earnings injection errors. DO NOT use for reporting."
                ),
            })

        # Final balance check — honest reporting
        result["balanced"] = abs(
            result["totals"]["assets"] - result["totals"]["liabilities"] - result["totals"]["equity"]
        ) < 1
    except Exception:
        pass  # If P&L computation fails, don't block BS

    if include_mappings and ds_id:
        mapping_data = await _build_mapping_table(ds_id, db)
        result["mapping_table"] = mapping_data["mappings"]
        result["valid_ifrs_lines"] = mapping_data["valid_ifrs_lines"]

    # ── Transparency ──
    bs_reconciliation = {
        "check": "A = L + E",
        "assets": result["totals"]["assets"],
        "liabilities": result["totals"]["liabilities"],
        "equity": result["totals"]["equity"],
        "balanced": result.get("balanced", False),
        "variance": round(abs(result["totals"]["assets"] - result["totals"]["liabilities"] - result["totals"]["equity"]), 2),
    }
    transparency = await _build_transparency(ds_id, db, "balance_sheet_structure",
        sources={
            "data_source": result.get("data_source", ""),
        },
        reconciliation=bs_reconciliation)
    result["transparency"] = transparency

    return result


async def _build_mapping_table(ds_id: int, db) -> dict:
    """Build mapping table showing how each TB account maps to IFRS line items.

    Now includes ifrs_statement (BS/PL) and BAKU MR mapping from the
    intelligence layer — so every account shows which report it feeds into.
    """
    from app.services.file_parser import map_coa, GEORGIAN_COA, _user_coa_overrides, _coa_master_cache
    from app.services.mr_mapping import ACCOUNT_CLASS_KNOWLEDGE
    import re as _re

    q_tb = select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == ds_id)
    tb_result = await db.execute(q_tb)
    tb_items = tb_result.scalars().all()

    mappings = []
    for item in tb_items:
        code = (item.account_code or "").strip()
        if not code:
            continue
        coa = map_coa(code)
        normalized = _re.sub(r'[^0-9]', '', code)
        if coa:
            # Determine source with 3-tier attribution
            if code in _user_coa_overrides:
                source = "User"
                confidence = 1.0
            elif normalized in _coa_master_cache:
                source = "COA Master"
                confidence = 0.95
            elif coa.get("prefix") and coa["prefix"] in GEORGIAN_COA:
                source = "COA Rule"
                confidence = 0.85 if coa["prefix"] == normalized[:len(coa["prefix"])] else 0.7
            else:
                source = "Class Rule"
                confidence = 0.5
            ifrs_line = coa.get("bs") or coa.get("pl") or ""
            bs_side = coa.get("bs_side") or coa.get("side") or ""
        else:
            source = "Unmapped"
            confidence = 0.0
            ifrs_line = ""
            bs_side = ""

        # Determine ifrs_statement (BS or PL) from account class knowledge
        first_digit = normalized[:1] if normalized else ''
        class_info = ACCOUNT_CLASS_KNOWLEDGE.get(first_digit, {})
        ifrs_statement = class_info.get("statement", "")

        entry = {
            "account_code": code,
            "account_name": item.account_name or "",
            "ifrs_line_item": ifrs_line,
            "ifrs_statement": ifrs_statement,  # BS or PL — which report this feeds into
            "bs_side": bs_side,
            "bs_sub": coa.get("bs_sub", "") if coa else "",
            "pl_line": coa.get("pl_line", "") if coa else "",
            "source": source,
            "confidence": confidence,
            # BAKU MR mapping — from populated mr_mapping fields on TB items
            "baku_mr_code": item.mr_mapping or "",
            "baku_mr_line": item.mr_mapping_line or "",
        }
        # Enrich with COA master metadata if available
        master = _coa_master_cache.get(normalized)
        if master:
            entry["account_type"] = master.get("account_type", "")
            entry["account_type_en"] = master.get("account_type_en", "")
            entry["name_ka"] = master.get("name_ka", "")
            entry["name_ru"] = master.get("name_ru", "")
        mappings.append(entry)

    # Valid IFRS lines for dropdown (from GEORGIAN_COA + COA master)
    valid_lines = set()
    for e in GEORGIAN_COA.values():
        if e.get("bs"): valid_lines.add(e["bs"])
        if e.get("pl"): valid_lines.add(e["pl"])
    for e in _coa_master_cache.values():
        if e.get("bs"): valid_lines.add(e["bs"])
        if e.get("pl"): valid_lines.add(e["pl"])
    valid_ifrs_lines = sorted(valid_lines)

    return {"mappings": mappings, "valid_ifrs_lines": valid_ifrs_lines}


def _build_bs_from_parsed_items(bsi_items, period: str) -> dict:
    """Build IFRS Balance Sheet from parsed BalanceSheetItem records (Balance/BS sheets)."""
    # IFRS line → BS section mapping (matches actual MAPPING GRP values + GEORGIAN_COA 'bs' values)
    IFRS_SECTIONS = {
        # Non-current assets (from Balance sheet MAPPING GRP)
        'Property, plant and equipment': 'nca',
        'PPE Cost': 'nca',
        'PPE Depreciation': 'nca',
        'Right of use asset': 'nca',
        'Right-of-use assets': 'nca',
        'Investment properties': 'nca',
        'Investment property': 'nca',
        'Investments': 'nca',
        'Investment in associate': 'nca',
        'Intangible assets': 'nca',
        'Intangible Assets COST': 'nca',
        'Intangible Assets Amortisations': 'nca',
        'Trade receivables LT': 'nca',
        'Goodwill': 'nca',
        'Long-term receivables': 'nca',
        'Deferred tax assets': 'nca',
        'Other non-current assets': 'nca',
        # Non-current assets (from GEORGIAN_COA auto-generation)
        'Noncurrent Assets': 'nca',
        'Fixed Assets (PP&E)': 'nca',
        'Fixed Assets': 'nca',
        'Land': 'nca',
        'Construction in Progress': 'nca',
        'Investment Property': 'nca',
        'Land Acquisition': 'nca',
        'Fixed Asset Acquisition': 'nca',
        'Accumulated Depreciation': 'nca',
        'Acc. Depr. - Fixed Assets': 'nca',
        'Deferred Tax Assets': 'nca',
        'Long-term Investments': 'nca',
        'Intangible Assets': 'nca',
        'Accumulated Amortization': 'nca',
        'Acc. Amort. - Intangibles': 'nca',
        'Other Non-current Assets': 'nca',
        # Current assets (from Balance sheet MAPPING GRP)
        'Inventories': 'ca',
        'Trade receivables': 'ca',
        'Tax assets': 'ca',
        'Prepayments and other receivables': 'ca',
        'Short term loans receivable': 'ca',
        'Cash and cash equivalents': 'ca',
        'Other current assets': 'ca',
        'Prepayments': 'ca',
        'Current tax assets': 'ca',
        'Short-term investments': 'ca',
        'Contract assets': 'ca',
        'Other receivables': 'ca',
        # Current assets (from GEORGIAN_COA auto-generation)
        'Current Assets': 'ca',
        'Cash & Equivalents': 'ca',
        'Cash in Hand (GEL)': 'ca',
        'Cash in Hand (FX)': 'ca',
        'Bank Accounts': 'ca',
        'Bank Accounts (GEL)': 'ca',
        'Bank Accounts (FX)': 'ca',
        'Money in Transit': 'ca',
        'Short-term Investments': 'ca',
        'Trade Receivables': 'ca',
        'Employee Receivables': 'ca',
        'Doubtful Debt Allowance': 'ca',
        'Advances to Suppliers': 'ca',
        'Other Receivables': 'ca',
        'Other Current Assets': 'ca',
        'Inventory': 'ca',
        'Goods in Transit': 'ca',
        'Merchandise': 'ca',
        'Raw Materials & Fuel': 'ca',
        'Work in Progress': 'ca',
        'Finished Goods': 'ca',
        'Prepaid Taxes': 'ca',
        'Prepaid VAT': 'ca',
        'Dividends & Interest Recv': 'ca',
        'Dividends Receivable': 'ca',
        'Interest Receivable': 'ca',
        'Input VAT (Asset)': 'ca',
        # Non-current liabilities (from Balance sheet MAPPING GRP)
        'Lease liability non current': 'ncl',
        'Lease liability non current portion': 'ncl',
        'Government Grants non current': 'ncl',
        'Long-term borrowings': 'ncl',
        'Long-term lease liabilities': 'ncl',
        'Long-term provisions': 'ncl',
        'Deferred tax liabilities': 'ncl',
        'Employee benefit obligations': 'ncl',
        'Other non-current liabilities': 'ncl',
        'Deferred revenue (non-current)': 'ncl',
        'Long-Term Loans Payable': 'ncl',
        # Non-current liabilities (from GEORGIAN_COA auto-generation)
        'Noncurrent Liabilities': 'ncl',
        'Long-term Debt': 'ncl',
        'Usufruct Obligations': 'ncl',
        'Long-term Loans': 'ncl',
        'Long-term Lease Liability': 'ncl',
        'Other LT Liabilities': 'ncl',
        'Deferred Tax Liabilities': 'ncl',
        # Current liabilities (from Balance sheet MAPPING GRP)
        'Trade and other payables': 'cl',
        'Trade payables': 'cl',
        'Advances received': 'cl',
        'Short-term loans and borrowings': 'cl',
        'Short-term borrowings': 'cl',
        'Other taxes payable': 'cl',
        'Lease liability': 'cl',
        'Government grants': 'cl',
        'Government grant liability': 'cl',
        'Current portion of long-term debt': 'cl',
        'Current tax liabilities': 'cl',
        'Accrued expenses': 'cl',
        'Short-term lease liabilities': 'cl',
        'Short-term provisions': 'cl',
        'Contract liabilities': 'cl',
        'Other current liabilities': 'cl',
        'Deferred revenue': 'cl',
        'Dividends payable': 'cl',
        # Current liabilities (from GEORGIAN_COA auto-generation)
        'Current Liabilities': 'cl',
        'Trade Payables': 'cl',
        'Advances Received': 'cl',
        'Wages Payable': 'cl',
        'Other Trade Payables': 'cl',
        'Short-term Debt': 'cl',
        'Short-term Loans': 'cl',
        'Current Lease Liability': 'cl',
        'Tax Payables': 'cl',
        'Income Tax Payable': 'cl',
        'Revenue Tax Payable': 'cl',
        'VAT Payable': 'cl',
        'Other Tax Payables': 'cl',
        'Excise Payable': 'cl',
        'Pension Obligations': 'cl',
        'Property Tax Payable': 'cl',
        'Other Tax Liabilities': 'cl',
        'Accrued Liabilities': 'cl',
        'Interest Payable': 'cl',
        'Dividends Payable': 'cl',
        'Other Accrued Liabilities': 'cl',
        # Equity (from Balance sheet MAPPING GRP)
        'Share capital': 'eq',
        'Additional Paid-in Capital': 'eq',
        'Unpaid Capital': 'eq',
        'Retained earnings': 'eq',
        'Net income for the Period': 'eq',
        'Revaluation reserve': 'eq',
        'Other reserves': 'eq',
        'Treasury shares': 'eq',
        'Translation reserve': 'eq',
        'Non-controlling interests': 'eq',
        # Equity (from GEORGIAN_COA auto-generation)
        'Equity': 'eq',
        'Share Capital': 'eq',
        'Retained Earnings': 'eq',
        'Reserves': 'eq',
    }

    # Known IS (Income Statement) line items to exclude from BS
    IS_LINES = {
        'Revenue from sale of gas', 'Gas purchases', 'Other Cost of sale',
        'Other operating expenses', 'Wages, benefits and payroll taxes',
        'Other Non-operating Income', 'Net FX gain/(loss)',
        'Selling and Distribution costs', 'Selling and Distribution Costs',
        'Depreciation and amortization', 'Interest expense', 'Interest income',
        'Loss on disposal of property, plant and equipment',
        'Taxes, other than income tax', 'Revenue', 'Cost of sales',
    }

    # ── Account-code based section override ──────────────────────────────
    # The source file's MAPPING GRP can misclassify accounts (e.g., class-3
    # liabilities labeled as "Tax assets"). Use account_code first digit to
    # determine the TRUE BS section, overriding IFRS_SECTIONS when they conflict.
    ACCT_CLASS_TO_SECTION = {
        # Georgian COA: 1=current assets, 2=non-current assets, 3=current liab,
        # 4=non-current liab, 5=equity
        '1': 'ca', '2': 'nca', '3': 'cl', '4': 'ncl', '5': 'eq',
    }

    # Aggregate closing_balance by IFRS line item across ALL statement types
    # For Balance-sheet-parsed items: Use summary rows (row_type == 'სხვა') to avoid double-counting
    # For COA_DERIVED items: All items are leaf accounts, include all
    ifrs_lines = {}
    has_coa_derived = any(getattr(item, 'row_type', '') == 'COA_DERIVED' or
                          (hasattr(item, 'row_type') and item.row_type == 'COA_DERIVED')
                          for item in bsi_items)
    for item in bsi_items:
        line = (item.ifrs_line_item or '').strip()
        if not line:
            continue
        # Skip known IS items
        if line in IS_LINES:
            continue

        # ── Step 1: Determine section from IFRS mapping ──
        sec = IFRS_SECTIONS.get(line)
        if not sec:
            # Heuristic classification by keywords (NCA checked BEFORE CA)
            ll = line.lower()
            if any(k in ll for k in ['ppe', 'property', 'equipment', 'intangible', 'goodwill',
                                      'invest', 'right-of-use', 'right of use', 'deferred tax asset',
                                      'fixed asset', 'depreciation', 'amortization', 'land']):
                sec = 'nca'
            elif any(k in ll for k in ['receivable', 'inventory', 'inventories', 'cash', 'prepay',
                                        'tax asset', 'loan receivable', 'bank account', 'merchandise',
                                        'finished good', 'raw material', 'work in progress', 'transit']):
                sec = 'ca'
            elif any(k in ll for k in ['capital', 'equity', 'retained', 'reserve', 'treasury',
                                        'net income', 'unpaid capital']):
                sec = 'eq'
            elif any(k in ll for k in ['non current', 'non-current', 'long-term', 'long term',
                                        'deferred tax liabilit', 'usufruct']):
                sec = 'ncl'
            elif any(k in ll for k in ['payable', 'accrued', 'current liabilit', 'short-term',
                                        'tax liabilit', 'provision', 'advance', 'loan', 'debt',
                                        'wages', 'pension', 'excise', 'dividend']):
                sec = 'cl'
            else:
                continue  # skip items we can't classify (likely IS items)

        # ── Step 2: Override section using account code when MAPPING GRP is wrong ──
        # Example: account 3310 (income tax payable) might be labeled "Tax assets"
        # by the source file, but it's really a current liability (class 3).
        # Also fixes: 32xx (short-term loans) labeled as "Long-Term Loans Payable".
        acct_code = (getattr(item, 'account_code', '') or '').strip()
        clean_code = acct_code.replace('X', '').replace('x', '')
        first_digit = clean_code[:1] if clean_code else ''
        if first_digit in ACCT_CLASS_TO_SECTION:
            correct_sec = ACCT_CLASS_TO_SECTION[first_digit]
            # Override if the IFRS mapping puts it in the wrong section:
            # 1) Asset vs liability/equity mismatch (most critical)
            # 2) Current vs non-current mismatch within liabilities (3xx→cl, 4xx→ncl)
            if sec != correct_sec:
                ifrs_is_asset = sec in ('ca', 'nca')
                code_is_asset = correct_sec in ('ca', 'nca')
                if ifrs_is_asset != code_is_asset:
                    # Wrong side of BS entirely
                    sec = correct_sec
                elif not ifrs_is_asset:
                    # Both on L/E side: check current vs non-current for liabilities
                    # Class 3 = current liabilities, Class 4 = non-current liabilities
                    if first_digit == '3' and sec == 'ncl':
                        sec = 'cl'
                    elif first_digit == '4' and sec == 'cl':
                        sec = 'ncl'

        if line not in ifrs_lines:
            ifrs_lines[line] = {'sec': sec, 'summary_total': 0.0, 'detail_total': 0.0,
                                'has_summary': False, 'coa_total': 0.0, 'has_coa': False}
        else:
            # If this line already exists but the new item has a different section
            # (due to account code override), use a descriptive label
            if ifrs_lines[line]['sec'] != sec:
                # Generate a better label for the overridden item
                acct_name = (getattr(item, 'account_name', '') or '').strip()
                OVERRIDE_LABELS = {
                    'cl': {
                        '33': 'Tax liabilities',
                        '34': 'Interest payable',
                        '32': 'Short-term borrowings',
                        '31': 'Trade payables',
                    },
                    'ncl': {'4': 'Non-current liabilities'},
                }
                override_line = None
                sec_labels = OVERRIDE_LABELS.get(sec, {})
                for prefix, label in sec_labels.items():
                    if clean_code.startswith(prefix):
                        override_line = label
                        break
                if not override_line:
                    override_line = f"{line} ({acct_code})"
                if override_line not in ifrs_lines:
                    ifrs_lines[override_line] = {'sec': sec, 'summary_total': 0.0, 'detail_total': 0.0,
                                                  'has_summary': False, 'coa_total': 0.0, 'has_coa': False}
                line = override_line

        amt = _d(item.closing_balance or 0)
        row_type = getattr(item, 'row_type', '') or ''
        if row_type == 'COA_DERIVED':
            ifrs_lines[line]['has_coa'] = True
            ifrs_lines[line]['coa_total'] += amt
        elif row_type == 'სხვა':
            ifrs_lines[line]['has_summary'] = True
            ifrs_lines[line]['summary_total'] += amt
        else:
            ifrs_lines[line]['detail_total'] += amt

    # Build sections: COA-derived items are already leaf accounts (no summary/detail split)
    sections = {'nca': {}, 'ca': {}, 'ncl': {}, 'cl': {}, 'eq': {}}
    for line, data in ifrs_lines.items():
        if data['has_coa']:
            amt = data['coa_total']
        elif data['has_summary']:
            amt = data['summary_total']
        else:
            amt = data['detail_total']
        if abs(amt) < 0.01:
            continue
        sections[data['sec']][line] = round(amt, 2)

    # ── Sign correction ──────────────────────────────────────────────────
    # Balance sheet data from Georgian TB / Balance sheets uses DR-CR convention:
    #   Assets: positive (debit balance), Liabilities/Equity: negative (credit balance)
    # For display, we need all sections as positive values, so negate L and E.
    #
    # Detection: if the total of ALL items is close to zero (within 20% of total
    # absolute values), the data is in DR-CR format. In presentation format,
    # everything would be positive and the total would be large and positive.
    all_raw_total = sum(v for sec in sections.values() for v in sec.values())
    all_abs_total = sum(abs(v) for sec in sections.values() for v in sec.values())
    is_dr_cr_format = all_abs_total > 0 and abs(all_raw_total) < all_abs_total * 0.3

    if is_dr_cr_format:
        # DR-CR format: ALWAYS negate liability and equity sections.
        # Liabilities (credit balance = negative) become positive for display.
        # Equity items that are losses (debit = positive) become negative after negation.
        for sec_key in ('ncl', 'cl', 'eq'):
            sections[sec_key] = {k: -v for k, v in sections[sec_key].items()}
    else:
        # Presentation format or uncertain: use per-section majority-vote heuristic as fallback
        for sec_key in ('ncl', 'cl', 'eq'):
            sec_vals = sections[sec_key]
            if sec_vals:
                neg_count = sum(1 for v in sec_vals.values() if v < 0)
                if neg_count > len(sec_vals) / 2:
                    sections[sec_key] = {k: -v for k, v in sec_vals.items()}

    # Compute totals
    ca_total = sum(sections['ca'].values())
    nca_total = sum(sections['nca'].values())
    total_assets = ca_total + nca_total

    cl_total = sum(sections['cl'].values())
    ncl_total = sum(sections['ncl'].values())
    total_liabilities = cl_total + ncl_total

    eq_total = sum(sections['eq'].values())

    eq_display = eq_total if eq_total else (total_assets - total_liabilities)
    # Balance check: A = L + E. The caller (get_balance_sheet) will add
    # Current Period P&L Result if the BS doesn't balance — that adjustment
    # is computed from the actual P&L pipeline, not raw discrepancy.
    balanced = abs(total_assets - total_liabilities - eq_total) < 1

    # Build rows
    def _item_rows(items: dict, prefix: str, sign: int) -> list:
        sorted_items = sorted(items.items(), key=lambda x: abs(x[1]), reverse=True)
        return [
            {"c": f"{prefix}{i:02d}", "l": lbl, "ac": val, "pl": 0, "lvl": 2, "s": sign}
            for i, (lbl, val) in enumerate(sorted_items, 1)
        ]

    rows = []
    rows.append({"c": "A",   "l": "TOTAL ASSETS",           "ac": round(total_assets),      "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": 1})
    rows.append({"c": "NCA", "l": "Non-Current Assets",     "ac": round(nca_total),          "pl": 0, "lvl": 1, "bold": True, "s": 1})
    rows.extend(_item_rows(sections["nca"], "NCA", 1))
    rows.append({"c": "CA",  "l": "Current Assets",         "ac": round(ca_total),           "pl": 0, "lvl": 1, "bold": True, "s": 1})
    rows.extend(_item_rows(sections["ca"], "CA", 1))
    rows.append({"c": "L",   "l": "TOTAL LIABILITIES",      "ac": round(total_liabilities),  "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": -1})
    rows.append({"c": "NCL", "l": "Non-Current Liabilities", "ac": round(ncl_total),          "pl": 0, "lvl": 1, "bold": True, "s": -1})
    rows.extend(_item_rows(sections["ncl"], "NCL", -1))
    rows.append({"c": "CL",  "l": "Current Liabilities",    "ac": round(cl_total),           "pl": 0, "lvl": 1, "bold": True, "s": -1})
    rows.extend(_item_rows(sections["cl"], "CL", -1))
    rows.append({"c": "EQ",  "l": "EQUITY",                 "ac": round(eq_display),         "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": 1})
    rows.extend(_item_rows(sections["eq"], "EQ", 1))

    return {
        "period": period, "balanced": balanced, "rows": rows,
        "totals": {"assets": round(total_assets), "liabilities": round(total_liabilities), "equity": round(eq_display)},
        "data_source": "Auto-generated BS from TDSheet via GEORGIAN_COA mapping" if has_coa_derived else "IFRS-mapped Balance Sheet (parsed from uploaded file)",
    }


async def _build_bs_from_transactions(ds_id, period: str, db) -> dict:
    """Fallback: build BS from transaction data via COA structural matching."""
    from app.services.file_parser import map_coa
    q = select(Transaction)
    if ds_id: q = q.where(Transaction.dataset_id == ds_id)
    result = await db.execute(q)
    txns = result.scalars().all()

    acct_data = {}
    for t in txns:
        amt = abs(_d(t.amount or 0))
        if not amt:
            continue
        for acct_code, sign in [(t.acct_dr, +1), (t.acct_cr, -1)]:
            m = map_coa(acct_code or "")
            if not m or not m.get("bs_side"):
                continue
            label = m.get("bs", "Other")
            if label not in acct_data:
                acct_data[label] = {
                    "bs_side": m["bs_side"],
                    "bs_sub": m.get("bs_sub", ""),
                    "contra": m.get("contra", False),
                    "bs_ka": m.get("bs_ka", ""),
                    "balance": 0.0,
                }
            acct_data[label]["balance"] += sign * amt

    SECTION_MAP = {
        ("asset", "current"):        "ca",
        ("asset", "noncurrent"):     "nca",
        ("liability", "current"):    "cl",
        ("liability", "noncurrent"): "ncl",
        ("equity", "equity"):        "eq",
    }
    sections = {s: {} for s in SECTION_MAP.values()}

    for label, info in acct_data.items():
        sec = SECTION_MAP.get((info["bs_side"], info["bs_sub"]))
        if not sec:
            continue
        bal = info["balance"]
        if info["bs_side"] in ("liability", "equity"):
            bal = -bal
        sections[sec][label] = round(bal)

    ca_total  = sum(sections["ca"].values())
    nca_total = sum(sections["nca"].values())
    total_assets = ca_total + nca_total

    cl_total  = sum(sections["cl"].values())
    ncl_total = sum(sections["ncl"].values())
    total_liabilities = cl_total + ncl_total

    eq_total = sum(sections["eq"].values())
    eq_display = eq_total if eq_total else (total_assets - total_liabilities)
    balanced = abs(total_assets - total_liabilities - eq_total) < 1 if eq_total else True
    has_data = any(sections[s] for s in sections)

    def _item_rows(items: dict, prefix: str, sign: int) -> list:
        sorted_items = sorted(items.items(), key=lambda x: abs(x[1]), reverse=True)
        return [
            {"c": f"{prefix}{i:02d}", "l": lbl, "ac": val, "pl": 0, "lvl": 2, "s": sign}
            for i, (lbl, val) in enumerate(sorted_items, 1)
        ]

    rows = []
    rows.append({"c": "A",   "l": "TOTAL ASSETS",          "ac": round(total_assets),      "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": 1})
    rows.append({"c": "CA",  "l": "Current Assets",        "ac": round(ca_total),           "pl": 0, "lvl": 1, "bold": True, "s": 1})
    rows.extend(_item_rows(sections["ca"], "CA", 1))
    rows.append({"c": "NCA", "l": "Non-Current Assets",    "ac": round(nca_total),          "pl": 0, "lvl": 1, "bold": True, "s": 1})
    rows.extend(_item_rows(sections["nca"], "NCA", 1))
    rows.append({"c": "L",   "l": "TOTAL LIABILITIES",     "ac": round(total_liabilities),  "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": -1})
    rows.append({"c": "CL",  "l": "Current Liabilities",   "ac": round(cl_total),           "pl": 0, "lvl": 1, "bold": True, "s": -1})
    rows.extend(_item_rows(sections["cl"], "CL", -1))
    rows.append({"c": "NCL", "l": "Non-Current Liabilities","ac": round(ncl_total),          "pl": 0, "lvl": 1, "bold": True, "s": -1})
    rows.extend(_item_rows(sections["ncl"], "NCL", -1))
    rows.append({"c": "EQ",  "l": "EQUITY",                "ac": round(eq_display),         "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": 1})
    rows.extend(_item_rows(sections["eq"], "EQ", 1))

    return {
        "period": period, "balanced": balanced, "rows": rows,
        "totals": {"assets": round(total_assets), "liabilities": round(total_liabilities), "equity": round(eq_display)},
        "data_source": "COA-classified transactions (structural matching)" if has_data else "No balance sheet data available — upload a file with balance sheet accounts",
    }


@router.get("/semantic-analysis")
async def get_semantic_analysis(dataset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """
    Semantic layer analysis of transactions.
    Shows how the AI classifies transactions using multi-signal fusion:
    COA codes + counterparty patterns + department mapping + cost class text.
    """
    from app.services.semantic_layer import (
        analyze_transactions_semantic, derive_enhanced_financials, get_pattern_store
    )

    ds_id = await _resolve_dataset_id(dataset_id, db)
    if not ds_id:
        return {"error": "No active dataset", "analysis": {}, "enhanced": {}}

    # Get dataset info
    ds = (await db.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one_or_none()
    period = ds.period if ds else "Unknown"

    # Fetch all transactions as dicts
    txn_result = await db.execute(
        select(Transaction).where(Transaction.dataset_id == ds_id)
    )
    txn_models = txn_result.scalars().all()
    txns = [t.to_dict() for t in txn_models]

    if not txns:
        return {
            "period": period,
            "dataset_id": ds_id,
            "error": "No transactions found",
            "analysis": {},
            "enhanced": {},
        }

    # Run semantic analysis
    analysis = analyze_transactions_semantic(txns)

    # Run enhanced financials derivation
    enhanced = derive_enhanced_financials(txns)

    # Pattern store stats
    store = get_pattern_store()

    return {
        "period": period,
        "dataset_id": ds_id,
        "analysis": analysis,
        "enhanced_financials": {
            "revenue_items": enhanced.get("revenue_items", []),
            "cogs_items": enhanced.get("cogs_items", []),
            "ga_expenses": enhanced.get("ga_expenses", []),
            "sga_breakdown": enhanced.get("sga_breakdown", {}),
            "finance": enhanced.get("finance", {}),
            "da": enhanced.get("da", 0),
            "tax": enhanced.get("tax", 0),
            "unclassified_sample": enhanced.get("unclassified", [])[:10],
        },
        "classification_stats": enhanced.get("stats", {}),
        "pattern_store": store.get_stats(),
    }


# ═══════════════════════════════════════════════════════════════════
#  GEORGIAN CHART OF ACCOUNTS (COA) ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/coa")
async def get_coa():
    """Full Georgian COA dictionary with all metadata for display."""
    from app.services.file_parser import GEORGIAN_COA
    entries = []
    for code, entry in sorted(GEORGIAN_COA.items(), key=lambda x: x[0]):
        entries.append({
            "code": code,
            "name_ka": entry.get("pl_ka") or entry.get("bs_ka", ""),
            "name_en": entry.get("pl") or entry.get("bs", ""),
            "type": "P&L" if entry.get("side") else ("BS" if entry.get("bs_side") else "Other"),
            "side": entry.get("side") or entry.get("bs_side", ""),
            "pl_line": entry.get("pl_line", ""),
            "bs_sub": entry.get("bs_sub", ""),
            "sub": entry.get("sub", ""),
            "segment": entry.get("segment", ""),
            "contra": entry.get("contra", False),
            "is_da": entry.get("is_da", False),
        })
    return {"entries": entries, "total": len(entries)}


@router.get("/diagnostics/bs-diff/{dataset_id}")
async def get_bs_diff(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Three-way diagnostic: raw parsed balance rows (from uploaded file),
    persisted BalanceSheetItem rows (DB), and aggregated IFRS BS built from persisted items.
    Returns a short summary plus samples for inspection.
    """
    ds = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "Dataset not found")

    parsed_raw = []
    # Try to re-parse original uploaded file if available
    if ds.upload_path and os.path.exists(ds.upload_path):
        try:
            with open(ds.upload_path, 'rb') as f:
                content = f.read()
            pf = parse_file(ds.original_filename or os.path.basename(ds.upload_path), content)
            parsed_raw = pf.get('balance_sheet_items', [])
        except Exception as e:
            logger.warning(f"Failed to reparse uploaded file for diagnostics: {e}")

    # Persisted DB items
    q = select(BalanceSheetItem).where(BalanceSheetItem.dataset_id == dataset_id)
    res = await db.execute(q)
    persisted_models = res.scalars().all()
    persisted = [p.to_dict() for p in persisted_models]

    # Aggregated IFRS from persisted items using existing builder
    try:
        agg = _build_bs_from_parsed_items(persisted_models, ds.period or "")
    except Exception as e:
        logger.error(f"BS aggregation error in diagnostics: {e}", exc_info=True)
        agg = {"rows": [], "totals": {}}

    # Simple diffs
    parsed_lines = set([r.get('ifrs_line_item') for r in parsed_raw if r.get('ifrs_line_item')])
    persisted_lines = set([p.get('ifrs_line_item') for p in persisted if p.get('ifrs_line_item')])
    missing_in_persisted = list(sorted(parsed_lines - persisted_lines))
    extra_in_persisted = list(sorted(persisted_lines - parsed_lines))

    return {
        "dataset_id": dataset_id,
        "dataset_name": ds.name,
        "counts": {
            "parsed_raw_count": len(parsed_raw),
            "persisted_count": len(persisted),
            "aggregated_lines": len(agg.get('rows', [])) if isinstance(agg, dict) else 0,
        },
        "samples": {
            "parsed_raw_sample": parsed_raw[:50],
            "persisted_sample": persisted[:50],
            "aggregated": agg,
        },
        "diffs": {
            "missing_in_persisted": missing_in_persisted[:50],
            "extra_in_persisted": extra_in_persisted[:50],
        }
    }


@router.get("/coa/coverage")
async def get_coa_coverage(dataset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """COA coverage statistics for a dataset — how many transactions map to known accounts."""
    from app.services.file_parser import map_coa
    ds_id = await _resolve_dataset_id(dataset_id, db)
    q = select(Transaction)
    if ds_id:
        q = q.where(Transaction.dataset_id == ds_id)
    result = await db.execute(q)
    txns = result.scalars().all()

    total = len(txns)
    if total == 0:
        return {"total_transactions": 0, "dr_classified": 0, "cr_classified": 0,
                "dr_coverage_pct": 0, "cr_coverage_pct": 0, "unmatched_codes": [], "top_prefixes": []}

    classified_dr = 0
    classified_cr = 0
    unmatched = set()
    prefixes = {}

    for t in txns:
        dr = map_coa(t.acct_dr or "")
        cr = map_coa(t.acct_cr or "")
        if dr:
            classified_dr += 1
            p = dr.get("prefix", "")
            prefixes[p] = prefixes.get(p, 0) + 1
        elif t.acct_dr:
            unmatched.add(str(t.acct_dr))
        if cr:
            classified_cr += 1
            p = cr.get("prefix", "")
            prefixes[p] = prefixes.get(p, 0) + 1
        elif t.acct_cr:
            unmatched.add(str(t.acct_cr))

    return {
        "total_transactions": total,
        "dr_classified": classified_dr,
        "cr_classified": classified_cr,
        "dr_coverage_pct": round(classified_dr / total * 100, 1),
        "cr_coverage_pct": round(classified_cr / total * 100, 1),
        "unmatched_codes": sorted(unmatched)[:50],
        "top_prefixes": sorted(prefixes.items(), key=lambda x: -x[1])[:20],
    }


@router.get("/coa/test")
async def test_coa_mapping(code: str = Query(..., description="Account code to test")):
    """Test what a specific account code maps to in the Georgian COA."""
    from app.services.file_parser import map_coa
    result = map_coa(code)
    if not result:
        return {"code": code, "matched": False, "mapping": None}
    return {"code": code, "matched": True, "mapping": result}


# ═══════════════════════════════════════════════════════════════════
#  CASH FLOW STATEMENT ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@router.get("/cash-flow")
async def get_cash_flow(
    dataset_id: Optional[int] = None,
    prior_dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Cash Flow Statement (indirect method).
    Requires current dataset; prior_dataset_id optional for change-based CFS.
    """
    from app.services.cash_flow import build_cash_flow

    ds_id = await _resolve_dataset_id(dataset_id, db)
    if not ds_id:
        raise HTTPException(status_code=400, detail="No active dataset found. Upload a dataset first.")

    # Auto-detect prior dataset if not provided
    prior_id = prior_dataset_id
    if not prior_id:
        result = await db.execute(
            select(Dataset.id)
            .where(Dataset.id < ds_id)
            .order_by(Dataset.id.desc())
            .limit(1)
        )
        row = result.first()
        prior_id = row[0] if row else None

    try:
        cfs = await build_cash_flow(db, ds_id, prior_id)
        reconciles = abs(cfs.cash_discrepancy) < 1.0
        return {
            "period_current": cfs.period,
            "period_prior": "",
            "currency": cfs.currency,
            "has_prior": prior_id is not None,
            "rows": cfs.to_rows(),
            "summary": {
                "operating": round(cfs.net_operating_cash, 2),
                "investing": round(cfs.net_investing_cash, 2),
                "financing": round(cfs.net_financing_cash, 2),
                "net_change": round(cfs.net_change_in_cash, 2),
                "beginning_cash": round(cfs.beginning_cash, 2),
                "ending_cash": round(cfs.ending_cash, 2),
                "reconciles": reconciles,
            },
            "notes": [cfs.note] if cfs.note else [],
        }
    except Exception as e:
        logger.error(f"Cash flow error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to build cash flow statement: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# RAW DATA EXPLORER — unified endpoint for all entity types
# ═══════════════════════════════════════════════════════════════════

_RAW_DATA_MODELS = {
    "transaction": Transaction,
    "revenue_item": RevenueItem,
    "cogs_item": COGSItem,
    "ga_expense": GAExpenseItem,
    "trial_balance_item": TrialBalanceItem,
    "balance_sheet_item": BalanceSheetItem,
}

_RAW_DATA_SEARCH_COLS = {
    "transaction": ["acct_dr", "acct_cr", "dept", "counterparty", "cost_class", "recorder"],
    "revenue_item": ["product", "segment", "category"],
    "cogs_item": ["product", "segment", "category"],
    "ga_expense": ["account_code", "account_name"],
    "trial_balance_item": ["account_code", "account_name", "sub_account_detail"],
    "balance_sheet_item": ["account_code", "account_name", "ifrs_line_item", "baku_bs_mapping"],
}

_RAW_DATA_COLUMNS = {
    "transaction": ["id", "date", "recorder", "acct_dr", "acct_cr", "dept", "counterparty", "cost_class", "type", "amount", "vat", "currency"],
    "revenue_item": ["id", "product", "gross", "vat", "net", "segment", "category", "eliminated"],
    "cogs_item": ["id", "product", "col6", "col7310", "col8230", "total_cogs", "segment", "category"],
    "ga_expense": ["id", "account_code", "account_name", "amount"],
    "trial_balance_item": ["id", "account_code", "account_name", "sub_account_detail", "opening_debit", "opening_credit", "turnover_debit", "turnover_credit", "closing_debit", "closing_credit", "net_pl_impact", "account_class", "hierarchy_level"],
    "balance_sheet_item": ["id", "account_code", "account_name", "ifrs_line_item", "ifrs_statement", "baku_bs_mapping", "intercompany_entity", "opening_balance", "turnover_debit", "turnover_credit", "closing_balance", "row_type"],
}


@router.get("/raw-data")
async def get_raw_data(
    entity_type: str = Query(..., description="transaction|revenue_item|cogs_item|ga_expense|trial_balance_item|balance_sheet_item"),
    dataset_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = "id",
    sort_dir: str = "asc",
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Unified raw data endpoint for browsing all parsed entity types with pagination."""
    if entity_type == "transaction":
        model = Transaction
    elif entity_type == "revenue_item":
        model = RevenueItem
    elif entity_type == "cogs_item":
        model = COGSItem
    elif entity_type == "ga_expense":
        model = GAExpenseItem
    elif entity_type == "trial_balance_item":
        model = TrialBalanceItem
    elif entity_type == "balance_sheet_item":
        model = BalanceSheetItem
    else:
        raise HTTPException(400, f"Unknown entity_type: {entity_type}")

    # Build query
    q = select(model)

    # Dataset filter
    if dataset_id and hasattr(model, 'dataset_id'):
        q = q.where(model.dataset_id == dataset_id)

    # Search filter
    if search:
        search_pattern = f"%{search}%"
        search_cols = _RAW_DATA_SEARCH_COLS.get(entity_type, [])
        from sqlalchemy import or_
        or_conditions = []
        for col_name in search_cols:
            col = getattr(model, col_name, None)
            if col is not None:
                or_conditions.append(col.ilike(search_pattern))
        if or_conditions:
            q = q.where(or_(*or_conditions))

    # Sort
    sort_col = getattr(model, sort_by, None) if sort_by else model.id
    if sort_col is None:
        sort_col = model.id
    if sort_dir.lower() == 'desc':
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col.asc())

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Pagination
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "entity_type": entity_type,
        "total": total,
        "offset": offset,
        "limit": limit,
        "columns": _RAW_DATA_COLUMNS.get(entity_type, []),
        "items": [item.to_dict() for item in items],
    }


# ═══════════════════════════════════════════════════════════════════
# TD ↔ BS CROSS-REFERENCE — reconcile Trial Balance vs Balance Sheet
# ═══════════════════════════════════════════════════════════════════

@router.get("/td-bs-crossref")
async def get_td_bs_crossref(
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Cross-reference TDSheet accounts against Balance Sheet IFRS lines.

    Fixed: Now properly excludes P&L items and counterparty-level detail.
    Only reconciles BS-classified accounts (classes 1-5) using summary rows
    ('სხვა') to avoid double-counting from counterparty detail ('საქვეანგარიშგებო').
    """
    ds_id = await _resolve_dataset_id(dataset_id, db)

    # Known Income Statement line items — must NOT appear in BS reconciliation
    IS_LINES = {
        'Revenue from sale of gas', 'Gas purchases', 'Other Cost of sale',
        'Other operating expenses', 'Wages, benefits and payroll taxes',
        'Other Non-operating Income', 'Net FX gain/(loss)',
        'Selling and Distribution costs', 'Selling and Distribution Costs',
        'Depreciation and amortization', 'Interest expense', 'Interest income',
        'Loss on disposal of property, plant and equipment',
        'Taxes, other than income tax', 'Revenue', 'Cost of sales',
        'Cost of Sales', 'COGS', 'Labour & HR', 'General & Administrative',
        'Sales Revenue', 'Other Revenue', 'Other Income', 'Other Expenses',
        'Finance Income', 'Finance Expense', 'Income Tax',
    }

    # Fetch TB items (level 1-2 only — meaningful account summaries)
    tb_q = select(TrialBalanceItem).where(
        TrialBalanceItem.dataset_id == ds_id,
        TrialBalanceItem.hierarchy_level.in_([1, 2]),
    )
    tb_items = (await db.execute(tb_q)).scalars().all()

    # Fetch BS items
    bs_q = select(BalanceSheetItem).where(BalanceSheetItem.dataset_id == ds_id)
    bs_items = (await db.execute(bs_q)).scalars().all()

    # Build TB lookup by account code (classes 1-5 = BS accounts only)
    tb_by_code = {}
    for tb in tb_items:
        if not tb.account_code:
            continue
        code = tb.account_code.strip()
        acct_class = (tb.account_class or "").strip()
        # Only include BS-related classes (1-5) in reconciliation
        if acct_class not in ("1", "2", "3", "4", "5"):
            continue
        # Use same DR-CR sign convention as BS items for consistency
        # (BS items from the Balance sheet store closing_balance as DR-CR)
        closing = (tb.closing_debit or 0) - (tb.closing_credit or 0)
        tb_by_code[code] = {
            "code": code,
            "name": tb.account_name or "",
            "closing_debit": tb.closing_debit or 0,
            "closing_credit": tb.closing_credit or 0,
            "net_closing": closing,
            "class": acct_class,
            "level": tb.hierarchy_level or 1,
        }

    # Determine if BS data was auto-generated (COA_DERIVED) or parsed from Excel
    has_coa_derived = any(
        (getattr(bsi, 'row_type', '') or '') == 'COA_DERIVED' for bsi in bs_items
    )

    # For parsed BS data: use summary rows ('სხვა') to avoid counterparty double-counting
    # For COA_DERIVED data: all rows are leaf accounts, use all
    # Group BS items by IFRS line
    ifrs_groups = {}
    for bsi in bs_items:
        ifrs_line = (bsi.ifrs_line_item or "").strip()
        if not ifrs_line:
            continue
        # Skip P&L items — they don't belong in BS reconciliation
        if ifrs_line in IS_LINES:
            continue
        # Check ifrs_statement field: skip if explicitly marked as P&L
        ifrs_stmt = (bsi.ifrs_statement or "").strip().upper()
        if ifrs_stmt in ("PL", "P&L", "IS"):
            continue

        row_type = (bsi.row_type or "").strip()
        code = (bsi.account_code or "").strip()

        # For parsed Excel data: only use summary rows ('სხვა'), not counterparty
        # detail ('საქვეანგარიშგებო') to avoid 2000+ duplicate entries
        if not has_coa_derived and row_type == 'საქვეანგარიშგებო':
            continue

        if ifrs_line not in ifrs_groups:
            ifrs_groups[ifrs_line] = {
                "ifrs_line": ifrs_line,
                "baku_mapping": bsi.baku_bs_mapping or "",
                "ifrs_statement": bsi.ifrs_statement or "",
                "bs_total": 0,
                "td_total": 0,
                "td_matched": False,
                "accounts": [],
            }
        grp = ifrs_groups[ifrs_line]
        bs_amount = bsi.closing_balance or 0
        grp["bs_total"] += bs_amount

        # Find matching TD item by exact code
        td_item = tb_by_code.get(code, None)
        td_amount = td_item["net_closing"] if td_item else 0
        if td_item:
            grp["td_matched"] = True
        grp["td_total"] += td_amount

        grp["accounts"].append({
            "code": code,
            "name": bsi.account_name or "",
            "bs_amount": round(bs_amount, 2),
            "td_amount": round(td_amount, 2),
            "row_type": row_type,
            "matched": abs(bs_amount - td_amount) < 1.0,
        })

    # Build result
    crossref = []
    matched_count = 0
    total_lines = len(ifrs_groups)

    for ifrs_line, grp in sorted(ifrs_groups.items()):
        grp["bs_total"] = round(grp["bs_total"], 2)
        grp["td_total"] = round(grp["td_total"], 2)
        grp["difference"] = round(grp["bs_total"] - grp["td_total"], 2)
        grp["matched"] = abs(grp["difference"]) < 1.0
        if grp["matched"]:
            matched_count += 1
        crossref.append(grp)

    return {
        "crossref": crossref,
        "summary": {
            "total_lines": total_lines,
            "matched": matched_count,
            "mismatched": total_lines - matched_count,
            "match_pct": round(matched_count / total_lines * 100, 1) if total_lines > 0 else 0,
        },
        "has_bs_data": len(bs_items) > 0,
        "has_tb_data": len(tb_items) > 0,
    }


# ═══════════════════════════════════════════════════════════════════
# FINANCIAL INTELLIGENCE — Suggestions & Mapping Enrichment
# ═══════════════════════════════════════════════════════════════════

@router.get("/suggestions")
async def get_suggestions(
    dataset_id: Optional[int] = None,
    context: str = Query("dashboard", description="Page context: dashboard|mr|tb|pl|bs|cogs|revenue"),
    db: AsyncSession = Depends(get_db),
):
    """Contextual, proactive suggestions based on dataset state and page context.

    Returns intelligent suggestions like:
    - Prior year dataset available for MR comparison
    - Budget data available for plan vs actual
    - Unmapped TB accounts needing attention
    - Data completeness tips
    """
    ds_id = await _resolve_dataset_id(dataset_id, db)
    if not ds_id:
        return {"suggestions": [], "context": context, "dataset_id": None}

    from app.services.financial_intelligence import SuggestionEngine
    engine = SuggestionEngine(db)

    try:
        suggestions = await engine.get_suggestions(ds_id, context=context)
    except Exception as e:
        logger.warning(f"SuggestionEngine error: {e}")
        suggestions = []

    return {
        "suggestions": suggestions,
        "context": context,
        "dataset_id": ds_id,
    }


@router.get("/capabilities")
async def get_capabilities(
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """The 'brain query' — ask the system what it knows about a dataset.

    Returns the full DataManifest: what data exists, what reports are possible,
    what's missing, linked datasets, financial totals, and data richness score.

    This endpoint is what makes FinAI intelligent — it doesn't just store data,
    it *thinks* about what the data means and what can be done with it.
    """
    ds_id = await _resolve_dataset_id(dataset_id, db, context="dashboard")
    if not ds_id:
        return {"error": "No dataset found", "capabilities": None}

    from app.services.financial_intelligence import DatasetIntelligence

    try:
        intel = DatasetIntelligence(db)
        manifest = await intel.analyze_quick(ds_id)
        if not manifest:
            return {"error": f"Dataset {ds_id} not found", "capabilities": None}

        return {
            "dataset_id": ds_id,
            "capabilities": manifest.to_dict(),
            "summary": manifest.summary,
            "richness_score": manifest.data_richness_score,
            "report_capabilities": manifest.report_capabilities,
            "missing": manifest.missing,
            "linked_datasets": {
                "prior_year": {
                    "dataset_id": manifest.prior_year_dataset_id,
                    "period": manifest.prior_year_period,
                    "has_data": manifest.prior_year_has_data,
                } if manifest.prior_year_dataset_id else None,
                "budget_source": {
                    "dataset_id": manifest.budget_source_dataset_id,
                    "source": manifest.budget_source,
                } if manifest.budget_source_dataset_id else None,
            },
        }
    except Exception as e:
        logger.error(f"Capabilities error: {e}", exc_info=True)
        return {"error": str(e), "capabilities": None}


@router.get("/datasets/periods")
async def get_dataset_periods(db: AsyncSession = Depends(get_db)):
    """Return all available dataset periods for dropdowns (prior year selector, etc.)."""
    from app.services.financial_intelligence import DatasetDiscovery
    discovery = DatasetDiscovery(db)
    periods = await discovery.find_all_periods()
    return {"periods": periods}


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD SUMMARY API — Powers modern dashboard without IndexedDB
# ═══════════════════════════════════════════════════════════════════

@router.get("/dashboard-summary")
async def dashboard_summary(
    period: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Return comprehensive dashboard data: KPIs, trends, alerts, health score."""
    # Find the active period
    if not period:
        latest = await db.execute(
            select(Dataset.period).where(Dataset.is_seed == True)
            .order_by(Dataset.id.desc()).limit(1)
        )
        period = latest.scalar() or "January 2025"

    # Get dataset for this period
    ds_q = await db.execute(
        select(Dataset).where(Dataset.period == period, Dataset.is_seed == True).limit(1)
    )
    ds = ds_q.scalar()
    if not ds:
        return {"error": f"No dataset for period {period}", "kpis": {}, "trends": []}

    # Revenue
    rev_q = await db.execute(
        select(func.sum(RevenueItem.net), func.sum(RevenueItem.gross), func.count(RevenueItem.id))
        .where(RevenueItem.dataset_id == ds.id)
    )
    rev_net, rev_gross, rev_count = rev_q.one()
    rev_net = rev_net or 0
    rev_gross = rev_gross or 0

    # Expenses
    exp_q = await db.execute(
        select(func.sum(Transaction.amount), func.count(Transaction.id))
        .where(Transaction.dataset_id == ds.id, Transaction.type == 'Expense')
    )
    total_exp, txn_count = exp_q.one()
    total_exp = total_exp or 0

    # Budget
    bud_q = await db.execute(
        select(BudgetLine.line_item, BudgetLine.budget_amount, BudgetLine.actual_amount)
        .where(BudgetLine.dataset_id == ds.id)
    )
    budget_lines = {row[0]: {"budget": row[1], "actual": row[2]} for row in bud_q.all()}

    cogs = budget_lines.get('COGS', {}).get('budget', 0) or 0
    budget_rev = budget_lines.get('Revenue', {}).get('budget', 0) or 0
    gross_margin = rev_net - cogs
    gm_pct = (gross_margin / rev_net * 100) if rev_net > 0 else 0
    rev_vs_bud = rev_net - budget_rev
    rev_vs_bud_pct = (rev_vs_bud / budget_rev * 100) if budget_rev > 0 else 0

    # 12-month trends
    all_periods_q = await db.execute(
        select(Dataset.id, Dataset.period).where(Dataset.is_seed == True)
        .order_by(Dataset.id)
    )
    all_periods = all_periods_q.all()

    trends = []
    for ds_id, ds_period in all_periods:
        rev_sum = await db.execute(
            select(func.sum(RevenueItem.net)).where(RevenueItem.dataset_id == ds_id)
        )
        exp_sum = await db.execute(
            select(func.sum(Transaction.amount))
            .where(Transaction.dataset_id == ds_id, Transaction.type == 'Expense')
        )
        r = rev_sum.scalar() or 0
        e = exp_sum.scalar() or 0
        trends.append({
            "period": ds_period,
            "revenue": round(r, 2),
            "expenses": round(e, 2),
            "gross_margin": round(r - cogs * (r / rev_net if rev_net else 1), 2),
        })

    # Alerts
    alerts = []
    whl_margin = budget_lines.get('Gr. Margin Wholesale', {}).get('budget', 0) or 0
    if whl_margin < 0:
        alerts.append({"severity": "critical", "message": f"Wholesale margin NEGATIVE: {fgel(whl_margin)}", "action": "Review pricing"})
    if rev_vs_bud < 0:
        alerts.append({"severity": "warning", "message": f"Revenue below budget by {fgel(abs(rev_vs_bud))}", "action": "Investigate shortfall"})

    return {
        "period": period,
        "company": ds.company or settings.COMPANY_NAME,
        "currency": ds.currency or "GEL",
        "kpis": {
            "revenue": round(rev_net, 2),
            "revenue_gross": round(rev_gross, 2),
            "cogs": round(cogs, 2),
            "gross_margin": round(gross_margin, 2),
            "gross_margin_pct": round(gm_pct, 2),
            "opex": round(total_exp, 2),
            "net_estimate": round(gross_margin - total_exp, 2),
            "budget_revenue": round(budget_rev, 2),
            "rev_vs_budget": round(rev_vs_bud, 2),
            "rev_vs_budget_pct": round(rev_vs_bud_pct, 2),
            "transaction_count": txn_count or 0,
            "product_count": rev_count or 0,
        },
        "trends": trends,
        "alerts": alerts,
        "budget_lines": {k: v for k, v in budget_lines.items()},
    }


@router.get("/trend")
async def get_trend(
    metric: str = Query("revenue", description="Metric: revenue, expenses, gross_margin"),
    periods: int = Query(12, description="Number of periods"),
    db: AsyncSession = Depends(get_db),
):
    """Return time-series data for a specific metric across periods."""
    ds_q = await db.execute(
        select(Dataset.id, Dataset.period).where(Dataset.is_seed == True)
        .order_by(Dataset.id).limit(periods)
    )
    datasets = ds_q.all()

    result = []
    for ds_id, ds_period in datasets:
        value = 0
        if metric == "revenue":
            q = await db.execute(select(func.sum(RevenueItem.net)).where(RevenueItem.dataset_id == ds_id))
            value = q.scalar() or 0
        elif metric == "expenses":
            q = await db.execute(
                select(func.sum(Transaction.amount))
                .where(Transaction.dataset_id == ds_id, Transaction.type == 'Expense')
            )
            value = q.scalar() or 0
        elif metric == "transactions":
            q = await db.execute(
                select(func.count(Transaction.id)).where(Transaction.dataset_id == ds_id)
            )
            value = q.scalar() or 0
        result.append({"period": ds_period, "value": round(value, 2)})

    return {"metric": metric, "data": result}
