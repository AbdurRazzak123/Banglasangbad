import json, os, re, urllib.request, urllib.parse, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree
from html import escape

SHEET_ID = os.environ.get('NEWS_SHEET_ID', '1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg')
SHEET_NAME = os.environ.get('NEWS_SHEET_NAME', 'Bangla News')
ROOT = Path(__file__).resolve().parent
NEWS = ROOT / 'news'
MEDIA = ROOT / 'news-media'
NEWS.mkdir(exist_ok=True)
MEDIA.mkdir(exist_ok=True)
TZ = ZoneInfo('Asia/Dhaka')


def site_base():
    raw = os.environ.get('SITE_BASE_URL', '').strip()
    if raw:
        return raw.rstrip('/') + '/'
    repo = os.environ.get('GITHUB_REPOSITORY', '').strip()
    if repo and '/' in repo:
        owner, name = repo.split('/', 1)
        return f'https://{owner}.github.io/{name}/'
    return ''

BASE = site_base()


def cell(row, idx):
    c = row.get('c', [])
    if idx >= len(c) or c[idx] is None:
        return ''
    return str(c[idx].get('v', '') or '').strip()


def parse_date(v):
    if not v:
        return None
    v = str(v).strip().translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
    m = re.fullmatch(r'Date\((\d+),(\d+),(\d+)(?:,(\d+),(\d+),(\d+))?\)', v)
    if m:
        y, mo, d = map(int, m.group(1, 2, 3))
        return datetime(y, mo + 1, d, int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0), tzinfo=TZ)
    months = {'জানুয়ারি':1,'জানুয়ারি':1,'ফেব্রুয়ারি':2,'ফেব্রুয়ারি':2,'মার্চ':3,'এপ্রিল':4,'মে':5,'জুন':6,'জুলাই':7,'আগস্ট':8,'সেপ্টেম্বর':9,'অক্টোবর':10,'নভেম্বর':11,'ডিসেম্বর':12}
    m = re.fullmatch(r'(\d{1,2})\s+([\u0980-\u09ff]+)\s+(\d{4})', v)
    if m and m.group(2) in months:
        return datetime(int(m.group(3)), months[m.group(2)], int(m.group(1)), tzinfo=TZ)
    for fmt in ('%Y-%m-%dT%H:%M:%S%z','%Y-%m-%d %H:%M:%S','%Y-%m-%d','%m/%d/%Y %H:%M:%S','%m/%d/%Y'):
        try:
            d = datetime.strptime(v, fmt)
            return d if d.tzinfo else d.replace(tzinfo=TZ)
        except ValueError:
            pass
    return None


def bangla_date(v, dt=None):
    """Return a consistent Bengali display date for article pages."""
    months = ['জানুয়ারি','ফেব্রুয়ারি','মার্চ','এপ্রিল','মে','জুন','জুলাই','আগস্ট','সেপ্টেম্বর','অক্টোবর','নভেম্বর','ডিসেম্বর']
    weekdays = ['সোমবার','মঙ্গলবার','বুধবার','বৃহস্পতিবার','শুক্রবার','শনিবার','রবিবার']
    d = dt or parse_date(v)
    if d:
        bn = str.maketrans('0123456789','০১২৩৪৫৬৭৮৯')
        return f'{weekdays[d.weekday()]}, {str(d.day).translate(bn)} {months[d.month-1]} {str(d.year).translate(bn)}'
    raw = str(v or '').strip()
    return raw.translate(str.maketrans('0123456789','০১২৩৪৫৬৭৮৯'))


def slug_id(v):
    raw = str(v).strip()
    m = re.fullmatch(r'(\d+)\.0+', raw)
    if m:
        raw = m.group(1)
    s = re.sub(r'[^A-Za-z0-9_-]+', '-', raw).strip('-')
    return s or 'article'


def drive_id(v):
    m = re.search(r'drive\.google\.com/(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=|thumbnail\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)', str(v or ''), re.I)
    return m.group(1) if m else ''


def download_drive_image(v, name_prefix):
    fid = drive_id(v)
    if not fid:
        return str(v or '').strip()
    target = MEDIA / (name_prefix + '-' + hashlib.sha1(fid.encode()).hexdigest()[:16] + '.jpg')
    if not target.exists():
        last = None
        for u in (f'https://drive.google.com/thumbnail?id={fid}&sz=w2000', f'https://drive.google.com/uc?export=view&id={fid}'):
            try:
                req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                    ctype = (r.headers.get('Content-Type') or '').split(';')[0].lower()
                if not data or not ctype.startswith('image/'):
                    raise RuntimeError('Drive response is not an image')
                ext = {'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','image/gif':'.gif'}.get(ctype, '.jpg')
                target = MEDIA / (name_prefix + '-' + hashlib.sha1(fid.encode()).hexdigest()[:16] + ext)
                target.write_bytes(data)
                break
            except Exception as e:
                last = e
        else:
            print('WARNING: Drive image download failed:', fid, last)
            return str(v or '').strip()
    return 'news-media/' + target.name


def fetch_sheet_rows(sheet_name):
    q = urllib.parse.quote('select *')
    u = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&sheet={urllib.parse.quote(sheet_name)}&tq={q}'
    req = urllib.request.Request(u, headers={'User-Agent': 'Banglasangbad-static-builder/2.0'})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode('utf-8')
    m = re.search(r'google\.visualization\.Query\.setResponse\((.*)\);?\s*$', raw, re.S)
    if not m:
        raise RuntimeError(f'Google Sheet response could not be parsed for {sheet_name}.')
    data = json.loads(m.group(1))
    return data.get('table', {}).get('rows', [])


def load_rows():
    snapshot_news = []
    snapshot_ads = []
    try:
        snapshot_news = json.loads((ROOT / 'news-data.json').read_text(encoding='utf-8')).get('table', {}).get('rows', [])
    except Exception:
        pass
    try:
        ads_file = ROOT / 'ads-data.json'
        snapshot_ads = json.loads(ads_file.read_text(encoding='utf-8')).get('table', {}).get('rows', []) if ads_file.exists() else []
    except Exception:
        pass
    if os.environ.get('USE_SNAPSHOT', '').lower() in ('1', 'true', 'yes'):
        return snapshot_news, snapshot_ads
    try:
        return fetch_sheet_rows(SHEET_NAME), fetch_sheet_rows('Ads')
    except Exception as exc:
        if snapshot_news:
            print('WARNING: Google Sheet fetch failed; preserving last known news snapshot:', exc)
            return snapshot_news, snapshot_ads
        raise


def normalize_rows(rows, is_ads=False):
    # Keep Google/Drive image URLs exactly as supplied by the Sheet.
    # Browser-side JavaScript resolves Drive URLs to renderable thumbnails.
    return json.loads(json.dumps(rows))


def snapshot(rows):
    return {'table': {'rows': rows}}


def clean_local_image(v):
    raw = str(v or '').strip()
    if not raw:
        return ''
    # Convert an absolute URL produced by an older generator back to its local media path.
    if raw.startswith(BASE):
        raw = raw[len(BASE):]
    if raw.startswith('./'):
        raw = raw[2:]
    raw = raw.lstrip('/')
    return raw


def article_image(article, index=0):
    key = ('image', 'image2', 'image3')[index]
    return clean_local_image(article.get(key, ''))


def image_src_for_news_page(v):
    local = clean_local_image(v)
    if not local:
        return ''
    if local.startswith(('http://', 'https://', 'data:')):
        return local
    return '../' + local


def body_html(text):
    parts = [x.strip() for x in re.split(r'\n\s*\n|\n', str(text or '')) if x.strip()]
    return ''.join('<p>%s</p>' % escape(x) for x in parts) or '<p>এই সংবাদের বিস্তারিত তথ্য পাওয়া যায়নি।</p>'


def description(text, title):
    t = re.sub(r'\s+', ' ', str(text or '')).strip()
    return title if not t else (t[:152].rstrip() + '...' if len(t) > 155 else t)


def video_html(url, title):
    if not url:
        return ''
    m = re.search(r'(?:youtu\.be/|[?&]v=|youtube\.com/(?:embed|shorts|live)/)([\w-]{6,})', url)
    if m:
        return '<div class="sheet-video"><iframe loading="lazy" src="https://www.youtube.com/embed/%s" title="%s" allowfullscreen></iframe></div>' % (escape(m.group(1)), escape(title))
    if re.search(r'\.(mp4|webm|ogg)(?:\?.*)?$', url, re.I):
        return '<div class="sheet-video"><video controls preload="metadata" src="%s"></video></div>' % escape(url)
    return '<p><a href="%s" target="_blank" rel="noopener" class="read-more-btn">▶ ভিডিও দেখুন</a></p>' % escape(url)


def norm_cat(s):
    return re.sub(r'[^\w\u0980-\u09FF]+', '', str(s or '').lower())


CATEGORY_MAP = {
    'জাতীয়': ['জাতীয়','জাতীয়','national'],
    'রাজনীতি': ['রাজনীতি','politics'],
    'আন্তর্জাতিক': ['আন্তর্জাতিক','international'],
    'অর্থনীতি': ['অর্থনীতি','economy'],
    'খেলাধুলা': ['খেলাধুলা','sports','sport'],
    'বিনোদন': ['বিনোদন','entertainment'],
    'প্রযুক্তি': ['প্রযুক্তি','technology','tech'],
}


def catmatch(cat, aliases):
    return any(norm_cat(cat) == norm_cat(a) for a in aliases)


def load_existing_fallbacks():
    # Kept deliberately small: it protects older articles if a Sheet snapshot temporarily omits them.
    out = {}
    for p in NEWS.glob('*.html'):
        if not p.stem.isdigit():
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        h = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S | re.I)
        if not h:
            continue
        title = re.sub('<[^>]+>', '', h.group(1)).strip()
        cont = re.search(r'<div[^>]*class="[^"]*(?:article-full-details|home-full-details|detail-content)[^"]*"[^>]*>(.*?)</div>', text, re.S | re.I)
        body = re.sub('<[^>]+>', '\n', cont.group(1)).strip() if cont else ''
        img = re.search(r'<img[^>]+src="(\.\./assets/news/[^"?#]+|assets/news/[^"?#]+)"', text, re.I)
        image = img.group(1).replace('../', '') if img else ''
        out[p.stem] = {'id': p.stem, 'category': 'সংবাদ', 'title': title, 'body': body, 'image': image, 'date': ''}
    return out


news_rows_raw, ads_rows_raw = load_rows()
news_rows = normalize_rows(news_rows_raw, False)
ads_rows = normalize_rows(ads_rows_raw, True)
# Preserve existing rows that disappear from a transient Sheet response. Current Sheet values win on ID collisions.
try:
    old_rows = json.loads((ROOT / 'news-data.json').read_text(encoding='utf-8')).get('table', {}).get('rows', [])
except Exception:
    old_rows = []
current_ids = {slug_id(cell(r, 0)) for r in news_rows if cell(r, 0)}
for old_row in old_rows:
    raw_old_id = cell(old_row, 0)
    oid = slug_id(raw_old_id) if raw_old_id else ''
    if oid and oid not in current_ids:
        news_rows.append(old_row)
(ROOT / 'news-data.json').write_text(json.dumps(snapshot(news_rows), ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
(ROOT / 'ads-data.json').write_text(json.dumps(snapshot(ads_rows), ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

articles = []
seen = set()
for i, row in enumerate(news_rows, 1):
    aid = slug_id(cell(row, 0) or str(i))
    if aid in seen:
        continue
    title = cell(row, 2)
    if not title:
        continue
    seen.add(aid)
    articles.append({
        'id': aid,
        'category': cell(row, 1) or 'সংবাদ',
        'title': title,
        'body': cell(row, 3),
        'image': cell(row, 4),
        'date': cell(row, 5),
        'image2': cell(row, 6),
        'image3': cell(row, 7),
        'video': cell(row, 8),
        'keywords': cell(row, 9),
        'dt': parse_date(cell(row, 5)),
    })

fallbacks = load_existing_fallbacks()
byid = {a['id']: a for a in articles}
for aid, old in fallbacks.items():
    if aid not in byid:
        old['dt'] = parse_date(old.get('date', ''))
        byid[aid] = old
articles = list(byid.values())
if not articles:
    raise RuntimeError('No valid news rows found.')

ordered = sorted(articles, key=lambda x: (x.get('dt') or datetime.min.replace(tzinfo=TZ), int(x['id']) if x['id'].isdigit() else -1), reverse=True)
latest = ordered[:10]
six = []
for label, aliases in CATEGORY_MAP.items():
    if label == 'অর্থনীতি':
        continue
    found = next((x for x in ordered if catmatch(x.get('category', ''), aliases)), None)
    if found:
        six.append((found, label))
six = six[:6]

from bs4 import BeautifulSoup

home_html = (ROOT / 'home.html').read_text(encoding='utf-8')
home_s = BeautifulSoup(home_html, 'html.parser')
# Remove the homepage's Sheet-fetching inline script. Static news pages must not wait for Google Sheets in the browser.
for sc in list(home_s.find_all('script')):
    if not sc.get('src') and ('DATA_URL=' in (sc.string or '') or 'load().then(list=>' in (sc.string or '')):
        sc.decompose()
# Make all root-level local references valid from /news/.
for tag in home_s.find_all(['a', 'img', 'link', 'script']):
    attr = 'href' if tag.name in ('a', 'link') else 'src'
    u = tag.get(attr)
    if not u or u.startswith(('http:', 'https:', '#', 'data:', 'javascript:')):
        continue
    if u.startswith('../'):
        continue
    if u.startswith('news/'):
        tag[attr] = u[5:]
    else:
        tag[attr] = '../' + u

# Add a tiny static-only media style, without changing the homepage's visual system.
style = home_s.new_tag('style')
style.string = '.sheet-video{margin:18px 0;background:#000;border-radius:8px;overflow:hidden}.sheet-video iframe{width:100%;aspect-ratio:16/9;border:0;display:block}.sheet-video video{width:100%;display:block}.article-extra-image{margin:18px 0}.article-extra-image img{width:100%;height:auto;display:block;border-radius:6px}'
home_s.head.append(style)

# Final responsive detail CSS is shared with generated News 1+ pages.
FINAL_DETAIL_CSS = r'''
<style id="final-responsive-detail-fix">
html,body{width:100%;max-width:100%;overflow-x:hidden}
img{max-width:100%;height:auto}
.logo-image{max-width:100%;object-fit:contain}
@media(max-width:768px){
  .top-bar{display:block;overflow:hidden}
  .site-header{padding:10px 12px!important}
  .header-inner{width:100%!important;max-width:100%!important;display:flex!important;flex-direction:column!important;justify-content:center!important;align-items:center!important;gap:6px!important}
  .logo{width:100%!important;text-align:center!important}
  .logo-image{width:min(230px,72vw)!important;max-width:72vw!important;max-height:68px!important;margin:0 auto!important}
  #live-date{font-size:12px!important;text-align:center!important}
  .nav{width:100%!important;overflow:hidden!important}
  .nav-inner{width:100%!important;max-width:100%!important;display:flex!important;flex-wrap:nowrap!important;overflow-x:auto!important;overflow-y:hidden!important;-webkit-overflow-scrolling:touch!important;scrollbar-width:none!important}
  .nav-inner::-webkit-scrollbar{display:none}
  .nav a{flex:0 0 auto!important;padding:10px 13px!important;font-size:14px!important}
  .breaking{width:calc(100% - 16px)!important;max-width:none!important;margin:9px 8px 14px!important}
  .breaking-news-container{width:100%!important;display:flex!important;min-height:42px!important}
  .breaking-title{flex:0 0 auto!important;font-size:13px!important;padding:9px 10px!important}
  .ticker-window{min-width:0!important;flex:1 1 auto!important}
  .ticker-track{font-size:13px!important;line-height:42px!important}
  .detail-breadcrumb{width:100%!important;max-width:none!important;padding:0 12px!important;margin:0 0 8px!important;overflow:hidden!important;white-space:nowrap!important;text-overflow:ellipsis!important}
  .home-main-layout{width:100%!important;max-width:none!important;padding:0 12px!important;margin:0!important;display:flex!important;flex-direction:column!important;gap:20px!important}
  #home-feature,.home-sidebar{width:100%!important;max-width:none!important;min-width:0!important}
  .article-full-block{width:100%!important;min-width:0!important}
  .news-image-top,.article-full-image{width:100%!important;height:auto!important;max-height:none!important}
  .news-image-top img,.article-full-image img{width:100%!important;height:auto!important;max-height:none!important;object-fit:contain!important}
  .home-feature-title{font-size:25px!important;line-height:1.42!important;overflow-wrap:anywhere!important;word-break:normal!important}
  .home-full-details{font-size:16px!important;line-height:1.9!important;overflow-wrap:anywhere!important}
  .home-full-details p{overflow-wrap:anywhere!important}
  .sidebar{width:100%!important;position:static!important;min-width:0!important}
  .latest-news-scroll{max-height:none!important;overflow:visible!important}
  .category-latest-item a{min-width:0!important}
  .category-latest-thumb{flex:0 0 82px!important;width:82px!important;height:62px!important}
  .category-latest-title{min-width:0!important;overflow-wrap:anywhere!important}
  .category-six-grid{width:100%!important;max-width:none!important;margin:20px 0!important;padding:0 12px!important;grid-template-columns:1fr!important}
  .category-six-grid .news-card{width:100%!important;min-width:0!important}
  .category-six-grid .news-card .news-image img{width:100%!important;height:auto!important;max-height:none!important;object-fit:contain!important}
  .section-title{width:100%!important;padding:0 12px!important}
  .ad-slot.top,.ad-slot.bottom{width:calc(100% - 24px)!important;max-width:none!important;margin-left:12px!important;margin-right:12px!important;overflow:hidden!important}
  .ad-slot.middle{width:100%!important;max-width:100%!important;overflow:hidden!important}
  .site-footer{width:100%!important;overflow:hidden!important}
}
</style>
'''


BUILD = ROOT / '.news-build'
if BUILD.exists():
    import shutil
    shutil.rmtree(BUILD)
BUILD.mkdir(parents=True)


CATEGORY_PAGES = {
    'জাতীয়': 'national.html', 'জাতীয়': 'national.html', 'national': 'national.html',
    'রাজনীতি': 'politics.html', 'politics': 'politics.html',
    'আন্তর্জাতিক': 'international.html', 'international': 'international.html',
    'অর্থনীতি': 'economy.html', 'economy': 'economy.html',
    'খেলাধুলা': 'sports.html', 'sports': 'sports.html', 'sport': 'sports.html',
    'বিনোদন': 'entertainment.html', 'entertainment': 'entertainment.html',
    'প্রযুক্তি': 'technology.html', 'technology': 'technology.html', 'tech': 'technology.html',
}

def category_page_for(article):
    c = str(article.get('category', '')).strip().lower()
    return CATEGORY_PAGES.get(c, 'national.html')

def detail_to_category_link(article):
    return static_link(article['id'])

def static_link(aid):
    return urllib.parse.quote(slug_id(aid)) + '.html'

for a in articles:
    sid = slug_id(a['id'])
    s = BeautifulSoup(str(home_s), 'html.parser')
    s.head.append(BeautifulSoup(FINAL_DETAIL_CSS, 'html.parser'))
    for limg in s.select('.logo-image'):
        limg['onerror'] = "this.style.display='none';var f=this.parentElement.querySelector('.logo-fallback');if(f)f.style.display='block'"
    canonical = (BASE + 'news/' + urllib.parse.quote(sid) + '.html') if BASE else ('news/' + urllib.parse.quote(sid) + '.html')
    desc = description(a.get('body', ''), a['title'])
    title = a['title'] + ' | বাংলা সংবাদ'
    if s.title:
        s.title.string = title
    for sel, attr, val in [
        ('link[rel="canonical"]', 'href', canonical),
        ('meta[name="description"]', 'content', desc),
        ('meta[property="og:title"]', 'content', a['title']),
        ('meta[property="og:description"]', 'content', desc),
        ('meta[property="og:url"]', 'content', canonical),
        ('meta[property="og:type"]', 'content', 'article'),
    ]:
        el = s.select_one(sel)
        if el:
            el[attr] = val
    im = article_image(a, 0)
    absolute_image = (BASE + im) if im and not im.startswith(('http://','https://')) and BASE else (im or (BASE + 'logo.png' if BASE else '../logo.png'))
    og = s.select_one('meta[property="og:image"]')
    if og: og['content'] = absolute_image
    for sel, attr, val in [
        ('meta[property="og:image:alt"]','content',a['title']),
        ('meta[name="twitter:title"]','content',a['title']),
        ('meta[name="twitter:description"]','content',desc),
        ('meta[name="twitter:image"]','content',absolute_image),
    ]:
        el=s.select_one(sel)
        if el: el[attr]=val
        elif sel.startswith('meta[name="twitter:image"]'):
            s.head.append(s.new_tag('meta', attrs={'name':'twitter:image','content':absolute_image}))
    if not s.select_one('meta[property="article:published_time"]'):
        m=s.new_tag('meta',property='article:published_time',content=(a.get('dt').isoformat() if a.get('dt') else ''))
        s.head.append(m)
    tick = s.select_one('#breaking-ticker')
    if tick:
        tick.string = a['title']
    date_el = s.select_one('#live-date')
    if date_el:
        date_el.string = 'তারিখ'
        if not s.select_one('#detail-live-date-script'):
            ds=s.new_tag('script', id='detail-live-date-script')
            ds.string="(function(){const e=document.getElementById('live-date');if(e)e.textContent=new Intl.DateTimeFormat('bn-BD',{timeZone:'Asia/Dhaka',weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(new Date());})();"
            s.body.append(ds)
    article_schema = {
        '@context':'https://schema.org','@type':'NewsArticle','headline':a['title'],
        'description':desc,'mainEntityOfPage':{'@type':'WebPage','@id':canonical},
        'image':[absolute_image] if absolute_image else [],'datePublished':(a.get('dt').isoformat() if a.get('dt') else ''),
        'dateModified':(a.get('dt').isoformat() if a.get('dt') else ''),
        'author':{'@type':'Organization','name':'বাংলা সংবাদ'},
        'publisher':{'@type':'Organization','name':'বাংলা সংবাদ'}
    }
    ld=s.new_tag('script',type='application/ld+json'); ld.string=json.dumps(article_schema,ensure_ascii=False,separators=(',',':')); s.head.append(ld)
    breadcrumb={'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[
        {'@type':'ListItem','position':1,'name':'হোম','item':BASE+'home.html' if BASE else '../home.html'},
        {'@type':'ListItem','position':2,'name':a.get('category','সংবাদ')},
        {'@type':'ListItem','position':3,'name':a['title'],'item':canonical}
    ]}
    ld2=s.new_tag('script',type='application/ld+json'); ld2.string=json.dumps(breadcrumb,ensure_ascii=False,separators=(',',':')); s.head.append(ld2)

    main = s.select_one('main.home-main-layout')
    if not main:
        raise RuntimeError('home.html is missing main.home-main-layout')
    main.clear()

    section = s.new_tag('section', id='home-feature', **{'aria-label': 'পূর্ণ সংবাদ'})
    article = s.new_tag('article', **{'class': 'vertical-news-block article-full-block'})
    im = article_image(a, 0)
    if im:
        wrap = s.new_tag('div', **{'class': 'news-image-top article-full-image'})
        tag = s.new_tag('img', src=image_src_for_news_page(im), alt=a['title'], loading='eager', **{'data-image-source':im})
        wrap.append(tag); article.append(wrap)
    text = s.new_tag('div', **{'class': 'news-text-bottom'})
    cat = s.new_tag('span', **{'class': 'category-tag'}); cat.string = a.get('category', 'সংবাদ'); text.append(cat)
    dt = s.new_tag('div', **{'class': 'breaking-news-date'}); dt.string = a.get('display_date') or bangla_date(a.get('date',''), a.get('dt')); text.append(dt)
    h = s.new_tag('h1', **{'class': 'home-feature-title'}); h.string = a['title']; text.append(h)
    ad1 = s.new_tag('div', **{'class': 'ad-slot in-article sheet-ad-slot middle'}, **{'data-ad-slot':'middle-top','aria-label':'বিজ্ঞাপন'}); text.append(ad1)
    details = s.new_tag('div', **{'class': 'home-full-details article-full-details'})
    details.append(BeautifulSoup(body_html(a.get('body', '')), 'html.parser'))
    for idx in (1, 2):
        ex = article_image(a, idx)
        if ex:
            fig = s.new_tag('figure', **{'class':'article-extra-image'})
            eim = s.new_tag('img', src=image_src_for_news_page(ex), alt=a['title'] + ' - ছবি ' + str(idx + 1), loading='lazy', **{'data-image-source':ex})
            fig.append(eim); details.append(fig)
    vh = video_html(a.get('video', ''), a['title'])
    if vh:
        details.append(BeautifulSoup(vh, 'html.parser'))
    text.append(details); article.append(text); section.append(article)
    ad2 = s.new_tag('div', **{'class':'ad-slot in-article sheet-ad-slot middle'}, **{'data-ad-position':'middle-bottom','data-ad-slot':'middle-bottom','aria-label':'বিজ্ঞাপন'})
    section.append(ad2); main.append(section)

    aside = s.new_tag('aside', **{'class':'sidebar home-sidebar'})
    hh = s.new_tag('h2'); hh.string = 'সর্বশেষ ১০ সংবাদ'; aside.append(hh)
    lst = s.new_tag('div', **{'class':'latest-news-scroll'})
    for x in latest:
        art = s.new_tag('article', **{'class':'latest-item category-latest-item'})
        link = s.new_tag('a', href=detail_to_category_link(x), **{'data-news-id':x['id'], 'data-category-news-id':x['id']})
        th = s.new_tag('span', **{'class':'category-latest-thumb'})
        xim = article_image(x, 0)
        if xim:
            xi = s.new_tag('img', src=image_src_for_news_page(xim), alt=x['title'], loading='lazy', **{'data-image-source':xim}); th.append(xi)
        tt = s.new_tag('span', **{'class':'category-latest-title'}); tt.string = x['title']
        link.append(th); link.append(tt); art.append(link); lst.append(art)
    aside.append(lst); main.append(aside)

    grid = s.select_one('#category-six-grid')
    if grid:
        grid.clear()
        for x, label in six:
            card = s.new_tag('article', **{'class':'news-card'})
            link = s.new_tag('a', href=detail_to_category_link(x), **{'class':'category-card-link','data-news-id':x['id'], 'data-category-news-id':x['id']})
            box = s.new_tag('div', **{'class':'news-image'})
            xim = article_image(x, 0)
            if xim:
                xi = s.new_tag('img', src=image_src_for_news_page(xim), alt=x['title'], loading='lazy', **{'data-image-source':xim}); box.append(xi)
            link.append(box)
            cc = s.new_tag('div', **{'class':'news-card-content'})
            lab = s.new_tag('div', **{'class':'category'}); lab.string = label
            th = s.new_tag('h3'); th.string = x['title']
            cc.append(lab); cc.append(th); link.append(cc); card.append(link); grid.append(card)

    # Remove any remaining inline JS that could attempt a Sheet request.
    for sc in list(s.find_all('script')):
        if not sc.get('src') and sc.get('type') != 'application/ld+json' and sc.get('id') != 'detail-live-date-script':
            sc.decompose()
    # Detail pages use detail-tools.js for their single working search.
    # Never include the root-page global search script here, or two search bars
    # will be injected and the relative result paths will conflict.
    for sc in list(s.find_all('script', src=True)):
        if 'site-search.js' in str(sc.get('src')):
            sc.decompose()

    # Shared search + social/share tools are injected into every generated detail page.
    if not s.find('script', src='../detail-tools.js'):
        tool_script = s.new_tag('script', src='../detail-tools.js', defer=True)
        s.body.append(tool_script)
    # Media reliability layer also runs on detail pages so a repository move
    # (for example Banglasangbad -> Mukta) cannot break article images.
    if not s.find('script', src=re.compile(r'\.\./news-media\.js')):
        media_script = s.new_tag('script', src='../news-media.js?v=20260913-media-final', defer=True)
        s.body.append(media_script)

    out = BUILD / (sid + '.html')
    out.write_text('<!DOCTYPE html>\n' + str(s), encoding='utf-8')

# Atomic replacement: if generation/validation fails, existing live pages remain untouched.
expected = {slug_id(a['id']) for a in articles}
actual = {p.stem for p in BUILD.glob('*.html')}
if expected != actual:
    raise RuntimeError(f'Static page set mismatch. Missing={sorted(expected-actual)} Extra={sorted(actual-expected)}')
for p in BUILD.glob('*.html'):
    t = p.read_text(encoding='utf-8', errors='ignore')
    if '<main class="container home-main-layout">' not in t or 'home-sidebar' not in t or 'category-six-grid' not in t or '<h1' not in t or 'article-full-details' not in t:
        raise RuntimeError(f'Validation failed: {p.name} is not a complete Home-style article page.')

import shutil
old = ROOT / '.news-old'
if old.exists(): shutil.rmtree(old)
if NEWS.exists(): NEWS.rename(old)
BUILD.rename(NEWS)
shutil.rmtree(old)

now = datetime.now(TZ)
static = ['', 'home.html', 'national.html', 'politics.html', 'international.html', 'economy.html', 'sports.html', 'entertainment.html', 'technology.html', 'more.html', 'about.html', 'contact.html', 'privacy.html', 'disclaimer.html', 'advertise.html']
root = Element('urlset', {'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9'})
for p in static:
    u = SubElement(root, 'url'); SubElement(u, 'loc').text = (BASE + p) if BASE else p; SubElement(u, 'lastmod').text = now.date().isoformat()
for a in articles:
    u = SubElement(root, 'url'); SubElement(u, 'loc').text = (BASE + 'news/' + urllib.parse.quote(slug_id(a['id'])) + '.html') if BASE else ('news/' + urllib.parse.quote(slug_id(a['id'])) + '.html')
    if a.get('dt'): SubElement(u, 'lastmod').text = a['dt'].date().isoformat()
ElementTree(root).write(ROOT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)

cutoff = now - timedelta(days=2)
ns = Element('urlset', {'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9','xmlns:news':'http://www.google.com/schemas/sitemap-news/0.9'})
fresh = [a for a in articles if a.get('dt') and cutoff <= a['dt'] <= now + timedelta(minutes=10)]
for a in sorted(fresh, key=lambda x:x['dt'], reverse=True)[:1000]:
    u = SubElement(ns, 'url'); SubElement(u, 'loc').text = (BASE + 'news/' + urllib.parse.quote(slug_id(a['id'])) + '.html') if BASE else ('news/' + urllib.parse.quote(slug_id(a['id'])) + '.html')
    n = SubElement(u, 'news:news'); pub = SubElement(n, 'news:publication'); SubElement(pub, 'news:name').text = 'বাংলা সংবাদ'; SubElement(pub, 'news:language').text = 'bn'
    SubElement(n, 'news:publication_date').text = a['dt'].isoformat(timespec='seconds'); SubElement(n, 'news:title').text = a['title']
ElementTree(ns).write(ROOT / 'news-sitemap.xml', encoding='utf-8', xml_declaration=True)

# Normalize category-page navigation so every news card opens the canonical static detail page directly.
for cp in [ROOT / n for n in ('national.html','politics.html','international.html','economy.html','sports.html','entertainment.html','technology.html')]:
    if not cp.exists(): continue
    txt=cp.read_text(encoding='utf-8')
    key=cp.stem
    txt=txt.replace(f'href="{key}.html?news=${{encodeURIComponent(normId(n.id))}}"', 'href="news/${encodeURIComponent(normId(n.id))}.html"')
    # If a requested-news query is used from an old bookmark, redirect it to the canonical detail URL.
    marker="const requestedNewsId = normId(new URLSearchParams(location.search).get('news') || '');"
    if marker in txt:
        txt=txt.replace(marker, marker+"\nif(requestedNewsId){location.replace('news/'+encodeURIComponent(requestedNewsId)+'.html');}")
    if 'site-search.js' not in txt:
        txt=txt.replace('</body>', '<script src="site-search.js" defer></script></body>')
    cp.write_text(txt,encoding='utf-8')
# Add the same global search to main root pages.
for name in ('home.html','index.html','more.html','about.html','contact.html','privacy.html','disclaimer.html','advertise.html'):
    rp=ROOT/name
    if not rp.exists(): continue
    txt=rp.read_text(encoding='utf-8')
    if 'site-search.js' not in txt:
        txt=txt.replace('</body>', '<script src="site-search.js" defer></script></body>')
    rp.write_text(txt,encoding='utf-8')

print(f'Generated {len(articles)} static Home-style news pages.')
print(f'Site base: {BASE or "relative URLs (GitHub Actions will set the repo URL)"}')
