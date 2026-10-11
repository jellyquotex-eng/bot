import os
import json
import sqlite3
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .signals import generate_signal
from .quotex_client import QuotexClient

DB_PATH = os.environ.get("SIGNALS_DB", "signals.sqlite")

app = FastAPI(title="Quotex Signal Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Quotex client (lazy connect)
QUOTEX_EMAIL = os.environ.get("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.environ.get("QUOTEX_PASSWORD")
ACCOUNT_MODE = os.environ.get("ACCOUNT_MODE", "PRACTICE")
quotex_client = QuotexClient(QUOTEX_EMAIL or "", QUOTEX_PASSWORD or "", ACCOUNT_MODE)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT,
            timeframe INTEGER,
            direction TEXT,
            confidence INTEGER,
            indicators TEXT,
            candle_close_time INTEGER,
            generated_at INTEGER,
            result TEXT,
            evaluated_at INTEGER
        )"""
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup_event():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": int(time.time())}


@app.get("/api/assets")
async def assets():
    # Minimal curated list
    return ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc"]


def insert_signal_record(asset: str, timeframe: int, direction: str, confidence: int, indicators: dict, candle_close_time: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO signals (asset, timeframe, direction, confidence, indicators, candle_close_time, generated_at, result) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
        (asset, timeframe, direction, confidence, json.dumps(indicators), candle_close_time, int(time.time())),
    )
    conn.commit()
    conn.close()


async def evaluate_signal_later(asset: str, timeframe: int, candle_close_time: int, direction: str, record_time: int):
    # Wait until the candle_close_time + a small buffer
    now = int(time.time())
    wait = max(0, candle_close_time - now + 2)
    await asyncio.sleep(wait)
    # Try to fetch the latest closed candle to evaluate outcome
    try:
        # We'll attempt to use quotex_client.get_candles; if not available, mark unknown
        candles = []
        try:
            # fetch 2 candles at timeframe to get closed candle
            candles = await quotex_client.get_candles(asset, timeframe, count=3)
        except Exception:
            candles = []

        result = "UNKNOWN"
        if candles:
            # assume last closed candle is last element
            last = candles[-1]
            close = float(last.get("close", 0))
            prev = candles[-2]
            prev_close = float(prev.get("close", 0))
            if direction == "CALL" and close > prev_close:
                result = "WIN"
            elif direction == "PUT" and close < prev_close:
                result = "WIN"
            else:
                result = "LOSS"

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "UPDATE signals SET result = ?, evaluated_at = ? WHERE generated_at = ? AND asset = ?",
            (result, int(time.time()), record_time, asset),
        )
        conn.commit()
        conn.close()
    except Exception:
        # best-effort only
        pass


@app.get("/api/signal")
async def api_signal(asset: str = "EURUSD_otc", timeframe: int = 1):
    # Get recent candles. For the demo we generate sample data if the client is not configured.
    candles = []
    try:
        candles = await quotex_client.get_candles(asset, timeframe, count=100)
    except Exception:
        # fallback: generate synthetic candles using simple sine
        import math

        now = int(time.time())
        candles = []
        for i in range(120):
            t = now - (120 - i) * timeframe * 60
            close = 1.0 + math.sin(i / 5.0) * 0.001
            candles.append({"time": t, "close": float(close)})

    sig = generate_signal(candles, timeframe)

    # Determine next candle close time (approx)
    now = int(time.time())
    seconds_per = timeframe * 60
    # next candle close = ceil(now / seconds_per) * seconds_per
    candle_close_time = ((now // seconds_per) + 1) * seconds_per

    insert_signal_record(asset, timeframe, sig["direction"], sig["confidence"], sig["indicators"], candle_close_time)

    # schedule evaluation
    record_time = int(time.time())
    asyncio.create_task(evaluate_signal_later(asset, timeframe, candle_close_time, sig["direction"], record_time))

    return {
        "asset": asset,
        "direction": sig["direction"],
        "confidence": sig["confidence"],
        "indicators": sig["indicators"],
        "candle_close_time": candle_close_time,
        "generated_at": int(time.time()),
    }


@app.get("/api/history")
async def api_history(limit: int = 100):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT asset, timeframe, direction, confidence, indicators, candle_close_time, generated_at, result, evaluated_at FROM signals ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append(
            {
                "asset": r[0],
                "timeframe": r[1],
                "direction": r[2],
                "confidence": r[3],
                "indicators": json.loads(r[4]),
                "candle_close_time": r[5],
                "generated_at": r[6],
                "result": r[7],
                "evaluated_at": r[8],
            }
        )
    return out


# Serve frontend index
@app.get("/")
async def root():
    path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"message": "Quotex Signal Bot"}
