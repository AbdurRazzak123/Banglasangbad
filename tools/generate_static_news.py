from __future__ import annotations

import csv
import html
import io
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import requests

try:
    from news_assets import process_news_images
except ImportError:
    from News_assets import process_news_images


# ============================================================
# BASIC CONFIG
# ============================================================

SHEET_ID = (
    "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg"
)

SHEET_NAME = "Bangla News"

BASE_URL = (
    "https://abdurrazzak123.github.io/"
    "Banglasangbad/"
)

ROOT = Path(__file__).resolve().parents[1]

# The existing repository uses capitalized folders (News / Asset).
# Keep compatibility with lowercase folders if a copy of the site uses them.
NEWS_DIR = (
    ROOT / "News"
    if (ROOT / "News").exists()
    else ROOT / "news"
)

if (ROOT / "Asset" / "news").exists() or (ROOT / "Asset").exists():
    ASSETS_DIR = ROOT / "Asset" / "news"
else:
    ASSETS_DIR = ROOT / "assets" / "news"

NEWS_DATA_FILE = (
    ROOT / "news-data.json"
)

ADS_DATA_FILE = (
    ROOT / "ads-data.json"
)

SITEMAP_FILE = (
    ROOT / "sitemap.xml"
)

NEWS_SITEMAP_FILE = (
    ROOT / "news-sitemap.xml"
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
    # Social automation controls/status are read from the same Bangla News tab.
    # They are kept in the news records but are intentionally not exposed as
    # frontend table columns, so the existing website JS remains unchanged.
    "Publish",
    "Facebook",
    "Instagram",
    "X",
    "Threads",
    "Youtube",
    "Social Status",
    "Posted Time",
]


# ============================================================
# HELPERS
# ============================================================

def clean(value) -> str:

    if value is None:
        return ""

    return str(value).strip()


def escape(value) -> str:

    return html.escape(
        clean(value),
        quote=True
    )


def safe_id(value) -> str:

    value = clean(value)

    value = re.sub(
        r"[^A-Za-z0-9_-]+",
        "-",
        value
    )

    value = re.sub(
        r"-+",
        "-",
        value
    )

    return (
        value.strip("-_")
        or "news"
    )


def page_url(news_id: str) -> str:

    return (
        BASE_URL.rstrip("/")
        + "/news/"
        + urllib.parse.quote(
            safe_id(news_id)
        )
        + ".html"
    )


def absolute_image_url(path: str) -> str:

    path = clean(path)

    if not path:
        return ""

    if path.startswith(
        ("http://", "https://")
    ):
        return path

    return (
        BASE_URL.rstrip("/")
        + "/"
        + path.lstrip("/")
    )


def relative_image_url(path: str) -> str:

    path = clean(path)

    if not path:
        return ""

    if path.startswith(
        ("http://", "https://")
    ):
        return path

    return (
        "../"
        + path.lstrip("/")
    )


def normalize_generated_image_paths(paths) -> list[str]:
    """Normalize helper-returned image paths to the actual repo asset folder."""
    try:
        asset_prefix = ASSETS_DIR.relative_to(ROOT).as_posix().rstrip("/")
    except ValueError:
        asset_prefix = "assets/news"

    out = []
    for value in paths or []:
        value = clean(value)
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            out.append(value)
            continue
        # The helper historically returned Asset/news/... even when the
        # actual folder was lowercase assets/news. Normalize both cases.
        m = re.match(r"^(?:Asset|assets)/news/(.+)$", value, re.I)
        if m:
            out.append(asset_prefix + "/" + m.group(1))
        else:
            out.append(value.lstrip("./"))
    return out


# ============================================================
# GOOGLE SHEET
# ============================================================

def load_sheet_csv(sheet_name: str) -> list[list[str]]:
    """Read one tab from the single Google Sheet as CSV."""
    sheet = urllib.parse.quote(clean(sheet_name))
    url = (
        "https://docs.google.com/spreadsheets/d/"
        + SHEET_ID
        + "/gviz/tq?sheet="
        + sheet
        + "&tqx=out:csv"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read().decode("utf-8-sig")
    return list(csv.reader(io.StringIO(content)))


def load_google_sheet() -> list[dict]:
    rows = load_sheet_csv(SHEET_NAME)
    if not rows:
        return []
    result = []
    for row in rows[1:]:
        row = list(row)
        while len(row) < len(EXPECTED_COLUMNS):
            row.append("")
        item = {}
        for index, column in enumerate(EXPECTED_COLUMNS):
            item[column] = clean(row[index])
        if not item["ID"]:
            continue
        result.append(item)
    return result


def load_ads_sheet() -> dict | None:
    """Read the Ads tab from the same Google Sheet and preserve its table shape."""
    try:
        rows = load_sheet_csv("Ads")
    except Exception as exc:
        print("Ads sheet could not be read:", exc)
        return None
    if not rows:
        return None
    columns = [clean(x) for x in rows[0]]
    while columns and not columns[-1]:
        columns.pop()
    if not columns:
        return None
    data_rows = []
    for raw in rows[1:]:
        raw = list(raw)
        while len(raw) < len(columns):
            raw.append("")
        values = [clean(raw[i]) for i in range(len(columns))]
        if any(values):
            data_rows.append(values)
    return {"table": {"columns": columns, "rows": data_rows},
            "updated_at": datetime.utcnow().isoformat() + "Z"}


# ============================================================
# NEWS NORMALIZATION
# ============================================================

def parse_news_date(value):
    """Parse the Google Sheet Date cell into a real date when possible."""
    raw = clean(value).translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))
    if not raw:
        return None

    m = re.fullmatch(r"Date\((\d+),(\d+),(\d+)(?:,(\d+),(\d+),(\d+))?\)", raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)) + 1, int(m.group(3)))
        except ValueError:
            return None

    # Google Sheets / gviz can return ISO timestamps with milliseconds or Z.
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(?:Z|[+-]\d{2}:?\d{2})?)?", raw)
    if iso:
        try:
            return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            pass

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d-%m-%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    return None


def bangla_news_date(value):
    """Format the Sheet article date in Bengali for display below the category."""
    d = parse_news_date(value)
    if not d:
        return clean(value).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))
    months = [
        "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
        "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর",
    ]
    digits = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return f"{str(d.day).translate(digits)} {months[d.month - 1]} {str(d.year).translate(digits)}"


def normalize_news(rows):

    result = []

    for row in rows:

        news_id = safe_id(
            row.get("ID")
        )

        if not news_id:
            continue

        result.append(
            {
                "id": news_id,
                "category": clean(
                    row.get("Category")
                ),
                "headline": clean(
                    row.get("Headline")
                ),
                "details": clean(
                    row.get("Details")
                ),
                "date": clean(
                    row.get("Date")
                ),
                "video": clean(
                    row.get("Video")
                ),
                "keyword": clean(
                    row.get("Keyword")
                ),
                # These fields come from the same Google Sheet row and drive
                # per-news social publishing. Missing/blank values remain safe.
                "publish": clean(row.get("Publish")),
                "facebook": clean(row.get("Facebook")),
                "instagram": clean(row.get("Instagram")),
                "x": clean(row.get("X")),
                "threads": clean(row.get("Threads")),
                "youtube": clean(row.get("Youtube")),
                "social_status": clean(row.get("Social Status")),
                "posted_time": clean(row.get("Posted Time")),
                "image_urls": [
                    clean(row.get("Image-1")),
                    clean(row.get("Image-2")),
                    clean(row.get("Image-3")),
                ],
                "images": [],
            }
        )

    return result


# ============================================================
# VIDEO
# ============================================================

def youtube_id(url: str):

    url = clean(url)

    patterns = [
        r"youtu\.be/([^?&/]+)",
        r"youtube\.com/watch\?v=([^?&/]+)",
        r"youtube\.com/embed/([^?&/]+)",
        r"youtube\.com/shorts/([^?&/]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url
        )

        if match:
            return match.group(1)

    return ""


def render_video(url: str):

    url = clean(url)

    if not url:
        return ""

    video_id = youtube_id(url)

    if video_id:

        return f"""
<div class="video-box">
    <iframe
        src="https://www.youtube.com/embed/{escape(video_id)}"
        title="YouTube video"
        loading="lazy"
        allowfullscreen>
    </iframe>
</div>
"""

    if url.lower().endswith(
        (
            ".mp4",
            ".webm",
            ".ogg",
            ".mov"
        )
    ):

        return f"""
<div class="video-box">
    <video
        controls
        preload="metadata"
        src="{escape(url)}">
    </video>
</div>
"""

    return f"""
<div class="video-link">
    <a
        href="{escape(url)}"
        target="_blank"
        rel="noopener">
        ভিডিও দেখুন
    </a>
</div>
"""


# ============================================================
# DETAILS TEXT
# ============================================================

def render_details(text: str):

    text = clean(text)

    if not text:
        return ""

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    output = []

    for paragraph in paragraphs:

        paragraph = clean(
            paragraph
        )

        if not paragraph:
            continue

        output.append(
            "<p>"
            + escape(paragraph)
            .replace("\n", "<br>")
            + "</p>"
        )

    return "\n".join(
        output
    )


# ============================================================
# IMAGE HTML
# ============================================================

def render_main_image(
    item
):

    images = item.get(
        "images",
        []
    )

    first = ""

    for image in images:

        if image:
            first = image
            break

    if not first:
        return ""

    return f"""
<div class="news-image-top">
    <img
        src="{escape(relative_image_url(first))}"
        alt="{escape(item["headline"])}"
        loading="eager">
</div>
"""


def render_gallery(item):

    images = [
        x
        for x in item.get(
            "images",
            []
        )
        if x
    ]

    if len(images) <= 1:
        return ""

    output = [
        '<div class="news-gallery">'
    ]

    for image in images:

        output.append(
            f"""
<img
    src="{escape(relative_image_url(image))}"
    alt="{escape(item["headline"])}"
    loading="lazy">
"""
        )

    output.append(
        "</div>"
    )

    return "\n".join(
        output
    )


# ============================================================
# SHARE
# ============================================================

def render_share_buttons(item):

    url = page_url(
        item["id"]
    )

    encoded_url = urllib.parse.quote(
        url,
        safe=""
    )

    encoded_title = urllib.parse.quote(
        item["headline"]
    )

    facebook = (
        "https://www.facebook.com/"
        "sharer/sharer.php?u="
        + encoded_url
    )

    twitter = (
        "https://twitter.com/intent/tweet?"
        "url="
        + encoded_url
        + "&text="
        + encoded_title
    )

    whatsapp = (
        "https://api.whatsapp.com/send?"
        "text="
        + urllib.parse.quote(
            item["headline"]
            + " "
            + url
        )
    )

    js_title = json.dumps(
        item["headline"],
        ensure_ascii=False
    )

    return f"""
<div class="share-box">

    <strong>
        শেয়ার করুন
    </strong>

    <div class="share-buttons">

        <a
            class="share-btn"
            href="{escape(facebook)}"
            target="_blank"
            rel="noopener">
            Facebook
        </a>

        <a
            class="share-btn"
            href="{escape(twitter)}"
            target="_blank"
            rel="noopener">
            X / Twitter
        </a>

        <a
            class="share-btn"
            href="{escape(whatsapp)}"
            target="_blank"
            rel="noopener">
            WhatsApp
        </a>

        <button
            class="share-btn"
            type="button"
            onclick="shareNews()">
            Share
        </button>

        <a
            class="share-btn"
            href="https://www.youtube.com/"
            target="_blank"
            rel="noopener">
            YouTube
        </a>

        <a
            class="share-btn"
            href="https://www.tiktok.com/"
            target="_blank"
            rel="noopener">
            TikTok
        </a>

    </div>
</div>

<script>
function shareNews() {{

    const shareData = {{
        title: {js_title},
        text: {js_title},
        url: window.location.href
    }};

    if (navigator.share) {{

        navigator.share(
            shareData
        ).catch(
            function() {{}}
        );

    }} else if (
        navigator.clipboard
    ) {{

        navigator.clipboard
            .writeText(
                window.location.href
            )
            .then(
                function() {{
                    alert(
                        "নিউজের লিংক কপি হয়েছে"
                    );
                }}
            );

    }} else {{

        alert(
            window.location.href
        );
    }}
}}
</script>
"""


# ============================================================
# CARD
# ============================================================

def render_card(item):

    images = item.get(
        "images",
        []
    )

    image = ""

    for value in images:

        if value:
            image = value
            break

    if image:

        image_html = f"""
<img
    src="{escape(relative_image_url(image))}"
    alt="{escape(item["headline"])}"
    loading="lazy">
"""

    else:

        image_html = ""

    return f"""
<article class="news-card">

    <a
        href="{escape(safe_id(item["id"]))}.html">

        {image_html}

        <div class="news-card-content">

            <div class="category">
                {escape(item["category"])}
            </div>

            <h3>
                {escape(item["headline"])}
            </h3>

        </div>

    </a>

</article>
"""


# ============================================================
# CATEGORY RELATED NEWS
# ============================================================

def same_category_news(
    current,
    all_news
):

    category = current["category"]

    result = []

    for item in all_news:

        if item["id"] == current["id"]:
            continue

        if item["category"] != category:
            continue

        result.append(item)

    return result[:6]


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar(
    current,
    all_news
):

    related = same_category_news(
        current,
        all_news
    )

    links = []

    for item in related:

        image = ""

        for value in item.get(
            "images",
            []
        ):

            if value:
                image = value
                break

        if image:

            image_html = f"""
<img
    src="{escape(relative_image_url(image))}"
    alt="{escape(item["headline"])}"
    loading="lazy">
"""

        else:

            image_html = ""

        links.append(
            f"""
<a
    class="latest-link"
    href="{escape(safe_id(item["id"]))}.html">

    {image_html}

    <span class="latest-link-title">
        {escape(item["headline"])}
    </span>

</a>
"""
        )

    return "\n".join(
        links
    )


# ============================================================
# FINAL PAGE CSS
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
    background:#f3f4f6;
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

/* =========================
   TOP BAR
========================= */

.top-bar{
    background:#151515;
    color:#fff;
    padding:6px 0;
    font-size:13px;
}

.header-inner{
    max-width:1250px;
    margin:auto;
    padding:0 18px;
}

/* =========================
   HEADER
========================= */

.site-header{
    background:#fff;
    border-bottom:1px solid #ddd;
}

.logo{
    font-size:34px;
    font-weight:900;
    color:#c40000;
    padding:16px 0 5px;
    letter-spacing:-.5px;
}

.date-box{
    font-size:13px;
    color:#777;
    padding-bottom:12px;
}

/* =========================
   NAVIGATION
========================= */

.nav{
    background:#b40000;
    border-bottom:3px solid #8e0000;
}

.nav-inner{
    max-width:1250px;
    margin:auto;
    display:flex;
    align-items:center;
    flex-wrap:wrap;
    padding:0 18px;
}

.nav a{
    color:#fff;
    padding:11px 16px;
    font-weight:700;
    font-size:15px;
    border-right:1px solid rgba(255,255,255,.12);
    transition:.2s;
}

.nav a:hover{
    background:#850000;
}

/* =========================
   BREAKING NEWS
========================= */

.breaking{
    background:#fff;
    border-bottom:1px solid #ddd;
    color:#222;
    display:flex;
    align-items:center;
    overflow:hidden;
}

.breaking-title{
    background:#d00000;
    color:#fff;
    padding:8px 18px;
    font-weight:900;
    white-space:nowrap;
}

.breaking-text{
    padding:8px 18px;
    white-space:nowrap;
    overflow:hidden;
    color:#333;
    font-weight:600;
}

/* =========================
   MAIN CONTAINER
========================= */

.container{
    max-width:1250px;
    margin:25px auto;
    padding:0 18px;
}

main.container{
    display:grid;
    grid-template-columns:minmax(0,2.25fr) minmax(300px,1fr);
    gap:28px;
}

.main-content{
    min-width:0;
}

/* =========================
   NEWS TITLE
========================= */

.news-title{
    background:#fff;
    padding:22px 24px 18px;
    border-top:4px solid #c40000;
    border-bottom:1px solid #ddd;
    margin-bottom:18px;
}

.news-title h1{
    margin:6px 0 12px;
    font-size:35px;
    line-height:1.45;
    font-weight:900;
    color:#202020;
}

.news-meta{
    color:#777;
    font-size:14px;
    border-top:1px solid #eee;
    padding-top:8px;
}

.category{
    color:#c40000;
    font-size:14px;
    font-weight:900;
}

/* =========================
   NEWS BODY
========================= */

.news-body{
    background:#fff;
    padding:24px;
    border:1px solid #e2e2e2;
}

.news-text-bottom{
    font-size:18px;
    color:#292929;
    line-height:2;
}

.news-text-bottom p{
    margin:0 0 20px;
}

/* =========================
   MAIN NEWS IMAGE
========================= */

.news-image-top{
    width:100%;
    margin:0 0 22px;
}

.news-image-top img{
    width:100%;
    height:auto;
    display:block;
    border-radius:3px;
}

/* =========================
   GALLERY
========================= */

.news-gallery{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:12px;
    margin:24px 0;
}

.news-gallery img{
    width:100%;
    height:auto;
    display:block;
    border-radius:4px;
}

/* =========================
   VIDEO
========================= */

.video-box{
    width:100%;
    aspect-ratio:16/9;
    margin:25px 0;
    background:#000;
}

.video-box iframe,
.video-box video{
    width:100%;
    height:100%;
    border:0;
}

.video-link{
    margin:20px 0;
}

.video-link a{
    color:#c40000;
    font-weight:800;
}

/* =========================
   SHARE
========================= */

.share-box{
    margin-top:28px;
    padding-top:18px;
    border-top:1px solid #ddd;
}

.share-box strong{
    display:block;
    margin-bottom:12px;
    font-size:17px;
}

.share-buttons{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
}

.share-btn{
    display:inline-block;
    border:1px solid #ddd;
    padding:8px 14px;
    background:#f5f5f5;
    color:#222;
    border-radius:3px;
    font-weight:700;
    font-size:13px;
    cursor:pointer;
    transition:.2s;
}

.share-btn:hover{
    background:#c40000;
    color:#fff;
    border-color:#c40000;
}

/* =========================
   RIGHT SIDEBAR
========================= */

.side-news{
    background:#fff;
    border:1px solid #ddd;
    padding:17px;
    align-self:start;
}

.side-news h2{
    margin:0 0 5px;
    color:#b40000;
    font-size:21px;
    font-weight:900;
    border-bottom:3px solid #b40000;
    padding-bottom:9px;
}

/* =========================
   SIDEBAR IMAGE + HEADLINE
========================= */

.latest-link{
    display:flex;
    align-items:flex-start;
    gap:11px;
    color:#222;
    border-bottom:1px solid #e2e2e2;
    padding:12px 0;
    font-weight:700;
    line-height:1.45;
    transition:.2s;
}

.latest-link img{
    width:95px;
    height:62px;
    flex:0 0 95px;
    object-fit:cover;
    display:block;
    border-radius:3px;
    background:#eee;
}

.latest-link-title{
    display:block;
    flex:1;
    font-size:15px;
}

.latest-link:hover{
    color:#c40000;
}

.latest-link:hover img{
    opacity:.9;
}

/* =========================
   RELATED NEWS
========================= */

.news-grid{
    display:grid;
    grid-template-columns:repeat(2,1fr);
    gap:20px;
    margin-top:28px;
}

.news-card{
    background:#fff;
    border:1px solid #ddd;
    overflow:hidden;
    transition:.2s;
}

.news-card:hover{
    transform:translateY(-2px);
    box-shadow:0 5px 15px rgba(0,0,0,.08);
}

.news-card img{
    width:100%;
    aspect-ratio:16/9;
    object-fit:cover;
    display:block;
}

.news-card-content{
    padding:14px 15px 16px;
}

.news-card-content .category{
    font-size:12px;
    margin-bottom:4px;
}

.news-card-content h3{
    margin:4px 0 0;
    color:#222;
    font-size:18px;
    line-height:1.5;
    font-weight:800;
}

/* =========================
   FOOTER
========================= */

.footer,
.site-footer{
    background:#151515;
    color:#fff;
    text-align:center;
    padding:30px 15px;
    margin-top:35px;
}

.social-links{
    display:flex;
    justify-content:center;
    gap:10px;
    flex-wrap:wrap;
    margin-top:14px;
}

.social-links a{
    color:#fff;
    padding:7px 13px;
    border:1px solid #555;
    border-radius:3px;
}

.social-links a:hover{
    background:#c40000;
    border-color:#c40000;
}

/* =========================
   TABLET
========================= */

@media(max-width:900px){

    main.container{
        grid-template-columns:1fr;
    }

    .side-news{
        margin-top:5px;
    }

    .news-title h1{
        font-size:30px;
    }

}

/* =========================
   MOBILE
========================= */

@media(max-width:650px){

    .logo{
        font-size:28px;
    }

    .nav-inner{
        overflow-x:auto;
        flex-wrap:nowrap;
    }

    .nav a{
        white-space:nowrap;
        padding:10px 14px;
        font-size:14px;
    }

    .container{
        margin:15px auto;
        padding:0 10px;
    }

    .news-title{
        padding:17px 15px;
    }

    .news-title h1{
        font-size:26px;
        line-height:1.5;
    }

    .news-body{
        padding:15px;
    }

    .news-text-bottom{
        font-size:17px;
        line-height:1.9;
    }

    .news-gallery{
        grid-template-columns:1fr;
    }

    .news-grid{
        grid-template-columns:1fr;
        gap:15px;
    }

    .latest-link img{
        width:82px;
        height:55px;
        flex-basis:82px;
    }

    .latest-link-title{
        font-size:14px;
    }

}

/* =========================
   SMALL MOBILE
========================= */

@media(max-width:400px){

    .logo{
        font-size:25px;
    }

    .news-title h1{
        font-size:23px;
    }

    .breaking-title{
        padding:7px 11px;
    }

    .breaking-text{
        padding:7px 10px;
    }

    .latest-link img{
        width:76px;
        height:52px;
        flex-basis:76px;
    }

}
"""


# ============================================================
# COMPLETE DETAILS PAGE
# ============================================================

def _home_template_parts():
    candidates = [ROOT / "home.html", Path(__file__).resolve().parent / "home.html"]
    home = next((x for x in candidates if x.exists()), None)
    if home is None:
        raise FileNotFoundError("home.html not found beside the generator/project root")
    text = home.read_text(encoding="utf-8")
    m = re.search(r"<head>(.*?)</head>", text, flags=re.I | re.S)
    if not m:
        raise ValueError("Could not read <head> from home.html")
    head = m.group(1)
    for asset in ("ads.css?v=20260915-ads-v28-mobile-fit-sheet-row-compatible", "image-pattern.css"):
        head = head.replace(f'href="{asset}"', f'href="../{asset}"')
    head += """\n<style id="mobile-logo-live-date-final-fix">
/* FINAL MOBILE-ONLY HEADER FIX — desktop/tablet unchanged */
@media (max-width:768px){
  .site-header{overflow:visible!important;}
  .site-header .header-inner{position:relative!important;width:100%!important;max-width:none!important;overflow:visible!important;}
  .site-header .logo{left:45%!important;width:175px!important;}
  .site-header .logo-image,.site-header .site-brand-logo{width:175px!important;max-width:44vw!important;max-height:56px!important;}
  .site-header #live-date{display:block!important;position:absolute!important;right:4px!important;top:50%!important;transform:translateY(-50%)!important;width:125px!important;max-width:32vw!important;margin:0!important;padding:0!important;text-align:right!important;white-space:normal!important;overflow:visible!important;font-size:11px!important;line-height:1.25!important;z-index:5!important;}
}
@media (max-width:380px){
  .site-header .logo{left:42%!important;width:145px!important;}
  .site-header .logo-image,.site-header .site-brand-logo{width:145px!important;max-width:46vw!important;max-height:52px!important;}
  .site-header #live-date{right:5px!important;width:100px!important;max-width:31vw!important;font-size:10px!important;line-height:1.22!important;}
}
</style>
"""
    return head


def _category_key(value: str) -> str:
    value = clean(value).lower()
    aliases = {
        "জাতীয়": "জাতীয়", "জাতীয়": "জাতীয়", "national": "জাতীয়",
        "রাজনীতি": "রাজনীতি", "politics": "রাজনীতি",
        "আন্তর্জাতিক": "আন্তর্জাতিক", "international": "আন্তর্জাতিক",
        "অর্থনীতি": "অর্থনীতি", "economy": "অর্থনীতি",
        "খেলাধুলা": "খেলাধুলা", "sports": "খেলাধুলা", "sport": "খেলাধুলা",
        "বিনোদন": "বিনোদন", "entertainment": "বিনোদন",
        "প্রযুক্তি": "প্রযুক্তি", "technology": "প্রযুক্তি", "tech": "প্রযুক্তি",
    }
    return aliases.get(value, clean(value))


def _home_latest_sidebar(current, all_news):
    """Home-style right rail: two newest stories per category, seven categories."""
    category_order = ["জাতীয়", "রাজনীতি", "আন্তর্জাতিক", "অর্থনীতি", "খেলাধুলা", "বিনোদন", "প্রযুক্তি"]
    buckets = {key: [] for key in category_order}
    ordered = sorted(all_news, key=lambda n: int(n["id"]) if str(n["id"]).isdigit() else -1, reverse=True)
    for n in ordered:
        key = _category_key(n.get("category"))
        if key in buckets and len(buckets[key]) < 2:
            buckets[key].append(n)

    out = []
    for category in category_order:
        for n in buckets[category]:
            image = next((x for x in n.get("images", []) if x), "")
            img = (
                f'<img loading="lazy" src="{escape(relative_image_url(image))}" alt="{escape(n["headline"])}" onerror="imageFallback(this)">'
                if image else ""
            )
            out.append(
                f'''<article class="latest-item category-latest-item">
<a href="{escape(safe_id(n["id"]))}.html" data-news-id="{escape(safe_id(n["id"]))}">
<span class="category-latest-thumb">{img}</span>
<span class="category-latest-copy"><span class="category-latest-category">{escape(category)}</span><span class="category-latest-title">{escape(n["headline"])}</span></span>
</a>
</article>'''
            )
    return "\n".join(out) or '<div style="text-align:center;padding:20px;color:#888;">কোনো সংবাদ নেই।</div>'


def _home_category_cards(current, all_news):
    category_order = ["জাতীয়", "রাজনীতি", "আন্তর্জাতিক", "অর্থনীতি", "খেলাধুলা", "বিনোদন", "প্রযুক্তি"]
    current_id = safe_id(current.get("id"))
    ordered = sorted(all_news, key=lambda n: int(n["id"]) if str(n["id"]).isdigit() else -1, reverse=True)
    chosen, seen = [], set()
    for n in ordered:
        if safe_id(n.get("id")) == current_id:
            continue
        category = _category_key(n.get("category"))
        if category in category_order and category not in seen:
            seen.add(category)
            image = next((x for x in n.get("images", []) if x), "")
            img = (f'<div class="news-image"><img loading="lazy" src="{escape(relative_image_url(image))}" alt="{escape(n["headline"])}" onerror="imageFallback(this)"></div>'
                   if image else '<div class="news-image"></div>')
            chosen.append(
                f'''<article class="news-card"><a href="{escape(safe_id(n["id"]))}.html" class="category-card-link" data-news-id="{escape(safe_id(n["id"]))}">
{img}<div class="news-card-content"><div class="category">{escape(category)}</div><h3>{escape(n["headline"])}</h3></div>
</a></article>'''
            )
            if len(chosen) == 6:
                break
    return "\n".join(chosen) or '<div style="text-align:center;padding:30px;color:#888;grid-column:1/-1;">কোনো সংবাদ নেই।</div>'


def render_news_page(item, all_news):
    canonical = page_url(item["id"])
    first_image = next((x for x in item.get("images", []) if x), "")
    og_image = absolute_image_url(first_image)

    jsonld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": item["headline"],
        "articleSection": item["category"],
        "datePublished": item["date"],
        "mainEntityOfPage": canonical,
    }
    if og_image:
        jsonld["image"] = [og_image]

    head = _home_template_parts()
    # Copy the same ad CSS used by category pages into every generated Details page.
    # This prevents page-specific styles from changing the phone layout.
    ads_css_path = ROOT / "ads.css"
    if ads_css_path.exists():
        ads_css = ads_css_path.read_text(encoding="utf-8")
        head += "\n<style id=\"category-ads-css-copy\">\n" + ads_css + "\n</style>\n"
    # Details-only safeguards: keep the live Bangladesh date visible on phones and
    # prevent third-party ad creatives from forcing horizontal overflow.
    head += """\n<style id=\"details-mobile-final-fix\">
@media(max-width:900px){
  .site-header #live-date{display:block!important;margin-left:auto!important;text-align:right!important;font-size:12px!important;line-height:1.35!important;max-width:150px!important;white-space:normal!important;}
  .ad-slot:not(:empty){box-sizing:border-box!important;width:100%!important;max-width:100%!important;min-width:0!important;overflow:hidden!important;}
  .ad-slot:not(:empty) .ad-code-host,.ad-slot:not(:empty)>*,.ad-slot:not(:empty) iframe,.ad-slot:not(:empty) video,.ad-slot:not(:empty) object,.ad-slot:not(:empty) embed,.ad-slot:not(:empty) canvas,.ad-slot:not(:empty) svg,.ad-slot:not(:empty) img{box-sizing:border-box!important;max-width:100%!important;}
  .ad-slot:not(:empty) iframe,.ad-slot:not(:empty) video,.ad-slot:not(:empty) object,.ad-slot:not(:empty) embed,.ad-slot:not(:empty) canvas,.ad-slot:not(:empty) svg,.ad-slot:not(:empty) img{width:100%!important;height:auto!important;}
  .ad-slot:not(:empty) .ad-code-host{min-height:0!important;height:auto!important;}
  .ad-slot:not(:empty) .ad-code-host[data-ad-width][data-ad-height] iframe{width:100%!important;height:auto!important;aspect-ratio:var(--ad-ratio)!important;}
}
@media(max-width:600px){.site-header #live-date{font-size:11px!important;max-width:125px!important;white-space:normal!important;}}
</style>
"""
    head = re.sub(
        r'<title>.*?</title>',
        f'<title>{escape(item["headline"])} | বাংলা সংবাদ</title>',
        head,
        flags=re.I | re.S,
    )
    head = re.sub(
        r'<link\s+rel="canonical"[^>]*>',
        f'<link rel="canonical" href="{escape(canonical)}">',
        head,
        flags=re.I,
    )
    head = re.sub(
        r'<meta\s+name="description"[^>]*>',
        f'<meta name="description" content="{escape(item["headline"])}">',
        head,
        flags=re.I,
    )
    head = re.sub(
        r'<meta\s+name="keywords"[^>]*>',
        f'<meta name="keywords" content="{escape(item.get("keyword", ""))}">',
        head,
        flags=re.I,
    )
    head = re.sub(
        r'<meta\s+property="og:title"[^>]*>',
        f'<meta property="og:title" content="{escape(item["headline"])}">',
        head,
        flags=re.I,
    )
    head = re.sub(
        r'<meta\s+property="og:description"[^>]*>',
        f'<meta property="og:description" content="{escape(item["headline"])}">',
        head,
        flags=re.I,
    )
    head = re.sub(
        r'<meta\s+property="og:url"[^>]*>',
        f'<meta property="og:url" content="{escape(canonical)}">',
        head,
        flags=re.I,
    )
    if og_image:
        head = re.sub(
            r'<meta\s+property="og:image"[^>]*>',
            f'<meta property="og:image" content="{escape(og_image)}">',
            head,
            flags=re.I,
        )
        head = re.sub(
            r'<meta\s+name="twitter:image"[^>]*>',
            f'<meta name="twitter:image" content="{escape(og_image)}">',
            head,
            flags=re.I,
        )

    # Keep the existing social/share controls and add only page-specific SEO data.
    head += f"""
<meta property="og:type" content="article">
<meta name="robots" content="index, follow, max-image-preview:large">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False, indent=2)}</script>
<style>
.details-social-links{{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-top:14px}}
.details-social-links a{{color:#fff!important;padding:7px 13px;border:1px solid #555;border-radius:3px;text-decoration:none!important}}
.details-social-links a:hover{{background:#c40000;border-color:#c40000}}
.details-share-box{{margin-top:22px;padding:14px;border-top:1px solid #eee;display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.details-share-box a,.details-share-box button{{border:1px solid #ddd;background:#fff;padding:7px 12px;border-radius:6px;text-decoration:none;cursor:pointer;font:inherit}}
.category-latest-copy{{display:block!important;flex:1!important;min-width:0!important}}
.category-latest-category{{display:block!important;font-size:12px!important;line-height:1.25!important;font-weight:800!important;color:#b91c1c!important;margin-bottom:2px!important}}
.category-latest-title{{display:block!important;font-size:15px!important;line-height:1.45!important;font-weight:700!important;word-break:break-word!important;overflow-wrap:anywhere!important;min-width:0!important}}
.home-sidebar h2{{font-size:20px!important;font-weight:800!important}}

/* ===== EXACT HOME PAGE SIDEBAR + MOBILE SCROLL MATCH ===== */
.category-latest-item{{padding:10px 0!important;border-bottom:1px solid #eee!important}}
.category-latest-item:last-child{{border-bottom:0!important}}
.category-latest-item a{{display:flex!important;align-items:center!important;gap:10px!important;text-decoration:none!important;color:inherit!important}}
.category-latest-thumb{{display:block!important;flex:0 0 92px!important;width:92px!important;height:68px!important;border-radius:6px!important;overflow:hidden!important;background:#d1d5db!important}}
.category-latest-thumb img{{display:block!important;width:100%!important;height:100%!important;object-fit:cover!important}}
.image-load-failed{{background:#f1f1f1!important;min-height:68px!important}}
.category-latest-title{{display:block!important;flex:1!important;font-size:15px!important;line-height:1.45!important;font-weight:700!important;color:#1f2937!important;min-width:0!important;word-break:break-word!important;overflow-wrap:anywhere!important}}

@media(max-width:768px){{
  /* Home's mobile main layout */
  .home-main-layout{{display:flex!important;flex-direction:column!important;width:100%!important;max-width:100%!important;padding:0 12px!important;gap:20px!important}}
  .home-main-layout>#home-feature,.home-main-layout>.home-sidebar{{width:100%!important;max-width:100%!important}}
  .home-main-layout>.home-sidebar{{order:2!important;margin-top:0!important}}

  /* Home's actual sidebar scrolling behavior: max-height, not a forced height. */
  .latest-news-scroll,#latest-news-container{{max-height:280px!important;overflow-y:auto!important;padding-right:5px!important;display:block!important;-webkit-overflow-scrolling:touch!important}}
  .latest-item{{padding:12px 0!important;border-bottom:1px solid #eee!important;width:100%!important}}
  .latest-item a{{color:#cc0000!important;font-size:15px!important;line-height:1.5!important;text-decoration:none!important;font-weight:bold!important;display:block!important;word-wrap:break-word!important}}

  /* Home's thumbnail sizing on phones, plus category label used by Details. */
  .category-latest-item a{{display:flex!important;align-items:center!important;gap:10px!important;text-decoration:none!important;color:inherit!important}}
  .category-latest-thumb{{flex-basis:88px!important;width:88px!important;height:64px!important}}
  .category-latest-title{{font-size:14px!important;line-height:1.45!important;white-space:normal!important;word-break:break-word!important;overflow-wrap:anywhere!important}}
  .category-latest-copy{{min-width:0!important;flex:1!important;max-width:calc(100% - 98px)!important}}
  .category-latest-category{{font-size:11px!important;line-height:1.25!important;margin-bottom:2px!important}}
}}

@media(min-width:769px){{
  /* Home's desktop two-column container */
  .home-main-layout{{display:grid!important;grid-template-columns:minmax(0,1fr) 320px!important;gap:22px!important;align-items:start!important}}
  .home-main-layout>#home-feature{{grid-column:1;min-width:0}}
  .home-main-layout>.home-sidebar{{grid-column:2;grid-row:1;min-width:0}}
  .latest-news-scroll,#latest-news-container{{overflow-y:visible!important;overflow-x:hidden!important}}
  .category-latest-copy{{min-width:0!important;flex:1!important;max-width:calc(100% - 102px)!important}}
}}
</style>"""

    image_html = render_main_image(item)
    body_html = render_details(item["details"])
    gallery_html = render_gallery(item)
    video_html = render_video(item["video"])
    share_html = render_share_buttons(item).replace(
        'class="share-box"',
        'class="details-share-box"',
    )

    nav = """<nav class="nav"><div class="nav-inner">
<a href="../home.html" class="active">হোম</a><a href="../national.html">জাতীয়</a><a href="../politics.html">রাজনীতি</a><a href="../international.html">আন্তর্জাতিক</a><a href="../economy.html">অর্থনীতি</a><a href="../sports.html">খেলাধুলা</a><a href="../entertainment.html">বিনোদন</a><a href="../technology.html">প্রযুক্তি</a><a href="../more.html">আরও</a>
</div></nav>"""

    sidebar = _home_latest_sidebar(item, all_news)
    cards = _home_category_cards(item, all_news)

    footer = """<footer class="site-footer"><h3>বাংলা সংবাদ</h3><p>সর্বশেষ সংবাদ সবার আগে</p><div class="links"><a href="../about.html">আমাদের সম্পর্কে</a><a href="../contact.html">যোগাযোগ</a><a href="../privacy.html">গোপনীয়তা নীতি</a><a href="../disclaimer.html">দাবিত্যাগ</a></div><div class="details-social-links">
<a href="https://www.facebook.com/" target="_blank" rel="noopener">Facebook</a>
<a href="https://www.youtube.com/" target="_blank" rel="noopener">YouTube</a>
<a href="https://www.tiktok.com/" target="_blank" rel="noopener">TikTok</a>
<a href="https://twitter.com/" target="_blank" rel="noopener">X / Twitter</a>
</div><p>© ২০২৬ বাংলা সংবাদ — সর্বস্বত্ব সংরক্ষিত</p><a href="../advertise.html">বিজ্ঞাপন দিন</a></footer>"""

    scripts = """<script src="../ads-loader.js?v=20260915-ads-v28-mobile-fit-sheet-row-compatible"></script><script src="../news-media.js?v=20260912-details-v1"></script><script src="../news-reader.js"></script><script src="../site-search.js" defer></script>"""

    # Exact requested Details ad order:
    # Top -> headline -> Middle top -> article content -> Middle bottom ->
    # Home-style sidebar/category content -> Bottom.
    return f"""<!DOCTYPE html>
<html lang="bn">
<head>{head}</head>
<body data-site-base="../">
<div class="ad-slot top sheet-ad-slot" data-ad-position="top" data-ad-slot="top" aria-label="বিজ্ঞাপন"></div>
<div class="top-bar">বাংলা সংবাদ — সত্য ও নির্ভরযোগ্য খবর</div>
<header class="site-header"><div class="header-inner"><div class="logo"><img src="../logo.png" alt="বাংলা সংবাদ লোগো" class="logo-image"><div class="logo-fallback"><h1>বাংলা সংবাদ</h1><p>সর্বশেষ সংবাদ সবার আগে</p></div></div><div id="live-date">তারিখ</div></div></header>
<script id="detail-live-date-script">(function(){{const e=document.getElementById('live-date');if(e)e.textContent=new Intl.DateTimeFormat('bn-BD',{{timeZone:'Asia/Dhaka',weekday:'long',day:'numeric',month:'long',year:'numeric'}}).format(new Date());}})();</script>
{nav}
<div class="breaking"><div class="breaking-news-container"><div class="breaking-title">ব্রেকিং নিউজ</div><div class="ticker-window"><div class="ticker-track" id="breaking-ticker">{escape(item["headline"])}</div></div></div></div>
<main class="container home-main-layout">
<section id="home-feature" aria-label="সংবাদের বিস্তারিত"><article class="vertical-news-block" id="news-{escape(safe_id(item["id"]))}">
{image_html}<div class="news-text-bottom"><span class="category-tag">{escape(item["category"])}</span><div class="breaking-news-date">{escape(bangla_news_date(item["date"]))}</div><h1 class="home-feature-title">{escape(item["headline"])}</h1>
<div class="ad-slot in-article sheet-ad-slot middle" data-ad-position="middle-top" data-ad-slot="middle-top" aria-label="বিজ্ঞাপন"></div>
<div class="home-full-details">{body_html}</div>{gallery_html}{video_html}{share_html}
<div class="ad-slot in-article sheet-ad-slot middle" data-ad-position="middle-bottom" data-ad-slot="middle-bottom" aria-label="বিজ্ঞাপন"></div>
</div></article></section>
<aside class="sidebar home-sidebar"><h2>ক্যাটাগরি অনুযায়ী সর্বশেষ ১৪ সংবাদ</h2><div class="latest-news-scroll" id="latest-news-container">{sidebar}</div></aside>
</main>
<h2 class="section-title">সর্বশেষ ৬ ক্যাটাগরির খবর</h2>
<section class="news-grid category-six-grid" id="category-six-grid">{cards}</section>
<div class="ad-slot footer-ad sheet-ad-slot bottom" data-ad-position="bottom" data-ad-slot="bottom" aria-label="বিজ্ঞাপন"></div>
{footer}
{scripts}
</body></html>"""


# ============================================================
# GENERATE NEWS PAGES
# ============================================================

def generate_news_pages(
    news
):

    NEWS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    valid_files = {
        safe_id(item["id"])
        + ".html"
        for item in news
    }

    for old_file in NEWS_DIR.glob(
        "*.html"
    ):

        if old_file.name not in valid_files:

            try:
                old_file.unlink()
            except Exception:
                pass

    for item in news:

        output_file = (
            NEWS_DIR
            / (
                safe_id(item["id"])
                + ".html"
            )
        )

        output_file.write_text(
            render_news_page(
                item,
                news
            ),
            encoding="utf-8"
        )


# ============================================================
# NEWS DATA JSON
# ============================================================

def generate_news_data(
    news
):

    rows = []

    for item in news:

        rows.append(
            {
                "ID": item["id"],
                "Category": item["category"],
                "Headline": item["headline"],
                "Details": item["details"],
                "Image-1": item["image_urls"][0],
                "Date": item["date"],
                "Video": item["video"],
                "Image-2": item["image_urls"][1],
                "Image-3": item["image_urls"][2],
                "Keyword": item["keyword"],
            }
        )

    # Keep the existing website table at its original 10 columns.
    # Social controls remain available in data["news"] for automation.
    FRONTEND_COLUMNS = [
        "ID", "Category", "Headline", "Details", "Image-1",
        "Date", "Video", "Image-2", "Image-3", "Keyword"
    ]
    table_rows = [
        {
            "c": [
                {"v": item.get(column, "")}
                for column in FRONTEND_COLUMNS
            ]
        }
        for item in rows
    ]

    data = {
        "news": news,
        "table": {
            "columns": FRONTEND_COLUMNS,
            "rows": table_rows,
        },
        "updated_at": (
            datetime.utcnow()
            .isoformat()
            + "Z"
        ),
    }

    NEWS_DATA_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================================
# ADS DATA
# ============================================================

def generate_ads_data():
    """Generate ads-data.json from the Ads tab of the same Google Sheet."""
    data = load_ads_sheet()
    if data is None:
        if ADS_DATA_FILE.exists():
            print("Ads Sheet unavailable; keeping existing ads-data.json")
            return False
        data = {"table": {"columns": [], "rows": []}}
    ADS_DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Ads data generated from Google Sheet tab: Ads")
    return True


# ============================================================
# SITEMAP
# ============================================================

def generate_sitemap(
    news
):

    urls = [
        BASE_URL.rstrip("/")
        + "/"
    ]

    for item in news:

        urls.append(
            page_url(
                item["id"]
            )
        )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for url in urls:

        lines.append(
            "  <url>"
            + "<loc>"
            + escape(url)
            + "</loc>"
            + "</url>"
        )

    lines.append(
        "</urlset>"
    )

    SITEMAP_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


def generate_news_sitemap(
    news
):

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for item in news:

        lines.append(
            "  <url>"
            + "<loc>"
            + escape(
                page_url(item["id"])
            )
            + "</loc>"
            + "</url>"
        )

    lines.append(
        "</urlset>"
    )

    NEWS_SITEMAP_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "Bangla Sangbad Generator"
    )

    print(
        "========================================"
    )

    NEWS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    ASSETS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        "Reading Google Sheet..."
    )

    rows = load_google_sheet()

    print(
        "Rows found:",
        len(rows)
    )

    news = normalize_news(
        rows
    )

    if not news:

        raise RuntimeError(
            "No news found in Google Sheet."
        )

    print(
        "News found:",
        len(news)
    )

    session = requests.Session()

    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------

    for item in news:

        print(
            "Downloading images for:",
            item["id"]
        )

        item["images"] = normalize_generated_image_paths(
            process_news_images(
                news_id=item["id"],
                image_urls=item["image_urls"],
                assets_dir=ASSETS_DIR,
                session=session,
            )
        )

        print(
            "Images:",
            item["images"]
        )

    # --------------------------------------------------------
    # PAGES
    # --------------------------------------------------------

    print(
        "Generating news pages..."
    )

    generate_news_pages(
        news
    )

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    print(
        "Generating news-data.json..."
    )

    generate_news_data(
        news
    )

    print(
        "Reading Ads tab from the same Google Sheet..."
    )

    generate_ads_data()

    # --------------------------------------------------------
    # SITEMAPS
    # --------------------------------------------------------

    print(
        "Generating sitemap.xml..."
    )

    generate_sitemap(
        news
    )

    print(
        "Generating news-sitemap.xml..."
    )

    generate_news_sitemap(
        news
    )

    print(
        "========================================"
    )

    print(
        "SYNC COMPLETE"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
