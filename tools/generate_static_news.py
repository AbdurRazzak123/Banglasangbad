import json
import re
import urllib.request
import urllib.parse
from pathlib import Path

SHEET_ID = "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg"

ROOT = Path(__file__).resolve().parent.parent
NEWS_JSON = ROOT / "news-data.json"
ADS_JSON = ROOT / "ads-data.json"

MEDIA_DIR = ROOT / "assets" / "news-media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def get_sheet(sheet_name):
    query = urllib.parse.quote("select *")

    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
        f"?tqx=out:json"
        f"&sheet={urllib.parse.quote(sheet_name)}"
        f"&tq={query}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Banglasangbad-GitHub-Sync/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")

    match = re.search(
        r"google\.visualization\.Query\.setResponse\((.*)\);?\s*$",
        raw,
        re.S
    )

    if not match:
        raise RuntimeError(
            f"Google Sheet '{sheet_name}' response could not be read."
        )

    data = json.loads(match.group(1))

    return data.get("table", {}).get("rows", [])


def cell(row, index):
    cells = row.get("c", [])

    if index >= len(cells):
        return ""

    value = cells[index]

    if value is None:
        return ""

    return str(value.get("v", "") or "").strip()


def drive_url(url):
    if not url:
        return ""

    url = url.strip()

    match = re.search(
        r"drive\.google\.com/"
        r"(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)"
        r"([A-Za-z0-9_-]+)",
        url,
        re.I
    )

    if match:
        file_id = match.group(1)
        return (
            f"https://drive.google.com/thumbnail"
            f"?id={file_id}&sz=w2000"
        )

    return url


# =========================================================
# NEWS
# Google Sheet:
# A ID
# B Category
# C Headline
# D Details
# E Image1
# F Date
# G Image2
# H Image3
# I Video
# J Keywords / Tags
# =========================================================

news_rows = get_sheet("Bangla News")

news = []

for row_number, row in enumerate(news_rows, start=1):

    news_id = cell(row, 0)

    # Sheet row order is preserved.
    if not news_id:
        news_id = str(row_number)

    headline = cell(row, 2)

    # Empty headline = not a news item.
    if not headline:
        continue

    item = {
        "id": news_id,
        "category": cell(row, 1),
        "title": headline,
        "text": cell(row, 3),

        "image": drive_url(cell(row, 4)),
        "date": cell(row, 5),

        "image2": drive_url(cell(row, 6)),
        "image3": drive_url(cell(row, 7)),

        "video": cell(row, 8),
        "keywords": cell(row, 9),

        # Preserve original Sheet position.
        "sheet_row": row_number
    }

    news.append(item)


if not news:
    raise RuntimeError(
        "No news found in Google Sheet."
    )


# IMPORTANT:
# Do NOT sort by date or ID.
# The Google Sheet row order is preserved.
NEWS_JSON.write_text(
    json.dumps(
        news,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


# =========================================================
# ADS
#
# Ads Sheet columns:
# A Position
# B Active
# C Image URL
# D Click URL
# E Title
# F Ad Code
# =========================================================

ads_rows = get_sheet("Ads")

ads = []

for row_number, row in enumerate(ads_rows, start=1):

    position = cell(row, 0)
    active = cell(row, 1)
    image = cell(row, 2)
    click_url = cell(row, 3)
    title = cell(row, 4)
    ad_code = cell(row, 5)

    # Skip completely empty rows.
    if not any([
        position,
        active,
        image,
        click_url,
        title,
        ad_code
    ]):
        continue

    # Preserve Sheet values exactly.
    ads.append({
        "position": position,
        "active": active,
        "image": image,
        "clickUrl": click_url,
        "title": title,
        "adCode": ad_code,
        "sheet_row": row_number
    })


ADS_JSON.write_text(
    json.dumps(
        ads,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


print(
    f"Google Sheet sync complete: "
    f"{len(news)} news, {len(ads)} ads."
)
