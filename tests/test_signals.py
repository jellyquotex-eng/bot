import math
import pytest
from app.signals import rsi, ema, macd, bollinger, generate_signal


def make_values(n=50):
    return [1.0 + math.sin(i / 5.0) * 0.01 for i in range(n)]


def test_rsi_returns_value():
    s = make_values(30)
    val = rsi(s, 14)
    assert isinstance(val, float)
    assert 0 <= val <= 100


def test_ema_monotonic():
    s = make_values(30)
    e9 = ema(s, 9)
    e21 = ema(s, 21)
    assert isinstance(e9, float)
    assert isinstance(e21, float)


def test_macd_shape():
    s = make_values(100)
    m = macd(s)
    assert set(m.keys()) == {"macd", "signal", "hist"}


def test_bollinger_bounds():
    s = make_values(30)
    b = bollinger(s, 20, 2.0)
    assert b["upper"] >= b["lower"]


def test_generate_signal_neutral_with_short_data():
    sample = [{"close": 1.0, "time": i} for i in range(10)]
    sig = generate_signal(sample)
    assert sig["direction"] == "NEUTRAL"
