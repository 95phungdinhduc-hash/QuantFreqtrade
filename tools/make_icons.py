"""Vẽ icon cho web app (docs/icons/). Chạy lại khi muốn đổi icon: .venv/bin/python tools/make_icons.py (cần macOS vì dùng font emoji của Apple)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[1] / "docs" / "icons"
EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
S = 1024


def background() -> Image.Image:
    """Nền tối + 3 quầng sáng xanh / tím / lục giống theme Aurora."""
    img = Image.new("RGB", (S, S), (8, 12, 22))
    glow = Image.new("RGB", (S, S), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    for (cx, cy, r, col) in ((260, 230, 520, (57, 135, 229)), (820, 260, 420, (108, 95, 240)), (700, 860, 460, (31, 191, 117))):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(170))
    return Image.blend(img, glow, 0.55)


def duck(size: int) -> Image.Image:
    font = ImageFont.truetype(EMOJI_FONT, 160)       # font emoji Apple chỉ có cỡ bitmap 160
    tile = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((100, 100), "🦆", font=font, embedded_color=True, anchor="mm")
    return tile.crop(tile.getbbox()).resize((size, size), Image.LANCZOS)


def compose(scale: float) -> Image.Image:
    img = background().convert("RGBA")
    ds = int(S * scale)
    d = duck(ds)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), ((S - ds) // 2, (S - ds) // 2 + 40), d)
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(30)))
    img.alpha_composite(d, ((S - ds) // 2, (S - ds) // 2))
    return img.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    normal, maskable = compose(0.56), compose(0.44)   # maskable: chừa vùng an toàn để Android cắt tròn
    for name, img, px in (("icon-512.png", normal, 512), ("icon-192.png", normal, 192),
                          ("apple-touch-icon.png", normal, 180), ("icon-512-maskable.png", maskable, 512)):
        img.resize((px, px), Image.LANCZOS).save(OUT / name, optimize=True)
        print("ghi", OUT / name)


if __name__ == "__main__":
    main()
