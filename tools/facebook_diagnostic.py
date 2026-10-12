#!/usr/bin/env python3
"""Read-only diagnostics for Banglasangbad Facebook publishing.

This script never publishes, edits, comments, deletes, or prints access tokens.
Run from repository root: python tools/facebook_diagnostic.py [--news-id 25] [--post-id POST_ID]
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
SITE_BASE = os.getenv("SITE_BASE_URL", "https://abdurrazzak123.github.io/Banglasangbad").rstrip("/")
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
TIMEOUT = 20


def say(label: str, status: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")


def safe_http_check(url: str, label: str) -> bool:
    try:
        r = requests.get(url, timeout=TIMEOUT, allow_redirects=True, headers={"User-Agent": "Banglasangbad-Diagnostic/1.0"})
        content_type = r.headers.get("content-type", "unknown").split(";")[0]
        ok = r.status_code == 200
        extra = f"HTTP {r.status_code}, content-type={content_type}, final-host={urlparse(r.url).netloc}"
        if label == "Social image" and ok and not content_type.startswith("image/"):
            ok = False
            extra += " (expected an image response)"
        say(label, "OK" if ok else "FAIL", extra)
        return ok
    except requests.RequestException as exc:
        say(label, "FAIL", f"request error: {type(exc).__name__}: {exc}")
        return False


def graph_get(path: str, token: str, params: dict | None = None) -> tuple[dict | None, str | None]:
    q = dict(params or {})
    q["access_token"] = token
    try:
        r = requests.get(f"{GRAPH_BASE}/{path.lstrip('/')}", params=q, timeout=TIMEOUT)
        try:
            data = r.json()
        except ValueError:
            return None, f"HTTP {r.status_code}: non-JSON response"
        if not r.ok or "error" in data:
            err = data.get("error", {})
            # Only print Meta's diagnostic message/code, never request URL/query string/token.
            return None, f"HTTP {r.status_code}; Meta code={err.get('code', 'n/a')}; subcode={err.get('error_subcode', 'n/a')}; message={err.get('message', 'unknown error')}"
        return data, None
    except requests.RequestException as exc:
        return None, f"request error: {type(exc).__name__}: {exc}"



def public_visibility_check(url: str, label: str = "Public visibility (logged out)") -> bool | None:
    """Fetch a Facebook permalink without any access token. This is a useful signal, not a perfect proof.

    Facebook may serve login walls or bot-protection pages to automated requests even for public posts.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = host == "facebook.com" or host.endswith(".facebook.com")
    if parsed.scheme not in ("http", "https") or not allowed:
        say(label, "FAIL", "refused URL: provide a facebook.com permalink; no token will be sent to this URL")
        return False
    try:
        # Deliberately unauthenticated: do not attach cookies or access tokens.
        r = requests.get(
            url, timeout=TIMEOUT, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
                     "Accept": "text/html,application/xhtml+xml"},
        )
        final = urlparse(r.url)
        final_host = (final.hostname or "").lower()
        if not (final_host == "facebook.com" or final_host.endswith(".facebook.com")):
            say(label, "WARN", f"redirected outside Facebook to {final_host or 'unknown host'}; public visibility not confirmed")
            return None
        body = r.text[:1_000_000].lower() if "text" in r.headers.get("content-type", "") or "html" in r.headers.get("content-type", "") else ""
        login_markers = ("log in or sign up", "log into facebook", "you must log in", "login_form", "login.php", "content isn't available right now", "this content isn't available")
        if r.status_code in (401, 403, 404, 410):
            say(label, "WARN", f"anonymous HTTP {r.status_code}; post may be restricted/unavailable OR Facebook may block automated checks; not conclusive")
            return None
        if r.status_code >= 400:
            say(label, "WARN", f"anonymous HTTP {r.status_code}; Facebook may block automated requests; not conclusive")
            return None
        if any(marker in body for marker in login_markers) or "/login" in final.path.lower() or "/checkpoint" in final.path.lower():
            say(label, "WARN", f"anonymous request landed on a login/interstitial page (HTTP {r.status_code}); public visibility NOT confirmed")
            return None
        # Facebook's HTML response can be incomplete for crawlers; HTTP 200 alone is not proof.
        has_fb_page_signals = any(marker in body for marker in ("og:title", "story_fbid", "post_id", "permalink_url", "data-ft"))
        if r.status_code == 200 and has_fb_page_signals:
            say(label, "INFO", f"anonymous request fetched a Facebook HTML page (HTTP 200, final-host={final_host}); promising, but cannot prove ordinary users can view the post")
            return True
        say(label, "WARN", f"anonymous HTTP {r.status_code}, but response did not clearly identify a post; public visibility remains inconclusive")
        return None
    except requests.RequestException as exc:
        say(label, "WARN", f"anonymous request failed ({type(exc).__name__}); Facebook may block automated checks; not conclusive")
        return None


def inspect_log() -> None:
    path = ROOT / "social-publish-log.json"
    if not path.exists():
        say("Publish log", "WARN", "social-publish-log.json not found")
        return
    try:
        log = json.loads(path.read_text(encoding="utf-8"))
        articles = log.get("articles", {}) if isinstance(log, dict) else {}
        rows = []
        for nid, entry in articles.items():
            fb = (entry.get("platforms") or {}).get("facebook") or {}
            if fb:
                rows.append((str(fb.get("updated_at") or entry.get("updated_at") or ""), str(nid), fb))
        rows.sort(reverse=True)
        say("Publish log", "OK", f"{len(rows)} article(s) have a Facebook log entry")
        for _, nid, fb in rows[:8]:
            status = str(fb.get("status", "unknown"))
            result = fb.get("result") if isinstance(fb.get("result"), dict) else {}
            err = fb.get("error") or result.get("error") or result.get("comment_error")
            if status == "posted" and err:
                say(f"Log article {nid}", "WARN", f"status says posted BUT error field exists: {str(err)[:260]}")
            elif status == "posted" and result.get("id") and not result.get("post_id"):
                say(f"Log article {nid}", "WARN", "posted status has an id but no explicit post_id; verify whether it is a photo ID or post ID")
            else:
                say(f"Log article {nid}", "INFO", f"status={status}; id={result.get('id') or result.get('post_id') or 'none'}" + (f"; error={str(err)[:220]}" if err else ""))
    except Exception as exc:
        say("Publish log", "FAIL", f"could not parse JSON: {type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Facebook/site diagnostics; does not publish anything.")
    parser.add_argument("--news-id", help="Check this article page and social image, e.g. 25")
    parser.add_argument("--post-id", help="Optional existing Facebook post ID (not a news article ID)")
    parser.add_argument("--post-url", help="Optional Facebook permalink to test anonymously (no token/cookies sent)")
    args = parser.parse_args()

    print("Banglasangbad Facebook Auto-Publish Diagnostic (READ-ONLY)")
    print(f"Graph API version: {GRAPH_VERSION}")
    print(f"Website base: {SITE_BASE}")
    print("Safety: no publishing, no commenting, no changes; access token is never printed.\n")

    site_ok = safe_http_check(SITE_BASE + "/", "Website home")
    if args.news_id:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.news_id):
            say("News ID", "FAIL", "use only letters, numbers, underscore, or hyphen")
            return 2
        safe_http_check(f"{SITE_BASE}/news/{args.news_id}.html", f"News page {args.news_id}")
        safe_http_check(f"{SITE_BASE}/social-media/{args.news_id}.jpg", "Social image")
    else:
        say("Article/image URLs", "SKIP", "pass --news-id N to test the exact article and image")

    page_id = os.getenv("META_PAGE_ID", "").strip()
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    if not page_id:
        say("META_PAGE_ID", "FAIL", "GitHub secret/environment variable is missing")
    else:
        say("META_PAGE_ID", "OK", f"configured (value hidden except final 4 digits: …{page_id[-4:]})")
    if not token:
        say("META_PAGE_ACCESS_TOKEN", "FAIL", "GitHub secret/environment variable is missing")
    else:
        say("META_PAGE_ACCESS_TOKEN", "OK", "configured; secret value hidden")

    if page_id and token:
        page, err = graph_get(page_id, token, {"fields": "id,name,link"})
        if err:
            say("Meta Page token / Page ID validation", "FAIL", err)
        else:
            returned_id = str(page.get("id", ""))
            say("Meta Page token / Page ID validation", "OK" if returned_id == page_id else "FAIL",
                f"Meta returned page name={page.get('name', 'unknown')!r}; returned ID matches configured ID={returned_id == page_id}; page link={page.get('link', 'not returned')}")
        me, me_err = graph_get("me", token, {"fields": "id,name"})
        if me_err:
            say("Token identity check", "WARN", me_err)
        else:
            say("Token identity check", "INFO", f"Meta identifies token as id={me.get('id', 'unknown')}, name={me.get('name', 'unknown')!r}")
        perms, perms_err = graph_get("me/permissions", token)
        if perms_err:
            say("Permission inspection", "WARN", perms_err)
        else:
            values = perms.get("data", [])
            useful = {str(x.get("permission")): str(x.get("status")) for x in values if isinstance(x, dict)}
            expected = ["pages_show_list", "pages_read_engagement", "pages_manage_posts"]
            say("Permission inspection", "OK", "; ".join(f"{p}={useful.get(p, 'not returned')}" for p in expected))
    else:
        say("Meta API checks", "SKIP", "both META_PAGE_ID and META_PAGE_ACCESS_TOKEN are required")

    permalink_to_test = args.post_url.strip() if args.post_url else ""
    if args.post_id:
        if not token:
            say("Existing Facebook post metadata", "SKIP", "token is missing; cannot inspect post metadata")
        else:
            post, err = graph_get(args.post_id, token, {"fields": "id,message,permalink_url,is_published,is_hidden,privacy,timeline_visibility,created_time"})
            if err:
                say("Existing Facebook post metadata", "WARN", err)
            else:
                privacy = post.get("privacy")
                if isinstance(privacy, dict):
                    privacy = privacy.get("value", privacy.get("description", "returned"))
                say("Existing Facebook post metadata", "OK",
                    f"id={post.get('id')}; is_published={post.get('is_published', 'not returned')}; is_hidden={post.get('is_hidden', 'not returned')}; timeline_visibility={post.get('timeline_visibility', 'not returned')}; privacy={privacy or 'not returned'}; created_time={post.get('created_time', 'not returned')}")
                if post.get("permalink_url") and not permalink_to_test:
                    permalink_to_test = str(post["permalink_url"])
    if permalink_to_test:
        public_visibility_check(permalink_to_test)
    else:
        say("Public visibility (logged out)", "SKIP", "provide --post-url OR a valid --post-id whose API response includes permalink_url")

    inspect_log()
    print("\nHow to read this report:")
    print("- Website/image FAIL: investigate GitHub Pages path, deployment, or image file first.")
    print("- Meta Page validation FAIL: investigate Page ID, token expiry, token-to-Page association, and Page permissions.")
    print("- Public visibility check: tests the Facebook permalink without a token and inspects post metadata when a post ID is supplied. Facebook may block automated requests, so INFO/WARN is a signal—not absolute proof; verify in a different account/browser if inconclusive.")
    print("- If you only have a share link, use it as --post-url. If you also provide --post-id, the report checks API metadata and the public permalink in the same run.")
    print("- Old log entries may be stale. A log marked posted alongside an error is inconsistent and should not be treated as proof of a successful new publish.")
    return 0 if site_ok else 1

if __name__ == "__main__":
    sys.exit(main())
