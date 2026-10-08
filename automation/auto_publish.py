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
THREADS_BASE = os.getenv("THREADS_GRAPH_BASE", "https://graph.threads.net/v1.0")
SITE_BASE_URL = os.getenv(
    "SITE_BASE_URL",
    "https://abdurrazzak123.github.io/Banglasangbad",
).rstrip("/")

PLATFORMS = ("facebook", "instagram", "x", "threads", "youtube")

GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "abdurrazzak123/Banglasangbad")
GITHUB_REF_NAME = os.getenv("GITHUB_REF_NAME", "main")


def social_card_url(news_id: str, platform: str = "facebook") -> str:
    """Return the raw GitHub image URL used by Meta."""
    rel = (
        f"social-media/{news_id}.jpg"
        if platform.lower() == "facebook"
        else f"social-media/instagram/{news_id}.jpg"
    )
    return f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_REF_NAME}/{rel}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def bangla_date(value: str) -> str:
    months = {
        "01": "জানুয়ারি", "02": "ফেব্রুয়ারি", "03": "মার্চ",
        "04": "এপ্রিল", "05": "মে", "06": "জুন",
        "07": "জুলাই", "08": "আগস্ট", "09": "সেপ্টেম্বর",
        "10": "অক্টোবর", "11": "নভেম্বর", "12": "ডিসেম্বর",
    }
    digits = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    if not m:
        return clean_text(value)
    return (
        f"{m.group(3).translate(digits)} "
        f"{months.get(m.group(2), m.group(2))} "
        f"{m.group(1).translate(digits)}"
    )


def news_url(news_id: str) -> str:
    return f"{SITE_BASE_URL}/news/{news_id}.html"


def request_json(method: str, url: str, **kwargs):
    kwargs.setdefault("timeout", 60)
    for attempt in range(4):
        try:
            r = requests.request(method, url, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            if not r.ok:
                try:
                    detail = r.json()
                except Exception:
                    detail = r.text[:2000]
                raise RuntimeError(
                    f"{method} {url} -> HTTP {r.status_code}: {detail}"
                )
            return r.json() if r.text else {}
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Request failed")


def local_image_for(item: dict) -> Path | None:
    for raw in item.get("images") or []:
        if raw:
            p = ROOT / raw
            if p.exists() and p.is_file():
                return p

    nid = str(item.get("id", ""))
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = ROOT / "assets" / "news" / f"{nid}-1.{ext}"
        if p.exists():
            return p
    return None


def download_remote_image(item: dict, dest: Path) -> Path | None:
    for raw in item.get("image_urls") or []:
        if not raw or not raw.startswith(("http://", "https://")):
            continue

        m = re.search(r"/file/d/([^/]+)", raw)
        url = (
            f"https://drive.google.com/uc?export=download&id={m.group(1)}"
            if m else raw
        )

        try:
            r = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "BanglasangbadSocialBot/1.0"},
            )
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            if dest.stat().st_size > 1000:
                return dest
        except Exception:
            continue
    return None


def caption(item: dict, include_url: bool = True, full_details: bool = False) -> str:
    headline = clean_text(item.get("headline"))
    category = clean_text(item.get("category"))
    details = str(item.get("details") or "").strip()
    tag = re.sub(r"[^\w\u0980-\u09ff]+", "", category)

    # Instagram captions are limited to 2,200 characters. Keep the headline and
    # a meaningful portion of the article while always preserving the news link.
    if full_details and details:
        link = f"বিস্তারিত: {news_url(str(item.get('id')))}"
        hashtags = f"#{tag} #বাংলা_সংবাদ"
        fixed = len(f"📰 {headline}\n\n{link}\n\n{hashtags}")
        available = max(500, 2200 - fixed - 12)
        if len(details) > available:
            details = details[:available].rsplit(" ", 1)[0].rstrip("।,;: ") + "…"

    parts = [f"📰 {headline}"]
    if full_details and details:
        parts.append(details)
    if include_url:
        parts.append(f"বিস্তারিত: {news_url(str(item.get('id')))}")
    parts.append(f"#{tag} #বাংলা_সংবাদ")
    return "\n\n".join(p for p in parts if p)


def article_link_comment(item: dict) -> str:
    return f"বিস্তারিত খবর: {news_url(str(item.get('id')))}"


def meta_preflight() -> dict:
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
        return result

    if not page_id:
        result["status"] = "failed"
        result["facebook"] = {
            "status": "failed",
            "error": "META_PAGE_ID is missing",
        }
        return result

    try:
        page = request_json(
            "GET",
            f"{META_BASE}/{page_id}",
            params={"fields": "id,name", "access_token": token},
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

    if ig_id:
        try:
            ig = request_json(
                "GET",
                f"{META_BASE}/{ig_id}",
                params={"fields": "id,username", "access_token": token},
            )
            result["instagram"] = {
                "status": "ok",
                "id": ig.get("id"),
                "username": ig.get("username"),
            }
        except Exception as exc:
            result["instagram"] = {
                "status": "failed",
                "error": str(exc),
            }
    else:
        result["instagram"] = {
            "status": "failed",
            "error": "INSTAGRAM_BUSINESS_ACCOUNT_ID is missing",
        }

    fb_ok = result["facebook"].get("status") == "ok"
    ig_ok = result["instagram"].get("status") == "ok"

    if fb_ok and ig_ok:
        result["status"] = "ok"
    elif fb_ok:
        result["status"] = "facebook_ok_instagram_failed"
    elif ig_ok:
        result["status"] = "instagram_ok_facebook_failed"
    else:
        result["status"] = "failed"

    return result


def facebook_publish(item: dict, card_path: Path, dry_run: bool = False):
    message = caption(item, include_url=False)
    if dry_run:
        return {"status": "dry_run", "message": message}

    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")

    if not token:
        raise RuntimeError("Missing META_PAGE_ACCESS_TOKEN")
    if not page_id:
        raise RuntimeError("Missing META_PAGE_ID")

    image_url = social_card_url(str(item["id"]), "facebook")

    result = request_json(
        "POST",
        f"{META_BASE}/{page_id}/photos",
        data={
            "url": image_url,
            "caption": message,
            "access_token": token,
        },
    )

    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook returned no post id: {result}")

    comment = {"status": "not_attempted"}
    try:
        comment_result = request_json(
            "POST",
            f"{META_BASE}/{post_id}/comments",
            data={
                "message": article_link_comment(item),
                "access_token": token,
            },
        )
        comment = {"status": "posted", "id": comment_result.get("id")}
    except Exception as exc:
        # The post itself is successful even if comment permission is missing.
        comment = {"status": "failed", "error": str(exc)}

    return {
        "status": "posted",
        "id": post_id,
        "image_url": image_url,
        "link_comment": comment,
    }


def instagram_publish(item: dict, dry_run: bool = False):
    # Instagram carries the full article in the caption; no automatic comment is created.
    text = caption(item, include_url=True, full_details=True)
    if dry_run:
        return {"status": "dry_run", "caption": text}

    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

    if not token:
        raise RuntimeError("Missing META_PAGE_ACCESS_TOKEN")
    if not ig_id:
        raise RuntimeError("Missing INSTAGRAM_BUSINESS_ACCOUNT_ID")

    image_url = social_card_url(str(item["id"]), "instagram")

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
            f"Instagram container creation returned no id: {container}"
        )

    # Meta may need time to fetch/process the public image before publishing.
    # Poll the container instead of publishing immediately.
    last_status = {}
    for attempt in range(15):
        try:
            last_status = request_json(
                "GET",
                f"{META_BASE}/{creation_id}",
                params={
                    "fields": "id,status_code,status",
                    "access_token": token,
                },
            )
        except Exception as exc:
            last_status = {"status": "poll_error", "error": str(exc)}

        status_code = str(last_status.get("status_code") or "").upper()
        status = str(last_status.get("status") or "").upper()
        if status_code == "FINISHED" or status == "FINISHED":
            break
        if status_code in {"ERROR", "EXPIRED"} or status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram media container failed: {last_status}")
        if attempt < 14:
            time.sleep(2)
    else:
        raise RuntimeError(f"Instagram media container was not ready: {last_status}")

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
            f"Instagram publish returned no id: {published}"
        )

    return {
        "status": "posted",
        "id": post_id,
        "creation_id": creation_id,
        "image_url": image_url,
    }


def x_upload_image(path: Path, token: str) -> str:
    raw = path.read_bytes()

    init = request_json(
        "POST",
        "https://api.x.com/2/media/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "command": (None, "INIT"),
            "media_type": (None, "image/jpeg"),
            "total_bytes": (None, str(len(raw))),
            "media_category": (None, "tweet_image"),
        },
    )

    mid = (init.get("data") or {}).get("id")
    if not mid:
        raise RuntimeError(f"X INIT returned no media id: {init}")

    request_json(
        "POST",
        "https://api.x.com/2/media/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "command": (None, "APPEND"),
            "media_id": (None, mid),
            "segment_index": (None, "0"),
            "media": ("social.jpg", raw, "image/jpeg"),
        },
    )

    fin = request_json(
        "POST",
        "https://api.x.com/2/media/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "command": (None, "FINALIZE"),
            "media_id": (None, mid),
        },
    )

    info = (fin.get("data") or {}).get("processing_info")

    if info:
        for _ in range(30):
            state = info.get("state")
            if state == "succeeded":
                break
            if state == "failed":
                raise RuntimeError(f"X media processing failed: {fin}")

            time.sleep(int(info.get("check_after_secs", 2)))

            status = request_json(
                "GET",
                "https://api.x.com/2/media/upload",
                params={"command": "STATUS", "media_id": mid},
                headers={"Authorization": f"Bearer {token}"},
            )
            info = (
                (status.get("data") or {})
                .get("processing_info", {})
            )

    return mid


def x_publish(item: dict, card_path: Path, dry_run: bool = False):
    text = caption(item)
    if dry_run:
        return {"status": "dry_run", "text": text}

    token = os.getenv("X_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Missing X_ACCESS_TOKEN")

    media_id = x_upload_image(card_path, token)

    result = request_json(
        "POST",
        "https://api.x.com/2/tweets",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "media": {"media_ids": [media_id]},
        },
    )

    return {
        "status": "posted",
        "id": (result.get("data") or {}).get("id"),
        "media_id": media_id,
    }


def threads_publish(item: dict, dry_run: bool = False):
    text = caption(item)
    if dry_run:
        return {"status": "dry_run", "text": text}

    token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id = os.getenv("THREADS_USER_ID", "me")

    if not token:
        raise RuntimeError("Missing THREADS_ACCESS_TOKEN")

    image_url = social_card_url(str(item["id"]))

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
            f"Threads container returned no id: {container}"
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


def youtube_access_token() -> str:
    direct = os.getenv("YOUTUBE_ACCESS_TOKEN")
    if direct:
        return direct

    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if not all((client_id, client_secret, refresh)):
        raise RuntimeError(
            "Missing YouTube OAuth secrets: "
            "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
            "YOUTUBE_REFRESH_TOKEN"
        )

    r = request_json(
        "POST",
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
    )

    return r["access_token"]


def youtube_upload(
    item: dict,
    video_path: Path,
    dry_run: bool = False,
):
    if not video_path.exists():
        raise RuntimeError("YouTube video file was not generated")

    title = clean_text(item.get("headline"))[:95]
    desc = (
        f"{clean_text(item.get('headline'))}\n\n"
        f"বিস্তারিত খবর: {news_url(str(item['id']))}\n\n"
        "বাংলা সংবাদ"
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
            "description": desc,
            "categoryId": "25",
            "defaultLanguage": "bn",
        },
        "status": {
            "privacyStatus": os.getenv(
                "YOUTUBE_PRIVACY_STATUS", "private"
            ),
            "selfDeclaredMadeForKids": False,
        },
    }

    init_response = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={
            "uploadType": "resumable",
            "part": "snippet,status",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        },
        json=metadata,
        timeout=60,
    )

    if not init_response.ok:
        raise RuntimeError(
            f"YouTube init failed: HTTP {init_response.status_code}: "
            f"{init_response.text[:1000]}"
        )

    upload_url = init_response.headers.get("Location")
    if not upload_url:
        raise RuntimeError(
            "YouTube upload session did not return Location header"
        )

    with video_path.open("rb") as video_file:
        upload_response = requests.put(
            upload_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(video_path.stat().st_size),
            },
            data=video_file,
            timeout=600,
        )

    if not upload_response.ok:
        raise RuntimeError(
            f"YouTube upload failed: HTTP {upload_response.status_code}: "
            f"{upload_response.text[:1000]}"
        )

    body = upload_response.json()

    return {
        "status": "posted",
        "id": body.get("id"),
        "privacy_status": os.getenv(
            "YOUTUBE_PRIVACY_STATUS", "private"
        ),
    }


def generate_video(
    item: dict,
    image_path: Path,
    video_path: Path,
):
    frame = VIDEO_DIR / f"{item['id']}-frame.jpg"

    create_vertical_frame(
        image_path,
        clean_text(item.get("headline")),
        bangla_date(item.get("date", "")),
        ROOT / "logo.png",
        frame,
    )

    video_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(frame),
        "-vf",
        (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
        ),
        "-t", "12",
        "-r", "30",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(video_path),
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    try:
        frame.unlink()
    except OSError:
        pass


def publish_social_card_to_pages(
    card_path: Path,
    news_id: str,
):
    rel = card_path.relative_to(ROOT).as_posix()

    subprocess.run(
        ["git", "add", rel],
        cwd=ROOT,
        check=True,
    )

    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
    )

    if staged.returncode != 0:
        subprocess.run(
            ["git", "config", "user.name", "github-actions[bot]"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                "git", "config", "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                "git", "commit", "-m",
                f"Create social card for news {news_id}",
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["git", "push"],
            cwd=ROOT,
            check=True,
        )


def wait_public(url: str, attempts: int = 15) -> bool:
    for i in range(attempts):
        try:
            r = requests.get(
                url,
                timeout=15,
                allow_redirects=True,
                headers={"User-Agent": "BanglasangbadSocialBot/1.0"},
            )
            if r.status_code == 200 and len(r.content) > 100:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def load_news():
    data = load_json(NEWS_FILE, {})
    return data.get("news") or []


def enabled(platform: str) -> bool:
    return env_bool(f"ENABLE_{platform.upper()}", True)


def sheet_yes(item: dict, key: str) -> bool:
    value = clean_text(item.get(key, ""))
    return value.lower() in {"yes", "y", "true", "1", "on"}


def requested_platforms(item: dict) -> list[str]:
    if not sheet_yes(item, "publish"):
        return []

    return [
        p for p in PLATFORMS
        if enabled(p) and sheet_yes(item, p)
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    state = load_json(
        STATE_FILE,
        {"version": 3, "articles": {}},
    )
    state.setdefault("version", 3)
    state.setdefault("articles", {})

    log = load_json(
        LOG_FILE,
        {"generated_at": None, "articles": {}},
    )
    log.setdefault("articles", {})

    news = sorted(
        load_news(),
        key=lambda x: int(str(x.get("id", "0")) or 0),
    )

    candidates = []
    skipped = []

    for item in news:
        nid = str(item.get("id", "")).strip()
        headline = clean_text(item.get("headline"))

        if not nid:
            skipped.append({
                "id": "",
                "reason": "missing article id",
            })
            continue

        if not headline:
            skipped.append({
                "id": nid,
                "reason": "missing headline",
            })
            continue

        entry = state["articles"].setdefault(
            nid,
            {"status": "pending", "platforms": {}},
        )

        if entry.get("status") == "skipped_existing":
            skipped.append({
                "id": nid,
                "reason": "skipped_existing",
            })
            continue

        controls = {
            "publish": sheet_yes(item, "publish"),
            "facebook": sheet_yes(item, "facebook"),
            "instagram": sheet_yes(item, "instagram"),
            "x": sheet_yes(item, "x"),
            "threads": sheet_yes(item, "threads"),
            "youtube": sheet_yes(item, "youtube"),
        }
        entry["sheet_controls"] = controls

        requested = requested_platforms(item)

        if not controls["publish"]:
            entry["status"] = "waiting_sheet_publish"
            entry["updated_at"] = utc_now()
            skipped.append({
                "id": nid,
                "headline": headline,
                "reason": "publish is not YES",
                "sheet": controls,
            })
            continue

        if not requested:
            entry["status"] = "no_social_platform_selected"
            entry["updated_at"] = utc_now()
            skipped.append({
                "id": nid,
                "headline": headline,
                "reason": "publish is YES, but no social platform is selected",
                "sheet": controls,
            })
            continue

        if all(
            entry.get("platforms", {}).get(p, {}).get("status") == "posted"
            for p in requested
        ):
            entry["status"] = "posted_all"
            skipped.append({
                "id": nid,
                "headline": headline,
                "reason": "all requested platforms already posted",
                "platforms": requested,
            })
            continue

        candidates.append(item)

    candidates = candidates[:max(args.limit, 0)]

    meta_check = None
    wants_meta = any(
        p in requested_platforms(item)
        for item in candidates
        for p in ("facebook", "instagram")
    )

    if wants_meta and not args.dry_run:
        meta_check = meta_preflight()
        print(json.dumps(
            {"meta_preflight": meta_check},
            ensure_ascii=False,
            indent=2,
        ))

    processed = []

    for item in candidates:
        nid = str(item["id"])
        processed.append(nid)

        entry = state["articles"].setdefault(
            nid,
            {"status": "pending", "platforms": {}},
        )
        entry["last_attempt_at"] = utc_now()

        try:
            image_path = local_image_for(item)

            if not image_path:
                temp = ROOT / ".social-tmp" / f"{nid}.jpg"
                image_path = download_remote_image(item, temp)

            if not image_path:
                raise RuntimeError(
                    f"No usable news image for article {nid}"
                )

            headline_text = clean_text(item["headline"])
            date_text = bangla_date(item.get("date", ""))
            fb_card = CARD_DIR / f"{nid}.jpg"
            ig_card = CARD_DIR / "instagram" / f"{nid}.jpg"

            create_card(
                image_path, headline_text, date_text, ROOT / "logo.png", fb_card,
                category=clean_text(item.get("category", "")), platform="facebook",
            )
            create_card(
                image_path, headline_text, date_text, ROOT / "logo.png", ig_card,
                category=clean_text(item.get("category", "")), platform="instagram",
            )

            entry["social_card"] = f"social-media/{nid}.jpg"
            entry["instagram_social_card"] = f"social-media/instagram/{nid}.jpg"
            entry["updated_at"] = utc_now()

            requested = requested_platforms(item)
            video_path = VIDEO_DIR / f"{nid}.mp4"

            if (
                "youtube" in requested
                and env_bool("AUTO_YOUTUBE_VIDEO", True)
                and not video_path.exists()
            ):
                generate_video(item, image_path, video_path)

            if not args.dry_run:
                publish_social_card_to_pages(fb_card, nid)
                publish_social_card_to_pages(ig_card, nid)

                public_card_url = social_card_url(nid, "facebook")
                public_ig_card_url = social_card_url(nid, "instagram")

                if not wait_public(public_card_url, attempts=15):
                    raise RuntimeError(
                        f"Facebook social card is not publicly reachable yet: {public_card_url}"
                    )
                if not wait_public(public_ig_card_url, attempts=15):
                    raise RuntimeError(
                        f"Instagram social card is not publicly reachable yet: {public_ig_card_url}"
                    )

            funcs = {
                "facebook": lambda: facebook_publish(
                    item, fb_card, args.dry_run
                ),
                "instagram": lambda: instagram_publish(
                    item, args.dry_run
                ),
                "x": lambda: x_publish(
                    item, fb_card, args.dry_run
                ),
                "threads": lambda: threads_publish(
                    item, args.dry_run
                ),
                "youtube": lambda: youtube_upload(
                    item, video_path, args.dry_run
                ),
            }

            for platform in PLATFORMS:
                if platform not in requested:
                    entry["platforms"].setdefault(
                        platform,
                        {"status": "not_selected"},
                    )
                    continue

                pentry = entry["platforms"].setdefault(
                    platform,
                    {},
                )

                if pentry.get("status") == "posted":
                    continue

                try:
                    result = funcs[platform]()
                    pentry.update({
                        "status": (
                            "dry_run"
                            if args.dry_run
                            else "posted"
                        ),
                        "updated_at": utc_now(),
                        "result": result,
                    })
                except Exception as exc:
                    pentry.update({
                        "status": "failed",
                        "updated_at": utc_now(),
                        "error": str(exc),
                    })

            if requested and all(
                entry["platforms"].get(p, {}).get("status")
                in {"posted", "dry_run"}
                for p in requested
            ):
                entry["status"] = (
                    "dry_run" if args.dry_run else "posted_all"
                )
            else:
                entry["status"] = "partial_failure"

        except Exception as exc:
            entry["status"] = "failed_preflight"
            entry["error"] = str(exc)
            entry["updated_at"] = utc_now()

        log["articles"][nid] = entry

    state["updated_at"] = utc_now()
    log["generated_at"] = utc_now()
    log["last_run"] = {
        "dry_run": args.dry_run,
        "limit": args.limit,
        "candidate_count": len(candidates),
        "processed": processed,
        "skipped": skipped,
        "meta_preflight": meta_check,
    }

    save_json(STATE_FILE, state)
    save_json(LOG_FILE, log)

    print(json.dumps({
        "processed": processed,
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "dry_run": args.dry_run,
        "limit": args.limit,
        "meta_preflight": meta_check,
        "message": (
            "No eligible article was found. Check the skipped reasons."
            if not processed
            else "Publish pipeline finished. Check each platform status."
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
