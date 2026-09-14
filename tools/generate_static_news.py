from __future__ import annotations

import csv
import html
import io
import json
import re
import shutil
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from news_assets import process_news_images


# ============================================================
# CONFIG
# ============================================================

SHEET_ID = "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg"
SHEET_NAME = "Bangla News"

BASE_URL = "https://abdurrazzak123.github.io/Banglasangbad/"

ROOT = Path(__file__).resolve().parents[1]

NEWS_DIR = ROOT / "news"
ASSETS_DIR = ROOT / "assets" / "news"

NEWS_DATA_FILE = ROOT / "news-data.json"
ADS_DATA_FILE = ROOT / "ads-data.json"

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


# ============================================================
# HELPERS
# ============================================================

def clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def esc(value) -> str:
    return html.escape(clean(value), quote=True)


def safe_id(value) -> str:
    value = clean(value)
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-_") or "news"


def fetch_sheet() -> list[dict[str, str]]:

    encoded_sheet = urllib.parse.quote(SHEET_NAME)

    url = (
        f"https://docs.google.com/spreadsheets/d/"
        f"{SHEET_ID}/gviz/tq"
        f"?sheet={encoded_sheet}"
        f"&tqx=out:csv"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8-sig")

    reader = csv.reader(io.StringIO(raw))

    rows = list(reader)

    if not rows:
        return []

    header = [
        clean(x)
        for x in rows[0]
    ]

    # Google Sheet-এর column order ঠিক রাখতে
    # প্রথম ১০টি expected column নেওয়া হবে।
    if header[:10] != EXPECTED_COLUMNS:
        print("Warning: Sheet header differs from expected order.")

    news = []

    for row in rows[1:]:

        values = list(row)

        while len(values) < len(EXPECTED_COLUMNS):
            values.append("")

        item = {}

        for index, column in enumerate(EXPECTED_COLUMNS):
            item[column] = clean(values[index])

        if not item["ID"]:
            continue

        news.append(item)

    return news


def normalize_news(items):

    result = []

    for item in items:

        news_id = safe_id(item.get("ID"))

        if not news_id:
            continue

        result.append(
            {
                "id": news_id,
                "category": clean(item.get("Category")),
                "headline": clean(item.get("Headline")),
                "details": clean(item.get("Details")),
                "date": clean(item.get("Date")),
                "video": clean(item.get("Video")),
                "keyword": clean(item.get("Keyword")),
                "image_urls": [
                    clean(item.get("Image-1")),
                    clean(item.get("Image-2")),
                    clean(item.get("Image-3")),
                ],
            }
        )

    return result


def format_date(value):

    value = clean(value)

    if not value:
        return ""

    return value


def first_image(images):

    for image in images:
        if image:
            return image

    return ""


def image_src(path: str) -> str:

    if not path:
        return ""

    if path.startswith("http://") or path.startswith("https://"):
        return path

    return "../" + path.lstrip("/")


def absolute_image(path: str) -> str:

    if not path:
        return ""

    if path.startswith("http://") or path.startswith("https://"):
        return path

    return BASE_URL.rstrip("/") + "/" + path.lstrip("/")


def youtube_embed(url):

    url = clean(url)

    if not url:
        return ""

    match = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]+)",
        url,
    )

    if not match:
        return ""

    video_id = match.group(1)

    return (
        '<div class="video-box">'
        f'<iframe src="https://www.youtube.com/embed/{esc(video_id)}" '
        'title="YouTube video" '
        'allowfullscreen></iframe>'
        '</div>'
    )


def video_block(url):

    url = clean(url)

    if not url:
        return ""

    youtube = youtube_embed(url)

    if youtube:
        return youtube

    if url.lower().endswith(
        (".mp4", ".webm", ".ogg", ".mov")
    ):
        return (
            '<div class="video-box">'
            f'<video controls preload="metadata" src="{esc(url)}"></video>'
            '</div>'
        )

    return (
        '<div class="video-link">'
        f'<a href="{esc(url)}" target="_blank" rel="noopener">'
        "ভিডিও দেখুন"
        "</a>"
        "</div>"
    )


# ============================================================
# FINAL DESIGN CSS
# ============================================================

STYLE = r"""
*{
    box-sizing:border-box;
}

html{
    scroll-behavior:smooth;
}

body{
    margin:0;
    background:#f4f4f4;
    color:#222;
    font-family:
        "Noto Sans Bengali",
        "SolaimanLipi",
        Arial,
        sans-serif;
    line-height:1.75;
}

a{
    text-decoration:none;
}

.top-bar{
    background:#111;
    color:#fff;
    padding:7px 0;
    font-size:14px;
}

.header-inner{
    max-width:1200px;
    margin:auto;
    padding:0 15px;
}

.site-header{
    background:#fff;
    border-bottom:1px solid #ddd;
}

.logo{
    font-size:30px;
    font-weight:800;
    color:#d60000;
    padding:14px 0;
}

.date-box{
    font-size:14px;
    color:#555;
}

.nav{
    background:#b40000;
}

.nav-inner{
    max-width:1200px;
    margin:auto;
    display:flex;
    flex-wrap:wrap;
    padding:0 15px;
}

.nav a{
    color:#fff;
    padding:10px 15px;
    font-weight:700;
}

.nav a:hover{
    background:#8d0000;
}

.breaking{
    background:#e60000;
    color:#fff;
    display:flex;
    align-items:center;
    overflow:hidden;
}

.breaking-title{
    background:#9e0000;
    padding:8px 15px;
    font-weight:800;
    white-space:nowrap;
}

.breaking-text{
    padding:8px 15px;
    white-space:nowrap;
    overflow:hidden;
}

.container{
    max-width:1200px;
    margin:25px auto;
    padding:0 15px;
}

main.container{
    display:grid;
    grid-template-columns:2.2fr 1fr;
    gap:25px;
}

.main-content{
    min-width:0;
}

.side-news{
    background:#fff;
    border:1px solid #ddd;
    padding:15px;
}

.side-news h2{
    margin:0 0 12px;
    color:#b40000;
    font-size:22px;
    border-bottom:2px solid #b40000;
    padding-bottom:8px;
}

.latest-link{
    display:block;
    color:#222;
    border-bottom:1px solid #ddd;
    padding:10px 0;
    font-weight:600;
}

.latest-link:hover{
    color:#d00000;
}

.news-title{
    background:#fff;
    padding:20px;
    border-bottom:3px solid #d00000;
    margin-bottom:15px;
}

.news-title h1{
    margin:0 0 10px;
    font-size:34px;
    line-height:1.4;
}

.news-meta{
    color:#777;
    font-size:14px;
}

.news-body{
    background:#fff;
    padding:20px;
}

.news-image-top{
    width:100%;
    margin-bottom:20px;
}

.news-image-top img{
    width:100%;
    height:auto;
    display:block;
    border-radius:4px;
}

.news-text-bottom{
    font-size:18px;
}

.news-text-bottom p{
    margin:0 0 18px;
}

.news-gallery{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:12px;
    margin:20px 0;
}

.news-gallery img{
    width:100%;
    display:block;
    border-radius:5px;
}

.video-box{
    margin:20px 0;
    position:relative;
    width:100%;
    aspect-ratio:16/9;
}

.video-box iframe,
.video-box video{
    width:100%;
    height:100%;
    border:0;
}

.share-box{
    margin-top:25px;
    padding-top:18px;
    border-top:1px solid #ddd;
}

.share-box strong{
    display:block;
    margin-bottom:10px;
}

.share-buttons{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
}

.share-btn{
    display:inline-block;
    padding:8px 13px;
    background:#eee;
    color:#111;
    border-radius:4px;
    font-weight:700;
    font-size:14px;
}

.share-btn:hover{
    opacity:.85;
}

.read-more-btn{
    display:inline-block;
    margin-top:10px;
    background:#c40000;
    color:#fff;
    padding:8px 15px;
    border-radius:4px;
    font-weight:700;
}

.news-grid{
    display:grid;
    grid-template-columns:repeat(2,1fr);
    gap:18px;
    margin-top:25px;
}

.news-card{
    background:#fff;
    border:1px solid #ddd;
    overflow:hidden;
}

.news-card img{
    width:100%;
    aspect-ratio:16/9;
    object-fit:cover;
    display:block;
}

.news-card-content{
    padding:13px;
}

.news-card-content h3{
    margin:0 0 8px;
    font-size:18px;
    line-height:1.5;
}

.category{
    color:#d00000;
    font-size:13px;
    font-weight:800;
}

.footer,
.site-footer{
    background:#111;
    color:#fff;
    text-align:center;
    padding:25px 15px;
    margin-top:30px;
}

.social-links{
    display:flex;
    justify-content:center;
    gap:10px;
    flex-wrap:wrap;
    margin-top:12px;
}

.social-links a{
    color:#fff;
    padding:7px 12px;
    border:1px solid #555;
    border-radius:4px;
}

@media(max-width:800px){

    main.container{
        display:block;
    }

    .side-news{
        margin-top:20px;
    }

    .news-title h1{
        font-size:27px;
    }

    .news-grid{
        grid-template-columns:1fr;
    }

    .news-gallery{
        grid-template-columns:1fr;
    }

    .nav-inner{
        overflow-x:auto;
        flex-wrap:nowrap;
    }

    .nav a{
        white-space:nowrap;
    }
}

@media(max-width:500px){

    .logo{
        font-size:25px;
    }

    .news-body,
    .news-title{
        padding:15px;
    }

    .news-text-bottom{
        font-size:17px;
    }
}
"""


# ============================================================
# HTML
# ============================================================

def social_links(item):

    page_url = (
        BASE_URL.rstrip("/")
        + "/news/"
        + urllib.parse.quote(item["id"])
        + ".html"
    )

    encoded_url = urllib.parse.quote(page_url, safe="")

    facebook = (
        "https://www.facebook.com/sharer/sharer.php?u="
        + encoded_url
    )

    twitter = (
        "https://twitter.com/intent/tweet?url="
        + encoded_url
        + "&text="
        + urllib.parse.quote(item["headline"])
    )

    whatsapp = (
        "https://api.whatsapp.com/send?text="
        + urllib.parse.quote(
            item["headline"] + " " + page_url
        )
    )

    youtube = item.get("video", "")

    return f"""
<div class="share-box">
    <strong>শেয়ার করুন</strong>

    <div class="share-buttons">

        <a class="share-btn"
           href="{esc(facebook)}"
           target="_blank"
           rel="noopener">
           Facebook
        </a>

        <a class="share-btn"
           href="{esc(twitter)}"
           target="_blank"
           rel="noopener">
           X / Twitter
        </a>

        <a class="share-btn"
           href="{esc(whatsapp)}"
           target="_blank"
           rel="noopener">
           WhatsApp
        </a>

        <button class="share-btn"
                type="button"
                onclick="shareNews()">
                Share
        </button>

        <a class="share-btn"
           href="https://www.youtube.com/"
           target="_blank"
           rel="noopener">
           YouTube
        </a>

        <a class="share-btn"
           href="https://www.tiktok.com/"
           target="_blank"
           rel="noopener">
           TikTok
        </a>

    </div>
</div>

<script>
function shareNews(){

    const data = {
        title: {json.dumps(item["headline"], ensure_ascii=False)},
        text: {json.dumps(item["headline"], ensure_ascii=False)},
        url: window.location.href
    };

    if(navigator.share){
        navigator.share(data).catch(function(){});
    }else{
        navigator.clipboard.writeText(window.location.href);
        alert("নিউজের লিংক কপি হয়েছে");
    }
}
</script>
"""


def card_html(item):

    image = first_image(item.get("images", []))

    if image:
        image_tag = (
            f'<img src="{esc(image_src(image))}" '
            f'alt="{esc(item["headline"])}" '
            'loading="lazy">'
        )
    else:
        image_tag = ""

    return f"""
<article class="news-card">

    <a href="{esc(item["id"])}.html">

        {image_tag}

        <div class="news-card-content">

            <div class="category">
                {esc(item["category"])}
            </div>

            <h3>
                {esc(item["headline"])}
            </h3>

        </div>

    </a>

</article>
"""


def related_news(current, all_news):

    same_category = [
        x for x in all_news
        if x["category"] == current["category"]
    ]

    # বর্তমান নিউজ বাদ দিয়ে একই category-এর নিউজ
    same_category = [
        x for x in same_category
        if x["id"] != current["id"]
    ]

    return same_category[:6]


def latest_same_category(current, all_news):

    same_category = [
        x for x in all_news
        if x["category"] == current["category"]
        and x["id"] != current["id"]
    ]

    return same_category[:6]


def render_page(item, all_news):

    images = item.get("images", [])

    first = first_image(images)

    gallery = ""

    available_images = [
        x for x in images
        if x
    ]

    if len(available_images) > 1:

        gallery_items = []

        for image in available_images:

            gallery_items.append(
                f"""
                <img
                    src="{esc(image_src(image))}"
                    alt="{esc(item["headline"])}"
                    loading="lazy"
                >
                """
            )

        gallery = (
            '<div class="news-gallery">'
            + "".join(gallery_items)
            + "</div>"
        )

    related = related_news(
        item,
        all_news
    )

    latest = latest_same_category(
        item,
        all_news
    )

    details = item["details"]

    # Details-এর line break বজায় রাখা
    details_html = "<p>" + (
        esc(details)
        .replace("\n\n", "</p><p>")
        .replace("\n", "<br>")
    ) + "</p>"

    video = video_block(
        item.get("video", "")
    )

    if first:
        main_image = f"""
        <div class="news-image-top">
            <img
                src="{esc(image_src(first))}"
                alt="{esc(item["headline"])}"
            >
        </div>
        """
    else:
        main_image = ""

    related_html = ""

    if related:

        related_html = """
        <section>
            <div class="news-grid">
        """

        for news in related:
            related_html += card_html(news)

        related_html += """
            </div>
        </section>
        """

    latest_html = ""

    for news in latest:

        latest_html += f"""
        <a class="latest-link"
           href="{esc(news["id"])}.html">
           {esc(news["headline"])}
        </a>
        """

    canonical = (
        BASE_URL.rstrip("/")
        + "/news/"
        + urllib.parse.quote(item["id"])
        + ".html"
    )

    og_image = absolute_image(first)

    jsonld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": item["headline"],
        "datePublished": item["date"],
        "articleSection": item["category"],
        "mainEntityOfPage": canonical,
    }

    if og_image:
        jsonld["image"] = [og_image]

    return f"""<!DOCTYPE html>
<html lang="bn">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>{esc(item["headline"])} | বাংলা সংবাদ</title>

<meta name="description"
      content="{esc(item["headline"])}">

<meta name="keywords"
      content="{esc(item["keyword"])}">

<link rel="canonical"
      href="{esc(canonical)}">

<meta property="og:type"
      content="article">

<meta property="og:title"
      content="{esc(item["headline"])}">

<meta property="og:description"
      content="{esc(item["headline"])}">

<meta property="og:url"
      content="{esc(canonical)}">

<meta property="og:site_name"
      content="বাংলা সংবাদ">

{"<meta property=\"og:image\" content=\"" + esc(og_image) + "\">" if og_image else ""}

<meta name="twitter:card"
      content="summary_large_image">

<meta name="twitter:title"
      content="{esc(item["headline"])}">

{"<meta name=\"twitter:image\" content=\"" + esc(og_image) + "\">" if og_image else ""}

<script type="application/ld+json">
{json.dumps(jsonld, ensure_ascii=False, indent=2)}
</script>

<style>
{STYLE}
</style>

</head>

<body>

<div class="top-bar">
    <div class="header-inner">
        বাংলা সংবাদ — সর্বশেষ খবর
    </div>
</div>

<header class="site-header">

    <div class="header-inner">

        <div class="logo">
            বাংলা সংবাদ
        </div>

        <div class="date-box">
            {esc(item["date"])}
        </div>

    </div>

</header>

<nav class="nav">

    <div class="nav-inner">

        <a href="../index.html">হোম</a>
        <a href="../index.html">জাতীয়</a>
        <a href="../index.html">রাজনীতি</a>
        <a href="../index.html">আন্তর্জাতিক</a>
        <a href="../index.html">খেলা</a>
        <a href="../index.html">বিনোদন</a>
        <a href="../index.html">প্রযুক্তি</a>

    </div>

</nav>

<div class="breaking">

    <div class="breaking-title">
        ব্রেকিং নিউজ
    </div>

    <div class="breaking-text">
        {esc(item["headline"])}
    </div>

</div>

<main class="container">

    <section class="main-content">

        <article>

            <div class="news-title">

                <div class="category">
                    {esc(item["category"])}
                </div>

                <h1>
                    {esc(item["headline"])}
                </h1>

                <div class="news-meta">
                    {esc(item["date"])}
                </div>

            </div>

            <div class="news-body">

                {main_image}

                <div class="news-text-bottom">

                    {details_html}

                </div>

                {gallery}

                {video}

                {social_links(item)}

            </div>

        </article>

        {related_html}

    </section>

    <aside class="side-news">

        <h2>
            সর্বশেষ সংবাদ
        </h2>

        {latest_html}

    </aside>

</main>

<footer class="site-footer">

    <div>
        © বাংলা সংবাদ
    </div>

    <div class="social-links">

        <a href="https://www.facebook.com/"
           target="_blank"
           rel="noopener">
           Facebook
        </a>

        <a href="https://www.youtube.com/"
           target="_blank"
           rel="noopener">
           YouTube
        </a>

        <a href="https://www.tiktok.com/"
           target="_blank"
           rel="noopener">
           TikTok
        </a>

        <a href="https://twitter.com/"
           target="_blank"
           rel="noopener">
           X / Twitter
        </a>

    </div>

</footer>

</body>
</html>
"""


# ============================================================
# GENERATION
# ============================================================

def remove_old_generated_pages(valid_ids):

    NEWS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    valid_names = {
        f"{safe_id(x)}.html"
        for x in valid_ids
    }

    for file in NEWS_DIR.glob("*.html"):

        if file.name not in valid_names:
