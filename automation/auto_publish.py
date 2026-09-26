from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from PIL import Image

AUTOMATION_DIR = Path(__file__).resolve().parent
ROOT = AUTOMATION_DIR.parent
for _p in (AUTOMATION_DIR, ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from social_card import create_card, create_vertical_frame, create_instagram_carousel
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "social_card.py was not found. Put social_card.py beside auto_publish.py in automation/."
    ) from exc

AUTOMATION_VERSION = "2026-09-26-premium-fb-ig-v4"
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
AUTO_DEFAULT_PLATFORMS = {"facebook", "instagram"}
TRUE_VALUES = {"yes", "y", "true", "1", "on"}
FALSE_VALUES = {"no", "n", "false", "0", "off", "disable", "disabled"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any):
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
            response = requests.request(method, url, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
            if not response.ok:
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:1500]
                raise RuntimeError(
                    f"{method} {url} -> HTTP {response.status_code}: {detail}"
                )
            return response.json() if response.text else {}
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("request failed")


def local_image_for(item: dict) -> Path | None:
    for raw in item.get("images") or []:
        if raw:
            path = ROOT / str(raw)
            if path.exists() and path.is_file():
                return path

    for ext in ("jpg", "jpeg", "png", "webp"):
        path = ROOT / "assets" / "news" / f"{item.get('id')}-1.{ext}"
        if path.exists():
            return path
    return None


def download_remote_image(item: dict, dest: Path) -> Path | None:
    for raw in item.get("image_urls") or []:
        if not raw or not raw.startswith(("http://", "https://")):
            continue
        match = re.search(r"/file/d/([^/]+)", raw)
        url = (
            f"https://drive.google.com/uc?export=download&id={match.group(1)}"
            if match else raw
        )
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "BanglasangbadSocialBot/1.0"},
            )
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(response.content)
            if dest.stat().st_size <= 1000:
                continue
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


def caption(item: dict) -> str:
    # Facebook/X/Threads: only the article URL, as requested.
    return news_url(str(item.get("id")))


def instagram_caption(item: dict) -> str:
    headline = clean_text(item.get("headline"))
    details = clean_text(item.get("details"))
    category = clean_text(item.get("category"))
    tag = (
        f"#{re.sub(r'[^\w\u0980-\u09ff]+', '', category)} #বাংলা_সংবাদ"
        if category else "#বাংলা_সংবাদ"
    )
    if details:
        return f"📰 {headline}\n\n{details}\n\n{tag}"
    return f"📰 {headline}\n\n{tag}"


def instagram_needs_carousel(item: dict) -> bool:
    return len(instagram_caption(item)) > 2200


def instagram_carousel_caption(item: dict) -> str:
    headline = clean_text(item.get("headline"))
    category = clean_text(item.get("category"))
    tag = (
        f"#{re.sub(r'[^\w\u0980-\u09ff]+', '', category)} #বাংলা_সংবাদ"
        if category else "#বাংলা_সংবাদ"
    )
    return f"📰 {headline}\n\n{tag}"


def meta_preflight(dry_run: bool = False) -> None:
    if dry_run:
        return

    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("META_PAGE_ID", "").strip()
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()

    if not token or not page_id:
        raise RuntimeError(
            "Meta preflight failed: META_PAGE_ID or META_PAGE_ACCESS_TOKEN is missing."
        )
    if not ig_id:
        raise RuntimeError(
            "Meta preflight failed: INSTAGRAM_BUSINESS_ACCOUNT_ID is missing."
        )

    page = request_json(
        "GET",
        f"{META_BASE}/{page_id}",
        params={
            "fields": "id,name,instagram_business_account",
            "access_token": token,
        },
    )
    if str(page.get("id", "")).strip() != page_id:
        raise RuntimeError(
            "Meta preflight failed: META_PAGE_ID does not match the Page returned by Meta."
        )

    linked_ig = ((page.get("instagram_business_account") or {}).get("id") or "").strip()
    if linked_ig and linked_ig != ig_id:
        raise RuntimeError(
            "Meta preflight failed: INSTAGRAM_BUSINESS_ACCOUNT_ID does not match "
            "the Instagram account linked to the Page."
        )

    ig = request_json(
        "GET",
        f"{META_BASE}/{ig_id}",
        params={
            "fields": "id,username",
            "access_token": token,
        },
    )
    if str(ig.get("id", "")).strip() != ig_id:
        raise RuntimeError("Meta preflight failed: Instagram account ID verification failed.")

    print(f"Meta preflight OK: Page {page_id}; Instagram {ig_id}.")


def facebook_publish(item, card_path, dry_run=False, prior_result=None):
    """Publish one Facebook Page photo post.

    IMPORTANT:
    - Uses the Page access token from GitHub Secrets.
    - Never publishes a comment.
    - Does not use the removed publish_actions permission in code.
    """
    message = caption(item)

    if dry_run:
        return {
            "dry_run": True,
            "message": message,
            "status": "dry_run",
        }

    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("META_PAGE_ID", "").strip()
    if not token or not page_id:
        raise RuntimeError("Missing META_PAGE_ID or META_PAGE_ACCESS_TOKEN")

    public_url = f"{SITE_BASE_URL}/social-media/{item['id']}.jpg"
    print(f"FACEBOOK START: article={item['id']}")

    try:
        result = request_json(
            "POST",
            f"{META_BASE}/{page_id}/photos",
            data={
                "url": public_url,
                "caption": message,
                "published": "true",
                "access_token": token,
            },
        )
    except Exception as exc:
        print(f"FACEBOOK FAILED: article={item['id']}: {exc}")
        raise

    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook photo publish returned no post id: {result}")

    print(f"FACEBOOK PUBLISH OK: article={item['id']}, post_id={post_id}")
    return {
        "id": post_id,
        "post_id": post_id,
        "status": "posted",
        "comment_created": False,
    }


def _wait_instagram_container(container_id: str, token: str, attempts: int = 36):
    last = {}
    for attempt in range(attempts):
        last = request_json(
            "GET",
            f"{META_BASE}/{container_id}",
            params={
                "fields": "status_code,status",
                "access_token": token,
            },
        )
        status = str(last.get("status_code") or "").upper()
        if status == "FINISHED":
            return last
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(
                f"Instagram media container {container_id} failed: {last}"
            )
        time.sleep(min(10, 2 + attempt // 3))
    raise RuntimeError(
        f"Instagram media container {container_id} did not reach FINISHED: {last}"
    )


def instagram_publish(
    item,
    image_path=None,
    carousel_paths=None,
    dry_run=False,
    prior_result=None,
):
    """Publish one Instagram image or a full-article carousel.

    The API returning an id is treated as success and explicitly returned with
    status='posted'. This fixes the old state bug where Instagram actually
    returned an id but the runner marked it as failed because status was absent.
    """
    use_carousel = instagram_needs_carousel(item)

    if dry_run:
        return {
            "dry_run": True,
            "mode": "carousel" if use_carousel else "single",
            "caption": (
                instagram_carousel_caption(item)
                if use_carousel else instagram_caption(item)
            ),
            "status": "dry_run",
        }

    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    if not token or not ig_id:
        raise RuntimeError(
            "Missing META_PAGE_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ACCOUNT_ID"
        )

    print(f"INSTAGRAM START: article={item['id']}")

    if use_carousel:
        paths = carousel_paths or []
        if len(paths) < 2:
            raise RuntimeError(
                "Instagram carousel was required but fewer than 2 images were generated."
            )

        child_ids = []
        for path in paths:
            public_url = (
                f"{SITE_BASE_URL}/social-media/instagram/"
                f"{item['id']}/{path.name}"
            )
            child = request_json(
                "POST",
                f"{META_BASE}/{ig_id}/media",
                data={
                    "image_url": public_url,
                    "is_carousel_item": "true",
                    "access_token": token,
                },
            )
            cid = child.get("id")
            if not cid:
                raise RuntimeError(
                    f"Instagram carousel child returned no id: {child}"
                )
            _wait_instagram_container(cid, token)
            child_ids.append(cid)

        parent = request_json(
            "POST",
            f"{META_BASE}/{ig_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": instagram_carousel_caption(item),
                "access_token": token,
            },
        )
        parent_id = parent.get("id")
        if not parent_id:
            raise RuntimeError(
                f"Instagram carousel parent returned no id: {parent}"
            )

        _wait_instagram_container(parent_id, token)

        published = request_json(
            "POST",
            f"{META_BASE}/{ig_id}/media_publish",
            data={
                "creation_id": parent_id,
                "access_token": token,
            },
        )
        published_id = published.get("id")
        if not published_id:
            raise RuntimeError(
                f"Instagram carousel publish returned no id: {published}"
            )

        print(
            f"INSTAGRAM PUBLISH OK: article={item['id']}, post_id={published_id}"
        )
        return {
            "id": published_id,
            "creation_id": parent_id,
            "mode": "carousel",
            "children": child_ids,
            "status": "posted",
        }

    if not image_path:
        raise RuntimeError("No Instagram image was generated")

    public_url = f"{SITE_BASE_URL}/social-media/instagram/{item['id']}.jpg"
    container = request_json(
        "POST",
        f"{META_BASE}/{ig_id}/media",
        data={
            "image_url": public_url,
            "caption": instagram_caption(item),
            "access_token": token,
        },
    )
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(
            f"Instagram media container returned no id: {container}"
        )

    _wait_instagram_container(creation_id, token)

    published = request_json(
        "POST",
        f"{META_BASE}/{ig_id}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": token,
        },
    )
    published_id = published.get("id")
    if not published_id:
        raise RuntimeError(
            f"Instagram publish returned no id: {published}"
        )

    print(
        f"INSTAGRAM PUBLISH OK: article={item['id']}, post_id={published_id}"
    )
    return {
        "id": published_id,
        "creation_id": creation_id,
        "mode": "single",
        "status": "posted",
    }


def x_publish(item, card_path, dry_run=False):
    # Kept disabled by default; existing X implementation can be restored later.
    if dry_run:
        return {"dry_run": True, "text": caption(item), "status": "dry_run"}
    raise RuntimeError("X publishing is disabled in this premium FB/Instagram build.")


def threads_publish(item, dry_run=False):
    if dry_run:
        return {"dry_run": True, "text": caption(item), "status": "dry_run"}
    raise RuntimeError("Threads publishing is disabled until explicitly enabled.")


def youtube_upload(item, video_path: Path, dry_run=False):
    if dry_run:
        return {"dry_run": True, "video": str(video_path), "status": "dry_run"}
    raise RuntimeError("YouTube publishing is disabled until explicitly enabled.")


def generate_video(item, image_path: Path, video_path: Path):
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
        "ffmpeg", "-y", "-loop", "1", "-i", str(frame),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-t", "12", "-r", "30", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(video_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        frame.unlink()
    except OSError:
        pass


def configure_git_identity():
    name = "github-actions[bot]"
    email = "41898282+github-actions[bot]@users.noreply.github.com"
    os.environ["GIT_AUTHOR_NAME"] = name
    os.environ["GIT_AUTHOR_EMAIL"] = email
    os.environ["GIT_COMMITTER_NAME"] = name
    os.environ["GIT_COMMITTER_EMAIL"] = email
    subprocess.run(["git", "config", "user.name", name], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", email], cwd=ROOT, check=True)


def verify_git_identity():
    configure_git_identity()
    name = subprocess.check_output(
        ["git", "config", "--get", "user.name"], cwd=ROOT, text=True
    ).strip()
    email = subprocess.check_output(
        ["git", "config", "--get", "user.email"], cwd=ROOT, text=True
    ).strip()
    if not name or not email:
        raise RuntimeError("Git identity verification failed")
    print(f"Git identity: {name} <{email}>")


def git_sync_and_push(max_attempts: int = 4):
    verify_git_identity()
    for attempt in range(1, max_attempts + 1):
        try:
            subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT, check=True)
            subprocess.run(["git", "rebase", "origin/main"], cwd=ROOT, check=True)
            subprocess.run(
                ["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True
            )
            return
        except subprocess.CalledProcessError:
            subprocess.run(
                ["git", "rebase", "--abort"],
                cwd=ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if attempt == max_attempts:
                raise
            time.sleep(min(10, 2 * attempt))


def publish_social_assets_to_pages(paths, news_id: str):
    rels = [Path(p).relative_to(ROOT).as_posix() for p in paths]
    subprocess.run(["git", "add", *rels], cwd=ROOT, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode != 0:
        configure_git_identity()
        subprocess.run(
            ["git", "commit", "-m", f"Create social assets for news {news_id}"],
            cwd=ROOT,
            check=True,
        )
        git_sync_and_push()


def commit_social_state():
    verify_git_identity()
    subprocess.run(
        ["git", "add", "social-publish-state.json", "social-publish-log.json"],
        cwd=ROOT,
        check=True,
    )
    if (ROOT / "social-media").is_dir():
        subprocess.run(["git", "add", "social-media"], cwd=ROOT, check=True)

    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode == 0:
        return False

    configure_git_identity()
    subprocess.run(
        ["git", "commit", "-m", "Update social auto-publish state"],
        cwd=ROOT,
        check=True,
    )
    git_sync_and_push()
    return True


def wait_public(url: str, attempts: int = 24) -> bool:
    for i in range(attempts):
        try:
            response = requests.get(
                url,
                timeout=15,
                allow_redirects=True,
                headers={"User-Agent": "BanglasangbadSocialBot/1.0"},
            )
            if response.status_code == 200 and len(response.content) > 100:
                return True
        except Exception:
            pass
        time.sleep(min(10, 2 + i))
    return False


def load_news():
    data = load_json(NEWS_FILE, {})
    return data.get("news") or []


def enabled(platform: str):
    return env_bool(f"ENABLE_{platform.upper()}", True)


def sheet_control(item: dict, key: str, default: bool = False) -> bool:
    raw = item.get(key)
    value = clean_text(raw).lower() if raw is not None else ""
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def sheet_yes(item: dict, key: str) -> bool:
    return sheet_control(
        item,
        key,
        default=(key in AUTO_DEFAULT_PLATFORMS or key == "publish"),
    )


def requested_platforms(item: dict) -> list[str]:
    if not sheet_control(item, "publish", default=True):
        return []

    requested = []
    for platform in PLATFORMS:
        default = platform in AUTO_DEFAULT_PLATFORMS
        if enabled(platform) and sheet_control(item, platform, default=default):
            requested.append(platform)
    return requested


def reconcile_state(state: dict):
    articles = state.setdefault("articles", {})
    for _, entry in articles.items():
        platforms = entry.setdefault("platforms", {})
        for _, pentry in platforms.items():
            if not isinstance(pentry, dict):
                continue
            if pentry.get("status") == "posted" and pentry.get("error"):
                pentry["status"] = "failed"
                pentry["updated_at"] = utc_now()

        requested = [
            p for p in PLATFORMS
            if platforms.get(p, {}).get("status") != "not_selected"
        ]
        if entry.get("status") == "posted_all" and any(
            platforms.get(p, {}).get("status") == "failed"
            for p in requested
        ):
            entry["status"] = "partial_failure"
            entry["updated_at"] = utc_now()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    state = load_json(
        STATE_FILE,
        {"version": 3, "articles": {}},
    )
    state.setdefault("version", 3)
    state.setdefault("articles", {})

    log = load_json(LOG_FILE, {"generated_at": None, "articles": {}})
    log.setdefault("articles", {})

    reconcile_state(state)
    meta_preflight(args.dry_run)

    news = sorted(
        load_news(),
        key=lambda x: int(str(x.get("id", "0")) or 0),
    )

    candidates = []

    for item in news:
        nid = str(item.get("id", "")).strip()
        if not nid or not clean_text(item.get("headline")):
            continue

        entry = state["articles"].setdefault(
            nid,
            {"status": "pending", "platforms": {}},
        )

        if entry.get("status") == "skipped_existing":
            continue

        requested = requested_platforms(item)

        entry["sheet_controls"] = {
            "publish": sheet_yes(item, "publish"),
            "facebook": sheet_yes(item, "facebook"),
            "instagram": sheet_yes(item, "instagram"),
            "x": sheet_yes(item, "x"),
            "threads": sheet_yes(item, "threads"),
            "youtube": sheet_yes(item, "youtube"),
        }

        if not requested:
            entry["status"] = (
                "waiting_sheet_publish"
                if not sheet_yes(item, "publish")
                else "no_social_platform_selected"
            )
            entry["updated_at"] = utc_now()
            continue

        if all(
            entry.get("platforms", {}).get(p, {}).get("status") == "posted"
            for p in requested
        ):
            entry["status"] = "posted_all"
            continue

        candidates.append(item)

    candidates = candidates[: max(1, args.limit)]

    for item in candidates:
        nid = str(item["id"])
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
                raise RuntimeError(f"No usable news image for article {nid}")

            card = CARD_DIR / f"{nid}.jpg"
            create_card(
                image_path,
                clean_text(item["headline"]),
                bangla_date(item.get("date", "")),
                ROOT / "logo.png",
                card,
                width=1200,
                height=1500,
                category=clean_text(item.get("category")),
            )

            ig_card = CARD_DIR / "instagram" / f"{nid}.jpg"
            create_card(
                image_path,
                clean_text(item["headline"]),
                bangla_date(item.get("date", "")),
                ROOT / "logo.png",
                ig_card,
                width=1080,
                height=1350,
                category=clean_text(item.get("category")),
            )

            carousel_paths = []
            if instagram_needs_carousel(item):
                carousel_dir = CARD_DIR / "instagram" / nid
                carousel_paths = create_instagram_carousel(
                    image_path,
                    clean_text(item.get("headline")),
                    clean_text(item.get("details")),
                    bangla_date(item.get("date", "")),
                    ROOT / "logo.png",
                    carousel_dir,
                    nid,
                    max_slides=10,
                )

            entry["social_card"] = f"social-media/{nid}.jpg"
            entry["instagram_image"] = f"social-media/instagram/{nid}.jpg"

            if carousel_paths:
                entry["instagram_carousel"] = [
                    Path(p).relative_to(ROOT).as_posix()
                    for p in carousel_paths
                ]
            else:
                entry.pop("instagram_carousel", None)

            entry["updated_at"] = utc_now()
            requested = requested_platforms(item)

            if not args.dry_run:
                article_url = news_url(nid)
                if not wait_public(article_url):
                    raise RuntimeError(
                        f"News article URL is not publicly reachable yet: {article_url}"
                    )

                assets = list(dict.fromkeys([card, ig_card] + carousel_paths))
                publish_social_assets_to_pages(assets, nid)

                urls = [
                    f"{SITE_BASE_URL}/social-media/{nid}.jpg",
                    f"{SITE_BASE_URL}/social-media/instagram/{nid}.jpg",
                ]
                for url in urls:
                    if not wait_public(url):
                        raise RuntimeError(
                            f"Social asset is not publicly reachable yet: {url}"
                        )

                for cp in carousel_paths:
                    url = (
                        f"{SITE_BASE_URL}/social-media/instagram/"
                        f"{nid}/{Path(cp).name}"
                    )
                    if not wait_public(url):
                        raise RuntimeError(
                            f"Instagram carousel asset is not publicly reachable yet: {url}"
                        )

            funcs = {
                "facebook": lambda pentry: facebook_publish(
                    item, card, args.dry_run, pentry.get("result")
                ),
                "instagram": lambda pentry: instagram_publish(
                    item, ig_card, carousel_paths, args.dry_run, pentry.get("result")
                ),
                "x": lambda pentry: x_publish(item, card, args.dry_run),
                "threads": lambda pentry: threads_publish(item, args.dry_run),
                "youtube": lambda pentry: youtube_upload(
                    item, VIDEO_DIR / f"{nid}.mp4", args.dry_run
                ),
            }

            for platform in PLATFORMS:
                if platform not in requested:
                    entry["platforms"].setdefault(
                        platform, {"status": "not_selected"}
                    )
                    continue

                pentry = entry["platforms"].setdefault(platform, {})
                if pentry.get("status") == "posted":
                    continue

                try:
                    result = funcs[platform](pentry)
                    success = (
                        args.dry_run
                        or (
                            isinstance(result, dict)
                            and result.get("status") == "posted"
                            and bool(result.get("id") or result.get("post_id"))
                        )
                    )

                    pentry.update({
                        "status": "dry_run" if args.dry_run else (
                            "posted" if success else "failed"
                        ),
                        "updated_at": utc_now(),
                        "result": result,
                    })

                    if not success:
                        pentry["error"] = (
                            result.get("error", "Platform publish did not complete successfully")
                            if isinstance(result, dict)
                            else "Platform publish did not complete successfully"
                        )

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
                entry["status"] = "dry_run" if args.dry_run else "posted_all"
            else:
                entry["status"] = "partial_failure"

        except Exception as exc:
            entry["status"] = "failed_preflight"
            entry["error"] = str(exc)
            entry["updated_at"] = utc_now()

        log["articles"][nid] = entry

    state["updated_at"] = utc_now()
    log["generated_at"] = utc_now()
    save_json(STATE_FILE, state)
    save_json(LOG_FILE, log)

    if not args.dry_run:
        commit_social_state()

    print(
        json.dumps(
            {
                "processed": [str(x["id"]) for x in candidates],
                "dry_run": args.dry_run,
                "total_news": len(news),
                "candidate_count": len(candidates),
                "latest_news_id": str(news[-1].get("id")) if news else None,
                "automation_version": AUTOMATION_VERSION,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
