"""
Training Data Generator for Financial AI
==========================================
Generates synthetic training data to teach the LLM:
1. Ledger entries with multilingual descriptions (EN/KA/RU)
2. Messy spreadsheet tables with various formats
3. COA mappings (1C → IFRS)
4. Turnover computations
5. Inconsistency detection examples
6. Financial statement reconstruction from partial data

Output: JSONL files for fine-tuning OR RAG knowledge base entries.
"""

import json
import logging
import os
import random
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# MULTILINGUAL DICTIONARIES
# ═══════════════════════════════════════════════════════════════

TRANSACTION_DESCRIPTIONS = {
    "fuel_sale_retail": {
        "en": "Retail fuel sale at station #{station}",
        "ka": "საცალო საწვავის გაყიდვა სადგურ #{station}-ზე",
        "ru": "Розничная продажа топлива на АЗС #{station}",
    },
    "fuel_sale_wholesale": {
        "en": "Wholesale fuel delivery to {customer}",
        "ka": "საბითუმო საწვავის მიწოდება {customer}-ისთვის",
        "ru": "Оптовая поставка топлива {customer}",
    },
    "fuel_purchase": {
        "en": "Fuel purchase from {supplier} - {product}",
        "ka": "საწვავის შეძენა {supplier}-ისგან - {product}",
        "ru": "Закупка топлива у {supplier} - {product}",
    },
    "salary_payment": {
        "en": "Salary payment for {month} - {department}",
        "ka": "ხელფასის გადახდა {month} - {department}",
        "ru": "Выплата зарплаты за {month} - {department}",
    },
    "rent_payment": {
        "en": "Station rent payment - {location}",
        "ka": "სადგურის იჯარის გადახდა - {location}",
        "ru": "Оплата аренды АЗС - {location}",
    },
    "utility_payment": {
        "en": "Utility payment - {type} - {location}",
        "ka": "კომუნალური გადახდა - {type} - {location}",
        "ru": "Оплата коммунальных - {type} - {location}",
    },
    "bank_commission": {
        "en": "Bank commission - {bank}",
        "ka": "საბანკო საკომისიო - {bank}",
        "ru": "Банковская комиссия - {bank}",
    },
    "depreciation": {
        "en": "Monthly depreciation - {asset_type}",
        "ka": "ყოველთვიური ცვეთა - {asset_type}",
        "ru": "Ежемесячная амортизация - {asset_type}",
    },
    "tax_payment": {
        "en": "Tax payment - {tax_type}",
        "ka": "გადასახადის გადახდა - {tax_type}",
        "ru": "Уплата налога - {tax_type}",
    },
    "loan_repayment": {
        "en": "Loan repayment to {bank} - principal + interest",
        "ka": "სესხის დაფარვა {bank} - ძირი + პროცენტი",
        "ru": "Погашение кредита {bank} - основной долг + проценты",
    },
    "inventory_receipt": {
        "en": "Fuel receipt to depot - {product} {quantity}L",
        "ka": "საწვავის მიღება საწყობში - {product} {quantity}ლ",
        "ru": "Поступление топлива на базу - {product} {quantity}л",
    },
    "fx_conversion": {
        "en": "Currency conversion {from_curr} to {to_curr}",
        "ka": "ვალუტის კონვერტაცია {from_curr}-დან {to_curr}-ში",
        "ru": "Конвертация валюты {from_curr} в {to_curr}",
    },
    "insurance_payment": {
        "en": "Insurance premium - {coverage}",
        "ka": "სადაზღვევო პრემია - {coverage}",
        "ru": "Страховая премия - {coverage}",
    },
    "repair_maintenance": {
        "en": "Repair and maintenance - {facility}",
        "ka": "რემონტი და მოვლა - {facility}",
        "ru": "Ремонт и обслуживание - {facility}",
    },
    "transport_fuel": {
        "en": "Fuel transportation - {route}",
        "ka": "საწვავის ტრანსპორტირება - {route}",
        "ru": "Перевозка топлива - {route}",
    },
}

PRODUCTS = {
    "diesel": {"en": "Diesel", "ka": "დიზელი", "ru": "Дизель", "unit": "L"},
    "euro_regular": {"en": "Euro Regular", "ka": "ევრო რეგულარი", "ru": "Евро Регуляр", "unit": "L"},
    "euro_premium": {"en": "Euro Premium", "ka": "ევრო პრემიუმ", "ru": "Евро Премиум", "unit": "L"},
    "cng": {"en": "CNG", "ka": "ბუნებრივი აირი", "ru": "КПГ", "unit": "m3"},
    "lpg": {"en": "LPG", "ka": "თხევადი აირი", "ru": "СУГ", "unit": "L"},
    "bitumen": {"en": "Bitumen", "ka": "ბიტუმი", "ru": "Битум", "unit": "kg"},
}

CUSTOMERS = [
    "Wissol LLC", "Gulf LLC", "Rompetrol Georgia", "Lukoil Georgia",
    "Georgian Railway", "Tbilisi Transport", "Ministry of Defense",
    "Agro Georgia Ltd", "TransCaucasus Logistics", "Batumi Port Authority",
]

SUPPLIERS = ["NYX Core Trading", "Lukoil Trading", "Vitol", "Trafigura", "Litasco"]
BANKS = ["TBC Bank", "Bank of Georgia", "Liberty Bank", "Basis Bank", "ProCredit Bank"]
LOCATIONS = ["Tbilisi", "Batumi", "Kutaisi", "Rustavi", "Gori", "Zugdidi", "Telavi", "Poti"]
DEPARTMENTS = ["Commercial", "Administrative", "Operations", "Logistics", "IT"]

# ═══════════════════════════════════════════════════════════════
# 1. SYNTHETIC LEDGER GENERATOR
# ═══════════════════════════════════════════════════════════════

class LedgerEntryGenerator:
    """Generates realistic double-entry journal entries."""

    def __init__(self):
        self._coa = self._load_coa()

    def _load_coa(self) -> Dict[str, Dict]:
        """Load COA from 1C file if available."""
        try:
            from app.services.onec_interpreter import onec_interpreter
            tree = onec_interpreter.parse_file_bytes(
                open("uploads/1c AccountN.xlsx", "rb").read()
            )
            coa = {}
            for acct in tree.accounts:
                coa[acct.code] = {
                    "code": acct.code,
                    "name_ka": acct.name_ka,
                    "name_ru": acct.name_ru,
                    "type": acct.account_type,
                    "normal_balance": acct.normal_balance,
                    "ifrs_pl": acct.ifrs_pl_line,
                    "ifrs_bs": acct.ifrs_bs_line,
                }
            return coa
        except Exception:
            return {}

    def generate_entry(self, lang: str = "en") -> Dict[str, Any]:
        """Generate a single realistic journal entry."""
        entry_type = random.choice(list(TRANSACTION_DESCRIPTIONS.keys()))
        template = TRANSACTION_DESCRIPTIONS[entry_type]

        # Generate context-specific parameters
        params = {
            "station": random.randint(1, 150),
            "customer": random.choice(CUSTOMERS),
            "supplier": random.choice(SUPPLIERS),
            "product": random.choice(list(PRODUCTS.values()))[lang],
            "month": random.choice(["January", "February", "March", "April"]),
            "department": random.choice(DEPARTMENTS),
            "location": random.choice(LOCATIONS),
            "type": random.choice(["electricity", "water", "gas", "internet"]),
            "bank": random.choice(BANKS),
            "asset_type": random.choice(["stations", "vehicles", "equipment"]),
            "tax_type": random.choice(["VAT", "property", "income"]),
            "quantity": random.randint(1000, 50000),
            "from_curr": "USD",
            "to_curr": "GEL",
            "coverage": random.choice(["property", "liability", "vehicle"]),
            "facility": random.choice(["station #" + str(random.randint(1, 150)), "depot", "office"]),
            "route": f"{random.choice(LOCATIONS)} - {random.choice(LOCATIONS)}",
        }

        description = template[lang].format(**params)

        # Generate accounts and amounts based on entry type
        accounts = self._get_accounts_for_type(entry_type)
        amount = self._generate_amount(entry_type)

        entry = {
            "date": self._random_date(),
            "description": description,
            "description_en": template["en"].format(**params),
            "description_ka": template["ka"].format(**params),
            "description_ru": template["ru"].format(**params),
            "reference": f"JE-{random.randint(10000, 99999)}",
            "debit_account": accounts[0],
            "credit_account": accounts[1],
            "amount": float(amount),
            "currency": "GEL",
            "entry_type": entry_type,
        }

        # Add COA names if available
        if accounts[0] in self._coa:
            entry["debit_name_ka"] = self._coa[accounts[0]].get("name_ka", "")
            entry["debit_name_ru"] = self._coa[accounts[0]].get("name_ru", "")
        if accounts[1] in self._coa:
            entry["credit_name_ka"] = self._coa[accounts[1]].get("name_ka", "")
            entry["credit_name_ru"] = self._coa[accounts[1]].get("name_ru", "")

        return entry

    def _get_accounts_for_type(self, entry_type: str) -> Tuple[str, str]:
        """Return (debit_account, credit_account) for entry type."""
        mapping = {
            "fuel_sale_retail": ("1210", "6110"),      # Bank DR / Revenue CR
            "fuel_sale_wholesale": ("1410", "6110"),   # Receivable DR / Revenue CR
            "fuel_purchase": ("1610", "3110"),          # Inventory DR / Payable CR
            "salary_payment": ("7310", "1210"),         # Expense DR / Bank CR
            "rent_payment": ("7310", "1210"),            # Expense DR / Bank CR
            "utility_payment": ("7310", "1210"),         # Expense DR / Bank CR
            "bank_commission": ("7310", "1210"),         # Expense DR / Bank CR
            "depreciation": ("7410", "2210"),            # Expense DR / Accum Dep CR
            "tax_payment": ("3310", "1210"),             # Tax Payable DR / Bank CR
            "loan_repayment": ("4110", "1210"),          # Loan DR / Bank CR
            "inventory_receipt": ("1610", "1296"),       # Inventory DR / Transit CR
            "fx_conversion": ("1220", "1210"),           # FX Bank DR / GEL Bank CR
            "insurance_payment": ("7310", "1210"),       # Expense DR / Bank CR
            "repair_maintenance": ("7310", "1210"),      # Expense DR / Bank CR
            "transport_fuel": ("7310", "1210"),          # Expense DR / Bank CR
        }
        return mapping.get(entry_type, ("7410", "1210"))

    def _generate_amount(self, entry_type: str) -> Decimal:
        """Generate realistic amount for entry type."""
        ranges = {
            "fuel_sale_retail": (500, 50000),
            "fuel_sale_wholesale": (50000, 5000000),
            "fuel_purchase": (100000, 20000000),
            "salary_payment": (500, 15000),
            "rent_payment": (2000, 100000),
            "utility_payment": (100, 20000),
            "bank_commission": (10, 5000),
            "depreciation": (10000, 500000),
            "tax_payment": (5000, 1000000),
            "loan_repayment": (50000, 2000000),
            "inventory_receipt": (100000, 10000000),
            "fx_conversion": (10000, 5000000),
            "insurance_payment": (1000, 50000),
            "repair_maintenance": (500, 100000),
            "transport_fuel": (5000, 500000),
        }
        lo, hi = ranges.get(entry_type, (1000, 100000))
        return Decimal(str(round(random.uniform(lo, hi), 2)))

    def _random_date(self) -> str:
        """Generate random date in 2025-2026."""
        start = date(2025, 1, 1)
        delta = random.randint(0, 450)
        d = start + timedelta(days=delta)
        return d.isoformat()

    def generate_batch(self, count: int = 1000, lang: str = "en") -> List[Dict]:
        """Generate a batch of journal entries."""
        return [self.generate_entry(lang) for _ in range(count)]


# ═══════════════════════════════════════════════════════════════
# 2. MESSY SPREADSHEET GENERATOR
# ═══════════════════════════════════════════════════════════════

class MessySpreadsheetGenerator:
    """Generates training examples of various spreadsheet formats."""

    def generate_messy_headers(self) -> List[Dict]:
        """Generate examples of headers at different row positions."""
        examples = []

        # Standard headers at row 1
        examples.append({
            "input": [
                ["Product", "Amount", "VAT", "Net Revenue", "Category"],
                ["Diesel", 5000000, 763568, 4236432, "Revenue Retail"],
            ],
            "expected": {"header_row": 0, "type": "revenue_breakdown",
                         "column_map": {"Product": 0, "Amount": 1, "VAT": 2, "Net Revenue": 3, "Category": 4}},
        })

        # Headers at row 5 with company info above
        examples.append({
            "input": [
                [settings.COMPANY_NAME, "", "", "", ""],
                ["Financial Report", "", "", "", ""],
                ["Period: January 2026", "", "", "", ""],
                ["", "", "", "", ""],
                ["Product", "Amount GEL", "VAT 18%", "Net Revenue", "Type"],
                ["Diesel", 7895668, 1203206, 6692462, "Retail"],
            ],
            "expected": {"header_row": 4, "type": "revenue_breakdown",
                         "column_map": {"Product": 0, "Amount GEL": 1, "VAT 18%": 2, "Net Revenue": 3, "Type": 4}},
        })

        # Georgian headers
        examples.append({
            "input": [
                ["პროდუქცია", "თანხა", "დღგ", "წმინდა შემოსავალი", "კატეგორია"],
                ["დიზელი", 5000000, 763568, 4236432, "საცალო"],
            ],
            "expected": {"header_row": 0, "type": "revenue_breakdown",
                         "column_map": {"პროდუქცია": 0, "თანხა": 1, "დღგ": 2, "წმინდა შემოსავალი": 3, "კატეგორია": 4}},
        })

        # Russian 1C trial balance format
        examples.append({
            "input": [
                ["", "", "Оборотно-сальдовая ведомость", "", "", ""],
                ["", "", "Период: Январь 2026 г.", "", "", ""],
                ["", "", "Счет", "", "", "Сальдо на начало"],
                ["", "", "Код", "Наименование", "", "Дебет", "Кредит"],
                ["", "", "1110", "Касса", "", "27679.77", ""],
            ],
            "expected": {"header_row": 3, "type": "trial_balance",
                         "column_map": {"Код": 2, "Наименование": 3, "Дебет": 5, "Кредит": 6}},
        })

        # Mixed Georgian-Russian (common in 1C)
        examples.append({
            "input": [
                ["", "7310.01.1/1", "საბანკო ხარჯები (საკომისიო) // Банковские расходы", "135284.38", "Other operating expenses", "Bank Commisions"],
            ],
            "expected": {"type": "pl_mapping", "account_code": "7310",
                         "category": "selling_expenses", "is_sub_account": True},
        })

        return examples

    def generate_inconsistency_examples(self) -> List[Dict]:
        """Generate examples of data inconsistencies for training."""
        return [
            {
                "input": {"revenue": 50000000, "cogs": 60000000},
                "issue": "COGS exceeds revenue",
                "severity": "critical",
                "explanation_en": "Cost of goods sold (60M) exceeds revenue (50M), resulting in negative gross margin. This is unsustainable and may indicate pricing errors, unrecorded revenue, or cost misclassification.",
                "explanation_ka": "გაყიდული საქონლის თვითღირებულება (60მ) აღემატება შემოსავალს (50მ), რაც იწვევს უარყოფით მთლიან მარჟას.",
            },
            {
                "input": {"total_assets": 100000000, "total_liabilities": 70000000, "total_equity": 25000000},
                "issue": "Balance sheet does not balance",
                "severity": "critical",
                "explanation_en": "Assets (100M) != Liabilities (70M) + Equity (25M). Difference of 5M indicates missing items or calculation error.",
                "explanation_ka": "აქტივები (100მ) != ვალდებულებები (70მ) + კაპიტალი (25მ). 5მ სხვაობა მიუთითებს გამოტოვებულ მუხლებზე.",
            },
            {
                "input": {"trial_balance_debit_total": 500000000, "trial_balance_credit_total": 499500000},
                "issue": "Trial balance out of balance",
                "severity": "critical",
                "explanation_en": "Trial balance debit total (500M) does not equal credit total (499.5M). Difference of 500K must be investigated.",
            },
            {
                "input": {"revenue": 50000000, "receivables_current": 30000000, "receivables_prior": 15000000},
                "issue": "Receivables growing faster than revenue",
                "severity": "warning",
                "explanation_en": "Receivables doubled (15M to 30M) while revenue stayed at 50M. Receivable days = 219 days. This indicates collection problems or potentially fictitious revenue.",
            },
            {
                "input": {"interest_expense": 3000000, "total_opex": 8700000},
                "issue": "High interest expense ratio",
                "severity": "warning",
                "explanation_en": "Interest expense is 34.5% of total operating expenses, significantly above the healthy threshold of 10-15%. Indicates excessive leverage.",
                "explanation_ka": "საპროცენტო ხარჯი 34.5%-ია ოპერაციული ხარჯების, საგრძნობლად მაღალია ჯანსაღი ზღვარის 10-15%.",
            },
            {
                "input": {"depreciation": 2800000, "total_assets": 160000000, "depreciation_rate_expected": 0.05},
                "issue": "Depreciation rate below expected",
                "severity": "info",
                "explanation_en": "Effective depreciation rate 1.75% vs expected 5% for fuel infrastructure. Assets may be understated or useful lives overestimated.",
            },
        ]


# ═══════════════════════════════════════════════════════════════
# 3. COA MAPPING TRAINING DATA
# ═══════════════════════════════════════════════════════════════

class COAMappingGenerator:
    """Generates training examples for account code classification."""

    def generate_mapping_examples(self) -> List[Dict]:
        """Generate Q&A pairs for account classification."""
        examples = []

        mappings = [
            ("1110", "Cash", "BS", "current_assets", "ნაღდი ფული", "Касса"),
            ("1210", "Bank Account GEL", "BS", "current_assets", "საბანკო ანგარიში", "Расчетный счет"),
            ("1410", "Trade Receivables", "BS", "current_assets", "სავაჭრო მოთხოვნები", "Дебиторская задолженность"),
            ("1610", "Inventory (Goods for Resale)", "BS", "current_assets", "სასაქონლო მარაგები", "Товары"),
            ("2110", "Fixed Assets - Buildings", "BS", "noncurrent_assets", "ძირითადი საშუალებები", "Основные средства"),
            ("2210", "Accumulated Depreciation", "BS", "noncurrent_assets", "დაგროვილი ცვეთა", "Амортизация"),
            ("3110", "Trade Payables", "BS", "current_liabilities", "სავაჭრო ვალდებულებები", "Кредиторская задолженность"),
            ("3310", "VAT Payable", "BS", "current_liabilities", "დღგ ვალდებულება", "НДС к уплате"),
            ("4110", "Long-term Bank Loan", "BS", "noncurrent_liabilities", "გრძელვადიანი სესხი", "Долгосрочный кредит"),
            ("5110", "Share Capital", "BS", "equity", "საწესდებო კაპიტალი", "Уставный капитал"),
            ("6110", "Revenue from Sales", "PL", "revenue", "შემოსავალი რეალიზაციიდან", "Выручка"),
            ("7110", "Cost of Goods Sold", "PL", "cogs", "თვითღირებულება", "Себестоимость"),
            ("7310", "Selling Expenses", "PL", "selling_expenses", "გაყიდვების ხარჯები", "Коммерческие расходы"),
            ("7410", "Admin Expenses", "PL", "admin_expenses", "ადმინისტრაციული ხარჯები", "Общехозяйственные расходы"),
            ("8110", "Other Operating Income", "PL", "other_income", "სხვა შემოსავალი", "Прочие доходы"),
            ("8220", "Interest Expense", "PL", "other_expense", "საპროცენტო ხარჯი", "Процентные расходы"),
        ]

        for code, name_en, stmt, line, name_ka, name_ru in mappings:
            examples.append({
                "question": f"What is account {code}?",
                "answer": f"Account {code} is '{name_en}' ({name_ka} / {name_ru}). It belongs to the {stmt} statement under '{line}'. "
                          f"Normal balance: {'debit' if code[0] in '1279' else 'credit'}.",
                "code": code,
                "name_en": name_en,
                "name_ka": name_ka,
                "name_ru": name_ru,
                "statement": stmt,
                "line": line,
            })

            # Georgian question
            examples.append({
                "question": f"რა არის ანგარიში {code}?",
                "answer": f"ანგარიში {code} არის '{name_ka}' ({name_en}). "
                          f"ეკუთვნის {'ბალანსს' if stmt == 'BS' else 'მოგება-ზარალს'}, ხაზი: '{line}'.",
            })

        # Critical distinction examples
        examples.append({
            "question": "Is account 1610 COGS?",
            "answer": "NO. Account 1610 is INVENTORY (Balance Sheet, Current Assets). "
                      "COGS is account 7110. The COGS Breakdown sheet shows inventory TURNOVERS "
                      "on account 1610, which are balance sheet movements, NOT cost of goods sold. "
                      "Always use account 7110 from the Mapping sheet for the real COGS figure.",
        })

        examples.append({
            "question": "Why is revenue negative in the trial balance?",
            "answer": "Revenue accounts (61XX) have a CREDIT normal balance. In double-entry, "
                      "credits appear as negative in the trial balance. To get the positive revenue "
                      "figure, take the absolute value. For example, if 6110 shows -51,226,182 in "
                      "the trial balance, the actual revenue is 51,226,182 GEL.",
        })

        examples.append({
            "question": "What is the difference between 7310 and 7310/1?",
            "answer": "Account 7310 is the PARENT account (Selling Expenses total). "
                      "Account 7310/1 is a SUB-ACCOUNT (specific line item within selling expenses). "
                      "For P&L reporting, use the 4-digit parent account (7310). "
                      "Sub-accounts provide detail breakdown but should not be used as totals.",
        })

        return examples


# ═══════════════════════════════════════════════════════════════
# 4. TURNOVER COMPUTATION TRAINING
# ═══════════════════════════════════════════════════════════════

class TurnoverTrainer:
    """Generates training examples for understanding turnovers."""

    def generate_examples(self) -> List[Dict]:
        """Generate Q&A pairs for turnover computation."""
        return [
            {
                "question": "Given opening debit balance 1,000,000, debit turnover 5,000,000, credit turnover 4,500,000 for a debit-normal account, what is the closing balance?",
                "answer": "Closing balance = Opening + Debit Turnover - Credit Turnover = 1,000,000 + 5,000,000 - 4,500,000 = 1,500,000 (debit).",
                "formula": "closing = opening + debit_turnover - credit_turnover (for debit-normal accounts)",
            },
            {
                "question": "Account 6110 (Revenue, credit-normal) has opening credit 0, credit turnover 51,226,182, debit turnover 798. What is the closing balance?",
                "answer": "For credit-normal accounts: Closing = Opening + Credit Turnover - Debit Turnover = 0 + 51,226,182 - 798 = 51,225,384 (credit). Revenue for the period is 51,225,384 GEL.",
                "formula": "closing = opening + credit_turnover - debit_turnover (for credit-normal accounts)",
            },
            {
                "question": "Account 1610 has debit turnover 184,887,280 for January 2026. Is this the COGS?",
                "answer": "NO. Account 1610 is Inventory (Balance Sheet). Debit turnover of 184,887,280 represents total inventory RECEIVED during the period. This is NOT the cost of goods sold. COGS is on account 7110, which shows 44,816,783 GEL in the Mapping sheet.",
            },
            {
                "question": "Trial balance shows: DR total = 500,234,567.89, CR total = 500,234,567.89. Is it balanced?",
                "answer": "YES. The trial balance is balanced because total debits equal total credits (difference = 0). This is a necessary (but not sufficient) condition for correct bookkeeping.",
            },
        ]


# ═══════════════════════════════════════════════════════════════
# 5. EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def generate_all_training_data(output_dir: str = "training_data") -> Dict[str, int]:
    """Generate all training data and save to files."""
    os.makedirs(output_dir, exist_ok=True)
    stats = {}

    # 1. Ledger entries
    ledger = LedgerEntryGenerator()
    entries_en = ledger.generate_batch(500, "en")
    entries_ka = ledger.generate_batch(500, "ka")
    entries_ru = ledger.generate_batch(200, "ru")
    all_entries = entries_en + entries_ka + entries_ru
    with open(os.path.join(output_dir, "ledger_entries.jsonl"), "w", encoding="utf-8") as f:
        for e in all_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    stats["ledger_entries"] = len(all_entries)

    # 2. Messy spreadsheet examples
    messy = MessySpreadsheetGenerator()
    headers = messy.generate_messy_headers()
    inconsistencies = messy.generate_inconsistency_examples()
    with open(os.path.join(output_dir, "spreadsheet_patterns.jsonl"), "w", encoding="utf-8") as f:
        for h in headers:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
        for i in inconsistencies:
            f.write(json.dumps(i, ensure_ascii=False) + "\n")
    stats["spreadsheet_patterns"] = len(headers) + len(inconsistencies)

    # 3. COA mappings
    coa_gen = COAMappingGenerator()
    coa_examples = coa_gen.generate_mapping_examples()
    with open(os.path.join(output_dir, "coa_mappings.jsonl"), "w", encoding="utf-8") as f:
        for c in coa_examples:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    stats["coa_mappings"] = len(coa_examples)

    # 4. Turnover examples
    turnover = TurnoverTrainer()
    turnover_examples = turnover.generate_examples()
    with open(os.path.join(output_dir, "turnover_training.jsonl"), "w", encoding="utf-8") as f:
        for t in turnover_examples:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    stats["turnover_examples"] = len(turnover_examples)

    # 5. Combined knowledge for RAG injection
    from app.services.accounting_knowledge import build_full_accounting_knowledge
    knowledge = build_full_accounting_knowledge()
    with open(os.path.join(output_dir, "accounting_knowledge.txt"), "w", encoding="utf-8") as f:
        f.write(knowledge)
    stats["knowledge_chars"] = len(knowledge)

    logger.info("Training data generated: %s", stats)
    return stats


# Module-level generators
ledger_generator = LedgerEntryGenerator()
messy_generator = MessySpreadsheetGenerator()
coa_generator = COAMappingGenerator()
turnover_trainer = TurnoverTrainer()
