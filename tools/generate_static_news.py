import json
import mimetypes
import os
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

SHEET_ID = '1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg'
NEWS_SHEET = 'Bangla News'
ADS_SHEET = 'Ads'
BASE = 'https://abdurrazzak123.github.io/Banglasangbad/'
ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'news-media'
NEWS_DIR = ROOT / 'news'

NEWS_COLUMNS = ['id', 'category', 'title', 'summary', 'image', 'date', 'image2', 'image3', 'video', 'keywords']


def fetch_gviz(sheet_name):
    query = urllib.parse.quote('select *')
    url = (
        f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq'
        f'?tqx=out:json&sheet={urllib.parse.quote(sheet_name)}&tq={query}'
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'Banglasangbad-Sheet-Sync/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read().decode('utf-8')
    match = re.search(r'google\.visualization\.Query\.setResponse\((.*)\);?\s*$', raw, re.S)
    if not match:
        raise RuntimeError(f'Could not parse Google Sheet: {sheet_name}')
    data = json.loads(match.group(1))
    return data.get('table', {}).get('rows', [])


def cell(row, index):
    cells = row.get('c', [])
    if index >= len(cells) or cells[index] is None:
        return ''
    value = cells[index].get('v', '')
    return '' if value is None else str(value).strip()


def normalize_drive_url(value):
    value = str(value or '').strip()
    m = re.search(
        r'drive\.google\.com/(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)',
        value,
        re.I,
    )
    if m:
        return f'https://drive.google.com/uc?export=download&id={m.group(1)}'
    return value


def safe_id(value, fallback):
    value = str(value or '').strip()
    if re.fullmatch(r'\d+\.0+', value):
        value = value.split('.')[0]
    return value or str(fallback)


def ext_for(url, content_type=''):
    path = urllib.parse.urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif'}:
        return '.jpg' if ext == '.jpeg' else ext
    guessed = mimetypes.guess_extension(content_type.split(';')[0].strip()) if content_type else None
    return guessed if guessed in {'.jpg', '.png', '.webp', '.gif', '.bmp', '.avif'} else '.jpg'


def download_image(source_url, target_stem):
    source_url = str(source_url or '').strip()
    if not source_url or source_url.startswith('data:'):
        return None
    if source_url.startswith(BASE + 'news-media/'):
        return source_url

    request_url = normalize_drive_url(source_url)
    try:
        req = urllib.request.Request(
            request_url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; Banglasangbad/1.0)'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content_type = response.headers.get('Content-Type', '')
            data = response.read()
        if not data or not content_type.lower().startswith('image/'):
            return None
        ext = ext_for(request_url, content_type)
        target = MEDIA / f'{target_stem}{ext}'
        target.write_bytes(data)
        return BASE + 'news-media/' + target.name
    except Exception as exc:
        print(f'Image download skipped: {source_url} ({exc})')
        return None


def sync_news():
    rows = fetch_gviz(NEWS_SHEET)
    news = []
    seen = set()
    MEDIA.mkdir(exist_ok=True)

    for row_number, row in enumerate(rows, 1):
        item = {
            'id': safe_id(cell(row, 0), row_number),
            'category': cell(row, 1),
            'title': cell(row, 2),
            'summary': cell(row, 3),
            'image': cell(row, 4),
            'date': cell(row, 5),
            'image2': cell(row, 6),
            'image3': cell(row, 7),
            'video': cell(row, 8),
            'keywords': cell(row, 9),
        }
        if not item['title'] and not item['summary']:
            continue
        if item['id'] in seen:
            continue
        seen.add(item['id'])

        for key, suffix in [('image', '1'), ('image2', '2'), ('image3', '3')]:
            local = download_image(item[key], f'{item["id"]}-{suffix}')
            if local:
                item[key] = local

        news.append(item)

    if not news:
        raise RuntimeError('No news rows found in Bangla News sheet.')

    (ROOT / 'news-data.json').write_text(
        json.dumps(news, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    return news


def sync_ads():
    rows = fetch_gviz(ADS_SHEET)
    ads = []
    for row in rows:
        item = {
            'position': cell(row, 0),
            'active': cell(row, 1),
            'image': cell(row, 2),
            'click': cell(row, 3),
            'title': cell(row, 4),
            'code': cell(row, 5),
        }
        if any(item.values()):
            ads.append(item)
    (ROOT / 'ads-data.json').write_text(
        json.dumps(ads, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    return ads


def slug_id(value):
    raw = safe_id(value, value)
    return re.sub(r'[^A-Za-z0-9_-]+', '-', raw).strip('-') or 'article'


def write_compatibility_pages(news):
    # Keep existing article pages untouched. For new IDs, create a tiny redirect to
    # the existing details.html renderer so the current "আরও পড়ুন" URLs continue to work.
    NEWS_DIR.mkdir(exist_ok=True)
    for item in news:
        sid = slug_id(item['id'])
        path = NEWS_DIR / f'{sid}.html'
        if path.exists():
            continue
        target = '../details.html?id=' + urllib.parse.quote(str(item['id']))
        html = f'''<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow"><meta http-equiv="refresh" content="0;url={target}"><title>{item['title']} | বাংলা সংবাদ</title></head><body><script>location.replace({json.dumps(target)});</script><p>খবরটি লোড হচ্ছে...</p></body></html>\n'''
        path.write_text(html, encoding='utf-8')


def write_sitemaps(news):
    static = [
        'index.html', 'home.html', 'national.html', 'politics.html', 'international.html',
        'economy.html', 'sports.html', 'entertainment.html', 'technology.html', 'more.html',
        'details.html', 'about.html', 'contact.html', 'privacy.html', 'disclaimer.html', 'advertise.html'
    ]
    root = Element('urlset', {'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9'})
    for filename in static:
        if (ROOT / filename).exists():
            u = SubElement(root, 'url')
            SubElement(u, 'loc').text = BASE + filename
    for item in news:
        u = SubElement(root, 'url')
        SubElement(u, 'loc').text = BASE + 'news/' + urllib.parse.quote(slug_id(item['id'])) + '.html'
    ElementTree(root).write(ROOT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)

    ns = Element('urlset', {
        'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'xmlns:news': 'http://www.google.com/schemas/sitemap-news/0.9',
    })
    # Preserve the existing Google News sitemap file structure without changing article data.
    for item in news[-1000:]:
        u = SubElement(ns, 'url')
        SubElement(u, 'loc').text = BASE + 'news/' + urllib.parse.quote(slug_id(item['id'])) + '.html'
        n = SubElement(u, 'news:news')
        pub = SubElement(n, 'news:publication')
        SubElement(pub, 'news:name').text = 'বাংলা সংবাদ'
        SubElement(pub, 'news:language').text = 'bn'
        # Sheet date is retained as-is in JSON; sitemap date is only added when it is parseable.
        date = str(item['date'] or '')
        m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date)
        if m:
            SubElement(n, 'news:publication_date').text = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
        SubElement(n, 'news:title').text = item['title']
    ElementTree(ns).write(ROOT / 'news-sitemap.xml', encoding='utf-8', xml_declaration=True)


def main():
    news = sync_news()
    ads = sync_ads()
    write_compatibility_pages(news)
    write_sitemaps(news)
    print(f'Synced {len(news)} news rows and {len(ads)} ad rows from Google Sheets.')


if __name__ == '__main__':
    main()
