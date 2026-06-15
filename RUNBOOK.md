# RUNBOOK — Content Automation Pipeline

> Proven procedures — วิธีทำงานที่เคยทำแล้วและจะทำอีก
> Updated: 2026-06-15

## Quick Reference

| Item | Value |
|------|-------|
| VM stream | `zoneloop-stream` GCP us-central1-c (ffmpeg 24/7) |
| Stream target | YouTube RTMP `rtmp://a.rtmp.youtube.com/live2` |
| Shorts uploader | `/home/natthawat_derb/zoneloop/uploader/` |
| TikTok uploader | CDP-based (Chromium), `tiktok_uploaded.json` state |
| Cron user | `dref_` (ต้อง own token files) |
| YouTube channel | ZONE LOOP `UCB23KhbA3W4ok3eTP--91WA` (Brand Account ใต้ `rickydref17@gmail.com`) |
| Alert | LINE Notify → ZONELOOP Alert `@325uhaig` |
| Config | `config.json` (gitignored) — copy from `config.example.json` |

---

## 1. Restart YouTube Stream (ffmpeg zombie)

**When:** YouTube channel shows offline แต่ ffmpeg ยังรันอยู่บน VM (TX bytes flowing, broadcast stale)

**Steps:**
```bash
# SSH เข้า VM
gcloud compute ssh zoneloop-stream

# 1. Kill ffmpeg (ต้อง sudo เพราะ owner อาจเป็น natthawat_derb)
sudo pkill -9 -x ffmpeg

# 2. Start ใหม่เป็น natthawat_derb
sudo -u natthawat_derb bash -c 'nohup bash ~/zoneloop/stream.sh >> ~/zoneloop/logs/stream.log 2>&1 &'

# 3. Verify
sleep 5
pgrep -c ffmpeg          # ต้อง = 1
ss -tn dst :1935         # ESTABLISHED with new source port
```

**⚠️ Gotchas:**
- อย่า `gcloud compute instances reset` ถ้า network OK — เช็ค TX bytes ก่อน
- `restart_stream.sh` เก่าให้ false positive ถ้า kill ไม่มีสิทธิ์ — ใช้ v3 + watchdog service
- Watchdog แบบ `pgrep-only` มองไม่เห็น zombie → v3 เช็ค write-stall (`/proc/PID/io`)

**Ref:** zoneloop `INCIDENTS/2026-06-13_youtube_stream_zombie_ffmpeg.md`

---

## 2. Re-auth YouTube OAuth (Shorts uploader)

**When:** Upload log แสดง `HttpError 401: youtubeSignupRequired` หรือ `PermissionError token.json`

**Steps:**
```bash
# 1. บนเครื่องที่มี browser (ไม่ใช่ VM)
python3 auth_flow.py  # ใช้ client_secret.json เดิม

# 2. Login rickydref17@gmail.com → เลือก Brand Account "ZONE LOOP"

# 3. Verify ก่อน save
python3 -c "from googleapiclient.discovery import build; ...channels.list(mine=True)"
# ต้องได้ UCB23KhbA3W4ok3eTP--91WA

# 4. Upload token ไป VM
scp token.json zoneloop-stream:/home/natthawat_derb/zoneloop/uploader/
gcloud compute ssh zoneloop-stream -- 'chmod 644 /home/natthawat_derb/zoneloop/uploader/token.json && sudo chown dref_:dref_ /home/natthawat_derb/zoneloop/uploader/token.json'

# 5. Test
gcloud compute ssh zoneloop-stream -- 'python3 upload_shorts.py --limit 1'
```

**⚠️ Gotchas:**
- อย่า login ด้วย `zoneloopmusic@gmail.com` — ไม่มี channel
- cron user (`dref_`) ต้องเป็น owner ของ `token.json`
- Windows: ต้อง `PYTHONIOENCODING=utf-8` ไม่งั้น emoji crash (cp874)
- Quota: 1,600 units/clip, 10,000/day → max ~6 clips/day

**Ref:** zoneloop `INCIDENTS/2026-06-04_youtube_shorts_upload_stopped.md`

---

## 3. Fix TikTok Schedule Collision

**When:** TikTok clips scheduled ซ้ำเวลาเดียวกัน หรือ `tiktok_uploaded.json` มี entries ผิด

**Steps:**
```bash
# 1. ตรวจสอบ state file
cat tiktok_uploaded.json | python3 -m json.tool | grep schedule_time

# 2. ถ้ามี collision — ลบ scheduled posts บน TikTok
python3 delete_scheduled.py --dry-run  # review ก่อน
python3 delete_scheduled.py            # ลบจริง

# 3. Re-schedule ด้วย fixed slot computation
python3 upload_tiktok.py --schedule --limit 15
```

**⚠️ Gotchas:**
- ห้าม cancel batch run แล้วคิดว่ามันหยุด — process อาจยังรันอยู่ background
- `slot_for_index()` ใช้ global index (ไม่ใช่ per-run position)
- หลัง 15 uploads ติดกัน TikTok อาจ throttle → รอแล้ว retry

**Ref:** zoneloop `INCIDENTS/2026-06-03_tiktok_schedule_collision.md`

---

## 4. Stream Health Check

**When:** Routine — ทุกวันหรือเมื่อได้ LINE alert

```bash
# เช็คว่า ffmpeg ยังส่ง data
gcloud compute ssh zoneloop-stream -- '
  PID=$(pgrep -x ffmpeg)
  if [ -z "$PID" ]; then echo "NO FFMPEG"; exit 1; fi
  B1=$(awk "/write_bytes/{print \$2}" /proc/$PID/io)
  sleep 3
  B2=$(awk "/write_bytes/{print \$2}" /proc/$PID/io)
  DELTA=$((B2 - B1))
  echo "PID=$PID write_delta=${DELTA}B/3s"
  [ $DELTA -gt 0 ] && echo "OK: streaming" || echo "STALL: zombie detected"
'
```

---

## 5. VPS Provisioning (new/replacement)

**When:** ต้อง setup VM ใหม่

```bash
scp infra/setup_vps.sh user@new-vm:~/
ssh user@new-vm 'bash setup_vps.sh'
# Installs: Docker, FFmpeg, Python3, pip, systemd service
```

---

## Secrets & Security

| Secret | Location | Rotate how |
|--------|----------|-----------|
| YouTube OAuth token | VM `uploader/token.json` | Re-auth flow (procedure #2) |
| YouTube client_secret | Local machine only | Google Cloud Console → OAuth |
| TikTok OAuth | CDP session cookie | Re-login in Chromium |
| LINE Notify token | `config.json` | LINE Notify settings page |
| Stream key | `config.json` | YouTube Studio → Stream |

- **ห้าม commit:** `config.json`, `token.json`, `client_secret.json`
- Scan `git diff --cached` ก่อน commit ทุกครั้ง

---

## Related Docs

- `INCIDENTS.md` — บันทึกปัญหาที่เกิด
- `README.md` — ภาพรวม architecture & modules
- `monitoring/health_check.sh` — automated health check script
