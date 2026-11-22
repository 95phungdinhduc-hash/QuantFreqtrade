"""
Client nhỏ gọn đọc REST API của Freqtrade (bot đang chạy dry-run/live).
Dashboard dùng nó để hiển thị lệnh đang mở, lợi nhuận, số dư... của bot.
Tài liệu API: https://www.freqtrade.io/en/stable/rest-api/
"""

from __future__ import annotations

import requests

from quant_core import settings


class FreqtradeClient:
    def __init__(self, url: str | None = None, username: str | None = None,
                 password: str | None = None, timeout: float = 5.0):
        self.url = (url or settings.FT_API_URL).rstrip("/")
        self.auth = (username or settings.FT_API_USERNAME, password or settings.FT_API_PASSWORD)
        self.timeout = timeout

    def _get(self, path: str, **params):
        r = requests.get(f"{self.url}/api/v1/{path}", auth=self.auth, params=params,
                         timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def ping(self) -> bool:
        try:
            return requests.get(f"{self.url}/api/v1/ping", timeout=2).json().get("status") == "pong"
        except Exception:
            return False

    def show_config(self) -> dict:
        return self._get("show_config")

    def status(self) -> list[dict]:
        """Các lệnh đang mở."""
        return self._get("status")

    def profit(self) -> dict:
        return self._get("profit")

    def balance(self) -> dict:
        return self._get("balance")

    def trades(self, limit: int = 100) -> list[dict]:
        return self._get("trades", limit=limit).get("trades", [])

    def daily(self, days: int = 30) -> list[dict]:
        return self._get("daily", timescale=days).get("data", [])
