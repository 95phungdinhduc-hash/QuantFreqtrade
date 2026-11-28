#!/usr/bin/env bash
# =====================================================================
#  QuantFreqtrade — lệnh điều khiển tất cả trong 1 file
#  Gõ:  ./run.sh help
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
PY="$ROOT/.venv/bin/python"
FT="$ROOT/.venv/bin/freqtrade"
CFG="user_data/config.json"
CFG_FUT="user_data/config.futures.json"

load_env() {
  # Nạp .env nhưng KHÔNG ghi đè biến đã có sẵn, để có thể tạm đổi khi chạy, ví dụ:
  #   FREQTRADE__TELEGRAM__ENABLED=false ./run.sh dryrun
  [[ -f .env ]] || return 0
  local line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"; key="${key//[[:space:]]/}"
    val="${line#*=}"; val="${val%\"}"; val="${val#\"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ -z "${!key+x}" ]]; then export "$key=$val"; fi
  done < .env
  return 0
}

# Thông báo Telegram cho bot phụ (Breakout, DCA, Futures) qua WEBHOOK: bot chỉ GỬI tin, không đọc tin,
# nên không tranh token với bot Hybrid (bot duy nhất nhận lệnh /status, /profit...).
WEBHOOK_ENV=()
bot_notify_on() { [[ "${BOT_TELEGRAM_NOTIFY:-false}" == true ]]; }  # 4 bot tiền ảo có nhắn Telegram không

tg_webhook_env() {  # $1 = tên bot hiện trong tin nhắn
  WEBHOOK_ENV=()
  bot_notify_on || return 0   # mặc định IM LẶNG: Telegram chỉ dành cho tín hiệu của alert bot
  [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]] || return 0
  local n=$'\n' b="[$1]"
  WEBHOOK_ENV=(
    "FREQTRADE__WEBHOOK__ENABLED=true"
    "FREQTRADE__WEBHOOK__FORMAT=json"
    "FREQTRADE__WEBHOOK__RETRIES=2"
    "FREQTRADE__WEBHOOK__URL=https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage?chat_id=${TELEGRAM_CHAT_ID}"
    "FREQTRADE__WEBHOOK__ENTRY_FILL__TEXT=🟢 $b VÀO LỆNH #{trade_id} {pair}${n}Hướng: {direction} x{leverage:.0f} · Kiểu: {enter_tag}${n}Giá: {open_rate}${n}Tiền: {stake_amount:.2f} {stake_currency}"
    "FREQTRADE__WEBHOOK__EXIT_FILL__TEXT=🏁 $b THOÁT LỆNH #{trade_id} {pair}${n}Lãi/lỗ: {profit_ratio:.2%} ({profit_amount:.2f} {stake_currency})${n}Lý do: {exit_reason}${n}Giá: {open_rate} → {close_rate}"
    "FREQTRADE__WEBHOOK__STATUS__TEXT=ℹ️ $b {status}"
    "FREQTRADE__WEBHOOK__WARNING__TEXT=⚠️ $b {status}"
    "FREQTRADE__WEBHOOK__EXCEPTION__TEXT=❌ $b {status}"
  )
}

need_venv() {
  [[ -x "$PY" ]] || { echo "[!] Chưa cài đặt. Chạy: ./run.sh setup"; exit 1; }
}

cmd_setup() {
  local PYBIN
  PYBIN="$(command -v python3.12 || command -v python3.11 || command -v python3.13 || true)"
  [[ -n "$PYBIN" ]] || { echo "[!] Cần Python 3.11+  ->  brew install python@3.12"; exit 1; }
  echo "[*] Dùng $PYBIN"
  [[ -d .venv ]] || "$PYBIN" -m venv .venv
  "$PY" -m pip install -q --upgrade pip wheel setuptools
  "$PY" -m pip install -q -r requirements.txt
  "$PY" -m pip check
  if [[ ! -f .env ]]; then
    cp .env.example .env && chmod 600 .env
    echo "[+] Đã tạo .env — hãy mở file .env và điền Telegram/Gemini nếu muốn."
  fi
  "$PY" tools/ensure_secrets.py
  echo "[✓] Cài đặt xong. Phiên bản Freqtrade: $("$FT" --version 2>/dev/null | tail -1)"
}

# =====================================================================
#  TỰ ĐỘNG HOÁ: bật/tắt mọi thứ chạy NỀN (không cần giữ Terminal mở)
# =====================================================================
LOGDIR="$ROOT/logs"
SERVICES=(dashboard hybrid breakout dca futures alert)
DEFAULT_SERVICES=(dashboard hybrid alert)
LA_DIR="$HOME/Library/LaunchAgents"
LA_START="com.quantfreqtrade.start"
LA_WEEKLY="com.quantfreqtrade.weekly"
LA_WATCHDOG="com.quantfreqtrade.watchdog"
AUTOSTART_SERVICES="all"   # autostart bật gì khi mở máy: "all" = dashboard + 4 bot + alert

svc_args() {
  case "$1" in
    dashboard) echo "dashboard --server.headless true" ;;
    hybrid)    echo "dryrun" ;;
    breakout)  echo "dryrun-breakout" ;;
    dca)       echo "dryrun-dca" ;;
    futures)   echo "dryrun-futures" ;;
    alert)     echo "alert" ;;
    *) return 1 ;;
  esac
}
svc_port() {
  case "$1" in dashboard) echo 8502 ;; hybrid) echo 8080 ;; futures) echo 8081 ;;
               breakout) echo 8082 ;; dca) echo 8083 ;; *) echo "" ;; esac
}
svc_label() {
  case "$1" in dashboard) echo "Dashboard" ;; hybrid) echo "Bot Spot (Hybrid)" ;; breakout) echo "Bot Breakout" ;;
               dca) echo "Bot Smart DCA" ;; futures) echo "Bot Futures" ;; alert) echo "Alert bot Telegram" ;; esac
}
svc_pid() {  # PID nếu dịch vụ do ./run.sh start bật và còn sống
  local f="$LOGDIR/$1.pid" pid
  [[ -f "$f" ]] || return 0
  pid="$(cat "$f")"
  kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o command= 2>/dev/null | grep -q "run.sh" && echo "$pid"
  return 0
}
port_busy() { [[ -n "$1" ]] && lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
svc_running() {
  [[ -n "$(svc_pid "$1")" ]] && return 0
  port_busy "$(svc_port "$1")" && return 0
  [[ "$1" == alert ]] && pgrep -f "alert_bot/alert_bot.py" >/dev/null && return 0
  return 1
}
kill_tree() {  # tắt tiến trình và mọi tiến trình con (bot nhận SIGTERM -> tắt êm)
  local p="$1" c
  for c in $(pgrep -P "$p" 2>/dev/null); do kill_tree "$c"; done
  kill -TERM "$p" 2>/dev/null || true
}
expand_services() {  # "" -> mặc định, "all" -> tất cả
  if [[ $# -eq 0 ]]; then echo "${DEFAULT_SERVICES[@]}"
  elif [[ "$1" == all ]]; then echo "${SERVICES[@]}"
  else echo "$@"; fi
}

cmd_start() {
  mkdir -p "$LOGDIR"
  local s args launcher=()
  command -v caffeinate >/dev/null && launcher=(caffeinate -i)  # Mac không tự ngủ khi bot đang chạy
  export PYTHONUNBUFFERED=1  # log ghi ra file ngay lập tức
  for s in $(expand_services "$@"); do
    args="$(svc_args "$s")" || { echo "  [!] Không có dịch vụ tên '$s'. Chọn: ${SERVICES[*]}"; continue; }
    if svc_running "$s"; then echo "  [ĐÃ CHẠY] $(svc_label "$s")"; continue; fi
    echo "===== $(date '+%Y-%m-%d %H:%M:%S') BẬT =====" >> "$LOGDIR/$s.log"
    # shellcheck disable=SC2086
    nohup ${launcher[@]+"${launcher[@]}"} "$ROOT/run.sh" $args >> "$LOGDIR/$s.log" 2>&1 &
    echo $! > "$LOGDIR/$s.pid"
    echo "  [  BẬT   ] $(svc_label "$s")   (log: logs/$s.log)"
  done
  echo "→ Xem trạng thái: ./run.sh status · Tắt: ./run.sh stop"
}

cmd_stop() {
  local s pid i
  local list; list="$(if [[ $# -eq 0 ]]; then echo "${SERVICES[@]}"; else expand_services "$@"; fi)"
  for s in $list; do
    pid="$(svc_pid "$s")"
    if [[ -n "$pid" ]]; then
      kill_tree "$pid"
      for i in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
      kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null
      # chờ tiến trình con (freqtrade) nhả cổng — nếu không, "restart" bật lại quá sớm sẽ tưởng bot còn chạy
      for i in $(seq 1 20); do port_busy "$(svc_port "$s")" || break; sleep 1; done
      rm -f "$LOGDIR/$s.pid"
      echo "  [  TẮT   ] $(svc_label "$s")"
    elif svc_running "$s"; then
      echo "  [ CHÚ Ý  ] $(svc_label "$s") đang chạy trong một Terminal khác → bấm Ctrl + C ở Terminal đó"
    fi
  done
}

cmd_status() {
  local s port pid where
  for s in "${SERVICES[@]}"; do
    port="$(svc_port "$s")"; pid="$(svc_pid "$s")"
    where=""; [[ -n "$port" ]] && where="  http://127.0.0.1:$port"
    if [[ -n "$pid" ]]; then echo "  [ĐANG CHẠY] $(svc_label "$s")$where   (chạy nền)"
    elif svc_running "$s"; then echo "  [ĐANG CHẠY] $(svc_label "$s")$where   (trong Terminal)"
    else echo "  [   TẮT   ] $(svc_label "$s")"; fi
  done
  if [[ -f "$LA_DIR/$LA_START.plist" ]]; then echo "  Tự bật khi mở máy: CÓ"; else echo "  Tự bật khi mở máy: KHÔNG"; fi
  if [[ -f "$LA_DIR/$LA_WEEKLY.plist" ]]; then echo "  Cập nhật hằng tuần (CN 8:00): CÓ"; else echo "  Cập nhật hằng tuần: KHÔNG"; fi
  if [[ -f "$LA_DIR/$LA_WATCHDOG.plist" ]]; then echo "  Tự bật lại bot bị tắt (5 phút/lần): CÓ"; else echo "  Tự bật lại bot bị tắt: KHÔNG"; fi
}

capital_env() {  # $1 = tên bot, $2 = file config -> CAP_ENV: vốn riêng của bot (quant.capital trong config)
  # Nhiều bot dùng chung 1 tài khoản sàn thì mỗi bot chỉ được dùng phần vốn của nó
  # (available_capital); dry-run cũng mô phỏng y như vậy (dry_run_wallet = phần vốn đó).
  local v
  v="$("$PY" -c 'import json,sys
c = json.load(open(sys.argv[1])).get("quant", {}).get("capital", {})
t, s = float(c.get("total_usdt", 0)), float(c.get("split", {}).get(sys.argv[2], 0))
print(round(t * s, 2) if t > 0 and s > 0 else "")' "$2" "$1" 2>/dev/null || true)"
  CAP_ENV=()
  [[ -n "$v" ]] && CAP_ENV=(FREQTRADE__DRY_RUN_WALLET="$v" FREQTRADE__AVAILABLE_CAPITAL="$v")
  return 0
}

tg_notify() {  # gửi 1 tin Telegram (bỏ qua nếu chưa cấu hình hoặc mất mạng)
  [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]] || return 0
  curl -s -m 10 -o /dev/null "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=$1" || true
}

cmd_watchdog() {
  # Chạy mỗi 5 phút (launchd). Kiểm tra 4 thứ, có vấn đề thì ghi logs/watchdog.log + báo Telegram:
  #   1. Máy ngủ / tắt: lần chạy trước cách đây > 15 phút -> bot đã "mù" trong khoảng đó.
  #   2. Mất kết nối Binance: ghi lúc mất, báo khi có mạng lại (nếu mất >= 10 phút).
  #   3. Bot chết: còn file .pid (= chưa bị ./run.sh stop) mà tiến trình đã chết -> bật lại.
  #   4. Bot treo: tiến trình còn sống, mạng vẫn có, nhưng 2 lần kiểm tra liên tiếp (~10 phút)
  #      bot không xử lý vòng lặp nào (API /health) -> khởi động lại.
  #   Kèm: dọn log quá 20 MB.
  mkdir -p "$LOGDIR"
  local st="$LOGDIR/.watchdog" now last since s f port body ts n q msgs=()
  mkdir -p "$st"
  now="$(date +%s)"
  # wlog "tin" [quiet]: luôn ghi log; chỉ nhắn Telegram khi không có "quiet" (việc của bot ảo chỉ nhắn
  # khi BOT_TELEGRAM_NOTIFY=true — Telegram mặc định chỉ dành cho alert bot)
  wlog() {
    echo "$(date '+%F %T') $1" >> "$LOGDIR/watchdog.log"
    if [[ "${2:-}" != quiet ]] || bot_notify_on; then msgs+=("$1"); fi
  }
  fmt_t() { date -r "$1" '+%H:%M %d/%m'; }

  # 1. máy ngủ / tắt
  if [[ -f "$st/last_run" ]]; then
    last="$(cat "$st/last_run")"
    if (( now - last > 900 )); then
      wlog "💤 Watchdog không chạy từ $(fmt_t "$last") đến $(fmt_t "$now") (~$(( (now - last) / 60 )) phút): máy ngủ, tắt hoặc gập nắp — alert bot không quét tín hiệu trong khoảng này."
    fi
  fi
  echo "$now" > "$st/last_run"

  # 2. kết nối Binance
  local net_ok=1
  curl -s -m 8 -o /dev/null "https://api.binance.com/api/v3/ping" || net_ok=0
  if (( net_ok == 0 )); then
    [[ -f "$st/net_down" ]] || { echo "$now" > "$st/net_down"; echo "$(date '+%F %T') Mất kết nối Binance" >> "$LOGDIR/watchdog.log"; }
  elif [[ -f "$st/net_down" ]]; then
    since="$(cat "$st/net_down")"; rm -f "$st/net_down"
    if (( now - since >= 600 )); then
      wlog "📡 Mất kết nối Binance từ $(fmt_t "$since") đến $(fmt_t "$now") (~$(( (now - since) / 60 )) phút) — alert bot không quét được tín hiệu trong khoảng này."
    fi
  fi

  # 3. bot chết bất thường
  for s in "${SERVICES[@]}"; do
    f="$LOGDIR/$s.pid"
    [[ -f "$f" ]] || continue
    [[ -n "$(svc_pid "$s")" ]] && continue
    rm -f "$f"
    if svc_running "$s"; then continue; fi   # đang chạy trong Terminal -> không đụng vào
    cmd_start "$s" >> "$LOGDIR/watchdog.log" 2>&1
    case "$s" in alert|dashboard) q="" ;; *) q=quiet ;; esac   # bot tiền ảo: chỉ ghi log
    wlog "⚠️ $(svc_label "$s") bị tắt bất thường — đã tự bật lại." $q
  done

  # 4. bot treo (chỉ xét khi có mạng: mất mạng thì bot đứng chờ là bình thường)
  if (( net_ok == 1 )); then
    for s in hybrid breakout dca futures; do
      f="$LOGDIR/$s.pid"
      if [[ -z "$(svc_pid "$s")" ]] || (( now - $(stat -f %m "$f") < 600 )); then  # tắt hoặc vừa bật
        rm -f "$st/$s.bad"; continue
      fi
      port="$(svc_port "$s")"
      body="$(curl -s -m 5 -u "${FREQTRADE__API_SERVER__USERNAME:-}:${FREQTRADE__API_SERVER__PASSWORD:-}" \
               "http://127.0.0.1:$port/api/v1/health" || true)"
      ts="$(printf '%s' "$body" | grep -o '"last_process_ts":[0-9]*' | cut -d: -f2 || true)"
      if [[ -n "$ts" ]] && (( now - ts <= 600 )); then rm -f "$st/$s.bad"; continue; fi
      n=$(( $(cat "$st/$s.bad" 2>/dev/null || echo 0) + 1 ))
      echo "$n" > "$st/$s.bad"
      echo "$(date '+%F %T') $(svc_label "$s") không phản hồi lần $n (health: ${body:-không trả lời})" >> "$LOGDIR/watchdog.log"
      if (( n >= 2 )); then
        rm -f "$st/$s.bad"
        { cmd_stop "$s"; cmd_start "$s"; } >> "$LOGDIR/watchdog.log" 2>&1
        wlog "🔁 $(svc_label "$s") bị treo (> 10 phút không xử lý) — đã khởi động lại." quiet
      fi
    done
  fi

  for f in "$LOGDIR"/*.log; do
    [[ -f "$f" ]] || continue
    if [[ "$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f")" -gt 20971520 ]]; then
      cp "$f" "$f.1" && : > "$f"   # giữ 1 bản cũ (.log.1), bot vẫn ghi tiếp vào file hiện tại
    fi
  done

  if [[ ${#msgs[@]} -gt 0 ]]; then
    local text="🐶 QuantFreqtrade watchdog"
    for f in "${msgs[@]}"; do text+=$'\n'"• $f"; done
    tg_notify "$text"
  fi
  return 0
}

cmd_logs() {
  local s="${1:-hybrid}"
  [[ -f "$LOGDIR/$s.log" ]] || { echo "[!] Chưa có log cho '$s'. Có: $(ls "$LOGDIR" 2>/dev/null | grep '\.log$' | tr '\n' ' ')"; exit 1; }
  echo "(Đang xem log $s — bấm Ctrl + C để thoát, bot vẫn chạy)"
  tail -n 40 -f "$LOGDIR/$s.log"
}

cmd_weekly() {
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') CẬP NHẬT HẰNG TUẦN ====="
  "$ROOT/run.sh" download 10
  "$ROOT/run.sh" download-futures 10
  FREQTRADE__TELEGRAM__ENABLED=false "$ROOT/run.sh" backtest-all
  # kiểm chứng theo giai đoạn (mỗi bản ~10–20 phút): có bộ lọc thị trường + không lọc để so sánh
  "$ROOT/run.sh" validate || echo "[!] walk-forward lỗi (xem ở trên)"
  FREQTRADE__QUANT__MARKET_FILTER=false "$ROOT/run.sh" validate --out user_data/walk_forward_nofilter.json \
    || echo "[!] walk-forward (không lọc) lỗi"
  "$ROOT/run.sh" web-data push || echo "[!] Không đưa được kết quả lên bản web (xem lỗi ở trên)"
  echo "===== XONG — kết quả mới đã có trên dashboard và bản web (tab 📊 Backtest, 🧭 Tư vấn) ====="
}

write_plist() {  # $1 = label, $2 = lệnh, $3 = khối XML lịch chạy
  cat > "$LA_DIR/$1.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$1</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>-lc</string><string>cd "$ROOT" &amp;&amp; ./run.sh $2</string></array>
  $3
  <key>AbandonProcessGroup</key><true/>
  <key>StandardOutPath</key><string>$LOGDIR/launchd-${1##*.}.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/launchd-${1##*.}.log</string>
</dict>
</plist>
PLIST
}

cmd_autostart() {
  local uid; uid="$(id -u)"
  case "${1:-}" in
    on)
      mkdir -p "$LA_DIR" "$LOGDIR"
      write_plist "$LA_START" "start $AUTOSTART_SERVICES" "<key>RunAtLoad</key><true/>"
      write_plist "$LA_WEEKLY" "weekly" \
        "<key>StartCalendarInterval</key><dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>"
      write_plist "$LA_WATCHDOG" "watchdog" "<key>StartInterval</key><integer>300</integer>"
      plutil -lint "$LA_DIR/$LA_START.plist" "$LA_DIR/$LA_WEEKLY.plist" "$LA_DIR/$LA_WATCHDOG.plist" >/dev/null
      launchctl bootout "gui/$uid/$LA_WATCHDOG" 2>/dev/null || true
      launchctl bootstrap "gui/$uid" "$LA_DIR/$LA_WATCHDOG.plist"
      launchctl bootout "gui/$uid/$LA_START" 2>/dev/null || true
      launchctl bootout "gui/$uid/$LA_WEEKLY" 2>/dev/null || true
      launchctl bootstrap "gui/$uid" "$LA_DIR/$LA_WEEKLY.plist"
      # Đăng ký job tự bật; nó chạy ngay 1 lần (giống lúc mở máy) — các dịch vụ đã chạy sẽ được bỏ qua
      launchctl bootstrap "gui/$uid" "$LA_DIR/$LA_START.plist"
      echo "[✓] Đã bật tự động:"
      echo "    • Mỗi lần đăng nhập máy: tự chạy ./run.sh start $AUTOSTART_SERVICES ($(expand_services $AUTOSTART_SERVICES))"
      echo "    • Chủ nhật 8:00 hằng tuần: tải dữ liệu mới + backtest-all"
      echo "    • Mỗi 5 phút: bot nào tắt bất thường thì tự bật lại (báo Telegram) + dọn log > 20 MB"
      echo "    Tắt: ./run.sh autostart off" ;;
    off)
      launchctl bootout "gui/$uid/$LA_START" 2>/dev/null || true
      launchctl bootout "gui/$uid/$LA_WEEKLY" 2>/dev/null || true
      launchctl bootout "gui/$uid/$LA_WATCHDOG" 2>/dev/null || true
      rm -f "$LA_DIR/$LA_START.plist" "$LA_DIR/$LA_WEEKLY.plist" "$LA_DIR/$LA_WATCHDOG.plist"
      echo "[✓] Đã tắt tự động (các bot đang chạy vẫn chạy — tắt bằng ./run.sh stop)" ;;
    *) echo "Dùng: ./run.sh autostart on | off" ;;
  esac
}

cmd_help() {
  cat <<'EOF'
Cách dùng: ./run.sh <lệnh> [tham số thêm cho freqtrade]

  TỰ ĐỘNG (chạy nền, không cần giữ Terminal mở)
    start              Bật dashboard + bot Hybrid + alert bot
    start all          Bật tất cả: dashboard, hybrid, breakout, dca, futures, alert
    start dca breakout Chỉ bật những thứ được kể tên
    stop               Tắt mọi thứ đã bật bằng start     (stop hybrid = chỉ tắt bot Hybrid)
    restart            Tắt rồi bật lại
    logs [tên]         Xem log trực tiếp, ví dụ: ./run.sh logs hybrid   (Ctrl + C để thoát)
    weekly             Tải dữ liệu mới + backtest-all + walk-forward + đưa lên bản web (việc hằng tuần)
    autostart on|off   Tự bật khi mở máy + weekly mỗi Chủ nhật 8:00 + tự bật lại bot bị tắt (5 phút/lần)
    watchdog           Kiểm tra 1 lần: bot chết/treo thì bật lại, báo máy ngủ / mất mạng (autostart chạy 5 phút/lần)
    readiness          Chấm từng điều kiện trước khi dùng tiền thật (bằng chứng, an toàn, bảo mật)

  CÀI ĐẶT
    setup              Tạo môi trường .venv, cài Freqtrade + thư viện, tạo .env
    test               Chạy kiểm thử tự động (pytest + web app khớp số với Python)

  DỮ LIỆU
    import             Chuyển dữ liệu từ ../QuantTradingSystem/quant_data.db (chỉ đọc)
    download [ngày]    Tải nến Spot mới từ Binance (mặc định 365 ngày, 15m + 1h + 4h)
    download-futures [ngày]  Tải nến Futures + funding rate (cho backtest-futures)
    web-data [push]    Xuất backtest + tin cho bản web (docs/data); 'push' đưa lên GitHub. weekly tự chạy lệnh này

  NGHIÊN CỨU
    backtest           Backtest so sánh QuantZScoreStrategy (gốc) vs QuantHybridStrategy (nâng cấp)
    backtest-all       Backtest so sánh CẢ 4 chiến lược Spot: Z-Score, Hybrid, Breakout, Smart DCA
    backtest-futures   Backtest QuantHybridFuturesStrategy (Long + Short, đòn bẩy)
    check-bias         Kiểm tra chiến lược có "nhìn trước tương lai" (lookahead bias) không
    hyperopt [epochs]  Tối ưu tham số QuantHybridStrategy (mặc định 200 vòng)
    validate           Kiểm chứng theo từng giai đoạn 6 tháng trên toàn bộ dữ liệu (walk-forward, 10–20 phút)
    legacy             Chạy lại backtest kiểu cũ (vector hoá) trên dữ liệu Freqtrade để đối chiếu
    plot [cặp]         Vẽ biểu đồ lệnh backtest (mặc định BTC/USDT) -> user_data/plot/

  CHẠY BOT (DRY-RUN = tiền ảo, không mất tiền thật)
    dryrun             Bot Spot, API ở http://127.0.0.1:8080 (mở FreqUI trên trình duyệt)
    dryrun-futures     Bot Futures (Long+Short, đòn bẩy), API cổng 8081
                       muốn có Telegram: FUTURES_TELEGRAM=true ./run.sh dryrun-futures
    dryrun-breakout    Bot chiến lược Breakout (mua theo đà), API cổng 8082
    dryrun-dca         Bot chiến lược Smart DCA (tích luỹ từng phần), API cổng 8083
                       muốn có Telegram (khi KHÔNG chạy bot Spot chính): STRATEGY_TELEGRAM=true ./run.sh dryrun-dca
    dashboard          Dashboard Streamlit nâng cấp ở http://localhost:8502
    alert              Bot cảnh báo Telegram + Gemini AI (+ tóm tắt 8:00, trả lời lệnh /help)
                       thêm --legacy để báo tín hiệu y hệt bản gốc, --once để quét 1 lần
    ui                 Cài giao diện web FreqUI (chạy 1 lần)

  THEO DÕI
    status             Xem bot Spot / Futures / dashboard / alert bot nào đang chạy
    trades             Liệt kê các lệnh của bot Spot (dry-run) từ database
    trades-futures     Liệt kê các lệnh của bot Futures (dry-run) từ database

  KHÁC
    ft <...>           Gọi thẳng freqtrade, ví dụ: ./run.sh ft list-strategies
EOF
}

main() {
  local cmd="${1:-help}"; shift || true
  case "$cmd" in
    setup) cmd_setup ;;
    help|-h|--help) cmd_help ;;
    *)
      need_venv; load_env
      # 🔒 KHOÁ CỨNG: mọi bot luôn chạy TIỀN ẢO, bất kể config hay .env ghi gì.
      # Hệ thống này chỉ gửi tín hiệu để bạn TỰ đặt lệnh — không bao giờ tự giao dịch bằng tiền thật.
      export FREQTRADE__DRY_RUN=true
      case "$cmd" in
        test)      "$PY" -m pytest -q tests "$@"
                   if command -v node >/dev/null; then node --test tests/web/; else echo "(bỏ qua kiểm thử web app: chưa cài Node)"; fi ;;
        import)    "$PY" tools/import_legacy_db.py "$@" ;;
        web-data)
          "$PY" tools/export_web_data.py || exit 1
          if [[ "${1:-}" == push ]]; then
            local files=(docs/data/snapshot.json docs/css/theme.css docs/js/fx.js)
            # chỉ đẩy khi nhánh main không có commit nào khác chưa đẩy -> không vô tình đưa thay đổi khác lên GitHub
            git fetch -q origin main 2>/dev/null || true
            if [[ "$(git rev-parse --abbrev-ref HEAD)" != main || -n "$(git rev-list origin/main..HEAD 2>/dev/null)" ]]; then
              echo "[!] Nhánh hiện tại không phải main hoặc còn commit chưa đẩy — bỏ qua, hãy đẩy bằng tay."; exit 0
            fi
            if git diff --quiet HEAD -- "${files[@]}" && [[ -z "$(git ls-files --others --exclude-standard -- "${files[@]}")" ]]; then
              echo "Không có gì mới để đưa lên."
            else
              git add -- "${files[@]}"
              git commit -q -m "web: cập nhật dữ liệu backtest + tin tức" -- "${files[@]}" && git push -q origin main \
                && echo "Đã đưa lên GitHub — trang web cập nhật sau ~1 phút."
            fi
          else
            echo "Xem thử xong thì chạy: ./run.sh web-data push"
          fi ;;
        download)
          local days="${1:-365}"; shift || true
          "$FT" download-data -c "$CFG" --days "$days" -t 15m 1h 4h 1d "$@" ;;
        download-futures)
          local days="${1:-365}"; shift || true
          "$FT" download-data -c "$CFG_FUT" --days "$days" -t 1h 4h 1d "$@" ;;
        backtest)
          "$FT" backtesting -c "$CFG" --strategy-list QuantZScoreStrategy QuantHybridStrategy \
            --timeframe-detail 15m --export trades --breakdown month "$@" ;;
        backtest-all)
          "$FT" backtesting -c "$CFG" --strategy-list QuantZScoreStrategy QuantHybridStrategy \
            QuantBreakoutStrategy QuantSmartDCAStrategy \
            --timeframe-detail 15m --export trades --breakdown month "$@" ;;
        backtest-futures)
          "$FT" backtesting -c "$CFG_FUT" -s QuantHybridFuturesStrategy --export trades \
            --breakdown month "$@" ;;
        check-bias)
          # Freqtrade bắt buộc có --timerange. Mặc định: 120 ngày gần nhất (tự đổi được bằng --timerange ...)
          local tr=()
          [[ " $* " == *" --timerange"* ]] || tr=(--timerange "$(date -v-120d +%Y%m%d 2>/dev/null || date -d '120 days ago' +%Y%m%d)-")
          "$FT" lookahead-analysis -c "$CFG" --strategy-list QuantHybridStrategy QuantZScoreStrategy \
            QuantBreakoutStrategy QuantSmartDCAStrategy \
            --minimum-trade-amount 5 --targeted-trade-amount 10 ${tr[@]+"${tr[@]}"} "$@" ;;
        hyperopt)
          local epochs="${1:-200}"; shift || true
          "$FT" hyperopt -c "$CFG" -s QuantHybridStrategy --hyperopt-loss SharpeHyperOptLossDaily \
            --spaces buy sell protection -e "$epochs" -j 4 "$@" ;;
        legacy)    "$PY" tools/legacy_backtest.py "$@" ;;
        validate)  "$PY" tools/walk_forward.py "$@" ;;
        plot)
          local pair="${1:-BTC/USDT}"; shift || true
          # Tìm file backtest mới nhất CÓ QuantHybridStrategy (bỏ qua kết quả futures)
          local btfile
          btfile="$("$PY" -c 'import json,pathlib,sys
fs=sorted(pathlib.Path("user_data/backtest_results").glob("*.meta.json"),reverse=True)
m=[f for f in fs if "QuantHybridStrategy" in json.loads(f.read_text())]
print(str(m[0]).replace(".meta.json",".zip") if m else "")')"
          if [[ -n "$btfile" ]]; then
            "$FT" plot-dataframe -c "$CFG" -s QuantHybridStrategy -p "$pair" --backtest-filename "$btfile" \
              --indicators1 rolling_mean ema_fast ema_slow --indicators2 z_score adf_p "$@"
          else
            echo "[i] Chưa có backtest QuantHybridStrategy -> vẽ không kèm lệnh (chạy ./run.sh backtest trước)"
            "$FT" plot-dataframe -c "$CFG" -s QuantHybridStrategy -p "$pair" --no-trades \
              --indicators1 rolling_mean ema_fast ema_slow --indicators2 z_score adf_p "$@"
          fi ;;
        dryrun)
          capital_env hybrid "$CFG"
          local tg_hybrid="${FREQTRADE__TELEGRAM__ENABLED:-false}"
          bot_notify_on || tg_hybrid=false   # im lặng (BOT_TELEGRAM_NOTIFY=false trong .env)
          env ${CAP_ENV[@]+"${CAP_ENV[@]}"} FREQTRADE__TELEGRAM__ENABLED="$tg_hybrid" \
            "$FT" trade -c "$CFG" --db-url "sqlite:///user_data/tradesv3.hybrid.dryrun.sqlite" "$@" ;;
        dryrun-futures)
          # Chỉ 1 bot được dùng 1 Telegram token cùng lúc -> mặc định tắt Telegram cho bot futures.
          # Chỉ chạy bot Futures (không chạy bot Spot) mà muốn có Telegram:
          #   FUTURES_TELEGRAM=true ./run.sh dryrun-futures
          [[ "${FUTURES_TELEGRAM:-false}" == true ]] || tg_webhook_env "Futures"
          capital_env futures "$CFG_FUT"
          env ${WEBHOOK_ENV[@]+"${WEBHOOK_ENV[@]}"} ${CAP_ENV[@]+"${CAP_ENV[@]}"} \
            FREQTRADE__TELEGRAM__ENABLED="${FUTURES_TELEGRAM:-false}" \
            "$FT" trade -c "$CFG_FUT" "$@" ;;
        dryrun-breakout|dryrun-dca)
          # Bot Spot thứ 2/3: cổng API & database riêng để chạy song song với bot Hybrid.
          # Telegram mặc định tắt (token chỉ dùng được cho 1 bot); bật: STRATEGY_TELEGRAM=true
          local strat port db
          if [[ "$cmd" == "dryrun-breakout" ]]; then strat=QuantBreakoutStrategy; port=8082; db=breakout
          else strat=QuantSmartDCAStrategy; port=8083; db=dca; fi
          [[ "${STRATEGY_TELEGRAM:-false}" == true ]] || tg_webhook_env "$( [[ $db == dca ]] && echo "Smart DCA" || echo "Breakout")"
          capital_env "$db" "$CFG"
          env ${WEBHOOK_ENV[@]+"${WEBHOOK_ENV[@]}"} ${CAP_ENV[@]+"${CAP_ENV[@]}"} \
          FREQTRADE__TELEGRAM__ENABLED="${STRATEGY_TELEGRAM:-false}" \
          FREQTRADE__API_SERVER__LISTEN_PORT=$port FREQTRADE__BOT_NAME="QuantFreqtrade-$db" \
            "$FT" trade -c "$CFG" -s "$strat" --db-url "sqlite:///user_data/tradesv3.$db.dryrun.sqlite" "$@" ;;
        dashboard) "$ROOT/.venv/bin/streamlit" run dashboard/app.py --server.port 8502 "$@" ;;
        alert)     "$PY" alert_bot/alert_bot.py "$@" ;;
        ui)        "$FT" install-ui ;;
        status)    cmd_status ;;
        start)     cmd_start "$@" ;;
        stop)      cmd_stop "$@" ;;
        restart)   cmd_stop "$@"; sleep 2; cmd_start "$@" ;;
        logs)      cmd_logs "$@" ;;
        weekly)    cmd_weekly ;;
        watchdog)  cmd_watchdog ;;
        readiness) "$PY" tools/readiness.py ;;
        autostart) cmd_autostart "$@" ;;
        trades)
          "$FT" show-trades -c "$CFG" --db-url "sqlite:///user_data/tradesv3.hybrid.dryrun.sqlite" "$@" ;;
        trades-futures)
          "$FT" show-trades -c "$CFG_FUT" --db-url "sqlite:///user_data/tradesv3.futures.dryrun.sqlite" "$@" ;;
        ft)        "$FT" "$@" ;;
        *) echo "[!] Lệnh không hợp lệ: $cmd"; cmd_help; exit 1 ;;
      esac ;;
  esac
}

main "$@"
