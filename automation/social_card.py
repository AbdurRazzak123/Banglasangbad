from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT_CANDIDATES = [
    Path('/usr/share/fonts/opentype/noto/NotoSansBengali-Bold.ttf'),
    Path('/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf'),
    Path('/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf'),
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = DEFAULT_FONT_CANDIDATES
    if not bold:
        candidates = [p.with_name(p.name.replace('Bold', '')) for p in DEFAULT_FONT_CANDIDATES] + candidates
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int, start: int, min_size: int = 24):
    text = ' '.join(str(text or '').split())
    size = start
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
        size -= 2
    f = _font(min_size, True)
    return f, lines[:max_lines]


def _paste_cover(base: Image.Image, image: Image.Image, box: tuple[int, int, int, int], focus: str = 'center'):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    fitted = ImageOps.fit(image.convert('RGB'), (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    base.paste(fitted, (x1, y1))


def _add_logo(canvas: Image.Image, logo_path: Optional[Path], max_size=(250, 90), margin=35):
    if not logo_path or not logo_path.exists():
        return
    logo = Image.open(logo_path).convert('RGBA')
    logo.thumbnail(max_size, Image.Resampling.LANCZOS)
    x = canvas.width - logo.width - margin
    y = margin
    # Light translucent backing keeps the logo readable over busy photos.
    pad = 10
    backing = Image.new('RGBA', (logo.width + pad * 2, logo.height + pad * 2), (0, 0, 0, 105))
    canvas.alpha_composite(backing, (x - pad, y - pad))
    canvas.alpha_composite(logo, (x, y))


def create_card(image_path: Path, headline: str, date_text: str, logo_path: Optional[Path], output: Path,
                width: int = 1200, height: int = 1500) -> Path:
    image = Image.open(image_path).convert('RGB')
    canvas = Image.new('RGBA', (width, height), '#f3f3f3')
    photo_h = int(height * 0.62)
    _paste_cover(canvas, image, (0, 0, width, photo_h))
    _add_logo(canvas, logo_path, (260, 95), 35)

    panel_y = photo_h - 2
    panel = Image.new('RGB', (width, height - panel_y), '#a40000')
    pd = ImageDraw.Draw(panel)
    for y in range(panel.height):
        t = y / max(1, panel.height - 1)
        r = int(170 - 45*t); g = int(8 + 12*t); b = int(8 + 12*t)
        pd.line((0, y, width, y), fill=(r, g, b))
    canvas.paste(panel, (0, panel_y))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, panel_y, width, panel_y + 6), fill='white')

    headline_font, lines = _fit_text(d, headline, width - 120, 4, 66, 30)
    line_h = headline_font.size + 13
    y = panel_y + 95
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=headline_font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        d.text((x+2, y+2), line, font=headline_font, fill='#5b0000')
        d.text((x, y), line, font=headline_font, fill='white')
        y += line_h

    sub_font = _font(32, True)
    sub = 'বিস্তারিত প্রথম কমেন্টে'
    sb = d.textbbox((0,0), sub, font=sub_font)
    d.text(((width-(sb[2]-sb[0]))//2, y+38), sub, font=sub_font, fill='#ffe500')

    footer_y = height - 120
    d.rectangle((40, footer_y, width-40, footer_y+2), fill='#ffffff')
    date_font = _font(26, True)
    d.text((55, footer_y+24), date_text, font=date_font, fill='white')
    brand_font = _font(34, True)
    brand = 'বাংলা সংবাদ'
    bb = d.textbbox((0,0), brand, font=brand_font)
    d.text((width-(bb[2]-bb[0])-55, footer_y+30), brand, font=brand_font, fill='white')

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(output, quality=92, optimize=True)
    return output


def _wrap_bengali(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for paragraph in str(text or '').splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append('')
            continue
        words = paragraph.split()
        current = ''
        for word in words:
            trial = (current + ' ' + word).strip()
            if ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0,0), trial, font=font)[2] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap Bengali/Unicode text by measured pixel width, preserving paragraphs."""
    lines: list[str] = []
    for paragraph in str(text or '').splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            if lines and lines[-1] != '':
                lines.append('')
            continue
        current = ''
        for word in paragraph.split():
            trial = f'{current} {word}'.strip()
            if not current or draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    while lines and lines[-1] == '':
        lines.pop()
    return lines


def _split_article_for_slides(text: str, width: int, height: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Split the complete article into at most nine readable detail-slide chunks.

    We calculate chunks from actual rendered line capacity instead of a character
    count, so Bengali text is not silently cut because glyph widths differ.
    """
    text = str(text or '').strip()
    if not text:
        return _font(32, True), ['এই খবরের বিস্তারিত ওয়েবসাইটে প্রকাশিত হয়েছে।']

    max_width = width - 120
    # Try progressively smaller fonts so ordinary long articles still fit in
    # the 9 detail slides available after the cover (10 carousel items total).
    for size, max_lines in ((38, 25), (34, 28), (30, 31), (27, 34), (24, 38)):
        font = _font(size, True)
        probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        all_lines = _wrap_lines(probe, text, font, max_width)
        chunks: list[str] = []
        current: list[str] = []
        for line in all_lines:
            if len(current) >= max_lines:
                chunks.append('\n'.join(current))
                current = []
            current.append(line)
        if current:
            chunks.append('\n'.join(current))
        if len(chunks) <= 9:
            return font, chunks

    raise ValueError(
        'Instagram carousel cannot fit the complete article into the API limit of '
        '10 images. Shorten the Details field in Google Sheet for this article.'
    )


def create_instagram_carousel(image_path: Path, headline: str, details: str, date_text: str,
                              logo_path: Optional[Path], output_dir: Path, news_id: str,
                              max_slides: int = 10) -> list[Path]:
    """Create a complete, readable Instagram carousel: cover + article details.

    Instagram allows up to 10 carousel children. The first slide is the branded
    news image; the remaining slides contain the complete Details text. Text is
    measured by rendered width and the function refuses to silently truncate it.
    """
    if max_slides < 2:
        raise ValueError('Instagram carousel requires at least 2 slides')
    max_slides = min(max_slides, 10)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    width, height = 1080, 1350

    # Cover: original news image with the logo in the upper-right corner.
    cover = Image.new('RGBA', (width, height), '#111111')
    photo_h = 790
    _paste_cover(cover, Image.open(image_path).convert('RGB'), (0, 0, width, photo_h))
    _add_logo(cover, logo_path, (240, 90), 32)
    d = ImageDraw.Draw(cover)
    d.rectangle((0, photo_h, width, height), fill='#a40000')
    f, lines = _fit_text(d, headline, width - 100, 5, 58, 30)
    y = photo_h + 65
    for line in lines:
        tw = d.textbbox((0, 0), line, font=f)[2]
        x = (width - tw) // 2
        d.text((x + 2, y + 2), line, font=f, fill='#5b0000')
        d.text((x, y), line, font=f, fill='white')
        y += f.size + 12
    df = _font(28, True)
    d.text((55, height - 75), date_text, font=df, fill='white')
    cover_path = output_dir / f'{news_id}-ig-01.jpg'
    cover.convert('RGB').save(cover_path, quality=92, optimize=True)
    paths.append(cover_path)

    # Detail slides contain the entire Details field, with no silent truncation.
    body_font, chunks = _split_article_for_slides(details, width, height)
    if len(chunks) > max_slides - 1:
        raise ValueError('Instagram article requires more than 10 carousel slides.')

    small_font = _font(26, True)
    max_width = width - 120
    line_h = body_font.size + 13
    for idx, chunk in enumerate(chunks, start=2):
        page = Image.new('RGB', (width, height), '#ffffff')
        pd = ImageDraw.Draw(page)
        pd.rectangle((0, 0, width, 105), fill='#a40000')
        pd.text((55, 31), f'বাংলা সংবাদ  •  {idx - 1}/{len(chunks)}', font=small_font, fill='white')
        _add_logo(page.convert('RGBA'), logo_path, (180, 65), 35)

        # Re-draw logo on RGB canvas with alpha mask because the helper works on RGBA.
        if logo_path and logo_path.exists():
            logo = Image.open(logo_path).convert('RGBA')
            logo.thumbnail((180, 65), Image.Resampling.LANCZOS)
            pad = 7
            bx = width - logo.width - 35
            by = 20
            backing = Image.new('RGBA', (logo.width + pad * 2, logo.height + pad * 2), (0, 0, 0, 90))
            page.paste(backing.convert('RGB'), (bx - pad, by - pad))
            page.paste(logo, (bx, by), logo)

        lines = _wrap_lines(pd, chunk, body_font, max_width)
        y = 145
        for line in lines:
            if not line:
                y += max(10, line_h // 2)
                continue
            if y + line_h > height - 85:
                raise ValueError('Internal layout overflow while rendering Instagram article slide.')
            pd.text((60, y), line, font=body_font, fill='#151515')
            y += line_h

        pd.line((60, height - 65, width - 60, height - 65), fill='#dddddd', width=2)
        pd.text((60, height - 50), date_text, font=small_font, fill='#555555')
        out = output_dir / f'{news_id}-ig-{idx:02d}.jpg'
        page.save(out, quality=92, optimize=True)
        paths.append(out)

    # The carousel API requires at least two items. A missing Details field gets
    # a second readable slide rather than falling back to an invalid one-item carousel.
    if len(paths) < 2:
        raise ValueError('Instagram carousel requires at least two generated images.')
    return paths


def create_vertical_frame(image_path: Path, headline: str, date_text: str, logo_path: Optional[Path], output: Path,
                          width: int = 1080, height: int = 1920) -> Path:
    image = Image.open(image_path).convert('RGB')
    canvas = Image.new('RGB', (width, height), '#111111')
    photo_h = 1180
    _paste_cover(canvas, image, (0, 0, width, photo_h))
    panel_y = photo_h
    panel = Image.new('RGB', (width, height-panel_y), '#a40000')
    pd = ImageDraw.Draw(panel)
    for y in range(panel.height):
        t = y / max(1, panel.height-1)
        pd.line((0,y,width,y), fill=(int(175-55*t), int(8+15*t), int(8+15*t)))
    canvas.paste(panel,(0,panel_y))
    d=ImageDraw.Draw(canvas)
    d.rectangle((0,panel_y,width,panel_y+6),fill='white')
    f,lines=_fit_text(d,headline,width-100,5,64,30)
    y=panel_y+80
    for line in lines:
        tw=d.textbbox((0,0),line,font=f)[2]; x=(width-tw)//2
        d.text((x+2,y+2),line,font=f,fill='#5b0000'); d.text((x,y),line,font=f,fill='white'); y+=f.size+12
    sf=_font(34,True); sub='বিস্তারিত প্রথম কমেন্টে'; tw=d.textbbox((0,0),sub,font=sf)[2]
    d.text(((width-tw)//2,y+40),sub,font=sf,fill='#ffe500')
    df=_font(28,True); d.text((55,height-105),date_text,font=df,fill='white')
    if logo_path and logo_path.exists():
        logo=Image.open(logo_path).convert('RGBA'); logo.thumbnail((240,90),Image.Resampling.LANCZOS)
        canvas.paste(logo,(width-logo.width-50,height-120),logo)
    output.parent.mkdir(parents=True,exist_ok=True); canvas.save(output,quality=92); return output
