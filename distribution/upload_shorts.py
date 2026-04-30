#!/usr/bin/env python3
"""
CONTENT-PIPELINE — YouTube Shorts Auto-Uploader
Usage:
    python3 upload_shorts.py --auth              # ครั้งแรก: authorize
    python3 upload_shorts.py --test              # ทดสอบ upload 1 clip (private)
    python3 upload_shorts.py                     # upload ตาม schedule.json
    python3 upload_shorts.py --clip "Deadline_Mode_A_clip.mp4"  # upload clip เดียว
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
BASE_DIR = Path(__file__).parent
CLIENT_SECRET = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCHEDULE_FILE = BASE_DIR / "schedule.json"
UPLOAD_LOG = BASE_DIR / "upload_log.json"
ICT = timezone(timedelta(hours=7))


def get_credentials():
    """Load or refresh OAuth credentials."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                print("❌ client_secret.json not found — ดู SETUP.md")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_console()
        TOKEN_FILE.write_text(creds.to_json())
        print("✅ Token saved")
    return creds


def load_log():
    """Load upload history."""
    if UPLOAD_LOG.exists():
        return json.loads(UPLOAD_LOG.read_text(encoding="utf-8"))
    return {}


def save_log(log):
    """Save upload history."""
    UPLOAD_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def upload_video(youtube, file_path, title, description, tags, privacy="public", publish_at=None):
    """Upload a single video to YouTube as Shorts."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "10",  # Music
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    if publish_at and privacy == "private":
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(str(file_path), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"⬆️  Uploading: {file_path.name}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"✅ Done: https://youtube.com/shorts/{video_id}")
    return video_id


def run_schedule(youtube):
    """Upload clips based on schedule.json."""
    if not SCHEDULE_FILE.exists():
        print("❌ schedule.json not found — สร้างก่อน")
        sys.exit(1)

    schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    log = load_log()
    now = datetime.now(ICT)
    uploaded = 0

    for entry in schedule["clips"]:
        clip_name = entry["file"]

        # skip ถ้า upload แล้ว
        if clip_name in log:
            continue

        # skip ถ้ายังไม่ถึงเวลา
        scheduled_time = datetime.fromisoformat(entry["schedule"]).replace(tzinfo=ICT)
        if now < scheduled_time:
            continue

        clip_path = Path(schedule["clips_dir"]) / clip_name
        if not clip_path.exists():
            print(f"⚠️  File not found: {clip_path}")
            continue

        video_id = upload_video(
            youtube,
            clip_path,
            title=entry["title"],
            description=entry["description"],
            tags=entry.get("tags", []),
            privacy=entry.get("privacy", "public"),
        )

        log[clip_name] = {
            "video_id": video_id,
            "uploaded_at": now.isoformat(),
            "title": entry["title"],
        }
        save_log(log)
        uploaded += 1

        # YouTube API quota: wait between uploads
        time.sleep(5)

    print(f"\n📊 Uploaded {uploaded} clip(s) | Total: {len(log)}/{len(schedule['clips'])}")


def upload_single(youtube, clip_path):
    """Upload a single clip with default metadata."""
    name = clip_path.stem.replace("_clip", "").replace("_", " ")
    title = f"{name} — AI Beat 🎵 #shorts #content #hiphop"
    description = (
        f"{name}\nContent AI beat by Content Pipeline.\n\n"
        "#CONTENT-PIPELINE #content #hiphop #aimusic #shorts"
    )
    upload_video(youtube, clip_path, title, description, tags=["content", "shorts", "aimusic", "CONTENT-PIPELINE"])


def main():
    parser = argparse.ArgumentParser(description="CONTENT-PIPELINE YouTube Shorts Uploader")
    parser.add_argument("--auth", action="store_true", help="Authorize only")
    parser.add_argument("--test", action="store_true", help="Test upload 1 clip (private)")
    parser.add_argument("--clip", type=str, help="Upload a single clip file")
    args = parser.parse_args()

    creds = get_credentials()

    if args.auth:
        print("✅ Authorization complete")
        return

    youtube = build("youtube", "v3", credentials=creds)

    if args.test:
        schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        first = schedule["clips"][0]
        clip_path = Path(schedule["clips_dir"]) / first["file"]
        upload_video(youtube, clip_path, first["title"], first["description"],
                     first.get("tags", []), privacy="private")
    elif args.clip:
        upload_single(youtube, Path(args.clip))
    else:
        run_schedule(youtube)


if __name__ == "__main__":
    main()
