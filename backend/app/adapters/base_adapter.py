"""
Base ERP Adapter — Abstract interface for all ERP system adapters.

Every ERP adapter must implement this interface. This enables:
  - Auto-detection of ERP system from uploaded files
  - Standardized account and transaction parsing
  - IFRS classification specific to each ERP's chart of accounts
  - 2-week adapter creation for new ERP systems

To create a new adapter:
  1. Subclass BaseERPAdapter
  2. Implement all abstract methods
  3. Register via @register_adapter in registry.py
  4. Add tests in tests/unit/test_<system>_adapter.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StandardAccount:
    """Normalized account representation — ERP-agnostic.

    All ERP adapters must map their native accounts to this format.
    """
    code: str
    name_primary: str                     # Primary language name
    name_secondary: str = ""              # Secondary language (e.g. Georgian/Russian)
    account_type: str = ""                # active|passive|active-passive
    normal_balance: str = ""              # debit|credit
    ifrs_section: str = ""                # balance_sheet|income_statement
    ifrs_line: str = ""                   # "Cash & Equivalents", "Revenue", etc.
    bs_side: str = ""                     # asset|liability|equity|income|expense
    bs_sub: str = ""                      # current|noncurrent|equity
    parent_code: Optional[str] = None     # Parent account code (for hierarchy)
    is_group: bool = False                # True if this is a group/summary account
    balance: Optional[Decimal] = None     # Current balance (if available)
    metadata: Dict = field(default_factory=dict)


@dataclass
class StandardTransaction:
    """Normalized transaction — ERP-agnostic double-entry format."""
    date: str                              # ISO format: YYYY-MM-DD
    debit_account: str                     # Account code
    credit_account: str                    # Account code
    amount: Decimal
    description: str = ""
    document_ref: str = ""                 # External reference (invoice #, etc.)
    currency: str = "GEL"
    counterparty: str = ""
    department: str = ""
    metadata: Dict = field(default_factory=dict)


class BaseERPAdapter(ABC):
    """Abstract base class for ERP system adapters.

    Subclass this to add support for a new ERP system.
    See app/adapters/onec_adapter.py for a reference implementation.
    """

    @property
    @abstractmethod
    def system_name(self) -> str:
        """Short identifier: '1c', 'quickbooks', 'sap_b1', 'xero'"""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name: '1C:Enterprise', 'QuickBooks Online'"""

    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """File extensions this adapter can parse: ['.xlsx', '.xml', '.csv']"""

    @abstractmethod
    def detect(self, file_path: Path) -> float:
        """Return confidence 0.0-1.0 that this file is from this ERP system.

        Should examine file structure, headers, encoding, and known patterns
        without fully parsing the file. Must be fast (< 100ms).

        Args:
            file_path: Path to the uploaded file

        Returns:
            Confidence score 0.0 (definitely not) to 1.0 (definitely yes)
        """

    @abstractmethod
    def parse_chart_of_accounts(self, file_path: Path) -> List[StandardAccount]:
        """Parse a COA export into StandardAccount list.

        Args:
            file_path: Path to the COA export file

        Returns:
            List of StandardAccount objects with at minimum code and name_primary
        """

    @abstractmethod
    def parse_transactions(self, file_path: Path) -> List[StandardTransaction]:
        """Parse a transaction export into StandardTransaction list.

        Args:
            file_path: Path to the transaction export file

        Returns:
            List of StandardTransaction objects
        """

    @abstractmethod
    def map_to_ifrs(self, account: StandardAccount) -> StandardAccount:
        """Apply IFRS classification rules specific to this ERP system.

        Takes a StandardAccount with code and name, returns the same account
        enriched with ifrs_section, ifrs_line, bs_side, and bs_sub fields.

        Args:
            account: Account with at minimum code and name_primary

        Returns:
            Same account with IFRS fields populated
        """

    def parse_trial_balance(self, file_path: Path) -> List[StandardAccount]:
        """Parse a trial balance export. Optional — defaults to COA parse.

        Override this if the ERP system has a distinct trial balance format.
        """
        return self.parse_chart_of_accounts(file_path)
