"""
Cấu hình tập trung, đọc từ file .env ở thư mục gốc dự án.

Bản gốc ghi cứng TOKEN/API KEY trong 4_alert_bot.py — ở đây chuyển hết sang .env
(file .env đã nằm trong .gitignore, không bao giờ bị đẩy lên GitHub).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
USER_DATA = PROJECT_ROOT / "user_data"
FT_DATA_DIR = USER_DATA / "data" / "binance"
APP_DB = PROJECT_ROOT / "app_data.db"  # DB riêng của dashboard/alert bot (KHÔNG đụng quant_data.db cũ)

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:  # dotenv không bắt buộc
    pass


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.8-flash")

FT_API_URL = env("FT_API_URL", "http://127.0.0.1:8080")
FT_API_USERNAME = env("FREQTRADE__API_SERVER__USERNAME", "freqtrader")
FT_API_PASSWORD = env("FREQTRADE__API_SERVER__PASSWORD")


# ---------- Cài đặt vốn/rủi ro dùng chung giữa dashboard <-> alert bot <-> chiến lược ----------
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(APP_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_settings (id INTEGER PRIMARY KEY CHECK (id = 1),"
        " capital REAL NOT NULL, risk_pct REAL NOT NULL)"
    )
    return conn


def get_user_settings(default_capital: float = 1000.0, default_risk: float = 1.5) -> tuple[float, float]:
    try:
        with _conn() as conn:
            row = conn.execute("SELECT capital, risk_pct FROM user_settings WHERE id = 1").fetchone()
        if row:
            return float(row[0]), float(row[1])
    except Exception:
        pass
    return default_capital, default_risk


def save_user_settings(capital: float, risk_pct: float) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO user_settings (id, capital, risk_pct) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET capital = excluded.capital, risk_pct = excluded.risk_pct",
            (capital, risk_pct),
        )
