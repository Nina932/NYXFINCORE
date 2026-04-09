"""
PARENT-CHILD RELATIONSHIP MATCHING & SEGMENTATION LOGIC
========================================================

This module teaches LLM to understand hierarchical financial structures
and correctly segment products into wholesale/retail categories.

Supports: Georgian (GEO), Russian (RUS), English (ENG)
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


# ============================================================================
# PART 1: PARENT-CHILD RELATIONSHIP MATCHING PRINCIPLE
# ============================================================================

@dataclass
class FinancialNode:
    """
    Represents a node in financial hierarchy
    """
    name_eng: str
    name_geo: str
    name_rus: str
    level: int  # 0=root, 1=category, 2=subcategory, 3=product
    parent: Optional['FinancialNode'] = None
    children: List['FinancialNode'] = None
    value: float = 0.0
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    def add_child(self, child: 'FinancialNode'):
        """Add child and set parent relationship"""
        self.children.append(child)
        child.parent = self
    
    def calculate_total(self) -> float:
        """
        AXIOM: Parent value MUST equal sum of children
        This is recursive and self-validating
        """
        if not self.children:
            return self.value
        
        calculated_total = sum(child.calculate_total() for child in self.children)
        
        # Validate
        if self.value > 0 and abs(calculated_total - self.value) > 0.01:
            raise ValueError(
                f"Parent-Child mismatch at {self.name_eng}: "
                f"Parent={self.value:,.2f}, Children sum={calculated_total:,.2f}"
            )
        
        return calculated_total if self.value == 0 else self.value


class ParentChildMatchingEngine:
    """
    Teaches LLM how to correctly match parent-child relationships
    across three languages
    """
    
    def __init__(self):
        # Define the complete hierarchy
        self.hierarchy = self._build_hierarchy()
    
    def _build_hierarchy(self) -> FinancialNode:
        """
        Build complete NYX Core Thinker income statement hierarchy
        with all three languages
        """
        # Root
        root = FinancialNode(
            name_eng="Total Revenue",
            name_geo="სულ შემოსავალი",
            name_rus="Общая выручка",
            level=0
        )
        
        # Level 1: Wholesale
        wholesale = FinancialNode(
            name_eng="Revenue Wholesale",
            name_geo="საბითუმო შემოსავალი",
            name_rus="Оптовая выручка",
            level=1
        )
        root.add_child(wholesale)
        
        # Level 2: Wholesale Petrol
        wholesale_petrol = FinancialNode(
            name_eng="Revenue Wholesale Petrol (Lari)",
            name_geo="საბითუმო ბენზინის შემოსავალი (ლარი)",
            name_rus="Оптовая выручка бензин (лари)",
            level=2
        )
        wholesale.add_child(wholesale_petrol)
        
        # Level 3: Individual products
        products_wholesale_petrol = [
            ("Euro Regular (Import)", "ევრო რეგულარი (იმპორტი)", "Евро Регуляр (Импорт)"),
            ("Premium (Re-export)", "პრემიუმი (რეექსპორტი)", "Премиум (Реэкспорт)"),
            ("Super (Re-export)", "სუპერი (რეექსპორტი)", "Супер (Реэкспорт)"),
            ("Euro Regular (Wholesale)", "ევრო რეგულარი (საბითუმო)", "Евро Регуляр (Оптом)"),
        ]
        
        for eng, geo, rus in products_wholesale_petrol:
            product = FinancialNode(
                name_eng=eng,
                name_geo=geo,
                name_rus=rus,
                level=3
            )
            wholesale_petrol.add_child(product)
        
        # Level 2: Wholesale Diesel
        wholesale_diesel = FinancialNode(
            name_eng="Revenue Wholesale Diesel (Lari)",
            name_geo="საბითუმო დიზელის შემოსავალი (ლარი)",
            name_rus="Оптовая выручка дизель (лари)",
            level=2
        )
        wholesale.add_child(wholesale_diesel)
        
        products_wholesale_diesel = [
            ("Diesel (Wholesale)", "დიზელი (საბითუმო)", "Дизель (Оптом)"),
            ("Euro Diesel (Export)", "ევროდიზელი (ექსპორტი)", "Евродизель (Экспорт)"),
        ]
        
        for eng, geo, rus in products_wholesale_diesel:
            product = FinancialNode(
                name_eng=eng,
                name_geo=geo,
                name_rus=rus,
                level=3
            )
            wholesale_diesel.add_child(product)
        
        # Level 2: Wholesale Bitumen
        wholesale_bitumen = FinancialNode(
            name_eng="Revenue Wholesale Bitumen (Lari)",
            name_geo="საბითუმო ბიტუმის შემოსავალი (ლარი)",
            name_rus="Оптовая выручка битум (лари)",
            level=2
        )
        wholesale.add_child(wholesale_bitumen)
        
        bitumen_product = FinancialNode(
            name_eng="Bitumen (Wholesale)",
            name_geo="ბიტუმი (საბითუმო)",
            name_rus="Битум (Оптом)",
            level=3
        )
        wholesale_bitumen.add_child(bitumen_product)
        
        # Level 1: Retail
        retail = FinancialNode(
            name_eng="Revenue Retail",
            name_geo="საცალო შემოსავალი",
            name_rus="Розничная выручка",
            level=1
        )
        root.add_child(retail)
        
        # Level 2: Retail Petrol
        retail_petrol = FinancialNode(
            name_eng="Revenue Retail Petrol (Lari)",
            name_geo="საცალო ბენზინის შემოსავალი (ლარი)",
            name_rus="Розничная выручка бензин (лари)",
            level=2
        )
        retail.add_child(retail_petrol)
        
        products_retail_petrol = [
            ("Euro Regular", "ევრო რეგულარი", "Евро Регуляр"),
            ("Premium", "პრემიუმი", "Премиум"),
            ("Super", "სუპერი", "Супер"),
        ]
        
        for eng, geo, rus in products_retail_petrol:
            product = FinancialNode(
                name_eng=eng,
                name_geo=geo,
                name_rus=rus,
                level=3
            )
            retail_petrol.add_child(product)
        
        # Level 2: Retail Diesel
        retail_diesel = FinancialNode(
            name_eng="Revenue Retail Diesel (Lari)",
            name_geo="საცალო დიზელის შემოსავალი (ლარი)",
            name_rus="Розничная выручка дизель (лари)",
            level=2
        )
        retail.add_child(retail_diesel)
        
        products_retail_diesel = [
            ("Diesel", "დიზელი", "Дизель"),
            ("Euro Diesel", "ევრო დიზელი", "Евро Дизель"),
        ]
        
        for eng, geo, rus in products_retail_diesel:
            product = FinancialNode(
                name_eng=eng,
                name_geo=geo,
                name_rus=rus,
                level=3
            )
            retail_diesel.add_child(product)
        
        # Level 2: Retail CNG
        retail_cng = FinancialNode(
            name_eng="Revenue Retail CNG (Lari)",
            name_geo="საცალო CNG შემოსავალი (ლარი)",
            name_rus="Розничная выручка CNG (лари)",
            level=2
        )
        retail.add_child(retail_cng)
        
        products_retail_cng = [
            ("Natural Gas", "ბუნებრივი აირი", "Природный газ"),
            ("Natural Gas (Wholesale)", "ბუნებრივი აირი (საბითუმო)", "Природный газ (Оптом)"),
        ]
        
        for eng, geo, rus in products_retail_cng:
            product = FinancialNode(
                name_eng=eng,
                name_geo=geo,
                name_rus=rus,
                level=3
            )
            retail_cng.add_child(product)
        
        # Level 2: Retail LPG
        retail_lpg = FinancialNode(
            name_eng="Revenue Retail LPG (Lari)",
            name_geo="საცალო LPG შემოსავალი (ლარი)",
            name_rus="Розничная выручка LPG (лари)",
            level=2
        )
        retail.add_child(retail_lpg)
        
        lpg_product = FinancialNode(
            name_eng="LPG (SGP only)",
            name_geo="თხევადი აირი (მხოლოდ SGP !!!)",
            name_rus="Сжиженный газ (только SGP)",
            level=3
        )
        retail_lpg.add_child(lpg_product)
        
        # Level 1: Other Revenue
        other = FinancialNode(
            name_eng="Other Revenue",
            name_geo="სხვა შემოსავალი",
            name_rus="Прочая выручка",
            level=1
        )
        root.add_child(other)
        
        return root
    
    def find_parent(self, product_name: str, language: str = 'auto') -> Optional[FinancialNode]:
        """
        Find parent category for a given product
        Works in any language
        """
        # Detect language if auto
        if language == 'auto':
            language = self._detect_language(product_name)
        
        # Search hierarchy
        def search(node: FinancialNode) -> Optional[FinancialNode]:
            # Check if product is in this node's children
            for child in node.children:
                if child.level == 3:  # Product level
                    if language == 'eng' and product_name.lower() in child.name_eng.lower():
                        return node
                    elif language == 'geo' and product_name in child.name_geo:
                        return node
                    elif language == 'rus' and product_name in child.name_rus:
                        return node
                else:
                    # Recurse
                    result = search(child)
                    if result:
                        return result
            return None
        
        return search(self.hierarchy)
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        # Georgian characters
        if re.search(r'[ა-ჰ]', text):
            return 'geo'
        # Cyrillic characters
        elif re.search(r'[а-яА-Я]', text):
            return 'rus'
        # Default to English
        else:
            return 'eng'
    
    def get_path_to_root(self, product_name: str) -> List[str]:
        """
        Get complete path from product to root
        Example: ["Premium", "Retail Petrol", "Retail", "Total Revenue"]
        """
        parent = self.find_parent(product_name)
        if not parent:
            return []
        
        path = []
        current = parent
        
        # Find the product node itself
        product_node = None
        for child in parent.children:
            if product_name in [child.name_eng, child.name_geo, child.name_rus]:
                product_node = child
                break
        
        if product_node:
            path.append(product_node.name_eng)
        
        # Traverse to root
        while current:
            path.append(current.name_eng)
            current = current.parent
        
        return path
    
    def validate_hierarchy(self, data: Dict[str, float]) -> Dict:
        """
        Validate that parent-child relationships are correct
        """
        errors = []
        
        # Assign values to nodes based on data
        def assign_values(node: FinancialNode):
            if node.level == 3:  # Product level
                # Look up value in data
                for key in [node.name_eng, node.name_geo, node.name_rus]:
                    if key in data:
                        node.value = data[key]
                        break
            
            for child in node.children:
                assign_values(child)
        
        assign_values(self.hierarchy)
        
        # Validate each parent-child relationship
        def validate(node: FinancialNode):
            if not node.children:
                return
            
            calculated = sum(child.calculate_total() for child in node.children)
            
            if node.value > 0:
                difference = abs(calculated - node.value)
                
                if difference > 0.01:
                    errors.append({
                        'node': node.name_eng,
                        'stated_value': node.value,
                        'calculated_value': calculated,
                        'difference': difference,
                        'severity': 'CRITICAL' if difference > 1000 else 'MEDIUM'
                    })
            
            for child in node.children:
                validate(child)
        
        validate(self.hierarchy)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


# ============================================================================
# PART 2: SEGMENTATION LOGIC (WHOLESALE VS RETAIL)
# ============================================================================

class SegmentationLogic:
    """
    სეგმენტაციის ლოგიკა - Teaches LLM how to correctly classify
    products into Wholesale vs Retail
    
    Supports multilingual pattern matching
    """
    
    def __init__(self):
        self.rules = self._define_segmentation_rules()
    
    def _define_segmentation_rules(self) -> Dict:
        """
        Define comprehensive segmentation rules
        """
        return {
            'wholesale_indicators': {
                'eng': [
                    r'\(import\)',
                    r'\(export\)',
                    r'\(re-?export\)',
                    r'\(wholesale\)',
                    r',\s*kg',  # Sold by kilogram (bulk)
                ],
                'geo': [
                    r'\(იმპორტი\)',
                    r'\(ექსპორტი\)',
                    r'\(რეექსპორტი\)',
                    r'\(საბითუმო\)',
                    r',\s*კგ',
                ],
                'rus': [
                    r'\(импорт\)',
                    r'\(экспорт\)',
                    r'\(реэкспорт\)',
                    r'\(оптом\)',
                    r',\s*кг',
                ]
            },
            'retail_indicators': {
                'eng': [
                    r',\s*l(?:\s|$)',  # Sold by liter
                    r',\s*m3',          # Sold by cubic meter
                    r'\(retail\)',
                ],
                'geo': [
                    r',\s*ლ(?:\s|$)',
                    r',\s*მ3',
                ],
                'rus': [
                    r',\s*л(?:\s|$)',
                    r',\s*м3',
                ]
            },
            'special_cases': {
                # Products that look wholesale but are retail
                'retail_despite_wholesale_markers': [
                    'ბუნებრივი აირი (საბითუმო)',  # Has საბითუმო but is retail!
                ],
                # Products with ambiguous naming
                'context_dependent': [
                    'ევრო რეგულარი',  # Could be retail or wholesale
                ]
            },
            'reasoning_rules': {
                'rule_1': {
                    'eng': 'If product name contains (Import), (Export), or (Re-export), it is WHOLESALE',
                    'geo': 'თუ პროდუქტის სახელი შეიცავს (იმპორტი), (ექსპორტი), ან (რეექსპორტი), ეს არის ᲡᲐᲑᲘᲗᲣᲛᲝ',
                    'rus': 'Если название продукта содержит (Импорт), (Экспорт), или (Реэкспорт), это ОПТОМ'
                },
                'rule_2': {
                    'eng': 'If product is sold by kg, it is typically WHOLESALE (bulk)',
                    'geo': 'თუ პროდუქტი იყიდება კილოგრამებში, ეს ჩვეულებრივ არის ᲡᲐᲑᲘᲗᲣᲛᲝ',
                    'rus': 'Если продукт продается на килограммы, это обычно ОПТОМ'
                },
                'rule_3': {
                    'eng': 'If product is sold by liter or m3, it is typically RETAIL',
                    'geo': 'თუ პროდუქტი იყიდება ლიტრებში ან მ3-ში, ეს ჩვეულებრივ არის ᲡᲐᲪᲐᲚᲝ',
                    'rus': 'Если продукт продается литрами или м3, это обычно РОЗНИЦА'
                },
                'rule_4': {
                    'eng': 'Product name alone is not sufficient - check unit of measure',
                    'geo': 'მხოლოდ პროდუქტის სახელი არ არის საკმარისი - შეამოწმე საზომი ერთეული',
                    'rus': 'Только название продукта недостаточно - проверьте единицу измерения'
                },
                'rule_5': {
                    'eng': 'EXCEPTION: "ბუნებრივი აირი (საბითუმო)" is RETAIL despite having "საბითუმო" in name',
                    'geo': 'გამონაკლისი: "ბუნებრივი აირი (საბითუმო)" არის ᲡᲐᲪᲐᲚᲝ მიუხედავად "საბითუმო"-ს',
                    'rus': 'ИСКЛЮЧЕНИЕ: "ბუნებრივი აირი (საბითუმო)" это РОЗНИЦА несмотря на "საბითუმო"'
                }
            }
        }
    
    def classify(self, product_name: str, context: Optional[Dict] = None) -> Dict:
        """
        Classify product as wholesale or retail with reasoning
        
        Returns full reasoning chain showing WHY decision was made
        """
        # Check special cases first
        if product_name in self.rules['special_cases']['retail_despite_wholesale_markers']:
            return {
                'segment': 'retail',
                'confidence': 1.0,
                'reasoning': [
                    f"SPECIAL CASE: '{product_name}' is a known exception",
                    self.rules['reasoning_rules']['rule_5']['eng'],
                    "Despite containing 'საბითუმო' (wholesale), this product is sold retail"
                ],
                'applied_rules': ['rule_5']
            }
        
        reasoning = []
        applied_rules = []
        wholesale_score = 0
        retail_score = 0
        
        # Check wholesale indicators
        for lang, patterns in self.rules['wholesale_indicators'].items():
            for pattern in patterns:
                if re.search(pattern, product_name, re.IGNORECASE):
                    wholesale_score += 1
                    reasoning.append(
                        f"Found wholesale indicator: '{pattern}' in product name"
                    )
                    applied_rules.append('rule_1' if 'export' in pattern else 'rule_2')
        
        # Check retail indicators
        for lang, patterns in self.rules['retail_indicators'].items():
            for pattern in patterns:
                if re.search(pattern, product_name, re.IGNORECASE):
                    retail_score += 1
                    reasoning.append(
                        f"Found retail indicator: '{pattern}' in product name"
                    )
                    applied_rules.append('rule_3')
        
        # Decision logic
        if wholesale_score > retail_score:
            segment = 'wholesale'
            confidence = wholesale_score / (wholesale_score + retail_score)
        elif retail_score > wholesale_score:
            segment = 'retail'
            confidence = retail_score / (wholesale_score + retail_score)
        else:
            segment = 'unknown'
            confidence = 0.5
            reasoning.append("AMBIGUOUS: Equal evidence for wholesale and retail")
            reasoning.append(self.rules['reasoning_rules']['rule_4']['eng'])
        
        # Add context if available
        if context and 'unit' in context:
            unit = context['unit']
            if unit in ['kg', 'кг', 'კგ']:
                wholesale_score += 1
                reasoning.append(f"Unit of measure '{unit}' suggests wholesale")
            elif unit in ['l', 'л', 'ლ', 'm3', 'м3', 'მ3']:
                retail_score += 1
                reasoning.append(f"Unit of measure '{unit}' suggests retail")
        
        return {
            'segment': segment,
            'confidence': confidence,
            'reasoning': reasoning,
            'applied_rules': list(set(applied_rules)),
            'scores': {
                'wholesale': wholesale_score,
                'retail': retail_score
            }
        }
    
    def explain_segmentation(self, product_name: str, language: str = 'eng') -> str:
        """
        Generate detailed explanation of segmentation decision
        in specified language
        """
        result = self.classify(product_name)
        
        explanations = {
            'eng': f"""
SEGMENTATION ANALYSIS: {product_name}
{'=' * 60}

DECISION: {result['segment'].upper()}
CONFIDENCE: {result['confidence']:.1%}

REASONING CHAIN:
{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(result['reasoning']))}

APPLIED RULES:
{chr(10).join(f'- {rule}: {self.rules["reasoning_rules"][rule]["eng"]}' for rule in result['applied_rules'])}

SCORING:
- Wholesale indicators: {result['scores']['wholesale']}
- Retail indicators: {result['scores']['retail']}

CONCLUSION: Based on the analysis above, this product is classified as {result['segment'].upper()}.
""",
            'geo': f"""
სეგმენტაციის ანალიზი: {product_name}
{'=' * 60}

გადაწყვეტილება: {result['segment'].upper()}
ნდობა: {result['confidence']:.1%}

მსჯელობის ჯაჭვი:
{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(result['reasoning']))}

გამოყენებული წესები:
{chr(10).join(f'- {rule}: {self.rules["reasoning_rules"][rule]["geo"]}' for rule in result['applied_rules'])}

ქულები:
- საბითუმო ინდიკატორები: {result['scores']['wholesale']}
- საცალო ინდიკატორები: {result['scores']['retail']}

დასკვნა: ზემოთ მოცემული ანალიზის საფუძველზე, ეს პროდუქტი კლასიფიცირდება როგორც {result['segment'].upper()}.
""",
            'rus': f"""
АНАЛИЗ СЕГМЕНТАЦИИ: {product_name}
{'=' * 60}

РЕШЕНИЕ: {result['segment'].upper()}
УВЕРЕННОСТЬ: {result['confidence']:.1%}

ЦЕПОЧКА РАССУЖДЕНИЙ:
{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(result['reasoning']))}

ПРИМЕНЁННЫЕ ПРАВИЛА:
{chr(10).join(f'- {rule}: {self.rules["reasoning_rules"][rule]["rus"]}' for rule in result['applied_rules'])}

ОЦЕНКА:
- Оптовые индикаторы: {result['scores']['wholesale']}
- Розничные индикаторы: {result['scores']['retail']}

ВЫВОД: На основании вышеизложенного анализа, этот продукт классифицируется как {result['segment'].upper()}.
"""
        }
        
        return explanations.get(language, explanations['eng'])


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("PARENT-CHILD MATCHING & SEGMENTATION LOGIC DEMONSTRATION")
    print("=" * 80)
    
    # Test 1: Parent-Child Matching
    print("\n1. PARENT-CHILD RELATIONSHIP MATCHING")
    print("-" * 80)
    
    matcher = ParentChildMatchingEngine()
    
    test_products = [
        "Premium",
        "პრემიუმი (რეექსპორტი)",
        "Дизель (Оптом)",
        "ბუნებრივი აირი",
    ]
    
    for product in test_products:
        path = matcher.get_path_to_root(product)
        print(f"\nProduct: {product}")
        print(f"Path to root: {' → '.join(reversed(path))}")
    
    # Test 2: Segmentation Logic
    print("\n\n2. SEGMENTATION LOGIC (WHOLESALE VS RETAIL)")
    print("-" * 80)
    
    segmenter = SegmentationLogic()
    
    test_cases = [
        ("ევრო რეგულარი (იმპორტი), კგ", None),
        ("პრემიუმი, ლ", None),
        ("ბუნებრივი აირი (საბითუმო), მ3", None),
        ("დიზელი (საბითუმო), ლ", None),
    ]
    
    for product, context in test_cases:
        result = segmenter.classify(product, context)
        print(f"\n{'=' * 80}")
        print(f"Product: {product}")
        print(f"Segment: {result['segment'].upper()}")
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"\nReasoning:")
        for i, r in enumerate(result['reasoning'], 1):
            print(f"  {i}. {r}")
    
    # Test 3: Multilingual Explanation
    print("\n\n3. MULTILINGUAL SEGMENTATION EXPLANATION")
    print("-" * 80)
    
    product = "ბუნებრივი აირი (საბითუმო)"
    
    for lang, lang_name in [('eng', 'ENGLISH'), ('geo', 'GEORGIAN'), ('rus', 'RUSSIAN')]:
        print(f"\n{lang_name}:")
        print(segmenter.explain_segmentation(product, lang))
