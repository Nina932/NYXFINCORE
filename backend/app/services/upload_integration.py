"""
FinAI Backend Integration — Universal Parser → smart-upload → DataStore

INSTALLATION:
1. Copy `socar_universal_parser.py` (NYX parser) to `backend/app/services/socar_universal_parser.py`
2. Copy this file to `backend/app/services/upload_integration.py`
3. In `backend/routers/agent.py`, replace the smart-upload endpoint body with:

    from app.services.upload_integration import handle_smart_upload
    
    @router.post("/agents/smart-upload")
    async def smart_upload(file: UploadFile = File(...)):
        return await handle_smart_upload(file, data_store, knowledge_graph)

That's it. The rest of the backend stays the same.
"""

import os
import json
import tempfile
import shutil
from datetime import datetime
from typing import Optional

# Import the universal parser
from app.services.socar_universal_parser import parse_nyx_excel, ParseResult


async def handle_smart_upload(file, data_store, knowledge_graph=None) -> dict:
    """
    Complete smart-upload handler.
    
    1. Save uploaded file to temp
    2. Parse with universal parser
    3. Store all financial data in DataStore
    4. Return complete result for frontend store
    """
    
    # ── Step 1: Save to temp file ──
    suffix = os.path.splitext(file.filename)[1] or '.xlsx'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Also save a permanent copy
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        permanent_path = os.path.join(upload_dir, file.filename)
        shutil.copy2(tmp_path, permanent_path)
        
        # ── Step 2: Parse ──
        result = parse_nyx_excel(tmp_path, file.filename)
        
        if not result.success:
            return {
                "success": False,
                "error": "Failed to parse file",
                "flags": [f.__dict__ for f in result.data_quality_flags],
                "sheets_found": result.sheets_available
            }
        
        # ── Step 3: Store in DataStore ──
        company_id = _store_company(data_store, result.company)
        period_id = _store_period(data_store, company_id, result.period)
        
        # Store P&L
        pnl = result.pnl
        _store_snapshot(data_store, period_id, 'revenue', pnl.revenue)
        _store_snapshot(data_store, period_id, 'revenue_wholesale', pnl.revenue_wholesale)
        _store_snapshot(data_store, period_id, 'revenue_retail', pnl.revenue_retail)
        _store_snapshot(data_store, period_id, 'revenue_other', pnl.revenue_other)
        _store_snapshot(data_store, period_id, 'cogs', pnl.cogs)
        _store_snapshot(data_store, period_id, 'cogs_wholesale', pnl.cogs_wholesale)
        _store_snapshot(data_store, period_id, 'cogs_retail', pnl.cogs_retail)
        _store_snapshot(data_store, period_id, 'gross_profit', pnl.gross_profit)
        _store_snapshot(data_store, period_id, 'selling_expenses', pnl.selling_expenses)
        _store_snapshot(data_store, period_id, 'admin_expenses', pnl.admin_expenses)
        _store_snapshot(data_store, period_id, 'ga_expenses', pnl.selling_expenses + pnl.admin_expenses)  # Legacy field
        _store_snapshot(data_store, period_id, 'total_opex', pnl.total_opex)
        _store_snapshot(data_store, period_id, 'ebitda', pnl.ebitda)
        _store_snapshot(data_store, period_id, 'depreciation', pnl.depreciation)
        _store_snapshot(data_store, period_id, 'amortization', pnl.amortization)
        _store_snapshot(data_store, period_id, 'ebit', pnl.ebit)
        _store_snapshot(data_store, period_id, 'non_operating_income', pnl.non_operating_income)
        _store_snapshot(data_store, period_id, 'non_operating_expense', pnl.non_operating_expense)
        _store_snapshot(data_store, period_id, 'interest_income', pnl.interest_income)
        _store_snapshot(data_store, period_id, 'interest_expense', pnl.interest_expense)
        _store_snapshot(data_store, period_id, 'fx_gain_loss', pnl.fx_gain_loss)
        _store_snapshot(data_store, period_id, 'profit_before_tax', pnl.profit_before_tax)
        _store_snapshot(data_store, period_id, 'net_profit', pnl.net_profit)
        
        # Store Revenue Breakdown
        rev_breakdown = [
            {"product": item.product, "gross": item.gross_amount, "vat": item.vat, 
             "net": item.net_revenue, "category": item.category}
            for item in result.revenue_breakdown
        ]
        _store_snapshot(data_store, period_id, 'revenue_breakdown', json.dumps(rev_breakdown, ensure_ascii=False))
        
        # Store COGS Breakdown
        cogs_breakdown = [
            {"product": item.product, "amount": item.amount, "category": item.category}
            for item in result.cogs_breakdown
        ]
        _store_snapshot(data_store, period_id, 'cogs_breakdown', json.dumps(cogs_breakdown, ensure_ascii=False))
        
        # Store Revenue by Category (for frontend charts)
        rev_by_cat = {}
        for item in result.revenue_breakdown:
            rev_by_cat[item.category] = rev_by_cat.get(item.category, 0) + item.net_revenue
        _store_snapshot(data_store, period_id, 'revenue_by_category', json.dumps(rev_by_cat, ensure_ascii=False))
        
        # Store Expense Detail
        if result.selling_expense_detail:
            sell_detail = {cat.name: cat.amount for cat in result.selling_expense_detail}
            _store_snapshot(data_store, period_id, 'selling_expense_detail', json.dumps(sell_detail, ensure_ascii=False))
        
        if result.admin_expense_detail:
            admin_detail = {cat.name: cat.amount for cat in result.admin_expense_detail}
            _store_snapshot(data_store, period_id, 'admin_expense_detail', json.dumps(admin_detail, ensure_ascii=False))
        
        # Store Balance Sheet
        bs = result.balance_sheet
        if bs.total_assets > 0:
            _store_snapshot(data_store, period_id, 'total_assets', bs.total_assets)
            _store_snapshot(data_store, period_id, 'non_current_assets', bs.non_current_assets)
            _store_snapshot(data_store, period_id, 'current_assets', bs.current_assets)
            _store_snapshot(data_store, period_id, 'cash', bs.cash)
            _store_snapshot(data_store, period_id, 'inventories', bs.inventories)
            _store_snapshot(data_store, period_id, 'trade_receivables', bs.trade_receivables)
            _store_snapshot(data_store, period_id, 'ppe_net', bs.ppe_net)
            _store_snapshot(data_store, period_id, 'ppe_cost', bs.ppe_cost)
            _store_snapshot(data_store, period_id, 'ppe_depreciation', bs.ppe_depreciation)
            _store_snapshot(data_store, period_id, 'total_liabilities', bs.total_liabilities)
            _store_snapshot(data_store, period_id, 'non_current_liabilities', bs.non_current_liabilities)
            _store_snapshot(data_store, period_id, 'current_liabilities', bs.current_liabilities)
            _store_snapshot(data_store, period_id, 'trade_payables', bs.trade_payables)
            _store_snapshot(data_store, period_id, 'long_term_loans', bs.long_term_loans)
            _store_snapshot(data_store, period_id, 'total_equity', bs.total_equity)
            _store_snapshot(data_store, period_id, 'share_capital', bs.share_capital)
            _store_snapshot(data_store, period_id, 'retained_earnings', bs.retained_earnings)
            
            # Store full BS as JSON for the dashboard
            bs_dict = result.balance_sheet.__dict__
            _store_snapshot(data_store, period_id, 'balance_sheet', json.dumps(bs_dict))
        
        # Store metadata
        _store_snapshot(data_store, period_id, 'file_type', result.file_type)
        _store_snapshot(data_store, period_id, 'data_quality_score', result.data_quality_score)
        _store_snapshot(data_store, period_id, 'sheets_used', json.dumps(result.sheets_used))
        _store_snapshot(data_store, period_id, 'upload_filename', file.filename)
        _store_snapshot(data_store, period_id, 'upload_timestamp', datetime.utcnow().isoformat())
        
        if result.data_quality_flags:
            flags_json = json.dumps([f.__dict__ for f in result.data_quality_flags], ensure_ascii=False)
            _store_snapshot(data_store, period_id, 'data_quality_flags', flags_json)
        
        # ── Step 4: Build frontend response ──
        # This matches what the frontend Zustand store expects from setFromUpload()
        response = {
            "success": True,
            "company": result.company,
            "period": result.period,
            "file_type": result.file_type,
            "data_quality_score": result.data_quality_score,
            "data_quality_flags": [f.__dict__ for f in result.data_quality_flags],
            "sheets_available": result.sheets_available,
            "sheets_used": result.sheets_used,
            
            # P&L for frontend store
            "pnl": {
                "revenue": pnl.revenue,
                "revenue_wholesale": pnl.revenue_wholesale,
                "revenue_retail": pnl.revenue_retail,
                "revenue_other": pnl.revenue_other,
                "cogs": pnl.cogs,
                "cogs_wholesale": pnl.cogs_wholesale,
                "cogs_retail": pnl.cogs_retail,
                "gross_profit": pnl.gross_profit,
                "selling_expenses": pnl.selling_expenses,
                "admin_expenses": pnl.admin_expenses,
                "ga_expenses": pnl.selling_expenses + pnl.admin_expenses,
                "total_opex": pnl.total_opex,
                "ebitda": pnl.ebitda,
                "depreciation": pnl.depreciation,
                "ebit": pnl.ebit,
                "non_operating_income": pnl.non_operating_income,
                "non_operating_expense": pnl.non_operating_expense,
                "interest_income": pnl.interest_income,
                "interest_expense": pnl.interest_expense,
                "fx_gain_loss": pnl.fx_gain_loss,
                "profit_before_tax": pnl.profit_before_tax,
                "net_profit": pnl.net_profit,
            },
            
            # Balance Sheet
            "balance_sheet": result.balance_sheet.__dict__ if bs.total_assets > 0 else {},
            
            # Revenue breakdown for charts
            "revenue_breakdown": rev_breakdown,
            "cogs_breakdown": cogs_breakdown,
            "revenue_by_category": rev_by_cat,
            
            # Expense detail
            "selling_expense_detail": {cat.name: cat.amount for cat in result.selling_expense_detail} if result.selling_expense_detail else {},
            "admin_expense_detail": {cat.name: cat.amount for cat in result.admin_expense_detail} if result.admin_expense_detail else {},
            
            # P&L line items for the structured P&L table
            "pl_line_items": _build_pl_line_items(pnl),
        }
        
        return response
        
    finally:
        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _build_pl_line_items(pnl) -> list:
    """Build structured P&L line items for the frontend table."""
    items = []
    
    def add(code, name, amount, level=0, is_total=False):
        items.append({
            "code": code,
            "name": name,
            "amount": amount,
            "level": level,
            "is_total": is_total
        })
    
    add("6110", "Revenue", pnl.revenue, 0, True)
    if pnl.revenue_wholesale:
        add("6110.W", "  Revenue Wholesale", pnl.revenue_wholesale, 1)
    if pnl.revenue_retail:
        add("6110.R", "  Revenue Retail", pnl.revenue_retail, 1)
    if pnl.revenue_other:
        add("6110.O", "  Other Revenue", pnl.revenue_other, 1)
    
    add("7110", "Cost of Goods Sold", -pnl.cogs, 0, True)
    if pnl.cogs_wholesale:
        add("7110.W", "  COGS Wholesale", -pnl.cogs_wholesale, 1)
    if pnl.cogs_retail:
        add("7110.R", "  COGS Retail", -pnl.cogs_retail, 1)
    
    add("GP", "Gross Profit", pnl.gross_profit, 0, True)
    
    if pnl.selling_expenses:
        add("7310", "Selling Expenses", -pnl.selling_expenses, 0)
    if pnl.admin_expenses:
        add("7410", "Administrative Expenses", -pnl.admin_expenses, 0)
    
    add("EBITDA", "EBITDA", pnl.ebitda, 0, True)
    
    if pnl.depreciation:
        add("DA", "Depreciation & Amortization", -pnl.depreciation, 0)
    
    add("EBIT", "EBIT", pnl.ebit, 0, True)
    
    if pnl.non_operating_income:
        add("8110", "Non-Operating Income", pnl.non_operating_income, 0)
    if pnl.non_operating_expense:
        add("8220", "Non-Operating Expenses", -pnl.non_operating_expense, 0)
    
    add("PBT", "Profit Before Tax", pnl.profit_before_tax, 0, True)
    add("NP", "Net Profit", pnl.net_profit, 0, True)
    
    return items


def _store_company(data_store, company_name: str) -> int:
    """Get or create company in the database."""
    import sqlite3
    conn = data_store.conn if hasattr(data_store, 'conn') else sqlite3.connect(data_store.db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM companies WHERE name = ?", (company_name,))
    row = cur.fetchone()
    if row:
        return row[0]
    
    cur.execute("INSERT INTO companies (name, industry) VALUES (?, ?)", 
                (company_name, 'fuel_distribution'))
    conn.commit()
    return cur.lastrowid


def _store_period(data_store, company_id: int, period: str) -> int:
    """Get or create period in the database."""
    import sqlite3
    conn = data_store.conn if hasattr(data_store, 'conn') else sqlite3.connect(data_store.db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM financial_periods WHERE company_id = ? AND period = ?", 
                (company_id, period))
    row = cur.fetchone()
    if row:
        period_id = row[0]
        # Delete old snapshots for this period (fresh data)
        cur.execute("DELETE FROM financial_snapshots WHERE period_id = ?", (period_id,))
        conn.commit()
        return period_id
    
    cur.execute("INSERT INTO financial_periods (company_id, period) VALUES (?, ?)", 
                (company_id, period))
    conn.commit()
    return cur.lastrowid


def _store_snapshot(data_store, period_id: int, key: str, value) -> None:
    """Store a financial data point."""
    import sqlite3
    import json
    
    conn = data_store.conn if hasattr(data_store, 'conn') else sqlite3.connect(data_store.db_path)
    cur = conn.cursor()
    
    # Serialize value
    if isinstance(value, (dict, list)):
        val_json = json.dumps(value, ensure_ascii=False)
    else:
        val_json = json.dumps(value)
    
    cur.execute("""
        INSERT OR REPLACE INTO financial_snapshots (period_id, key, value)
        VALUES (?, ?, ?)
    """, (period_id, key, val_json))
    conn.commit()
