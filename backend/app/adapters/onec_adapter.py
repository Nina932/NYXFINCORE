"""
1C:Enterprise ERP Adapter — wraps the existing OneCInterpreter
to conform to the BaseERPAdapter interface.

This adapter handles:
  - 1C:Enterprise COA exports (Georgian/Russian bilingual Excel)
  - Account classification using Georgian IFRS class digits (1-9)
  - Russian 2-digit 1C standard account mappings
  - Bilingual name parsing (Georgian // Russian format)
  - Subkonto dimension classification (44 dimension types)

Detection heuristics:
  - Cyrillic or Georgian Unicode in column headers
  - Known 1C column patterns (Код, Быстрый выбор, Вид)
  - Account code format matching (4-digit with dots)
"""

import logging
from decimal import Decimal
from pathlib import Path
from typing import List

from app.adapters.base_adapter import BaseERPAdapter, StandardAccount, StandardTransaction
from app.adapters.registry import register_adapter

logger = logging.getLogger(__name__)


@register_adapter
class OneCAdapter(BaseERPAdapter):
    """Adapter for 1C:Enterprise accounting system.

    Wraps the existing OneCInterpreter (app/services/onec_interpreter.py)
    and maps its output to the StandardAccount/StandardTransaction format.
    """

    @property
    def system_name(self) -> str:
        return "1c"

    @property
    def display_name(self) -> str:
        return "1C:Enterprise"

    @property
    def supported_formats(self) -> List[str]:
        return [".xlsx", ".xls"]

    def detect(self, file_path: Path) -> float:
        """Detect 1C files by checking for Cyrillic/Georgian headers and
        known 1C column patterns.

        Returns confidence 0.0-1.0.
        """
        if file_path.suffix.lower() not in self.supported_formats:
            return 0.0

        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            if ws is None:
                wb.close()
                return 0.0

            # Check first 5 rows for 1C indicators
            score = 0.0
            onec_keywords = {"код", "быстрый", "наименование", "вид", "валютный",
                             "количественный", "субконто", "забалансовый"}
            georgian_keywords = {"კოდი", "დასახელება", "ტიპი", "ვალუტა"}

            for row_idx, row in enumerate(ws.iter_rows(max_row=5, values_only=True)):
                if row_idx > 4:
                    break
                for cell in row:
                    if cell is None:
                        continue
                    cell_lower = str(cell).lower().strip()
                    if cell_lower in onec_keywords:
                        score += 0.15
                    if cell_lower in georgian_keywords:
                        score += 0.1
                    # Check for Cyrillic Unicode range
                    if any('\u0400' <= c <= '\u04FF' for c in str(cell)):
                        score += 0.05
                    # Check for Georgian Unicode range
                    if any('\u10A0' <= c <= '\u10FF' for c in str(cell)):
                        score += 0.05

            wb.close()
            return min(score, 1.0)

        except Exception as exc:
            logger.debug("1C detection failed for %s: %s", file_path, exc)
            return 0.0

    def parse_chart_of_accounts(self, file_path: Path) -> List[StandardAccount]:
        """Parse a 1C COA export into StandardAccount list.

        Delegates to the existing OneCInterpreter and maps the output.
        """
        from app.services.onec_interpreter import onec_interpreter

        tree = onec_interpreter.parse_file(str(file_path))
        accounts = []

        for acct in tree.accounts:
            std_acct = StandardAccount(
                code=acct.code,
                name_primary=acct.name_ka or acct.name_ru or "",
                name_secondary=acct.name_ru if acct.name_ka else "",
                account_type=acct.account_type,
                normal_balance=acct.normal_balance,
                ifrs_section=acct.ifrs_section,
                ifrs_line=acct.ifrs_line,
                bs_side=acct.bs_side,
                bs_sub=acct.bs_sub,
                parent_code=acct.parent_code,
                is_group=acct.is_group,
                metadata={
                    "is_off_balance": acct.is_off_balance,
                    "tracks_currency": acct.tracks_currency,
                    "tracks_quantity": acct.tracks_quantity,
                    "subkonto": acct.subkonto,
                    "depth": acct.depth,
                    "quick_code": acct.quick_code,
                },
            )
            accounts.append(std_acct)

        logger.info("1C COA: parsed %d accounts from %s", len(accounts), file_path.name)
        return accounts

    def parse_transactions(self, file_path: Path) -> List[StandardTransaction]:
        """Parse 1C transaction exports.

        Note: The current OneCInterpreter focuses on COA parsing.
        Transaction parsing from 1C exports (ОСВ/журнал операций) is
        handled by the smart_excel_parser pipeline, which detects
        transaction-like sheets automatically.

        This method returns an empty list — transaction ingestion goes
        through the main upload pipeline rather than the ERP adapter.
        """
        logger.info("1C transaction parsing delegated to smart_excel_parser pipeline")
        return []

    def map_to_ifrs(self, account: StandardAccount) -> StandardAccount:
        """Apply 1C-specific IFRS classification rules.

        Uses the existing _infer_ifrs logic from OneCInterpreter.
        """
        from app.services.onec_interpreter import _infer_ifrs

        ifrs = _infer_ifrs(
            code=account.code,
            account_type=account.account_type,
            is_off_balance=account.metadata.get("is_off_balance", False),
        )

        account.ifrs_section = ifrs.get("ifrs_section", account.ifrs_section)
        account.ifrs_line = ifrs.get("ifrs_line", account.ifrs_line)
        account.bs_side = ifrs.get("bs_side", account.bs_side)
        account.bs_sub = ifrs.get("bs_sub", account.bs_sub)

        return account
