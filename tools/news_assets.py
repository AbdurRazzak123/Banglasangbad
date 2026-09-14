from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests


USER_AGENT = (
    "Mozilla/5.0 (compatible; BanglaSangbad-NewsBot/1.0; "
    "+https://abdurrazzak123.github.io/Banglasangbad/)"
)

TIMEOUT = 30

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".avif",
}


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_id(value) -> str:
    value = clean_text(value)

    value = re.sub(
        r"[^A-Za-z0-9_-]+",
        "-",
        value
    )

    value = re.sub(
        r"-+",
        "-",
        value
    )

    return value.strip("-_") or "news"


def convert_google_drive_url(url: str) -> str:

    url = clean_text(url)

    if "drive.google.com" not in url:
        return url

    match = re.search(
        r"/file/d/([^/]+)",
        url
    )

    if match:
        file_id = match.group(1)

        return (
            "https://drive.google.com/uc"
            "?export=download&id="
            + file_id
        )

    parsed = urlparse(url)

    query = parse_qs(
        parsed.query
    )

    if "id" in query and query["id"]:

        return (
            "https://drive.google.com/uc"
            "?export=download&id="
            + query["id"][0]
        )

    return url


def detect_extension(
    url: str,
    content_type: str = ""
) -> str:

    suffix = Path(
        urlparse(url).path
    ).suffix.lower()

    if suffix in IMAGE_EXTENSIONS:

        if suffix == ".jpeg":
            return ".jpg"

        return suffix

    content_type = (
        content_type
        .lower()
        .split(";")[0]
        .strip()
    )

    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }

    return mapping.get(
        content_type,
        ".jpg"
    )


def make_filename(
    news_id: str,
    image_number: int,
    extension: str
) -> str:

    news_id = safe_id(news_id)

    extension = extension.lower()

    if not extension.startswith("."):
        extension = "." + extension

    return (
        f"{news_id}-{image_number}"
        f"{extension}"
    )


def download_image(
    url: str,
    news_id: str,
    image_number: int,
    assets_dir: Path,
    session=None,
) -> str:

    url = clean_text(url)

    if not url:
        return ""

    if not url.startswith(
        ("http://", "https://")
    ):
        return ""

    url = convert_google_drive_url(url)

    assets_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    if session is None:
        session = requests.Session()

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "image/avif,image/webp,"
            "image/apng,image/svg+xml,"
            "image/*,*/*;q=0.8"
        ),
    }

    response = None
    temporary = None

    try:

        response = session.get(
            url,
            headers=headers,
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=True,
        )

        response.raise_for_status()

        content_type = (
            response.headers
            .get("content-type", "")
            .lower()
        )

        extension = detect_extension(
            url,
            content_type
        )

        filename = make_filename(
            news_id,
            image_number,
            extension
        )

        destination = (
            assets_dir / filename
        )

        if (
            destination.exists()
            and destination.stat().st_size > 0
        ):

            response.close()

            return (
                f"assets/news/{filename}"
            )

        temporary = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        with open(
            temporary,
            "wb"
        ) as output:

            for chunk in response.iter_content(
                chunk_size=65536
            ):

                if chunk:
                    output.write(chunk)

        response.close()

        if (
            not temporary.exists()
            or temporary.stat().st_size == 0
        ):

            if temporary.exists():
                temporary.unlink()

            return ""

        temporary.replace(
            destination
        )

        return (
            f"assets/news/{filename}"
        )

    except Exception:

        if response is not None:

            try:
                response.close()
            except Exception:
                pass

        if (
            temporary is not None
            and temporary.exists()
        ):

            try:
                temporary.unlink()
            except Exception:
                pass

        return ""


def process_news_images(
    news_id: str,
    image_urls: list[str],
    assets_dir: Path,
    session=None,
) -> list[str]:

    assets_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    if session is None:
        session = requests.Session()

    result = []

    for index in range(3):

        url = ""

        if index < len(image_urls):
            url = clean_text(
                image_urls[index]
            )

        if not url:

            result.append("")

            continue

        path = download_image(
            url=url,
            news_id=news_id,
            image_number=index + 1,
            assets_dir=assets_dir,
            session=session,
        )

        result.append(path)

    return result
