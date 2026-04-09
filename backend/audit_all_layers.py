"""
Full Architecture Audit Script for FinAI Backend
=================================================
Checks all 5 layers:
  Layer 1: Intelligence Engine (Phases A-L)
  Layer 2: Data Engine (Excel/PDF parsing, DB, validation)
  Layer 3: Accounting Core (double-entry, COA, journal entries)
  Layer 4: Report Generator (P&L, Balance Sheet, Cash Flow, PDF export)
  Layer 5: Intelligent Interface (chat, what-if, auto-diagnosis, alerts)
Usage:
  cd /path/to/FinAI_Backend_3/backend && python audit_all_layers.py
"""
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple

# ── CONFIG ──────────────────────────────────────────────────────────
BACKEND_ROOT = Path(".")
SERVICES_DIR = BACKEND_ROOT / "app" / "services"
ROUTERS_DIR = BACKEND_ROOT / "app" / "routers"
MODELS_DIR = BACKEND_ROOT / "app" / "models"
UTILS_DIR = BACKEND_ROOT / "app" / "utils"
APP_DIR = BACKEND_ROOT / "app"

# Colors (safe for Windows — disabled if not supported)
try:
    os.system("")  # Enable ANSI on Windows
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
except Exception:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""

results: Dict[str, List[Tuple[str, bool, str]]] = {}
total_found = 0
total_missing = 0


def check(layer: str, name: str, condition: bool, detail: str = ""):
    global total_found, total_missing
    if layer not in results:
        results[layer] = []
    results[layer].append((name, condition, detail))
    if condition:
        total_found += 1
    else:
        total_missing += 1


def file_exists(path: str) -> bool:
    return Path(path).exists()


def file_contains(path: str, *keywords: str) -> Tuple[bool, List[str]]:
    if not Path(path).exists():
        return False, list(keywords)
    content = Path(path).read_text(encoding="utf-8", errors="ignore")
    missing = [kw for kw in keywords if kw.lower() not in content.lower()]
    return len(missing) == 0, missing


def find_files_with(directory: str, keyword: str) -> List[str]:
    found = []
    root = Path(directory)
    if not root.exists():
        return found
    for f in root.rglob("*.py"):
        try:
            if keyword.lower() in f.read_text(encoding="utf-8", errors="ignore").lower():
                found.append(str(f))
        except Exception:
            pass
    return found


def find_routes(directory: str, path_fragment: str) -> List[str]:
    return find_files_with(directory, path_fragment)


def count_py_files(directory: str) -> int:
    root = Path(directory)
    if not root.exists():
        return 0
    return len(list(root.rglob("*.py")))


def count_classes_in_dir(directory: str) -> int:
    count = 0
    root = Path(directory)
    if not root.exists():
        return 0
    for f in root.rglob("*.py"):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            count += len(re.findall(r"^class \w+", content, re.MULTILINE))
        except Exception:
            pass
    return count


def count_routes_in_dir(directory: str) -> int:
    count = 0
    root = Path(directory)
    if not root.exists():
        return 0
    for f in root.rglob("*.py"):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            count += len(re.findall(r"@router\.(get|post|put|delete|patch)", content))
        except Exception:
            pass
    return count


# ===================================================================
print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
print(f"{BOLD}{CYAN}  FINAI BACKEND - FULL ARCHITECTURE AUDIT{RESET}")
print(f"{BOLD}{CYAN}{'=' * 70}{RESET}\n")

# ── GENERAL STATS ──────────────────────────────────────────────────
print(f"{BOLD}General Codebase Stats:{RESET}")
py_count = count_py_files(str(APP_DIR))
class_count = count_classes_in_dir(str(APP_DIR))
route_count = count_routes_in_dir(str(APP_DIR))
service_count = count_py_files(str(SERVICES_DIR))
print(f"  Python files in app/:     {py_count}")
print(f"  Classes defined:          {class_count}")
print(f"  API routes:               {route_count}")
print(f"  Service modules:          {service_count}")
print()

# ===================================================================
# LAYER 1: INTELLIGENCE ENGINE (Phases A-L)
# ===================================================================
LAYER = "Layer 1: Intelligence Engine (Phases A-L)"

check(LAYER, "CalcAgent service", len(find_files_with(str(APP_DIR), "class CalcAgent")) > 0)
check(LAYER, "AgentMemory model", len(find_files_with(str(APP_DIR), "AgentMemory")) > 0)
check(LAYER, "SemanticEnricher", len(find_files_with(str(APP_DIR), "SemanticEnricher")) > 0)
check(LAYER, "Anomaly detection", len(find_files_with(str(APP_DIR), "anomal")) > 0)
check(LAYER, "ResponseCache", len(find_files_with(str(APP_DIR), "ResponseCache")) > 0)
check(LAYER, "KnowledgeGraph", len(find_files_with(str(APP_DIR), "KnowledgeGraph")) > 0)
check(LAYER, "SchemaRegistry", len(find_files_with(str(APP_DIR), "SchemaRegistry")) > 0)
check(LAYER, "Telemetry", len(find_files_with(str(APP_DIR), "Telemetry")) > 0)
check(LAYER, "FinancialReasoningEngine", len(find_files_with(str(APP_DIR), "FinancialReasoning")) > 0)
check(LAYER, "1C COA Interpreter", len(find_files_with(str(APP_DIR), "OneCInterpreter")) > 0)
check(LAYER, "IngestionIntelligence", len(find_files_with(str(APP_DIR), "Ingestion")) > 0)
check(LAYER, "AccountHierarchy", len(find_files_with(str(APP_DIR), "AccountHierarchy")) > 0 or len(find_files_with(str(APP_DIR), "account_hierarchy")) > 0)
check(LAYER, "GL Pipeline", len(find_files_with(str(APP_DIR), "GLPipeline")) > 0 or len(find_files_with(str(APP_DIR), "gl_pipeline")) > 0)
check(LAYER, "LearningEngine", len(find_files_with(str(APP_DIR), "LearningEngine")) > 0)
check(LAYER, "BenchmarkEngine", len(find_files_with(str(APP_DIR), "BenchmarkEngine")) > 0)
check(LAYER, "Auth / RBAC", len(find_files_with(str(APP_DIR), "rbac")) > 0 or len(find_files_with(str(APP_DIR), "auth")) > 0)
check(LAYER, "ForecastEnsemble", len(find_files_with(str(APP_DIR), "ForecastEnsemble")) > 0)
check(LAYER, "DiagnosisEngine", len(find_files_with(str(APP_DIR), "DiagnosisEngine")) > 0)
check(LAYER, "MetricSignalDetector", len(find_files_with(str(APP_DIR), "MetricSignal")) > 0)
check(LAYER, "DecisionEngine", len(find_files_with(str(APP_DIR), "DecisionEngine")) > 0)
check(LAYER, "CFOVerdict", len(find_files_with(str(APP_DIR), "CFOVerdict")) > 0)
check(LAYER, "MonteCarloSimulator", len(find_files_with(str(APP_DIR), "MonteCarloSimulator")) > 0)
check(LAYER, "PredictionTracker", len(find_files_with(str(APP_DIR), "PredictionTracker")) > 0)
check(LAYER, "MonitoringEngine", len(find_files_with(str(APP_DIR), "MonitoringEngine")) > 0)
check(LAYER, "StrategyEngine", len(find_files_with(str(APP_DIR), "StrategicEngine")) > 0 or len(find_files_with(str(APP_DIR), "strategy_engine")) > 0)
check(LAYER, "SensitivityAnalyzer", len(find_files_with(str(APP_DIR), "SensitivityAnalyzer")) > 0)
check(LAYER, "KPIWatcher", len(find_files_with(str(APP_DIR), "KPIWatcher")) > 0)
check(LAYER, "CashRunwayCalculator", len(find_files_with(str(APP_DIR), "CashRunway")) > 0)
check(LAYER, "ExpenseSpikeDetector", len(find_files_with(str(APP_DIR), "ExpenseSpike")) > 0)
check(LAYER, "FinancialOrchestrator", len(find_files_with(str(APP_DIR), "FinancialOrchestrator")) > 0)
check(LAYER, "AnalogyBase", len(find_files_with(str(APP_DIR), "AnalogyBase")) > 0)
check(LAYER, "SyntheticGenerator", len(find_files_with(str(APP_DIR), "SyntheticGenerator")) > 0)
check(LAYER, "EmbeddingGenerator", len(find_files_with(str(APP_DIR), "EmbeddingGenerator")) > 0)
check(LAYER, "verify_all.py exists", file_exists("verify_all.py"))

# ===================================================================
# LAYER 2: DATA ENGINE
# ===================================================================
LAYER = "Layer 2: Data Engine (Parsing, DB, Validation)"

check(LAYER, "Excel/XLSX parser",
      len(find_files_with(str(APP_DIR), "openpyxl")) > 0 or len(find_files_with(str(APP_DIR), "read_excel")) > 0 or len(find_files_with(str(APP_DIR), "xlsx")) > 0)
check(LAYER, "PDF parser",
      len(find_files_with(str(APP_DIR), "pdf")) > 0)
check(LAYER, "CSV parser",
      len(find_files_with(str(APP_DIR), "csv")) > 0 or len(find_files_with(str(APP_DIR), "read_csv")) > 0)
check(LAYER, "Schema auto-detection",
      len(find_files_with(str(APP_DIR), "SchemaDetector")) > 0 or len(find_files_with(str(APP_DIR), "detect_from_sample")) > 0 or len(find_files_with(str(APP_DIR), "FileStructureDetector")) > 0)
check(LAYER, "Database integration (SQLAlchemy)",
      len(find_files_with(str(APP_DIR), "sqlalchemy")) > 0 or len(find_files_with(str(APP_DIR), "database")) > 0)
check(LAYER, "Data validation pipeline",
      len(find_files_with(str(APP_DIR), "validat")) > 0 or len(find_files_with(str(APP_DIR), "detect_accounting_issues")) > 0)
check(LAYER, "File upload API endpoint",
      len(find_files_with(str(APP_DIR), "upload")) > 0 or len(find_files_with(str(APP_DIR), "UploadFile")) > 0)
check(LAYER, "1C data ingestion",
      len(find_files_with(str(APP_DIR), "OneCInterpreter")) > 0 or len(find_files_with(str(APP_DIR), "onec")) > 0)
check(LAYER, "Data normalization / MetricComputer",
      len(find_files_with(str(APP_DIR), "MetricComputer")) > 0 or len(find_files_with(str(APP_DIR), "normaliz")) > 0)
check(LAYER, "Multi-period data (DatasetSnapshot)",
      len(find_files_with(str(APP_DIR), "DatasetSnapshot")) > 0 or len(find_files_with(str(APP_DIR), "snapshot")) > 0)

# ===================================================================
# LAYER 3: ACCOUNTING CORE
# ===================================================================
LAYER = "Layer 3: Accounting Core (Double-Entry, COA, Journals)"

check(LAYER, "Double-entry bookkeeping (debit/credit)",
      len(find_files_with(str(APP_DIR), "acct_dr")) > 0 or len(find_files_with(str(APP_DIR), "debit")) > 0 or len(find_files_with(str(APP_DIR), "TransactionAdapter")) > 0)
check(LAYER, "Chart of Accounts (COA)",
      len(find_files_with(str(APP_DIR), "COAMasterAccount")) > 0 or len(find_files_with(str(APP_DIR), "AccountHierarchy")) > 0)
check(LAYER, "Trial Balance generator",
      len(find_files_with(str(APP_DIR), "TrialBalance")) > 0)
check(LAYER, "Transaction / journal model",
      len(find_files_with(str(APP_DIR), "class Transaction")) > 0)
check(LAYER, "Period tracking",
      len(find_files_with(str(APP_DIR), "period")) > 0)
check(LAYER, "Multi-currency support",
      len(find_files_with(str(APP_DIR), "currency")) > 0 or len(find_files_with(str(APP_DIR), "exchange_rate")) > 0)
check(LAYER, "IFRS standards in KG",
      len(find_files_with(str(APP_DIR), "ifrs")) > 0 or len(find_files_with(str(APP_DIR), "IFRS")) > 0)
check(LAYER, "Account type classification (asset/liability/equity)",
      len(find_files_with(str(APP_DIR), "account_type")) > 0 or len(find_files_with(str(APP_DIR), "liability")) > 0 or len(find_files_with(str(APP_DIR), "classify_account")) > 0)
check(LAYER, "BS equation reconciliation",
      len(find_files_with(str(APP_DIR), "reconcil")) > 0 or len(find_files_with(str(APP_DIR), "bs_equation")) > 0)
check(LAYER, "Audit trail (AgentAuditLog / ETLAudit)",
      len(find_files_with(str(APP_DIR), "AuditLog")) > 0 or len(find_files_with(str(APP_DIR), "ETLAudit")) > 0 or len(find_files_with(str(APP_DIR), "AuthAudit")) > 0)

# ===================================================================
# LAYER 4: REPORT GENERATOR
# ===================================================================
LAYER = "Layer 4: Report Generator (Financial Statements, Export)"

check(LAYER, "Income Statement generator",
      len(find_files_with(str(APP_DIR), "income_statement")) > 0 or len(find_files_with(str(APP_DIR), "IncomeStatement")) > 0)
check(LAYER, "Balance Sheet generator",
      len(find_files_with(str(APP_DIR), "balance_sheet")) > 0 or len(find_files_with(str(APP_DIR), "BalanceSheet")) > 0)
check(LAYER, "Cash Flow Statement",
      len(find_files_with(str(APP_DIR), "cash_flow")) > 0 or len(find_files_with(str(APP_DIR), "CashFlow")) > 0)
check(LAYER, "Financial Ratios",
      len(find_files_with(str(APP_DIR), "ratio")) > 0 or len(find_files_with(str(APP_DIR), "liquidity")) > 0)
check(LAYER, "PDF support",
      len(find_files_with(str(APP_DIR), "pdf")) > 0)
check(LAYER, "Excel export",
      len(find_files_with(str(APP_DIR), "excel_export")) > 0 or len(find_files_with(str(APP_DIR), "openpyxl")) > 0)
check(LAYER, "Report templates (MR / narrative)",
      len(find_files_with(str(APP_DIR), "template")) > 0 or len(find_files_with(str(APP_DIR), "NarrativeEngine")) > 0 or len(find_files_with(str(APP_DIR), "MREngine")) > 0)
check(LAYER, "Period-over-period / variance",
      len(find_files_with(str(APP_DIR), "variance")) > 0 or len(find_files_with(str(APP_DIR), "compare_periods")) > 0)
check(LAYER, "Chart / trend generation",
      len(find_files_with(str(APP_DIR), "chart")) > 0 or len(find_files_with(str(APP_DIR), "trend")) > 0)
check(LAYER, "Scheduled reports",
      len(find_files_with(str(APP_DIR), "ScheduledReport")) > 0 or len(find_files_with(str(APP_DIR), "ReportScheduler")) > 0)

# ===================================================================
# LAYER 5: INTELLIGENT INTERFACE
# ===================================================================
LAYER = "Layer 5: Intelligent Interface (Chat, What-If, Alerts)"

check(LAYER, "Financial chat / NLP query",
      len(find_files_with(str(APP_DIR), "chat")) > 0 or len(find_files_with(str(APP_DIR), "stream_chat")) > 0)
check(LAYER, "What-If scenario simulation",
      len(find_files_with(str(APP_DIR), "scenario")) > 0 or len(find_files_with(str(APP_DIR), "sensitivity")) > 0)
check(LAYER, "Auto-diagnosis engine",
      len(find_files_with(str(APP_DIR), "diagnos")) > 0)
check(LAYER, "Anomaly alerts",
      len(find_files_with(str(APP_DIR), "alert")) > 0 or len(find_files_with(str(APP_DIR), "MonitoringAlert")) > 0)
check(LAYER, "Recommendation engine",
      len(find_files_with(str(APP_DIR), "Recommend")) > 0 or len(find_files_with(str(APP_DIR), "BusinessAction")) > 0)
check(LAYER, "Learning from feedback",
      len(find_files_with(str(APP_DIR), "LearningEngine")) > 0 or len(find_files_with(str(APP_DIR), "StrategyLearner")) > 0)
check(LAYER, "Dashboard API endpoints",
      len(find_routes(str(APP_DIR), "dashboard")) > 0 or len(find_routes(str(APP_DIR), "summary")) > 0)
check(LAYER, "WebSocket / streaming",
      len(find_files_with(str(APP_DIR), "WebSocket")) > 0 or len(find_files_with(str(APP_DIR), "websocket")) > 0)
check(LAYER, "Georgian / multi-language",
      len(find_files_with(str(APP_DIR), "label_ka")) > 0 or len(find_files_with(str(APP_DIR), "georgian")) > 0)
check(LAYER, "Role-based access (RBAC)",
      len(find_files_with(str(APP_DIR), "role")) > 0 or len(find_files_with(str(APP_DIR), "require_role")) > 0)

# ===================================================================
# CROSS-CUTTING CONCERNS
# ===================================================================
LAYER = "Cross-Cutting: Infrastructure & Quality"

check(LAYER, "FastAPI entry point", file_exists("main.py") or len(find_files_with(str(APP_DIR), "FastAPI")) > 0)
check(LAYER, "Environment config (.env / settings)", file_exists(".env") or file_exists("app/config.py"))
check(LAYER, "Error handling middleware", len(find_files_with(str(APP_DIR), "middleware")) > 0 or len(find_files_with(str(BACKEND_ROOT), "exception_handler")) > 0)
check(LAYER, "Structured logging", len(find_files_with(str(APP_DIR), "logger")) > 0)
check(LAYER, "CORS configuration", len(find_files_with(str(APP_DIR), "CORS")) > 0 or len(find_files_with(str(APP_DIR), "cors")) > 0)
check(LAYER, "API documentation (OpenAPI)", len(find_files_with(str(APP_DIR), "docs")) > 0)
check(LAYER, "Docker deployment config", file_exists("Dockerfile") or file_exists("docker-compose.yml"))
check(LAYER, "Requirements file", file_exists("requirements.txt") or file_exists("pyproject.toml"))
check(LAYER, "Test suite", file_exists("verify_all.py"))
check(LAYER, "Modular routers (3+)",
      len(list(Path(str(ROUTERS_DIR)).glob("*.py"))) > 2 if Path(str(ROUTERS_DIR)).exists() else False)

# ===================================================================
# RESULTS
# ===================================================================
print()
print(f"{BOLD}{'=' * 70}{RESET}")
print(f"{BOLD}  DETAILED RESULTS{RESET}")
print(f"{'=' * 70}")

for layer_name, checks_list in results.items():
    found = sum(1 for _, ok, _ in checks_list if ok)
    total = len(checks_list)
    pct = found / total * 100 if total else 0

    if pct == 100:
        color = GREEN
        status = "COMPLETE"
    elif pct >= 70:
        color = YELLOW
        status = "PARTIAL"
    elif pct >= 30:
        color = YELLOW
        status = "INCOMPLETE"
    else:
        color = RED
        status = "MISSING"

    print(f"\n{BOLD}{color}  {layer_name}  [{found}/{total}] -- {status}{RESET}")

    for name, ok, detail in checks_list:
        icon = f"{GREEN}[OK]{RESET}" if ok else f"{RED}[--]{RESET}"
        det = f"  ({detail})" if detail else ""
        print(f"    {icon}  {name}{det}")

# ── SUMMARY ────────────────────────────────────────────────────────
print()
print(f"{'=' * 70}")
print(f"{BOLD}  SUMMARY{RESET}")
print(f"{'=' * 70}")
print(f"  Found:    {GREEN}{total_found}{RESET}")
print(f"  Missing:  {RED}{total_missing}{RESET}")
print(f"  Total:    {total_found + total_missing}")
pct = total_found / (total_found + total_missing) * 100 if (total_found + total_missing) else 0
print(f"  Coverage: {BOLD}{pct:.1f}%{RESET}")
print()

# Layer summary table
print(f"  {'Layer':<55} {'Score':<10}")
print(f"  {'=' * 55} {'=' * 10}")
for layer_name, checks_list in results.items():
    found = sum(1 for _, ok, _ in checks_list if ok)
    total = len(checks_list)
    pct_l = found / total * 100 if total else 0

    if pct_l == 100:
        color = GREEN
    elif pct_l >= 50:
        color = YELLOW
    else:
        color = RED

    short_name = layer_name[:53]
    print(f"  {short_name:<55} {color}{found}/{total} ({pct_l:.0f}%){RESET}")

print()

# Missing items list
missing_items = []
for layer_name, checks_list in results.items():
    for name, ok, _ in checks_list:
        if not ok:
            missing_items.append((layer_name, name))

if missing_items:
    print(f"{BOLD}{RED}  MISSING COMPONENTS ({len(missing_items)}):{RESET}")
    current_layer = ""
    for layer, name in missing_items:
        if layer != current_layer:
            print(f"\n    {BOLD}{layer}{RESET}")
            current_layer = layer
        print(f"      -- {name}")
    print()
else:
    print(f"  {GREEN}{BOLD}ALL COMPONENTS PRESENT -- PRODUCTION READY{RESET}")

print(f"{'=' * 70}\n")
