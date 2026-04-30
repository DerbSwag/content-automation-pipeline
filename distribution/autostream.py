#!/usr/bin/env python3
"""
Content YouTube Auto-Stream Script
Stack: Python + FFmpeg + RTMP
Target: Oracle Cloud Free VPS (Ubuntu 22.04)
Author: AI Music Monetization System

Usage:
    python3 content_autostream.py --key YOUR_YOUTUBE_STREAM_KEY
    python3 content_autostream.py --key YOUR_KEY --visual bg_video.mp4 --music_dir ./music
"""

import os
import sys
import glob
import time
import random
import logging
import argparse
import subprocess
import signal
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG (แก้ตรงนี้)
# ─────────────────────────────────────────────
DEFAULT_CONFIG = {
    # YouTube RTMP endpoint
    "rtmp_url": "rtmp://a.rtmp.youtube.com/live2",

    # Path ไฟล์เพลง (WAV/MP3 จาก AudioSource)
    "music_dir": "./music",

    # Path visual loop (MP4 ไม่มีเสียง, loop ตลอด)
    "visual_path": "./visual/loop.mp4",

    # Output resolution (1920x1080 หรือ 1280x720)
    "resolution": "1280x720",

    # Video bitrate (2500k = 1080p, 1500k = 720p)
    "video_bitrate": "1500k",

    # Audio bitrate
    "audio_bitrate": "128k",

    # Framerate
    "fps": 25,

    # สลับ session เพลงทุก N วินาที (ป้องกัน Reused Content flag)
    # 7200 = 2 ชม., 3600 = 1 ชม.
    "session_duration": 7200,

    # จำนวน session ต่อรอบก่อน restart process
    "sessions_per_cycle": 12,

    # Text overlay (ชื่อช่อง / ข้อความ)
    "overlay_text": "content beats • study & relax",
    "overlay_font_size": 18,
    "overlay_color": "white@0.4",

    # Log file
    "log_file": "./stream.log",
}


# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
def setup_logging(log_file: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("content_stream")


# ─────────────────────────────────────────────
# MUSIC PLAYLIST BUILDER
# ─────────────────────────────────────────────
def build_playlist(music_dir: str, concat_file: str, session_num: int) -> int:
    """
    สร้าง FFmpeg concat list จากเพลงใน music_dir
    shuffle ทุก session เพื่อความ unique
    Return: จำนวนเพลงที่ใส่
    """
    music_dir = Path(music_dir)
    tracks = (
        list(music_dir.glob("*.mp3"))
        + list(music_dir.glob("*.wav"))
        + list(music_dir.glob("*.flac"))
        + list(music_dir.glob("*.ogg"))
    )

    if not tracks:
        raise FileNotFoundError(f"ไม่พบไฟล์เพลงใน {music_dir}")

    # Shuffle ด้วย seed ที่ต่างกันทุก session (ป้องกัน pattern ซ้ำ)
    random.seed(session_num * 31337 + int(time.time() % 10000))
    shuffled = random.sample(tracks, len(tracks))

    with open(concat_file, "w") as f:
        for track in shuffled:
            # ffconcat format
            f.write(f"file '{track.resolve()}'\n")

    return len(shuffled)


# ─────────────────────────────────────────────
# FFMPEG COMMAND BUILDER
# ─────────────────────────────────────────────
def build_ffmpeg_cmd(cfg: dict, concat_file: str, stream_key: str, session_num: int) -> list:
    """
    สร้าง FFmpeg command สำหรับ stream ขึ้น YouTube
    
    Architecture:
    - Video: loop MP4 visual (ไม่มีเสียง)
    - Audio: concat playlist เพลง
    - Overlay: text timestamp + channel name (dynamic ทุก session)
    - Output: RTMP → YouTube Live
    """
    rtmp_target = f"{cfg['rtmp_url']}/{stream_key}"
    w, h = cfg["resolution"].split("x")
    
    # Dynamic text overlay (timestamp เปลี่ยนทุก session = unique content)
    session_label = datetime.now().strftime("session %d.%m.%Y %H:%M")
    overlay_text = f"{cfg['overlay_text']} • {session_label}"

    cmd = [
        "ffmpeg",
        "-loglevel", "warning",
        "-stats",
        "-re",  # realtime input

        # INPUT 1: Visual loop (วน loop ตลอด)
        "-stream_loop", "-1",
        "-i", cfg["visual_path"],

        # INPUT 2: Audio concat playlist
        "-f", "concat",
        "-safe", "0",
        "-stream_loop", "-1",  # วนกลับถ้าเพลงหมด
        "-i", concat_file,

        # MAP: video จาก input 0, audio จาก input 1
        "-map", "0:v",
        "-map", "1:a",

        # VIDEO FILTER: scale + text overlay
        "-vf", (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
            f"drawtext=text='{overlay_text}':"
            f"fontsize={cfg['overlay_font_size']}:"
            f"fontcolor={cfg['overlay_color']}:"
            f"x=20:y=H-th-20"
        ),

        # VIDEO ENCODE
        "-c:v", "libx264",
        "-preset", "veryfast",   # CPU usage ต่ำ (เหมาะ VPS)
        "-tune", "stillimage",   # optimize สำหรับภาพนิ่ง/loop
        "-b:v", cfg["video_bitrate"],
        "-maxrate", cfg["video_bitrate"],
        "-bufsize", "3000k",
        "-g", str(cfg["fps"] * 2),  # keyframe interval = 2s
        "-r", str(cfg["fps"]),

        # AUDIO ENCODE
        "-c:a", "aac",
        "-b:a", cfg["audio_bitrate"],
        "-ar", "44100",

        # OUTPUT FORMAT
        "-f", "flv",
        "-flvflags", "no_duration_filesize",

        # หยุดหลัง session_duration วินาที
        "-t", str(cfg["session_duration"]),

        rtmp_target,
    ]
    return cmd


# ─────────────────────────────────────────────
# STREAM SESSION
# ─────────────────────────────────────────────
def run_session(cfg: dict, stream_key: str, session_num: int, log: logging.Logger) -> bool:
    """
    Run 1 session ของ stream
    Return True ถ้าสำเร็จ, False ถ้า error
    """
    concat_file = f"/tmp/playlist_s{session_num}.txt"

    try:
        num_tracks = build_playlist(cfg["music_dir"], concat_file, session_num)
        log.info(f"[Session {session_num}] Playlist built: {num_tracks} tracks")
    except FileNotFoundError as e:
        log.error(str(e))
        return False

    cmd = build_ffmpeg_cmd(cfg, concat_file, stream_key, session_num)
    log.info(f"[Session {session_num}] Starting stream → YouTube Live")
    log.info(f"Duration: {cfg['session_duration']}s ({cfg['session_duration']//3600:.1f}h)")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Stream log output
        for line in proc.stdout:
            if "error" in line.lower() or "fatal" in line.lower():
                log.warning(f"FFmpeg: {line.strip()}")

        proc.wait()

        if proc.returncode == 0:
            log.info(f"[Session {session_num}] ✅ Completed cleanly")
            return True
        else:
            log.error(f"[Session {session_num}] ❌ FFmpeg exit code: {proc.returncode}")
            return False

    except KeyboardInterrupt:
        log.info("Stream interrupted by user")
        proc.terminate()
        sys.exit(0)
    except Exception as e:
        log.error(f"[Session {session_num}] Exception: {e}")
        return False
    finally:
        # Cleanup temp file
        if os.path.exists(concat_file):
            os.remove(concat_file)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────
def preflight_check(cfg: dict, log: logging.Logger) -> bool:
    """ตรวจสอบก่อน stream"""
    ok = True

    # Check FFmpeg
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if result.returncode != 0:
        log.error("❌ FFmpeg ไม่พบ — ติดตั้ง: sudo apt install ffmpeg")
        ok = False
    else:
        log.info("✅ FFmpeg found")

    # Check visual file
    if not os.path.exists(cfg["visual_path"]):
        log.error(f"❌ Visual file ไม่พบ: {cfg['visual_path']}")
        ok = False
    else:
        log.info(f"✅ Visual: {cfg['visual_path']}")

    # Check music dir
    music_dir = Path(cfg["music_dir"])
    if not music_dir.exists():
        log.error(f"❌ Music dir ไม่พบ: {music_dir}")
        ok = False
    else:
        count = len(list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav")))
        if count == 0:
            log.error(f"❌ ไม่มีเพลงใน {music_dir}")
            ok = False
        else:
            log.info(f"✅ Music: {count} tracks in {music_dir}")

    return ok


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Content YouTube Auto-Stream")
    parser.add_argument("--key", required=True, help="YouTube Stream Key")
    parser.add_argument("--visual", default=DEFAULT_CONFIG["visual_path"], help="Visual loop MP4")
    parser.add_argument("--music_dir", default=DEFAULT_CONFIG["music_dir"], help="Music directory")
    parser.add_argument("--resolution", default=DEFAULT_CONFIG["resolution"], help="1280x720 หรือ 1920x1080")
    parser.add_argument("--session_hours", type=float, default=DEFAULT_CONFIG["session_duration"] / 3600,
                        help="Session duration in hours (default: 2)")
    parser.add_argument("--overlay", default=DEFAULT_CONFIG["overlay_text"], help="Text overlay")
    args = parser.parse_args()

    # Build config
    cfg = DEFAULT_CONFIG.copy()
    cfg["visual_path"] = args.visual
    cfg["music_dir"] = args.music_dir
    cfg["resolution"] = args.resolution
    cfg["session_duration"] = int(args.session_hours * 3600)
    cfg["overlay_text"] = args.overlay

    log = setup_logging(cfg["log_file"])
    log.info("=" * 60)
    log.info("  Content Auto-Stream System")
    log.info(f"  Resolution: {cfg['resolution']} | Session: {args.session_hours}h")
    log.info("=" * 60)

    # Preflight
    if not preflight_check(cfg, log):
        log.error("Preflight failed — แก้ปัญหาด้านบนก่อน")
        sys.exit(1)

    # Stream loop
    session_num = 1
    consecutive_errors = 0
    MAX_ERRORS = 5

    while True:
        success = run_session(cfg, args.key, session_num, log)

        if success:
            consecutive_errors = 0
        else:
            consecutive_errors += 1
            log.warning(f"Error count: {consecutive_errors}/{MAX_ERRORS}")

            if consecutive_errors >= MAX_ERRORS:
                log.error("Too many consecutive errors — waiting 5 minutes before retry")
                time.sleep(300)
                consecutive_errors = 0

            # Short wait before retry
            wait = min(30 * consecutive_errors, 120)
            log.info(f"Retry in {wait}s...")
            time.sleep(wait)

        # ทุก N sessions: log summary
        if session_num % cfg["sessions_per_cycle"] == 0:
            log.info(f"📊 Cycle complete: {session_num} sessions done")

        session_num += 1


if __name__ == "__main__":
    main()
