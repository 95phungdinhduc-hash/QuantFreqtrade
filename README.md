# QuantFreqtrade — QuantTradingSystem × Freqtrade

> 📘 **Lệnh hay dùng (bản ngắn):** [LENH.md](LENH.md) · **Hướng dẫn chi tiết có ví dụ:** [HUONG_DAN_CHI_TIET.md](HUONG_DAN_CHI_TIET.md) · **Đọc hiểu dashboard:** [HUONG_DAN_DASHBOARD.md](HUONG_DAN_DASHBOARD.md)

> 🆕 **Mới:** 2 chiến lược `QuantBreakoutStrategy` (mua theo đà) và `QuantSmartDCAStrategy` (tích luỹ từng phần),
> lệnh `./run.sh backtest-all` so sánh cả 4 chiến lược Spot, và tab **🧭 Tư vấn** trên dashboard
> (chấm điểm coin, chiến lược phù hợp, phân bổ vốn theo hồ sơ rủi ro, AI tóm tắt). Xem mục 11.1 trong HUONG_DAN_CHI_TIET.md.

Dự án này ghép **QuantTradingSystem** (code của bạn) với **[Freqtrade](https://github.com/freqtrade/freqtrade)**,
một bot giao dịch crypto mã nguồn mở. Bạn giữ được phần phân tích định lượng của mình (Z-Score, ADF,
EMA, quản lý vốn, tin tức, Gemini AI), còn Freqtrade lo phần backtest chuẩn, tối ưu tham số,
chạy bot 24/7, quản lý lệnh, FreqUI và Telegram.

> ⚠️ Đây là công cụ nghiên cứu, không phải lời khuyên đầu tư. Luôn chạy **dry-run (tiền ảo)** đủ lâu
> trước khi nghĩ tới tiền thật.

---

## 1. Cấu trúc thư mục

```
QuantFreqtrade/
├── run.sh                      ← MỌI lệnh đều chạy qua file này (./run.sh help)
├── .env                        ← Token Telegram, Gemini, mật khẩu API (BÍ MẬT, không chia sẻ)
├── requirements.txt            ← Thư viện (đã kiểm tra không xung đột)
├── quant_core/                 ← Thư viện dùng chung, tách từ code cũ của bạn
│   ├── indicators.py           ← Z-Score, EMA, ADF trượt, ATR       (từ 2_dashboard / 3_backtest)
│   ├── risk.py                 ← Quy mô lệnh, SL/TP, VaR, Kelly    (từ tab 3 dashboard)
│   ├── market_context.py       ← Tin tức RSS + phiên giao dịch     (từ 4_alert_bot)
│   ├── ai_advisor.py           ← Gemini AI (SDK mới)               (từ 4_alert_bot)
│   ├── data.py, ft_client.py   ← Đọc dữ liệu Freqtrade + REST API của bot
│   └── settings.py             ← Đọc .env, lưu cài đặt vốn/rủi ro
├── user_data/                  ← Thư mục chuẩn của Freqtrade
│   ├── config.json             ← Bot Spot (dry-run, 4 cặp BTC/ETH/SOL/BNB)
│   ├── config.futures.json     ← Bot Futures (Long + Short)
│   ├── strategies/
│   │   ├── QuantZScoreStrategy.py   ← Port 1:1 từ 3_backtest_engine.py (để so sánh)
│   │   └── QuantHybridStrategy.py   ← Chiến lược NÂNG CẤP (+ bản Futures)
│   └── data/binance/           ← Dữ liệu nến (dùng chung cho bot, dashboard, alert bot)
├── dashboard/app.py            ← Dashboard Streamlit nâng cấp (7 tab, có trang Tổng quan)
│   └── ui.py                   ← Giao diện: màu, CSS, biểu đồ (muốn đổi màu thì sửa ở đây)
├── .streamlit/config.toml      ← Theme tối cho dashboard
├── alert_bot/alert_bot.py      ← Bot cảnh báo Telegram + AI nâng cấp
├── tools/
│   ├── import_legacy_db.py     ← Chuyển quant_data.db cũ sang Freqtrade (CHỈ ĐỌC)
│   └── legacy_backtest.py      ← Backtest kiểu cũ để đối chiếu
├── tests/                      ← Kiểm thử tự động (./run.sh test)
└── .vscode/                    ← Sẵn cấu hình VS Code (Tasks + Debug)
```

### Code cũ đi đâu trong dự án mới?

| File cũ (QuantTradingSystem) | Trong dự án mới |
|---|---|
| `1_data_pipeline.py` | `./run.sh download` (Freqtrade tự tải, tự nối dữ liệu) + `./run.sh import` (lấy dữ liệu cũ) |
| `2_dashboard.py` | `dashboard/app.py`: giữ 4 tab cũ, thêm tab **Bot Freqtrade** và **Kết quả Backtest** |
| `3_backtest_engine.py` | `QuantZScoreStrategy` (backtest bằng Freqtrade) + `tools/legacy_backtest.py` |
| `4_alert_bot.py` | `alert_bot/alert_bot.py` + logic vào lệnh/SL/khối lượng của `QuantHybridStrategy` |
| `quant_data.db` | Chỉ **đọc** một lần khi import; dữ liệu mới lưu ở `user_data/data/binance/*.feather` |

---

## 2. Vì sao không xung đột với dự án cũ

| Nguy cơ | Cách xử lý |
|---|---|
| Sửa nhầm code cũ | Dự án nằm ở thư mục riêng `~/QuantFreqtrade`, **không đụng** `~/QuantTradingSystem` |
| Xung đột thư viện | Môi trường riêng `.venv` (Python 3.12). Dự án cũ dùng `venv` Python 3.9 của nó. Phiên bản thư viện đã khoá, `pip check` báo OK |
| Hỏng dữ liệu cũ | `quant_data.db` được mở ở chế độ **chỉ đọc** (`mode=ro`); đã kiểm tra mã MD5 trước và sau khi import, file không đổi |
| Trùng cổng (port) | Dashboard mới dùng **8502** (cũ là 8501), API bot Spot **8080**, Futures **8081** |
| Trùng bảng `user_settings` | Dự án mới lưu cài đặt riêng trong `app_data.db` |
| Telegram | Mỗi token chỉ được **một** bot Freqtrade dùng. `./run.sh dryrun-futures` mặc định tắt Telegram; nếu **chỉ** chạy bot Futures thì bật bằng `FUTURES_TELEGRAM=true ./run.sh dryrun-futures`. Nếu bật song song `4_alert_bot.py` cũ và alert bot mới, bạn sẽ nhận tin **trùng**, nên chỉ chạy một trong hai |

---

## 3. Cài đặt (ĐÃ LÀM SẴN trên máy bạn)

Mọi thứ đã được cài và chạy thử. Bạn chỉ cần đọc phần này nếu muốn cài lại hoặc cài sang máy khác.

### Bước 3.1: Mở Terminal
Nhấn `Cmd + Space`, gõ **Terminal**, Enter. Rồi chuyển vào thư mục dự án:
```bash
cd ~/QuantFreqtrade
```

### Bước 3.2: Cần có Python 3.11+ (máy bạn đã có 3.12)
```bash
python3.12 --version
```
Nếu chưa có thì cài bằng `brew install python@3.12`.

### Bước 3.3: Cài toàn bộ (Freqtrade + thư viện + file .env)
```bash
./run.sh setup
```
Lệnh này tạo `.venv`, cài Freqtrade 2026.10 kèm TA-Lib (có sẵn bản cho chip Apple, không cần biên dịch),
tạo `.env` và tự sinh mật khẩu API.

### Bước 3.4: Kiểm tra
```bash
./run.sh test
```
Kết quả đúng là `15 passed` (trong đó có bài test chạy backtest Freqtrade thật).

---

## 4. Dùng hằng ngày, từng bước

> Mỗi lệnh dưới đây chạy trong Terminal, sau khi đã `cd ~/QuantFreqtrade`.
> Lệnh chạy liên tục (bot, dashboard) thì dừng bằng `Ctrl + C`.

### Bước 4.1: Lấy dữ liệu
Dữ liệu cũ (180 ngày, 4 coin, 4 khung) **đã được chuyển sẵn**. Để tải thêm dữ liệu mới hoặc dài hơn:
```bash
./run.sh download 365
```

### Bước 4.2: Backtest, so sánh chiến lược cũ và mới
```bash
./run.sh backtest
```
Freqtrade in ra bảng chi tiết và cuối cùng là **STRATEGY SUMMARY**. Kết quả cũng xem được trực quan
ở tab "📊 Backtest" trên dashboard.

### Bước 4.3: Mở dashboard
```bash
./run.sh dashboard
```
Mở trình duyệt vào **http://localhost:8502**

- **🏠 Tổng quan**: giá trực tiếp Binance, tín hiệu hệ thống từng coin (kèm giá vào, cắt lỗ, chốt lời,
  khối lượng theo % rủi ro của bạn), thanh "mức gần tín hiệu", trạng thái bot và kết quả backtest.
- **📈 Phân tích**: nến + dải ±2σ + EMA, Z-Score, ADF, đánh dấu ▲▼ các điểm Mean Reversion trong quá khứ.
- **🎯 Screener**, **🛡️ Vốn & Rủi ro** (có biểu đồ kịch bản vào lệnh), **📰 Tin tức**, **🤖 Bot Freqtrade**, **📊 Backtest**.

### Bước 4.4: Chạy bot bằng tiền ảo (dry-run)
Mở **một cửa sổ Terminal khác** (`Cmd + T`), rồi:
```bash
cd ~/QuantFreqtrade
```
```bash
./run.sh dryrun
```
Bot giả lập ví 1000 USDT, giao dịch theo `QuantHybridStrategy` với giá thật của Binance nhưng **không đặt lệnh thật**.
- Theo dõi trên dashboard ở tab "🤖 Bot Freqtrade"
- Telegram mặc định chỉ nhận tín hiệu alert bot; muốn điều khiển bot Hybrid qua `/status`, `/profit`… thì đặt
  `BOT_TELEGRAM_NOTIFY=true` trong `.env` (xem LENH.md mục 4)
- Hoặc giao diện web chính chủ **FreqUI**: chạy `./run.sh ui` một lần, rồi mở http://127.0.0.1:8080
  (đăng nhập bằng `freqtrader` và mật khẩu ở dòng `FREQTRADE__API_SERVER__PASSWORD` trong `.env`)

### Bước 4.5: Bot cảnh báo Telegram + AI
```bash
./run.sh alert
```
Muốn thử một lần mà không gửi Telegram:
```bash
TELEGRAM_BOT_TOKEN= ./run.sh alert --once
```
Muốn bot báo tín hiệu **y hệt bản cũ `4_alert_bot.py`** (không lọc ADF, SL 1,2σ/1,5σ, báo nhiều hơn):
```bash
./run.sh alert --legacy
```
Cả hai chế độ đều gửi tin cùng định dạng: phân tích Gemini, Z-Score/EMA, gợi ý lệnh **Spot** và **Futures**
(đòn bẩy, ký quỹ, Min Notional của sàn, phí 2 chiều, TP/SL).

### Bước 4.6: Đồng bộ vốn và rủi ro
Ở tab "🛡️ Vốn & Rủi ro" trên dashboard, chỉnh "Rủi ro tối đa mỗi lệnh". Bot Freqtrade (dry-run/live)
**dùng luôn con số này** để tính khối lượng mỗi lệnh (do `"sync_risk_from_dashboard": true` trong `config.json`).
Khi backtest, bot dùng `"risk_pct": 1.5` cố định để kết quả lặp lại được.

---

## 5. Chiến lược nâng cấp `QuantHybridStrategy` làm gì

1. **Nhận diện chế độ thị trường**: tính ADF p-value trên 200 nến gần nhất (bản cũ tính trên *toàn bộ*
   lịch sử, tức là nhìn trước tương lai nếu dùng để backtest).
   - ADF < 0.20 thì coi là thị trường đi ngang và đánh **Mean Reversion**
   - Ngược lại thì coi là có xu hướng và đánh **Trend Following** (EMA20/50 mở rộng > 1%, khung 4h cùng chiều)
2. **Không bắt dao rơi**: chỉ mua khi nến trước có Z < -2 **và** Z bắt đầu quay đầu đi lên, kèm nến xanh.
3. **Bộ lọc 4h**: Mean Reversion chỉ Long khi giá đang trên EMA50 của khung 4h.
4. **Cắt lỗ theo độ biến động**: SL = 2σ tính tại lúc vào lệnh; dời về hoà vốn khi giá chạy được 1.5σ.
5. **Khối lượng lệnh theo rủi ro**: mỗi lệnh chỉ mất tối đa 1.5% vốn nếu dính SL (quy tắc tab 3 dashboard).
6. **Thoát lệnh**: Mean Reversion thoát khi Z hồi về 0 hoặc sau 48 giờ; Trend thoát khi EMA cắt xuống.
7. **Protections**: nghỉ 2 nến sau mỗi lệnh; dừng 12 nến nếu thua 3 lệnh trong 24 nến; dừng 24 nến nếu sụt vốn quá 15%.
8. **Bộ lọc tin tức** (chỉ khi chạy dry-run/live): ngừng mở Long khi điểm tin RSS ≤ -4.

`QuantHybridFuturesStrategy` có thêm lệnh **Short** đối xứng và đòn bẩy giống alert bot cũ
(x5 khi |Z| ≥ 3, x2 cho Mean Reversion, x3 cho Trend), **nhưng bị giới hạn bởi `"max_leverage"`
trong `user_data/config.futures.json` (hiện đặt x5)**. Backtest 2 năm: x2 lỗ ít hơn x5 (−9,4% so với −13,8%).

### Kết quả backtest thực tế (25/05 đến 20/11/2026, BTC/ETH/SOL/BNB, khung 1h, vốn 1000 USDT, phí 0.1%)

| Chiến lược | Số lệnh | Lợi nhuận | Sụt vốn tối đa |
|---|---|---|---|
| Mua và giữ (thị trường) | — | **-20.1%** | — |
| QuantZScoreStrategy (code cũ) | 151 | **-22.6%** | 26.2% |
| QuantHybridStrategy (nâng cấp) | 15 | **-6.1%** | 6.1% |
| QuantHybridFuturesStrategy (01/06 đến 20/11) | 36 | **-8.6%** | 12.3% |

**Nói thẳng:** trong 6 tháng thị trường giảm này, **chưa chiến lược nào có lãi**. Bản nâng cấp mất ít hơn
và sụt vốn nhỏ hơn nhiều, nhưng như vậy *chưa đủ* để chạy tiền thật. Freqtrade đã kiểm tra:
không có **lookahead bias** (`./run.sh check-bias`) và chỉ báo không bị lệch giữa live và backtest
(`recursive-analysis`).

Nên làm tiếp:
- Tải dữ liệu dài hơn (`./run.sh download 1000`) rồi backtest lại trên nhiều giai đoạn tăng, giảm, đi ngang.
- Tối ưu tham số: `./run.sh hyperopt 300`. Freqtrade lưu tham số tốt nhất vào
  `user_data/strategies/QuantHybridStrategy.json`, và file này **tự động được dùng** cho các lần backtest
  hoặc chạy bot sau đó. Muốn quay về mặc định thì xoá file đó.
  Cẩn thận *overfitting*: tối ưu trên một đoạn (ví dụ `--timerange 20250101-20260601`), rồi kiểm tra trên đoạn
  khác (`./run.sh backtest --timerange 20260601-`).

---

## 6. Dùng VS Code

1. Mở VS Code, chọn **File, rồi Open Folder…**, chọn thư mục `QuantFreqtrade`.
2. Khi được hỏi, cài các extension được gợi ý (Python, Pylance).
3. Môi trường `.venv` được chọn tự động (đã cấu hình trong `.vscode/settings.json`).
4. Chạy nhanh: `Cmd + Shift + P`, gõ **Tasks: Run Task**, rồi chọn (Backtest, Dashboard, Bot Dry-run…).
5. Debug từng dòng chiến lược: đặt breakpoint trong `QuantHybridStrategy.py`, nhấn `F5`, chọn
   "Debug: Backtest QuantHybridStrategy".

---

## 7. Chuyển sang tiền thật (CHỈ khi đã chắc chắn)

1. Chạy dry-run **ít nhất 4 đến 8 tuần**, so sánh kết quả dry-run với backtest cùng giai đoạn.
2. Tạo API key Binance: **tắt quyền Withdraw (rút tiền)**, bật giới hạn IP.
3. Mở `.env`, bỏ dấu `#` và điền `FREQTRADE__EXCHANGE__KEY` và `FREQTRADE__EXCHANGE__SECRET`.
4. Trong `user_data/config.json`, đổi `"dry_run": true` thành `false`. Bắt đầu với vốn nhỏ.
5. Bản Futures có đòn bẩy và **có thể cháy tài khoản**. Chỉ dùng khi đã hiểu rõ.

---

## 8. Bảo mật: nên làm ngay

File `4_alert_bot.py` cũ **ghi thẳng** token Telegram và Gemini API key trong code. Dự án mới đã chuyển
các giá trị này vào `.env` (quyền đọc chỉ dành cho bạn, và nằm trong `.gitignore`). Tuy vậy, chúng vẫn còn
trong file cũ. Nếu bạn từng gửi hoặc upload file cũ ở đâu đó, hãy:
- Tạo token Telegram mới: nhắn `/revoke` cho **@BotFather**, rồi cập nhật cả hai dòng token trong `.env`.
- Tạo Gemini API key mới ở Google AI Studio, rồi cập nhật `GEMINI_API_KEY` trong `.env`.

---

## 9. Lỗi thường gặp

| Lỗi | Cách sửa |
|---|---|
| `jwt_secret_key ... is too short` | Chạy `./run.sh setup` (tự sinh khóa) hoặc kiểm tra `.env` |
| `No data found` khi backtest | `./run.sh import` hoặc `./run.sh download` |
| Backtest Futures báo thiếu dữ liệu | `./run.sh download-futures 365` |
| Telegram báo `Conflict: terminated by other getUpdates` | Đang có 2 bot Freqtrade dùng chung token, hãy tắt một bot |
| Dashboard tab Bot báo "Bot chưa chạy" | Mở Terminal khác và chạy `./run.sh dryrun` |
| `Permission denied: ./run.sh` | `chmod +x run.sh` |
| Gemini báo lỗi model | Đổi `GEMINI_MODEL` trong `.env` (ví dụ `gemini-2.5-flash-lite`) |

Tài liệu Freqtrade: https://www.freqtrade.io/en/stable/
