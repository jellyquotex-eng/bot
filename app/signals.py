"""Indicator and signal generation utilities."""
from typing import List, Dict, Any, Tuple
import math

# Lightweight indicator implementations using plain Python lists. This avoids a hard
# dependency on pandas so the test suite and minimal installs work out of the box.


def rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    # Wilder's smoothing
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    k = 2.0 / (period + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return float(ema_val)


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    if len(values) < slow:
        return {"macd": 0.0, "signal": 0.0, "hist": 0.0}
    def ema_list(vals, period):
        k = 2.0 / (period + 1)
        out = []
        if not vals:
            return out
        val = vals[0]
        out.append(val)
        for v in vals[1:]:
            val = v * k + val * (1 - k)
            out.append(val)
        return out

    fast_ema = ema_list(values, fast)
    slow_ema = ema_list(values, slow)
    # align
    macd_line = [f - s for f, s in zip(fast_ema[-len(slow_ema) :], slow_ema)] if len(fast_ema) >= len(slow_ema) else [0]
    sig_list = ema_list(macd_line, signal) if macd_line else [0]
    macd_val = macd_line[-1] if macd_line else 0.0
    sig_val = sig_list[-1] if sig_list else 0.0
    hist = macd_val - sig_val
    return {"macd": float(macd_val), "signal": float(sig_val), "hist": float(hist)}


def bollinger(values: List[float], period: int = 20, stddev_mult: float = 2.0) -> Dict[str, float]:
    if len(values) < period:
        last = values[-1] if values else 0.0
        return {"upper": last, "middle": last, "lower": last, "last": last}
    window = values[-period:]
    ma = sum(window) / period
    var = sum((x - ma) ** 2 for x in window) / (period - 1 if period > 1 else 1)
    std = math.sqrt(var)
    last = values[-1]
    return {"upper": ma + stddev_mult * std, "middle": ma, "lower": ma - stddev_mult * std, "last": last}


def generate_signal(candles: List[Dict[str, Any]], timeframe_minutes: int = 1) -> Dict[str, Any]:
    """Given recent candles (list of dicts with 'close' and 'time'), generate a signal
    for the next candle. Returns direction in {CALL, PUT, NEUTRAL} and confidence 0-100.
    """
    if len(candles) < 30:
        return {"direction": "NEUTRAL", "confidence": 0, "indicators": {}}

    closes = [float(c["close"]) for c in candles]

    indicators: Dict[str, Any] = {}
    indicators["rsi"] = round(rsi(closes, 14), 2)
    indicators["ema_fast"] = round(ema(closes, 9), 5)
    indicators["ema_slow"] = round(ema(closes, 21), 5)
    macd_vals = macd(closes)
    indicators["macd"] = round(macd_vals["macd"], 6)
    indicators["macd_signal"] = round(macd_vals["signal"], 6)
    indicators["macd_hist"] = round(macd_vals["hist"], 6)
    bb = bollinger(closes, 20, 2.0)
    indicators["bollinger"] = {k: round(v, 6) for k, v in bb.items()}

    # Simple rule-based ensemble: require agreement between trend (ema), momentum (macd) and rsi
    votes = 0
    vote_reasons = []

    # EMA trend
    if indicators["ema_fast"] > indicators["ema_slow"]:
        votes += 1
        vote_reasons.append("ema_up")
    elif indicators["ema_fast"] < indicators["ema_slow"]:
        votes -= 1
        vote_reasons.append("ema_down")

    # MACD histogram
    if indicators["macd_hist"] > 0:
        votes += 1
        vote_reasons.append("macd_pos")
    elif indicators["macd_hist"] < 0:
        votes -= 1
        vote_reasons.append("macd_neg")

    # RSI thresholds
    r = indicators["rsi"]
    if r < 30:
        votes += 1
        vote_reasons.append("rsi_oversold")
    elif r > 70:
        votes -= 1
        vote_reasons.append("rsi_overbought")

    direction = "NEUTRAL"
    confidence = 0

    if votes >= 2:
        direction = "CALL"
        confidence = min(95, 50 + votes * 25)
    elif votes <= -2:
        direction = "PUT"
        confidence = min(95, 50 + (-votes) * 25)
    else:
        direction = "NEUTRAL"
        confidence = max(0, 30 + votes * 10)

    return {
        "direction": direction,
        "confidence": int(confidence),
        "indicators": indicators,
    }


if __name__ == "__main__":
    # quick self test
    sample = [{"close": float(1 + math.sin(i / 5.0)), "time": i} for i in range(100)]
    print(generate_signal(sample))
