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
for p in (AUTOMATION_DIR, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from social_card import create_card

AUTOMATION_VERSION = "2026-09-26-fb-ig-single-image-v5"
STATE_FILE = ROOT / "social-publish-state.json"
LOG_FILE = ROOT / "social-publish-log.json"
NEWS_FILE = ROOT / "news-data.json"
CARD_DIR = ROOT / "social-media"

META_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
META_BASE = f"https://graph.facebook.com/{META_VERSION}"
SITE_BASE_URL = os.getenv(
    "SITE_BASE_URL", "https://abdurrazzak123.github.io/Banglasangbad"
).rstrip("/")

PLATFORMS = ("facebook", "instagram")
TRUE_VALUES = {"yes", "y", "true", "1", "on", "enable", "enabled"}
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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
            try:
                data = r.json()
            except Exception:
                data = {"raw": r.text[:1500]}
            if not r.ok:
                raise RuntimeError(
                    f"{method} {url} -> HTTP {r.status_code}: {data}"
                )
            return data
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("request failed")


def local_image_for(item: dict) -> Path | None:
    for raw in item.get("images") or []:
        if raw:
            p = ROOT / str(raw)
            if p.exists() and p.is_file():
                return p
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = ROOT / "assets" / "news" / f"{item.get('id')}-1.{ext}"
        if p.exists():
            return p
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
            r = requests.get(
                url, timeout=30,
                headers={"User-Agent": "BanglasangbadSocialBot/1.0"},
            )
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            if dest.stat().st_size <= 1000:
                continue
            with Image.open(dest) as probe:
                probe.verify()
            return dest
        except Exception:
            try:
                if dest.exists():
                    dest.unlink()
            except OSError:
                pass
    return None


def caption(item: dict) -> str:
    return news_url(str(item.get("id")))


def instagram_caption(item: dict) -> str:
    headline = clean_text(item.get("headline"))
    details = clean_text(item.get("details"))
    category = clean_text(item.get("category"))
    tag = (
        f"#{re.sub(r'[^\\w\\u0980-\\u09ff]+', '', category)} #বাংলা_সংবাদ"
        if category else "#বাংলা_সংবাদ"
    )
    # Keep the caption comfortably below common platform limits.
    text = f"📰 {headline}"
    if details:
        text += f"\n\n{details}"
    text += f"\n\n{tag}"
    return text[:2100]


def facebook_publish(item: dict, card_path: Path, dry_run: bool = False):
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("META_PAGE_ID", "").strip()
    message = caption(item)

    if dry_run:
        return {"status": "dry_run", "message": message}

    if not token or not page_id:
        raise RuntimeError("Missing META_PAGE_ID or META_PAGE_ACCESS_TOKEN")

    # Current code deliberately uses only the Page access token.
    # No publish_actions permission is requested or referenced here.
    public_url = f"{SITE_BASE_URL}/social-media/{item['id']}.jpg"

    print(f"FACEBOOK START: article={item['id']}")
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

    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook returned no post id: {result}")

    print(f"FACEBOOK PUBLISH OK: article={item['id']}, post_id={post_id}")
    return {
        "status": "posted",
        "id": post_id,
        "post_id": post_id,
        "comment_created": False,
    }


def wait_instagram_container(container_id: str, token: str, attempts: int = 36):
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


def instagram_publish(item: dict, image_path: Path | None, dry_run: bool = False):
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()

    if dry_run:
        return {
            "status": "dry_run",
            "mode": "single",
            "caption": instagram_caption(item),
        }

    if not token or not ig_id:
        raise RuntimeError(
            "Missing META_PAGE_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ACCOUNT_ID"
        )
    if not image_path:
        raise RuntimeError("No Instagram image was generated")

    public_url = f"{SITE_BASE_URL}/social-media/instagram/{item['id']}.jpg"

    print(f"INSTAGRAM START: article={item['id']}")
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
        raise RuntimeError(f"Instagram media container returned no id: {container}")

    wait_instagram_container(creation_id, token)

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
        raise RuntimeError(f"Instagram publish returned no id: {published}")

    print(f"INSTAGRAM PUBLISH OK: article={item['id']}, post_id={published_id}")
    return {
        "status": "posted",
        "id": published_id,
        "creation_id": creation_id,
        "mode": "single",
    }


def load_news():
    data = load_json(NEWS_FILE, {})
    return data.get("news") or []


def sheet_control(item: dict, key: str, default: bool) -> bool:
    raw = item.get(key)
    value = clean_text(raw).lower() if raw is not None else ""
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def requested_platforms(item: dict) -> list[str]:
    if not sheet_control(item, "publish", True):
        return []
    out = []
    for p in PLATFORMS:
        env_default = env_bool(f"ENABLE_{p.upper()}", True)
        if env_default and sheet_control(item, p, True):
            out.append(p)
    return out


def reconcile_state(state: dict):
    # Never convert a successful post to failed just because an old error
    # field remained in the JSON. A posted status is authoritative.
    for entry in state.setdefault("articles", {}).values():
        platforms = entry.setdefault("platforms", {})
        for pentry in platforms.values():
            if not isinstance(pentry, dict):
                continue
            if pentry.get("status") == "posted":
                pentry.pop("error", None)
        requested = [
            p for p in PLATFORMS
            if platforms.get(p, {}).get("status") != "not_selected"
        ]
        if requested and all(
            platforms.get(p, {}).get("status") == "posted"
            for p in requested
        ):
            entry["status"] = "posted_all"
        elif any(
            platforms.get(p, {}).get("status") == "failed"
            for p in requested
        ):
            entry["status"] = "partial_failure"


def configure_git_identity():
    name = "github-actions[bot]"
    email = "41898282+github-actions[bot]@users.noreply.github.com"
    subprocess.run(["git", "config", "user.name", name], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", email], cwd=ROOT, check=True)


def git_sync_and_push(max_attempts: int = 4):
    configure_git_identity()
    for attempt in range(1, max_attempts + 1):
        try:
            subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT, check=True)
            subprocess.run(["git", "rebase", "origin/main"], cwd=ROOT, check=True)
            subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True)
            return
        except subprocess.CalledProcessError:
            subprocess.run(
                ["git", "rebase", "--abort"], cwd=ROOT, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if attempt == max_attempts:
                raise
            time.sleep(min(10, 2 * attempt))


def publish_social_assets_to_pages(paths, news_id: str):
    rels = [Path(p).relative_to(ROOT).as_posix() for p in paths]
    subprocess.run(["git", "add", *rels], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        configure_git_identity()
        subprocess.run(
            ["git", "commit", "-m", f"Create social assets for news {news_id}"],
            cwd=ROOT, check=True
        )
        git_sync_and_push()


def commit_social_state():
    configure_git_identity()
    subprocess.run(
        ["git", "add", "social-publish-state.json", "social-publish-log.json"],
        cwd=ROOT, check=True
    )
    if (ROOT / "social-media").is_dir():
        subprocess.run(["git", "add", "social-media"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return False
    subprocess.run(
        ["git", "commit", "-m", "Update social auto-publish state"],
        cwd=ROOT, check=True
    )
    git_sync_and_push()
    return True


def wait_public(url: str, attempts: int = 24) -> bool:
    for i in range(attempts):
        try:
            r = requests.get(
                url, timeout=15, allow_redirects=True,
                headers={"User-Agent": "BanglasangbadSocialBot/1.0"}
            )
            if r.status_code == 200 and len(r.content) > 100:
                return True
        except Exception:
            pass
        time.sleep(min(10, 2 + i))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    state = load_json(STATE_FILE, {"version": 5, "articles": {}})
    state.setdefault("version", 5)
    state.setdefault("articles", {})
    log = load_json(LOG_FILE, {"generated_at": None, "articles": {}})
    log.setdefault("articles", {})

    reconcile_state(state)

    if not args.dry_run:
        # Basic credential presence check. The workflow runs the full preflight too.
        if not os.getenv("META_PAGE_ACCESS_TOKEN", "").strip():
            raise RuntimeError("META_PAGE_ACCESS_TOKEN is missing")
        if not os.getenv("META_PAGE_ID", "").strip():
            raise RuntimeError("META_PAGE_ID is missing")
        if not os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip():
            raise RuntimeError("INSTAGRAM_BUSINESS_ACCOUNT_ID is missing")

    news = sorted(
        load_news(),
        key=lambda x: int(str(x.get("id", "0")) or 0)
    )

    candidates = []
    for item in news:
        nid = str(item.get("id", "")).strip()
        if not nid or not clean_text(item.get("headline")):
            continue

        entry = state["articles"].setdefault(
            nid, {"status": "pending", "platforms": {}}
        )
        requested = requested_platforms(item)

        entry["sheet_controls"] = {
            "publish": sheet_control(item, "publish", True),
            "facebook": sheet_control(item, "facebook", True),
            "instagram": sheet_control(item, "instagram", True),
        }

        if not requested:
            entry["status"] = "waiting_sheet_publish"
            entry["updated_at"] = utc_now()
            continue

        if all(
            entry["platforms"].get(p, {}).get("status") == "posted"
            for p in requested
        ):
            entry["status"] = "posted_all"
            continue

        candidates.append(item)

    candidates = candidates[:max(1, args.limit)]

    for item in candidates:
        nid = str(item["id"])
        entry = state["articles"].setdefault(
            nid, {"status": "pending", "platforms": {}}
        )
        entry["last_attempt_at"] = utc_now()

        try:
            image_path = local_image_for(item)
            if not image_path:
                image_path = download_remote_image(
                    item, ROOT / ".social-tmp" / f"{nid}.jpg"
                )
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

            entry["social_card"] = f"social-media/{nid}.jpg"
            entry["instagram_image"] = f"social-media/instagram/{nid}.jpg"
            entry["updated_at"] = utc_now()

            requested = requested_platforms(item)

            if not args.dry_run:
                article_url = news_url(nid)
                if not wait_public(article_url):
                    raise RuntimeError(
                        f"News article URL is not publicly reachable: {article_url}"
                    )

                assets = [card, ig_card]
                publish_social_assets_to_pages(assets, nid)

                for url in (
                    f"{SITE_BASE_URL}/social-media/{nid}.jpg",
                    f"{SITE_BASE_URL}/social-media/instagram/{nid}.jpg",
                ):
                    if not wait_public(url):
                        raise RuntimeError(
                            f"Social asset is not publicly reachable: {url}"
                        )

            funcs = {
                "facebook": lambda: facebook_publish(item, card, args.dry_run),
                "instagram": lambda: instagram_publish(item, ig_card, args.dry_run),
            }

            for platform in PLATFORMS:
                if platform not in requested:
                    entry["platforms"].setdefault(platform, {"status": "not_selected"})
                    continue

                pentry = entry["platforms"].setdefault(platform, {})
                if pentry.get("status") == "posted":
                    pentry.pop("error", None)
                    continue

                try:
                    result = funcs[platform]()
                    success = args.dry_run or (
                        isinstance(result, dict)
                        and result.get("status") == "posted"
                        and bool(result.get("id") or result.get("post_id"))
                    )

                    if success:
                        pentry.clear()
                        pentry.update({
                            "status": "dry_run" if args.dry_run else "posted",
                            "updated_at": utc_now(),
                            "result": result,
                        })
                    else:
                        pentry.update({
                            "status": "failed",
                            "updated_at": utc_now(),
                            "result": result,
                            "error": "Platform publish did not complete successfully",
                        })
                except Exception as exc:
                    pentry.update({
                        "status": "failed",
                        "updated_at": utc_now(),
                        "error": str(exc),
                    })

            if requested and all(
                entry["platforms"].get(p, {}).get("status") in {"posted", "dry_run"}
                for p in requested
            ):
                entry["status"] = "dry_run" if args.dry_run else "posted_all"
                entry.pop("error", None)
            else:
                entry["status"] = "partial_failure"

        except Exception as exc:
            entry["status"] = "failed_preflight"
            entry["error"] = str(exc)
            entry["updated_at"] = utc_now()

        log["articles"][nid] = json.loads(json.dumps(entry, ensure_ascii=False))

    state["updated_at"] = utc_now()
    log["generated_at"] = utc_now()
    save_json(STATE_FILE, state)
    save_json(LOG_FILE, log)

    if not args.dry_run:
        commit_social_state()

    print(json.dumps({
        "processed": [str(x["id"]) for x in candidates],
        "dry_run": args.dry_run,
        "total_news": len(news),
        "candidate_count": len(candidates),
        "latest_news_id": str(news[-1].get("id")) if news else None,
        "automation_version": AUTOMATION_VERSION,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
