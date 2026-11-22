# 📘 Lệnh hay dùng — QuantFreqtrade

Bản ngắn để tra nhanh. Cần giải thích từng kết quả và ví dụ chi tiết → [HUONG_DAN_CHI_TIET.md](HUONG_DAN_CHI_TIET.md).

---

## ⚡ Chế độ tự động (cách nhanh nhất)

Mọi thứ chạy **nền**: không cần giữ Terminal mở.

| Muốn | Lệnh |
|---|---|
| Bật dashboard + bot Hybrid + alert bot | `./run.sh start` |
| Bật **tất cả** (thêm Breakout, DCA, Futures) | `./run.sh start all` |
| Chỉ bật vài thứ | `./run.sh start dca breakout` |
| Tắt tất cả / tắt 1 thứ | `./run.sh stop` · `./run.sh stop dca` |
| Xem cái gì đang chạy | `./run.sh status` |
| Xem bot đang làm gì | `./run.sh logs hybrid` (`Ctrl + C` để thoát, bot vẫn chạy) |

Tên dùng được: `dashboard` · `hybrid` · `breakout` · `dca` · `futures` · `alert`.

**Không muốn gõ lệnh?** Dashboard → tab 🤖 **Bot Freqtrade** → nút **▶ Bật / ■ Tắt**.
Hoặc VS Code → `Cmd + Shift + P` → **Tasks: Run Task** → **▶️ BẬT TẤT CẢ**.

**Tự động hoàn toàn** — đang **BẬT** trên máy bạn (`./run.sh autostart off` để tắt):
- Mở máy → tự bật dashboard, cả 4 bot và alert bot.
- Mỗi **5 phút** → bot nào tắt bất thường (lỗi mạng, crash…) thì **tự bật lại** và nhắn Telegram báo bạn.
  Bot bạn tự tắt (nút Tắt / `./run.sh stop`) sẽ **không** bị bật lại.
- Mỗi **Chủ nhật 8:00** → tự tải dữ liệu mới và chạy backtest.

> Máy phải **bật** thì bot mới chạy. Gập nắp MacBook thì máy vẫn ngủ (trừ khi cắm sạc + màn hình ngoài).

---

## 1. Chọn bot nào?

| Bot | Hợp khi thị trường | Lệnh chạy riêng | Xem trên web |
|---|---|---|---|
| **Hybrid** | Đi ngang hoặc xu hướng nhẹ | `./run.sh dryrun` | http://127.0.0.1:8080 |
| **Breakout** | Tăng mạnh, phá đỉnh | `./run.sh dryrun-breakout` | http://127.0.0.1:8082 |
| **Smart DCA** | Hoảng loạn, muốn tích luỹ dần | `./run.sh dryrun-dca` | http://127.0.0.1:8083 |
| **Futures** (Long + Short, đòn bẩy) | Giảm mạnh, muốn Short | `./run.sh dryrun-futures` | http://127.0.0.1:8081 |

- Đăng nhập web: `freqtrader` / mật khẩu ở dòng `FREQTRADE__API_SERVER__PASSWORD` trong file `.env`.
- **Cả 4 bot đều nhắn Telegram** khi vào/thoát lệnh (tin có tên bot, ví dụ `🟢 [Breakout] VÀO LỆNH…`).
- **Chỉ bot Hybrid nhận lệnh** `/status`, `/profit`… Các bot khác xem chi tiết trên web hoặc dashboard.

**Bộ lọc thị trường (đang BẬT):** BTC đóng cửa ngày **dưới SMA200 ngày** → thị trường chung đang giảm →
3 bot Spot **không mở lệnh Long mới**, bot Futures **chỉ được Short**. Trạng thái hiện tại xem ở dashboard
(tab 🏠 và 🧭). Tắt bộ lọc: sửa `"market_filter": true` thành `false` trong `user_data/config.json` và
`config.futures.json`, rồi `./run.sh restart`.

**Kết quả 2 năm** (12/2024 – 11/2026, thị trường **giảm 42%**, chạy lại: `./run.sh validate`):

| Chiến lược | Không lọc | **Có bộ lọc** | Sụt vốn tối đa (có lọc) | Giai đoạn 6 tháng có lãi |
|---|---|---|---|---|
| Smart DCA | −11,9% | **−7,2%** | 8,5% | 0 / 4 |
| Breakout | −33,5% | **−7,8%** | 18,6% | 2 / 4 |
| Hybrid | −19,2% | **−8,6%** | 14,4% | 1 / 4 |
| Futures | −34,4% | **−13,8%** | 21,7% | 2 / 4 |
| Z-Score gốc (không có lọc) | −44,7% | — | 54,3% | 1 / 4 |

→ Bộ lọc giảm lỗ **2–4 lần**. Trong giai đoạn giảm mạnh nhất (12/2025 – 6/2026, thị trường −23,5%), các bot Spot
đứng ngoài hoàn toàn (0%). **Nhưng vẫn chưa chiến lược nào có lãi ổn định → chỉ chạy tiền ảo.**
Chi tiết từng giai đoạn (có/không lọc): dashboard → tab 📊 Backtest.

---

## 2. Tất cả lệnh `./run.sh`

| Nhóm | Lệnh | Làm gì |
|---|---|---|
| **Tự động** | `./run.sh start` · `stop` · `restart` | Bật / tắt / bật lại mọi thứ chạy nền |
| | `./run.sh logs hybrid` | Xem log trực tiếp của 1 bot |
| | `./run.sh autostart on` / `off` | Tự bật khi mở máy + tự bật lại bot bị tắt + việc hằng tuần |
| | `./run.sh weekly` | Tải dữ liệu mới + backtest (autostart tự chạy mỗi Chủ nhật) |
| **Dữ liệu** | `./run.sh download` | Tải nến Spot mới |
| | `./run.sh download 730 --prepend` | Tải thêm dữ liệu **cũ hơn** (lùi về 2 năm) |
| | `./run.sh download-futures` | Tải nến Futures |
| **Backtest** | `./run.sh backtest-all` | So sánh 4 chiến lược Spot trên toàn bộ dữ liệu |
| | `./run.sh backtest-futures` | Backtest Futures |
| | `./run.sh validate` | **Kiểm chứng từng giai đoạn 6 tháng** (10–20 phút) |
| | `./run.sh plot BTC/USDT` | Vẽ lệnh backtest lên biểu đồ (`user_data/plot/`) |
| **Kiểm tra** | `./run.sh check-bias` | Chiến lược có "nhìn trước tương lai" không (`No` là tốt) |
| | `./run.sh hyperopt 200` | Tự tìm tham số tốt hơn (10–30 phút) |
| | `./run.sh test` | Kiểm tra code còn chạy đúng |
| **Theo dõi** | `./run.sh status` | Cái gì đang chạy |
| | `./run.sh trades` · `trades-futures` | Lịch sử lệnh bot Hybrid / Futures |
| **Khác** | `./run.sh alert --once` | Alert bot quét thử 1 lần |
| | `./run.sh ui` | Cài lại giao diện web FreqUI |
| | `./run.sh help` | Xem mọi lệnh |

**Tuỳ chọn cho backtest** (gõ sau lệnh): `--timerange 20261001-` (từ ngày), `-p BTC/USDT` (1 coin),
`--breakdown week` (lãi/lỗ theo tuần).

---

## 3. Lệnh Telegram (gửi cho bot Hybrid)

| Lệnh | Làm gì |
|---|---|
| `/status` | Lệnh đang mở |
| `/profit` · `/daily` | Tổng lãi/lỗ · lãi/lỗ từng ngày |
| `/balance` · `/trades` | Số dư · lệnh đã đóng gần nhất |
| `/stopentry` | **Ngừng mở lệnh mới** (lệnh cũ vẫn được quản lý) — cách dừng an toàn nhất |
| `/start` | Cho bot chạy lại |
| `/forceexit 3` · `/forceexit all` | Đóng ngay lệnh số 3 · đóng tất cả |
| `/help` | Xem mọi lệnh |

---

## 4. Gặp lỗi?

| Thấy | Làm |
|---|---|
| `no such file or directory: ./run.sh` | Gõ `cd ~/QuantFreqtrade` trước |
| `Address already in use` | Chương trình đã chạy rồi → `./run.sh status` |
| Trang FreqUI báo "not installed" | Tải lại bỏ cache: `Option + Cmd + R` |
| FreqUI "Login failed" khi thêm bot | Kiểm tra bot đó đang chạy (`./run.sh status`) và đúng cổng |
| Bot tắt mà không rõ vì sao | `./run.sh logs hybrid` (hoặc file `logs/watchdog.log`) |
| Backtest báo thiếu dữ liệu | `./run.sh download` (Futures: `./run.sh download-futures`) |
| Bot chạy cả ngày không có lệnh | Bình thường — chưa có tín hiệu. Xem "mức gần tín hiệu" ở tab 🏠 |
| Gemini báo lỗi 404 / 503 | Không cần làm gì — hệ thống tự thử model khác |

Lỗi khác: copy dòng lỗi gửi cho Claude.
