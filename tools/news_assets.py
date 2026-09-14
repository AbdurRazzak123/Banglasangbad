# tools/news_assets.py
# ============================================================
# Bangla Sangbad
# News Image / Asset Downloader
# ============================================================

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

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
        value,
    )

    value = re.sub(
        r"-+",
        "-",
        value,
    )

    value = value.strip("-_")

    return value or "news"


def image_extension(
    url: str,
    content_type: str = "",
) -> str:

    try:
        suffix = Path(
            urlparse(url).path
        ).suffix.lower()
    except Exception:
        suffix = ""

    if suffix in IMAGE_EXTENSIONS:
        if suffix == ".jpeg":
            return ".jpg"

        return suffix

    mime = (
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
        mime,
        ".jpg",
    )


def make_asset_filename(
    news_id: str,
    image_number: int,
    extension: str,
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
    destination: Path,
    session: requests.Session | None = None,
) -> bool:

    url = clean_text(url)

    if not url:
        return False

    if not url.startswith(
        ("http://", "https://")
    ):
        return False

    session = (
        session
        or requests.Session()
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_name(
        destination.name + ".tmp"
    )

    try:

        response = session.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "image/avif,"
                    "image/webp,"
                    "image/apng,"
                    "image/*,"
                    "*/*;q=0.8"
                ),
            },
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

        if (
            content_type
            and not content_type.startswith(
                "image/"
            )
        ):
            response.close()
            return False

        with open(
            temporary,
            "wb",
        ) as output:

            for chunk in response.iter_content(
                chunk_size=1024 * 64
            ):

                if chunk:
                    output.write(chunk)

        response.close()

        if (
            not temporary.exists()
            or temporary.stat().st_size == 0
        ):
            return False

        temporary.replace(
            destination
        )

        return True

    except Exception:

        try:
            if temporary.exists():
                temporary.unlink()
        except Exception:
            pass

        return False


def get_remote_image(
    url: str,
    news_id: str,
    image_number: int,
    assets_dir: Path,
    session: requests.Session | None = None,
) -> str:

    url = clean_text(url)

    if not url:
        return ""

    if not url.startswith(
        ("http://", "https://")
    ):
        return ""

    session = (
        session
        or requests.Session()
    )

    assets_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Try HEAD first to detect extension
    # --------------------------------------------------------

    content_type = ""

    try:

        response = session.head(
            url,
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=15,
            allow_redirects=True,
        )

        content_type = (
            response.headers
            .get("content-type", "")
        )

        response.close()

    except Exception:
        content_type = ""

    extension = image_extension(
        url,
        content_type,
    )

    filename = make_asset_filename(
        news_id,
        image_number,
        extension,
    )

    destination = (
        assets_dir / filename
    )

    # --------------------------------------------------------
    # Existing asset = do not download again
    # --------------------------------------------------------

    if (
        destination.exists()
        and destination.stat().st_size > 0
    ):

        return (
            f"assets/news/{filename}"
        )

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    success = download_image(
        url,
        destination,
        session,
    )

    if success:

        return (
            f"assets/news/{filename}"
        )

    return ""


def process_news_images(
    news_id: str,
    image_urls: list[str],
    assets_dir: Path,
    session: requests.Session | None = None,
) -> list[str]:

    """
    Supports:

        Image-1
        Image-2
        Image-3

    Example result:

        [
            "assets/news/32-1.jpg",
            "assets/news/32-2.jpg",
            "assets/news/32-3.jpg"
        ]

    Missing images remain empty strings.
    """

    assets_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    session = (
        session
        or requests.Session()
    )

    result = []

    for number in range(1, 4):

        url = ""

        if len(image_urls) >= number:
            url = clean_text(
                image_urls[number - 1]
            )

        if not url:

            result.append("")

            continue

        path = get_remote_image(
            url=url,
            news_id=news_id,
            image_number=number,
            assets_dir=assets_dir,
            session=session,
        )

        result.append(path)

    return result


def is_image_url(
    value: str,
) -> bool:

    value = clean_text(value)

    return value.startswith(
        ("http://", "https://")
    )
