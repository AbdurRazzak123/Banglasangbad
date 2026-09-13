#!/usr/bin/env python3

"""
Bangla Sangbad
Google Sheet -> Static News Pages + JSON + Sitemap

Google Sheet columns:
ID | Category | Headline | Details | Image-1 | Date | Video | Image-2 | Image-3 | Keyword

This script:
1. Reads the public Google Sheet using the gviz endpoint.
2. Generates news/ID.html for every valid news row.
3. Generates news-data.json.
4. Generates sitemap.xml.
5. Generates news-sitemap.xml.
6. Downloads remote images into assets/news/ when possible.
7. Keeps the generated pages independent/static.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


# ============================================================
# CONFIGURATION
# ============================================================

SHEET_ID = "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg"
SHEET_NAME = "Bangla News"

BASE_URL = "https://abdurrazzak123.github.io/Banglasangbad/"

ROOT = Path(__file__).resolve().parents[1]
NEWS_DIR = ROOT / "news"
NEWS_ASSETS_DIR = ROOT / "assets" / "news"

NEWS_JSON = ROOT / "news-data.json"
SITEMAP_XML = ROOT / "sitemap.xml"
NEWS_SITEMAP_XML = ROOT / "news-sitemap.xml"


# ============================================================
# GOOGLE SHEET
# ============================================================

EXPECTED_COLUMNS = [
    "ID",
    "Category",
    "Headline",
    "Details",
    "Image-1",
    "Date",
    "Video",
    "Image-2",
    "Image-3",
    "Keyword",
]


def sheet_url() -> str:
    params = {
        "tqx": "out:json",
        "sheet": SHEET_NAME,
        "tq": "select *",
    }

    return (
        "https://docs.google.com/spreadsheets/d/"
        + SHEET_ID
        + "/gviz/tq?"
        + urllib.parse.urlencode(params)
    )


def fetch_google_sheet() -> dict[str, Any]:
    request = urllib.request.Request(
        sheet_url(),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/plain,text/html,application/xhtml+xml",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8", errors="replace")

    # Google returns:
    # google.visualization.Query.setResponse({...});
    match = re.search(
        r"google\.visualization\.Query\.setResponse\((.*)\)\s*;?\s*$",
        raw,
        flags=re.DOTALL,
    )

    if not match:
        raise RuntimeError(
            "Google Sheet response could not be parsed. "
            "Make sure the sheet is public/published."
        )

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Google Sheet returned invalid JSON."
        ) from exc


# ============================================================
# HELPERS
# ============================================================

def clean_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        if "formattedValue" in value:
            value = value["formattedValue"]
        elif "v" in value:
            value = value["v"]
        else:
            value = ""

    return str(value).strip()


def safe_id(value: str) -> str:
    value = clean_text(value)

    # Keep normal numeric/alphanumeric IDs.
    # Also allow Bengali characters.
    value = re.sub(r"[^\w\u0980-\u09FF-]+", "-", value, flags=re.UNICODE)
    value = value.strip("-_")

    return value


def normalize_url(value: str) -> str:
    value = clean_text(value)

    if not value:
        return ""

    if value.startswith("//"):
        return "https:" + value

    return value


def is_remote_url(value: str) -> bool:
    value = normalize_url(value)
    return value.startswith("http://") or value.startswith("https://")


def is_youtube_url(url: str) -> bool:
    url = normalize_url(url).lower()

    return (
        "youtube.com/" in url
        or "youtu.be/" in url
        or "youtube-nocookie.com/" in url
    )


def youtube_embed_url(url: str) -> str:
    url = normalize_url(url)

    parsed = urllib.parse.urlparse(url)

    # youtu.be/VIDEO_ID
    if parsed.netloc.lower() in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

    # youtube.com/watch?v=VIDEO_ID
    query = urllib.parse.parse_qs(parsed.query)

    if query.get("v"):
        video_id = query["v"][0]
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

    # youtube.com/embed/VIDEO_ID
    match = re.search(r"/embed/([^/?&]+)", parsed.path)

    if match:
        return f"https://www.youtube.com/embed/{match.group(1)}"

    return url


def parse_date(value: str) -> str:
    """
    Convert common Google Sheet dates into a useful ISO-ish value.

    If parsing is impossible, preserve the original value.
    """

    value = clean_text(value)

    if not value:
        return ""

    # Already ISO-like
    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.isoformat()
        except ValueError:
            continue

    return value


def date_for_display(value: str) -> str:
    value = clean_text(value)

    if not value:
        return ""

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%d %B %Y")
        except ValueError:
            continue

    return value


def xml_escape(value: str) -> str:
    return html.escape(clean_text(value), quote=True)


def make_absolute_url(path_or_url: str) -> str:
    value = normalize_url(path_or_url)

    if not value:
        return ""

    if value.startswith("http://") or value.startswith("https://"):
        return value

    return urllib.parse.urljoin(BASE_URL, value.lstrip("/"))


# ============================================================
# GOOGLE SHEET ROW PARSING
# ============================================================

def get_cell_value(cell: Any) -> str:
    if cell is None:
        return ""

    if isinstance(cell, dict):
        if "formattedValue" in cell:
            return clean_text(cell["formattedValue"])

        if "v" in cell:
            return clean_text(cell["v"])

    return clean_text(cell)


def parse_gviz_table(data: dict[str, Any]) -> list[dict[str, str]]:
    table = data.get("table")

    if not isinstance(table, dict):
        raise RuntimeError("Google Sheet response does not contain a table.")

    cols = table.get("cols", [])
    rows = table.get("rows", [])

    headers: list[str] = []

    for col in cols:
        label = clean_text(col.get("label", ""))

        if not label:
            label = clean_text(col.get("id", ""))

        headers.append(label)

    # Sometimes labels are missing. Use the exact expected order.
    if len(headers) < len(EXPECTED_COLUMNS):
        headers = EXPECTED_COLUMNS[: len(cols)]

    # Normalize header names
    normalized_headers = []

    for index, header in enumerate(headers):
        header = header.strip()

        if not header and index < len(EXPECTED_COLUMNS):
            header = EXPECTED_COLUMNS[index]

        normalized_headers.append(header)

    # If the Google Sheet labels don't match, map by position.
    use_expected_headers = False

    if len(normalized_headers) >= len(EXPECTED_COLUMNS):
        first_ten = normalized_headers[:10]

        if first_ten != EXPECTED_COLUMNS:
            use_expected_headers = True

    if use_expected_headers:
        normalized_headers = EXPECTED_COLUMNS[: len(normalized_headers)]

    articles: list[dict[str, str]] = []

    for row in rows:
        cells = row.get("c", []) if isinstance(row, dict) else []

        values: list[str] = []

        for index in range(max(len(cells), len(EXPECTED_COLUMNS))):
            cell = cells[index] if index < len(cells) else None
            values.append(get_cell_value(cell))

        article: dict[str, str] = {}

        for index, column in enumerate(EXPECTED_COLUMNS):
            article[column] = values[index] if index < len(values) else ""

        # Ignore completely empty rows
        if not any(article.values()):
            continue

        articles.append(article)

    return articles


# ============================================================
# IMAGE HANDLING
# ============================================================

def image_extension(url: str, content_type: str = "") -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()

    for extension in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]:
        if path.endswith(extension):
            return extension

    content_type = content_type.lower()

    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }

    return mapping.get(content_type, ".jpg")


def download_image(url: str, destination: Path) -> bool:
    """
    Download an image into assets/news.

    If downloading fails, the original remote URL is kept in the
    generated page instead.
    """

    url = normalize_url(url)

    if not is_remote_url(url):
        return False

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()

        if not data:
            return False

        extension = image_extension(url, content_type)

        final_destination = destination.with_suffix(extension)

        final_destination.parent.mkdir(parents=True, exist_ok=True)
        final_destination.write_bytes(data)

        return True

    except Exception as exc:
        print(f"Image download skipped: {url} ({exc})")
        return False


def prepare_image(
    url: str,
    article_id: str,
    image_number: int,
) -> str:
    """
    Returns a URL suitable for the website.

    Remote image:
        tries to save locally as assets/news/{id}-{number}.ext

    Local/relative image:
        returns it unchanged.

    Failed remote download:
        returns original remote URL.
    """

    url = normalize_url(url)

    if not url:
        return ""

    if not is_remote_url(url):
        return url

    destination = (
        NEWS_ASSETS_DIR
        / f"{article_id}-{image_number}"
    )

    if download_image(url, destination):
        # Find the actual extension created.
        candidates = list(
            NEWS_ASSETS_DIR.glob(
                f"{article_id}-{image_number}.*"
            )
        )

        if candidates:
            relative = candidates[0].relative_to(ROOT)
            return "/" + relative.as_posix()

    return url


# ============================================================
# NEWS PAGE HTML
# ============================================================

PAGE_CSS = """
<style>
.news-detail-page {
    max-width: 1100px;
    margin: 30px auto;
    padding: 0 18px 50px;
    box-sizing: border-box;
}

.news-detail-card {
    background: #fff;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,.08);
}

.news-detail-category {
    display: inline-block;
    margin-bottom: 12px;
    padding: 6px 12px;
    border-radius: 20px;
    background: #eaf3ff;
    color: #1769aa;
    font-size: 14px;
    font-weight: 700;
}

.news-detail-title {
    margin: 0 0 12px;
    font-size: clamp(28px, 4vw, 44px);
    line-height: 1.35;
}

.news-detail-date {
    color: #777;
    font-size: 14px;
    margin-bottom: 22px;
}

.news-detail-main-image {
    width: 100%;
    max-height: 650px;
    object-fit: cover;
    border-radius: 12px;
    display: block;
    margin: 0 auto 25px;
}

.news-detail-text {
    font-size: 18px;
    line-height: 1.9;
    color: #222;
    white-space: normal;
    word-break: break-word;
}

.news-detail-text p {
    margin: 0 0 18px;
}

.news-detail-gallery {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin-top: 25px;
}

.news-detail-gallery img {
    width: 100%;
    border-radius: 10px;
    display: block;
}

.news-detail-video {
    margin-top: 25px;
}

.news-detail-video iframe,
.news-detail-video video {
    width: 100%;
    min-height: 400px;
    border: 0;
    border-radius: 12px;
}

.news-detail-keywords {
    margin-top: 25px;
    color: #666;
    font-size: 14px;
}

@media (max-width: 700px) {
    .news-detail-card {
        padding: 17px;
    }

    .news-detail-text {
        font-size: 17px;
        line-height: 1.8;
    }

    .news-detail-gallery {
        grid-template-columns: 1fr;
    }

    .news-detail-video iframe,
    .news-detail-video video {
        min-height: 230px;
    }
}
</style>
"""


def details_to_html(details: str) -> str:
    """
    Preserve paragraph breaks from Google Sheet.
    """

    details = clean_text(details)

    if not details:
        return ""

    escaped = html.escape(details)

    paragraphs = re.split(r"\n\s*\n|\r\n\s*\r\n", escaped)

    result = []

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        paragraph = paragraph.replace("\n", "<br>\n")
        result.append(f"<p>{paragraph}</p>")

    return "\n".join(result)


def build_video_html(video_url: str) -> str:
    video_url = normalize_url(video_url)

    if not video_url:
        return ""

    if is_youtube_url(video_url):
        embed = youtube_embed_url(video_url)

        return f"""
        <div class="news-detail-video">
            <iframe
                src="{html.escape(embed, quote=True)}"
                title="News video"
                loading="lazy"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowfullscreen>
            </iframe>
        </div>
        """

    # Direct video file
    if re.search(
        r"\.(mp4|webm|ogg)(\?.*)?$",
        video_url,
        flags=re.IGNORECASE,
    ):
        return f"""
        <div class="news-detail-video">
            <video controls preload="metadata">
                <source src="{html.escape(video_url, quote=True)}">
                Your browser does not support the video tag.
            </video>
        </div>
        """

    # Generic video URL
    return f"""
    <div class="news-detail-video">
        <p>
            <a href="{html.escape(video_url, quote=True)}"
               target="_blank"
               rel="noopener">
                ভিডিও দেখুন
            </a>
        </p>
    </div>
    """


def build_gallery_html(images: list[str]) -> str:
    images = [image for image in images if image]

    if not images:
        return ""

    if len(images) == 1:
        return ""

    items = []

    for image in images[1:]:
        absolute = make_absolute_url(image)

        items.append(
            f"""
            <img
                src="{html.escape(absolute, quote=True)}"
                alt="সংবাদ ছবি"
                loading="lazy"
            >
            """
        )

    return f"""
    <div class="news-detail-gallery">
        {"".join(items)}
    </div>
    """


def build_json_ld(article: dict[str, str], main_image: str) -> str:
    article_id = article["ID"]
    headline = article["Headline"]
    details = article["Details"]
    category = article["Category"]
    date_value = article["Date"]

    page_url = make_absolute_url(f"news/{article_id}.html")
    image_url = make_absolute_url(main_image)

    iso_date = parse_date(date_value)

    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": page_url,
        },
        "headline": headline,
        "articleSection": category,
        "description": re.sub(
            r"\s+",
            " ",
            details,
        )[:300],
        "url": page_url,
    }

    if image_url:
        data["image"] = [image_url]

    if iso_date:
        data["datePublished"] = iso_date
        data["dateModified"] = iso_date

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )


def build_news_page(article: dict[str, str]) -> str:
    article_id = safe_id(article["ID"])

    category = article["Category"]
    headline = article["Headline"]
    details = article["Details"]
    date_value = article["Date"]
    keyword = article["Keyword"]
    video = article["Video"]

    images = [
        article["Image-1"],
        article["Image-2"],
        article["Image-3"],
    ]

    main_image = images[0]

    title = headline or "বাংলা সংবাদ"
    description = re.sub(r"\s+", " ", details).strip()

    if len(description) > 160:
        description = description[:157] + "..."

    canonical_url = make_absolute_url(
        f"news/{article_id}.html"
    )

    display_date = date_for_display(date_value)

    image_tags = ""

    if main_image:
        absolute_image = make_absolute_url(main_image)

        image_tags = f"""
        <img
            class="news-detail-main-image"
            src="{html.escape(absolute_image, quote=True)}"
            alt="{html.escape(headline, quote=True)}"
            loading="eager"
        >
        """

    details_html = details_to_html(details)

    gallery_html = build_gallery_html(images)

    video_html = build_video_html(video)

    keywords_meta = html.escape(keyword, quote=True)

    json_ld = build_json_ld(
        article,
        main_image,
    )

    return f"""<!doctype html>
<html lang="bn">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>{html.escape(title)} | বাংলা সংবাদ</title>

    <meta
        name="description"
        content="{html.escape(description, quote=True)}"
    >

    <meta
        name="keywords"
        content="{keywords_meta}"
    >

    <link
        rel="canonical"
        href="{html.escape(canonical_url, quote=True)}"
    >

    <!-- Open Graph -->
    <meta property="og:type" content="article">

    <meta
        property="og:title"
        content="{html.escape(title, quote=True)}"
    >

    <meta
        property="og:description"
        content="{html.escape(description, quote=True)}"
    >

    <meta
        property="og:url"
        content="{html.escape(canonical_url, quote=True)}"
    >
    {
        f'<meta property="og:image" content="{html.escape(make_absolute_url(main_image), quote=True)}">'
        if main_image
        else ""
    }

    <!-- Twitter -->
    <meta
        name="twitter:card"
        content="summary_large_image"
    >

    <meta
        name="twitter:title"
        content="{html.escape(title, quote=True)}"
    >

    <meta
        name="twitter:description"
        content="{html.escape(description, quote=True)}"
    >
    {
        f'<meta name="twitter:image" content="{html.escape(make_absolute_url(main_image), quote=True)}">'
