#!/bin/bash
# CONTENT-PIPELINE — Long-form Mix Generator
# สร้าง video 1-3 ชม. จากเพลงทั้งหมด สำหรับ upload YouTube เป็น video ปกติ
#
# Usage:
#   bash longform_mix.sh                    # สร้าง mix จากทุกเพลง
#   bash longform_mix.sh --hours 2          # กำหนดความยาว 2 ชม.
#   bash longform_mix.sh --theme "study"    # ใช้ชื่อ theme
#   bash longform_mix.sh --tracks "Rain on Glass" "3AM Thoughts" "Drift Off"

set -e

# ── Config ───────────────────────────────────────────────────
MUSIC_DIR=~/CONTENT-PIPELINE/music
VISUAL=~/CONTENT-PIPELINE/visuals/background.jpg
OUTPUT_DIR=~/CONTENT-PIPELINE/longform
LOG=~/CONTENT-PIPELINE/logs/longform.log
TARGET_HOURS=2
THEME="study-chill"
SELECTED_TRACKS=()

# ── Parse args ───────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --hours) TARGET_HOURS="$2"; shift 2 ;;
        --theme) THEME="$2"; shift 2 ;;
        --tracks) shift; while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do SELECTED_TRACKS+=("$1"); shift; done ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

mkdir -p "$OUTPUT_DIR"
TARGET_SECONDS=$((TARGET_HOURS * 3600))
TIMESTAMP=$(date +%Y%m%d_%H%M)
OUTPUT_FILE="$OUTPUT_DIR/CONTENT-PIPELINE_${THEME}_${TARGET_HOURS}hr_${TIMESTAMP}.mp4"
TEMP_PLAYLIST="$OUTPUT_DIR/_temp_playlist.txt"
TIMESTAMP_FILE="$OUTPUT_DIR/CONTENT-PIPELINE_${THEME}_${TARGET_HOURS}hr_${TIMESTAMP}_timestamps.txt"

echo "=== CONTENT-PIPELINE Long-form Mix Generator ===" | tee -a "$LOG"
echo "Target: ${TARGET_HOURS}hr | Theme: ${THEME}" | tee -a "$LOG"
echo "Output: ${OUTPUT_FILE}" | tee -a "$LOG"

# ── Build playlist (repeat until target duration) ────────────
> "$TEMP_PLAYLIST"
> "$TIMESTAMP_FILE"

TOTAL_DURATION=0
TRACK_NUM=0

# Get track list
if [ ${#SELECTED_TRACKS[@]} -gt 0 ]; then
    TRACKS=("${SELECTED_TRACKS[@]}")
else
    mapfile -t TRACKS < <(ls "$MUSIC_DIR"/*.wav | sort)
fi

echo "" | tee -a "$LOG"
echo "Tracks: ${#TRACKS[@]}" | tee -a "$LOG"

# Loop tracks until we hit target duration
while (( $(echo "$TOTAL_DURATION < $TARGET_SECONDS" | bc -l) )); do
    for TRACK in "${TRACKS[@]}"; do
        if [ ${#SELECTED_TRACKS[@]} -gt 0 ]; then
            TRACK_PATH="$MUSIC_DIR/${TRACK}.wav"
        else
            TRACK_PATH="$TRACK"
        fi

        if [ ! -f "$TRACK_PATH" ]; then
            echo "  [SKIP] Not found: $TRACK_PATH" | tee -a "$LOG"
            continue
        fi

        DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$TRACK_PATH" 2>/dev/null)
        DURATION=${DURATION%.*}  # truncate to int

        TRACK_NUM=$((TRACK_NUM + 1))
        TRACK_NAME=$(basename "$TRACK_PATH" .wav)

        # Generate timestamp
        HOURS=$((${TOTAL_DURATION%.*} / 3600))
        MINS=$(( (${TOTAL_DURATION%.*} % 3600) / 60 ))
        SECS=$((${TOTAL_DURATION%.*} % 60))
        TSTAMP=$(printf "%02d:%02d:%02d" $HOURS $MINS $SECS)

        echo "$TSTAMP $TRACK_NAME" >> "$TIMESTAMP_FILE"
        echo "file '$TRACK_PATH'" >> "$TEMP_PLAYLIST"

        TOTAL_DURATION=$(echo "$TOTAL_DURATION + $DURATION" | bc)

        if (( $(echo "$TOTAL_DURATION >= $TARGET_SECONDS" | bc -l) )); then
            break 2
        fi
    done
done

FINAL_HOURS=$((${TOTAL_DURATION%.*} / 3600))
FINAL_MINS=$(( (${TOTAL_DURATION%.*} % 3600) / 60 ))
echo "" | tee -a "$LOG"
echo "Total duration: ${FINAL_HOURS}h ${FINAL_MINS}m (${TRACK_NUM} tracks)" | tee -a "$LOG"

# ── Encode video ─────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "Encoding video..." | tee -a "$LOG"

ffmpeg -y \
    -loop 1 -framerate 1 -i "$VISUAL" \
    -f concat -safe 0 -i "$TEMP_PLAYLIST" \
    -c:v libx264 -preset ultrafast -tune stillimage \
    -r 1 -b:v 1000k -maxrate 1000k -bufsize 1000k \
    -vf "scale=1920:1080" \
    -c:a aac -b:a 192k -ar 44100 \
    -shortest \
    "$OUTPUT_FILE" \
    2>> "$LOG"

# ── Cleanup ──────────────────────────────────────────────────
rm -f "$TEMP_PLAYLIST"

# ── Output ───────────────────────────────────────────────────
FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
echo "" | tee -a "$LOG"
echo "=== Done ===" | tee -a "$LOG"
echo "Video:      $OUTPUT_FILE ($FILE_SIZE)" | tee -a "$LOG"
echo "Timestamps: $TIMESTAMP_FILE" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "--- Timestamps (copy to YouTube description) ---"
cat "$TIMESTAMP_FILE"
