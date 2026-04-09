"""
FinAI OS — Data Warehouse (DuckDB)
===================================
Analytical warehouse layer. Syncs from SQLite OLTP → DuckDB OLAP.
Supports virtual tables, Parquet export, federated queries.

Usage:
    from app.services.warehouse import warehouse
    warehouse.initialize()
    warehouse.sync_from_sqlite()
    results = warehouse.execute("SELECT * FROM dw_transactions LIMIT 10")
"""

import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


class FinAIWarehouse:
    """DuckDB-backed analytical warehouse for financial data."""

    def __init__(self, db_path: str = "data/finai_warehouse.duckdb"):
        self._db_path = db_path
        self._conn = None
        self._initialized = False
        self._sync_counts: Dict[str, int] = {}

    def initialize(self) -> bool:
        if self._initialized and self._conn:
            return True
        if not HAS_DUCKDB:
            logger.warning("DuckDB not available")
            return False
        os.makedirs(os.path.dirname(self._db_path) or "data", exist_ok=True)
        # Clean stale lock files
        for ext in (".wal", ".tmp"):
            lock_path = self._db_path + ext
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except OSError:
                    pass
        abs_path = os.path.abspath(self._db_path)
        # Try file-backed first, fallback to in-memory
        for attempt, path in enumerate([abs_path, ":memory:"]):
            try:
                print(f"[WAREHOUSE] Connecting to {path} (attempt {attempt+1})", flush=True)
                self._conn = duckdb.connect(path)
                self._create_schema()
                self._initialized = True
                self._db_path = path
                print(f"[WAREHOUSE] Initialized OK at {path}", flush=True)
                logger.info(f"Warehouse initialized OK at {path}")
                return True
            except Exception as e:
                print(f"[WAREHOUSE] Attempt {attempt+1} FAILED ({path}): {e}", flush=True)
                logger.warning(f"Warehouse attempt {attempt+1} failed ({path}): {e}")
                if attempt == 0:
                    for ext in (".wal", ".tmp"):
                        try: os.remove(abs_path + ext)
                        except OSError: pass
        print("[WAREHOUSE] All init attempts FAILED", flush=True)
        return False

    def _create_schema(self):
        """Create warehouse tables (wide, denormalized for analytics)."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dw_transactions (
                id INTEGER, dataset_id INTEGER, date VARCHAR,
                description VARCHAR, account_debit VARCHAR, account_credit VARCHAR,
                department VARCHAR, counterparty VARCHAR, cost_class VARCHAR,
                amount DOUBLE, vat DOUBLE, type VARCHAR,
                created_at TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dw_revenue_items (
                id INTEGER, dataset_id INTEGER, product VARCHAR,
                gross_amount DOUBLE, vat_amount DOUBLE, net_amount DOUBLE,
                segment VARCHAR, category VARCHAR, eliminated BOOLEAN
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dw_trial_balance (
                id INTEGER, dataset_id INTEGER, account_code VARCHAR,
                account_name VARCHAR, account_class INTEGER,
                opening_debit DOUBLE, opening_credit DOUBLE,
                turnover_debit DOUBLE, turnover_credit DOUBLE,
                closing_debit DOUBLE, closing_credit DOUBLE,
                net_pl_impact DOUBLE, mr_mapping VARCHAR, ifrs_line_item VARCHAR
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dw_financial_snapshots (
                id INTEGER, period_id INTEGER, field_name VARCHAR,
                value DOUBLE, source_file VARCHAR, uploaded_at TIMESTAMP
            )
        """)
        
        # 🔗 Phase 3: Institutional Fact & Dimension Tables
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS fact_financial_ledger (
                id INTEGER PRIMARY KEY, dataset_id INTEGER, period VARCHAR,
                account_code VARCHAR, ifrs_line_item VARCHAR, baku_mr_code VARCHAR,
                business_unit VARCHAR, product_category VARCHAR, counterparty VARCHAR,
                amount_gel DOUBLE, amount_usd DOUBLE, quantity DOUBLE,
                entry_type VARCHAR, confidence_score DOUBLE, audit_id VARCHAR,
                created_at TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_products (
                product_name VARCHAR PRIMARY KEY, category VARCHAR,
                segment VARCHAR, unit_measure VARCHAR, is_active BOOLEAN
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_business_units (
                name VARCHAR PRIMARY KEY, region VARCHAR,
                manager VARCHAR, unit_type VARCHAR
            )
        """)

        # ── 4-Tier Pipeline Views (Palantir pattern: raw → clean → semantic → application) ──
        self._create_pipeline_views()

        # ── Materialized analytical views ──
        self._create_materialized_views()

    def _create_pipeline_views(self):
        """Create semantic and application-layer views on top of raw warehouse tables."""
        try:
            # LAYER 2: Clean views (standardized, nulls handled)
            self._conn.execute("""
                CREATE OR REPLACE VIEW clean_trial_balance AS
                SELECT
                    id, dataset_id, account_code, account_name,
                    COALESCE(account_class, CAST(LEFT(account_code, 1) AS INTEGER)) as account_class,
                    COALESCE(opening_debit, 0) as opening_debit,
                    COALESCE(opening_credit, 0) as opening_credit,
                    COALESCE(turnover_debit, 0) as turnover_debit,
                    COALESCE(turnover_credit, 0) as turnover_credit,
                    COALESCE(closing_debit, 0) as closing_debit,
                    COALESCE(closing_credit, 0) as closing_credit,
                    COALESCE(net_pl_impact, 0) as net_pl_impact,
                    mr_mapping, ifrs_line_item
                FROM dw_trial_balance
                WHERE account_code IS NOT NULL AND account_code != ''
            """)

            self._conn.execute("""
                CREATE OR REPLACE VIEW clean_transactions AS
                SELECT
                    id, dataset_id, date,
                    COALESCE(description, '') as description,
                    account_debit, account_credit,
                    COALESCE(department, 'Unassigned') as department,
                    COALESCE(counterparty, 'Unknown') as counterparty,
                    COALESCE(amount, 0) as amount,
                    COALESCE(vat, 0) as vat,
                    type
                FROM dw_transactions
                WHERE amount != 0
            """)

            # LAYER 3: Semantic views (business logic, ontology-backing)
            self._conn.execute("""
                CREATE OR REPLACE VIEW semantic_pl_accounts AS
                SELECT
                    account_code, account_name, account_class,
                    CASE
                        WHEN account_class = 6 THEN 'revenue'
                        WHEN account_class = 7 THEN 'cost_of_sales'
                        WHEN account_class = 8 THEN 'operating_expense'
                        WHEN account_class = 9 THEN 'other_expense'
                        ELSE 'unknown'
                    END as pl_category,
                    CASE WHEN account_class = 6 THEN 'credit' ELSE 'debit' END as normal_balance,
                    turnover_debit, turnover_credit,
                    CASE
                        WHEN account_class = 6 THEN turnover_credit - turnover_debit
                        ELSE turnover_debit - turnover_credit
                    END as period_amount
                FROM clean_trial_balance
                WHERE account_class BETWEEN 6 AND 9
            """)

            self._conn.execute("""
                CREATE OR REPLACE VIEW semantic_bs_accounts AS
                SELECT
                    account_code, account_name, account_class,
                    CASE
                        WHEN account_class IN (1, 2) THEN 'asset'
                        WHEN account_class IN (3, 4) THEN 'liability'
                        WHEN account_class = 5 THEN 'equity'
                        ELSE 'other'
                    END as bs_category,
                    CASE WHEN account_class <= 2 THEN 'debit' ELSE 'credit' END as normal_balance,
                    closing_debit, closing_credit,
                    CASE
                        WHEN account_class <= 2 THEN closing_debit - closing_credit
                        ELSE closing_credit - closing_debit
                    END as balance
                FROM clean_trial_balance
                WHERE account_class BETWEEN 1 AND 5
            """)

            # LAYER 4: Application views (aggregated, ready to serve)
            self._conn.execute("""
                CREATE OR REPLACE VIEW app_income_statement AS
                SELECT
                    pl_category,
                    SUM(period_amount) as total_amount,
                    COUNT(*) as account_count
                FROM semantic_pl_accounts
                GROUP BY pl_category
                ORDER BY
                    CASE pl_category
                        WHEN 'revenue' THEN 1
                        WHEN 'cost_of_sales' THEN 2
                        WHEN 'operating_expense' THEN 3
                        WHEN 'other_expense' THEN 4
                    END
            """)

            self._conn.execute("""
                CREATE OR REPLACE VIEW app_balance_sheet AS
                SELECT
                    bs_category,
                    SUM(balance) as total_balance,
                    COUNT(*) as account_count
                FROM semantic_bs_accounts
                GROUP BY bs_category
                ORDER BY
                    CASE bs_category
                        WHEN 'asset' THEN 1
                        WHEN 'liability' THEN 2
                        WHEN 'equity' THEN 3
                    END
            """)

            self._conn.execute("""
                CREATE OR REPLACE VIEW app_department_costs AS
                SELECT
                    department,
                    SUM(amount) as total_amount,
                    COUNT(*) as transaction_count,
                    MIN(date) as first_date,
                    MAX(date) as last_date
                FROM clean_transactions
                GROUP BY department
                ORDER BY total_amount DESC
            """)

            # LAYER 4.1: Institutional Fact Summary (The "Golden Niche" Insight View)
            self._conn.execute("""
                CREATE OR REPLACE VIEW app_forensic_ledger_summary AS
                SELECT
                    period,
                    business_unit,
                    ifrs_line_item,
                    SUM(amount_gel) as total_gel,
                    SUM(amount_usd) as total_usd,
                    AVG(confidence_score) as avg_confidence
                FROM fact_financial_ledger
                GROUP BY period, business_unit, ifrs_line_item
            """)

            logger.debug("Pipeline views created (clean → semantic → application)")
        except Exception as e:
            logger.debug(f"Pipeline views creation: {e}")

    # ─── Sync from SQLite ────────────────────────────────────────────

    def sync_from_sqlite(self, sqlite_path: str = "data/finai.db") -> Dict[str, int]:
        """Sync SQLite OLTP data into DuckDB warehouse.

        Populates all 4 warehouse tables:
          - dw_financial_snapshots: from finai_store.db financial_snapshots table
          - dw_revenue_items: extracted from upload_history.result_json (revenue_breakdown + cogs_breakdown)
          - dw_trial_balance: extracted from upload_history.result_json (account_classifications from TB uploads)
          - dw_transactions: extracted from upload_history.result_json (pl_line_items)
        """
        if not self._conn:
            self.initialize()
        if not self._conn:
            return {}

        counts = {}
        # Use absolute path so it works regardless of cwd
        store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "finai_store.db")
        store_path = os.path.normpath(store_path)

        # ── 1. Sync financial_snapshots (direct table copy) ──────────
        try:
            if os.path.exists(store_path):
                # Use forward slashes for DuckDB compatibility
                attach_path = store_path.replace("\\", "/")
                logger.info(f"Warehouse syncing snapshots from {attach_path}")
                self._conn.execute(f"ATTACH '{attach_path}' AS store (TYPE SQLITE)")
                self._conn.execute("DELETE FROM dw_financial_snapshots")
                self._conn.execute("INSERT INTO dw_financial_snapshots SELECT * FROM store.financial_snapshots")
                count = self._conn.execute("SELECT COUNT(*) FROM dw_financial_snapshots").fetchone()[0]
                counts["dw_financial_snapshots"] = count
                logger.info(f"Warehouse synced {count} financial snapshots from SQLite")
                self._conn.execute("DETACH store")
            else:
                logger.warning(f"Warehouse sync: finai_store.db not found at {store_path}")
        except Exception as e:
            logger.warning(f"Snapshot sync error: {e}")
            try:
                self._conn.execute("DETACH store")
            except Exception:
                pass

        # ── 2. Extract structured data from upload_history.result_json ──
        import sqlite3
        if not os.path.exists(store_path):
            self._sync_counts = counts
            return counts

        try:
            conn = sqlite3.connect(store_path)
            conn.row_factory = sqlite3.Row
            uploads = conn.execute(
                "SELECT id, company_id, result_json FROM upload_history "
                "WHERE result_json IS NOT NULL AND result_json != '' "
                "ORDER BY created_at"
            ).fetchall()
            conn.close()
            logger.info(f"Warehouse sync: found {len(uploads)} uploads with result_json")
        except Exception as e:
            logger.warning(f"Cannot read upload_history: {e}")
            self._sync_counts = counts
            return counts

        # Clear target tables before re-populating
        for tbl in ("dw_revenue_items", "dw_trial_balance", "dw_transactions"):
            try:
                self._conn.execute(f"DELETE FROM {tbl}")
            except Exception:
                pass

        rev_id = 0
        tb_id = 0
        txn_id = 0

        for upload in uploads:
            upload_id = upload["id"]
            dataset_id = upload["company_id"] or upload_id
            try:
                result = json.loads(upload["result_json"])
            except (json.JSONDecodeError, TypeError):
                continue

            rb = len(result.get("revenue_breakdown", []))
            cb = len(result.get("cogs_breakdown", []))
            pl = len(result.get("pl_line_items", []))
            ac = len(result.get("account_classifications", []))
            if rb + cb + pl + ac > 0:
                logger.info(f"Warehouse sync upload#{upload_id}: rev={rb} cogs={cb} pl={pl} acct={ac}")

            # ── 2a. Revenue items (revenue_breakdown + cogs_breakdown) ──
            for item in result.get("revenue_breakdown", []):
                rev_id += 1
                product = item.get("product", "")
                gross = float(item.get("gross_revenue", item.get("amount", 0)) or 0)
                vat = float(item.get("vat", 0) or 0)
                net = float(item.get("net_revenue", gross - vat) or 0)
                category = item.get("category", "Revenue")
                segment = item.get("segment", "")
                try:
                    self._conn.execute(
                        "INSERT INTO dw_revenue_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [rev_id, dataset_id, product, gross, vat, net, segment, category, False]
                    )
                    counts["dw_revenue_items"] = counts.get("dw_revenue_items", 0) + 1
                except Exception as e:
                    logger.warning(f"Revenue item insert: {e}")

            for item in result.get("cogs_breakdown", []):
                rev_id += 1
                product = item.get("product", item.get("category", "COGS"))
                amount = float(item.get("amount", item.get("net_revenue", 0)) or 0)
                category = item.get("category", "COGS")
                try:
                    self._conn.execute(
                        "INSERT INTO dw_revenue_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [rev_id, dataset_id, product, amount, 0.0, amount, "", category, False]
                    )
                except Exception as e:
                    logger.debug(f"COGS item insert: {e}")

            # ── 2b. Trial balance (from account_classifications in TB uploads) ──
            # account_classifications is stored in result_json for trial_balance doc_type uploads
            # Each entry has: code, name, section, pl_line/bs_side, closing_dr, closing_cr,
            #                  turnover_dr, turnover_cr, opening_dr, opening_cr, method, confidence
            for acct in result.get("account_classifications", []):
                tb_id += 1
                code = str(acct.get("code", ""))
                name = acct.get("name", "")
                # Derive account class from first digit of code
                acct_class = 0
                if code and code[0].isdigit():
                    acct_class = int(code[0])
                opening_dr = float(acct.get("opening_dr", 0) or 0)
                opening_cr = float(acct.get("opening_cr", 0) or 0)
                turnover_dr = float(acct.get("turnover_dr", 0) or 0)
                turnover_cr = float(acct.get("turnover_cr", 0) or 0)
                closing_dr = float(acct.get("closing_dr", 0) or 0)
                closing_cr = float(acct.get("closing_cr", 0) or 0)
                # Net P&L impact: for revenue (class 6) it's cr-dr, for expenses (7-9) it's dr-cr
                if acct_class == 6:
                    net_pl = turnover_cr - turnover_dr
                elif acct_class in (7, 8, 9):
                    net_pl = turnover_dr - turnover_cr
                else:
                    net_pl = 0.0
                section = acct.get("section", "")
                pl_line = acct.get("pl_line", "")
                bs_side = acct.get("bs_side", "")
                mr_mapping = pl_line or bs_side or section
                ifrs_line = acct.get("ifrs_line_item", "")
                try:
                    self._conn.execute(
                        "INSERT INTO dw_trial_balance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [tb_id, dataset_id, code, name, acct_class,
                         opening_dr, opening_cr, turnover_dr, turnover_cr,
                         closing_dr, closing_cr, net_pl, mr_mapping, ifrs_line]
                    )
                except Exception as e:
                    logger.debug(f"TB item insert: {e}")

            # ── 2c. Transactions (from pl_line_items) ──
            # pl_line_items have: label, amount, level, is_total, and optionally code/date
            for item in result.get("pl_line_items", []):
                txn_id += 1
                label = item.get("label", "")
                amount = float(item.get("amount", 0) or 0)
                if amount == 0:
                    continue
                level = item.get("level", 0)
                is_total = item.get("is_total", False)
                code = item.get("code", "")
                # Map P&L items to debit/credit accounts based on sign and type
                if amount > 0:
                    acct_debit = code or label
                    acct_credit = "P&L Summary"
                else:
                    acct_debit = "P&L Summary"
                    acct_credit = code or label
                txn_type = "total" if is_total else f"level_{level}"
                cost_class = ""
                if "revenue" in label.lower() or "income" in label.lower():
                    cost_class = "revenue"
                elif "cogs" in label.lower() or "cost of" in label.lower():
                    cost_class = "cogs"
                elif "expense" in label.lower() or "admin" in label.lower() or "selling" in label.lower():
                    cost_class = "opex"
                elif "depreciation" in label.lower() or "amortization" in label.lower():
                    cost_class = "depreciation"
                try:
                    self._conn.execute(
                        "INSERT INTO dw_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [txn_id, dataset_id, "", label, acct_debit, acct_credit,
                         "", "", cost_class, abs(amount), 0.0, txn_type, None]
                    )
                except Exception as e:
                    logger.debug(f"Transaction insert: {e}")

        # Record counts
        for tbl in ("dw_revenue_items", "dw_trial_balance", "dw_transactions"):
            try:
                count = self._conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                counts[tbl] = count
            except Exception:
                counts[tbl] = 0

        self._sync_counts = counts
        logger.info(f"Warehouse sync complete: {counts}")

        # ── Auto-generate historical data if warehouse is sparse ──────────
        # SAFETY: Synthetic history is only auto-generated in development.
        # In production, historical data must come from real uploads.
        try:
            import os
            app_env = os.getenv("APP_ENV", "development")
            if app_env == "production":
                logger.info(
                    "Synthetic historical data generation SKIPPED (APP_ENV=production). "
                    "Upload real historical data for trend analysis."
                )
            else:
                snap_count = self._conn.execute(
                    "SELECT COUNT(*) FROM dw_financial_snapshots"
                ).fetchone()[0]
                if snap_count > 0 and snap_count < 100:
                    hist = self.generate_historical_data(periods=24)
                    counts["historical_generated"] = hist.get("rows_inserted", 0)
                    logger.info(f"Auto-generated {hist.get('rows_inserted', 0)} synthetic historical rows (dev only)")
        except Exception as e:
            logger.debug(f"Historical data auto-generation skipped: {e}")

        # Refresh materialized views after sync
        try:
            self._create_materialized_views()
        except Exception:
            pass

        return counts

    # ─── Historical Data Generation ─────────────────────────────────

    # Seasonal factors for fuel distribution (index 0 = January)
    _FUEL_SEASONALITY = [
        1.18, 1.12, 1.04, 0.92, 0.85, 0.80,   # Jan-Jun: high winter → low summer
        0.82, 0.88, 0.95, 1.02, 1.10, 1.15,    # Jul-Dec: rising back to winter
    ]

    def generate_historical_data(self, periods: int = 24, company_id: int = 1) -> Dict[str, Any]:
        """Generate SYNTHETIC historical data for trend/forecast engines.

        WARNING: This generates FABRICATED data with random noise. Outputs are
        NOT derived from real financial records. Any analysis based on this
        data should be clearly labeled as synthetic/estimated.

        When a company uploads a single period, this back-fills the previous
        `periods` months with plausible synthetic data based on the current
        period's financials. Applies:
          - Seasonal pattern (fuel distribution: high winter, low summer)
          - Growth trend (reverse-compound at ~0.5-1% per month)
          - Slight random noise (±3%)
          - Stable expenses with inflation (~0.3% monthly)
          - BS items that grow proportionally

        Returns: {"rows_inserted": int, "periods_generated": int, "metrics": [...],
                  "data_source": "synthetic"}
        """
        if not self._conn:
            return {"rows_inserted": 0, "error": "warehouse not initialized"}

        # ── 1. Gather current-period baseline from snapshots ──────────
        try:
            rows = self._conn.execute("""
                SELECT field_name, value, period_id, uploaded_at
                FROM dw_financial_snapshots
                ORDER BY uploaded_at DESC
            """).fetchall()
        except Exception as e:
            return {"rows_inserted": 0, "error": str(e)}

        if not rows:
            return {"rows_inserted": 0, "error": "no snapshot data to base history on"}

        # Build baseline: latest value for each metric
        baseline: Dict[str, float] = {}
        latest_period_id = rows[0][2]  # period_id of most recent
        latest_uploaded = rows[0][3]
        for field_name, value, period_id, uploaded_at in rows:
            if field_name not in baseline:
                baseline[field_name] = float(value or 0)

        if not baseline:
            return {"rows_inserted": 0, "error": "empty baseline"}

        # Classify metrics into categories for appropriate generation
        revenue_keys = [k for k in baseline if any(w in k.lower() for w in
                        ["revenue", "sales", "income", "turnover"])]
        cogs_keys = [k for k in baseline if any(w in k.lower() for w in
                     ["cogs", "cost_of_goods", "cost_of_sales", "direct_cost"])]
        expense_keys = [k for k in baseline if any(w in k.lower() for w in
                        ["expense", "admin", "selling", "salary", "rent", "depreciation",
                         "amortization", "overhead", "utility", "insurance"])]
        profit_keys = [k for k in baseline if any(w in k.lower() for w in
                       ["profit", "ebitda", "ebit", "net_income", "operating_income"])]
        bs_asset_keys = [k for k in baseline if any(w in k.lower() for w in
                         ["asset", "cash", "receivable", "inventory", "equipment",
                          "property", "investment", "prepaid"])]
        bs_liab_keys = [k for k in baseline if any(w in k.lower() for w in
                        ["liability", "payable", "debt", "loan", "accrued", "provision"])]
        bs_equity_keys = [k for k in baseline if any(w in k.lower() for w in
                          ["equity", "capital", "retained", "reserve"])]
        ratio_keys = [k for k in baseline if any(w in k.lower() for w in
                      ["margin", "ratio", "percentage", "rate", "multiple", "yield"])]

        # All categorized keys
        categorized = set(revenue_keys + cogs_keys + expense_keys + profit_keys +
                         bs_asset_keys + bs_liab_keys + bs_equity_keys + ratio_keys)
        other_keys = [k for k in baseline if k not in categorized]

        # ── 2. Generate historical periods ────────────────────────────
        # Determine base date
        if isinstance(latest_uploaded, str):
            try:
                base_date = datetime.fromisoformat(latest_uploaded.replace("Z", "+00:00"))
            except Exception:
                base_date = datetime.now()
        elif latest_uploaded:
            base_date = latest_uploaded if isinstance(latest_uploaded, datetime) else datetime.now()
        else:
            base_date = datetime.now()

        random.seed(42)  # Reproducible results
        monthly_growth = 0.008   # ~1% monthly growth (reversed for going backward)
        inflation = 0.003        # ~0.3% monthly inflation on expenses
        noise_pct = 0.03         # ±3% random noise
        inserted = 0
        metrics_generated = set()

        # Get max existing ID
        try:
            max_id = self._conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM dw_financial_snapshots"
            ).fetchone()[0]
        except Exception:
            max_id = 0
        next_id = max_id + 1

        # Check if historical data already exists (more than 2 distinct period_ids)
        try:
            distinct_periods = self._conn.execute(
                "SELECT COUNT(DISTINCT period_id) FROM dw_financial_snapshots"
            ).fetchone()[0]
            if distinct_periods > 3:
                return {"rows_inserted": 0, "periods_generated": 0,
                        "note": f"Historical data already exists ({distinct_periods} periods)"}
        except Exception:
            pass

        for month_offset in range(1, periods + 1):
            period_date = base_date - timedelta(days=30 * month_offset)
            period_str = period_date.strftime("%Y-%m")
            period_id_hist = latest_period_id + 1000 + month_offset  # Synthetic period IDs
            month_idx = period_date.month - 1  # 0-based month index
            seasonal = self._FUEL_SEASONALITY[month_idx]

            for key in baseline:
                base_val = baseline[key]
                if base_val == 0:
                    # For zero values, keep them zero with rare small variation
                    hist_val = 0.0
                elif key in revenue_keys:
                    # Revenue: reverse growth + seasonal + noise
                    growth_factor = (1 - monthly_growth) ** month_offset
                    noise = 1 + random.uniform(-noise_pct, noise_pct)
                    hist_val = base_val * growth_factor * seasonal * noise
                elif key in cogs_keys:
                    # COGS follows revenue pattern with slight margin variation
                    growth_factor = (1 - monthly_growth) ** month_offset
                    margin_noise = 1 + random.uniform(-0.02, 0.02)
                    hist_val = base_val * growth_factor * seasonal * margin_noise
                elif key in expense_keys:
                    # Expenses: stable with reverse inflation + small noise
                    inflation_factor = (1 - inflation) ** month_offset
                    noise = 1 + random.uniform(-0.015, 0.015)
                    hist_val = base_val * inflation_factor * noise
                elif key in profit_keys:
                    # Profit: derive from revenue/cogs pattern (seasonal + growth)
                    growth_factor = (1 - monthly_growth) ** month_offset
                    noise = 1 + random.uniform(-noise_pct * 1.5, noise_pct * 1.5)
                    hist_val = base_val * growth_factor * seasonal * noise
                elif key in bs_asset_keys:
                    # BS assets: grow proportionally (reverse compounding)
                    growth_factor = (1 - monthly_growth * 0.5) ** month_offset
                    noise = 1 + random.uniform(-0.01, 0.01)
                    hist_val = base_val * growth_factor * noise
                elif key in bs_liab_keys:
                    # Liabilities: slow growth
                    growth_factor = (1 - monthly_growth * 0.3) ** month_offset
                    noise = 1 + random.uniform(-0.01, 0.01)
                    hist_val = base_val * growth_factor * noise
                elif key in bs_equity_keys:
                    # Equity: very stable
                    growth_factor = (1 - monthly_growth * 0.2) ** month_offset
                    hist_val = base_val * growth_factor
                elif key in ratio_keys:
                    # Ratios: small bounded fluctuations
                    noise = 1 + random.uniform(-0.05, 0.05)
                    hist_val = base_val * noise
                else:
                    # Other: moderate noise
                    growth_factor = (1 - monthly_growth * 0.5) ** month_offset
                    noise = 1 + random.uniform(-noise_pct, noise_pct)
                    hist_val = base_val * growth_factor * noise

                hist_val = round(hist_val, 2)
                uploaded_ts = period_date.strftime("%Y-%m-%d %H:%M:%S")

                try:
                    self._conn.execute(
                        "INSERT INTO dw_financial_snapshots VALUES (?, ?, ?, ?, ?, ?)",
                        [next_id, period_id_hist, key, hist_val, "synthetic_history", uploaded_ts]
                    )
                    next_id += 1
                    inserted += 1
                    metrics_generated.add(key)
                except Exception as e:
                    logger.debug(f"Historical insert failed: {e}")

        logger.info(f"Generated {inserted} SYNTHETIC historical rows across {periods} periods")
        return {
            "rows_inserted": inserted,
            "periods_generated": periods,
            "metrics": sorted(metrics_generated),
            "baseline_metrics_count": len(baseline),
            "data_source": "synthetic",
            "warning": (
                "This data is synthetically generated with random noise (±3%). "
                "It is NOT derived from real financial records. Do not use for "
                "audit, compliance, or investment decisions."
            ),
        }

    # ─── Materialized Analytical Views ────────────────────────────────

    def _create_materialized_views(self):
        """Create DuckDB views for fast KPI analytics, trend analysis, and revenue mix."""
        if not self._conn:
            return
        try:
            # Monthly KPI view with lag and percent-change
            self._conn.execute("""
                CREATE OR REPLACE VIEW vw_monthly_kpis AS
                SELECT
                    field_name AS metric,
                    period_id,
                    uploaded_at AS period,
                    value,
                    LAG(value) OVER (PARTITION BY field_name ORDER BY uploaded_at) AS prev_value,
                    CASE
                        WHEN LAG(value) OVER (PARTITION BY field_name ORDER BY uploaded_at) IS NULL THEN NULL
                        WHEN LAG(value) OVER (PARTITION BY field_name ORDER BY uploaded_at) = 0 THEN NULL
                        ELSE (value - LAG(value) OVER (PARTITION BY field_name ORDER BY uploaded_at))
                             / ABS(LAG(value) OVER (PARTITION BY field_name ORDER BY uploaded_at)) * 100
                    END AS pct_change
                FROM dw_financial_snapshots
                WHERE field_name IN (
                    'revenue', 'gross_profit', 'ebitda', 'net_profit', 'net_income',
                    'operating_income', 'cost_of_goods_sold', 'operating_expenses',
                    'total_revenue', 'sales', 'turnover'
                )
                ORDER BY field_name, uploaded_at
            """)

            # Revenue mix breakdown
            self._conn.execute("""
                CREATE OR REPLACE VIEW vw_revenue_mix AS
                SELECT
                    category,
                    SUM(net_amount) AS total,
                    COUNT(*) AS items,
                    SUM(net_amount) / NULLIF(SUM(SUM(net_amount)) OVER (), 0) * 100 AS pct
                FROM dw_revenue_items
                GROUP BY category
            """)

            # Trend analysis with moving averages
            self._conn.execute("""
                CREATE OR REPLACE VIEW vw_trend_analysis AS
                SELECT
                    field_name AS metric,
                    period_id,
                    uploaded_at AS period,
                    value,
                    AVG(value) OVER (
                        PARTITION BY field_name ORDER BY uploaded_at
                        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                    ) AS ma_3,
                    AVG(value) OVER (
                        PARTITION BY field_name ORDER BY uploaded_at
                        ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
                    ) AS ma_6,
                    AVG(value) OVER (
                        PARTITION BY field_name ORDER BY uploaded_at
                        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                    ) AS ma_12,
                    STDDEV_POP(value) OVER (
                        PARTITION BY field_name ORDER BY uploaded_at
                        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                    ) AS stddev_12
                FROM dw_financial_snapshots
                ORDER BY field_name, uploaded_at
            """)

            # Anomaly detection view (values beyond 2 std devs from 12-period MA)
            self._conn.execute("""
                CREATE OR REPLACE VIEW vw_anomalies AS
                SELECT
                    metric, period_id, period, value, ma_12, stddev_12,
                    CASE
                        WHEN stddev_12 > 0 THEN (value - ma_12) / stddev_12
                        ELSE 0
                    END AS z_score,
                    CASE
                        WHEN stddev_12 > 0 AND ABS(value - ma_12) / stddev_12 > 2.0 THEN 'anomaly'
                        WHEN stddev_12 > 0 AND ABS(value - ma_12) / stddev_12 > 1.5 THEN 'warning'
                        ELSE 'normal'
                    END AS status
                FROM vw_trend_analysis
                WHERE ma_12 IS NOT NULL AND stddev_12 IS NOT NULL AND stddev_12 > 0
            """)

            # Period-over-period comparison view
            self._conn.execute("""
                CREATE OR REPLACE VIEW vw_period_comparison AS
                SELECT
                    field_name AS metric,
                    period_id,
                    uploaded_at AS period,
                    value AS current_value,
                    LAG(value, 1) OVER (PARTITION BY field_name ORDER BY uploaded_at) AS prev_1m,
                    LAG(value, 3) OVER (PARTITION BY field_name ORDER BY uploaded_at) AS prev_3m,
                    LAG(value, 6) OVER (PARTITION BY field_name ORDER BY uploaded_at) AS prev_6m,
                    LAG(value, 12) OVER (PARTITION BY field_name ORDER BY uploaded_at) AS prev_12m
                FROM dw_financial_snapshots
                ORDER BY field_name, uploaded_at
            """)

            logger.debug("Materialized analytical views created/refreshed")
        except Exception as e:
            logger.debug(f"Materialized views creation: {e}")

    # ─── Trend & Anomaly Queries ──────────────────────────────────────

    def get_trends(self, metric: str, periods: int = 12) -> Dict[str, Any]:
        """Query trend data for a metric with moving averages and pct changes.

        Returns: {"metric": str, "data": [...], "summary": {...}}
        """
        if not self._conn:
            self.initialize()
        if not self._conn:
            return {"metric": metric, "data": [], "error": "warehouse not initialized"}

        try:
            rows = self._conn.execute("""
                SELECT metric, period_id, period, value, ma_3, ma_6, ma_12, stddev_12
                FROM vw_trend_analysis
                WHERE metric = ?
                ORDER BY period DESC
                LIMIT ?
            """, [metric, periods]).fetchall()

            if not rows:
                # Try partial match
                rows = self._conn.execute("""
                    SELECT metric, period_id, period, value, ma_3, ma_6, ma_12, stddev_12
                    FROM vw_trend_analysis
                    WHERE LOWER(metric) LIKE LOWER(?)
                    ORDER BY period DESC
                    LIMIT ?
                """, [f"%{metric}%", periods]).fetchall()

            data = []
            for r in rows:
                data.append({
                    "metric": r[0],
                    "period_id": r[1],
                    "period": str(r[2]) if r[2] else None,
                    "value": round(r[3], 2) if r[3] is not None else None,
                    "ma_3": round(r[4], 2) if r[4] is not None else None,
                    "ma_6": round(r[5], 2) if r[5] is not None else None,
                    "ma_12": round(r[6], 2) if r[6] is not None else None,
                    "stddev_12": round(r[7], 2) if r[7] is not None else None,
                })

            # Build summary
            values = [d["value"] for d in data if d["value"] is not None]
            summary = {}
            if values:
                summary = {
                    "latest": values[0],
                    "min": min(values),
                    "max": max(values),
                    "mean": round(sum(values) / len(values), 2),
                    "data_points": len(values),
                    "trend_direction": "up" if len(values) >= 2 and values[0] > values[-1]
                                       else "down" if len(values) >= 2 and values[0] < values[-1]
                                       else "flat",
                }
                if len(values) >= 2 and values[-1] != 0:
                    summary["total_change_pct"] = round(
                        (values[0] - values[-1]) / abs(values[-1]) * 100, 2
                    )

            return {"metric": metric, "data": list(reversed(data)), "summary": summary}
        except Exception as e:
            return {"metric": metric, "data": [], "error": str(e)}

    def get_anomalies(self, threshold: float = 2.0) -> Dict[str, Any]:
        """Detect values that deviate more than `threshold` std devs from the moving average.

        Returns: {"anomalies": [...], "warnings": [...], "total_checked": int}
        """
        if not self._conn:
            self.initialize()
        if not self._conn:
            return {"anomalies": [], "warnings": [], "error": "warehouse not initialized"}

        try:
            rows = self._conn.execute("""
                SELECT metric, period_id, period, value, ma_12, stddev_12, z_score, status
                FROM vw_anomalies
                WHERE ABS(z_score) > ?
                ORDER BY ABS(z_score) DESC
                LIMIT 100
            """, [threshold * 0.75]).fetchall()  # Include warnings at 75% of threshold

            anomalies = []
            warnings = []
            for r in rows:
                entry = {
                    "metric": r[0],
                    "period_id": r[1],
                    "period": str(r[2]) if r[2] else None,
                    "value": round(r[3], 2) if r[3] is not None else None,
                    "moving_avg": round(r[4], 2) if r[4] is not None else None,
                    "std_dev": round(r[5], 2) if r[5] is not None else None,
                    "z_score": round(r[6], 2) if r[6] is not None else None,
                    "deviation_pct": round(
                        (r[3] - r[4]) / abs(r[4]) * 100, 2
                    ) if r[4] and r[4] != 0 else 0,
                }
                if abs(r[6]) >= threshold:
                    entry["severity"] = "critical" if abs(r[6]) >= threshold * 1.5 else "anomaly"
                    anomalies.append(entry)
                else:
                    entry["severity"] = "warning"
                    warnings.append(entry)

            # Total data points checked
            try:
                total = self._conn.execute(
                    "SELECT COUNT(*) FROM vw_anomalies"
                ).fetchone()[0]
            except Exception:
                total = 0

            return {
                "anomalies": anomalies,
                "warnings": warnings,
                "total_checked": total,
                "threshold": threshold,
                "anomaly_count": len(anomalies),
                "warning_count": len(warnings),
            }
        except Exception as e:
            return {"anomalies": [], "warnings": [], "error": str(e)}

    # ─── Query ───────────────────────────────────────────────────────

    def execute(self, sql: str) -> List[Dict]:
        """Execute raw SQL (DEPRECATED — use execute_safe for new code)."""
        if not self._conn:
            self.initialize()
        if not self._conn:
            return []
        try:
            df = self._conn.execute(sql).fetchdf()
            return df.to_dict(orient="records") if len(df) > 0 else []
        except Exception as e:
            return [{"error": str(e)}]

    def execute_safe(self, sql: str, params: list) -> List[Dict]:
        """Execute parameterized SQL — safe from injection."""
        if not self._conn:
            self.initialize()
        if not self._conn:
            return []
        try:
            df = self._conn.execute(sql, params).fetchdf()
            return df.to_dict(orient="records") if len(df) > 0 else []
        except Exception as e:
            logger.error(f"Safe query failed: {e} | SQL: {sql} | Params: {params}")
            return [{"error": str(e)}]

    def validate_table_name(self, name: str) -> Optional[str]:
        """Validate a table name against known warehouse tables.
        Returns the safe name if valid, None otherwise."""
        import re
        # Only allow alphanumeric + underscore table names
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            logger.warning(f"Rejected invalid table name: {name!r}")
            return None
        # Check against actual warehouse tables
        if not self._conn:
            self.initialize()
        if not self._conn:
            return None
        try:
            known = self._conn.execute(
                "SELECT table_name FROM duckdb_tables()"
            ).fetchdf()["table_name"].tolist()
            if name in known:
                return name
            logger.warning(f"Table {name!r} not found in warehouse")
            return None
        except Exception:
            return None

    def list_tables(self) -> List[Dict]:
        if not self._conn:
            return []
        df = self._conn.execute("SELECT table_name, estimated_size FROM duckdb_tables()").fetchdf()
        result = []
        for _, row in df.iterrows():
            name = row["table_name"]
            # table name comes from DuckDB catalog — safe to quote-escape
            safe_name = self.validate_table_name(name)
            if not safe_name:
                result.append({"table": name, "rows": 0})
                continue
            try:
                count = self._conn.execute(f'SELECT COUNT(*) FROM "{safe_name}"').fetchone()[0]
            except Exception:
                count = 0
            result.append({"table": name, "rows": count})
        return result

    # ─── Virtual Tables (Views) ──────────────────────────────────────

    def create_virtual_table(self, name: str, query: str) -> bool:
        if not self._conn:
            return False
        try:
            self._conn.execute(f"CREATE OR REPLACE VIEW {name} AS {query}")
            return True
        except Exception as e:
            logger.error(f"Virtual table {name} failed: {e}")
            return False

    # ─── Time Series ─────────────────────────────────────────────────

    def get_time_series(self, metric: str) -> List[Dict]:
        if not self._conn:
            return []
        try:
            import sqlite3, os
            # Build period_id -> period_name map from SQLite
            store_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'data', 'finai_store.db')
            if not os.path.exists(store_path):
                store_path = 'data/finai_store.db'
            period_map = {}
            try:
                sconn = sqlite3.connect(store_path)
                rows = sconn.execute("SELECT id, period_name FROM financial_periods").fetchall()
                for r in rows:
                    period_map[r[0]] = r[1]
                sconn.close()
            except Exception:
                pass

            df = self._conn.execute("""
                SELECT
                    field_name as metric,
                    period_id,
                    value
                FROM dw_financial_snapshots
                WHERE field_name = ?
                ORDER BY period_id
            """, [metric]).fetchdf()

            if len(df) == 0:
                return []

            results = []
            for _, row in df.iterrows():
                pid = int(row['period_id'])
                period_name = period_map.get(pid, f'P{pid}')
                results.append({
                    'metric': row['metric'],
                    'period': period_name,
                    'value': float(row['value'])
                })
            return results
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Time series query failed for {metric}: {e}")
            return []

    # ─── Parquet ─────────────────────────────────────────────────────

    def export_parquet(self, table_name: str, output_path: str) -> str:
        if not self._conn:
            return ""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self._conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT PARQUET)")
        return output_path

    def import_parquet(self, file_path: str, table_name: str) -> int:
        if not self._conn:
            return 0
        self._conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM read_parquet('{file_path}')")
        return self._conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    # ─── Stats ───────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        _ensure_warehouse()
        if not self._conn:
            return {"initialized": False}
        tables = self.list_tables()
        return {
            "initialized": True,
            "engine": "duckdb",
            "db_path": self._db_path,
            "tables": tables,
            "last_sync": self._sync_counts,
        }


# Singleton — lazy initialization on first use
warehouse = FinAIWarehouse()

def _ensure_warehouse():
    """Ensure warehouse is initialized before use."""
    if not warehouse._initialized:
        warehouse.initialize()
    return warehouse._initialized
