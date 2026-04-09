"""
NYX Core Thinker P&L Classification Engine
=============================================
Implements the exact business rules for building NYX Core Thinker's
Profit & Loss statement from Revenue Breakdown, COGS Breakdown, and Base sheets.

Rules encoded from the official NYX Core Thinker P&L specification:
- Revenue = Revenue Wholesale + Revenue Retail + Other Revenue
- COGS mirrors Revenue structure (same product-level breakdown)
- Gross Margin = Revenue - COGS (per product, per category)
- G&A from Base sheet (accounts 73XX, 74XX, 82XX, 92XX)
- EBITDA = Total Gross Profit - G&A

All computation is deterministic (Decimal). No LLM involved.
"""

import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# PRODUCT CLASSIFICATION RULES
# ═══════════════════════════════════════════════════════════════

# Revenue product → P&L line mapping
# Key: substring match in Georgian product name (lowercase)
# Value: (category, subcategory)

REVENUE_PRODUCT_MAP = {
    # WHOLESALE PETROL
    "ევრო რეგულარი (იმპორტი)": ("Revenue Wholesale", "Revenue Whsale Petrol (Lari)"),
    "ევრო რეგულარი (საბითუმო)": ("Revenue Wholesale", "Revenue Whsale Petrol (Lari)"),
    "პრემიუმი (რეექსპორტი)": ("Revenue Wholesale", "Revenue Whsale Petrol (Lari)"),
    "სუპერი (რეექსპორტი)": ("Revenue Wholesale", "Revenue Whsale Petrol (Lari)"),
    # WHOLESALE DIESEL
    "დიზელი (საბითუმო)": ("Revenue Wholesale", "Revenue Whsale Diesel (Lari)"),
    "ევროდიზელი (ექსპორტი)": ("Revenue Wholesale", "Revenue Whsale Diesel (Lari)"),
    "ევრო დიზელი (ექსპორტი)": ("Revenue Wholesale", "Revenue Whsale Diesel (Lari)"),
    # WHOLESALE BITUMEN
    "ბიტუმი (საბითუმო)": ("Revenue Wholesale", "Revenue Whsale Bitumen (Lari)"),
    # WHOLESALE CNG
    "ბუნებრივი აირი (საბითუმო)": ("Revenue Wholesale", "Revenue Whsale CNG (Lari)"),
    # WHOLESALE LPG
    "თხევადი აირი (საბითუმო)": ("Revenue Wholesale", "Revenue Whsale LPG (Lari)"),

    # RETAIL PETROL
    "ევრო რეგულარი, ლ": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    "ევრო რეგულარი,": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    "პრემიუმი , ლ": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    "პრემიუმი, ლ": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    "პრემიუმი ,": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    "სუპერი , ლ": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    "სუპერი, ლ": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    "სუპერი ,": ("Revenue Retail", "Revenue Retial Petrol (Lari)"),
    # RETAIL DIESEL
    "დიზელი, ლ": ("Revenue Retail", "Revenue Retial Diesel (Lari)"),
    "დიზელი,": ("Revenue Retail", "Revenue Retial Diesel (Lari)"),
    "ევრო დიზელი, ლ": ("Revenue Retail", "Revenue Retial Diesel (Lari)"),
    "ევრო დიზელი,": ("Revenue Retail", "Revenue Retial Diesel (Lari)"),
    # RETAIL CNG
    "ბუნებრივი აირი, მ3": ("Revenue Retail", "Revenue Retial CNG (Lari)"),
    "ბუნებრივი აირი,": ("Revenue Retail", "Revenue Retial CNG (Lari)"),
    # RETAIL LPG
    "თხევადი აირი (მხოლოდ SGP": ("Revenue Retail", "Revenue Retial LPG (Lari)"),
    "თხევადი აირი (მხოლოდ": ("Revenue Retail", "Revenue Retial LPG (Lari)"),
}

# COGS product mapping (same structure as Revenue)
COGS_PRODUCT_MAP = {
    # WHOLESALE PETROL
    "ევრო რეგულარი (იმპორტი)": ("COGS Wholesale", "COGS Whsale Petrol (Lari)"),
    "ევრო რეგულარი (საბითუმო)": ("COGS Wholesale", "COGS Whsale Petrol (Lari)"),
    "პრემიუმი (რეექსპორტი)": ("COGS Wholesale", "COGS Whsale Petrol (Lari)"),
    "სუპერი (რეექსპორტი)": ("COGS Wholesale", "COGS Whsale Petrol (Lari)"),
    # WHOLESALE DIESEL
    "დიზელი (საბითუმო)": ("COGS Wholesale", "COGS Whsale Diesel (Lari)"),
    "ევროდიზელი (ექსპორტი)": ("COGS Wholesale", "COGS Whsale Diesel (Lari)"),
    "დიზელი ნულოვანი (საბითუმო)": ("COGS Wholesale", "COGS Whsale Diesel (Lari)"),
    # WHOLESALE BITUMEN
    "ბიტუმი (საბითუმო)": ("COGS Wholesale", "COGS Whsale Bitumen (Lari)"),
    "ბიტუმი (იმპორტი)": ("COGS Wholesale", "COGS Whsale Bitumen (Lari)"),
    # WHOLESALE CNG
    "ბუნებრივი აირი (საბითუმო)": ("COGS Wholesale", "COGS Whsale CNG (Lari)"),
    # WHOLESALE LPG
    "თხევადი აირი (საბითუმო)": ("COGS Wholesale", "COGS Whsale LPG (Lari)"),

    # RETAIL PETROL
    "ევრო რეგულარი": ("COGS Retail", "COGS Retial Petrol (Lari)"),
    "პრემიუმი": ("COGS Retail", "COGS Retial Petrol (Lari)"),
    "სუპერი": ("COGS Retail", "COGS Retial Petrol (Lari)"),
    # RETAIL DIESEL
    "დიზელი": ("COGS Retail", "COGS Retial Diesel (Lari)"),
    "ევრო დიზელი": ("COGS Retail", "COGS Retial Diesel (Lari)"),
    "დიზელი (იმპორტი)": ("COGS Retail", "COGS Retial Diesel (Lari)"),
    # RETAIL CNG
    "ბუნებრივი აირი": ("COGS Retail", "COGS Retial CNG (Lari)"),
    # RETAIL LPG
    "თხევადი აირი": ("COGS Retail", "COGS Retial LPG (Lari)"),
}

# G&A account codes from Base sheet
GA_ACCOUNT_CODES = ["7310.02.1", "7410", "7410.01", "8220.01.1", "9210"]


# ═══════════════════════════════════════════════════════════════
# P&L BUILDER
# ═══════════════════════════════════════════════════════════════

class NyxPLEngine:
    """Builds a structured P&L from NYX Core Thinker's specific file format."""

    def classify_revenue_product(self, product_name: str) -> Tuple[str, str]:
        """Classify a product from Revenue Breakdown into P&L line."""
        name = product_name.strip()

        # Try exact prefix matching (longest match first)
        for pattern, (category, subcategory) in sorted(
            REVENUE_PRODUCT_MAP.items(), key=lambda x: -len(x[0])
        ):
            if name.startswith(pattern) or pattern in name:
                return category, subcategory

        # Fallback: check if it contains wholesale indicators
        name_lower = name.lower()
        if "(საბითუმო)" in name or "(იმპორტი)" in name or "(რეექსპორტი)" in name or "(ექსპორტი)" in name:
            return "Revenue Wholesale", "Revenue Wholesale Other"

        # Default: Other Revenue
        return "Other Revenue", "Other Revenue"

    def classify_cogs_product(self, product_name: str) -> Tuple[str, str]:
        """Classify a product from COGS Breakdown into P&L line."""
        name = product_name.strip()

        # Try exact prefix matching (longest match first for wholesale)
        for pattern, (category, subcategory) in sorted(
            COGS_PRODUCT_MAP.items(), key=lambda x: -len(x[0])
        ):
            if name.startswith(pattern) or pattern in name:
                return category, subcategory

        # Fallback: Other COGS
        return "Other COGS", "Other COGS"

    def build_pl(
        self,
        revenue_breakdown: List[Dict],
        cogs_breakdown: List[Dict],
        base_transactions: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Build the full NYX Core Thinker P&L from Revenue Breakdown, COGS Breakdown, and Base sheets.

        Returns structured dict with all line items, subtotals, and totals.
        """
        pl = {
            "revenue": {},
            "cogs": {},
            "gross_margin": {},
            "ga_expenses": Decimal("0"),
            "ebitda": Decimal("0"),
            "line_items": [],
        }

        # ── 1. Revenue classification ──────────────────────────────
        rev_by_line = {}
        rev_products = {}  # Store individual products per line

        for item in revenue_breakdown:
            product = item.get("product", "")
            net_rev = Decimal(str(item.get("net_revenue", 0)))
            if not product or net_rev == 0:
                continue

            # Skip total rows
            if any(t in product.lower() for t in ["итог", "total", "სულ", "ჯამ"]):
                continue

            category, subcategory = self.classify_revenue_product(product)
            rev_by_line.setdefault(category, {})
            rev_by_line[category].setdefault(subcategory, Decimal("0"))
            rev_by_line[category][subcategory] += net_rev

            rev_products.setdefault(subcategory, [])
            rev_products[subcategory].append({"product": product, "amount": float(net_rev)})

        pl["revenue"] = {
            cat: {sub: float(amt) for sub, amt in subs.items()}
            for cat, subs in rev_by_line.items()
        }
        pl["revenue_products"] = {k: v for k, v in rev_products.items()}

        # Revenue totals
        rev_wholesale = sum(
            sum(v for v in subs.values())
            for cat, subs in rev_by_line.items() if cat == "Revenue Wholesale"
        )
        rev_retail = sum(
            sum(v for v in subs.values())
            for cat, subs in rev_by_line.items() if cat == "Revenue Retail"
        )
        rev_other = sum(
            sum(v for v in subs.values())
            for cat, subs in rev_by_line.items() if cat == "Other Revenue"
        )
        total_revenue = rev_wholesale + rev_retail + rev_other

        pl["revenue_totals"] = {
            "Revenue Wholesale": float(rev_wholesale),
            "Revenue Retail": float(rev_retail),
            "Other Revenue": float(rev_other),
            "Total Revenue": float(total_revenue),
        }

        # ── 2. COGS classification ──────────────────────────────────
        cogs_by_line = {}
        cogs_products = {}

        for item in cogs_breakdown:
            product = item.get("product", "")
            # COGS amount = sum of columns K(6), L(7310), O(8230)
            amount = Decimal(str(item.get("amount", 0)))
            # If individual columns are available, use their sum
            col_6 = Decimal(str(item.get("col_6", 0)))
            col_7310 = Decimal(str(item.get("col_7310", 0)))
            col_8230 = Decimal(str(item.get("col_8230", 0)))
            if col_6 + col_7310 + col_8230 > 0:
                amount = col_6 + col_7310 + col_8230

            if not product or amount == 0:
                continue
            if any(t in product.lower() for t in ["итог", "total", "სულ", "ჯამ"]):
                continue

            category, subcategory = self.classify_cogs_product(product)
            cogs_by_line.setdefault(category, {})
            cogs_by_line[category].setdefault(subcategory, Decimal("0"))
            cogs_by_line[category][subcategory] += amount

            cogs_products.setdefault(subcategory, [])
            cogs_products[subcategory].append({"product": product, "amount": float(amount)})

        pl["cogs"] = {
            cat: {sub: float(amt) for sub, amt in subs.items()}
            for cat, subs in cogs_by_line.items()
        }
        pl["cogs_products"] = {k: v for k, v in cogs_products.items()}

        cogs_wholesale = sum(
            sum(v for v in subs.values())
            for cat, subs in cogs_by_line.items() if cat == "COGS Wholesale"
        )
        cogs_retail = sum(
            sum(v for v in subs.values())
            for cat, subs in cogs_by_line.items() if cat == "COGS Retail"
        )
        cogs_other = sum(
            sum(v for v in subs.values())
            for cat, subs in cogs_by_line.items() if cat == "Other COGS"
        )
        total_cogs = cogs_wholesale + cogs_retail + cogs_other

        pl["cogs_totals"] = {
            "COGS Wholesale": float(cogs_wholesale),
            "COGS Retail": float(cogs_retail),
            "Other COGS": float(cogs_other),
            "Total COGS": float(total_cogs),
        }

        # ── 3. Gross Margin (Revenue - COGS per line) ──────────────
        # Build matching lines
        all_subcategories = set()
        for cat_subs in rev_by_line.values():
            all_subcategories.update(cat_subs.keys())

        margin_lines = {}
        # Wholesale margins
        for rev_sub in ["Revenue Whsale Petrol (Lari)", "Revenue Whsale Diesel (Lari)",
                         "Revenue Whsale Bitumen (Lari)", "Revenue Whsale CNG (Lari)", "Revenue Whsale LPG (Lari)"]:
            cogs_sub = rev_sub.replace("Revenue", "COGS")
            rev_amt = Decimal(str(rev_by_line.get("Revenue Wholesale", {}).get(rev_sub, 0)))
            cogs_amt = Decimal(str(cogs_by_line.get("COGS Wholesale", {}).get(cogs_sub, 0)))
            margin_sub = rev_sub.replace("Revenue", "Gr. Margin")
            margin_lines[margin_sub] = float(rev_amt - cogs_amt)

        # Retail margins
        for rev_sub in ["Revenue Retial Petrol (Lari)", "Revenue Retial Diesel (Lari)",
                         "Revenue Retial CNG (Lari)", "Revenue Retial LPG (Lari)"]:
            cogs_sub = rev_sub.replace("Revenue", "COGS")
            rev_amt = Decimal(str(rev_by_line.get("Revenue Retail", {}).get(rev_sub, 0)))
            cogs_amt = Decimal(str(cogs_by_line.get("COGS Retail", {}).get(cogs_sub, 0)))
            margin_sub = rev_sub.replace("Revenue", "Gr. Margin")
            margin_lines[margin_sub] = float(rev_amt - cogs_amt)

        pl["gross_margin"] = margin_lines
        pl["gross_margin_totals"] = {
            "Gr. Margin Wholesale": float(rev_wholesale - cogs_wholesale),
            "Gr. Margin Retail": float(rev_retail - cogs_retail),
            "Total Gross Profit": float(total_revenue - total_cogs),
        }

        # ── 4. G&A from Base transactions ──────────────────────────
        ga_total = Decimal("0")
        ga_by_account = {}

        if base_transactions:
            for txn in base_transactions:
                acct_dr = str(txn.get("account_dr", "")).strip()
                amount = Decimal(str(txn.get("amount", 0)))

                # Check if account matches G&A codes
                for ga_code in GA_ACCOUNT_CODES:
                    if acct_dr.startswith(ga_code):
                        ga_total += amount
                        ga_by_account.setdefault(ga_code, Decimal("0"))
                        ga_by_account[ga_code] += amount
                        break

        pl["ga_expenses"] = float(ga_total)
        pl["ga_by_account"] = {k: float(v) for k, v in ga_by_account.items()}

        # ── 5. EBITDA ──────────────────────────────────────────────
        total_gp = total_revenue - total_cogs + rev_other
        pl["ebitda"] = float(total_gp - ga_total)

        # ── 6. Summary ────────────────────────────────────────────
        pl["summary"] = {
            "total_revenue": float(total_revenue),
            "total_cogs": float(total_cogs),
            "total_gross_profit": float(total_revenue - total_cogs),
            "gross_margin_pct": float((total_revenue - total_cogs) / total_revenue * 100) if total_revenue else 0,
            "other_revenue": float(rev_other),
            "total_gross_profit_with_other": float(total_gp),
            "ga_expenses": float(ga_total),
            "ebitda": float(total_gp - ga_total),
            "revenue_wholesale": float(rev_wholesale),
            "revenue_retail": float(rev_retail),
            "cogs_wholesale": float(cogs_wholesale),
            "cogs_retail": float(cogs_retail),
        }

        # ── 7. Build ordered line items for UI rendering ───────────
        line_items = []

        # Revenue section
        line_items.append({"code": "REV", "label": "REVENUE", "amount": float(total_revenue), "type": "header", "level": 0})

        # Revenue Wholesale
        line_items.append({"code": "REV.W", "label": "Revenue Wholesale", "amount": float(rev_wholesale), "type": "subtotal", "level": 1})
        for sub in ["Revenue Whsale Petrol (Lari)", "Revenue Whsale Diesel (Lari)",
                     "Revenue Whsale Bitumen (Lari)", "Revenue Whsale CNG (Lari)", "Revenue Whsale LPG (Lari)"]:
            amt = float(rev_by_line.get("Revenue Wholesale", {}).get(sub, 0))
            if amt != 0:
                line_items.append({"code": "", "label": sub, "amount": amt, "type": "detail", "level": 2})

        # Revenue Retail
        line_items.append({"code": "REV.R", "label": "Revenue Retail", "amount": float(rev_retail), "type": "subtotal", "level": 1})
        for sub in ["Revenue Retial Petrol (Lari)", "Revenue Retial Diesel (Lari)",
                     "Revenue Retial CNG (Lari)", "Revenue Retial LPG (Lari)"]:
            amt = float(rev_by_line.get("Revenue Retail", {}).get(sub, 0))
            if amt != 0:
                line_items.append({"code": "", "label": sub, "amount": amt, "type": "detail", "level": 2})

        # Other Revenue
        if rev_other > 0:
            line_items.append({"code": "OR", "label": "Other Revenue", "amount": float(rev_other), "type": "subtotal", "level": 1})

        # Total Revenue
        line_items.append({"code": "", "label": "Total Revenue", "amount": float(total_revenue), "type": "total", "level": 0})

        # COGS section
        line_items.append({"code": "COGS", "label": "COST OF GOODS SOLD", "amount": -float(total_cogs), "type": "header", "level": 0})

        # COGS Wholesale
        line_items.append({"code": "COGS.W", "label": "COGS Wholesale", "amount": -float(cogs_wholesale), "type": "subtotal", "level": 1})
        for sub in ["COGS Whsale Petrol (Lari)", "COGS Whsale Diesel (Lari)",
                     "COGS Whsale Bitumen (Lari)", "COGS Whsale CNG (Lari)", "COGS Whsale LPG (Lari)"]:
            amt = float(cogs_by_line.get("COGS Wholesale", {}).get(sub, 0))
            if amt != 0:
                line_items.append({"code": "", "label": sub, "amount": -amt, "type": "detail", "level": 2})

        # COGS Retail
        line_items.append({"code": "COGS.R", "label": "COGS Retail", "amount": -float(cogs_retail), "type": "subtotal", "level": 1})
        for sub in ["COGS Retial Petrol (Lari)", "COGS Retial Diesel (Lari)",
                     "COGS Retial CNG (Lari)", "COGS Retial LPG (Lari)"]:
            amt = float(cogs_by_line.get("COGS Retail", {}).get(sub, 0))
            if amt != 0:
                line_items.append({"code": "", "label": sub, "amount": -amt, "type": "detail", "level": 2})

        # Other COGS
        if cogs_other > 0:
            line_items.append({"code": "COGS.O", "label": "Other COGS", "amount": -float(cogs_other), "type": "subtotal", "level": 1})

        # Gross Margin section
        line_items.append({"code": "GM", "label": "GROSS MARGIN", "amount": float(total_revenue - total_cogs), "type": "header", "level": 0})

        # GM Wholesale
        gm_wholesale = float(rev_wholesale - cogs_wholesale)
        line_items.append({"code": "GM.W", "label": "Gr. Margin Wholesale", "amount": gm_wholesale, "type": "subtotal", "level": 1})
        for sub_key, sub_label in [("Petrol", "Gr. Margin Whsale Petrol (Lari)"),
                                     ("Diesel", "Gr. Margin Whsale Diesel (Lari)"),
                                     ("Bitumen", "Gr. Margin Whsale Bitumen (Lari)")]:
            amt = margin_lines.get(sub_label, 0)
            if amt != 0:
                line_items.append({"code": "", "label": sub_label, "amount": amt, "type": "detail", "level": 2})

        # GM Retail
        gm_retail = float(rev_retail - cogs_retail)
        line_items.append({"code": "GM.R", "label": "Gr. Margin Retail", "amount": gm_retail, "type": "subtotal", "level": 1})
        for sub_key, sub_label in [("Petrol", "Gr. Margin Retial Petrol (Lari)"),
                                     ("Diesel", "Gr. Margin Retial Diesel (Lari)"),
                                     ("CNG", "Gr. Margin Retial CNG (Lari)"),
                                     ("LPG", "Gr. Margin Retial LPG (Lari)")]:
            amt = margin_lines.get(sub_label, 0)
            if amt != 0:
                line_items.append({"code": "", "label": sub_label, "amount": amt, "type": "detail", "level": 2})

        # Other Revenue (added after GM)
        if rev_other > 0:
            line_items.append({"code": "OR", "label": "Other Revenue", "amount": float(rev_other), "type": "subtotal", "level": 1})

        # Total Gross Profit
        line_items.append({"code": "TGP", "label": "Total Gross Profit", "amount": float(total_gp), "type": "total", "level": 0})

        # G&A
        if ga_total > 0:
            line_items.append({"code": "GA", "label": "General and Administrative Expenses", "amount": -float(ga_total), "type": "header", "level": 0})

        # EBITDA
        line_items.append({"code": "EBITDA", "label": "EBITDA", "amount": float(total_gp - ga_total), "type": "total", "level": 0})

        pl["line_items"] = line_items

        logger.info("NYX P&L built: Rev=%.0f (W:%.0f R:%.0f O:%.0f), COGS=%.0f, GM=%.0f (%.1f%%), GA=%.0f, EBITDA=%.0f",
                     float(total_revenue), float(rev_wholesale), float(rev_retail), float(rev_other),
                     float(total_cogs), float(total_revenue - total_cogs),
                     float((total_revenue - total_cogs) / total_revenue * 100) if total_revenue else 0,
                     float(ga_total), float(total_gp - ga_total))

        return pl


# Singleton
nyx_pl_engine = NyxPLEngine()
