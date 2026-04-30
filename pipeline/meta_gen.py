#!/usr/bin/env python3
"""
CONTENT-PIPELINE — Auto Title/Description Generator
สร้าง title, description, tags สำหรับทุก platform จากชื่อเพลง

Usage:
    python3 meta_gen.py --song "Rooftop Rain"
    python3 meta_gen.py --batch songs.txt
    python3 meta_gen.py --batch songs.txt --format json
    python3 meta_gen.py --song "Rooftop Rain" --platform youtube-shorts
"""

import argparse
import json
import random
import sys
import io
from pathlib import Path

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"

# ── Mood/Hook templates ──────────────────────────────────────
HOOKS = {
    "rain": [
        "Rain on the window. Nowhere to be.",
        "Let the rain wash everything away.",
        "Rainy nights hit different with this beat.",
    ],
    "anime": [
        "Anime vibes for late night study sessions.",
        "Like walking through a Ghibli scene.",
        "Cherry blossoms and chill beats.",
    ],
    "city": [
        "City lights. Empty roads. Just you and the beat.",
        "Neon reflections on wet streets.",
        "Late night drive energy.",
    ],
    "night": [
        "When the world sleeps, the beat plays on.",
        "3AM thoughts need 3AM beats.",
        "The night is yours. So is this beat.",
    ],
    "cozy": [
        "Warm vibes for slow mornings.",
        "Like a warm cup on a cold day.",
        "Cozy beats for quiet moments.",
    ],
    "winter": [
        "Snow falling. Fire crackling. Beat playing.",
        "Winter nights need warm beats.",
        "Cozy winter vibes to melt into.",
    ],
    "autumn": [
        "Falling leaves and falling into the beat.",
        "Autumn afternoons need this soundtrack.",
        "Golden hour vibes on a crisp day.",
    ],
    "summer": [
        "Sun-kissed beats for lazy afternoons.",
        "Balcony sunset energy.",
        "Summer breeze and smooth beats.",
    ],
}

# ── Song → mood mapping (same as cover art) ──────────────────
SONG_MOOD_MAP = {
    "rooftop rain": "rain", "puddle reflections": "rain", "thunder & tea": "rain",
    "rain on glass": "rain", "coffee & rain": "rain",
    "cherry blossom walk": "anime", "tokyo sunset": "anime", "shrine steps": "anime",
    "highway glow": "city", "neon exit": "city", "parking lot stars": "city",
    "winter fireplace": "winter", "autumn pages": "autumn", "summer balcony": "summer",
    "3am thoughts": "night", "midnight loop": "night", "late night code": "night",
    "2am focus": "night", "deadline mode": "night", "tab overload": "night",
    "drift off": "cozy", "golden hour": "summer", "flow state": "cozy",
    "closing time": "night", "analog drift": "city", "window seat": "cozy",
    "sunday brew": "cozy", "library hours": "cozy", "espresso shot": "cozy",
    "bookstore find": "autumn",
}

# ── Emoji mapping ────────────────────────────────────────────
MOOD_EMOJI = {
    "rain": ["🌧️", "☔", "🌊"],
    "anime": ["🌸", "✨", "🎌"],
    "city": ["🌃", "🏙️", "💜"],
    "night": ["🌙", "🌌", "💫"],
    "cozy": ["☕", "🕯️", "🧸"],
    "winter": ["❄️", "🔥", "🧣"],
    "autumn": ["🍂", "🍁", "📖"],
    "summer": ["☀️", "🌴", "🌅"],
}

# ── Tag pools ────────────────────────────────────────────────
BASE_TAGS = ["content", "contenthiphop", "chillbeats", "studymusic", "aimusic", "CONTENT-PIPELINE"]
MOOD_TAGS = {
    "rain": ["rain", "rainyvibes", "ambient", "relaxing"],
    "anime": ["anime", "japanese", "aesthetic", "kawaii"],
    "city": ["nightdrive", "citypop", "neon", "urban"],
    "night": ["latenight", "3am", "nocturnal", "midnight"],
    "cozy": ["cozy", "warmvibes", "coffeeshop", "comfort"],
    "winter": ["winter", "snow", "fireplace", "coldweather"],
    "autumn": ["autumn", "fall", "cozy", "bookstore"],
    "summer": ["summer", "sunshine", "tropical", "bossanova"],
}


def get_mood(song_name):
    return SONG_MOOD_MAP.get(song_name.lower(), "night")


def gen_youtube_shorts(song_name, mood):
    emoji = random.choice(MOOD_EMOJI[mood])
    hook = random.choice(HOOKS[mood])
    tags = BASE_TAGS + MOOD_TAGS[mood]

    title = f"{song_name} {emoji} #shorts #content #aimusic"
    description = (
        f"{hook}\n"
        f"AI-made Content beat by Content Pipeline. No filler.\n\n"
        f"24/7 Stream: youtube.com/@CONTENT-PIPELINEMusic\n"
        f"Spotify: Content Pipeline\n\n"
        f"#{' #'.join(tags)}"
    )
    return {"title": title, "description": description, "tags": tags}


def gen_tiktok(song_name, mood):
    emoji = random.choice(MOOD_EMOJI[mood])
    hook = random.choice(HOOKS[mood])
    tags = BASE_TAGS + MOOD_TAGS[mood]

    title = f"{song_name} {emoji} #content #aimusic #shorts"
    caption = (
        f"{hook} {emoji}\n"
        f"AI beat by Content Pipeline.\n\n"
        f"#{' #'.join(tags)}"
    )
    return {"title": title, "caption": caption, "tags": tags}


def gen_instagram(song_name, mood):
    emoji = random.choice(MOOD_EMOJI[mood])
    hook = random.choice(HOOKS[mood])
    tags = BASE_TAGS + MOOD_TAGS[mood] + ["reels", "beats", "musicproducer"]

    caption = (
        f"{hook} {emoji}\n"
        f"AI beat that hits different.\n\n"
        f"#{' #'.join(tags)}"
    )
    return {"caption": caption, "tags": tags}


def gen_DistributionPlatform(song_name, mood):
    tags = MOOD_TAGS[mood][:3] + ["content", "instrumental"]
    return {
        "title": song_name,
        "artist": "Content Pipeline",
        "album": song_name,
        "genre": "Hip-Hop/Rap",
        "subgenre": "Content",
        "tags": tags,
    }


def gen_youtube_live(song_name, mood):
    emoji = random.choice(MOOD_EMOJI[mood])
    return {
        "title": f"Content Pipeline {emoji} Content Hip Hop 24/7 - Study / Relax / Focus",
        "description_track_entry": f"- {song_name}",
    }


def generate_all(song_name):
    mood = get_mood(song_name)
    return {
        "song": song_name,
        "mood": mood,
        "youtube_shorts": gen_youtube_shorts(song_name, mood),
        "tiktok": gen_tiktok(song_name, mood),
        "instagram": gen_instagram(song_name, mood),
        "DistributionPlatform": gen_DistributionPlatform(song_name, mood),
        "youtube_live": gen_youtube_live(song_name, mood),
    }


def print_result(data, format_type="text"):
    if format_type == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print(f"\n{'='*60}")
    print(f"  {data['song']}  (mood: {data['mood']})")
    print(f"{'='*60}")

    yt = data["youtube_shorts"]
    print(f"\n--- YouTube Shorts ---")
    print(f"Title: {yt['title']}")
    print(f"Description:\n{yt['description']}")

    tt = data["tiktok"]
    print(f"\n--- TikTok ---")
    print(f"Caption:\n{tt['caption']}")

    ig = data["instagram"]
    print(f"\n--- Instagram Reels ---")
    print(f"Caption:\n{ig['caption']}")

    dk = data["DistributionPlatform"]
    print(f"\n--- DistributionPlatform ---")
    print(f"Title: {dk['title']} | Artist: {dk['artist']} | Genre: {dk['genre']}")
    print(f"Tags: {', '.join(dk['tags'])}")


def main():
    parser = argparse.ArgumentParser(description="CONTENT-PIPELINE Meta Generator")
    parser.add_argument("--song", type=str, help="Song name")
    parser.add_argument("--batch", type=str, help="Text file with song names")
    parser.add_argument("--format", type=str, default="text", choices=["text", "json"])
    parser.add_argument("--platform", type=str, choices=["youtube-shorts", "tiktok", "instagram", "DistributionPlatform", "all"], default="all")
    parser.add_argument("--output", type=str, help="Save JSON output to file")
    args = parser.parse_args()

    songs = []
    if args.batch:
        songs = [l.strip() for l in Path(args.batch).read_text(encoding="utf-8").splitlines() if l.strip()]
    elif args.song:
        songs = [args.song]
    else:
        parser.print_help()
        return

    all_results = []
    for song in songs:
        data = generate_all(song)

        if args.platform != "all":
            key = args.platform.replace("-", "_")
            data = {"song": song, "mood": data["mood"], key: data[key]}

        all_results.append(data)
        print_result(data, args.format)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[SAVED] {out_path}")


if __name__ == "__main__":
    main()
