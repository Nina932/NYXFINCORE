"""
MR Mapping Service — Financial Knowledge Layer

This module provides the semantic mapping between:
  1. Georgian Chart of Accounts (COA) account codes
  2. IFRS MAPPING GRP categories (Cash & Equivalents, Trade Receivables, etc.)
  3. NYX Core Thinker Baku MR Report line codes (10.B.03.01, 02.A, etc.)

The mapping flows:
  COA Account Code → (prefix match) → Baku MR Code + IFRS Line
  Trial Balance inherits mapping from COA

This replaces hardcoded pattern matching with database-driven mappings,
enabling the FinAI Agent to correctly orchestrate any financial reporting logic.
"""

import re
import logging
from typing import Optional
from app.services.mr_template import BAKU_BS_TEMPLATE, BAKU_PL_TEMPLATE

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# Build Reverse Mapping: Account Prefix → Baku MR Code
# ════════════════════════════════════════════════════════════════

def _extract_account_prefixes(template: list, statement: str) -> dict[str, dict]:
    """
    Walk a Baku template and extract account prefix → MR code mappings.

    Returns dict: {
        "1610": {"mr_code": "10.B.01.01.02", "mr_line": "Products held for resale", "statement": "BS"},
        "2110": {"mr_code": "10.A.01.01", "mr_line": "PPE: cost", "statement": "BS"},
        ...
    }

    Pattern handling:
      "1610"  → exact prefix "1610"
      "1610*" → prefix "1610" (wildcard stripped)
      "16XX"  → prefix "16"
      "141X"  → prefix "141"
    """
    result: dict[str, dict] = {}

    for tmpl in template:
        mr_code = tmpl.get("code", "")
        mr_line = tmpl.get("line", "")
        accounts = tmpl.get("accounts", [])

        for pattern in accounts:
            pattern = pattern.strip()
            if not pattern:
                continue

            # Clean pattern to extract the base prefix
            if pattern.endswith("XX"):
                prefix = pattern[:-2]
            elif pattern.endswith("X"):
                prefix = pattern[:-1]
            elif pattern.endswith("*"):
                prefix = pattern[:-1]
            else:
                prefix = pattern

            if prefix:
                result[prefix] = {
                    "mr_code": mr_code,
                    "mr_line": mr_line,
                    "statement": statement,
                    "sign": tmpl.get("sign", "+"),
                    "side": tmpl.get("side", "dr" if statement == "BS" else "dr"),
                }

    return result


def build_full_mr_mapping() -> dict[str, dict]:
    """
    Build the complete COA prefix → MR code mapping from both BS and PL templates.

    Returns a dict keyed by account prefix (most specific first when resolving).
    Example:
        {
            "1610": {"mr_code": "10.B.01.01.02", "mr_line": "Products held for resale", "statement": "BS"},
            "2110": {"mr_code": "10.A.01.01", "mr_line": "PPE: cost", "statement": "BS"},
            "6110": {"mr_code": "01.A", "mr_line": "Revenue from sale of products", "statement": "PL"},
            ...
        }
    """
    mapping = {}
    mapping.update(_extract_account_prefixes(BAKU_BS_TEMPLATE, "BS"))
    mapping.update(_extract_account_prefixes(BAKU_PL_TEMPLATE, "PL"))
    logger.info(f"Built MR mapping with {len(mapping)} account prefix entries")
    return mapping


def resolve_mr_code_for_account(account_code: str, prefix_mapping: dict[str, dict]) -> Optional[dict]:
    """
    Resolve a specific account code to its Baku MR code using longest-prefix matching.

    Args:
        account_code: Georgian COA account code (e.g., "1610.01", "2110", "7110.02.1")
        prefix_mapping: Output of build_full_mr_mapping()

    Returns:
        Dict with mr_code, mr_line, statement, or None if no match.

    Algorithm:
        1. Clean code to digits only
        2. Try longest prefix first (most specific match)
        3. Progressively shorten until a match is found
        4. Also handles dotted/slashed sub-accounts
    """
    if not account_code:
        return None

    raw = str(account_code).strip()
    clean = re.sub(r'[^0-9]', '', raw)

    if not clean:
        return None

    # Try longest prefix first
    for length in range(len(clean), 0, -1):
        prefix = clean[:length]
        if prefix in prefix_mapping:
            return {**prefix_mapping[prefix], "matched_prefix": prefix}

    # Handle dotted sub-accounts: "7110.01.1" → try "711001", "71100", "7110", etc.
    parts = re.split(r'[./]', raw)
    if len(parts) > 1:
        for num_parts in range(len(parts), 0, -1):
            joined = ''.join(re.sub(r'[^0-9]', '', p) for p in parts[:num_parts])
            for length in range(len(joined), 0, -1):
                prefix = joined[:length]
                if prefix in prefix_mapping:
                    return {**prefix_mapping[prefix], "matched_prefix": prefix}

    return None


# ════════════════════════════════════════════════════════════════
# IFRS Classification Knowledge
# ════════════════════════════════════════════════════════════════

# Account class → IFRS statement + side (financial knowledge)
ACCOUNT_CLASS_KNOWLEDGE = {
    "1": {"statement": "BS", "side": "asset",     "sub": "current",    "ifrs_group": "Current Assets"},
    "2": {"statement": "BS", "side": "asset",     "sub": "noncurrent", "ifrs_group": "Non-current Assets"},
    "3": {"statement": "BS", "side": "liability", "sub": "current",    "ifrs_group": "Current Liabilities"},
    "4": {"statement": "BS", "side": "liability", "sub": "noncurrent", "ifrs_group": "Non-current Liabilities"},
    "5": {"statement": "BS", "side": "equity",    "sub": "equity",     "ifrs_group": "Equity"},
    "6": {"statement": "PL", "side": "income",    "sub": None,         "ifrs_group": "Revenue"},
    "7": {"statement": "PL", "side": "expense",   "sub": None,         "ifrs_group": "Expenses"},
    "8": {"statement": "PL", "side": "mixed",     "sub": None,         "ifrs_group": "Other Income/Expense"},
    "9": {"statement": "PL", "side": "mixed",     "sub": None,         "ifrs_group": "Other P&L"},
}


def get_account_financial_context(account_code: str) -> dict:
    """
    Get financial context for an account based on its class digit.

    Returns: {statement, side, sub, ifrs_group}
    This embedded financial knowledge allows the system to understand
    any account's role without hardcoded sheet names.
    """
    if not account_code:
        return {}
    first_digit = re.sub(r'[^0-9]', '', str(account_code).strip())[:1]
    return ACCOUNT_CLASS_KNOWLEDGE.get(first_digit, {})


# ════════════════════════════════════════════════════════════════
# Database Seed: Populate COA Master with MR Mappings
# ════════════════════════════════════════════════════════════════

async def seed_coa_mr_mappings(db) -> dict:
    """
    Populate baku_mr_code, baku_mr_line, baku_mr_statement on all COAMasterAccount rows
    using the template-derived prefix mapping.

    This bridges the gap between:
      - Hardcoded template patterns in mr_template.py
      - Database-driven COA records in coa_master_accounts

    Returns: {"total": N, "mapped": M, "unmapped": K}
    """
    from sqlalchemy import select, update
    from app.models.all_models import COAMasterAccount

    prefix_mapping = build_full_mr_mapping()

    # Fetch all COA accounts
    result = await db.execute(select(COAMasterAccount))
    accounts = result.scalars().all()

    mapped_count = 0
    unmapped_codes = []

    for acct in accounts:
        code = acct.account_code or ""
        resolved = resolve_mr_code_for_account(code, prefix_mapping)

        if resolved:
            acct.baku_mr_code = resolved["mr_code"]
            acct.baku_mr_line = resolved["mr_line"]
            acct.baku_mr_statement = resolved["statement"]
            mapped_count += 1
        else:
            # Still set the statement based on account class knowledge
            ctx = get_account_financial_context(code)
            if ctx:
                acct.baku_mr_statement = ctx.get("statement")
            unmapped_codes.append(code)

    await db.flush()

    result_info = {
        "total": len(accounts),
        "mapped": mapped_count,
        "unmapped": len(unmapped_codes),
        "unmapped_codes": unmapped_codes[:20],  # First 20 for debugging
    }
    logger.info(f"COA MR mapping seed: {result_info['mapped']}/{result_info['total']} mapped")
    return result_info


# ════════════════════════════════════════════════════════════════
# Populate TB items with MR mappings from COA
# ════════════════════════════════════════════════════════════════

async def populate_tb_mr_mappings(db, dataset_id: int) -> dict:
    """
    Set mr_mapping, mr_mapping_line, and ifrs_line_item on all TrialBalanceItem rows
    for a given dataset, using:
      1. COAMasterAccount.baku_mr_code (if seeded)
      2. Fallback: direct prefix matching from template

    This ensures every TB line knows which MR report line it feeds into.

    Returns: {"total": N, "mapped": M}
    """
    from sqlalchemy import select
    from app.models.all_models import TrialBalanceItem, COAMasterAccount

    # Build COA lookup (code → MR info)
    coa_result = await db.execute(select(COAMasterAccount))
    coa_accounts = coa_result.scalars().all()

    coa_lookup: dict[str, dict] = {}
    for acct in coa_accounts:
        code_norm = re.sub(r'[^0-9]', '', acct.account_code or '')
        coa_lookup[code_norm] = {
            "mr_code": acct.baku_mr_code,
            "mr_line": acct.baku_mr_line,
            "statement": acct.baku_mr_statement,
            "ifrs_bs_line": acct.ifrs_bs_line,
            "ifrs_pl_line": acct.ifrs_pl_line,
        }

    # Fallback: direct template matching
    prefix_mapping = build_full_mr_mapping()

    # Fetch TB items for dataset
    tb_result = await db.execute(
        select(TrialBalanceItem).where(TrialBalanceItem.dataset_id == dataset_id)
    )
    tb_items = tb_result.scalars().all()

    mapped_count = 0
    for item in tb_items:
        code = (item.account_code or "").strip()
        if not code:
            continue

        # Clean code for COA lookup
        code_clean = re.sub(r'[^0-9]', '', code)

        # Priority 1: COA Master exact match
        coa_match = coa_lookup.get(code_clean)
        if coa_match and coa_match.get("mr_code"):
            item.mr_mapping = coa_match["mr_code"]
            item.mr_mapping_line = coa_match["mr_line"]
            item.ifrs_line_item = coa_match.get("ifrs_bs_line") or coa_match.get("ifrs_pl_line")
            mapped_count += 1
            continue

        # Priority 2: COA Master prefix match (for sub-accounts like 1610.01)
        for length in range(len(code_clean), 0, -1):
            prefix = code_clean[:length]
            coa_match = coa_lookup.get(prefix)
            if coa_match and coa_match.get("mr_code"):
                item.mr_mapping = coa_match["mr_code"]
                item.mr_mapping_line = coa_match["mr_line"]
                item.ifrs_line_item = coa_match.get("ifrs_bs_line") or coa_match.get("ifrs_pl_line")
                mapped_count += 1
                break
        else:
            # Priority 3: Direct template prefix matching (fallback)
            resolved = resolve_mr_code_for_account(code, prefix_mapping)
            if resolved:
                item.mr_mapping = resolved["mr_code"]
                item.mr_mapping_line = resolved["mr_line"]
                mapped_count += 1

    await db.flush()

    result_info = {"total": len(tb_items), "mapped": mapped_count}
    logger.info(f"TB MR mapping: {mapped_count}/{len(tb_items)} mapped for dataset {dataset_id}")
    return result_info


# ════════════════════════════════════════════════════════════════
# Generate MAPPING GRP / MAPPING BAKU Cross-Reference
# ════════════════════════════════════════════════════════════════

def build_mapping_grp_baku_reference(tb_items) -> list[dict]:
    """
    Build the MAPPING GRP → MAPPING BAKU cross-reference table.

    This is the sheet the user explicitly requested — it shows:
      Account Code | Account Name | IFRS MAPPING GRP | MAPPING BAKU (MR Code) | MR Line | Statement | Balance

    Populated from TB items that have mr_mapping set.
    """
    rows = []
    seen_codes = set()

    for item in tb_items:
        code = (item.account_code or "").strip()
        if not code or code in seen_codes:
            continue

        # Skip summary rows (ending in X)
        if code.upper().endswith("X"):
            continue

        seen_codes.add(code)

        # Calculate balance
        closing_dr = item.closing_debit or 0
        closing_cr = item.closing_credit or 0
        ctx = get_account_financial_context(code)
        if ctx.get("side") in ("liability", "equity", "income"):
            balance = closing_cr - closing_dr
        else:
            balance = closing_dr - closing_cr

        rows.append({
            "account_code": code,
            "account_name": item.account_name or "",
            "ifrs_mapping_grp": getattr(item, 'ifrs_line_item', '') or "",
            "baku_mr_code": getattr(item, 'mr_mapping', '') or "",
            "baku_mr_line": getattr(item, 'mr_mapping_line', '') or "",
            "statement": ctx.get("statement", ""),
            "side": ctx.get("side", ""),
            "closing_balance": balance,
        })

    # Sort by account code
    rows.sort(key=lambda r: r["account_code"])
    return rows
