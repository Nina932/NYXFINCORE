"""
MR Engine — Populates Baku MR templates from FinAI data.
Takes TrialBalance / BalanceSheet / Revenue / COGS / GA items and walks the
Baku template definitions to produce populated rows with actual values.

Key innovation: Uses the Mapping sheet data (MAPING ST classification) to
intelligently categorize expenses into P&L sub-items (Wages, Depreciation,
Utilities, etc.) even when multiple expense types share the same account code.
For items classified as "Other operating expenses", Georgian/Russian keyword
matching on account names provides further sub-classification.
"""

from typing import Any
from app.services.mr_template import (
    BAKU_BS_TEMPLATE, BAKU_PL_TEMPLATE, BAKU_CFS_TEMPLATE,
    BAKU_OPEX_TEMPLATE, BAKU_PRODUCTS_WHOLESALE_TEMPLATE,
    BAKU_PRODUCTS_RETAIL_TEMPLATE, BAKU_PRODUCTS_GAS_DISTR_TEMPLATE,
    BAKU_CATEGORY_TO_PL_SUFFIX, IFRS_LINE_TO_PL_SUFFIX,
    ACCOUNT_PREFIX_TO_EXPENSE_CODE, BAKU_NONOP_TO_PL_CODE,
    DEPRECIATION_NAME_KEYWORDS,
    MAPING_ST_TO_PL_SUFFIX, MAPING_ST_NONOP,
    EXPENSE_NAME_KEYWORDS, EXPENSE_NAME_KEYWORDS_DEPRECIATION,
    INCOME_NAME_KEYWORDS, OTHER_OPEX_NAME_KEYWORDS, COGS_NAME_KEYWORDS,
)
import logging, copy, re

logger = logging.getLogger(__name__)


class MREngine:
    """
    Populate Baku MR templates from FinAI database items.

    Usage:
        engine = MREngine(tb_items, bsi_items, rev_items, cogs_items, ga_items, rate=2.7)
        bs = engine.populate_bs()     # -> list[dict] with 'actual' values
        pl = engine.populate_pl()
        ...
    """

    def __init__(self, tb_items, bsi_items=None, rev_items=None, cogs_items=None, ga_items=None,
                 mapping_rows=None, rate: float = 1.0,
                 prior_values: dict = None, budget_values: dict = None):
        self.rate = rate
        self.rev_items = rev_items or []
        self.cogs_items = cogs_items or []
        self.ga_items = ga_items or []

        # Multi-period intelligence: prior year values and budget/plan values
        self._prior_values = prior_values or {}    # {mr_code: usd_k_value} from prior year engine
        self._budget_values = budget_values or {}  # {mr_code: gel_amount} from BudgetLine records

        # Build index: account_code -> {opening_dr, opening_cr, closing_dr, closing_cr, turnover_dr, turnover_cr}
        self._account_idx: dict[str, dict] = {}
        self._build_account_index(tb_items or [])

        # Build P&L sub-item index: mr_code -> GEL turnover
        # e.g. {"02.C.01": 1577967.35, "02.B.02.01": 2685865.80}
        self._bsi_pl_idx: dict[str, float] = {}
        # Track amounts reclassified from one P&L section to another
        # (e.g., 8110 interest income moved from 03 to 09.A)
        # {source_account_prefix: {target_mr_code: amount}}
        self._nonop_adjustments: dict[str, float] = {}
        if mapping_rows:
            self._build_pl_index_from_mapping(mapping_rows)
        elif bsi_items:
            self._build_bsi_pl_index(bsi_items)

        # TB-based semantic fallback: sub-classify items that the mapping/BSI
        # couldn't break down (e.g., COGS entirely in "Other", income not classified)
        self._build_tb_semantic_fallback()

    # ════════════════════════════════════════════════════════════════
    # Account Index
    # ════════════════════════════════════════════════════════════════

    def _build_account_index(self, tb_items):
        """Index all TB items by account_code for fast lookup."""
        for item in tb_items:
            code = (item.account_code or "").strip()
            if not code:
                continue
            if code not in self._account_idx:
                self._account_idx[code] = {
                    "name": "",
                    "opening_dr": 0.0, "opening_cr": 0.0,
                    "closing_dr": 0.0, "closing_cr": 0.0,
                    "turnover_dr": 0.0, "turnover_cr": 0.0,
                }
            entry = self._account_idx[code]
            # Store account name for semantic analysis
            if not entry["name"] and item.account_name:
                entry["name"] = item.account_name.strip()
            entry["opening_dr"]  += item.opening_debit or 0.0
            entry["opening_cr"]  += item.opening_credit or 0.0
            entry["closing_dr"]  += item.closing_debit or 0.0
            entry["closing_cr"]  += item.closing_credit or 0.0
            entry["turnover_dr"] += item.turnover_debit or 0.0
            entry["turnover_cr"] += item.turnover_credit or 0.0

    def _build_pl_index_from_mapping(self, mapping_rows: list[list]):
        """
        Build P&L sub-item index from Mapping sheet data.

        The Mapping sheet has pre-classified expense lines with IFRS categories:
          Col B (idx 1) = account code (e.g. "7310.01.1/1")
          Col C (idx 2) = account name in Georgian/Russian
          Col D (idx 3) = turnover amount
          Col E (idx 4) = MAPING ST classification (e.g. "Wages, benefits and payroll taxes")

        Algorithm:
          1. For each detail row (with "/" = counterparty level):
             a. Check MAPING ST for non-operating items (FX, interest, disposals)
             b. Determine parent code from account prefix:
                - 7110 -> 02.A (COGS), 7310 -> 02.C (S&D), 7410 -> 02.B (Admin)
                - 8110 -> 03 (Other operating income), 8220 -> 02.H (Other operating expenses)
             c. Use MAPING ST for broad category (Wages -> .01, Depreciation -> .02)
             d. Use account-name keyword matching for semantic sub-classification
             e. Section-specific sub-classification:
                - Expense (02.A-D): EXPENSE_NAME_KEYWORDS + COGS_NAME_KEYWORDS
                - Income (03): INCOME_NAME_KEYWORDS -> A/B/C
                - Other opex (02.H): OTHER_OPEX_NAME_KEYWORDS -> 01/02/03/04
          2. Sum amounts by MR code

        Result: _bsi_pl_idx = {"02.C.01": 1577967.35, "03.C": 136598.52, ...}
        """
        for row in mapping_rows:
            if not row or len(row) < 5:
                continue

            acct_code = str(row[1] or "").strip()
            acct_name = str(row[2] or "").strip()
            amount_raw = row[3]
            maping_st = str(row[4] or "").strip()

            if not acct_code:
                continue
            first_char = acct_code[:1]
            if first_char not in "6789":
                continue

            # Only process detail rows (with "/" = counterparty level)
            # to avoid double-counting with parent aggregation rows
            if "/" not in acct_code:
                continue

            # Parse amount
            try:
                amount = float(amount_raw) if amount_raw else 0.0
            except (ValueError, TypeError):
                continue
            if amount == 0:
                continue

            acct_name_lower = acct_name.lower()

            # ── Check for non-operating items (FX, interest, disposals) ──
            if maping_st in MAPING_ST_NONOP:
                target = MAPING_ST_NONOP[maping_st]
                # Income items (8110/x): amounts are negative in data = credit side
                # We want income as positive for "Other operating income" (03.C)
                # and FX/Interest with correct sign
                if first_char == "8" and acct_code.startswith("811"):
                    val = -amount  # Reverse sign: negative in data = income
                elif first_char == "8" and acct_code.startswith("822"):
                    val = amount   # Expenses: positive in data = expense
                else:
                    val = amount
                self._bsi_pl_idx[target] = self._bsi_pl_idx.get(target, 0) + val

                # Track that this amount was MOVED from the account's natural parent
                # to a DIFFERENT P&L section. This allows populate_pl() to adjust parent totals.
                # e.g., 8110/x interest → moved from "03" (8110's TB parent) to "09.A"
                # But 8110/x → "03.C" stays WITHIN section 03, so no adjustment needed.
                source_parent = None
                for prefix, mr_prefix in ACCOUNT_PREFIX_TO_EXPENSE_CODE.items():
                    if acct_code.startswith(prefix):
                        source_parent = mr_prefix
                        break
                if source_parent and source_parent != target:
                    # Only adjust if target is in a DIFFERENT section (not a sub-item)
                    # e.g., 03 → 03.C is same section (no adjustment)
                    #        03 → 07 is different section (needs adjustment)
                    #        02.H → 09.B is different section (needs adjustment)
                    if not target.startswith(source_parent + "."):
                        self._nonop_adjustments[source_parent] = (
                            self._nonop_adjustments.get(source_parent, 0) + val
                        )

                continue

            # ── Determine parent code from account prefix ──
            parent_code = None
            for prefix, mr_prefix in ACCOUNT_PREFIX_TO_EXPENSE_CODE.items():
                if acct_code.startswith(prefix):
                    parent_code = mr_prefix
                    break
            if not parent_code:
                continue

            # ── Route to section-specific sub-classification ──

            # === INCOME accounts (03 — Other operating income) ===
            if parent_code == "03":
                # Income amounts: negative in data = credit = income
                val = -amount if amount < 0 else amount
                if acct_code.startswith("811"):
                    val = -amount  # 8110 sub-accounts: reverse sign

                suffix = None
                # Try MAPING ST first
                if maping_st in MAPING_ST_TO_PL_SUFFIX:
                    mapped = MAPING_ST_TO_PL_SUFFIX[maping_st]
                    if mapped == "SKIP":
                        continue
                # Keyword matching for income sub-items (A, B, C)
                for kw_suffix, keywords in INCOME_NAME_KEYWORDS.items():
                    if any(kw.lower() in acct_name_lower for kw in keywords):
                        suffix = kw_suffix
                        break
                if suffix is None:
                    suffix = "C"  # Default: Other operating income
                mr_code = f"03.{suffix}"
                self._bsi_pl_idx[mr_code] = self._bsi_pl_idx.get(mr_code, 0) + val
                continue

            # === OTHER OPERATING EXPENSES (02.H) ===
            if parent_code == "02.H":
                suffix = None
                # Keyword matching for other opex sub-items
                for kw_suffix, keywords in OTHER_OPEX_NAME_KEYWORDS.items():
                    if any(kw.lower() in acct_name_lower for kw in keywords):
                        suffix = kw_suffix
                        break
                if suffix is None:
                    suffix = "04"  # Default: Other (Other operating expenses)
                mr_code = f"02.H.{suffix}"
                self._bsi_pl_idx[mr_code] = self._bsi_pl_idx.get(mr_code, 0) + amount
                continue

            # === EXPENSE accounts (02.A, 02.B, 02.C, 02.D, etc.) ===
            suffix = None

            # 1. Try MAPING ST for known broad categories
            if maping_st in MAPING_ST_TO_PL_SUFFIX:
                mapped = MAPING_ST_TO_PL_SUFFIX[maping_st]
                if mapped == "SKIP":
                    continue  # Revenue/COGS handled elsewhere
                elif mapped is not None:
                    suffix = mapped  # Direct mapping (e.g., Wages -> 01)
                # None -> fall through to keyword matching

            # 2. Keyword matching on Georgian/Russian account name
            if suffix is None:
                # For COGS (02.A), try COGS-specific keywords first
                if parent_code == "02.A":
                    for kw_suffix, keywords in COGS_NAME_KEYWORDS.items():
                        if any(kw.lower() in acct_name_lower for kw in keywords):
                            suffix = kw_suffix
                            break

                # Try general expense keywords (works for all 02.x sections)
                if suffix is None:
                    for kw_suffix, keywords in EXPENSE_NAME_KEYWORDS.items():
                        if any(kw.lower() in acct_name_lower for kw in keywords):
                            suffix = kw_suffix
                            break

            # 3. Default fallback: "Other"
            if suffix is None:
                if parent_code == "02.A":
                    suffix = "17"  # Other (Cost of sales)
                else:
                    suffix = "16"  # Other (for admin/S&D/social sections)

            # ── Split depreciation into PPE / ROU / Intangible ──
            if suffix == "02":
                dep_suffix = "02.01"  # Default: PPE depreciation
                for sub_suffix, keywords in EXPENSE_NAME_KEYWORDS_DEPRECIATION.items():
                    if any(kw.lower() in acct_name_lower for kw in keywords):
                        dep_suffix = sub_suffix
                        break
                suffix = dep_suffix

            mr_code = f"{parent_code}.{suffix}"
            self._bsi_pl_idx[mr_code] = self._bsi_pl_idx.get(mr_code, 0) + amount

        # Log results
        nonzero = {k: round(v, 2) for k, v in self._bsi_pl_idx.items() if v != 0}
        if nonzero:
            logger.info(f"Mapping P&L index: {len(nonzero)} non-zero codes: {sorted(nonzero.keys())}")
            for k in sorted(nonzero.keys()):
                logger.info(f"  MAP {k}: {nonzero[k]:,.2f} GEL")
        else:
            logger.warning("Mapping P&L index: no items classified!")

    def _build_bsi_pl_index(self, bsi_items):
        """Fallback: Build P&L index from BSI items (when Mapping sheet not available)."""
        for item in bsi_items:
            code = (item.account_code or "").strip()
            if not code or code[0] not in "6789":
                continue
            if code.upper().endswith("X"):
                continue
            baku_map = (getattr(item, "baku_bs_mapping", None) or "").strip()
            ifrs_line = (getattr(item, "ifrs_line_item", None) or "").strip()
            if not baku_map and not ifrs_line:
                continue
            turnover = (item.turnover_debit or 0.0) - (item.turnover_credit or 0.0)
            if turnover == 0:
                continue

            # Check non-operating
            for val in [baku_map, ifrs_line]:
                if val in BAKU_NONOP_TO_PL_CODE:
                    target = BAKU_NONOP_TO_PL_CODE[val]
                    self._bsi_pl_idx[target] = self._bsi_pl_idx.get(target, 0) + turnover
                    break
            else:
                expense_code = None
                for prefix, mr_prefix in ACCOUNT_PREFIX_TO_EXPENSE_CODE.items():
                    if code.startswith(prefix):
                        expense_code = mr_prefix
                        break
                if not expense_code:
                    continue
                suffix = BAKU_CATEGORY_TO_PL_SUFFIX.get(baku_map)
                if suffix is None and ifrs_line:
                    suffix = IFRS_LINE_TO_PL_SUFFIX.get(ifrs_line)
                if suffix is None:
                    suffix = "17" if expense_code == "02.A" else "16"
                mr_code = f"{expense_code}.{suffix}"
                self._bsi_pl_idx[mr_code] = self._bsi_pl_idx.get(mr_code, 0) + turnover

        nonzero = {k: round(v, 2) for k, v in self._bsi_pl_idx.items() if v != 0}
        if nonzero:
            logger.info(f"BSI P&L index (fallback): {len(nonzero)} codes: {sorted(nonzero.keys())}")

    def _build_tb_semantic_fallback(self):
        """
        TB-based semantic fallback: when mapping sheet / BSI index doesn't
        cover all P&L sections, analyze TB item NAMES to sub-classify.

        This is the 'financial ontology' layer — the system understands what
        an account MEANS by reading its name, even without explicit classification.

        Processes TB items for parent codes that have a total but no sub-classification.
        E.g., if 02.A = 44M but all 44M is in "Other", try to break it down using
        account name keywords (salary, depreciation, materials, etc.).

        Also handles income accounts (8110 sub-accounts -> 03.A/B/C) and
        other operating expenses (8220 -> 02.H.01-04).
        """
        # Identify which parent codes have a "total" from TB matching
        # but ALL value is in the default "Other" sub-item
        parent_codes_to_check = {
            "02.A": {"default_suffix": "17", "keywords": COGS_NAME_KEYWORDS},
            "02.H": {"default_suffix": "04", "keywords": OTHER_OPEX_NAME_KEYWORDS},
            "03":   {"default_suffix": "C",  "keywords": INCOME_NAME_KEYWORDS},
        }

        for parent_code, config in parent_codes_to_check.items():
            default_key = f"{parent_code}.{config['default_suffix']}"

            # Check if all value sits in the default sub-item (no mapping sheet detail)
            default_val = self._bsi_pl_idx.get(default_key, 0)
            non_default_total = sum(
                v for k, v in self._bsi_pl_idx.items()
                if k.startswith(parent_code + ".") and k != default_key and v != 0
            )

            # If there's already meaningful sub-classification, skip this parent
            if non_default_total != 0:
                continue
            # If no value at all in this parent, skip
            if default_val == 0:
                continue

            # Find TB accounts that feed this parent code
            prefix_map = {v: k for k, v in ACCOUNT_PREFIX_TO_EXPENSE_CODE.items()}
            account_prefixes = [k for k, v in ACCOUNT_PREFIX_TO_EXPENSE_CODE.items()
                                if v == parent_code]

            if not account_prefixes:
                continue

            # Walk TB items and try to sub-classify by name
            reclassified = {}
            for code, entry in self._account_idx.items():
                if code.upper().endswith("X"):
                    continue
                matching = any(code.startswith(p) for p in account_prefixes)
                if not matching:
                    continue

                turnover = entry["turnover_dr"] - entry["turnover_cr"]
                if abs(turnover) < 0.01:
                    continue

                acct_name_lower = entry.get("name", "").lower()
                if not acct_name_lower:
                    continue

                suffix = None
                for kw_suffix, keywords in config['keywords'].items():
                    if any(kw.lower() in acct_name_lower for kw in keywords):
                        suffix = kw_suffix
                        break

                if suffix is not None:
                    # For income accounts, handle sign properly
                    val = turnover
                    if parent_code == "03":
                        val = -turnover  # Income: reverse sign (cr-dr is positive)

                    mr_code = f"{parent_code}.{suffix}"
                    reclassified[mr_code] = reclassified.get(mr_code, 0) + val

            if reclassified:
                # Apply reclassification: move amounts from default to specific sub-items
                total_reclassified = sum(abs(v) for v in reclassified.values())
                for mr_code, val in reclassified.items():
                    self._bsi_pl_idx[mr_code] = self._bsi_pl_idx.get(mr_code, 0) + val
                    # Reduce the default "Other" bucket
                    if parent_code == "03":
                        self._bsi_pl_idx[default_key] = self._bsi_pl_idx.get(default_key, 0) - val
                    else:
                        self._bsi_pl_idx[default_key] = self._bsi_pl_idx.get(default_key, 0) - val

                logger.info(
                    f"TB semantic fallback: {parent_code} reclassified "
                    f"{len(reclassified)} sub-items from default '{default_key}': "
                    f"{sorted(reclassified.keys())}"
                )

    def _match_accounts(self, patterns: list[str], side: str = "dr", balance_type: str = "closing") -> float:
        """
        Sum TB balances for account codes matching any of the given patterns.
        De-duplicates accounts across patterns and skips TB summary rows
        (codes ending in XX) to prevent double-counting.

        Patterns:
          "1610"  -> exact match for account code "1610"
          "16XX"  -> matches codes starting with "16" (XX = any suffix, wildcard)
          "1610*" -> matches codes starting with "1610" (1610, 16100, 1610.01, etc.)
          "31XX"  -> matches codes starting with "31"

        Side:
          "dr"  -> balance = debit - credit (assets, expenses)
          "cr"  -> balance = credit - debit (liabilities, equity, revenue)

        Balance type:
          "closing" -> closing balance
          "opening" -> opening balance
          "turnover" -> period movement
        """
        if not patterns:
            return 0.0

        # Collect unique account codes across all patterns,
        # skipping TB summary rows (codes ending with X/XX/XXX) to avoid
        # double-counting with leaf accounts
        unique_codes: set[str] = set()
        for pattern in patterns:
            pattern = pattern.strip()
            if not pattern:
                continue
            matched_codes = self._resolve_pattern(pattern)
            for code in matched_codes:
                # Skip TB summary/hierarchy rows:
                # Codes ending in X (e.g. "141X", "162X", "61XX", "6XXX")
                # These are aggregations of leaf accounts and would double-count
                if code.upper().endswith("X"):
                    continue
                unique_codes.add(code)

        # If no leaf accounts matched (only summary rows in TB),
        # fall back to using summary rows
        if not unique_codes:
            for pattern in patterns:
                pattern = pattern.strip()
                if not pattern:
                    continue
                matched_codes = self._resolve_pattern(pattern)
                for code in matched_codes:
                    unique_codes.add(code)
            # Use only the most specific (longest code) summary row
            if len(unique_codes) > 1:
                longest = max(unique_codes, key=len)
                unique_codes = {longest}

        # Remove parent accounts when their children are also in the set.
        # E.g., if both "3370" and "3370.01" matched, keep only "3370.01"
        # because "3370" is the parent summary and would double-count.
        if len(unique_codes) > 1:
            to_remove = set()
            sorted_codes = sorted(unique_codes)
            for i, code_a in enumerate(sorted_codes):
                for code_b in sorted_codes[i + 1:]:
                    # If code_b starts with code_a (+ separator), code_a is parent
                    if code_b.startswith(code_a + ".") or (
                        code_b.startswith(code_a) and len(code_b) > len(code_a)
                        and not code_b[len(code_a)].isalpha()
                    ):
                        to_remove.add(code_a)
                        break
            unique_codes -= to_remove

        total = 0.0
        for code in unique_codes:
            entry = self._account_idx[code]
            if balance_type == "closing":
                dr_val = entry["closing_dr"]
                cr_val = entry["closing_cr"]
            elif balance_type == "opening":
                dr_val = entry["opening_dr"]
                cr_val = entry["opening_cr"]
            else:  # turnover
                dr_val = entry["turnover_dr"]
                cr_val = entry["turnover_cr"]

            if side == "dr":
                total += dr_val - cr_val
            else:  # cr
                total += cr_val - dr_val

        return total

    def _resolve_pattern(self, pattern: str) -> list[str]:
        """Resolve a single pattern to a list of matching account codes."""
        matched = []

        if pattern.endswith("XX"):
            # "16XX" -> match codes starting with "16"
            prefix = pattern[:-2]
            for code in self._account_idx:
                if code.startswith(prefix) and code != prefix:
                    matched.append(code)
        elif pattern.endswith("X"):
            # "141X" -> match codes starting with "141" (but not exactly "141")
            prefix = pattern[:-1]
            for code in self._account_idx:
                if code.startswith(prefix) and code != prefix:
                    matched.append(code)
        elif "*" in pattern:
            # "1610*" -> match codes starting with "1610"
            prefix = pattern.replace("*", "")
            for code in self._account_idx:
                if code.startswith(prefix):
                    matched.append(code)
        else:
            # Exact match
            if pattern in self._account_idx:
                matched.append(pattern)

        return matched

    def _to_usd_k(self, gel_amount: float) -> float:
        """Convert GEL to USD thousands."""
        if self.rate <= 0:
            return 0.0
        return round(gel_amount / self.rate / 1000, 1)

    def _sum_children(self, template: list, sum_of: list[str],
                      value_dict: dict[str, float],
                      parent_code: str = "") -> float:
        """Sum child values respecting the sign field for contra-accounts.

        A child is SUBTRACTED only when it is a contra-account:
          - child sign is "-" AND parent sign is "+"
        This handles PPE (cost - depreciation), intangibles (cost - amort),
        receivables - ECL, etc.

        In all other cases (same sign, or parent is "-" and child is "-"),
        children are ADDED normally. This ensures liability subtotals
        (20.B = sum of all "-" children) work correctly.
        """
        parent_tmpl = self._find_tmpl(template, parent_code) if parent_code else {}
        parent_sign = parent_tmpl.get("sign", "+")

        total = 0.0
        for child_code in sum_of:
            child_val = value_dict.get(child_code, 0.0)
            child_tmpl = self._find_tmpl(template, child_code)
            child_sign = child_tmpl.get("sign", "+")

            # Contra-account: child is "-" under a "+" parent → subtract
            is_contra = (child_sign == "-" and parent_sign == "+")
            if is_contra:
                total -= child_val
            else:
                total += child_val
        return total

    # ════════════════════════════════════════════════════════════════
    # Balance Sheet
    # ════════════════════════════════════════════════════════════════

    def populate_bs(self) -> list[dict]:
        """
        Walk BAKU_BS_TEMPLATE, populate each row with actual values.
        Returns list of dicts with 'code', 'line', 'actual_gel', 'actual_usd_k',
        'opening_gel', 'opening_usd_k', etc.
        """
        rows = []
        value_by_code: dict[str, float] = {}  # code -> GEL value (closing)
        opening_by_code: dict[str, float] = {}  # code -> GEL value (opening)

        # First pass: populate leaf nodes (rows with 'accounts' or no sum_of)
        for tmpl in BAKU_BS_TEMPLATE:
            row = self._make_row(tmpl)
            accounts = tmpl.get("accounts", [])
            side = tmpl.get("side", "dr")
            has_sum_of = bool(tmpl.get("sum_of"))

            if accounts:
                gel_closing = self._match_accounts(accounts, side=side, balance_type="closing")
                gel_opening = self._match_accounts(accounts, side=side, balance_type="opening")
                row["actual_gel"] = gel_closing
                row["actual_usd_k"] = self._to_usd_k(gel_closing)
                row["opening_gel"] = gel_opening
                row["opening_usd_k"] = self._to_usd_k(gel_opening)
                value_by_code[tmpl["code"]] = gel_closing
                opening_by_code[tmpl["code"]] = gel_opening
            elif not has_sum_of and "formula" not in tmpl:
                # Leaf node with no accounts and no sum_of → value is 0
                value_by_code[tmpl["code"]] = 0.0
                opening_by_code[tmpl["code"]] = 0.0

            rows.append(row)

        # Second pass: compute sum_of rows (bottom-up: deepest first)
        # Since template is in display order, we need multiple passes
        # until all sum_of rows are resolved
        for _pass in range(5):  # Max 5 levels of nesting
            changed = False
            for row in rows:
                code = row["code"]
                tmpl = self._find_tmpl(BAKU_BS_TEMPLATE, code)
                sum_of = tmpl.get("sum_of", [])
                if sum_of and code not in value_by_code:
                    # Check if all children are resolved
                    all_resolved = all(c in value_by_code for c in sum_of)
                    if all_resolved:
                        gel_val = self._sum_children(BAKU_BS_TEMPLATE, sum_of, value_by_code, parent_code=code)
                        gel_open = self._sum_children(BAKU_BS_TEMPLATE, sum_of, opening_by_code, parent_code=code)
                        row["actual_gel"] = gel_val
                        row["actual_usd_k"] = self._to_usd_k(gel_val)
                        row["opening_gel"] = gel_open
                        row["opening_usd_k"] = self._to_usd_k(gel_open)
                        value_by_code[code] = gel_val
                        opening_by_code[code] = gel_open
                        changed = True
            if not changed:
                break

        return rows

    # ════════════════════════════════════════════════════════════════
    # Profit & Loss
    # ════════════════════════════════════════════════════════════════

    def populate_pl(self) -> list[dict]:
        """
        Walk BAKU_PL_TEMPLATE, populate from:
        - TB account matching for direct line items
        - Revenue/COGS/GA items for aggregated totals
        - Formulas for computed lines (GP, OP, EBITDA, etc.)
        """
        rows = []
        value_by_code: dict[str, float] = {}

        # Pre-calculate totals from specific item types
        total_revenue_gel = sum(r.net or r.gross or 0 for r in self.rev_items)
        total_cogs_gel = sum(c.total_cogs or 0 for c in self.cogs_items)
        total_ga_gel = sum(g.amount or 0 for g in self.ga_items)

        # First pass: populate leaf nodes
        for tmpl in BAKU_PL_TEMPLATE:
            row = self._make_row(tmpl)
            code = tmpl["code"]
            accounts = tmpl.get("accounts", [])
            side = tmpl.get("side", "dr")
            has_sum_of = bool(tmpl.get("sum_of"))
            has_formula = bool(tmpl.get("formula"))

            if accounts:
                # Use TB turnover for P&L items (period activity, not balance)
                gel_val = self._match_accounts(accounts, side=side, balance_type="turnover")
                row["actual_gel"] = gel_val
                row["actual_usd_k"] = self._to_usd_k(gel_val)
                value_by_code[code] = gel_val
            elif not has_sum_of and not has_formula:
                # Leaf node with no accounts → value is 0 (enables sum_of resolution)
                value_by_code[code] = 0.0

            # Special handling: populate Revenue from RevenueItem data if TB doesn't have it
            if code == "01.A" and value_by_code.get("01.A", 0) == 0 and total_revenue_gel != 0:
                # Fallback: use RevenueItem totals
                row["actual_gel"] = total_revenue_gel
                row["actual_usd_k"] = self._to_usd_k(total_revenue_gel)
                value_by_code["01.A"] = total_revenue_gel

            # Special: use COGS items if TB 7110 is empty
            if code == "02.A" and value_by_code.get("02.A", 0) == 0 and total_cogs_gel != 0:
                row["actual_gel"] = total_cogs_gel
                row["actual_usd_k"] = self._to_usd_k(total_cogs_gel)
                value_by_code["02.A"] = total_cogs_gel

            # Special: use GA items if TB 7410 is empty
            if code == "02.B" and value_by_code.get("02.B", 0) == 0 and total_ga_gel != 0:
                row["actual_gel"] = total_ga_gel
                row["actual_usd_k"] = self._to_usd_k(total_ga_gel)
                value_by_code["02.B"] = total_ga_gel

            rows.append(row)

        # ── Non-operating reconciliation pass ──
        # When BSI mapping moves items from one P&L section to another
        # (e.g., interest income from 8110 → moved from "03" to "09.A"),
        # the source section's TB-derived total must be reduced.
        # Otherwise 03 shows the full 8110 total INCLUDING items that
        # were correctly reclassified to 04/07/09.A/09.B.
        if self._nonop_adjustments:
            for source_code, adjustment in self._nonop_adjustments.items():
                if source_code in value_by_code:
                    old_val = value_by_code[source_code]
                    new_val = old_val - adjustment
                    value_by_code[source_code] = new_val
                    # Update the corresponding row
                    for row in rows:
                        if row["code"] == source_code:
                            row["actual_gel"] = new_val
                            row["actual_usd_k"] = self._to_usd_k(new_val)
                            break
                    logger.info(
                        f"NonOp reconciliation: {source_code} adjusted "
                        f"{old_val:,.2f} -> {new_val:,.2f} GEL "
                        f"(moved {adjustment:,.2f} to other sections)"
                    )

        # ── BSI Category Pass: populate sub-items from BalanceSheetItem data ──
        # The BSI index maps codes like "02.C.01" -> GEL amount based on
        # baku_bs_mapping categories. This fills in expense sub-breakdowns
        # (Wages, Depreciation, Utilities, etc.) that can't be determined
        # from account codes alone.
        if self._bsi_pl_idx:
            bsi_populated = 0
            for row in rows:
                code = row["code"]
                if code in self._bsi_pl_idx and value_by_code.get(code, 0) == 0:
                    gel_val = self._bsi_pl_idx[code]
                    row["actual_gel"] = gel_val
                    row["actual_usd_k"] = self._to_usd_k(gel_val)
                    value_by_code[code] = gel_val
                    bsi_populated += 1
            if bsi_populated:
                logger.info(f"BSI populated {bsi_populated} P&L sub-items")

        # ── Parent reconciliation pass ──
        # After BSI populates sub-items, a parent's TB-derived value may be
        # less than the sum of its BSI-populated children.  This happens when
        # non-operating reclassification moves amounts INTO this section from
        # another source (e.g., 8220 "Other opex" items → classified as 03.C
        # "Other operating income" via MAPING_ST_NONOP).  The 8220 contribution
        # increases 03.C but was never part of 03's TB accounts (8110/81XX).
        # Fix: ensure parent ≥ sum of direct children by re-deriving if needed.
        if self._bsi_pl_idx:
            # Identify parent codes that have BSI-populated children
            bsi_parent_codes: set[str] = set()
            for bsi_code in self._bsi_pl_idx:
                parts = bsi_code.rsplit(".", 1)
                if len(parts) == 2:
                    bsi_parent_codes.add(parts[0])

            for parent_code in sorted(bsi_parent_codes):
                if parent_code not in value_by_code:
                    continue
                # Sum all direct children (one level deeper only)
                children_sum = 0.0
                child_count = 0
                for vc_code, vc_val in value_by_code.items():
                    if vc_code.startswith(parent_code + "."):
                        remainder = vc_code[len(parent_code) + 1:]
                        if "." not in remainder:  # direct child, not grandchild
                            children_sum += vc_val
                            child_count += 1

                current = value_by_code[parent_code]
                if child_count > 0 and children_sum > current:
                    value_by_code[parent_code] = children_sum
                    for row in rows:
                        if row["code"] == parent_code:
                            row["actual_gel"] = children_sum
                            row["actual_usd_k"] = self._to_usd_k(children_sum)
                            break
                    logger.info(
                        f"Parent reconciliation: {parent_code} updated "
                        f"{current:,.2f} -> {children_sum:,.2f} GEL "
                        f"(BSI children sum exceeds TB-adjusted value)"
                    )

        # Second pass: compute sum_of rows (respects sign field for child items)
        for _pass in range(5):
            changed = False
            for row in rows:
                code = row["code"]
                tmpl = self._find_tmpl(BAKU_PL_TEMPLATE, code)
                sum_of = tmpl.get("sum_of", [])
                if sum_of and code not in value_by_code:
                    all_resolved = all(c in value_by_code for c in sum_of)
                    if all_resolved:
                        gel_val = self._sum_children(BAKU_PL_TEMPLATE, sum_of, value_by_code, parent_code=code)
                        row["actual_gel"] = gel_val
                        row["actual_usd_k"] = self._to_usd_k(gel_val)
                        value_by_code[code] = gel_val
                        changed = True
            if not changed:
                break

        # Third pass: compute formula rows (GP, OP, EBITDA, etc.)
        self._compute_pl_formulas(rows, value_by_code)

        return rows

    def _compute_pl_formulas(self, rows: list[dict], values: dict[str, float]):
        """Compute formula-based P&L lines: GP, OP, EBITDA, etc."""
        formulas = {
            "GP": lambda v: v.get("01", 0) - v.get("02.A", 0),
            "OP": lambda v: (
                v.get("GP", 0)
                - v.get("02.B", 0) - v.get("02.C", 0) - v.get("02.D", 0)
                - v.get("02.E", 0) - v.get("02.F", 0) - v.get("02.G", 0)
                - v.get("02.H", 0) + v.get("03", 0) + v.get("04", 0)
            ),
            "08": lambda v: v.get("OP", 0) + v.get("05", 0) + v.get("06", 0) + v.get("07", 0),
            "09": lambda v: v.get("09.A", 0) - v.get("09.B", 0),
            "10": lambda v: v.get("08", 0) + v.get("09", 0),
            "12": lambda v: v.get("10", 0) - v.get("11", 0),
            "14": lambda v: v.get("12", 0) + v.get("13", 0),
        }

        # Compute in order of dependency
        formula_order = ["GP", "OP", "08", "EBITDA", "09", "10", "12", "14"]
        for code in formula_order:
            if code == "EBITDA":
                # EBITDA = OP + total D&A from all expense sections
                # Sum depreciation sub-items across COGS, Admin, S&D, Social
                total_da = 0
                for section in ["02.A", "02.B", "02.C", "02.D", "02.E", "02.F"]:
                    total_da += values.get(f"{section}.02", 0)
                    total_da += values.get(f"{section}.02.01", 0)
                    total_da += values.get(f"{section}.02.02", 0)
                    total_da += values.get(f"{section}.02.03", 0)
                # Avoid double-counting: if .02 is sum of .02.01-.02.03, use .02
                # If .02 has value, its children were already summed into it
                total_da_final = 0
                for section in ["02.A", "02.B", "02.C", "02.D", "02.E", "02.F"]:
                    parent = values.get(f"{section}.02", 0)
                    if parent != 0:
                        total_da_final += parent
                    else:
                        total_da_final += (
                            values.get(f"{section}.02.01", 0) +
                            values.get(f"{section}.02.02", 0) +
                            values.get(f"{section}.02.03", 0)
                        )
                gel_val = values.get("OP", 0) + total_da_final
                values["EBITDA"] = gel_val
            elif code in formulas:
                gel_val = formulas[code](values)
                values[code] = gel_val
            else:
                continue

            # Update the row
            for row in rows:
                if row["code"] == code:
                    row["actual_gel"] = values[code]
                    row["actual_usd_k"] = self._to_usd_k(values[code])
                    break

    # ════════════════════════════════════════════════════════════════
    # Cash Flow Statement
    # ════════════════════════════════════════════════════════════════

    def populate_cfs(self, pl_values: dict[str, float] = None) -> list[dict]:
        """
        Walk BAKU_CFS_TEMPLATE. Uses P&L values for cross-references
        and BS changes for working capital items.
        """
        pl_vals = pl_values or {}
        rows = []
        value_by_code: dict[str, float] = {}

        for tmpl in BAKU_CFS_TEMPLATE:
            row = self._make_row(tmpl)
            code = tmpl["code"]

            # pl_ref: pull value from P&L
            if "pl_ref" in tmpl:
                gel_val = pl_vals.get(tmpl["pl_ref"], 0.0)
                if tmpl.get("negate"):
                    gel_val = -gel_val
                row["actual_gel"] = gel_val
                row["actual_usd_k"] = self._to_usd_k(gel_val)
                value_by_code[code] = gel_val

            # bs_change: compute period change from TB opening vs closing
            elif "bs_change" in tmpl:
                patterns = tmpl["bs_change"]
                closing = self._match_accounts(patterns, side="dr", balance_type="closing")
                opening = self._match_accounts(patterns, side="dr", balance_type="opening")
                gel_val = closing - opening
                # For liabilities, reverse sign (increase in payables = cash inflow)
                if any(p.startswith("3") or p.startswith("4") for p in patterns):
                    gel_val = -gel_val
                row["actual_gel"] = gel_val
                row["actual_usd_k"] = self._to_usd_k(gel_val)
                value_by_code[code] = gel_val

            # bs_opening / bs_closing: specific balance snapshots
            elif "bs_opening" in tmpl:
                gel_val = self._match_accounts(tmpl["bs_opening"], side="dr", balance_type="opening")
                row["actual_gel"] = gel_val
                row["actual_usd_k"] = self._to_usd_k(gel_val)
                value_by_code[code] = gel_val
            elif "bs_closing" in tmpl:
                gel_val = self._match_accounts(tmpl["bs_closing"], side="dr", balance_type="closing")
                row["actual_gel"] = gel_val
                row["actual_usd_k"] = self._to_usd_k(gel_val)
                value_by_code[code] = gel_val

            rows.append(row)

        # Compute sum_of rows
        for _pass in range(5):
            changed = False
            for row in rows:
                code = row["code"]
                tmpl = self._find_tmpl(BAKU_CFS_TEMPLATE, code)
                sum_of = tmpl.get("sum_of", [])
                if sum_of and code not in value_by_code:
                    all_resolved = all(c in value_by_code for c in sum_of)
                    if all_resolved:
                        gel_val = sum(value_by_code.get(c, 0.0) for c in sum_of)
                        row["actual_gel"] = gel_val
                        row["actual_usd_k"] = self._to_usd_k(gel_val)
                        value_by_code[code] = gel_val
                        changed = True
            if not changed:
                break

        # Compute net cash lines — V8 codes
        # CFI.01.01 = before working capital changes (already computed via sum_of)
        cf_before_wc = value_by_code.get("CFI.01.01", 0)
        wc_changes = sum(value_by_code.get(f"CFI.01.0{i}", 0) for i in range(2, 8))
        cf_op_gen_total = cf_before_wc + wc_changes
        for row in rows:
            if row["code"] == "CFI.01":
                row["actual_gel"] = cf_op_gen_total
                row["actual_usd_k"] = self._to_usd_k(cf_op_gen_total)
                value_by_code["CFI.01"] = cf_op_gen_total

        # CFI (operating total) = CFI.01 + CFI.02 + CFI.03
        cf_op_net = cf_op_gen_total + value_by_code.get("CFI.02", 0) + value_by_code.get("CFI.03", 0)
        for row in rows:
            if row["code"] == "CFI":
                row["actual_gel"] = cf_op_net
                row["actual_usd_k"] = self._to_usd_k(cf_op_net)
                value_by_code["CFI"] = cf_op_net

        # CF02 (investing total) = sum of CF02.01..CF02.13
        inv_codes = ["CF02.01","CF02.02","CF02.03","CF02.04","CF02.05","CF02.06",
                     "CF02.07","CF02.08","CF02.09","CF02.10","CF02.11","CF02.12","CF02.13"]
        cf_inv_net = sum(value_by_code.get(c, 0) for c in inv_codes)
        for row in rows:
            if row["code"] == "CF02":
                row["actual_gel"] = cf_inv_net
                row["actual_usd_k"] = self._to_usd_k(cf_inv_net)
                value_by_code["CF02"] = cf_inv_net

        # CF03 (financing total) = sum of CF03.01..CF03.12
        fin_codes = [f"CF03.{i:02d}" for i in range(1, 13)]
        cf_fin_net = sum(value_by_code.get(c, 0) for c in fin_codes)
        for row in rows:
            if row["code"] == "CF03":
                row["actual_gel"] = cf_fin_net
                row["actual_usd_k"] = self._to_usd_k(cf_fin_net)
                value_by_code["CF03"] = cf_fin_net

        # CF08 = Net increase = CFI + CF02 + CF03 + CF04..CF07
        net_increase = (
            value_by_code.get("CFI", 0)
            + value_by_code.get("CF02", 0)
            + value_by_code.get("CF03", 0)
            + value_by_code.get("CF04", 0)
            + value_by_code.get("CF05", 0)
            + value_by_code.get("CF06", 0)
            + value_by_code.get("CF07", 0)
        )
        for row in rows:
            if row["code"] == "CF08":
                row["actual_gel"] = net_increase
                row["actual_usd_k"] = self._to_usd_k(net_increase)

        return rows

    # ════════════════════════════════════════════════════════════════
    # Products Revenue (Wholesale / Retail)
    # ════════════════════════════════════════════════════════════════

    def populate_products_wholesale(self) -> list[dict]:
        """Map RevenueItem/COGSItem with wholesale segments."""
        return self._populate_products("wholesale", BAKU_PRODUCTS_WHOLESALE_TEMPLATE)

    def populate_products_retail(self) -> list[dict]:
        """Map RevenueItem/COGSItem with retail segments."""
        return self._populate_products("retail", BAKU_PRODUCTS_RETAIL_TEMPLATE)

    def populate_products_gas_distr(self) -> list[dict]:
        """Map RevenueItem/COGSItem with gas distribution segments."""
        return self._populate_products("gas", BAKU_PRODUCTS_GAS_DISTR_TEMPLATE)

    def _populate_products(self, segment_key: str, template: list) -> list[dict]:
        """Populate product revenue template from RevenueItem/COGSItem."""
        # Filter revenue/cogs by segment
        seg_lower = segment_key.lower()
        rev_filtered = [r for r in self.rev_items
                        if seg_lower in (r.segment or "").lower()]
        cogs_filtered = [c for c in self.cogs_items
                         if seg_lower in (c.segment or "").lower()]

        rows = []
        total_rev_gel = sum(r.net or r.gross or 0 for r in rev_filtered)
        total_cogs_gel = sum(c.total_cogs or 0 for c in cogs_filtered)

        for tmpl in template:
            row = {
                "code": tmpl.get("code", ""),
                "line": tmpl["line"],
                "bold": tmpl.get("bold", False),
                "level": tmpl.get("level", 1),
                "type": tmpl.get("type", ""),
                "actual_gel": 0.0,
                "actual_usd_k": 0.0,
            }

            if tmpl.get("type") == "header":
                row["actual_gel"] = total_rev_gel
                row["actual_usd_k"] = self._to_usd_k(total_rev_gel)
            elif tmpl.get("type") == "cogs_header":
                row["actual_gel"] = total_cogs_gel
                row["actual_usd_k"] = self._to_usd_k(total_cogs_gel)
            elif tmpl.get("type") == "product":
                category_patterns = tmpl.get("category_match", [])
                if category_patterns:
                    match_rev = sum(
                        r.net or r.gross or 0 for r in rev_filtered
                        if any(pat.lower() in (r.product or "").lower()
                               or pat.lower() in (r.category or "").lower()
                               for pat in category_patterns)
                    )
                    match_cogs = sum(
                        c.total_cogs or 0 for c in cogs_filtered
                        if any(pat.lower() in (c.product or "").lower()
                               or pat.lower() in (c.category or "").lower()
                               for pat in category_patterns)
                    )
                else:
                    # "Other products" — remainder
                    accounted_rev = sum(
                        r.net or r.gross or 0 for r in rev_filtered
                        if self._matches_any_product_category(r, template)
                    )
                    match_rev = total_rev_gel - accounted_rev
                    accounted_cogs = sum(
                        c.total_cogs or 0 for c in cogs_filtered
                        if self._matches_any_product_category(c, template)
                    )
                    match_cogs = total_cogs_gel - accounted_cogs

                row["actual_gel"] = match_rev
                row["actual_usd_k"] = self._to_usd_k(match_rev)
                row["cogs_gel"] = match_cogs
                row["cogs_usd_k"] = self._to_usd_k(match_cogs)

            rows.append(row)

        # Add individual product detail rows
        for r in rev_filtered:
            net = r.net or r.gross or 0
            rows.append({
                "code": "",
                "line": f"  {r.product}",
                "bold": False,
                "level": 3,
                "type": "detail",
                "actual_gel": net,
                "actual_usd_k": self._to_usd_k(net),
                "category": r.category or "",
            })

        return rows

    def _matches_any_product_category(self, item, template) -> bool:
        """Check if an item matches any named product category in template."""
        product_name = (getattr(item, 'product', '') or '').lower()
        category_name = (getattr(item, 'category', '') or '').lower()
        for tmpl in template:
            for pat in tmpl.get("category_match", []):
                if pat.lower() in product_name or pat.lower() in category_name:
                    return True
        return False

    # ════════════════════════════════════════════════════════════════
    # OPEX Breakdown
    # ════════════════════════════════════════════════════════════════

    def populate_opex(self) -> list[dict]:
        """Map GA expense items to OPEX template structure."""
        rows = []

        # Build GA by account_code prefix for mapping
        ga_by_prefix: dict[str, float] = {}
        for g in self.ga_items:
            prefix = (g.account_code or "")[:4]
            ga_by_prefix[prefix] = ga_by_prefix.get(prefix, 0) + (g.amount or 0)

        total_ga_gel = sum(g.amount or 0 for g in self.ga_items)

        for tmpl in BAKU_OPEX_TEMPLATE:
            row = {
                "segment": tmpl["segment"],
                "line": tmpl["line"],
                "bold": tmpl.get("bold", False),
                "actual_gel": 0.0,
                "actual_usd_k": 0.0,
            }
            rows.append(row)

        # Add dynamic GA line items
        ga_grouped: dict[str, dict] = {}
        for g in self.ga_items:
            key = g.account_name or g.account_code or "Other"
            if key not in ga_grouped:
                ga_grouped[key] = {"gel": 0.0, "code": g.account_code or ""}
            ga_grouped[key]["gel"] += g.amount or 0

        for name, data in sorted(ga_grouped.items()):
            rows.append({
                "segment": "SGP",
                "line": f"{data['code']} — {name}",
                "bold": False,
                "actual_gel": data["gel"],
                "actual_usd_k": self._to_usd_k(data["gel"]),
            })

        # Add total row
        rows.append({
            "segment": "SGP",
            "line": "Total G&A Expenses",
            "bold": True,
            "actual_gel": total_ga_gel,
            "actual_usd_k": self._to_usd_k(total_ga_gel),
        })

        return rows

    # ════════════════════════════════════════════════════════════════
    # Borrowings / Receivables / Payables / Prepayments
    # ════════════════════════════════════════════════════════════════

    def populate_borrowings(self) -> list[dict]:
        """Extract borrowing accounts from TB (class 32XX, 41XX)."""
        patterns = ["32XX", "3210", "3211", "41XX", "4170", "4171"]
        return self._populate_tb_extract("Borrowings", patterns, side="cr")

    def populate_receivables(self) -> list[dict]:
        """Extract receivable accounts from TB (class 1410, 141X, etc.)."""
        patterns = ["1410", "1412", "141X", "1430", "143X", "149X", "1491", "1495", "1496"]
        return self._populate_tb_extract("Receivables", patterns, side="dr")

    def populate_payables(self) -> list[dict]:
        """Extract payable accounts from TB (class 3110, 31XX, etc.)."""
        patterns = ["3110", "3111", "31XX", "3121", "3130", "3190", "3191", "3199"]
        return self._populate_tb_extract("Payables", patterns, side="cr")

    def populate_prepayments(self) -> list[dict]:
        """Extract prepayment accounts from TB (1296, 143X, 1430)."""
        patterns = ["1296", "129X", "1430", "143X"]
        return self._populate_tb_extract("Prepayments", patterns, side="dr")

    def _populate_tb_extract(self, section: str, patterns: list[str], side: str = "dr") -> list[dict]:
        """Extract individual account lines matching patterns from TB."""
        rows = []
        total_gel = 0.0

        # Get all matching account codes
        all_codes: set[str] = set()
        for pattern in patterns:
            all_codes.update(self._resolve_pattern(pattern))

        for code in sorted(all_codes):
            entry = self._account_idx[code]
            if side == "dr":
                closing = entry["closing_dr"] - entry["closing_cr"]
                opening = entry["opening_dr"] - entry["opening_cr"]
            else:
                closing = entry["closing_cr"] - entry["closing_dr"]
                opening = entry["opening_cr"] - entry["opening_dr"]

            if closing == 0 and opening == 0:
                continue  # Skip zero-balance accounts

            total_gel += closing
            rows.append({
                "account_code": code,
                "line": code,  # We don't have account names in the index
                "opening_gel": opening,
                "opening_usd_k": self._to_usd_k(opening),
                "actual_gel": closing,
                "actual_usd_k": self._to_usd_k(closing),
                "change_gel": closing - opening,
                "change_usd_k": self._to_usd_k(closing - opening),
            })

        # Enrich with account names from TB items (second pass)
        # Build code->name map from the index source data is lost,
        # so we add the total row
        rows.append({
            "account_code": "",
            "line": f"Total {section}",
            "opening_gel": sum(r["opening_gel"] for r in rows if "opening_gel" in r),
            "opening_usd_k": self._to_usd_k(sum(r["opening_gel"] for r in rows if "opening_gel" in r)),
            "actual_gel": total_gel,
            "actual_usd_k": self._to_usd_k(total_gel),
            "change_gel": total_gel - sum(r["opening_gel"] for r in rows if "opening_gel" in r),
            "change_usd_k": self._to_usd_k(total_gel - sum(r["opening_gel"] for r in rows if "opening_gel" in r)),
            "bold": True,
        })

        return rows

    # ════════════════════════════════════════════════════════════════
    # Full Population — All Sections
    # ════════════════════════════════════════════════════════════════

    def populate_all(self) -> dict[str, Any]:
        """Populate all MR sections and return as a dict suitable for MRReportSnapshot.sections."""
        bs_rows = self.populate_bs()
        pl_rows = self.populate_pl()

        # Build P&L value dict for CFS cross-references
        pl_values = {row["code"]: row.get("actual_gel", 0) for row in pl_rows}

        cfs_rows = self.populate_cfs(pl_values=pl_values)
        products_ws = self.populate_products_wholesale()
        products_rt = self.populate_products_retail()
        products_gd = self.populate_products_gas_distr()
        opex_rows = self.populate_opex()
        borrowings = self.populate_borrowings()
        receivables = self.populate_receivables()
        payables = self.populate_payables()
        prepayments = self.populate_prepayments()

        # Build summary from P&L values
        revenue_gel = pl_values.get("01", pl_values.get("01.A", 0))
        cogs_gel = pl_values.get("02.A", 0)
        gp_gel = pl_values.get("GP", 0)
        op_gel = pl_values.get("OP", 0)
        net_income_gel = pl_values.get("12", 0)
        ebitda_gel = pl_values.get("EBITDA", 0)

        result = {
            "bs": bs_rows,
            "pl": pl_rows,
            "cfs": cfs_rows,
            "products_wholesale": products_ws,
            "products_retail": products_rt,
            "products_gas_distr": products_gd,
            "opex": opex_rows,
            "borrowings": borrowings,
            "receivables": receivables,
            "payables": payables,
            "prepayments": prepayments,
            "summary": {
                "total_revenue_usd_k": self._to_usd_k(revenue_gel),
                "total_cogs_usd_k": self._to_usd_k(cogs_gel),
                "gross_profit_usd_k": self._to_usd_k(gp_gel),
                "operating_profit_usd_k": self._to_usd_k(op_gel),
                "net_income_usd_k": self._to_usd_k(net_income_gel),
                "ebitda_usd_k": self._to_usd_k(ebitda_gel),
                "exchange_rate": self.rate,
                "currency": "USD",
                "unit": "thousands",
            }
        }

        # Enrich with prior year and budget/plan data if available
        if self._prior_values or self._budget_values:
            result = self.enrich_with_prior_and_budget(result)

        return result

    # ════════════════════════════════════════════════════════════════
    # Multi-Period Enrichment (Prior Year + Budget/Plan + Deviations)
    # ════════════════════════════════════════════════════════════════

    def enrich_with_prior_and_budget(self, sections: dict) -> dict:
        """Fill prev_year_usd_k, plan_usd_k, deviation_abs, deviation_pct on all section rows.

        Called after populate_all() builds all sections. Iterates every row across
        BS, P&L, CFS, Products, and OPEX sections and enriches with:
          - Prior year values (from a second MREngine run on prior-year dataset)
          - Budget/Plan values (from BudgetLine records mapped to MR codes)
          - Deviation = actual - baseline (plan if available, else prior year)
          - Deviation % = deviation / |baseline| * 100
        """
        ENRICHABLE_SECTIONS = [
            "bs", "pl", "cfs",
            "products_wholesale", "products_retail", "products_gas_distr",
            "opex",
        ]

        for section_key in ENRICHABLE_SECTIONS:
            rows = sections.get(section_key, [])
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue
                code = row.get("code", "")
                actual = row.get("actual_usd_k", 0.0) or 0.0

                # ── Prior year ────────────────────────────────────
                if code and code in self._prior_values:
                    row["prev_year_usd_k"] = self._prior_values[code]

                # ── Budget/Plan ───────────────────────────────────
                if code and code in self._budget_values:
                    plan_gel = self._budget_values[code]
                    row["plan_usd_k"] = self._to_usd_k(plan_gel)

                # ── Deviations ────────────────────────────────────
                # Primary: actual vs plan. Fallback: actual vs prior year.
                plan = row.get("plan_usd_k", 0.0) or 0.0
                prior = row.get("prev_year_usd_k", 0.0) or 0.0

                baseline = plan if plan != 0 else prior
                if baseline != 0:
                    deviation = round(actual - baseline, 1)
                    row["deviation_abs"] = deviation
                    row["deviation_pct"] = round(deviation / abs(baseline) * 100, 1)

        logger.info(
            f"MR enrichment: {len(self._prior_values)} prior year codes, "
            f"{len(self._budget_values)} budget codes applied"
        )
        return sections

    # ════════════════════════════════════════════════════════════════
    # Helpers
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _make_row(tmpl: dict) -> dict:
        """Create a populated row dict from a template entry."""
        return {
            "code": tmpl.get("code", ""),
            "line": tmpl.get("line", ""),
            "sign": tmpl.get("sign", ""),
            "bold": tmpl.get("bold", False),
            "level": tmpl.get("level", 0),
            "actual_gel": 0.0,
            "actual_usd_k": 0.0,
            "opening_gel": 0.0,
            "opening_usd_k": 0.0,
            "prev_year_usd_k": 0.0,
            "plan_usd_k": 0.0,
            "deviation_abs": 0.0,
            "deviation_pct": 0.0,
        }

    @staticmethod
    def _find_tmpl(template: list, code: str) -> dict:
        """Find template entry by code."""
        for t in template:
            if t.get("code") == code:
                return t
        return {}


def enrich_with_account_names(rows: list[dict], tb_items) -> list[dict]:
    """Post-process TB extract rows to add account names from TB items."""
    name_map: dict[str, str] = {}
    for item in tb_items:
        code = (item.account_code or "").strip()
        if code and item.account_name:
            name_map[code] = item.account_name

    for row in rows:
        acct = row.get("account_code", "")
        if acct and acct in name_map and row.get("line") == acct:
            row["line"] = f"{acct} — {name_map[acct]}"

    return rows
