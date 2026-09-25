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
        candidates = [
            p.with_name(
                p.name.replace('Bold', '')
            )
            for p in DEFAULT_FONT_CANDIDATES
        ] + candidates

    for p in candidates:
        if p.exists():
            return ImageFont.truetype(
                str(p),
                size
            )

    return ImageFont.load_default()


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_lines: int,
    start: int,
    min_size: int = 24
):
    text = ' '.join(
        str(text or '').split()
    )

    size = start

    while size >= min_size:
        f = _font(
            size,
            True
        )

        words = text.split()
        lines = []
        current = ''

        for word in words:
            trial = (
                current + ' ' + word
            ).strip()

            if draw.textbbox(
                (0, 0),
                trial,
                font=f
            )[2] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(
                        current
                    )

                current = word

        if current:
            lines.append(current)

        if len(lines) <= max_lines:
            return f, lines

        size -= 2

    f = _font(
        min_size,
        True
    )

    return f, lines[:max_lines]


def _paste_cover(
    base: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    focus: str = 'center'
):
    x1, y1, x2, y2 = box

    w = x2 - x1
    h = y2 - y1

    fitted = ImageOps.fit(
        image.convert('RGB'),
        (w, h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.45)
    )

    base.paste(
        fitted,
        (x1, y1)
    )


def _rounded_mask(size, radius):
    mask = Image.new(
        'L',
        size,
        0
    )

    d = ImageDraw.Draw(mask)

    d.rounded_rectangle(
        (
            0,
            0,
            size[0] - 1,
            size[1] - 1
        ),
        radius=radius,
        fill=255
    )

    return mask


# ============================================================
# LOGO
# ============================================================

def _paste_logo_top_right(
    canvas: Image.Image,
    logo_path: Optional[Path],
    photo_h: int,
    max_width: int = 260,
    max_height: int = 90,
    margin: int = 35
):
    """
    Logo will be placed at the TOP-RIGHT corner
    of the MAIN PHOTO area.

    It will NOT appear in the bottom footer.
    """

    if not logo_path:
        return

    if not logo_path.exists():
        return

    try:
        logo = Image.open(
            logo_path
        ).convert('RGBA')
    except Exception:
        return

    logo.thumbnail(
        (
            max_width,
            max_height
        ),
        Image.Resampling.LANCZOS
    )

    # Right side position
    x = (
        canvas.width
        - logo.width
        - margin
    )

    # Top of the main image
    y = margin

    # Make absolutely sure the logo stays
    # inside the main photo area.
    if y + logo.height > photo_h:
        y = max(
            margin,
            photo_h
            - logo.height
            - margin
        )

    canvas.paste(
        logo,
        (x, y),
        logo
    )


def create_card(
    image_path: Path,
    headline: str,
    date_text: str,
    logo_path: Optional[Path],
    output: Path,
    width: int = 1200,
    height: int = 1500
) -> Path:

    image = Image.open(
        image_path
    ).convert('RGB')

    canvas = Image.new(
        'RGB',
        (width, height),
        '#f3f3f3'
    )

    photo_h = int(
        height * 0.62
    )

    # ========================================================
    # MAIN NEWS PHOTO
    # ========================================================

    _paste_cover(
        canvas,
        image,
        (
            0,
            0,
            width,
            photo_h
        )
    )

    # ========================================================
    # LOGO — TOP RIGHT OF PHOTO
    # ========================================================

    _paste_logo_top_right(
        canvas,
        logo_path,
        photo_h,
        max_width=260,
        max_height=90,
        margin=35
    )

    # ========================================================
    # DARK/RED NEWS LOWER PANEL
    # ========================================================

    panel_y = photo_h - 2

    panel = Image.new(
        'RGB',
        (
            width,
            height - panel_y
        ),
        '#a40000'
    )

    pd = ImageDraw.Draw(
        panel
    )

    for y in range(
        panel.height
    ):

        t = y / max(
            1,
            panel.height - 1
        )

        r = int(
            170 - 45 * t
        )

        g = int(
            8 + 12 * t
        )

        b = int(
            8 + 12 * t
        )

        pd.line(
            (
                0,
                y,
                width,
                y
            ),
            fill=(
                r,
                g,
                b
            )
        )

    canvas.paste(
        panel,
        (0, panel_y)
    )

    d = ImageDraw.Draw(
        canvas
    )

    # ========================================================
    # WHITE DIVIDER
    # ========================================================

    d.rectangle(
        (
            0,
            panel_y,
            width,
            panel_y + 6
        ),
        fill='white'
    )

    # ========================================================
    # HEADLINE
    # ========================================================

    headline_font, lines = _fit_text(
        d,
        headline,
        width - 120,
        4,
        66,
        30
    )

    line_h = (
        headline_font.size
        + 13
    )

    y = panel_y + 95

    for line in lines:

        bbox = d.textbbox(
            (0, 0),
            line,
            font=headline_font
        )

        tw = (
            bbox[2]
            - bbox[0]
        )

        x = (
            width - tw
        ) // 2

        # Subtle shadow
        d.text(
            (
                x + 2,
                y + 2
            ),
            line,
            font=headline_font,
            fill='#5b0000'
        )

        d.text(
            (
                x,
                y
            ),
            line,
            font=headline_font,
            fill='white'
        )

        y += line_h

    # ========================================================
    # COMMENT NOTICE
    # ========================================================

    sub_font = _font(
        32,
        True
    )

    sub = 'বিস্তারিত প্রথম কমেন্টে'

    sb = d.textbbox(
        (0, 0),
        sub,
        font=sub_font
    )

    d.text(
        (
            (
                width
                - (
                    sb[2]
                    - sb[0]
                )
            ) // 2,
            y + 38
        ),
        sub,
        font=sub_font,
        fill='#ffe500'
    )

    # ========================================================
    # FOOTER
    # ========================================================
    # IMPORTANT:
    # Logo is NO LONGER placed here.
    # Only date remains in footer.

    footer_y = height - 120

    d.rectangle(
        (
            40,
            footer_y,
            width - 40,
            footer_y + 2
        ),
        fill='#ffffff'
    )

    date_font = _font(
        26,
        True
    )

    d.text(
        (
            55,
            footer_y + 24
        ),
        date_text,
        font=date_font,
        fill='white'
    )

    # No logo here.
    # No default "বাংলা সংবাদ" logo here.
    # Logo is already at the top-right of photo.

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    canvas.save(
        output,
        quality=92,
        optimize=True
    )

    return output


def create_vertical_frame(
    image_path: Path,
    headline: str,
    date_text: str,
    logo_path: Optional[Path],
    output: Path,
    width: int = 1080,
    height: int = 1920
) -> Path:

    # Same visual language,
    # optimized for Shorts/Reels/vertical video.

    image = Image.open(
        image_path
    ).convert('RGB')

    canvas = Image.new(
        'RGB',
        (width, height),
        '#111111'
    )

    photo_h = 1180

    # ========================================================
    # MAIN VERTICAL PHOTO
    # ========================================================

    _paste_cover(
        canvas,
        image,
        (
            0,
            0,
            width,
            photo_h
        )
    )

    # ========================================================
    # LOGO — TOP RIGHT OF VERTICAL PHOTO
    # ========================================================

    _paste_logo_top_right(
        canvas,
        logo_path,
        photo_h,
        max_width=240,
        max_height=90,
        margin=30
    )

    # ========================================================
    # RED LOWER PANEL
    # ========================================================

    panel_y = photo_h

    panel = Image.new(
        'RGB',
        (
            width,
            height - panel_y
        ),
        '#a40000'
    )

    pd = ImageDraw.Draw(
        panel
    )

    for y in range(
        panel.height
    ):

        t = y / max(
            1,
            panel.height - 1
        )

        pd.line(
            (
                0,
                y,
                width,
                y
            ),
            fill=(
                int(
                    175 - 55 * t
                ),
                int(
                    8 + 15 * t
                ),
                int(
                    8 + 15 * t
                )
            )
        )

    canvas.paste(
        panel,
        (0, panel_y)
    )

    d = ImageDraw.Draw(
        canvas
    )

    # ========================================================
    # WHITE DIVIDER
    # ========================================================

    d.rectangle(
        (
            0,
            panel_y,
            width,
            panel_y + 6
        ),
        fill='white'
    )

    # ========================================================
    # HEADLINE
    # ========================================================

    f, lines = _fit_text(
        d,
        headline,
        width - 100,
        5,
        64,
        30
    )

    y = panel_y + 80

    for line in lines:

        bbox = d.textbbox(
            (0, 0),
            line,
            font=f
        )

        tw = bbox[2]

        x = (
            width - tw
        ) // 2

        d.text(
            (
                x + 2,
                y + 2
            ),
            line,
            font=f,
            fill='#5b0000'
        )

        d.text(
            (
                x,
                y
            ),
            line,
            font=f,
            fill='white'
        )

        y += (
            f.size
            + 12
        )

    # ========================================================
    # COMMENT NOTICE
    # ========================================================

    sf = _font(
        34,
        True
    )

    sub = 'বিস্তারিত প্রথম কমেন্টে'

    bbox = d.textbbox(
        (0, 0),
        sub,
        font=sf
    )

    tw = bbox[2]

    d.text(
        (
            (width - tw) // 2,
            y + 40
        ),
        sub,
        font=sf,
        fill='#ffe500'
    )

    # ========================================================
    # DATE FOOTER
    # ========================================================

    df = _font(
        28,
        True
    )

    d.text(
        (
            55,
            height - 105
        ),
        date_text,
        font=df,
        fill='white'
    )

    # IMPORTANT:
    # Logo is NOT placed at bottom anymore.
    # It was already placed at the top-right
    # of the main photo above.

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    canvas.save(
        output,
        quality=92
    )

    return output
