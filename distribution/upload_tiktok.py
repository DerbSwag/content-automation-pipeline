#!/usr/bin/env python3
"""
CONTENT-PIPELINE — TikTok Auto-Uploader (Content Posting API)
Usage:
    python3 upload_tiktok.py --auth                # ครั้งแรก: authorize
    python3 upload_tiktok.py --test                # ทดสอบ upload 1 clip
    python3 upload_tiktok.py                       # upload ตาม schedule.json
    python3 upload_tiktok.py --clip "Deadline_Mode_A_clip.mp4"
"""

import os
import sys
import json
import argparse
import time
import webbrowser
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
TOKEN_FILE = BASE_DIR / "tiktok_token.json"
SCHEDULE_FILE = BASE_DIR / "schedule.json"
UPLOAD_LOG = BASE_DIR / "upload_log.json"
ICT = timezone(timedelta(hours=7))

API_BASE = "https://open.tiktokapis.com/v2"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def load_config():
    """Load client_key and client_secret from config.json."""
    if not CONFIG_FILE.exists():
        print("❌ config.json not found — สร้างก่อน:")
        print('  {"client_key": "YOUR_KEY", "client_secret": "YOUR_SECRET"}')
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_token():
    """Load saved token."""
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    return None


def save_token(token_data):
    """Save token to file."""
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")


def authorize(config):
    """OAuth2 authorization flow."""
    params = {
        "client_key": config["client_key"],
        "scope": "video.upload,video.publish",
        "response_type": "code",
        "redirect_uri": "https://localhost:3000/callback",
    }
    url = f"{AUTH_URL}?{urlencode(params)}"
    print(f"🔗 เปิด URL นี้ใน browser:\n\n{url}\n")
    print("หลัง Allow → copy URL ที่ redirect มาทั้งหมด แล้ววางที่นี่:")
    redirect_url = input("> ").strip()

    parsed = urlparse(redirect_url)
    code = parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        print("❌ ไม่พบ code ใน URL")
        sys.exit(1)

    resp = requests.post(TOKEN_URL, json={
        "client_key": config["client_key"],
        "client_secret": config["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": "https://localhost:3000/callback",
    })
    token_data = resp.json()

    if "access_token" not in token_data:
        print(f"❌ Auth failed: {token_data}")
        sys.exit(1)

    token_data["obtained_at"] = datetime.now(ICT).isoformat()
    save_token(token_data)
    print("✅ Token saved")
    return token_data


def refresh_token(config, token_data):
    """Refresh expired token."""
    resp = requests.post(TOKEN_URL, json={
        "client_key": config["client_key"],
        "client_secret": config["client_secret"],
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"],
    })
    new_token = resp.json()

    if "access_token" not in new_token:
        print(f"❌ Refresh failed: {new_token} — run --auth again")
        sys.exit(1)

    new_token["obtained_at"] = datetime.now(ICT).isoformat()
    save_token(new_token)
    print("🔄 Token refreshed")
    return new_token


def get_access_token(config):
    """Get valid access token, refresh if needed."""
    token_data = load_token()
    if not token_data:
        print("❌ No token — run: python3 upload_tiktok.py --auth")
        sys.exit(1)

    obtained = datetime.fromisoformat(token_data["obtained_at"])
    expires_in = token_data.get("expires_in", 86400)
    if datetime.now(ICT) > obtained + timedelta(seconds=expires_in - 300):
        token_data = refresh_token(config, token_data)

    return token_data["access_token"]


def upload_video(access_token, file_path, title):
    """Upload video via TikTok Content Posting API (direct post)."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    file_size = file_path.stat().st_size

    # Step 1: Initialize upload
    init_resp = requests.post(
        f"{API_BASE}/post/publish/inbox/video/init/",
        headers=headers,
        json={
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            }
        },
    )
    init_data = init_resp.json()

    if "data" not in init_data or "upload_url" not in init_data["data"]:
        print(f"❌ Init failed: {init_data}")
        return None

    upload_url = init_data["data"]["upload_url"]
    publish_id = init_data["data"]["publish_id"]

    # Step 2: Upload video file
    print(f"⬆️  Uploading: {file_path.name} ({file_size / 1024 / 1024:.1f}MB)")
    with open(file_path, "rb") as f:
        upload_resp = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            },
            data=f,
        )

    if upload_resp.status_code not in (200, 201):
        print(f"❌ Upload failed: {upload_resp.status_code} {upload_resp.text}")
        return None

    # Step 3: Publish
    publish_resp = requests.post(
        f"{API_BASE}/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title": title,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": upload_url,
            },
        },
    )
    pub_data = publish_resp.json()

    if pub_data.get("error", {}).get("code") == "ok":
        print(f"✅ Published: {title}")
        return pub_data.get("data", {}).get("publish_id", publish_id)
    else:
        print(f"⚠️  Publish response: {pub_data}")
        return publish_id


def load_log():
    if UPLOAD_LOG.exists():
        return json.loads(UPLOAD_LOG.read_text(encoding="utf-8"))
    return {}


def save_log(log):
    UPLOAD_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def run_schedule(access_token):
    """Upload clips based on schedule.json."""
    if not SCHEDULE_FILE.exists():
        print("❌ schedule.json not found")
        sys.exit(1)

    schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    log = load_log()
    now = datetime.now(ICT)
    uploaded = 0

    for entry in schedule["clips"]:
        clip_name = entry["file"]

        if clip_name in log:
            continue

        scheduled_time = datetime.fromisoformat(entry["schedule"]).replace(tzinfo=ICT)
        if now < scheduled_time:
            continue

        clip_path = Path(schedule["clips_dir"]) / clip_name
        if not clip_path.exists():
            print(f"⚠️  File not found: {clip_path}")
            continue

        publish_id = upload_video(access_token, clip_path, entry["title"])

        log[clip_name] = {
            "publish_id": publish_id,
            "uploaded_at": now.isoformat(),
            "title": entry["title"],
        }
        save_log(log)
        uploaded += 1
        time.sleep(10)  # rate limit

    print(f"\n📊 Uploaded {uploaded} clip(s) | Total: {len(log)}/{len(schedule['clips'])}")


def main():
    parser = argparse.ArgumentParser(description="CONTENT-PIPELINE TikTok Uploader")
    parser.add_argument("--auth", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--clip", type=str)
    args = parser.parse_args()

    config = load_config()

    if args.auth:
        authorize(config)
        return

    access_token = get_access_token(config)

    if args.test:
        schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        first = schedule["clips"][0]
        clip_path = Path(schedule["clips_dir"]) / first["file"]
        upload_video(access_token, clip_path, first["title"] + " [TEST]")
    elif args.clip:
        p = Path(args.clip)
        name = p.stem.replace("_clip", "").replace("_", " ")
        upload_video(access_token, p, f"{name} — AI Beat 🎵 #content #shorts")
    else:
        run_schedule(access_token)


if __name__ == "__main__":
    main()
