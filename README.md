# Quotex Signal Bot (FastAPI) with Web Dashboard

This repository contains a small Quotex signal server (FastAPI) that computes technical indicators
and serves CALL/PUT/NEUTRAL signals with a simple web dashboard.

Important: This project produces signals only. It does not execute trades.

Quickstart

1. Copy `.env.example` to `.env` and fill `QUOTEX_EMAIL` and `QUOTEX_PASSWORD` (optional).
2. Build and run with Docker:

```bash
docker compose up --build
```

3. Open the dashboard: http://localhost:8000/

Or run locally:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints

- `GET /health` — server health check
- `GET /api/assets` — supported assets
- `GET /api/signal?asset=EURUSD_otc&timeframe=1` — compute a signal for the next candle
- `GET /api/history` — recent signals and outcomes (WIN/LOSS)

Notes

- The server tries to use the `pyquotex` library if available to fetch real candles.
- If `pyquotex` is not installed or credentials are not provided, the server will fall back
  to synthetic candle data for demo purposes.
- Signals are computed on closed candles (non-repainting) and evaluated after the candle closes.

Development

- Unit tests for the indicator logic are in `tests/`. Run with `pytest`.
