"""
FinAI AI Agent Service — tool names and data formats match frontend v6 exactly
Tools: navigate_to_page, query_transactions, calculate_financials,
       generate_pl_statement, generate_balance_sheet, generate_mr_report,
       generate_chart, save_report_to_db, analyze_products,
       detect_anomalies, search_counterparty
MR row format: {c, l, ac, pl, lvl, bold, sep, s}
"""
import json
import re
import httpx
from typing import Dict, List, Any, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from anthropic import AsyncAnthropic
from app.services.regulatory_intelligence import regulatory_intelligence
from app.services.external_data import external_data
try:
    import google.generativeai as genai
except ImportError:
    genai = None
from app.config import settings
from app.models.all_models import Transaction, RevenueItem, BudgetLine, Report, AgentMemory, Dataset, COGSItem, GAExpenseItem
from app.services.income_statement import build_income_statement
from app.services.file_parser import GA_ACCOUNT_NAMES
import logging
from app.services.forecasting import ForecastEngine, TrendAnalyzer
from app.services.anomaly_detector import AnomalyDetector
from app.services.currency_service import CurrencyService
from app.services.scenario_engine import ScenarioEngine
from app.services.vector_store import vector_store
from app.services.logistics_intelligence_service import logistics_intelligence
from app.services.risk_intelligence import risk_engine
from app.services.regulatory_intelligence import regulatory_intelligence

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    # Fallback dummy tracer if opentelemetry isn't installed
    class DummySpan:
        def set_attribute(self, *args, **kwargs): pass
        def end(self): pass
    class DummyTracer:
        def start_span(self, *args, **kwargs): return DummySpan()
    tracer = DummyTracer()


def fgel(v: float) -> str:
    if v is None: return "—"
    a = abs(v)
    if a >= 1e6: return f"₾{v/1e6:.3f}M"
    if a >= 1e3: return f"₾{v/1e3:.1f}K"
    return f"₾{v:.2f}"


def fexact(v: float) -> str:
    """Format as exact figure with 2 decimal places and thousand separators."""
    if v is None: return "—"
    return f"{v:,.2f}"


class FinAIAgent:
    """
    Production AI agent — tool names match frontend v6 BUILTIN_TOOLS exactly
    so both the standalone HTML and the backend produce identical outputs.
    """

    def __init__(self):
        # Lazy-init: create client only when API key is available
        self._client = None
        self.model  = settings.ANTHROPIC_MODEL
        self.max_tokens = settings.ANTHROPIC_MAX_TOKENS
        
        # NVIDIA / Gemma 4 primary settings
        from app.services.local_llm import GEMMA4_MODEL, GEMMA4_TIMEOUT
        self.gemma_model = GEMMA4_MODEL
        self.gemma_timeout = GEMMA4_TIMEOUT

        # Initialize Gemini for multilingual depth
        if genai and settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            self._gemini_model = None

        # ── Advanced service instances ──────────────────────────────────
        self.forecast_engine = ForecastEngine()
        self.trend_analyzer = TrendAnalyzer()
        self.anomaly_detector = AnomalyDetector()
        self.currency_service = CurrencyService()
        self.scenario_engine = ScenarioEngine()

        # ── TOOL DEFINITIONS (identical names to frontend) ──────────────────
        self.tools = [
            {
                "name": "navigate_to_page",
                "description": "Navigate the UI to a specific page",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "string",
                                 "description": "dash|pl|bs|cfs|coa|revenue|cogs|costs|budget|mr|txn|lib|tools|train|forecast|scenarios|anomalies|advtools"}
                    },
                    "required": ["page"]
                }
            },
            {
                "name": "query_transactions",
                "description": "Filter and query transactions",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type":     {"type": "string", "description": "Expense|Income|Transfer"},
                        "dept":     {"type": "string"},
                        "category": {"type": "string", "description": "cost_class filter"},
                        "counterparty": {"type": "string"},
                        "min_amount":   {"type": "number"},
                        "max_amount":   {"type": "number"},
                        "limit":        {"type": "integer"}
                    }
                }
            },
            {
                "name": "calculate_financials",
                "description": "Calculate financial metrics",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string",
                                   "description": "revenue|margins|expenses|top_categories|dept_breakdown|full_summary|profitability_ratios"}
                    },
                    "required": ["metric"]
                }
            },
            {
                "name": "generate_pl_statement",
                "description": "Generate P&L statement from database. Navigates to P&L page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "period":   {"type": "string"},
                        "currency": {"type": "string"},
                        "source":   {"type": "string", "description": "transactions|budget|auto"}
                    }
                }
            },
            {
                "name": "generate_balance_sheet",
                "description": "Generate Balance Sheet. Navigates to BS page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "period": {"type": "string"}
                    }
                }
            },
            {
                "name": "generate_mr_report",
                "description": "Generate Management Report from active dataset. Auto-saves to database.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "period": {"type": "string"},
                        "save":   {"type": "boolean"}
                    }
                }
            },
            {
                "name": "generate_income_statement",
                "description": "Generate structured Income Statement with Wholesale/Retail/Other breakdown. Shows Revenue, COGS, Margins, G&A, and EBITDA. Navigates to P&L page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "period":   {"type": "string"},
                        "currency": {"type": "string"},
                        "save":     {"type": "boolean", "description": "Save to database (default true)"}
                    }
                }
            },
            {
                "name": "generate_chart",
                "description": "Generate an inline chart in the chat",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type":   {"type": "string", "description": "bar|line|doughnut|pie"},
                        "title":  {"type": "string"},
                        "labels": {"type": "array",  "items": {"type": "string"}},
                        "data":   {"type": "array",  "items": {"type": "number"}}
                    },
                    "required": ["type","title","labels","data"]
                }
            },
            {
                "name": "save_report_to_db",
                "description": "Save a generated report to the database",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type":    {"type": "string", "description": "pl|bs|mr|custom"},
                        "title":   {"type": "string"},
                        "period":  {"type": "string"},
                        "summary": {"type": "string"}
                    },
                    "required": ["type","title","period"]
                }
            },
            {
                "name": "analyze_products",
                "description": "Analyze revenue products and segments",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "segment": {"type": "string", "description": "Revenue Retail|Revenue Wholesale|Other Revenue|all"},
                        "top_n":   {"type": "integer"}
                    }
                }
            },
            {
                "name": "command_digital_twin",
                "description": "Directly manipulate the Industrial Digital Twin (Strategic Map). Use this to highlight critical infrastructure, pulse hubs, or reveal competitor supply chains based on user queries or risk audits.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command_type": {
                            "type": "string", 
                            "enum": ["highlight_route", "pulse_node", "show_competitors", "trigger_simulation"],
                            "description": "The type of map manipulation to execute."
                        },
                        "target_id": {
                            "type": "string",
                            "description": "The ID of the route or node (e.g., 'btc_pipeline', 'BAKU', 'TBILISI')."
                        },
                        "intent": {
                            "type": "string",
                            "description": "Strategic intent (e.g., 'OPTIMIZE_LOGISTICS', 'THREAT_DETECTION')."
                        },
                        "rationale": {
                            "type": "string",
                            "description": "The tactical reasoning behind this map command to be displayed in the Operator HUD."
                        },
                        "efficiency_gain": {
                            "type": "number",
                            "description": "Estimated efficiency gain percentage (if applicable)."
                        }
                    },
                    "required": ["command_type", "intent", "rationale"]
                }
            },
            {
                "name": "detect_anomalies",
                "description": "Detect anomalies in transactions: large amounts, unusual patterns",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "threshold_pct": {"type": "number", "description": "Flag if > X% of category total"},
                        "min_amount":    {"type": "number"}
                    }
                }
            },
            {
                "name": "search_counterparty",
                "description": "Search and analyze transactions by counterparty/vendor",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name":    {"type": "string", "description": "Counterparty name to search"},
                        "top_n":   {"type": "integer", "description": "Return top N counterparties by spend"}
                    }
                }
            },
            {
                "name": "compare_periods",
                "description": "Compare two periods' P&L data side by side. Requires two dataset IDs.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id_1": {"type": "integer", "description": "Prior period dataset ID"},
                        "dataset_id_2": {"type": "integer", "description": "Current period dataset ID"},
                    },
                    "required": ["dataset_id_1", "dataset_id_2"]
                }
            },
            {
                "name": "analyze_semantic",
                "description": "Run semantic layer analysis on transactions. Shows how transactions are classified using AI multi-signal fusion: COA codes + counterparty patterns + department mapping + cost classification text. Useful for explaining data quality, classification confidence, and identifying unclassified transactions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "focus": {"type": "string", "description": "Focus area: overview|counterparty|department|confidence|unclassified"}
                    }
                }
            },
            {
                "name": "deep_financial_analysis",
                "description": "Deep financial analysis with EXACT figures. Provides: COGS column breakdown (K/L/O per product), VAT analysis (rates, zero-VAT products), revenue concentration (Pareto/top-N), per-product profitability (margin % per product), cross-validation (Revenue vs COGS matching). Use this for detailed test-level questions requiring exact precision figures.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "analysis": {"type": "string", "description": "cogs_columns|vat_analysis|concentration|product_profitability|cross_validation|full_exact_is"},
                        "category_filter": {"type": "string", "description": "Optional: filter by category like 'COGS Whsale Petrol' or 'Revenue Retial Diesel'"},
                        "top_n": {"type": "integer", "description": "Number of top items to show (default 10)"}
                    },
                    "required": ["analysis"]
                }
            },
            {
                "name": "generate_forecast",
                "description": "Generate revenue, COGS, margin, or expense forecasts using statistical methods. Uses historical data across all uploaded datasets.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "forecast_type": {"type": "string", "description": "revenue|cogs|margin|ga_expenses"},
                        "product": {"type": "string", "description": "Optional: petrol|diesel|cng|lpg|bitumen"},
                        "segment": {"type": "string", "description": "Optional: wholesale|retail"},
                        "method": {"type": "string", "description": "auto|moving_average|exponential_smoothing|linear_regression|growth_rate|seasonal_decompose"},
                        "periods": {"type": "integer", "description": "Number of future periods to forecast (default 6)"}
                    },
                    "required": ["forecast_type"]
                }
            },
            {
                "name": "search_knowledge",
                "description": "Search across all financial data, documents, and domain knowledge using semantic/keyword search (RAG). Use this to find specific transactions, counterparties, amounts, or answer questions not covered by other tools.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language search query"},
                        "n_results": {"type": "integer", "description": "Number of results to return (default 10)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "analyze_trends",
                "description": "Analyze trends across multiple periods — growth rates, CAGR, volatility, direction. Requires 2+ datasets uploaded for different periods.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "description": "revenue|cogs|margin|ga_expenses"},
                        "segment": {"type": "string", "description": "Optional: wholesale|retail"},
                        "product": {"type": "string", "description": "Optional: petrol|diesel|cng|lpg|bitumen"}
                    },
                    "required": ["metric"]
                }
            },
            {
                "name": "create_scenario",
                "description": "Create a what-if scenario to model business changes. Specify changes like price increases, volume changes, new stations, cost adjustments.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Scenario name"},
                        "description": {"type": "string", "description": "What this scenario models"},
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target": {"type": "string", "description": "revenue_wholesale_diesel|cogs_retail_petrol|volume_retail|price_diesel|ga_expenses|new_retail_stations"},
                                    "change_type": {"type": "string", "description": "pct_change|absolute|delta"},
                                    "value": {"type": "number", "description": "Change value (% for pct_change, absolute amount, or delta)"}
                                },
                                "required": ["target", "change_type", "value"]
                            },
                            "description": "List of changes to apply"
                        }
                    },
                    "required": ["name", "changes"]
                }
            },
            {
                "name": "compare_scenarios",
                "description": "Compare multiple what-if scenarios side by side. Shows how different business decisions affect the P&L.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "scenario_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of scenario IDs to compare"
                        }
                    },
                    "required": ["scenario_ids"]
                }
            },
            {
                "name": "detect_anomalies_statistical",
                "description": "Run statistical anomaly detection on transaction data using Z-score, IQR, and Benford's Law analysis. Finds unusual transactions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "integer", "description": "Optional: specific dataset ID (defaults to active)"},
                        "zscore_threshold": {"type": "number", "description": "Z-score threshold for flagging (default 2.0)"},
                        "iqr_multiplier": {"type": "number", "description": "IQR multiplier for outlier fences (default 1.5)"}
                    }
                }
            },
            {
                "name": "convert_currency",
                "description": "Convert financial amounts between currencies using live exchange rates. Supports GEL, USD, EUR, GBP, TRY.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Amount to convert"},
                        "from_currency": {"type": "string", "description": "Source currency code (e.g. GEL)"},
                        "to_currency": {"type": "string", "description": "Target currency code (e.g. USD)"}
                    },
                    "required": ["amount", "from_currency", "to_currency"]
                }
            },
            {
                "name": "trace_lineage",
                "description": "Trace the data lineage of any financial figure back to its source file, sheet, row, and classification rule.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_type": {"type": "string", "description": "transaction|revenue_item|cogs_item|ga_expense"},
                        "entity_id": {"type": "integer", "description": "The record ID to trace"}
                    },
                    "required": ["entity_type", "entity_id"]
                }
            },
            {
                "name": "query_coa",
                "description": "Query the Georgian Chart of Accounts. Search by account code or name. Shows COA mapping details and navigates to the COA page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Account code to look up (e.g. 6110, 7310, 1410)"},
                        "search": {"type": "string", "description": "Search text to find accounts by name"},
                    }
                }
            },
            {
                "name": "generate_cash_flow",
                "description": "Generate a Cash Flow Statement using the indirect method. Shows Operating, Investing, and Financing activities. Navigates to the Cash Flow page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "integer", "description": "Current period dataset ID (default: active)"},
                        "prior_dataset_id": {"type": "integer", "description": "Prior period dataset ID for change calculations"},
                    }
                }
            },
            {
                "name": "query_balance_sheet",
                "description": "Query IFRS-mapped Balance Sheet data from parsed Balance/BS sheets. Returns line items by section (assets, liabilities, equity) or specific IFRS line item.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "string", "description": "Filter by section: noncurrent_assets|current_assets|noncurrent_liabilities|current_liabilities|equity|all"},
                        "ifrs_line": {"type": "string", "description": "Filter by specific IFRS line item name (e.g. 'Cash and cash equivalents', 'Trade receivables')"},
                    }
                }
            },
            {
                "name": "query_trial_balance",
                "description": "Query Trial Balance (TDSheet) data. Can filter by account prefix (e.g. '73' for selling expenses) or account class (1-9). Returns account codes, names, turnovers, and net P&L impact.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "account_prefix": {"type": "string", "description": "Account code prefix to filter (e.g. '73' for selling, '74' for admin, '71' for COGS, '6' for revenue)"},
                        "account_class": {"type": "integer", "description": "Account class 1-9 (1=Current Assets, 2=Noncurrent Assets, 3=CL, 4=NCL, 5=Equity, 6=Revenue, 7=OpEx, 8=Non-Operating, 9=Other)"},
                        "top_n": {"type": "integer", "description": "Return top N by turnover (default: 20)"},
                    }
                }
            },
            {
                "name": "analyze_accounting_flows",
                "description": "Analyze the accounting flow structure of the active dataset using Accounting Intelligence. "
                               "Shows account coverage (mapped vs unmapped), financial flows (inventory→COGS, revenue formation, "
                               "COGS formation, BS identity A=L+E), working capital, and data quality warnings. "
                               "Can also classify any specific account code using 5-level hierarchical fallback "
                               "(exact → parent → root → class → unmapped) per the Georgian 1C Chart of Accounts.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "flow_type": {
                            "type": "string",
                            "description": "Specific flow to explain: inventory_to_cogs | revenue_formation | cogs_formation | "
                                           "operating_expenses | financial_burden | working_capital | bs_identity | intercompany | full (default)"
                        },
                        "account_code": {
                            "type": "string",
                            "description": "Classify a specific account code with hierarchical fallback (e.g. '7110.01/1', '8220', '1610')"
                        },
                    }
                }
            },
            {
                "name": "visualize_logistics",
                "description": "Visualize tactical logistics on the map: optimized routes, competitor supply chains, infrastructure health. The agent will analyze current risks and company needs and then suggest a map view. This tool can also show 'competitors' (Socar, Rompetrol, Gulf, etc.).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "description": "optimize_route|show_competitors|infrastructure_health"},
                        "competitor_id": {"type": "string", "description": "Optional: socar|rompetrol|gulf|lukoil|all"},
                        "target_route_id": {"type": "string", "description": "Optional: btc_pipeline|scp_pipeline|supsa_route|black_sea_maritime"},
                        "user_intent_summary": {"type": "string", "description": "Short text for the map overlay showing what the agent is doing (e.g., 'Optimizing Logistics Path...')"}
                    },
                    "required": ["mode"]
                }
            },
            {
                "name": "command_digital_twin",
                "description": "Directly manipulate the Industrial Digital Twin map. Essential for tactical briefings, competitor analysis, and strategic overlays. Use this to highlight routes, pulse nodes, show competitors, or trigger full 'War Room' strategy simulations during market disruptions (like fuel price jumps).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command_type": {
                            "type": "string",
                            "description": "highlight_route|pulse_node|show_competitors|trigger_strategy"
                        },
                        "target_id": {
                            "type": "string",
                            "description": "Optional: ID of the route or node (e.g., 'btc_pipeline', 'BAKU', 'BASRA')"
                        },
                        "intent": {
                            "type": "string",
                            "description": "Short descriptive intent for the map (e.g., 'Optimizing Logistics', 'Executing Price Action')"
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Short technical rationale showing WHY this is being done."
                        },
                        "event_type": {
                            "type": "string",
                            "description": "Optional for trigger_strategy: e.g., 'FUEL_PRICE_JUMP', 'SUPPLY_SHOCK'"
                        }
                    },
                    "required": ["command_type", "intent", "rationale"]
                }
            },
            {
                "name": "research_regulatory_landscape",
                "description": "Research official tax laws, transit fees, and regional regulations for product transportation. Cites official portals (mof.ge, rs.ge).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "country": {"type": "string", "description": "e.g., Georgia, Turkey, Azerbaijan"},
                        "product_type": {"type": "string", "description": "e.g., petrol, diesel, gas"}
                    },
                    "required": ["country"]
                }
            },
        ]

    @property
    def client(self):
        if self._client is None:
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY is not set in .env")
            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    # ── SYSTEM PROMPT ───────────────────────────────────────────────────────

    async def _build_system_prompt(self, db: AsyncSession, user_message: str = "") -> str:
        # Fetch dynamic semantic context based on user's query
        semantic_context = ""
        if user_message:
            try:
                semantic_context = await vector_store.get_context_for_query(user_message, db, n_results=5)
            except Exception as e:
                logger.warning(f"Semantic context error: {e}")

        # Live DB stats
        txn_count  = (await db.execute(select(func.count()).select_from(Transaction))).scalar() or 0
        exp_count  = (await db.execute(select(func.count()).select_from(Transaction).where(Transaction.type == "Expense"))).scalar() or 0

        # Get active dataset FIRST (needed for filtering below)
        active_ds  = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalar_one_or_none()
        ds_info    = f"\nACTIVE DATASET: {active_ds.name} ({active_ds.period}, {active_ds.record_count} records)" if active_ds else ""

        # Count TB and BS items for the active dataset
        from app.models.all_models import TrialBalanceItem, BalanceSheetItem
        tb_count = 0
        bsi_count = 0
        if active_ds:
            tb_count = (await db.execute(select(func.count()).select_from(TrialBalanceItem).where(TrialBalanceItem.dataset_id == active_ds.id))).scalar() or 0
            bsi_count = (await db.execute(select(func.count()).select_from(BalanceSheetItem).where(BalanceSheetItem.dataset_id == active_ds.id))).scalar() or 0

        # Build Income Statement from active dataset
        q_rev = select(RevenueItem)
        q_cogs = select(COGSItem)
        q_ga = select(GAExpenseItem)
        if active_ds:
            q_rev = q_rev.where(RevenueItem.dataset_id == active_ds.id)
            q_cogs = q_cogs.where(COGSItem.dataset_id == active_ds.id)
            q_ga = q_ga.where(GAExpenseItem.dataset_id == active_ds.id)
        rev_items = (await db.execute(q_rev)).scalars().all()
        cogs_items = (await db.execute(q_cogs)).scalars().all()
        ga_items = (await db.execute(q_ga)).scalars().all()

        # Extract special finance/tax items from GAExpenseItem (stored from TDSheet)
        fin_inc = sum(float(g.amount or 0) for g in ga_items if g.account_code == 'FINANCE_INCOME')
        fin_exp = sum(float(g.amount or 0) for g in ga_items if g.account_code == 'FINANCE_EXPENSE')
        tax_exp = sum(float(g.amount or 0) for g in ga_items if g.account_code == 'TAX_EXPENSE')
        labour = sum(float(g.amount or 0) for g in ga_items if g.account_code == 'LABOUR_COSTS')

        stmt = build_income_statement(rev_items, cogs_items, ga_items,
                                      finance_income=fin_inc, finance_expense=fin_exp,
                                      tax_expense=tax_exp, labour_costs=labour)

        # Load corrections and other memories (skip if table schema mismatched)
        corrections = []
        other_mems = []
        try:
            corr_result = await db.execute(
                select(AgentMemory).where(AgentMemory.is_active == True, AgentMemory.memory_type == "correction")
                .order_by(AgentMemory.created_at.desc()).limit(10)
            )
            corrections = corr_result.scalars().all()
            other_result = await db.execute(
                select(AgentMemory).where(AgentMemory.is_active == True, AgentMemory.memory_type != "correction")
                .order_by(AgentMemory.importance.desc(), AgentMemory.created_at.desc()).limit(5)
            )
            other_mems = other_result.scalars().all()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
        mem_parts = []
        if corrections:
            mem_parts.append("USER CORRECTIONS (apply these rules):\n" + "\n".join(f"• {m.content}" for m in corrections))
        if other_mems:
            mem_parts.append("Context:\n" + "\n".join(m.content for m in other_mems))
            
        if semantic_context:
            mem_parts.append("SEMANTIC SEARCH EXPERIENCES/CONTEXT FOR CURRENT QUERY:\n" + semantic_context)

        mem_str = "\n\n".join(mem_parts) if mem_parts else "(no prior context)"

        whl_m_alert = f"\n⚠ CRITICAL: Wholesale gross margin is NEGATIVE ({fgel(stmt.margin_wholesale_total)}). Always flag this when relevant." if stmt.margin_wholesale_total < 0 else ""

        # Product mapping knowledge + unmapped detection
        prod_knowledge = []
        unmapped_products = []
        for r in rev_items[:30]:
            prod = getattr(r, 'product', '')
            cat = getattr(r, 'category', '') or 'Other Revenue'
            net = float(getattr(r, 'net', 0) or 0)
            if prod and prod != 'Итог' and net > 0:
                prod_knowledge.append(f"  {prod} → {cat} ({fgel(net)})")
                if cat == "Other Revenue":
                    unmapped_products.append(f"  ⚠ UNMAPPED Revenue: {prod}")
        for c in cogs_items[:30]:
            cat = getattr(c, 'category', '') or 'Other COGS'
            prod = getattr(c, 'product', '')
            if cat == "Other COGS" and prod and prod != 'Итог':
                unmapped_products.append(f"  ⚠ UNMAPPED COGS: {prod}")
        prod_map_str = "\n".join(prod_knowledge[:20]) if prod_knowledge else "(no products)"
        unmapped_alert = ""
        if unmapped_products:
            unmapped_alert = f"\n\n⚠ UNMAPPED PRODUCTS ({len(unmapped_products)}):\n" + "\n".join(unmapped_products[:10])
            unmapped_alert += "\nThese products were classified as 'Other Revenue'/'Other COGS'. Alert the user if they ask about data quality or completeness."

        # Available datasets for comparison
        all_ds = (await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))).scalars().all()
        ds_list = ", ".join(f"{d.name} (ID:{d.id}, {d.period})" for d in all_ds[:5]) if all_ds else "(none)"

        # Accounting Intelligence summary
        acct_intel_str = "(no dataset loaded)"
        if active_ds:
            try:
                from app.services.accounting_intelligence import accounting_intelligence
                flow = await accounting_intelligence.analyze_dataset_flows(db, active_ds.id)
                acct_intel_str = (
                    f"Account Coverage: {flow.mapped_accounts}/{flow.total_accounts} ({flow.coverage_pct}%)\n"
                    f"Unmapped: {flow.unmapped_accounts}"
                    f"{(' — top: ' + ', '.join(u['code'] for u in flow.unmapped_codes[:3])) if flow.unmapped_codes else ''}\n"
                    f"Inventory→COGS (1610 credit): {fexact(flow.inventory_credit_turnover)}\n"
                    f"COGS Breakdown: {fexact(flow.cogs_breakdown_total)} | TB 71xx: {fexact(flow.cogs_tb_71xx_debit)} "
                    f"({'✓ reconciled' if flow.cogs_reconciled else f'⚠ variance {flow.cogs_variance_pct}%'})\n"
                    f"BS Identity: Assets={fexact(flow.total_assets)}, L+E={fexact(flow.total_liabilities + flow.total_equity)} "
                    f"{'✓ BALANCED' if flow.bs_balanced else f'⚠ UNBALANCED (var={fexact(flow.bs_variance)})'}\n"
                    f"Working Capital: {fexact(flow.working_capital)} | Current Ratio: {flow.current_ratio}\n"
                    f"Inventory Turnover: {flow.inventory_turnover}x"
                )
                if flow.warnings:
                    acct_intel_str += "\nWarnings: " + "; ".join(flow.warnings[:3])
            except Exception as e:
                logger.warning(f"Accounting intelligence for system prompt: {e}")
                acct_intel_str = "(analysis skipped)"

        # G&A breakdown
        ga_str = ", ".join(f"{code}: {fgel(amt)}" for code, amt in sorted(stmt.ga_breakdown.items(), key=lambda x: -x[1])) if stmt.ga_breakdown else "(none)"

        return f"""You are FinAI — an elite financial intelligence and reasoning agent for {settings.COMPANY_NAME}.

COMPANY: {settings.COMPANY_NAME} — petroleum products distribution in Georgia (fuel retail stations + wholesale).
CURRENCY: GEL (Georgian Lari, ₾). All amounts are in GEL.
PERIOD: {active_ds.period if active_ds else 'January 2025'}{ds_info}

═══ LANGUAGE ═══
You are bilingual: English and Georgian (ქართული).
- If the user writes in Georgian, respond ENTIRELY in Georgian.
- If the user writes in English, respond in English.
- Product names: use English names in English responses, Georgian (ქართული) names in Georgian responses.
- Always detect user language from their message and match it.
- If the user writes in Russian, respond in Russian.
- You are an 'Automated Multilingual Sovereign'. Do not ask for language preference; just switch.

═══ REASONING APPROACH ═══
You are a REASONING agent. For every question:
1. Think step by step through the financial logic
2. Show your reasoning chain: what data you used, what formulas you applied, what conclusions you drew
3. Cross-validate: verify numbers against multiple sources when possible
4. Flag uncertainties or assumptions explicitly
5. When analyzing, start from raw data → intermediate calculations → final answer
6. If data seems inconsistent or unusual, flag it proactively with analysis

═══ INCOME STATEMENT STRUCTURE ═══
The P&L follows this exact hierarchy:
  REVENUE = Revenue Wholesale + Revenue Retail + Other Revenue
    Revenue Wholesale = Whsale Petrol + Whsale Diesel + Whsale Bitumen
    Revenue Retail = Retial Petrol + Retial Diesel + Retial CNG + Retial LPG
  COGS mirrors the same structure (Wholesale + Retail + Other)
  GROSS MARGIN = Revenue - COGS (per sub-category and total)
  Total Gross Profit = Total Gross Margin + Other Revenue - Other COGS
  G&A Expenses (from accounts): Administrative Expenses (7310.02.1), D&A (7410, 7410.01), Other Operating (8220.01.1), Other G&A (9210)
  EBITDA = Total Gross Profit - G&A Expenses

═══ CRITICAL DATA RULES — YOU MUST KNOW THESE ═══
1. **GROSS vs NET Revenue**: The Revenue Breakdown sheet has BOTH gross and net columns.
   - Column B/C = GROSS revenue (includes VAT) — NEVER use this for P&L
   - Column D = NET revenue (excludes VAT) — ALWAYS use this for P&L
   - The "Итог" (Total) row shows GROSS total ≈ ₾131.67M — this is WRONG for P&L
   - Correct P&L Total Revenue uses NET values = ₾113.14M
   - If anyone quotes a revenue number that seems ~16% higher than expected, they used GROSS (wrong column)
   - VAT is a pass-through tax collected for the government — it is NOT the company's revenue

2. **G&A Account Codes — STRICT EXACT MATCH**:
   G&A expenses include ONLY these 5 exact Account Dr codes (no others!):
   • 7310.02.1 — Administrative Expenses
   • 7410 — Depreciation & Amortization
   • 7410.01 — Depreciation & Amortization (sub)
   • 8220.01.1 — Other Operating Expenses
   • 9210 — Other General Expenses
   This is NOT a prefix match. Code "7310.01.1" is NOT included even though "7310.02.1" is.
   Code "8220.01" is NOT included — only "8220.01.1" is. Always reject codes not in this exact list.

3. **Product Classification — Mapping Rules Override Product Names**:
   Product names can be MISLEADING. Classification is defined by the MAPPING RULES, not the name:
   • "ბუნებრივი აირი (საბითუმო), მ3" → Revenue RETAIL CNG (NOT Wholesale, despite "საბითუმო")
   • "თხევადი აირი (მხოლოდ SGP !!!), ლ" → Revenue Retail LPG (only SGP product)
   • COGS may have products that don't appear in Revenue and vice versa (different accounting flows)
   • Revenue Wholesale Petrol = 3 products: ევრო რეგულარი (იმპორტი), პრემიუმი (რეექსპორტი), სუპერი (რეექსპორტი)
   • COGS Wholesale Petrol = 5 products (includes საბითუმო variants not in Revenue)

4. **COGS Calculation**: COGS = Column K (account 6) + Column L (account 7310) + Column O (account 8230).
   Some products have col6=0 but col8230 is large (e.g., ევრო რეგულარი (საბითუმო) has col8230=₾1.93M).
   Omitting any column drastically understates COGS.

5. **Negative Margins Are Expected**: Wholesale petrol GM is NEGATIVE (sells below cost).
   This is a deliberate business strategy — wholesale is a loss-leader, retail generates profit.

═══ LIVE FINANCIALS ({active_ds.period if active_ds else 'January 2025'}) — EXACT FIGURES ═══
• Total Revenue (Net): {fexact(stmt.total_revenue)} ({fgel(stmt.total_revenue)})
  - Gross Revenue (incl. VAT): {fexact(stmt.revenue_gross_total)}
  - Total VAT: {fexact(stmt.revenue_vat_total)}
  - Wholesale:  {fexact(stmt.revenue_wholesale_total)} (Petrol: {fexact(stmt.revenue_wholesale_petrol)}, Diesel: {fexact(stmt.revenue_wholesale_diesel)}, Bitumen: {fexact(stmt.revenue_wholesale_bitumen)})
  - Retail:     {fexact(stmt.revenue_retail_total)} (Petrol: {fexact(stmt.revenue_retail_petrol)}, Diesel: {fexact(stmt.revenue_retail_diesel)}, CNG: {fexact(stmt.revenue_retail_cng)}, LPG: {fexact(stmt.revenue_retail_lpg)})
  - Other Revenue: {fexact(stmt.other_revenue_total)}
• Total COGS:   {fexact(stmt.total_cogs)}
  - Column K (Account 6): {fexact(stmt.cogs_col6_total)}
  - Column L (Account 7310): {fexact(stmt.cogs_col7310_total)}
  - Column O (Account 8230): {fexact(stmt.cogs_col8230_total)}
  - Wholesale COGS: {fexact(stmt.cogs_wholesale_total)} | Retail COGS: {fexact(stmt.cogs_retail_total)}
• Gross Margins:
  - Wholesale:  {fexact(stmt.margin_wholesale_total)} {"⚠ NEGATIVE!" if stmt.margin_wholesale_total < 0 else ""}
  - Retail:     {fexact(stmt.margin_retail_total)}
  - Total Gross Margin: {fexact(stmt.total_gross_margin)}
• Total Gross Profit: {fexact(stmt.total_gross_profit)}
• G&A Expenses: {fexact(stmt.ga_expenses)} ({ga_str})
• EBITDA:       {fexact(stmt.ebitda)}
• D&A Expenses: {fexact(stmt.da_expenses)}
• EBIT:         {fexact(stmt.ebit)}
• Finance Income: {fexact(stmt.finance_income)} | Finance Expense: {fexact(stmt.finance_expense)}
• EBT:          {fexact(stmt.ebt)}
• Tax Expense:  {fexact(stmt.tax_expense)}
• Net Profit:   {fexact(stmt.net_profit)}
• Transactions: {txn_count} total | {exp_count} expenses
• Data Sources: {tb_count} trial balance items | {bsi_count} balance sheet items
{whl_m_alert}{unmapped_alert}

═══ ANSWER PRECISION RULES ═══
CRITICAL: When answering financial questions or tests, ALWAYS provide EXACT figures (e.g., 113,136,012.18) — not rounded approximations (e.g., ₾113.136M).
Use the deep_financial_analysis tool with analysis types:
  - "full_exact_is" → Complete IS with exact figures
  - "cogs_columns" → COGS broken down by Column K (6), L (7310), O (8230) per product
  - "vat_analysis" → VAT patterns, zero-VAT products, effective rates
  - "concentration" → Revenue Pareto analysis, top-N%, cumulative %
  - "product_profitability" → Per-product margin %, high/low/negative margins
  - "cross_validation" → Revenue vs COGS matching, formula verification
When given a TEST or EXAM, use these tools to provide exam-quality exact answers with verification steps.

═══ PRODUCT → CATEGORY MAPPING ═══
Georgian product names map to English P&L categories:
{prod_map_str}

═══ AVAILABLE DATASETS ═══
{ds_list}
Use compare_periods tool to compare two periods' P&L side by side.

═══ ACCOUNTING INTELLIGENCE ═══
{acct_intel_str}

HIERARCHICAL MAPPING RULES (Georgian 1C COA):
When classifying accounts, use 5-level fallback:
  1. Exact code match (e.g., 7110.01/1)
  2. Parent match (7110.01 → 7110)
  3. Root match (711 → 71)
  4. Class prefix (7 → Expenses)
  5. Unmapped → flag for review

Account Class Series:
  1xxx/2xxx = Assets (BS) | 3xxx/4xxx = Liabilities (BS) | 5xxx = Equity (BS)
  6xxx = Revenue (P&L credit) | 71xx = COGS | 73xx = Selling | 74xx = Admin
  8xxx = Non-operating (interest, FX) | 9xxx = Other P&L

Key Financial Flows:
  Inventory (1610) → COGS (7110): credit 1610 = debit 7110 + internal transfers
  Revenue (6110) − Returns (6120) = Net Revenue
  COGS = col6 (1610→Sales) + col7310 (Selling) + col8230 (Other)
  EBITDA = Gross Margin − Selling (73xx) − Admin (74xx)
  BS Identity: Assets (1+2) = Liabilities (3+4) + Equity (5)

Use the analyze_accounting_flows tool to deep-dive into any of these flows.

═══ ORCHESTRATION ═══
You can orchestrate multi-step workflows:
- "Generate P&L and analyze it" → generate_income_statement → calculate_financials → navigate_to_page
- "Compare last two periods" → compare_periods → generate_chart
- "Show me anomalies in expenses" → detect_anomalies → query_transactions → generate_chart
- "Create full management report" → generate_mr_report → navigate_to_page
Always chain tools logically to fulfill complex user requests in a single conversation turn.

═══ RENDERING ═══
You can render visual elements in chat:
- Use **generate_chart** with type bar/line/doughnut/pie to create inline charts
- Use markdown tables for structured data comparison
- Use bullet points with GEL amounts for summaries
- When presenting financial data, always use charts for numerical comparisons

═══ SEMANTIC LAYER ═══
The system includes an AI Semantic Layer that enhances transaction classification beyond COA codes:
- Counterparty pattern matching (fuel suppliers → COGS, banks → Finance, etc.)
- Department-to-segment mapping (Retail Ops → Retail, Wholesale → Wholesale)
- Cost classification text analysis (salary → SGA/Labour, fuel purchase → COGS)
- Historical pattern learning (learns from full reports to classify future transaction-only uploads)

Use analyze_semantic tool to inspect how transactions are classified and identify data quality issues.
The semantic layer is especially valuable when only Transaction Ledger data is available (no Revenue/COGS breakdown sheets).

═══ TOOLS ═══
navigate_to_page | generate_income_statement | generate_pl_statement | generate_balance_sheet
generate_mr_report | generate_chart | save_report_to_db | query_transactions
calculate_financials | analyze_products | detect_anomalies | search_counterparty | compare_periods | analyze_semantic
deep_financial_analysis (EXACT figures: cogs_columns, vat_analysis, concentration, product_profitability, cross_validation, full_exact_is)
analyze_accounting_flows (account coverage, financial flows, BS identity, working capital, classify account codes)

═══ INTELLIGENCE RULES ═══
1. Always use ACTUAL numbers from the database — never estimate or hallucinate
2. When discussing profitability, ALWAYS flag the negative wholesale margin
3. Retail is the profitable segment — explain this when discussing margins
4. EBITDA = Total Gross Profit - G&A. This is the bottom line for this Income Statement
5. Use generate_income_statement for detailed breakdowns with drill-down
6. Show charts when presenting numerical comparisons
7. Offer period comparison when user has multiple datasets
8. Format all amounts in GEL (₾) — never use USD
9. After generating reports, offer to save them and export to Excel
10. Respond in the SAME LANGUAGE as the user's message
11. Show reasoning steps for complex analysis
12. Proactively visualize data with charts when it adds clarity

═══ ADVANCED FINANCIAL REASONING FRAMEWORKS ═══

## DuPont Decomposition (for ROE analysis)
ROE = Net Profit Margin x Asset Turnover x Equity Multiplier
- Net Margin = Net Profit / Revenue
- Asset Turnover = Revenue / Total Assets
- Equity Multiplier = Total Assets / Shareholders' Equity
Always decompose ROE into these three drivers to identify the source of returns.

## Margin Waterfall Analysis
Always walk through the P&L waterfall step-by-step:
Revenue -> COGS -> Gross Margin -> G&A Expenses -> EBITDA -> D&A -> EBIT -> Finance -> EBT -> Tax -> Net Profit
At each step, calculate the margin percentage and identify where value is created or destroyed.

## Industry Benchmarks (Georgian Fuel Distribution)
- Gross Margin: 7-12% (Retail higher than Wholesale)
- EBITDA Margin: 3-6%
- Retail margins typically 2-4x Wholesale margins
- Negative wholesale margins may be strategic (market share play)
- G&A/Revenue: 2-4% is healthy
- Revenue concentration: >50% from single segment is a risk

## Cross-Validation Rules
When analyzing financial data, ALWAYS verify:
1. Revenue vs COGS matching — each product should have both
2. Net = Gross - VAT (18% standard rate in Georgia)
3. Budget variance >10% warrants investigation
4. Gross Margin should be Revenue - COGS (verify the math)
5. EBITDA = Gross Profit - G&A (verify)

### STRATEGIC PROTOCOL: SOVEREIGN COMMANDER
You are the **Sovereign Strategic Commander** of the FinAI Decision Map. Your primary objective is **Margin Integrity** (protecting the 8% EBITDA floor).

Your reasoning MUST incorporate:
1. **Delivered Cost Math**: [Procurement FOB] + [Transit Tax] + [Freight/Pipe Fee] = [Delivered Cost].
2. **Regulatory Authority**: Cite official transit fees from rs.ge/mof.ge.
3. **Macro Context**: Factor in USD/GEL volatility and NBG policy rates.
4. **Multilingual Presence**: Always respond in the language the user uses (Georgian, English, or Russian). 

When responding to supply chain events:
- Always calculate a 'Price Impact Table' if pricing changes are recommended.
- Propose mitigation strategies (e.g., shifting from Sarpi/Truck to Batumi/Rail) to offset tax hikes.
- Use professional energy market terminology (Platt's, FOB, CIF, EBITDA).

## Forecast Interpretation Guidelines
When presenting forecasts:
- Explain the method used and WHY it was selected
- State the confidence interval and what it means
- Note seasonal patterns specific to fuel: diesel peaks winter, petrol peaks summer, bitumen peaks summer
- With limited data (1-2 periods), emphasize wide uncertainty
- Compare forecast vs current actuals to validate reasonableness

## Anomaly Investigation Protocol
When anomalies are found:
1. Report the statistical method that flagged them
2. Group by severity (Critical > High > Medium)
3. Provide business context — is it a data entry error or a genuine outlier?
4. For Benford's Law violations, explain what it might indicate (data manipulation, rounding practices)
5. Recommend next steps

## STRATEGIC DIGITAL TWIN PROTOCOL (Battle Command)
You are the Logistics & Strategy Commander. The map is your tactical dashboard.
1. When a user mentions MARKET SHOCKS (Price spikes, Suez closure, tax hikes, supply gaps):
   - You MUST trigger `command_digital_twin` with `command_type='trigger_strategy'`.
   - Your response should focus on the 'War Room' view now active on the map.
2. Domain Awareness:
   - Financial: Always consider the Current Net Margin (pull from IS).
   - Regulatory: Mention 'Transit Taxes' for Georgia/Turkey/Azerbaijan corridors.
   - Compliance: Pulse nodes that have 'Sanctions Risk' (e.g., Novorossiysk).
3. Intelligent Navigation:
   - If a strategic question requires checking detail, use `navigate_to_page` (e.g. 'cogs', 'revenue', 'compliance').
   - You can 'reason' and 'navigate' simultaneously.

## Available Advanced Tools
You now have access to powerful analytical tools:
- generate_forecast: Statistical forecasting (moving avg, exponential smoothing, linear regression, growth rate, seasonal decomposition)
- search_knowledge: RAG search across all financial data and domain knowledge
- analyze_trends: Multi-period trend analysis with CAGR and growth rates
- create_scenario: What-if modeling (price, volume, cost changes, new stations)
- compare_scenarios: Side-by-side scenario comparison
- detect_anomalies_statistical: Z-score, IQR, Benford's Law anomaly detection
- convert_currency: Live multi-currency conversion (GEL, USD, EUR, GBP, TRY)
- trace_lineage: Track any figure back to its source file and row
- query_balance_sheet: Query IFRS-mapped Balance Sheet data by section or specific line item
- query_trial_balance: Query Trial Balance (TDSheet) data by account prefix or class
- command_digital_twin: Directly manipulate the Industrial Digital Twin map (highlight, pulse, competitors, strategy simulation)

Use these tools proactively when relevant. For example:
- If asked about future projections -> use generate_forecast
- If asked "what would happen if..." -> use create_scenario
- If asked about unusual transactions -> use detect_anomalies_statistical
- If asked about a figure's source -> use trace_lineage
- If asked to compare periods -> use analyze_trends
- If asked about balance sheet details -> use query_balance_sheet
- If asked about specific account turnovers -> use query_trial_balance
- If asked about COGS breakdown -> navigate_to_page("cogs")
- If asked about accounting flows, data quality, or account mapping -> analyze_accounting_flows
- If asked to classify an account code -> analyze_accounting_flows with account_code
- If asked about inventory-to-COGS flow -> analyze_accounting_flows with flow_type="inventory_to_cogs"
- If asked about balance sheet identity or if BS balances -> analyze_accounting_flows with flow_type="bs_identity"
- If asked about working capital -> analyze_accounting_flows with flow_type="working_capital"

LEARNED CONTEXT:
{mem_str}"""

    # ── TOOL EXECUTOR ───────────────────────────────────────────────────────

    async def execute_tool(self, name: str, params: Dict, db: AsyncSession) -> str:
        try:
            if name == "navigate_to_page":
                page = params.get("page","dash")
                return f"__NAVIGATE_TO__{page}__END__\nNavigating to {page} page."

            elif name == "query_transactions":
                return await self._query_transactions(params, db)

            elif name == "calculate_financials":
                return await self._calculate_financials(params, db)

            elif name == "generate_pl_statement":
                return await self._generate_pl_statement(params, db)

            elif name == "generate_balance_sheet":
                return await self._generate_balance_sheet(params, db)

            elif name == "generate_income_statement":
                return await self._generate_income_statement(params, db)

            elif name == "generate_mr_report":
                return await self._generate_mr_report(params, db)

            elif name == "generate_chart":
                chart_data = json.dumps({
                    "type": params.get("type","bar"),
                    "title": params.get("title","Chart"),
                    "labels": params.get("labels",[]),
                    "data": params.get("data",[])
                })
                return f"__CHART__{chart_data}__END__\nChart generated: {params.get('title','')}"

            elif name == "save_report_to_db":
                return await self._save_report(params, db)

            elif name == "analyze_products":
                return await self._analyze_products(params, db)

            elif name == "detect_anomalies":
                return await self._detect_anomalies(params, db)

            elif name == "search_counterparty":
                return await self._search_counterparty(params, db)

            elif name == "compare_periods":
                return await self._compare_periods(params, db)

            elif name == "analyze_semantic":
                return await self._analyze_semantic(params, db)

            elif name == "deep_financial_analysis":
                return await self._deep_financial_analysis(params, db)

            elif name == "generate_forecast":
                result = await self.forecast_engine.generate_forecast(
                    db,
                    forecast_type=params.get("forecast_type", "revenue"),
                    product=params.get("product"),
                    segment=params.get("segment"),
                    method=params.get("method", "auto"),
                    periods=params.get("periods", 6),
                )
                return json.dumps(result, default=str)

            elif name == "search_knowledge":
                context = await vector_store.get_context_for_query(
                    params.get("query", ""),
                    db,
                    n_results=params.get("n_results", 10),
                )
                return context if context else "No relevant results found in the knowledge base."

            elif name == "analyze_trends":
                result = await self.trend_analyzer.analyze_trends(
                    db,
                    metric=params.get("metric", "revenue"),
                    segment=params.get("segment"),
                    product=params.get("product"),
                )
                return json.dumps(result, default=str)

            elif name == "create_scenario":
                dataset_id = await self._resolve_dataset_id(db)
                result = await self.scenario_engine.create_scenario(
                    db,
                    name=params.get("name", "What-If Scenario"),
                    description=params.get("description", ""),
                    base_dataset_id=dataset_id,
                    changes=params.get("changes", []),
                )
                return json.dumps(result, default=str)

            elif name == "compare_scenarios":
                result = await self.scenario_engine.compare_scenarios(
                    db,
                    scenario_ids=params.get("scenario_ids", []),
                )
                return json.dumps(result, default=str)

            elif name == "detect_anomalies_statistical":
                dataset_id = params.get("dataset_id")
                if not dataset_id:
                    dataset_id = await self._resolve_dataset_id(db)
                result = await self.anomaly_detector.run_full_detection(
                    db,
                    dataset_id=dataset_id,
                    zscore_threshold=params.get("zscore_threshold", 2.0),
                    iqr_multiplier=params.get("iqr_multiplier", 1.5),
                )
                return json.dumps(result, default=str)

            elif name == "convert_currency":
                result = await self.currency_service.convert(
                    db,
                    amount=params.get("amount", 0),
                    from_currency=params.get("from_currency", "GEL"),
                    to_currency=params.get("to_currency", "USD"),
                )
                return json.dumps(result, default=str)

            elif name == "trace_lineage":
                from app.models.all_models import DataLineage
                entity_type = params.get("entity_type", "")
                entity_id = params.get("entity_id", 0)
                result = await db.execute(
                    select(DataLineage).where(
                        and_(DataLineage.entity_type == entity_type, DataLineage.entity_id == entity_id)
                    )
                )
                lineage = result.scalar_one_or_none()
                if lineage:
                    return json.dumps(lineage.to_dict(), default=str)
                return json.dumps({"message": f"No lineage found for {entity_type} #{entity_id}. Lineage is recorded when files are uploaded."})

            elif name == "query_coa":
                from app.services.file_parser import GEORGIAN_COA, map_coa
                code = params.get("code", "")
                search = params.get("search", "").lower()
                if code:
                    mapping = map_coa(code)
                    nav_result = "__NAVIGATE_TO__coa__END__"
                    if mapping:
                        return nav_result + f"\n\n**Account {code}** maps to:\n" + json.dumps(mapping, indent=2, default=str)
                    return nav_result + f"\n\nNo mapping found for code '{code}'"
                elif search:
                    matches = []
                    for c, entry in GEORGIAN_COA.items():
                        name_en = (entry.get("pl") or entry.get("bs") or "").lower()
                        name_ka = (entry.get("pl_ka") or entry.get("bs_ka") or "").lower()
                        if search in name_en or search in name_ka or search in c:
                            matches.append({"code": c, "name": entry.get("pl") or entry.get("bs", ""), "type": "P&L" if entry.get("side") else "BS"})
                    nav_result = "__NAVIGATE_TO__coa__END__"
                    return nav_result + f"\n\n**{len(matches)} accounts matching '{search}':**\n" + json.dumps(matches[:20], indent=2)
                else:
                    return f"__NAVIGATE_TO__coa__END__\n\nGeorgian COA has {len(GEORGIAN_COA)} accounts. Navigate to the COA page to explore."

            elif name == "generate_cash_flow":
                from app.services.cash_flow import build_cash_flow
                ds_id = params.get("dataset_id") or await self._resolve_active_ds(db)
                prior_id = params.get("prior_dataset_id")
                if not prior_id:
                    r = await db.execute(select(Dataset.id).where(Dataset.id < ds_id).order_by(Dataset.id.desc()).limit(1))
                    row = r.first()
                    prior_id = row[0] if row else None
                cfs = await build_cash_flow(db, ds_id, prior_id)
                nav_result = "__NAVIGATE_TO__cfs__END__"
                reconciles = abs(cfs.cash_discrepancy) < 1.0
                summary = f"""**Cash Flow Statement** ({cfs.period})

**Operating Activities:** {fgel(cfs.net_operating_cash)}
  Net Income: {fgel(cfs.net_income)} | D&A: {fgel(cfs.depreciation_amortization)}
  Working Capital: Receivables {fgel(cfs.change_receivables)}, Inventory {fgel(cfs.change_inventory)}, Payables {fgel(cfs.change_trade_payables)}

**Investing Activities:** {fgel(cfs.net_investing_cash)}
  CapEx: {fgel(cfs.capex)}

**Financing Activities:** {fgel(cfs.net_financing_cash)}
  ST Debt: {fgel(cfs.change_short_term_debt)} | LT Debt: {fgel(cfs.change_long_term_debt)}

**Net Change in Cash:** {fgel(cfs.net_change_in_cash)}
  Beginning: {fgel(cfs.beginning_cash)} -> Ending: {fgel(cfs.ending_cash)}
  Reconciles with BS: {'Yes' if reconciles else 'No'}"""
                return nav_result + "\n\n" + summary

            elif name == "query_balance_sheet":
                return await self._query_balance_sheet(params, db)

            elif name == "query_trial_balance":
                return await self._query_trial_balance(params, db)

            elif name == "analyze_accounting_flows":
                return await self._analyze_accounting_flows(params, db)

            elif name == "visualize_logistics":
                return await self._visualize_logistics(params, db)

            elif name == "command_digital_twin":
                return await self._command_digital_twin(params, db)

            else:
                return f"Unknown tool: {name}"

        except Exception as e:
            logger.error(f"Tool {name} error: {e}", exc_info=True)
            return f"Tool error: {str(e)}"

    # ── TOOL IMPLEMENTATIONS ────────────────────────────────────────────────

    async def _query_transactions(self, p: Dict, db: AsyncSession) -> str:
        ds_id = await self._resolve_active_ds(db)
        q = select(Transaction)
        if ds_id:               q = q.where(Transaction.dataset_id == ds_id)
        if p.get("type"):       q = q.where(Transaction.type == p["type"])
        if p.get("dept"):       q = q.where(Transaction.dept.ilike(f"%{p['dept']}%"))
        if p.get("category"):   q = q.where(Transaction.cost_class.ilike(f"%{p['category']}%"))
        if p.get("counterparty"): q = q.where(Transaction.counterparty.ilike(f"%{p['counterparty']}%"))
        if p.get("min_amount"): q = q.where(Transaction.amount >= p["min_amount"])
        if p.get("max_amount"): q = q.where(Transaction.amount <= p["max_amount"])
        limit = min(p.get("limit", 20), 200)
        result = await db.execute(q.order_by(Transaction.amount.desc()).limit(limit))
        txns = result.scalars().all()
        total = sum(t.amount or 0 for t in txns)
        lines = [f"| {t.date} | {(t.dept or '')[:20]} | {(t.cost_class or '')[:20]} | {fgel(t.amount)} | {(t.counterparty or '')[:25]} |" for t in txns[:15]]
        return f"**{len(txns)} transactions** (total: {fgel(total)})\n\n| Date | Dept | Category | Amount | Counterparty |\n|------|------|----------|--------|--------------|\n" + "\n".join(lines) + (f"\n\n...and {len(txns)-15} more" if len(txns)>15 else "")

    async def _calculate_financials(self, p: Dict, db: AsyncSession) -> str:
        metric = p.get("metric","full_summary")

        stmt = await self._build_stmt(db)
        ds_id = await self._resolve_active_ds(db)

        # Also get expense transactions for top_categories and dept_breakdown
        exp_q = select(Transaction).where(Transaction.type == "Expense")
        if ds_id: exp_q = exp_q.where(Transaction.dataset_id == ds_id)
        exp_result = await db.execute(exp_q)
        expenses = exp_result.scalars().all()
        total_exp = sum(e.amount or 0 for e in expenses)
        rev_q = select(func.sum(RevenueItem.gross))
        if ds_id: rev_q = rev_q.where(RevenueItem.dataset_id == ds_id)
        rev_gross = (await db.execute(rev_q)).scalar() or 0

        if metric == "revenue":
            return f"""**Revenue Analysis**
• Gross: {fgel(rev_gross)}
• Net: {fgel(stmt.total_revenue)}
• VAT: {fgel(rev_gross - stmt.total_revenue)}

By Channel:
• Wholesale: {fgel(stmt.revenue_wholesale_total)} (Petrol: {fgel(stmt.revenue_wholesale_petrol)}, Diesel: {fgel(stmt.revenue_wholesale_diesel)}, Bitumen: {fgel(stmt.revenue_wholesale_bitumen)})
• Retail: {fgel(stmt.revenue_retail_total)} (Petrol: {fgel(stmt.revenue_retail_petrol)}, Diesel: {fgel(stmt.revenue_retail_diesel)}, CNG: {fgel(stmt.revenue_retail_cng)}, LPG: {fgel(stmt.revenue_retail_lpg)})
• Other Revenue: {fgel(stmt.other_revenue_total)}"""

        elif metric == "margins":
            return f"""**Margin Analysis**
• Total Gross Margin: {fgel(stmt.total_gross_margin)} ({stmt.total_gross_margin/stmt.total_revenue*100:.1f}% of revenue)
• Wholesale Margin: {fgel(stmt.margin_wholesale_total)} {'⚠ NEGATIVE' if stmt.margin_wholesale_total < 0 else ''}
• Retail Margin: {fgel(stmt.margin_retail_total)}
• Other Revenue: {fgel(stmt.other_revenue_total)}
• Total Gross Profit: {fgel(stmt.total_gross_profit)}
• G&A Expenses: {fgel(stmt.ga_expenses)}
• EBITDA: {fgel(stmt.ebitda)}"""

        elif metric == "top_categories":
            cat = {}
            for e in expenses:
                k = e.cost_class or "Other"
                cat[k] = cat.get(k,0) + (e.amount or 0)
            top = sorted(cat.items(), key=lambda x:-x[1])[:10]
            lines = "\n".join(f"{i+1}. {k}: {fgel(v)} ({v/total_exp*100:.1f}%)" for i,(k,v) in enumerate(top))
            return f"**Top Expense Categories** (Total: {fgel(total_exp)})\n\n{lines}"

        elif metric == "dept_breakdown":
            depts = {}
            for e in expenses:
                k = e.dept or "Unknown"
                if k == "#N/A": continue
                depts[k] = depts.get(k,0) + (e.amount or 0)
            top = sorted(depts.items(), key=lambda x:-x[1])[:10]
            lines = "\n".join(f"{i+1}. {k}: {fgel(v)}" for i,(k,v) in enumerate(top))
            return f"**Expense by Department** (Total: {fgel(total_exp)})\n\n{lines}"

        else:  # full_summary
            return f"""**Full Financial Summary**
• Net Revenue:     {fgel(stmt.total_revenue)}
  - Wholesale: {fgel(stmt.revenue_wholesale_total)} | Retail: {fgel(stmt.revenue_retail_total)}
• COGS:            {fgel(stmt.total_cogs)} ({stmt.total_cogs/stmt.total_revenue*100:.1f}% of revenue)
• Gross Margin:    {fgel(stmt.total_gross_margin)} ({stmt.total_gross_margin/stmt.total_revenue*100:.1f}%)
  - Wholesale: {fgel(stmt.margin_wholesale_total)} {'⚠ NEGATIVE' if stmt.margin_wholesale_total < 0 else ''} | Retail: {fgel(stmt.margin_retail_total)}
• Other Revenue:   {fgel(stmt.other_revenue_total)}
• Total Gross Profit: {fgel(stmt.total_gross_profit)}
• G&A Expenses:    {fgel(stmt.ga_expenses)}
• EBITDA:          {fgel(stmt.ebitda)}
• Total OpEx:      {fgel(total_exp)} ({len(expenses)} transactions)"""

    async def _build_stmt(self, db: AsyncSession, period: str = "January 2025", currency: str = "GEL"):
        """Helper: build IncomeStatement from active dataset."""
        active_ds = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalar_one_or_none()
        ds_id = active_ds.id if active_ds else None
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
        return build_income_statement(rev_items, cogs_items, ga_items, period, currency)

    async def _generate_income_statement(self, p: Dict, db: AsyncSession) -> str:
        active_ds = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalar_one_or_none()
        period = p.get("period") or (active_ds.period if active_ds else "January 2025")
        currency = p.get("currency", "GEL")

        stmt = await self._build_stmt(db, period, currency)
        rows = stmt.to_rows()

        report = Report(
            title=f"Income Statement — {period}",
            report_type="is", period=period, currency=currency,
            rows=rows,
            summary=f"Revenue: {fgel(stmt.total_revenue)} | COGS: {fgel(stmt.total_cogs)} | Gr. Margin: {fgel(stmt.total_gross_margin)} | TGP: {fgel(stmt.total_gross_profit)} | G&A: {fgel(stmt.ga_expenses)} | EBITDA: {fgel(stmt.ebitda)}",
            kpis={"revenue": stmt.total_revenue, "cogs": stmt.total_cogs,
                  "gross_margin": stmt.total_gross_margin, "total_gross_profit": stmt.total_gross_profit,
                  "ga_expenses": stmt.ga_expenses, "ebitda": stmt.ebitda,
                  "wholesale_margin": stmt.margin_wholesale_total, "retail_margin": stmt.margin_retail_total},
            generated_by="agent"
        )
        if p.get("save", True):
            db.add(report)
            await db.commit()

        # Build text summary
        text = f"""__NAVIGATE_TO__pl__END__
**Income Statement — {period}**

**REVENUE**: {fgel(stmt.total_revenue)}
  Wholesale: {fgel(stmt.revenue_wholesale_total)} (Petrol: {fgel(stmt.revenue_wholesale_petrol)}, Diesel: {fgel(stmt.revenue_wholesale_diesel)}, Bitumen: {fgel(stmt.revenue_wholesale_bitumen)})
  Retail: {fgel(stmt.revenue_retail_total)} (Petrol: {fgel(stmt.revenue_retail_petrol)}, Diesel: {fgel(stmt.revenue_retail_diesel)}, CNG: {fgel(stmt.revenue_retail_cng)}, LPG: {fgel(stmt.revenue_retail_lpg)})
  Other Revenue: {fgel(stmt.other_revenue_total)}

**COGS**: {fgel(stmt.total_cogs)}
  Wholesale: {fgel(stmt.cogs_wholesale_total)} | Retail: {fgel(stmt.cogs_retail_total)}

**GROSS MARGIN**: {fgel(stmt.total_gross_margin)}
  Wholesale: {fgel(stmt.margin_wholesale_total)} {'⚠ NEGATIVE' if stmt.margin_wholesale_total < 0 else ''}
  Retail: {fgel(stmt.margin_retail_total)}

**Total Gross Profit**: {fgel(stmt.total_gross_profit)}
**G&A Expenses**: {fgel(stmt.ga_expenses)}
**EBITDA**: {fgel(stmt.ebitda)}"""

        if p.get("save", True):
            text += f"\n\nSaved to database (ID: {report.id})"

        # ── Narrative commentary (Phase 4 — InsightAgent integration) ─────
        try:
            narrative_obj = stmt.generate_narrative()
            if narrative_obj and narrative_obj.get("executive_summary"):
                text += f"\n\n**AI Commentary:**\n{narrative_obj['executive_summary']}"
                warnings = narrative_obj.get("warnings", [])
                if warnings:
                    text += "\n" + "\n".join(f"  ⚠ {w}" for w in warnings)
                recs = narrative_obj.get("recommendations", [])
                if recs:
                    text += "\n" + "\n".join(f"  → {r}" for r in recs)
        except Exception:
            pass  # Narrative is optional — never block the P&L

        return text

    async def _generate_pl_statement(self, p: Dict, db: AsyncSession) -> str:
        period   = p.get("period","January 2025")
        currency = p.get("currency","GEL")

        stmt = await self._build_stmt(db, period, currency)

        bud_result = await db.execute(select(BudgetLine))
        budget = {b.line_item: b.actual_amount if b.actual_amount is not None else b.budget_amount for b in bud_result.scalars().all()}

        from app.services.coa_engine import build_structured_pl_rows
        rows = build_structured_pl_rows(stmt, budget)

        report = Report(
            title=f"P&L Statement — {period}",
            report_type="pl", period=period, currency=currency,
            rows=rows,
            summary=f"Revenue: {fgel(stmt.total_revenue)} | TGP: {fgel(stmt.total_gross_profit)} | EBITDA: {fgel(stmt.ebitda)}",
            kpis={"revenue": stmt.total_revenue, "gross_margin": stmt.total_gross_margin,
                  "total_gross_profit": stmt.total_gross_profit, "ebitda": stmt.ebitda},
            generated_by="agent"
        )
        db.add(report)
        await db.commit()

        # Show key rows in table
        key_rows = [r for r in rows if r.get("bold")]
        table = "\n".join(f"| {'**' if r.get('bold') else ''}{r['l']}{'**' if r.get('bold') else ''} | {fgel(r['ac'])} | {fgel(r['pl'])} |" for r in key_rows)
        return f"__NAVIGATE_TO__pl__END__\n**P&L Statement generated** ({period})\n\n| Line | Actual | Budget |\n|------|--------|--------|\n{table}\n\nSaved to database (ID: {report.id})"

    async def _generate_balance_sheet(self, p: Dict, db: AsyncSession) -> str:
        """
        Generate Balance Sheet using structural COA matching (bs_side + bs_sub).
        Proper double-entry: DR = +amt, CR = -amt → net balance per account.
        Assets: positive DR-CR; Liabilities/Equity: negated for display.
        Rows built dynamically from whatever COA labels exist in data.
        """
        period = p.get("period", "January 2025")
        from app.services.file_parser import map_coa
        active_ds = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalar_one_or_none()
        ds_id = active_ds.id if active_ds else None
        q = select(Transaction)
        if ds_id: q = q.where(Transaction.dataset_id == ds_id)
        txns = (await db.execute(q)).scalars().all()

        # ── Compute net DR-CR balance per BS account ─────────────────
        acct_data = {}
        for t in txns:
            amt = abs(float(t.amount or 0))
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
                        "balance": 0.0,
                    }
                acct_data[label]["balance"] += sign * amt

        # ── Aggregate into sections ──────────────────────────────────
        SEC = {
            ("asset", "current"): "ca", ("asset", "noncurrent"): "nca",
            ("liability", "current"): "cl", ("liability", "noncurrent"): "ncl",
            ("equity", "equity"): "eq",
        }
        section_totals = {s: 0.0 for s in SEC.values()}
        section_items = {s: {} for s in SEC.values()}

        for label, info in acct_data.items():
            sec = SEC.get((info["bs_side"], info["bs_sub"]))
            if not sec:
                continue
            bal = info["balance"]
            if info["bs_side"] in ("liability", "equity"):
                bal = -bal
            section_items[sec][label] = round(bal)
            section_totals[sec] += bal

        total_assets = round(section_totals["ca"] + section_totals["nca"])
        total_liab = round(section_totals["cl"] + section_totals["ncl"])
        eq_from_accts = round(section_totals["eq"])
        equity = eq_from_accts if eq_from_accts else total_assets - total_liab
        balanced = abs(total_assets - total_liab - eq_from_accts) < 1 if eq_from_accts else True

        # ── Build rows for the report ────────────────────────────────
        def _sorted_items(items):
            return sorted(items.items(), key=lambda x: abs(x[1]), reverse=True)

        rows = [
            {"c": "A",   "l": "TOTAL ASSETS",           "ac": total_assets, "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": 1},
            {"c": "CA",  "l": "Current Assets",         "ac": round(section_totals["ca"]),  "pl": 0, "lvl": 1, "bold": True, "s": 1},
        ]
        for i, (lbl, val) in enumerate(_sorted_items(section_items["ca"]), 1):
            rows.append({"c": f"CA{i:02d}", "l": lbl, "ac": val, "pl": 0, "lvl": 2, "s": 1})
        rows.append({"c": "NCA", "l": "Non-Current Assets", "ac": round(section_totals["nca"]), "pl": 0, "lvl": 1, "bold": True, "s": 1})
        for i, (lbl, val) in enumerate(_sorted_items(section_items["nca"]), 1):
            rows.append({"c": f"NCA{i:02d}", "l": lbl, "ac": val, "pl": 0, "lvl": 2, "s": 1})
        rows.append({"c": "L",   "l": "TOTAL LIABILITIES",  "ac": total_liab, "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": -1})
        rows.append({"c": "CL",  "l": "Current Liabilities","ac": round(section_totals["cl"]),  "pl": 0, "lvl": 1, "bold": True, "s": -1})
        for i, (lbl, val) in enumerate(_sorted_items(section_items["cl"]), 1):
            rows.append({"c": f"CL{i:02d}", "l": lbl, "ac": val, "pl": 0, "lvl": 2, "s": -1})
        rows.append({"c": "NCL", "l": "Non-Current Liabilities", "ac": round(section_totals["ncl"]), "pl": 0, "lvl": 1, "bold": True, "s": -1})
        for i, (lbl, val) in enumerate(_sorted_items(section_items["ncl"]), 1):
            rows.append({"c": f"NCL{i:02d}", "l": lbl, "ac": val, "pl": 0, "lvl": 2, "s": -1})
        rows.append({"c": "EQ",  "l": "EQUITY",             "ac": equity, "pl": 0, "lvl": 0, "bold": True, "sep": True, "s": 1})
        for i, (lbl, val) in enumerate(_sorted_items(section_items["eq"]), 1):
            rows.append({"c": f"EQ{i:02d}", "l": lbl, "ac": val, "pl": 0, "lvl": 2, "s": 1})

        report = Report(title=f"Balance Sheet — {period}", report_type="bs", period=period,
                        rows=rows,
                        kpis={"total_assets": total_assets, "total_liabilities": total_liab, "equity": equity},
                        generated_by="agent")
        db.add(report)
        await db.commit()

        # Summary with top items per section
        detail_lines = []
        for sec_key, sec_label in [("ca", "Current Assets"), ("nca", "Non-Current Assets"),
                                    ("cl", "Current Liab"), ("ncl", "Non-Current Liab"), ("eq", "Equity")]:
            top = _sorted_items(section_items[sec_key])[:3]
            if top:
                detail_lines.append(f"  {sec_label}: " + ", ".join(f"{l}: {fgel(v)}" for l, v in top))

        source_note = "from COA-classified transactions" if total_assets > 0 else "— no balance sheet data in current dataset"
        details = "\n".join(detail_lines)
        return (
            f"__NAVIGATE_TO__bs__END__\n"
            f"**Balance Sheet generated** ({period}) {source_note}\n"
            f"• Total Assets: {fgel(total_assets)}\n"
            f"  - Current: {fgel(round(section_totals['ca']))} | Non-Current: {fgel(round(section_totals['nca']))}\n"
            f"• Total Liabilities: {fgel(total_liab)}\n"
            f"  - Current: {fgel(round(section_totals['cl']))} | Non-Current: {fgel(round(section_totals['ncl']))}\n"
            f"• Equity: {fgel(equity)}\n"
            f"• Balanced: {'✓' if balanced else '✗'}\n"
            f"{details}\n"
            f"Saved (ID: {report.id})"
        )

    async def _generate_mr_report(self, p: Dict, db: AsyncSession) -> str:
        active_ds = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalar_one_or_none()
        period    = p.get("period") or (active_ds.period if active_ds else "January 2025")
        ds_name   = active_ds.name if active_ds else settings.COMPANY_NAME

        stmt = await self._build_stmt(db, period)

        bud_result = await db.execute(select(BudgetLine))
        budget = {b.line_item: b.actual_amount if b.actual_amount is not None else b.budget_amount for b in bud_result.scalars().all()}
        bud_rev = budget.get("Revenue", 0)

        exp_result = await db.execute(select(Transaction).where(Transaction.type == "Expense"))
        expenses = exp_result.scalars().all()
        total_exp = sum(e.amount or 0 for e in expenses)

        from app.services.coa_engine import build_structured_pl_rows
        rows = build_structured_pl_rows(stmt, budget)

        summary = f"""Management Report — {period}
Source: {ds_name} | {len(stmt.revenue_by_product)} revenue products | {len(stmt.cogs_by_product)} COGS products

KEY METRICS
• Net Revenue: {fgel(stmt.total_revenue)} (Budget: {fgel(bud_rev)}, Variance: {fgel(stmt.total_revenue - bud_rev)})
• Revenue Wholesale: {fgel(stmt.revenue_wholesale_total)} | Revenue Retail: {fgel(stmt.revenue_retail_total)}
• COGS: {fgel(stmt.total_cogs)} ({stmt.total_cogs/stmt.total_revenue*100:.1f}% of revenue)
• Gross Margin: {fgel(stmt.total_gross_margin)} ({stmt.total_gross_margin/stmt.total_revenue*100:.1f}%)
  - Wholesale: {fgel(stmt.margin_wholesale_total)} {"⚠ NEGATIVE" if stmt.margin_wholesale_total < 0 else ""}
  - Retail: {fgel(stmt.margin_retail_total)}
• Other Revenue: {fgel(stmt.other_revenue_total)}
• Total Gross Profit: {fgel(stmt.total_gross_profit)}
• G&A Expenses: {fgel(stmt.ga_expenses)}
• EBITDA: {fgel(stmt.ebitda)}
• Total OpEx: {fgel(total_exp)} ({len(expenses)} transactions)"""

        report = Report(
            title=f"Management Report — {period}",
            report_type="mr", period=period, currency="GEL",
            rows=rows, summary=summary,
            kpis={"revenue": stmt.total_revenue, "cogs": stmt.total_cogs,
                  "gross_margin": stmt.total_gross_margin, "total_gross_profit": stmt.total_gross_profit,
                  "ga_expenses": stmt.ga_expenses, "ebitda": stmt.ebitda,
                  "wholesale_margin": stmt.margin_wholesale_total, "retail_margin": stmt.margin_retail_total},
            generated_by="agent"
        )
        db.add(report)
        await db.commit()
        return f"__NAVIGATE_TO__mr__END__\n**Management Report generated from {ds_name}**\nPeriod: {period}\n\n{summary}\n\nSaved to database (ID: {report.id})"

    async def _save_report(self, p: Dict, db: AsyncSession) -> str:
        report = Report(
            title=p.get("title","Report"),
            report_type=p.get("type","custom"),
            period=p.get("period","January 2025"),
            summary=p.get("summary",""),
            generated_by="agent"
        )
        db.add(report)
        await db.commit()
        return f"Report saved to database (ID: {report.id}): {report.title}"

    async def _analyze_products(self, p: Dict, db: AsyncSession) -> str:
        ds_id = await self._resolve_active_ds(db)
        q = select(RevenueItem)
        if ds_id:
            q = q.where(RevenueItem.dataset_id == ds_id)
        seg = p.get("segment","all")
        if seg and seg != "all":
            q = q.where(RevenueItem.segment.ilike(f"%{seg}%"))
        result = await db.execute(q.order_by(RevenueItem.net.desc()))
        items  = result.scalars().all()
        total  = sum(r.net or 0 for r in items)
        top_n  = min(p.get("top_n", 10), len(items))
        lines  = "\n".join(f"{i+1}. {r.product[:40]} | {fgel(r.net)} ({r.net/total*100:.1f}%) | {r.segment}"
                           for i,r in enumerate(items[:top_n]))
        segs = {}
        for r in items:
            segs[r.segment] = segs.get(r.segment,0) + (r.net or 0)
        seg_lines = "\n".join(f"• {k}: {fgel(v)}" for k,v in sorted(segs.items(),key=lambda x:-x[1]))
        return f"**Product Revenue Analysis** ({len(items)} products, Total: {fgel(total)})\n\nBy Segment:\n{seg_lines}\n\nTop Products:\n{lines}"

    async def _detect_anomalies(self, p: Dict, db: AsyncSession) -> str:
        ds_id = await self._resolve_active_ds(db)
        min_amt = p.get("min_amount", 1000000)
        q = select(Transaction).where(Transaction.amount >= min_amt)
        if ds_id: q = q.where(Transaction.dataset_id == ds_id)
        result  = await db.execute(q.order_by(Transaction.amount.desc()).limit(20))
        large   = result.scalars().all()
        # Negative amounts
        q_neg = select(Transaction).where(Transaction.amount < 0)
        if ds_id: q_neg = q_neg.where(Transaction.dataset_id == ds_id)
        neg_result = await db.execute(q_neg.limit(10))
        negatives  = neg_result.scalars().all()
        lines = [f"• {t.date} | {fgel(t.amount)} | {t.dept} | {(t.cost_class or '')[:30]} | {(t.counterparty or '')[:30]}" for t in large]
        out = f"**Anomaly Detection**\n\nLarge transactions (>{fgel(min_amt)}):\n" + "\n".join(lines)
        if negatives:
            out += f"\n\nNegative amounts ({len(negatives)}):\n" + "\n".join(f"• {t.date} | {fgel(t.amount)} | {t.dept}" for t in negatives)
        return out

    async def _search_counterparty(self, p: Dict, db: AsyncSession) -> str:
        ds_id = await self._resolve_active_ds(db)
        name  = p.get("name","")
        top_n = p.get("top_n", 10)
        if name:
            q = select(Transaction.counterparty, func.sum(Transaction.amount).label("total"), func.count().label("cnt")).where(Transaction.counterparty.ilike(f"%{name}%"))
            if ds_id: q = q.where(Transaction.dataset_id == ds_id)
            result = await db.execute(q.group_by(Transaction.counterparty).order_by(func.sum(Transaction.amount).desc()).limit(20))
        else:
            q = select(Transaction.counterparty, func.sum(Transaction.amount).label("total"), func.count().label("cnt")).where(Transaction.counterparty.isnot(None))
            if ds_id: q = q.where(Transaction.dataset_id == ds_id)
            result = await db.execute(q.group_by(Transaction.counterparty).order_by(func.sum(Transaction.amount).desc()).limit(top_n))
        rows = result.all()
        lines = "\n".join(f"{i+1}. {r[0][:40]} | {fgel(r[1])} | {r[2]} transactions" for i,r in enumerate(rows))
        return f"**Counterparty Analysis**{f' (search: {name})' if name else ' (top {top_n})'}\n\n{lines}"

    async def _compare_periods(self, p: Dict, db: AsyncSession) -> str:
        ds_id_1 = p.get("dataset_id_1")
        ds_id_2 = p.get("dataset_id_2")
        if not ds_id_1 or not ds_id_2:
            return "Error: Both dataset_id_1 and dataset_id_2 are required."

        async def build(ds_id):
            rev = (await db.execute(select(RevenueItem).where(RevenueItem.dataset_id == ds_id))).scalars().all()
            cogs = (await db.execute(select(COGSItem).where(COGSItem.dataset_id == ds_id))).scalars().all()
            ga = (await db.execute(select(GAExpenseItem).where(GAExpenseItem.dataset_id == ds_id))).scalars().all()
            ds = (await db.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one_or_none()
            return build_income_statement(rev, cogs, ga, ds.period if ds else "Unknown"), ds

        stmt1, ds1 = await build(ds_id_1)
        stmt2, ds2 = await build(ds_id_2)
        p1 = ds1.period if ds1 else "Period 1"
        p2 = ds2.period if ds2 else "Period 2"

        def delta(cur, prev):
            d = cur - prev
            pct = d / abs(prev) * 100 if prev else 0
            return f"{fgel(d)} ({'+' if pct >= 0 else ''}{pct:.1f}%)"

        return f"""**Period Comparison: {p1} vs {p2}**

| Metric | {p1} | {p2} | Change |
|--------|------|------|--------|
| Revenue | {fgel(stmt1.total_revenue)} | {fgel(stmt2.total_revenue)} | {delta(stmt2.total_revenue, stmt1.total_revenue)} |
| COGS | {fgel(stmt1.total_cogs)} | {fgel(stmt2.total_cogs)} | {delta(stmt2.total_cogs, stmt1.total_cogs)} |
| Gross Margin | {fgel(stmt1.total_gross_margin)} | {fgel(stmt2.total_gross_margin)} | {delta(stmt2.total_gross_margin, stmt1.total_gross_margin)} |
| Wholesale Margin | {fgel(stmt1.margin_wholesale_total)} | {fgel(stmt2.margin_wholesale_total)} | {delta(stmt2.margin_wholesale_total, stmt1.margin_wholesale_total)} |
| Retail Margin | {fgel(stmt1.margin_retail_total)} | {fgel(stmt2.margin_retail_total)} | {delta(stmt2.margin_retail_total, stmt1.margin_retail_total)} |
| G&A Expenses | {fgel(stmt1.ga_expenses)} | {fgel(stmt2.ga_expenses)} | {delta(stmt2.ga_expenses, stmt1.ga_expenses)} |
| EBITDA | {fgel(stmt1.ebitda)} | {fgel(stmt2.ebitda)} | {delta(stmt2.ebitda, stmt1.ebitda)} |"""

    async def _analyze_semantic(self, p: Dict, db: AsyncSession) -> str:
        """Run semantic layer analysis on active dataset transactions."""
        from app.services.semantic_layer import analyze_transactions_semantic, derive_enhanced_financials, get_pattern_store

        ds_id = await self._resolve_active_ds(db)
        if not ds_id:
            return "No active dataset. Upload a file first."

        txn_result = await db.execute(select(Transaction).where(Transaction.dataset_id == ds_id))
        txns = [t.to_dict() for t in txn_result.scalars().all()]
        if not txns:
            return "No transactions found in active dataset."

        focus = p.get("focus", "overview")

        analysis = analyze_transactions_semantic(txns)
        enhanced = derive_enhanced_financials(txns)
        store = get_pattern_store()

        lines = [f"**Semantic Layer Analysis** ({len(txns)} transactions)\n"]

        if focus in ("overview", "confidence"):
            conf = analysis.get("confidence_levels", {})
            total_classified = conf.get("high", 0) + conf.get("medium", 0) + conf.get("low", 0)
            total = len(txns)
            lines.append(f"Classification confidence:")
            lines.append(f"  - HIGH: {conf.get('high', 0)} ({conf.get('high',0)/total*100:.0f}%)")
            lines.append(f"  - MEDIUM: {conf.get('medium', 0)}")
            lines.append(f"  - LOW: {conf.get('low', 0)}")
            lines.append(f"  - Unclassified: {conf.get('none', 0)}")
            lines.append(f"  - Overall coverage: {total_classified}/{total} ({total_classified/total*100:.0f}%)\n")

        if focus in ("overview", "counterparty"):
            stats = enhanced.get("stats", {})
            lines.append(f"Signal sources:")
            lines.append(f"  - COA codes: {stats.get('by_coa', 0)}")
            lines.append(f"  - Counterparty: {stats.get('by_counterparty', 0)}")
            lines.append(f"  - Department: {stats.get('by_department', 0)}")
            lines.append(f"  - Cost class: {stats.get('by_cost_class', 0)}")
            lines.append(f"  - Unclassified: {stats.get('unclassified', 0)}\n")

        if focus in ("overview",):
            pl_dist = analysis.get("pl_distribution", {})
            lines.append("P&L distribution:")
            for k, v in pl_dist.items():
                lines.append(f"  - {k}: {fgel(v['amount'])} ({v['pct']}%)")
            lines.append("")

        if focus in ("overview", "department"):
            seg_dist = analysis.get("segment_distribution", {})
            lines.append("Segment distribution:")
            for k, v in list(seg_dist.items())[:8]:
                lines.append(f"  - {k}: {fgel(v['amount'])} ({v['pct']}%)")
            lines.append("")

        if focus == "unclassified":
            uncl = enhanced.get("unclassified", [])
            if uncl:
                lines.append(f"Top unclassified transactions ({len(uncl)}):")
                for u in uncl[:10]:
                    lines.append(f"  - {u.get('date','')} | {u.get('counterparty','(none)')[:25]} | {fgel(u.get('amount',0))} | Dr:{u.get('acct_dr','')} Cr:{u.get('acct_cr','')}")
            else:
                lines.append("All transactions were classified.")

        store_stats = store.get_stats()
        if any(v > 0 for v in store_stats.values()):
            lines.append(f"\nPattern store: {store_stats['counterparties_learned']} counterparty patterns learned")

        return "\n".join(lines)

    async def _deep_financial_analysis(self, p: Dict, db: AsyncSession) -> str:
        """Deep financial analysis with exact precision figures."""
        analysis = p.get("analysis", "full_exact_is")
        cat_filter = p.get("category_filter", "")
        top_n = p.get("top_n", 10)
        stmt = await self._build_stmt(db)

        if analysis == "cogs_columns":
            # COGS column breakdown (K/L/O) per product
            lines = [f"**COGS Column Breakdown (Exact Figures)**\n"]
            lines.append(f"Column K (Account 6) Total:    {fexact(stmt.cogs_col6_total)}")
            lines.append(f"Column L (Account 7310) Total: {fexact(stmt.cogs_col7310_total)}")
            lines.append(f"Column O (Account 8230) Total: {fexact(stmt.cogs_col8230_total)}")
            lines.append(f"TOTAL COGS:                    {fexact(stmt.cogs_col6_total + stmt.cogs_col7310_total + stmt.cogs_col8230_total)}")
            lines.append(f"\n**Per-Product COGS Breakdown:**")
            lines.append(f"{'Product':<45} | {'Col K (6)':>15} | {'Col L (7310)':>15} | {'Col O (8230)':>15} | {'Total COGS':>15}")
            lines.append(f"{'-'*45}-+-{'-'*15}-+-{'-'*15}-+-{'-'*15}-+-{'-'*15}")
            prods = stmt.cogs_by_product
            if cat_filter:
                prods = [p for p in prods if p.get("category", "") == cat_filter]
            prods = sorted(prods, key=lambda x: -abs(x.get("total_cogs", 0)))
            for cp in prods[:top_n]:
                name = (cp.get("product_en") or cp.get("product", ""))[:44]
                lines.append(f"{name:<45} | {fexact(cp.get('col6', 0)):>15} | {fexact(cp.get('col7310', 0)):>15} | {fexact(cp.get('col8230', 0)):>15} | {fexact(cp.get('total_cogs', 0)):>15}")
            if cat_filter:
                cat_total = sum(p.get("total_cogs", 0) for p in prods)
                lines.append(f"\n**Category Total ({cat_filter}): {fexact(cat_total)}**")
            return "\n".join(lines)

        elif analysis == "vat_analysis":
            # VAT analysis per product
            lines = [f"**VAT Analysis (Exact Figures)**\n"]
            zero_vat = []
            with_vat = []
            for rp in sorted(stmt.revenue_by_product, key=lambda x: -abs(x.get("net", 0))):
                vat = rp.get("vat", 0)
                gross = rp.get("gross", 0)
                net = rp.get("net", 0)
                if abs(vat) < 0.01:
                    zero_vat.append(rp)
                else:
                    eff_rate = (vat / gross * 100) if gross else 0
                    with_vat.append({**rp, "eff_rate": eff_rate})
            lines.append(f"**Products with VAT ({len(with_vat)}):**")
            lines.append(f"{'Product':<45} | {'Gross':>15} | {'VAT':>15} | {'Net':>15} | {'Eff.Rate':>8}")
            lines.append(f"{'-'*45}-+-{'-'*15}-+-{'-'*15}-+-{'-'*15}-+-{'-'*8}")
            for rp in with_vat[:top_n]:
                name = (rp.get("product_en") or rp.get("product", ""))[:44]
                lines.append(f"{name:<45} | {fexact(rp.get('gross', 0)):>15} | {fexact(rp.get('vat', 0)):>15} | {fexact(rp.get('net', 0)):>15} | {rp['eff_rate']:>7.2f}%")
            lines.append(f"\n**Products with ZERO VAT ({len(zero_vat)}):**")
            for rp in zero_vat:
                name = (rp.get("product_en") or rp.get("product", ""))[:44]
                lines.append(f"  - {name}: Gross={fexact(rp.get('gross', 0))}, Net={fexact(rp.get('net', 0))}")
            lines.append(f"\n**Totals:** Gross={fexact(stmt.revenue_gross_total)}, VAT={fexact(stmt.revenue_vat_total)}, Net={fexact(stmt.total_revenue)}")
            lines.append(f"**Verification:** {fexact(stmt.revenue_gross_total)} - {fexact(stmt.revenue_vat_total)} = {fexact(stmt.revenue_gross_total - stmt.revenue_vat_total)}")
            return "\n".join(lines)

        elif analysis == "concentration":
            # Revenue concentration / Pareto analysis
            prods = sorted(stmt.revenue_by_product, key=lambda x: -abs(x.get("net", 0)))
            prods = [p for p in prods if p.get("product", "") != "Итог"]
            total = stmt.total_revenue
            lines = [f"**Revenue Concentration Analysis (Exact Figures)**\n"]
            lines.append(f"Total Net Revenue: {fexact(total)}")
            lines.append(f"Total Products: {len(prods)}\n")
            cumulative = 0
            pareto_80 = None
            lines.append(f"{'#':<3} {'Product':<40} | {'Net Revenue':>15} | {'% Total':>8} | {'Cumul.%':>8}")
            lines.append(f"{'-'*3} {'-'*40}-+-{'-'*15}-+-{'-'*8}-+-{'-'*8}")
            for i, rp in enumerate(prods):
                net = rp.get("net", 0)
                pct = net / total * 100 if total else 0
                cumulative += pct
                lines.append(f"{i+1:<3} {(rp.get('product_en') or rp.get('product', ''))[:39]:<40} | {fexact(net):>15} | {pct:>7.2f}% | {cumulative:>7.2f}%")
                if pareto_80 is None and cumulative >= 80:
                    pareto_80 = i + 1
            top3_pct = sum(p.get("net", 0) for p in prods[:3]) / total * 100 if total else 0
            top5_pct = sum(p.get("net", 0) for p in prods[:5]) / total * 100 if total else 0
            lines.append(f"\n**Concentration Summary:**")
            lines.append(f"  Top 3 products: {top3_pct:.2f}% of total revenue")
            lines.append(f"  Top 5 products: {top5_pct:.2f}% of total revenue")
            lines.append(f"  Products needed for 80%: {pareto_80 or 'N/A'}")
            return "\n".join(lines)

        elif analysis == "product_profitability":
            # Per-product profitability with margin %
            import re as _re
            def _strip_unit_p(name):
                return _re.sub(r',\s*(კგ|ლ|მ3|ცალი|მომსახურება)\s*$', '', name).strip()

            rev_map = {}
            rev_stripped_map = {}
            for rp in stmt.revenue_by_product:
                prod = rp.get("product", "")
                if prod and prod != "Итог":
                    rev_map[prod] = rp
                    rev_stripped_map[_strip_unit_p(prod)] = rp
            cogs_map = {}
            cogs_stripped_map = {}
            for cp in stmt.cogs_by_product:
                prod = cp.get("product", "")
                if prod and prod != "Итого":
                    cogs_map[prod] = cp
                    cogs_stripped_map[_strip_unit_p(prod)] = cp
            # Merge using fuzzy matching
            all_products = set(list(rev_map.keys()) + list(cogs_map.keys()))
            rows = []
            seen = set()
            for prod in all_products:
                stripped = _strip_unit_p(prod)
                if stripped in seen:
                    continue
                seen.add(stripped)
                rp = rev_map.get(prod) or rev_stripped_map.get(stripped, {})
                cp = cogs_map.get(prod) or cogs_stripped_map.get(stripped, {})
                rev = rp.get("net", 0) if isinstance(rp, dict) else 0
                cogs = cp.get("total_cogs", 0) if isinstance(cp, dict) else 0
                gp = rev - cogs
                margin_pct = (gp / rev * 100) if rev else 0
                cat_r = rp.get("category", "") if isinstance(rp, dict) else ""
                cat_c = cp.get("category", "") if isinstance(cp, dict) else ""
                rows.append({"product": prod, "revenue": rev, "cogs": cogs, "gross_profit": gp, "margin_pct": margin_pct, "rev_cat": cat_r, "cogs_cat": cat_c})
            if cat_filter:
                rows = [r for r in rows if cat_filter in r.get("rev_cat", "") or cat_filter in r.get("cogs_cat", "")]
            rows = sorted(rows, key=lambda x: -x["margin_pct"])
            lines = [f"**Product Profitability Analysis (Exact Figures)**\n"]
            lines.append(f"{'Product':<40} | {'Revenue':>15} | {'COGS':>15} | {'Gross Profit':>15} | {'Margin%':>8}")
            lines.append(f"{'-'*40}-+-{'-'*15}-+-{'-'*15}-+-{'-'*15}-+-{'-'*8}")
            high_margin = [r for r in rows if r["margin_pct"] > 30 and r["revenue"] > 0]
            low_margin = [r for r in rows if 0 < r["margin_pct"] < 5 and r["revenue"] > 0]
            negative_margin = [r for r in rows if r["margin_pct"] < 0 and r["revenue"] > 0]
            for r in rows[:top_n]:
                name = r["product"][:39]
                flag = " ⚠" if r["margin_pct"] < 0 else ""
                lines.append(f"{name:<40} | {fexact(r['revenue']):>15} | {fexact(r['cogs']):>15} | {fexact(r['gross_profit']):>15} | {r['margin_pct']:>7.2f}%{flag}")
            lines.append(f"\n**Margin Buckets:**")
            lines.append(f"  High margin (>30%): {len(high_margin)} products")
            if high_margin:
                for r in high_margin[:5]:
                    lines.append(f"    - {r['product'][:40]}: {r['margin_pct']:.2f}%")
            lines.append(f"  Low margin (<5%): {len(low_margin)} products")
            if low_margin:
                for r in low_margin[:5]:
                    lines.append(f"    - {r['product'][:40]}: {r['margin_pct']:.2f}%")
            lines.append(f"  Negative margin: {len(negative_margin)} products")
            if negative_margin:
                for r in negative_margin[:5]:
                    lines.append(f"    - {r['product'][:40]}: {r['margin_pct']:.2f}% (Revenue: {fexact(r['revenue'])}, COGS: {fexact(r['cogs'])})")
            return "\n".join(lines)

        elif analysis == "cross_validation":
            # Cross-validation between Revenue and COGS
            import re as _re
            def _strip_unit(name):
                """Strip unit suffixes like ', კგ', ', ლ', ', მ3', ', ცალი' for fuzzy matching."""
                return _re.sub(r',\s*(კგ|ლ|მ3|ცალი|მომსახურება)\s*$', '', name).strip()

            rev_products_raw = {rp.get("product", ""): rp for rp in stmt.revenue_by_product if rp.get("product") and rp.get("product") != "Итог"}
            cogs_products_raw = {cp.get("product", ""): cp for cp in stmt.cogs_by_product if cp.get("product") and cp.get("product") != "Итого"}

            # Build fuzzy match maps
            rev_stripped = {_strip_unit(k): k for k in rev_products_raw}
            cogs_stripped = {_strip_unit(k): k for k in cogs_products_raw}

            matched = []
            only_rev_names = []
            only_cogs_names = []
            for stripped, orig in rev_stripped.items():
                if stripped in cogs_stripped:
                    matched.append((orig, cogs_stripped[stripped]))
                else:
                    only_rev_names.append(orig)
            for stripped, orig in cogs_stripped.items():
                if stripped not in rev_stripped:
                    only_cogs_names.append(orig)

            lines = [f"**Cross-Validation: Revenue vs COGS (Exact Figures)**\n"]
            lines.append(f"Revenue products: {len(rev_products_raw)}")
            lines.append(f"COGS products: {len(cogs_products_raw)}")
            lines.append(f"Matched (fuzzy): {len(matched)}")
            lines.append(f"\n**Matched Products ({len(matched)}) — Revenue vs COGS:**")
            for rev_name, cogs_name in sorted(matched, key=lambda x: -abs(rev_products_raw.get(x[0], {}).get("net", 0))):
                rp = rev_products_raw.get(rev_name, {})
                cp = cogs_products_raw.get(cogs_name, {})
                gp = rp.get("net", 0) - cp.get("total_cogs", 0)
                margin_pct = (gp / rp.get("net", 0) * 100) if rp.get("net", 0) else 0
                lines.append(f"  {rev_name[:40]} | Rev: {fexact(rp.get('net', 0))} | COGS: {fexact(cp.get('total_cogs', 0))} | GM: {fexact(gp)} ({margin_pct:.1f}%)")
            lines.append(f"\n**Products ONLY in Revenue (no COGS entry) — {len(only_rev_names)}:**")
            for p in sorted(only_rev_names):
                rp = rev_products_raw.get(p, {})
                lines.append(f"  - {p} (Net: {fexact(rp.get('net', 0))}, Category: {rp.get('category', '')})")
            lines.append(f"\n**Products ONLY in COGS (no Revenue entry) — {len(only_cogs_names)}:**")
            for p in sorted(only_cogs_names):
                cp = cogs_products_raw.get(p, {})
                lines.append(f"  - {p} (COGS: {fexact(cp.get('total_cogs', 0))}, Category: {cp.get('category', '')})")
            lines.append(f"\n**Revenue Total Verification:**")
            rev_sum = sum(rp.get("net", 0) for rp in stmt.revenue_by_product if rp.get("product") != "Итог")
            lines.append(f"  Sum of products: {fexact(rev_sum)}")
            lines.append(f"  IS Total Revenue: {fexact(stmt.total_revenue)}")
            lines.append(f"  Match: {'✓' if abs(rev_sum - stmt.total_revenue) < 0.1 else f'✗ Diff: {fexact(rev_sum - stmt.total_revenue)}'}")
            lines.append(f"\n**COGS Total Verification:**")
            cogs_sum = sum(cp.get("total_cogs", 0) for cp in stmt.cogs_by_product if cp.get("product") != "Итого")
            lines.append(f"  Sum of products: {fexact(cogs_sum)}")
            lines.append(f"  Col K+L+O: {fexact(stmt.cogs_col6_total)} + {fexact(stmt.cogs_col7310_total)} + {fexact(stmt.cogs_col8230_total)} = {fexact(stmt.cogs_col6_total + stmt.cogs_col7310_total + stmt.cogs_col8230_total)}")
            lines.append(f"  IS Total COGS: {fexact(stmt.total_cogs)}")
            lines.append(f"  Match: {'✓' if abs(cogs_sum - stmt.total_cogs) < 0.1 else f'✗ Diff: {fexact(cogs_sum - stmt.total_cogs)}'}")
            # Formula verification for 5 sample products
            lines.append(f"\n**Formula Verification (Net = Gross - VAT) — 5 samples:**")
            samples = sorted(stmt.revenue_by_product, key=lambda x: -abs(x.get("net", 0)))[:5]
            for rp in samples:
                if rp.get("product") == "Итог": continue
                gross = rp.get("gross", 0)
                vat = rp.get("vat", 0)
                net = rp.get("net", 0)
                calc = gross - vat
                match = abs(calc - net) < 0.1
                lines.append(f"  {rp.get('product', '')[:35]}: {fexact(gross)} - {fexact(vat)} = {fexact(calc)} {'✓' if match else f'✗ (expected {fexact(net)})'}")
            return "\n".join(lines)

        elif analysis == "full_exact_is":
            # Complete Income Statement with EXACT figures
            lines = [f"**COMPLETE INCOME STATEMENT — EXACT FIGURES ({stmt.period})**\n"]
            lines.append(f"{'='*70}")
            lines.append(f"REVENUE")
            lines.append(f"  Revenue Wholesale")
            lines.append(f"    Revenue Whsale Petrol:         {fexact(stmt.revenue_wholesale_petrol):>20}")
            lines.append(f"    Revenue Whsale Diesel:         {fexact(stmt.revenue_wholesale_diesel):>20}")
            lines.append(f"    Revenue Whsale Bitumen:        {fexact(stmt.revenue_wholesale_bitumen):>20}")
            lines.append(f"  Total Wholesale Revenue:         {fexact(stmt.revenue_wholesale_total):>20}")
            lines.append(f"  Revenue Retail")
            lines.append(f"    Revenue Retail Petrol:          {fexact(stmt.revenue_retail_petrol):>20}")
            lines.append(f"    Revenue Retail Diesel:          {fexact(stmt.revenue_retail_diesel):>20}")
            lines.append(f"    Revenue Retail CNG:             {fexact(stmt.revenue_retail_cng):>20}")
            lines.append(f"    Revenue Retail LPG:             {fexact(stmt.revenue_retail_lpg):>20}")
            lines.append(f"  Total Retail Revenue:            {fexact(stmt.revenue_retail_total):>20}")
            lines.append(f"  Other Revenue:                   {fexact(stmt.other_revenue_total):>20}")
            lines.append(f"{'─'*70}")
            lines.append(f"TOTAL REVENUE:                     {fexact(stmt.total_revenue):>20}")
            lines.append(f"{'─'*70}")
            lines.append(f"COST OF GOODS SOLD")
            lines.append(f"  COGS Wholesale")
            lines.append(f"    COGS Whsale Petrol:            {fexact(stmt.cogs_wholesale_petrol):>20}")
            lines.append(f"    COGS Whsale Diesel:            {fexact(stmt.cogs_wholesale_diesel):>20}")
            lines.append(f"    COGS Whsale Bitumen:           {fexact(stmt.cogs_wholesale_bitumen):>20}")
            lines.append(f"  Total COGS Wholesale:            {fexact(stmt.cogs_wholesale_total):>20}")
            lines.append(f"  COGS Retail")
            lines.append(f"    COGS Retail Petrol:             {fexact(stmt.cogs_retail_petrol):>20}")
            lines.append(f"    COGS Retail Diesel:             {fexact(stmt.cogs_retail_diesel):>20}")
            lines.append(f"    COGS Retail CNG:                {fexact(stmt.cogs_retail_cng):>20}")
            lines.append(f"    COGS Retail LPG:                {fexact(stmt.cogs_retail_lpg):>20}")
            lines.append(f"  Total COGS Retail:               {fexact(stmt.cogs_retail_total):>20}")
            lines.append(f"  Other COGS:                      {fexact(stmt.other_cogs_total):>20}")
            lines.append(f"{'─'*70}")
            lines.append(f"TOTAL COGS:                        {fexact(stmt.total_cogs):>20}")
            lines.append(f"  (Col K/6: {fexact(stmt.cogs_col6_total)}, Col L/7310: {fexact(stmt.cogs_col7310_total)}, Col O/8230: {fexact(stmt.cogs_col8230_total)})")
            lines.append(f"{'─'*70}")
            lines.append(f"GROSS MARGIN")
            lines.append(f"  GM Wholesale Petrol:             {fexact(stmt.margin_wholesale_petrol):>20} {'⚠ NEGATIVE' if stmt.margin_wholesale_petrol < 0 else ''}")
            lines.append(f"  GM Wholesale Diesel:             {fexact(stmt.margin_wholesale_diesel):>20}")
            lines.append(f"  GM Wholesale Bitumen:            {fexact(stmt.margin_wholesale_bitumen):>20}")
            lines.append(f"  Total Wholesale Margin:          {fexact(stmt.margin_wholesale_total):>20}")
            lines.append(f"  GM Retail Petrol:                {fexact(stmt.margin_retail_petrol):>20}")
            lines.append(f"  GM Retail Diesel:                {fexact(stmt.margin_retail_diesel):>20}")
            lines.append(f"  GM Retail CNG:                   {fexact(stmt.margin_retail_cng):>20}")
            lines.append(f"  GM Retail LPG:                   {fexact(stmt.margin_retail_lpg):>20}")
            lines.append(f"  Total Retail Margin:             {fexact(stmt.margin_retail_total):>20}")
            lines.append(f"  Total Gross Margin:              {fexact(stmt.total_gross_margin):>20}")
            lines.append(f"  Other Revenue:                   {fexact(stmt.other_revenue_total):>20}")
            lines.append(f"{'─'*70}")
            lines.append(f"TOTAL GROSS PROFIT:                {fexact(stmt.total_gross_profit):>20}")
            lines.append(f"{'─'*70}")
            lines.append(f"G&A EXPENSES")
            for code, amt in sorted(stmt.ga_breakdown.items(), key=lambda x: -x[1]):
                ga_name = GA_ACCOUNT_NAMES.get(code, code)
                lines.append(f"  {code} ({ga_name}): {fexact(amt):>20}")
            lines.append(f"TOTAL G&A:                         {fexact(stmt.ga_expenses):>20}")
            lines.append(f"{'='*70}")
            lines.append(f"EBITDA:                            {fexact(stmt.ebitda):>20}")
            lines.append(f"{'='*70}")
            gm_pct = stmt.total_gross_margin / stmt.total_revenue * 100 if stmt.total_revenue else 0
            ebitda_pct = stmt.ebitda / stmt.total_revenue * 100 if stmt.total_revenue else 0
            lines.append(f"\nGross Margin %: {gm_pct:.2f}%")
            lines.append(f"EBITDA Margin %: {ebitda_pct:.2f}%")
            lines.append(f"COGS as % of Revenue: {stmt.total_cogs / stmt.total_revenue * 100:.2f}%")
            lines.append(f"G&A as % of Revenue: {stmt.ga_expenses / stmt.total_revenue * 100:.2f}%")
            return "\n".join(lines)

        return "Unknown analysis type. Use: cogs_columns|vat_analysis|concentration|product_profitability|cross_validation|full_exact_is"

    async def _query_balance_sheet(self, p: Dict, db: AsyncSession) -> str:
        """Query IFRS-mapped Balance Sheet data from parsed BalanceSheetItem records."""
        from app.models.all_models import BalanceSheetItem
        ds_id = await self._resolve_active_ds(db)
        q = select(BalanceSheetItem)
        if ds_id:
            q = q.where(BalanceSheetItem.dataset_id == ds_id)
        if p.get("ifrs_line"):
            q = q.where(BalanceSheetItem.ifrs_line_item.ilike(f"%{p['ifrs_line']}%"))
        if p.get("section"):
            sec = p["section"].lower()
            if sec == "current_assets":
                q = q.where(BalanceSheetItem.ifrs_statement == "BS")
            elif sec == "equity":
                q = q.where(BalanceSheetItem.ifrs_statement == "BS")
        # Only get summary rows for aggregation
        q = q.where(BalanceSheetItem.row_type == 'სხვა')
        result = await db.execute(q)
        items = result.scalars().all()
        if not items:
            return "No Balance Sheet items found. This dataset may not have a parsed Balance/BS sheet."
        # Aggregate by IFRS line
        aggregated = {}
        for item in items:
            line = item.ifrs_line_item or 'Other'
            if line not in aggregated:
                aggregated[line] = {'closing_balance': 0.0, 'count': 0, 'statement': item.ifrs_statement}
            aggregated[line]['closing_balance'] += float(item.closing_balance or 0)
            aggregated[line]['count'] += 1
        lines = []
        for line, data in sorted(aggregated.items(), key=lambda x: -abs(x[1]['closing_balance'])):
            lines.append(f"  {line}: {fgel(data['closing_balance'])} ({data['statement']}, {data['count']} accounts)")
        total_assets = sum(d['closing_balance'] for d in aggregated.values() if d['closing_balance'] > 0)
        total_liab = sum(abs(d['closing_balance']) for d in aggregated.values() if d['closing_balance'] < 0)
        return f"**Balance Sheet** ({len(aggregated)} IFRS line items)\nTotal positive: {fgel(total_assets)} | Total negative: {fgel(total_liab)}\n\n" + "\n".join(lines[:30])

    async def _query_trial_balance(self, p: Dict, db: AsyncSession) -> str:
        """Query Trial Balance (TDSheet) data from parsed TrialBalanceItem records."""
        from app.models.all_models import TrialBalanceItem
        ds_id = await self._resolve_active_ds(db)
        q = select(TrialBalanceItem)
        if ds_id:
            q = q.where(TrialBalanceItem.dataset_id == ds_id)
        if p.get("account_prefix"):
            q = q.where(TrialBalanceItem.account_code.like(f"{p['account_prefix']}%"))
        if p.get("account_class"):
            q = q.where(TrialBalanceItem.account_class == p["account_class"])
        q = q.order_by(TrialBalanceItem.turnover_debit.desc())
        top_n = min(p.get("top_n", 20), 50)
        q = q.limit(top_n)
        result = await db.execute(q)
        items = result.scalars().all()
        if not items:
            return "No Trial Balance items found. This dataset may not have a parsed TDSheet."
        lines = []
        total_dr = 0.0
        total_cr = 0.0
        for item in items:
            dr = float(item.turnover_debit or 0)
            cr = float(item.turnover_credit or 0)
            total_dr += dr
            total_cr += cr
            net = float(item.net_pl_impact or 0)
            lines.append(f"  {item.account_code} | {(item.account_name or '')[:40]} | Dr:{fgel(dr)} Cr:{fgel(cr)} | Net P&L:{fgel(net)}")
        prefix_info = f" (prefix: {p['account_prefix']})" if p.get("account_prefix") else ""
        class_info = f" (class: {p['account_class']})" if p.get("account_class") else ""
        return f"**Trial Balance{prefix_info}{class_info}** — {len(items)} accounts\nTotal Turnover: Dr {fgel(total_dr)} | Cr {fgel(total_cr)}\n\n" + "\n".join(lines)

    async def _analyze_accounting_flows(self, p: Dict, db: AsyncSession) -> str:
        """Analyze accounting flows using the AccountingIntelligence service."""
        from app.services.accounting_intelligence import accounting_intelligence

        flow_type = p.get("flow_type", "full")
        account_code = p.get("account_code")
        parts = []

        # Classify a specific account code
        if account_code:
            cls = accounting_intelligence.classify_account(account_code)
            parts.append(
                f"**Account Classification: {account_code}**\n"
                f"  Match level: {cls.match_level} | Confidence: {cls.confidence:.0%}\n"
                f"  Statement: {cls.statement or 'N/A'} | Side: {cls.side or 'N/A'}\n"
                f"  P&L Line: {cls.pl_line or 'N/A'} | Category: {cls.category or 'N/A'}\n"
                f"  Label: {cls.label_en or 'N/A'} ({cls.label_ka or ''})\n"
                f"  Sub: {cls.sub or 'N/A'} | Matched prefix: {cls.matched_prefix or 'N/A'}\n"
                f"  Source: {cls.source}"
            )
            if cls.key_account_info:
                ki = cls.key_account_info
                parts.append(f"  Key account: {ki.get('label', '')} ({ki.get('label_ka', '')}) — flow: {ki.get('flow', '')}")

        # Explain a specific flow
        if flow_type and flow_type != "full":
            flow = accounting_intelligence.explain_financial_flow(flow_type)
            if "title" in flow:
                parts.append(f"\n**{flow['title']}** ({flow.get('title_ka', '')})")
                parts.append(flow.get("description", ""))
                if flow.get("formula"):
                    parts.append(f"  Formula: {flow['formula']}")
                if flow.get("journal_entry"):
                    parts.append(f"  Journal: {flow['journal_entry']}")
                if flow.get("verification"):
                    parts.append(f"  Verification: {flow['verification']}")
                if flow.get("accounts"):
                    parts.append(f"  Accounts: {', '.join(flow['accounts'])}")
            else:
                parts.append(json.dumps(flow, indent=2))

        # Full dataset flow analysis
        if flow_type == "full" or (not account_code and not flow_type):
            ds_id = await self._resolve_active_ds(db)
            if ds_id:
                try:
                    analysis = await accounting_intelligence.analyze_dataset_flows(db, ds_id)
                    parts.append(f"""
**=== Accounting Flow Analysis ({analysis.period}) ===**

**Account Coverage:** {analysis.mapped_accounts}/{analysis.total_accounts} ({analysis.coverage_pct}%)
  Unmapped: {analysis.unmapped_accounts}{(' — top: ' + ', '.join(u['code'] for u in analysis.unmapped_codes[:5])) if analysis.unmapped_codes else ''}

**Revenue Flow:**
  Gross Revenue: {fexact(analysis.gross_revenue)} | Returns: {fexact(analysis.returns_allowances)} | Net: {fexact(analysis.net_revenue)}
  Segments: {', '.join(f'{k}: {fexact(v)}' for k, v in analysis.revenue_by_segment.items())}

**COGS Formation:**
  Col K (1610→Sales): {fexact(analysis.cogs_col6_total)}
  Col L (7310 Selling): {fexact(analysis.cogs_col7310_total)}
  Col O (8230 Other): {fexact(analysis.cogs_col8230_total)}
  Breakdown Total: {fexact(analysis.cogs_breakdown_total)} | TB 71xx: {fexact(analysis.cogs_tb_71xx_debit)}
  Variance: {analysis.cogs_variance_pct}% {'✓ RECONCILED' if analysis.cogs_reconciled else '⚠ MISMATCH'}

**Inventory Flow (1610):**
  Opening: {fexact(analysis.inventory_opening)} | Closing: {fexact(analysis.inventory_closing)}
  Credit Turnover (outflows): {fexact(analysis.inventory_credit_turnover)}
  Turnover Ratio: {analysis.inventory_turnover}x

**P&L Waterfall:**
  Net Revenue: {fexact(analysis.net_revenue)}
  − COGS: {fexact(analysis.cogs_breakdown_total)}
  = Gross Margin: {fexact(analysis.gross_margin)}
  − Selling (73xx): {fexact(analysis.selling_expenses_73xx)}
  − Admin (74xx): {fexact(analysis.admin_expenses_74xx)}
  = EBITDA: {fexact(analysis.ebitda)}
  − Interest (8220): {fexact(analysis.interest_expense)}
  ≈ Net Income: {fexact(analysis.net_income)}

**Balance Sheet Identity:**
  Assets: {fexact(analysis.total_assets)} (CA: {fexact(analysis.total_current_assets)} + NCA: {fexact(analysis.total_noncurrent_assets)})
  Liabilities: {fexact(analysis.total_liabilities)} (CL: {fexact(analysis.total_current_liabilities)} + NCL: {fexact(analysis.total_noncurrent_liabilities)})
  Equity: {fexact(analysis.total_equity)}
  A = L + E: {'✓ BALANCED' if analysis.bs_balanced else f'⚠ VARIANCE: {fexact(analysis.bs_variance)}'}

**Working Capital:**
  Inventory: {fexact(analysis.inventory_balance)} | Receivables: {fexact(analysis.receivables_balance)}
  Prepayments: {fexact(analysis.prepayments_balance)} | Payables: {fexact(analysis.payables_balance)}
  Net Working Capital: {fexact(analysis.working_capital)} | Current Ratio: {analysis.current_ratio}

{'**Warnings:** ' + chr(10).join('  ⚠ ' + w for w in analysis.warnings) if analysis.warnings else ''}
{'**Info:** ' + chr(10).join('  ℹ ' + i for i in analysis.info) if analysis.info else ''}""")
                except Exception as e:
                    parts.append(f"Flow analysis error: {str(e)}")
            else:
                parts.append("No active dataset. Upload financial data first.")

        return "\n".join(parts) if parts else "Provide flow_type or account_code parameter."

    async def _visualize_logistics(self, p: Dict, db: AsyncSession) -> str:
        """Handler for tactical logistics visualization."""
        mode = p.get("mode")
        comp_id = p.get("competitor_id")
        intent = p.get("user_intent_summary", "Analyzing Logistics Corridor...")
        
        # Fetch base intelligence data
        risk_data = await risk_engine.get_situational_risk()
        
        if mode == "optimize_route":
            best = await logistics_intelligence.find_best_route(risk_data)
            cmd = {
                "type": "MAP_HIGHLIGHT",
                "route_id": best["recommended_id"],
                "rationale": best["rationale"],
                "intent": intent,
                "efficiency": best["efficiency_gain_pct"]
            }
            return f"__AGENT_MAP_COMMAND__{json.dumps(cmd)}__END__\n**Logistics Optimization**: I have identified the {best['recommended_name']} as the most efficient route currently. {best['rationale']}"
            
        elif mode == "show_competitors":
            overlay = await logistics_intelligence.get_competitor_overlay()
            if comp_id and comp_id != "all":
                overlay = [c for c in overlay if c["id"] == comp_id]
            
            cmd = {
                "type": "MAP_SHOW_COMPETITORS",
                "competitors": overlay,
                "intent": intent
            }
            comp_names = ", ".join([o['name'] for o in overlay])
            return f"__AGENT_MAP_COMMAND__{json.dumps(cmd)}__END__\n**Competitor Intelligence**: Visualizing supply chain corridors for {comp_names}. Dotted lines on the map indicate estimated transit lanes."
            
        else:
            return f"Analyzing {intent}. Check the map for infrastructure health updates."

    async def _research_regulatory_landscape(self, p: Dict, db: AsyncSession) -> str:
        """Call the regulatory intelligence service to fetch tax laws."""
        from app.services.regulatory_intelligence import regulatory_intelligence
        country = p.get("country", "GEORGIA")
        product = p.get("product_type")
        
        data = await regulatory_intelligence.get_transit_taxes(country, product)
        impact = await regulatory_intelligence.analyze_price_impact(country, 2500, 1000) # Sample 1000 ton impact
        
        lines = [f"**Regulatory Brief: {country.upper()}**"]
        for k, v in data.items():
            if k != "source":
                lines.append(f"• {k.replace('_',' ').title()}: {v}")
        
        lines.append(f"\n**Est. Financial Impact (1k Tons):** {fgel(impact['total_tax_impact'])}")
        lines.append(f"**Source Authority:** {data.get('source', 'Official Gazette')}")
        
        return "\n".join(lines)

    async def _command_digital_twin(self, p: Dict, db: AsyncSession) -> str:
        """Execute a direct command to the Industrial Digital Twin map."""
        cmd_type = p.get("command_type")
        target_id = p.get("target_id")
        intent = p.get("intent", "Neural Strategy Update")
        rationale = p.get("rationale", "Analyzing critical infrastructure nodes...")
        eff = p.get("efficiency_gain")

        # Bridge tool names to map event types
        type_map = {
            "highlight_route": "MAP_HIGHLIGHT",
            "pulse_node": "MAP_PULSE_NODE",
            "show_competitors": "MAP_SHOW_COMPETITORS",
            "trigger_simulation": "MAP_TRIGGER_SIMULATION",
            "trigger_strategy": "MAP_TRIGGER_STRATEGY"
        }

        cmd = {
            "type": type_map.get(cmd_type, "MAP_HIGHLIGHT"),
            "intent": intent,
            "rationale": rationale
        }

        if cmd_type == "trigger_strategy":
            from app.services.logistics_intelligence_service import logistics_intelligence
            
            # Fetch current financial context (Margin) for the strategy engine
            from app.services.coa_engine import build_income_statement
            rev_items = (await db.execute(select(RevenueItem))).scalars().all()
            cogs_items = (await db.execute(select(COGSItem))).scalars().all()
            ga_items = (await db.execute(select(GAExpenseItem))).scalars().all()
            stmt = build_income_statement(rev_items, cogs_items, ga_items)
            current_margin = stmt.total_ebitda_margin or 0.08
            
            strategy = await logistics_intelligence.get_strategic_response(
                p.get("event_type", "MARKET_DISRUPTION"),
                current_margin=current_margin
            )
            cmd["strategy"] = strategy
            # Add specific action markers to the map
            cmd["markers"] = [
                {"coord": r["coords"], "label": f"{r['name'].split()[0].upper()}: {r['action'].upper()}", "color": r["color"]}
                for r in strategy["competitor_reactions"]
            ]
            cmd["procurement_path"] = strategy["optimal_procurement"]["path"]

        elif target_id:
            if cmd_type == "highlight_route":
                cmd["route_id"] = target_id
            else:
                cmd["node_id"] = target_id

        if eff:
            cmd["efficiency"] = eff

        # If showing competitors, fetch live overlay data
        if cmd_type == "show_competitors":
            from app.services.logistics_intelligence_service import logistics_intelligence
            overlay = await logistics_intelligence.get_competitor_overlay()
            cmd["competitors"] = overlay

        cmd_json = json.dumps(cmd)
        
        # Return the special marker that the frontend Layout.tsx parses
        return (
            f"__AGENT_MAP_COMMAND__{cmd_json}__END__\n"
            f"**Digital Twin Command Executed**: {intent}\n"
            f"Rationale: {rationale}"
        )

    async def _resolve_active_ds(self, db: AsyncSession) -> Optional[int]:
        result = await db.execute(select(Dataset.id).where(Dataset.is_active == True).limit(1))
        row = result.first()
        return row[0] if row else None

    async def _resolve_dataset_id(self, db: AsyncSession) -> int:
        """Get the active dataset ID."""
        result = await db.execute(select(Dataset).where(Dataset.is_active == True))
        ds = result.scalar_one_or_none()
        if ds:
            return ds.id
        # Fallback to most recent
        result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()).limit(1))
        ds = result.scalar_one_or_none()
        if ds:
            return ds.id
        return None

    async def _build_system_prompt(self, db: AsyncSession, user_message: str = "") -> str:
        """Dynamically build the system prompt with active memory and Sovereign Protocols."""
        # Fetch memory for context (skip if table schema mismatched)
        mems = []
        try:
            mems = (await db.execute(select(AgentMemory).order_by(AgentMemory.created_at.desc()).limit(10))).scalars().all()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
        mem_str = "\n".join([f"- {m.content}" for m in mems]) if mems else "(no prior context)"

        prompt = f"""You are the **Sovereign Strategic Commander** of the NYX Core Financial Digital Twin.
Your primary objective is **Margin Integrity** (protecting the 8% EBITDA floor).

### TACTICAL CORE (SOVEREIGN PROTOCOL)
1. **Delivered Cost Math**: [Procurement FOB] + [Transit Tax] + [Freight] = [Delivered Cost].
2. **Regulatory Intelligence**: Use provided tools to cite official tax laws from rs.ge and mof.ge.
3. **Institutional Reasoning**: When advising on logistics or pricing shocks, format your response as a **STRATEGIC MEMORANDUM**:
   - **I. EXECUTIVE SUMMARY**: Situational risk assessment.
   - **II. DELIVERED COST AUDIT**: Breakdown of financial exposure.
   - **III. BATTLE ORDER**: Actionable logistics/pricing pivot.

### MULTILINGUAL COMMAND
Match the user's language exactly: **Georgian (ქართული)**, **Russian**, or **English**.

### DIGITAL TWIN SYNERGY
The map is your tactical theater. Use `command_digital_twin` to manipulate map assets (pulse nodes, highlight routes, show competitors).

RECENT CONTEXT:
{mem_str}"""
        return prompt

    # ── MAIN CHAT ENTRY POINT ────────────────────────────────────────────────

    async def chat(self, message: str, history: List[Dict], db: AsyncSession) -> Dict:
        span = tracer.start_span("agent.execution")
        span.set_attribute("agent.type", "finai_assistant_sync")
        span.set_attribute("agent.model", self.model)
        
        system  = await self._build_system_prompt(db, user_message=message)
        messages = list(history) + [{"role":"user","content":message}]
        navigation = None
        report_data = None
        tool_calls_log = []

        MAX_TOOL_ROUNDS = 12  # Allow complex multi-step financial analysis

        # Agentic loop: Gemma 4 (primary) → Claude (fallback)
        response = await self._get_gemma4_completion(system, messages)

        rounds = 0
        while response.stop_reason == "tool_use" and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            tool_results = []

            for tu in tool_uses:
                result = await self.execute_tool(tu.name, tu.input or {}, db)
                tool_calls_log.append({"tool": tu.name, "input": tu.input, "result": result[:200]})
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result})
                if "__NAVIGATE_TO__" in result:
                    import re
                    m = re.search(r"__NAVIGATE_TO__(\w+)__END__", result)
                    if m:
                        navigation = m.group(1)

            # Convert SDK content blocks to plain dicts for message history
            assistant_content = []
            for block in response.content:
                if hasattr(block, "model_dump"):
                    assistant_content.append(block.model_dump())
                elif hasattr(block, "to_dict"):
                    assistant_content.append(block.to_dict())
                else:
                    assistant_content.append(block)
            messages += [{"role": "assistant", "content": assistant_content},
                         {"role": "user",      "content": tool_results}]

            logger.info(f"Tool round {rounds}: {[tu.name for tu in tool_uses]} → calling model again")

            # Call model again with tool results
            response = await self._get_gemma4_completion(system, messages)

        logger.info(f"Final stop_reason={response.stop_reason} after {rounds} tool rounds, content_types={[b.type for b in response.content]}")

        # Extract final text from response
        final_text = "".join(
            b.text if hasattr(b, "text") else (b.get("text", "") if isinstance(b, dict) else "")
            for b in response.content
        )

        # If response is empty after max rounds, provide a summary from tool results
        if not final_text.strip() and tool_calls_log:
            tool_summaries = []
            for tc in tool_calls_log:
                tool_summaries.append(f"**{tc['tool']}**: {tc['result'][:300]}")
            final_text = "Based on my analysis using the available tools, here is what I found:\n\n" + "\n\n".join(tool_summaries[-3:])
            logger.warning(f"Empty response after {rounds} rounds — generated fallback from tool results")

        # Save to memory (rollback first in case session is dirty)
        try:
            await db.rollback()
            db.add(AgentMemory(
                memory_type="conversation",
                content=f"Q: {message[:100]} | A: {final_text[:150]}",
                importance=3
            ))
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

        span.set_attribute("agent.result_size", len(final_text))
        span.end()

        return {
            "response":    final_text,
            "tool_calls":  tool_calls_log,
            "navigation":  navigation,
            "report_data": report_data,
        }

    async def _get_gemma4_completion(self, system: str, messages: List[Dict]):
        """Gemma 4 via NVIDIA API: OpenAI-compatible chat completions."""
        import httpx, asyncio

        # ── Build OpenAI-format tools from Anthropic tool definitions ──
        oai_tools = []
        for t in self.tools:
            schema = t.get("input_schema", {})
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": schema,
                }
            })

        # ── Build OpenAI-format messages ──
        oai_messages = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            content = m["content"]

            # Handle tool results (Anthropic format → OpenAI tool role)
            if isinstance(content, list) and any(
                isinstance(c, dict) and c.get("type") == "tool_result" for c in content
            ):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        oai_messages.append({
                            "role": "tool",
                            "tool_call_id": b.get("tool_use_id", "unknown"),
                            "content": b.get("content", ""),
                        })
                continue

            # Handle assistant messages with tool_use blocks
            if role == "assistant" and isinstance(content, list):
                tool_calls = []
                text_parts = []
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tool_calls.append({
                            "id": b.get("id", b.get("name", "unknown")),
                            "type": "function",
                            "function": {
                                "name": b["name"],
                                "arguments": json.dumps(b.get("input", {})),
                            }
                        })
                    elif isinstance(b, dict) and b.get("type") == "text":
                        text_parts.append(b.get("text", ""))
                msg = {"role": "assistant", "content": "\n".join(text_parts) or None}
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                oai_messages.append(msg)
                continue

            # Plain text messages
            if isinstance(content, str):
                oai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                text = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
                oai_messages.append({"role": role, "content": text})

        # ── API call to NVIDIA ──
        from app.services.local_llm import NVIDIA_API_URL, GEMMA4_MODEL, GEMMA4_TIMEOUT, _get_nvidia_gemma_key

        api_key = _get_nvidia_gemma_key()
        if not api_key:
            logger.warning("Gemma 4 API key not configured — falling back to Claude")
            return await self._get_claude_completion(system, messages)

        payload = {
            "model": GEMMA4_MODEL,
            "messages": oai_messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.7,
            "top_p": 0.95,
            "stream": False,
        }
        # Note: tool calling disabled for now — NVIDIA free tier times out with function defs

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # ── Pseudo-Anthropic response classes (same interface as Claude SDK) ──
        class _Content:
            def __init__(self, text="", tool_use=None):
                self.type = "text" if text else "tool_use"
                self.text = text
                self.name = tool_use.get("name") if tool_use else None
                self.input = tool_use.get("input") if tool_use else None
                self.id = tool_use.get("id") if tool_use else None
            def model_dump(self):
                if self.type == "text":
                    return {"type": "text", "text": self.text}
                return {"type": "tool_use", "name": self.name, "input": self.input, "id": self.id}

        class _Response:
            def __init__(self):
                self.content = []
                self.stop_reason = "end_turn"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(GEMMA4_TIMEOUT, connect=15.0)) as client:
                resp = await client.post(NVIDIA_API_URL, json=payload, headers=headers)

                if resp.status_code != 200:
                    logger.warning("Gemma 4 API %d: %s", resp.status_code, resp.text[:300])
                    return await self._get_claude_completion(system, messages)

                data = resp.json()
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                finish = choice.get("finish_reason", "stop")

                result = _Response()

                # Text content
                text = msg.get("content", "")
                if text:
                    result.content.append(_Content(text=text))

                # Tool calls
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    result.stop_reason = "tool_use"
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        try:
                            args = json.loads(fn.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}
                        result.content.append(_Content(tool_use={
                            "name": fn.get("name", "unknown"),
                            "input": args,
                            "id": tc.get("id", fn.get("name", "unknown")),
                        }))

                if not result.content:
                    result.content.append(_Content(text=""))

                logger.info("Gemma 4 chat OK: model=%s, %d chars, finish=%s", GEMMA4_MODEL, len(text), finish)
                return result

        except httpx.TimeoutException:
            logger.error("Gemma 4 TIMEOUT after %ds (prompt ~%d chars)", GEMMA4_TIMEOUT, len(system))
            return await self._get_claude_completion(system, messages)
        except Exception as e:
            logger.error("Gemma 4 error: %s: %s", type(e).__name__, e)
            return await self._get_claude_completion(system, messages)

    async def _get_claude_completion(self, system: str, messages: List[Dict]):
        """Claude fallback when Gemma 4 is unavailable."""
        try:
            return await self.client.messages.create(
                model=self.model, max_tokens=self.max_tokens,
                system=system, messages=messages, tools=self.tools
            )
        except Exception as e:
            logger.error("Claude fallback also failed: %s", e)
            class _Empty:
                content = []
                stop_reason = "error"
            return _Empty()

    # ── WEBSOCKET STREAMING CHAT ────────────────────────────────────────────

    async def _stream_gemma4(
        self, system: str, messages: List[Dict], tools: List[Dict]
    ) -> AsyncGenerator[Any, None]:
        """SSE stream from NVIDIA API for Gemma 4, yielding Anthropic-compatible events."""
        from app.services.local_llm import NVIDIA_API_URL, _get_nvidia_gemma_key
        api_key = _get_nvidia_gemma_key()
        if not api_key:
            raise ValueError("NVIDIA_API_KEY_GEMMA not configured")

        # Convert Anthropic messages to OpenAI format
        oai_messages = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            content = m["content"]
            if isinstance(content, str):
                oai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Handle tool results/use lists
                text = ""
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text += c.get("text", "")
                    elif isinstance(c, dict) and c.get("type") == "tool_result":
                         text += f"\n[Tool Result: {c.get('content', '')[:500]}]"
                oai_messages.append({"role": role, "content": text or str(content)})

        payload = {
            "model": self.gemma_model,
            "messages": oai_messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.7,
            "top_p": 0.95,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        # Mock event classes for stream_chat compatibility
        class MockEvent:
            def __init__(self, type, text=None, content_block=None, delta=None):
                self.type = type
                self.text = text
                self.content_block = content_block
                self.delta = delta

        class MockFinalMessage:
            def __init__(self, content):
                self.content = content

        class MockToolUse:
            def __init__(self, name, input, id):
                self.type = "tool_use"
                self.name = name
                self.input = input
                self.id = id
            def model_dump(self): return {"type": "tool_use", "name": self.name, "input": self.input, "id": self.id}
            def to_dict(self): return self.model_dump()

        class MockText:
            def __init__(self, text):
                self.type = "text"
                self.text = text
            def model_dump(self): return {"type": "text", "text": self.text}
            def to_dict(self): return self.model_dump()

        full_content = ""
        tool_calls = {}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.gemma_timeout)) as client:
                async with client.stream("POST", NVIDIA_API_URL, json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        raise Exception(f"NVIDIA API Error {resp.status_code}: {err.decode()[:200]}")

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "): continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]": break
                        
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            
                            # Text delta
                            text = delta.get("content")
                            if text:
                                full_content += text
                                yield MockEvent("content_block_delta", delta=MockEvent("delta", text=text))

                            # Tool call delta (if Gemma 4 supports it via OAI format)
                            tc_list = delta.get("tool_calls")
                            if tc_list:
                                for tc in tc_list:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls:
                                        tool_calls[idx] = {"name": "", "args": "", "id": tc.get("id")}
                                    
                                    fn = tc.get("function", {})
                                    if fn.get("name"): tool_calls[idx]["name"] += fn["name"]
                                    if fn.get("arguments"): tool_calls[idx]["args"] += fn["arguments"]

                        except json.JSONDecodeError: continue

            # Yield final message summary
            final_content = [MockText(full_content)] if full_content else []
            for tc in tool_calls.values():
                try:
                    args = json.loads(tc["args"] or "{}")
                except: args = {}
                final_content.append(MockToolUse(tc["name"], args, tc["id"]))
            
            # Wrap in something that has get_final_message
            class StreamWrapper:
                async def __aenter__(self): return self
                async def __aexit__(self, *args): pass
                def __aiter__(self): return iter_func()
                async def get_final_message(self): return MockFinalMessage(final_content)

            async def iter_func():
                # This is a bit hacky, but we've already yielded the events
                # stream_chat expects an async iterator
                return
            
            # Re-architecting below to return the wrapper or just use the events
            # Actually, let's just update stream_chat to use this helper.

        except Exception as e:
            logger.error(f"Gemma 4 streaming failed: {e}")
            raise

    async def stream_chat(self, message: str, history: List[Dict], db: AsyncSession, ws) -> None:
        """Stream AI response token-by-token via WebSocket with dual-engine support (Gemma 4 / Claude)."""
        span = tracer.start_span("agent.execution")
        span.set_attribute("agent.type", "finai_assistant_stream")
        
        system = await self._build_system_prompt(db, user_message=message)
        messages = list(history) + [{"role": "user", "content": message}]
        tool_calls_log = []
        navigation = None
        MAX_TOOL_ROUNDS = 12
        rounds = 0
        collected_text = ""

        # Priority: Gemma 4 (NVIDIA)
        use_gemma = bool(settings.NVIDIA_API_KEY_GEMMA)
        span.set_attribute("agent.target_model", "gemma-4-31b" if use_gemma else "claude-sonnet-4")

        while rounds <= MAX_TOOL_ROUNDS:
            rounds += 1
            final_message = None

            try:
                if use_gemma:
                    # IMPLEMENTATION NOTE: Gemma 4 SSE logic
                    from app.services.local_llm import NVIDIA_API_URL, _get_nvidia_gemma_key
                    api_key = _get_nvidia_gemma_key()
                    
                    # Tool defs in OAI format
                    oai_tools = []
                    for t in self.tools:
                        oai_tools.append({
                            "type": "function",
                            "function": {
                                "name": t["name"],
                                "description": t["description"],
                                "parameters": t["input_schema"]
                            }
                        })

                    # OAI Messages
                    oai_messages = [{"role": "system", "content": system}]
                    for m in messages:
                        role = m["role"]
                        content = m["content"]
                        if isinstance(content, str):
                            oai_messages.append({"role": role, "content": content})
                        elif isinstance(content, list):
                            text_parts = []
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    text_parts.append(c.get("text", ""))
                                elif isinstance(c, dict) and c.get("type") == "tool_result":
                                    text_parts.append(f"\n[Result: {c.get('content','')[:1000]}]")
                            oai_messages.append({"role": role, "content": " ".join(text_parts)})

                    payload = {
                        "model": self.gemma_model,
                        "messages": oai_messages,
                        "max_tokens": self.max_tokens,
                        "stream": True,
                        "tools": oai_tools,
                        "tool_choice": "auto"
                    }

                    stream_started = False
                    full_content = ""
                    tool_calls = {}

                    async with httpx.AsyncClient(timeout=httpx.Timeout(self.gemma_timeout)) as client:
                        async with client.stream("POST", NVIDIA_API_URL, json=payload, headers={"Authorization": f"Bearer {api_key}"}) as resp:
                            if resp.status_code != 200:
                                raise Exception(f"Gemma 4 API Error {resp.status_code}")
                            
                            async for line in resp.aiter_lines():
                                if not line.startswith("data: "): continue
                                data_str = line[6:].strip()
                                if data_str == "[DONE]": break
                                try:
                                    chunk = json.loads(data_str)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    
                                    # Text
                                    chunk_text = delta.get("content")
                                    if chunk_text:
                                        if not stream_started:
                                            await ws.send_json({"type": "stream_start"})
                                            stream_started = True
                                        full_content += chunk_text
                                        collected_text += chunk_text
                                        await ws.send_json({"type": "stream_delta", "content": chunk_text})
                                    
                                    # Tools
                                    tcs = delta.get("tool_calls")
                                    if tcs:
                                        for tc in tcs:
                                            idx = tc.get("index", 0)
                                            if idx not in tool_calls:
                                                tool_calls[idx] = {"name": "", "args": "", "id": tc.get("id")}
                                            if tc.get("function", {}).get("name"):
                                                tool_calls[idx]["name"] += tc["function"]["name"]
                                            if tc.get("function", {}).get("arguments"):
                                                tool_calls[idx]["args"] += tc["function"]["arguments"]
                                except: continue

                    # Build final message mock for tool execution
                    class MockMsg:
                        def __init__(self, txt, tcs):
                            self.content = []
                            if txt:
                                class Txt:
                                    def __init__(self, t): self.type="text"; self.text=t
                                    def model_dump(self): return {"type":"text", "text":self.text}
                                self.content.append(Txt(txt))
                            for tc in tcs.values():
                                class TC:
                                    def __init__(self, n, a, i):
                                        self.type="tool_use"; self.name=n; self.id=i
                                        try: self.input=json.loads(a or "{}")
                                        except: self.input={}
                                    def model_dump(self): return {"type":"tool_use", "name":self.name, "input":self.input, "id":self.id}
                                self.content.append(TC(tc["name"], tc["args"], tc["id"]))
                    
                    final_message = MockMsg(full_content, tool_calls)

                else:
                    # Fallback or User-forced: Claude
                    stream = self.client.messages.stream(
                        model=self.model, max_tokens=self.max_tokens,
                        system=system, messages=messages, tools=self.tools
                    )
                    async with stream as s:
                        stream_started = False
                        async for event in s:
                            if event.type == "content_block_delta":
                                if hasattr(event.delta, "text"):
                                    if not stream_started:
                                        await ws.send_json({"type": "stream_start"})
                                        stream_started = True
                                    collected_text += event.delta.text
                                    await ws.send_json({"type": "stream_delta", "content": event.delta.text})
                        final_message = await s.get_final_message()

            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                error_str = str(e).lower()
                if "auth" in error_str or "api_key" in error_str or "401" in error_str:
                    user_msg = (
                        "AI service authentication failed (API key missing or invalid). "
                        "The financial computation APIs are still fully operational — "
                        "you can use the P&L, Balance Sheet, and analytics features directly."
                    )
                else:
                    user_msg = str(e)
                await ws.send_json({"type": "error", "content": user_msg})
                return

            # Check for tool use
            tool_use_blocks = [b for b in final_message.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # No tools — streaming is done
                break

            # Execute tools
            tool_results = []
            for tu in tool_use_blocks:
                result = await self.execute_tool(tu.name, tu.input or {}, db)
                tool_calls_log.append({"tool": tu.name, "input": tu.input, "result": result[:200]})
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result})

                # Send tool execution notification
                await ws.send_json({
                    "type": "tool_call",
                    "tool": tu.name,
                    "input": tu.input,
                    "result": result[:300]
                })

                if "__NAVIGATE_TO__" in result:
                    m = re.search(r"__NAVIGATE_TO__(\w+)__END__", result)
                    if m:
                        navigation = m.group(1)

            # Build messages for next round
            assistant_content = []
            for block in final_message.content:
                if hasattr(block, "model_dump"):
                    assistant_content.append(block.model_dump())
                elif hasattr(block, "to_dict"):
                    assistant_content.append(block.to_dict())
                else:
                    assistant_content.append(block)

            messages += [
                {"role": "assistant", "content": assistant_content},
                {"role": "user", "content": tool_results}
            ]

        # Send completion signal
        await ws.send_json({
            "type": "stream_end",
            "tool_calls": tool_calls_log,
            "navigation": navigation,
        })

        # Save to memory
        try:
            db.add(AgentMemory(
                memory_type="conversation",
                content=f"Q: {message[:100]} | A: {collected_text[:150]}",
                importance=3
            ))
            await db.commit()
        except Exception:
            pass
            
        span.set_attribute("agent.result_size", len(collected_text))
        span.end()


# Singleton
agent = FinAIAgent()
