from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests


USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; BanglaSangbad/1.0; "
    "+https://abdurrazzak123.github.io/Banglasangbad/)"
)

TIMEOUT = 45

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".avif",
}


def clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_id(value) -> str:
    value = clean(value)

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


def get_drive_id(url: str) -> str:
    url = clean(url)

    if not url:
        return ""

    if "drive.google.com" not in url.lower():
        return ""

    match = re.search(
        r"/file/d/([^/?#]+)",
        url,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    match = re.search(
        r"/d/([^/?#]+)",
        url,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        if query.get("id"):
            return query["id"][0]

    except Exception:
        pass

    return ""


def drive_urls(url: str) -> list[str]:
    file_id = get_drive_id(url)

    if not file_id:
        return []

    return [
        (
            "https://drive.google.com/thumbnail"
            "?id="
            + file_id
            + "&sz=w2000"
        ),
        (
            "https://drive.google.com/uc"
            "?export=view&id="
            + file_id
        ),
        (
            "https://drive.usercontent.google.com/download"
            "?id="
            + file_id
            + "&export=download"
        ),
        (
            "https://drive.google.com/uc"
            "?export=download&id="
            + file_id
        ),
    ]


def make_candidates(url: str) -> list[str]:
    url = clean(url)

    if not url:
        return []

    candidates = []

    for item in drive_urls(url):
        if item not in candidates:
            candidates.append(item)

    if url not in candidates:
        candidates.append(url)

    if "github.com/" in url.lower():

        raw_url = url

        raw_url = raw_url.replace(
            "https://github.com/",
            "https://raw.githubusercontent.com/",
        )

        raw_url = raw_url.replace(
            "http://github.com/",
            "https://raw.githubusercontent.com/",
        )

        raw_url = raw_url.replace(
            "/blob/",
            "/",
        )

        if raw_url not in candidates:
            candidates.append(raw_url)

    return candidates


def detect_extension(
    url: str,
    content_type: str,
    content: bytes,
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

    content_type = clean(
        content_type
    ).lower().split(";")[0]

    content_types = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }

    if content_type in content_types:
        return content_types[content_type]

    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"

    if content.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        return ".png"

    if content.startswith(
        b"GIF87a"
    ) or content.startswith(
        b"GIF89a"
    ):
        return ".gif"

    if (
        len(content) >= 12
        and content[0:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return ".webp"

    return ".jpg"


def is_image(
    content: bytes,
    content_type: str,
) -> bool:

    content_type = clean(
        content_type
    ).lower()

    if content_type.startswith("image/"):
        return True

    if content.startswith(b"\xff\xd8\xff"):
        return True

    if content.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        return True

    if content.startswith(
        b"GIF87a"
    ) or content.startswith(
        b"GIF89a"
    ):
        return True

    if (
        len(content) >= 12
        and content[0:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return True

    return False


def make_filename(
    news_id: str,
    image_number: int,
    extension: str,
) -> str:

    news_id = safe_id(news_id)

    extension = clean(
        extension
    ).lower()

    if not extension:
        extension = ".jpg"

    if not extension.startswith("."):
        extension = "." + extension

    if extension == ".jpeg":
        extension = ".jpg"

    return (
        f"{news_id}-"
        f"{image_number}"
        f"{extension}"
    )


def download_image(
    url: str,
    news_id: str,
    image_number: int,
    assets_dir: Path,
    session: requests.Session,
) -> str:

    url = clean(url)

    if not url:
        return ""

    if not url.startswith(
        ("http://", "https://")
    ):
        return ""

    assets_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "image/avif,image/webp,"
            "image/apng,image/svg+xml,"
            "image/*,*/*;q=0.8"
        ),
    }

    candidates = make_candidates(url)

    for candidate in candidates:

        response = None

        try:

            print(
                "Trying image:",
                candidate,
            )

            response = session.get(
                candidate,
                headers=headers,
                timeout=TIMEOUT,
                allow_redirects=True,
            )

            response.raise_for_status()

            content_type = response.headers.get(
                "content-type",
                "",
            )

            content = response.content

            if not content:
                raise RuntimeError(
                    "Empty response"
                )

            if not is_image(
                content,
                content_type,
            ):

                preview = (
                    content[:300]
                    .decode(
                        "utf-8",
                        errors="ignore",
                    )
                    .lower()
                )

                if (
                    "<html" in preview
                    or "<!doctype" in preview
                    or "<head" in preview
                ):
                    raise RuntimeError(
                        "Server returned HTML instead of image"
                    )

                raise RuntimeError(
                    "Response is not an image"
                )

            extension = detect_extension(
                candidate,
                content_type,
                content,
            )

            filename = make_filename(
                news_id,
                image_number,
                extension,
            )

            destination = (
                assets_dir / filename
            )

            temporary = Path(
                str(destination) + ".tmp"
            )

            with open(
                temporary,
                "wb",
            ) as file:

                file.write(content)

            if (
                not temporary.exists()
                or temporary.stat().st_size == 0
            ):
                raise RuntimeError(
                    "Image file is empty"
                )

            temporary.replace(
                destination
            )

            print(
                "Saved:",
                destination,
            )

            return (
                "assets/news/"
                + filename
            )

        except Exception as error:

            print(
                "Image failed:",
                error,
            )

        finally:

            if response is not None:

                try:
                    response.close()
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
        exist_ok=True,
    )

    if session is None:
        session = requests.Session()

    results = []

    for index in range(3):

        image_number = index + 1

        if index >= len(image_urls):
            results.append("")
            continue

        url = clean(
            image_urls[index]
        )

        if not url:
            results.append("")
            continue

        print(
            f"Processing image {image_number} "
            f"for news ID {news_id}"
        )

        result = download_image(
            url=url,
            news_id=news_id,
            image_number=image_number,
            assets_dir=assets_dir,
            session=session,
        )

        results.append(result)

    return results
