# 📘 Lệnh hay dùng — QuantFreqtrade

Bản ngắn để tra nhanh. Cần giải thích từng kết quả và ví dụ chi tiết → [HUONG_DAN_CHI_TIET.md](HUONG_DAN_CHI_TIET.md).

---

## 1. Trước khi gõ lệnh

Mở Terminal (VS Code: **Terminal → New Terminal**), rồi vào thư mục dự án:

```bash
cd ~/QuantFreqtrade
```

| Muốn | Làm |
|---|---|
| Xem cái gì đang chạy | `./run.sh status` |
| Xem danh sách lệnh | `./run.sh help` |
| Dừng chương trình đang chạy | Bấm `Ctrl + C` |
| Chạy 2 thứ cùng lúc | Mở thêm Terminal (nút **+**), mỗi thứ một Terminal |

---

## 2. Bốn việc hay làm nhất

**① Cập nhật dữ liệu** (mỗi tuần 1 lần)
```bash
./run.sh download
```

**② Thử chiến lược trên quá khứ** (backtest, không tốn tiền)
```bash
./run.sh backtest-all
```
Nhìn bảng cuối cùng **STRATEGY SUMMARY**: cột `Tot Profit %` (lãi/lỗ) và `Drawdown` (sụt vốn tối đa).

**③ Xem dashboard**
```bash
./run.sh dashboard
```
Mở http://localhost:8502. Tab **🧭 Tư vấn** gợi ý chiến lược và cách chia vốn.

**④ Chạy bot bằng tiền ảo** (dry-run, không mất tiền thật)
```bash
./run.sh dryrun
```
Bot nhắn Telegram khi vào/thoát lệnh. Để nguyên Terminal này, muốn tắt thì bấm `Ctrl + C`.

---

## 3. Chọn bot nào?

| Bot | Hợp khi thị trường | Lệnh chạy | Xem trên web |
|---|---|---|---|
| **Hybrid** (mặc định) | Đi ngang hoặc xu hướng nhẹ | `./run.sh dryrun` | http://127.0.0.1:8080 |
| **Breakout** | Tăng mạnh, phá đỉnh | `./run.sh dryrun-breakout` | http://127.0.0.1:8082 |
| **Smart DCA** | Hoảng loạn, muốn tích luỹ dần | `./run.sh dryrun-dca` | http://127.0.0.1:8083 |
| **Futures** (Long + Short, đòn bẩy) | Giảm mạnh, muốn Short | `./run.sh dryrun-futures` | http://127.0.0.1:8081 |

- Đăng nhập web: `freqtrader` / mật khẩu ở dòng `FREQTRADE__API_SERVER__PASSWORD` trong file `.env`.
- **Chỉ bot Hybrid gửi Telegram.** Muốn bot khác gửi Telegram thì tắt bot Hybrid trước, rồi chạy:
  `FUTURES_TELEGRAM=true ./run.sh dryrun-futures` hoặc `STRATEGY_TELEGRAM=true ./run.sh dryrun-dca`

Kết quả backtest hiện tại (25/05 – 22/11/2026, thị trường giảm 18,9%):

| Hybrid | Breakout | Smart DCA | Futures |
|---|---|---|---|
| −6,1% | −0,5% | −2,3% | −8,6% |

→ **Chưa bot nào có lãi. Chỉ chạy tiền ảo.**

---

## 4. Tất cả lệnh `./run.sh`

| Nhóm | Lệnh | Làm gì |
|---|---|---|
| **Dữ liệu** | `./run.sh download` | Tải nến Spot 365 ngày |
| | `./run.sh download-futures` | Tải nến Futures (cần trước khi backtest Futures) |
| **Backtest** | `./run.sh backtest-all` | So sánh 4 chiến lược Spot |
| | `./run.sh backtest` | Chỉ so sánh Z-Score gốc với Hybrid |
| | `./run.sh backtest-futures` | Backtest Futures |
| | `./run.sh plot BTC/USDT` | Vẽ lệnh backtest lên biểu đồ (file trong `user_data/plot/`) |
| **Kiểm tra** | `./run.sh check-bias` | Chiến lược có "nhìn trước tương lai" không (`No` là tốt) |
| | `./run.sh hyperopt 200` | Tự tìm tham số tốt hơn (10–30 phút) |
| | `./run.sh test` | Kiểm tra code còn chạy đúng |
| **Chạy bot** | `./run.sh dryrun` · `dryrun-breakout` · `dryrun-dca` · `dryrun-futures` | Xem mục 3 |
| | `./run.sh alert` | Bot **chỉ gửi cảnh báo** Telegram (không tự đặt lệnh) |
| | `./run.sh dashboard` | Mở dashboard |
| **Theo dõi** | `./run.sh status` | Cái gì đang chạy |
| | `./run.sh trades` | Lịch sử lệnh bot Hybrid |
| | `./run.sh trades-futures` | Lịch sử lệnh bot Futures |
| **Cài đặt** | `./run.sh setup` | Cài lại từ đầu |
| | `./run.sh ui` | Cài giao diện web FreqUI (1 lần) |

**Thêm tuỳ chọn cho backtest** (gõ sau lệnh):

| Thêm | Ví dụ | Nghĩa |
|---|---|---|
| `--timerange` | `./run.sh backtest-all --timerange 20261001-` | Chỉ thử từ 01/10/2026 |
| `-p` | `./run.sh backtest-all -p BTC/USDT` | Chỉ thử BTC |
| `--breakdown` | `./run.sh backtest-all --breakdown week` | Xem lãi/lỗ theo tuần |

**Tuỳ chọn cho alert bot:**

| Lệnh | Nghĩa |
|---|---|
| `./run.sh alert --once` | Quét 1 lần rồi thoát |
| `./run.sh alert --legacy` | Báo y hệt bot cũ `4_alert_bot.py` |
| `./run.sh alert --pairs BTC/USDT XRP/USDT` | Chọn coin theo dõi |

---

## 5. Lệnh Telegram

Nhắn cho bot khi `./run.sh dryrun` đang chạy:

| Lệnh | Làm gì |
|---|---|
| `/status` | Lệnh đang mở |
| `/profit` | Tổng lãi/lỗ |
| `/daily` | Lãi/lỗ từng ngày |
| `/balance` | Số dư |
| `/trades` | Lệnh đã đóng gần nhất |
| `/stopentry` | **Ngừng mở lệnh mới** (lệnh cũ vẫn được quản lý) — cách dừng an toàn nhất |
| `/start` | Cho bot chạy lại |
| `/forceexit 3` | Đóng ngay lệnh số 3 (số lấy từ `/status`) |
| `/forceexit all` | Đóng tất cả lệnh |
| `/help` | Xem mọi lệnh |

---

## 6. Gặp lỗi?

| Thấy | Làm |
|---|---|
| `no such file or directory: ./run.sh` | Gõ `cd ~/QuantFreqtrade` trước |
| `Address already in use` | Chương trình đó đã chạy ở Terminal khác → `./run.sh status` |
| `Conflict: terminated by other getUpdates` | 2 bot cùng dùng Telegram → tắt bớt 1 bot |
| Backtest báo thiếu dữ liệu | `./run.sh download` (Futures: `./run.sh download-futures`) |
| Bot chạy cả ngày không có lệnh | Bình thường — chưa có tín hiệu. Xem "mức gần tín hiệu" ở tab 🏠 |
| Gemini báo lỗi 404 / 503 | Không cần làm gì — hệ thống tự thử model khác |

Lỗi khác: copy dòng lỗi gửi cho Claude.
