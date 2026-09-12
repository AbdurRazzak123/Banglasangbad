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
    if os.environ.get('USE_SNAPSHOT', '').lower() in ('1', 'true', 'yes'):
        data = json.loads((ROOT / 'news-data.json').read_text(encoding='utf-8'))
        news_rows = data.get('table', {}).get('rows', [])
        ads_file = ROOT / 'ads-data.json'
        ads_rows = json.loads(ads_file.read_text(encoding='utf-8')).get('table', {}).get('rows', []) if ads_file.exists() else []
        return news_rows, ads_rows
    return fetch_sheet_rows(SHEET_NAME), fetch_sheet_rows('Ads')


def normalize_rows(rows, is_ads=False):
    rows = json.loads(json.dumps(rows))
    for row_no, row in enumerate(rows, 1):
        cells = row.get('c', [])
        cols = (2,) if is_ads else (4, 6, 7)
        for col in cols:
            if col < len(cells) and cells[col] is not None:
                original = str(cells[col].get('v', '') or '').strip()
                if original:
                    cells[col]['v'] = download_drive_image(original, f'{"ad" if is_ads else "news"}-{row_no}-img{col}')
    return rows


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

BUILD = ROOT / '.news-build'
if BUILD.exists():
    import shutil
    shutil.rmtree(BUILD)
BUILD.mkdir(parents=True)


def static_link(aid):
    return urllib.parse.quote(slug_id(aid)) + '.html'

for a in articles:
    sid = slug_id(a['id'])
    s = BeautifulSoup(str(home_s), 'html.parser')
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
    og = s.select_one('meta[property="og:image"]')
    if og:
        im = article_image(a, 0)
        og['content'] = (BASE + im) if im and not im.startswith('http') and BASE else (im or (BASE + 'logo.png' if BASE else '../logo.png'))
    tick = s.select_one('#breaking-ticker')
    if tick:
        tick.string = a['title']
    date_el = s.select_one('#live-date')
    if date_el:
        date_el.string = a.get('date', '') or ''

    main = s.select_one('main.home-main-layout')
    if not main:
        raise RuntimeError('home.html is missing main.home-main-layout')
    main.clear()

    section = s.new_tag('section', id='home-feature', **{'aria-label': 'পূর্ণ সংবাদ'})
    article = s.new_tag('article', **{'class': 'vertical-news-block article-full-block'})
    im = article_image(a, 0)
    if im:
        wrap = s.new_tag('div', **{'class': 'news-image-top article-full-image'})
        tag = s.new_tag('img', src=image_src_for_news_page(im), alt=a['title'], loading='eager')
        wrap.append(tag); article.append(wrap)
    text = s.new_tag('div', **{'class': 'news-text-bottom'})
    cat = s.new_tag('span', **{'class': 'category-tag'}); cat.string = a.get('category', 'সংবাদ'); text.append(cat)
    dt = s.new_tag('div', **{'class': 'breaking-news-date'}); dt.string = a.get('date', ''); text.append(dt)
    h = s.new_tag('h1', **{'class': 'home-feature-title'}); h.string = a['title']; text.append(h)
    ad1 = s.new_tag('div', **{'class': 'ad-slot in-article sheet-ad-slot middle'}, **{'data-ad-slot':'middle-top','aria-label':'বিজ্ঞাপন'}); text.append(ad1)
    details = s.new_tag('div', **{'class': 'home-full-details article-full-details'})
    details.append(BeautifulSoup(body_html(a.get('body', '')), 'html.parser'))
    for idx in (1, 2):
        ex = article_image(a, idx)
        if ex:
            fig = s.new_tag('figure', **{'class':'article-extra-image'})
            eim = s.new_tag('img', src=image_src_for_news_page(ex), alt=a['title'] + ' - ছবি ' + str(idx + 1), loading='lazy')
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
        link = s.new_tag('a', href=static_link(x['id']), **{'data-news-id':x['id']})
        th = s.new_tag('span', **{'class':'category-latest-thumb'})
        xim = article_image(x, 0)
        if xim:
            xi = s.new_tag('img', src=image_src_for_news_page(xim), alt=x['title'], loading='lazy'); th.append(xi)
        tt = s.new_tag('span', **{'class':'category-latest-title'}); tt.string = x['title']
        link.append(th); link.append(tt); art.append(link); lst.append(art)
    aside.append(lst); main.append(aside)
    mid = s.new_tag('div', **{'class':'ad-slot in-article sheet-ad-slot middle'}, **{'data-ad-position':'middle-top','data-ad-slot':'middle-top','aria-label':'বিজ্ঞাপন'})
    main.append(mid)

    grid = s.select_one('#category-six-grid')
    if grid:
        grid.clear()
        for x, label in six:
            card = s.new_tag('article', **{'class':'news-card'})
            link = s.new_tag('a', href=static_link(x['id']), **{'class':'category-card-link','data-news-id':x['id']})
            box = s.new_tag('div', **{'class':'news-image'})
            xim = article_image(x, 0)
            if xim:
                xi = s.new_tag('img', src=image_src_for_news_page(xim), alt=x['title'], loading='lazy'); box.append(xi)
            link.append(box)
            cc = s.new_tag('div', **{'class':'news-card-content'})
            lab = s.new_tag('div', **{'class':'category'}); lab.string = label
            th = s.new_tag('h3'); th.string = x['title']
            cc.append(lab); cc.append(th); link.append(cc); card.append(link); grid.append(card)

    # Remove any remaining inline JS that could attempt a Sheet request.
    for sc in list(s.find_all('script')):
        if not sc.get('src'):
            sc.decompose()

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

print(f'Generated {len(articles)} static Home-style news pages.')
print(f'Site base: {BASE or "relative URLs (GitHub Actions will set the repo URL)"}')
