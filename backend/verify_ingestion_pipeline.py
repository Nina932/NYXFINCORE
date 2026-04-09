import os
import sys
import json
import logging
from datetime import datetime

# Set up logging to console
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add backend to path so we can import app
sys.path.append(os.getcwd())

from app.config import settings
from app.services.socar_universal_parser import parse_nyx_excel
from app.services.ontology_write_guard import write_guard
from app.services.data_store import data_store

def verify_pipeline():
    logger.info("=== STARTING FORENSIC INGESTION VERIFICATION ===")
    
    # 1. Check Environment
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    logger.info(f"Secondary Store: {settings.FINAI_STORE_DB}")
    
    # 2. Pick a known good file for testing
    test_file = "uploads/January 2026.xlsx"
    if not os.path.exists(test_file):
        test_file = "uploads/Meridian_Group_March_2026_COMPLEX.xlsx"
    if not os.path.exists(test_file):
        logger.error("No valid XLSX files found for testing.")
        return
    
    logger.info(f"Testing with file: {test_file}")
    
    # 3. Parse File
    logger.info("Step 1: Parsing institutional Excel...")
    result = parse_nyx_excel(test_file, os.path.basename(test_file))
    
    if not result.success:
        logger.error(f"Parsing failed: {result.data_quality_flags}")
        # We continue to see what we got
    
    logger.info(f"Parsed Company: {result.company}")
    logger.info(f"Parsed Period:  {result.period}")
    logger.info(f"Quality Score:  {result.data_quality_score}/100")
    
    # Check for forensic flags
    critical_flags = [f for f in result.data_quality_flags if f.severity == 'CRITICAL']
    if critical_flags:
        logger.warning(f"CRITICAL Forensic Flags detected: {critical_flags}")
    else:
        logger.info("No CRITICAL forensic flags. Parser logic validated.")

    # 4. Verify P&L and Balance Sheet Integrity
    pnl = result.pnl
    bs = result.balance_sheet
    
    logger.info(f"Revenue: {pnl.revenue:,.2f} GEL")
    logger.info(f"Net Profit: {pnl.net_profit:,.2f} GEL")
    
    if bs.total_assets > 0:
        logger.info(f"Total Assets: {bs.total_assets:,.2f}")
        logger.info(f"Total Liab+Equity: {bs.total_liabilities + bs.total_equity:,.2f}")
        diff = abs(bs.total_assets - (bs.total_liabilities + bs.total_equity))
        if diff < 1.0:
            logger.info("FORENSIC CHECK PASSED: Assets = Liabilities + Equity (Balance Balanced)")
        else:
            logger.error(f"FORENSIC CHECK FAILED: Balance discrepancy = {diff:,.2f}")
    else:
        logger.warning("No Balance Sheet data found for forensic check.")

    # 5. Simulate Database Injection via OntologyWriteGuard
    logger.info("Step 2: Simulating Database Injection via OntologyWriteGuard...")
    
    # Prepare data for injection
    financials = result.to_dict()
    # Flattend P&L for snapshots
    flat_data = financials.get('pnl', {})
    # Add BS fields prefixed with bs_
    for k, v in financials.get('balance_sheet', {}).items():
        flat_data[f"bs_{k}"] = v
        
    # Inject
    company_name = "Forensic Verification Corp"
    company_id = data_store.create_company(company_name, industry="forensic_test")
    period = result.period or datetime.now().strftime("%Y-%m")
    
    logger.info(f"Injecting into Company ID: {company_id} for Period: {period}")
    write_result = write_guard.write_financials(
        company_id=company_id,
        period=period,
        financials=flat_data,
        user="verification_script"
    )
    
    if write_result.get("success"):
        logger.info(f"SUCCESS: Data successfully injected. Audit ID: {write_result.get('audit_id')}")
    else:
        logger.error(f"INJECTION FAILED: {write_result.get('errors') or write_result.get('error')}")
        return

    # 6. Verify Persistence in DataStore
    logger.info("Step 3: Verifying persistence in DataStore...")
    persisted_data = data_store.get_financials(company_id, period)
    if persisted_data:
        logger.info(f"Persistence validated. Retrieved {len(persisted_data)} fields from DataStore.")
        if "revenue" in persisted_data:
            logger.info(f"Verified field 'revenue' = {persisted_data['revenue']:,.2f}")
    else:
        logger.error("Verification failed: No data found in DataStore after injection.")

    logger.info("=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    verify_pipeline()
