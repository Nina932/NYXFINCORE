"""
FinAI v2 Tax Engine — Georgian tax calculation foundation.
============================================================
Fills the "Tax Engine" gap identified in SAP FI benchmark.

Georgian tax rates (2025-2026):
- VAT: 18% (standard), exempt for certain goods
- CIT: 15% on distributed profits (Estonian model)
- Excise: varies by product (fuel: GEL 0.40/liter petrol, GEL 0.30/liter diesel)
- Withholding: 5-20% depending on payment type

Public API:
    from app.services.v2.tax_engine import tax_engine
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin

logger = logging.getLogger(__name__)
D = Decimal


@dataclass
class TaxCode:
    """A tax code definition."""
    code: str
    description: str
    rate: Decimal
    tax_type: str  # vat|cit|excise|withholding
    is_deductible: bool = True
    account_code: str = ""  # GL account for tax liability


# Georgian tax codes
GEORGIAN_TAX_CODES: Dict[str, TaxCode] = {
    "V18": TaxCode("V18", "VAT Standard 18%", D("0.18"), "vat", True, "3310"),
    "V0": TaxCode("V0", "VAT Exempt", D("0"), "vat", False, ""),
    "CIT15": TaxCode("CIT15", "Corporate Income Tax 15% (distributed)", D("0.15"), "cit", False, "3320"),
    "EXC_P": TaxCode("EXC_P", "Excise - Petrol GEL 0.40/liter", D("0.40"), "excise", True, "3330"),
    "EXC_D": TaxCode("EXC_D", "Excise - Diesel GEL 0.30/liter", D("0.30"), "excise", True, "3330"),
    "WH5": TaxCode("WH5", "Withholding Tax 5%", D("0.05"), "withholding", False, "3340"),
    "WH10": TaxCode("WH10", "Withholding Tax 10%", D("0.10"), "withholding", False, "3340"),
    "WH20": TaxCode("WH20", "Withholding Tax 20%", D("0.20"), "withholding", False, "3340"),
}


class TaxEngine:
    """Georgian tax calculation engine."""

    def __init__(self):
        self._codes = dict(GEORGIAN_TAX_CODES)

    def get_tax_codes(self) -> List[Dict[str, Any]]:
        """List all available tax codes."""
        return [
            {
                "code": tc.code, "description": tc.description,
                "rate": str(tc.rate), "tax_type": tc.tax_type,
                "is_deductible": tc.is_deductible,
                "account_code": tc.account_code,
            }
            for tc in self._codes.values()
        ]

    def calculate_vat(
        self, net_amount: Any, tax_code: str = "V18"
    ) -> Dict[str, str]:
        """Calculate VAT on a net amount."""
        net = to_decimal(net_amount)
        tc = self._codes.get(tax_code)
        if not tc or tc.tax_type != "vat":
            return {"net": str(round_fin(net)), "vat": "0.00",
                    "gross": str(round_fin(net)), "error": f"Invalid VAT code: {tax_code}"}

        vat = round_fin(net * tc.rate)
        gross = net + vat
        return {
            "net": str(round_fin(net)),
            "vat": str(vat),
            "gross": str(round_fin(gross)),
            "tax_code": tax_code,
            "rate": str(tc.rate),
        }

    def extract_vat_from_gross(
        self, gross_amount: Any, tax_code: str = "V18"
    ) -> Dict[str, str]:
        """Extract VAT from a gross (VAT-inclusive) amount."""
        gross = to_decimal(gross_amount)
        tc = self._codes.get(tax_code)
        if not tc or tc.tax_type != "vat" or tc.rate == 0:
            return {"gross": str(round_fin(gross)), "vat": "0.00",
                    "net": str(round_fin(gross))}

        net = safe_divide(gross, D("1") + tc.rate)
        vat = gross - net
        return {
            "gross": str(round_fin(gross)),
            "net": str(round_fin(net)),
            "vat": str(round_fin(vat)),
            "tax_code": tax_code,
        }

    def calculate_cit(
        self, distributed_profit: Any
    ) -> Dict[str, str]:
        """Calculate Georgian CIT (15% on distributed profits — Estonian model)."""
        dist = to_decimal(distributed_profit)
        tc = self._codes["CIT15"]
        tax = round_fin(dist * tc.rate)
        return {
            "distributed_profit": str(round_fin(dist)),
            "cit_rate": str(tc.rate),
            "cit_amount": str(tax),
            "net_distribution": str(round_fin(dist - tax)),
            "note": "Georgian Estonian model: CIT only on distributed profits",
        }

    def calculate_excise(
        self, volume_liters: Any, product: str = "petrol"
    ) -> Dict[str, str]:
        """Calculate fuel excise tax."""
        vol = to_decimal(volume_liters)
        code = "EXC_P" if product.lower() in ("petrol", "gasoline", "premium", "super") else "EXC_D"
        tc = self._codes.get(code)
        if not tc:
            return {"error": f"No excise code for {product}"}

        excise = round_fin(vol * tc.rate)
        return {
            "volume_liters": str(round_fin(vol)),
            "product": product,
            "excise_rate_per_liter": str(tc.rate),
            "excise_amount": str(excise),
            "tax_code": code,
        }

    def tax_summary(
        self, revenue: Any, cogs: Any, distributed: Any = 0
    ) -> Dict[str, str]:
        """Compute summary tax obligations."""
        rev = to_decimal(revenue)
        cog = to_decimal(cogs)
        dist = to_decimal(distributed)

        output_vat = round_fin(rev * D("0.18"))
        input_vat = round_fin(cog * D("0.18"))
        vat_payable = output_vat - input_vat
        cit = round_fin(dist * D("0.15")) if dist > 0 else D("0")

        return {
            "output_vat": str(output_vat),
            "input_vat": str(input_vat),
            "vat_payable": str(round_fin(vat_payable)),
            "cit_on_distributed": str(cit),
            "total_tax_liability": str(round_fin(vat_payable + cit)),
        }


# Module singleton
tax_engine = TaxEngine()
