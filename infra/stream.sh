#!/bin/bash
STREAM_KEY="YOUR_YOUTUBE_STREAM_KEY"
RTMP_URL="rtmp://a.rtmp.youtube.com/live2/$STREAM_KEY"
VIDEO="/opt/CONTENT-PIPELINE/loop_video_v4.mp4"
LOG="/opt/CONTENT-PIPELINE/logs/stream.log"

echo "CONTENT-PIPELINE Stream Starting: $(date)" >> $LOG

ffmpeg \
  -re \
  -stream_loop -1 -i "$VIDEO" \
  -vf "format=yuv420p" \
  -c:v libx264 -preset ultrafast -tune stillimage \
  -x264-params "keyint=2:min-keyint=2:scenecut=0" \
  -b:v 500k -maxrate 500k -bufsize 500k \
  -c:a copy \
  -f flv "$RTMP_URL" \
  2>> $LOG
