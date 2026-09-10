import json, re, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree
from html import escape

SHEET_ID = '1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg'
SHEET_NAME = 'Bangla News'
BASE = 'https://abdurrazzak123.github.io/Banglasangbad/'
ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / 'news'
MEDIA = ROOT / 'assets' / 'news-media'
DATA_FILE = ROOT / 'news-data.json'
TZ = ZoneInfo('Asia/Dhaka')

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'}


def cell(row, idx):
    c = row.get('c', [])
    if idx >= len(c) or c[idx] is None:
        return ''
    return str(c[idx].get('v', '') or '').strip()


def parse_date(v):
    if not v:
        return None
    m = re.fullmatch(r'Date\((\d+),(\d+),(\d+)(?:,(\d+),(\d+),(\d+))?\)', v)
    if m:
        y, mo, d = map(int, m.group(1, 2, 3))
        return datetime(y, mo + 1, d, int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0), tzinfo=TZ)
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y'):
        try:
            d = datetime.strptime(v, fmt)
            return d if d.tzinfo else d.replace(tzinfo=TZ)
        except ValueError:
            pass
    return None


def normalize_id(v):
    raw = str(v or '').strip()
    m = re.fullmatch(r'(\d+)\.0+', raw)
    return m.group(1) if m else raw


def slug_id(v):
    raw = normalize_id(v)
    s = re.sub(r'[^A-Za-z0-9_-]+', '-', raw).strip('-')
    return s or 'article'


def drive_id(url):
    raw = str(url or '').strip()
    patterns = [
        r'drive\.google\.com/file/d/([A-Za-z0-9_-]+)',
        r'drive\.google\.com/open\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)',
        r'drive\.google\.com/uc\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)',
        r'drive\.usercontent\.google\.com/download\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)',
    ]
    for p in patterns:
        m = re.search(p, raw, re.I)
        if m:
            return m.group(1)
    return ''


def guess_ext(url, content_type=''):
    ct = (content_type or '').split(';', 1)[0].lower().strip()
    by_type = {
        'image/jpeg': '.jpg', 'image/jpg': '.jpg', 'image/png': '.png',
        'image/webp': '.webp', 'image/gif': '.gif', 'image/avif': '.avif'
    }
    if ct in by_type:
        return by_type[ct]
    path = urllib.parse.urlparse(url).path.lower()
    ext = Path(path).suffix
    return ext if ext in IMAGE_EXTS else '.jpg'


def download_image(url, out_path):
    raw = str(url or '').strip()
    if not raw:
        return ''
    if raw.startswith('assets/') or raw.startswith('../assets/'):
        return raw
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ('http', 'https'):
        return raw

    did = drive_id(raw)
    candidates = []
    if did:
        candidates = [
            f'https://drive.usercontent.google.com/download?id={did}&export=download&confirm=t',
            f'https://drive.google.com/uc?export=download&id={did}&confirm=t',
        ]
    else:
        candidates = [raw]

    last_error = None
    for candidate in candidates:
        try:
            req = urllib.request.Request(candidate, headers={'User-Agent': 'Mozilla/5.0 (GitHub Actions; Banglasangbad)'})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
                ctype = r.headers.get('Content-Type', '')
                if not ctype.lower().startswith('image/'):
                    # Some servers omit Content-Type; accept only a known image extension.
                    if Path(urllib.parse.urlparse(raw).path).suffix.lower() not in IMAGE_EXTS:
                        raise ValueError(f'not an image ({ctype})')
                ext = guess_ext(raw, ctype)
                final = out_path.with_suffix(ext)
                final.parent.mkdir(parents=True, exist_ok=True)
                final.write_bytes(data)
                return str(final.relative_to(ROOT)).replace('\\', '/')
        except Exception as e:
            last_error = e
    print(f'WARNING: image download failed for {raw}: {last_error}')
    return raw


def preview_remaining(text):
    clean = re.sub(r'\r\n?', '\n', str(text or '')).strip()
    if not clean:
        return '', ''
    # One deterministic preview is stored in GitHub data. Cards still use CSS line-clamp:3.
    # Keeping the preview short makes the Details page begin close to the visible 3-line teaser.
    limit = 180
    if len(clean) <= limit:
        return clean, ''
    cut = clean.rfind(' ', 0, limit + 1)
    if cut < 120:
        cut = limit
    preview = clean[:cut].strip() + '…'
    remaining = clean[cut:].strip()
    return preview, remaining


def desc(text, title):
    t = re.sub(r'\s+', ' ', text or '').strip()
    return title if not t else (t[:152].rstrip() + '...' if len(t) > 155 else t)


def video_html(url, title, prefix='../'):
    if not url:
        return ''
    m = re.search(r'(?:youtu\.be/|[?&]v=|youtube\.com/(?:embed|shorts|live)/)([\w-]{6,})', url)
    if m:
        return '<div class="sheet-video"><iframe loading="lazy" src="https://www.youtube.com/embed/%s" title="%s" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div>' % (escape(m.group(1)), escape(title))
    if re.search(r'\.(mp4|webm|ogg)(?:\?.*)?$', url, re.I):
        return '<div class="sheet-video"><video controls preload="metadata" src="%s"></video></div>' % escape(url)
    return '<p><a href="%s" target="_blank" rel="noopener" class="read-more-btn">▶ ভিডিও দেখুন</a></p>' % escape(url)


def load_sheet_articles():
    q = urllib.parse.quote('select *')
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&sheet={urllib.parse.quote(SHEET_NAME)}&tq={q}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Banglasangbad-static-builder/2.0'})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode('utf-8')
    m = re.search(r'google\.visualization\.Query\.setResponse\((.*)\);?\s*$', raw, re.S)
    if not m:
        raise RuntimeError('Google Sheet response could not be parsed. Make sure the sheet is public/published.')
    rows = json.loads(m.group(1)).get('table', {}).get('rows', [])
    return rows


def load_offline_articles():
    if not DATA_FILE.exists():
        raise RuntimeError('Offline test requested but news-data.json is missing.')
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    return [
        {**a, 'id': normalize_id(a.get('id')), 'text': a.get('text', a.get('summary', '')), 'dt': parse_date(a.get('date', ''))}
        for a in data
    ]


def build_articles():
    offline = False
    try:
        rows = load_sheet_articles()
    except Exception as e:
        if __import__('os').environ.get('OFFLINE_TEST') == '1':
            print(f'OFFLINE_TEST=1: using existing news-data.json because Sheet fetch failed: {e}')
            return load_offline_articles()
        raise

    articles = []
    seen = set()
    for i, row in enumerate(rows, 1):
        aid = normalize_id(cell(row, 0) or str(i))
        title = cell(row, 2)
        if not title or aid in seen:
            continue
        seen.add(aid)
        text = cell(row, 3)
        preview, remaining = preview_remaining(text)
        articles.append({
            'id': aid,
            'category': cell(row, 1),
            'title': title,
            'text': text,
            'preview': preview,
            'remaining': remaining,
            'image': cell(row, 4),
            'date': cell(row, 5),
            'image2': cell(row, 6),
            'image3': cell(row, 7),
            'video': cell(row, 8),
            'keywords': cell(row, 9),
            'dt': parse_date(cell(row, 5)),
        })
    return articles


def write_media_and_data(articles):
    MEDIA.mkdir(parents=True, exist_ok=True)
    # Track generated media so edited/removed images do not leave stale files behind.
    old_manifest = ROOT / '.generated-news-media.json'
    if old_manifest.exists():
        try:
            for rel in json.loads(old_manifest.read_text(encoding='utf-8')):
                p = ROOT / rel
                if p.is_file():
                    p.unlink()
        except Exception as e:
            print('WARNING: old media cleanup skipped:', e)

    generated = []
    for a in articles:
        for key, slot in [('image', 1), ('image2', 2), ('image3', 3)]:
            src = a.get(key, '')
            if not src:
                a[key] = ''
                continue
            stem = MEDIA / f"{slug_id(a['id'])}-{slot}"
            local = download_image(src, stem)
            a[key] = local
            if local.startswith('assets/news-media/'):
                generated.append(local)

    old_manifest.write_text(json.dumps(sorted(set(generated)), ensure_ascii=False, indent=2), encoding='utf-8')
    serial = []
    for a in articles:
        x = dict(a)
        x.pop('dt', None)
        serial.append(x)
    DATA_FILE.write_text(json.dumps(serial, ensure_ascii=False, indent=2), encoding='utf-8')


def render_detail_pages(articles):
    NEWS.mkdir(exist_ok=True)
    for p in NEWS.glob('*.html'):
        p.unlink()

    home = (ROOT / 'home.html').read_text(encoding='utf-8')
    head = home.split('</head>', 1)[0] + '</head>'
    body_start = home.split('<body>', 1)[1].split('<div class="container">', 1)[0]
    body_tail = home.split('<div class="ad-slot footer-ad', 1)[1]
    body_tail = '<div class="ad-slot footer-ad' + body_tail

    detail_css = '''<style id="generated-detail-feed">
.detail-feed-page{max-width:1200px;margin:20px auto;padding:0 15px}
.detail-main-card{background:#fff;border:1px solid #ddd;border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.detail-main-card .detail-image-wrap{width:100%;text-align:center;background:#f5f5f5}
.detail-main-card .detail-image-wrap img{display:block;width:100%;height:auto;max-height:650px;object-fit:contain;margin:0 auto}
.detail-main-content{padding:18px}
.detail-main-content .category-tag{color:#c1121f;font-weight:bold;font-size:13px;display:inline-block;margin-right:10px}
.detail-main-content .news-date{color:#777;font-size:13px}
.detail-main-content h1{font-size:30px;line-height:1.45;color:#111;margin:8px 0 14px}
.detail-remaining{font-size:17px;line-height:1.9;color:#333}
.detail-remaining p{margin:0 0 16px}
.detail-feed-title{font-size:22px;color:#990000;border-left:5px solid #990000;padding-left:10px;margin:28px 0 15px}
.detail-feed-list{display:flex;flex-direction:column;gap:15px;background:#fff;padding:20px;border-radius:5px;box-shadow:0 2px 5px rgba(0,0,0,.08)}
.detail-feed-card{border-bottom:1px solid #eee;padding-bottom:15px;margin-bottom:5px}
.detail-feed-card:last-child{border-bottom:none}
.detail-feed-card .detail-feed-image{width:100%;text-align:center;margin-bottom:10px}
.detail-feed-card .detail-feed-image img{display:block;width:100%;height:auto;max-height:460px;object-fit:contain}
.detail-feed-card h2{font-size:20px;color:#222;margin-bottom:8px;line-height:1.45}
.detail-feed-card .detail-feed-meta{font-size:12px;color:#888;margin-bottom:5px}
.detail-feed-card p{font-size:15px;color:#555;line-height:1.6}
.sheet-video{margin:20px 0;background:#000;border-radius:6px;overflow:hidden}.sheet-video iframe{width:100%;aspect-ratio:16/9;border:0;display:block}.sheet-video video{width:100%;display:block}
@media(max-width:768px){.detail-feed-page{padding:0 12px}.detail-main-content{padding:14px}.detail-main-content h1{font-size:24px}.detail-remaining{font-size:16px}.detail-feed-list{padding:14px}.detail-feed-card h2{font-size:19px}}
</style>'''

    for a in articles:
        sid = slug_id(a['id'])
        page_url = BASE + 'news/' + urllib.parse.quote(sid) + '.html'
        description = desc(a.get('text', ''), a['title'])
        keywords = [x.strip() for x in re.split(r'[,،|\n]+', a.get('keywords', '')) if x.strip()][:15]
        schema = {
            '@context':'https://schema.org','@type':'NewsArticle','headline':a['title'],
            'description':description,'inLanguage':'bn','url':page_url,
            'mainEntityOfPage':{'@type':'WebPage','@id':page_url},
            'author':{'@type':'Organization','name':'বাংলা সংবাদ','url':BASE},
            'publisher':{'@type':'Organization','name':'বাংলা সংবাদ','logo':{'@type':'ImageObject','url':BASE+'logo.png'}},
            'image':[BASE+a['image'][len('../'):] if a.get('image','').startswith('../') else (BASE+a['image'] if a.get('image','').startswith('assets/') else a.get('image') or BASE+'logo.png')],
        }
        if a.get('dt'):
            pub=a['dt'].isoformat(timespec='seconds'); schema['datePublished']=pub; schema['dateModified']=pub
        if a.get('category'): schema['articleSection']=a['category']
        if keywords: schema['keywords']=keywords

        h = head
        replacements = {
            r'<title>.*?</title>': f'<title>{escape(a["title"])} | বাংলা সংবাদ</title>',
            r'<link rel="canonical" href="[^"]*">': f'<link rel="canonical" href="{escape(page_url, quote=True)}">',
            r'<meta name="description" content="[^"]*">': f'<meta name="description" content="{escape(description, quote=True)}">',
            r'<meta property="og:title" content="[^"]*">': f'<meta property="og:title" content="{escape(a["title"], quote=True)}">',
            r'<meta property="og:description" content="[^"]*">': f'<meta property="og:description" content="{escape(description, quote=True)}">',
            r'<meta property="og:url" content="[^"]*">': f'<meta property="og:url" content="{escape(page_url, quote=True)}">',
            r'<meta property="og:type" content="[^"]*">': '<meta property="og:type" content="article">',
            r'<meta name="twitter:title" content="[^"]*">': f'<meta name="twitter:title" content="{escape(a["title"], quote=True)}">',
            r'<meta name="twitter:description" content="[^"]*">': f'<meta name="twitter:description" content="{escape(description, quote=True)}">',
            r'<meta name="keywords" content="[^"]*">': f'<meta name="keywords" content="{escape(", ".join(keywords), quote=True)}">',
        }
        for pattern, repl in replacements.items():
            h = re.sub(pattern, repl, h, count=1, flags=re.S)
        og = a.get('image','')
        if og:
            og_abs = BASE + og if og.startswith('assets/') else og
            h = re.sub(r'<meta property="og:image" content="[^"]*">', f'<meta property="og:image" content="{escape(og_abs, quote=True)}">', h, count=1)
        h = h.replace('</head>', detail_css + '<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False, separators=(',',':')) + '</script></head>')

        image = ''
        if a.get('image'):
            image = f'<div class="detail-image-wrap"><img src="../{escape(a["image"])}" alt="{escape(a["title"])}" loading="eager"></div>' if a['image'].startswith('assets/') else f'<div class="detail-image-wrap"><img src="{escape(a["image"])}" alt="{escape(a["title"])}" loading="eager"></div>'
        remaining = a.get('remaining','')
        if remaining:
            paragraphs = ''.join(f'<p>{escape(x)}</p>' for x in re.split(r'\n\s*\n|\n', remaining) if x.strip())
        else:
            paragraphs = '<p>এই সংবাদের বাকি অংশ নেই।</p>'

        main = f'''<div class="container detail-feed-page">
  <article class="detail-main-card" id="news-{escape(a['id'])}">
    {image}
    <div class="detail-main-content">
      <span class="category-tag">{escape(a.get('category',''))}</span><span class="news-date">{escape(a.get('date',''))}</span>
      <h1>{escape(a['title'])}</h1>
      <div class="detail-remaining">{paragraphs}</div>
      {video_html(a.get('video',''), a['title'])}
    </div>
  </article>
  <h2 class="detail-feed-title">আরও সংবাদ</h2>
  <section class="detail-feed-list">
'''
        cat = str(a.get('category','')).strip().lower()
        related = [x for x in reversed(articles) if str(x.get('category','')).strip().lower() == cat and normalize_id(x.get('id')) != normalize_id(a.get('id'))]
        for x in related:
            ximg = ''
            if x.get('image'):
                src = '../' + x['image'] if x['image'].startswith('assets/') else x['image']
                ximg = f'<div class="detail-feed-image"><img src="{escape(src)}" alt="{escape(x["title"])}" loading="lazy"></div>'
            main += f'''    <article class="detail-feed-card">
      <a href="{escape(sid and ("../news/"+urllib.parse.quote(slug_id(x['id']))+".html"))}">{ximg}<h2>{escape(x['title'])}</h2></a>
      <div class="detail-feed-meta">{escape(x.get('date',''))}</div>
      <p>{escape(x.get('preview') or x.get('text',''))}</p>
      <a class="read-more-btn" href="../news/{urllib.parse.quote(slug_id(x['id']))}.html">আরও পড়ুন</a>
    </article>\n'''
        if not related:
            main += '    <p style="color:#777;">এই ক্যাটাগরিতে আপাতত আর কোনো সংবাদ নেই।</p>\n'
        main += '  </section>\n</div>\n'
        html = '<!DOCTYPE html><html lang="bn">' + h.split('<html lang="bn">',1)[1] + '<body>' + body_start + main + body_tail.split('<body>',1)[-1] if False else None
        # Construct from head/body pieces without duplicating the head's opening tag.
        html = '<!DOCTYPE html><html lang="bn">' + h.split('<html lang="bn">',1)[1] + '<body>' + body_start + main + body_tail
        (NEWS / f'{sid}.html').write_text(html, encoding='utf-8')


def write_sitemaps(articles):
    now = datetime.now(TZ)
    static = ['', 'home.html', 'national.html', 'politics.html', 'international.html', 'economy.html', 'sports.html', 'entertainment.html', 'technology.html', 'more.html', 'about.html', 'contact.html', 'privacy.html', 'disclaimer.html', 'advertise.html']
    root = Element('urlset', {'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9'})
    for p in static:
        u=SubElement(root,'url'); SubElement(u,'loc').text=BASE+p; SubElement(u,'lastmod').text=now.date().isoformat()
    for a in articles:
        u=SubElement(root,'url'); SubElement(u,'loc').text=BASE+'news/'+urllib.parse.quote(slug_id(a['id']))+'.html'
        if a.get('dt'): SubElement(u,'lastmod').text=a['dt'].date().isoformat()
    ElementTree(root).write(ROOT/'sitemap.xml',encoding='utf-8',xml_declaration=True)

    cutoff=now-timedelta(days=2)
    ns=Element('urlset',{'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9','xmlns:news':'http://www.google.com/schemas/sitemap-news/0.9'})
    fresh=[a for a in articles if a.get('dt') and cutoff<=a['dt']<=now+timedelta(minutes=10)]
    for a in sorted(fresh,key=lambda x:x['dt'],reverse=True)[:1000]:
        u=SubElement(ns,'url'); SubElement(u,'loc').text=BASE+'news/'+urllib.parse.quote(slug_id(a['id']))+'.html'
        n=SubElement(u,'news:news'); pub=SubElement(n,'news:publication'); SubElement(pub,'news:name').text='বাংলা সংবাদ'; SubElement(pub,'news:language').text='bn'; SubElement(n,'news:publication_date').text=a['dt'].isoformat(timespec='seconds'); SubElement(n,'news:title').text=a['title']
    ElementTree(ns).write(ROOT/'news-sitemap.xml',encoding='utf-8',xml_declaration=True)


articles = build_articles()
if not articles:
    raise RuntimeError('No valid news rows found in the Google Sheet.')
write_media_and_data(articles)
render_detail_pages(articles)
write_sitemaps(articles)
print(f'Generated GitHub news data, {len(articles)} article pages, local media, sitemap.xml and news-sitemap.xml.')
