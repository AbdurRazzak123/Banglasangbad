import json, re, urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree
from html import escape

# ============================================================
# Banglasangbad static news generator
# Deep-research revision: Details pages follow Home-page design
# while preserving the existing media/social JS hooks.
# ============================================================

SHEET_ID = '1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg'
SHEET_NAME = 'Bangla News'
BASE = 'https://abdurrazzak123.github.io/Banglasangbad/'
ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / 'news'
NEWS.mkdir(exist_ok=True)
TZ = ZoneInfo('Asia/Dhaka')

# Keep these as configuration only. Do not invent social URLs here.
# Existing social/share behaviour from the site's JS files remains loaded below.
SOCIAL_LINKS = {
    'facebook': '',
    'youtube': '',
    'instagram': '',
    'telegram': '',
}


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
    # Google Drive share URLs need a browser-loadable thumbnail endpoint.
    m = re.search(r'drive\.google\.com/(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)', v, re.I)
    if m:
        return f'https://drive.google.com/thumbnail?id={m.group(1)}&sz=w2000'
    if v.startswith('http://'):
        return 'https://' + v[7:]
    return v


def page_image_url(v):
    """Make image paths correct from /news/ID.html without breaking absolute URLs."""
    v = (v or '').strip()
    if not v:
        return ''
    if v.startswith(('https://', 'http://', 'data:', 'blob:')):
        return v
    v = v.lstrip('./')
    if v.startswith('assets/'):
        return '../' + v
    if v.startswith('/assets/'):
        return '..' + v
    return v


def slug_id(v):
    raw = str(v).strip()
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
    return '<p class="video-link"><a href="%s" rel="noopener noreferrer">▶ ভিডিও দেখুন</a></p>' % escape(url)


def social_share_html(page, title):
    """Share controls only; no fake account URLs are created."""
    u = urllib.parse.quote(page, safe='')
    t = urllib.parse.quote(title, safe='')
    return '''
    <div class="social-share" aria-label="সামাজিক যোগাযোগমাধ্যমে শেয়ার করুন">
      <span class="social-label">শেয়ার করুন</span>
      <a class="social-btn fb" href="https://www.facebook.com/sharer/sharer.php?u=%s" target="_blank" rel="noopener noreferrer">Facebook</a>
      <a class="social-btn wa" href="https://api.whatsapp.com/send?text=%s%%20%s" target="_blank" rel="noopener noreferrer">WhatsApp</a>
      <a class="social-btn tg" href="https://t.me/share/url?url=%s&text=%s" target="_blank" rel="noopener noreferrer">Telegram</a>
      <button class="social-btn copy" type="button" onclick="navigator.clipboard&&navigator.clipboard.writeText(location.href).then(()=>{this.textContent='কপি হয়েছে'})">লিংক কপি</button>
    </div>
    ''' % (u, t, u, u, t)


# ------------------------- Google Sheet -------------------------
q = urllib.parse.quote('select *')
url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&sheet={urllib.parse.quote(SHEET_NAME)}&tq={q}'
req = urllib.request.Request(url, headers={'User-Agent': 'Banglasangbad-static-builder/2.0'})
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
        'text': cell(row, 3),          # FULL Details column; never truncate article body
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

# ------------------------- Home-style CSS -------------------------
CSS = r'''
*{box-sizing:border-box}
:root{--bn-green:#006a4e;--bn-dark:#063b2b;--bn-red:#d71920;--bn-bg:#f4f6f8;--bn-text:#202124}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bn-bg);color:var(--bn-text);font-family:Arial,"Noto Sans Bengali","SolaimanLipi",sans-serif;line-height:1.75}
a{color:inherit}
.ad-slot{width:100%;min-height:0}
.top-ad-space{margin:0 auto}
.top-bar{background:var(--bn-dark);color:#fff;text-align:center;padding:8px 10px;font-size:13px}
.site-header{height:96px;min-height:96px;background:#fff;border-bottom:3px solid var(--bn-red);padding:6px 12px;overflow:hidden}
.header-inner{height:100%;max-width:1200px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:14px}
.logo{display:flex;align-items:center;min-width:0}
.logo-image{display:block;width:260px;max-width:72vw;max-height:78px;height:auto;object-fit:contain}
.logo-fallback{display:none}
#live-date{font-size:14px;color:#4b5563;white-space:nowrap}
.nav{background:#fff;border-bottom:1px solid #e5e7eb;position:relative;z-index:2}
.nav-inner{max-width:1200px;margin:auto;display:flex;align-items:center;justify-content:center;gap:0;overflow-x:auto;white-space:nowrap}
.nav a{display:block;padding:10px 13px;text-decoration:none;font-size:14px;font-weight:700;color:#1f2937}
.nav a:hover,.nav a.active{color:var(--bn-red)}
.breaking{background:#fff;border-bottom:1px solid #e5e7eb}
.breaking-news-container{max-width:1200px;margin:auto;display:flex;min-height:38px;align-items:center;overflow:hidden}
.breaking-title{background:var(--bn-red);color:#fff;font-weight:700;padding:7px 12px;flex:0 0 auto;font-size:13px}
.ticker-window{overflow:hidden;flex:1;padding:0 12px;white-space:nowrap}
#breaking-ticker{font-size:13px;color:#374151;overflow:hidden;text-overflow:ellipsis}
.container{max-width:1200px;margin:0 auto}
.home-main-layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:20px;padding:20px 12px 0;align-items:start}
.article-panel{background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden}
.article-inner{padding:20px}
.article-category{display:inline-block;color:var(--bn-red);font-weight:800;font-size:14px;margin-bottom:4px}
.article-title{font-size:34px;line-height:1.35;margin:4px 0 8px;font-weight:800;color:#111827}
.article-meta{font-size:13px;color:#6b7280;margin-bottom:14px}
.details-container{width:100%}
.details-container>img,.detail-inline-media img,.reader-inline-media img,.article-hero{width:100%!important;height:auto!important;max-height:620px!important;object-fit:contain!important;object-position:center!important;background:#fff!important;display:block!important;border-radius:6px!important;margin:0 auto 20px!important}
.article-body{font-size:17px;line-height:1.9;color:#252a31}
.article-body p{margin:0 0 18px}
.article-body h2,.article-body h3{line-height:1.45;color:#111827;margin:24px 0 10px}
.video{margin:24px 0}
.video iframe,.video video{display:block;width:100%;aspect-ratio:16/9;border:0;background:#000;border-radius:6px}
.video-link{margin:20px 0}
.video-link a{color:var(--bn-green);font-weight:700}
.tags{display:flex;gap:7px;flex-wrap:wrap;margin-top:20px}
.tag{border:1px solid #dfe3e7;border-radius:999px;padding:3px 9px;font-size:12px;color:#5f6368;background:#fff}
.social-share{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:22px 0 4px;padding-top:16px;border-top:1px solid #eee}
.social-label{font-size:13px;font-weight:700;color:#4b5563;margin-right:2px}
.social-btn{border:1px solid #d9dde2;background:#fff;border-radius:6px;padding:6px 10px;font-size:12px;font-weight:700;text-decoration:none;cursor:pointer}
.social-btn:hover{background:#f5f7f9}
.sidebar{background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden}
.sidebar h2{font-size:18px;margin:0;padding:12px 14px;background:var(--bn-dark);color:#fff}
.latest-news-scroll{max-height:620px;overflow:auto;padding:0 12px}
.category-latest-item{padding:10px 0!important;border-bottom:1px solid #eee!important}
.category-latest-item a{display:flex!important;align-items:center!important;gap:10px!important;text-decoration:none!important;color:inherit!important}
.category-latest-thumb{display:block!important;flex:0 0 92px!important;width:92px!important;height:68px!important;border-radius:6px!important;overflow:hidden!important;background:#d1d5db!important}
.category-latest-thumb img{display:block!important;width:100%!important;height:100%!important;object-fit:cover!important}
.category-latest-title{display:block!important;flex:1!important;font-size:15px!important;line-height:1.45!important;font-weight:700!important;color:#1f2937!important}
.section-title{max-width:1200px;margin:22px auto 10px;padding:0 12px;font-size:21px;color:#111827}
.category-six-grid{max-width:1200px;margin:0 auto;padding:0 12px 20px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.category-six-grid .news-card{background:#fff!important;border:1px solid #ddd!important;border-radius:6px!important;overflow:hidden!important}
.category-card-link{display:block;text-decoration:none}
.category-six-grid .news-card .news-image{height:170px!important;min-height:170px!important;max-height:170px!important;overflow:hidden!important;background:#e5e7eb}
.category-six-grid .news-card .news-image img{display:block!important;width:100%!important;height:170px!important;object-fit:cover!important}
.category-card-title{padding:11px 12px 13px;font-weight:700;font-size:15px;line-height:1.5;color:#1f2937}
.middle-ad{max-width:1200px;margin:12px auto;padding:0 12px}
.footer-ad{max-width:1200px;margin:0 auto;padding:0 12px}
.site-footer{background:linear-gradient(135deg,#071f2b,#003b2b)!important;border-top:4px solid var(--bn-red)!important;color:#d1d5db;text-align:center;padding:26px 14px;font-size:13px}
.site-footer h3{color:#fff;margin:0 0 4px;font-size:19px}
.site-footer p{margin:4px 0}
.site-footer .links{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 16px;margin:10px 0}
.site-footer a{color:#fff;text-decoration:none}
.image-load-failed{background:#f3f4f6;position:relative}
@media(max-width:900px){
 .home-main-layout{grid-template-columns:minmax(0,1fr) 290px}
 .article-title{font-size:29px}
}
@media(max-width:768px){
 .site-header{height:76px;min-height:76px;padding:6px 10px}
 .logo-image{width:190px;max-width:62vw;max-height:58px}
 #live-date{font-size:11px}
 .nav-inner{justify-content:flex-start}
 .nav a{padding:9px 11px;font-size:13px}
 .home-main-layout{display:flex!important;flex-direction:column!important;width:100%!important;max-width:100%!important;padding:12px 12px 0!important;gap:20px!important}
 .home-main-layout>.article-panel,.home-main-layout>.home-sidebar{width:100%!important;max-width:100%!important}
 .home-main-layout>.home-sidebar{order:2!important;margin-top:0!important}
 .article-inner{padding:15px}
 .article-title{font-size:22px;line-height:1.45}
 .article-body{font-size:15px;line-height:1.75}
 .article-meta{font-size:12px}
 .details-container>img,.detail-inline-media img,.reader-inline-media img,.article-hero{max-height:none!important;height:auto!important;object-fit:contain!important}
 .category-latest-thumb{flex-basis:88px!important;width:88px!important;height:64px!important}
 .category-latest-title{font-size:14px!important}
 .section-title{font-size:19px;margin-top:18px}
 .category-six-grid{grid-template-columns:1fr 1fr;gap:10px}
 .category-six-grid .news-card .news-image,.category-six-grid .news-card .news-image img{height:190px!important;min-height:190px!important;max-height:190px!important}
}
@media(max-width:380px){.logo-image{width:170px;max-height:52px}.category-six-grid{grid-template-columns:1fr}}
'''

# ------------------------- Generate article pages -------------------------
for p in NEWS.glob('*.html'):
    p.unlink()

sorted_articles = sorted(articles, key=lambda x: x['dt'] or datetime.min.replace(tzinfo=TZ), reverse=True)


def latest_html(current_id):
    out = []
    for a in sorted_articles[:10]:
        sid = slug_id(a['id'])
        if sid == slug_id(current_id):
            continue
        im = page_image_url(a['image'])
        img = '<img alt="%s" loading="lazy" src="%s">' % (escape(a['title'], quote=True), escape(im, quote=True)) if im else ''
        out.append('<article class="latest-item category-latest-item"><a data-category-news-id="%s" data-news-id="%s" href="%snews/%s.html"><span class="category-latest-thumb">%s</span><span class="category-latest-title">%s</span></a></article>' % (
            escape(str(a['id'])), escape(str(a['id'])), BASE, urllib.parse.quote(sid), img, escape(a['title'])
        ))
    return ''.join(out) or '<p style="padding:15px">আরও সংবাদ শিগগিরই প্রকাশ হবে।</p>'


def category_cards(current_id):
    wanted = ['জাতীয়','রাজনীতি','আন্তর্জাতিক','অর্থনীতি','খেলাধুলা','বিনোদন','প্রযুক্তি']
    chosen = []
    used = set()
    for cat in wanted:
        for a in sorted_articles:
            if a['category'].strip().lower() == cat.lower() and slug_id(a['id']) not in used:
                chosen.append(a); used.add(slug_id(a['id'])); break
    # Fill to six with newest articles if fewer categories are present.
    for a in sorted_articles:
        if len(chosen) >= 6: break
        if slug_id(a['id']) not in used and slug_id(a['id']) != slug_id(current_id):
            chosen.append(a); used.add(slug_id(a['id']))
    out=[]
    for a in chosen[:6]:
        sid=slug_id(a['id']); im=page_image_url(a['image'])
        image = '<div class="news-image"><img src="%s" alt="%s" loading="lazy"></div>' % (escape(im, quote=True), escape(a['title'], quote=True)) if im else '<div class="news-image"></div>'
        out.append('<article class="news-card"><a class="category-card-link" data-category-news-id="%s" data-news-id="%s" href="%snews/%s.html">%s<div class="category-card-title">%s</div></a></article>' % (
            escape(str(a['id'])), escape(str(a['id'])), BASE, urllib.parse.quote(sid), image, escape(a['title'])
        ))
    return ''.join(out)


for a in articles:
    sid = slug_id(a['id'])
    page = BASE + 'news/' + urllib.parse.quote(sid) + '.html'
    description = desc(a['text'], a['title'])
    keywords = [x.strip() for x in re.split(r'[,،|\n]+', a['keywords']) if x.strip()][:15]
    paragraphs = [x.strip() for x in re.split(r'\n\s*\n|\n', a['text']) if x.strip()]
    content = ''.join('<p>%s</p>' % escape(x) for x in paragraphs) or '<p>এই সংবাদের বিস্তারিত তথ্য পাওয়া যায়নি।</p>'

    hero = ''
    im = page_image_url(a['image'])
    if im:
        hero = '<img class="article-hero" src="%s" alt="%s" loading="eager">' % (escape(im, quote=True), escape(a['title'], quote=True))

    extra = ''.join('<figure class="detail-inline-media"><img src="%s" alt="%s" loading="lazy"></figure>' % (escape(page_image_url(u), quote=True), escape(a['title'], quote=True)) for u in (a['image2'], a['image3']) if u)
    tags = ''.join('<span class="tag">%s</span>' % escape(x) for x in keywords)
    tag_html = '<div class="tags">%s</div>' % tags if tags else ''
    pub = a['dt'].isoformat(timespec='seconds') if a['dt'] else ''

    schema = {
        '@context':'https://schema.org',
        '@type':'NewsArticle',
        'headline':a['title'],
        'description':description,
        'inLanguage':'bn',
        'url':page,
        'mainEntityOfPage':{'@type':'WebPage','@id':page},
        'author':{'@type':'Organization','name':'বাংলা সংবাদ','url':BASE},
        'publisher':{'@type':'Organization','name':'বাংলা সংবাদ','logo':{'@type':'ImageObject','url':BASE+'logo.png'}},
        'image':[im] if im else [BASE+'logo.png'],
    }
    if pub:
        schema['datePublished']=pub; schema['dateModified']=pub
    if a['category']: schema['articleSection']=a['category']
    if keywords: schema['keywords']=keywords

    og_image = '<meta property="og:image" content="%s">' % escape(im, quote=True) if im else ''
    nav = '''<a href="../home.html" class="active">হোম</a><a href="../national.html">জাতীয়</a><a href="../politics.html">রাজনীতি</a><a href="../international.html">আন্তর্জাতিক</a><a href="../economy.html">অর্থনীতি</a><a href="../sports.html">খেলাধুলা</a><a href="../entertainment.html">বিনোদন</a><a href="../technology.html">প্রযুক্তি</a><a href="../more.html">আরও</a>'''

    html = '''<!doctype html>
<html lang="bn">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s | বাংলা সংবাদ</title>
<meta name="description" content="%s">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="%s">
<meta property="og:type" content="article"><meta property="og:title" content="%s"><meta property="og:description" content="%s"><meta property="og:url" content="%s"><meta property="og:site_name" content="বাংলা সংবাদ">%s
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="../ads.css?v=20260907-ads-v26-sequential-final">
<link rel="stylesheet" href="../image-pattern.css">
<style>%s</style>
<script type="application/ld+json">%s</script>
</head>
<body>
<div class="ad-slot top sheet-ad-slot" data-ad-position="top" data-ad-slot="top" aria-label="বিজ্ঞাপন"></div>
<div class="top-bar">বাংলা সংবাদ — সত্য ও নির্ভরযোগ্য খবর</div>
<header class="site-header"><div class="header-inner"><div class="logo"><a href="../home.html" aria-label="বাংলা সংবাদ"><img src="../logo.png" alt="বাংলা সংবাদ লোগো" class="logo-image"></a></div><div id="live-date">তারিখ</div></div></header>
<nav class="nav"><div class="nav-inner">%s</div></nav>
<div class="breaking"><div class="breaking-news-container"><div class="breaking-title">ব্রেকিং নিউজ</div><div class="ticker-window"><div class="ticker-track" id="breaking-ticker">সর্বশেষ শিরোনাম লোড হচ্ছে...</div></div></div></div>
<main class="container home-main-layout">
<section id="home-feature" class="article-panel"><article class="article-inner">
<div class="article-category">%s</div>
<h1 class="article-title">%s</h1>
<div class="article-meta">%s &nbsp; • &nbsp; প্রতিবেদক: বাংলা সংবাদ ডেস্ক</div>
<div class="details-container">%s</div>
<div class="article-body">%s</div>
%s
%s
%s
%s
</article></section>
<aside class="sidebar home-sidebar"><h2>সর্বশেষ ১০ সংবাদ</h2><div class="latest-news-scroll">%s</div></aside>
<div class="ad-slot in-article sheet-ad-slot middle" data-ad-position="middle-top" data-ad-slot="middle-top" aria-label="বিজ্ঞাপন"></div>
<div class="ad-slot in-article sheet-ad-slot middle" data-ad-position="middle-bottom" data-ad-slot="middle-bottom" aria-label="বিজ্ঞাপন"></div>
</main>
<h2 class="section-title">সর্বশেষ ৬ ক্যাটাগরির খবর</h2>
<section class="news-grid category-six-grid" id="category-six-grid">%s</section>
<div class="ad-slot footer-ad sheet-ad-slot bottom" data-ad-position="bottom" data-ad-slot="bottom" aria-label="বিজ্ঞাপন"></div>
<footer class="site-footer"><h3>বাংলা সংবাদ</h3><p>সর্বশেষ সংবাদ সবার আগে</p><div class="links"><a href="../about.html">আমাদের সম্পর্কে</a><a href="../contact.html">যোগাযোগ</a><a href="../privacy.html">গোপনীয়তা নীতি</a><a href="../disclaimer.html">দাবিত্যাগ</a><a href="../advertise.html">বিজ্ঞাপন দিন</a></div><p>© ২০২৬ বাংলা সংবাদ — সর্বস্বত্ব সংরক্ষিত</p></footer>
<script>document.addEventListener('DOMContentLoaded',function(){var d=document.getElementById('live-date');if(d){d.textContent=new Intl.DateTimeFormat('bn-BD',{year:'numeric',month:'long',day:'numeric',weekday:'long'}).format(new Date())}});</script>
<script src="../ads-loader.js?v=20260907-ads-v26-sequential-final"></script>
<script src="../news-media.js?v=20260912-details-v1"></script>
<script src="../news-reader.js"></script>
</body></html>''' % (
        escape(a['title']), escape(description, quote=True), escape(page, quote=True), escape(a['title'], quote=True), escape(description, quote=True), escape(page, quote=True), og_image,
        CSS, json.dumps(schema, ensure_ascii=False, separators=(',',':')), nav,
        escape(a['category'] or 'সংবাদ'), escape(a['title']), escape(a['date']), hero, content,
        extra, video_html(a['video'], a['title']), social_share_html(page, a['title']), tag_html,
        latest_html(a['id']), category_cards(a['id'])
    )
    (NEWS / (sid + '.html')).write_text(html, encoding='utf-8')

# ------------------------- Sitemaps -------------------------
now = datetime.now(TZ)
static = ['', 'home.html', 'national.html', 'politics.html', 'international.html', 'economy.html', 'sports.html', 'entertainment.html', 'technology.html', 'more.html', 'about.html', 'contact.html', 'privacy.html', 'disclaimer.html', 'advertise.html']
root = Element('urlset', {'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9'})
for p in static:
    u=SubElement(root,'url'); SubElement(u,'loc').text=BASE+p; SubElement(u,'lastmod').text=now.date().isoformat()
for a in articles:
    u=SubElement(root,'url'); SubElement(u,'loc').text=BASE+'news/'+urllib.parse.quote(slug_id(a['id']))+'.html'
    if a['dt']: SubElement(u,'lastmod').text=a['dt'].date().isoformat()
ElementTree(root).write(ROOT/'sitemap.xml',encoding='utf-8',xml_declaration=True)

cutoff=now-timedelta(days=2)
ns=Element('urlset',{'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9','xmlns:news':'http://www.google.com/schemas/sitemap-news/0.9'})
fresh=[a for a in articles if a['dt'] and cutoff<=a['dt']<=now+timedelta(minutes=10)]
for a in sorted(fresh,key=lambda x:x['dt'],reverse=True)[:1000]:
    u=SubElement(ns,'url'); SubElement(u,'loc').text=BASE+'news/'+urllib.parse.quote(slug_id(a['id']))+'.html'
    n=SubElement(u,'news:news'); pn=SubElement(n,'news:publication'); SubElement(pn,'news:name').text='বাংলা সংবাদ'; SubElement(pn,'news:language').text='bn'
    SubElement(n,'news:publication_date').text=a['dt'].isoformat(timespec='seconds'); SubElement(n,'news:title').text=a['title']
ElementTree(ns).write(ROOT/'news-sitemap.xml',encoding='utf-8',xml_declaration=True)

print('Generated %d article pages and %d Google News entries.' % (len(articles),len(fresh)))
