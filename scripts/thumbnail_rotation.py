from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path
import re
from shutil import copy2
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = ROOT / "이미"
OUTPUT_DIRECTORY = ROOT / "output" / "assets" / "search-thumbnails"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SITE_URL = "https://tutorplan.co.kr"


def natural_sort_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", path.name)]


@lru_cache(maxsize=1)
def images() -> tuple[Path, ...]:
    files = [path for path in SOURCE_DIRECTORY.iterdir() if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS]
    if not files:
        raise RuntimeError(f"No thumbnail images found in {SOURCE_DIRECTORY}")
    return tuple(sorted(files, key=natural_sort_key))


def publish_images() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for source in images():
        copy2(source, OUTPUT_DIRECTORY / source.name)


def image_markup(index: int, page_title: str) -> str:
    source = image_source(index)
    alt = escape(f"{page_title} 과외 안내")
    return f'<figure class="page-thumbnail"><img src="/assets/search-thumbnails/{source}" alt="{alt}" loading="lazy"></figure>'


def image_source(index: int) -> str:
    """Return the URL-encoded filename assigned to a regional page."""
    return quote(images()[index % len(images())].name)


def image_url(index: int) -> str:
    """Return the absolute representative-image URL for Open Graph metadata."""
    return f"{SITE_URL}/assets/search-thumbnails/{image_source(index)}"
