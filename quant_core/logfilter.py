"""
Gộp log lặp lại khi mất mạng.

Khi Binance/mạng gặp sự cố, mỗi bot ghi lại CÙNG một cảnh báo (kèm traceback dài) hàng nghìn lần mỗi giờ
-> file log phình ~20 MB/giờ mà không thêm thông tin gì (watchdog đã ghi "Mất kết nối Binance" riêng).
Bộ lọc này: cùng logger + cùng mức + cùng mẫu tin (bỏ qua con số) trong `window` giây chỉ ghi LẦN ĐẦU;
khi hết cửa sổ, lần ghi tiếp theo kèm "(đã lặp lại N lần)". Chỉ áp dụng cho WARNING trở lên — log INFO
(vào/ra lệnh, heartbeat) giữ nguyên.
"""

from __future__ import annotations

import logging
import re
import time

_DIGITS = re.compile(r"\d+")


class DedupFilter(logging.Filter):
    def __init__(self, window: float = 600.0, min_level: int = logging.WARNING, clock=time.monotonic):
        super().__init__()
        self.window, self.min_level, self.clock = window, min_level, clock
        self.seen: dict[tuple, list] = {}          # key -> [thời điểm ghi gần nhất, số lần bị gộp]

    def _key(self, record: logging.LogRecord) -> tuple:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return record.name, record.levelno, _DIGITS.sub("#", msg)[:160]

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < self.min_level:
            return True
        now, key = self.clock(), self._key(record)
        st = self.seen.get(key)
        if st is not None and now - st[0] < self.window:
            st[1] += 1
            return False
        if st is not None and st[1]:
            record.msg = f"{record.getMessage()} (đã lặp lại {st[1]} lần trong {self.window / 60:.0f} phút trước, đã gộp)"
            record.args = ()
        self.seen[key] = [now, 0]
        if len(self.seen) > 500:                   # dọn mẫu cũ cho khỏi tốn bộ nhớ
            self.seen = {k: v for k, v in self.seen.items() if now - v[0] < self.window}
        return True


def install_log_dedup(window: float = 600.0) -> None:
    """Gắn bộ lọc vào mọi handler của root logger (gọi nhiều lần cũng chỉ gắn 1 lần)."""
    for h in logging.getLogger().handlers:
        if not any(isinstance(f, DedupFilter) for f in h.filters):
            h.addFilter(DedupFilter(window))
