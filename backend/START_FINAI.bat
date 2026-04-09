@echo off
title FinAI Financial Intelligence Platform v3.0
color 0A
echo.
echo  ================================================================
echo  ╔═══════════════════════════════════════════════════════════════╗
echo  ║       FinAI  Financial Intelligence Platform  v3.0          ║
echo  ║       NYX Core Thinker LLC                              ║
echo  ║       Multi-Agent Architecture (Phases A-M Complete)        ║
echo  ╚═══════════════════════════════════════════════════════════════╝
echo  ================================================================
echo.

cd /d "%~dp0"

:: Activate virtual environment
if exist "venv2\Scripts\activate.bat" (
    call venv2\Scripts\activate.bat
    echo  [OK] Virtual environment activated (venv2)
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated (venv)
) else (
    echo  [!] No virtual environment found, using system Python
)

:: Check required packages
echo  [..] Checking dependencies...
python -c "import fastapi, sqlalchemy, anthropic, numpy, pandas, openpyxl, httpx" 2>nul
if errorlevel 1 (
    echo  [!] Missing packages detected. Installing requirements...
    pip install -r requirements.txt --quiet
) else (
    echo  [OK] All core dependencies present
)

:: Create required directories
for %%D in (static,uploads,exports,logs,data) do (
    if not exist "%%D" mkdir "%%D"
)

:: Kill any process on port 9200
echo  [..] Checking port 9200...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9200" ^| findstr "LISTENING"') do (
    echo  [!] Port 9200 in use by PID %%a - killing...
    taskkill /PID %%a /F >nul 2>&1
    timeout /t 2 /nobreak >nul
)
echo  [OK] Port 9200 is free

:: Check Ollama
echo  [..] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo  [!] Ollama not running (optional - install from ollama.com)
    echo      Run: ollama pull mistral:7b  for local AI fallback
) else (
    echo  [OK] Ollama is running
)

:: Show feature status
echo.
echo  ================================================================
echo   MULTI-AGENT SYSTEM (6 Specialized Agents)
echo  ================================================================
echo   [+] Supervisor     Intent routing (rule-based + LLM fallback)
echo   [+] CalcAgent      Financial calculations, focused chat
echo   [+] DataAgent      Semantic enrichment, 3-pass COA classification
echo   [+] InsightAgent   Causal reasoning, scenario simulation
echo   [+] ReportAgent    Structured report generation (PDF export)
echo   [+] DecisionAgent  Decision intelligence, predictions, monitoring
echo.
echo  ================================================================
echo   INTELLIGENCE ENGINES
echo  ================================================================
echo   [+] 4-Tier LLM:        Cache ^> Claude ^> Ollama ^> Templates
echo   [+] Knowledge Graph:    710+ entities (accounts, rules, IFRS, COA)
echo   [+] CRA:                Collaborative Reasoning Architecture
echo   [+] Financial Reasoning: Causal chains, scenario simulation
echo   [+] Sensitivity:        Tornado, Monte Carlo, multi-variable sims
echo   [+] Strategy Engine:    Phased planning, time projection, learning
echo   [+] Orchestrator:       7-stage E2E pipeline (23ms execution)
echo   [+] Analogy Base:       Pattern matching, synthetic generation
echo.
echo  ================================================================
echo   FINANCIAL MODULES
echo  ================================================================
echo   [+] GL Pipeline:       GL ^> Trial Balance ^> IS ^> BS ^> CF
echo   [+] 1C COA Interpreter: Georgian/IFRS hybrid (406 accounts)
echo   [+] Consolidation:     IFRS 10 multi-entity, NCI, eliminations
echo   [+] AP Automation:     3-way match (Invoice/PO/GRN), exception mgmt
echo   [+] Sub-Ledger:        AR/AP aging, DSO/DPO analytics
echo   [+] Company 360:       Executive health dashboard, KPI tracking
echo   [+] Budgeting:         Budget vs actual, variance analysis
echo   [+] Benchmark Engine:  6 industry profiles, ratio comparison
echo   [+] Ensemble Forecast: 5 methods + backtest + inverse-MAPE
echo   [+] Anomaly Detection: Z-score, IQR, Benford's Law
echo.
echo  ================================================================
echo   GOVERNANCE ^& COMPLIANCE
echo  ================================================================
echo   [+] SOX/IFRS Compliance: Real-time monitoring, audit trail
echo   [+] Auth/RBAC:          JWT with jti revocation, audit logging
echo   [+] Data Lineage:       End-to-end provenance tracking
echo   [+] ESG ^& Sustainability: Carbon footprint, ESG scoring
echo.
echo  ================================================================
echo   MARKET DATA ^& EXTERNAL
echo  ================================================================
echo   [+] NBG Exchange Rates:  Live Georgian Lari rates
echo   [+] Yahoo Finance:       Commodity prices (Brent, WTI, NatGas)
echo   [+] EIA API:             Weekly Petroleum Reports, inventories
echo   [+] Geopolitical Risk:   Supply chain, route monitoring
echo.
echo  ================================================================
echo   FRONTEND (React 19 + TypeScript + Vite 8)
echo  ================================================================
echo   [+] 25+ pages: Dashboard, P^&L, BS, Revenue, Costs, Budget
echo   [+] Enterprise Charts: Treemap, Sunburst, Heatmap, Waterfall
echo   [+] Pivot Tables:      Grouping, aggregation, CSV export
echo   [+] Sankey/Funnel:     Revenue flow, conversion analysis
echo   [+] Monte Carlo:       Distribution visualization
echo   [+] Geo Map:           Strategic asset ^& supply chain overlay
echo   [+] Dark/Light Mode:   Corporate Fiori-grade theme toggle
echo   [+] ECharts 6 + Recharts + ReactFlow + react-grid-layout
echo.
echo  ================================================================
echo   VERIFICATION: 397/397 unit checks + 39/39 E2E pipeline
echo  ================================================================
echo.
echo   Backend:     http://localhost:9200
echo   Frontend:    http://localhost:3000
echo   API Docs:    http://localhost:9200/api/docs
echo   Health:      http://localhost:9200/health
echo.
echo   Press Ctrl+C to stop the server
echo  ================================================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 9200

pause
