#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  Content Auto-Stream: VPS Setup Script
#  Target: Oracle Cloud Free Tier (Ubuntu 22.04 / 24.04)
#  Run as: bash setup_vps.sh
# ─────────────────────────────────────────────────────────────────

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Content Stream VPS Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

STREAM_DIR="/opt/content-stream"
SERVICE_NAME="content-autostream"
SCRIPT_NAME="content_autostream.py"

# ─── 1. Update & Install dependencies ───
echo "[1/6] Installing dependencies..."
sudo apt-get update -q
sudo apt-get install -y -q \
    ffmpeg \
    python3 \
    python3-pip \
    python3-venv \
    screen \
    htop \
    curl

echo "  ✅ ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
echo "  ✅ python: $(python3 --version)"

# ─── 2. Create project directory ───
echo "[2/6] Creating project structure..."
sudo mkdir -p "$STREAM_DIR"
sudo mkdir -p "$STREAM_DIR/music"
sudo mkdir -p "$STREAM_DIR/visual"
sudo mkdir -p "$STREAM_DIR/logs"
sudo chown -R "$USER:$USER" "$STREAM_DIR"

echo "  ✅ Created: $STREAM_DIR"
echo "  📂 Structure:"
echo "     $STREAM_DIR/"
echo "     ├── music/         ← ใส่ไฟล์เพลง .mp3 / .wav จาก AudioSource ที่นี่"
echo "     ├── visual/        ← ใส่ loop.mp4 ที่นี่"
echo "     ├── logs/          ← log files"
echo "     └── content_autostream.py"

# ─── 3. Copy script ───
echo "[3/6] Copying script..."
cp "$SCRIPT_NAME" "$STREAM_DIR/"
chmod +x "$STREAM_DIR/$SCRIPT_NAME"

# Patch log path ใน script
sed -i "s|./stream.log|$STREAM_DIR/logs/stream.log|g" "$STREAM_DIR/$SCRIPT_NAME"
sed -i "s|./music|$STREAM_DIR/music|g" "$STREAM_DIR/$SCRIPT_NAME"
sed -i "s|./visual/loop.mp4|$STREAM_DIR/visual/loop.mp4|g" "$STREAM_DIR/$SCRIPT_NAME"

echo "  ✅ Script installed"

# ─── 4. Prompt for Stream Key ───
echo ""
echo "[4/6] YouTube Stream Key Setup"
echo "  ไปที่ YouTube Studio → Go Live → Stream Key → Copy"
echo ""
read -rp "  ใส่ Stream Key: " YT_STREAM_KEY

if [ -z "$YT_STREAM_KEY" ]; then
    echo "  ⚠️  ยังไม่ใส่ key — ข้ามก่อน แก้ทีหลังใน service file"
    YT_STREAM_KEY="YOUR_STREAM_KEY_HERE"
fi

# ─── 5. Create systemd service ───
echo "[5/6] Creating systemd service..."

sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=Content YouTube Auto-Stream
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$STREAM_DIR

# ─── แก้ค่าตรงนี้ถ้าต้องการ ───
ExecStart=/usr/bin/python3 $STREAM_DIR/$SCRIPT_NAME \\
    --key $YT_STREAM_KEY \\
    --visual $STREAM_DIR/visual/loop.mp4 \\
    --music_dir $STREAM_DIR/music \\
    --session_hours 2 \\
    --overlay "content beats • study & relax"

# Restart policy
Restart=always
RestartSec=60

# Logs
StandardOutput=append:$STREAM_DIR/logs/stdout.log
StandardError=append:$STREAM_DIR/logs/stderr.log

# Resource limits (Oracle Free Tier)
CPUQuota=80%
MemoryMax=1G

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "  ✅ Service created: $SERVICE_NAME"

# ─── 6. Logrotate ───
echo "[6/6] Setting up log rotation..."
sudo tee "/etc/logrotate.d/content-stream" > /dev/null <<EOF
$STREAM_DIR/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  📋 NEXT STEPS:"
echo ""
echo "  1. ใส่เพลง (.mp3/.wav) ใน:"
echo "     $STREAM_DIR/music/"
echo ""
echo "  2. ใส่ visual loop ที่:"
echo "     $STREAM_DIR/visual/loop.mp4"
echo "     (ดูวิธีทำ visual ใน README)"
echo ""
echo "  3. Start stream:"
echo "     sudo systemctl start $SERVICE_NAME"
echo ""
echo "  4. ดู status:"
echo "     sudo systemctl status $SERVICE_NAME"
echo "     tail -f $STREAM_DIR/logs/stream.log"
echo ""
echo "  5. หยุด stream:"
echo "     sudo systemctl stop $SERVICE_NAME"
echo ""
echo "  ⚙️  แก้ Stream Key:"
echo "     sudo nano /etc/systemd/system/${SERVICE_NAME}.service"
echo "     sudo systemctl daemon-reload && sudo systemctl restart $SERVICE_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
