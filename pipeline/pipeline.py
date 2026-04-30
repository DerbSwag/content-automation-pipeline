#!/usr/bin/env python3
"""
CONTENT-PIPELINE — One-Command Pipeline
เพิ่มเพลงใหม่เข้าระบบทั้งหมดด้วย command เดียว

Usage:
    python3 pipeline.py --songs "Rooftop Rain.wav" "Tokyo Sunset.wav"
    python3 pipeline.py --songs-dir ./new_songs/
    python3 pipeline.py --songs "Rooftop Rain.wav" --dry-run
    python3 pipeline.py --songs "Rooftop Rain.wav" --skip-upload

Requirements:
    pip install Pillow paramiko
    (paramiko ใช้สำหรับ SSH ไป VPS — ถ้าไม่มีจะ fallback เป็น scp command)
"""

import argparse
import json
import subprocess
import sys
import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
ICT = timezone(timedelta(hours=7))

# Import sibling tools
sys.path.insert(0, str(BASE_DIR.parent / "cover-art-gen"))
sys.path.insert(0, str(BASE_DIR.parent / "meta-gen"))


def load_config():
    if not CONFIG_FILE.exists():
        print("[ERROR] config.json not found. Copy config.example.json and edit it.")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def log(step, msg):
    print(f"[{step}] {msg}")


def step_1_generate_cover_art(songs, config, dry_run=False):
    """Generate cover art for each song."""
    log("1/7", "Generating cover art...")
    cover_script = BASE_DIR.parent / "cover-art-gen" / "cover_art_gen.py"
    output_dir = Path(config.get("cover_output", str(BASE_DIR / "output" / "covers")))

    for song in songs:
        name = Path(song).stem
        cmd = [sys.executable, str(cover_script), "--song", name, "--output", str(output_dir)]
        if dry_run:
            log("1/7", f"  [DRY-RUN] Would generate cover for: {name}")
        else:
            subprocess.run(cmd, check=True)
    return output_dir


def step_2_generate_metadata(songs, config, dry_run=False):
    """Generate title/description/tags for all platforms."""
    log("2/7", "Generating metadata...")
    meta_script = BASE_DIR.parent / "meta-gen" / "meta_gen.py"
    output_file = BASE_DIR / "output" / "metadata.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    song_names = [Path(s).stem for s in songs]
    songs_file = BASE_DIR / "output" / "_temp_songs.txt"
    songs_file.write_text("\n".join(song_names), encoding="utf-8")

    cmd = [sys.executable, str(meta_script), "--batch", str(songs_file),
           "--format", "json", "--output", str(output_file)]

    if dry_run:
        log("2/7", f"  [DRY-RUN] Would generate metadata for: {', '.join(song_names)}")
    else:
        subprocess.run(cmd, check=True, capture_output=True)
        log("2/7", f"  Saved to {output_file}")

    songs_file.unlink(missing_ok=True)
    return output_file


def step_3_upload_to_vps(songs, config, dry_run=False):
    """Upload WAV files to VPS via SCP."""
    log("3/7", "Uploading songs to VPS...")
    vps = config["vps"]
    host = vps["host"]
    user = vps["user"]
    key = vps.get("key_file", "")
    music_dir = vps["music_dir"]

    for song in songs:
        song_path = Path(song)
        if not song_path.exists():
            # Try looking in songs_dir
            songs_dir = config.get("songs_dir", ".")
            song_path = Path(songs_dir) / song
        if not song_path.exists():
            log("3/7", f"  [SKIP] File not found: {song}")
            continue

        key_arg = f'-i "{key}"' if key else ""
        cmd = f'scp {key_arg} "{song_path}" {user}@{host}:"{music_dir}/"'

        if dry_run:
            log("3/7", f"  [DRY-RUN] {cmd}")
        else:
            log("3/7", f"  Uploading: {song_path.name}")
            subprocess.run(cmd, shell=True, check=True)


def ssh_cmd(config, command, dry_run=False):
    """Run command on VPS via SSH."""
    vps = config["vps"]
    key_arg = f'-i "{vps.get("key_file", "")}"' if vps.get("key_file") else ""
    cmd = f'ssh {key_arg} {vps["user"]}@{vps["host"]} "{command}"'
    if dry_run:
        log("SSH", f"  [DRY-RUN] {command}")
        return ""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout


def step_4_update_playlist(config, dry_run=False):
    """Rebuild playlist.txt on VPS."""
    log("4/7", "Updating playlist on VPS...")
    music_dir = config["vps"]["music_dir"]
    cmd = (
        f"cd {music_dir} && "
        f"ls *.wav | sort | while read f; do echo \"file '$PWD/$f'\"; done "
        f"> ~/CONTENT-PIPELINE/playlist.txt && "
        f"echo \"Playlist updated: $(wc -l < ~/CONTENT-PIPELINE/playlist.txt) tracks\""
    )
    output = ssh_cmd(config, cmd, dry_run)
    if output:
        log("4/7", f"  {output.strip()}")


def step_5_reencode_video(config, dry_run=False):
    """Re-encode loop video on VPS."""
    log("5/7", "Re-encoding loop video (this takes a few minutes)...")
    cmd = (
        "screen -S CONTENT-PIPELINE -X quit 2>/dev/null; sleep 2; "
        "ffmpeg -loop 1 -framerate 1 -i ~/CONTENT-PIPELINE/visuals/background.jpg "
        "-f concat -safe 0 -i ~/CONTENT-PIPELINE/playlist.txt "
        "-c:v libx264 -preset ultrafast -tune stillimage "
        "-r 1 -b:v 1000k -maxrate 1000k -bufsize 1000k "
        "-vf 'scale=1280:720' "
        "-c:a aac -b:a 128k -ar 44100 "
        "-shortest -y ~/CONTENT-PIPELINE/loop_video_v3.mp4 && "
        "sed -i 's/loop_video_v[0-9]*.mp4/loop_video_v3.mp4/' ~/CONTENT-PIPELINE/scripts/stream.sh && "
        "echo 'Re-encode done'"
    )
    output = ssh_cmd(config, cmd, dry_run)
    if output:
        log("5/7", f"  {output.strip()}")


def step_6_restart_stream(config, dry_run=False):
    """Restart the 24/7 stream."""
    log("6/7", "Restarting stream...")
    cmd = (
        "screen -S CONTENT-PIPELINE -X quit 2>/dev/null; screen -wipe 2>/dev/null; sleep 2; "
        "screen -dmS CONTENT-PIPELINE bash ~/CONTENT-PIPELINE/scripts/stream.sh && "
        "sleep 3 && screen -list"
    )
    output = ssh_cmd(config, cmd, dry_run)
    if output:
        log("6/7", f"  {output.strip()}")


def step_7_update_schedules(songs, config, metadata_file, dry_run=False):
    """Add new clips to YouTube/TikTok upload schedules."""
    log("7/7", "Updating upload schedules...")

    if not metadata_file or not Path(metadata_file).exists():
        log("7/7", "  [SKIP] No metadata file")
        return

    metadata = json.loads(Path(metadata_file).read_text(encoding="utf-8"))
    now = datetime.now(ICT)

    # YouTube Shorts schedule
    yt_schedule_file = BASE_DIR.parent / "youtube-shorts-uploader" / "schedule.json"
    if yt_schedule_file.exists():
        yt_schedule = json.loads(yt_schedule_file.read_text(encoding="utf-8"))
    else:
        yt_schedule = {"clips_dir": "/opt/CONTENT-PIPELINE/clips", "clips": []}

    # TikTok schedule
    tt_schedule_file = BASE_DIR.parent / "tiktok-uploader" / "schedule.json"
    if tt_schedule_file.exists():
        tt_schedule = json.loads(tt_schedule_file.read_text(encoding="utf-8"))
    else:
        tt_schedule = {"clips_dir": "/opt/CONTENT-PIPELINE/clips", "clips": []}

    for i, meta in enumerate(metadata):
        song_name = meta["song"]
        safe_name = song_name.replace(" ", "_").replace("&", "and")
        clip_file = f"{safe_name}_A_clip.mp4"

        # Schedule: stagger 2.5 hours apart, starting tomorrow 18:00
        schedule_time = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        schedule_time += timedelta(hours=i * 2.5)

        yt_data = meta.get("youtube_shorts", {})
        tt_data = meta.get("tiktok", {})

        yt_schedule["clips"].append({
            "file": clip_file,
            "title": yt_data.get("title", f"{song_name} #shorts #content"),
            "description": yt_data.get("description", ""),
            "tags": yt_data.get("tags", []),
            "schedule": schedule_time.strftime("%Y-%m-%dT%H:%M"),
            "privacy": "public",
        })

        tt_time = schedule_time - timedelta(minutes=30)
        tt_schedule["clips"].append({
            "file": clip_file,
            "title": tt_data.get("title", f"{song_name} #content #shorts"),
            "schedule": tt_time.strftime("%Y-%m-%dT%H:%M"),
        })

    if dry_run:
        log("7/7", f"  [DRY-RUN] Would add {len(metadata)} clips to schedules")
    else:
        yt_schedule_file.parent.mkdir(parents=True, exist_ok=True)
        yt_schedule_file.write_text(json.dumps(yt_schedule, indent=2, ensure_ascii=False), encoding="utf-8")
        tt_schedule_file.parent.mkdir(parents=True, exist_ok=True)
        tt_schedule_file.write_text(json.dumps(tt_schedule, indent=2, ensure_ascii=False), encoding="utf-8")
        log("7/7", f"  Added {len(metadata)} clips to YouTube + TikTok schedules")


def main():
    parser = argparse.ArgumentParser(description="CONTENT-PIPELINE One-Command Pipeline")
    parser.add_argument("--songs", nargs="+", help="WAV file names to add")
    parser.add_argument("--songs-dir", type=str, help="Directory containing WAV files")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--skip-upload", action="store_true", help="Skip VPS upload + re-encode")
    parser.add_argument("--skip-stream", action="store_true", help="Skip stream restart")
    args = parser.parse_args()

    config = load_config()

    # Collect songs
    songs = []
    if args.songs:
        songs = args.songs
    elif args.songs_dir:
        songs = [str(p) for p in Path(args.songs_dir).glob("*.wav")]
    else:
        parser.print_help()
        return

    if not songs:
        print("[ERROR] No songs found")
        return

    print("=" * 60)
    print(f"  CONTENT-PIPELINE Pipeline — {len(songs)} song(s)")
    print(f"  {'[DRY-RUN MODE]' if args.dry_run else ''}")
    print("=" * 60)
    for s in songs:
        print(f"  + {Path(s).stem}")
    print()

    # Run pipeline
    cover_dir = step_1_generate_cover_art(songs, config, args.dry_run)
    meta_file = step_2_generate_metadata(songs, config, args.dry_run)

    if not args.skip_upload:
        step_3_upload_to_vps(songs, config, args.dry_run)
        step_4_update_playlist(config, args.dry_run)
        step_5_reencode_video(config, args.dry_run)

    if not args.skip_stream and not args.skip_upload:
        step_6_restart_stream(config, args.dry_run)

    step_7_update_schedules(songs, config, meta_file, args.dry_run)

    print()
    print("=" * 60)
    print("  Pipeline complete!")
    print(f"  Covers:   {cover_dir}")
    print(f"  Metadata: {meta_file}")
    if not args.skip_upload:
        print("  VPS:      Songs uploaded + playlist updated + stream restarted")
    print("  Schedule: YouTube + TikTok schedules updated")
    print("=" * 60)


if __name__ == "__main__":
    main()
