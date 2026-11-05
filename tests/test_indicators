"""Tests για τους τεχνικούς δείκτες."""

import math

import pytest

from sol_trade.indicators import ema, rsi, sma, volatility_pct


def test_sma_basic():
    values = [1, 2, 3, 4, 5]
    out = sma(values, 3)
    assert out[0] is None and out[1] is None
    assert math.isclose(out[2], 2.0)
    assert math.isclose(out[3], 3.0)
    assert math.isclose(out[4], 4.0)


def test_ema_converges_to_price():
    # Σταθερή τιμή -> η EMA τείνει στην ίδια τιμή (seed στο index period-1)
    values = [10.0] * 50
    out = ema(values, 12)
    assert out[11] == pytest.approx(10.0)  # seed = SMA των 12 πρώτων
    assert out[-1] == pytest.approx(10.0)


def test_ema_responds_to_change():
    values = [10.0] * 30 + [20.0] * 30
    out = ema(values, 5)
    assert out[-1] > 18.0  # έχει κινηθεί προς το 20
    assert out[-1] < 20.0  # αλλά δεν το έχει φτάσει


def test_rsi_all_up_is_100():
    values = [float(i) for i in range(1, 40)]  # συνεχής άνοδος
    out = rsi(values, 14)
    assert out[-1] == 100.0


def test_rsi_all_down_is_low():
    values = [float(100 - i) for i in range(1, 40)]  # συνεχής πτώση
    out = rsi(values, 14)
    assert out[-1] == 0.0


def test_rsi_range_bounds():
    values = [100.0]
    for _ in range(60):
        values.append(values[-1] * (1 + ((-1) ** len(values)) * 0.01))
    out = rsi(values, 14)
    for v in out:
        if v is not None:
            assert 0.0 <= v <= 100.0


def test_volatility_flat_is_zero():
    values = [50.0] * 30
    out = volatility_pct(values, 20)
    assert out[-1] == pytest.approx(0.0)


def test_short_series_returns_none():
    assert ema([1.0, 2.0], 5)[-1] is None
    assert rsi([1.0, 2.0, 3.0], 14)[-1] is None
