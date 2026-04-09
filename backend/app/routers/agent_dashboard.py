"""
FinAI Agent Dashboard Sub-Router
==================================
Extracted from agent.py -- handles dashboard, analytics, sensitivity, strategy.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from app.database import get_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix -- parent adds /api/agent


# ── Dashboard: single endpoint for frontend ──────────────────────────────

@router.get("/agents/dashboard")
async def get_dashboard(period: str = None, db: AsyncSession = Depends(get_db)):
    """Return full dashboard data. Priority: pl_comparison (entity tables) -> GL journals -> data_store."""

    # ── PRIORITY 1: pl_comparison service (same source as P&L page) ──
    try:
        from app.services.v2.pl_comparison import pl_comparison
        from app.models.all_models import Dataset
        from sqlalchemy import select

        # Find best dataset (prefer reasonable size, fall back to any)
        ds = (await db.execute(
            select(Dataset).where(Dataset.record_count > 0, Dataset.record_count < 10000)
            .order_by(Dataset.id.desc()).limit(1)
        )).scalar_one_or_none()
        if not ds:
            ds = (await db.execute(
                select(Dataset).where(Dataset.record_count > 0)
                .order_by(Dataset.id.desc()).limit(1)
            )).scalar_one_or_none()

        if ds:
            pl_data = await pl_comparison.full_pl(ds.id, None, db)
            summary = pl_data.get("summary", {})

            # Build revenue/COGS breakdowns from revenue_comparison
            revenue_breakdown = []
            cogs_breakdown = []
            rev_by_category = {}
            try:
                rev_comp = await pl_comparison.revenue_comparison(ds.id, None, db)
                for r in rev_comp.get("rows", []):
                    revenue_breakdown.append({
                        "product": r.get("product", ""),
                        "category": r.get("category", ""),
                        "net_revenue": r.get("actual_net", 0),
                    })
                    cat = r.get("category", "Other") or "Other"
                    rev_by_category[cat] = rev_by_category.get(cat, 0) + r.get("actual_net", 0)
            except Exception:
                pass

            # Build P&L line items from pl_comparison rows
            pl_line_items = []
            for row in pl_data.get("rows", []):
                pl_line_items.append({
                    "label": row.get("label", ""),
                    "amount": row.get("actual", 0),
                    "level": row.get("level", 0),
                    "is_total": row.get("bold", False),
                })

            # Compute real health score via diagnosis engine
            _intelligence = None
            try:
                from app.services.diagnosis_engine import diagnosis_engine
                current_fin = {
                    "revenue": summary.get("revenue", 0),
                    "cogs": summary.get("cogs", 0),
                    "gross_profit": summary.get("gross_profit", 0),
                    "ebitda": summary.get("ebitda", 0),
                    "net_profit": summary.get("net_profit", 0),
                }
                diag_report = diagnosis_engine.run_full_diagnosis(current_financials=current_fin)
                _intelligence = {
                    "health_summary": {
                        "health_score": diag_report.health_score,
                        "health_grade": diag_report.health_grade,
                    },
                    "diagnoses_count": len(diag_report.diagnoses),
                    "signal_summary": diag_report.signal_summary,
                }
            except Exception as e:
                logger.debug("Diagnosis engine failed in dashboard: %s", e)

            # ── Sync financials into ontology KPI objects ──
            _ontology_sync = None
            try:
                from app.services.v2.ontology_calculator import ontology_calculator
                _ontology_sync = await ontology_calculator.sync_to_ontology(db)
                logger.debug("Ontology sync: %d KPIs updated", _ontology_sync.get("synced", 0))
            except Exception as e:
                logger.debug("Ontology sync failed in dashboard: %s", e)

            logger.info("Dashboard served from pl_comparison (dataset_id=%d, revenue=%.0f)", ds.id, summary.get("revenue", 0))
            return {
                "empty": False,
                "company": {"id": 0, "name": pl_data.get("company") or ds.company or settings.COMPANY_NAME},
                "period": pl_data.get("period") or ds.period or "Unknown",
                "periods_available": [pl_data.get("period") or ds.period] if (pl_data.get("period") or ds.period) else [],
                "dataset_id": ds.id,
                "financials": {
                    "revenue": summary.get("revenue", 0),
                    "cogs": summary.get("cogs", 0),
                    "gross_profit": summary.get("gross_profit", 0),
                    "ga_expenses": summary.get("ga_expenses", 0),
                    "ebitda": summary.get("ebitda", 0),
                    "net_profit": summary.get("net_profit", 0),
                },
                "revenue_breakdown": revenue_breakdown[:50],
                "cogs_breakdown": cogs_breakdown[:50],
                "pl_line_items": pl_line_items,
                "revenue_by_category": rev_by_category,
                "pnl": {
                    "revenue": summary.get("revenue", 0),
                    "cogs": summary.get("cogs", 0),
                    "gross_profit": summary.get("gross_profit", 0),
                    "ebitda": summary.get("ebitda", 0),
                    "net_profit": summary.get("net_profit", 0),
                },
                "balance_sheet": {},
                "intelligence": _intelligence,
                "ontology_sync": _ontology_sync,
                "data_source": {"source": "pl_comparison", "dataset_id": ds.id},
            }
    except Exception as e:
        logger.debug("pl_comparison dashboard failed: %s", e)

    # DEPRECATED: data_store fallback (Priority 2/3 below). All financial reporting now uses pl_comparison.
    # Kept for backward compatibility with legacy data only.

    # ── PRIORITY 2: GL Reporting from posted journal entries ──
    try:
        from app.services.v2.gl_reporting import gl_reporting
        gl_data = await gl_reporting.dashboard_from_gl(period, db)
        if gl_data:
            logger.info("Dashboard served from GL (%d periods available)", len(gl_data.get("periods_available", [])))
            return gl_data
    except Exception as e:
        logger.debug("GL reporting not available: %s", e)

    # ── PRIORITY 3: data_store (legacy, for backward compatibility) ──
    try:
        from app.services.data_store import data_store

        companies = data_store.list_companies()
        if not companies:
            # ── PRIORITY 4: DB Fallback (income_statement builder) ──
            from app.models.all_models import Dataset, RevenueItem, COGSItem, GAExpenseItem
            from sqlalchemy import select

            ds = (await db.execute(
                select(Dataset).where(Dataset.record_count > 0).order_by(Dataset.id.desc()).limit(1)
            )).scalar_one_or_none()
            if not ds:
                return {"empty": True, "message": "No data uploaded yet. Upload a financial Excel file to begin."}

            rev_items = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == ds.id))).scalars().all()
            cogs_items = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == ds.id))).scalars().all()
            ga_items = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds.id))).scalars().all()

            from app.services.income_statement import build_income_statement
            stmt = build_income_statement(rev_items, cogs_items, ga_items, ds.period or "Unknown", ds.currency or "GEL")

            def _f(v):
                try: return float(v) if v else 0
                except: return 0

            return {
                "empty": False,
                "company": {"id": 0, "name": ds.company or settings.COMPANY_NAME},
                "period": ds.period or "Unknown",
                "periods_available": [ds.period] if ds.period else [],
                "dataset_id": ds.id,
                "financials": {},
                "revenue_breakdown": [{"product": p.get("product_en", p.get("product", "")),
                    "category": p.get("category", ""), "net_revenue": _f(p.get("net", 0))}
                    for p in stmt.revenue_by_product],
                "cogs_breakdown": [{"product": p.get("product_en", p.get("product", "")),
                    "category": p.get("category", ""), "amount": _f(p.get("total_cogs", 0))}
                    for p in stmt.cogs_by_product],
                "pl_line_items": [],
                "revenue_by_category": {},
                "pnl": {
                    "revenue": _f(stmt.total_revenue), "cogs": _f(stmt.total_cogs),
                    "gross_profit": _f(stmt.total_gross_profit), "ga_expenses": _f(stmt.ga_expenses),
                    "ebitda": _f(stmt.ebitda), "depreciation": _f(stmt.da_expenses),
                    "ebit": _f(stmt.ebit), "net_profit": _f(stmt.net_profit),
                },
                "balance_sheet": {},
                "intelligence": None,
            }

        # Find company with the RICHEST data (has orchestrator result + BS data)
        company = companies[-1]
        best_score = -1
        for c in reversed(companies):
            periods = data_store.get_all_periods(c["id"])
            if not periods:
                continue
            score = len(periods)
            fin = data_store.get_financials(c["id"], periods[-1])
            if fin:
                score += len([k for k in fin if k.startswith("bs_")]) * 10
            orch = data_store.get_last_orchestrator_result(c["id"])
            if orch:
                score += 100
            if score > best_score:
                best_score = score
                company = c
        company_id = company["id"]

        # Get all periods for this company
        periods = data_store.get_all_periods(company_id)
        if not periods:
            return {"empty": True, "message": "No financial data found. Upload a file."}

        # Use requested period or fall back to latest
        if period and period in periods:
            latest_period = period
        else:
            latest_period = periods[-1]

        # Get financials
        financials = data_store.get_financials(company_id, latest_period)

        # Back-calculate COGS if missing but Revenue and GP exist
        _rev = financials.get("revenue", 0)
        _gp = financials.get("gross_profit", 0)
        if _rev > 0 and _gp > 0 and not financials.get("cogs"):
            financials["cogs"] = _rev - _gp

        # Get last orchestrator result (v3 or legacy) -- unwrap DB record
        _raw_orch = data_store.get_last_orchestrator_result(company_id)
        orch_result = None
        if isinstance(_raw_orch, str):
            try:
                import json as _json2
                _raw_orch = _json2.loads(_raw_orch)
            except Exception:
                _raw_orch = None
        if isinstance(_raw_orch, dict):
            # DB returns {id, company_id, result, ...} -- unwrap the 'result' field
            inner = _raw_orch.get("result")
            if isinstance(inner, str):
                try:
                    orch_result = _json2.loads(inner)
                except Exception:
                    orch_result = _raw_orch
            elif isinstance(inner, dict):
                orch_result = inner
            elif _raw_orch.get("version") == "v3":
                orch_result = _raw_orch
            else:
                orch_result = _raw_orch

        # Get upload history
        history = data_store.get_upload_history(company_id) if hasattr(data_store, 'get_upload_history') else []

        # Load breakdowns from last smart-upload result if available
        revenue_breakdown = []
        cogs_breakdown = []
        try:
            import json as _json
            upload_hist = data_store.get_upload_history(company_id) if hasattr(data_store, 'get_upload_history') else []
            if upload_hist:
                # Find the NEWEST upload that has result_json data
                for _uh in (upload_hist if isinstance(upload_hist, list) else [upload_hist]):
                    rj = _uh.get("result_json") if isinstance(_uh, dict) else None
                    if rj and len(str(rj)) > 10:
                        result_json = rj
                        break
                else:
                    result_json = None
                if result_json:
                    parsed = _json.loads(result_json) if isinstance(result_json, str) else result_json
                    revenue_breakdown = parsed.get("revenue_breakdown", [])
                    cogs_breakdown = parsed.get("cogs_breakdown", [])
                    stored_pl_items = parsed.get("pl_line_items", [])
        except Exception:
            stored_pl_items = []

        # Build revenue category summary
        rev_by_category = {}
        for item in revenue_breakdown:
            cat = item.get("category", "Other")
            rev_by_category[cat] = rev_by_category.get(cat, 0) + item.get("net_revenue", 0)

        # If no breakdowns from upload history, generate from stored financial fields
        if not revenue_breakdown and financials.get("revenue", 0) > 0:
            rev = financials.get("revenue", 0)
            rev_w = financials.get("revenue_wholesale", 0)
            rev_r = financials.get("revenue_retail", 0)
            rev_o = financials.get("revenue_other", 0)
            if rev_w > 0:
                revenue_breakdown.append({"product": "Wholesale Revenue", "category": "Wholesale", "net_revenue": rev_w, "gross_revenue": rev_w})
            if rev_r > 0:
                revenue_breakdown.append({"product": "Retail Revenue", "category": "Retail", "net_revenue": rev_r, "gross_revenue": rev_r})
            if rev_o > 0:
                revenue_breakdown.append({"product": "Other Revenue", "category": "Other", "net_revenue": rev_o, "gross_revenue": rev_o})
            if not revenue_breakdown and rev > 0:
                revenue_breakdown.append({"product": "Total Revenue", "category": "Revenue", "net_revenue": rev, "gross_revenue": rev})
            rev_by_category = {}
            for item in revenue_breakdown:
                cat = item.get("category", "Other")
                rev_by_category[cat] = rev_by_category.get(cat, 0) + item.get("net_revenue", 0)

        if not cogs_breakdown and financials.get("cogs", 0) > 0:
            cogs_breakdown.append({"product": "Cost of Goods Sold", "category": "COGS", "amount": financials.get("cogs", 0)})

        # Build P&L line items from financials
        pl_line_items = []
        if financials.get("revenue", 0) > 0:
            _rev = financials.get("revenue", 0)
            def _add_pl(label, val, level=0, is_total=False):
                if val != 0 or is_total:
                    pl_line_items.append({"label": label, "amount": val, "level": level, "is_total": is_total})
            _add_pl("Revenue", _rev, 0, True)
            if financials.get("revenue_wholesale"): _add_pl("  Wholesale", financials["revenue_wholesale"], 1)
            if financials.get("revenue_retail"): _add_pl("  Retail", financials["revenue_retail"], 1)
            _add_pl("COGS", -(financials.get("cogs", 0)), 0)
            _add_pl("Gross Profit", financials.get("gross_profit", 0), 0, True)
            if financials.get("selling_expenses"): _add_pl("Selling Expenses", -(financials["selling_expenses"]), 0)
            if financials.get("admin_expenses"): _add_pl("Admin Expenses", -(financials["admin_expenses"]), 0)
            if financials.get("ebitda") is not None: _add_pl("EBITDA", financials["ebitda"], 0, True)
            if financials.get("depreciation"): _add_pl("D&A", -(financials["depreciation"]), 0)
            if financials.get("ebit") is not None: _add_pl("EBIT", financials["ebit"], 0, True)
            if financials.get("other_income"): _add_pl("Other Income", financials["other_income"], 0)
            if financials.get("other_expense"): _add_pl("Other Expense", -(financials["other_expense"]), 0)
            _add_pl("Net Profit", financials.get("net_profit", 0), 0, True)

        # ── Auto-sync to Ontology + Warehouse (Palantir-style pipeline) ──
        try:
            from app.services.ontology_engine import ontology_registry
            ontology_registry.sync_financial_data(
                company_name=company.get("name", "Unknown"),
                period=latest_period,
                pnl={k: v for k, v in financials.items() if not k.startswith("bs_")},
                balance_sheet={k: v for k, v in financials.items() if k.startswith("bs_") or k in ("cash", "receivables", "inventory", "total_assets", "total_liabilities", "total_equity")},
            )
        except Exception:
            pass
        try:
            from app.services.warehouse import warehouse as _wh
            if _wh._initialized:
                _wh.sync_from_sqlite()
        except Exception:
            pass

        # ── Proactive Intelligence Layer ──
        _intelligence = None
        try:
            from app.services.proactive_intelligence import proactive_intelligence as _pi
            _bs_data = {k: v for k, v in financials.items() if k.startswith("bs_") or k in (
                "cash", "receivables", "inventory", "total_current_assets",
                "fixed_assets_net", "total_assets", "current_liabilities",
                "long_term_debt", "total_liabilities", "total_equity",
            )}
            # Try to get previous period financials
            _prev_fin = None
            if len(periods) >= 2:
                _prev_period = periods[-2] if latest_period == periods[-1] else None
                if _prev_period:
                    _prev_fin = data_store.get_financials(company_id, _prev_period)
            _intelligence = _pi.analyze(financials, _bs_data, _prev_fin)
        except Exception:
            pass

        return {
            "empty": False,
            "company": {"id": company_id, "name": company.get("name", "Unknown"), "industry": company.get("industry", "")},
            "period": latest_period,
            "periods_available": periods,
            "financials": financials,
            "orchestrator": orch_result,
            "upload_history": history if isinstance(history, list) else [],
            "revenue_breakdown": revenue_breakdown[:50],
            "cogs_breakdown": cogs_breakdown[:50],
            "pl_line_items": stored_pl_items if stored_pl_items and len(stored_pl_items) > len(pl_line_items) else pl_line_items,
            "revenue_by_category": rev_by_category,
            "pnl": {
                "revenue": financials.get("revenue", 0),
                "revenue_wholesale": financials.get("revenue_wholesale", 0),
                "revenue_retail": financials.get("revenue_retail", 0),
                "revenue_other": financials.get("revenue_other", 0),
                "cogs": financials.get("cogs", 0),
                "gross_profit": financials.get("gross_profit", 0),
                "selling_expenses": financials.get("selling_expenses", 0),
                "admin_expenses": financials.get("admin_expenses", 0),
                "ga_expenses": financials.get("ga_expenses", 0),
                "labour_costs": financials.get("labour_costs", 0),
                "ebitda": financials.get("ebitda", 0),
                "depreciation": financials.get("depreciation", 0),
                "ebit": financials.get("ebit", 0),
                "finance_income": financials.get("finance_income", 0),
                "finance_expense": financials.get("finance_expense", 0),
                "other_income": financials.get("other_income", 0),
                "other_expense": financials.get("other_expense", 0),
                "non_operating_income": financials.get("non_operating_income", 0),
                "non_operating_expense": financials.get("non_operating_expense", 0),
                "profit_before_tax": financials.get("profit_before_tax", 0),
                "tax_expense": financials.get("tax_expense", 0),
                "net_profit": financials.get("net_profit", 0),
            },
            "balance_sheet": {
                **{k[3:]: v for k, v in financials.items() if k.startswith("bs_")},
                **{k: v for k, v in financials.items() if k in (
                    "cash", "receivables", "inventory", "total_current_assets",
                    "fixed_assets_net", "total_assets", "total_current_liabilities",
                    "long_term_debt", "total_liabilities", "total_equity",
                    "current_ratio", "debt_to_equity", "working_capital",
                )},
            },
            "intelligence": _intelligence,
            "data_source": _build_data_source_info(
                revenue_breakdown, cogs_breakdown, history, financials
            ),
            "aggregation_hint": {
                "total_periods": len(periods),
                "available_annual": len(periods) >= 12,
                "available_quarters": [
                    f"Q{q}" for q in range(1, 5)
                    if any(p.endswith(f"-{m:02d}") for p in periods for m in range((q-1)*3+1, q*3+1))
                ],
            },
        }
    except Exception as e:
        return {"empty": True, "error": str(e)}


def _build_data_source_info(
    revenue_breakdown: list,
    cogs_breakdown: list,
    upload_history: list,
    financials: dict,
) -> dict:
    """Build data_source metadata so the frontend knows what detail is available."""
    has_product_breakdown = len(revenue_breakdown) > 2
    has_cogs_breakdown = len(cogs_breakdown) > 2

    # Determine source type from upload history result_json or fallback heuristics
    source_type = "unknown"
    sheets_parsed: list[str] = []
    try:
        import json as _dsj
        if isinstance(upload_history, list):
            for uh in upload_history:
                rj = uh.get("result_json") if isinstance(uh, dict) else None
                if rj and len(str(rj)) > 10:
                    parsed = _dsj.loads(rj) if isinstance(rj, str) else rj
                    dt = parsed.get("doc_type", "")
                    if dt:
                        source_type = dt
                    sp = parsed.get("sheets_parsed") or parsed.get("parsed_sheets") or []
                    if sp:
                        sheets_parsed = sp if isinstance(sp, list) else [sp]
                    break
    except Exception:
        pass

    # Fallback: if we still don't know, infer from data richness
    if source_type == "unknown":
        if has_product_breakdown:
            source_type = "mr_report"
        elif financials.get("revenue", 0) > 0:
            source_type = "trial_balance"

    message = None
    if not has_product_breakdown:
        message = (
            "This data was loaded from a Trial Balance which shows account-level totals only. "
            "Upload a file with Revenue Breakdown / COGS Breakdown sheets for product-level detail."
        )

    return {
        "type": source_type,
        "has_product_breakdown": has_product_breakdown,
        "has_cogs_breakdown": has_cogs_breakdown,
        "message": message,
        "sheets_parsed": sheets_parsed,
    }


# ── Period Comparison API ─────────────────────────────────────────────────

@router.get("/agents/dashboard/compare")
async def compare_periods(current: str = None, previous: str = None):
    """Compare two periods side-by-side. Returns current + previous financials with variances."""
    try:
        from app.services.data_store import data_store

        companies = data_store.list_companies()
        if not companies:
            return {"error": "No data available"}

        company = companies[-1]
        company_id = company["id"]
        periods = data_store.get_all_periods(company_id)
        if not periods:
            return {"error": "No periods available"}

        # Determine periods
        curr_period = current if current and current in periods else periods[-1]
        prev_period = previous
        if not prev_period:
            # Auto-detect previous period
            idx = periods.index(curr_period) if curr_period in periods else len(periods) - 1
            prev_period = periods[idx - 1] if idx > 0 else None

        curr_data = data_store.get_financials(company_id, curr_period)
        prev_data = data_store.get_financials(company_id, prev_period) if prev_period else {}

        # Compute variances
        variances = {}
        key_metrics = [
            "revenue", "cogs", "gross_profit", "selling_expenses", "admin_expenses",
            "ebitda", "depreciation", "ebit", "net_profit",
            "total_assets", "total_liabilities", "total_equity", "cash",
        ]
        for key in key_metrics:
            curr_val = curr_data.get(key, 0) or 0
            prev_val = prev_data.get(key, 0) or 0
            change = curr_val - prev_val
            pct_change = (change / abs(prev_val) * 100) if prev_val != 0 else 0
            variances[key] = {
                "current": curr_val,
                "previous": prev_val,
                "change": change,
                "pct_change": round(pct_change, 1),
            }

        return {
            "company": company.get("name", ""),
            "current_period": curr_period,
            "previous_period": prev_period,
            "periods_available": periods,
            "current": curr_data,
            "previous": prev_data,
            "variances": variances,
        }
    except Exception as e:
        logger.error("compare_periods error: %s", e)
        return {"error": str(e)}


# ── Phase L: Financial Analogy Base ───────────────────────────────────────

@router.post("/agents/analogy/search")
async def analogy_search(body: dict):
    """Phase L: Find analogous historical financial situations."""
    try:
        from app.services.analogy_base import analogy_base
        result = analogy_base.get_analogous_strategies(
            body.get("financials", {}),
            top_k=body.get("top_k", 5),
            industry=body.get("industry", None),
        )
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/analogy/ingest")
async def analogy_ingest(body: dict):
    """Phase L: Ingest a real financial snapshot into the analogy base."""
    try:
        from app.services.analogy_base import analogy_base
        snapshot = analogy_base.ingest_snapshot(
            raw_financials=body.get("financials", {}),
            industry=body.get("industry", "fuel_distribution"),
            period=body.get("period", ""),
            outcome_metadata=body.get("outcome", None),
        )
        return snapshot.to_dict()
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/analogy/summary")
async def analogy_summary():
    """Phase L: Get analogy base statistics."""
    try:
        from app.services.analogy_base import analogy_base
        if not analogy_base._initialized:
            analogy_base.initialize()
        return analogy_base.summary()
    except Exception as e:
        return {"error": str(e)}


# ── Phase J: Strategy Engine + Sensitivity + KPI Watcher ──────────────────

@router.post("/agents/sensitivity/analyze")
async def sensitivity_analyze(body: dict):
    """Phase J: One-at-a-time sensitivity analysis (tornado chart data)."""
    try:
        from app.services.sensitivity_analyzer import sensitivity_analyzer
        financials = body.get("financials") or body
        report = sensitivity_analyzer.analyze(financials)
        result = report.to_dict()
        # Generate smart summary
        most_sens = report.most_sensitive_variable.replace("_", " ").title() if report.most_sensitive_variable else "Unknown"
        if report.bands:
            top_band = report.bands[0]
            base_np = report.base_net_profit if report.base_net_profit != 0 else 1
            impact_pct = abs(top_band.swing / 2 / base_np * 100) if base_np != 0 else 0
            summary = f"{most_sens} is the most sensitive variable. A 10% change would affect net profit by {impact_pct:.0f}%."
        else:
            summary = "Insufficient data for sensitivity analysis."
        result["summary"] = summary
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/sensitivity/multi-variable")
async def sensitivity_multi_var(body: dict):
    """Phase J: Multi-variable simultaneous simulation."""
    try:
        from app.services.sensitivity_analyzer import multi_var_simulator
        result = multi_var_simulator.simulate(
            body.get("financials", {}),
            body.get("changes", {}),
            body.get("name", "Multi-variable scenario"),
        )
        return result.to_dict()
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/sensitivity/monte-carlo")
async def sensitivity_monte_carlo(body: dict):
    """Phase J: Standalone Monte Carlo simulation on arbitrary P&L."""
    try:
        from app.services.sensitivity_analyzer import scenario_monte_carlo
        ranges = body.get("variable_ranges", None)
        # Convert list values to tuples if needed
        if ranges:
            ranges = {k: tuple(v) if isinstance(v, list) else v for k, v in ranges.items()}
        result = scenario_monte_carlo.simulate(
            body.get("financials", {}),
            variable_ranges=ranges,
            iterations=body.get("iterations", 2000),
            seed=body.get("seed", 42),
        )
        return result.to_dict()
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/strategy/generate")
async def strategy_generate(body: dict):
    """Phase J: Generate multi-phase strategy with time projection."""
    try:
        from app.services.decision_engine import decision_engine
        from app.services.diagnosis_engine import diagnosis_engine
        from app.services.strategy_engine import strategic_engine

        financials = body.get("current", body.get("financials", {}))
        previous = body.get("previous", None)
        months = body.get("months", 12)

        diag = diagnosis_engine.run_full_diagnosis(
            current_financials=financials,
            previous_financials=previous,
            balance_sheet=body.get("balance_sheet"),
            industry_id=body.get("industry", "fuel_distribution"),
        )
        dec_report = decision_engine.generate_decision_report(diag, financials)
        result = strategic_engine.generate_strategy(
            dec_report.top_actions, diag.health_score, financials, months,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/strategy/last")
async def strategy_last():
    """Phase J: Get the most recently generated strategy."""
    try:
        from app.services.strategy_engine import strategic_engine
        s = strategic_engine.get_last_strategy()
        if s:
            return s.to_dict()
        return {"message": "No strategy generated yet."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/strategy/learning")
async def strategy_learning():
    """Phase J: Get strategy learning summary (closed decision loop)."""
    try:
        from app.services.strategy_engine import strategic_engine
        return strategic_engine.learner.generate_learning_summary()
    except Exception as e:
        return {"error": str(e)}


@router.get("/agents/monitoring/kpi")
async def monitoring_kpi(body: dict = {}):
    """Phase J: Evaluate KPIs against targets."""
    try:
        from app.services.monitoring_engine import monitoring_engine
        # Accept financials from query params or use empty dict
        financials = body if body else {}
        statuses = monitoring_engine.kpi_watcher.evaluate(financials)
        return {
            "kpi_statuses": [s.to_dict() for s in statuses],
            "targets": [t.to_dict() for t in monitoring_engine.kpi_watcher.get_targets()],
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/monitoring/kpi/evaluate")
async def monitoring_kpi_evaluate(body: dict):
    """Phase J: Evaluate KPIs with provided financials."""
    try:
        from app.services.monitoring_engine import monitoring_engine
        statuses = monitoring_engine.kpi_watcher.evaluate(body.get("financials", {}))
        status_dicts = [s.to_dict() for s in statuses]
        # Generate smart summary
        total = len(statuses)
        below = [s for s in statuses if s.status in ("missed", "at_risk")]
        below_count = len(below)
        summary_parts = []
        if total > 0:
            summary_parts.append(f"{below_count} of {total} KPIs are below target.")
        for s in below[:2]:
            summary_parts.append(f"{s.metric.replace('_', ' ').title()} ({s.actual:.1f}) is below target ({s.target:.1f}).")
        summary = " ".join(summary_parts) if summary_parts else "All KPIs are on track."
        return {"kpi_statuses": status_dicts, "summary": summary}
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/monitoring/cash-runway")
async def monitoring_cash_runway(body: dict):
    """Phase J: Calculate cash runway from current financials."""
    try:
        from app.services.monitoring_engine import monitoring_engine
        runway = monitoring_engine.cash_runway.calculate(
            cash_balance=body.get("cash_balance", 0),
            monthly_revenue=body.get("monthly_revenue", 0),
            monthly_expenses=body.get("monthly_expenses", 0),
        )
        result = runway.to_dict()
        # Generate smart summary
        months = runway.runway_months
        if months == float("inf") or months > 120:
            summary = "Cash runway is effectively unlimited — the company is cash-flow positive."
        else:
            import math
            quarter = math.ceil(months / 3)
            year_part = 2025 + (quarter - 1) // 4
            q_in_year = ((quarter - 1) % 4) + 1
            summary = f"Cash runway is {months:.0f} months. At current burn rate, action needed by Q{q_in_year} {year_part}."
        result["summary"] = summary
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/agents/monitoring/expense-spikes")
async def monitoring_expense_spikes(body: dict):
    """Phase J: Detect month-over-month expense spikes."""
    try:
        from app.services.monitoring_engine import monitoring_engine
        spikes = monitoring_engine.expense_spike.detect(
            current_expenses=body.get("current", {}),
            previous_expenses=body.get("previous", {}),
            spike_threshold_pct=body.get("threshold_pct", 15.0),
        )
        return {"spikes": spikes, "count": len(spikes)}
    except Exception as e:
        return {"error": str(e)}
