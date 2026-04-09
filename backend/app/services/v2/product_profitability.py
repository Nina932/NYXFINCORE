"""
FinAI v2 Product Profitability — Single-endpoint product margin analysis.
=========================================================================
Fixes the stress test finding: "No single endpoint for product-level margin."

Joins Revenue and COGS by product to compute:
- Gross profit per product
- Margin % per product
- Contribution % to total
- Segment breakdown (wholesale vs retail)

Public API:
    from app.services.v2.product_profitability import compute_product_profitability
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.v2.decimal_utils import to_decimal, safe_divide, round_fin

D = Decimal


async def compute_product_profitability(
    dataset_id: int,
    db: AsyncSession,
    segment: Optional[str] = None,
    sort_by: str = "margin_pct",
) -> Dict[str, Any]:
    """Compute product-level profitability from Revenue and COGS items.

    Returns:
        Dict with products list, summary totals, and filters.
    """
    from app.models.all_models import RevenueItem, COGSItem

    # Load revenue by product
    rev_q = select(RevenueItem).where(RevenueItem.dataset_id == dataset_id)
    rev_result = await db.execute(rev_q)
    rev_items = rev_result.scalars().all()

    # Load COGS by product
    cogs_q = select(COGSItem).where(COGSItem.dataset_id == dataset_id)
    cogs_result = await db.execute(cogs_q)
    cogs_items = cogs_result.scalars().all()

    # Index by product name
    rev_by_product: Dict[str, Dict[str, Any]] = {}
    for r in rev_items:
        name = r.product or ""
        if name.lower() in ('итог', 'итого', 'total'):
            continue
        if name not in rev_by_product:
            rev_by_product[name] = {
                "net": D("0"), "gross": D("0"), "vat": D("0"),
                "segment": getattr(r, 'segment', '') or "", "category": getattr(r, 'category', '') or "",
                "product_en": getattr(r, 'product_en', None) or name,
            }
        rev_by_product[name]["net"] += to_decimal(r.net)
        rev_by_product[name]["gross"] += to_decimal(r.gross)
        rev_by_product[name]["vat"] += to_decimal(r.vat)

    cogs_by_product: Dict[str, Dict[str, Any]] = {}
    for c in cogs_items:
        name = c.product or ""
        if name.lower() in ('итог', 'итого', 'total'):
            continue
        if name not in cogs_by_product:
            cogs_by_product[name] = {
                "total_cogs": D("0"), "col6": D("0"),
                "col7310": D("0"), "col8230": D("0"),
                "segment": getattr(c, 'segment', '') or "", "category": getattr(c, 'category', '') or "",
            }
        cogs_by_product[name]["total_cogs"] += to_decimal(c.total_cogs)
        cogs_by_product[name]["col6"] += to_decimal(c.col6_amount)
        cogs_by_product[name]["col7310"] += to_decimal(c.col7310_amount)
        cogs_by_product[name]["col8230"] += to_decimal(c.col8230_amount)

    # Compute profitability
    all_products = set(rev_by_product.keys()) | set(cogs_by_product.keys())
    products = []

    for product in all_products:
        rev = rev_by_product.get(product, {})
        cogs = cogs_by_product.get(product, {})

        rev_net = rev.get("net", D("0"))
        cogs_total = cogs.get("total_cogs", D("0"))
        gross_profit = rev_net - cogs_total
        margin_pct = safe_divide(gross_profit * D("100"), rev_net) if rev_net > 0 else D("0")

        prod_segment = rev.get("segment", cogs.get("segment", "Other"))

        # Apply segment filter
        if segment and segment.lower() not in (prod_segment or "").lower():
            continue

        products.append({
            "product": product,
            "product_en": rev.get("product_en", product),
            "segment": prod_segment,
            "revenue_net": str(round_fin(rev_net)),
            "cogs_total": str(round_fin(cogs_total)),
            "gross_profit": str(round_fin(gross_profit)),
            "margin_pct": str(round_fin(margin_pct)),
            "cogs_breakdown": {
                "col6_material": str(round_fin(cogs.get("col6", D("0")))),
                "col7310_selling": str(round_fin(cogs.get("col7310", D("0")))),
                "col8230_other": str(round_fin(cogs.get("col8230", D("0")))),
            },
        })

    # Sort
    sort_keys = {
        "margin_pct": lambda x: to_decimal(x["margin_pct"]),
        "revenue": lambda x: -to_decimal(x["revenue_net"]),
        "cogs": lambda x: -to_decimal(x["cogs_total"]),
        "gp": lambda x: -to_decimal(x["gross_profit"]),
    }
    sort_fn = sort_keys.get(sort_by, sort_keys["margin_pct"])
    products.sort(key=sort_fn, reverse=(sort_by == "margin_pct"))

    # Summary
    total_rev = sum(to_decimal(p["revenue_net"]) for p in products)
    total_cogs = sum(to_decimal(p["cogs_total"]) for p in products)
    total_gp = sum(to_decimal(p["gross_profit"]) for p in products)
    avg_margin = safe_divide(total_gp * D("100"), total_rev) if total_rev > 0 else D("0")

    # Contribution %
    for p in products:
        p["contribution_pct"] = str(round_fin(
            safe_divide(to_decimal(p["gross_profit"]) * D("100"), total_gp) if total_gp != 0 else D("0")
        ))

    return {
        "products": products,
        "summary": {
            "total_revenue": str(round_fin(total_rev)),
            "total_cogs": str(round_fin(total_cogs)),
            "total_gross_profit": str(round_fin(total_gp)),
            "avg_margin_pct": str(round_fin(avg_margin)),
            "product_count": len(products),
        },
        "filters_applied": {"segment": segment, "sort_by": sort_by},
    }
