"""
FinAI Agent Datasets Sub-Router
==================================
Datasets, classifications, eval, export, financial chat, alerts,
connectors, subledger, COA upload, audit logs, insight feedback.
Extracted from agent.py for maintainability.
"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix -- parent adds /api/agent


def _guarded_save_financials(company_id, period, financials, source_file=None, user="api"):
    """Route all financial writes through OntologyWriteGuard."""
    try:
        from app.services.ontology_write_guard import write_guard
        write_guard.write_financials(company_id, period, financials, user=user)
    except Exception:
        from app.services.data_store import data_store
        data_store.save_financials(company_id, period, financials, source_file)


# ── Phase Q: Financial Chat + Persistent Alerts ──────────────────────────────

@router.post("/agents/financial-chat")
async def financial_chat_direct(body: dict):
    """Phase Q: Direct financial chat engine with action execution."""
    try:
        from app.services.financial_chat import chat_engine
        query = body.get("query", "")
        financials = body.get("financials", {})
        previous = body.get("previous", {})
        balance_sheet = body.get("balance_sheet", {})
        if financials:
            chat_engine.set_context(financials, previous, balance_sheet)
        response = chat_engine.query(query)
        return response.to_dict()
    except Exception as e:
        return {"error": str(e)}


@router.get("/alerts")
async def get_alerts(severity: str = None):
    """Phase Q: Get active alerts, optionally filtered by severity."""
    try:
        from app.services.persistent_alerts import alert_manager
        alerts = alert_manager.get_active_alerts(severity=severity)
        return {"alerts": [a.to_dict() for a in alerts], "count": len(alerts)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """Phase Q: Acknowledge an alert."""
    try:
        from app.services.persistent_alerts import alert_manager
        ok = alert_manager.acknowledge_alert(alert_id)
        return {"acknowledged": ok}
    except Exception as e:
        return {"error": str(e)}


@router.get("/alerts/rules")
async def get_alert_rules():
    """Phase Q: Get current alert threshold rules."""
    try:
        from app.services.persistent_alerts import alert_manager
        rules = alert_manager.get_rules()
        return {"rules": [r.to_dict() for r in rules]}
    except Exception as e:
        return {"error": str(e)}


@router.put("/alerts/rules")
async def update_alert_rule(body: dict):
    """Phase Q: Update an alert rule threshold."""
    try:
        from app.services.persistent_alerts import alert_manager
        rule_id = body.get("rule_id")
        if not rule_id:
            return {"error": "rule_id required"}
        ok = alert_manager.update_rule(rule_id, body)
        return {"updated": ok}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
#   EVALUATION ENGINE -- AI Reasoning Quality Assessment
# ═══════════════════════════════════════════════════════════════════

@router.get("/agents/eval/cases")
async def eval_list_cases():
    """List available evaluation cases."""
    try:
        from app.services.eval_engine import EvalEngine
        engine = EvalEngine()
        return {"cases": engine.list_cases()}
    except Exception as e:
        logger.error("eval_list_cases error: %s", e)
        return {"error": str(e)}


@router.post("/agents/eval/run-all")
async def eval_run_all():
    """Run evaluation on all cases. Returns full report."""
    try:
        from app.services.eval_engine import EvalEngine
        from app.services.local_llm import LocalLLMService
        llm = LocalLLMService()
        engine = EvalEngine(llm_service=llm)
        report = await engine.run_all()
        return report.to_dict()
    except Exception as e:
        logger.error("eval_run_all error: %s", e, exc_info=True)
        return {"error": str(e)}


@router.post("/agents/eval/run/{case_id}")
async def eval_run_single(case_id: str):
    """Run evaluation on a single case."""
    try:
        from app.services.eval_engine import EvalEngine
        from app.services.local_llm import LocalLLMService
        llm = LocalLLMService()
        engine = EvalEngine(llm_service=llm)
        result = await engine.run_single(case_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("eval_run_single error: %s", e, exc_info=True)
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
#   EXCEL EXPORT -- Styled financial reports in .xlsx
# ═══════════════════════════════════════════════════════════════════

@router.post("/agents/export/excel")
async def export_excel(body: dict):
    """Generate a styled multi-sheet Excel report. Returns .xlsx file.
    Merges frontend-provided data with live dashboard data for completeness."""
    try:
        from app.services.excel_export import excel_exporter
        from app.routers.agent_dashboard import get_dashboard
        from fastapi.responses import Response

        # Fetch live dashboard data so the export always reflects current state
        live = {}
        try:
            live = await get_dashboard(period=body.get("period"))
            if isinstance(live, dict) and not live.get("empty"):
                logger.info("export_excel: dashboard returned revenue=%s", live.get("financials", {}).get("revenue"))
            else:
                logger.warning("export_excel: dashboard returned empty or non-dict: %s", type(live))
                live = {}
        except Exception as _e:
            logger.warning("export_excel: dashboard call failed: %s", _e)
            live = {}

        live_fin = live.get("financials") or {}
        live_rev = live.get("revenue_breakdown") or []
        live_cogs = live.get("cogs_breakdown") or []
        live_pl = live.get("pl_line_items") or []
        live_bs = live.get("balance_sheet") or {}
        live_company = live.get("company", {}).get("name", "") if isinstance(live.get("company"), dict) else ""
        live_period = live.get("period", "")

        # Merge: body data fills in anything not in live data
        pnl_body = body.get("pnl") or body.get("financials") or body.get("current", {})
        pnl = {**live_fin, **{k: v for k, v in pnl_body.items() if v}} if pnl_body else live_fin
        bs = body.get("balance_sheet") if body.get("balance_sheet") else live_bs
        rev_bd = body.get("revenue_breakdown") if body.get("revenue_breakdown") else live_rev
        cogs_bd = body.get("cogs_breakdown") if body.get("cogs_breakdown") else live_cogs
        pl_items = body.get("pl_line_items") if body.get("pl_line_items") else live_pl
        company_name = body.get("company") or live_company or "Company"
        period_str = body.get("period") or live_period

        xlsx_bytes = excel_exporter.generate(
            pnl=pnl,
            balance_sheet=bs,
            revenue_breakdown=rev_bd,
            cogs_breakdown=cogs_bd,
            pl_line_items=pl_items,
            company=company_name,
            period=period_str,
        )

        # Sanitize filename -- HTTP headers must be ASCII
        import re as _re
        raw_name = body.get('company', 'finai')
        safe_name = _re.sub(r'[^\x20-\x7E]', '', raw_name).strip().replace(' ', '_') or 'FinAI'
        filename = f"{safe_name}_report.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error("export_excel error: %s", e, exc_info=True)
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
#   DATASET MANAGEMENT -- List uploads, switch active dataset
# ═══════════════════════════════════════════════════════════════════

@router.get("/agents/datasets")
async def list_datasets(db: AsyncSession = Depends(get_db)):
    """List all uploaded datasets with metadata -- from main DB, not data_store."""
    try:
        # Primary: query the real datasets table
        from app.models.all_models import Dataset
        from sqlalchemy import select
        result = await db.execute(
            select(Dataset).order_by(Dataset.id.desc())
        )
        datasets = result.scalars().all()
        return {"datasets": [d.to_dict() for d in datasets]}
    except Exception as e:
        logger.error("list_datasets error: %s", e)
        # Fallback to data_store
        try:
            from app.services.data_store import data_store
            return {"datasets": data_store.list_datasets()}
        except Exception:
            return {"datasets": [], "error": str(e)}


@router.get("/agents/datasets/{dataset_id}")
async def get_dataset(dataset_id: int):
    """Load a specific dataset's financial data."""
    try:
        from app.services.data_store import data_store
        data = data_store.get_dataset_full(dataset_id)
        if not data:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_dataset error: %s", e)
        return {"error": str(e)}


@router.delete("/agents/datasets/{dataset_id}")
async def delete_dataset_endpoint(dataset_id: int):
    """Delete a dataset and all its related data (snapshots, orchestrator runs)."""
    try:
        from app.services.data_store import data_store
        result = data_store.delete_dataset(dataset_id)
        if not result.get("deleted"):
            raise HTTPException(status_code=404, detail=result.get("error", "Dataset not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_dataset error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# --- Classification Approvals -----------------------------------------

@router.get("/agents/classifications/pending")
async def list_pending_classifications(db: AsyncSession = Depends(get_db)):
    """List all pending account classification approvals."""
    try:
        from app.models.all_models import ClassificationApproval
        result = await db.execute(
            select(ClassificationApproval)
            .where(ClassificationApproval.status == "pending")
            .order_by(ClassificationApproval.created_at.desc())
        )
        approvals = result.scalars().all()
        return {"pending": [a.to_dict() for a in approvals]}
    except Exception as e:
        logger.error("list_pending_classifications error: %s", e)
        return {"pending": [], "error": str(e)}


@router.post("/agents/classifications/{approval_id}/approve")
async def approve_classification(approval_id: int, db: AsyncSession = Depends(get_db)):
    """Approve a suggested classification -- saves to LearningEngine."""
    try:
        from app.models.all_models import ClassificationApproval
        from app.services.learning_engine import learning_engine
        from datetime import datetime, timezone

        approval = (await db.execute(
            select(ClassificationApproval).where(ClassificationApproval.id == approval_id)
        )).scalar_one_or_none()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")

        # Mark as approved
        approval.status = "approved"
        approval.resolved_at = datetime.now(timezone.utc)
        await db.commit()

        # Save to LearningEngine as user-verified (confidence 0.95)
        classification = {
            "section": approval.suggested_section,
            "side": approval.suggested_bs_side,
            "pl_line": approval.suggested_pl_line,
            "sub": approval.suggested_sub or "",
            "normal_balance": "credit" if approval.suggested_bs_side in ("liability", "equity", "revenue") else "debit",
        }
        learning_engine.record_correction(
            account_code=approval.account_code,
            original={},
            corrected=classification,
            source="user",
        )

        # Sync to KG
        try:
            learning_engine.sync_to_kg()
        except Exception:
            pass

        return {"approved": True, "account_code": approval.account_code, "classification": classification}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("approve_classification error: %s", e)
        return {"error": str(e)}


@router.post("/agents/classifications/{approval_id}/modify")
async def modify_classification(approval_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    """Approve with user's correction -- saves corrected classification."""
    try:
        from app.models.all_models import ClassificationApproval
        from app.services.learning_engine import learning_engine
        from datetime import datetime, timezone

        approval = (await db.execute(
            select(ClassificationApproval).where(ClassificationApproval.id == approval_id)
        )).scalar_one_or_none()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")

        # User provides corrected classification
        corrected = {
            "section": body.get("section", approval.suggested_section),
            "side": body.get("side", approval.suggested_bs_side),
            "pl_line": body.get("pl_line", approval.suggested_pl_line),
            "sub": body.get("sub", approval.suggested_sub or ""),
            "normal_balance": body.get("normal_balance", "debit"),
        }

        approval.status = "modified"
        approval.user_choice_json = corrected
        approval.resolved_at = datetime.now(timezone.utc)
        await db.commit()

        # Save corrected version to LearningEngine
        learning_engine.record_correction(
            account_code=approval.account_code,
            original={"section": approval.suggested_section, "pl_line": approval.suggested_pl_line},
            corrected=corrected,
            source="user",
        )

        try:
            learning_engine.sync_to_kg()
        except Exception:
            pass

        return {"modified": True, "account_code": approval.account_code, "classification": corrected}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("modify_classification error: %s", e)
        return {"error": str(e)}


@router.post("/agents/classifications/bulk-approve")
async def bulk_approve_classifications(body: dict, db: AsyncSession = Depends(get_db)):
    """Approve all pending classifications for a dataset."""
    try:
        from app.models.all_models import ClassificationApproval
        from app.services.learning_engine import learning_engine
        from datetime import datetime, timezone

        dataset_id = body.get("dataset_id")
        query = select(ClassificationApproval).where(ClassificationApproval.status == "pending")
        if dataset_id:
            query = query.where(ClassificationApproval.dataset_id == dataset_id)

        result = await db.execute(query)
        approvals = result.scalars().all()

        count = 0
        for approval in approvals:
            approval.status = "approved"
            approval.resolved_at = datetime.now(timezone.utc)
            classification = {
                "section": approval.suggested_section,
                "side": approval.suggested_bs_side,
                "pl_line": approval.suggested_pl_line,
                "sub": approval.suggested_sub or "",
                "normal_balance": "credit" if approval.suggested_bs_side in ("liability", "equity", "revenue") else "debit",
            }
            learning_engine.record_correction(
                account_code=approval.account_code,
                original={},
                corrected=classification,
                source="user",
            )
            count += 1

        await db.commit()
        try:
            learning_engine.sync_to_kg()
        except Exception:
            pass

        return {"approved": count}
    except Exception as e:
        logger.error("bulk_approve error: %s", e)
        return {"error": str(e)}


# --- COA Upload --------------------------------------------------------

@router.post("/agents/coa/upload")
async def upload_coa(file: UploadFile = File(...)):
    """Upload a 1C Chart of Accounts file to update account classifications."""
    try:
        from app.services.onec_interpreter import onec_interpreter
        from app.services.knowledge_graph import knowledge_graph
        from app.services.vector_store import vector_store
        import tempfile, os

        raw_bytes = await file.read()
        filename = file.filename or "coa.xlsx"

        # Save to temp file for parsing
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        try:
            tree = onec_interpreter.parse_file(tmp_path)

            if not tree or tree.summary().get("total", 0) == 0:
                return {"error": "No accounts found in file", "success": False}

            # Merge into existing tree
            added = 0
            updated = 0
            existing_tree = onec_interpreter.tree
            for acct in tree.postable():
                existing = existing_tree.get(acct.code) if existing_tree else None
                if existing:
                    updated += 1
                else:
                    added += 1

            # Update the interpreter's tree
            onec_interpreter._tree = tree

            # Add to Knowledge Graph
            kg_entities = tree.to_kg_entities()
            for entity in kg_entities:
                knowledge_graph._add_entity(entity)

            # Index in VectorStore for semantic search
            try:
                docs = [{"content": f"{e.label_en} {e.description}", "metadata": e.properties}
                        for e in kg_entities if hasattr(e, 'label_en')]
            except Exception:
                pass

            logger.info("COA upload: %d added, %d updated, %d total from %s",
                        added, updated, len(tree.postable()), filename)

            return {
                "success": True,
                "filename": filename,
                "added": added,
                "updated": updated,
                "total_accounts": len(tree.postable()),
                "total_groups": len([a for a in tree._accounts.values() if a.is_group]),
                "summary": tree.summary(),
            }
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error("COA upload error: %s", e)
        return {"success": False, "error": str(e)}


# NOTE: /agents/feedback and /agents/audit/logs are handled by agent_monitoring.py


# [Consolidation and Connectors moved to standalone routers]

@router.get("/connectors")
async def list_connectors():
    """List all available connector types with their status and capabilities."""
    from app.services.data_connectors import connector_registry
    return connector_registry.list_available()


@router.post("/connectors/{connector_type}/test")
async def test_connector(connector_type: str, body: dict):
    """Test connection to a data source.

    Body: connector configuration (server_url, database, username, password, etc.)
    Returns: {connected: bool, message: str, details: {...}}
    """
    try:
        from app.services.data_connectors import (
            ConnectorConfig, connector_registry, CONNECTOR_CLASSES,
        )

        if connector_type not in CONNECTOR_CLASSES:
            return {
                "connected": False,
                "message": f"Unknown connector type: {connector_type}",
                "available_types": list(CONNECTOR_CLASSES.keys()),
            }

        config = ConnectorConfig(
            connector_type=connector_type,
            name=body.get("name", "test"),
            server_url=body.get("server_url", ""),
            database=body.get("database", ""),
            username=body.get("username", ""),
            password=body.get("password", ""),
            host=body.get("host", body.get("server_url", "")),
            system_number=body.get("system_number", "00"),
            client=body.get("client", "100"),
            bank_format=body.get("bank_format", "auto"),
            encoding=body.get("encoding", "utf-8"),
            extra=body.get("extra", {}),
        )

        connector = connector_registry.create_connector(config)
        result = await connector.test_connection()
        return result
    except Exception as e:
        return {"connected": False, "message": str(e), "details": {}}


@router.post("/connectors/{connector_type}/fetch")
async def fetch_connector_data(connector_type: str, body: dict):
    """Fetch data from a connector and optionally trigger the upload pipeline.

    Body:
      config: {server_url, database, username, password, ...}
      data_type: "trial_balance" | "journal_entries" | "chart_of_accounts" | "bank_statement"
      params: {period, date_from, date_to, csv_content, csv_path, ...}
      auto_ingest: bool -- if true, save fetched data to the FinAI data store

    Returns: ConnectorResult with records sample and metadata.
    """
    try:
        from app.services.data_connectors import (
            ConnectorConfig, connector_registry, CONNECTOR_CLASSES,
        )

        if connector_type not in CONNECTOR_CLASSES:
            return {
                "success": False,
                "error": f"Unknown connector type: {connector_type}",
                "available_types": list(CONNECTOR_CLASSES.keys()),
            }

        config_data = body.get("config", body)
        config = ConnectorConfig(
            connector_type=connector_type,
            name=config_data.get("name", "fetch"),
            server_url=config_data.get("server_url", ""),
            database=config_data.get("database", ""),
            username=config_data.get("username", ""),
            password=config_data.get("password", ""),
            host=config_data.get("host", config_data.get("server_url", "")),
            system_number=config_data.get("system_number", "00"),
            client=config_data.get("client", "100"),
            bank_format=config_data.get("bank_format", "auto"),
            encoding=config_data.get("encoding", "utf-8"),
            extra=config_data.get("extra", {}),
        )

        connector = connector_registry.create_connector(config)
        data_type = body.get("data_type", "trial_balance")
        fetch_params = body.get("params", {})

        result = await connector.fetch_data(data_type, fetch_params)

        # Auto-ingest into FinAI data store if requested
        if body.get("auto_ingest") and result.success and result.financials:
            try:
                from app.services.data_store import data_store
                from datetime import datetime, timezone

                company_name = fetch_params.get("company", config_data.get("name", "Imported Company"))
                period = result.period or datetime.now(timezone.utc).strftime("%Y-%m")

                # Find or create company
                existing = data_store.list_companies()
                company_id = None
                for ec in existing:
                    if company_name.lower() in ec["name"].lower() or ec["name"].lower() in company_name.lower():
                        company_id = ec["id"]
                        break
                if not company_id:
                    industry = fetch_params.get("industry", "fuel_distribution")
                    company_id = data_store.create_company(company_name, industry)

                _guarded_save_financials(
                    company_id, period, result.financials,
                    source_file=f"connector:{connector_type}",
                )
                result.metadata["ingested"] = True
                result.metadata["company_id"] = company_id
                result.metadata["period"] = period
                logger.info(
                    "Connector data auto-ingested: type=%s, company=%s, period=%s",
                    connector_type, company_name, period,
                )
            except Exception as ingest_err:
                result.warnings.append(f"Auto-ingest failed: {ingest_err}")
                result.metadata["ingested"] = False

        return result.to_dict()
    except Exception as e:
        logger.error("Connector fetch error: %s", e)
        return {"success": False, "error": str(e), "records_sample": []}


# ── Sub-Ledger System (AR / AP / Fixed Assets) ─────────────────────────────


@router.get("/subledger/ar/aging")
async def subledger_ar_aging():
    """AR aging report with current/1-30/31-60/61-90/90+ buckets."""
    try:
        from app.services.subledger import subledger_manager
        return subledger_manager.ar.get_aging_report()
    except Exception as e:
        return {"error": str(e)}


@router.get("/subledger/ap/aging")
async def subledger_ap_aging():
    """AP aging report with current/1-30/31-60/61-90/90+ buckets."""
    try:
        from app.services.subledger import subledger_manager
        return subledger_manager.ap.get_aging_report()
    except Exception as e:
        return {"error": str(e)}


@router.get("/subledger/ap/payment-schedule")
async def subledger_ap_payment_schedule(days_forward: int = 90):
    """Upcoming AP payments within the specified window."""
    try:
        from app.services.subledger import subledger_manager
        return subledger_manager.ap.get_payment_schedule(days_forward=days_forward)
    except Exception as e:
        return {"error": str(e)}


@router.get("/subledger/fa/register")
async def subledger_fa_register():
    """Full fixed asset register with accumulated depreciation and NBV."""
    try:
        from app.services.subledger import subledger_manager
        return subledger_manager.fa.get_register()
    except Exception as e:
        return {"error": str(e)}


@router.get("/subledger/fa/depreciation/{asset_id}")
async def subledger_fa_depreciation(asset_id: str):
    """Annual depreciation schedule for a specific asset."""
    try:
        from app.services.subledger import subledger_manager
        return subledger_manager.fa.get_depreciation_schedule(asset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    except Exception as e:
        return {"error": str(e)}


@router.post("/subledger/populate")
async def subledger_populate(body: dict):
    """Populate sub-ledgers from uploaded financials (PnL + balance sheet)."""
    try:
        from app.services.subledger import subledger_manager
        result = subledger_manager.populate_from_financials(
            pnl=body.get("pnl", {}),
            balance_sheet=body.get("balance_sheet", {}),
        )
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/subledger/reconciliation")
async def subledger_reconciliation(
    gl_receivables: float = 0.0,
    gl_payables: float = 0.0,
    gl_fixed_assets: float = 0.0,
    gl_accum_depr: float = 0.0,
):
    """Reconcile all sub-ledgers against GL control account totals."""
    try:
        from app.services.subledger import subledger_manager
        return subledger_manager.full_reconciliation(
            gl_receivables=gl_receivables,
            gl_payables=gl_payables,
            gl_fixed_assets=gl_fixed_assets,
            gl_accum_depr=gl_accum_depr,
        )
    except Exception as e:
        return {"error": str(e)}
