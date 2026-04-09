import pytest
from decimal import Decimal
from app.services.calculation_engine import FinancialDecimal as FD


def test_basic_arithmetic():
    assert FD.add(1.1, 2.2) == Decimal('3.3')
    assert FD.subtract(5.5, 2.25) == Decimal('3.25')
    assert FD.multiply(2.5, 4) == Decimal('10.0')


def test_rounding_and_margin():
    # rounding
    assert FD.round2(Decimal('1.235')) == Decimal('1.24')
    assert FD.round2('2.234') == Decimal('2.23')

    # margin: ((rev - cost) / rev) * 100
    m = FD.margin(200, 50)
    assert isinstance(m, Decimal)
    assert m == Decimal('75.00')


def test_allocate_exactness():
    parts = FD.allocate(100, [1, 1, 1])
    assert sum(parts) == FD.to_decimal(100)
    assert len(parts) == 3
