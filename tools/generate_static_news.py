# tools/generate_static_news.py
# ============================================================
# Bangla Sangbad
# Google Sheet -> GitHub -> Static News Pages
# ============================================================

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests

from news_assets import process_news_images


# ============================================================
# CONFIGURATION
# ============================================================

SHEET_ID = "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg"
SHEET_NAME = "Bangla News"

BASE_URL = "https://abdurrazzak123.github.io/Banglasangbad/"

ROOT = Path(__file__).resolve().parents[1]

NEWS_DIR = ROOT / "news"
ASSETS_DIR = ROOT / "assets" / "news"

NEWS_DATA_FILE = ROOT / "news-data.json"
SITEMAP_FILE = ROOT / "sitemap.xml"
NEWS_SITEMAP_FILE = ROOT / "news-sitemap.xml"


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


USER_AGENT = (
    "Mozilla/5.0 (compatible; BanglaSangbadGenerator/1.0; "
    "+https://abdurrazzak123.github.io/Banglasangbad/)"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value) -> str:
    if value is None:
        return ""

    return str(value).strip()


def escape(value) -> str:
    return html.escape(clean(value), quote=True)


def safe_id(value) -> str:
    value = clean(value)

    if not value:
        return ""

    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value)

    return value.strip("-_")


def normalize_column_name(value) -> str:
    value = clean(value)

    value = value.replace("–", "-")
    value = value.replace("—", "-")

    return re.sub(r"\s+", " ", value).strip().lower()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ============================================================
# GOOGLE SHEET
# ============================================================

def sheet_url() -> str:
    encoded_sheet = quote(SHEET_NAME)

    return (
        f"https://docs.google.com/spreadsheets/d/"
        f"{SHEET_ID}/gviz/tq"
        f"?sheet={encoded_sheet}"
        f"&tqx=out:json"
    )


def load_google_sheet() -> list[dict]:
    print("Reading Google Sheet...")

    response = requests.get(
        sheet_url(),
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )

    response.raise_for_status()

    text = response.text.strip()

    # Google gviz normally returns:
    # google.visualization.Query.setResponse({...});
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise RuntimeError(
            "Google Sheet returned an unexpected response."
        )

    payload = json.loads(text[start:end + 1])

    table = payload.get("table", {})

    columns = table.get("cols", [])
    rows = table.get("rows", [])

    actual_columns = []

    for column in columns:
        actual_columns.append(
            clean(column.get("label"))
            or clean(column.get("id"))
        )

    normalized_actual = [
        normalize_column_name(column)
        for column in actual_columns
    ]

    normalized_expected = [
        normalize_column_name(column)
        for column in EXPECTED_COLUMNS
    ]

    # If Google does not return proper column labels,
    # use the expected order.
    if not all(
        column in normalized_actual
        for column in normalized_expected
    ):
        print("Google Sheet column labels were not complete.")
        print("Using expected 10-column order.")

        actual_columns = EXPECTED_COLUMNS[:]

    records = []

    for row in rows:
        cells = row.get("c", [])

        values = []

        for index in range(len(EXPECTED_COLUMNS)):
            if index < len(cells):
                cell = cells[index]

                if cell is None:
                    values.append("")
                else:
                    value = cell.get("f")

                    if value is None:
                        value = cell.get("v")

                    values.append(clean(value))
            else:
                values.append("")

        record = dict(
            zip(EXPECTED_COLUMNS, values)
        )

        # Skip completely empty rows.
        if not any(record.values()):
            continue

        records.append(record)

    return records


# ============================================================
# NEWS NORMALIZATION
# ============================================================

def normalize_news(rows: list[dict]) -> list[dict]:
    result = []

    used_ids = set()

    for row in rows:
        news_id = safe_id(row.get("ID"))

        if not news_id:
            continue

        # Do not allow duplicate IDs.
        if news_id in used_ids:
            print(f"Skipping duplicate ID: {news_id}")
            continue

        used_ids.add(news_id)

        item = {
            "ID": news_id,
            "Category": clean(row.get("Category")),
            "Headline": clean(row.get("Headline")),
            "Details": clean(row.get("Details")),
            "Image-1": clean(row.get("Image-1")),
            "Date": clean(row.get("Date")),
            "Video": clean(row.get("Video")),
            "Image-2": clean(row.get("Image-2")),
            "Image-3": clean(row.get("Image-3")),
            "Keyword": clean(row.get("Keyword")),
        }

        # A row without headline is not a usable news article.
        if not item["Headline"]:
            print(
                f"Skipping ID {news_id}: headline is empty."
            )
            continue

        result.append(item)

    return result


# ============================================================
# VIDEO HELPERS
# ============================================================

def youtube_id(url: str) -> str:
    url = clean(url)

    if not url:
        return ""

    patterns = [
        r"(?:youtube\.com/watch\?v=)([A-Za-z0-9_-]{6,})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{6,})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{6,})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{6,})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return ""


def video_html(video: str) -> str:
    video = clean(video)

    if not video:
        return ""

    yt_id = youtube_id(video)

    if yt_id:
        safe_yt_id = escape(yt_id)

        return f"""
<div class="news-video">
  <div class="video-wrapper">
    <iframe
      src="https://www.youtube.com/embed/{safe_yt_id}"
      title="News video"
      loading="lazy"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
      allowfullscreen>
    </iframe>
  </div>
</div>
"""

    if video.startswith(("http://", "https://")):
        safe_video = escape(video)

        return f"""
<div class="news-video">
  <video controls preload="metadata">
    <source src="{safe_video}">
    আপনার ব্রাউজার ভিডিও চালাতে পারছে না।
  </video>
</div>
"""

    return ""


# ============================================================
# IMAGE HELPERS
# ============================================================

def image_url(relative_path: str) -> str:
    relative_path = clean(relative_path)

    if not relative_path:
        return ""

    return BASE_URL.rstrip("/") + "/" + relative_path.lstrip("/")


def first_image(images: list[str]) -> str:
    for image in images:
        if image:
            return image

    return ""


# ============================================================
# HTML
# ============================================================

def render_news_html(
    item: dict,
    images: list[str],
) -> str:
    news_id = escape(item["ID"])
    category = escape(item["Category"])
    headline = escape(item["Headline"])
    details = escape(item["Details"])
    date = escape(item["Date"])
    keyword = escape(item["Keyword"])

    main_image = first_image(images)

    if main_image:
        main_image_html = f"""
<img
  src="../{escape(main_image)}"
  alt="{headline}"
  loading="eager"
  decoding="async"
>
"""
    else:
        main_image_html = """
<div class="no-image">
  ছবি পাওয়া যায়নি
</div>
"""

    extra_images_html = ""

    for index, image in enumerate(images[1:], start=2):
        if not image:
            continue

        extra_images_html += f"""
<figure class="news-extra-image">
  <img
    src="../{escape(image)}"
    alt="{headline} - ছবি {index}"
    loading="lazy"
    decoding="async"
  >
</figure>
"""

    video = video_html(item["Video"])

    canonical = (
        BASE_URL.rstrip("/")
        + "/news/"
        + quote(item["ID"])
        + ".html"
    )

    json_ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": item["Headline"],
        "datePublished": item["Date"],
        "dateModified": item["Date"],
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical,
        },
        "url": canonical,
        "articleSection": item["Category"],
        "keywords": item["Keyword"],
    }

    if main_image:
        json_ld["image"] = [image_url(main_image)]

    json_ld_text = json.dumps(
        json_ld,
        ensure_ascii=False,
        indent=2,
    )

    return f"""<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">

<meta
  name="viewport"
  content="width=device-width, initial-scale=1.0"
>

<title>{headline} | বাংলা সংবাদ</title>

<meta
  name="description"
  content="{headline}"
>

<meta
  name="keywords"
  content="{keyword}"
>

<link
  rel="canonical"
  href="{escape(canonical)}"
>

<meta
  property="og:type"
  content="article"
>

<meta
  property="og:title"
  content="{headline}"
>

<meta
  property="og:description"
  content="{headline}"
>

<meta
  property="og:url"
  content="{escape(canonical)}"
>

<meta
  property="og:site_name"
  content="বাংলা সংবাদ"
>
{"<meta property=\"og:image\" content=\"" + escape(image_url(main_image)) + "\">" if main_image else ""}

<meta
  name="twitter:card"
  content="summary_large_image"
>

<meta
  name="twitter:title"
  content="{headline}"
>

<meta
  name="twitter:description"
  content="{headline}"
>
{"<meta name=\"twitter:image\" content=\"" + escape(image_url(main_image)) + "\">" if main_image else ""}

<script type="application/ld+json">
{json_ld_text}
</script>

<style>
* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  padding: 0;
  background: #f5f5f5;
  color: #222;
  font-family:
    Arial,
    "Noto Sans Bengali",
    "SolaimanLipi",
    sans-serif;
}}

.news-page {{
  max-width: 900px;
  margin: 30px auto;
  padding: 0 16px 50px;
}}

.news-card {{
  background: #ffffff;
  border-radius: 12px;
  padding: 22px;
  box-shadow: 0 2px 12px rgba(0,0,0,.08);
}}

.news-category {{
  display: inline-block;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 700;
  color: #c62828;
}}

.news-title {{
  margin: 0 0 12px;
  font-size: 32px;
  line-height: 1.35;
}}

.news-date {{
  color: #777;
  font-size: 14px;
  margin-bottom: 20px;
}}

.news-main-image img,
.news-extra-image img {{
  display: block;
  width: 100%;
  height: auto;
  border-radius: 10px;
}}

.news-main-image {{
  margin-bottom: 20px;
}}

.news-extra-image {{
  margin: 25px 0;
}}

.news-details {{
  font-size: 18px;
  line-height: 1.9;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}}

.news-video {{
  margin: 25px 0;
}}

.video-wrapper {{
  position: relative;
  width: 100%;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
  border-radius: 10px;
}}

.video-wrapper iframe {{
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
}}

.news-video video {{
  width: 100%;
  max-height: 600px;
  border-radius: 10px;
}}

.no-image {{
  background: #eeeeee;
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #777;
}}

.back-home {{
  display: inline-block;
  margin-top: 20px;
  text-decoration: none;
  font-weight: 700;
  color: #c62828;
}}

@media (max-width: 650px) {{
  .news-page {{
    margin: 12px auto;
  }}

  .news-card {{
    padding: 15px;
  }}

  .news-title {{
    font-size: 25px;
  }}

  .news-details {{
    font-size: 17px;
  }}
}}
</style>

</head>

<body>

<main class="news-page">

  <article class="news-card">

    <div class="news-category">
      {category}
    </div>

    <h1 class="news-title">
      {headline}
    </h1>

    <div class="news-date">
      {date}
    </div>

    <div class="news-main-image">
      {main_image_html}
    </div>

    {video}

    <div class="news-details">
      {details}
    </div>

    {extra_images_html}

    <a
      class="back-home"
      href="../index.html"
    >
      ← মূল পাতায় ফিরে যান
    </a>

  </article>

</main>

</body>
</html>
"""


# ============================================================
# NEWS DATA JSON
# ============================================================

def build_news_data(
    items: list[dict],
    processed_images: dict[str, list[str]],
) -> dict:
    rows = []

    for item in items:
        news_id = item["ID"]

        images = processed_images.get(
            news_id,
            ["", "", ""],
        )

        row = dict(item)

        # Keep the original Sheet values.
        # Add local image paths separately.
        row["images"] = images

        # Useful direct detail URL.
        row["url"] = (
            BASE_URL.rstrip("/")
            + "/news/"
            + quote(news_id)
            + ".html"
        )

        rows.append(row)

    return {
        "generatedAt": now_iso(),
        "sheetId": SHEET_ID,
        "sheetName": SHEET_NAME,
        "columns": EXPECTED_COLUMNS,
        "table": {
            "cols": [
                {"id": column, "label": column}
                for column in EXPECTED_COLUMNS
            ],
            "rows": [
                {
                    "c": [
                        {"v": row.get(column, "")}
                        for column in EXPECTED_COLUMNS
                    ]
                }
                for row in rows
            ],
        },
        "news": rows,
    }


def write_news_data(
    items: list[dict],
    processed_images: dict[str, list[str]],
):
    payload = build_news_data(
        items,
        processed_images,
    )

    NEWS_DATA_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Created {NEWS_DATA_FILE.name} "
        f"with {len(items)} news items."
    )


# ============================================================
# STATIC NEWS PAGES
# ============================================================

def generate_news_pages(
    items: list[dict],
    processed_images: dict[str, list[str]],
):
    NEWS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated_ids = set()

    for item in items:
        news_id = item["ID"]

        images = processed_images.get(
            news_id,
            ["", "", ""],
        )

        content = render_news_html(
            item,
            images,
        )

        target = NEWS_DIR / f"{news_id}.html"

        target.write_text(
            content,
            encoding="utf-8",
        )

        generated_ids.add(news_id)

    # Remove old generated numeric/slug pages
    # that no longer exist in Google Sheet.
    for existing in NEWS_DIR.glob("*.html"):
        existing_id = existing.stem

        if existing_id not in generated_ids:
            try:
                existing.unlink()
            except Exception:
                pass

    print(
        f"Generated {len(generated_ids)} static news pages."
    )


# ============================================================
# SITEMAP
# ============================================================

def xml_escape(value: str) -> str:
    return (
        clean(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def write_sitemap(items: list[dict]):
    urls = [
        f"""  <url>
    <loc>{xml_escape(BASE_URL)}</loc>
  </url>"""
    ]

    for item in items:
        news_id = item["ID"]

        url = (
            BASE_URL.rstrip("/")
            + "/news/"
            + quote(news_id)
            + ".html"
        )

        urls.append(
            f"""  <url>
    <loc>{xml_escape(url)}</loc>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>"""
        )

    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset
  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
>
""" + "\n".join(urls) + """
</urlset>
"""

    SITEMAP_FILE.write_text(
        sitemap,
        encoding="utf-8",
    )

    print("Created sitemap.xml")


def write_news_sitemap(items: list[dict]):
    urls = []

    for item in items:
        news_id = item["ID"]

        url = (
            BASE_URL.rstrip("/")
            + "/news/"
            + quote(news_id)
            + ".html"
        )

        headline = xml_escape(item["Headline"])

        publication_date = clean(item["Date"])

        urls.append(
            f"""  <url>
    <loc>{xml_escape(url)}</loc>
    <news:news>
      <news:publication>
        <news:name>বাংলা সংবাদ</news:name>
        <news:language>bn</news:language>
      </news:publication>
      <news:publication_date>{xml_escape(publication_date)}</news:publication_date>
      <news:title>{headline}</news:title>
    </news:news>
  </url>"""
        )

    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset
  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
  xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"
>
""" + "\n".join(urls) + """
</urlset>
"""

    NEWS_SITEMAP_FILE.write_text(
        sitemap,
        encoding="utf-8",
    )

    print("Created news-sitemap.xml")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("Bangla Sangbad - Google Sheet News Generator")
    print("=" * 60)

    NEWS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ASSETS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 1. Read Google Sheet.
    raw_rows = load_google_sheet()

    print(
        f"Google Sheet rows received: {len(raw_rows)}"
    )

    # 2. Normalize.
    items = normalize_news(raw_rows)

    print(
        f"Usable news items: {len(items)}"
    )

    # 3. Download media.
    processed_images = {}

    session = requests.Session()

    for item in items:
        news_id = item["ID"]

        print(
            f"Processing images for news ID: {news_id}"
        )

        images = process_news_images(
            news_id=news_id,
            image_urls=[
                item["Image-1"],
                item["Image-2"],
                item["Image-3"],
            ],
            assets_dir=ASSETS_DIR,
            session=session,
        )

        processed_images[news_id] = images

    # 4. Generate static detail pages.
    generate_news_pages(
        items,
        processed_images,
    )

    # 5. Generate news-data.json.
    write_news_data(
        items,
        processed_images,
    )

    # 6. Generate sitemap.
    write_sitemap(items)

    # 7. Generate Google News sitemap.
    write_news_sitemap(items)

    print("=" * 60)
    print("SYNC COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
