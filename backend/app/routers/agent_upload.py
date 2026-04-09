"""
FinAI Agent Upload Sub-Router
==============================
Extracted from agent.py — handles file upload, parsing, and ingestion.
Covers: Excel parsing, smart upload, smart analyze, PDF parsing, account tree.
"""
from fastapi import APIRouter, File, UploadFile
from typing import Optional, List, Dict, Any
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix — parent adds /api/agent


def _guarded_save_financials(company_id, period, financials, source_file=None, user="api"):
    """Route all financial writes through OntologyWriteGuard."""
    try:
        from app.services.ontology_write_guard import write_guard
        write_guard.write_financials(company_id, period, financials, user=user)
    except Exception:
        from app.services.data_store import data_store
        data_store.save_financials(company_id, period, financials, source_file)


# ── Phase N: Smart Excel/CSV Parser ────────────────────────────────────────

@router.post("/agents/parse-excel")
async def parse_excel(body: dict):
    """Phase N: Parse Excel/CSV with smart column detection + persist to DataStore."""
    try:
        from app.services.smart_excel_parser import smart_parser
        from app.services.data_validator import data_validator
        from app.services.data_store import data_store
        import base64, os
        from datetime import datetime, timezone

        data_b64 = body.get("data")
        filename = body.get("filename", "upload.xlsx")
        company_name = body.get("company", "Default Company")

        # ─── File size guard ─────────────────────────────────────────
        from app.config import settings as _settings
        if data_b64:
            raw_bytes = base64.b64decode(data_b64)
            _size = len(raw_bytes)
        else:
            _path = body.get("path")
            _size = os.path.getsize(_path) if _path and os.path.exists(_path) else 0
            raw_bytes = None
        if _size > _settings.max_upload_bytes:
            return {
                "error": (
                    f"File too large: {_size / 1024 / 1024:.1f}MB. "
                    f"Maximum allowed: {_settings.MAX_UPLOAD_SIZE_MB}MB."
                )
            }

        # 1. Parse file
        if raw_bytes is not None:
            result = smart_parser.parse_bytes(raw_bytes, filename)
        else:
            path = body.get("path")
            if not path:
                return {"error": "Provide 'data' (base64) or 'path'"}
            result = smart_parser.parse_file(path)
            with open(path, "rb") as f:
                raw_bytes = f.read()

        # 2. Save original file to uploads/
        os.makedirs("uploads", exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = f"{ts}_{filename.replace('/', '_').replace(chr(92), '_')}"
        saved_path = os.path.join("uploads", safe_name)
        with open(saved_path, "wb") as f:
            f.write(raw_bytes)

        # 3. Validate
        validation = data_validator.validate(result.normalized_financials)
        financials = validation.corrected_data

        # 4. Persist to DataStore
        company_id = body.get("company_id")
        if not company_id:
            companies = data_store.list_companies()
            match = next((c for c in companies if c["name"] == company_name), None)
            if match:
                company_id = match["id"]
            else:
                company_id = data_store.create_company(company_name)

        # Save financials per period (or default period from filename)
        period = financials.pop("period", None) or filename.replace(".xlsx", "").replace(".csv", "")
        periods_saved = []
        if isinstance(period, str):
            _guarded_save_financials(company_id, period, financials, saved_path)
            periods_saved.append(period)
        # Also save per-sheet if multi-sheet
        for sheet in result.sheets:
            for rec in sheet.records:
                p = rec.get("period")
                if p and p not in periods_saved:
                    _guarded_save_financials(company_id, str(p), rec, saved_path)
                    periods_saved.append(str(p))

        # 5. Log upload
        upload_id = data_store.log_upload(
            filename=filename,
            file_type=result.file_type,
            file_size=len(raw_bytes),
            company_id=company_id,
            parsed_records=sum(len(s.records) for s in result.sheets),
            confidence=result.confidence_score,
            status="success",
        )

        return {
            "success": True,
            "file_saved": saved_path,
            "company_id": company_id,
            "periods_saved": periods_saved,
            "upload_id": upload_id,
            "parsed_data": result.to_dict(),
            "validation": validation.to_dict(),
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/smart-upload")
async def smart_upload(file: UploadFile = File(...)):
    """Upload + Smart Analyze in one step. Accepts multipart file upload.
    Returns full analysis: extracted financials, balance sheet, orchestrator results."""
    import time as _time_upload
    _t0_upload = _time_upload.time()
    try:
        from app.services.multi_sheet_analyzer import multi_sheet_analyzer
        from app.services.data_validator import data_validator
        from app.services.data_store import data_store
        from app.services.orchestrator import orchestrator
        from app.services.pdf_report import pdf_generator
        import os
        from datetime import datetime, timezone
        from fastapi import File, UploadFile

        # 1. Read file bytes
        raw_bytes = await file.read()
        filename = file.filename or "upload.xlsx"

        # ─── File size guard (before any parsing) ────────────────────
        from fastapi import HTTPException
        from app.config import settings as _settings
        if len(raw_bytes) > _settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large: {len(raw_bytes) / 1024 / 1024:.1f}MB. "
                    f"Maximum allowed: {_settings.MAX_UPLOAD_SIZE_MB}MB. "
                    "Split the file into smaller sheets and retry."
                ),
            )

        # Detect period from filename IMMEDIATELY (before any processing)
        import re as _re_period
        _period_match = _re_period.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})',
            filename, _re_period.IGNORECASE)
        _detected_period = None
        if _period_match:
            _mm = {"january":"01","february":"02","march":"03","april":"04","may":"05","june":"06",
                   "july":"07","august":"08","september":"09","october":"10","november":"11","december":"12"}
            _detected_period = f"{_period_match.group(2)}-{_mm.get(_period_match.group(1).lower(),'01')}"
            logger.info("PERIOD FROM FILENAME: %s (file: %s)", _detected_period, filename)

        # 2. Save to uploads/
        os.makedirs("uploads", exist_ok=True)
        save_path = os.path.join("uploads", filename)
        with open(save_path, "wb") as f:
            f.write(raw_bytes)

        # ─── Document Intelligence: detect file type ───────────────
        from app.services.document_intelligence import doc_intelligence
        doc_analysis = doc_intelligence.analyze(save_path)
        logger.info("Document Intelligence: type=%s confidence=%.2f company=%s period=%s",
                     doc_analysis.doc_type, doc_analysis.confidence,
                     doc_analysis.detected_company, doc_analysis.detected_period)

        # ─── Trial Balance path ──────────────────────────────────────
        if doc_analysis.doc_type == "trial_balance" and doc_analysis.confidence >= 0.5:
            from app.services.tb_parser import tb_parser
            from app.services.tb_to_statements import tb_to_statements
            tb_result = tb_parser.detect_and_parse(save_path)
            if tb_result and tb_result.detected and tb_result.postable_count > 0:
                logger.info("TB detected: %d accounts (%d postable), company=%s, period=%s, balanced=%s",
                            tb_result.account_count, tb_result.postable_count,
                            tb_result.company, tb_result.period, tb_result.is_balanced)
                statements = tb_to_statements.convert(tb_result)
                all_data = tb_to_statements.to_financials_dict(statements)
                pnl_data = tb_to_statements.to_pnl_dict(statements)
                bs_data = tb_to_statements.to_bs_dict(statements)

                # Use TB-detected metadata
                company_name = tb_result.company or doc_analysis.detected_company or "Unknown Company"
                _save_period = _detected_period or tb_result.period or doc_analysis.detected_period or datetime.now(timezone.utc).strftime("%Y-%m")

                # Find/create company
                existing = data_store.list_companies()
                company_id = None
                for ec in existing:
                    if company_name.lower() in ec["name"].lower() or ec["name"].lower() in company_name.lower():
                        company_id = ec["id"]
                        company_name = ec["name"]
                        break
                if not company_id:
                    company_id = data_store.create_company(company_name, "fuel_distribution")

                # Save financials via OntologyWriteGuard (all writes gated)
                _guarded_save_financials(company_id, _save_period, all_data, source_file=filename, user="upload_api")
                import json as _tb_json
                data_store.log_upload(
                    filename=filename, file_type="trial_balance", file_size=len(raw_bytes),
                    company_id=company_id,
                    parsed_records=tb_result.postable_count,
                    confidence=int(doc_analysis.confidence * 100),
                    status="processed",
                    result_json=_tb_json.dumps({
                        "doc_type": "trial_balance",
                        "accounts": tb_result.account_count,
                        "postable": tb_result.postable_count,
                        "balanced": tb_result.is_balanced,
                        "revenue_breakdown": tb_to_statements.to_revenue_breakdown(statements),
                        "cogs_breakdown": tb_to_statements.to_cogs_breakdown(statements),
                        "pl_line_items": tb_to_statements.to_pl_line_items(statements),
                    }, ensure_ascii=False),
                )

                # Build breakdowns from TB account data
                rev_breakdown = tb_to_statements.to_revenue_breakdown(statements)
                cogs_bd = tb_to_statements.to_cogs_breakdown(statements)
                pl_lines = tb_to_statements.to_pl_line_items(statements)
                rev_by_cat = {}
                for rb in rev_breakdown:
                    cat = rb.get("category", "Other")
                    rev_by_cat[cat] = rev_by_cat.get(cat, 0) + rb.get("net_revenue", 0)

                result = {
                    "success": True,
                    "company": company_name,
                    "period": _save_period,
                    "company_id": company_id,
                    "doc_type": "trial_balance",
                    "file_saved": save_path,
                    "pnl": pnl_data,
                    "extracted_financials": pnl_data,
                    "balance_sheet": bs_data,
                    "revenue_breakdown": rev_breakdown,
                    "cogs_breakdown": cogs_bd,
                    "pl_line_items": pl_lines,
                    "revenue_by_category": rev_by_cat,
                    "trial_balance_accounts": tb_result.postable_count,
                    "tb_balanced": tb_result.is_balanced,
                    "validation": {"score": 90, "flags": [], "corrected_data": pnl_data},
                    "warnings": tb_result.warnings + statements.warnings,
                    "data_quality_score": 90 if tb_result.is_balanced else 70,
                    "data_quality_flags": [],
                    "sheet_analyses": [{"sheet": tb_result.sheet_name, "type": "trial_balance",
                                        "accounts": tb_result.account_count}],
                    "account_classifications": statements.account_classifications[:50],
                    "bs_equation_holds": statements.bs_equation_holds,
                    "pending_approvals": statements.pending_approvals,
                    "classification_summary": statements.classification_summary,
                }

                # Save pending approvals to database for user review
                if statements.pending_approvals:
                    try:
                        from app.models.all_models import ClassificationApproval
                        from app.database import AsyncSessionLocal
                        from datetime import datetime, timezone as tz
                        async with AsyncSessionLocal() as db_sess:
                            for pa in statements.pending_approvals:
                                approval = ClassificationApproval(
                                    dataset_id=None,
                                    account_code=pa["code"],
                                    account_name=pa.get("name", ""),
                                    suggested_section=pa.get("section", ""),
                                    suggested_pl_line=pa.get("pl_line", ""),
                                    suggested_bs_side=pa.get("side", ""),
                                    confidence=pa.get("confidence", 0.0),
                                    method=pa.get("method", ""),
                                    explanation=pa.get("explanation", ""),
                                    alternatives_json=pa.get("alternatives", []),
                                    status="pending",
                                )
                                db_sess.add(approval)
                            await db_sess.commit()
                        logger.info("Saved %d pending classification approvals", len(statements.pending_approvals))
                    except Exception as approval_err:
                        logger.warning("Failed to save pending approvals: %s", approval_err)

                # Run orchestrator on TB-derived data
                try:
                    v3_result = {}
                    orch_input = dict(pnl_data)
                    orch_bs = dict(bs_data)
                    try:
                        orch_out = orchestrator.run(orch_input, {}, orch_bs, industry_id="fuel_distribution")
                        if orch_out:
                            v3_result = orch_out if isinstance(orch_out, dict) else orch_out.to_dict()
                    except Exception as orch_err:
                        logger.warning("Orchestrator on TB data failed (non-blocking): %s", orch_err)
                    result["orchestrator"] = v3_result
                    if v3_result.get("executive_summary"):
                        result["health_score"] = v3_result["executive_summary"].get("health_score", 0)
                        result["health_grade"] = v3_result["executive_summary"].get("health_grade", "")
                except Exception:
                    pass

                # Auto-sync warehouse after successful TB upload
                try:
                    from app.services.warehouse import warehouse as _wh
                    _wh.sync_from_sqlite()
                except Exception as _wh_err:
                    logger.debug("Warehouse auto-sync after TB upload: %s", _wh_err)

                # Emit real-time upload_complete event
                try:
                    from app.services.realtime import realtime_manager
                    await realtime_manager.emit("upload_complete", {
                        "filename": filename,
                        "doc_type": doc_analysis.doc_type,
                        "company": result.get("company", ""),
                        "period": result.get("period", ""),
                        "health_score": result.get("health_score"),
                    })
                except Exception:
                    pass

                return result

        # ─── Transaction Journal path ────────────────────────────────
        if doc_analysis.doc_type == "transaction_journal" and doc_analysis.confidence >= 0.5:
            from app.services.transaction_parser import transaction_parser
            from app.services.gl_pipeline import gl_pipeline
            txn_result = transaction_parser.detect_and_parse(save_path)
            if txn_result and txn_result.detected and len(txn_result.transactions) > 0:
                logger.info("Transaction journal detected: %d transactions", len(txn_result.transactions))
                gl_input = txn_result.as_gl_input
                _save_period = _detected_period or txn_result.period or datetime.now(timezone.utc).strftime("%Y-%m")
                pipeline_out = gl_pipeline.run_from_transactions(gl_input, _save_period, "GEL")
                # Extract P&L and BS from pipeline output
                stmts = pipeline_out.get("statements", {})
                pnl_data = stmts.get("income_statement", {})
                bs_data = stmts.get("balance_sheet", {})
                all_data = {**pnl_data, **{f"bs_{k}": v for k, v in bs_data.items()}, **bs_data}

                company_name = doc_analysis.detected_company or "Unknown Company"
                existing = data_store.list_companies()
                company_id = None
                for ec in existing:
                    if company_name.lower() in ec["name"].lower() or ec["name"].lower() in company_name.lower():
                        company_id = ec["id"]
                        company_name = ec["name"]
                        break
                if not company_id:
                    company_id = data_store.create_company(company_name, "fuel_distribution")

                _guarded_save_financials(company_id, _save_period, all_data, source_file=filename)
                data_store.log_upload(
                    filename=filename, file_type="transaction_journal", file_size=len(raw_bytes),
                    company_id=company_id, parsed_records=len(txn_result.transactions),
                    confidence=int(doc_analysis.confidence * 100), status="processed",
                )
                # Auto-sync warehouse after successful transaction journal upload
                try:
                    from app.services.warehouse import warehouse as _wh
                    _wh.sync_from_sqlite()
                except Exception as _wh_err:
                    logger.debug("Warehouse auto-sync after txn upload: %s", _wh_err)

                return {
                    "success": True, "company": company_name, "period": _save_period,
                    "doc_type": "transaction_journal",
                    "pnl": pnl_data, "extracted_financials": pnl_data, "balance_sheet": bs_data,
                    "revenue_breakdown": [], "cogs_breakdown": [],
                    "trial_balance": pipeline_out.get("trial_balance", {}),
                    "reconciliation": pipeline_out.get("reconciliation", {}),
                    "validation": {"score": 85, "flags": [], "corrected_data": pnl_data},
                    "warnings": [],
                }

        # ─── Existing flow: P&L / BS / Combined report ──────────────
        # 3a. Skip slow LLM file analysis — use fast deterministic parsing
        llm_analysis = []
        llm_period = None
        llm_company = None

        # 3c. Smart analyze with pattern matching
        extracted = multi_sheet_analyzer.analyze_file(save_path)

        # Override period/company with LLM detection if the analyzer couldn't detect
        if llm_period and (not extracted.period or extracted.period == datetime.now(timezone.utc).strftime("%Y-%m")):
            extracted.period = llm_period
        if llm_company and not extracted.company_name:
            extracted.company_name = llm_company

        # ALWAYS try to detect period from filename (most reliable source)
        try:
            import re as _re2
            logger.info("Checking filename for period: '%s'", filename)
            fname_period = _re2.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})', filename, _re2.IGNORECASE)
            if not fname_period:
                fname_period = _re2.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})', save_path, _re2.IGNORECASE)
            if fname_period:
                month_name = fname_period.group(1)
                year = fname_period.group(2)
                month_map = {"january":"01","february":"02","march":"03","april":"04","may":"05","june":"06",
                             "july":"07","august":"08","september":"09","october":"10","november":"11","december":"12"}
                extracted.period = f"{year}-{month_map.get(month_name.lower(), '01')}"
                logger.info("Period from filename: %s", extracted.period)
            else:
                logger.info("No period found in filename: '%s'", filename)
        except Exception as period_err:
            logger.warning("Period detection from filename failed: %s", period_err)

        # 4. Validate
        validation = data_validator.validate(extracted.current_financials)

        # 5. Store — find existing company or create new
        company_name = extracted.company_name or (_detected_period and settings.COMPANY_NAME) or "Unknown Company"
        # Use LLM-detected company name if available AND longer than existing
        if llm_analysis:
            for la in llm_analysis:
                c = la.get("company_detected")
                if c and c != "unknown" and len(c) > 10 and len(c) > len(company_name):
                    company_name = c.split("//")[0].strip()  # Remove Russian translation
                    break

        # Find existing company by name (don't create duplicates)
        existing = data_store.list_companies()
        company_id = None
        for ec in existing:
            if ec["name"] == company_name:
                company_id = ec["id"]
                break
        if not company_id:
            # Try partial match
            for ec in existing:
                if company_name.lower() in ec["name"].lower() or ec["name"].lower() in company_name.lower():
                    company_id = ec["id"]
                    company_name = ec["name"]  # Use existing name
                    break
        if not company_id:
            company_id = data_store.create_company(company_name, "fuel_distribution")

        # Save P&L financials + balance sheet fields together
        all_data = dict(validation.corrected_data)
        # Also save balance sheet fields WITH bs_ prefix AND without (for direct access)
        if extracted.balance_sheet:
            for k, v in extracted.balance_sheet.items():
                all_data[f"bs_{k}"] = v
                all_data[k] = v  # Also save without prefix for dashboard
        _save_period = _detected_period or extracted.period
        _guarded_save_financials(company_id, _save_period, all_data, source_file=filename)
        import json as _json
        breakdown_data = {
            "revenue_breakdown": extracted.revenue_breakdown[:50],
            "cogs_breakdown": extracted.cogs_breakdown[:30],
            "pl_line_items": extracted.pl_line_items[:60],
            "balance_sheet": extracted.balance_sheet or {},
            "sheet_analyses": extracted.sheet_analyses,
        }
        data_store.log_upload(
            filename=filename, file_type="xlsx", file_size=len(raw_bytes),
            company_id=company_id,
            parsed_records=len(extracted.revenue_breakdown) + len(extracted.cogs_breakdown),
            confidence=85, status="processed",
            result_json=_json.dumps(breakdown_data, ensure_ascii=False, default=str),
        )

        result = {
            "success": True,
            "company": company_name,
            "period": _detected_period or extracted.period,
            "_debug_detected_period": _detected_period,
            "_debug_extracted_period": extracted.period,
            "_debug_filename": filename,
            "file_saved": save_path,
            "company_id": company_id,
            "sheet_analyses": extracted.sheet_analyses,
            "llm_file_analysis": llm_analysis if llm_analysis else None,
            "extracted_financials": extracted.current_financials,
            "pnl": extracted.current_financials,
            "balance_sheet": extracted.balance_sheet,
            "revenue_breakdown": extracted.revenue_breakdown[:50],
            "cogs_breakdown": extracted.cogs_breakdown[:30],
            "pl_line_items": extracted.pl_line_items[:60],
            "revenue_by_category": {},
            "trial_balance_accounts": len(extracted.trial_balance_accounts),
            "validation": validation.to_dict(),
            "warnings": extracted.warnings,
        }

        # Compute revenue by category
        for item in extracted.revenue_breakdown:
            cat = item.get("category", "Other")
            result["revenue_by_category"][cat] = result["revenue_by_category"].get(cat, 0) + item.get("net_revenue", 0)

        # ── Run Universal Parser for complete P&L (with G&A, Depreciation, BS) ──
        # The multi_sheet_analyzer may miss G&A/Depreciation. The universal parser
        # handles Mapping sheet (complete P&L) and BS sheet correctly.
        try:
            from app.services.socar_universal_parser import parse_nyx_excel
            universal_result = parse_nyx_excel(save_path, filename)
            if universal_result.success:
                # Merge universal parser's complete P&L into extracted financials
                upnl = universal_result.pnl
                if upnl.selling_expenses > 0 or upnl.admin_expenses > 0:
                    all_data["selling_expenses"] = upnl.selling_expenses
                    all_data["admin_expenses"] = upnl.admin_expenses
                    all_data["ga_expenses"] = upnl.selling_expenses + upnl.admin_expenses
                    all_data["total_opex"] = upnl.total_opex
                    all_data["ebitda"] = upnl.ebitda
                    all_data["depreciation"] = upnl.depreciation
                    all_data["ebit"] = upnl.ebit
                    all_data["non_operating_income"] = upnl.non_operating_income
                    all_data["non_operating_expense"] = upnl.non_operating_expense
                    all_data["profit_before_tax"] = upnl.profit_before_tax
                    all_data["net_profit"] = upnl.net_profit
                    # Update the result dict too
                    result["extracted_financials"].update({
                        "selling_expenses": upnl.selling_expenses,
                        "admin_expenses": upnl.admin_expenses,
                        "ga_expenses": upnl.selling_expenses + upnl.admin_expenses,
                        "ebitda": upnl.ebitda,
                        "depreciation": upnl.depreciation,
                        "ebit": upnl.ebit,
                        "non_operating_income": upnl.non_operating_income,
                        "non_operating_expense": upnl.non_operating_expense,
                        "profit_before_tax": upnl.profit_before_tax,
                        "net_profit": upnl.net_profit,
                    })
                    result["pnl"] = result["extracted_financials"]
                    logger.info("Universal parser: GA=%.0f (Sell=%.0f + Admin=%.0f), D&A=%.0f, EBITDA=%.0f, NP=%.0f",
                                upnl.selling_expenses + upnl.admin_expenses,
                                upnl.selling_expenses, upnl.admin_expenses,
                                upnl.depreciation, upnl.ebitda, upnl.net_profit)

                # Merge BS from universal parser if available
                ubs = universal_result.balance_sheet
                if ubs.total_assets > 0:
                    bs_dict = ubs.__dict__
                    result["balance_sheet"] = bs_dict
                    for k, v in bs_dict.items():
                        all_data[f"bs_{k}"] = v
                        all_data[k] = v

                # Data quality info
                result["data_quality_score"] = universal_result.data_quality_score
                result["data_quality_flags"] = [f.__dict__ for f in universal_result.data_quality_flags]
                result["file_type_detected"] = universal_result.file_type
                result["period_source"] = universal_result.period_source

                # Expense detail
                if universal_result.selling_expense_detail:
                    result["selling_expense_detail"] = {c.name: c.amount for c in universal_result.selling_expense_detail}
                if universal_result.admin_expense_detail:
                    result["admin_expense_detail"] = {c.name: c.amount for c in universal_result.admin_expense_detail}

                # Re-save financials with complete data
                _guarded_save_financials(company_id, _save_period, all_data, source_file=filename)
                logger.info("Universal parser merged: complete P&L with G&A, D&A, BS saved")
        except Exception as up_err:
            logger.warning("Universal parser failed (non-blocking, using legacy): %s", up_err)

        # Build NYX Core Thinker P&L with product-level breakdown
        try:
            from app.services.socar_pl_engine import nyx_pl_engine
            nyx_pl = nyx_pl_engine.build_pl(
                revenue_breakdown=extracted.revenue_breakdown,
                cogs_breakdown=extracted.cogs_breakdown,
            )
            result["nyx_pl"] = nyx_pl
            # If universal parser provided complete P&L, build enhanced line items
            # that include Selling/Admin/D&A/NonOp — not just Revenue/COGS/GM
            try:
                from app.services.upload_integration import _build_pl_line_items
                upnl_data = result.get("extracted_financials", {})
                if upnl_data.get("selling_expenses") or upnl_data.get("admin_expenses"):
                    # Build a PnL-like object from the merged data
                    class _PnlProxy:
                        pass
                    _p = _PnlProxy()
                    _p.revenue = upnl_data.get("revenue", 0)
                    _p.revenue_wholesale = upnl_data.get("revenue_wholesale", 0)
                    _p.revenue_retail = upnl_data.get("revenue_retail", 0)
                    _p.revenue_other = upnl_data.get("revenue_other", upnl_data.get("other_income", 0))
                    _p.cogs = upnl_data.get("cogs", 0)
                    _p.cogs_wholesale = upnl_data.get("cogs_wholesale", 0)
                    _p.cogs_retail = upnl_data.get("cogs_retail", 0)
                    _p.gross_profit = upnl_data.get("gross_profit", _p.revenue - _p.cogs)
                    _p.selling_expenses = upnl_data.get("selling_expenses", 0)
                    _p.admin_expenses = upnl_data.get("admin_expenses", 0)
                    _p.ebitda = upnl_data.get("ebitda", 0)
                    _p.depreciation = upnl_data.get("depreciation", 0)
                    _p.ebit = upnl_data.get("ebit", 0)
                    _p.non_operating_income = upnl_data.get("non_operating_income", 0)
                    _p.non_operating_expense = upnl_data.get("non_operating_expense", 0)
                    _p.profit_before_tax = upnl_data.get("profit_before_tax", 0)
                    _p.net_profit = upnl_data.get("net_profit", 0)
                    # Only override if the analyzer didn't produce richer hierarchical items
                    if not extracted.pl_line_items or not any(i.get("code") for i in extracted.pl_line_items):
                        result["pl_line_items"] = _build_pl_line_items(_p)
                else:
                    if not extracted.pl_line_items:
                        result["pl_line_items"] = nyx_pl.get("line_items", [])
            except Exception:
                if not extracted.pl_line_items:
                    result["pl_line_items"] = nyx_pl.get("line_items", [])
        except Exception as pl_err:
            logger.warning("NYX P&L engine failed: %s", pl_err)

        # 6. Run FAST orchestrator (legacy — instant, no LLM wait)
        v3_result = {}
        try:
            from app.services.orchestrator import orchestrator as _fast_orch
            _orch_fin = dict(validation.corrected_data)
            _orch_bs = extracted.balance_sheet or {}
            _orch_result = _fast_orch.run(
                current_financials=_orch_fin,
                balance_sheet=_orch_bs,
                monte_carlo_iterations=100,
            )
            v3_result = {"orchestrator_legacy": _orch_result.to_dict()}
            data_store.save_orchestrator_result(company_id, v3_result)
            result["orchestrator"] = v3_result
            result["health_score"] = _orch_result.health_score
            result["health_grade"] = _orch_result.health_grade
            result["strategy_name"] = _orch_result.strategy_name
            # Quick LLM insight (non-blocking, best-effort)
            try:
                from app.services.llm_chain import llm_chain
                llm_resp = llm_chain.reason_sync(validation.corrected_data)
                if llm_resp and isinstance(llm_resp, dict):
                    result["llm_insights"] = llm_resp.get("insights", [])
                    result["llm_summary"] = llm_resp.get("summary", "")
                    result["llm_model"] = llm_resp.get("model_used", "")
            except Exception as llm_err:
                logger.warning("LLM insight failed (non-blocking): %s", llm_err)
        except Exception as orch_err:
            logger.warning("Orchestrator failed (non-blocking): %s", orch_err)
            result["orchestrator_error"] = str(orch_err)

        # Also generate PDF if full data available
        if v3_result.get("orchestrator_legacy"):
            os.makedirs("exports", exist_ok=True)
            try:
                pdf_bytes = pdf_generator.generate_from_orchestrator(
                    v3_result["orchestrator_legacy"], company_name,
                )
                pdf_name = f"{company_name.replace(' ', '_')}_{extracted.period}_Report.pdf"
                pdf_path = os.path.join("exports", pdf_name)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                result["pdf_report"] = pdf_path
            except Exception as pdf_err:
                result["pdf_error"] = str(pdf_err)

        # ── Upload Intelligence Assessment ──
        try:
            from app.services.upload_intelligence import assess_upload
            sheets_list = [sa.get("sheet_name", sa.get("name", "")) for sa in extracted.sheet_analyses] if extracted.sheet_analyses else []
            if not sheets_list:
                # Fallback: use openpyxl to get sheet names
                import openpyxl, io
                _wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True)
                sheets_list = _wb.sheetnames
                _wb.close()
            upload_assessment = assess_upload(sheets_list, result)
            result["upload_assessment"] = upload_assessment.to_dict()
        except Exception as ua_err:
            logger.warning("Upload intelligence assessment failed: %s", ua_err)

        # Auto-sync warehouse after successful P&L upload
        try:
            from app.services.warehouse import warehouse as _wh
            _wh.sync_from_sqlite()
        except Exception as _wh_err:
            logger.debug("Warehouse auto-sync after P&L upload: %s", _wh_err)

        # Record smart-upload activity event
        try:
            from app.services.activity_feed import activity_feed
            _dur_u = int((_time_upload.time() - _t0_upload) * 1000)
            activity_feed.record(
                event_type="upload", resource_type="Dataset",
                resource_id=filename, action="smart_upload",
                details={"filename": filename, "file_size": len(raw_bytes),
                         "company": result.get("company", ""), "period": result.get("period", "")},
                status="success", duration_ms=_dur_u,
            )
        except Exception:
            pass

        return result
    except Exception as e:
        import traceback
        try:
            from app.services.activity_feed import activity_feed
            activity_feed.record(
                event_type="upload", resource_type="Dataset",
                resource_id="unknown", action="smart_upload",
                details={"error": str(e)[:200]}, status="failure",
                duration_ms=int((_time_upload.time() - _t0_upload) * 1000),
            )
        except Exception:
            pass
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.post("/agents/smart-analyze")
async def smart_analyze(body: dict):
    """Phase T: Multi-sheet intelligent analysis — detects all sheet types,
    extracts P&L + Balance Sheet + Revenue/COGS breakdowns + Trial Balance,
    runs full orchestrator, generates PDF report, returns everything."""
    try:
        from app.services.multi_sheet_analyzer import multi_sheet_analyzer
        from app.services.data_validator import data_validator
        from app.services.data_store import data_store
        from app.services.orchestrator import orchestrator
        from app.services.pdf_report import pdf_generator
        import base64, os
        from datetime import datetime, timezone

        data_b64 = body.get("data")
        filename = body.get("filename", "upload.xlsx")
        file_path = body.get("path")
        run_orchestrator = body.get("run_orchestrator", True)
        generate_pdf = body.get("generate_pdf", True)

        # 1. Parse with MultiSheetAnalyzer
        if data_b64:
            raw_bytes = base64.b64decode(data_b64)
            extracted = multi_sheet_analyzer.analyze_bytes(raw_bytes)
        elif file_path:
            extracted = multi_sheet_analyzer.analyze_file(file_path)
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
        else:
            return {"error": "Provide 'data' (base64) or 'path'"}

        # 2. Save original file
        os.makedirs("uploads", exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = f"{ts}_{filename.replace('/', '_').replace(chr(92), '_')}"
        saved_path = os.path.join("uploads", safe_name)
        with open(saved_path, "wb") as f:
            f.write(raw_bytes)

        # 3. Validate extracted financials
        validation = data_validator.validate(extracted.current_financials)

        # 4. Save to DataStore
        company_name = extracted.company_name or body.get("company", "Default Company")
        company_id = data_store.create_company(company_name, "fuel_distribution")
        _guarded_save_financials(company_id, extracted.period, validation.corrected_data)
        upload_id = data_store.log_upload(
            filename=filename, file_type="xlsx", file_size=len(raw_bytes),
            company_id=company_id,
            parsed_records=len(extracted.revenue_breakdown) + len(extracted.cogs_breakdown),
            confidence=85, status="processed",
        )

        result_out = {
            "success": True,
            "company": company_name,
            "period": _detected_period or extracted.period,
            "file_saved": saved_path,
            "company_id": company_id,
            "upload_id": upload_id,
            "sheet_analyses": extracted.sheet_analyses,
            "extracted_financials": extracted.current_financials,
            "balance_sheet": extracted.balance_sheet,
            "revenue_breakdown_count": len(extracted.revenue_breakdown),
            "cogs_breakdown_count": len(extracted.cogs_breakdown),
            "trial_balance_accounts": len(extracted.trial_balance_accounts),
            "account_mappings": len(extracted.account_mapping),
            "validation": validation.to_dict(),
            "warnings": extracted.warnings,
        }

        # 5. Run orchestrator if requested
        if run_orchestrator and extracted.current_financials.get("revenue", 0) > 0:
            orch_result = orchestrator.run(
                current_financials=validation.corrected_data,
                balance_sheet=extracted.balance_sheet or None,
                industry_id=body.get("industry", "fuel_distribution"),
                monte_carlo_iterations=body.get("mc_iterations", 200),
            )
            data_store.save_orchestrator_result(company_id, orch_result.to_dict())

            result_out["orchestrator"] = {
                "stages_completed": orch_result.stages_completed,
                "stages_failed": orch_result.stages_failed,
                "health_score": orch_result.health_score,
                "health_grade": orch_result.health_grade,
                "strategy": orch_result.strategy_name,
                "conviction_grade": orch_result.conviction_grade,
                "actions_evaluated": orch_result.actions_evaluated,
                "active_alerts": orch_result.active_alerts,
                "cash_runway_months": orch_result.cash_runway_months,
                "kpi_on_track": orch_result.kpi_on_track,
                "kpi_missed": orch_result.kpi_missed,
                "execution_ms": orch_result.execution_time_ms,
            }

            # 6. Generate PDF if requested
            if generate_pdf:
                os.makedirs("exports", exist_ok=True)
                pdf_bytes = pdf_generator.generate_from_orchestrator(
                    orch_result.to_dict(), company_name,
                )
                pdf_name = f"{company_name.replace(' ', '_')}_{extracted.period}_Report.pdf"
                pdf_path = os.path.join("exports", pdf_name)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                result_out["pdf_report"] = pdf_path
                result_out["pdf_size"] = len(pdf_bytes)

        return result_out
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.post("/agents/parse-pdf")
async def parse_pdf(body: dict):
    """Phase N: Parse PDF financial document + persist to DataStore."""
    try:
        from app.services.smart_pdf_extractor import pdf_extractor
        from app.services.data_validator import data_validator
        from app.services.data_store import data_store
        import base64, os
        from datetime import datetime, timezone

        data_b64 = body.get("data")
        filename = body.get("filename", "upload.pdf")
        company_name = body.get("company", "Default Company")

        # 1. Parse
        if data_b64:
            raw_bytes = base64.b64decode(data_b64)
            result = pdf_extractor.extract_bytes(raw_bytes, filename)
        else:
            path = body.get("path")
            if not path:
                return {"error": "Provide 'data' (base64) or 'path'"}
            result = pdf_extractor.extract_file(path)
            with open(path, "rb") as f:
                raw_bytes = f.read()

        # 2. Save file
        os.makedirs("uploads", exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = f"{ts}_{filename.replace('/', '_').replace(chr(92), '_')}"
        saved_path = os.path.join("uploads", safe_name)
        with open(saved_path, "wb") as f:
            f.write(raw_bytes)

        # 3. Validate + persist
        validation = data_validator.validate(result.normalized_financials)
        financials = validation.corrected_data

        company_id = body.get("company_id")
        if not company_id:
            companies = data_store.list_companies()
            match = next((c for c in companies if c["name"] == company_name), None)
            company_id = match["id"] if match else data_store.create_company(company_name)

        period = financials.pop("period", None) or filename.replace(".pdf", "")
        _guarded_save_financials(company_id, str(period), financials, saved_path)

        upload_id = data_store.log_upload(
            filename=filename, file_type="pdf", file_size=len(raw_bytes),
            company_id=company_id,
            parsed_records=sum(len(s.records) for s in result.sheets),
            confidence=result.confidence_score, status="success",
        )

        return {
            "success": True,
            "file_saved": saved_path,
            "company_id": company_id,
            "periods_saved": [str(period)],
            "upload_id": upload_id,
            "parsed_data": result.to_dict(),
            "validation": validation.to_dict(),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/ingestion/account-tree")
async def ingestion_account_tree():
    """
    Return a summary of the 1C COA account hierarchy loaded in the KG.
    Returns counts by type, IFRS section, and dimension types.
    """
    try:
        from app.services.knowledge_graph import knowledge_graph
        if not knowledge_graph.is_built:
            knowledge_graph.build()
        coa_entities = knowledge_graph._index_by_type.get("coa_account", [])
        dims_entities = knowledge_graph._index_by_type.get("onec_dimension", [])
        # Group by IFRS section
        pl_accounts = []
        bs_accounts = []
        for eid in coa_entities[:50]:  # sample
            e = knowledge_graph._entities.get(eid)
            if e:
                section = e.properties.get("ifrs_section", "")
                entry   = {"code": e.properties.get("code"), "name": e.label_en,
                           "bs_line": e.properties.get("ifrs_bs_line"),
                           "pl_line": e.properties.get("ifrs_pl_line")}
                if section == "income_statement":
                    pl_accounts.append(entry)
                else:
                    bs_accounts.append(entry)
        return {
            "total_coa_accounts":  len(coa_entities),
            "total_dimensions":    len(dims_entities),
            "pl_accounts_sample":  pl_accounts[:15],
            "bs_accounts_sample":  bs_accounts[:15],
            "total_kg_entities":   knowledge_graph.entity_count,
        }
    except Exception as e:
        return {"error": str(e)}
