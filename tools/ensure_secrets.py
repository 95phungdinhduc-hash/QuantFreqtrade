"""Tự sinh mật khẩu/khóa ngẫu nhiên cho API Freqtrade trong .env nếu đang để trống."""

import re
import secrets
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"

GENERATORS = {
    "FREQTRADE__API_SERVER__PASSWORD": lambda: secrets.token_urlsafe(18),
    "FREQTRADE__API_SERVER__JWT_SECRET_KEY": lambda: secrets.token_hex(32),
    "FREQTRADE__API_SERVER__WS_TOKEN": lambda: secrets.token_urlsafe(24),
}

text = ENV.read_text()
changed = []
for key, gen in GENERATORS.items():
    pattern = re.compile(rf'^{key}=""\s*$', re.M)
    if pattern.search(text):
        text = pattern.sub(f'{key}="{gen()}"', text)
        changed.append(key)
    elif not re.search(rf"^{key}=", text, re.M):
        text += f'\n{key}="{gen()}"\n'
        changed.append(key)
ENV.write_text(text)
ENV.chmod(0o600)
print("[+] Đã sinh khóa: " + ", ".join(changed) if changed else "[=] Khóa API đã có sẵn.")
