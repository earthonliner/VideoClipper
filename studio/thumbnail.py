from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from . import config
from .project import project_dir

SIZE = (1280, 720)
MAX_BYTES = 2 * 1024 * 1024


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines = []
    for para in text.split("\n"):
        line = ""
        # Character-level wrapping works for CJK; for latin text break on spaces.
        tokens = para.split(" ") if para.isascii() else list(para)
        sep = " " if para.isascii() else ""
        for tok in tokens:
            trial = f"{line}{sep}{tok}" if line else tok
            if draw.textlength(trial, font=font) <= max_w:
                line = trial
            else:
                lines.append(line)
                line = tok
        lines.append(line)
    return [l for l in lines if l]


def make_thumbnail(slug: str, source: str, text: str, variant: str = "a", accent: str = "#FFD400",
                   position: str = "left", darken: float = 0.55) -> dict:
    """Compose a 1280x720 thumbnail from a project image (frame or asset) with bold headline text.

    `text` may contain '\n'; wrap a word in [brackets] to highlight it in the accent color.
    """
    base = project_dir(slug)
    img = ImageOps.fit(Image.open(base / source).convert("RGB"), SIZE, Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.15)

    shade = Image.new("L", SIZE)
    sd = ImageDraw.Draw(shade)
    for x in range(SIZE[0]):
        ratio = x / SIZE[0] if position == "left" else 1 - x / SIZE[0]
        sd.line([(x, 0), (x, SIZE[1])], fill=int(255 * darken * max(0.0, 1 - ratio * 1.4)))
    img = Image.composite(Image.new("RGB", SIZE, "black"), img, shade)

    draw = ImageDraw.Draw(img)
    font_path = config.find_font()
    plain = text.replace("[", "").replace("]", "")
    size = 150
    while True:
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size)
        lines = _wrap(draw, plain, font, int(SIZE[0] * 0.6))
        height = len(lines) * size * 1.15
        if (height <= SIZE[1] * 0.8 and len(lines) <= 3) or size <= 60:
            break
        size -= 8

    flags, inside = [], False
    for ch in text:
        if ch in "[]":
            inside = ch == "["
        else:
            flags.append(inside)
    ptr = 0
    y = (SIZE[1] - height) / 2
    margin = 60
    for line in lines:
        lw = draw.textlength(line, font=font)
        x = margin if position == "left" else SIZE[0] - margin - lw
        for ch in line:
            while ptr < len(plain) and plain[ptr] != ch:
                ptr += 1
            fill = accent if ptr < len(flags) and flags[ptr] else "white"
            ptr += 1
            draw.text((x, y), ch, font=font, fill=fill, stroke_width=max(4, size // 14), stroke_fill="black")
            x += draw.textlength(ch, font=font)
        y += size * 1.15

    out = base / "thumbs" / f"thumb-{variant}.jpg"
    quality = 92
    while True:
        img.save(out, "JPEG", quality=quality, optimize=True)
        if out.stat().st_size <= MAX_BYTES or quality <= 60:
            break
        quality -= 8
    return {"file": str(out.relative_to(base)), "bytes": out.stat().st_size, "font": font_path}
