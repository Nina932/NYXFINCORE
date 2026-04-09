"""
FINANCIAL ONTOLOGY: Teaching LLMs to Actually Think About Finance
==================================================================

This ontology defines:
1. Core financial concepts (entities, relationships, constraints)
2. Reasoning rules (what MUST be true)
3. Validation logic (detect violations)
4. Inference engine (derive new facts from known facts)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
from decimal import Decimal
import json


# ============================================================================
# PART 1: CORE FINANCIAL CONCEPTS (ONTOLOGY ENTITIES)
# ============================================================================

class FinancialConcept(Enum):
    """
    Top-level financial concepts
    These are the fundamental building blocks of financial reasoning
    """
    # Income Statement Components
    REVENUE = "revenue"
    COGS = "cost_of_goods_sold"
    GROSS_PROFIT = "gross_profit"
    OPERATING_EXPENSE = "operating_expense"
    EBITDA = "ebitda"
    NET_INCOME = "net_income"
    
    # Balance Sheet Components
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    
    # Cash Flow Components
    OPERATING_CF = "operating_cash_flow"
    INVESTING_CF = "investing_cash_flow"
    FINANCING_CF = "financing_cash_flow"
    
    # Product/Channel Dimensions
    PRODUCT = "product"
    CHANNEL = "channel"
    CATEGORY = "category"


class RevenueChannel(Enum):
    """Revenue can come from wholesale or retail channels"""
    WHOLESALE = "wholesale"
    RETAIL = "retail"
    OTHER = "other"


class ProductCategory(Enum):
    """Product categories in fuel business"""
    PETROL = "petrol"
    DIESEL = "diesel"
    CNG = "cng"
    LPG = "lpg"
    BITUMEN = "bitumen"
    OTHER = "other"


@dataclass
class FinancialLineItem:
    """
    Represents a single line item in financial statement
    Contains both data AND metadata about its nature
    """
    concept: FinancialConcept
    name: str
    amount: Decimal
    
    # Hierarchical structure
    parent: Optional['FinancialLineItem'] = None
    children: List['FinancialLineItem'] = field(default_factory=list)
    
    # Business dimensions
    channel: Optional[RevenueChannel] = None
    category: Optional[ProductCategory] = None
    
    # Calculation metadata
    formula: Optional[str] = None  # How this was calculated
    source: Optional[str] = None   # Where data came from
    
    # Validation state
    validated: bool = False
    validation_errors: List[str] = field(default_factory=list)


# ============================================================================
# PART 2: FINANCIAL AXIOMS (FUNDAMENTAL TRUTHS)
# ============================================================================

class FinancialAxiom:
    """
    Fundamental truths that MUST always hold in financial statements
    These are the "laws of physics" for finance
    """
    
    @staticmethod
    def gross_profit_formula() -> Dict:
        """
        AXIOM 1: Gross Profit = Revenue - COGS
        This is ALWAYS true, no exceptions
        """
        return {
            'name': 'gross_profit_formula',
            'formula': 'gross_profit = revenue - cogs',
            'constraint': lambda r, c, gp: abs((r - c) - gp) < 0.01,
            'violation_message': 'Gross Profit must equal Revenue minus COGS',
            'severity': 'CRITICAL'
        }
    
    @staticmethod
    def ebitda_formula() -> Dict:
        """
        AXIOM 2: EBITDA = Gross Profit - G&A Expenses
        """
        return {
            'name': 'ebitda_formula',
            'formula': 'ebitda = gross_profit - ga_expenses',
            'constraint': lambda gp, ga, ebitda: abs((gp - ga) - ebitda) < 0.01,
            'violation_message': 'EBITDA must equal Gross Profit minus G&A',
            'severity': 'CRITICAL'
        }
    
    @staticmethod
    def revenue_aggregation() -> Dict:
        """
        AXIOM 3: Total Revenue = Sum of all revenue components
        """
        return {
            'name': 'revenue_aggregation',
            'formula': 'total_revenue = sum(revenue_wholesale, revenue_retail, revenue_other)',
            'constraint': lambda total, parts: abs(total - sum(parts)) < 0.01,
            'violation_message': 'Total revenue must equal sum of components',
            'severity': 'CRITICAL'
        }
    
    @staticmethod
    def balance_sheet_equation() -> Dict:
        """
        AXIOM 4: Assets = Liabilities + Equity
        """
        return {
            'name': 'balance_sheet_equation',
            'formula': 'assets = liabilities + equity',
            'constraint': lambda a, l, e: abs(a - (l + e)) < 0.01,
            'violation_message': 'Balance sheet must balance!',
            'severity': 'CRITICAL'
        }
    
    @staticmethod
    def non_negative_revenue() -> Dict:
        """
        AXIOM 5: Revenue cannot be negative
        (Returns are handled separately)
        """
        return {
            'name': 'non_negative_revenue',
            'formula': 'revenue >= 0',
            'constraint': lambda r: r >= 0,
            'violation_message': 'Revenue cannot be negative',
            'severity': 'HIGH'
        }
    
    @staticmethod
    def margin_bounds() -> Dict:
        """
        AXIOM 6: Gross margin % must be between -100% and 100%
        (Can be negative if selling at loss, but not < -100%)
        """
        return {
            'name': 'margin_bounds',
            'formula': '-100% <= margin_pct <= 100%',
            'constraint': lambda margin_pct: -100 <= margin_pct <= 100,
            'violation_message': 'Margin percentage outside realistic bounds',
            'severity': 'MEDIUM'
        }


# ============================================================================
# PART 3: DOMAIN KNOWLEDGE (NYX CORE THINKER-SPECIFIC BUSINESS RULES)
# ============================================================================

class NyxBusinessRules:
    """
    Business rules specific to NYX Core Thinker
    These are learned patterns, not universal axioms
    """
    
    @staticmethod
    def wholesale_products() -> Dict[str, List[str]]:
        """
        Knowledge: Which products are wholesale
        """
        return {
            'petrol': [
                'ევრო რეგულარი (იმპორტი)',
                'პრემიუმი (რეექსპორტი)',
                'სუპერი (რეექსპორტი)',
                'ევრო რეგულარი (საბითუმო)',
            ],
            'diesel': [
                'დიზელი (საბითუმო)',
                'ევროდიზელი (ექსპორტი)',
            ],
            'bitumen': [
                'ბიტუმი (საბითუმო)',
            ]
        }
    
    @staticmethod
    def retail_products() -> Dict[str, List[str]]:
        """
        Knowledge: Which products are retail
        """
        return {
            'petrol': [
                'ევრო რეგულარი',
                'პრემიუმი',
                'სუპერი',
            ],
            'diesel': [
                'დიზელი',
                'ევრო დიზელი',
            ],
            'cng': [
                'ბუნებრივი აირი',
                'ბუნებრივი აირი (საბითუმო)',
            ],
            'lpg': [
                'თხევადი აირი (მხოლოდ SGP !!!)',
            ]
        }
    
    @staticmethod
    def ga_account_prefixes() -> List[str]:
        """
        Knowledge: Which account codes represent G&A expenses
        """
        return ['73', '74', '82', '92']
    
    @staticmethod
    def cogs_account_columns() -> List[int]:
        """
        Knowledge: Which columns contain COGS data
        In NYX Core Thinker's 1C export: columns K (10), L (11), O (14)
        """
        return [10, 11, 14]  # 0-indexed
    
    @staticmethod
    def expected_margin_ranges() -> Dict[str, Tuple[float, float]]:
        """
        Knowledge: Expected margin ranges by category
        Based on historical data
        """
        return {
            'wholesale_petrol': (0, 5),      # 0-5%
            'wholesale_diesel': (-1, 3),     # -1% to 3% (can be negative)
            'wholesale_bitumen': (2, 8),     # 2-8%
            'retail_petrol': (12, 20),       # 12-20%
            'retail_diesel': (8, 16),        # 8-16%
            'retail_cng': (18, 55),          # 18-55% (high margins)
            'retail_lpg': (15, 25),          # 15-25%
        }


# ============================================================================
# PART 4: REASONING ENGINE (INFERENCE & VALIDATION)
# ============================================================================

class FinancialReasoningEngine:
    """
    Makes the LLM actually THINK about financial data
    Not just pattern matching - actual logical reasoning
    """
    
    def __init__(self):
        self.axioms = self._load_axioms()
        self.business_rules = NyxBusinessRules()
        self.knowledge_base = []  # Stores derived facts
        
    def _load_axioms(self) -> List[Dict]:
        """Load all financial axioms"""
        return [
            FinancialAxiom.gross_profit_formula(),
            FinancialAxiom.ebitda_formula(),
            FinancialAxiom.revenue_aggregation(),
            FinancialAxiom.balance_sheet_equation(),
            FinancialAxiom.non_negative_revenue(),
            FinancialAxiom.margin_bounds(),
        ]
    
    def validate_against_axioms(self, financial_data: Dict) -> Dict:
        """
        Validate financial data against fundamental axioms
        Returns violations if any
        """
        violations = []
        
        # Axiom 1: Gross Profit = Revenue - COGS
        if all(k in financial_data for k in ['revenue', 'cogs', 'gross_profit']):
            axiom = FinancialAxiom.gross_profit_formula()
            
            revenue = financial_data['revenue']
            cogs = financial_data['cogs']
            stated_gp = financial_data['gross_profit']
            calculated_gp = revenue - cogs
            
            if not axiom['constraint'](revenue, cogs, stated_gp):
                violations.append({
                    'axiom': axiom['name'],
                    'severity': axiom['severity'],
                    'message': axiom['violation_message'],
                    'details': {
                        'stated_gross_profit': stated_gp,
                        'calculated_gross_profit': calculated_gp,
                        'difference': stated_gp - calculated_gp,
                        'formula': 'Gross Profit = Revenue - COGS',
                        'calculation': f'{revenue:,.2f} - {cogs:,.2f} = {calculated_gp:,.2f}',
                        'expected': calculated_gp,
                        'actual': stated_gp
                    }
                })
        
        # Axiom 2: EBITDA = Gross Profit - G&A
        if all(k in financial_data for k in ['gross_profit', 'ga_expenses', 'ebitda']):
            axiom = FinancialAxiom.ebitda_formula()
            
            gp = financial_data['gross_profit']
            ga = financial_data['ga_expenses']
            stated_ebitda = financial_data['ebitda']
            calculated_ebitda = gp - ga
            
            if not axiom['constraint'](gp, ga, stated_ebitda):
                violations.append({
                    'axiom': axiom['name'],
                    'severity': axiom['severity'],
                    'message': axiom['violation_message'],
                    'details': {
                        'stated_ebitda': stated_ebitda,
                        'calculated_ebitda': calculated_ebitda,
                        'difference': stated_ebitda - calculated_ebitda,
                        'formula': 'EBITDA = Gross Profit - G&A',
                        'calculation': f'{gp:,.2f} - {ga:,.2f} = {calculated_ebitda:,.2f}'
                    }
                })
        
        # Axiom 3: Revenue Aggregation
        if 'revenue_components' in financial_data:
            axiom = FinancialAxiom.revenue_aggregation()
            
            total = financial_data.get('total_revenue', 0)
            components = financial_data['revenue_components']
            calculated_total = sum(components)
            
            if not axiom['constraint'](total, components):
                violations.append({
                    'axiom': axiom['name'],
                    'severity': axiom['severity'],
                    'message': axiom['violation_message'],
                    'details': {
                        'stated_total': total,
                        'calculated_total': calculated_total,
                        'difference': total - calculated_total,
                        'components': components
                    }
                })
        
        # Axiom 5: Non-negative revenue
        if 'revenue' in financial_data:
            axiom = FinancialAxiom.non_negative_revenue()
            revenue = financial_data['revenue']
            
            if not axiom['constraint'](revenue):
                violations.append({
                    'axiom': axiom['name'],
                    'severity': axiom['severity'],
                    'message': axiom['violation_message'],
                    'details': {
                        'revenue': revenue
                    }
                })
        
        return {
            'valid': len(violations) == 0,
            'violations': violations,
            'axioms_checked': len(self.axioms)
        }
    
    def infer_missing_values(self, financial_data: Dict) -> Dict:
        """
        Use axioms to INFER missing values from known values
        This is actual reasoning!
        """
        inferred = {}
        
        # Inference 1: If we know Revenue and COGS, we can calculate Gross Profit
        if 'revenue' in financial_data and 'cogs' in financial_data:
            if 'gross_profit' not in financial_data:
                inferred['gross_profit'] = financial_data['revenue'] - financial_data['cogs']
                inferred['gross_profit_source'] = 'INFERRED from Revenue - COGS'
        
        # Inference 2: If we know Gross Profit and EBITDA, we can calculate G&A
        if 'gross_profit' in financial_data and 'ebitda' in financial_data:
            if 'ga_expenses' not in financial_data:
                inferred['ga_expenses'] = financial_data['gross_profit'] - financial_data['ebitda']
                inferred['ga_expenses_source'] = 'INFERRED from Gross Profit - EBITDA'
        
        # Inference 3: If we know Revenue and Gross Profit, we can calculate COGS
        if 'revenue' in financial_data and 'gross_profit' in financial_data:
            if 'cogs' not in financial_data:
                inferred['cogs'] = financial_data['revenue'] - financial_data['gross_profit']
                inferred['cogs_source'] = 'INFERRED from Revenue - Gross Profit'
        
        # Inference 4: Calculate margin %
        if 'gross_profit' in financial_data and 'revenue' in financial_data:
            revenue = financial_data['revenue']
            if revenue > 0:
                gp = financial_data.get('gross_profit', inferred.get('gross_profit'))
                if gp is not None:
                    inferred['margin_pct'] = (gp / revenue) * 100
                    inferred['margin_pct_source'] = 'CALCULATED from (GP / Revenue) * 100'
        
        return inferred
    
    def explain_calculation(self, metric: str, financial_data: Dict) -> str:
        """
        Generate human-readable explanation of how a metric was calculated
        """
        if metric == 'gross_profit':
            revenue = financial_data.get('revenue', 0)
            cogs = financial_data.get('cogs', 0)
            gp = revenue - cogs
            
            return f"""
Gross Profit Calculation:
─────────────────────────
Formula: Gross Profit = Revenue - COGS

Given:
  Revenue = {revenue:,.2f} GEL
  COGS    = {cogs:,.2f} GEL

Calculation:
  Gross Profit = {revenue:,.2f} - {cogs:,.2f}
               = {gp:,.2f} GEL

Margin %: {(gp/revenue*100) if revenue > 0 else 0:.2f}%
"""
        
        elif metric == 'ebitda':
            gp = financial_data.get('gross_profit', 0)
            ga = financial_data.get('ga_expenses', 0)
            ebitda = gp - ga
            
            return f"""
EBITDA Calculation:
───────────────────
Formula: EBITDA = Gross Profit - G&A Expenses

Given:
  Gross Profit  = {gp:,.2f} GEL
  G&A Expenses  = {ga:,.2f} GEL

Calculation:
  EBITDA = {gp:,.2f} - {ga:,.2f}
         = {ebitda:,.2f} GEL

EBITDA Margin: {(ebitda/financial_data.get('revenue', 1)*100):.2f}%
"""
        
        return f"No explanation available for {metric}"
    
    def detect_anomalies_with_reasoning(self, financial_data: Dict) -> List[Dict]:
        """
        Detect anomalies using BUSINESS LOGIC, not just statistics
        """
        anomalies = []
        
        # Anomaly 1: Margin outside expected range for category
        if 'margin_pct' in financial_data and 'category' in financial_data:
            margin = financial_data['margin_pct']
            category = financial_data['category']
            
            expected_range = self.business_rules.expected_margin_ranges().get(category)
            
            if expected_range:
                min_margin, max_margin = expected_range
                
                if margin < min_margin or margin > max_margin:
                    anomalies.append({
                        'type': 'margin_out_of_range',
                        'severity': 'HIGH' if abs(margin - min_margin) > 10 else 'MEDIUM',
                        'message': f'Margin {margin:.2f}% outside expected range for {category}',
                        'expected_range': expected_range,
                        'actual': margin,
                        'reasoning': f"""
Based on historical data, {category} margins typically range from {min_margin}% to {max_margin}%.
Current margin of {margin:.2f}% is {'below' if margin < min_margin else 'above'} this range.

Possible causes:
- Pricing error (check selling price)
- Cost spike (verify supplier invoices)
- Product mix shift (analyze by sub-category)
- Data entry error (validate source data)
"""
                    })
        
        # Anomaly 2: Negative margin in typically profitable category
        if 'gross_profit' in financial_data and 'category' in financial_data:
            gp = financial_data['gross_profit']
            category = financial_data['category']
            
            if gp < 0 and 'retail' in category:
                anomalies.append({
                    'type': 'negative_retail_margin',
                    'severity': 'CRITICAL',
                    'message': f'Retail category showing loss: {gp:,.2f} GEL',
                    'reasoning': f"""
Retail operations should typically be profitable.
Negative gross profit of {gp:,.2f} GEL indicates:

Most likely causes:
1. COGS > Revenue (selling below cost)
2. Data error (check COGS calculation)
3. Promotional pricing without corresponding cost reduction

Action required: IMMEDIATE INVESTIGATION
"""
                })
        
        # Anomaly 3: COGS > Revenue (always suspicious)
        if 'revenue' in financial_data and 'cogs' in financial_data:
            revenue = financial_data['revenue']
            cogs = financial_data['cogs']
            
            if cogs > revenue and revenue > 0:
                anomalies.append({
                    'type': 'cogs_exceeds_revenue',
                    'severity': 'CRITICAL',
                    'message': 'COGS exceeds Revenue',
                    'reasoning': f"""
COGS ({cogs:,.2f}) is greater than Revenue ({revenue:,.2f}).
This means selling at a loss of {cogs - revenue:,.2f} GEL.

This is only acceptable if:
- Loss-leader strategy (deliberately selling at loss)
- Liquidation/clearance sale
- Temporary promotional pricing

Otherwise, this indicates:
- Pricing error (check selling price vs cost)
- COGS calculation error (verify account codes)
- Data entry mistake (review source transactions)
"""
                })
        
        return anomalies
    
    def generate_reasoning_chain(self, query: str, financial_data: Dict) -> List[str]:
        """
        Generate a chain of reasoning steps to answer a query
        This is what makes the LLM "think"
        """
        reasoning_chain = []
        
        if "what is gross profit" in query.lower():
            reasoning_chain = [
                "Step 1: Understand the query - User wants to know gross profit",
                "Step 2: Recall the axiom - Gross Profit = Revenue - COGS",
                f"Step 3: Identify known values - Revenue: {financial_data.get('revenue', 'UNKNOWN')}, COGS: {financial_data.get('cogs', 'UNKNOWN')}",
                f"Step 4: Apply formula - {financial_data.get('revenue', 0):,.2f} - {financial_data.get('cogs', 0):,.2f}",
                f"Step 5: Calculate result - Gross Profit = {financial_data.get('revenue', 0) - financial_data.get('cogs', 0):,.2f} GEL",
                f"Step 6: Validate - Check if result makes sense (should be positive for profitable business)",
                "Step 7: Answer - Provide calculation with explanation"
            ]
        
        elif "why is margin low" in query.lower():
            margin_pct = financial_data.get('margin_pct', 0)
            category = financial_data.get('category', 'unknown')
            
            reasoning_chain = [
                f"Step 1: Understand the concern - Margin is {margin_pct:.2f}%",
                f"Step 2: Recall expected range - {category} typically has {self.business_rules.expected_margin_ranges().get(category, 'unknown')}% margin",
                "Step 3: Identify components - Check Revenue and COGS breakdown",
                "Step 4: Analyze variance - Compare to historical average",
                "Step 5: Generate hypotheses:",
                "   - Hypothesis A: Revenue decreased (check pricing, volume)",
                "   - Hypothesis B: COGS increased (check supplier prices)",
                "   - Hypothesis C: Product mix shifted (check by sub-category)",
                "Step 6: Recommend investigation - Specify which data to examine",
                "Step 7: Answer with reasoning - Explain most likely cause"
            ]
        
        elif "calculate ebitda" in query.lower():
            reasoning_chain = [
                "Step 1: Understand the task - Calculate EBITDA",
                "Step 2: Recall the formula - EBITDA = Gross Profit - G&A Expenses",
                "Step 3: Check if Gross Profit is known",
                f"   - If yes: Use {financial_data.get('gross_profit', 'UNKNOWN')}",
                "   - If no: Calculate from Revenue - COGS first",
                "Step 4: Check if G&A is known",
                f"   - If yes: Use {financial_data.get('ga_expenses', 'UNKNOWN')}",
                "   - If no: Extract from Base sheet (accounts 73*, 74*, 82*, 92*)",
                "Step 5: Apply formula",
                "Step 6: Validate result",
                "Step 7: Return answer with calculation breakdown"
            ]
        
        return reasoning_chain


# ============================================================================
# PART 5: NYX CORE THINKER INCOME STATEMENT ONTOLOGY
# ============================================================================

class NyxIncomeStatementOntology:
    """
    Complete ontology for NYX Core Thinker's income statement structure
    Based on the detailed Georgian specification
    """
    
    def __init__(self):
        self.structure = self._build_structure()
        self.reasoning_engine = FinancialReasoningEngine()
    
    def _build_structure(self) -> Dict:
        """
        Build the complete hierarchical structure
        """
        return {
            'revenue': {
                'concept': FinancialConcept.REVENUE,
                'formula': 'revenue_wholesale + revenue_retail + revenue_other',
                'children': {
                    'revenue_wholesale': {
                        'formula': 'revenue_wholesale_petrol + revenue_wholesale_diesel + revenue_wholesale_bitumen',
                        'children': {
                            'revenue_wholesale_petrol': {
                                'products': [
                                    'ევრო რეგულარი (იმპორტი)',
                                    'პრემიუმი (რეექსპორტი)',
                                    'სუპერი (რეექსპორტი)',
                                ],
                                'source_sheet': 'Revenue Breakdown',
                                'source_column': 'Net Revenue (D)',
                                'filter_column': 'Product (A)'
                            },
                            'revenue_wholesale_diesel': {
                                'products': [
                                    'დიზელი (საბითუმო)',
                                    'ევროდიზელი (ექსპორტი)',
                                ],
                                'source_sheet': 'Revenue Breakdown',
                                'source_column': 'Net Revenue (D)'
                            },
                            'revenue_wholesale_bitumen': {
                                'products': [
                                    'ბიტუმი (საბითუმო)',
                                ],
                                'source_sheet': 'Revenue Breakdown',
                                'source_column': 'Net Revenue (D)'
                            }
                        }
                    },
                    'revenue_retail': {
                        'formula': 'revenue_retail_petrol + revenue_retail_diesel + revenue_retail_cng + revenue_retail_lpg',
                        'children': {
                            'revenue_retail_petrol': {
                                'products': [
                                    'ევრო რეგულარი',
                                    'პრემიუმი',
                                    'სუპერი',
                                ],
                                'source_sheet': 'Revenue Breakdown',
                                'source_column': 'Net Revenue (D)'
                            },
                            'revenue_retail_diesel': {
                                'products': [
                                    'დიზელი',
                                    'ევრო დიზელი',
                                ],
                                'source_sheet': 'Revenue Breakdown',
                                'source_column': 'Net Revenue (D)'
                            },
                            'revenue_retail_cng': {
                                'products': [
                                    'ბუნებრივი აირი',
                                    'ბუნებრივი აირი (საბითუმო)',
                                ],
                                'source_sheet': 'Revenue Breakdown',
                                'source_column': 'Net Revenue (D)'
                            },
                            'revenue_retail_lpg': {
                                'products': [
                                    'თხევადი აირი (მხოლოდ SGP !!!)',
                                ],
                                'source_sheet': 'Revenue Breakdown',
                                'source_column': 'Net Revenue (D)'
                            }
                        }
                    },
                    'revenue_other': {
                        'formula': 'sum(all products not in wholesale or retail)',
                        'source_sheet': 'Revenue Breakdown',
                        'source_column': 'Net Revenue (D)'
                    }
                }
            },
            'cogs': {
                'concept': FinancialConcept.COGS,
                'formula': 'cogs_wholesale + cogs_retail + cogs_other',
                'calculation_rule': 'SUM(column_K + column_L + column_O)',
                'source_columns': [10, 11, 14],  # K, L, O (0-indexed)
                'children': {
                    'cogs_wholesale': {
                        'formula': 'cogs_wholesale_petrol + cogs_wholesale_diesel + cogs_wholesale_bitumen',
                        'children': {
                            'cogs_wholesale_petrol': {
                                'products': [
                                    'ევრო რეგულარი (იმპორტი)',
                                    'პრემიუმი (რეექსპორტი)',
                                    'სუპერი (რეექსპორტი)',
                                    'ევრო რეგულარი (საბითუმო)',
                                ],
                                'source_sheet': 'COGS Breakdown',
                                'source_column': 'Субконто (A)'
                            },
                            'cogs_wholesale_diesel': {
                                'products': [
                                    'დიზელი (საბითუმო)',
                                    'ევროდიზელი (ექსპორტი)',
                                ],
                                'source_sheet': 'COGS Breakdown'
                            },
                            'cogs_wholesale_bitumen': {
                                'products': [
                                    'ბიტუმი (საბითუმო)',
                                ],
                                'source_sheet': 'COGS Breakdown'
                            }
                        }
                    },
                    'cogs_retail': {
                        'formula': 'cogs_retail_petrol + cogs_retail_diesel + cogs_retail_cng + cogs_retail_lpg',
                        'children': {
                            'cogs_retail_petrol': {
                                'products': [
                                    'ევრო რეგულარი',
                                    'პრემიუმი',
                                    'სუპერი',
                                ],
                                'source_sheet': 'COGS Breakdown'
                            },
                            'cogs_retail_diesel': {
                                'products': [
                                    'დიზელი',
                                    'ევრო დიზელი',
                                ],
                                'source_sheet': 'COGS Breakdown'
                            },
                            'cogs_retail_cng': {
                                'products': [
                                    'ბუნებრივი აირი',
                                    'ბუნებრივი აირი (საბითუმო)',
                                ],
                                'source_sheet': 'COGS Breakdown'
                            },
                            'cogs_retail_lpg': {
                                'products': [
                                    'თხევადი აირი (მხოლოდ SGP !!!)',
                                ],
                                'source_sheet': 'COGS Breakdown'
                            }
                        }
                    },
                    'cogs_other': {
                        'formula': 'sum(all products not in wholesale or retail)',
                        'source_sheet': 'COGS Breakdown'
                    }
                }
            },
            'gross_profit': {
                'concept': FinancialConcept.GROSS_PROFIT,
                'formula': 'revenue - cogs',
                'axiom': FinancialAxiom.gross_profit_formula(),
                'children': {
                    'gp_wholesale': {
                        'formula': 'revenue_wholesale - cogs_wholesale',
                        'children': {
                            'gp_wholesale_petrol': {
                                'formula': 'revenue_wholesale_petrol - cogs_wholesale_petrol'
                            },
                            'gp_wholesale_diesel': {
                                'formula': 'revenue_wholesale_diesel - cogs_wholesale_diesel'
                            },
                            'gp_wholesale_bitumen': {
                                'formula': 'revenue_wholesale_bitumen - cogs_wholesale_bitumen'
                            }
                        }
                    },
                    'gp_retail': {
                        'formula': 'revenue_retail - cogs_retail',
                        'children': {
                            'gp_retail_petrol': {
                                'formula': 'revenue_retail_petrol - cogs_retail_petrol'
                            },
                            'gp_retail_diesel': {
                                'formula': 'revenue_retail_diesel - cogs_retail_diesel'
                            },
                            'gp_retail_cng': {
                                'formula': 'revenue_retail_cng - cogs_retail_cng'
                            },
                            'gp_retail_lpg': {
                                'formula': 'revenue_retail_lpg - cogs_retail_lpg'
                            }
                        }
                    },
                    'gp_other': {
                        'formula': 'revenue_other - cogs_other'
                    }
                }
            },
            'ga_expenses': {
                'concept': FinancialConcept.OPERATING_EXPENSE,
                'formula': 'SUM(amounts where account_dr starts with 73|74|82|92)',
                'source_sheet': 'Base',
                'filter_rules': {
                    'column': 'Account Dr (E)',
                    'condition': 'starts_with',
                    'values': ['73', '74', '82', '92']
                },
                'specific_accounts': [
                    '7310.02.1',
                    '7410',
                    '7410.01',
                    '8220.01.1',
                    '9210'
                ],
                'amount_column': 'Сумма (S)',
                'period_column': 'Period (A)'
            },
            'ebitda': {
                'concept': FinancialConcept.EBITDA,
                'formula': 'gross_profit - ga_expenses',
                'axiom': FinancialAxiom.ebitda_formula()
            }
        }
    
    def get_calculation_path(self, metric: str) -> List[str]:
        """
        Get the complete calculation path for a metric
        """
        path = []
        
        def traverse(node, current_path):
            if isinstance(node, dict):
                if 'formula' in node:
                    current_path.append(node['formula'])
                
                if 'children' in node:
                    for child_name, child_node in node['children'].items():
                        traverse(child_node, current_path + [child_name])
        
        if metric in self.structure:
            traverse(self.structure[metric], [metric])
        
        return path
    
    def validate_complete_income_statement(self, data: Dict) -> Dict:
        """
        Validate entire income statement using ontology
        """
        validation_results = {
            'valid': True,
            'violations': [],
            'warnings': [],
            'inferences': {}
        }
        
        # Validate using reasoning engine
        axiom_validation = self.reasoning_engine.validate_against_axioms(data)
        
        if not axiom_validation['valid']:
            validation_results['valid'] = False
            validation_results['violations'].extend(axiom_validation['violations'])
        
        # Infer missing values
        inferred = self.reasoning_engine.infer_missing_values(data)
        validation_results['inferences'] = inferred
        
        # Detect anomalies
        anomalies = self.reasoning_engine.detect_anomalies_with_reasoning(data)
        validation_results['warnings'].extend(anomalies)
        
        return validation_results


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("FINANCIAL ONTOLOGY: Teaching LLMs to Actually Think")
    print("=" * 80)
    
    # Initialize ontology
    ontology = NyxIncomeStatementOntology()
    engine = ontology.reasoning_engine
    
    # Example 1: Validate financial data
    print("\n1. AXIOM VALIDATION")
    print("-" * 80)
    
    financial_data = {
        'revenue': Decimal('114159290.53'),
        'cogs': Decimal('102207129.67'),
        'gross_profit': Decimal('11952160.86'),  # Correct
        'ga_expenses': Decimal('6201571.95'),
        'ebitda': Decimal('5750588.91')
    }
    
    validation = engine.validate_against_axioms(financial_data)
    
    if validation['valid']:
        print("✅ All axioms satisfied!")
    else:
        print("❌ Axiom violations detected:")
        for v in validation['violations']:
            print(f"\n{v['severity']}: {v['message']}")
            print(f"Details: {v['details']}")
    
    # Example 2: Test with WRONG data
    print("\n\n2. DETECTING ERRORS")
    print("-" * 80)
    
    wrong_data = {
        'revenue': Decimal('114159290.53'),
        'cogs': Decimal('102207129.67'),
        'gross_profit': Decimal('13952160.86'),  # WRONG! (should be 11.95M)
        'ga_expenses': Decimal('6201571.95'),
        'ebitda': Decimal('7750588.91')  # Also wrong cascades from GP
    }
    
    validation = engine.validate_against_axioms(wrong_data)
    
    print(f"Valid: {validation['valid']}")
    for v in validation['violations']:
        print(f"\n❌ {v['severity']}: {v['message']}")
        print(f"   Expected: {v['details']['expected']:,.2f}")
        print(f"   Actual:   {v['details']['actual']:,.2f}")
        print(f"   Formula:  {v['details']['formula']}")
    
    # Example 3: Inference
    print("\n\n3. INFERRING MISSING VALUES")
    print("-" * 80)
    
    partial_data = {
        'revenue': Decimal('114159290.53'),
        'cogs': Decimal('102207129.67'),
        # gross_profit missing - can we infer it?
    }
    
    inferred = engine.infer_missing_values(partial_data)
    
    print("Given:")
    print(f"  Revenue: {partial_data['revenue']:,.2f} GEL")
    print(f"  COGS:    {partial_data['cogs']:,.2f} GEL")
    print("\nInferred:")
    for key, value in inferred.items():
        if not key.endswith('_source'):
            source = inferred.get(f"{key}_source", "")
            print(f"  {key}: {value:,.2f if isinstance(value, Decimal) else value}")
            if source:
                print(f"    → {source}")
    
    # Example 4: Explain calculation
    print("\n\n4. EXPLAINING CALCULATIONS")
    print("-" * 80)
    
    explanation = engine.explain_calculation('gross_profit', financial_data)
    print(explanation)
    
    # Example 5: Reasoning chain
    print("\n\n5. REASONING CHAIN")
    print("-" * 80)
    
    chain = engine.generate_reasoning_chain("calculate ebitda", financial_data)
    for step in chain:
        print(step)
    
    # Example 6: Anomaly detection
    print("\n\n6. BUSINESS LOGIC ANOMALY DETECTION")
    print("-" * 80)
    
    suspicious_data = {
        'revenue': Decimal('1000000'),
        'cogs': Decimal('1200000'),  # COGS > Revenue!
        'gross_profit': Decimal('-200000'),
        'margin_pct': Decimal('-20'),
        'category': 'retail_petrol'  # Retail should be profitable!
    }
    
    anomalies = engine.detect_anomalies_with_reasoning(suspicious_data)
    
    print(f"Detected {len(anomalies)} anomalies:\n")
    for anomaly in anomalies:
        print(f"{anomaly['severity']}: {anomaly['message']}")
        print(f"\nReasoning:")
        print(anomaly['reasoning'])
        print("-" * 80)
