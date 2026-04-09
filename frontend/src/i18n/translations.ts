export type Lang = 'en' | 'ka';

const translations: Record<string, Record<Lang, string>> = {
  // Navigation groups
  'nav.workspace': { en: 'WORKSPACE', ka: 'სამუშაო სივრცე' },
  'nav.analytics': { en: 'ANALYTICS', ka: 'ანალიტიკა' },
  'nav.intelligence': { en: 'INTELLIGENCE', ka: 'ინტელექტი' },
  'nav.decision_engine': { en: 'DECISION ENGINE', ka: 'გადაწყვეტილების სისტემა' },
  'nav.monitoring': { en: 'MONITORING', ka: 'მონიტორინგი' },
  'nav.data': { en: 'DATA', ka: 'მონაცემები' },
  'nav.market': { en: 'MARKET', ka: 'ბაზარი' },
  'nav.system': { en: 'SYSTEM', ka: 'სისტემა' },

  // Navigation items
  'nav.dashboard': { en: 'Dashboard', ka: 'მთავარი პანელი' },
  'nav.data_library': { en: 'Data & Library', ka: 'მონაცემები და ბიბლიოთეკა' },
  'nav.pnl': { en: 'P&L', ka: 'მოგება-ზარალი' },
  'nav.balance_sheet': { en: 'Balance Sheet', ka: 'ბალანსი' },
  'nav.revenue': { en: 'Revenue', ka: 'შემოსავალი' },
  'nav.costs': { en: 'Costs', ka: 'ხარჯები' },
  'nav.budget': { en: 'Budget', ka: 'ბიუჯეტი' },
  'nav.mr_reports': { en: 'MR Reports', ka: 'ანგარიშები' },
  'nav.cash_runway': { en: 'Cash Runway', ka: 'ფულადი რესურსი' },
  'nav.kpi_monitor': { en: 'KPI Monitor', ka: 'KPI მონიტორი' },
  'nav.ai_intelligence': { en: 'AI Intelligence', ka: 'AI ინტელექტი' },
  'nav.benchmarks': { en: 'Benchmarks', ka: 'შედარებები' },
  'nav.forecasts': { en: 'Forecasts', ka: 'პროგნოზები' },
  'nav.gl_pipeline': { en: 'GL Pipeline', ka: 'GL პაიპლაინი' },
  'nav.orchestrator': { en: 'Orchestrator', ka: 'ორკესტრატორი' },
  'nav.strategy': { en: 'Strategy', ka: 'სტრატეგია' },
  'nav.sensitivity': { en: 'Sensitivity', ka: 'მგრძნობელობა' },
  'nav.decisions': { en: 'Decisions', ka: 'გადაწყვეტილებები' },
  'nav.analogies': { en: 'Analogies', ka: 'ანალოგიები' },
  'nav.alerts': { en: 'Alerts', ka: 'შეტყობინებები' },
  'nav.predictions': { en: 'Predictions', ka: 'პროგნოზირება' },
  'nav.transactions': { en: 'Transactions', ka: 'ტრანზაქციები' },
  'nav.market_data': { en: 'Market Data', ka: 'საბაზრო მონაცემები' },
  'nav.system_status': { en: 'System Status', ka: 'სისტემის სტატუსი' },
  'nav.ai_evaluation': { en: 'AI Evaluation', ka: 'AI შეფასება' },
  'nav.tools': { en: 'Tools', ka: 'ინსტრუმენტები' },
  'nav.deep_reasoning': { en: 'Deep Reasoning', ka: 'ღრმა ანალიზი' },
  'nav.workflow': { en: 'Agent Workflow', ka: 'აგენტის პროცესი' },
  'nav.ai_report': { en: 'AI Report', ka: 'AI ანგარიში' },
  'nav.profitability': { en: 'Product Profitability', ka: 'პროდუქტის მომგებიანობა' },
  'nav.ingest': { en: 'Intelligent Ingestion', ka: 'ინტელექტუალური ინგესტაცია' },
  'nav.journal': { en: 'Journal Entries', ka: 'ბუღალტრული ჩანაწერები' },
  'nav.periods': { en: 'Period Close', ka: 'პერიოდის დახურვა' },

  // Page titles
  'page.dashboard': { en: 'Financial Dashboard', ka: 'ფინანსური პანელი' },
  'page.upload': { en: 'Upload Financial Data', ka: 'ფინანსური მონაცემების ატვირთვა' },
  'page.data_library': { en: 'Data & Library', ka: 'მონაცემები და ბიბლიოთეკა' },
  'page.pnl': { en: 'Income Statement', ka: 'მოგება-ზარალის უწყისი' },
  'page.balance_sheet': { en: 'Balance Sheet', ka: 'ბალანსი' },
  'page.revenue': { en: 'Revenue Analysis', ka: 'შემოსავლის ანალიზი' },
  'page.costs': { en: 'Cost Analysis', ka: 'ხარჯების ანალიზი' },
  'page.orchestrator': { en: 'Orchestrator', ka: 'ორკესტრატორი' },
  'page.strategy': { en: 'Strategy', ka: 'სტრატეგია' },
  'page.sensitivity': { en: 'Sensitivity Analysis', ka: 'მგრძნობელობის ანალიზი' },
  'page.decisions': { en: 'Decisions', ka: 'გადაწყვეტილებები' },

  // Common UI
  'ui.refresh': { en: 'Refresh', ka: 'განახლება' },
  'ui.upload': { en: 'Upload', ka: 'ატვირთვა' },
  'ui.export_pdf': { en: 'Export PDF', ka: 'PDF ექსპორტი' },
  'ui.export_excel': { en: 'Export Excel', ka: 'Excel ექსპორტი' },
  'ui.run_analysis': { en: 'Run Analysis', ka: 'ანალიზის გაშვება' },
  'ui.generate': { en: 'Generate', ka: 'გენერირება' },
  'ui.download': { en: 'Download', ka: 'ჩამოტვირთვა' },
  'ui.logout': { en: 'Logout', ka: 'გამოსვლა' },
  'ui.upload_data': { en: 'Upload Data', ka: 'მონაცემების ატვირთვა' },
  'ui.upload_first': { en: 'Upload a file to begin', ka: 'ატვირთეთ ფაილი დასაწყებად' },
  'ui.no_data': { en: 'No data available', ka: 'მონაცემები არ არის' },
  'ui.loading': { en: 'Loading...', ka: 'იტვირთება...' },
  'ui.error': { en: 'Error', ka: 'შეცდომა' },
  'ui.retry': { en: 'Retry', ka: 'ხელახლა ცდა' },

  // Financial terms
  'fin.revenue': { en: 'Revenue', ka: 'შემოსავალი' },
  'fin.cogs': { en: 'Cost of Goods Sold', ka: 'გაყიდული საქონლის ღირებულება' },
  'fin.gross_profit': { en: 'Gross Profit', ka: 'მთლიანი მოგება' },
  'fin.net_profit': { en: 'Net Profit', ka: 'წმინდა მოგება' },
  'fin.ebitda': { en: 'EBITDA', ka: 'EBITDA' },
  'fin.gross_margin': { en: 'Gross Margin', ka: 'მთლიანი მარჟა' },
  'fin.net_margin': { en: 'Net Margin', ka: 'წმინდა მარჟა' },
  'fin.total_assets': { en: 'Total Assets', ka: 'მთლიანი აქტივები' },
  'fin.total_liabilities': { en: 'Total Liabilities', ka: 'მთლიანი ვალდებულებები' },
  'fin.total_equity': { en: 'Total Equity', ka: 'მთლიანი კაპიტალი' },
  'fin.current_ratio': { en: 'Current Ratio', ka: 'მიმდინარე კოეფიციენტი' },
  'fin.debt_to_equity': { en: 'D/E Ratio', ka: 'ვალი/კაპიტალი' },
  'fin.cash_runway': { en: 'Cash Runway', ka: 'ფულადი რესურსი' },
  'fin.selling_expenses': { en: 'Selling Expenses', ka: 'გაყიდვის ხარჯები' },
  'fin.admin_expenses': { en: 'Administrative Expenses', ka: 'ადმინისტრაციული ხარჯები' },
  'fin.depreciation': { en: 'Depreciation', ka: 'ამორტიზაცია' },
  'fin.operating_expenses': { en: 'Operating Expenses', ka: 'საოპერაციო ხარჯები' },

  // Dashboard specific
  'dash.real_time': { en: 'Real-time financial intelligence', ka: 'რეალურ-დროის ფინანსური ინტელექტი' },
  'dash.cost_structure': { en: 'Cost Structure', ka: 'ხარჯების სტრუქტურა' },
  'dash.pnl_summary': { en: 'P&L Summary', ka: 'მოგ/ზარ შეჯამება' },
  'dash.recent_alerts': { en: 'Recent Alerts', ka: 'ბოლო შეტყობინებები' },
  'dash.quick_actions': { en: 'Quick Actions', ka: 'სწრაფი მოქმედებები' },
  'dash.upload_financial': { en: 'Upload Financial Data', ka: 'ფინანსური მონაცემების ატვირთვა' },
  'dash.generate_report': { en: 'Generate Full Report', ka: 'სრული ანგარიშის გენერირება' },
  'dash.executive_brief': { en: 'Executive Brief', ka: 'აღმასრულებელი მოხსენება' },
  'dash.ask_ai': { en: 'Ask AI', ka: 'ჰკითხე AI-ს' },
  'dash.key_metrics': { en: 'KEY METRICS', ka: 'ძირითადი მეტრიკები' },
  'dash.financial_story': { en: 'FINANCIAL STORY', ka: 'ფინანსური ისტორია' },
  'dash.intelligence': { en: 'INTELLIGENCE', ka: 'ინტელიგენცია' },
  'dash.health_score': { en: 'Health Score', ka: 'ჯანმრთელობის ქულა' },
  'dash.risks': { en: 'Risk Signals', ka: 'რისკის სიგნალები' },
  'dash.recommendations': { en: 'Recommendations', ka: 'რეკომენდაციები' },
  'dash.opportunities': { en: 'Opportunities', ka: 'შესაძლებლობები' },
  'dash.kpi_status': { en: 'KPI Status', ka: 'KPI სტატუსი' },
  'dash.run_analysis': { en: 'Run Analysis', ka: 'ანალიზის გაშვება' },
  'dash.export_report': { en: 'Export Report', ka: 'რეპორტის ექსპორტი' },
  'dash.take_action': { en: 'Take Action', ka: 'მოქმედება' },
  'dash.investigate': { en: 'Investigate', ka: 'გამოკვლევა' },
  'dash.total_impact': { en: 'Total Potential Impact', ka: 'მთლიანი პოტენციური ეფექტი' },
  'dash.balance_sheet': { en: 'Balance Sheet Summary', ka: 'ბალანსის შეჯამება' },
  'dash.why_this_score': { en: 'Why this score?', ka: 'რატომ ეს ქულა?' },
  'dash.no_data': { en: 'No Financial Data', ka: 'ფინანსური მონაცემები არ არის' },
  'dash.ai_narrative': { en: 'AI Narrative', ka: 'AI ნარატივი' },

  // Agent panel
  'agent.title': { en: 'FinAI Agent', ka: 'FinAI აგენტი' },
  'agent.context': { en: 'context', ka: 'კონტექსტი' },
  'agent.ask_anything': { en: 'Ask anything...', ka: 'იკითხეთ ნებისმიერი...' },
  'agent.ask_about': { en: 'Ask FinAI anything about your financial data.', ka: 'ჰკითხეთ FinAI-ს ფინანსური მონაცემების შესახებ.' },

  // Chat
  'chat.ask_anything': { en: 'Ask FinAI Anything', ka: 'ჰკითხე FinAI-ს ნებისმიერი' },
  'chat.placeholder': { en: 'Ask about your financial data...', ka: 'იკითხეთ ფინანსური მონაცემების შესახებ...' },
  'chat.agent_name': { en: 'FinAI Agent', ka: 'FinAI აგენტი' },

  // Upload
  'upload.drag_drop': { en: 'Drag & drop your financial file here', ka: 'გადმოიტანეთ ფინანსური ფაილი აქ' },
  'upload.browse': { en: 'Browse Files', ka: 'ფაილების დათვალიერება' },
  'upload.processing': { en: 'Processing financial data with AI...', ka: 'ფინანსური მონაცემების დამუშავება AI-ით...' },
  'upload.complete': { en: 'Upload Complete', ka: 'ატვირთვა დასრულებულია' },
  'upload.how_it_works': { en: 'How it works', ka: 'როგორ მუშაობს' },

  // Action controls
  'action.export': { en: 'Export', ka: 'ექსპორტი' },
  'action.export_pdf': { en: 'Export PDF', ka: 'PDF ექსპორტი' },
  'action.export_excel': { en: 'Export Excel', ka: 'Excel ექსპორტი' },
  'action.export_csv': { en: 'Export CSV', ka: 'CSV ექსპორტი' },
  'action.compare_with': { en: 'Compare with', ka: 'შედარება' },
  'action.no_comparison': { en: 'No comparison', ka: 'შედარების გარეშე' },
  'action.all_segments': { en: 'All Segments', ka: 'ყველა სეგმენტი' },
  'action.wholesale': { en: 'Wholesale', ka: 'საბითუმო' },
  'action.retail': { en: 'Retail', ka: 'საცალო' },
  'action.other': { en: 'Other', ka: 'სხვა' },
  'action.view_summary': { en: 'Summary', ka: 'შეჯამება' },
  'action.view_detailed': { en: 'Detailed', ka: 'დეტალური' },
  'action.sort_by': { en: 'Sort by', ka: 'სორტირება' },
  'action.sort_amount': { en: 'Amount', ka: 'თანხა' },
  'action.sort_name': { en: 'Name', ka: 'სახელი' },
  'action.sort_category': { en: 'Category', ka: 'კატეგორია' },

  // Report builder
  'report.type': { en: 'Report Type', ka: 'ანგარიშის ტიპი' },
  'report.executive_brief': { en: 'Executive Brief', ka: 'აღმასრულებელი მოხსენება' },
  'report.full_analysis': { en: 'Full Analysis', ka: 'სრული ანალიზი' },
  'report.board_deck': { en: 'Board Deck', ka: 'დირექტორთა პრეზენტაცია' },
  'report.audit_workpaper': { en: 'Audit Workpaper', ka: 'აუდიტის სამუშაო ქაღალდი' },
  'report.sections': { en: 'Sections to Include', ka: 'ჩასართავი სექციები' },
  'report.depth': { en: 'Analysis Depth', ka: 'ანალიზის სიღრმე' },
  'report.depth_high': { en: 'High-level', ka: 'ზოგადი' },
  'report.depth_standard': { en: 'Standard', ka: 'სტანდარტული' },
  'report.depth_deep': { en: 'Deep drill-down', ka: 'ღრმა ანალიზი' },
  'report.format': { en: 'Output Format', ka: 'ფორმატი' },
  'report.language': { en: 'Language', ka: 'ენა' },
  'report.generate': { en: 'Generate Report', ka: 'ანგარიშის გენერირება' },

  // Table columns
  'col.current': { en: 'Current', ka: 'მიმდინარე' },
  'col.prior': { en: 'Prior', ka: 'წინა' },
  'col.variance': { en: 'Variance', ka: 'ვარიაცია' },
  'col.variance_pct': { en: 'Var %', ka: 'ვარ %' },

  // Ontology Explorer
  'onto.knowledge_graph': { en: 'Financial Knowledge Graph', ka: 'ფინანსური ცოდნის გრაფი' },
  'onto.search_placeholder': { en: 'Ask the ontology...', ka: 'ჰკითხეთ ონტოლოგიას...' },
  'onto.object_types': { en: 'OBJECT TYPES', ka: 'ობიექტის ტიპები' },
  'onto.objects_in_graph': { en: 'objects in graph', ka: 'ობიექტი გრაფში' },
  'onto.graph_view': { en: 'Graph View', ka: 'გრაფის ხედი' },
  'onto.list_view': { en: 'List View', ka: 'სიის ხედი' },

  // Monitoring
  'mon.alerts': { en: 'Alerts', ka: 'შეტყობინებები' },
  'mon.kpi_status': { en: 'KPI Status', ka: 'KPI სტატუსი' },
  'mon.cash_runway': { en: 'Cash Runway', ka: 'ფულადი რესურსი' },
  'mon.acknowledge': { en: 'Acknowledge', ka: 'აღიარება' },
  'mon.resolve': { en: 'Resolve', ka: 'გადაჭრა' },
  'mon.escalate': { en: 'Escalate', ka: 'ესკალაცია' },
  'mon.dismiss': { en: 'Dismiss', ka: 'უარყოფა' },
  'mon.no_alerts': { en: 'No active alerts', ka: 'აქტიური შეტყობინებები არ არის' },

  // Sensitivity
  'sens.tornado': { en: 'Tornado Chart', ka: 'ტორნადოს დიაგრამა' },
  'sens.monte_carlo': { en: 'Monte Carlo Simulation', ka: 'მონტე კარლოს სიმულაცია' },
  'sens.what_if': { en: 'What If?', ka: 'რა თუ?' },
  'sens.run_scenario': { en: 'Run Scenario', ka: 'სცენარის გაშვება' },
  'sens.reset': { en: 'Reset to Current', ka: 'მიმდინარეზე დაბრუნება' },

  // Company 360
  'c360.financial_snapshot': { en: 'Financial Snapshot', ka: 'ფინანსური სურათი' },
  'c360.key_ratios': { en: 'Key Ratios', ka: 'ძირითადი კოეფიციენტები' },
  'c360.risks_recs': { en: 'Risks & Recommendations', ka: 'რისკები და რეკომენდაციები' },
  'c360.subledgers': { en: 'Sub-Ledger Summary', ka: 'ქვე-წიგნის შეჯამება' },
  'c360.trends': { en: 'Trends', ka: 'ტენდენციები' },
  'c360.recent_activity': { en: 'Recent Activity', ka: 'ბოლო აქტივობა' },
  'c360.causal_chain': { en: 'Causal Chain', ka: 'მიზეზობრივი ჯაჭვი' },

  // Strategy
  'strat.run_strategy': { en: 'Run Strategy', ka: 'სტრატეგიის გაშვება' },
  'strat.phases': { en: 'Phases', ka: 'ფაზები' },
  'strat.investment': { en: 'Total Investment', ka: 'მთლიანი ინვესტიცია' },
  'strat.timeline': { en: 'Timeline', ka: 'ვადები' },

  // Decisions
  'dec.cfo_verdict': { en: 'CFO Verdict', ka: 'CFO-ს ვერდიქტი' },
  'dec.ranked_actions': { en: 'Ranked Actions', ka: 'რეიტინგული ქმედებები' },
  'dec.generate_verdict': { en: 'Generate CFO Verdict', ka: 'CFO ვერდიქტის გენერირება' },
  'dec.roi': { en: 'ROI', ka: 'ROI' },
  'dec.risk_level': { en: 'Risk Level', ka: 'რისკის დონე' },

  // Workflow
  'wf.pipeline': { en: 'Intelligence Pipeline', ka: 'ინტელექტის პაიპლაინი' },
  'wf.composable': { en: 'Composable Workflows', ka: 'კომპოზიციური სამუშაო პროცესები' },
  'wf.stages': { en: 'stages', ka: 'ეტაპი' },
  'wf.steps': { en: 'steps', ka: 'ნაბიჯი' },

  // Dashboard — data freshness
  'dash.just_now': { en: 'Just now', ka: 'ახლახანს' },
  'dash.updated_min_ago': { en: 'min ago', ka: 'წუთის წინ' },
  'dash.updated_hours_ago': { en: 'h ago', ka: 'სთ წინ' },
  'dash.financial_health': { en: 'Financial Health', ka: 'ფინანსური ჯანმრთელობა' },
  'dash.pnl_bridge': { en: 'P&L Bridge', ka: 'მოგ/ზარ ხიდი' },
  'dash.cause_effect': { en: 'Cause-Effect Chain', ka: 'მიზეზ-შედეგობრივი ჯაჭვი' },
  'dash.empty_desc': { en: 'Upload a Trial Balance or P&L report to activate the intelligence platform', ka: 'ატვირთეთ საცდელი ბალანსი ან მოგება-ზარალის ანგარიში ინტელექტის პლატფორმის გასააქტიურებლად' },
  'dash.no_health_breakdown': { en: 'No health breakdown available yet.', ka: 'ჯანმრთელობის დეტალები ჯერ არ არის ხელმისაწვდომი.' },
  'dash.no_critical_risks': { en: 'No critical risks', ka: 'კრიტიკული რისკები არ არის' },
  'dash.recent_activity': { en: 'Recent Activity', ka: 'ბოლო აქტივობა' },
  'dash.revenue_profit_trends': { en: 'Revenue & Profit Trends', ka: 'შემოსავლებისა და მოგების ტენდენციები' },
  'dash.accounts_receivable': { en: 'Accounts Receivable', ka: 'მისაღები ანგარიშები' },
  'dash.accounts_payable': { en: 'Accounts Payable', ka: 'გადასახდელი ანგარიშები' },
  'dash.fixed_assets': { en: 'Fixed Assets', ka: 'ძირითადი საშუალებები' },
  'dash.causal_drivers': { en: 'Causal Drivers', ka: 'მიზეზობრივი ფაქტორები' },
  'dash.annual_hint': { en: 'months loaded — switch to Year view for full picture', ka: 'თვე ჩატვირთულია — გადართეთ წლიურ ხედზე სრული სურათისთვის' },

  // Waterfall chart labels
  'fin.chart_revenue': { en: 'Revenue', ka: 'შემოსავალი' },
  'fin.chart_cogs': { en: 'COGS', ka: 'თვითღირებულება' },
  'fin.chart_gp': { en: 'GP', ka: 'მთლ.მოგ' },
  'fin.chart_opex': { en: 'OpEx', ka: 'საოპ.ხარჯი' },
  'fin.chart_ebitda': { en: 'EBITDA', ka: 'EBITDA' },
  'fin.chart_da': { en: 'D&A', ka: 'ამორტ.' },
  'fin.chart_net': { en: 'Net', ka: 'წმინდა' },

  // Status descriptors
  'fin.margin_healthy': { en: 'healthy', ka: 'ჯანსაღი' },
  'fin.margin_moderate': { en: 'moderate', ka: 'საშუალო' },
  'fin.margin_thin': { en: 'thin', ka: 'მცირე' },
  'fin.status_profitable': { en: 'profitable', ka: 'მომგებიანი' },
  'fin.status_loss_making': { en: 'loss-making', ka: 'წამგებიანი' },
  'fin.ebitda_margin': { en: 'EBITDA Margin', ka: 'EBITDA მარჟა' },
  'fin.asset_turnover': { en: 'Asset Turnover', ka: 'აქტივების ბრუნვა' },
  'fin.cash': { en: 'Cash', ka: 'ფულადი სახსრები' },

  // KPI status labels
  'fin.status_critical': { en: 'Critical', ka: 'კრიტიკული' },
  'fin.status_below_target': { en: 'Below Target', ka: 'სამიზნეს ქვემოთ' },
  'fin.status_on_target': { en: 'On Target', ka: 'სამიზნეზე' },
  'fin.status_healthy': { en: 'Healthy', ka: 'ჯანსაღი' },

  // View mode buttons
  'ui.view_month': { en: 'Month', ka: 'თვე' },
  'ui.view_quarter': { en: 'Quarter', ka: 'კვარტალი' },
  'ui.view_ytd': { en: 'YTD', ka: 'წლის დასაწყისიდან' },
  'ui.view_year': { en: 'Year', ka: 'წელი' },

  // Month names
  'ui.month_jan': { en: 'Jan', ka: 'იან' },
  'ui.month_feb': { en: 'Feb', ka: 'თებ' },
  'ui.month_mar': { en: 'Mar', ka: 'მარ' },
  'ui.month_apr': { en: 'Apr', ka: 'აპრ' },
  'ui.month_may': { en: 'May', ka: 'მაი' },
  'ui.month_jun': { en: 'Jun', ka: 'ივნ' },
  'ui.month_jul': { en: 'Jul', ka: 'ივლ' },
  'ui.month_aug': { en: 'Aug', ka: 'აგვ' },
  'ui.month_sep': { en: 'Sep', ka: 'სექ' },
  'ui.month_oct': { en: 'Oct', ka: 'ოქტ' },
  'ui.month_nov': { en: 'Nov', ka: 'ნოე' },
  'ui.month_dec': { en: 'Dec', ka: 'დეკ' },
};

let currentLang: Lang = 'en';

export function setLang(lang: Lang) {
  currentLang = lang;
}

export function getLang(): Lang {
  return currentLang;
}

export function t(key: string): string {
  return translations[key]?.[currentLang] ?? translations[key]?.en ?? key;
}

export function monthNames(): string[] {
  return [
    t('ui.month_jan'), t('ui.month_feb'), t('ui.month_mar'), t('ui.month_apr'),
    t('ui.month_may'), t('ui.month_jun'), t('ui.month_jul'), t('ui.month_aug'),
    t('ui.month_sep'), t('ui.month_oct'), t('ui.month_nov'), t('ui.month_dec'),
  ];
}

export default translations;
