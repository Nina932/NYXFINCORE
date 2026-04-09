"""
currency_service.py — Multi-currency conversion service with live exchange rates.

Base currency: GEL (Georgian Lari).
Supports live rate fetching from open.er-api.com, database caching,
fallback rates, and triangulation through USD when direct rates are unavailable.
"""

import httpx
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.all_models import ExchangeRate
from app.config import settings

logger = logging.getLogger(__name__)


class CurrencyService:
    """
    Production-grade multi-currency service for the FinAI financial platform.

    Provides exchange rate fetching, caching, conversion, historical tracking,
    and automatic fallback with triangulation when direct rates are unavailable.
    """

    SUPPORTED_CURRENCIES = ["GEL", "USD", "EUR", "GBP", "TRY"]

    # Maximum age (in days) before a fallback rate triggers a warning.
    # Consolidated statements using rates older than this are flagged.
    FALLBACK_STALENESS_DAYS = 30

    # Fallback rates if API unavailable (approximate mid-2025).
    # WARNING: These are static and become increasingly inaccurate over time.
    # Any consolidated statement generated using fallback rates should be flagged.
    FALLBACK_RATES_DATE = "2025-06-01"
    FALLBACK_RATES = {
        ("GEL", "USD"): 0.37, ("USD", "GEL"): 2.70,
        ("GEL", "EUR"): 0.34, ("EUR", "GEL"): 2.95,
        ("GEL", "GBP"): 0.29, ("GBP", "GEL"): 3.45,
        ("GEL", "TRY"): 12.0, ("TRY", "GEL"): 0.083,
        ("USD", "EUR"): 0.92, ("EUR", "USD"): 1.09,
        ("USD", "GBP"): 0.79, ("GBP", "USD"): 1.27,
        ("USD", "TRY"): 32.5, ("TRY", "USD"): 0.031,
        ("EUR", "GBP"): 0.86, ("GBP", "EUR"): 1.16,
        ("EUR", "TRY"): 35.4, ("TRY", "EUR"): 0.028,
        ("GBP", "TRY"): 41.2, ("TRY", "GBP"): 0.024,
    }

    async def fetch_rates(self, base: str = "USD") -> Optional[Dict[str, float]]:
        """
        Fetch live exchange rates from an external API.

        Uses the configured EXCHANGE_RATE_API_URL if available in settings,
        otherwise falls back to the free open.er-api.com endpoint.

        Args:
            base: The base currency code (e.g. "USD", "EUR").

        Returns:
            A dict mapping currency codes to their rates relative to the base,
            or None if the request fails.
        """
        custom_url = getattr(settings, "EXCHANGE_RATE_API_URL", None)
        if custom_url:
            url = f"{custom_url.rstrip('/')}/{base}"
        else:
            url = f"https://open.er-api.com/v6/latest/{base}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            if data.get("result") == "error":
                logger.warning(
                    "Exchange rate API returned error for base=%s: %s",
                    base, data.get("error-type", "unknown"),
                )
                return None

            rates = data.get("rates")
            if not rates:
                logger.warning(
                    "Exchange rate API returned no rates for base=%s", base,
                )
                return None

            logger.info(
                "Fetched %d exchange rates for base=%s from %s",
                len(rates), base, url,
            )
            return rates

        except httpx.TimeoutException:
            logger.warning(
                "Exchange rate API request timed out for base=%s (url=%s)",
                base, url,
            )
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Exchange rate API HTTP error for base=%s: %s %s",
                base, exc.response.status_code, exc.response.reason_phrase,
            )
            return None
        except Exception as exc:
            logger.warning(
                "Exchange rate API request failed for base=%s: %s", base, exc,
            )
            return None

    async def store_rates(
        self,
        db: AsyncSession,
        rates: Dict[str, float],
        base: str = "USD",
        source: str = "api",
    ) -> int:
        """
        Persist fetched exchange rates into the ExchangeRate table.

        Creates one record per base/target currency pair for today's date.
        Skips pairs that already exist for the same date to avoid duplicates.

        Args:
            db: The async database session.
            rates: Dict of {currency_code: rate} relative to the base.
            base: The base currency code the rates are denominated in.
            source: Label for where the rates came from (e.g. "api", "fallback").

        Returns:
            The number of new rate records stored.
        """
        today = date.today().isoformat()
        stored_count = 0

        for currency_code, rate_value in rates.items():
            currency_code_upper = currency_code.upper()

            # Only store rates for our supported currencies
            if currency_code_upper not in self.SUPPORTED_CURRENCIES:
                continue

            # Skip identity pair
            if currency_code_upper == base.upper():
                continue

            try:
                # Check if this pair + date already exists
                existing = await db.execute(
                    select(ExchangeRate).where(
                        and_(
                            ExchangeRate.from_currency == base.upper(),
                            ExchangeRate.to_currency == currency_code_upper,
                            ExchangeRate.rate_date == today,
                        )
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                record = ExchangeRate(
                    from_currency=base.upper(),
                    to_currency=currency_code_upper,
                    rate=round(rate_value, 6),
                    rate_date=today,
                    source=source,
                )
                db.add(record)
                stored_count += 1

            except Exception as exc:
                logger.error(
                    "Failed to store rate %s->%s: %s",
                    base, currency_code_upper, exc,
                )

        if stored_count > 0:
            try:
                await db.commit()
                logger.info(
                    "Stored %d exchange rates for base=%s date=%s",
                    stored_count, base, today,
                )
            except Exception as exc:
                await db.rollback()
                logger.error("Failed to commit exchange rates: %s", exc)
                stored_count = 0

        return stored_count

    async def get_rate(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
        rate_date: date = None,
    ) -> float:
        """
        Get the exchange rate between two currencies.

        Resolution order:
        1. If from == to, return 1.0 immediately.
        2. Check the database for a stored rate (exact date or latest available).
        3. If not in DB, fetch live rates from the API and store them.
        4. If the API fails, use hardcoded FALLBACK_RATES.
        5. If no direct rate exists, attempt triangulation through USD.

        Args:
            db: The async database session.
            from_currency: Source currency code (e.g. "GEL").
            to_currency: Target currency code (e.g. "USD").
            rate_date: Optional specific date; defaults to today if None.

        Returns:
            The exchange rate as a float. Falls back to 1.0 only as a
            last resort if no rate can be determined at all.
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Identity
        if from_currency == to_currency:
            return 1.0

        # Step 1: Check database
        db_rate = await self._get_rate_from_db(db, from_currency, to_currency, rate_date)
        if db_rate is not None:
            return db_rate

        # Step 2: Try to fetch live rates and store them
        try:
            rates = await self.fetch_rates(base=from_currency)
            if rates:
                await self.store_rates(db, rates, base=from_currency, source="api")
                target_rate = rates.get(to_currency) or rates.get(to_currency.lower())
                if target_rate is not None:
                    return round(float(target_rate), 6)
        except Exception as exc:
            logger.warning("Live rate fetch failed for %s->%s: %s", from_currency, to_currency, exc)

        # Step 3: Use fallback rates (with staleness warning)
        fallback = self.FALLBACK_RATES.get((from_currency, to_currency))
        if fallback is not None:
            days_stale = (date.today() - date.fromisoformat(self.FALLBACK_RATES_DATE)).days
            if days_stale > self.FALLBACK_STALENESS_DAYS:
                logger.warning(
                    "STALE EXCHANGE RATE: Using fallback rate for %s->%s (%.4f) "
                    "from %s — %d days old. Consolidated statements using this rate "
                    "may be materially inaccurate. Configure EXCHANGE_RATE_API_URL "
                    "or ensure internet access for live rates.",
                    from_currency, to_currency, fallback,
                    self.FALLBACK_RATES_DATE, days_stale,
                )
            else:
                logger.info(
                    "Using fallback rate for %s->%s: %s (from %s)",
                    from_currency, to_currency, fallback, self.FALLBACK_RATES_DATE,
                )
            return fallback

        # Step 4: Triangulation through USD
        rate = await self._triangulate_through_usd(db, from_currency, to_currency)
        if rate is not None:
            return rate

        # Last resort — should not happen for supported currencies
        logger.error(
            "No exchange rate found for %s->%s; returning 1.0 as last resort",
            from_currency, to_currency,
        )
        return 1.0

    async def _get_rate_from_db(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
        rate_date: date = None,
    ) -> Optional[float]:
        """
        Look up a rate from the ExchangeRate table.

        If rate_date is provided, searches for that exact date.
        Otherwise, retrieves the most recent rate for the pair.

        Args:
            db: The async database session.
            from_currency: Source currency code.
            to_currency: Target currency code.
            rate_date: Optional specific date to look up.

        Returns:
            The rate as a float, or None if not found.
        """
        try:
            if rate_date is not None:
                date_str = rate_date.isoformat() if isinstance(rate_date, date) else str(rate_date)
                stmt = (
                    select(ExchangeRate)
                    .where(
                        and_(
                            ExchangeRate.from_currency == from_currency,
                            ExchangeRate.to_currency == to_currency,
                            ExchangeRate.rate_date == date_str,
                        )
                    )
                    .limit(1)
                )
            else:
                # Get the most recent rate for this pair
                stmt = (
                    select(ExchangeRate)
                    .where(
                        and_(
                            ExchangeRate.from_currency == from_currency,
                            ExchangeRate.to_currency == to_currency,
                        )
                    )
                    .order_by(ExchangeRate.rate_date.desc())
                    .limit(1)
                )

            result = await db.execute(stmt)
            record = result.scalar_one_or_none()

            if record is not None:
                return float(record.rate)

            # Also check the inverse pair and compute reciprocal
            if rate_date is not None:
                date_str = rate_date.isoformat() if isinstance(rate_date, date) else str(rate_date)
                inverse_stmt = (
                    select(ExchangeRate)
                    .where(
                        and_(
                            ExchangeRate.from_currency == to_currency,
                            ExchangeRate.to_currency == from_currency,
                            ExchangeRate.rate_date == date_str,
                        )
                    )
                    .limit(1)
                )
            else:
                inverse_stmt = (
                    select(ExchangeRate)
                    .where(
                        and_(
                            ExchangeRate.from_currency == to_currency,
                            ExchangeRate.to_currency == from_currency,
                        )
                    )
                    .order_by(ExchangeRate.rate_date.desc())
                    .limit(1)
                )

            inverse_result = await db.execute(inverse_stmt)
            inverse_record = inverse_result.scalar_one_or_none()

            if inverse_record is not None and float(inverse_record.rate) != 0:
                return round(1.0 / float(inverse_record.rate), 6)

        except Exception as exc:
            logger.error(
                "DB lookup failed for %s->%s: %s", from_currency, to_currency, exc,
            )

        return None

    async def _triangulate_through_usd(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
    ) -> Optional[float]:
        """
        Compute a cross rate by triangulating through USD.

        Calculates: from_currency -> USD -> to_currency.

        Args:
            db: The async database session.
            from_currency: Source currency code.
            to_currency: Target currency code.

        Returns:
            The triangulated rate, or None if either leg is unavailable.
        """
        if from_currency == "USD" or to_currency == "USD":
            # One leg is already USD; triangulation won't help
            return None

        logger.info(
            "Attempting triangulation %s -> USD -> %s",
            from_currency, to_currency,
        )

        # Leg 1: from_currency -> USD
        from_to_usd = self.FALLBACK_RATES.get((from_currency, "USD"))
        if from_to_usd is None:
            # Try DB
            from_to_usd = await self._get_rate_from_db(db, from_currency, "USD")

        # Leg 2: USD -> to_currency
        usd_to_target = self.FALLBACK_RATES.get(("USD", to_currency))
        if usd_to_target is None:
            usd_to_target = await self._get_rate_from_db(db, "USD", to_currency)

        if from_to_usd is not None and usd_to_target is not None:
            triangulated_rate = round(from_to_usd * usd_to_target, 6)
            logger.info(
                "Triangulated rate %s->%s: %s * %s = %s",
                from_currency, to_currency,
                from_to_usd, usd_to_target, triangulated_rate,
            )
            return triangulated_rate

        return None

    async def convert(
        self,
        db: AsyncSession,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: date = None,
    ) -> Dict:
        """
        Convert an amount from one currency to another.

        Args:
            db: The async database session.
            amount: The monetary amount to convert.
            from_currency: Source currency code (e.g. "GEL").
            to_currency: Target currency code (e.g. "USD").
            rate_date: Optional date for the conversion rate.

        Returns:
            A dict containing:
                - original_amount: The input amount.
                - original_currency: The source currency.
                - converted_amount: The result rounded to 2 decimal places.
                - target_currency: The target currency.
                - rate: The exchange rate used.
                - rate_date: The date of the rate.
                - source: Where the rate came from.
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        effective_date = rate_date or date.today()

        rate = await self.get_rate(db, from_currency, to_currency, rate_date)
        converted_amount = round(amount * rate, 2)

        # Determine source by checking DB first
        source = "calculated"
        try:
            date_str = effective_date.isoformat() if isinstance(effective_date, date) else str(effective_date)
            result = await db.execute(
                select(ExchangeRate.source)
                .where(
                    and_(
                        ExchangeRate.from_currency == from_currency,
                        ExchangeRate.to_currency == to_currency,
                        ExchangeRate.rate_date == date_str,
                    )
                )
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                source = row
            elif (from_currency, to_currency) in self.FALLBACK_RATES:
                source = "fallback"
        except Exception:
            pass

        if from_currency == to_currency:
            source = "identity"

        # Add staleness warning if fallback rates were used
        warnings = []
        if source == "fallback":
            days_stale = (date.today() - date.fromisoformat(self.FALLBACK_RATES_DATE)).days
            if days_stale > self.FALLBACK_STALENESS_DAYS:
                warnings.append(
                    f"Exchange rate is from static fallback data ({self.FALLBACK_RATES_DATE}, "
                    f"{days_stale} days old). This rate may be materially inaccurate. "
                    f"Consolidated financial statements using this rate should not be "
                    f"relied upon for audit or compliance purposes."
                )

        result = {
            "original_amount": round(amount, 2),
            "original_currency": from_currency,
            "converted_amount": converted_amount,
            "target_currency": to_currency,
            "rate": rate,
            "rate_date": effective_date.isoformat() if isinstance(effective_date, date) else str(effective_date),
            "source": source,
        }
        if warnings:
            result["warnings"] = warnings
        return result

    async def get_rate_history(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
        days: int = 30,
    ) -> List[Dict]:
        """
        Retrieve historical exchange rates for a currency pair.

        Queries the ExchangeRate table for the specified pair within the
        given number of past days.

        Args:
            db: The async database session.
            from_currency: Source currency code.
            to_currency: Target currency code.
            days: Number of days of history to retrieve (default 30).

        Returns:
            A list of dicts [{date, rate, source}, ...] ordered by date ascending.
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        start_date = (date.today() - timedelta(days=days)).isoformat()

        try:
            stmt = (
                select(ExchangeRate)
                .where(
                    and_(
                        ExchangeRate.from_currency == from_currency,
                        ExchangeRate.to_currency == to_currency,
                        ExchangeRate.rate_date >= start_date,
                    )
                )
                .order_by(ExchangeRate.rate_date.asc())
            )

            result = await db.execute(stmt)
            records = result.scalars().all()

            history = [
                {
                    "date": record.rate_date,
                    "rate": round(float(record.rate), 6),
                    "source": record.source,
                }
                for record in records
            ]

            logger.info(
                "Retrieved %d historical rates for %s->%s over %d days",
                len(history), from_currency, to_currency, days,
            )
            return history

        except Exception as exc:
            logger.error(
                "Failed to retrieve rate history for %s->%s: %s",
                from_currency, to_currency, exc,
            )
            return []

    async def refresh_all_rates(self, db: AsyncSession) -> Dict:
        """
        Fetch and store the latest rates for all supported currency pairs.

        Fetches rates with USD as base, then computes and stores cross-rates
        between all supported currencies.

        Args:
            db: The async database session.

        Returns:
            A dict with:
                - updated: Total number of new rates stored.
                - timestamp: ISO timestamp of the refresh.
        """
        total_stored = 0
        today = date.today().isoformat()

        # Fetch rates for multiple bases to get all cross pairs
        fetched_bases: Dict[str, Dict[str, float]] = {}

        for base in self.SUPPORTED_CURRENCIES:
            rates = await self.fetch_rates(base=base)
            if rates:
                fetched_bases[base] = rates
                stored = await self.store_rates(db, rates, base=base, source="api")
                total_stored += stored
            else:
                logger.warning("Could not fetch rates for base=%s", base)

        # If we could not fetch any live data, store fallback rates
        if not fetched_bases:
            logger.warning("All API fetches failed; storing fallback rates")
            for (from_cur, to_cur), rate in self.FALLBACK_RATES.items():
                try:
                    # Check for existing record
                    existing = await db.execute(
                        select(ExchangeRate).where(
                            and_(
                                ExchangeRate.from_currency == from_cur,
                                ExchangeRate.to_currency == to_cur,
                                ExchangeRate.rate_date == today,
                            )
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        continue

                    record = ExchangeRate(
                        from_currency=from_cur,
                        to_currency=to_cur,
                        rate=rate,
                        rate_date=today,
                        source="fallback",
                    )
                    db.add(record)
                    total_stored += 1
                except Exception as exc:
                    logger.error(
                        "Failed to store fallback rate %s->%s: %s",
                        from_cur, to_cur, exc,
                    )

            if total_stored > 0:
                try:
                    await db.commit()
                except Exception as exc:
                    await db.rollback()
                    logger.error("Failed to commit fallback rates: %s", exc)
                    total_stored = 0

        timestamp = datetime.utcnow().isoformat()
        logger.info(
            "Rate refresh complete: %d rates updated at %s",
            total_stored, timestamp,
        )

        return {
            "updated": total_stored,
            "timestamp": timestamp,
        }
