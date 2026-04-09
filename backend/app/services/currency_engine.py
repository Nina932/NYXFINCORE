"""
Phase O-2: Multi-Currency Engine
===================================
Handles currency conversion with:
  - Default exchange rates (GEL, USD, EUR, GBP, TRY, RUB, AZN)
  - Historical rate storage
  - Multi-currency journal entries
  - FX revaluation entries
  - NBG (National Bank of Georgia) API integration with 1-hour cache
  - IAS 21 translation support

All conversions use deterministic Decimal math.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Rate = how many GEL per 1 unit of foreign currency
_DEFAULT_RATES: Dict[str, Decimal] = {
    "GEL": Decimal("1.0000"),
    "USD": Decimal("2.7200"),
    "EUR": Decimal("2.9500"),
    "GBP": Decimal("3.4500"),
    "TRY": Decimal("0.0830"),
    "RUB": Decimal("0.0280"),
    "AZN": Decimal("1.6000"),
}

SUPPORTED_CURRENCIES = list(_DEFAULT_RATES.keys())

# NBG API base URL
_NBG_API_URL = "https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies/"
_NBG_CURRENCIES = "USD,EUR,GBP,TRY,RUB,AZN"

# Cache TTL: 1 hour (3600 seconds)
_CACHE_TTL_SECONDS = 3600


class _RateCache:
    """In-memory rate cache with TTL."""

    def __init__(self, ttl: int = _CACHE_TTL_SECONDS):
        self._ttl = ttl
        self._cache: Dict[str, Tuple[Dict[str, Decimal], float]] = {}  # date_key -> (rates, timestamp)

    def get(self, date_key: str) -> Optional[Dict[str, Decimal]]:
        """Get cached rates if still valid."""
        entry = self._cache.get(date_key)
        if entry is None:
            return None
        rates, cached_at = entry
        if time.time() - cached_at > self._ttl:
            del self._cache[date_key]
            return None
        return rates

    def set(self, date_key: str, rates: Dict[str, Decimal]):
        """Cache rates with current timestamp."""
        self._cache[date_key] = (rates, time.time())

    def clear(self):
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class CurrencyEngine:
    """
    Multi-currency conversion engine.

    Base currency: GEL (Georgian Lari).
    All rates stored as "GEL per 1 unit of foreign currency".
    Supports 7 currencies: GEL, USD, EUR, GBP, TRY, RUB, AZN.
    """

    def __init__(self, base_currency: str = "GEL"):
        self.base_currency = base_currency
        self._current_rates: Dict[str, Decimal] = dict(_DEFAULT_RATES)
        self._historical_rates: Dict[str, Dict[str, Decimal]] = {}  # date -> {currency -> rate}
        self._cache = _RateCache()

    def set_rate(self, currency: str, rate: float, date: Optional[str] = None):
        """
        Set exchange rate.

        Args:
            currency: Currency code (USD, EUR, GBP, TRY, RUB, AZN)
            rate: How many GEL per 1 unit of currency
            date: Optional date for historical rate
        """
        rate_d = Decimal(str(rate))
        self._current_rates[currency] = rate_d

        if date:
            if date not in self._historical_rates:
                self._historical_rates[date] = {}
            self._historical_rates[date][currency] = rate_d

        logger.info("Rate set: 1 %s = %s GEL%s", currency, rate_d,
                     f" (date={date})" if date else "")

    def get_rate(self, from_ccy: str, to_ccy: str, date: Optional[str] = None) -> Decimal:
        """
        Get exchange rate from one currency to another.

        Args:
            from_ccy: Source currency
            to_ccy: Target currency
            date: Optional date for historical rate (YYYY-MM-DD)

        Returns:
            Rate (multiply source amount by this to get target amount)
        """
        if from_ccy == to_ccy:
            return Decimal("1.0000")

        # Get rates vs base currency
        from_rate = self._get_base_rate(from_ccy, date)
        to_rate = self._get_base_rate(to_ccy, date)

        if to_rate == 0:
            raise ValueError(f"Zero rate for {to_ccy}")

        # Cross rate: from -> base -> to
        return (from_rate / to_rate).quantize(Decimal("0.0001"), ROUND_HALF_UP)

    def _get_base_rate(self, currency: str, date: Optional[str] = None) -> Decimal:
        """Get rate vs base currency (GEL)."""
        if currency == self.base_currency:
            return Decimal("1.0000")

        # Try historical first
        if date and date in self._historical_rates:
            rate = self._historical_rates[date].get(currency)
            if rate is not None:
                return rate

        # Try cache (from NBG API)
        if date:
            cached = self._cache.get(date)
            if cached and currency in cached:
                return cached[currency]

        # Fall back to current rate
        rate = self._current_rates.get(currency)
        if rate is None:
            raise ValueError(f"No rate available for {currency}")
        return rate

    def convert(
        self,
        amount: float,
        from_ccy: str,
        to_ccy: str,
        date: Optional[str] = None,
    ) -> Decimal:
        """
        Convert amount from one currency to another.

        Returns:
            Converted amount as Decimal (rounded to 2 places)
        """
        if from_ccy == to_ccy:
            return Decimal(str(amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)

        rate = self.get_rate(from_ccy, to_ccy, date)
        result = Decimal(str(amount)) * rate
        return result.quantize(Decimal("0.01"), ROUND_HALF_UP)

    def convert_to_base(self, amount: float, currency: str, date: Optional[str] = None) -> Decimal:
        """Convert to base currency (GEL)."""
        return self.convert(amount, currency, self.base_currency, date)

    def revalue_balance(
        self,
        amount: float,
        currency: str,
        book_rate_date: str,
        revalue_date: str,
    ) -> Dict[str, Any]:
        """
        Calculate FX revaluation gain/loss.

        Args:
            amount: Foreign currency balance
            currency: Foreign currency code
            book_rate_date: Date when balance was recorded
            revalue_date: Date for revaluation

        Returns:
            Dict with book_value, revalued_value, gain_loss
        """
        book_value = self.convert_to_base(amount, currency, book_rate_date)
        revalue_value = self.convert_to_base(amount, currency, revalue_date)
        gain_loss = revalue_value - book_value

        return {
            "currency": currency,
            "foreign_amount": amount,
            "book_rate_date": book_rate_date,
            "revalue_date": revalue_date,
            "book_value_gel": float(book_value),
            "revalued_value_gel": float(revalue_value),
            "fx_gain_loss_gel": float(gain_loss),
            "is_gain": gain_loss > 0,
        }

    def get_all_rates(self) -> Dict[str, float]:
        """Get all current rates."""
        return {k: float(v) for k, v in self._current_rates.items()}

    def get_supported_currencies(self) -> List[str]:
        """Get list of supported currencies."""
        return list(self._current_rates.keys())

    async def fetch_rates_nbg(self, date: Optional[str] = None) -> Dict[str, float]:
        """
        Fetch exchange rates from the National Bank of Georgia API.

        Args:
            date: Date string YYYY-MM-DD (defaults to today)

        Returns:
            Dict of {currency: rate_in_GEL}
        """
        import httpx

        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Check cache first
        cached = self._cache.get(date)
        if cached:
            logger.debug("NBG rates for %s served from cache", date)
            return {k: float(v) for k, v in cached.items()}

        url = f"{_NBG_API_URL}?currencies={_NBG_CURRENCIES}&date={date}"
        fetched_rates: Dict[str, Decimal] = {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                # NBG API returns: [{"currencies": [{"code": "USD", "rate": 2.72, "quantity": 1, ...}]}]
                if isinstance(data, list) and len(data) > 0:
                    currencies_list = data[0].get("currencies", [])
                    for entry in currencies_list:
                        code = entry.get("code", "").upper()
                        rate = entry.get("rate")
                        quantity = entry.get("quantity", 1)
                        if code and rate is not None:
                            # NBG gives rate per `quantity` units, normalize to 1 unit
                            rate_per_unit = Decimal(str(rate)) / Decimal(str(quantity))
                            fetched_rates[code] = rate_per_unit

            if fetched_rates:
                # Update current rates
                for code, rate_d in fetched_rates.items():
                    self._current_rates[code] = rate_d

                # Store in historical
                if date not in self._historical_rates:
                    self._historical_rates[date] = {}
                self._historical_rates[date].update(fetched_rates)

                # Cache with TTL
                self._cache.set(date, fetched_rates)

                logger.info("NBG rates fetched for %s: %d currencies", date, len(fetched_rates))
            else:
                logger.warning("NBG API returned no currency data for %s", date)

        except Exception as e:
            logger.warning("NBG API fetch failed for %s: %s (using defaults)", date, e)

        # Always return something (fetched or defaults)
        result = {k: float(v) for k, v in self._current_rates.items() if k != "GEL"}
        return result

    def translate_ias21(
        self,
        amounts: Dict[str, float],
        from_currency: str,
        to_currency: str,
        closing_rate: Optional[float] = None,
        average_rate: Optional[float] = None,
        historical_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        IAS 21 translation method for consolidation.

        Uses:
          - Closing rate for balance sheet items
          - Average rate for income statement items
          - Historical rate for equity items

        Args:
            amounts: Dict with keys like 'assets', 'liabilities', 'equity', 'revenue', 'expenses'
            from_currency: Source currency
            to_currency: Target currency (typically GEL)
            closing_rate: Closing rate override (default: current rate)
            average_rate: Period average rate override
            historical_rate: Historical equity rate override

        Returns:
            Translated amounts + translation difference
        """
        # Default to current rate if not provided
        current_rate = float(self.get_rate(from_currency, to_currency))
        c_rate = closing_rate or current_rate
        a_rate = average_rate or current_rate
        h_rate = historical_rate or current_rate

        translated = {}
        # Balance sheet items at closing rate
        for key in ("assets", "total_assets", "liabilities", "total_liabilities",
                     "cash", "receivables", "inventory", "fixed_assets",
                     "payables", "debt", "long_term_debt"):
            if key in amounts:
                translated[key] = round(amounts[key] * c_rate, 2)

        # Income statement items at average rate
        for key in ("revenue", "total_revenue", "expenses", "total_expenses",
                     "cogs", "cost_of_goods_sold", "gross_profit",
                     "operating_income", "net_income", "ebitda",
                     "depreciation", "interest_expense", "tax_expense"):
            if key in amounts:
                translated[key] = round(amounts[key] * a_rate, 2)

        # Equity at historical rate
        for key in ("equity", "total_equity", "share_capital",
                     "retained_earnings", "reserves"):
            if key in amounts:
                translated[key] = round(amounts[key] * h_rate, 2)

        # Calculate translation difference (IAS 21 OCI item)
        bs_total = translated.get("total_assets", 0)
        bs_liab_eq = translated.get("total_liabilities", 0) + translated.get("total_equity", 0)
        translation_difference = round(bs_total - bs_liab_eq, 2) if bs_total and bs_liab_eq else 0.0

        return {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rates_used": {
                "closing_rate": c_rate,
                "average_rate": a_rate,
                "historical_rate": h_rate,
            },
            "translated": translated,
            "translation_difference": translation_difference,
        }

    def reset(self):
        """Reset to default rates."""
        self._current_rates = dict(_DEFAULT_RATES)
        self._historical_rates.clear()
        self._cache.clear()


# Module-level singleton
currency_engine = CurrencyEngine()
