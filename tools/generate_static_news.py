import json, re, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree

SHEET_ID = '1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg'
BASE = 'https://abdurrazzak123.github.io/Banglasangbad/'
ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'assets' / 'news-media'
TZ = ZoneInfo('Asia/Dhaka')


def fetch_sheet(name):
    q = urllib.parse.quote('select *')
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&sheet={urllib.parse.quote(name)}&tq={q}'
    req = urllib.request.Request(url, headers={'User-Agent':'Banglasangbad-Sheet-Sync/1.0'})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode('utf-8')
    m = re.search(r'google\.visualization\.Query\.setResponse\((.*)\);?\s*$', raw, re.S)
    if not m:
        raise RuntimeError(f'Google Sheet response could not be parsed for {name}.')
    data = json.loads(m.group(1))
    return data.get('table', {}).get('rows', [])


def cell(row, i):
    c=row.get('c',[])
    return str(c[i].get('v','') if i<len(c) and c[i] is not None else '').strip()


def drive_id(v):
    m=re.search(r'drive\.google\.com/(?:file/d/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)', str(v or ''), re.I)
    return m.group(1) if m else ''


def image_url(v):
    v=str(v or '').strip()
    did=drive_id(v)
    return f'https://drive.google.com/thumbnail?id={did}&sz=w2000' if did else v


def safe_name(aid, idx):
    raw=str(aid or idx).strip()
    m=re.fullmatch(r'(\d+)\.0+',raw)
    if m: raw=m.group(1)
    return re.sub(r'[^A-Za-z0-9_-]+','-',raw).strip('-') or str(idx)


def download_image(url, aid, num):
    if not url: return ''
    did=drive_id(url)
    if not did: return url
    MEDIA.mkdir(parents=True, exist_ok=True)
    ext='.jpg'
    out=MEDIA/f'{safe_name(aid,aid)}-{num}{ext}'
    try:
        req=urllib.request.Request(f'https://drive.google.com/uc?export=download&id={did}',headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=45) as r:
            data=r.read()
        if len(data)<1000: raise RuntimeError('small response')
        out.write_bytes(data)
        return BASE + 'assets/news-media/' + urllib.parse.quote(out.name)
    except Exception as e:
        print(f'Image download failed for {aid}/{num}: {e}')
        return url


def parse_date(v):
    m=re.fullmatch(r'Date\((\d+),(\d+),(\d+)(?:,(\d+),(\d+),(\d+))?\)',str(v or ''))
    if m:
        y,mo,d=map(int,m.group(1,2,3)); return datetime(y,mo+1,d,int(m.group(4) or 0),int(m.group(5) or 0),int(m.group(6) or 0),tzinfo=TZ)
    for fmt in ('%Y-%m-%dT%H:%M:%S%z','%Y-%m-%d %H:%M:%S','%Y-%m-%d','%m/%d/%Y %H:%M:%S','%m/%d/%Y'):
        try:
            d=datetime.strptime(str(v or ''),fmt); return d if d.tzinfo else d.replace(tzinfo=TZ)
        except ValueError: pass
    return None

rows=fetch_sheet('Bangla News')
news=[]; seen=set()
for i,row in enumerate(rows,1):
    aid=cell(row,0) or str(i)
    title=cell(row,2)
    if not title or aid in seen: continue
    seen.add(aid)
    a={'id':aid,'category':cell(row,1),'title':title,'summary':cell(row,3),'image':image_url(cell(row,4)),'date':cell(row,5),'image2':image_url(cell(row,6)),'image3':image_url(cell(row,7)),'video':cell(row,8),'keywords':cell(row,9)}
    # Download/copy Google Drive images into GitHub while preserving the original URL if download is impossible.
    a['image']=download_image(a['image'],aid,1)
    a['image2']=download_image(a['image2'],aid,2)
    a['image3']=download_image(a['image3'],aid,3)
    news.append(a)
if not news: raise RuntimeError('No valid news rows found in Bangla News.')
(ROOT/'news-data.json').write_text(json.dumps(news,ensure_ascii=False,indent=2),encoding='utf-8')

ads=[]
for row in fetch_sheet('Ads'):
    ads.append({'position':cell(row,0),'active':cell(row,1),'image':cell(row,2),'click':cell(row,3),'title':cell(row,4),'code':cell(row,5)})
(ROOT/'ads-data.json').write_text(json.dumps(ads,ensure_ascii=False,indent=2),encoding='utf-8')

now=datetime.now(TZ)
root=Element('urlset',{'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9'})
static=['','home.html','national.html','politics.html','international.html','economy.html','sports.html','entertainment.html','technology.html','more.html','about.html','contact.html','privacy.html','disclaimer.html','advertise.html']
for p in static:
    u=SubElement(root,'url'); SubElement(u,'loc').text=BASE+p; SubElement(u,'lastmod').text=now.date().isoformat()
for a in news:
    u=SubElement(root,'url'); SubElement(u,'loc').text=BASE+'news/'+urllib.parse.quote(safe_name(a['id'],a['id']))+'.html'
    d=parse_date(a['date'])
    if d: SubElement(u,'lastmod').text=d.date().isoformat()
ElementTree(root).write(ROOT/'sitemap.xml',encoding='utf-8',xml_declaration=True)
# Keep news sitemap simple and based on the exact Sheet rows/IDs.
ns=Element('urlset',{'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9','xmlns:news':'http://www.google.com/schemas/sitemap-news/0.9'})
for a in news:
    d=parse_date(a['date']) or now
    u=SubElement(ns,'url'); SubElement(u,'loc').text=BASE+'news/'+urllib.parse.quote(safe_name(a['id'],a['id']))+'.html'
    ne=SubElement(u,'news:news'); pub=SubElement(ne,'news:publication'); SubElement(pub,'news:name').text='বাংলা সংবাদ'; SubElement(pub,'news:language').text='bn'
    n=SubElement(ne,'news:publication_date'); n.text=d.isoformat(); SubElement(ne,'news:title').text=a['title']
ElementTree(ns).write(ROOT/'news-sitemap.xml',encoding='utf-8',xml_declaration=True)
print(f'Synced {len(news)} news rows and {len(ads)} ads rows.')
