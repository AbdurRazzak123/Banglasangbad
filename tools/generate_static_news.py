# tools/generate_static_news.py
# ============================================================
# Bangla Sangbad
# Google Sheet -> Static News Generator
# ============================================================

from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from news_assets import process_news_images


# ============================================================
# CONFIG
# ============================================================

SHEET_ID = (
    "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg"
)

SHEET_NAME = "Bangla News"

BASE_URL = (
    "https://abdurrazzak123.github.io/"
    "Banglasangbad/"
)

ROOT = Path(
    __file__
).resolve().parents[1]

NEWS_DIR = ROOT / "news"

ASSETS_DIR = (
    ROOT
    / "assets"
    / "news"
)

NEWS_DATA_FILE = (
    ROOT
    / "news-data.json"
)

ADS_DATA_FILE = (
    ROOT
    / "ads-data.json"
)

SITEMAP_FILE = (
    ROOT
    / "sitemap.xml"
)

NEWS_SITEMAP_FILE = (
    ROOT
    / "news-sitemap.xml"
)


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
    "Mozilla/5.0 "
    "(compatible; "
    "BanglaSangbadGenerator/1.0)"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value) -> str:

    if value is None:
        return ""

    return str(value).strip()


def esc(value) -> str:

    return html.escape(
        clean(value),
        quote=True,
    )


def safe_id(value) -> str:

    value = clean(value)

    value = re.sub(
        r"[^A-Za-z0-9_-]+",
        "-",
        value,
    )

    value = re.sub(
        r"-+",
        "-",
        value,
    )

    value = value.strip("-_")

    return value or "news"


# ============================================================
# DATE
# ============================================================

def normalize_date(
    value: str,
) -> str:

    value = clean(value)

    if not value:

        return datetime.now().strftime(
            "%Y-%m-%d"
        )

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt,
            ).strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            continue

    return value[:10]


# ============================================================
# GOOGLE SHEET
# ============================================================

def sheet_url() -> str:

    return (
        "https://docs.google.com/"
        "spreadsheets/d/"
        + SHEET_ID
        + "/gviz/tq?"
        "tqx=out:csv&sheet="
        + quote(SHEET_NAME)
    )


def load_google_sheet() -> list[dict[str, str]]:

    request = Request(
        sheet_url(),
        headers={
            "User-Agent": USER_AGENT
        },
    )

    with urlopen(
        request,
        timeout=30,
    ) as response:

        text = response.read().decode(
            "utf-8-sig"
        )

    rows = list(
        csv.reader(
            text.splitlines()
        )
    )

    if not rows:
        return []

    header = [
        clean(x)
        for x in rows[0]
    ]

    positions = {
        name.lower(): index
        for index, name
        in enumerate(header)
    }

    missing = []

    for column in EXPECTED_COLUMNS:

        if column.lower() not in positions:
            missing.append(column)

    if missing:

        raise RuntimeError(
            "Google Sheet columns missing: "
            + ", ".join(missing)
        )

    result = []

    for raw in rows[1:]:

        item = {}

        for column in EXPECTED_COLUMNS:

            index = positions[
                column.lower()
            ]

            item[column] = (
                clean(raw[index])
                if index < len(raw)
                else ""
            )

        if (
            item["ID"]
            and item["Headline"]
        ):

            result.append(item)

    return result


# ============================================================
# NEWS DATA
# ============================================================

def normalize_news(
    rows: list[dict[str, str]]
) -> list[dict]:

    news = []

    seen = set()

    for row in rows:

        news_id = safe_id(
            row["ID"]
        )

        if not news_id:
            continue

        if news_id in seen:
            continue

        seen.add(news_id)

        news.append(
            {
                "id": news_id,
                "category": row["Category"],
                "headline": row["Headline"],
                "details": row["Details"],
                "image1": row["Image-1"],
                "date": normalize_date(
                    row["Date"]
                ),
                "video": row["Video"],
                "image2": row["Image-2"],
                "image3": row["Image-3"],
                "keyword": row["Keyword"],
                "images": [],
            }
        )

    def sort_key(item):

        value = item["id"]

        if value.isdigit():

            return (
                0,
                int(value),
            )

        return (
            1,
            value.lower(),
        )

    news.sort(
        key=sort_key,
        reverse=True,
    )

    return news


# ============================================================
# URL
# ============================================================

def abs_url(
    path: str,
) -> str:

    path = clean(path)

    if not path:
        return ""

    return (
        BASE_URL.rstrip("/")
        + "/"
        + path.lstrip("/")
    )


def page_url(
    news_id: str,
) -> str:

    return abs_url(
        "news/"
        + safe_id(news_id)
        + ".html"
    )


def first_image(
    item: dict,
) -> str:

    for image in item.get(
        "images",
        [],
    ):

        if image:
            return abs_url(image)

    return ""


# ============================================================
# VIDEO
# ============================================================

def youtube_embed(
    url: str,
) -> str:

    url = clean(url)

    if not url:
        return ""

    match = re.search(
        r"(?:youtube\.com/watch\?v=|"
        r"youtu\.be/|"
        r"youtube\.com/embed/)"
        r"([A-Za-z0-9_-]{6,})",
        url,
    )

    if not match:
        return ""

    video_id = match.group(1)

    return f"""
<div class="video-box">
<iframe
src="https://www.youtube.com/embed/{esc(video_id)}"
title="YouTube video"
loading="lazy"
allowfullscreen>
</iframe>
</div>
"""


def video_block(
    url: str,
) -> str:

    url = clean(url)

    if not url:
        return ""

    youtube = youtube_embed(url)

    if youtube:
        return youtube

    if re.match(
        r"^https?://",
        url,
        re.I,
    ):

        return f"""
<div class="video-box">
<video
controls
preload="metadata"
src="{esc(url)}">
</video>
</div>
"""

    return ""


# ============================================================
# SOCIAL SHARE
# ============================================================

def share_block(
    item: dict,
) -> str:

    url = page_url(
        item["id"]
    )

    title = item["headline"]

    facebook = (
        "https://www.facebook.com/sharer/"
        "sharer.php?"
        + urlencode(
            {"u": url}
        )
    )

    twitter = (
        "https://twitter.com/intent/tweet?"
        + urlencode(
            {
                "url": url,
                "text": title,
            }
        )
    )

    whatsapp = (
        "https://wa.me/?"
        + urlencode(
            {
                "text":
                    title
                    + " "
                    + url
            }
        )
    )

    return f"""
<div class="share-box">

<span class="share-label">
শেয়ার করুন
</span>

<div class="share-buttons">

<a
class="share-btn facebook"
target="_blank"
rel="noopener"
href="{esc(facebook)}">
Facebook
</a>

<a
class="share-btn youtube"
target="_blank"
rel="noopener"
href="https://www.youtube.com/">
YouTube
</a>

<a
class="share-btn tiktok"
target="_blank"
rel="noopener"
href="https://www.tiktok.com/">
TikTok
</a>

<a
class="share-btn twitter"
target="_blank"
rel="noopener"
href="{esc(twitter)}">
X / Twitter
</a>

<a
class="share-btn whatsapp"
target="_blank"
rel="noopener"
href="{esc(whatsapp)}">
WhatsApp
</a>

<button
class="share-btn native"
type="button"
data-share-url="{esc(url)}"
data-share-title="{esc(title)}">
Share
</button>

</div>
</div>
"""


# ============================================================
# FINAL DESIGN CSS
# ============================================================

DETAIL_CSS = r"""
*{
box-sizing:border-box;
}

html,
body{
margin:0;
padding:0;
}

body{
font-family:
Arial,
"Noto Sans Bengali",
sans-serif;
background:#f5f5f5;
color:#222;
line-height:1.7;
}

a{
text-decoration:none;
}

.container{
width:min(
1180px,
94%
);
margin:auto;
}


/* TOP BAR */

.top-bar{
background:#111;
color:#fff;
padding:7px 0;
font-size:13px;
}


/* HEADER */

.site-header{
background:#fff;
border-bottom:1px solid #ddd;
}

.header-inner{
display:flex;
align-items:center;
justify-content:space-between;
gap:20px;
padding:14px 0;
}

.logo{
font-size:28px;
font-weight:800;
color:#d40000;
}

.date-box{
font-size:14px;
color:#555;
}


/* NAV */

.nav{
background:#d40000;
color:#fff;
}

.nav-inner{
display:flex;
gap:0;
overflow-x:auto;
}

.nav-inner a{
color:#fff;
padding:11px 16px;
white-space:nowrap;
font-weight:700;
}

.nav-inner a:hover{
background:#b00000;
}


/* BREAKING */

.breaking{
background:#fff;
border-bottom:1px solid #ddd;
display:flex;
align-items:center;
}

.breaking-title{
background:#d40000;
color:#fff;
padding:8px 14px;
font-weight:800;
white-space:nowrap;
}

.breaking-text{
padding:8px 14px;
overflow:hidden;
white-space:nowrap;
}


/* MAIN */

main.container{
display:grid;
grid-template-columns:
2.2fr 1fr;
gap:24px;
margin-top:22px;
}


/* ARTICLE */

.article{
background:#fff;
padding:22px;
border:1px solid #ddd;
}

.article h1{
font-size:32px;
line-height:1.35;
margin:8px 0 10px;
}

.category{
display:inline-block;
color:#d40000;
font-weight:800;
font-size:14px;
margin-bottom:4px;
}

.meta{
color:#777;
font-size:13px;
border-bottom:1px solid #eee;
padding-bottom:12px;
margin-bottom:18px;
}

.hero-image{
width:100%;
display:block;
height:auto;
border-radius:4px;
}

.article-body{
font-size:18px;
line-height:2;
white-space:pre-line;
margin-top:18px;
}

.article-body p{
margin:0 0 16px;
}

.article-image{
width:100%;
display:block;
margin:18px 0;
border-radius:4px;
}


/* VIDEO */

.video-box{
position:relative;
width:100%;
aspect-ratio:16/9;
margin:20px 0;
background:#000;
}

.video-box iframe,
.video-box video{
width:100%;
height:100%;
border:0;
}


/* SHARE */

.share-box{
border-top:1px solid #eee;
border-bottom:1px solid #eee;
padding:15px 0;
margin:22px 0;
}

.share-label{
display:block;
font-weight:800;
margin-bottom:10px;
}

.share-buttons{
display:flex;
flex-wrap:wrap;
gap:8px;
}

.share-btn{
display:inline-block;
border:0;
cursor:pointer;
padding:8px 12px;
border-radius:4px;
color:#fff;
font-size:13px;
font-weight:700;
}

.facebook{
background:#1877f2;
}

.youtube{
background:#ff0000;
}

.tiktok{
background:#111;
}

.twitter{
background:#000;
}

.whatsapp{
background:#25d366;
}

.native{
background:#555;
}


/* SIDEBAR */

.side-news{
background:#fff;
border:1px solid #ddd;
padding:16px;
}

.side-news h2{
font-size:20px;
margin:0 0 12px;
border-bottom:2px solid #d40000;
padding-bottom:8px;
}

.latest-link{
display:block;
color:#222;
border-bottom:1px solid #eee;
padding:10px 0;
font-weight:700;
}

.latest-link:hover{
color:#d40000;
}


/* RELATED */

.related{
margin-top:24px;
}

.related h2{
font-size:22px;
border-bottom:2px solid #d40000;
padding-bottom:8px;
}

.news-grid{
display:grid;
grid-template-columns:
repeat(2,1fr);
gap:16px;
}

.news-card{
background:#fff;
border:1px solid #ddd;
overflow:hidden;
}

.news-card a{
color:#222;
}

.news-image{
width:100%;
aspect-ratio:16/9;
object-fit:cover;
display:block;
}

.news-card-content{
padding:12px;
}

.news-card-content h3{
font-size:17px;
line-height:1.45;
margin:4px 0 0;
}


/* FOOTER */

.footer,
.site-footer{
background:#111;
color:#ddd;
text-align:center;
padding:24px 10px;
margin-top:30px;
}


/* MOBILE */

@media(max-width:800px){

main.container{
grid-template-columns:1fr;
}

.article h1{
font-size:25px;
}

.article-body{
font-size:17px;
}

.news-grid{
grid-template-columns:
1fr 1fr;
}

}


@media(max-width:520px){

.header-inner{
display:block;
}

.date-box{
margin-top:5px;
}

.news-grid{
grid-template-columns:1fr;
}

.article{
padding:15px;
}

}
"""


# ============================================================
# RELATED NEWS
# ============================================================

def related_items(
    item: dict,
    all_news: list[dict],
    limit: int = 6,
) -> list[dict]:

    category = clean(
        item["category"]
    ).casefold()

    result = []

    for news in all_news:

        if news["id"] == item["id"]:
            continue

        if (
            clean(
                news["category"]
            ).casefold()
            == category
        ):

            result.append(news)

        if len(result) >= limit:
            break

    return result


# ============================================================
# CARD
# ============================================================

def card_html(
    item: dict,
) -> str:

    image = first_image(
        item
    )

    if image:

        image_html = f"""
<img
class="news-image"
src="{esc('../' + image)}"
alt="{esc(item['headline'])}"
loading="lazy">
"""

    else:

        image_html = """
<div
class="news-image"
style="background:#ddd">
</div>
"""

    return f"""
<article class="news-card">

<a href="{esc(item['id'] + '.html')}">

{image_html}

<div class="news-card-content">

<span class="category">
{esc(item['category'])}
</span>

<h3>
{esc(item['headline'])}
</h3>

</div>

</a>

</article>
"""


# ============================================================
# DETAILS PAGE
# ============================================================

def render_page(
    item: dict,
    all_news: list[dict],
) -> str:

    images = [
        image
        for image
        in item.get("images", [])
        if image
    ]

    hero = (
        images[0]
        if images
        else ""
    )

    if hero:

        hero_html = f"""
<img
class="hero-image"
src="{esc('../' + hero)}"
alt="{esc(item['headline'])}"
loading="eager">
"""

    else:

        hero_html = ""


    extra_images = ""

    for image in images[1:]:

        extra_images += f"""
<img
class="article-image"
src="{esc('../' + image)}"
alt="{esc(item['headline'])}"
loading="lazy">
"""


    details = clean(
        item["details"]
    )

    paragraphs = []

    for part in re.split(
        r"\n\s*\n|\r?\n",
        details,
    ):

        part = part.strip()

        if part:

            paragraphs.append(
                "<p>"
                + esc(part)
                + "</p>"
            )

    article_text = "\n".join(
        paragraphs
    )


    related = related_items(
        item,
        all_news,
        6,
    )

    cards = "\n".join(
        card_html(x)
        for x in related
    )


    latest_links = "\n".join(
        f"""
<a
class="latest-link"
href="{esc(x['id'] + '.html')}">
{esc(x['headline'])}
</a>
"""
        for x in related
    )


    video = video_block(
        item["video"]
    )

    canonical = page_url(
        item["id"]
    )

    og_image = first_image(
        item
    )


    return f"""<!DOCTYPE html>

<html lang="bn">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width,initial-scale=1">

<title>
{esc(item["headline"])}
| বাংলা সংবাদ
</title>

<meta
name="description"
content="{esc(item["details"][:155])}">

<meta
name="keywords"
content="{esc(item["keyword"])}">

<link
rel="canonical"
href="{esc(canonical)}">


<meta
property="og:type"
content="article">

<meta
property="og:title"
content="{esc(item["headline"])}">

<meta
property="og:description"
content="{esc(item["details"][:155])}">

<meta
property="og:url"
content="{esc(canonical)}">

<meta
property="og:site_name"
content="বাংলা সংবাদ">

{
f'<meta property="og:image" content="{esc(og_image)}">'
if og_image
else ""
}


<meta
name="twitter:card"
content="summary_large_image">

<meta
name="twitter:title"
content="{esc(item["headline"])}">

<meta
name="twitter:description"
content="{esc(item["details"][:155])}">

{
f'<meta name="twitter:image" content="{esc(og_image)}">'
if og_image
else ""
}


<style>

{DETAIL_CSS}

</style>

</head>


<body>


<div class="top-bar">

<div class="container">

বাংলা সংবাদ — সর্বশেষ খবর

</div>

</div>


<header class="site-header">

<div class="container header-inner">

<a
class="logo"
href="../index.html">

বাংলা সংবাদ

</a>

<div class="date-box">

{esc(item["date"])}

</div>

</div>

</header>


<nav class="nav">

<div class="container nav-inner">

<a href="../index.html">
হোম
</a>

<a href="../index.html">
জাতীয়
</a>

<a href="../index.html">
রাজনীতি
</a>

<a href="../index.html">
আন্তর্জাতিক
</a>

<a href="../index.html">
খেলা
</a>

<a href="../index.html">
বিনোদন
</a>

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


<section>


<article class="article">


<span class="category">

{esc(item["category"])}

</span>


<h1>

{esc(item["headline"])}

</h1>


<div class="meta">

প্রকাশিত:
{esc(item["date"])}

</div>


{hero_html}


<div class="article-body">

{article_text}

</div>


{extra_images}


{video}


{share_block(item)}


</article>


<section class="related">

<h2>

{esc(item["category"])}
—
আরও খবর

</h2>


<div class="news-grid">

{cards}

</div>

</section>


</section>


<aside class="side-news">

<h2>

সর্বশেষ সংবাদ

</h2>

{latest_links}

</aside>


</main>


<footer class="footer site-footer">

© বাংলা সংবাদ —
সর্বস্বত্ব সংরক্ষিত

</footer>


<script>

document
.querySelectorAll(".native")
.forEach(function(button){

button.addEventListener(
"click",
async function(event){

event.preventDefault();

const url =
button.dataset.shareUrl;

const title =
button.dataset.shareTitle
|| document.title;


try{

if(navigator.share){

await navigator.share({

title:title,

text:title,

url:url

});

}

else if(
navigator.clipboard
){

await navigator.clipboard
.writeText(url);

button.textContent =
"লিংক কপি হয়েছে";

}

else{

window.prompt(
"এই লিংকটি কপি করুন:",
url
);

}

}
catch(error){

}

});

});

</script>


</body>

</html>
"""


# ============================================================
# JSON
# ============================================================

def write_json(
    news: list[dict],
) -> None:

    rows = []

    for item in news:

        rows.append(
            [
                item["id"],
                item["category"],
                item["headline"],
                item["details"],
                item["image1"],
                item["date"],
                item["video"],
                item["image2"],
                item["image3"],
                item["keyword"],
            ]
        )


    payload = {

        "generated_at":
            datetime.utcnow()
            .isoformat()
            + "Z",

        "columns":
            EXPECTED_COLUMNS,

        "news":
            news,

        "table":
            {
                "columns":
                    EXPECTED_COLUMNS,

                "rows":
                    rows,
            },

    }


    NEWS_DATA_FILE.write_text(

        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",

    )


    # --------------------------------------------------------
    # ads-data.json
    # --------------------------------------------------------
    # Workflow validation expects this file.
    # Ads can be added later without breaking news sync.

    ads_payload = {

        "generated_at":
            datetime.utcnow()
            .isoformat()
            + "Z",

        "ads": [],

        "table":
            {
                "columns": [],
                "rows": [],
            },

    }


    ADS_DATA_FILE.write_text(

        json.dumps(
            ads_payload,
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",

    )


# ============================================================
# SITEMAP
# ============================================================

def write_sitemap(
    news: list[dict],
) -> None:

    urls = [
        BASE_URL
    ]

    urls.extend(
        page_url(x["id"])
        for x in news
    )


    output = [

        '<?xml version="1.0" encoding="UTF-8"?>',

        '<urlset '
        'xmlns="http://www.sitemaps.org/'
        'schemas/sitemap/0.9">',

    ]


    for url in urls:

        output.append(

            "<url>"
            "<loc>"
            + html.escape(url)
            + "</loc>"
            "</url>"

        )


    output.append(
        "</urlset>"
    )


    SITEMAP_FILE.write_text(

        "\n".join(output)
        + "\n",

        encoding="utf-8",

    )


# ============================================================
# NEWS SITEMAP
# ============================================================

def write_news_sitemap(
    news: list[dict],
) -> None:

    output = [

        '<?xml version="1.0" encoding="UTF-8"?>',

        '<urlset '
        'xmlns="http://www.sitemaps.org/'
        'schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/'
        'schemas/sitemap-news/0.9">',

    ]


    for item in news:

        output.extend(

            [

                "<url>",

                "<loc>"
                + html.escape(
                    page_url(
                        item["id"]
                    )
                )
                + "</loc>",

                "<news:news>",

                "<news:publication>",

                "<news:name>"
                "বাংলা সংবাদ"
                "</news:name>",

                "<news:language>"
                "bn"
                "</news:language>",

                "</news:publication>",

                "<news:publication_date>"
                + esc(item["date"])
                + "</news:publication_date>",

                "<news:title>"
                + esc(item["headline"])
                + "</news:title>",

                "</news:news>",

                "</url>",

            ]

        )


    output.append(
        "</urlset>"
    )


    NEWS_SITEMAP_FILE.write_text(

        "\n".join(output)
        + "\n",

        encoding="utf-8",

    )


# ============================================================
# REMOVE OLD PAGES
# ============================================================

def remove_old_pages(
    active_ids: set[str],
) -> None:

    NEWS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for file in NEWS_DIR.glob(
        "*.html"
    ):

        if file.stem not in active_ids:

            file.unlink()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    NEWS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ASSETS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    print(
        "Reading Google Sheet..."
    )

    rows = load_google_sheet()


    news = normalize_news(
        rows
    )


    if not news:

        raise RuntimeError(
            "No valid news rows found "
            "in Google Sheet."
        )


    print(
        f"Found {len(news)} news items."
    )


    import requests

    session = requests.Session()


    # --------------------------------------------------------
    # Download Image-1 / Image-2 / Image-3
    # --------------------------------------------------------

    for item in news:

        print(
            "Processing images for ID:",
            item["id"],
        )

        item["images"] = (
            process_news_images(

                news_id=item["id"],

                image_urls=[
                    item["image1"],
                    item["image2"],
                    item["image3"],
                ],

                assets_dir=ASSETS_DIR,

                session=session,

            )
        )


    # --------------------------------------------------------
    # Remove deleted news pages
    # --------------------------------------------------------

    active_ids = {
        item["id"]
        for item in news
    }

    remove_old_pages(
        active_ids
    )


    # --------------------------------------------------------
    # Generate Details Pages
    # --------------------------------------------------------

    for item in news:

        target = (
            NEWS_DIR
            / f"{item['id']}.html"
        )

        target.write_text(

            render_page(
                item,
                news,
            ),

            encoding="utf-8",

        )


    # --------------------------------------------------------
    # JSON + Sitemap
    # --------------------------------------------------------

    write_json(
        news
    )

    write_sitemap(
        news
    )

    write_news_sitemap(
        news
    )


    print("")
    print(
        "================================"
    )
    print(
        "Bangla Sangbad generation complete"
    )
    print(
        "================================"
    )

    print(
        f"News pages: {len(news)}"
    )

    print(
        "news-data.json: OK"
    )

    print(
        "ads-data.json: OK"
    )

    print(
        "sitemap.xml: OK"
    )

    print(
        "news-sitemap.xml: OK"
    )


if __name__ == "__main__":

    main()
