"""
Cố vấn AI (Gemini) — port từ 4_alert_bot.py.

Nâng cấp: thư viện cũ `google-generativeai` và model `gemini-1.5-*` đã bị Google ngừng hỗ trợ,
bản này dùng SDK mới `google-genai`. Tên model đổi được qua biến GEMINI_MODEL trong .env.

Google thường xuyên ngừng model cũ (lỗi 404) hoặc quá tải model mới (lỗi 503), nên mỗi lần gọi
sẽ thử lần lượt: GEMINI_MODEL trong .env -> các model dự phòng bên dưới.
Nếu không có API key hoặc mọi model đều lỗi -> trả về None, hệ thống chạy thuần toán học.
"""

from __future__ import annotations

from quant_core import settings

# Model dự phòng (thử theo thứ tự nếu model chính lỗi). Sửa danh sách này khi Google đổi tên model.
FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

_client = None


def _get_client():
    global _client
    if _client is None and settings.GEMINI_API_KEY:
        from google import genai

        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def is_enabled() -> bool:
    return bool(settings.GEMINI_API_KEY)


_EN_HINTS = (" the ", "bullet", "sentence", "checked", "check:", "constraint", "draft", "let me", "i will")


def _clean(text: str) -> str:
    """Bỏ ký tự Markdown và các dòng 'tự kiểm tra' tiếng Anh mà đôi khi model in lẫn vào câu trả lời."""
    lines = []
    for line in text.replace("*", "").replace("_", "").replace("`", "").splitlines():
        low = f" {line.lower()} "
        if any(h in low for h in _EN_HINTS) and not any(ch in line for ch in "ăâđêôơưàảãáạềếệờớợừứựịỉìíòóỏõọùúủũụ"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _generate(prompt: str, max_tokens: int, temperature: float, timeout_ms: int) -> str | None:
    client = _get_client()
    if client is None:
        return None
    from google.genai import types

    models = list(dict.fromkeys([settings.GEMINI_MODEL, *FALLBACK_MODELS]))
    truncated: str | None = None
    for model in models:
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=max_tokens, temperature=temperature,
                                                   http_options=types.HttpOptions(timeout=timeout_ms)))
            text = _clean(resp.text or "")
            finish = str(getattr(resp.candidates[0], "finish_reason", "") if resp.candidates else "")
            if text and "MAX_TOKENS" in finish:
                # Model "suy nghĩ" quá lâu nên câu trả lời bị cắt giữa chừng -> thử model khác
                print(f"  ⚠️ AI ({model}) trả lời bị cắt (MAX_TOKENS) -> thử model khác")
                truncated = truncated or text
                continue
            if text:
                return text
        except Exception as e:  # 404 model bị ngừng, 503 quá tải, 429 hết quota, mất mạng...
            print(f"  ⚠️ AI ({model}) lỗi: {str(e)[:120]} -> thử model khác")
    return truncated  # không model nào trả lời trọn vẹn -> dùng tạm câu trả lời bị cắt (nếu có)


def portfolio_brief(summary: str, profile_label: str) -> str | None:
    """Nhờ Gemini diễn giải bảng tư vấn (do hệ thống tính) thành vài gạch đầu dòng dễ hiểu."""
    prompt = f"""
Bạn là chuyên gia phân tích định lượng crypto. Dưới đây là kết quả do một hệ thống quy tắc tính sẵn
(điểm -100..+100, chế độ thị trường, chiến lược phù hợp, kết quả backtest). Hồ sơ rủi ro người dùng: {profile_label}.

{summary}

Viết đúng 5 gạch đầu dòng tiếng Việt, mỗi dòng 1-2 câu, không dùng ký tự * _ `:
- Bức tranh chung của thị trường
- Coin đáng chú ý nhất và vì sao (dựa vào số liệu ở trên)
- Rủi ro lớn nhất hiện tại
- Cách quản trị vốn phù hợp hồ sơ {profile_label}
- Điều cần theo dõi trong 24-48 giờ tới
Không hứa hẹn lợi nhuận, không bịa số liệu ngoài bảng. Dòng cuối ghi đúng câu:
Đây là phân tích tham khảo từ dữ liệu, không phải lời khuyên đầu tư.
"""
    return _generate(prompt, max_tokens=4096, temperature=0.2, timeout_ms=40_000)


def analyze(sym: str, timeframe: str, price: float, z_score: float, ema_fast: float,
            ema_slow: float, adf_p: float, session: str, sentiment: str,
            ft_context: str = "") -> str | None:
    gap = (ema_fast - ema_slow) / ema_slow * 100
    prompt = f"""
Bạn là chuyên gia Quant Trading. Phân tích nhanh cặp {sym} (khung {timeframe}):
- Giá hiện tại: {price:.4f}
- Z-Score (50 nến): {z_score:.2f} (ngoài vùng ±2.0 là quá mua/quá bán)
- EMA20: {ema_fast:.4f} | EMA50: {ema_slow:.4f} (chênh lệch {gap:.2f}%)
- ADF p-value (200 nến): {adf_p:.3f} (< 0.05 là đi ngang / hồi quy)
- Phiên: {session}
- Tin tức: {sentiment}
{ft_context}
Trả lời đúng 3 gạch đầu dòng ngắn (không dùng ký tự * _ `):
- Nhận diện thị trường: Trend hay Sideway?
- Chiến lược ưu tiên: Mean Reversion hay Trend Following?
- Hành động: Long, Short hay Đứng ngoài?
"""
    return _generate(prompt, max_tokens=2048, temperature=0.1, timeout_ms=20_000)
