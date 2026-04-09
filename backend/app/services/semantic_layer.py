"""
semantic_layer.py — Intelligent Semantic Layer for FinAI.

Adds AI/NLP-style understanding to transaction classification when dedicated
breakdown sheets (Revenue, COGS) are missing. Works by analyzing:

1. Counterparty names  — known fuel suppliers → COGS, banks → Finance, etc.
2. Department names    — Retail Ops → Retail segment, Wholesale → Wholesale, etc.
3. Cost classification — free-text cost_class field semantic parsing
4. Account code cross-reference — COA codes enriched with contextual signals
5. Historical patterns — learns from full-report uploads for future inference

Priority waterfall:
  COA account code  >  Counterparty pattern  >  Department  >  Cost class text  >  Historical

This module does NOT replace the COA-based classification — it augments it
by resolving ambiguities and classifying "Other" items into proper buckets.
"""

import re
import logging
from typing import Optional, Dict, List, Tuple, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. COUNTERPARTY CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════════

# Known counterparty patterns and their financial classification
# Each pattern maps to: (pl_line, segment, sub_category, confidence)
COUNTERPARTY_PATTERNS = {
    # ── Fuel suppliers → COGS ──────────────────────────────────────
    "fuel": {
        "keywords": [
            "nyx", "petrol", "fuel", "oil", "petroleum", "benzin",
            "diesel", "gasoline", "bitumen", "lpg", "cng", "gas station",
            "filling", "refinery", "lukoil", "bp ", "shell", "total",
            "gulf", "opet", "sunpetro", "wissol", "rompetrol",
            # Georgian fuel companies
            "საწვავ", "ნავთობ", "ბენზინ", "დიზელ", "ბიტუმ",
        ],
        "pl_line": "COGS",
        "segment": "Fuel",
        "confidence": 0.8,
    },
    # ── Banks & financial → Finance ────────────────────────────────
    "banking": {
        "keywords": [
            "bank", "tbilisi", "bog", "tbc", "liberty", "basis bank",
            "procredit", "credo", "finca", "crystal",
            "ბანკ", "საქართველოს ბანკი",
        ],
        "pl_line": "Finance",
        "segment": "Finance",
        "confidence": 0.85,
    },
    # ── Government & tax → Tax ─────────────────────────────────────
    "government": {
        "keywords": [
            "tax", "revenue service", "customs", "government",
            "ministry", "municipality", "საგადასახადო", "მთავრობ",
            "საბაჟო", "სამინისტრო",
        ],
        "pl_line": "Tax",
        "segment": "Government",
        "confidence": 0.9,
    },
    # ── Utilities → SGA/Admin ──────────────────────────────────────
    "utilities": {
        "keywords": [
            "electric", "water", "gas supply", "telasi", "gwp",
            "energo", "utility", "telecom", "magti", "geocell",
            "beeline", "silknet", "ელექტრო", "წყალ",
        ],
        "pl_line": "SGA",
        "sub": "Admin",
        "segment": "Utilities",
        "confidence": 0.75,
    },
    # ── Transport & logistics → COGS or SGA ────────────────────────
    "transport": {
        "keywords": [
            "transport", "logistics", "shipping", "freight", "cargo",
            "delivery", "truck", "railway", "ტრანსპორტ", "ლოჯისტ",
            "გადაზიდვ",
        ],
        "pl_line": "COGS",
        "segment": "Transport",
        "confidence": 0.65,
    },
    # ── Insurance → SGA ────────────────────────────────────────────
    "insurance": {
        "keywords": [
            "insurance", "aldagi", "gpi", "ardi", "unison",
            "დაზღვევ",
        ],
        "pl_line": "SGA",
        "sub": "Admin",
        "segment": "Insurance",
        "confidence": 0.8,
    },
    # ── HR / staffing → SGA Labour ─────────────────────────────────
    "personnel": {
        "keywords": [
            "salary", "payroll", "pension", "social", "hr ",
            "staff", "employee", "ხელფას", "პენსი",
        ],
        "pl_line": "SGA",
        "sub": "Labour",
        "segment": "Personnel",
        "confidence": 0.85,
    },
    # ── Professional services → SGA Admin ──────────────────────────
    "professional": {
        "keywords": [
            "audit", "legal", "consulting", "advisory", "accounting",
            "lawyer", "attorney", "notary", "აუდიტ", "იურიდ",
            "კონსულტ", "ბუღალტრ",
        ],
        "pl_line": "SGA",
        "sub": "Admin",
        "segment": "Professional Services",
        "confidence": 0.8,
    },
    # ── Maintenance & repair → SGA or COGS ─────────────────────────
    "maintenance": {
        "keywords": [
            "repair", "maintenance", "service", "construction",
            "building", "renovation", "შეკეთებ", "მოვლა",
            "მშენებლობ",
        ],
        "pl_line": "SGA",
        "sub": "Other",
        "segment": "Maintenance",
        "confidence": 0.6,
    },
}


def classify_counterparty(counterparty: str) -> Optional[Dict]:
    """
    Classify a transaction based on counterparty name.
    Returns dict with {pl_line, segment, sub, confidence} or None.
    """
    if not counterparty:
        return None
    cp_lower = counterparty.lower().strip()
    if not cp_lower or cp_lower in ("0", "???", "-", "n/a"):
        return None

    best_match = None
    best_confidence = 0.0

    for category, config in COUNTERPARTY_PATTERNS.items():
        for kw in config["keywords"]:
            if kw in cp_lower:
                conf = config["confidence"]
                # Boost confidence for longer keyword matches
                if len(kw) > 5:
                    conf = min(1.0, conf + 0.05)
                if conf > best_confidence:
                    best_confidence = conf
                    best_match = {
                        "category": category,
                        "pl_line": config["pl_line"],
                        "segment": config.get("segment", "Other"),
                        "sub": config.get("sub", ""),
                        "confidence": round(conf, 2),
                        "matched_keyword": kw,
                    }

    return best_match


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DEPARTMENT MAPPER
# ═══════════════════════════════════════════════════════════════════════════════

DEPARTMENT_SEGMENT_MAP = {
    # Retail departments
    "retail": "Retail",
    "station": "Retail",
    "filling station": "Retail",
    "gas station": "Retail",
    "petrol station": "Retail",
    "retail operations": "Retail",
    "retail sales": "Retail",
    "საცალო": "Retail",
    "სადგურ": "Retail",
    # Wholesale departments
    "wholesale": "Wholesale",
    "bulk": "Wholesale",
    "export": "Wholesale",
    "import": "Wholesale",
    "trading": "Wholesale",
    "საბითუმო": "Wholesale",
    "ექსპორტ": "Wholesale",
    "იმპორტ": "Wholesale",
    # Administrative / HQ
    "hq": "Admin",
    "head office": "Admin",
    "admin": "Admin",
    "finance": "Admin",
    "hr": "Admin",
    "human resources": "Admin",
    "legal": "Admin",
    "it": "Admin",
    "management": "Admin",
    "ადმინისტრაც": "Admin",
    "ფინანს": "Admin",
    # Operations
    "operations": "Operations",
    "logistics": "Operations",
    "supply": "Operations",
    "warehouse": "Operations",
    "depot": "Operations",
    "ლოჯისტიკ": "Operations",
    "საწყობ": "Operations",
}


def classify_department(dept: str) -> Optional[str]:
    """
    Map a department name to a business segment.
    Returns: 'Retail' | 'Wholesale' | 'Admin' | 'Operations' | None
    """
    if not dept:
        return None
    d_lower = dept.lower().strip()
    if not d_lower or d_lower in ("0", "???", "-", "n/a"):
        return None

    # Exact match first
    if d_lower in DEPARTMENT_SEGMENT_MAP:
        return DEPARTMENT_SEGMENT_MAP[d_lower]

    # Substring match
    for keyword, segment in DEPARTMENT_SEGMENT_MAP.items():
        if keyword in d_lower:
            return segment

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. COST CLASSIFICATION TEXT ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

COST_CLASS_PATTERNS = {
    "COGS": {
        "keywords": [
            "fuel purchase", "raw material", "product cost", "cost of goods",
            "inventory", "procurement", "purchase", "საწვავ", "ნედლეულ",
            "შეძენ", "პროდუქც",
        ],
        "confidence": 0.75,
    },
    "SGA_Labour": {
        "keywords": [
            "salary", "wage", "payroll", "bonus", "compensation",
            "social contribution", "pension", "benefits",
            "ხელფას", "ანაზღაურებ", "პრემი", "პენსი",
        ],
        "confidence": 0.85,
    },
    "SGA_Admin": {
        "keywords": [
            "rent", "office", "admin", "utility", "communication",
            "telephone", "internet", "stationery", "subscription",
            "ქირა", "ოფის", "კომუნალ", "ტელეფონ",
        ],
        "confidence": 0.75,
    },
    "SGA_Marketing": {
        "keywords": [
            "marketing", "advertising", "promotion", "sponsorship",
            "brand", "pr ", "public relation",
            "მარკეტინგ", "რეკლამ", "სპონსორ",
        ],
        "confidence": 0.8,
    },
    "DA": {
        "keywords": [
            "depreciation", "amortization", "write-off", "impairment",
            "ცვეთა", "ამორტიზაც",
        ],
        "confidence": 0.9,
    },
    "Finance": {
        "keywords": [
            "interest", "bank charge", "commission", "loan",
            "exchange rate", "forex", "currency",
            "პროცენტ", "საბანკო", "საკომისი", "სესხ",
        ],
        "confidence": 0.8,
    },
    "Tax": {
        "keywords": [
            "income tax", "property tax", "vat", "excise",
            "საშემოსავლო გადასახადი", "ქონების გადასახადი", "აქციზ",
        ],
        "confidence": 0.85,
    },
}


def classify_cost_class(cost_class: str) -> Optional[Dict]:
    """
    Analyze cost_class text field for semantic meaning.
    Returns dict with {pl_line, sub, confidence} or None.
    """
    if not cost_class:
        return None
    cc_lower = cost_class.lower().strip()
    if not cc_lower or cc_lower in ("0", "???", "-", "n/a"):
        return None

    best_match = None
    best_confidence = 0.0

    for category, config in COST_CLASS_PATTERNS.items():
        for kw in config["keywords"]:
            if kw in cc_lower:
                conf = config["confidence"]
                if conf > best_confidence:
                    best_confidence = conf
                    pl_line = category.split("_")[0] if "_" in category else category
                    sub = category.split("_")[1] if "_" in category else ""
                    best_match = {
                        "category": category,
                        "pl_line": pl_line,
                        "sub": sub,
                        "confidence": round(conf, 2),
                        "matched_keyword": kw,
                    }

    return best_match


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SEMANTIC TRANSACTION CLASSIFIER (Multi-Signal Fusion)
# ═══════════════════════════════════════════════════════════════════════════════

class SemanticClassification:
    """Result of semantic classification for a single transaction."""
    __slots__ = [
        "pl_line", "segment", "sub", "confidence",
        "signals", "product_hint", "is_revenue",
    ]

    def __init__(self):
        self.pl_line = "Other"       # COGS | SGA | DA | Finance | Tax | Other
        self.segment = "Other"       # Retail | Wholesale | Admin | Other
        self.sub = ""                # Labour | Admin | Marketing | Other
        self.confidence = 0.0        # 0.0 - 1.0
        self.signals = []            # list of (source, classification, confidence)
        self.product_hint = ""       # inferred product type if any
        self.is_revenue = False      # True if this appears to be revenue

    def to_dict(self):
        return {
            "pl_line": self.pl_line,
            "segment": self.segment,
            "sub": self.sub,
            "confidence": self.confidence,
            "signals": self.signals,
            "product_hint": self.product_hint,
            "is_revenue": self.is_revenue,
        }


def classify_transaction_semantic(txn: Dict) -> SemanticClassification:
    """
    Multi-signal semantic classification of a single transaction.

    Combines:
    1. COA account code (highest priority)
    2. Counterparty pattern
    3. Department mapping
    4. Cost classification text

    Returns a SemanticClassification with fused result.
    """
    from app.services.file_parser import map_coa

    result = SemanticClassification()
    signals = []

    acct_dr = str(txn.get("acct_dr", "")).strip()
    acct_cr = str(txn.get("acct_cr", "")).strip()
    counterparty = str(txn.get("counterparty", "")).strip()
    dept = str(txn.get("dept", "")).strip()
    cost_class = str(txn.get("cost_class", "")).strip()
    amount = abs(float(txn.get("amount", 0)))

    # ── Signal 1: COA Account Code (weight: 1.0) ──────────────────
    dr_map = map_coa(acct_dr) if acct_dr else None
    cr_map = map_coa(acct_cr) if acct_cr else None

    if dr_map:
        if dr_map.get("side") == "expense":
            pl_line = dr_map.get("pl_line", "SGA")
            signals.append(("coa_dr", pl_line, 1.0))
        if dr_map.get("bs_side"):
            signals.append(("coa_dr_bs", dr_map.get("bs_side"), 0.9))

    if cr_map:
        if cr_map.get("side") == "income":
            signals.append(("coa_cr", "Revenue", 1.0))
            result.is_revenue = True
            seg = cr_map.get("segment", "Other")
            if seg != "Other":
                signals.append(("coa_cr_segment", seg, 0.95))

    # ── Signal 2: Counterparty Pattern (weight: 0.7) ──────────────
    cp_result = classify_counterparty(counterparty)
    if cp_result:
        signals.append(("counterparty", cp_result["pl_line"], cp_result["confidence"] * 0.7))
        if cp_result.get("segment"):
            signals.append(("counterparty_segment", cp_result["segment"], cp_result["confidence"] * 0.6))
        # Infer product hint from fuel counterparties
        if cp_result["category"] == "fuel":
            result.product_hint = "Fuel Product"

    # ── Signal 3: Department (weight: 0.5) ─────────────────────────
    dept_segment = classify_department(dept)
    if dept_segment:
        signals.append(("department", dept_segment, 0.5))

    # ── Signal 4: Cost Class Text (weight: 0.6) ───────────────────
    cc_result = classify_cost_class(cost_class)
    if cc_result:
        signals.append(("cost_class", cc_result["pl_line"], cc_result["confidence"] * 0.6))
        if cc_result.get("sub"):
            signals.append(("cost_class_sub", cc_result["sub"], cc_result["confidence"] * 0.5))

    # ── Fuse signals ──────────────────────────────────────────────
    result.signals = [(s, c, round(w, 3)) for s, c, w in signals]

    if not signals:
        result.pl_line = "Other"
        result.confidence = 0.0
        return result

    # Find highest-confidence pl_line signal
    pl_signals = [(c, w) for s, c, w in signals
                  if c in ("COGS", "SGA", "DA", "Finance", "Tax", "Revenue", "Other")
                  and s not in ("coa_dr_bs", "counterparty_segment", "department", "cost_class_sub")]

    if pl_signals:
        # Weighted vote
        pl_scores = defaultdict(float)
        for classification, weight in pl_signals:
            pl_scores[classification] += weight
        best_pl = max(pl_scores, key=pl_scores.get)
        result.pl_line = best_pl
        result.confidence = round(min(1.0, pl_scores[best_pl]), 2)

    # Find segment
    seg_signals = [(c, w) for s, c, w in signals
                   if s in ("coa_cr_segment", "counterparty_segment", "department")]
    if seg_signals:
        seg_scores = defaultdict(float)
        for classification, weight in seg_signals:
            seg_scores[classification] += weight
        result.segment = max(seg_scores, key=seg_scores.get)

    # Find sub-category
    sub_signals = [(c, w) for s, c, w in signals if s == "cost_class_sub"]
    if sub_signals:
        result.sub = max(sub_signals, key=lambda x: x[1])[0]

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ENHANCED TRANSACTION-DERIVED FINANCIALS
# ═══════════════════════════════════════════════════════════════════════════════

def derive_enhanced_financials(transactions: list) -> Dict:
    """
    Enhanced derivation of financial data from Transaction Ledger using
    semantic layer. Goes beyond pure COA code matching to classify
    transactions using counterparty, department, and cost text signals.

    Returns a dict with:
    - revenue_items: enriched with segment inference
    - cogs_items: enriched with product hints
    - ga_expenses: enriched with sub-category breakdown
    - sga_breakdown: {Labour, Admin, Marketing, Other}
    - finance_items: interest, bank charges, etc.
    - tax_items: estimated tax transactions
    - classification_stats: how many were classified by each signal
    - unclassified: transactions that couldn't be classified
    """
    from app.services.file_parser import map_coa, GA_ACCOUNT_CODES, GA_ACCOUNT_NAMES

    revenue_items = []
    cogs_items = []
    ga_expenses_by_code = {}
    sga_breakdown = {"Labour": 0.0, "Admin": 0.0, "Marketing": 0.0, "Other": 0.0}
    finance_items = {"income": 0.0, "expense": 0.0}
    tax_total = 0.0
    da_total = 0.0
    unclassified = []

    # Classification statistics
    stats = {
        "total": len(transactions),
        "by_coa": 0,
        "by_counterparty": 0,
        "by_department": 0,
        "by_cost_class": 0,
        "unclassified": 0,
        "zero_amount": 0,
    }

    # Revenue and COGS accumulators (keyed by inferred segment)
    rev_accum = defaultdict(lambda: {"gross": 0.0, "net": 0.0, "count": 0})
    cogs_accum = defaultdict(lambda: {"total": 0.0, "count": 0})

    for txn in transactions:
        amt = abs(float(txn.get("amount", 0)))
        if amt == 0:
            stats["zero_amount"] += 1
            continue

        acct_dr = str(txn.get("acct_dr", "")).strip()
        acct_cr = str(txn.get("acct_cr", "")).strip()

        # Get semantic classification
        sem = classify_transaction_semantic(txn)

        # Track which signal source was primary
        primary_source = "unclassified"
        if sem.signals:
            top_signal = max(sem.signals, key=lambda x: x[2])
            if "coa" in top_signal[0]:
                primary_source = "coa"
            elif "counterparty" in top_signal[0]:
                primary_source = "counterparty"
            elif "department" in top_signal[0]:
                primary_source = "department"
            elif "cost_class" in top_signal[0]:
                primary_source = "cost_class"

        if primary_source != "unclassified":
            stats[f"by_{primary_source}"] = stats.get(f"by_{primary_source}", 0) + 1
        else:
            stats["unclassified"] += 1

        # ── G&A extraction (specific account codes) ───────────────
        if acct_dr and acct_dr in GA_ACCOUNT_CODES:
            if acct_dr not in ga_expenses_by_code:
                ga_expenses_by_code[acct_dr] = 0.0
            ga_expenses_by_code[acct_dr] += amt
            continue  # G&A is handled separately, don't double-count

        # ── Route by semantic classification ──────────────────────
        if sem.is_revenue:
            # Revenue transaction
            seg_key = sem.segment if sem.segment != "Other" else "Other Revenue"
            rev_accum[seg_key]["net"] += amt
            rev_accum[seg_key]["gross"] += amt
            rev_accum[seg_key]["count"] += 1

        elif sem.pl_line == "COGS":
            seg_key = sem.segment if sem.segment != "Other" else "Other COGS"
            cogs_accum[seg_key]["total"] += amt
            cogs_accum[seg_key]["count"] += 1

        elif sem.pl_line == "DA":
            da_total += amt

        elif sem.pl_line == "Finance":
            # Check if it's income or expense
            dr_map = map_coa(acct_dr) if acct_dr else None
            if dr_map and dr_map.get("pl_line") == "Finance":
                finance_items["expense"] += amt
            else:
                finance_items["income"] += amt

        elif sem.pl_line == "Tax":
            tax_total += amt

        elif sem.pl_line == "SGA":
            sub = sem.sub or "Other"
            if sub in sga_breakdown:
                sga_breakdown[sub] += amt
            else:
                sga_breakdown["Other"] += amt

        elif sem.confidence < 0.3:
            unclassified.append({
                "date": txn.get("date", ""),
                "counterparty": txn.get("counterparty", ""),
                "amount": amt,
                "acct_dr": acct_dr,
                "acct_cr": acct_cr,
                "dept": txn.get("dept", ""),
                "cost_class": txn.get("cost_class", ""),
                "semantic": sem.to_dict(),
            })
        else:
            sga_breakdown["Other"] += amt

    # ── Build revenue items ───────────────────────────────────────
    for seg_key, data in rev_accum.items():
        # Map segment to known revenue categories
        rev_category = _infer_revenue_category(seg_key)
        revenue_items.append({
            "product": seg_key,
            "product_en": seg_key,
            "gross": round(data["gross"], 2),
            "vat": 0.0,
            "net": round(data["net"], 2),
            "segment": rev_category.get("segment", "Other Revenue"),
            "category": rev_category.get("category", "Other Revenue"),
            "source": "semantic_layer",
            "txn_count": data["count"],
        })

    # ── Build COGS items ──────────────────────────────────────────
    for seg_key, data in cogs_accum.items():
        cogs_category = _infer_cogs_category(seg_key)
        cogs_items.append({
            "product": seg_key,
            "product_en": seg_key,
            "col6": round(data["total"], 2),
            "col7310": 0.0,
            "col8230": 0.0,
            "total_cogs": round(data["total"], 2),
            "segment": cogs_category.get("segment", "Other COGS"),
            "category": cogs_category.get("category", "Other COGS"),
            "source": "semantic_layer",
            "txn_count": data["count"],
        })

    # ── Build G&A expense items ───────────────────────────────────
    ga_expenses = [
        {
            "account_code": code,
            "account_name": GA_ACCOUNT_NAMES.get(code, f"G&A ({code})"),
            "amount": round(amount, 2),
        }
        for code, amount in ga_expenses_by_code.items()
    ]

    return {
        "revenue_items": revenue_items,
        "cogs_items": cogs_items,
        "ga_expenses": ga_expenses,
        "sga_breakdown": {k: round(v, 2) for k, v in sga_breakdown.items()},
        "finance": {k: round(v, 2) for k, v in finance_items.items()},
        "da": round(da_total, 2),
        "tax": round(tax_total, 2),
        "unclassified": unclassified[:20],  # Limit to top 20
        "stats": stats,
    }


def _infer_revenue_category(segment_key: str) -> Dict:
    """Map a semantic segment key to known revenue categories."""
    sk = segment_key.lower()
    if "retail" in sk:
        return {"segment": "Revenue Retail", "category": "Other Revenue"}  # Can't determine product
    if "wholesale" in sk:
        return {"segment": "Revenue Wholesale", "category": "Other Revenue"}
    return {"segment": "Other Revenue", "category": "Other Revenue"}


def _infer_cogs_category(segment_key: str) -> Dict:
    """Map a semantic segment key to known COGS categories."""
    sk = segment_key.lower()
    if "retail" in sk:
        return {"segment": "COGS Retail", "category": "Other COGS"}
    if "wholesale" in sk:
        return {"segment": "COGS Wholesale", "category": "Other COGS"}
    return {"segment": "Other COGS", "category": "Other COGS"}


# ═══════════════════════════════════════════════════════════════════════════════
# 6. HISTORICAL PATTERN LEARNER
# ═══════════════════════════════════════════════════════════════════════════════

class PatternStore:
    """
    In-memory store for learned patterns from full-report uploads.
    Persists counterparty → category associations.
    """
    def __init__(self):
        self._counterparty_map: Dict[str, Dict] = {}  # cp_name → {category, count, confidence}
        self._dept_map: Dict[str, str] = {}            # dept → segment
        self._cost_class_map: Dict[str, str] = {}      # cost_class → pl_line

    def learn_from_full_report(
        self,
        transactions: list,
        revenue_items: list,
        cogs_items: list,
    ):
        """
        Learn counterparty/dept/cost_class patterns from a full report
        where we have ground truth from Revenue/COGS breakdown sheets.
        """
        # Build a set of known revenue and COGS amounts to match against txns
        rev_total = sum(float(r.get("net", 0)) for r in revenue_items)
        cogs_total = sum(float(c.get("total_cogs", 0)) for c in cogs_items)

        for txn in transactions:
            cp = str(txn.get("counterparty", "")).strip().lower()
            dept = str(txn.get("dept", "")).strip().lower()
            cost_class = str(txn.get("cost_class", "")).strip().lower()
            txn_type = str(txn.get("type", "")).strip()

            if cp and cp not in ("0", "???", "-", "n/a"):
                if cp not in self._counterparty_map:
                    self._counterparty_map[cp] = {"category": txn_type, "count": 0, "confidence": 0.5}
                self._counterparty_map[cp]["count"] += 1
                # Higher confidence with more observations
                self._counterparty_map[cp]["confidence"] = min(
                    0.9, 0.5 + 0.1 * self._counterparty_map[cp]["count"]
                )

            if dept and dept not in ("0", "???", "-", "n/a"):
                segment = classify_department(dept)
                if segment:
                    self._dept_map[dept] = segment

            if cost_class and cost_class not in ("0", "???", "-", "n/a"):
                cc_result = classify_cost_class(cost_class)
                if cc_result:
                    self._cost_class_map[cost_class] = cc_result["pl_line"]

        learned = len(self._counterparty_map)
        logger.info(f"Semantic layer learned {learned} counterparty patterns from full report")

    def get_counterparty_class(self, cp: str) -> Optional[Dict]:
        """Look up a learned counterparty classification."""
        return self._counterparty_map.get(cp.lower().strip())

    def get_dept_segment(self, dept: str) -> Optional[str]:
        return self._dept_map.get(dept.lower().strip())

    def get_stats(self) -> Dict:
        return {
            "counterparties_learned": len(self._counterparty_map),
            "departments_mapped": len(self._dept_map),
            "cost_classes_mapped": len(self._cost_class_map),
        }


# Global pattern store (persists across requests within the same process)
_pattern_store = PatternStore()


def get_pattern_store() -> PatternStore:
    """Get the global pattern store instance."""
    return _pattern_store


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SEMANTIC ANALYSIS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_transactions_semantic(transactions: list) -> Dict:
    """
    Run full semantic analysis on a set of transactions.
    Returns a comprehensive report of how transactions are classified.

    Used by the analytics endpoint to provide visibility into the semantic layer.
    """
    classifications = []
    pl_distribution = defaultdict(float)
    segment_distribution = defaultdict(float)
    confidence_levels = {"high": 0, "medium": 0, "low": 0, "none": 0}
    signal_usage = defaultdict(int)

    for txn in transactions:
        amt = abs(float(txn.get("amount", 0)))
        if amt == 0:
            continue

        sem = classify_transaction_semantic(txn)

        # Track distributions
        pl_distribution[sem.pl_line] += amt
        segment_distribution[sem.segment] += amt

        # Track confidence levels
        if sem.confidence >= 0.8:
            confidence_levels["high"] += 1
        elif sem.confidence >= 0.5:
            confidence_levels["medium"] += 1
        elif sem.confidence > 0:
            confidence_levels["low"] += 1
        else:
            confidence_levels["none"] += 1

        # Track which signals contributed
        for source, _, _ in sem.signals:
            base_source = source.split("_")[0]
            signal_usage[base_source] += 1

    total_amount = sum(pl_distribution.values()) or 1

    return {
        "total_transactions": len(transactions),
        "pl_distribution": {
            k: {"amount": round(v, 2), "pct": round(v / total_amount * 100, 1)}
            for k, v in sorted(pl_distribution.items(), key=lambda x: -x[1])
        },
        "segment_distribution": {
            k: {"amount": round(v, 2), "pct": round(v / total_amount * 100, 1)}
            for k, v in sorted(segment_distribution.items(), key=lambda x: -x[1])
        },
        "confidence_levels": confidence_levels,
        "signal_usage": dict(signal_usage),
        "pattern_store_stats": _pattern_store.get_stats(),
    }
