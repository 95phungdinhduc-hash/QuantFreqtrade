# 🦆 Đọc hiểu Dashboard — giải thích từng tab, từng con số

Mở dashboard: http://localhost:8502 (tự bật khi mở máy, hoặc `./run.sh start dashboard`).

Ví dụ trong tài liệu này lấy **số liệu thật ngày 23/11/2026** để bạn so với màn hình.
Số trên màn hình của bạn sẽ khác vì giá thay đổi liên tục, nhưng cách đọc thì giữ nguyên.

> 💡 **Rê chuột vào dấu ⓘ "?"** cạnh mỗi chỉ số trên dashboard để xem giải thích ngắn ngay tại chỗ
> (trên điện thoại: chạm vào dấu "?"). Tài liệu này là bản đầy đủ.

> 🎨 **Hiệu ứng giao diện:**
> - Số **đếm lên** khi vừa hiện ra.
> - Giá **nháy xanh** khi tăng, **nháy đỏ** khi giảm lúc tự làm mới.
> - Thẻ có tín hiệu LONG/SHORT có **viền sáng chạy vòng quanh**.
> - Băng giá chạy ngang **dừng lại khi rê chuột** vào.
>
> Chỉ để dễ nhìn, không ảnh hưởng số liệu. Muốn tắt hết chuyển động: bật *Giảm chuyển động*
> (macOS: Cài đặt → Trợ năng → Màn hình). Sửa giao diện tại `dashboard/theme.css` và `dashboard/fx.js`.

> ⚠️ Dashboard là **công cụ phân tích theo quy tắc cố định**, không phải lời khuyên đầu tư.
> Mọi bot đang chạy **tiền ảo (dry-run)**.

---

## Mục lục

0. [Đọc nhanh trong 2 phút](#0-đọc-nhanh-trong-2-phút)
1. [Từ điển: các chỉ số dùng khắp nơi](#1-từ-điển-các-chỉ-số-dùng-khắp-nơi)
2. [Thanh bên trái (sidebar)](#2-thanh-bên-trái-sidebar)
3. [Tab 🏠 Tổng quan](#3-tab--tổng-quan)
4. [Tab 🧭 Tư vấn](#4-tab--tư-vấn)
5. [Tab 📈 Phân tích](#5-tab--phân-tích)
6. [Tab 🎯 Screener](#6-tab--screener)
7. [Tab 🛡️ Vốn & Rủi ro](#7-tab-️-vốn--rủi-ro)
8. [Tab 📰 Tin tức](#8-tab--tin-tức)
9. [Tab 🤖 Bot Freqtrade](#9-tab--bot-freqtrade)
10. [Tab 📊 Backtest](#10-tab--backtest)
11. [Màu sắc và ký hiệu](#11-màu-sắc-và-ký-hiệu)
12. [Câu hỏi thường gặp](#12-câu-hỏi-thường-gặp)

---

## 0. Đọc nhanh trong 2 phút

Mỗi ngày chỉ cần nhìn 5 chỗ, theo thứ tự:

| # | Nhìn ở đâu | Câu hỏi | Ví dụ 23/11/2026 |
|---|---|---|---|
| 1 | 🏠 → viên **"BTC dưới/trên SMA200 ngày"** | Thị trường chung tăng hay giảm? | BTC **dưới** SMA200 15,4% → bot Spot đứng ngoài |
| 2 | 🧭 → **Nhiệt kế thị trường** | Tổng thể tốt hay xấu? | **−35/100, Tiêu cực** |
| 3 | 🏠 → **Tín hiệu hệ thống** | Có coin nào đang có tín hiệu? | Không, cả 4 coin đang "Chờ / Đứng ngoài" |
| 4 | 🤖 → **Bật / tắt bot** | Bot còn chạy không? | 4 bot + alert bot đều "Đang chạy (nền)" |
| 5 | 🤖 → **Lợi nhuận** từng bot | Bot đang lời hay lỗ? | Xem từng cổng 8080–8083 |

Nếu cả 5 chỗ đều "chờ / đứng ngoài" thì **không có gì để làm**. Đây là trạng thái bình thường.
Hệ thống được thiết kế để kiên nhẫn chờ lợi thế thống kê, không mở lệnh cho có.

---

## 1. Từ điển: các chỉ số dùng khắp nơi

Đọc phần này một lần, các tab sau sẽ dễ hiểu hơn nhiều.

### Nến (candle)
Một nến 1h là giá **mở / cao / thấp / đóng** trong 1 giờ. Hệ thống chỉ dùng **nến đã đóng**: nến đang chạy
bị bỏ qua để tín hiệu không nhảy lung tung. Vì vậy tín hiệu chỉ thay đổi mỗi giờ một lần, vào phút 00.

### Trung bình (TB) và σ (độ lệch chuẩn)
- **Trung bình trượt**: giá trung bình của 50 nến gần nhất (đổi số 50 ở sidebar).
- **σ (sigma)**: giá thường dao động xa trung bình bao nhiêu. σ lớn nghĩa là coin biến động mạnh.
- **Dải ±2σ**: khoảng giá mà khoảng 95% thời gian giá nằm bên trong. Ra ngoài dải là bất thường.

### Z-Score — "giá đang đắt hay rẻ so với bình thường?"
```
Z = (giá hiện tại − trung bình 50 nến) ÷ σ
```
| Z | Ý nghĩa |
|---|---|
| **≤ −2** | **Quá bán**: rẻ bất thường, có thể hồi lên |
| −2 … +2 | Bình thường, chưa có lợi thế |
| **≥ +2** | **Quá mua**: đắt bất thường, có thể điều chỉnh xuống |

Ví dụ: BTC Z = **+1,22σ**, nghĩa là giá cao hơn trung bình 1,22 lần độ lệch chuẩn. Giá hơi cao nhưng chưa bất thường.

### ADF p-value — "thị trường đi ngang hay có xu hướng?"
ADF là một kiểm định thống kê, chạy trên **200 nến 1h gần nhất** và tính lại mỗi 12 giờ.
| ADF p | Chế độ | Chiến lược phù hợp |
|---|---|---|
| **< 0,20** | **Đi ngang**: giá dao động quanh trung bình rồi quay về | **Mean Reversion**: mua rẻ (Z ≤ −2), bán khi về trung bình |
| ≥ 0,20 | **Có xu hướng**: giá đi một chiều | **Trend Following**: đánh theo EMA |

Ví dụ: SOL ADF = **0,14**, thuộc vùng đi ngang. BTC ADF = **0,41**, thuộc vùng có xu hướng.

### EMA20 / EMA50 và "EMA gap %"
- **EMA** là đường trung bình có ưu tiên giá gần đây. EMA20 phản ứng nhanh, EMA50 phản ứng chậm.
- **EMA gap %** = EMA20 cao hơn EMA50 bao nhiêu %.
  - **> +1%**: xu hướng tăng rõ.
  - **< −1%**: xu hướng giảm rõ.
  - Từ −1% đến +1%: chưa rõ.
- **EMA50 khung 4h**: dùng để lọc thêm. Giá trên EMA50 4h thì xu hướng lớn đang tăng.

### SMA200 ngày của BTC — **bộ lọc thị trường**
Trung bình giá đóng cửa **200 ngày** của BTC, là thước đo phổ biến nhất cho "thị trường bò hay gấu".
- **BTC đóng cửa ngày trên SMA200**: thị trường chung tăng. Bot được mở Long.
- **BTC dưới SMA200**: thị trường giảm.
  - 3 bot Spot **không mở Long mới**.
  - Bot Futures **chỉ Short**.
  - Alert bot **chỉ báo Short**.

Ví dụ: BTC đóng cửa 22/11 ở $61.271, SMA200 là $72.385, tức **−15,4%**. Bộ lọc đang chặn Long.

### RSI (0–100)
Đo lực mua so với lực bán trong 14 nến.
- **< 30**: quá bán.
- **> 70**: quá mua.
- Khoảng 50: cân bằng.

### ATR
Biên độ dao động trung bình của một nến. Bot Breakout dùng ATR để đặt cắt lỗ: 2,5 × ATR dưới giá vào.

### Kênh Donchian 48
Giá cao nhất và thấp nhất của 48 nến trước đó. Giá **vượt đỉnh 48 giờ** là tín hiệu Breakout.

### Cắt lỗ (SL), chốt lời (TP), R:R
- **SL (Stop Loss)**: giá mà nếu chạm thì chấp nhận thua và thoát.
- **TP (Take Profit)**: giá chốt lời.
- **R:R = 1 : 1,5** nghĩa là: chấp nhận mất 1 đồng để có cơ hội lời 1,5 đồng.

### Quy mô lệnh theo % rủi ro (cách hệ thống tính tiền vào lệnh)
```
Số tiền chấp nhận mất = Vốn × % rủi ro           (1000$ × 1,5% = 15$)
Khoảng cách tới SL    = |giá vào − SL| ÷ giá vào  (ví dụ 3%)
Quy mô lệnh           = 15$ ÷ 3% = 500$
```
Nếu chạm SL thì mất đúng **15$** (1,5% vốn), dù coin biến động mạnh hay yếu. SL càng xa thì lệnh càng nhỏ.
Khi quy mô lệnh lớn hơn vốn, dashboard báo **"Đòn bẩy cần"** (ví dụ 1,5x). Spot không có đòn bẩy, nên phải dùng Futures
hoặc chấp nhận lệnh nhỏ hơn.

### Sụt vốn tối đa (Max Drawdown, DD)
Mức giảm lớn nhất của tài khoản tính từ đỉnh xuống đáy. DD 15% nghĩa là có lúc tài khoản từ 1000$ xuống còn 850$.
**DD quan trọng ngang lợi nhuận**: chiến lược lời 20% nhưng DD 50% thì rất khó chịu đựng khi chạy thật.

### Dry-run
Bot chạy y như thật, theo giá thật, nhưng **bằng tiền ảo** (ví ảo 1000 USDT). Không mất tiền thật.

---

## 2. Thanh bên trái (sidebar)

(Trên điện thoại, bấm `>` ở góc trên trái để mở sidebar.)

| Mục | Làm gì | Ảnh hưởng tới |
|---|---|---|
| **Tài sản** | Chọn coin và khung thời gian, ví dụ `BTC/USDT · 1h` | Tab 📈 Phân tích, 🛡️ Vốn & Rủi ro, ma trận tương quan ở 🎯 |
| **Chu kỳ Z-Score (nến)** | Số nến để tính trung bình và σ, mặc định **50** | Z-Score ở 🏠 📈 🎯 🛡️. **Bot luôn dùng 50**: đổi số này chỉ để xem thử, không đổi bot |
| **Tải / cập nhật từ Binance** | Tải nến về máy (chọn coin, khung, số ngày) | Dữ liệu cho 📈 🎯 và backtest. Có autostart thì không cần bấm: Chủ nhật tự tải |
| **Mở FreqUI** | Mở giao diện web gốc của Freqtrade | Bot Spot ở cổng 8080, bot Futures ở 8081 |

---

## 3. Tab 🏠 Tổng quan

Trang "bìa": nhìn một lần biết thị trường và bot đang thế nào.

### 3.1 Khối giới thiệu (hero) — các viên trạng thái

| Viên | Nghĩa |
|---|---|
| 🟢 **Bot đang chạy · DRY-RUN · spot** | Bot Hybrid (8080) đang chạy bằng tiền ảo |
| 🟠 **Bot đang khởi động…** | Bot vừa bật, khoảng 30 giây sau sẽ thành 🟢 |
| 🟠 **Bot chạy nhưng sai mật khẩu API** | Mật khẩu trong `.env` không khớp |
| ⚫ **Bot chưa chạy** | Bot Hybrid đang tắt |
| 🕒 **Phiên** | Phiên giao dịch theo giờ Việt Nam (xem bảng dưới) |
| 📰 **Tin tức** | Tâm lý tin tức tổng: Tích cực, Tiêu cực hoặc Trung lập (xem tab 📰) |
| 🟢/⚫ **BTC trên/dưới SMA200 ngày (±x%)** | **Bộ lọc thị trường**: bot có được mở Long không |

Phiên giao dịch (giờ VN):
| Giờ | Phiên | Đặc điểm |
|---|---|---|
| 6h–14h | 🇯🇵 Á | Đi ngang, biên độ hẹp |
| 14h–19h | 🇬🇧 Âu | Biến động trung bình |
| 19h–23h | 🇺🇸 Mỹ + Âu | Thanh khoản lớn nhất, sóng mạnh |
| 23h–6h | 🇺🇸 Mỹ | Chạy theo xu hướng |

4 ô số bên phải:
- **Theo dõi**: số coin trong danh sách giao dịch của bot (BTC, ETH, SOL, BNB).
- **Rủi ro mỗi lệnh**: % vốn chấp nhận mất mỗi lệnh, và số tiền tương ứng trên **vốn bạn khai ở tab 🛡️**.
- **Chiến lược**: 5 bot, gồm 4 bot chạy được và 1 bản Z-Score gốc để so sánh.
- **Kiểm soát rủi ro**: sụt vốn tối đa của Hybrid trong lần backtest gần nhất.

### 3.2 Thị trường — thẻ giá từng coin
- **Giá lớn**: giá trực tiếp từ Binance, cập nhật mỗi 60 giây.
- **±x% 24h**: thay đổi so với 24 giờ trước. Xanh là tăng, đỏ là giảm.
- **Đường nhỏ (sparkline)**: giá 72 giờ gần nhất.
- **Z-Score**: xem từ điển ở mục 1.
- **Vol 24h**: khối lượng giao dịch 24h tính bằng USDT, ví dụ `$1.234M`. Coin có vol lớn thì dễ mua bán, ít trượt giá.
- **Nhãn góc phải**: tín hiệu hiện tại, giống phần 3.3.
- Góc trên phải ghi **🟢 Trực tiếp** nếu lấy được giá Binance. **🟠 Dữ liệu đã tải** nghĩa là mất mạng và đang dùng dữ liệu cũ.

### 3.3 Tín hiệu hệ thống — phần quan trọng nhất của tab
Mỗi coin có một thẻ, tính trên **nến 1h đã đóng**, cùng logic với bot Hybrid:

```
ADF < 0,20 (đi ngang)?
 ├─ Có → Mean Reversion:  Z ≤ −2 → "Long"   ·  Z ≥ +2 → "Short"   ·  còn lại → "Chờ"
 └─ Không → Trend:        EMA gap > +1% → "Xu hướng tăng" · < −1% → "Xu hướng giảm" · còn lại → "Đứng ngoài"
```

**Khi có tín hiệu** (thẻ phát sáng xanh hoặc đỏ), thẻ hiện kế hoạch lệnh:
| Dòng | Nghĩa |
|---|---|
| Giá vào tham khảo | Giá hiện tại |
| Cắt lỗ (2σ) | SL cách giá vào 2σ |
| Chốt lời | Mean Reversion: về trung bình (ít nhất 1,5σ). Trend: cách giá vào 3σ |
| Quy mô lệnh | Số USDT nên vào, tính theo % rủi ro |
| Rủi ro nếu chạm SL | Số tiền mất nếu sai |
| Tỷ lệ lời/lỗ | R:R |

**Khi chưa có tín hiệu**, thẻ hiện **thanh tiến độ "Mức gần tín hiệu"**:
- Đi ngang: = |Z| ÷ 2. Ví dụ SOL Z = 0,92σ thì **46%**, nghĩa là mới đi được gần nửa đường tới vùng mua/bán.
- Có xu hướng: = |EMA gap| ÷ 1%. Ví dụ BTC gap 0,47% thì **47%**.
- Đạt **100%** là có tín hiệu.

> Thẻ ở đây **không xét bộ lọc thị trường**. Nó trả lời câu hỏi "chiến lược nói gì". Nếu BTC đang dưới SMA200 thì
> tín hiệu Long vẫn hiện, nhưng bot Spot **sẽ không vào lệnh**. Muốn biết bot có vào không, xem viên SMA200 ở trên.

### 3.4 Hiệu suất
- **Trái — Bot đang chạy** (bot Hybrid):
  - % lớn: tổng lãi/lỗ, tính cả lệnh đang mở.
  - Số lệnh đã đóng, thắng / thua, lệnh đang mở.
- **Phải — Backtest gần nhất**: bảng so sánh các chiến lược trên dữ liệu quá khứ.
  - **Lợi nhuận** và **Sụt vốn** (xem mục 1).
  - **Lệnh**: số lệnh trong cả giai đoạn.
  - **Mua & giữ**: nếu chỉ mua rồi giữ thì lời/lỗ bao nhiêu. Đây là mốc để so sánh.

### 3.5 Hệ thống hoạt động thế nào / Lưu ý rủi ro
Phần chữ tĩnh tóm tắt 4 bước của bot. Không có số liệu.

---

## 4. Tab 🧭 Tư vấn

Gom **mọi phân tích** thành một điểm số cho từng coin, gợi ý chiến lược và gợi ý chia vốn.
Tab này tự lấy khoảng 1000 nến 1h mới nhất từ Binance, **không phụ thuộc** coin chọn ở sidebar.

### 4.1 Hồ sơ rủi ro
| Hồ sơ | Rủi ro/lệnh | Futures | Tiền mặt tối thiểu | Tối đa 1 coin |
|---|---|---|---|---|
| Thận trọng | 0,75% | Không | 50% | 20% |
| **Cân bằng** (mặc định) | 1,5% | Tối đa x2 | 30% | 30% |
| Mạo hiểm | 2,5% | Tối đa x3 | 10% | 40% |

Nút **"Áp dụng rủi ro x%/lệnh cho bot"** lưu mức rủi ro đó. Cả 4 bot sẽ dùng nó **cho lệnh tiếp theo**,
không cần khởi động lại. Nút bị mờ nếu bot đang dùng đúng mức đó rồi.

### 4.2 Ô "Bộ lọc thị trường"
Như viên SMA200 ở tab 🏠, nhưng ghi đủ số: giá đóng cửa ngày của BTC, SMA200 và khoảng cách giữa hai giá.
Ghi **(đang BẬT)** hoặc **(đang TẮT)** theo `"market_filter"` trong config.

### 4.3 Bốn ô tổng quan

**Nhiệt kế thị trường (−100 … +100)**: trung bình điểm của các coin.
| Điểm | Nhãn |
|---|---|
| ≤ −40 | Rất tiêu cực |
| −40 … −15 | Tiêu cực |
| −15 … +15 | Trung lập |
| +15 … +40 | Tích cực |
| ≥ +40 | Rất tích cực |

Ví dụ: (BTC −42, ETH −35, SOL −23, BNB −41) ÷ 4 = **−35, Tiêu cực**.

**Chế độ thị trường**: đếm số coin đang Đi ngang / Xu hướng tăng / Xu hướng giảm / Chưa rõ.
- **Đi ngang**: ADF < 0,20.
- **Xu hướng tăng**: giá trên EMA50 4h **và** EMA20 > EMA50.
- **Xu hướng giảm**: giá dưới EMA50 4h **và** EMA20 < EMA50.
- **Chưa rõ**: hai điều kiện trái ngược nhau.

**Điểm cao nhất**: coin có điểm tốt nhất và gợi ý hành động cho nó.

**Tin tức**: tổng điểm tin, bằng số tin tốt trừ số tin xấu. **Bot chặn lệnh Long khi ≤ −4.** Ví dụ hôm nay là **−6**, nên đang chặn.

### 4.4 Thẻ từng coin — cách tính điểm

Mỗi coin được chấm **5 yếu tố**, mỗi yếu tố từ **−2 đến +2**, rồi cộng theo trọng số:

| Yếu tố | Trọng số | Cách chấm | +2 khi | −2 khi |
|---|---|---|---|---|
| **Xu hướng** | 35% | (+1 nếu giá > EMA50 4h, −1 nếu không) + (+1 nếu EMA20 > EMA50, −1 nếu không) | Cả hai đều tăng | Cả hai đều giảm |
| **Động lượng** | 20% | % thay đổi 7 ngày ÷ 5 | Tăng ≥ 10%/tuần | Giảm ≥ 10%/tuần |
| **Định giá (Z)** | 20% | −Z ÷ 1,25 | Z ≤ −2,5 (rẻ) | Z ≥ +2,5 (đắt) |
| **Độ ổn định** | 10% | So biến động 24h với 30 ngày qua | Đang yên nhất tháng | Đang biến động mạnh nhất tháng |
| **Tin tức** | 15% | Điểm tin ÷ 3 | Điểm tin ≥ +6 | Điểm tin ≤ −6 |

```
Điểm = (35×Xu hướng + 20×Động lượng + 20×Định giá + 10×Ổn định + 15×Tin tức) ÷ 2
```

**Ví dụ BTC hôm nay:**

| Yếu tố | Điểm | Vì sao |
|---|---|---|
| Xu hướng | 0,0 | Giá dưới EMA50 4h (−1) nhưng EMA20 > EMA50 (+1) |
| Động lượng | −1,1 | 7 ngày −5,5% |
| Định giá | −1,0 | Z = +1,22, hơi đắt |
| Độ ổn định | −1,2 | Biến động 24h cao hơn khoảng 80% thời gian trong tháng |
| Tin tức | −2,0 | Điểm tin −6 |

→ (0 − 22 − 20 − 12 − 30) ÷ 2 = **−42**

**Trên mỗi thẻ có:**
- **Dòng nhỏ dưới tên coin**: chế độ thị trường, RSI, % thay đổi 7 ngày.
- **Điểm lớn và thanh màu**: thanh lệch phải (xanh) là tốt, lệch trái (đỏ) là xấu.
- **Nhãn hành động** và **nhãn chế độ**.
- **Playbook**: chiến lược phù hợp (bảng dưới).
- **5 thanh yếu tố**: thanh nào đỏ là đang kéo điểm xuống.
- **Danh sách lý do**: giải thích bằng lời, có "điểm mạnh" và "điểm yếu".
- **🎯 Vùng giá**, nếu có: giá nên đặt lệnh chờ, ví dụ "Mua quanh … (−2σ) · Bán quanh … (+2σ)".
- **Kế hoạch lệnh**, nếu có: giá vào, SL, TP, khối lượng, mất tối đa, R:R.
- **Kiểm chứng**: kết quả backtest của bot tương ứng, để biết gợi ý này trong quá khứ hiệu quả đến đâu.

**Bảng gợi ý hành động:**
| Chế độ | Điều kiện | Gợi ý | Bot tương ứng |
|---|---|---|---|
| Đi ngang | Z ≤ −2 | **Mua (hồi quy)** | Hybrid |
| Đi ngang | Z ≥ +2 | **Chốt lời / Short** | Futures (hoặc chốt Spot) |
| Đi ngang | còn lại | **Chờ vùng giá đẹp** (kèm vùng giá) | Hybrid |
| Tăng | Giá vượt đỉnh 48h | **Mua theo đà** | Breakout |
| Tăng | Z < 0,5 | **Mua khi điều chỉnh** | Hybrid |
| Tăng | Z ≥ 0,5 | **Chờ điều chỉnh** về EMA20 | Hybrid |
| Giảm | Z ≤ −2 và RSI < 30 | **Tích luỹ từng phần** | Smart DCA |
| Giảm | Z > −1 (có Futures) | **Short khi hồi** | Futures |
| Giảm / Chưa rõ | còn lại | **Đứng ngoài** | — |

### 4.5 Phân bổ vốn đề xuất
- Chỉ chọn coin có **điểm > 0** và **không** đang ở xu hướng giảm.
- Tiền chia cho mỗi coin tỷ lệ với **điểm ÷ biến động năm**: coin càng biến động mạnh thì càng ít tiền.
- Mức tự tin = điểm trung bình ÷ 50, tối đa 1. Điểm thấp thì đầu tư ít, giữ nhiều tiền mặt.
- Áp trần mỗi coin và mức tiền mặt tối thiểu theo hồ sơ.
- **Thanh ngang** cho biết % vốn và số USDT của mỗi coin. Thanh xám là tiền mặt.
- **Cảnh báo 🔗**: hiện nếu 2 coin có tương quan ≥ 0,85. Giữ cả hai gần như **nhân đôi rủi ro**, vì chúng lên xuống cùng nhau.
- Ví dụ hôm nay: mọi coin đều điểm âm, nên đề xuất **100% tiền mặt (USDT)**.

### 4.6 🤖 Nhờ AI diễn giải
Bấm **"Tóm tắt bằng Gemini"**: AI đọc bảng số liệu ở trên rồi viết tóm tắt bằng tiếng Việt.
AI **không tự lấy số mới**, chỉ diễn giải số đã có. Nếu báo lỗi, hệ thống tự thử model khác. Hết hạn mức thì để sau.

### 4.7 📚 Thư viện chiến lược
Năm thẻ mô tả 5 chiến lược. Mỗi thẻ ghi:
- **khi nào dùng**;
- **quản trị rủi ro** ra sao;
- **lợi nhuận backtest, sụt vốn, số lệnh, tỷ lệ thắng** gần nhất;
- lệnh để chạy riêng chiến lược đó.

---

## 5. Tab 📈 Phân tích

Phân tích sâu **một coin** (chọn ở sidebar), trên dữ liệu đã tải về máy.

### 5.1 Tiêu đề
Tên coin, khung thời gian, nhãn tín hiệu và một câu giải thích (giống thẻ ở 🏠).
Góc phải ghi giờ của nến cuối cùng.

### 5.2 Năm ô số
| Ô | Nghĩa | Ghi chú nhỏ bên dưới |
|---|---|---|
| **Giá** | Giá đóng cửa nến cuối | |
| **Z-Score** | Mục 1 | Quá mua (> 2) / Quá bán (< −2) / Trung tính |
| **ADF 200 nến** | Mục 1 | Đi ngang (< 0,20) / Có xu hướng |
| **EMA20 / EMA50** | EMA gap % | Dương là EMA nhanh nằm trên |
| **Kurtosis** | "Độ béo đuôi" của lợi nhuận từng nến | **> 3: Đuôi béo**, dễ có cú sốc giá bất ngờ, nên SL chặt hơn |

### 5.3 Biểu đồ 3 tầng (chọn khoảng 7 / 30 / 90 ngày / Tất cả)

**Tầng 1 — Giá:**
- **Nến xanh/đỏ**: giá từng nến.
- **Dải xanh mờ**: ±2σ quanh trung bình. Giá chạm mép dưới là quá bán, mép trên là quá mua.
- **Nét đứt xám**: trung bình 50 nến, là mục tiêu chốt lời của Mean Reversion.
- **Đường xanh dương**: EMA20. **Đường cam**: EMA50. EMA20 cắt lên EMA50 là xu hướng tăng bắt đầu.
- **▲ xanh / ▼ đỏ**: những lần trong quá khứ có tín hiệu Mean Reversion. Điều kiện: đi ngang, Z vượt ±2 **rồi quay đầu**.
  Nhìn các tam giác này để tự đánh giá tín hiệu trong quá khứ có hay không.

**Tầng 2 — Z-Score (đường tím):**
- Vùng **đỏ mờ phía trên +2**: quá mua. Vùng **xanh mờ phía dưới −2**: quá bán. Đường 0 là giá bằng trung bình.

**Tầng 3 — ADF p (đường xanh ngọc):**
- **Vùng xanh dưới nét chấm 0,20**: thị trường đi ngang, Mean Reversion được phép.
- Trên 0,20: có xu hướng.

Rê chuột lên biểu đồ để xem số của cả 3 tầng ở cùng thời điểm.

---

## 6. Tab 🎯 Screener

### 6.1 Bảng lọc tất cả coin đã tải
Mỗi dòng là một cặp coin và khung thời gian. Bảng sắp xếp theo **Z-Score từ thấp đến cao**: coin rẻ nhất nằm trên cùng.

| Cột | Nghĩa |
|---|---|
| Tài sản · Khung | Coin, khung nến |
| Giá | Giá đóng cửa nến cuối |
| Diễn biến (60 nến) | Biểu đồ nhỏ |
| Z-Score | Mục 1 |
| **ADF 200** | ADF trên 200 nến gần nhất. **Bot dùng cột này** |
| ADF toàn bộ | ADF trên toàn bộ dữ liệu (tối đa 5000 nến), để tham khảo dài hạn |
| EMA gap % | Mục 1 |
| Mục tiêu (TB) | Giá trung bình, là nơi Mean Reversion kỳ vọng giá quay về |
| Khuyến nghị | 🟢 MUA / 🔴 BÁN-SHORT / 🚀 TĂNG / 🔻 GIẢM / ⚪ Chờ, Đứng ngoài |

Bấm vào tiêu đề cột để sắp xếp lại.

### 6.2 Ma trận tương quan
Mức độ các coin lên xuống cùng nhau, từ **−1 đến +1**, tính trên lợi nhuận từng nến của khung đang chọn.
- Ô **đỏ đậm** (gần +1): đi cùng nhau. **> 0,80** thì nên giữ 1 trong 2 coin, giữ cả hai là nhân đôi rủi ro.
- Ô **xám** (gần 0): độc lập, tốt cho đa dạng hoá.
- Ô **xanh dương** (âm): đi ngược nhau. Hiếm gặp ở crypto.
- Đường chéo luôn bằng 1, vì đó là coin so với chính nó.

---

## 7. Tab 🛡️ Vốn & Rủi ro

Máy tính khối lượng lệnh cho coin chọn ở sidebar.

### 7.1 Ô nhập (bên trái)
| Ô | Nghĩa |
|---|---|
| **Tổng vốn (USDT)** | Vốn để **tính toán** trên dashboard |
| **Rủi ro tối đa mỗi lệnh (%)** | **Bot dùng thật** (lưu ngay, áp cho lệnh tiếp theo của cả 4 bot) |
| **Hướng** | Long (mua lên) hoặc Short (bán xuống) |
| **Cắt lỗ cách bao nhiêu σ** | Mặc định 2σ, giống bot. SL xa hơn thì lệnh nhỏ hơn nhưng ít bị quét |

> Bot dry-run dùng **ví ảo 1000 USDT** của riêng nó để tính tiền vào lệnh. Bot chỉ lấy **% rủi ro** từ đây.
> Nếu vốn ở đây khác vốn bot, tab hiện cảnh báo ⚠️ và nút **"Dùng vốn của bot"** để đồng bộ bằng một cú bấm.

### 7.2 Sáu ô kết quả
| Ô | Nghĩa |
|---|---|
| **Rủi ro tối đa** | Số tiền mất nếu chạm SL = vốn × % rủi ro |
| **Quy mô lệnh** | Tổng giá trị lệnh (USDT) và số coin tương ứng |
| **Đòn bẩy cần** | Quy mô lệnh ÷ vốn. **1x** thì Spot làm được. **> 1x** thì cần Futures. **> 5x là nguy hiểm** |
| **Cắt lỗ** | Giá SL và khoảng cách % |
| **Chốt lời** | Giá TP (về trung bình, ít nhất 1,5σ) và R:R |
| **VaR 95% / nến** | Trong 95% số nến, mức lỗ **không vượt quá** con số này. Ví dụ −1,2% |
| **CVaR** (dưới VaR) | Trong 5% số nến **tệ nhất**, trung bình lỗ bao nhiêu. Đây là "ngày xấu" thực sự trông như thế nào |

### 7.3 Biểu đồ kịch bản
- 120 nến gần nhất, cùng 3 đường ngang: **Chốt lời** (xanh), **Vào lệnh** (nét chấm), **Cắt lỗ** (đỏ).
- Vùng **xanh** là phần lời, vùng **đỏ** là phần lỗ. Hai vùng chênh nhau càng nhiều về chiều cao thì R:R càng tốt.

---

## 8. Tab 📰 Tin tức

- Lấy khoảng 16 tin mới nhất từ **CoinDesk** và **CoinTelegraph**, tự làm mới mỗi 5 phút.
- Mỗi tin được chấm điểm bằng **từ khoá tiếng Anh** trong tiêu đề và tóm tắt:
  - Tích cực: surge, rally, bull, ETF, approve, adoption, record…
  - Tiêu cực: crash, hack, ban, SEC, lawsuit, dump, fear, CPI…
  - Điểm của một tin = số từ tích cực − số từ tiêu cực. Dương là 🟢, âm là 🔴, bằng 0 là ⚪.
- **Ba ô số**:
  - Số tin tích cực.
  - Số tin tiêu cực.
  - **Điểm tổng** = số tin tốt − số tin xấu.
- **Điểm tổng ≤ −4 thì cả 4 bot ngừng mở lệnh Long mới.** Hôm nay **−6**, nên đang chặn.
- Bấm vào thẻ tin để mở bài gốc.

> Chấm theo **từ khoá nguyên vẹn** ("security" không bị tính là "SEC", "below" không bị tính là "low"),
> nhưng vẫn đơn giản: "Bitcoin hits record **low**" có cả "record" (tốt) lẫn "low" (xấu) nên tính ra 0.
> Coi đây là **nhiệt kế thô**, không phải phân tích tin.

---

## 9. Tab 🤖 Bot Freqtrade

### 9.1 🎛️ Bật / tắt bot
Năm ô cho 5 dịch vụ:
- 🔄 Hybrid (8080)
- 🚀 Breakout (8082)
- 🧺 Smart DCA (8083)
- ⚡ Futures (8081)
- 🔔 Alert bot

| Trạng thái | Nghĩa | Nút |
|---|---|---|
| 🟢 **Đang chạy (nền)** | Bật bằng `./run.sh start` hoặc autostart | **■ Tắt** |
| 🟢 **Đang chạy (Terminal)** | Bạn tự bật trong cửa sổ Terminal | Tắt bằng `Ctrl + C` ở cửa sổ đó |
| ⚫ **Đang tắt** | | **▶ Bật** |

Bot bạn tự tắt bằng nút **sẽ không** bị watchdog bật lại. Bot tắt do lỗi thì tự bật lại sau tối đa 5 phút.

### 9.2 Bot đang chạy (tự làm mới mỗi 30 giây)
Chọn bot ở thanh trên: Hybrid 8080 · Futures 8081 · Breakout 8082 · Smart DCA 8083.

Dòng nhỏ đầu tiên: **🧪 DRY-RUN (tiền ảo)** hoặc **💰 LIVE (TIỀN THẬT)**, tên chiến lược, spot/futures.

| Ô | Nghĩa |
|---|---|
| **Lợi nhuận đã chốt** | Lời/lỗ của các lệnh **đã đóng** (USDT và %) |
| **Tổng (gồm lệnh mở)** | Đã chốt + lời/lỗ tạm tính của lệnh đang mở |
| **Số lệnh** | Tổng số lệnh, kèm số thắng / thua |
| **Lệnh đang mở** | Số lệnh chưa đóng |

**Bảng Lệnh đang mở:**
| Cột | Nghĩa |
|---|---|
| pair | Coin |
| is_short | True là lệnh Short (chỉ Futures) |
| enter_tag | **Lý do vào lệnh** (bảng dưới) |
| open_date | Giờ vào lệnh (UTC, giờ VN = UTC + 7) |
| open_rate / current_rate | Giá vào / giá hiện tại |
| stake_amount | Số USDT đã bỏ vào |
| leverage | Đòn bẩy (Spot luôn là 1) |
| Lãi/lỗ % | Lời/lỗ tạm tính |
| stop_loss_abs | Giá cắt lỗ hiện tại. Có thể dịch lên khi lời (trailing) |

**Bảng Lệnh đã đóng gần nhất**: thêm cột `close_date`, `exit_reason` (lý do thoát) và `profit_abs` (lời/lỗ USDT).

**Từ điển enter_tag / exit_reason:**
| Mã | Nghĩa |
|---|---|
| `mean_rev` / `mean_rev_short` | Vào theo Mean Reversion (Z vượt ±2 rồi quay đầu) |
| `trend` / `trend_short` | Vào theo xu hướng EMA |
| `breakout` | Phá đỉnh 48 giờ |
| `dca` | Lần mua đầu của Smart DCA. `dca_add_1`, `dca_add_2` là các lần mua thêm |
| `z_revert` | Thoát vì Z đã quay về trung bình. Mục tiêu đạt |
| `mr_timeout` | Thoát vì giữ lệnh Mean Reversion quá lâu mà giá không hồi |
| `ema_cross` | Thoát vì EMA20 cắt ngược EMA50 (hết xu hướng) |
| `channel_exit` | Breakout: giá thủng đáy 24 giờ |
| `dca_take_profit` | Smart DCA: lời 4% trên giá vốn |
| `roi` | Đạt mục tiêu lợi nhuận theo thời gian |
| `stop_loss` / `trailing_stop_loss` | Chạm cắt lỗ / chạm cắt lỗ đã kéo lên |
| `force_exit` | Bạn đóng tay (`/forceexit`) |

---

## 10. Tab 📊 Backtest

### 10.1 🧪 Kiểm chứng theo giai đoạn (walk-forward)
Câu hỏi nó trả lời: **"Chiến lược có ổn định qua nhiều kiểu thị trường không, hay chỉ may mắn?"**

Cách làm: chạy cùng một bộ tham số trên **từng 6 tháng riêng biệt**, không tối ưu lại giữa các giai đoạn.
Chạy lại bằng `./run.sh validate`.

**Nút chuyển** "Có bộ lọc thị trường" / "Không lọc (để so sánh)": xem bộ lọc SMA200 giúp được bao nhiêu.

**Bản đồ nhiệt**: mỗi hàng là một chiến lược, mỗi cột là một giai đoạn 6 tháng. Hàng cuối là **Mua & giữ** (thị trường).
- Ô **xanh** là có lãi, ô **đỏ** là lỗ, màu càng đậm thì con số càng lớn.
- Ô **0,0%** là bot đứng ngoài cả giai đoạn, nhờ bộ lọc.

Ví dụ (có bộ lọc):
| | 12/24–06/25 | 06/25–12/25 | 12/25–06/26 | 06/26–11/26 |
|---|---|---|---|---|
| Hybrid | −10,5% | +3,6% | 0,0% | −1,4% |
| Breakout | −10,1% | +0,2% | 0,0% | +2,3% |
| Smart DCA | −7,2% | 0,0% | 0,0% | −0,5% |
| Hybrid Futures | −18,3% | +6,0% | +2,2% | −2,4% |
| **Thị trường** | −11,4% | +1,1% | **−23,5%** | −18,2% |

Cách đọc: trong giai đoạn thị trường giảm mạnh nhất (−23,5%), các bot Spot đứng ngoài (0%), còn Futures lời +2,2% nhờ Short.

**Thẻ tổng kết từng chiến lược:**
| Dòng | Nghĩa |
|---|---|
| Nhãn **Ổn định / Chưa ổn định / Không ổn định** | Có lãi ở ≥ 75% / ≥ 50% / < 50% số giai đoạn |
| Giai đoạn có lãi | Ví dụ 1 / 4 |
| Thắng thị trường | Số giai đoạn lời nhiều hơn (hoặc lỗ ít hơn) mua & giữ |
| Tổng lãi/lỗ các giai đoạn | Cộng % các giai đoạn |
| Sụt vốn tệ nhất | DD lớn nhất trong một giai đoạn |

> Hiện **chưa chiến lược nào "Ổn định"**. Đó là lý do chỉ nên chạy dry-run.

### 10.2 📊 Kết quả Backtest Freqtrade
- **File kết quả**: chọn lần backtest muốn xem. Mặc định là lần gần nhất có Hybrid.
- **Bảng so sánh**:
  - Số lệnh, Lợi nhuận % và USDT.
  - Thắng / Thua.
  - **Sụt vốn tối đa**.
  - **Giữ lệnh TB**: trung bình giữ một lệnh bao lâu.
- **Đường cong vốn**: tài khoản tăng/giảm thế nào qua từng lệnh.
  - Nét chấm ngang là **vốn ban đầu**: đường nằm trên là đang lời, nằm dưới là đang lỗ.
  - Đường đi lên đều đặn thì tốt. Đường răng cưa, lao dốc thì rủi ro cao.
  - Số ở cuối mỗi đường là vốn cuối cùng.
- Dưới biểu đồ: **"Thị trường thay đổi trong giai đoạn"**, để so sánh.
- **Mục mở rộng "Chi tiết …"** cho từng chiến lược:
  - **Half-Kelly = x% vốn**: theo toán xác suất, nên đặt bao nhiêu % vốn mỗi lệnh dựa trên tỷ lệ thắng và
    lời/lỗ trung bình thật của backtest. **0%** nghĩa là chiến lược không có lợi thế, đừng tăng vốn cho nó.
  - **Bảng theo lý do thoát**: lý do nào đem lại lời, lý do nào gây lỗ (ví dụ `stop_loss` thường lỗ, `z_revert` thường lời).
  - **Danh sách từng lệnh**.

---

## 11. Màu sắc và ký hiệu

| Thấy | Nghĩa |
|---|---|
| 🟢 / chữ xanh / thẻ phát sáng xanh | Tốt, tăng, tín hiệu Long |
| 🔴 / chữ đỏ / thẻ phát sáng đỏ | Xấu, giảm, tín hiệu Short |
| ⚪ / xám / vàng | Chờ, trung lập |
| σ | Độ lệch chuẩn (xem mục 1) |
| ▲ / ▼ trên biểu đồ | Điểm tín hiệu Long / Short trong quá khứ |
| "Nến đã đóng · hh:mm UTC" | Giờ của nến dùng để tính (giờ VN = UTC + 7) |

---

## 12. Câu hỏi thường gặp

**Tab 🏠 báo "Long" mà bot không vào lệnh?**
Bot còn qua thêm 3 lớp kiểm tra:
1. **Bộ lọc SMA200**: BTC dưới SMA200 thì không Long.
2. **Tin tức**: điểm ≤ −4 thì không Long.
3. **Bảo vệ**: tạm dừng sau chuỗi cắt lỗ, dừng khi sụt vốn > 15%.

Ngoài ra, tín hiệu Mean Reversion của bot cần Z **quay đầu** sau khi vượt −2, không chỉ chạm −2.

**Số ở 🏠 và 🧭 lệch nhau một chút?**
- 🏠 dùng 400 nến và chu kỳ Z theo sidebar.
- 🧭 dùng 1000 nến và luôn dùng chu kỳ 50.

Cùng logic, chỉ khác lượng dữ liệu.

**Dashboard có tự cập nhật không?**
- Giá: mỗi 60 giây khi tải lại trang.
- Tín hiệu và tin tức: mỗi 5 phút.
- Bộ lọc SMA200: mỗi 15 phút.
- Tab 🤖: tự làm mới mỗi 30 giây.

Nhấn `R` trên trang (hoặc tải lại trình duyệt) để cập nhật ngay.

**Đổi cài đặt nào thì bot thay đổi theo?**
Chỉ **% rủi ro**, đổi ở tab 🛡️ hoặc nút "Áp dụng" ở tab 🧭, và nút **Bật/Tắt** ở tab 🤖.
Mọi thứ khác trên dashboard chỉ để xem.

**Khi nào mới nên nghĩ tới tiền thật?**
Khi tab 📊 có chiến lược đạt **"Ổn định"**, **và** bot dry-run chạy vài tháng có lãi trên tab 🤖.
Hiện cả hai điều kiện đều chưa đạt.

Xem thêm: lệnh hay dùng → [LENH.md](LENH.md) · hướng dẫn dài → [HUONG_DAN_CHI_TIET.md](HUONG_DAN_CHI_TIET.md).
