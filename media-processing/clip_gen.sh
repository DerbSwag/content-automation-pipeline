#!/bin/bash
# ============================================================
# CONTENT-PIPELINE — TikTok/Shorts/Reels Clip Generator v1.2
#
# Usage:
#   bash CONTENT-PIPELINE_clip_gen.sh --all
#   bash CONTENT-PIPELINE_clip_gen.sh --track "3AM Thoughts" --angle B
#   bash CONTENT-PIPELINE_clip_gen.sh --track "Rain on Glass" --angle A --start 5
#   bash CONTENT-PIPELINE_clip_gen.sh --track "Deadline Mode" --angle A --start 4
#
# Angles:
#   A = "AI Made This"  — hook text + waveform  (Deadline Mode, Espresso Shot, Tab Overload)
#   B = "Mood Sync"     — track name + mood text (3AM Thoughts, Closing Time, Midnight Loop)
#   C = "Sound Only"    — waveform + watermark   (Content/Ambient tracks ทั้งหมด)
# ============================================================

MUSIC_DIR="/opt/CONTENT-PIPELINE/music"
OUTPUT_DIR="/opt/CONTENT-PIPELINE/clips"
DURATION=30
ANGLE=""
MODE="all"
SPECIFIC_TRACK=""
MANUAL_START=""

VID_W=1080; VID_H=1920; WAVE_H=400; WAVE_Y=760
WAVE_COLOR="00FFB3"; BG_COLOR="0a0a0f"
FONT_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)       MODE="all" ;;
    --track)     MODE="single"; SPECIFIC_TRACK="$2"; shift ;;
    --angle)     ANGLE="${2^^}"; shift ;;
    --start)     MANUAL_START="$2"; shift ;;
    --duration)  DURATION="$2"; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

# Format: "start_sec|niche|angle_recommend"
declare -A TRACK_META=(
  ["2AM Focus"]="8|content|C"
  ["3AM Thoughts"]="0|sad|B"
  ["Analog Drift"]="5|synthwave|C"
  ["Bookstore Find"]="3|content|C"
  ["Closing Time"]="6|sad|B"
  ["Coffee & Rain_(1)"]="0|content|C"
  ["Deadline Mode"]="4|hiphop|A"
  ["Drift Off"]="2|ambient|C"
  ["Espresso Shot"]="5|hiphop|A"
  ["Flow State"]="7|content|C"
  ["Golden Hour"]="3|ambient|C"
  ["Late Night Code"]="10|content|C"
  ["Library Hours"]="4|content|C"
  ["Midnight Loop"]="6|content|B"
  ["Rain on Glass"]="0|ambient|C"
  ["Sunday Brew"]="5|content|C"
  ["Tab Overload"]="8|hiphop|A"
  ["Window Seat"]="3|content|C"
)

log()  { echo -e "\033[0;36m[CONTENT-PIPELINE]\033[0m $*"; }
ok()   { echo -e "\033[0;32m[  done  ]\033[0m $*"; }
warn() { echo -e "\033[0;33m[  warn  ]\033[0m $*"; }

mkdir -p "$OUTPUT_DIR"

make_clip() {
  local track_name="$1"
  local wav_file="${MUSIC_DIR}/${track_name}.wav"

  if [[ ! -f "$wav_file" ]]; then
    warn "ไม่พบไฟล์: $wav_file — ข้าม"
    return 0
  fi

  local meta="${TRACK_META[$track_name]:-"5|content|C"}"
  local default_start niche rec_angle
  IFS='|' read -r default_start niche rec_angle <<< "$meta"

  local start_sec="${MANUAL_START:-$default_start}"
  local use_angle="${ANGLE:-$rec_angle}"

  # ตรวจไม่ให้ clip เกิน total duration
  local total_dur
  total_dur=$(ffprobe -v quiet -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 "$wav_file" | cut -d. -f1)
  if (( start_sec + DURATION > total_dur )); then
    start_sec=$(( total_dur - DURATION ))
    [[ $start_sec -lt 0 ]] && start_sec=0
    warn "$track_name: ปรับ start → ${start_sec}s (total=${total_dur}s)"
  fi

  local safe_name
  safe_name=$(echo "$track_name" | tr ' ()&' '____')
  local out_file="${OUTPUT_DIR}/${safe_name}_${use_angle}_clip.mp4"

  # Escape track name สำหรับ drawtext (spaces → backslash-space)
  local track_esc="${track_name// /\\ }"

  log "[$use_angle] $track_name | start=${start_sec}s | niche=${niche}"

  case "$use_angle" in
    A)
      ffmpeg -y -loglevel error \
        -f lavfi -i "color=c=#${BG_COLOR}:s=${VID_W}x${VID_H}:r=30" \
        -ss "$start_sec" -t "$DURATION" -i "$wav_file" \
        -filter_complex \
          "[1:a]showwaves=s=${VID_W}x${WAVE_H}:mode=cline:colors=#${WAVE_COLOR}:scale=sqrt[waves];
           [0:v][waves]overlay=0:${WAVE_Y}[wv];
           [wv]drawtext=text=AI\ made\ this\ beat:fontcolor=#ffffff:fontsize=54:x=(w-text_w)/2:y=200:fontfile=${FONT_BOLD}[t1];
           [t1]drawtext=text=in\ 10\ seconds:fontcolor=#${WAVE_COLOR}:fontsize=42:x=(w-text_w)/2:y=270:fontfile=${FONT_REG}[t2];
           [t2]drawtext=text=@CONTENT-PIPELINEMusic:fontcolor=#444444:fontsize=30:x=(w-text_w)/2:y=h-100:fontfile=${FONT_REG}" \
        -c:v libx264 -preset veryfast -crf 23 \
        -c:a aac -b:a 192k \
        -t "$DURATION" -shortest -pix_fmt yuv420p "$out_file"
      ;;
    B)
      ffmpeg -y -loglevel error \
        -f lavfi -i "color=c=#${BG_COLOR}:s=${VID_W}x${VID_H}:r=30" \
        -ss "$start_sec" -t "$DURATION" -i "$wav_file" \
        -filter_complex \
          "[1:a]showwaves=s=${VID_W}x${WAVE_H}:mode=p2p:colors=#${WAVE_COLOR}:scale=lin[waves];
           [0:v][waves]overlay=0:${WAVE_Y}[wv];
           [wv]drawtext=text=when\ its\ 3am\ and\ you\ cant\ sleep:fontcolor=#888888:fontsize=36:x=(w-text_w)/2:y=220:fontfile=${FONT_REG}[t1];
           [t1]drawtext=text=${track_esc}:fontcolor=#${WAVE_COLOR}:fontsize=38:x=(w-text_w)/2:y=272:fontfile=${FONT_BOLD}[t2];
           [t2]drawtext=text=@CONTENT-PIPELINEMusic:fontcolor=#444444:fontsize=28:x=(w-text_w)/2:y=h-100:fontfile=${FONT_REG}" \
        -c:v libx264 -preset veryfast -crf 23 \
        -c:a aac -b:a 192k \
        -t "$DURATION" -shortest -pix_fmt yuv420p "$out_file"
      ;;
    C)
      ffmpeg -y -loglevel error \
        -f lavfi -i "color=c=#${BG_COLOR}:s=${VID_W}x${VID_H}:r=30" \
        -ss "$start_sec" -t "$DURATION" -i "$wav_file" \
        -filter_complex \
          "[1:a]showwaves=s=${VID_W}x${WAVE_H}:mode=cline:colors=#${WAVE_COLOR}:scale=sqrt[waves];
           [0:v][waves]overlay=0:${WAVE_Y}[wv];
           [wv]drawtext=text=@CONTENT-PIPELINEMusic:fontcolor=#444444:fontsize=28:x=(w-text_w)/2:y=h-100:fontfile=${FONT_REG}" \
        -c:v libx264 -preset veryfast -crf 23 \
        -c:a aac -b:a 192k \
        -t "$DURATION" -shortest -pix_fmt yuv420p "$out_file"
      ;;
    *)
      warn "Angle '${use_angle}' ไม่ถูกต้อง — ใช้ A, B หรือ C"
      return 1
      ;;
  esac

  local sz
  sz=$(du -h "$out_file" 2>/dev/null | cut -f1)
  ok "$track_name → $(basename "$out_file") [${sz}]"
}

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   CONTENT-PIPELINE — Clip Generator v1.2        ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

T0=$(date +%s); SUCCESS=0; FAILED=0

if [[ "$MODE" == "single" ]]; then
  make_clip "$SPECIFIC_TRACK" && (( SUCCESS++ )) || { (( FAILED++ )); true; }
else
  for t in "${!TRACK_META[@]}"; do
    make_clip "$t" && (( SUCCESS++ )) || { (( FAILED++ )); true; }
  done
fi

echo ""
printf "  clips: %d done | %d failed | %ds\n" "$SUCCESS" "$FAILED" "$(( $(date +%s) - T0 ))"
echo "  output: ${OUTPUT_DIR}/"
echo ""
