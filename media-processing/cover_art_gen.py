#!/usr/bin/env python3
"""
CONTENT-PIPELINE — Auto Cover Art Generator
สร้าง cover art 3000x3000 สำหรับ DistributionPlatform + YouTube thumbnail 1280x720

Usage:
    python3 cover_art_gen.py --song "Rooftop Rain"
    python3 cover_art_gen.py --song "Rooftop Rain" --theme rain
    python3 cover_art_gen.py --batch songs.txt
    python3 cover_art_gen.py --list-themes

Requirements:
    pip install Pillow
"""

import argparse
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
BG_DIR = BASE_DIR / "backgrounds"

# ── Color Themes ─────────────────────────────────────────────
THEMES = {
    "night": {
        "bg": (10, 12, 28),
        "gradient": (20, 25, 60),
        "title_color": (255, 255, 255),
        "subtitle_color": (77, 217, 192),
        "accent": (77, 217, 192),
        "glow": (77, 217, 192, 40),
    },
    "rain": {
        "bg": (8, 15, 25),
        "gradient": (15, 30, 50),
        "title_color": (200, 220, 240),
        "subtitle_color": (100, 160, 220),
        "accent": (100, 160, 220),
        "glow": (100, 160, 220, 40),
    },
    "anime": {
        "bg": (30, 15, 35),
        "gradient": (50, 20, 55),
        "title_color": (255, 200, 220),
        "subtitle_color": (255, 150, 180),
        "accent": (255, 150, 180),
        "glow": (255, 150, 180, 40),
    },
    "city": {
        "bg": (15, 10, 25),
        "gradient": (25, 15, 45),
        "title_color": (255, 220, 150),
        "subtitle_color": (200, 130, 255),
        "accent": (200, 130, 255),
        "glow": (200, 130, 255, 40),
    },
    "cozy": {
        "bg": (25, 18, 12),
        "gradient": (45, 30, 18),
        "title_color": (255, 230, 200),
        "subtitle_color": (245, 166, 35),
        "accent": (245, 166, 35),
        "glow": (245, 166, 35, 40),
    },
    "winter": {
        "bg": (15, 20, 30),
        "gradient": (25, 35, 55),
        "title_color": (220, 235, 255),
        "subtitle_color": (150, 200, 255),
        "accent": (150, 200, 255),
        "glow": (150, 200, 255, 40),
    },
    "autumn": {
        "bg": (28, 15, 8),
        "gradient": (50, 28, 12),
        "title_color": (255, 220, 180),
        "subtitle_color": (220, 140, 60),
        "accent": (220, 140, 60),
        "glow": (220, 140, 60, 40),
    },
    "summer": {
        "bg": (15, 25, 20),
        "gradient": (25, 45, 35),
        "title_color": (255, 245, 220),
        "subtitle_color": (120, 220, 160),
        "accent": (120, 220, 160),
        "glow": (120, 220, 160, 40),
    },
}

# ── Song → Theme mapping ────────────────────────────────────
SONG_THEME_MAP = {
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


def auto_theme(song_name):
    """Auto-detect theme from song name."""
    return SONG_THEME_MAP.get(song_name.lower(), "night")


def draw_gradient(img, color1, color2):
    """Draw vertical gradient background."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        ratio = y / h
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_noise(img, intensity=15):
    """Add subtle noise texture."""
    import struct
    w, h = img.size
    pixels = img.load()
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            noise = random.randint(-intensity, intensity)
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
            )


def draw_glow_circle(img, center, radius, color):
    """Draw soft glow circle."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for i in range(radius, 0, -2):
        alpha = int(color[3] * (i / radius))
        draw.ellipse(
            [center[0] - i, center[1] - i, center[0] + i, center[1] + i],
            fill=(color[0], color[1], color[2], alpha),
        )
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def get_font(size, bold=False):
    """Try to load a good font, fallback to default."""
    font_candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "",
    ]
    for f in font_candidates:
        if f and Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def generate_cover(song_name, theme_name=None, size=3000, use_bg_image=None):
    """Generate cover art for a song."""
    if not theme_name:
        theme_name = auto_theme(song_name)
    theme = THEMES.get(theme_name, THEMES["night"])

    img = Image.new("RGB", (size, size), theme["bg"])

    # Background image or gradient
    if use_bg_image and Path(use_bg_image).exists():
        bg = Image.open(use_bg_image).resize((size, size), Image.LANCZOS)
        # Darken overlay
        dark = Image.new("RGB", (size, size), (0, 0, 0))
        img = Image.blend(bg, dark, 0.5)
    else:
        draw_gradient(img, theme["bg"], theme["gradient"])
        draw_noise(img, 10)

    # Glow effects
    img_rgba = img.convert("RGBA")
    img_rgba = draw_glow_circle(img_rgba, (size // 3, size // 3), size // 2, theme["glow"])
    img_rgba = draw_glow_circle(img_rgba, (size * 2 // 3, size * 2 // 3), size // 3, theme["glow"])
    img = img_rgba.convert("RGB")

    # Blur glow slightly
    img = img.filter(ImageFilter.GaussianBlur(radius=2))

    draw = ImageDraw.Draw(img)

    # ── Accent line ──
    line_y = size * 0.42
    line_w = size * 0.15
    line_x = (size - line_w) / 2
    draw.rectangle(
        [line_x, line_y, line_x + line_w, line_y + 4],
        fill=theme["accent"],
    )

    # ── Song title ──
    title_font = get_font(size // 12, bold=True)
    bbox = draw.textbbox((0, 0), song_name, font=title_font)
    tw = bbox[2] - bbox[0]
    tx = (size - tw) / 2
    ty = size * 0.45
    draw.text((tx, ty), song_name, fill=theme["title_color"], font=title_font)

    # ── Artist name ──
    artist_font = get_font(size // 25)
    artist = "Content Pipeline"
    bbox2 = draw.textbbox((0, 0), artist, font=artist_font)
    aw = bbox2[2] - bbox2[0]
    ax = (size - aw) / 2
    ay = ty + (bbox[3] - bbox[1]) + size * 0.03
    draw.text((ax, ay), artist, fill=theme["subtitle_color"], font=artist_font)

    # ── Bottom accent line ──
    line_y2 = ay + (bbox2[3] - bbox2[1]) + size * 0.04
    draw.rectangle(
        [line_x, line_y2, line_x + line_w, line_y2 + 4],
        fill=theme["accent"],
    )

    # ── Watermark (small) ──
    wm_font = get_font(size // 50)
    wm_text = "Content Pipeline MUSIC"
    bbox3 = draw.textbbox((0, 0), wm_text, font=wm_font)
    wmw = bbox3[2] - bbox3[0]
    draw.text(
        ((size - wmw) / 2, size * 0.92),
        wm_text,
        fill=(*theme["subtitle_color"], 128) if len(theme["subtitle_color"]) == 3
        else theme["subtitle_color"],
        font=wm_font,
    )

    return img


def save_outputs(img, song_name, output_dir):
    """Save cover art in multiple sizes."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = song_name.replace(" ", "_").replace("&", "and")

    # DistributionPlatform cover (3000x3000)
    cover_path = output_dir / f"{safe_name}_cover_3000.png"
    img.save(str(cover_path), "PNG", quality=95)
    print(f"  [OK] DistributionPlatform cover: {cover_path}")

    # YouTube thumbnail (1280x720)
    thumb = img.crop((
        (3000 - 1280 * 3000 // 720) // 2, 0,
        (3000 + 1280 * 3000 // 720) // 2, 3000
    )).resize((1280, 720), Image.LANCZOS)
    thumb_path = output_dir / f"{safe_name}_thumb_1280x720.png"
    thumb.save(str(thumb_path), "PNG", quality=95)
    print(f"  [OK] YouTube thumb:   {thumb_path}")

    # TikTok/Shorts cover (1080x1920)
    vert = img.resize((1080, 1080), Image.LANCZOS)
    vert_full = Image.new("RGB", (1080, 1920), img.getpixel((0, 0)))
    vert_full.paste(vert, (0, (1920 - 1080) // 2))
    vert_path = output_dir / f"{safe_name}_vertical_1080x1920.png"
    vert_full.save(str(vert_path), "PNG", quality=95)
    print(f"  [OK] Vertical cover:  {vert_path}")


def main():
    parser = argparse.ArgumentParser(description="CONTENT-PIPELINE Cover Art Generator")
    parser.add_argument("--song", type=str, help="Song name")
    parser.add_argument("--theme", type=str, help="Theme name (auto-detect if omitted)")
    parser.add_argument("--bg", type=str, help="Background image path (optional)")
    parser.add_argument("--batch", type=str, help="Text file with song names (one per line)")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--list-themes", action="store_true", help="List available themes")
    args = parser.parse_args()

    if args.list_themes:
        print("Available themes:")
        for name, t in THEMES.items():
            print(f"  {name:10s} — accent: {t['accent']}")
        return

    songs = []
    if args.batch:
        songs = [line.strip() for line in Path(args.batch).read_text(encoding="utf-8").splitlines() if line.strip()]
    elif args.song:
        songs = [args.song]
    else:
        parser.print_help()
        return

    for song in songs:
        theme = args.theme or auto_theme(song)
        print(f"\n[ART] Generating: {song} (theme: {theme})")
        img = generate_cover(song, theme, use_bg_image=args.bg)
        save_outputs(img, song, args.output)

    print(f"\n[DONE] {len(songs)} cover(s) generated in {args.output}")


if __name__ == "__main__":
    main()
