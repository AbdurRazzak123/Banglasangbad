from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT_CANDIDATES = [
    Path('/usr/share/fonts/opentype/noto/NotoSansBengali-Bold.ttf'),
    Path('/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf'),
    Path('/usr/share/fonts/opentype/noto/NotoSansBengali-Regular.ttf'),
    Path('/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf'),
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = DEFAULT_FONT_CANDIDATES
    if not bold:
        candidates = [p.with_name(p.name.replace('Bold', 'Regular')) for p in DEFAULT_FONT_CANDIDATES] + candidates
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int, start: int, min_size: int = 24):
    text = ' '.join(str(text or '').split())
    size = start
    best_lines = [text]
    while size >= min_size:
        f = _font(size, True)
        words = text.split()
        lines = []
        current = ''
        for word in words:
            trial = (current + ' ' + word).strip()
            if draw.textbbox((0, 0), trial, font=f)[2] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if len(lines) <= max_lines:
            return f, lines
        best_lines = lines
        size -= 2
    f = _font(min_size, True)
    return f, best_lines[:max_lines]


def _paste_cover(base: Image.Image, image: Image.Image, box: tuple[int, int, int, int]):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    fitted = ImageOps.fit(image.convert('RGB'), (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    base.paste(fitted, (x1, y1))


def _add_logo(canvas: Image.Image, logo_path: Optional[Path], max_size=(260, 88), margin=34):
    """Put the transparent logo directly on the photo, upper-right, no box/shadow."""
    if not logo_path or not logo_path.exists():
        return
    logo = Image.open(logo_path).convert('RGBA')
    logo.thumbnail(max_size, Image.Resampling.LANCZOS)
    x = canvas.width - logo.width - margin
    y = margin
    # Deliberately no background, badge, shadow or backing plate.
    canvas.alpha_composite(logo, (x, y))


def create_card(
    image_path: Path,
    headline: str,
    date_text: str,
    logo_path: Optional[Path],
    output: Path,
    width: int = 1080,
    height: int = 1350,
    category: str = '',
    platform: str = 'facebook',
) -> Path:
    """Create the final vertical social news card.

    Facebook card: Headline + date + 'বিস্তারিত প্রথম কমেন্টে'.
    Instagram card: Headline + date + 'বিস্তারিত ক্যাপশনে'.
    No article details are rendered on the image.
    """
    image = Image.open(image_path).convert('RGB')
    canvas = Image.new('RGBA', (width, height), '#120708')

    # Large photo area.
    photo_h = 790
    _paste_cover(canvas, image, (0, 0, width, photo_h))
    _add_logo(canvas, logo_path, (260, 88), 34)

    # Dark red editorial panel below the photo.
    panel_top = photo_h - 8
    panel_h = height - panel_top
    panel = Image.new('RGBA', (width, panel_h), (74, 0, 5, 255))
    pd = ImageDraw.Draw(panel)
    for yy in range(panel_h):
        t = yy / max(1, panel_h - 1)
        r = int(125 - 55 * t)
        g = int(5 + 3 * (1 - t))
        b = int(10 + 8 * (1 - t))
        pd.line((0, yy, width, yy), fill=(r, g, b, 255))
    # Subtle diagonal accents.
    for offset in range(-500, width + 500, 180):
        pd.line((offset, panel_h, offset + 260, 0), fill=(180, 20, 20, 45), width=6)
    canvas.alpha_composite(panel, (0, panel_top))

    d = ImageDraw.Draw(canvas)

    # Thin bright divider between photo and headline panel.
    d.line((0, panel_top, width, panel_top), fill=(255, 45, 30, 255), width=5)

    # Headline only — no article details.
    headline_font, lines = _fit_text(d, headline, width - 120, 3, 66, 36)
    line_h = headline_font.size + 12
    total_h = len(lines) * line_h
    y = panel_top + 85
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=headline_font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        # Alternating yellow/white gives a premium news-card look.
        fill = '#ffd31a' if lines.index(line) == 0 else '#ffffff'
        d.text((x + 2, y + 3), line, font=headline_font, fill=(0, 0, 0, 160))
        d.text((x, y), line, font=headline_font, fill=fill)
        y += line_h

    # Date and the platform-specific callout on the same row.
    row_y = height - 125
    date_font = _font(27, True)
    callout_font = _font(25, True)
    date = date_text.strip()
    d.text((58, row_y), date, font=date_font, fill='#ffffff')

    callout = 'বিস্তারিত প্রথম কমেন্টে' if platform.lower() == 'facebook' else 'বিস্তারিত ক্যাপশনে'
    cb = d.textbbox((0, 0), callout, font=callout_font)
    cw = cb[2] - cb[0]
    # Compact red pill at the right, with no overlap with date.
    pill_x2 = width - 48
    pill_x1 = max(520, pill_x2 - cw - 46)
    pill_y1 = row_y - 10
    pill_y2 = row_y + 43
    d.rounded_rectangle((pill_x1, pill_y1, pill_x2, pill_y2), radius=26,
                        fill=(220, 28, 28, 245), outline=(255, 100, 75, 255), width=2)
    d.text((pill_x1 + (pill_x2 - pill_x1 - cw) // 2, row_y), callout,
           font=callout_font, fill='#ffffff')

    # Small brand line at the bottom.
    d.line((48, height - 62, width - 48, height - 62), fill=(255, 255, 255, 55), width=1)
    brand_font = _font(21, True)
    brand = 'বাংলা সংবাদ'
    bb = d.textbbox((0, 0), brand, font=brand_font)
    d.text((width - (bb[2] - bb[0]) - 50, height - 50), brand, font=brand_font, fill='#f7d66a')

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(output, quality=95, optimize=True, progressive=True)
    return output


# Kept for compatibility with existing imports/tools.
def _wrap_bengali(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    for paragraph in str(text or '').splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            if lines and lines[-1] != '':
                lines.append('')
            continue
        current = ''
        for word in paragraph.split():
            trial = f'{current} {word}'.strip()
            if not current or probe.textbbox((0, 0), trial, font=font)[2] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    return _wrap_bengali(text, font, max_width)


def _split_article_for_slides(text: str, width: int, height: int):
    # Legacy helper retained; current publishing no longer creates article-detail slides.
    font = _font(28, True)
    return font, _wrap_bengali(text, font, width - 120)


def create_instagram_carousel(*args, **kwargs):
    raise ValueError('Instagram carousel generation is disabled: article details belong in the Instagram caption.')


def create_vertical_frame(image_path: Path, headline: str, date_text: str, logo_path: Optional[Path], output: Path,
                          width: int = 1080, height: int = 1350, category: str = '', platform: str = 'facebook') -> Path:
    return create_card(image_path, headline, date_text, logo_path, output, width, height, category, platform)
