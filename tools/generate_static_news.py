import json, re, urllib.request, urllib.parse
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
NEWS.mkdir(exist_ok=True)
TZ = ZoneInfo('Asia/Dhaka')


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


def image_url(v):
    v = (v or '').strip()
    m = re.search(r'drive\.google\.com/(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)', v, re.I)
    return f'https://drive.google.com/thumbnail?id={m.group(1)}&sz=w2000' if m else v


def slug_id(v):
    raw = str(v).strip()
    # Google Sheets GViz may return numeric IDs such as 23.0.
    # Normalize integer-like IDs so article URLs stay stable: 23.html, not 23-0.html.
    m = re.fullmatch(r'(\d+)\.0+', raw)
    if m:
        raw = m.group(1)
    s = re.sub(r'[^A-Za-z0-9_-]+', '-', raw).strip('-')
    return s or 'article'


def desc(text, title):
    t = re.sub(r'\s+', ' ', text or '').strip()
    return title if not t else (t[:152].rstrip() + '...' if len(t) > 155 else t)


def video_html(url, title):
    if not url:
        return ''
    m = re.search(r'(?:youtu\.be/|[?&]v=|youtube\.com/(?:embed|shorts|live)/)([\w-]{6,})', url)
    if m:
        return '<div class="video"><iframe src="https://www.youtube.com/embed/%s" title="%s" loading="lazy" allowfullscreen></iframe></div>' % (escape(m.group(1)), escape(title))
    if re.search(r'\.(mp4|webm|ogg)(?:\?.*)?$', url, re.I):
        return '<div class="video"><video controls preload="metadata" src="%s"></video></div>' % escape(url)
    return '<p><a href="%s" rel="noopener">▶ ভিডিও দেখুন</a></p>' % escape(url)


q = urllib.parse.quote('select *')
url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&sheet={urllib.parse.quote(SHEET_NAME)}&tq={q}'
req = urllib.request.Request(url, headers={'User-Agent': 'Banglasangbad-static-builder/1.0'})
with urllib.request.urlopen(req, timeout=45) as r:
    raw = r.read().decode('utf-8')
m = re.search(r'google\.visualization\.Query\.setResponse\((.*)\);?\s*$', raw, re.S)
if not m:
    raise RuntimeError('Google Sheet response could not be parsed. Make sure the sheet is public/published.')
rows = json.loads(m.group(1)).get('table', {}).get('rows', [])

articles = []
seen = set()
for i, row in enumerate(rows, 1):
    aid = cell(row, 0) or str(i)
    title = cell(row, 2)
    if not title or aid in seen:
        continue
    seen.add(aid)
    articles.append({
        'id': aid,
        'category': cell(row, 1),
        'title': title,
        'text': cell(row, 3),
        'image': image_url(cell(row, 4)),
        'date': cell(row, 5),
        'image2': image_url(cell(row, 6)),
        'image3': image_url(cell(row, 7)),
        'video': cell(row, 8),
        'keywords': cell(row, 9),
        'dt': parse_date(cell(row, 5)),
    })

if not articles:
    raise RuntimeError('No valid news rows found in the Google Sheet.')

CSS = '''*{box-sizing:border-box}body{margin:0;background:#f4f6f8;color:#202124;font-family:Arial,"Noto Sans Bengali","SolaimanLipi",sans-serif;line-height:1.85}.top{background:#063b2b;color:#fff;text-align:center;padding:8px;font-size:13px}.head{background:#fff;border-bottom:3px solid #d71920;padding:10px;text-align:center}.logo{width:210px;max-width:70vw}.wrap{max-width:900px;margin:18px auto;padding:0 12px}.article{background:#fff;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.08);padding:28px}.crumb{font-size:13px;color:#6b7280}.crumb a{color:#006a4e;text-decoration:none}.cat{color:#c1121f;font-weight:700}.title{font-size:34px;line-height:1.35;margin:7px 0 10px}.meta{color:#6b7280;font-size:14px;margin-bottom:18px}.hero,.inline-img{width:100%;height:auto;max-height:620px;object-fit:contain;border-radius:8px;background:#f2f2f2;display:block;margin:0 0 22px}.content{font-size:18px}.content p{margin:0 0 18px}.tags{display:flex;gap:7px;flex-wrap:wrap;margin-top:20px}.tag{border:1px solid #e1e5e8;border-radius:999px;padding:3px 9px;font-size:12px;color:#5f6368}.video{margin:24px 0}.video iframe,.video video{width:100%;aspect-ratio:16/9;border:0}.foot{margin-top:30px;background:#111827;color:#d1d5db;text-align:center;padding:25px;font-size:13px}.foot a{color:#fff;margin:0 7px}@media(max-width:700px){.article{padding:18px}.title{font-size:25px}.content{font-size:17px}}'''

for p in NEWS.glob('*.html'):
    p.unlink()

for a in articles:
    sid = slug_id(a['id'])
    page = BASE + 'news/' + urllib.parse.quote(sid) + '.html'
    description = desc(a['text'], a['title'])
    keywords = [x.strip() for x in re.split(r'[,،|\n]+', a['keywords']) if x.strip()][:15]
    paragraphs = [x.strip() for x in re.split(r'\n\s*\n|\n', a['text']) if x.strip()]
    content = ''.join('<p>%s</p>' % escape(x) for x in paragraphs) or '<p>এই সংবাদের বিস্তারিত তথ্য পাওয়া যায়নি।</p>'
    hero = ''
    if a['image']:
        hero = '<img class="hero" src="%s" alt="%s" loading="eager">' % (escape(a['image'], quote=True), escape(a['title'], quote=True))
    extra = ''.join('<figure><img class="inline-img" src="%s" alt="%s" loading="lazy"></figure>' % (escape(u, quote=True), escape(a['title'], quote=True)) for u in (a['image2'], a['image3']) if u)
    tags = ''.join('<span class="tag">%s</span>' % escape(x) for x in keywords)
    pub = a['dt'].isoformat(timespec='seconds') if a['dt'] else ''
    schema = {
        '@context': 'https://schema.org',
        '@type': 'NewsArticle',
        'headline': a['title'],
        'description': description,
        'inLanguage': 'bn',
        'url': page,
        'mainEntityOfPage': {'@type': 'WebPage', '@id': page},
        'author': {'@type': 'Organization', 'name': 'বাংলা সংবাদ', 'url': BASE},
        'publisher': {'@type': 'Organization', 'name': 'বাংলা সংবাদ', 'logo': {'@type': 'ImageObject', 'url': BASE + 'logo.png'}},
        'image': [a['image']] if a['image'] else [BASE + 'logo.png'],
    }
    if pub:
        schema['datePublished'] = pub
        schema['dateModified'] = pub
    if a['category']:
        schema['articleSection'] = a['category']
    if keywords:
        schema['keywords'] = keywords
    og_image = '<meta property="og:image" content="%s">' % escape(a['image'], quote=True) if a['image'] else ''
    tag_html = ''  # Keywords remain in JSON-LD SEO metadata but are hidden from readers.
    html = '''<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s | বাংলা সংবাদ</title><meta name="description" content="%s"><meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="%s"><meta property="og:type" content="article"><meta property="og:title" content="%s"><meta property="og:description" content="%s"><meta property="og:url" content="%s"><meta property="og:site_name" content="বাংলা সংবাদ">%s<meta name="twitter:card" content="summary_large_image"><style>%s</style><script type="application/ld+json">%s</script></head><body><div class="top">সত্য ও নির্ভরযোগ্য সংবাদ জানতে চোখ রাখুন বাংলা সংবাদের সঙ্গে</div><header class="head"><a href="%s" aria-label="বাংলা সংবাদ"><img class="logo" src="%slogo.png" alt="বাংলা সংবাদ"></a></header><main class="wrap"><article class="article"><div class="crumb"><a href="%s">হোম</a> / %s</div><div class="cat">%s</div><h1 class="title">%s</h1><div class="meta">%s &nbsp; • &nbsp; প্রতিবেদক: বাংলা সংবাদ ডেস্ক</div>%s<div class="content">%s</div>%s%s%s</article></main><footer class="foot"><a href="%s">হোম</a><a href="%sabout.html">আমাদের সম্পর্কে</a><a href="%scontact.html">যোগাযোগ</a><a href="%sprivacy.html">গোপনীয়তা নীতি</a><div>© ২০২৬ বাংলা সংবাদ — সর্বস্বত্ব সংরক্ষিত</div></footer></body></html>''' % (
        escape(a['title']), escape(description, quote=True), escape(page, quote=True), escape(a['title'], quote=True), escape(description, quote=True), escape(page, quote=True), og_image, CSS, json.dumps(schema, ensure_ascii=False, separators=(',', ':')), BASE, BASE, BASE, escape(a['category'] or 'সংবাদ'), escape(a['category'] or 'সংবাদ'), escape(a['title']), escape(a['date']), hero, content, extra, video_html(a['video'], a['title']), tag_html, BASE, BASE, BASE, BASE)
    (NEWS / (sid + '.html')).write_text(html, encoding='utf-8')

now = datetime.now(TZ)
static = ['', 'home.html', 'national.html', 'politics.html', 'international.html', 'economy.html', 'sports.html', 'entertainment.html', 'technology.html', 'more.html', 'about.html', 'contact.html', 'privacy.html', 'disclaimer.html', 'advertise.html']
root = Element('urlset', {'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9'})
for p in static:
    u = SubElement(root, 'url'); SubElement(u, 'loc').text = BASE + p; SubElement(u, 'lastmod').text = now.date().isoformat()
for a in articles:
    u = SubElement(root, 'url'); SubElement(u, 'loc').text = BASE + 'news/' + urllib.parse.quote(slug_id(a['id'])) + '.html'
    if a['dt']:
        SubElement(u, 'lastmod').text = a['dt'].date().isoformat()
ElementTree(root).write(ROOT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)

cutoff = now - timedelta(days=2)
ns = Element('urlset', {'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'xmlns:news': 'http://www.google.com/schemas/sitemap-news/0.9'})
fresh = [a for a in articles if a['dt'] and cutoff <= a['dt'] <= now + timedelta(minutes=10)]
for a in sorted(fresh, key=lambda x: x['dt'], reverse=True)[:1000]:
    u = SubElement(ns, 'url'); SubElement(u, 'loc').text = BASE + 'news/' + urllib.parse.quote(slug_id(a['id'])) + '.html'
    n = SubElement(u, 'news:news'); pub_node = SubElement(n, 'news:publication'); SubElement(pub_node, 'news:name').text = 'বাংলা সংবাদ'; SubElement(pub_node, 'news:language').text = 'bn'
    SubElement(n, 'news:publication_date').text = a['dt'].isoformat(timespec='seconds'); SubElement(n, 'news:title').text = a['title']
ElementTree(ns).write(ROOT / 'news-sitemap.xml', encoding='utf-8', xml_declaration=True)
print('Generated %d article pages and %d Google News entries.' % (len(articles), len(fresh)))
