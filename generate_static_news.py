import json, re, urllib.request, urllib.parse, hashlib, mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree
from html import escape

SHEET_ID = '1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg'
SHEET_NAME = 'Bangla News'
BASE = 'https://abdurrazzak123.github.io/Banglasangbad/'
ROOT = Path(__file__).resolve().parent
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
    v = str(v).strip()
    bn = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
    v = v.translate(bn)
    m = re.fullmatch(r'Date\((\d+),(\d+),(\d+)(?:,(\d+),(\d+),(\d+))?\)', v)
    if m:
        y, mo, d = map(int, m.group(1,2,3))
        return datetime(y, mo+1, d, int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0), tzinfo=TZ)
    bn_months = {'জানুয়ারি':1,'জানুয়ারি':1,'ফেব্রুয়ারি':2,'ফেব্রুয়ারি':2,'মার্চ':3,'এপ্রিল':4,'মে':5,'জুন':6,'জুলাই':7,'আগস্ট':8,'সেপ্টেম্বর':9,'অক্টোবর':10,'নভেম্বর':11,'ডিসেম্বর':12}
    m = re.fullmatch(r'(\d{1,2})\s+([\u0980-\u09ff]+)\s+(\d{4})', v)
    if m and m.group(2) in bn_months:
        return datetime(int(m.group(3)), bn_months[m.group(2)], int(m.group(1)), tzinfo=TZ)
    for fmt in ('%Y-%m-%dT%H:%M:%S%z','%Y-%m-%d %H:%M:%S','%Y-%m-%d','%m/%d/%Y %H:%M:%S','%m/%d/%Y'):
        try:
            d=datetime.strptime(v,fmt)
            return d if d.tzinfo else d.replace(tzinfo=TZ)
        except ValueError: pass
    return None


def image_url(v):
    v = (v or '').strip()
    m = re.search(r'drive\.google\.com/(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)', v, re.I)
    return f'https://drive.google.com/thumbnail?id={m.group(1)}&sz=w2000' if m else v


MEDIA = ROOT / 'news-media'
MEDIA.mkdir(exist_ok=True)

def drive_id(v):
    v = (v or '').strip()
    m = re.search(r'drive\.google\.com/(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)', v, re.I)
    return m.group(1) if m else ''

def download_drive_image(v, name_prefix):
    fid = drive_id(v)
    if not fid:
        return v
    ext = '.jpg'
    target = MEDIA / (name_prefix + '-' + hashlib.sha1(fid.encode()).hexdigest()[:16] + ext)
    if not target.exists():
        urls = [
            f'https://drive.google.com/thumbnail?id={fid}&sz=w2000',
            f'https://drive.google.com/uc?export=view&id={fid}',
        ]
        last = None
        for u in urls:
            try:
                req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                    ctype = (r.headers.get('Content-Type') or '').split(';')[0].lower()
                if not data or not ctype.startswith('image/'):
                    raise RuntimeError('Drive response is not an image')
                ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif'}
                ext = ext_map.get(ctype, '.jpg')
                target = MEDIA / (name_prefix + '-' + hashlib.sha1(fid.encode()).hexdigest()[:16] + ext)
                target.write_bytes(data)
                break
            except Exception as e:
                last = e
        else:
            print('WARNING: Drive image could not be downloaded:', fid, last)
            return image_url(v)
    return BASE + 'news-media/' + urllib.parse.quote(target.name)

def snapshot_rows(rows, sheet_name):
    return {'table': {'rows': rows}}

def fetch_sheet_rows(sheet_name):
    q = urllib.parse.quote('select *')
    u = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&sheet={urllib.parse.quote(sheet_name)}&tq={q}'
    req = urllib.request.Request(u, headers={'User-Agent': 'Banglasangbad-static-builder/1.0'})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode('utf-8')
    m = re.search(r'google\.visualization\.Query\.setResponse\((.*)\);?\s*$', raw, re.S)
    if not m:
        raise RuntimeError(f'Google Sheet response could not be parsed for {sheet_name}.')
    data = json.loads(m.group(1))
    return data.get('table', {}).get('rows', [])


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


rows = fetch_sheet_rows(SHEET_NAME)

# Preserve the Sheet row order and all 10 columns in the GitHub snapshot.
# Drive images are copied into the repository when publicly downloadable.
news_rows = json.loads(json.dumps(rows))
for row_no, row in enumerate(news_rows, 1):
    cells = row.get('c', [])
    for col in (4, 6, 7):
        if col < len(cells) and cells[col] is not None:
            original = str(cells[col].get('v', '') or '').strip()
            if original:
                cells[col]['v'] = download_drive_image(original, f'news-{row_no}-img{col-3}')
(ROOT / 'news-data.json').write_text(json.dumps(snapshot_rows(news_rows, SHEET_NAME), ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

# Ads follow the same Sheet -> GitHub snapshot path; no website-side Sheet request.
ads_rows = fetch_sheet_rows('Ads')
for row_no, row in enumerate(ads_rows, 1):
    cells = row.get('c', [])
    if len(cells) > 2 and cells[2] is not None:
        original = str(cells[2].get('v', '') or '').strip()
        if original:
            cells[2]['v'] = download_drive_image(original, f'ad-{row_no}')
(ROOT / 'ads-data.json').write_text(json.dumps(snapshot_rows(ads_rows, 'Ads'), ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

# The article generator consumes the same transformed rows, keeping article images in sync.
rows = news_rows

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

CSS = ''  # Detail CSS is served from detail.css


for p in NEWS.glob('*.html'):
    p.unlink()

for a in articles:
    sid=slug_id(a['id']); page=BASE+'news/'+urllib.parse.quote(sid)+'.html'
    description=desc(a['text'],a['title'])
    keywords=[x.strip() for x in re.split(r'[,،|\n]+',a['keywords']) if x.strip()][:15]
    paragraphs=[x.strip() for x in re.split(r'\n\s*\n|\n',a['text']) if x.strip()]
    content=''.join('<p>%s</p>'%escape(x) for x in paragraphs) or '<p>এই সংবাদের বিস্তারিত তথ্য পাওয়া যায়নি।</p>'
    hero=('\'<img class="detail-media" src="../%s" alt="%s" loading="eager">\'' % (escape(a['image'],quote=True).lstrip('./'),escape(a['title'],quote=True))) if a['image'] else ''
    extra=''.join('<figure class="detail-inline"><img src="../%s" alt="%s" loading="lazy"></figure>'%(escape(u,quote=True).lstrip('./'),escape(a['title'],quote=True)) for u in (a['image2'],a['image3']) if u)
    video=video_html(a['video'],a['title']).replace('<div class="video">','<div class="detail-video">')
    pub=a['dt'].isoformat(timespec='seconds') if a['dt'] else ''
    schema={'@context':'https://schema.org','@type':'NewsArticle','headline':a['title'],'description':description,'inLanguage':'bn','url':page,'mainEntityOfPage':{'@type':'WebPage','@id':page},'author':{'@type':'Organization','name':'বাংলা সংবাদ','url':BASE},'publisher':{'@type':'Organization','name':'বাংলা সংবাদ','logo':{'@type':'ImageObject','url':BASE+'logo.png'}},'image':[a['image']] if a['image'] else [BASE+'logo.png']}
    if pub: schema['datePublished']=pub; schema['dateModified']=pub
    if a['category']: schema['articleSection']=a['category']
    if keywords: schema['keywords']=keywords
    og_image=('<meta property="og:image" content="%s">'%escape(a['image'],quote=True)) if a['image'] else ''
    others=[x for x in articles if slug_id(x['id'])!=sid]
    others.sort(key=lambda x:x.get('dt') or datetime.min.replace(tzinfo=TZ),reverse=True)
    latest=[]
    for x in others[:8]:
        xid=slug_id(x['id']); xpage=BASE+'news/'+urllib.parse.quote(xid)+'.html'
        thumb=x['image']
        im='<img class="detail-latest-thumb" src="../%s" alt="" loading="lazy">'%escape(thumb,quote=True).lstrip('./') if thumb else ''
        latest.append('<a class="detail-latest-card%s" href="%s">%s<div class="detail-latest-info"><div class="detail-latest-cat">%s</div><div class="detail-latest-title">%s</div><div class="detail-latest-date">%s</div></div></a>'%(('' if thumb else ' no-thumb'),xpage,im,escape(x['category'] or 'সংবাদ'),escape(x['title']),escape(x['date'])))
    latest_html='<section class="detail-latest"><div class="detail-latest-head"><h2>সর্বশেষ সংবাদ</h2></div><div class="detail-latest-list">%s</div></section>'%''.join(latest)
    nav=[('হোম','../home.html'),('জাতীয়','../national.html'),('রাজনীতি','../politics.html'),('আন্তর্জাতিক','../international.html'),('অর্থনীতি','../economy.html'),('খেলাধুলা','../sports.html'),('বিনোদন','../entertainment.html'),('প্রযুক্তি','../technology.html'),('আরও','../more.html')]
    nav_html=''.join('<a href="%s">%s</a>'%(u,n) for n,u in nav)
    html="""<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s | বাংলা সংবাদ</title><meta name="description" content="%s"><meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="%s"><meta property="og:type" content="article"><meta property="og:title" content="%s"><meta property="og:description" content="%s"><meta property="og:url" content="%s"><meta property="og:site_name" content="বাংলা সংবাদ">%s<meta name="twitter:card" content="summary_large_image"><link rel="stylesheet" href="../detail.css?v=20260910-clean"><link rel="stylesheet" href="../ads.css?v=20260910-clean"><script type="application/ld+json">%s</script></head><body><div class="ad-slot top sheet-ad-slot detail-ad" data-ad-slot="top" aria-label="বিজ্ঞাপন"></div><div class="top-bar">বাংলা সংবাদ — সত্য ও নির্ভরযোগ্য খবর</div><header class="site-header"><div class="header-inner"><div class="logo"><a href="../home.html"><img src="../logo.png" alt="বাংলা সংবাদ লোগো" class="logo-image"></a></div><div id="live-date">%s</div></div></header><nav class="nav"><div class="nav-inner">%s</div></nav><main class="detail-wrap"><div class="detail-main"><div class="detail-breadcrumb">%s</div><div class="detail-category">%s</div><h1 class="detail-title">%s</h1><div class="detail-meta">%s &nbsp; • &nbsp; প্রতিবেদক: বাংলা সংবাদ ডেস্ক</div><div class="ad-slot middle-top sheet-ad-slot detail-ad" data-ad-slot="middle-top" aria-label="বিজ্ঞাপন"></div><article class="detail-article">%s<div class="detail-content">%s</div>%s%s</article><div class="ad-slot middle-bottom sheet-ad-slot detail-ad" data-ad-slot="middle-bottom" aria-label="বিজ্ঞাপন"></div>%s<div class="ad-slot bottom sheet-ad-slot detail-ad detail-bottom-ad" data-ad-slot="bottom" aria-label="বিজ্ঞাপন"></div></div></main><footer class="site-footer"><div class="links"><a href="../home.html">হোম</a><a href="../about.html">আমাদের সম্পর্কে</a><a href="../contact.html">যোগাযোগ</a><a href="../privacy.html">গোপনীয়তা নীতি</a></div><p>© ২০২৬ বাংলা সংবাদ — সর্বস্বত্ব সংরক্ষিত</p></footer><script src="../ads-loader.js?v=20260910-clean"></script></body></html>"""%(escape(a['title']),escape(description,quote=True),escape(page,quote=True),escape(a['title'],quote=True),escape(description,quote=True),escape(page,quote=True),og_image,json.dumps(schema,ensure_ascii=False,separators=(',',':')),escape(a['date']),nav_html,escape(a['category'] or 'সংবাদ'),escape(a['category'] or 'সংবাদ'),escape(a['title']),escape(a['date']),hero,content,extra,video,latest_html)
    (NEWS/(sid+'.html')).write_text(html,encoding='utf-8')

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
