from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://abdurrazzak123.github.io/Banglasangbad/"
SITEMAP = ROOT / "sitemap.xml"
NEWS_SITEMAP = ROOT / "news-sitemap.xml"
ROBOTS = ROOT / "robots.txt"


def fail(message: str) -> None:
    raise SystemExit("SEO VALIDATION FAILED: " + message)


def parse_xml(path: Path):
    if not path.is_file():
        fail(f"missing {path.name}")
    raw = path.read_bytes()
    if not raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'):
        fail(f"{path.name} does not start with the expected XML declaration")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        fail(f"{path.name} is not valid XML: {exc}")


def check_urlset(root, path: Path):
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("sm:url", ns)
    seen = set()
    for item in urls:
        loc = item.find("sm:loc", ns)
        if loc is None or not (loc.text or "").strip():
            fail(f"{path.name} contains a URL entry without <loc>")
        url = loc.text.strip()
        if url in seen:
            fail(f"{path.name} contains duplicate URL: {url}")
        seen.add(url)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "abdurrazzak123.github.io":
            fail(f"{path.name} contains a non-canonical host/scheme URL: {url}")
        if not url.startswith(BASE_URL):
            fail(f"{path.name} contains a URL outside the site: {url}")
    return urls


def main():
    sitemap_root = parse_xml(SITEMAP)
    news_root = parse_xml(NEWS_SITEMAP)
    sitemap_urls = check_urlset(sitemap_root, SITEMAP)
    news_urls = check_urlset(news_root, NEWS_SITEMAP)

    robots = ROBOTS.read_text(encoding="utf-8", errors="replace")
    for expected in ("Sitemap: " + BASE_URL + "sitemap.xml",
                     "Sitemap: " + BASE_URL + "news-sitemap.xml"):
        if expected not in robots:
            fail(f"robots.txt is missing: {expected}")

    # Every sitemap URL should point to an existing local HTML page.
    for item in sitemap_urls:
        url = item.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text.strip()
        path = urlparse(url).path.removeprefix("/Banglasangbad/") or "index.html"
        local = ROOT / path
        if not local.is_file():
            fail(f"sitemap URL has no local file: {url}")

        soup = BeautifulSoup(local.read_text(encoding="utf-8", errors="replace"), "html.parser")
        robots_meta = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        robots_content = (robots_meta.get("content", "") if robots_meta else "").lower()
        if "noindex" in robots_content:
            fail(f"noindex page was included in sitemap: {url}")

    print(f"SEO validation OK: {len(sitemap_urls)} sitemap URLs; {len(news_urls)} News sitemap URLs.")


if __name__ == "__main__":
    main()
