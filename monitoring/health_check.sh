#!/bin/bash
# CONTENT-PIPELINE — Stream Health Check + LINE Notify
# ตรวจสอบ FFmpeg stream ทุก 5 นาที แจ้งเตือนผ่าน LINE เมื่อ stream ล่ม
#
# Setup:
#   1. ไปที่ https://notify-bot.line.me/my/
#   2. กด "Generate token" → เลือก "1-on-1 chat with LINE Notify"
#   3. Copy token มาใส่ด้านล่าง
#   4. chmod +x health_check.sh
#   5. เพิ่มใน crontab: */5 * * * * bash ~/CONTENT-PIPELINE/scripts/health_check.sh
#
# Usage:
#   bash health_check.sh              # ตรวจสอบครั้งเดียว
#   bash health_check.sh --test       # ทดสอบส่ง LINE

# ── Config ───────────────────────────────────────────────────
LINE_TOKEN="YOUR_LINE_NOTIFY_TOKEN"
LOG=~/CONTENT-PIPELINE/logs/health_check.log
STATE_FILE=~/CONTENT-PIPELINE/logs/.stream_state
STREAM_SCRIPT=~/CONTENT-PIPELINE/scripts/stream.sh
CHECK_INTERVAL=300  # 5 นาที (สำหรับ log)

# ── Functions ────────────────────────────────────────────────
send_line() {
    local msg="$1"
    curl -s -X POST https://notify-api.line.me/api/notify \
        -H "Authorization: Bearer $LINE_TOKEN" \
        -d "message=$msg" > /dev/null 2>&1
}

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

get_uptime() {
    local pid=$(pgrep -x "ffmpeg")
    if [ -n "$pid" ]; then
        ps -o etime= -p "$pid" 2>/dev/null | xargs
    fi
}

get_stream_info() {
    local pid=$(pgrep -x "ffmpeg")
    if [ -n "$pid" ]; then
        local cpu=$(ps -o %cpu= -p "$pid" 2>/dev/null | xargs)
        local mem=$(ps -o %mem= -p "$pid" 2>/dev/null | xargs)
        local uptime=$(get_uptime)
        echo "PID:$pid CPU:${cpu}% MEM:${mem}% Uptime:$uptime"
    fi
}

# ── Test mode ────────────────────────────────────────────────
if [ "$1" = "--test" ]; then
    echo "Sending test message to LINE..."
    send_line "
[CONTENT-PIPELINE TEST]
Health check is working!
Time: $(date '+%Y-%m-%d %H:%M:%S')
Stream: $(get_stream_info || echo 'Not running')"
    echo "Done! Check LINE."
    exit 0
fi

# ── Main check ───────────────────────────────────────────────
FFMPEG_PID=$(pgrep -x "ffmpeg")
PREV_STATE="unknown"
[ -f "$STATE_FILE" ] && PREV_STATE=$(cat "$STATE_FILE")

if [ -n "$FFMPEG_PID" ]; then
    # Stream is running
    echo "running" > "$STATE_FILE"

    if [ "$PREV_STATE" = "down" ]; then
        # Stream recovered
        INFO=$(get_stream_info)
        log_msg "RECOVERED — $INFO"
        send_line "
[CONTENT-PIPELINE] Stream RECOVERED
$INFO
Time: $(date '+%Y-%m-%d %H:%M:%S')"
    else
        log_msg "OK — $(get_stream_info)"
    fi
else
    # Stream is DOWN
    echo "down" > "$STATE_FILE"
    log_msg "DOWN — FFmpeg not found"

    if [ "$PREV_STATE" != "down" ]; then
        # First time detecting down — alert + try restart
        send_line "
[CONTENT-PIPELINE] Stream DOWN!
FFmpeg process not found.
Attempting auto-restart...
Time: $(date '+%Y-%m-%d %H:%M:%S')"

        # Try restart
        screen -ls | grep "CONTENT-PIPELINE" | grep -v "watchdog\|health" | \
            awk '{print $1}' | xargs -I{} screen -S {} -X quit 2>/dev/null
        sleep 2
        screen -dmS CONTENT-PIPELINE bash "$STREAM_SCRIPT"
        sleep 5

        # Check if restart worked
        NEW_PID=$(pgrep -x "ffmpeg")
        if [ -n "$NEW_PID" ]; then
            echo "running" > "$STATE_FILE"
            log_msg "RESTARTED — PID: $NEW_PID"
            send_line "
[CONTENT-PIPELINE] Stream RESTARTED
New PID: $NEW_PID
Time: $(date '+%Y-%m-%d %H:%M:%S')"
        else
            log_msg "RESTART FAILED"
            send_line "
[CONTENT-PIPELINE] RESTART FAILED!
Manual intervention needed.
SSH: console.cloud.google.com
Time: $(date '+%Y-%m-%d %H:%M:%S')"
        fi
    else
        # Already notified, just log
        log_msg "STILL DOWN — already notified"
    fi
fi
