from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from social_card import create_card, create_vertical_frame

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / 'social-publish-state.json'
LOG_FILE = ROOT / 'social-publish-log.json'
NEWS_FILE = ROOT / 'news-data.json'
CARD_DIR = ROOT / 'social-media'
VIDEO_DIR = ROOT / 'social-video'

META_VERSION = os.getenv('META_GRAPH_VERSION', 'v26.0')
META_BASE = f'https://graph.facebook.com/{META_VERSION}'
THREADS_BASE = os.getenv('THREADS_GRAPH_BASE', 'https://graph.threads.net/v1.0')
SITE_BASE_URL = os.getenv(
    'SITE_BASE_URL',
    'https://abdurrazzak123.github.io/Banglasangbad'
).rstrip('/')

PLATFORMS = ('facebook', 'instagram', 'x', 'threads', 'youtube')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path: Path, data: Any):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def clean_text(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def bangla_date(value: str) -> str:
    months = {
        '01': 'জানুয়ারি',
        '02': 'ফেব্রুয়ারি',
        '03': 'মার্চ',
        '04': 'এপ্রিল',
        '05': 'মে',
        '06': 'জুন',
        '07': 'জুলাই',
        '08': 'আগস্ট',
        '09': 'সেপ্টেম্বর',
        '10': 'অক্টোবর',
        '11': 'নভেম্বর',
        '12': 'ডিসেম্বর'
    }

    digits = str.maketrans(
        '0123456789',
        '০১২৩৪৫৬৭৮৯'
    )

    m = re.match(
        r'^(\d{4})-(\d{2})-(\d{2})',
        str(value or '')
    )

    if not m:
        return clean_text(value)

    return (
        f"{m.group(3).translate(digits)} "
        f"{months.get(m.group(2), m.group(2))} "
        f"{m.group(1).translate(digits)}"
    )


def news_url(news_id: str) -> str:
    return f'{SITE_BASE_URL}/news/{news_id}.html'


def local_image_for(item: dict) -> Path | None:
    candidates = []

    for x in item.get('images') or []:
        if x:
            candidates.append(x)

    for x in item.get('image_urls') or []:
        if x and x.startswith(('http://', 'https://')):
            continue

    for raw in candidates:
        p = ROOT / raw
        if p.exists() and p.is_file():
            return p

    nid = str(item.get('id', ''))

    for ext in ('jpg', 'jpeg', 'png', 'webp'):
        p = ROOT / 'assets' / 'news' / f'{nid}-1.{ext}'
        if p.exists():
            return p

    return None


def download_remote_image(item: dict, dest: Path) -> Path | None:
    for raw in item.get('image_urls') or []:
        if not raw or not raw.startswith(('http://', 'https://')):
            continue

        m = re.search(r'/file/d/([^/]+)', raw)

        url = (
            f'https://drive.google.com/uc?export=download&id={m.group(1)}'
            if m
            else raw
        )

        try:
            r = requests.get(
                url,
                timeout=30,
                headers={
                    'User-Agent':
                    'BanglasangbadSocialBot/1.0'
                }
            )

            r.raise_for_status()

            dest.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            dest.write_bytes(r.content)

            if dest.stat().st_size > 1000:
                return dest

        except Exception:
            continue

    return None


def request_json(method, url, **kwargs):
    kwargs.setdefault('timeout', 60)

    for attempt in range(4):
        try:
            r = requests.request(
                method,
                url,
                **kwargs
            )

            if r.status_code in (
                429,
                500,
                502,
                503,
                504
            ):
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue

            if not r.ok:
                try:
                    detail = r.json()
                except Exception:
                    detail = r.text[:1000]

                raise RuntimeError(
                    f'{method} {url} -> '
                    f'HTTP {r.status_code}: {detail}'
                )

            return r.json() if r.text else {}

        except requests.RequestException:
            if attempt == 3:
                raise

            time.sleep(2 ** attempt)

    raise RuntimeError('unreachable')


# ============================================================
# SOCIAL CAPTION
# ============================================================

def caption(item: dict) -> str:
    """
    মূল social post-এ আর headline বা website URL থাকবে না।
    শুধু category hashtag + বাংলা সংবাদ hashtag থাকবে।
    """

    category = clean_text(
        item.get('category')
    )

    category_tag = re.sub(
        r"[^\w\u0980-\u09ff]+",
        "",
        category
    )

    if category_tag:
        return f'#{category_tag} #বাংলা_সংবাদ'

    return '#বাংলা_সংবাদ'


# ============================================================
# FACEBOOK
# ============================================================

def facebook_publish(
    item,
    card_path,
    dry_run=False
):
    message = caption(item)

    article_url = news_url(
        str(item["id"])
    )

    first_comment = (
        f'বিস্তারিত সংবাদ পড়ুন 👇\n'
        f'{article_url}'
    )

    if dry_run:
        return {
            'dry_run': True,
            'message': message,
            'first_comment': first_comment
        }

    token = os.getenv(
        'META_PAGE_ACCESS_TOKEN'
    )

    page_id = os.getenv(
        'META_PAGE_ID'
    )

    if not token or not page_id:
        raise RuntimeError(
            'Missing META_PAGE_ID or '
            'META_PAGE_ACCESS_TOKEN'
        )

    data = {
        'url':
            f'{SITE_BASE_URL}/social-media/'
            f'{item["id"]}.jpg',

        'caption': message,

        'access_token': token
    }

    result = request_json(
        'POST',
        f'{META_BASE}/{page_id}/photos',
        data=data
    )

    post_id = (
        result.get('post_id')
        or result.get('id')
    )

    comment_id = None

    if post_id:
        try:
            comment = request_json(
                'POST',
                f'{META_BASE}/{post_id}/comments',
                data={
                    'message': first_comment,
                    'access_token': token
                }
            )

            comment_id = comment.get('id')

        except Exception as exc:
            return {
                'id': post_id,
                'comment_error': str(exc),
                'status':
                    'posted_comment_failed'
            }

    return {
        'id': post_id,
        'first_comment_id': comment_id,
        'article_url': article_url
    }


# ============================================================
# INSTAGRAM
# ============================================================

def instagram_publish(
    item,
    dry_run=False
):
    message = caption(item)

    if dry_run:
        return {
            'dry_run': True,
            'caption': message
        }

    token = os.getenv(
        'META_PAGE_ACCESS_TOKEN'
    )

    ig_id = os.getenv(
        'INSTAGRAM_BUSINESS_ACCOUNT_ID'
    )

    if not token or not ig_id:
        raise RuntimeError(
            'Missing META_PAGE_ACCESS_TOKEN or '
            'INSTAGRAM_BUSINESS_ACCOUNT_ID'
        )

    params = {
        'image_url':
            f'{SITE_BASE_URL}/social-media/'
            f'{item["id"]}.jpg',

        'caption': message,

        'access_token': token
    }

    c = request_json(
        'POST',
        f'{META_BASE}/{ig_id}/media',
        data=params
    )

    creation_id = c.get('id')

    if not creation_id:
        raise RuntimeError(
            f'Instagram container creation '
            f'returned no id: {c}'
        )

    p = request_json(
        'POST',
        f'{META_BASE}/{ig_id}/media_publish',
        data={
            'creation_id': creation_id,
            'access_token': token
        }
    )

    return {
        'id': p.get('id'),
        'creation_id': creation_id
    }


# ============================================================
# X
# ============================================================

def x_upload_image(
    path: Path,
    token: str
) -> str:

    raw = path.read_bytes()

    init = request_json(
        'POST',
        'https://api.x.com/2/media/upload',
        headers={
            'Authorization':
                f'Bearer {token}'
        },
        files={
            'command':
                (None, 'INIT'),

            'media_type':
                (None, 'image/jpeg'),

            'total_bytes':
                (None, str(len(raw))),

            'media_category':
                (None, 'tweet_image')
        }
    )

    mid = (
        (init.get('data') or {})
        .get('id')
    )

    if not mid:
        raise RuntimeError(
            f'X INIT returned no media id: {init}'
        )

    request_json(
        'POST',
        'https://api.x.com/2/media/upload',
        headers={
            'Authorization':
                f'Bearer {token}'
        },
        files={
            'command':
                (None, 'APPEND'),

            'media_id':
                (None, mid),

            'segment_index':
                (None, '0'),

            'media':
                ('social.jpg', raw, 'image/jpeg')
        }
    )

    fin = request_json(
        'POST',
        'https://api.x.com/2/media/upload',
        headers={
            'Authorization':
                f'Bearer {token}'
        },
        files={
            'command':
                (None, 'FINALIZE'),

            'media_id':
                (None, mid)
        }
    )

    info = (
        (fin.get('data') or {})
        .get('processing_info')
    )

    if info:
        for _ in range(30):
            state = info.get('state')

            if state == 'succeeded':
                break

            if state == 'failed':
                raise RuntimeError(
                    f'X media processing failed: {fin}'
                )

            time.sleep(
                int(
                    info.get(
                        'check_after_secs',
                        2
                    )
                )
            )

            status = request_json(
                'GET',
                'https://api.x.com/2/media/upload',
                params={
                    'command': 'STATUS',
                    'media_id': mid
                },
                headers={
                    'Authorization':
                        f'Bearer {token}'
                }
            )

            info = (
                (status.get('data') or {})
                .get('processing_info', {})
            )

    return mid


def x_publish(
    item,
    card_path,
    dry_run=False
):
    text = caption(item)

    if dry_run:
        return {
            'dry_run': True,
            'text': text
        }

    token = os.getenv(
        'X_ACCESS_TOKEN'
    )

    if not token:
        raise RuntimeError(
            'Missing X_ACCESS_TOKEN'
        )

    mid = x_upload_image(
        card_path,
        token
    )

    result = request_json(
        'POST',
        'https://api.x.com/2/tweets',
        headers={
            'Authorization':
                f'Bearer {token}',
            'Content-Type':
                'application/json'
        },
        json={
            'text': text,
            'media': {
                'media_ids': [mid]
            }
        }
    )

    return {
        'id':
            (result.get('data') or {})
            .get('id'),

        'media_id': mid
    }


# ============================================================
# THREADS
# ============================================================

def threads_publish(
    item,
    dry_run=False
):
    text = caption(item)

    if dry_run:
        return {
            'dry_run': True,
            'text': text
        }

    token = os.getenv(
        'THREADS_ACCESS_TOKEN'
    )

    user_id = os.getenv(
        'THREADS_USER_ID',
        'me'
    )

    if not token:
        raise RuntimeError(
            'Missing THREADS_ACCESS_TOKEN'
        )

    params = {
        'media_type': 'IMAGE',

        'image_url':
            f'{SITE_BASE_URL}/social-media/'
            f'{item["id"]}.jpg',

        'text': text,

        'access_token': token
    }

    c = request_json(
        'POST',
        f'{THREADS_BASE}/{user_id}/threads',
        params=params
    )

    cid = c.get('id')

    if not cid:
        raise RuntimeError(
            f'Threads container returned no id: {c}'
        )

    p = request_json(
        'POST',
        f'{THREADS_BASE}/{user_id}/threads_publish',
        params={
            'creation_id': cid,
            'access_token': token
        }
    )

    return {
        'id': p.get('id'),
        'creation_id': cid
    }


# ============================================================
# YOUTUBE
# ============================================================

def youtube_access_token():
    direct = os.getenv(
        'YOUTUBE_ACCESS_TOKEN'
    )

    if direct:
        return direct

    client_id = os.getenv(
        'YOUTUBE_CLIENT_ID'
    )

    client_secret = os.getenv(
        'YOUTUBE_CLIENT_SECRET'
    )

    refresh = os.getenv(
        'YOUTUBE_REFRESH_TOKEN'
    )

    if not all(
        (
            client_id,
            client_secret,
            refresh
        )
    ):
        raise RuntimeError(
            'Missing YouTube OAuth secrets: '
            'YOUTUBE_CLIENT_ID, '
            'YOUTUBE_CLIENT_SECRET, '
            'YOUTUBE_REFRESH_TOKEN'
        )

    r = request_json(
        'POST',
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh,
            'grant_type': 'refresh_token'
        }
    )

    return r['access_token']


def youtube_upload(
    item,
    video_path: Path,
    dry_run=False
):
    if not video_path.exists():
        raise RuntimeError(
            'YouTube video file was not generated'
        )

    title = clean_text(
        item.get('headline')
    )[:95]

    desc = (
        f'{clean_text(item.get("headline"))}\n\n'
        f'বিস্তারিত খবর: '
        f'{news_url(str(item["id"]))}\n\n'
        f'বাংলা সংবাদ'
    )

    if dry_run:
        return {
            'dry_run': True,
            'title': title,
            'video': str(video_path)
        }

    token = youtube_access_token()

    metadata = {
        'snippet': {
            'title': title,
            'description': desc,
            'categoryId': '25',
            'defaultLanguage': 'bn'
        },

        'status': {
            'privacyStatus':
                os.getenv(
                    'YOUTUBE_PRIVACY_STATUS',
                    'private'
                ),

            'selfDeclaredMadeForKids':
                False
        }
    }

    init = requests.post(
        'https://www.googleapis.com/upload/youtube/v3/videos',
        params={
            'uploadType': 'resumable',
            'part': 'snippet,status'
        },
        headers={
            'Authorization':
                f'Bearer {token}',

            'Content-Type':
                'application/json; charset=UTF-8',

            'X-Upload-Content-Type':
                'video/mp4',

            'X-Upload-Content-Length':
                str(video_path.stat().st_size)
        },
        json=metadata,
        timeout=60
    )

    if not init.ok:
        raise RuntimeError(
            f'YouTube init failed: '
            f'HTTP {init.status_code}: '
            f'{init.text[:1000]}'
        )

    upload_url = init.headers.get(
        'Location'
    )

    if not upload_url:
        raise RuntimeError(
            'YouTube upload session did not '
            'return Location header'
        )

    with video_path.open('rb') as f:
        r = requests.put(
            upload_url,
            headers={
                'Authorization':
                    f'Bearer {token}',

                'Content-Type':
                    'video/mp4',

                'Content-Length':
                    str(video_path.stat().st_size)
            },
            data=f,
            timeout=600
        )

    if not r.ok:
        raise RuntimeError(
            f'YouTube upload failed: '
            f'HTTP {r.status_code}: '
            f'{r.text[:1000]}'
        )

    body = r.json()

    return {
        'id': body.get('id'),
        'privacy_status':
            os.getenv(
                'YOUTUBE_PRIVACY_STATUS',
                'private'
            )
    }


# ============================================================
# VIDEO
# ============================================================

def generate_video(
    item,
    image_path: Path,
    video_path: Path
):
    frame = (
        VIDEO_DIR /
        f'{item["id"]}-frame.jpg'
    )

    create_vertical_frame(
        image_path,
        clean_text(item.get('headline')),
        bangla_date(
            item.get('date', '')
        ),
        ROOT / 'logo.png',
        frame
    )

    video_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    cmd = [
        'ffmpeg',
        '-y',
        '-loop',
        '1',
        '-i',
        str(frame),
        '-vf',
        'scale=1080:1920:'
        'force_original_aspect_ratio=decrease,'
        'pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
        '-t',
        '12',
        '-r',
        '30',
        '-c:v',
        'libx264',
        '-pix_fmt',
        'yuv420p',
        '-movflags',
        '+faststart',
        str(video_path)
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )

    try:
        frame.unlink()
    except OSError:
        pass


# ============================================================
# GITHUB SOCIAL CARD
# ============================================================

def publish_social_card_to_pages(
    card_path: Path,
    news_id: str
):
    """
    Commit only the generated social card
    so GitHub Pages can serve it publicly.
    """

    rel = (
        card_path
        .relative_to(ROOT)
        .as_posix()
    )

    subprocess.run(
        ['git', 'add', rel],
        cwd=ROOT,
        check=True
    )

    staged = subprocess.run(
        [
            'git',
            'diff',
            '--cached',
            '--quiet'
        ],
        cwd=ROOT
    )

    if staged.returncode != 0:
        subprocess.run(
            [
                'git',
                'config',
                'user.name',
                'github-actions[bot]'
            ],
            cwd=ROOT,
            check=True
        )

        subprocess.run(
            [
                'git',
                'config',
                'user.email',
                '41898282+github-actions[bot]@users.noreply.github.com'
            ],
            cwd=ROOT,
            check=True
        )

        subprocess.run(
            [
                'git',
                'commit',
                '-m',
                f'Create social card for news
