import os
import asyncio
from typing import List, Dict, Any

try:
    import pyquotex
except Exception:  # pragma: no cover - optional dependency
    pyquotex = None


class QuotexClient:
    """Simple Quotex client wrapper. Uses `pyquotex` when available.

    This client only implements the minimal methods needed by the demo signal
    server: login and fetching recent candles. If `pyquotex` is not installed
    the client will raise helpful errors when used.
    """

    def __init__(self, email: str, password: str, account_mode: str = "PRACTICE"):
        self.email = email
        self.password = password
        self.account_mode = account_mode
        self._client = None
        self._lock = asyncio.Lock()

    async def connect(self):
        if pyquotex is None:
            raise RuntimeError("pyquotex is not installed. Please add it to requirements.txt")
        async with self._lock:
            if self._client is None:
                # Example pyquotex usage (may vary depending on version)
                self._client = pyquotex.Quotex(email=self.email, password=self.password)
                await self._client.login(mode=self.account_mode)

    async def get_candles(self, asset: str, timeframe_minutes: int, count: int = 100) -> List[Dict[str, Any]]:
        """Return list of candles with fields: time (ms), open, high, low, close."""
        if pyquotex is None:
            raise RuntimeError("pyquotex is not installed. Candle retrieval is unavailable")
        await self.connect()
        # The real client method name may differ; adapt as needed for installed library.
        # We assume an async method `get_candles` exists; otherwise users should
        # adapt this wrapper to match their installed Quotex client.
        data = await self._client.get_candles(asset, timeframe_minutes, count)
        return data
