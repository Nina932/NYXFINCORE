"""
FinAI Upload Intelligence
=========================
After parsing an uploaded file, this module generates a human-readable
assessment of what was found, what can be generated, and what's missing.
Returns structured data for the frontend to display:
- What sheets were detected and what type of data they contain
- What financial statements can be generated
- What's missing and HOW to get it from 1C
- Data quality score with specific flags
"""
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class SheetAssessment:
    name: str
    data_type: str          # "revenue_turnover", "cogs_turnover", "pl_mapping", "gl_journal", "trial_balance", "balance_sheet", "chart_of_accounts", "unknown"
    description_en: str
    description_ka: str
    row_count: int = 0
    has_amounts: bool = True
    key_insight: str = ""


@dataclass
class GenerationCapability:
    metric: str
    name_en: str
    name_ka: str
    available: bool
    source: str = ""        # Which sheet provides this
    confidence: str = ""    # "exact", "partial", "derived"
    note: str = ""


@dataclass
class MissingData:
    what_en: str
    what_ka: str
    severity: str           # "critical", "important", "nice_to_have"
    how_to_get_en: str
    how_to_get_ka: str
    onec_report_name: str   # Exact 1C report name to export


@dataclass
class UploadAssessment:
    file_type: str          # "full_monthly", "revenue_cogs_only", "chart_of_accounts", "single_sheet"
    file_type_ka: str
    summary_en: str
    summary_ka: str
    quality_score: int
    sheets: List[SheetAssessment] = field(default_factory=list)
    can_generate: List[GenerationCapability] = field(default_factory=list)
    missing: List[MissingData] = field(default_factory=list)

    def to_dict(self):
        return {
            "file_type": self.file_type,
            "file_type_ka": self.file_type_ka,
            "summary_en": self.summary_en,
            "summary_ka": self.summary_ka,
            "quality_score": self.quality_score,
            "sheets": [s.__dict__ for s in self.sheets],
            "can_generate": [g.__dict__ for g in self.can_generate],
            "missing": [m.__dict__ for m in self.missing],
        }


# ── Sheet type detection rules ──
SHEET_PATTERNS = {
    "Revenue Breakdown":  ("revenue_turnover", "Revenue by product (6110 turnover)", "შემოსავალი პროდუქტების ჭრილში (6110 ბრუნვა)"),
    "COGS Breakdown":     ("cogs_turnover", "COGS by product (1610 turnover)", "თვითღირებულება პროდუქტების ჭრილში (1610 ბრუნვა)"),
    "Mapping":            ("pl_mapping", "Full P&L by account code", "სრული მოგება-ზარალი ანგარიშის კოდებით"),
    "Budget":             ("budget_summary", "Pre-computed P&L summary", "წინასწარ გათვლილი მოგ-ზარ შეჯამება"),
    "Base":               ("gl_journal", "GL journal entries (individual transactions)", "საბუღალტრო გატარებები (ინდივიდუალური ტრანზაქციები)"),
    "TDSheet":            ("trial_balance", "Trial Balance (all accounts)", "საცდელი ბალანსი (ყველა ანგარიში)"),
    "Balance":            ("detailed_balance", "Detailed Balance Sheet by account", "დეტალური ბალანსი ანგარიშების ჭრილში"),
    "BS":                 ("balance_sheet", "Statement of Financial Position", "ფინანსური მდგომარეობის ანგარიშგება"),
}


def assess_upload(sheets_available: List[str], parse_result: dict) -> UploadAssessment:
    """
    Assess what the uploaded file contains and what can be generated from it.

    Args:
        sheets_available: List of sheet names in the uploaded file
        parse_result: Output from parse_nyx_excel() or parse_file()

    Returns:
        UploadAssessment with full breakdown
    """

    assessment = UploadAssessment(
        file_type="unknown",
        file_type_ka="უცნობი",
        summary_en="",
        summary_ka="",
        quality_score=0,
    )

    # ── Detect sheet types ──
    has_revenue = False
    has_cogs = False
    has_mapping = False
    has_budget = False
    has_base = False
    has_tdsheet = False
    has_bs = False
    has_balance = False
    is_chart_of_accounts = False

    for sname in sheets_available:
        sname_lower = sname.lower().strip()

        # Match against known patterns
        matched = False
        for pattern, (dtype, desc_en, desc_ka) in SHEET_PATTERNS.items():
            if pattern.lower() in sname_lower or sname_lower in pattern.lower():
                assessment.sheets.append(SheetAssessment(
                    name=sname, data_type=dtype,
                    description_en=desc_en, description_ka=desc_ka,
                ))
                matched = True

                if dtype == "revenue_turnover": has_revenue = True
                elif dtype == "cogs_turnover": has_cogs = True
                elif dtype == "pl_mapping": has_mapping = True
                elif dtype == "budget_summary": has_budget = True
                elif dtype == "gl_journal": has_base = True
                elif dtype == "trial_balance": has_tdsheet = True
                elif dtype == "balance_sheet": has_bs = True
                elif dtype == "detailed_balance": has_balance = True
                break

        if not matched:
            # Check if it's a Chart of Accounts
            if sname_lower in ('sheet1',) and len(sheets_available) == 1:
                # Might be chart of accounts — check content
                # (parse_result would have no amounts)
                pnl = parse_result.get("pnl", {})
                if isinstance(pnl, dict) and pnl.get("revenue", 0) == 0:
                    is_chart_of_accounts = True
                    assessment.sheets.append(SheetAssessment(
                        name=sname, data_type="chart_of_accounts",
                        description_en="Chart of Accounts (no financial amounts)",
                        description_ka="ანგარიშთა გეგმა (ფინანსური თანხების გარეშე)",
                        has_amounts=False,
                    ))
                else:
                    assessment.sheets.append(SheetAssessment(
                        name=sname, data_type="unknown",
                        description_en=f"Unrecognized sheet: {sname}",
                        description_ka=f"ამოუცნობი შიტი: {sname}",
                    ))

    # ── Determine file type ──
    if is_chart_of_accounts:
        assessment.file_type = "chart_of_accounts"
        assessment.file_type_ka = "ანგარიშთა გეგმა"
        assessment.summary_en = "This is a Chart of Accounts — account definitions without financial amounts. It will be used as the system's accounting knowledge base for validating and classifying future uploads."
        assessment.summary_ka = "ეს არის ანგარიშთა გეგმა — ანგარიშების განმარტებები ფინანსური თანხების გარეშე. გამოიყენება როგორც ბუღალტრული ცოდნის ბაზა მომავალი ატვირთვების ვალიდაციისა და კლასიფიკაციისთვის."
        assessment.quality_score = 100
        return assessment

    if has_mapping and has_revenue and has_cogs and has_bs:
        assessment.file_type = "full_monthly"
        assessment.file_type_ka = "სრული თვიური პაკეტი"
    elif has_mapping and has_revenue and has_cogs:
        assessment.file_type = "pl_complete"
        assessment.file_type_ka = "სრული მოგება-ზარალი (ბალანსის გარეშე)"
    elif has_budget and has_base and has_revenue and has_cogs:
        assessment.file_type = "budget_base_format"
        assessment.file_type_ka = "ბიუჯეტი + ბაზა ფორმატი"
    elif has_revenue and has_cogs:
        assessment.file_type = "revenue_cogs_only"
        assessment.file_type_ka = "მხოლოდ შემოსავალი და თვითღირებულება"
    elif has_revenue:
        assessment.file_type = "revenue_only"
        assessment.file_type_ka = "მხოლოდ შემოსავალი"
    else:
        assessment.file_type = "incomplete"
        assessment.file_type_ka = "არასრული"

    # ── What CAN be generated ──

    # Revenue
    assessment.can_generate.append(GenerationCapability(
        metric="revenue", name_en="Revenue", name_ka="შემოსავალი",
        available=has_revenue or has_mapping or has_budget,
        source="Revenue Breakdown" if has_revenue else ("Mapping" if has_mapping else "Budget"),
        confidence="exact" if has_revenue else "exact",
    ))

    # Revenue by product
    assessment.can_generate.append(GenerationCapability(
        metric="revenue_by_product", name_en="Revenue by Product", name_ka="შემოსავალი პროდუქტების ჭრილში",
        available=has_revenue,
        source="Revenue Breakdown",
        confidence="exact",
    ))

    # COGS
    assessment.can_generate.append(GenerationCapability(
        metric="cogs", name_en="Cost of Goods Sold", name_ka="გაყიდული პროდუქციის თვითღირებულება",
        available=has_cogs or has_mapping or has_budget,
        source="COGS Breakdown" if has_cogs else ("Mapping" if has_mapping else "Budget"),
        confidence="exact",
    ))

    # COGS by product
    assessment.can_generate.append(GenerationCapability(
        metric="cogs_by_product", name_en="COGS by Product", name_ka="თვითღირებულება პროდუქტების ჭრილში",
        available=has_cogs,
        source="COGS Breakdown",
        confidence="exact",
    ))

    # Gross Profit
    assessment.can_generate.append(GenerationCapability(
        metric="gross_profit", name_en="Gross Profit", name_ka="მთლიანი მოგება",
        available=(has_revenue or has_mapping or has_budget) and (has_cogs or has_mapping or has_budget),
        source="Revenue - COGS",
        confidence="exact",
    ))

    # Selling Expenses
    assessment.can_generate.append(GenerationCapability(
        metric="selling_expenses", name_en="Selling Expenses (7310)", name_ka="გაყიდვების ხარჯები (7310)",
        available=has_mapping or has_base,
        source="Mapping" if has_mapping else "Base (GL journal)",
        confidence="exact" if has_mapping else "partial",
        note="" if has_mapping else "Base sheet may only contain admin journal entries",
    ))

    # Admin Expenses
    assessment.can_generate.append(GenerationCapability(
        metric="admin_expenses", name_en="Administrative Expenses (7410)", name_ka="ადმინისტრაციული ხარჯები (7410)",
        available=has_mapping or has_base,
        source="Mapping" if has_mapping else "Base (GL journal)",
        confidence="exact" if has_mapping else "exact",
    ))

    # EBITDA
    assessment.can_generate.append(GenerationCapability(
        metric="ebitda", name_en="EBITDA", name_ka="EBITDA",
        available=has_mapping or has_base,
        source="GP - Selling - Admin",
        confidence="exact" if has_mapping else "partial",
        note="" if (has_mapping or has_base) else "Requires Mapping or Base sheet for G&A expenses",
    ))

    # Depreciation
    assessment.can_generate.append(GenerationCapability(
        metric="depreciation", name_en="Depreciation & Amortization", name_ka="ცვეთა და ამორტიზაცია",
        available=has_mapping or has_base,
        source="Mapping (col F)" if has_mapping else "Base (col AJ)",
        confidence="exact" if has_mapping else "exact",
    ))

    # EBIT
    assessment.can_generate.append(GenerationCapability(
        metric="ebit", name_en="EBIT", name_ka="EBIT",
        available=has_mapping or has_base,
        source="EBITDA - Depreciation",
        confidence="exact" if has_mapping else "partial",
    ))

    # Non-operating
    assessment.can_generate.append(GenerationCapability(
        metric="non_operating", name_en="Non-Operating Income/Expense", name_ka="არასაოპერაციო შემოსავალი/ხარჯი",
        available=has_mapping or has_base,
        source="Mapping (8110/8220)" if has_mapping else "Base (8220)",
        confidence="exact" if has_mapping else "partial",
    ))

    # Net Profit
    assessment.can_generate.append(GenerationCapability(
        metric="net_profit", name_en="Net Profit / Loss", name_ka="წმინდა მოგება / ზარალი",
        available=has_mapping or has_base,
        source="EBIT + NonOp Income - NonOp Expense",
        confidence="exact" if has_mapping else "partial",
    ))

    # OPEX Breakdown
    assessment.can_generate.append(GenerationCapability(
        metric="opex_breakdown", name_en="OPEX Breakdown (30+ categories)", name_ka="ხარჯების კატეგორიზაცია (30+ კატეგორია)",
        available=has_mapping or has_base,
        source="Mapping (col F)" if has_mapping else "Base (col AJ)",
        confidence="exact",
    ))

    # Balance Sheet
    assessment.can_generate.append(GenerationCapability(
        metric="balance_sheet", name_en="Balance Sheet", name_ka="ბალანსი",
        available=has_bs or has_balance,
        source="BS" if has_bs else "Balance (detailed)",
        confidence="exact",
    ))

    # Ratios
    assessment.can_generate.append(GenerationCapability(
        metric="financial_ratios", name_en="Financial Ratios (D/E, Current, etc.)", name_ka="ფინანსური კოეფიციენტები (D/E, მიმდინარე, etc.)",
        available=has_bs or has_balance,
        source="Balance Sheet data",
        confidence="exact",
    ))

    # MR Report
    assessment.can_generate.append(GenerationCapability(
        metric="mr_report", name_en="MR Report (NYX Core Thinker format)", name_ka="MR რეპორტი (NYX Core Thinker ფორმატი)",
        available=has_mapping and has_revenue and has_cogs and has_bs,
        source="All sheets combined",
        confidence="exact" if (has_mapping and has_bs) else "partial",
        note="Requires: Revenue Breakdown + COGS Breakdown + Mapping + BS" if not (has_mapping and has_bs) else "",
    ))

    # ── What's MISSING ──

    if not has_mapping and not has_base:
        assessment.missing.append(MissingData(
            what_en="Selling & Admin Expenses, EBITDA, Depreciation, Net Profit",
            what_ka="გაყიდვების და ადმინისტრაციული ხარჯები, EBITDA, ცვეთა, წმინდა მოგება",
            severity="critical",
            how_to_get_en="Export the 'Mapping' report from 1C — it contains the full P&L by account code with expense categorization",
            how_to_get_ka="1C-დან გაიტანეთ 'Mapping' (ანგარიშთა მეპინგი) — შეიცავს სრულ მოგება-ზარალს ანგარიშის კოდებით და ხარჯების კატეგორიზაციით",
            onec_report_name="Оборотно-сальдовая ведомость с маппингом (OSV + Mapping)",
        ))

    if not has_bs and not has_balance:
        assessment.missing.append(MissingData(
            what_en="Balance Sheet (Assets, Liabilities, Equity, Cash position)",
            what_ka="ბალანსი (აქტივები, ვალდებულებები, კაპიტალი, ნაღდი ფული)",
            severity="important",
            how_to_get_en="Export the BS (Balance Sheet) from 1C — or include the 'Balance' sheet in the export",
            how_to_get_ka="1C-დან გაიტანეთ ბალანსი (BS sheet) — ან ჩართეთ 'Balance' შიტი ექსპორტში",
            onec_report_name="Бухгалтерский баланс (BS)",
        ))

    if not has_revenue:
        assessment.missing.append(MissingData(
            what_en="Revenue by Product (product-level sales detail)",
            what_ka="შემოსავალი პროდუქტების ჭრილში (გაყიდვების დეტალი)",
            severity="important",
            how_to_get_en="Export 'Revenue Breakdown' from 1C — account 6110 turnover by product with VAT split",
            how_to_get_ka="1C-დან გაიტანეთ 'Revenue Breakdown' — ანგარიში 6110-ის ბრუნვა პროდუქტების მიხედვით, VAT-ის გაყოფით",
            onec_report_name="Анализ субконто: Номенклатура (счет 6110)",
        ))

    if not has_cogs:
        assessment.missing.append(MissingData(
            what_en="COGS by Product (product-level cost detail)",
            what_ka="თვითღირებულება პროდუქტების ჭრილში (ხარჯების დეტალი)",
            severity="important",
            how_to_get_en="Export 'COGS Breakdown' from 1C — account 1610 turnover by product with credit accounts",
            how_to_get_ka="1C-დან გაიტანეთ 'COGS Breakdown' — ანგარიში 1610-ის ბრუნვა პროდუქტების მიხედვით, კრედიტ ანგარიშებით",
            onec_report_name="Анализ счета 1610: Субконто Номенклатура, Склады",
        ))

    # ── Quality Score ──
    available_count = sum(1 for g in assessment.can_generate if g.available)
    total_count = len(assessment.can_generate)
    assessment.quality_score = int(available_count / total_count * 100) if total_count > 0 else 0

    # ── Summary ──
    avail_metrics = [g.name_en for g in assessment.can_generate if g.available]
    missing_metrics = [g.name_en for g in assessment.can_generate if not g.available]

    if assessment.file_type == "full_monthly":
        assessment.summary_en = f"Complete monthly package — all {available_count} financial metrics available. Full P&L, Balance Sheet, and MR Report can be generated."
        assessment.summary_ka = f"სრული თვიური პაკეტი — ხელმისაწვდომია ყველა {available_count} ფინანსური მეტრიკა. შესაძლებელია სრული P&L, ბალანსი და MR რეპორტის გენერაცია."
    elif assessment.file_type == "revenue_cogs_only":
        assessment.summary_en = f"Only Revenue and COGS data found ({available_count}/{total_count} metrics). Can generate: Gross Profit, product margins. MISSING: {', '.join(missing_metrics[:3])}."
        assessment.summary_ka = f"აღმოჩენილია მხოლოდ შემოსავალი და COGS ({available_count}/{total_count} მეტრიკა). შესაძლებელია: მთლიანი მოგება, პროდუქტის მარჟა. აკლია: EBITDA, ხარჯები, ბალანსი."
    else:
        assessment.summary_en = f"{available_count}/{total_count} metrics available. Missing: {', '.join(missing_metrics[:3])}{'...' if len(missing_metrics) > 3 else ''}."
        assessment.summary_ka = f"{available_count}/{total_count} მეტრიკა ხელმისაწვდომია."

    return assessment
