from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from social_card import create_card, create_vertical_frame


ROOT = Path(__file__).resolve().parents[1]

STATE_FILE = ROOT / "social-publish-state.json"
LOG_FILE = ROOT / "social-publish-log.json"
NEWS_FILE = ROOT / "news-data.json"

CARD_DIR = ROOT / "social-media"
VIDEO_DIR = ROOT / "social-video"

META_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
META_BASE = f"https://graph.facebook.com/{META_VERSION}"

THREADS_BASE = os.getenv(
    "THREADS_GRAPH_BASE",
    "https://graph.threads.net/v1.0"
)

SITE_BASE_URL = os.getenv(
    "SITE_BASE_URL",
    "https://abdurrazzak123.github.io/Banglasangbad"
).rstrip("/")

PLATFORMS = (
    "facebook",
    "instagram",
    "x",
    "threads",
    "youtube",
)


# ============================================================
# BASIC HELPERS
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def load_json(path: Path, default: Any):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def clean_text(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "")
    ).strip()


def bangla_date(value: str) -> str:
    months = {
        "01": "জানুয়ারি",
        "02": "ফেব্রুয়ারি",
        "03": "মার্চ",
        "04": "এপ্রিল",
        "05": "মে",
        "06": "জুন",
        "07": "জুলাই",
        "08": "আগস্ট",
        "09": "সেপ্টেম্বর",
        "10": "অক্টোবর",
        "11": "নভেম্বর",
        "12": "ডিসেম্বর",
    }

    digits = str.maketrans(
        "0123456789",
        "০১২৩৪৫৬৭৮৯"
    )

    m = re.match(
        r"^(\d{4})-(\d{2})-(\d{2})",
        str(value or "")
    )

    if not m:
        return clean_text(value)

    return (
        f"{m.group(3).translate(digits)} "
        f"{months.get(m.group(2), m.group(2))} "
        f"{m.group(1).translate(digits)}"
    )


def news_url(news_id: str) -> str:
    return f"{SITE_BASE_URL}/news/{news_id}.html"


# ============================================================
# HTTP
# ============================================================

def request_json(method, url, **kwargs):
    kwargs.setdefault("timeout", 60)

    last_error = None

    for attempt in range(4):
        try:
            response = requests.request(
                method,
                url,
                **kwargs
            )

            if response.status_code in (
                429,
                500,
                502,
                503,
                504,
            ):
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue

            if not response.ok:
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:2000]

                raise RuntimeError(
                    f"{method} {url} -> "
                    f"HTTP {response.status_code}: {detail}"
                )

            if not response.text:
                return {}

            return response.json()

        except requests.RequestException as exc:
            last_error = exc

            if attempt == 3:
                raise

            time.sleep(2 ** attempt)

    raise RuntimeError(
        f"Request failed: {last_error}"
    )


# ============================================================
# META DIAGNOSTIC
# ============================================================

def meta_preflight() -> dict:
    """
    Checks whether the Meta credentials supplied to GitHub Actions
    can access the configured Facebook Page and Instagram account.

    IMPORTANT:
    The actual token value is NEVER printed.
    """

    result = {
        "status": "unknown",
        "facebook": {},
        "instagram": {},
    }

    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

    if not token:
        result["status"] = "failed"
        result["facebook"] = {
            "status": "failed",
            "error": "META_PAGE_ACCESS_TOKEN is missing",
        }
        result["instagram"] = {
            "status": "not_checked",
        }
        return result

    if not page_id:
        result["status"] = "failed"
        result["facebook"] = {
            "status": "failed",
            "error": "META_PAGE_ID is missing",
        }
        result["instagram"] = {
            "status": "not_checked",
        }
        return result

    # --------------------------------------------------------
    # Facebook Page check
    # --------------------------------------------------------

    try:
        page = request_json(
            "GET",
            f"{META_BASE}/{page_id}",
            params={
                "fields": "id,name",
                "access_token": token,
            },
        )

        result["facebook"] = {
            "status": "ok",
            "id": page.get("id"),
            "name": page.get("name"),
        }

    except Exception as exc:
        result["facebook"] = {
            "status": "failed",
            "error": str(exc),
        }

    # --------------------------------------------------------
    # Instagram account check
    # --------------------------------------------------------

    if ig_id:
        try:
            instagram = request_json(
                "GET",
                f"{META_BASE}/{ig_id}",
                params={
                    "fields": "id,username",
                    "access_token": token,
                },
            )

            result["instagram"] = {
                "status": "ok",
                "id": instagram.get("id"),
                "username": instagram.get("username"),
            }

        except Exception as exc:
            result["instagram"] = {
                "status": "failed",
                "error": str(exc),
            }

    else:
        result["instagram"] = {
            "status": "failed",
            "error": (
                "INSTAGRAM_BUSINESS_ACCOUNT_ID "
                "is missing"
            ),
        }

    if (
        result["facebook"].get("status") == "ok"
        and result["instagram"].get("status") == "ok"
    ):
        result["status"] = "ok"

    elif result["facebook"].get("status") == "ok":
        result["status"] = "facebook_ok_instagram_failed"

    elif result["instagram"].get("status") == "ok":
        result["status"] = "instagram_ok_facebook_failed"

    else:
        result["status"] = "failed"

    return result


# ============================================================
# IMAGE
# ============================================================

def local_image_for(item: dict) -> Path | None:
    candidates = []

    for value in item.get("images") or []:
        if value:
            candidates.append(value)

    for raw in candidates:
        path = ROOT / raw

        if path.exists() and path.is_file():
            return path

    nid = str(item.get("id", ""))

    for ext in (
        "jpg",
        "jpeg",
        "png",
        "webp",
    ):
        path = (
            ROOT
            / "assets"
            / "news"
            / f"{nid}-1.{ext}"
        )

        if path.exists():
            return path

    return None


def download_remote_image(
    item: dict,
    dest: Path
) -> Path | None:

    for raw in item.get("image_urls") or []:

        if not raw:
            continue

        if not raw.startswith(
            ("http://", "https://")
        ):
            continue

        match = re.search(
            r"/file/d/([^/]+)",
            raw
        )

        url = (
            f"https://drive.google.com/uc"
            f"?export=download&id={match.group(1)}"
            if match
            else raw
        )

        try:
            response = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent":
                        "BanglasangbadSocialBot/1.0"
                },
            )

            response.raise_for_status()

            dest.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            dest.write_bytes(
                response.content
            )

            if dest.stat().st_size > 1000:
                return dest

        except Exception:
            continue

    return None


# ============================================================
# CAPTION
# ============================================================

def caption(item: dict) -> str:
    headline = clean_text(
        item.get("headline")
    )

    category = clean_text(
        item.get("category")
    )

    clean_category = re.sub(
        r"[^\w\u0980-\u09ff]+",
        "",
        category
    )

    return (
        f"📰 {headline}\n\n"
        f"বিস্তারিত: "
        f"{news_url(str(item.get('id')))}\n\n"
        f"#{clean_category} "
        f"#বাংলা_সংবাদ"
    )


# ============================================================
# FACEBOOK
# ============================================================

def facebook_publish(
    item,
    card_path,
    dry_run=False
):

    message = caption(item)

    if dry_run:
        return {
            "status": "dry_run",
            "message": message,
        }

    token = os.getenv(
        "META_PAGE_ACCESS_TOKEN"
    )

    page_id = os.getenv(
        "META_PAGE_ID"
    )

    if not token:
        raise RuntimeError(
            "Missing META_PAGE_ACCESS_TOKEN"
        )

    if not page_id:
        raise RuntimeError(
            "Missing META_PAGE_ID"
        )

    public_image_url = (
        f"{SITE_BASE_URL}/social-media/"
        f"{item['id']}.jpg"
    )

    result = request_json(
        "POST",
        f"{META_BASE}/{page_id}/photos",
        data={
            "url": public_image_url,
            "caption": message,
            "access_token": token,
        },
    )

    post_id = (
        result.get("post_id")
        or result.get("id")
    )

    if not post_id:
        raise RuntimeError(
            f"Facebook returned no post id: {result}"
        )

    return {
        "status": "posted",
        "id": post_id,
        "public_image_url": public_image_url,
    }


# ============================================================
# INSTAGRAM
# ============================================================

def instagram_publish(
    item,
    dry_run=False
):

    text = caption(item)

    if dry_run:
        return {
            "status": "dry_run",
            "caption": text,
        }

    token = os.getenv(
        "META_PAGE_ACCESS_TOKEN"
    )

    ig_id = os.getenv(
        "INSTAGRAM_BUSINESS_ACCOUNT_ID"
    )

    if not token:
        raise RuntimeError(
            "Missing META_PAGE_ACCESS_TOKEN"
        )

    if not ig_id:
        raise RuntimeError(
            "Missing INSTAGRAM_BUSINESS_ACCOUNT_ID"
        )

    image_url = (
        f"{SITE_BASE_URL}/social-media/"
        f"{item['id']}.jpg"
    )

    container = request_json(
        "POST",
        f"{META_BASE}/{ig_id}/media",
        data={
            "image_url": image_url,
            "caption": text,
            "access_token": token,
        },
    )

    creation_id = container.get("id")

    if not creation_id:
        raise RuntimeError(
            "Instagram container creation "
            f"returned no id: {container}"
        )

    published = request_json(
        "POST",
        f"{META_BASE}/{ig_id}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": token,
        },
    )

    post_id = published.get("id")

    if not post_id:
        raise RuntimeError(
            "Instagram publish returned no id: "
            f"{published}"
        )

    return {
        "status": "posted",
        "id": post_id,
        "creation_id": creation_id,
        "image_url": image_url,
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
        "POST",
        "https://api.x.com/2/media/upload",
        headers={
            "Authorization": f"Bearer {token}"
        },
        files={
            "command": (None, "INIT"),
            "media_type": (
                None,
                "image/jpeg"
            ),
            "total_bytes": (
                None,
                str(len(raw))
            ),
            "media_category": (
                None,
                "tweet_image"
            ),
        },
    )

    mid = (
        init.get("data") or {}
    ).get("id")

    if not mid:
        raise RuntimeError(
            f"X INIT returned no media id: {init}"
        )

    request_json(
        "POST",
        "https://api.x.com/2/media/upload",
        headers={
            "Authorization": f"Bearer {token}"
        },
        files={
            "command": (None, "APPEND"),
            "media_id": (None, mid),
            "segment_index": (None, "0"),
            "media": (
                "social.jpg",
                raw,
                "image/jpeg"
            ),
        },
    )

    finalize = request_json(
        "POST",
        "https://api.x.com/2/media/upload",
        headers={
            "Authorization": f"Bearer {token}"
        },
        files={
            "command": (None, "FINALIZE"),
            "media_id": (None, mid),
        },
    )

    info = (
        (finalize.get("data") or {})
        .get("processing_info")
    )

    if info:
        for _ in range(30):

            state = info.get("state")

            if state == "succeeded":
                break

            if state == "failed":
                raise RuntimeError(
                    f"X media processing failed: "
                    f"{finalize}"
                )

            time.sleep(
                int(
                    info.get(
                        "check_after_secs",
                        2
                    )
                )
            )

            status = request_json(
                "GET",
                "https://api.x.com/2/media/upload",
                params={
                    "command": "STATUS",
                    "media_id": mid,
                },
                headers={
                    "Authorization":
                        f"Bearer {token}"
                },
            )

            info = (
                (status.get("data") or {})
                .get("processing_info", {})
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
            "status": "dry_run",
            "text": text,
        }

    token = os.getenv(
        "X_ACCESS_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "Missing X_ACCESS_TOKEN"
        )

    media_id = x_upload_image(
        card_path,
        token
    )

    result = request_json(
        "POST",
        "https://api.x.com/2/tweets",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":
                "application/json",
        },
        json={
            "text": text,
            "media": {
                "media_ids": [media_id]
            },
        },
    )

    return {
        "status": "posted",
        "id": (
            result.get("data") or {}
        ).get("id"),
        "media_id": media_id,
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
            "status": "dry_run",
            "text": text,
        }

    token = os.getenv(
        "THREADS_ACCESS_TOKEN"
    )

    user_id = os.getenv(
        "THREADS_USER_ID",
        "me"
    )

    if not token:
        raise RuntimeError(
            "Missing THREADS_ACCESS_TOKEN"
        )

    image_url = (
        f"{SITE_BASE_URL}/social-media/"
        f"{item['id']}.jpg"
    )

    container = request_json(
        "POST",
        f"{THREADS_BASE}/{user_id}/threads",
        params={
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
            "access_token": token,
        },
    )

    creation_id = container.get("id")

    if not creation_id:
        raise RuntimeError(
            f"Threads container returned no id: "
            f"{container}"
        )

    published = request_json(
        "POST",
        f"{THREADS_BASE}/{user_id}/threads_publish",
        params={
            "creation_id": creation_id,
            "access_token": token,
        },
    )

    return {
        "status": "posted",
        "id": published.get("id"),
        "creation_id": creation_id,
    }


# ============================================================
# YOUTUBE
# ============================================================

def youtube_access_token():

    direct = os.getenv(
        "YOUTUBE_ACCESS_TOKEN"
    )

    if direct:
        return direct

    client_id = os.getenv(
        "YOUTUBE_CLIENT_ID"
    )

    client_secret = os.getenv(
        "YOUTUBE_CLIENT_SECRET"
    )

    refresh = os.getenv(
        "YOUTUBE_REFRESH_TOKEN"
    )

    if not all(
        (
            client_id,
            client_secret,
            refresh,
        )
    ):
        raise RuntimeError(
            "Missing YouTube OAuth secrets"
        )

    response = request_json(
        "POST",
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
    )

    return response["access_token"]


def youtube_upload(
    item,
    video_path: Path,
    dry_run=False
):

    if not video_path.exists():
        raise RuntimeError(
            "YouTube video file was not generated"
        )

    title = clean_text(
        item.get("headline")
    )[:95]

    description = (
        f"{clean_text(item.get('headline'))}\n\n"
        f"বিস্তারিত খবর: "
        f"{news_url(str(item['id']))}\n\n"
        f"বাংলা সংবাদ"
    )

    if dry_run:
        return {
            "status": "dry_run",
            "title": title,
            "video": str(video_path),
        }

    token = youtube_access_token()

    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "25",
            "defaultLanguage": "bn",
        },
        "status": {
            "privacyStatus":
                os.getenv(
                    "YOUTUBE_PRIVACY_STATUS",
                    "private"
                ),
            "selfDeclaredMadeForKids":
                False,
        },
    }

    init = requests.post(
        "https://www.googleapis.com/upload/"
        "youtube/v3/videos",
        par
