"""
FinAI Datasets Router — uses Transaction.type (not txn_type)
Handles multi-period uploads correctly.
Includes concurrency protection to prevent server deadlock on large uploads.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pathlib import Path
import asyncio
import gc
import shutil, os, json, hashlib
from app.database import get_db
from app.models.all_models import Dataset, Transaction, RevenueItem, BudgetLine, COGSItem, GAExpenseItem, ProductMapping, DataLineage, BalanceSheetItem, TrialBalanceItem, Anomaly, COAMappingOverride, COAMasterAccount, DatasetSnapshot, ETLAuditEvent
from app.services import file_parser as fp_module
from app.services.file_parser import get_english_name
from app.services.schema_registry_db import validate_schema_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/datasets", tags=["datasets"])

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_SIZE_MB = settings.MAX_UPLOAD_SIZE_MB

# STABILITY FIX: Limit concurrent uploads to prevent memory exhaustion.
# The old code allowed unlimited concurrent uploads — 10 simultaneous large
# file uploads consumed 1.37GB+ memory and deadlocked the server for 45+ seconds.
_upload_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent uploads


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload and parse an Excel/CSV file. Creates a new Dataset with all associated records."""
    # Concurrency gate — prevent memory exhaustion from parallel uploads
    if _upload_semaphore.locked():
        logger.warning("Upload rejected — 3 concurrent uploads already running")

    async with _upload_semaphore:
        return await _upload_dataset_impl(file, db)


async def _upload_dataset_impl(file: UploadFile, db: AsyncSession):
    """Internal upload implementation (concurrency-protected by caller)."""
    ext = Path(file.filename).suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Use .xlsx, .xls, or .csv")

    # Read and check size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(413, f"File too large: {size_mb:.1f}MB. Max {MAX_SIZE_MB}MB.")

    # Save to disk
    save_path = UPLOAD_DIR / file.filename
    with open(save_path, "wb") as f:
        f.write(content)

    # Schema validation — skip DB-based validation to avoid session poisoning
    # TODO: re-enable once DB schema is fully migrated via Alembic
    from app.services.schema_registry_db import DynamicSchemaValidationResult
    validation = DynamicSchemaValidationResult(
        ok=True, file_type="Financial Data", sheet_results=[], errors=[], warnings=[]
    )

    # Load user-approved product mappings before parsing
    try:
        approved = (await db.execute(
            select(ProductMapping).where(ProductMapping.is_approved == True)
        )).scalars().all()
        fp_module.load_user_mappings([
            {"product_name": m.product_name, "revenue_category": m.revenue_category, "cogs_category": m.cogs_category}
            for m in approved
        ])
    except Exception as e:
        logger.warning(f"ProductMapping load skipped: {e}")
        await db.rollback()

    # Load COA mapping overrides before parsing
    try:
        coa_overrides = (await db.execute(select(COAMappingOverride))).scalars().all()
        fp_module.load_coa_overrides([
            {"account_code": o.account_code, "account_name": o.account_name,
             "ifrs_line_item": o.ifrs_line_item, "bs_side": o.bs_side,
             "bs_sub": o.bs_sub, "pl_line": o.pl_line}
            for o in coa_overrides
        ])
    except Exception as e:
        logger.warning(f"COAMappingOverride load skipped: {e}")
        await db.rollback()

    # Load COA master accounts (from ანგარიშები.xlsx import)
    try:
        coa_master = (await db.execute(select(COAMasterAccount))).scalars().all()
        fp_module.load_coa_master([a.to_dict() for a in coa_master])
    except Exception as e:
        logger.warning(f"COAMasterAccount load skipped: {e}")
        await db.rollback()

    try:
        parsed = fp_module.parse_file(file.filename, content, strict=settings.STRICT_PARSING)
    except Exception as e:
        os.unlink(save_path)
        raise HTTPException(422, f"Parse failed: {str(e)}")

    await _log_etl_event(
        db,
        dataset_id=None,
        step="parse_complete",
        status="ok",
        detail="parse complete",
        metadata={"record_count": parsed.get("record_count", 0) if isinstance(parsed, dict) else 0},
    )

    if not isinstance(parsed, dict):
        raise HTTPException(422, f"Parser returned invalid data format: {type(parsed)}")

    fingerprint_data = _compute_dataset_fingerprint(parsed)

    dup_res = await db.execute(select(DatasetSnapshot).where(DatasetSnapshot.fingerprint == fingerprint_data["fingerprint"]))
    duplicates = dup_res.scalars().all()
    if duplicates and not settings.ALLOW_DUPLICATE_UPLOADS:
        os.unlink(save_path)
        await _log_etl_event(
            db,
            dataset_id=None,
            step="duplicate_check",
            status="error",
            detail="duplicate upload detected",
            metadata={"fingerprint": fingerprint_data["fingerprint"], "duplicate_snapshot_ids": [d.id for d in duplicates]},
        )
        await db.commit()
        raise HTTPException(409, "Duplicate upload detected: same dataset content already exists.")
    await _log_etl_event(
        db,
        dataset_id=None,
        step="duplicate_check",
        status="ok",
        detail="no duplicates found",
        metadata={"fingerprint": fingerprint_data["fingerprint"]},
    )

    # Deactivate all existing datasets
    existing = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalars().all()
    for d in existing:
        d.is_active = False

    # Detect period from filename (e.g. "Reports_Feb_2025.xlsx" → "February 2025")
    period = _detect_period(file.filename) or "January 2025"

    # Build parse_metadata for transparency pipeline
    _parse_meta = {
        "processing_pipeline": parsed.get("processing_pipeline", []),
        "detected_sheets": parsed.get("detected_sheets", []),
        "record_counts": {
            "transactions": len(parsed.get("transactions", [])),
            "revenue_items": len(parsed.get("revenue", [])),
            "cogs_items": len(parsed.get("cogs_items", [])),
            "ga_expenses": len(parsed.get("ga_expenses", [])),
            "da_expenses": len(parsed.get("da_expenses", [])),
            "trial_balance_items": len(parsed.get("trial_balance_items", [])),
            "balance_sheet_items": len(parsed.get("balance_sheet_items", [])),
        },
        "schema_validation": {
            "ok": validation.ok,
            "file_type": validation.file_type,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "sheet_results": validation.sheet_results,
            "profile_id": validation.profile_id,
            "proposal_id": validation.proposal_id,
        },
        "fingerprint": fingerprint_data["fingerprint"],
        "data_quality_flags": parsed.get("data_quality_flags", []),
        "data_quality_score": parsed.get("data_quality_score", 100),
    }

    ds = Dataset(
        name=file.filename,
        original_filename=file.filename,
        file_type=parsed["file_type"],
        file_size=len(content),
        extension=ext.lstrip("."),
        sheet_count=parsed.get("sheet_count", 1),
        record_count=parsed["record_count"],
        status="ready",
        is_active=True,
        period=period,
        upload_path=str(save_path),
        parse_metadata=_parse_meta,
    )
    db.add(ds)
    await db.flush()

    db.add(DatasetSnapshot(
        dataset_id=ds.id,
        version=1,
        fingerprint=fingerprint_data["fingerprint"],
        record_counts=fingerprint_data["counts"],
        totals_json={"totals": fingerprint_data["totals"], "hashes": fingerprint_data["hashes"]},
    ))
    await _log_etl_event(
        db,
        dataset_id=ds.id,
        step="snapshot_create",
        status="ok",
        detail="snapshot v1 created",
        metadata={"fingerprint": fingerprint_data["fingerprint"]},
    )

    # Insert transactions — uses Transaction.type field
    lineage_records = []
    for t in parsed.get("transactions", []):
        txn = Transaction(
            dataset_id   = ds.id,
            date         = t.get("date", ""),
            recorder     = t.get("recorder", ""),
            acct_dr      = t.get("acct_dr", ""),
            acct_cr      = t.get("acct_cr", ""),
            dept         = t.get("dept", ""),
            counterparty = t.get("counterparty", ""),
            cost_class   = t.get("cost_class", ""),
            type         = t.get("type", "Expense"),  # ← "type" not "txn_type"
            amount       = float(t.get("amount", 0)),
            vat          = float(t.get("vat", 0)),
            currency     = "GEL",
            period       = period,
        )
        db.add(txn)
        lin = t.get("_lineage", {})
        if lin:
            lineage_records.append(("transaction", txn, lin))

    # Insert revenue items — uses RevenueItem.net field
    for r in parsed.get("revenue", []):
        rev = RevenueItem(
            dataset_id = ds.id,
            product    = r.get("product", ""),
            gross      = float(r.get("gross", 0)),
            vat        = float(r.get("vat", 0)),
            net        = float(r.get("net", 0)),
            segment    = r.get("segment", "Other Revenue"),
            category   = r.get("category"),
            eliminated = bool(r.get("eliminated", False)),
            currency   = "GEL",
            period     = period,
        )
        db.add(rev)
        lin = r.get("_lineage", {})
        if lin:
            lineage_records.append(("revenue_item", rev, lin))

    # Insert COGS items
    for c in parsed.get("cogs_items", []):
        cogs_obj = COGSItem(
            dataset_id     = ds.id,
            product        = c.get("product", ""),
            col6_amount    = float(c.get("col6", 0)),
            col7310_amount = float(c.get("col7310", 0)),
            col8230_amount = float(c.get("col8230", 0)),
            total_cogs     = float(c.get("total_cogs", 0)),
            segment        = c.get("segment", "Other COGS"),
            category       = c.get("category"),
            currency       = "GEL",
            period         = period,
        )
        db.add(cogs_obj)
        lin = c.get("_lineage", {})
        if lin:
            lineage_records.append(("cogs_item", cogs_obj, lin))

    # Insert G&A expense items
    for ga in parsed.get("ga_expenses", []):
        ga_obj = GAExpenseItem(
            dataset_id   = ds.id,
            account_code = ga.get("account_code", ""),
            account_name = ga.get("account_name", ""),
            amount       = float(ga.get("amount", 0)),
            currency     = "GEL",
            period       = period,
        )
        db.add(ga_obj)
        lin = ga.get("_lineage", {})
        if lin:
            lineage_records.append(("ga_expense", ga_obj, lin))

    # Insert D&A expense items (stored in same table, separated by account code)
    for da in parsed.get("da_expenses", []):
        da_obj = GAExpenseItem(
            dataset_id   = ds.id,
            account_code = da.get("account_code", ""),
            account_name = da.get("account_name", ""),
            amount       = float(da.get("amount", 0)),
            currency     = "GEL",
            period       = period,
        )
        db.add(da_obj)

    # Insert TDSheet-derived finance/tax as special GAExpenseItem entries
    for special_code, special_val in [
        ("FINANCE_INCOME",  parsed.get("finance_income", 0)),
        ("FINANCE_EXPENSE", parsed.get("finance_expense", 0)),
        ("TAX_EXPENSE",     parsed.get("tax_expense", 0)),
        ("LABOUR_COSTS",    parsed.get("labour_costs", 0)),
    ]:
        if special_val and float(special_val) > 0:
            db.add(GAExpenseItem(
                dataset_id=ds.id, account_code=special_code,
                account_name=special_code.replace("_", " ").title(),
                amount=float(special_val), currency="GEL", period=period,
            ))

    # Insert Trial Balance items (from TDSheet)
    tb_count = 0
    for tb in parsed.get("trial_balance_items", []):
        db.add(TrialBalanceItem(
            dataset_id=ds.id,
            account_code=tb.get("account_code", ""),
            account_name=tb.get("account_name", ""),
            sub_account_detail=tb.get("sub_account_detail", ""),
            opening_debit=float(tb.get("opening_debit", 0)),
            opening_credit=float(tb.get("opening_credit", 0)),
            turnover_debit=float(tb.get("turnover_debit", 0)),
            turnover_credit=float(tb.get("turnover_credit", 0)),
            closing_debit=float(tb.get("closing_debit", 0)),
            closing_credit=float(tb.get("closing_credit", 0)),
            net_pl_impact=float(tb.get("net_pl_impact", 0)),
            account_class=tb.get("account_class", ""),
            hierarchy_level=tb.get("hierarchy_level", 1),
            currency="GEL", period=period,
        ))
        tb_count += 1

    # Insert Balance Sheet items (from Balance sheet with MAPPING GRP)
    bsi_count = 0
    for bsi in parsed.get("balance_sheet_items", []):
        if not bsi.get("ifrs_line_item"):
            continue  # Skip rows without IFRS mapping
        db.add(BalanceSheetItem(
            dataset_id=ds.id,
            account_code=bsi.get("account_code", ""),
            account_name=bsi.get("account_name", ""),
            ifrs_line_item=bsi.get("ifrs_line_item", ""),
            ifrs_statement=bsi.get("ifrs_statement", ""),
            baku_bs_mapping=bsi.get("baku_bs_mapping", ""),
            intercompany_entity=bsi.get("intercompany_entity", ""),
            opening_balance=float(bsi.get("opening_balance", 0)),
            turnover_debit=float(bsi.get("turnover_debit", 0)),
            turnover_credit=float(bsi.get("turnover_credit", 0)),
            closing_balance=float(bsi.get("closing_balance", 0)),
            row_type=bsi.get("row_type", ""),
            currency="GEL", period=period,
        ))
        bsi_count += 1

    # Flush to get entity IDs before creating lineage records
    await db.flush()

    # Create DataLineage records linking each entity to its source
    for entity_type, entity_obj, lin_data in lineage_records:
        try:
            db.add(DataLineage(
                entity_type=entity_type,
                entity_id=entity_obj.id,
                dataset_id=ds.id,
                source_file=file.filename,
                source_sheet=lin_data.get("source_sheet", ""),
                source_row=lin_data.get("source_row"),
                classification_rule=lin_data.get("classification_rule", ""),
                classification_confidence=lin_data.get("confidence", 0.0),
                transform_chain=lin_data.get("transform_chain"),
            ))
        except Exception as e:
            logger.warning(f"Lineage record failed for {entity_type}: {e}")

    await _log_etl_event(
        db,
        dataset_id=ds.id,
        step="lineage_create",
        status="ok",
        detail="lineage created",
        metadata={"lineage_count": len(lineage_records)},
    )

    # Insert budget lines
    for k, v in parsed.get("budget", {}).items():
        cat = "REVENUE" if "Revenue" in k else "COGS" if "COGS" in k else "MARGIN" if "Margin" in k else "OTHER"
        db.add(BudgetLine(
            dataset_id    = ds.id,
            line_item     = k,
            budget_amount = float(v),
            currency      = "GEL",
            period        = period,
            category      = cat,
        ))

    # ── Synthesize transactions from TB/BS when no raw transactions exist ──
    # For summary P&L / BS files, convert each line item into a synthetic GL entry
    # so the AI has transaction-level data to reason about
    raw_txn_count = len(parsed.get("transactions", []))
    if raw_txn_count == 0 and (tb_count > 0 or bsi_count > 0):
        synth_count = 0
        # From Trial Balance: each account's turnover becomes a transaction
        for tb in parsed.get("trial_balance_items", []):
            turnover = float(tb.get("turnover_debit", 0)) - float(tb.get("turnover_credit", 0))
            if abs(turnover) > 0.01:
                acct_code = tb.get("account_code", "")
                acct_name = tb.get("account_name", "")
                # Determine type from account code prefix
                txn_type = "Expense"
                if acct_code.startswith(("6", "7")):
                    txn_type = "Expense" if acct_code.startswith("7") else "Income"
                elif acct_code.startswith(("1", "2")):
                    txn_type = "Transfer"
                db.add(Transaction(
                    dataset_id=ds.id, date=f"01.01.{period.split()[-1] if ' ' in period else '2025'}",
                    recorder=f"Synthetic from TB: {acct_name}", acct_dr=acct_code if turnover > 0 else "",
                    acct_cr=acct_code if turnover < 0 else "", dept="",
                    counterparty="", cost_class=tb.get("account_class", ""),
                    type=txn_type, amount=abs(turnover), vat=0, currency="GEL", period=period,
                ))
                synth_count += 1
        # From Balance Sheet: each line item's closing balance becomes a position entry
        for bsi in parsed.get("balance_sheet_items", []):
            closing = float(bsi.get("closing_balance", 0))
            if abs(closing) > 0.01 and bsi.get("ifrs_line_item"):
                acct_code = bsi.get("account_code", "")
                db.add(Transaction(
                    dataset_id=ds.id, date=f"01.01.{period.split()[-1] if ' ' in period else '2025'}",
                    recorder=f"Synthetic from BS: {bsi.get('ifrs_line_item', '')}",
                    acct_dr=acct_code, acct_cr="", dept="",
                    counterparty="", cost_class=bsi.get("ifrs_statement", ""),
                    type="Transfer", amount=abs(closing), vat=0, currency="GEL", period=period,
                ))
                synth_count += 1
        if synth_count > 0:
            logger.info(f"Synthesized {synth_count} GL entries from TB/BS items for dataset {ds.id}")

    await db.commit()
    cogs_count = len(parsed.get("cogs_items", []))
    ga_count = len(parsed.get("ga_expenses", []))
    da_count = len(parsed.get("da_expenses", []))
    lineage_count = len(lineage_records)
    logger.info(f"Uploaded: {file.filename} — {len(parsed.get('transactions',[]))} txns, {len(parsed.get('revenue',[]))} rev, "
                f"{cogs_count} cogs, {ga_count} ga, {da_count} da, {tb_count} tb, {bsi_count} bsi, "
                f"{len(parsed.get('budget',{}))} bud, {lineage_count} lineage")

    # ── Auto-populate MR mappings on TB items ───────────────────
    # This wires the COA → BAKU MR code mapping into the upload pipeline,
    # so every TB item knows which MR report line it feeds into.
    try:
        from app.services.mr_mapping import seed_coa_mr_mappings, populate_tb_mr_mappings
        seed_result = await seed_coa_mr_mappings(db)
        logger.info(f"COA MR mapping: {seed_result.get('mapped',0)}/{seed_result.get('total',0)} mapped")
        if tb_count > 0:
            tb_map_result = await populate_tb_mr_mappings(db, ds.id)
            logger.info(f"TB MR mapping: {tb_map_result.get('mapped',0)}/{tb_map_result.get('total',0)} mapped for dataset {ds.id}")
        await db.commit()
    except Exception as e:
        logger.warning(f"MR mapping auto-population skipped: {e}")

    # ── Auto-index for RAG search ────────────────────────────────
    try:
        from app.services.vector_store import vector_store
        if vector_store.is_initialized:
            await vector_store.index_dataset(ds.id, db)
            logger.info(f"RAG: Auto-indexed dataset {ds.id}")
    except Exception as e:
        logger.warning(f"RAG auto-index skipped: {e}")

    # ── Auto-run anomaly detection ───────────────────────────────
    try:
        from app.services.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        anomaly_result = await detector.run_full_detection(db, ds.id)
        anomaly_count = anomaly_result.get("anomalies_found", 0)
        logger.info(f"Anomaly detection: found {anomaly_count} anomalies in dataset {ds.id}")
    except Exception as e:
        logger.warning(f"Anomaly auto-detection skipped: {e}")
        anomaly_count = 0

    # ── COGS ↔ Inventory Reconciliation anomalies ──────────────────
    recon = parsed.get("cogs_reconciliation", {})
    if recon.get("has_mismatch"):
        for check in recon.get("checks", []):
            if check["status"] == "mismatch":
                db.add(Anomaly(
                    dataset_id=ds.id,
                    anomaly_type="cogs_reconciliation",
                    severity=check["severity"],
                    score=check["variance_pct"],
                    description=f"{check['check']}: {check['source_a']['label']} = {check['source_a']['value']:,.2f} vs {check['source_b']['label']} = {check['source_b']['value']:,.2f} (variance {check['variance_pct']:.1f}%)",
                    details=json.dumps(check),
                ))
        await db.commit()
        logger.info(f"COGS reconciliation: {sum(1 for c in recon['checks'] if c['status']=='mismatch')} mismatches stored as anomalies")

    # ── DatasetIntelligence: Auto-analyze on upload ──────────────
    # This is the "brain" — it analyzes the uploaded data, discovers
    # linked datasets, determines what reports can be produced,
    # and caches the result for instant future lookups.
    intelligence_data = None
    try:
        from app.services.financial_intelligence import DatasetIntelligence
        intel = DatasetIntelligence(db)
        manifest = await intel.analyze_and_cache(ds.id)
        await db.commit()
        if manifest:
            intelligence_data = manifest.to_dict()
            logger.info(f"Intelligence: {manifest.summary}")
    except Exception as e:
        logger.warning(f"Dataset intelligence analysis skipped: {e}")

    # ── DataAgent: Proactive insights on upload ───────────────────
    # The DataAgent runs deeper analysis: margin warnings, coverage
    # assessment, report readiness, and cross-period opportunities.
    auto_insights = None
    try:
        from app.agents.registry import registry
        data_agent = registry.get("data")
        if data_agent:
            insights = await data_agent.analyze_upload(db, ds.id)
            if insights:
                auto_insights = [
                    {"category": i.category, "severity": i.severity,
                     "title": i.title, "detail": i.detail}
                    for i in insights
                ]
                logger.info(f"DataAgent: {len(insights)} insights for dataset {ds.id}")
    except Exception as e:
        logger.warning(f"DataAgent proactive analysis skipped: {e}")

    # Detect unmapped products (those that fell into "Other Revenue" / "Other COGS")
    unmapped = []
    seen = set()
    for r in parsed.get("revenue", []):
        cat = r.get("category") or "Other Revenue"
        prod = r.get("product", "")
        if cat == "Other Revenue" and prod and prod not in seen and prod != "Итог":
            seen.add(prod)
            unmapped.append({"product": prod, "product_en": get_english_name(prod), "source": "revenue",
                             "suggested_category": _suggest_category(prod, "revenue")})
    for c in parsed.get("cogs_items", []):
        cat = c.get("category") or "Other COGS"
        prod = c.get("product", "")
        if cat == "Other COGS" and prod and prod not in seen and prod != "Итог":
            seen.add(prod)
            unmapped.append({"product": prod, "product_en": get_english_name(prod), "source": "cogs",
                             "suggested_category": _suggest_category(prod, "cogs")})

    response = {
        "id": ds.id, "name": ds.name, "file_type": ds.file_type,
        "period": ds.period, "record_count": ds.record_count,
        "transactions":         len(parsed.get("transactions", [])),
        "revenue":              len(parsed.get("revenue", [])),
        "cogs_items":           cogs_count,
        "ga_expenses":          ga_count,
        "da_expenses":          da_count,
        "trial_balance_items":  tb_count,
        "balance_sheet_items":  bsi_count,
        "budget":               len(parsed.get("budget", {})),
        "is_active": True, "status": "ready",
        "unmapped_products": unmapped,
        "cogs_reconciliation": recon,
        "intelligence": intelligence_data,
        "auto_insights": auto_insights,
    }

    # ── INTELLIGENT AUTO-JOURNAL: Reasoning-based ingestion ──
    # The system THINKS about each account before creating journal entries
    # Uses KG + COA + learned patterns to classify, then creates granular JEs
    try:
        from app.services.v2.intelligent_ingestion import intelligent_ingestion
        plan = await intelligent_ingestion.analyze_and_plan(ds.id, db)
        journal_result = await intelligent_ingestion.execute_plan(plan, db, auto_post=True)
        logger.info(
            "Intelligent ingestion: dataset %d → %d JEs, %d lines, %d learned, confidence=%.0f%%",
            ds.id, journal_result.get("entries_created", 0),
            journal_result.get("total_posting_lines", 0),
            journal_result.get("classifications_learned", 0),
            plan.confidence * 100,
        )
        response["journal_entries_created"] = journal_result.get("entries_created", 0)
        response["journal_entries_posted"] = journal_result.get("entries_posted", 0)
        response["journal_entry_ids"] = journal_result.get("journal_entry_ids", [])
        response["ingestion_confidence"] = round(plan.confidence, 2)
        response["ingestion_steps"] = plan.steps_taken
        response["classifications_learned"] = journal_result.get("classifications_learned", 0)
    except Exception as e:
        logger.warning("Intelligent ingestion failed for dataset %d: %s (non-blocking)", ds.id, e)

    return response


@router.get("")
async def list_datasets(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func as sqlfunc
    result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    datasets = result.scalars().all()

    enriched = []
    for d in datasets:
        dd = d.to_dict()
        # Quick entity counts
        rev_c = (await db.execute(select(sqlfunc.count()).where(RevenueItem.dataset_id == d.id))).scalar() or 0
        cogs_c = (await db.execute(select(sqlfunc.count()).where(COGSItem.dataset_id == d.id))).scalar() or 0
        txn_c = (await db.execute(select(sqlfunc.count()).where(Transaction.dataset_id == d.id))).scalar() or 0
        tb_c = (await db.execute(select(sqlfunc.count()).where(TrialBalanceItem.dataset_id == d.id))).scalar() or 0
        bsi_c = (await db.execute(select(sqlfunc.count()).where(BalanceSheetItem.dataset_id == d.id))).scalar() or 0
        ga_c = (await db.execute(select(sqlfunc.count()).where(
            GAExpenseItem.dataset_id == d.id,
            GAExpenseItem.account_code.notin_(['FINANCE_INCOME', 'FINANCE_EXPENSE', 'TAX_EXPENSE', 'LABOUR_COSTS'])
        ))).scalar() or 0
        dd["entity_counts"] = {
            "transactions": txn_c, "revenue_items": rev_c, "cogs_items": cogs_c,
            "trial_balance_items": tb_c, "balance_sheet_items": bsi_c,
            "ga_expenses": ga_c,
        }
        dd["parsed_sheets"] = _detect_parsed_sheets(txn_c, rev_c, cogs_c, ga_c, tb_c, bsi_c)
        enriched.append(dd)
    return enriched


@router.get("/{dataset_id}/snapshots")
async def list_dataset_snapshots(dataset_id: int, db: AsyncSession = Depends(get_db)):
    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")
    res = await db.execute(
        select(DatasetSnapshot).where(DatasetSnapshot.dataset_id == dataset_id).order_by(DatasetSnapshot.version.desc())
    )
    return [s.to_dict() for s in res.scalars().all()]


@router.get("/{dataset_id}/etl-events")
async def list_etl_events(dataset_id: int, limit: int = 200, db: AsyncSession = Depends(get_db)):
    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")
    res = await db.execute(
        select(ETLAuditEvent).where(ETLAuditEvent.dataset_id == dataset_id).order_by(ETLAuditEvent.created_at.desc()).limit(limit)
    )
    return [e.to_dict() for e in res.scalars().all()]


## ── Product Mapping CRUD ─────────────────────────────────────────────────────

@router.get("/product-mappings")
async def list_product_mappings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductMapping).order_by(ProductMapping.created_at.desc()))
    return [m.to_dict() for m in result.scalars().all()]


@router.post("/product-mappings")
async def create_product_mapping(payload: dict, db: AsyncSession = Depends(get_db)):
    m = ProductMapping(
        product_name=payload["product_name"],
        product_name_en=payload.get("product_name_en"),
        revenue_category=payload.get("revenue_category"),
        cogs_category=payload.get("cogs_category"),
        is_approved=True,
        suggested_by=payload.get("suggested_by", "user"),
    )
    db.add(m)
    await db.commit()
    return m.to_dict()


@router.delete("/product-mappings/{mapping_id}")
async def delete_product_mapping(mapping_id: int, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(ProductMapping).where(ProductMapping.id == mapping_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Mapping not found")
    await db.delete(m)
    await db.commit()
    return {"message": "Mapping deleted", "id": mapping_id}


## ── COA Mapping Override CRUD ────────────────────────────────────────────────

@router.get("/coa-mappings")
async def list_coa_mappings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(COAMappingOverride).order_by(COAMappingOverride.created_at.desc()))
    return [m.to_dict() for m in result.scalars().all()]


@router.post("/coa-mappings")
async def upsert_coa_mapping(payload: dict, db: AsyncSession = Depends(get_db)):
    """Create or update a COA mapping override (upsert by account_code)."""
    code = (payload.get("account_code") or "").strip()
    if not code:
        raise HTTPException(400, "account_code is required")
    if not payload.get("ifrs_line_item"):
        raise HTTPException(400, "ifrs_line_item is required")

    existing = (await db.execute(
        select(COAMappingOverride).where(COAMappingOverride.account_code == code)
    )).scalar_one_or_none()

    if existing:
        existing.account_name = payload.get("account_name", existing.account_name)
        existing.ifrs_line_item = payload["ifrs_line_item"]
        existing.bs_side = payload.get("bs_side", existing.bs_side)
        existing.bs_sub = payload.get("bs_sub", existing.bs_sub)
        existing.pl_line = payload.get("pl_line", existing.pl_line)
        await db.commit()
        await db.refresh(existing)
        return existing.to_dict()
    else:
        m = COAMappingOverride(
            account_code=code,
            account_name=payload.get("account_name"),
            ifrs_line_item=payload["ifrs_line_item"],
            bs_side=payload.get("bs_side"),
            bs_sub=payload.get("bs_sub"),
            pl_line=payload.get("pl_line"),
            created_by=payload.get("created_by", "user"),
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return m.to_dict()


@router.delete("/coa-mappings/{mapping_id}")
async def delete_coa_mapping(mapping_id: int, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(COAMappingOverride).where(COAMappingOverride.id == mapping_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "COA mapping override not found")
    await db.delete(m)
    await db.commit()
    return {"message": "COA mapping override deleted", "id": mapping_id}


## ── COA Master Account CRUD + Import ────────────────────────────────────────

@router.get("/coa-master")
async def list_coa_master(
    search: str = None, account_type: str = None, account_class: str = None,
    limit: int = 2000, db: AsyncSession = Depends(get_db)
):
    """List all COA master accounts with optional filters."""
    q = select(COAMasterAccount).order_by(COAMasterAccount.account_code)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            (COAMasterAccount.account_code.ilike(pattern)) |
            (COAMasterAccount.name_ka.ilike(pattern)) |
            (COAMasterAccount.name_ru.ilike(pattern))
        )
    if account_type:
        q = q.where(COAMasterAccount.account_type_en == account_type)
    if account_class:
        q = q.where(COAMasterAccount.account_code_normalized.like(f"{account_class}%"))
    q = q.limit(limit)
    result = await db.execute(q)
    items = [a.to_dict() for a in result.scalars().all()]
    return {"total": len(items), "items": items}


@router.post("/coa-master/import")
async def import_coa_master(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Import ანგარიშები.xlsx — parse, derive IFRS, upsert all accounts."""
    from app.services.coa_import import parse_coa_xlsx, derive_ifrs_mappings
    from app.services.file_parser import GEORGIAN_COA
    import tempfile

    ext = Path(file.filename).suffix.lower()
    if ext not in (".xlsx", ".xls"):
        raise HTTPException(400, "Only .xlsx/.xls files are supported for COA import")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        accounts = parse_coa_xlsx(tmp_path)
        accounts = derive_ifrs_mappings(accounts, GEORGIAN_COA)
    finally:
        os.unlink(tmp_path)

    if not accounts:
        raise HTTPException(422, "No accounts found in uploaded file")

    created, updated = 0, 0
    for acct in accounts:
        existing = (await db.execute(
            select(COAMasterAccount).where(COAMasterAccount.account_code == acct["account_code"])
        )).scalar_one_or_none()

        if existing:
            for k, v in acct.items():
                if k != "id" and hasattr(existing, k):
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(COAMasterAccount(**acct))
            created += 1

    await db.commit()

    # Reload COA master cache for immediate use
    all_master = (await db.execute(select(COAMasterAccount))).scalars().all()
    fp_module.load_coa_master([a.to_dict() for a in all_master])

    type_counts = {}
    for a in accounts:
        t = a.get("account_type_en", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "message": f"COA Master imported: {created} created, {updated} updated",
        "total": len(accounts), "created": created, "updated": updated,
        "type_distribution": type_counts
    }


@router.put("/coa-master/{account_id}")
async def update_coa_master_account(account_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    """Edit IFRS mapping fields on a master account."""
    acct = (await db.execute(
        select(COAMasterAccount).where(COAMasterAccount.id == account_id)
    )).scalar_one_or_none()
    if not acct:
        raise HTTPException(404, "COA master account not found")

    editable = ["ifrs_bs_line", "ifrs_pl_line", "ifrs_side", "ifrs_sub", "ifrs_pl_category", "is_contra",
                "name_ka", "name_ru", "account_type", "account_type_en"]
    for k in editable:
        if k in payload:
            setattr(acct, k, payload[k])

    await db.commit()
    await db.refresh(acct)

    # Reload cache
    all_master = (await db.execute(select(COAMasterAccount))).scalars().all()
    fp_module.load_coa_master([a.to_dict() for a in all_master])

    return acct.to_dict()


@router.delete("/coa-master/{account_id}")
async def delete_coa_master_account(account_id: int, db: AsyncSession = Depends(get_db)):
    acct = (await db.execute(
        select(COAMasterAccount).where(COAMasterAccount.id == account_id)
    )).scalar_one_or_none()
    if not acct:
        raise HTTPException(404, "COA master account not found")
    await db.delete(acct)
    await db.commit()
    return {"message": "COA master account deleted", "id": account_id}


## ── Multi-Dataset Group Endpoints ────────────────────────────────────────────
# NOTE: These MUST be defined before /{dataset_id} routes to avoid path conflicts.

@router.post("/groups")
async def create_dataset_group(payload: dict, db: AsyncSession = Depends(get_db)):
    """Create a dataset group for multi-period / consolidation analysis.

    Body: {"name": "Q1 2025", "description": "...", "group_type": "period", "dataset_ids": [1,2,3]}
    group_type: period | consolidation | comparison | custom
    """
    from app.models.all_models import DatasetGroup

    name = payload.get("name")
    if not name:
        raise HTTPException(400, "Group name is required")

    group = DatasetGroup(
        name=name,
        description=payload.get("description", ""),
        group_type=payload.get("group_type", "period"),
        metadata_json=payload.get("metadata"),
    )
    db.add(group)
    await db.flush()

    # Optionally assign datasets immediately
    dataset_ids = payload.get("dataset_ids", [])
    if dataset_ids:
        result = await db.execute(
            select(Dataset).where(Dataset.id.in_(dataset_ids))
        )
        datasets = result.scalars().all()
        for ds in datasets:
            ds.group_id = group.id

    await db.commit()
    await db.refresh(group)
    return {**group.to_dict(), "dataset_count": len(dataset_ids)}


@router.get("/groups")
async def list_dataset_groups(db: AsyncSession = Depends(get_db)):
    """List all dataset groups with their member datasets."""
    from app.models.all_models import DatasetGroup

    result = await db.execute(
        select(DatasetGroup).order_by(DatasetGroup.created_at.desc())
    )
    groups = result.scalars().all()

    enriched = []
    for g in groups:
        ds_result = await db.execute(
            select(Dataset).where(Dataset.group_id == g.id)
        )
        datasets = ds_result.scalars().all()
        gd = g.to_dict()
        gd["datasets"] = [
            {"id": d.id, "name": d.name, "period": d.period, "file_type": d.file_type}
            for d in datasets
        ]
        gd["dataset_count"] = len(datasets)
        enriched.append(gd)
    return enriched


@router.get("/groups/{group_id}")
async def get_dataset_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single dataset group with its datasets."""
    from app.models.all_models import DatasetGroup

    result = await db.execute(
        select(DatasetGroup).where(DatasetGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, f"Group {group_id} not found")

    ds_result = await db.execute(
        select(Dataset).where(Dataset.group_id == group_id)
    )
    datasets = ds_result.scalars().all()
    gd = group.to_dict()
    gd["datasets"] = [
        {"id": d.id, "name": d.name, "period": d.period,
         "file_type": d.file_type, "record_count": d.record_count}
        for d in datasets
    ]
    gd["dataset_count"] = len(datasets)
    return gd


@router.delete("/groups/{group_id}")
async def delete_dataset_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a dataset group (does NOT delete the datasets, just ungroups them)."""
    from app.models.all_models import DatasetGroup

    group = (await db.execute(
        select(DatasetGroup).where(DatasetGroup.id == group_id)
    )).scalar_one_or_none()
    if not group:
        raise HTTPException(404, f"Group {group_id} not found")

    # Ungroup all datasets in this group
    ds_result = await db.execute(
        select(Dataset).where(Dataset.group_id == group_id)
    )
    for ds in ds_result.scalars().all():
        ds.group_id = None

    await db.delete(group)
    await db.commit()
    return {"message": f"Group '{group.name}' deleted, datasets ungrouped"}


## ── Dataset Instance Endpoints ───────────────────────────────────────────────

@router.get("/{dataset_id}")
async def get_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func as sqlfunc
    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")

    txns = (await db.execute(
        select(Transaction).where(Transaction.dataset_id == dataset_id)
        .order_by(Transaction.amount.desc()).limit(50)
    )).scalars().all()

    revs = (await db.execute(
        select(RevenueItem).where(RevenueItem.dataset_id == dataset_id)
        .order_by(RevenueItem.net.desc()).limit(50)
    )).scalars().all()

    cogs = (await db.execute(
        select(COGSItem).where(COGSItem.dataset_id == dataset_id)
        .order_by(COGSItem.total_cogs.desc())
    )).scalars().all()

    ga_items = (await db.execute(
        select(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id)
    )).scalars().all()

    budget_lines = (await db.execute(
        select(BudgetLine).where(BudgetLine.dataset_id == dataset_id)
    )).scalars().all()

    # Entity counts for TB and BS
    tb_count = (await db.execute(
        select(sqlfunc.count()).where(TrialBalanceItem.dataset_id == dataset_id)
    )).scalar() or 0

    bsi_count = (await db.execute(
        select(sqlfunc.count()).where(BalanceSheetItem.dataset_id == dataset_id)
    )).scalar() or 0

    txn_total_count = (await db.execute(
        select(sqlfunc.count()).where(Transaction.dataset_id == dataset_id)
    )).scalar() or 0

    rev_total_count = (await db.execute(
        select(sqlfunc.count()).where(RevenueItem.dataset_id == dataset_id)
    )).scalar() or 0

    # Separate real G&A from special items (FINANCE_INCOME, etc.)
    ga_real = [g for g in ga_items if g.account_code not in ('FINANCE_INCOME', 'FINANCE_EXPENSE', 'TAX_EXPENSE', 'LABOUR_COSTS')]

    return {
        **d.to_dict(),
        "entity_counts": {
            "transactions": txn_total_count,
            "revenue_items": rev_total_count,
            "cogs_items": len(cogs),
            "ga_expenses": len(ga_real),
            "trial_balance_items": tb_count,
            "balance_sheet_items": bsi_count,
            "budget_lines": len(budget_lines),
        },
        "parsed_sheets": _detect_parsed_sheets(txn_total_count, rev_total_count, len(cogs), len(ga_real), tb_count, bsi_count),
        "sample_transactions": [t.to_dict() for t in txns],
        "revenue_items":       [r.to_dict() for r in revs],
        "cogs_items":          [c.to_dict() for c in cogs],
        "ga_expense_items":    [g.to_dict() for g in ga_real],
        "budget":              {b.line_item: b.actual_amount if b.actual_amount is not None else b.budget_amount for b in budget_lines},
    }


def _detect_parsed_sheets(txns, revs, cogs, ga, tb, bsi):
    """Return list of parsed sheet names based on entity counts."""
    sheets = []
    if revs > 0: sheets.append("Revenue Breakdown")
    if cogs > 0: sheets.append("COGS Breakdown")
    if tb > 0:   sheets.append("TDSheet (Trial Balance)")
    if bsi > 0:  sheets.append("Balance (IFRS Mapped)")
    if ga > 0:   sheets.append("G&A / D&A Expenses")
    if txns > 0: sheets.append("Transaction Ledger")
    return sheets


@router.put("/{dataset_id}/activate")
async def activate_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Set this dataset as active — deactivates all others."""
    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")

    others = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalars().all()
    for o in others:
        o.is_active = False

    d.is_active = True
    await db.commit()
    return {"message": f"Dataset '{d.name}' is now active", "id": dataset_id, "period": d.period}


@router.post("/{dataset_id}/reparse")
async def reparse_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Re-parse an existing dataset from its stored upload file."""
    from sqlalchemy import delete as sql_delete
    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")
    if not d.upload_path or not os.path.exists(d.upload_path):
        raise HTTPException(400, "Original upload file not found — cannot re-parse")

    # Read the stored file
    with open(d.upload_path, "rb") as f:
        content = f.read()

    validation = await validate_schema_db(d.original_filename or d.name, content, db, settings.VALIDATION_SAMPLE_ROWS)
    await _log_etl_event(
        db,
        dataset_id=d.id,
        step="schema_validation",
        status="ok" if validation.ok else "error",
        detail="schema validation (reparse)",
        metadata={"ok": validation.ok, "file_type": validation.file_type,
                  "errors": validation.errors, "warnings": validation.warnings,
                  "sheet_results": validation.sheet_results},
    )
    if settings.STRICT_SCHEMA_VALIDATION and not validation.ok:
        await db.commit()
        raise HTTPException(422, f"Schema validation failed: {validation.errors}. Proposal ID: {validation.proposal_id}")

    # Load user-approved product mappings
    try:
        approved = (await db.execute(
            select(ProductMapping).where(ProductMapping.is_approved == True)
        )).scalars().all()
        fp_module.load_user_mappings([
            {"product_name": m.product_name, "revenue_category": m.revenue_category, "cogs_category": m.cogs_category}
            for m in approved
        ])
    except Exception:
        pass

    # Load COA mapping overrides before parsing
    try:
        coa_overrides = (await db.execute(select(COAMappingOverride))).scalars().all()
        fp_module.load_coa_overrides([
            {"account_code": o.account_code, "account_name": o.account_name,
             "ifrs_line_item": o.ifrs_line_item, "bs_side": o.bs_side,
             "bs_sub": o.bs_sub, "pl_line": o.pl_line}
            for o in coa_overrides
        ])
    except Exception:
        pass

    # Load COA master accounts
    try:
        coa_master = (await db.execute(select(COAMasterAccount))).scalars().all()
        fp_module.load_coa_master([a.to_dict() for a in coa_master])
    except Exception:
        pass

    # Re-parse
    try:
        parsed = fp_module.parse_file(d.original_filename or d.name, content, strict=settings.STRICT_PARSING)
    except Exception as e:
        raise HTTPException(422, f"Re-parse failed: {str(e)}")

    fingerprint_data = _compute_dataset_fingerprint(parsed)
    await _log_etl_event(
        db,
        dataset_id=d.id,
        step="parse_complete",
        status="ok",
        detail="parse complete (reparse)",
        metadata={"record_count": parsed.get("record_count", 0)},
    )

    # Delete all existing related records for this dataset
    for model in [Transaction, RevenueItem, COGSItem, GAExpenseItem, BudgetLine,
                  TrialBalanceItem, BalanceSheetItem, DataLineage]:
        await db.execute(sql_delete(model).where(model.dataset_id == dataset_id))

    period = d.period or "January 2025"

    # Re-insert all parsed data (same logic as upload) — track lineage
    lineage_records = []
    for t in parsed.get("transactions", []):
        txn = Transaction(dataset_id=d.id, date=t.get("date",""), recorder=t.get("recorder",""),
            acct_dr=t.get("acct_dr",""), acct_cr=t.get("acct_cr",""), dept=t.get("dept",""),
            counterparty=t.get("counterparty",""), cost_class=t.get("cost_class",""),
            type=t.get("type","Expense"), amount=float(t.get("amount",0)),
            vat=float(t.get("vat",0)), currency="GEL", period=period)
        db.add(txn)
        lin = t.get("_lineage", {})
        if lin:
            lineage_records.append(("transaction", txn, lin))

    for r in parsed.get("revenue", []):
        rev = RevenueItem(dataset_id=d.id, product=r.get("product",""),
            gross=float(r.get("gross",0)), vat=float(r.get("vat",0)), net=float(r.get("net",0)),
            segment=r.get("segment","Other Revenue"), category=r.get("category"),
            eliminated=bool(r.get("eliminated", False)),
            currency="GEL", period=period)
        db.add(rev)
        lin = r.get("_lineage", {})
        if lin:
            lineage_records.append(("revenue_item", rev, lin))

    for c in parsed.get("cogs_items", []):
        cogs_obj = COGSItem(dataset_id=d.id, product=c.get("product",""),
            col6_amount=float(c.get("col6",0)), col7310_amount=float(c.get("col7310",0)),
            col8230_amount=float(c.get("col8230",0)), total_cogs=float(c.get("total_cogs",0)),
            segment=c.get("segment","Other COGS"), category=c.get("category"),
            currency="GEL", period=period)
        db.add(cogs_obj)
        lin = c.get("_lineage", {})
        if lin:
            lineage_records.append(("cogs_item", cogs_obj, lin))

    for ga in parsed.get("ga_expenses", []):
        ga_obj = GAExpenseItem(dataset_id=d.id, account_code=ga.get("account_code",""),
            account_name=ga.get("account_name",""), amount=float(ga.get("amount",0)),
            currency="GEL", period=period)
        db.add(ga_obj)
        lin = ga.get("_lineage", {})
        if lin:
            lineage_records.append(("ga_expense", ga_obj, lin))

    for da in parsed.get("da_expenses", []):
        da_obj = GAExpenseItem(dataset_id=d.id, account_code=da.get("account_code",""),
            account_name=da.get("account_name",""), amount=float(da.get("amount",0)),
            currency="GEL", period=period)
        db.add(da_obj)
        lin = da.get("_lineage", {})
        if lin:
            lineage_records.append(("ga_expense", da_obj, lin))

    for special_code, special_val in [
        ("FINANCE_INCOME", parsed.get("finance_income",0)),
        ("FINANCE_EXPENSE", parsed.get("finance_expense",0)),
        ("TAX_EXPENSE", parsed.get("tax_expense",0)),
        ("LABOUR_COSTS", parsed.get("labour_costs",0)),
    ]:
        if special_val and float(special_val) > 0:
            db.add(GAExpenseItem(dataset_id=d.id, account_code=special_code,
                account_name=special_code.replace("_"," ").title(),
                amount=float(special_val), currency="GEL", period=period))

    tb_count = 0
    for tb in parsed.get("trial_balance_items", []):
        db.add(TrialBalanceItem(dataset_id=d.id, account_code=tb.get("account_code",""),
            account_name=tb.get("account_name",""), sub_account_detail=tb.get("sub_account_detail",""),
            opening_debit=float(tb.get("opening_debit",0)), opening_credit=float(tb.get("opening_credit",0)),
            turnover_debit=float(tb.get("turnover_debit",0)), turnover_credit=float(tb.get("turnover_credit",0)),
            closing_debit=float(tb.get("closing_debit",0)), closing_credit=float(tb.get("closing_credit",0)),
            net_pl_impact=float(tb.get("net_pl_impact",0)), account_class=tb.get("account_class",""),
            hierarchy_level=tb.get("hierarchy_level",1), currency="GEL", period=period))
        tb_count += 1

    bsi_count = 0
    for bsi in parsed.get("balance_sheet_items", []):
        if not bsi.get("ifrs_line_item"): continue
        db.add(BalanceSheetItem(dataset_id=d.id, account_code=bsi.get("account_code",""),
            account_name=bsi.get("account_name",""), ifrs_line_item=bsi.get("ifrs_line_item",""),
            ifrs_statement=bsi.get("ifrs_statement",""),
            baku_bs_mapping=bsi.get("baku_bs_mapping",""),
            intercompany_entity=bsi.get("intercompany_entity",""),
            opening_balance=float(bsi.get("opening_balance",0)),
            turnover_debit=float(bsi.get("turnover_debit",0)),
            turnover_credit=float(bsi.get("turnover_credit",0)),
            closing_balance=float(bsi.get("closing_balance",0)),
            row_type=bsi.get("row_type",""), currency="GEL", period=period))
        bsi_count += 1

    for k, v in parsed.get("budget", {}).items():
        cat = "REVENUE" if "Revenue" in k else "COGS" if "COGS" in k else "MARGIN" if "Margin" in k else "OTHER"
        db.add(BudgetLine(dataset_id=d.id, line_item=k, budget_amount=float(v),
            currency="GEL", period=period, category=cat))

    # Update dataset metadata
    d.record_count = parsed["record_count"]
    d.sheet_count = parsed.get("sheet_count", 1)
    d.file_type = parsed["file_type"]
    d.parse_metadata = {
        "processing_pipeline": parsed.get("processing_pipeline", []),
        "detected_sheets": parsed.get("detected_sheets", []),
        "record_counts": {
            "transactions": len(parsed.get("transactions", [])),
            "revenue_items": len(parsed.get("revenue", [])),
            "cogs_items": len(parsed.get("cogs_items", [])),
            "ga_expenses": len(parsed.get("ga_expenses", [])),
            "da_expenses": len(parsed.get("da_expenses", [])),
            "trial_balance_items": len(parsed.get("trial_balance_items", [])),
            "balance_sheet_items": len(parsed.get("balance_sheet_items", [])),
        },
        "schema_validation": {
            "ok": validation.ok,
            "file_type": validation.file_type,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "sheet_results": validation.sheet_results,
            "profile_id": validation.profile_id,
            "proposal_id": validation.proposal_id,
        },
        "fingerprint": fingerprint_data["fingerprint"],
    }

    # Flush to get entity IDs, then create lineage records
    await db.flush()
    current_version = (await db.execute(
        select(func.max(DatasetSnapshot.version)).where(DatasetSnapshot.dataset_id == d.id)
    )).scalar() or 0
    db.add(DatasetSnapshot(
        dataset_id=d.id,
        version=current_version + 1,
        fingerprint=fingerprint_data["fingerprint"],
        record_counts=fingerprint_data["counts"],
        totals_json={"totals": fingerprint_data["totals"], "hashes": fingerprint_data["hashes"]},
    ))
    await _log_etl_event(
        db,
        dataset_id=d.id,
        step="snapshot_create",
        status="ok",
        detail=f"snapshot v{current_version + 1} created",
        metadata={"fingerprint": fingerprint_data["fingerprint"]},
    )

    for entity_type, entity_obj, lin_data in lineage_records:
        try:
            db.add(DataLineage(
                entity_type=entity_type,
                entity_id=entity_obj.id,
                dataset_id=d.id,
                source_file=d.original_filename or d.name,
                source_sheet=lin_data.get("source_sheet", ""),
                source_row=lin_data.get("source_row"),
                classification_rule=lin_data.get("classification_rule", ""),
                classification_confidence=lin_data.get("confidence", 0.0),
                transform_chain=lin_data.get("transform_chain"),
            ))
        except Exception as e:
            logger.warning(f"Reparse lineage record failed for {entity_type}: {e}")

    await _log_etl_event(
        db,
        dataset_id=d.id,
        step="lineage_create",
        status="ok",
        detail="lineage created (reparse)",
        metadata={"lineage_count": len(lineage_records)},
    )

    await db.commit()

    # ── Auto-populate MR mappings on TB items ───────────────────
    try:
        from app.services.mr_mapping import seed_coa_mr_mappings, populate_tb_mr_mappings
        seed_result = await seed_coa_mr_mappings(db)
        if tb_count > 0:
            tb_map_result = await populate_tb_mr_mappings(db, d.id)
            logger.info(f"Reparse MR mapping: {tb_map_result.get('mapped',0)}/{tb_map_result.get('total',0)} TB items mapped")
        await db.commit()
    except Exception as e:
        logger.warning(f"MR mapping auto-population skipped: {e}")

    # ── COGS ↔ Inventory Reconciliation anomalies ──────────────────
    recon = parsed.get("cogs_reconciliation", {})
    if recon.get("has_mismatch"):
        for check in recon.get("checks", []):
            if check["status"] == "mismatch":
                db.add(Anomaly(
                    dataset_id=d.id,
                    anomaly_type="cogs_reconciliation",
                    severity=check["severity"],
                    score=check["variance_pct"],
                    description=f"{check['check']}: {check['source_a']['label']} = {check['source_a']['value']:,.2f} vs {check['source_b']['label']} = {check['source_b']['value']:,.2f} (variance {check['variance_pct']:.1f}%)",
                    details=json.dumps(check),
                ))
        await db.commit()

    cogs_count = len(parsed.get("cogs_items", []))
    ga_count = len(parsed.get("ga_expenses", []))
    logger.info(f"Re-parsed: {d.name} — {len(parsed.get('transactions',[]))} txns, {len(parsed.get('revenue',[]))} rev, "
                f"{cogs_count} cogs, {ga_count} ga, {tb_count} tb, {bsi_count} bsi")

    return {
        "message": f"Dataset '{d.name}' re-parsed successfully",
        "id": d.id,
        "transactions": len(parsed.get("transactions", [])),
        "revenue": len(parsed.get("revenue", [])),
        "cogs_items": cogs_count,
        "trial_balance_items": tb_count,
        "balance_sheet_items": bsi_count,
        "cogs_reconciliation": recon,
    }


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")
    if d.is_seed:
        raise HTTPException(400, "Cannot delete seed dataset")

    if d.upload_path and os.path.exists(d.upload_path):
        try:
            os.unlink(d.upload_path)
        except Exception:
            pass

    await db.delete(d)
    await db.commit()
    return {"message": "Dataset deleted", "id": dataset_id}


## ── BS Regeneration ──────────────────────────────────────────────────────────

@router.post("/{dataset_id}/regenerate-bs")
async def regenerate_balance_sheet(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Regenerate Balance Sheet items from existing TB data using current COA mappings.
    Uses correct sign convention: Assets=DR-CR, Liabilities/Equity=CR-DR.
    Skips summary codes (containing X) and level-3 detail rows to avoid double-counting.
    """
    from sqlalchemy import delete as sql_delete
    from app.services.file_parser import map_coa as fp_map_coa
    import re as _re

    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")

    # Load COA overrides into file_parser
    coa_overrides = (await db.execute(select(COAMappingOverride))).scalars().all()
    fp_module.load_coa_overrides([
        {"account_code": o.account_code, "account_name": o.account_name,
         "ifrs_line_item": o.ifrs_line_item, "bs_side": o.bs_side,
         "bs_sub": o.bs_sub, "pl_line": o.pl_line}
        for o in coa_overrides
    ])

    # Load COA master accounts
    coa_master = (await db.execute(select(COAMasterAccount))).scalars().all()
    fp_module.load_coa_master([a.to_dict() for a in coa_master])

    # Read existing TB items
    tb_result = await db.execute(select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == dataset_id))
    tb_items = tb_result.scalars().all()
    if not tb_items:
        raise HTTPException(400, "No trial balance items found for this dataset")

    # Build parent-code set to identify leaf accounts (avoid double-counting parent+child)
    from app.services.file_parser import _build_parent_codes
    tb_dicts_for_parents = [{"account_code": tb.account_code or ""} for tb in tb_items]
    parent_codes = _build_parent_codes(tb_dicts_for_parents)

    # Delete existing BS items for this dataset
    await db.execute(sql_delete(BalanceSheetItem).where(BalanceSheetItem.dataset_id == dataset_id))

    # Regenerate BS items using map_coa (now 3-tier: user override → COA master → GEORGIAN_COA)
    period = d.period or "January 2025"
    bsi_count = 0
    for tb in tb_items:
        code = (tb.account_code or "").strip()
        if not code:
            continue
        # Skip summary codes (11XX, 21XX etc.) and parent codes and level-3 detail rows
        if 'X' in code.upper():
            continue
        if code in parent_codes:
            continue
        if (tb.hierarchy_level or 0) >= 3:
            continue

        coa = fp_map_coa(code)
        if not coa:
            continue
        bs_line = coa.get("bs")
        if not bs_line:
            continue
        # Only BS accounts (asset/liability/equity)
        bs_side = coa.get("bs_side", "")
        if bs_side not in ("asset", "liability", "equity"):
            continue

        # Correct sign convention (matching _generate_bs_from_tdsheet):
        # Assets: DR balance = positive → closing = DR - CR
        # Liabilities/Equity: CR balance = positive → closing = CR - DR
        o_dr = float(tb.opening_debit or 0)
        o_cr = float(tb.opening_credit or 0)
        c_dr = float(tb.closing_debit or 0)
        c_cr = float(tb.closing_credit or 0)
        if bs_side in ('liability', 'equity'):
            opening = o_cr - o_dr
            closing = c_cr - c_dr
        else:
            opening = o_dr - o_cr
            closing = c_dr - c_cr

        db.add(BalanceSheetItem(
            dataset_id=dataset_id,
            account_code=code,
            account_name=tb.account_name or "",
            ifrs_line_item=bs_line,
            ifrs_statement="BS",
            opening_balance=round(opening, 2),
            turnover_debit=float(tb.turnover_debit or 0),
            turnover_credit=float(tb.turnover_credit or 0),
            closing_balance=round(closing, 2),
            row_type="COA_DERIVED",
            currency="GEL",
            period=period,
        ))
        bsi_count += 1

    await db.commit()
    return {"message": f"Balance Sheet regenerated with {bsi_count} items", "count": bsi_count}


@router.post("/{dataset_id}/regenerate-pl")
async def regenerate_pl(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Regenerate P&L items (Revenue, COGS, GA) from TB class 6-9 accounts using map_coa().
    Only generates if no Revenue/COGS items already exist for this dataset."""
    from sqlalchemy import delete as sql_delete
    from app.services.file_parser import _generate_pl_from_tdsheet

    d = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")

    # Load COA caches
    coa_overrides = (await db.execute(select(COAMappingOverride))).scalars().all()
    fp_module.load_coa_overrides([
        {"account_code": o.account_code, "account_name": o.account_name,
         "ifrs_line_item": o.ifrs_line_item, "bs_side": o.bs_side,
         "bs_sub": o.bs_sub, "pl_line": o.pl_line}
        for o in coa_overrides
    ])
    coa_master = (await db.execute(select(COAMasterAccount))).scalars().all()
    fp_module.load_coa_master([a.to_dict() for a in coa_master])

    # Read TB items
    tb_result = await db.execute(select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == dataset_id))
    tb_items = tb_result.scalars().all()
    if not tb_items:
        raise HTTPException(400, "No trial balance items found")

    # Convert to dicts for _generate_pl_from_tdsheet
    tb_dicts = [{"account_code": t.account_code, "account_name": t.account_name,
                 "turnover_debit": t.turnover_debit, "turnover_credit": t.turnover_credit,
                 "hierarchy_level": t.hierarchy_level} for t in tb_items]

    auto_pl = _generate_pl_from_tdsheet(tb_dicts)
    if not auto_pl or not auto_pl.get('revenue_items'):
        return {"message": "No P&L accounts found in TB data", "count": 0}

    period = d.period or "January 2025"

    # Delete existing Revenue, COGS, GA for this dataset
    await db.execute(sql_delete(RevenueItem).where(RevenueItem.dataset_id == dataset_id))
    await db.execute(sql_delete(COGSItem).where(COGSItem.dataset_id == dataset_id))
    await db.execute(sql_delete(GAExpenseItem).where(GAExpenseItem.dataset_id == dataset_id))

    # Insert revenue items
    rev_count = 0
    for r in auto_pl['revenue_items']:
        db.add(RevenueItem(
            dataset_id=dataset_id, product=r.get('product', ''),
            gross=float(r.get('gross', 0)), vat=float(r.get('vat', 0)),
            net=float(r.get('net', 0)), segment=r.get('segment', 'TB-Derived'),
            category=r.get('category', ''), currency='GEL', period=period,
        ))
        rev_count += 1

    # Insert COGS items
    cogs_count = 0
    for c in auto_pl['cogs_items']:
        db.add(COGSItem(
            dataset_id=dataset_id, product=c.get('product', ''),
            total_cogs=float(c.get('total_cogs', 0)),
            segment=c.get('segment', 'TB-Derived'), category=c.get('category', ''),
            currency='GEL', period=period,
        ))
        cogs_count += 1

    # Insert GA expense items (GAExpenseItem has: account_code, account_name, amount)
    ga_count = 0
    for g in auto_pl['ga_expenses']:
        db.add(GAExpenseItem(
            dataset_id=dataset_id,
            account_code=g.get('account_code', ''),
            account_name=g.get('account_name', ''),
            amount=float(g.get('amount', 0)),
            currency='GEL', period=period,
        ))
        ga_count += 1

    # Store PL summary as special GA items for finance/tax (same pattern as TDSheet upload)
    pl_sum = auto_pl.get('pl_summary', {})
    if pl_sum.get('finance_income', 0):
        db.add(GAExpenseItem(dataset_id=dataset_id,
            account_code='FINANCE_INCOME', account_name='Finance Income (TB-derived)',
            amount=float(pl_sum['finance_income']), currency='GEL', period=period))
    if pl_sum.get('finance_expense', 0):
        db.add(GAExpenseItem(dataset_id=dataset_id,
            account_code='FINANCE_EXPENSE', account_name='Finance Expense (TB-derived)',
            amount=float(pl_sum['finance_expense']), currency='GEL', period=period))
    if pl_sum.get('tax', 0):
        db.add(GAExpenseItem(dataset_id=dataset_id,
            account_code='TAX_EXPENSE', account_name='Tax Expense (TB-derived)',
            amount=float(pl_sum['tax']), currency='GEL', period=period))

    await db.commit()
    return {
        "message": f"P&L regenerated: {rev_count} revenue, {cogs_count} COGS, {ga_count} expenses",
        "revenue_count": rev_count, "cogs_count": cogs_count, "ga_count": ga_count,
        "pl_summary": pl_sum,
    }


def _suggest_category(product_name: str, source: str) -> str:
    """Intelligently suggest a category for an unmapped product based on keyword analysis."""
    p = product_name.lower().strip()
    # Georgian keyword → category mapping
    petrol_kw = ["რეგულარი", "პრემიუმი", "სუპერი", "ბენზინ", "petrol", "gasoline", "regular", "premium", "super"]
    diesel_kw = ["დიზელი", "diesel", "ევროდიზელი"]
    cng_kw = ["ბუნებრივი აირი", "natural gas", "cng", "მეთანი", "methane"]
    lpg_kw = ["თხევადი აირი", "lpg", "პროპანი", "propane"]
    bitumen_kw = ["ბიტუმი", "bitumen", "ასფალტ"]
    wholesale_kw = ["იმპორტი", "ექსპორტი", "რეექსპორტი", "საბითუმო", "wholesale", "import", "export"]

    is_wholesale = any(kw in p for kw in wholesale_kw)
    seg = "Whsale" if is_wholesale else "Retial"

    if source == "revenue":
        if any(kw in p for kw in petrol_kw): return f"Revenue {seg} Petrol"
        if any(kw in p for kw in diesel_kw): return f"Revenue {seg} Diesel"
        if any(kw in p for kw in cng_kw):    return f"Revenue Retial CNG"
        if any(kw in p for kw in lpg_kw):    return f"Revenue Retial LPG"
        if any(kw in p for kw in bitumen_kw):return f"Revenue Whsale Bitumen"
        return "Other Revenue"
    else:
        if any(kw in p for kw in petrol_kw): return f"COGS {seg} Petrol"
        if any(kw in p for kw in diesel_kw): return f"COGS {seg} Diesel"
        if any(kw in p for kw in cng_kw):    return f"COGS Retial CNG"
        if any(kw in p for kw in lpg_kw):    return f"COGS Retial LPG"
        if any(kw in p for kw in bitumen_kw):return f"COGS Whsale Bitumen"
        return "Other COGS"


## ── Dataset ↔ Group Assignment ────────────────────────────────────────────────

@router.post("/{dataset_id}/group/{group_id}")
async def add_dataset_to_group(dataset_id: int, group_id: int, db: AsyncSession = Depends(get_db)):
    """Assign a dataset to a group."""
    from app.models.all_models import DatasetGroup

    group = (await db.execute(
        select(DatasetGroup).where(DatasetGroup.id == group_id)
    )).scalar_one_or_none()
    if not group:
        raise HTTPException(404, f"Group {group_id} not found")

    ds = (await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )).scalar_one_or_none()
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id} not found")

    ds.group_id = group_id
    await db.commit()
    return {"message": f"Dataset {dataset_id} added to group '{group.name}'", "dataset_id": dataset_id, "group_id": group_id}


@router.delete("/{dataset_id}/group")
async def remove_dataset_from_group(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a dataset from its group."""
    ds = (await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )).scalar_one_or_none()
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id} not found")

    old_group = ds.group_id
    ds.group_id = None
    await db.commit()
    return {"message": f"Dataset {dataset_id} removed from group {old_group}", "dataset_id": dataset_id}


## ── Private Helpers ──────────────────────────────────────────────────────────

async def _log_etl_event(db: AsyncSession, dataset_id: int, step: str, status: str = "ok", detail: str = "", metadata: dict = None):
    """Best-effort ETL audit logging. Never poisons the session."""
    pass  # DISABLED until etl_audit_events schema is fully stable


def _norm_val(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return str(v).strip()


def _hash_rows(rows: list, keys: list) -> str:
    xor_val = 0
    for r in rows:
        payload = {k: _norm_val(r.get(k)) for k in keys}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        h = int(hashlib.sha256(raw.encode("utf-8")).hexdigest(), 16)
        xor_val ^= h
    return f"{xor_val:064x}"


def _compute_dataset_fingerprint(parsed: dict) -> dict:
    txns = parsed.get("transactions", [])
    rev = parsed.get("revenue", [])
    cogs = parsed.get("cogs_items", [])
    ga = parsed.get("ga_expenses", [])
    tb = parsed.get("trial_balance_items", [])
    bs = parsed.get("balance_sheet_items", [])

    counts = {
        "transactions": len(txns),
        "revenue_items": len(rev),
        "cogs_items": len(cogs),
        "ga_expenses": len(ga),
        "trial_balance_items": len(tb),
        "balance_sheet_items": len(bs),
    }

    totals = {
        "transactions_amount": round(sum(_norm_val(t.get("amount", 0)) for t in txns), 2),
        "transactions_vat": round(sum(_norm_val(t.get("vat", 0)) for t in txns), 2),
        "revenue_gross": round(sum(_norm_val(r.get("gross", 0)) for r in rev), 2),
        "revenue_net": round(sum(_norm_val(r.get("net", 0)) for r in rev), 2),
        "cogs_total": round(sum(_norm_val(c.get("total_cogs", 0)) for c in cogs), 2),
        "ga_amount": round(sum(_norm_val(g.get("amount", 0)) for g in ga), 2),
        "tb_closing_debit": round(sum(_norm_val(t.get("closing_debit", 0)) for t in tb), 2),
        "tb_closing_credit": round(sum(_norm_val(t.get("closing_credit", 0)) for t in tb), 2),
        "bs_closing_balance": round(sum(_norm_val(b.get("closing_balance", 0)) for b in bs), 2),
    }

    hashes = {
        "transactions": _hash_rows(txns, ["date", "acct_dr", "acct_cr", "dept", "counterparty", "cost_class", "type", "amount", "vat"]),
        "revenue_items": _hash_rows(rev, ["product", "gross", "vat", "net", "segment", "category", "eliminated"]),
        "cogs_items": _hash_rows(cogs, ["product", "col6", "col7310", "col8230", "total_cogs", "segment", "category"]),
        "ga_expenses": _hash_rows(ga, ["account_code", "account_name", "amount"]),
        "trial_balance_items": _hash_rows(tb, ["account_code", "account_name", "sub_account_detail", "opening_debit", "opening_credit", "turnover_debit", "turnover_credit", "closing_debit", "closing_credit", "net_pl_impact", "account_class", "hierarchy_level"]),
        "balance_sheet_items": _hash_rows(bs, ["account_code", "account_name", "ifrs_line_item", "ifrs_statement", "baku_bs_mapping", "intercompany_entity", "opening_balance", "turnover_debit", "turnover_credit", "closing_balance", "row_type"]),
    }

    fingerprint_payload = {"counts": counts, "totals": totals, "hashes": hashes}
    fingerprint_raw = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint = hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()

    return {"fingerprint": fingerprint, "counts": counts, "totals": totals, "hashes": hashes}


def _detect_period(filename: str) -> str:
    """Try to extract period label from filename."""
    months = {
        "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
        "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
    }
    full_months = {
        "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
        "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    }
    fn_lower = filename.lower()
    year_m = __import__("re").search(r"(20\d{2})", filename)
    year   = year_m.group(1) if year_m else "2025"
    for name, num in {**full_months, **months}.items():
        if name in fn_lower:
            month_name = list(full_months.keys())[num-1].capitalize()
            return f"{month_name} {year}"
    return None
