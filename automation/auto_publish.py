from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from PIL import Image

# Load social_card reliably whether it is kept beside this file (recommended)
# or accidentally uploaded at the repository root.
AUTOMATION_DIR = Path(__file__).resolve().parent
REPO_ROOT_FOR_IMPORT = AUTOMATION_DIR.parent
for _p in (AUTOMATION_DIR, REPO_ROOT_FOR_IMPORT):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

try:
    from social_card import create_card, create_vertical_frame, create_instagram_carousel
except ModuleNotFoundError as exc:
    raise RuntimeError(
        'social_card.py was not found. Put social_card.py in automation/ ' 
        'beside auto_publish.py, then rerun the GitHub Action.'
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_VERSION = '2026-09-26-premium-fb-ig-v3'
STATE_FILE = ROOT / 'social-publish-state.json'
LOG_FILE = ROOT / 'social-publish-log.json'
NEWS_FILE = ROOT / 'news-data.json'
CARD_DIR = ROOT / 'social-media'
VIDEO_DIR = ROOT / 'social-video'

META_VERSION = os.getenv('META_GRAPH_VERSION', 'v26.0')
META_BASE = f'https://graph.facebook.com/{META_VERSION}'
THREADS_BASE = os.getenv('THREADS_GRAPH_BASE', 'https://graph.threads.net/v1.0')
SITE_BASE_URL = os.getenv('SITE_BASE_URL', 'https://abdurrazzak123.github.io/Banglasangbad').rstrip('/')

PLATFORMS = ('facebook', 'instagram', 'x', 'threads', 'youtube')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1','true','yes','on'}


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path: Path, data: Any):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def clean_text(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def bangla_date(value: str) -> str:
    months = {'01':'জানুয়ারি','02':'ফেব্রুয়ারি','03':'মার্চ','04':'এপ্রিল','05':'মে','06':'জুন','07':'জুলাই','08':'আগস্ট','09':'সেপ্টেম্বর','10':'অক্টোবর','11':'নভেম্বর','12':'ডিসেম্বর'}
    digits = str.maketrans('0123456789','০১২৩৪৫৬৭৮৯')
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', str(value or ''))
    if not m:
        return clean_text(value)
    return f"{m.group(3).translate(digits)} {months.get(m.group(2), m.group(2))} {m.group(1).translate(digits)}"


def news_url(news_id: str) -> str:
    return f'{SITE_BASE_URL}/news/{news_id}.html'


def local_image_for(item: dict) -> Path | None:
    candidates = []
    for x in item.get('images') or []:
        if x:
            candidates.append(x)
    for x in item.get('image_urls') or []:
        if x and x.startswith(('http://','https://')):
            # Remote fallback is downloaded by the caller.
            continue
    for raw in candidates:
        p = ROOT / raw
        if p.exists() and p.is_file():
            return p
    # Common generated naming fallback.
    nid = str(item.get('id',''))
    for ext in ('jpg','jpeg','png','webp'):
        p = ROOT / 'assets' / 'news' / f'{nid}-1.{ext}'
        if p.exists():
            return p
    return None


def download_remote_image(item: dict, dest: Path) -> Path | None:
    for raw in item.get('image_urls') or []:
        if not raw or not raw.startswith(('http://','https://')):
            continue
        # Google Drive view URLs are converted to a direct download attempt.
        m = re.search(r'/file/d/([^/]+)', raw)
        url = f'https://drive.google.com/uc?export=download&id={m.group(1)}' if m else raw
        try:
            r = requests.get(url, timeout=30, headers={'User-Agent':'BanglasangbadSocialBot/1.0'})
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            if dest.stat().st_size > 1000:
                try:
                    with Image.open(dest) as probe:
                        probe.verify()
                    return dest
                except Exception:
                    try:
                        dest.unlink()
                    except OSError:
                        pass
        except Exception:
            continue
    return None


def request_json(method, url, **kwargs):
    kwargs.setdefault('timeout', 60)
    for attempt in range(4):
        try:
            r = requests.request(method, url, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
            if not r.ok:
                try: detail = r.json()
                except Exception: detail = r.text[:1000]
                raise RuntimeError(f'{method} {url} -> HTTP {r.status_code}: {detail}')
            return r.json() if r.text else {}
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError('unreachable')


def caption(item: dict) -> str:
    """Facebook post text: the exact article Details Page URL only."""
    return news_url(str(item.get("id")))


def instagram_caption(item: dict) -> str:
    """Instagram caption with no website URL.

    Short articles use the complete Details text directly in the caption.
    Longer articles are published as a carousel; their complete Details text
    is rendered across the carousel slides so no article text is silently cut.
    """
    headline = clean_text(item.get('headline'))
    details = clean_text(item.get('details'))
    category = clean_text(item.get('category'))
    tag = f"#{re.sub(r'[^\w\u0980-\u09ff]+', '', category)} #বাংলা_সংবাদ" if category else '#বাংলা_সংবাদ'
    return '\n\n'.join([f'📰 {headline}', details, tag]) if details else '\n\n'.join([f'📰 {headline}', tag])


def instagram_needs_carousel(item: dict) -> bool:
    # Instagram captions have a finite character limit. Use a carousel for
    # longer Details fields so the complete article remains available without
    # putting a website URL in the Instagram post.
    return len(instagram_caption(item)) > 2200


def instagram_carousel_caption(item: dict) -> str:
    headline = clean_text(item.get('headline'))
    category = clean_text(item.get('category'))
    tag = f"#{re.sub(r'[^\w\u0980-\u09ff]+', '', category)} #বাংলা_সংবাদ" if category else '#বাংলা_সংবাদ'
    return f'📰 {headline}\n\n{tag}'

def meta_preflight(dry_run: bool = False) -> None:
    """Validate the Meta Page token, Page ID, and Instagram account before any publish.

    This is intentionally a read-only check. It never prints or stores the token.
    A bad/expired token stops the run before a single article is attempted, so the
    queue remains clean and will retry automatically after the GitHub secret is fixed.
    """
    if dry_run:
        return
    token = os.getenv('META_PAGE_ACCESS_TOKEN', '').strip()
    page_id = os.getenv('META_PAGE_ID', '').strip()
    ig_id = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID', '').strip()
    if not token or not page_id:
        raise RuntimeError('Meta preflight failed: META_PAGE_ID or META_PAGE_ACCESS_TOKEN is missing.')
    if not ig_id:
        raise RuntimeError('Meta preflight failed: INSTAGRAM_BUSINESS_ACCOUNT_ID is missing.')

    try:
        page = request_json('GET', f'{META_BASE}/{page_id}', params={
            'fields': 'id,name,instagram_business_account',
            'access_token': token,
        })
    except Exception as exc:
        raise RuntimeError(
            'Meta preflight failed for the Facebook Page. The Page token may be expired, invalid, or missing required Page access. ' + str(exc)
        ) from exc
    if str(page.get('id', '')).strip() != page_id:
        raise RuntimeError('Meta preflight failed: META_PAGE_ID does not match the Page returned by Meta.')

    linked_ig = ((page.get('instagram_business_account') or {}).get('id') or '').strip()
    if linked_ig and linked_ig != ig_id:
        raise RuntimeError('Meta preflight failed: INSTAGRAM_BUSINESS_ACCOUNT_ID does not match the Instagram account linked to the Page.')

    try:
        ig = request_json('GET', f'{META_BASE}/{ig_id}', params={
            'fields': 'id,username',
            'access_token': token,
        })
    except Exception as exc:
        raise RuntimeError(
            'Meta preflight failed for Instagram. The Page token may not have access to the configured Instagram Business account. ' + str(exc)
        ) from exc
    if str(ig.get('id', '')).strip() != ig_id:
        raise RuntimeError('Meta preflight failed: Instagram account ID verification failed.')

    print(f"Meta preflight OK: Page {page_id}; Instagram {ig_id}.")

def facebook_publish(item, card_path, dry_run=False, prior_result=None):
    message = caption(item)
    if dry_run:
        return {'dry_run': True, 'message': message}

    token = os.getenv('META_PAGE_ACCESS_TOKEN', '').strip()
    page_id = os.getenv('META_PAGE_ID', '').strip()
    if not token or not page_id:
        raise RuntimeError('Missing META_PAGE_ID or META_PAGE_ACCESS_TOKEN')

    print(f'FACEBOOK START: article={item["id"]}, page={page_id}')
    public_url = f'{SITE_BASE_URL}/social-media/{item["id"]}.jpg'

    try:
        result = request_json(
            'POST',
            f'{META_BASE}/{page_id}/photos',
            data={
                'url': public_url,
                'caption': message,
                'published': 'true',
                'access_token': token,
            },
        )
    except Exception as exc:
        print(f'FACEBOOK FAILED: article={item["id"]}: {exc}')
        raise

    post_id = result.get('post_id') or result.get('id')
    if not post_id:
        raise RuntimeError(f'Facebook publish returned no post id: {result}')

    print(f'FACEBOOK PUBLISH OK: article={item["id"]}, post_id={post_id}')
    return {
        'id': post_id,
        'post_id': post_id,
        'status': 'posted',
        'comment_created': False,
    }



def _wait_instagram_container(container_id: str, token: str, attempts: int = 30) -> dict:
    """Wait until an Instagram child container is ready for publishing."""
    last = {}
    for attempt in range(attempts):
        last = request_json(
            'GET',
            f'{META_BASE}/{container_id}',
            params={
                'fields': 'status_code,status',
                'access_token': token,
            },
        )
        status = str(last.get('status_code') or '').upper()
        if status == 'FINISHED':
            return last
        if status in {'ERROR', 'EXPIRED'}:
            raise RuntimeError(f'Instagram media container {container_id} failed: {last}')
        # Instagram can take several seconds to ingest a public image.
        time.sleep(min(10, 2 + attempt // 3))
    raise RuntimeError(f'Instagram media container {container_id} did not reach FINISHED: {last}')

def instagram_publish(item, image_path=None, carousel_paths=None, dry_run=False, prior_result=None):
    use_carousel = instagram_needs_carousel(item)

    if dry_run:
        return {
            'dry_run': True,
            'mode': 'carousel' if use_carousel else 'single',
            'caption': instagram_carousel_caption(item) if use_carousel else instagram_caption(item),
        }

    token = os.getenv('META_PAGE_ACCESS_TOKEN', '').strip()
    ig_id = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID', '').strip()
    if not token or not ig_id:
        raise RuntimeError('Missing META_PAGE_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ACCOUNT_ID')

    print(f'INSTAGRAM START: article={item["id"]}, account={ig_id}')

    if use_carousel:
        paths = carousel_paths or []
        if len(paths) < 2:
            raise RuntimeError('Instagram carousel requires at least 2 images')

        child_ids = []
        for path in paths:
            public_url = f'{SITE_BASE_URL}/social-media/instagram/{item["id"]}/{path.name}'
            child = request_json('POST', f'{META_BASE}/{ig_id}/media', data={
                'image_url': public_url,
                'is_carousel_item': 'true',
                'access_token': token,
            })
            cid = child.get('id')
            if not cid:
                raise RuntimeError(f'Instagram carousel child returned no id: {child}')
            _wait_instagram_container(cid, token, attempts=36)
            child_ids.append(cid)

        parent = request_json('POST', f'{META_BASE}/{ig_id}/media', data={
            'media_type': 'CAROUSEL',
            'children': ','.join(child_ids),
            'caption': instagram_carousel_caption(item),
            'access_token': token,
        })
        parent_id = parent.get('id')
        if not parent_id:
            raise RuntimeError(f'Instagram carousel parent returned no id: {parent}')

        _wait_instagram_container(parent_id, token, attempts=36)

        published = request_json('POST', f'{META_BASE}/{ig_id}/media_publish', data={
            'creation_id': parent_id,
            'access_token': token,
        })
        published_id = published.get('id')
        if not published_id:
            raise RuntimeError(f'Instagram carousel publish returned no id: {published}')

        print(f'INSTAGRAM PUBLISH OK: article={item["id"]}, post_id={published_id}')
        return {
            'id': published_id,
            'creation_id': parent_id,
            'mode': 'carousel',
            'children': child_ids,
            'status': 'posted',
        }

    if not image_path:
        raise RuntimeError('No Instagram image was generated')

    public_url = f'{SITE_BASE_URL}/social-media/instagram/{item["id"]}.jpg'
    container = request_json('POST', f'{META_BASE}/{ig_id}/media', data={
        'image_url': public_url,
        'caption': instagram_caption(item),
        'access_token': token,
    })
    creation_id = container.get('id')
    if not creation_id:
        raise RuntimeError(f'Instagram media container returned no id: {container}')

    _wait_instagram_container(creation_id, token, attempts=36)

    published = request_json('POST', f'{META_BASE}/{ig_id}/media_publish', data={
        'creation_id': creation_id,
        'access_token': token,
    })
    published_id = published.get('id')
    if not published_id:
        raise RuntimeError(f'Instagram publish returned no id: {published}')

    print(f'INSTAGRAM PUBLISH OK: article={item["id"]}, post_id={published_id}')
    return {
        'id': published_id,
        'creation_id': creation_id,
        'mode': 'single',
        'status': 'posted',
    }



def x_publish(item, card_path, dry_run=False):
    text = caption(item)
    if dry_run:
        return {'dry_run': True, 'text': text}
    token = os.getenv('X_ACCESS_TOKEN')
    if not token:
        raise RuntimeError('Missing X_ACCESS_TOKEN')
    mid = x_upload_image(card_path, token)
    result = request_json('POST', 'https://api.x.com/2/tweets', headers={'Authorization': f'Bearer {token}', 'Content-Type':'application/json'}, json={'text': text, 'media': {'media_ids': [mid]}})
    return {'id': (result.get('data') or {}).get('id'), 'media_id': mid}


def threads_publish(item, dry_run=False):
    text = caption(item)
    if dry_run:
        return {'dry_run': True, 'text': text}
    token = os.getenv('THREADS_ACCESS_TOKEN')
    user_id = os.getenv('THREADS_USER_ID', 'me')
    if not token:
        raise RuntimeError('Missing THREADS_ACCESS_TOKEN')
    params = {'media_type':'IMAGE', 'image_url':f'{SITE_BASE_URL}/social-media/{item["id"]}.jpg', 'text':text, 'access_token':token}
    c = request_json('POST', f'{THREADS_BASE}/{user_id}/threads', params=params)
    cid = c.get('id')
    if not cid: raise RuntimeError(f'Threads container returned no id: {c}')
    p = request_json('POST', f'{THREADS_BASE}/{user_id}/threads_publish', params={'creation_id':cid,'access_token':token})
    return {'id': p.get('id'), 'creation_id': cid}


def youtube_access_token():
    direct = os.getenv('YOUTUBE_ACCESS_TOKEN')
    if direct:
        return direct
    client_id, client_secret, refresh = os.getenv('YOUTUBE_CLIENT_ID'), os.getenv('YOUTUBE_CLIENT_SECRET'), os.getenv('YOUTUBE_REFRESH_TOKEN')
    if not all((client_id, client_secret, refresh)):
        raise RuntimeError('Missing YouTube OAuth secrets: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN')
    r = request_json('POST', 'https://oauth2.googleapis.com/token', data={'client_id':client_id,'client_secret':client_secret,'refresh_token':refresh,'grant_type':'refresh_token'})
    return r['access_token']


def youtube_upload(item, video_path: Path, dry_run=False):
    if not video_path.exists():
        raise RuntimeError('YouTube video file was not generated')
    title = clean_text(item.get('headline'))[:95]
    desc = f'{clean_text(item.get("headline"))}\n\nবিস্তারিত খবর: {news_url(str(item["id"]))}\n\nবাংলা সংবাদ'
    if dry_run:
        return {'dry_run': True, 'title': title, 'video': str(video_path)}
    token = youtube_access_token()
    metadata = {'snippet': {'title': title, 'description': desc, 'categoryId':'25', 'defaultLanguage':'bn'}, 'status': {'privacyStatus': os.getenv('YOUTUBE_PRIVACY_STATUS','private'), 'selfDeclaredMadeForKids': False}}
    init = requests.post('https://www.googleapis.com/upload/youtube/v3/videos', params={'uploadType':'resumable','part':'snippet,status'}, headers={'Authorization':f'Bearer {token}','Content-Type':'application/json; charset=UTF-8','X-Upload-Content-Type':'video/mp4','X-Upload-Content-Length':str(video_path.stat().st_size)}, json=metadata, timeout=60)
    if not init.ok:
        raise RuntimeError(f'YouTube init failed: HTTP {init.status_code}: {init.text[:1000]}')
    upload_url = init.headers.get('Location')
    if not upload_url:
        raise RuntimeError('YouTube upload session did not return Location header')
    with video_path.open('rb') as f:
        r = requests.put(upload_url, headers={'Authorization':f'Bearer {token}','Content-Type':'video/mp4','Content-Length':str(video_path.stat().st_size)}, data=f, timeout=600)
    if not r.ok:
        raise RuntimeError(f'YouTube upload failed: HTTP {r.status_code}: {r.text[:1000]}')
    body = r.json()
    return {'id': body.get('id'), 'privacy_status': os.getenv('YOUTUBE_PRIVACY_STATUS','private')}


def generate_video(item, image_path: Path, video_path: Path):
    frame = VIDEO_DIR / f'{item["id"]}-frame.jpg'
    create_vertical_frame(image_path, clean_text(item.get('headline')), bangla_date(item.get('date','')), ROOT/'logo.png', frame)
    video_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg','-y','-loop','1','-i',str(frame),'-vf','scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2','-t','12','-r','30','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(video_path)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try: frame.unlink()
    except OSError: pass



def configure_git_identity():
    """Set Git identity both in the repo config and subprocess environment.

    GitHub-hosted runners do not guarantee a preconfigured author identity.
    Setting both config and environment variables makes every commit path
    deterministic, including commits created before the workflow's final step.
    """
    name = 'github-actions[bot]'
    email = '41898282+github-actions[bot]@users.noreply.github.com'
    os.environ['GIT_AUTHOR_NAME'] = name
    os.environ['GIT_AUTHOR_EMAIL'] = email
    os.environ['GIT_COMMITTER_NAME'] = name
    os.environ['GIT_COMMITTER_EMAIL'] = email
    subprocess.run(['git', 'config', 'user.name', name], cwd=ROOT, check=True)
    subprocess.run(['git', 'config', 'user.email', email], cwd=ROOT, check=True)


def verify_git_identity():
    configure_git_identity()
    name = subprocess.check_output(['git', 'config', '--get', 'user.name'], cwd=ROOT, text=True).strip()
    email = subprocess.check_output(['git', 'config', '--get', 'user.email'], cwd=ROOT, text=True).strip()
    if not name or not email:
        raise RuntimeError('Git identity verification failed: user.name/user.email is empty')
    print(f'Git identity: {name} <{email}>')


def git_sync_and_push(max_attempts: int = 4):
    """Synchronize with origin/main and push without losing remote commits."""
    verify_git_identity()
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=ROOT, check=True)
            subprocess.run(['git', 'rebase', 'origin/main'], cwd=ROOT, check=True)
            subprocess.run(['git', 'push', 'origin', 'HEAD:main'], cwd=ROOT, check=True)
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            # If rebase entered a conflict, abort it before the next retry so
            # the local commit remains intact and can be rebased again.
            subprocess.run(['git', 'rebase', '--abort'], cwd=ROOT, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # A concurrent Sheet sync can update main between fetch/rebase/push.
            # Retry from the latest remote state rather than force-pushing.
            if attempt < max_attempts:
                time.sleep(min(10, 2 * attempt))
                continue
            raise last_error


def publish_social_assets_to_pages(paths, news_id: str):
    """Commit generated social assets and push them so GitHub Pages can serve them."""
    rels = [Path(p).relative_to(ROOT).as_posix() for p in paths]
    subprocess.run(['git', 'add', *rels], cwd=ROOT, check=True)
    staged = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT)
    if staged.returncode != 0:
        subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=ROOT, check=True)
        subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=ROOT, check=True)
        subprocess.run(['git', 'commit', '-m', f'Create social assets for news {news_id}'], cwd=ROOT, check=True)
        git_sync_and_push()


def commit_social_state():
    """Persist publisher state/log and push them safely to main."""
    # Do this before staging/commit so no code path can reach git commit
    # without an explicit author/committer identity.
    verify_git_identity()
    subprocess.run(['git', 'add', 'social-publish-state.json', 'social-publish-log.json'], cwd=ROOT, check=True)
    if (ROOT / 'social-media').is_dir():
        subprocess.run(['git', 'add', 'social-media'], cwd=ROOT, check=True)
    staged = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT)
    if staged.returncode == 0:
        return False
    # The workflow's checkout does not guarantee a preconfigured Git identity.
    # Configure it BEFORE commit (not only before push), otherwise Git aborts
    # with "Author identity unknown" before git_sync_and_push() is reached.
    configure_git_identity()
    subprocess.run(['git', 'commit', '-m', 'Update social auto-publish state'], cwd=ROOT, check=True)
    git_sync_and_push()
    return True

def wait_public(url: str, attempts: int = 12) -> bool:
    for i in range(attempts):
        try:
            r = requests.get(url, timeout=15, allow_redirects=True, headers={'User-Agent':'BanglasangbadSocialBot/1.0'})
            if r.status_code == 200 and len(r.content) > 100:
                return True
        except Exception:
            pass
        time.sleep(min(10, 2 + i))
    return False


def load_news():
    data = load_json(NEWS_FILE, {})
    return data.get('news') or []


def enabled(platform: str):
    # Global workflow safety switch. The Google Sheet still controls each row.
    return env_bool(f'ENABLE_{platform.upper()}', True)


AUTO_DEFAULT_PLATFORMS = {'facebook', 'instagram'}
TRUE_VALUES = {'yes', 'y', 'true', '1', 'on'}
FALSE_VALUES = {'no', 'n', 'false', '0', 'off', 'disable', 'disabled'}


def sheet_control(item: dict, key: str, default: bool = False) -> bool:
    """Read an optional Google-Sheet publishing switch safely.

    The website sync workflow normalizes news-data.json to the frontend
    columns, so optional social-control columns may be absent. Missing/blank
    controls therefore use the automatic defaults: Facebook and Instagram
    are enabled; the other platforms remain disabled unless explicitly
    enabled. Explicit NO/FALSE always disables a platform.
    """
    raw = item.get(key, None)
    value = clean_text(raw).lower() if raw is not None else ''
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def sheet_yes(item: dict, key: str) -> bool:
    """Backward-compatible boolean helper using the automatic defaults."""
    default = key in AUTO_DEFAULT_PLATFORMS or key == 'publish'
    return sheet_control(item, key, default=default)


def requested_platforms(item: dict) -> list[str]:
    """Return platforms that should be published for this news item.

    Google Sheet -> website -> social is the intended workflow. If the
    optional social-control columns are missing/blank after news-data
    normalization, Facebook and Instagram are automatically selected.
    Other platforms require an explicit YES so they cannot accidentally run
    when their credentials are empty.
    """
    if not sheet_control(item, 'publish', default=True):
        return []
    requested = []
    for platform in PLATFORMS:
        default = platform in AUTO_DEFAULT_PLATFORMS
        if enabled(platform) and sheet_control(item, platform, default=default):
            requested.append(platform)
    return requested


def reconcile_state(state: dict) -> None:
    """Repair stale aggregate states without deleting platform evidence."""
    articles = state.setdefault('articles', {})
    for nid, entry in articles.items():
        platforms = entry.setdefault('platforms', {})
        for platform, pentry in platforms.items():
            if not isinstance(pentry, dict):
                continue
            if pentry.get('status') == 'posted' and pentry.get('error'):
                pentry['status'] = 'failed'
                pentry['updated_at'] = utc_now()
        requested = [p for p in PLATFORMS if platforms.get(p, {}).get('status') != 'not_selected']
        if entry.get('status') == 'posted_all' and any(platforms.get(p, {}).get('status') == 'failed' for p in requested):
            entry['status'] = 'partial_failure'
            entry['updated_at'] = utc_now()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=5)
    args = ap.parse_args()

    state = load_json(STATE_FILE, {'version':2,'articles':{}})
    state.setdefault('version',2); state.setdefault('articles',{})
    log = load_json(LOG_FILE, {'generated_at':None,'articles':{}})
    log.setdefault('articles',{})
    reconcile_state(state)

    # Validate Meta once, before touching the queue. This prevents a bad token
    # from causing a long series of predictable per-article failures.
    meta_preflight(args.dry_run)

    news = sorted(load_news(), key=lambda x: int(str(x.get('id','0')) or 0))
    candidates = []
    for item in news:
        nid = str(item.get('id','')).strip()
        if not nid or not clean_text(item.get('headline')):
            continue
        entry = state['articles'].setdefault(nid, {'status':'pending','platforms':{}})
        if entry.get('status') == 'skipped_existing':
            continue

        requested = requested_platforms(item)
        entry['sheet_controls'] = {
            'publish': sheet_yes(item, 'publish'),
            'facebook': sheet_yes(item, 'facebook'),
            'instagram': sheet_yes(item, 'instagram'),
            'x': sheet_yes(item, 'x'),
            'threads': sheet_yes(item, 'threads'),
            'youtube': sheet_yes(item, 'youtube'),
        }

        if not requested:
            entry['status'] = ('waiting_sheet_publish'
                               if not sheet_yes(item, 'publish')
                               else 'no_social_platform_selected')
            entry['updated_at'] = utc_now()
            continue

        if all(entry.get('platforms',{}).get(p,{}).get('status') == 'posted' for p in requested):
            entry['status']='posted_all'; continue
        candidates.append(item)
    candidates = candidates[:args.limit]

    for item in candidates:
        nid = str(item['id'])
        entry = state['articles'].setdefault(nid, {'status':'pending','platforms':{}})
        entry['last_attempt_at'] = utc_now()
        try:
            image_path = local_image_for(item)
            if not image_path:
                temp = ROOT / '.social-tmp' / f'{nid}.jpg'
                image_path = download_remote_image(item, temp)
            if not image_path:
                raise RuntimeError(f'No usable news image for article {nid}')

            card = CARD_DIR / f'{nid}.jpg'
            create_card(image_path, clean_text(item['headline']), bangla_date(item.get('date','')), ROOT/'logo.png', card, width=1200, height=1500, category=clean_text(item.get('category')))
            # Instagram uses the same visual template, resized to its 4:5 feed format.
            ig_card = CARD_DIR / 'instagram' / f'{nid}.jpg'
            create_card(image_path, clean_text(item['headline']), bangla_date(item.get('date','')), ROOT/'logo.png', ig_card, width=1080, height=1350, category=clean_text(item.get('category')))
            carousel_paths = []
            if instagram_needs_carousel(item):
                carousel_dir = CARD_DIR / 'instagram' / str(nid)
                carousel_paths = create_instagram_carousel(
                    image_path,
                    clean_text(item.get('headline')),
                    clean_text(item.get('details')),
                    bangla_date(item.get('date','')),
                    ROOT/'logo.png',
                    carousel_dir,
                    nid,
                    max_slides=10,
                )
            entry['social_card'] = f'social-media/{nid}.jpg'
            entry['instagram_image'] = f'social-media/instagram/{nid}.jpg'
            if carousel_paths:
                entry['instagram_carousel'] = [Path(p).relative_to(ROOT).as_posix() for p in carousel_paths]
            else:
                entry.pop('instagram_carousel', None)
            entry['updated_at'] = utc_now()

            requested = requested_platforms(item)
            video_path = VIDEO_DIR / f'{nid}.mp4'
            if 'youtube' in requested and env_bool('AUTO_YOUTUBE_VIDEO', True) and not video_path.exists():
                generate_video(item, image_path, video_path)

            # In dry-run, do not require the card to be publicly visible.
            if not args.dry_run:
                article_url = news_url(nid)
                if not wait_public(article_url, attempts=24):
                    raise RuntimeError(f'News article URL is not publicly reachable yet: {article_url}')
                asset_paths = [card, ig_card] + carousel_paths
                # Preserve order while removing duplicates.
                unique_asset_paths = list(dict.fromkeys(asset_paths))
                publish_social_assets_to_pages(unique_asset_paths, nid)
                public_urls = [f'{SITE_BASE_URL}/social-media/{nid}.jpg', f'{SITE_BASE_URL}/social-media/instagram/{nid}.jpg']
                for public_url in public_urls:
                    if not wait_public(public_url, attempts=24):
                        raise RuntimeError(f'Social asset is not publicly reachable yet: {public_url}')
                for cp in carousel_paths:
                    public_url = f'{SITE_BASE_URL}/social-media/instagram/{nid}/{Path(cp).name}'
                    if not wait_public(public_url, attempts=24):
                        raise RuntimeError(f'Instagram carousel asset is not publicly reachable yet: {public_url}')

            funcs = {
                'facebook': lambda: facebook_publish(item, card, args.dry_run, pentry.get('result')),
                'instagram': lambda: instagram_publish(item, ig_card, carousel_paths, args.dry_run, pentry.get('result')),
                'x': lambda: x_publish(item, card, args.dry_run),
                'threads': lambda: threads_publish(item, args.dry_run),
                'youtube': lambda: youtube_upload(item, video_path, args.dry_run),
            }
            for platform in PLATFORMS:
                if platform not in requested:
                    entry['platforms'].setdefault(platform, {'status':'not_selected'})
                    continue
                pentry = entry['platforms'].setdefault(platform, {})
                if pentry.get('status') == 'posted':
                    continue
                try:
                    result = funcs[platform]()
                    result_status = str(result.get('status', '')) if isinstance(result, dict) else ''
                    successful = args.dry_run or (isinstance(result, dict) and result_status == 'posted' and bool(result.get('id') or result.get('post_id')))
                    pentry.update({
                        'status': 'dry_run' if args.dry_run else ('posted' if successful else 'failed'),
                        'updated_at': utc_now(),
                        'result': result,
                    })
                    if not successful:
                        pentry['error'] = (result.get('error') or result.get('comment_error') or 'Platform publish did not complete successfully') if isinstance(result, dict) else 'Platform publish did not complete successfully'
                except Exception as exc:
                    pentry.update({'status':'failed','updated_at':utc_now(),'error':str(exc)})
            if requested and all(entry['platforms'].get(p,{}).get('status') in {'posted','dry_run'} for p in requested):
                entry['status'] = 'dry_run' if args.dry_run else 'posted_all'
            else:
                entry['status'] = 'partial_failure'
        except Exception as exc:
            entry['status']='failed_preflight'; entry['error']=str(exc); entry['updated_at']=utc_now()
        log['articles'][nid] = entry

    state['updated_at']=utc_now(); log['generated_at']=utc_now()
    save_json(STATE_FILE,state); save_json(LOG_FILE,log)

    # Persist state here so the workflow's final git push is only a safety check.
    # This avoids a second independent writer racing with the Sheet sync workflow.
    if not args.dry_run:
        commit_social_state()

    print(json.dumps({
        'processed':[str(x['id']) for x in candidates],
        'dry_run':args.dry_run,
        'total_news': len(news),
        'candidate_count': len(candidates),
        'latest_news_id': str(news[-1].get('id')) if news else None,
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
