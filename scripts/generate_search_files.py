"""Generate crawler-facing robots.txt and sitemap.xml from canonical regional pages."""

from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"', re.IGNORECASE)


def canonical_urls() -> list[str]:
    urls: set[str] = set()
    for page in OUTPUT.rglob("index.html"):
        source = page.read_text(encoding="utf-8")
        match = CANONICAL_RE.search(source)
        if match:
            urls.add(match.group(1))
    return sorted(urls)


def main() -> None:
    urls = canonical_urls()
    if len(urls) != 1331:
        raise SystemExit(f"Expected 1331 canonical regional URLs, found {len(urls)}.")

    robots = "User-agent: *\nAllow: /\n\nSitemap: https://tutorplan.co.kr/sitemap.xml\n"
    (OUTPUT / "robots.txt").write_text(robots, encoding="utf-8", newline="\n")

    entries = "\n".join(
        f"  <url><loc>{html.escape(url)}</loc></url>" for url in urls
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    (OUTPUT / "sitemap.xml").write_text(sitemap, encoding="utf-8", newline="\n")
    print(f"Generated robots.txt and sitemap.xml with {len(urls)} canonical URLs.")


if __name__ == "__main__":
    main()
