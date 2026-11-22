# 📗 Hướng dẫn chi tiết có ví dụ — QuantFreqtrade

> Đây là bản **đầy đủ** (giải thích từng kết quả). Bản **ngắn gọn** để tra nhanh: [LENH.md](LENH.md)
>
> **Cập nhật mới (xem LENH.md):** chế độ tự động `./run.sh start/stop`, `autostart` (tự bật khi mở máy,
> tự bật lại bot bị tắt), cả 4 bot đều nhắn Telegram, dữ liệu 2 năm và `./run.sh validate` (kiểm chứng
> theo giai đoạn). Câu nào bên dưới nói "chỉ bot Hybrid gửi Telegram" nay không còn đúng.

File này gồm **tất cả các lệnh** của dự án, mỗi lệnh đều có **ví dụ cụ thể**: gõ gì, màn hình hiện gì,
và hiểu kết quả thế nào. Kết quả mẫu ở các mục 3–8 là **kết quả thật** chạy trên máy bạn ngày 22/11/2026
(đã cắt bớt cho gọn). Riêng tin nhắn Telegram ở mục 10 là **minh hoạ**, vì bot chưa có lệnh thật nào.

**Cách đọc mỗi ví dụ:**

- 💻 **Gõ**: lệnh bạn gõ vào Terminal (hoặc Telegram)
- 📤 **Bạn sẽ thấy**: kết quả hiện ra
- 🧠 **Nghĩa là**: giải thích kết quả

## Mục lục

1. [5 khái niệm cần hiểu trước](#1-5-khái-niệm-cần-hiểu-trước)
2. [Mở Terminal đúng chỗ](#2-mở-terminal-đúng-chỗ)
3. [Kiểm tra trạng thái & cài đặt](#3-kiểm-tra-trạng-thái--cài-đặt)
4. [Dữ liệu nến](#4-dữ-liệu-nến)
5. [Backtest Spot — thử chiến lược trên quá khứ](#5-backtest-spot--thử-chiến-lược-trên-quá-khứ)
6. [Kiểm tra & tối ưu chiến lược](#6-kiểm-tra--tối-ưu-chiến-lược)
7. [Chạy bot Spot bằng tiền ảo](#7-chạy-bot-spot-bằng-tiền-ảo)
8. [Futures — Long, Short, đòn bẩy](#8-futures--long-short-đòn-bẩy)
9. [Alert bot — cảnh báo Telegram + Gemini AI](#9-alert-bot--cảnh-báo-telegram--gemini-ai)
10. [Lệnh Telegram điều khiển bot Freqtrade](#10-lệnh-telegram-điều-khiển-bot-freqtrade)
11. [Dashboard](#11-dashboard)
12. [Tình huống thực tế: làm từng bước](#12-tình-huống-thực-tế-làm-từng-bước)
13. [Tạm đổi cấu hình khi chạy](#13-tạm-đổi-cấu-hình-khi-chạy)
14. [Lệnh Freqtrade nâng cao](#14-lệnh-freqtrade-nâng-cao)
15. [Lỗi thường gặp & cách sửa](#15-lỗi-thường-gặp--cách-sửa)
16. [Bảng tra nhanh 1 trang](#16-bảng-tra-nhanh-1-trang)

---

## 1. 5 khái niệm cần hiểu trước

| Khái niệm | Giải thích dễ hiểu |
|---|---|
| **Spot** | Mua coin thật rồi chờ giá lên để bán. Chỉ kiếm lời khi giá **tăng** (Long). Không có đòn bẩy, không bị "cháy tài khoản". |
| **Futures** | Hợp đồng đặt cược giá lên (**Long**) hoặc xuống (**Short**), có **đòn bẩy** (x2, x3, x5). Lời và lỗ đều nhân lên. Cặp coin viết dạng `BTC/USDT:USDT`. |
| **Backtest** | Cho chiến lược "chơi thử" trên dữ liệu **quá khứ** để xem nó sẽ lời/lỗ bao nhiêu. Không tốn tiền, chạy vài phút. |
| **Dry-run** | Bot chạy **thật** theo giá Binance hiện tại nhưng dùng **tiền ảo** (1000 USDT). Bước bắt buộc trước khi dùng tiền thật. |
| **2 loại bot Telegram** | **Bot Freqtrade** (`./run.sh dryrun`): tự giao dịch và **nhận lệnh** `/status`, `/profit`… **Alert bot** (`./run.sh alert`): chỉ **gửi cảnh báo**, không giao dịch, không nhận lệnh. Cả hai gửi vào cùng một chat Telegram của bạn. |

Chiến lược của dự án:

| Tên | Dùng cho | Ý tưởng |
|---|---|---|
| `QuantZScoreStrategy` | Spot | Bản gốc từ dự án cũ: mua khi Z-Score < −2, bán khi Z ≥ 0. Giữ lại để so sánh. |
| `QuantHybridStrategy` | Spot | Bản nâng cấp: ADF nhận diện đi ngang/xu hướng rồi chọn Mean Reversion hoặc Trend. Cắt lỗ 2σ, khối lượng theo % rủi ro. |
| `QuantHybridFuturesStrategy` | Futures | Như Hybrid, thêm **Short** và đòn bẩy x2–x5. |
| `QuantBreakoutStrategy` 🆕 | Spot | **Mua theo đà**: thị trường có xu hướng tăng, giá phá đỉnh 48 giờ kèm khối lượng lớn. Cắt lỗ kéo theo đỉnh (trailing 3×ATR). |
| `QuantSmartDCAStrategy` 🆕 | Spot | **Tích luỹ từng phần** (phong cách đầu tư): mua 1 phần khi hoảng loạn (Z < −2, RSI < 30), giảm thêm 4% / 8% thì mua thêm. Chốt khi lời 4% trên giá vốn. |

Kết quả backtest 4 chiến lược Spot trên cùng dữ liệu (25/05 – 22/11/2026, thị trường **−18,9%**):

| Chiến lược | Lợi nhuận | Sụt vốn tối đa | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|
| Z-Score gốc | −23,87% | 26,2% | 151 | 64% |
| Hybrid | −6,09% | 6,1% | 15 | 40% |
| **Breakout** 🆕 | **−0,54%** | 10,2% | 49 | 35% |
| **Smart DCA** 🆕 | −2,29% | **3,9%** | 89 | **90%** |

Chưa chiến lược nào có lãi trong giai đoạn giảm này. Hai chiến lược mới lỗ ít nhất, mỗi cái mạnh một kiểu:
Breakout lỗ ít nhất, Smart DCA sụt vốn ít nhất.

---

## 2. Mở Terminal đúng chỗ

**Cách 1, trong VS Code (khuyên dùng):** File → Open Folder → chọn `QuantFreqtrade` → menu
**Terminal → New Terminal**. Terminal tự đứng đúng thư mục.

**Cách 2, app Terminal của macOS:**

💻 Gõ:
```bash
cd ~/QuantFreqtrade
```

🧠 Nghĩa là: "đi vào" thư mục dự án. **Mọi lệnh `./run.sh` phải gõ trong thư mục này.** Nếu quên
bước này, bạn sẽ gặp lỗi `no such file or directory: ./run.sh`.

**Ba thao tác cần nhớ:**

| Thao tác | Cách làm | Ví dụ |
|---|---|---|
| Dừng chương trình đang chạy | Bấm `Ctrl + C` | Đang chạy bot → `Ctrl + C` → bot tắt an toàn |
| Mở Terminal thứ 2, 3… | VS Code: nút **+** ở khung Terminal · macOS: `Cmd + T` | Terminal 1 chạy bot, Terminal 2 chạy dashboard |
| Gọi lại lệnh vừa gõ | Phím mũi tên `↑` | Bấm `↑` rồi `Enter` để chạy lại backtest |

> **Quy tắc vàng:** chương trình chạy liên tục (bot, dashboard, alert bot) **chiếm luôn Terminal đó**.
> Muốn gõ lệnh khác thì mở Terminal mới. Đóng Terminal = tắt chương trình.

---

## 3. Kiểm tra trạng thái & cài đặt

### `./run.sh help` — xem danh sách lệnh

💻 Gõ:
```bash
./run.sh help
```
📤 Bạn sẽ thấy danh sách lệnh chia theo nhóm (CÀI ĐẶT, DỮ LIỆU, NGHIÊN CỨU, CHẠY BOT, THEO DÕI…).

### `./run.sh status` — cái gì đang chạy?

💻 Gõ:
```bash
./run.sh status
```
📤 Bạn sẽ thấy:
```
  [   TẮT   ] Bot Spot (Hybrid)
  [   TẮT   ] Bot Futures
  [ĐANG CHẠY] Bot Breakout  (http://127.0.0.1:8082)
  [   TẮT   ] Bot Smart DCA
  [ĐANG CHẠY] Dashboard  (http://127.0.0.1:8502)
  [   TẮT   ] Alert bot Telegram
```
🧠 Nghĩa là: đang chạy bot Breakout (cổng 8082) và dashboard. Các bot còn lại và alert bot đều tắt. Đây là lệnh
**nên gõ đầu tiên** mỗi khi bạn không nhớ mình đã bật những gì.

### `./run.sh test` — kiểm tra mọi thứ còn hoạt động

💻 Gõ:
```bash
./run.sh test
```
📤 Bạn sẽ thấy:
```
...............                                                          [100%]
23 passed in 16.65s
```
🧠 Nghĩa là: cả 23 bài kiểm tra đều đạt. Nếu có dòng `FAILED`, nghĩa là có gì đó bị hỏng (thường do
vừa sửa code). Copy lỗi gửi cho tôi.

### Các lệnh cài đặt khác

| Lệnh | Khi nào dùng | Ví dụ kết quả |
|---|---|---|
| `./run.sh setup` | Cài lần đầu, hoặc khi báo `Chưa cài đặt` | `[✓] Cài đặt xong. Phiên bản Freqtrade: freqtrade 2026.10` |
| `./run.sh ui` | Cài giao diện web FreqUI, **chỉ chạy 1 lần** | Tải FreqUI về `user_data/` |
| `./run.sh ft --version` | Xem phiên bản Freqtrade | `freqtrade 2026.10` |
| `./run.sh ft list-strategies` | Xem các chiến lược bot nhận ra | Bảng có 5 dòng: `QuantBreakoutStrategy`, `QuantHybridFuturesStrategy`, `QuantHybridStrategy`, `QuantSmartDCAStrategy`, `QuantZScoreStrategy`, cột Status là `OK` |

---

## 4. Dữ liệu nến

Backtest và dashboard cần **dữ liệu nến** (giá mở/đóng/cao/thấp theo từng giờ) tải về máy.
Bot đang chạy thì **tự** lấy giá trực tiếp, không cần lệnh này.

### `./run.sh download [số ngày]` — tải nến Spot

💻 Gõ (tải 365 ngày, mặc định):
```bash
./run.sh download
```
💻 Hoặc chỉ cập nhật vài ngày gần nhất (nhanh, vài giây):
```bash
./run.sh download 3
```
📤 Bạn sẽ thấy:
```
INFO - Downloading parallel candles for 15m for all pairs since 2026-11-19T00:00:00
INFO - Downloaded data for BTC/USDT, 15m, spot with length 344. Parallel Method.
INFO - Downloading parallel candles for 1h for all pairs since 2026-11-19T00:00:00
INFO - Downloaded data for BTC/USDT, 1h, spot with length 86. Parallel Method.
...
Downloading BNB/USDT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4/4 100% • 0:00:01
```
🧠 Nghĩa là: đã tải nến 15m, 1h, 4h của 4 coin. `length 86` = 86 cây nến 1h (≈ 3,5 ngày). Dữ liệu mới
được **nối tiếp** vào dữ liệu cũ, không ghi đè.

**Thêm ví dụ:**

| Bạn muốn | Gõ |
|---|---|
| Tải 2 năm (backtest đáng tin hơn) | `./run.sh download 730` |
| Tải thêm coin XRP và ADA | `./run.sh download 365 -p XRP/USDT ADA/USDT` |
| Chỉ tải BTC | `./run.sh download 365 -p BTC/USDT` |
| Tải nến Futures (cho backtest Futures) | `./run.sh download-futures` |
| Chuyển dữ liệu từ dự án cũ `quant_data.db` | `./run.sh import` (chỉ đọc, không sửa file cũ) |

### Xem đã có dữ liệu gì

💻 Gõ:
```bash
./run.sh ft list-data -c user_data/config.futures.json
```
📤 Bạn sẽ thấy:
```
│    BTC/USDT:USDT │          1h │  funding_rate │
│    BTC/USDT:USDT │      1h, 4h │       futures │
```
🧠 Nghĩa là: đã có nến Futures 1h, 4h của BTC và dữ liệu phí funding. Đổi `config.futures.json` thành
`config.json` để xem dữ liệu Spot.

---

## 5. Backtest Spot — thử chiến lược trên quá khứ

### `./run.sh backtest` — so sánh bản gốc và bản nâng cấp

💻 Gõ:
```bash
./run.sh backtest
```
📤 Bạn sẽ thấy rất nhiều bảng. **Chỉ cần đọc 3 bảng quan trọng nhất**, theo thứ tự từ cuối lên:

**Bảng 1: STRATEGY SUMMARY** (cuối cùng, quan trọng nhất)
```
┃            Strategy ┃ Trades ┃ Tot Profit USDT ┃ Tot Profit % ┃  Win  Draw  Loss  Win% ┃         Drawdown ┃
│ QuantZScoreStrategy │    151 │        -226.209 │       -22.62 │   98     0    53  64.9 │ 263.439 USDT  26.24% │
│ QuantHybridStrategy │     15 │         -60.946 │        -6.09 │    6     0     9  40.0 │  60.948 USDT   6.09% │
```
🧠 Nghĩa là:

| Cột | Ý nghĩa | Đọc ví dụ |
|---|---|---|
| `Trades` | Số lệnh đã vào | Bản gốc 151 lệnh, bản nâng cấp chỉ 15 lệnh (chọn lọc hơn) |
| `Tot Profit %` | Tổng lãi/lỗ so với vốn ban đầu | Bản gốc **lỗ 22,62%**, bản nâng cấp **lỗ 6,09%** |
| `Win%` | Tỷ lệ lệnh thắng | Bản gốc thắng 64,9% nhưng vẫn lỗ, vì lệnh thua lỗ nhiều hơn lệnh thắng lời |
| `Drawdown` | Mức sụt vốn tệ nhất từ đỉnh | Bản gốc có lúc mất 26,24% vốn, bản nâng cấp tối đa 6,09% |

> **Bài học:** tỷ lệ thắng cao **không** có nghĩa là có lãi. Luôn nhìn `Tot Profit %` và `Drawdown`.

**Bảng 2: EXIT REASON STATS** (vì sao lệnh đóng)
```
┃        Exit Reason ┃ Exits ┃ Tot Profit USDT ┃  Win  Draw  Loss  Win% ┃
│           z_revert │     4 │          16.549 │    4     0     0   100 │
│          ema_cross │     3 │         -11.051 │    1     0     2  33.3 │
│          stop_loss │     6 │         -66.445 │    0     0     6     0 │
```
🧠 Nghĩa là:
- `z_revert`: giá hồi về trung bình như kỳ vọng → 4/4 lệnh thắng, lời 16,5 USDT.
- `stop_loss`: chạm cắt lỗ → 6 lệnh, mất 66,4 USDT. **Đây là nguồn lỗ chính.**
- `ema_cross`: xu hướng đảo chiều nên thoát lệnh Trend.

Muốn cải thiện chiến lược thì nhìn bảng này trước.

**Bảng 3: SUMMARY METRICS** (chỉ số tổng hợp, trích các dòng quan trọng)
```
│ Backtesting from                       │ 2026-05-25 11:00:00 │
│ Backtesting to                         │ 2026-11-20 15:00:00 │
│ Starting balance                       │ 1000 USDT           │
│ Final balance                          │ 939.054 USDT        │
│ Profit factor                          │ 0.29                │
│ Market change                          │ -20.12%             │
│ Best trade                             │ SOL/USDT 2.20%      │
│ Worst trade                            │ SOL/USDT -3.56%     │
│ Max Consecutive Wins / Loss            │ 2 / 2               │
```
🧠 Nghĩa là:
- Vốn 1000 USDT còn 939 USDT sau 6 tháng.
- **`Market change −20,12%`**: nếu mua và giữ thì đã lỗ 20%, nên bot lỗ 6% là "đỡ tệ hơn".
- **`Profit factor 0.29`**: cứ lời 1 đồng thì lỗ khoảng 3,4 đồng. Chiến lược tốt cần **> 1,3**.
- Lệnh tệ nhất chỉ −3,56%: cắt lỗ đang hoạt động đúng, không có lệnh nào lỗ nặng.

### Backtest có tuỳ chọn

**Ví dụ 1: chỉ thử tháng 10/2026**

💻 Gõ:
```bash
./run.sh backtest --timerange 20261001-20261101
```
🧠 Nghĩa là: `--timerange NĂMTHÁNGNGÀY-NĂMTHÁNGNGÀY`. Để trống phía sau dấu `-` nghĩa là "đến hết dữ liệu":

| Bạn muốn | Gõ `--timerange` |
|---|---|
| Từ 01/08/2026 đến hết dữ liệu | `20260801-` |
| Từ đầu dữ liệu đến 30/09/2026 | `-20260930` |
| Đúng quý 3/2026 | `20260701-20261001` |

**Ví dụ 2: chỉ thử BTC**

💻 Gõ:
```bash
./run.sh backtest -p BTC/USDT
```

**Ví dụ 3: xem lãi/lỗ từng ngày, tuần, tháng**

💻 Gõ:
```bash
./run.sh backtest --breakdown day week month
```
🧠 Nghĩa là: có thêm bảng **DAY / WEEK / MONTH BREAKDOWN**, rất tiện để biết tháng nào bot lời, tháng nào lỗ.

**Ví dụ 4: kết hợp nhiều tuỳ chọn, vốn 500 USDT, chỉ BTC, từ tháng 10**

💻 Gõ:
```bash
FREQTRADE__DRY_RUN_WALLET=500 ./run.sh backtest -p BTC/USDT --timerange 20261001-
```
📤 Bạn sẽ thấy trong SUMMARY METRICS: `Starting balance │ 500 USDT`.

> ⚠️ Mỗi lần backtest tạo một file kết quả mới, và dashboard luôn hiển thị **lần backtest gần nhất**.
> Sau khi thử nghiệm kiểu ví dụ 4, chạy lại `./run.sh backtest` (không tuỳ chọn) để dashboard hiện
> lại kết quả đầy đủ.

### `./run.sh backtest-all` — so sánh cả 4 chiến lược Spot 🆕

💻 Gõ:
```bash
./run.sh backtest-all
```
📤 Bảng STRATEGY SUMMARY cuối cùng (kết quả thật):
```
┃              Strategy ┃ Trades ┃ Tot Profit % ┃  Win  Draw  Loss  Win% ┃             Drawdown ┃
│   QuantZScoreStrategy │    151 │       -23.87 │   97     0    54  64.2 │ 263.439 USDT  26.24% │
│   QuantHybridStrategy │     15 │        -6.09 │    6     0     9  40.0 │  60.948 USDT   6.09% │
│ QuantBreakoutStrategy │     49 │        -0.54 │   17     0    32  34.7 │ 109.178 USDT  10.22% │
│ QuantSmartDCAStrategy │     89 │        -2.29 │   80     0     9  89.9 │  39.876 USDT   3.94% │
```
🧠 Nghĩa là: hai chiến lược **thắng ít mà vẫn lỗ ít** và **thắng nhiều mà vẫn lỗ** cho thấy tỷ lệ thắng
không quyết định:
- **Breakout** chỉ thắng 35% nhưng gần hoà vốn: lệnh thắng "chạy" xa nhờ cắt lỗ kéo theo, lệnh thua bị cắt sớm.
- **Smart DCA** thắng 90% (chốt lời nhỏ 4%) nhưng vài lần chạm cắt lỗ −12% đã ăn hết lời. Bù lại sụt vốn
  chỉ 3,9% vì tổng tiền mỗi coin bị giới hạn theo % rủi ro.

Các tuỳ chọn của `backtest` (`--timerange`, `-p`, `--breakdown`) đều dùng được với `backtest-all`.
Kết quả này cũng hiện ở dashboard: tab 🧭 Tư vấn → **Thư viện chiến lược**.

### Xem lại & vẽ biểu đồ

| Bạn muốn | Gõ | Kết quả |
|---|---|---|
| Xem lại kết quả cũ, không chạy lại | `./run.sh ft backtesting-show` | In lại đúng các bảng ở trên |
| Vẽ lệnh lên biểu đồ BTC | `./run.sh plot` | File `user_data/plot/freqtrade-plot-BTC_USDT-1h.html`, mở bằng trình duyệt |
| Vẽ cho ETH | `./run.sh plot ETH/USDT` | File `...-ETH_USDT-1h.html` |
| Biểu đồ lợi nhuận tích luỹ | `./run.sh ft plot-profit -c user_data/config.json -s QuantHybridStrategy` | File `user_data/plot/freqtrade-profit-plot.html` |

Mở file biểu đồ vừa vẽ:
```bash
open user_data/plot/freqtrade-plot-BTC_USDT-1h.html
```

### `./run.sh legacy` — backtest kiểu cũ để đối chiếu

💻 Gõ:
```bash
./run.sh legacy
```
📤 Bạn sẽ thấy:
```
BACKTEST KIỂU CŨ — Z-Score 50 nến, mua Z<-2.0, bán Z>=0.0, phí 0.10%/chiều, khung 1h
     Cặp  Số lệnh  Lợi nhuận bot %  Mua & giữ %  Sharpe  Max DD %
BTC/USDT       47           -21.70       -23.03   -1.61    -24.40
ETH/USDT       40           -26.87       -23.14   -1.60    -33.05
SOL/USDT       45           -27.72       -20.12   -1.42    -30.98
BNB/USDT       45           -15.22       -15.37   -1.06    -23.33
```
🧠 Nghĩa là: đây là cách tính của `3_backtest_engine.py` cũ (mỗi coin dùng toàn bộ vốn, tính riêng).
Dùng để chắc chắn bản port sang Freqtrade cho kết quả **giống** bản cũ.

---

## 6. Kiểm tra & tối ưu chiến lược

### `./run.sh check-bias` — chiến lược có "gian lận" không?

"Lookahead bias" là lỗi chiến lược vô tình dùng **giá tương lai**, khiến backtest đẹp giả tạo nhưng
chạy thật thì thua.

💻 Gõ:
```bash
./run.sh check-bias
```
📤 Bạn sẽ thấy (mất khoảng 1 phút):
```
┃               filename ┃            strategy ┃ has_bias ┃ total_signals ┃ biased_entry_signals ┃ biased_exit_signals ┃
│ QuantHybridStrategy.py │ QuantHybridStrategy │       No │             8 │                    0 │                   0 │
│ QuantZScoreStrategy.py │ QuantZScoreStrategy │       No │             8 │                    0 │                   0 │
│ QuantBreakoutStrategy.py │ QuantBreakoutStrategy │    No │            10 │                    0 │                   0 │
│ QuantSmartDCAStrategy.py │ QuantSmartDCAStrategy │    No │            10 │                    0 │                   0 │
```
🧠 Nghĩa là: `has_bias = No` → **an toàn**, không dùng giá tương lai. Nếu thấy `Yes`, chiến lược có lỗi:
đừng tin backtest của nó. Mặc định lệnh kiểm tra 120 ngày gần nhất. Muốn đổi khoảng thời gian:
`./run.sh check-bias --timerange 20260601-`.

### `./run.sh hyperopt [số vòng]` — tự tìm tham số tốt hơn

Hyperopt thử hàng trăm bộ tham số (ngưỡng Z-Score, ngưỡng ADF, khoảng cắt lỗ…) và giữ lại bộ tốt nhất.

💻 Gõ (200 vòng, khoảng 10–30 phút):
```bash
./run.sh hyperopt
```
💻 Hoặc chạy thử nhanh 20 vòng:
```bash
./run.sh hyperopt 20
```
📤 Khi chạy xong bạn sẽ thấy dạng:
```
┃ Best   ┃ Epoch ┃ Trades ┃   Win% ┃ profit ┃ ...
│ * Best │  1/20 │     76 │     36 │ -0.48% │ ...
│ * Best │  2/20 │     55 │     29 │ -0.07% │ ...
Best result:

    # Buy hyperspace params:
    buy_params = {
        "adf_threshold": 0.15,
        "z_entry": 2.3,
        ...
    }
```
(Các con số `0.15`, `2.3` chỉ là ví dụ, mỗi lần chạy ra kết quả khác.)
🧠 Nghĩa là: mỗi dòng `* Best` là lần tìm được bộ tham số tốt hơn lần trước. Bộ tốt nhất **tự động
được lưu** vào `user_data/strategies/QuantHybridStrategy.json`, và mọi lần backtest/chạy bot sau sẽ dùng nó.

**Sau khi hyperopt xong:**

| Bạn muốn | Gõ |
|---|---|
| Xem lại các kết quả tốt nhất | `./run.sh ft hyperopt-list --best` |
| Xem chi tiết bộ tham số tốt nhất | `./run.sh ft hyperopt-show --best` |
| **Quay về tham số mặc định** | `rm user_data/strategies/QuantHybridStrategy.json` |

> ⚠️ **Bẫy "học thuộc bài":** hyperopt có thể tìm ra tham số chỉ đẹp trên đúng giai đoạn đã thử.
> Cách kiểm tra: tối ưu trên một giai đoạn, rồi backtest trên giai đoạn **khác**:
> ```bash
> ./run.sh hyperopt 200 --timerange 20260525-20260901
> ```
> ```bash
> ./run.sh backtest --timerange 20260901-
> ```
> Nếu giai đoạn sau vẫn tốt thì tham số mới đáng tin.

---

## 7. Chạy bot Spot bằng tiền ảo

### `./run.sh dryrun` — bật bot Spot

💻 Gõ (nên mở một Terminal riêng cho bot):
```bash
./run.sh dryrun
```
📤 Bạn sẽ thấy các dòng log chạy liên tục, trong đó có:
```
INFO - Using Protections:
CooldownPeriod - Cooldown period for 2 candles.
StoplossGuard - Frequent Stoploss Guard, 3 stoplosses with profit < 0.00% within 24 candles.
MaxDrawdown - Max drawdown protection, stop trading if drawdown is > 0.15 within 168 candles.
INFO - Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
INFO - Bot heartbeat. PID=46183, version='2026.10', state='RUNNING'
```
🧠 Nghĩa là:
- `Protections`: 3 bộ bảo vệ đang bật (nghỉ 2 nến sau mỗi lệnh, tạm dừng sau 3 lần cắt lỗ, dừng khi sụt vốn > 15%).
- `Uvicorn running on ...8080`: giao diện web của bot đã sẵn sàng.
- `state='RUNNING'`: bot đang chạy. Dòng "heartbeat" lặp lại định kỳ cho biết bot vẫn sống.

Đồng thời Telegram nhận tin "bot khởi động". **Để nguyên Terminal này.** Muốn tắt bot thì bấm `Ctrl + C`.

> Bot dùng nến 1h nên **có thể vài giờ đến vài ngày mới có lệnh đầu tiên**. Đó là bình thường.

**Các cách xem bot:**

| Cách | Làm gì |
|---|---|
| **FreqUI** (web) | Mở http://127.0.0.1:8080 · Username: `freqtrader` · Password: mở file `.env`, xem dòng `FREQTRADE__API_SERVER__PASSWORD=` |
| **Dashboard** | http://localhost:8502 → tab 🤖 Bot Freqtrade → chọn **Spot · 8080** |
| **Telegram** | Nhắn `/status`, `/profit`… (xem mục 10) |
| **Terminal** | `./run.sh trades` (bên dưới) |

**Biến thể:**

| Bạn muốn | Gõ |
|---|---|
| Chạy bot nhưng **không** gửi Telegram | `FREQTRADE__TELEGRAM__ENABLED=false ./run.sh dryrun` |
| Chạy với ví ảo 500 USDT | `FREQTRADE__DRY_RUN_WALLET=500 ./run.sh dryrun` |
| Tối đa 2 lệnh cùng lúc (mặc định 3) | `FREQTRADE__MAX_OPEN_TRADES=2 ./run.sh dryrun` |

### Chạy bot Breakout / Smart DCA 🆕

Mỗi bot có **cổng web và database riêng**, nên chạy song song với bot Hybrid được (mỗi bot 1 Terminal).

| Bạn muốn | Gõ | Xem bot ở |
|---|---|---|
| Bot Breakout (mua theo đà) | `./run.sh dryrun-breakout` | http://127.0.0.1:8082 · dashboard tab 🤖 → **Breakout · 8082** |
| Bot Smart DCA (tích luỹ) | `./run.sh dryrun-dca` | http://127.0.0.1:8083 · dashboard tab 🤖 → **Smart DCA · 8083** |
| Bot DCA **có Telegram** (bot Hybrid phải đang tắt) | `STRATEGY_TELEGRAM=true ./run.sh dryrun-dca` | Telegram `/status`, `/profit`… |

Xem lịch sử lệnh của 2 bot này:
```bash
./run.sh ft show-trades -c user_data/config.json --db-url sqlite:///user_data/tradesv3.breakout.dryrun.sqlite
```
(đổi `breakout` thành `dca` cho bot Smart DCA).

> Bot Smart DCA **mua thêm khi giá giảm**. Trong `/status` bạn sẽ thấy `Number of Entries: 2/3` nghĩa là
> đã mua 2 trong tối đa 3 lần.

### `./run.sh trades` — xem lịch sử lệnh trong Terminal

💻 Gõ (bot không cần đang chạy):
```bash
./run.sh trades
```
📤 Khi chưa có lệnh nào:
```
INFO - Using DB: "sqlite:///tradesv3.dryrun.sqlite"
INFO - Printing 0 Trades:
```
🧠 Nghĩa là: bot chưa vào lệnh nào. Khi có lệnh, mỗi lệnh hiện 1 dòng dạng
`Trade(id=1, pair=SOL/USDT, amount=10.65, is_short=False, leverage=1.0, open_rate=70.18, open_since=...)`.

---

## 8. Futures — Long, Short, đòn bẩy

> ⚠️ Futures có đòn bẩy: x3 nghĩa là giá đi ngược 1% thì bạn lỗ 3%. Backtest Futures hiện **đang lỗ
> 8,64%**. Chỉ chạy tiền ảo.

**Khác biệt so với Spot:**

| | Spot | Futures |
|---|---|---|
| Lệnh chạy bot | `./run.sh dryrun` | `./run.sh dryrun-futures` |
| Hướng | Chỉ Long | Long **và** Short |
| Đòn bẩy | Không | Bot tự chọn: Trend x3 · Mean Reversion x2 (x5 khi \|Z\| ≥ 3) |
| Cách viết cặp coin | `BTC/USDT` | `BTC/USDT:USDT` |
| Cổng web / FreqUI | 8080 | 8081 |
| Telegram | Bật | **Tắt** mặc định |
| File cấu hình | `user_data/config.json` | `user_data/config.futures.json` |
| Kiểu vào lệnh (enter tag) | `mean_rev`, `trend` | thêm `mean_rev_short`, `trend_short` |

### Bước 1: tải dữ liệu Futures (bắt buộc trước khi backtest Futures)

💻 Gõ:
```bash
./run.sh download-futures
```
🧠 Nghĩa là: tải nến Futures 1h, 4h và **phí funding** (phí trả 8 giờ/lần khi giữ lệnh Futures) trong 365 ngày.

### Bước 2: backtest Futures

💻 Gõ:
```bash
./run.sh backtest-futures
```
📤 Đọc giống mục 5. Trong SUMMARY METRICS có thêm các dòng Long/Short. Kết quả hiện tại:
```
┃                   Strategy ┃ Trades ┃ Avg Profit % ┃ Tot Profit USDT ┃ Tot Profit % ┃   Avg Duration ┃  Win  Draw  Loss  Win% ┃             Drawdown ┃
│ QuantHybridFuturesStrategy │     36 │         0.21 │         -86.404 │        -8.64 │ 1 day, 3:15:00 │   17     0    19  47.2 │ 123.215 USDT  12.32% │
```
🧠 Nghĩa là: 36 lệnh (cả Long và Short), thắng 17, thua 19, tổng lỗ 86,4 USDT (−8,64%), sụt vốn tối đa
12,32%. Rủi ro cao hơn Spot (6,09%) vì có đòn bẩy. Để ý `Avg Profit % = 0.21` **dương** mà tổng vẫn lỗ:
các lệnh lỗ dùng đòn bẩy cao hơn nên mất nhiều tiền hơn.

**Thêm ví dụ:**

| Bạn muốn | Gõ |
|---|---|
| Backtest Futures từ tháng 8 | `./run.sh backtest-futures --timerange 20260801-` |
| Chỉ BTC (nhớ đuôi `:USDT`) | `./run.sh backtest-futures -p BTC/USDT:USDT` |
| Xem Long và Short riêng theo tháng | `./run.sh backtest-futures --breakdown month` |

Vẽ biểu đồ lệnh Futures BTC:
```bash
./run.sh ft plot-dataframe -c user_data/config.futures.json -s QuantHybridFuturesStrategy -p BTC/USDT:USDT --indicators1 rolling_mean ema_fast ema_slow --indicators2 z_score adf_p
```

### Bước 3: chạy bot Futures tiền ảo

**Trường hợp A: chạy song song với bot Spot (Telegram tắt cho bot Futures)**

💻 Gõ (trong Terminal riêng):
```bash
./run.sh dryrun-futures
```
📤 Log giống bot Spot nhưng có `Uvicorn running on http://127.0.0.1:8081`.

🧠 Nghĩa là: bot Futures chạy, không gửi Telegram. Xem bot ở http://127.0.0.1:8081 (cùng tài khoản,
mật khẩu như Spot) hoặc dashboard → tab 🤖 Bot Freqtrade → **Futures · 8081**.

**Trường hợp B: chỉ chạy bot Futures, muốn có Telegram**

💻 Gõ (bot Spot phải **đang tắt**):
```bash
FUTURES_TELEGRAM=true ./run.sh dryrun-futures
```
🧠 Nghĩa là: bot Futures dùng token Telegram. Lúc này `/status`, `/profit`, `/profit_short`… trả lời
về bot Futures.

> ❌ **Đừng** bật `FUTURES_TELEGRAM=true` khi bot Spot đang chạy: hai bot tranh một token, Telegram
> sẽ báo lỗi `Conflict: terminated by other getUpdates request`.

### Xem lịch sử lệnh Futures

💻 Gõ:
```bash
./run.sh trades-futures
```
📤 Mỗi lệnh có thêm thông tin `is_short=True` (lệnh Short) và `leverage=3.0` (đòn bẩy).

---

## 9. Alert bot — cảnh báo Telegram + Gemini AI

Bản nâng cấp của `4_alert_bot.py`. Bot **chỉ gửi tín hiệu** để bạn tự quyết định, **không tự đặt lệnh**.
Mỗi tin gồm phân tích Gemini, Z-Score/EMA/ADF, gợi ý **Spot** và **Futures** (đòn bẩy, ký quỹ, Min
Notional, phí, TP/SL).

### `./run.sh alert --once` — quét thử 1 lần

💻 Gõ:
```bash
./run.sh alert --once
```
📤 Khi **chưa** có tín hiệu (trường hợp thường gặp):
```
=== QUANT ALERT BOT (Mean Reversion + Trend + ADF + Gemini + Freqtrade) ===
AI: BẬT (gemini-2.5-flash) | Telegram: BẬT
[20:32:46] Quét thị trường | Vốn $1,000.00 | Rủi ro 1.5%
  -> BTC/USDT: $60,835.06 | Z=1.07σ | EMA gap=-0.05% | ADF=0.389 | Min=$5.0
  -> ETH/USDT: $1,708.30 | Z=1.08σ | EMA gap=0.01% | ADF=0.275 | Min=$5.0
  -> SOL/USDT: $70.16 | Z=0.57σ | EMA gap=-0.25% | ADF=0.221 | Min=$5.0
  -> BNB/USDT: $555.22 | Z=1.02σ | EMA gap=-0.30% | ADF=0.385 | Min=$5.0
```
🧠 Đọc từng chỉ số trên dòng BTC:

| Chỉ số | Giá trị | Ý nghĩa | Khi nào có tín hiệu |
|---|---|---|---|
| `Z` | 1.07σ | Giá cao hơn trung bình 50 nến khoảng 1 độ lệch chuẩn | \|Z\| ≥ 2 (Mean Reversion) |
| `EMA gap` | −0.05% | EMA20 gần như trùng EMA50, chưa có xu hướng rõ | \|gap\| ≥ 1,5% (Trend) |
| `ADF` | 0.389 | ≥ 0,20 → thị trường **có xu hướng**, không đi ngang | < 0,20 mới đánh Mean Reversion |
| `Min` | $5.0 | Giá trị lệnh nhỏ nhất Binance Futures cho phép | — |

Kết luận: không coin nào đủ điều kiện, nên bot không gửi tin.

📤 Khi **có** tín hiệu, Telegram nhận tin dạng (minh hoạ):
```
🤖 QUANT × FREQTRADE: SOL/USDT

🧠 AI:
- Nhận diện: Sideway, giá lệch sâu dưới trung bình
- Chiến lược: Mean Reversion
- Hành động: Ưu tiên Long, khối lượng nhỏ

📊 Chỉ số (1h):
• Chiến lược: 🔄 MEAN REVERSION (mạnh)
• Hướng: 🟢 LONG
• Giá: $66.2100 | Z: -2.86σ | EMA gap: -0.40% | ADF: 0.140
• Phiên: 🇺🇸 Phiên Mỹ + Âu | Tin tức: 🔴 Tiêu cực

📦 SPOT: mua $512.40 — TP $68.9000 | SL $64.2700
⚡ FUTURES: x2, ký quỹ $256.20 (lệnh $512.40)
• Lỗ tối đa nếu chạm SL: $15.00
• Phí sàn 2 chiều (ước tính): ~$0.5124
• TP $68.9000 | SL $64.2700 | R:R 1:1.4

🕒 Thời gian gửi: 20:33:19 - 22/11/2026
```
🧠 Đọc tin:
- **SPOT:** mua khoảng 512 USDT SOL, đặt chốt lời ở 68,90 và cắt lỗ ở 64,27.
- **FUTURES:** dùng x2, chỉ cần ký quỹ 256 USDT cho lệnh 512 USDT.
- **Lỗ tối đa $15:** đúng 1,5% của vốn 1000 USDT (mức rủi ro bạn đặt trên dashboard).
- **R:R 1:1.4:** chấp nhận mất 1 để có cơ hội lời 1,4.

### Các tuỳ chọn của alert bot

| Bạn muốn | Gõ |
|---|---|
| Chạy liên tục, quét mỗi 5 phút (chế độ nâng cấp, có lọc ADF) | `./run.sh alert` |
| Báo tín hiệu **y hệt bản cũ** (không lọc ADF, báo nhiều hơn) | `./run.sh alert --legacy` |
| Thử mà **không gửi** Telegram (chỉ in ra màn hình) | `TELEGRAM_BOT_TOKEN= ./run.sh alert --once` |
| Theo dõi coin khác | `./run.sh alert --pairs BTC/USDT ETH/USDT XRP/USDT` |
| Dùng khung 4h | `./run.sh alert --timeframe 4h` |
| Quét mỗi 10 phút | `./run.sh alert --interval 600` |
| Cùng tín hiệu chỉ báo lại sau 2 giờ (mặc định 1 giờ) | `./run.sh alert --cooldown 120` |
| Z-Score 30 nến (nhạy hơn, mặc định 50) | `./run.sh alert --window 30` |

**Ví dụ kết hợp:** chế độ cũ, chỉ BTC và SOL, quét mỗi 10 phút:
```bash
./run.sh alert --legacy --pairs BTC/USDT SOL/USDT --interval 600
```

> Đừng chạy cùng lúc `4_alert_bot.py` cũ và alert bot mới, vì bạn sẽ nhận tin **trùng**.

---

## 10. Lệnh Telegram điều khiển bot Freqtrade

Gõ **trong khung chat Telegram với bot của bạn** khi `./run.sh dryrun` đang chạy (hoặc bot Futures chạy
với `FUTURES_TELEGRAM=true`). Gõ `/help` để xem toàn bộ.

> Các câu trả lời bên dưới là **minh hoạ** dựa trên định dạng của Freqtrade 2026.10, với một lệnh giả
> định: Long SOL ở giá 70,18. Bot chưa có lệnh thật nào. Câu trả lời của bot là tiếng Anh.

### Tin bot tự gửi (không cần gõ gì)

**Khi vào lệnh:**
```
🔵 Binance (dry): New Trade (#3)
Pair: SOL/USDT
Enter Tag: mean_rev
Amount: 10.65
Direction: Long
Open Rate: 70.18 USDT
Total: 747.59 USDT
```
🧠 Nghĩa là: lệnh số **3**, mua 10,65 SOL (≈ 747,59 USDT) theo kiểu `mean_rev` (bắt đáy khi thị trường
đi ngang). `(dry)` = tiền ảo. Biểu tượng ✅ thay 🔵 nghĩa là lệnh đã **khớp**.

**Khi thoát lệnh có lời:**
```
✳️ Binance (dry): Exited SOL/USDT (#3)
Profit: 1.52% (profit: 11.36 USDT)
Enter Tag: mean_rev
Exit Reason: z_revert
Direction: Long
Open Rate: 70.18 USDT
Exit Rate: 71.39 USDT
Duration: 18:45:00 (1125.0 min)
```
🧠 Nghĩa là: lệnh #3 lời 1,52% (11,36 USDT) sau 18 giờ 45 phút, đóng vì `z_revert` (giá đã hồi về
trung bình). Khi chạm cắt lỗ, biểu tượng là ⚠️ và `Exit Reason: stop_loss`.

**Bảng lý do thoát lệnh (Exit Reason):**

| Exit Reason | Nghĩa |
|---|---|
| `z_revert` | Mean Reversion thành công: giá hồi về trung bình |
| `mr_timeout` | Giữ lệnh Mean Reversion quá 48 giờ mà giá chưa hồi → thoát |
| `ema_cross` | Lệnh Trend: EMA20 cắt xuống EMA50, xu hướng kết thúc |
| `stop_loss` | Chạm cắt lỗ (2σ) |
| `trailing_stop_loss` | Cắt lỗ đã dời lên **hoà vốn**, giá quay về chạm |
| `roi` | Lời đủ 25% → chốt |
| `force_exit` | Bạn tự đóng bằng `/forceexit` |

### 10.1. Xem trạng thái

**`/status`: các lệnh đang mở**

💻 Gõ: `/status`

📤 Bot trả lời:
```
Trade ID: 3 (since 5 hours ago)
Current Pair: SOL/USDT
Direction: Long
Amount: 10.65 (747.59 USDT)
Enter Tag: mean_rev
Open Rate: 70.18
Open Date: 2026-11-22 08:00:00
Current Rate: 70.95
Unrealized Profit: 0.89% (6.62 USDT)

Stoploss: 68.42 (-2.51%)
Stoploss distance: -2.53 (-3.57%)
```
🧠 Nghĩa là: lệnh #3 mở 5 giờ trước, đang **tạm lời** 0,89% (chưa chốt). Cắt lỗ ở 68,42, tức cách
lúc vào −2,51% và cách giá hiện tại −3,57%. Với lệnh Futures sẽ có thêm `Liquidation:` (giá bị thanh lý).

| Lệnh | Tác dụng | Ví dụ |
|---|---|---|
| `/status` | Chi tiết tất cả lệnh đang mở | Như trên |
| `/status table` | Dạng bảng gọn, 1 dòng mỗi lệnh | `3  SOL  5 hours  0.89%` |
| `/status 3` | Chỉ xem lệnh số 3 | |
| `/count` | Đang mở bao nhiêu lệnh / tối đa | `1 / 3`: còn chỗ cho 2 lệnh |
| `/balance` | Số dư bot đang quản lý | `USDT: 252.41 … Estimated Value: 1006.62 USDT` |
| `/balance full` | Toàn bộ số dư tài khoản | |
| `/locks` | Coin bị tạm khoá bởi bộ bảo vệ | `SOL/USDT until 2026-11-22 15:00 (Cooldown period)` |
| `/whitelist` | Danh sách coin bot giao dịch | `BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT` |
| `/show_config` | Cấu hình đang chạy | Chiến lược, khung giờ, cắt lỗ, dry-run… |
| `/health` | Lần cuối bot xử lý | Thời gian cách đây vài giây → bot còn sống |
| `/logs` · `/logs 30` | 10 (hoặc 30) dòng log mới nhất | |
| `/version` | Phiên bản | `Version: 2026.10` |

### 10.2. Lãi / lỗ & thống kê

**`/profit`: tổng kết lãi/lỗ**

💻 Gõ: `/profit`

📤 Bot trả lời:
```
ROI: Closed trades
∙ 11.36 USDT (1.52%) (1.14 Σ%)
ROI: All trades
∙ 17.98 USDT (1.21%) (1.8 Σ%)
Total Trade Count: 2
Bot started: 2026-11-22 08:00:00
Win / Loss: 1 / 0
Winrate: 100.00%
Avg. Duration: 18:45:00
Best Performing: SOL/USDT: 11.36 USDT (1.52%)
Profit factor: ...
Max Drawdown: 0.00% (0 USDT)
```
🧠 Nghĩa là:
- `Closed trades`: lệnh **đã đóng** lời 11,36 USDT. `1.52%` là lời trung bình mỗi lệnh. **`1.14 Σ%`** là lời so với **tổng vốn** (11,36 / 1000).
- `All trades`: tính cả lệnh đang mở (+6,62 tạm lời) → 17,98 USDT.
- `Win / Loss 1 / 0`: 1 lệnh thắng, 0 lệnh thua.

| Lệnh | Tác dụng | Ví dụ dùng |
|---|---|---|
| `/profit` | Tổng lãi/lỗ từ đầu | Xem hằng ngày |
| `/profit 7` | Chỉ tính 7 ngày gần nhất | "Tuần này bot thế nào?" |
| `/profit_long` · `/profit_short` | Riêng lệnh Long / Short | Futures: "Short có hiệu quả không?" |
| `/daily` | Lãi/lỗ từng ngày, 7 ngày gần nhất | `2026-11-22  11.36 USDT  1 trade` |
| `/daily 30` | 30 ngày gần nhất | |
| `/weekly` · `/monthly` | Theo tuần / tháng | `/monthly 6`: 6 tháng |
| `/trades` · `/trades 20` | 10 (hoặc 20) lệnh đã đóng gần nhất | |
| `/performance` | Lãi/lỗ theo từng coin | `1. SOL/USDT 11.36 USDT (1.52%) (1)` |
| `/entries` | Lãi/lỗ theo kiểu vào lệnh | `mean_rev` lời, `trend` lỗ → biết phần nào của chiến lược tốt |
| `/exits` | Lãi/lỗ theo lý do thoát | Nhiều `stop_loss` → cắt lỗ đang quá chặt hoặc vào lệnh sai |
| `/mix_tags` | Kết hợp kiểu vào + lý do thoát | `mean_rev + z_revert`: 4 lệnh, 100% thắng |
| `/stats` | Thống kê thắng/thua & thời gian giữ lệnh | |

### 10.3. Điều khiển bot

| Lệnh | Tác dụng | Khi nào dùng |
|---|---|---|
| `/stopentry` (hoặc `/pause`) | **Ngừng mở lệnh mới**, lệnh đang mở vẫn được quản lý (cắt lỗ, chốt lời bình thường) | Tin xấu lớn, muốn tạm nghỉ — **cách an toàn nhất** |
| `/start` | Cho bot hoạt động lại | Sau `/stopentry` hoặc `/stop` |
| `/stop` | Dừng hẳn giao dịch. Lệnh đang mở **không** được quản lý nữa | Ít dùng; trên Terminal thì `Ctrl + C` có tác dụng tương tự |
| `/reload_config` | Đọc lại file cấu hình | Vừa sửa `config.json` (thêm coin…) mà không muốn tắt bot |

**Ví dụ: tin xấu, muốn bot nghỉ đến sáng mai**
```
/stopentry      → bot ngừng mở lệnh mới
/status         → kiểm tra các lệnh còn mở (bot vẫn tự quản lý chúng)
... sáng hôm sau ...
/start          → bot hoạt động lại
```

### 10.4. Can thiệp lệnh bằng tay ⚠️

| Lệnh | Tác dụng | Ví dụ |
|---|---|---|
| `/forceexit 3` (hoặc `/fx 3`) | Đóng **ngay** lệnh số 3 theo giá thị trường | Muốn chốt lời sớm lệnh #3 |
| `/forceexit all` | Đóng **tất cả** lệnh đang mở | Thị trường sập, muốn ra hết |
| `/coo 3` | Huỷ lệnh đang chờ khớp của lệnh #3 | Lệnh treo mãi không khớp |
| `/delete 3` | Xoá lệnh #3 khỏi database (không đặt lệnh lên sàn) | Dọn lệnh lỗi |
| `/reload_trade 3` | Đồng bộ lại lệnh #3 từ sàn | Số liệu bot lệch với sàn |
| `/forcelong BTC/USDT` | Mở Long ngay | **Mặc định bị tắt** (xem ghi chú) |
| `/forceshort BTC/USDT:USDT` | Mở Short ngay (Futures) | **Mặc định bị tắt** |

**Ví dụ: chốt lời sớm lệnh #3**
```
/status table   → tìm ID lệnh muốn đóng (ví dụ 3)
/forceexit 3    → bot đóng lệnh #3, gửi tin "Exited SOL/USDT (#3)" với Exit Reason: force_exit
/profit         → xem tổng kết sau khi đóng
```

> `/forcelong` và `/forceshort` chỉ hoạt động khi đặt `"force_entry_enable": true` trong file cấu hình.
> Tôi để **tắt** vì vào lệnh bằng tay phá vỡ kỷ luật của chiến lược.

### 10.5. Quản lý coin

| Lệnh | Tác dụng | Ví dụ |
|---|---|---|
| `/blacklist DOGE/USDT` | Cấm bot giao dịch coin này (đến khi khởi động lại bot) | Coin có tin xấu riêng |
| `/blacklist` | Xem danh sách cấm | |
| `/bl_delete DOGE/USDT` | Bỏ cấm | |
| `/unlock SOL/USDT` | Mở khoá coin đang bị bộ bảo vệ khoá | Thấy SOL bị khoá ở `/locks` nhưng muốn bot giao dịch lại ngay |

---

## 11. Dashboard

💻 Gõ (Terminal riêng):
```bash
./run.sh dashboard
```
📤 Bạn sẽ thấy:
```
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8502
```
Sau đó mở http://localhost:8502. Muốn dùng cổng khác (khi 8502 bị chiếm):
`./run.sh dashboard --server.port 8600`.

| Tab | Dùng để |
|---|---|
| 🏠 Tổng quan | Giá trực tiếp, tín hiệu từng coin kèm giá vào/SL/TP/khối lượng, "mức gần tín hiệu", trạng thái bot, kết quả backtest |
| 🧭 Tư vấn 🆕 | Chấm điểm từng coin, chiến lược phù hợp, phân bổ vốn theo hồ sơ rủi ro, AI tóm tắt, thư viện 5 chiến lược (xem mục 11.1) |
| 📈 Phân tích | Biểu đồ nến + ±2σ + EMA, Z-Score, ADF, đánh dấu ▲▼ các điểm vào lệnh trong quá khứ |
| 🎯 Screener | Bảng so sánh tất cả coin, ma trận tương quan |
| 🛡️ Vốn & Rủi ro | **Đặt vốn và % rủi ro mỗi lệnh. Bot dùng thật con số này**, kèm biểu đồ kịch bản lệnh |
| 📰 Tin tức | Tin CoinDesk/CoinTelegraph kèm điểm tâm lý (≤ −4 → bot chặn lệnh Long) |
| 🤖 Bot Freqtrade | Theo dõi bot Spot (8080) hoặc Futures (8081), tự làm mới 30 giây |
| 📊 Backtest | Bảng so sánh, đường cong vốn, Half-Kelly |

### 11.1. Tab 🧭 Tư vấn — đọc thế nào 🆕

Tab này **gom mọi phân tích** thành câu trả lời cho 3 câu hỏi: *thị trường đang thế nào? nên dùng chiến
lược nào? chia vốn ra sao?* Mọi kết luận đi từ quy tắc cố định và số liệu hiển thị ngay trên thẻ.

> ⚠️ Đây là **phân tích tự động theo quy tắc**, không phải lời khuyên đầu tư cá nhân. Tôi (Claude) không
> phải chuyên gia tư vấn tài chính được cấp phép. Hãy coi tab này là "trợ lý phân tích", và kiểm chứng
> bằng dry-run trước khi dùng tiền thật.

**Bước 1: chọn hồ sơ rủi ro**

| Hồ sơ | Rủi ro mỗi lệnh | Futures | Tiền mặt tối thiểu | Tối đa mỗi coin |
|---|---|---|---|---|
| Thận trọng | 0,75% | Không | 50% | 20% |
| Cân bằng (mặc định) | 1,5% | Tối đa x2 | 30% | 30% |
| Mạo hiểm | 2,5% | Tối đa x3 | 10% | 40% |

Nút **"Áp dụng rủi ro …%/lệnh cho bot"** lưu mức rủi ro đó để các bot dùng cho lệnh tiếp theo.

**Bước 2: đọc thẻ từng coin.** Ví dụ thật lúc 21:30 ngày 22/11/2026:
```
SOL/USDT                                   −58
Xu hướng giảm · RSI 52 · 7 ngày −3.5%
[SHORT KHI HỒI] [XU HƯỚNG GIẢM]
Trend Following — Short (Futures)
  Xu hướng      ◀━━━━━━━━|            −2.0
  Động lượng        ◀━━━━|            −0.7
  Định giá (Z)        ◀━━|            −0.4
  Độ ổn định             |━━▶         +0.6
  Tin tức       ◀━━━━━━━━|            −2.0
• Giá dưới EMA50 khung 4h và EMA20 < EMA50 (−0.25%) → xu hướng giảm.
• Spot: đứng ngoài. Futures: chờ nhịp hồi lên để Short thuận xu hướng.
🎯 Chờ Short khi giá hồi về EMA20 ≈ 69.97
Kiểm chứng: bot QuantHybridFuturesStrategy backtest −8.64%, sụt vốn 12.3%
```
🧠 Nghĩa là:
- **Điểm −58** = (35 × −2,0 + 20 × −0,7 + 20 × −0,4 + 10 × 0,6 + 15 × −2,0) ÷ 2. Mỗi yếu tố chấm từ −2 đến +2:
  - **Xu hướng −2**: giá dưới EMA50 khung 4h **và** EMA20 < EMA50.
  - **Động lượng −0,7**: giảm 3,5% trong 7 ngày (−5%/tuần = −1).
  - **Định giá −0,4**: Z-Score hơi dương → giá không rẻ.
  - **Độ ổn định +0,6**: biến động hiện thấp hơn bình thường → điểm cộng.
  - **Tin tức −2**: điểm tin tức −9, rất tiêu cực.
- **Spot: đứng ngoài.** Với Futures (hồ sơ Cân bằng/Mạo hiểm) gợi ý Short khi giá hồi lên EMA20.
- Dòng **"Kiểm chứng"** cho biết chiến lược được gợi ý đã từng cho kết quả ra sao trong backtest. Ở đây
  là −8,64%, nên **không đủ tốt** để làm theo bằng tiền thật.

**Các kiểu gợi ý bạn sẽ gặp:**

| Gợi ý | Khi nào | Bot tương ứng |
|---|---|---|
| Mua (hồi quy) | Đi ngang + Z ≤ −2 | Hybrid |
| Chờ vùng giá đẹp | Đi ngang, Z trong ±2 → kèm 🎯 vùng mua/bán đặt lệnh chờ | Hybrid |
| Mua theo đà | Xu hướng tăng + giá vừa phá đỉnh 48 giờ | Breakout |
| Mua khi điều chỉnh | Xu hướng tăng + giá về gần trung bình | Hybrid (trend) |
| Chờ điều chỉnh | Xu hướng tăng nhưng giá đã cao → kèm 🎯 vùng chờ mua | — |
| Tích luỹ từng phần | Xu hướng giảm nhưng quá bán sâu (Z ≤ −2, RSI < 30) | Smart DCA |
| Short khi hồi | Xu hướng giảm, hồ sơ cho phép Futures | Hybrid Futures |
| Đứng ngoài | Xu hướng giảm (Spot) hoặc chưa rõ | — |

**Bước 3: phân bổ vốn.** Hệ thống chỉ chọn coin **điểm dương và không ở xu hướng giảm**:
- Tỷ trọng tỷ lệ với *điểm ÷ biến động* (coin càng biến động càng ít tiền).
- Mỗi coin bị giới hạn theo hồ sơ, và luôn giữ phần tiền mặt tối thiểu.
- Khi mọi coin đều âm (như hôm nay), kết quả là **100% USDT**: đứng ngoài cũng là một chiến lược.
- Cảnh báo 🔗 khi các coin tương quan ≥ 0,85: giữ BTC + ETH + SOL gần như là giữ **một** khoản đặt cược.

**Bước 4: nhờ AI diễn giải.** Bấm **Tóm tắt bằng Gemini** → AI đọc đúng bảng số liệu ở trên và viết
5 ý ngắn gọn. Nếu Gemini quá tải, hệ thống tự thử lần lượt nhiều model (mất tới 1–2 phút).

**Ví dụ: giảm rủi ro mỗi lệnh từ 1,5% xuống 1%**
1. Mở tab 🛡️ Vốn & Rủi ro.
2. Kéo thanh "Rủi ro tối đa mỗi lệnh (%)" về **1.0**. Màn hình hiện "Đã lưu".
3. Lệnh tiếp theo của bot dùng 1%: với vốn 1000 USDT, mỗi lệnh chấp nhận mất tối đa 10 USDT thay vì 15 USDT.

---

## 12. Tình huống thực tế: làm từng bước

### 🟢 Tình huống 1: ngày đầu tiên dùng hệ thống

```bash
cd ~/QuantFreqtrade
```
```bash
./run.sh status
```
```bash
./run.sh download
```
```bash
./run.sh backtest
```
Sau đó mở Terminal mới:
```bash
./run.sh dashboard
```
→ mở http://localhost:8502, đọc tab 🏠 Tổng quan và 📊 Backtest.

### 🟢 Tình huống 2: chạy bot tiền ảo cả ngày và theo dõi bằng điện thoại

- **Terminal 1:** `./run.sh dryrun` (để nguyên)
- **Terminal 2:** `./run.sh dashboard` (để nguyên)
- **Terminal 3:** `./run.sh alert` (nếu muốn nhận thêm cảnh báo)
- **Trên điện thoại (Telegram):** sáng gõ `/status`, tối gõ `/profit` và `/daily`.

> Máy Mac phải **bật** và **không ngủ** thì bot mới chạy. Tắt máy = bot dừng.

### 🟢 Tình huống 3: chạy cả Spot lẫn Futures cùng lúc

- **Terminal 1:** `./run.sh dryrun` → Spot, có Telegram
- **Terminal 2:** `./run.sh dryrun-futures` → Futures, không Telegram
- **Terminal 3:** `./run.sh dashboard` → tab 🤖 Bot, chuyển qua lại giữa **Spot · 8080** và **Futures · 8081**

### 🟢 Tình huống 4: thêm coin XRP vào bot

1. Tải dữ liệu XRP:
   ```bash
   ./run.sh download 365 -p XRP/USDT
   ```
2. Mở `user_data/config.json`, tìm `"pair_whitelist"`, thêm `"XRP/USDT"`:
   ```json
   "pair_whitelist": [
       "BTC/USDT",
       "ETH/USDT",
       "SOL/USDT",
       "BNB/USDT",
       "XRP/USDT"
   ],
   ```
   (Nhớ dấu phẩy sau `"BNB/USDT"`.)
3. Backtest thử xem XRP có hợp chiến lược không:
   ```bash
   ./run.sh backtest -p XRP/USDT
   ```
4. Nếu bot đang chạy, nhắn Telegram `/reload_config`, rồi `/whitelist` để kiểm tra XRP đã có trong danh sách.

Với Futures thì sửa `user_data/config.futures.json`, thêm `"XRP/USDT:USDT"`, và tải bằng
`./run.sh download-futures 365 -p XRP/USDT:USDT`.

### 🟢 Tình huống 5: thị trường hoảng loạn, muốn an toàn

| Mức độ | Làm gì |
|---|---|
| Lo lắng nhẹ | Telegram: `/stopentry` (không mở lệnh mới, lệnh cũ vẫn được quản lý) |
| Muốn ra hết | Telegram: `/forceexit all` rồi `/stopentry` |
| Tắt hẳn bot | Terminal của bot: `Ctrl + C` |
| Hết lo | `./run.sh dryrun` (nếu đã tắt) hoặc Telegram `/start` |

### 🟢 Tình huống 6: muốn thử cải thiện chiến lược

```bash
./run.sh hyperopt 200 --timerange 20260525-20260901
```
```bash
./run.sh backtest --timerange 20260901-
```
```bash
./run.sh check-bias
```
→ Nếu kết quả không tốt hơn, quay về mặc định:
```bash
rm user_data/strategies/QuantHybridStrategy.json
```

### 🟢 Tình huống 8: chọn chiến lược theo tư vấn 🆕

1. Dashboard → tab 🧭 Tư vấn → chọn hồ sơ rủi ro → bấm **Áp dụng**.
2. Xem gợi ý nổi bật nhất trên các thẻ coin:
   - Phần lớn **Mua theo đà** → chạy `./run.sh dryrun-breakout`
   - Phần lớn **Mua (hồi quy)** / **Chờ vùng giá đẹp** → `./run.sh dryrun`
   - **Tích luỹ từng phần** → `./run.sh dryrun-dca`
   - Phần lớn **Đứng ngoài** → không chạy gì thêm, hoặc chỉ chạy `./run.sh alert` để được báo khi có cơ hội
3. Kiểm chứng lại trước bằng backtest gần đây:
   ```bash
   ./run.sh backtest-all --timerange 20260901-
   ```
4. Để bot chạy dry-run vài tuần, so sánh các bot ở tab 🤖 (chuyển giữa 8080 / 8082 / 8083).

### 🟢 Tình huống 7: mỗi tuần một lần (5 phút)

```bash
./run.sh download 7
```
```bash
./run.sh backtest
```
→ So sánh với tuần trước trên dashboard tab 📊 Backtest.

---

## 13. Tạm đổi cấu hình khi chạy

Đặt `FREQTRADE__<MỤC>__<KHOÁ>=giá_trị` **trước** lệnh. Chỉ có tác dụng cho lần chạy đó, file cấu hình
không bị sửa.

| Ví dụ | Tác dụng |
|---|---|
| `FREQTRADE__TELEGRAM__ENABLED=false ./run.sh dryrun` | Tắt Telegram |
| `FREQTRADE__MAX_OPEN_TRADES=2 ./run.sh dryrun` | Tối đa 2 lệnh cùng lúc |
| `FREQTRADE__DRY_RUN_WALLET=500 ./run.sh dryrun` | Ví ảo 500 USDT |
| `FREQTRADE__DRY_RUN_WALLET=5000 ./run.sh backtest` | Backtest với vốn 5000 USDT |
| `FUTURES_TELEGRAM=true ./run.sh dryrun-futures` | Bot Futures có Telegram |

Xem cấu hình cuối cùng bot sẽ dùng (đã gộp file và biến môi trường, mật khẩu được ẩn):
```bash
./run.sh ft show-config -c user_data/config.json
```

---

## 14. Lệnh Freqtrade nâng cao

Mọi lệnh Freqtrade gốc đều gọi được qua `./run.sh ft ...`.

| Lệnh | Tác dụng | Ví dụ kết quả |
|---|---|---|
| `./run.sh ft list-timeframes` | Khung thời gian Binance hỗ trợ | `1s, 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M` |
| `./run.sh ft list-pairs --quote USDT -c user_data/config.json` | Tất cả cặp Spot với USDT | `Exchange Binance has 526 active pairs with USDT as quote currency` |
| `./run.sh ft test-pairlist -c user_data/config.json` | Coin bot sẽ thực sự giao dịch | `Pairs for USDT: ['BTC/USDT', 'ETH/USDT', ...]` |
| `./run.sh ft backtesting-analysis -c user_data/config.json --analysis-groups 0 1 2` | Phân tích sâu theo kiểu vào × lý do thoát. **Cần chạy trước** `./run.sh backtest --export signals` | `mean_rev + stop_loss: 5 lệnh, −51.47` · `mean_rev + z_revert: 4 lệnh, +16.55` |
| `./run.sh ft recursive-analysis -c user_data/config.json -s QuantHybridStrategy --timerange 20260801-` | Kiểm tra chỉ báo cho kết quả giống nhau giữa live và backtest | |
| `./run.sh ft webserver -c user_data/config.json` | Mở FreqUI để xem/chạy backtest mà **không** chạy bot | http://127.0.0.1:8080 |

---

## 15. Lỗi thường gặp & cách sửa

| Bạn thấy | Nguyên nhân | Cách sửa |
|---|---|---|
| `no such file or directory: ./run.sh` | Đứng sai thư mục | `cd ~/QuantFreqtrade` |
| `permission denied: ./run.sh` | File mất quyền chạy | `chmod +x run.sh` |
| `[!] Chưa cài đặt. Chạy: ./run.sh setup` | Chưa có `.venv` | `./run.sh setup` |
| `Address already in use` | Cổng đang bị chương trình khác chiếm (thường do bot đã chạy ở Terminal khác) | `./run.sh status` để xem; tắt chương trình cũ bằng `Ctrl + C` ở Terminal của nó |
| `Conflict: terminated by other getUpdates request` | 2 bot Freqtrade dùng chung token Telegram | Tắt một bot, hoặc chạy Futures **không** có `FUTURES_TELEGRAM=true` |
| `No data found` / backtest 0 lệnh vì thiếu dữ liệu | Chưa tải nến cho khoảng thời gian đó | `./run.sh download` hoặc `./run.sh download-futures` |
| `Please set a timerange` | Một số lệnh phân tích bắt buộc `--timerange` | Thêm, ví dụ `--timerange 20260801-` |
| Dashboard: "Bot chưa chạy" | Bot tắt | `./run.sh dryrun` |
| Dashboard: "sai mật khẩu API" | Mật khẩu trong `.env` không khớp | Kiểm tra dòng `FREQTRADE__API_SERVER__PASSWORD` trong `.env`, rồi khởi động lại bot |
| Alert bot in `chưa cấu hình TELEGRAM_BOT_TOKEN` | Thiếu token trong `.env` | Điền `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` trong `.env` |
| Alert bot: `AI Tạm nghỉ` / Gemini không trả lời | Hết hạn mức hoặc sai key | Không sao: bot tự chạy thuần toán học |
| Bot chạy cả ngày không có lệnh | Chưa có tín hiệu đủ điều kiện (bình thường) | Xem "Mức gần tín hiệu" ở tab 🏠 Tổng quan |
| Log có `AI (gemini-…) lỗi: 404 NOT_FOUND` | Google đã ngừng model đó | Không cần làm gì: hệ thống tự thử model khác. Muốn đổi model chính: sửa dòng `GEMINI_MODEL=` trong `.env` |
| Log có `503 UNAVAILABLE` / `high demand` | Gemini đang quá tải | Tự thử model dự phòng; thử lại sau vài phút |

Tìm chương trình đang chiếm cổng 8080 (đổi số cổng nếu cần):
```bash
lsof -i :8080
```

---

## 16. Bảng tra nhanh 1 trang

| Mục đích | Spot | Futures |
|---|---|---|
| Tải dữ liệu | `./run.sh download` | `./run.sh download-futures` |
| Backtest | `./run.sh backtest` (hoặc `backtest-all` cho 4 chiến lược) | `./run.sh backtest-futures` |
| Backtest 1 khoảng ngày | `./run.sh backtest --timerange 20261001-` | `./run.sh backtest-futures --timerange 20261001-` |
| Backtest 1 coin | `./run.sh backtest -p BTC/USDT` | `./run.sh backtest-futures -p BTC/USDT:USDT` |
| Chạy bot tiền ảo | `./run.sh dryrun` (Hybrid) · `dryrun-breakout` · `dryrun-dca` | `./run.sh dryrun-futures` |
| Bot có Telegram | mặc định có | `FUTURES_TELEGRAM=true ./run.sh dryrun-futures` |
| Xem bot trên web | http://127.0.0.1:8080 | http://127.0.0.1:8081 |
| Lịch sử lệnh | `./run.sh trades` | `./run.sh trades-futures` |

| Mục đích | Lệnh |
|---|---|
| Cái gì đang chạy? | `./run.sh status` |
| Danh sách lệnh | `./run.sh help` |
| Dashboard | `./run.sh dashboard` → http://localhost:8502 |
| Alert bot | `./run.sh alert` · `--legacy` · `--once` |
| Tư vấn chiến lược & phân bổ vốn | Dashboard → tab 🧭 Tư vấn |
| Kiểm tra gian lận | `./run.sh check-bias` |
| Tối ưu tham số | `./run.sh hyperopt 200` |
| Vẽ biểu đồ | `./run.sh plot BTC/USDT` |
| Kiểm thử | `./run.sh test` |
| Dừng chương trình | `Ctrl + C` |

| Telegram | Tác dụng |
|---|---|
| `/status` · `/status table` | Lệnh đang mở |
| `/profit` · `/daily` · `/weekly` | Lãi/lỗ |
| `/trades` · `/performance` · `/entries` · `/exits` | Thống kê |
| `/balance` · `/count` · `/locks` | Số dư, số lệnh, coin bị khoá |
| `/stopentry` · `/start` | Tạm ngừng / chạy lại |
| `/forceexit 3` · `/forceexit all` | Đóng lệnh bằng tay |
| `/reload_config` · `/whitelist` | Cập nhật cấu hình, xem coin |
| `/help` | Tất cả lệnh |

---

> **Chuyển sang tiền thật:** chưa khuyến nghị, vì backtest đang lỗ. Khi dry-run có lãi ổn định nhiều tuần
> **và** backtest ≥ 1 năm cũng có lãi, làm theo mục "Checklist trước khi chạy tiền thật" trong
> `README.md`. Luôn bắt đầu bằng số tiền nhỏ chấp nhận mất.
