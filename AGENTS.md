# AGENTS.md

## Project Overview

End-to-end content automation pipeline — media processing (FFmpeg), AI metadata generation, multi-platform distribution (TikTok, YouTube Shorts), live streaming (RTMP), and health monitoring with LINE alerts.

## Tech Stack

- Python — pipeline orchestrator, cover art generation (Pillow), platform uploaders
- Bash — FFmpeg media processing, clip generation, health checks
- FFmpeg — audio/video processing, live streaming
- LINE Notify — alerting
- TikTok Content Posting API / YouTube Data API v3 — distribution
- GitHub Actions — CI

## Architecture

```
pipeline/           → Main orchestrator (pipeline.py) + AI metadata generator (meta_gen.py)
media-processing/   → FFmpeg scripts: cover art, longform mix, clip generation
distribution/       → Platform uploaders: autostream.py, upload_tiktok.py, upload_shorts.py
monitoring/         → health_check.sh (stream status → LINE alert)
infra/              → VPS provisioning (setup_vps.sh), stream launcher
config.example.json → Configuration template
```

## Conventions

- Python scripts in `pipeline/` and `distribution/`
- Bash scripts in `media-processing/`, `monitoring/`, and `infra/`
- Config via JSON file (`config.json`, gitignored)
- OAuth2 tokens managed per-platform (TikTok, YouTube)
- Cover art output: 3000x3000 (distribution) + 1280x720 (thumbnails)

## Commands

- Run pipeline: `python pipeline/pipeline.py`
- Start stream: `bash infra/stream.sh`
- Health check: `bash monitoring/health_check.sh`
- Provision VPS: `bash infra/setup_vps.sh`

## Security Rules

- API tokens and OAuth2 credentials in `config.json` (gitignored)
- Use `config.example.json` as template
- Never commit platform credentials or stream keys

## Important Notes

- Pipeline processes files in batch from input directory
- Autostream has auto-restart on failure
- Health check alerts via LINE Notify when stream goes down
- VPS setup installs Docker, FFmpeg, Python, and systemd service
