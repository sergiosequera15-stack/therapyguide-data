from __future__ import annotations

import json
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
import urllib3
from bs4 import BeautifulSoup


SEED_URL = (
    "https://www.huvn.es/profesionales/de_interes_sanitario/"
    "proa_programa_de_optimizacion_de_la_antibioterapia/"
    "guia_de_antibioterapia"
)

GUIDE_PATH = (
    "/profesionales/de_interes_sanitario/"
    "proa_programa_de_optimizacion_de_la_antibioterapia/"
    "guia_de_antibioterapia"
)

PUBLIC_DIR = Path("public")
DEBUG_OUTPUT = PUBLIC_DIR / "debug_discovery.json"

ALLOWED_HOSTS = {"www.huvn.es", "huvn.es"}

# Profundidad:
# 0 = página índice
# 1 = temas enlazados desde el índice
# 2 = subtemas enlazados desde cada tema
MAX_DEPTH = 2
MAX_PAGES = 80

# DEMO:
# La web HUVN dio problemas de cadena SSL en Android.
# En esta prueba desactivamos la verificación SSL.
VERIFY_SSL = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def download_text(url: str) -> str:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
        verify=VERIFY_SSL,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def normalize_url(base_url: str, href: str) -> str | None:
    href = href.strip()

    if not href:
        return None

    if href.startswith("#"):
        return None

    if href.lower().startswith(("mailto:", "tel:", "javascript:")):
        return None

    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)

    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()
    if host not in ALLOWED_HOSTS:
        return None

    path = parsed.path.rstrip("/")
    if not path:
        return None

    # Normalizamos siempre a https://www.huvn.es y quitamos query/fragment.
    return urlunparse(("https", "www.huvn.es", path, "", "", ""))


def is_probably_file(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(
        (
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".css",
            ".js",
            ".zip",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
        )
    )


def is_guide_page(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.netloc.lower() in ALLOWED_HOSTS
        and parsed.path.startswith(GUIDE_PATH)
        and not is_probably_file(url)
    )


def is_pdf_url(url: str) -> bool:
    return ".pdf" in url.lower()


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_title(soup: BeautifulSoup, fallback_url: str) -> str:
    h1 = soup.select_one("h1")
    if h1 and clean_text(h1.get_text()):
        return clean_text(h1.get_text())

    if soup.title and clean_text(soup.title.get_text()):
        return clean_text(soup.title.get_text())

    return urlparse(fallback_url).path.rstrip("/").split("/")[-1].replace("_", " ")


def discover_links(html: str, base_url: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")

    guide_links: set[str] = set()
    pdf_links: set[str] = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        normalized = normalize_url(base_url, href)

        if not normalized:
            continue

        if is_pdf_url(normalized):
            pdf_links.add(normalized)
            continue

        if is_guide_page(normalized):
            guide_links.add(normalized)

    return sorted(guide_links), sorted(pdf_links)


def crawl() -> dict:
    queue: deque[tuple[str, int, str | None]] = deque()
    queued: set[str] = set()
    visited: set[str] = set()

    pages: list[dict] = []
    all_guide_links: set[str] = set()
    all_pdf_links: set[str] = set()
    errors: list[dict] = []

    def enqueue(url: str, depth: int, found_from: str | None) -> None:
        if url in queued:
            return

        if len(queued) >= MAX_PAGES:
            return

        queued.add(url)
        queue.append((url, depth, found_from))

    enqueue(SEED_URL, 0, None)

    while queue and len(visited) < MAX_PAGES:
        url, depth, found_from = queue.popleft()

        if url in visited:
            continue

        visited.add(url)

        print(f"[depth={depth}] Descargando: {url}")

        try:
            html = download_text(url)
            soup = BeautifulSoup(html, "lxml")

            guide_links, pdf_links = discover_links(html, url)

            all_guide_links.update(guide_links)
            all_pdf_links.update(pdf_links)

            title = extract_title(soup, url)
            body_text = clean_text(soup.get_text(" "))
            page_record = {
                "url": url,
                "depth": depth,
                "foundFrom": found_from,
                "title": title,
                "htmlLength": len(html),
                "textLength": len(body_text),
                "guideLinkCount": len(guide_links),
                "pdfLinkCount": len(pdf_links),
                "guideLinks": guide_links,
                "pdfLinks": pdf_links,
            }
            pages.append(page_record)

            if depth < MAX_DEPTH:
                for link in guide_links:
                    enqueue(link, depth + 1, url)

        except Exception as exc:
            errors.append(
                {
                    "url": url,
                    "depth": depth,
                    "foundFrom": found_from,
                    "errorType": exc.__class__.__name__,
                    "error": str(exc),
                }
            )

    pediatric_candidates = [
        link
        for link in sorted(all_guide_links)
        if any(
            token in link.lower()
            for token in ("pediatr", "pediatrico", "pediatrica", "neonato", "nino")
        )
    ]

    return {
        "generatedAt": now_iso(),
        "seedUrl": SEED_URL,
        "maxDepth": MAX_DEPTH,
        "maxPages": MAX_PAGES,
        "visitedPageCount": len(visited),
        "pageRecordCount": len(pages),
        "allGuideLinkCount": len(all_guide_links),
        "allPdfLinkCount": len(all_pdf_links),
        "pediatricCandidateCount": len(pediatric_candidates),
        "pediatricCandidates": pediatric_candidates,
        "allGuideLinks": sorted(all_guide_links),
        "allPdfLinks": sorted(all_pdf_links),
        "pages": pages,
        "errors": errors,
    }


def main() -> None:
    if not VERIFY_SSL:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    result = crawl()

    DEBUG_OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Páginas visitadas: {result['visitedPageCount']}")
    print(f"Enlaces de guía totales: {result['allGuideLinkCount']}")
    print(f"PDFs totales: {result['allPdfLinkCount']}")
    print(f"Candidatos pediátricos: {result['pediatricCandidateCount']}")
    print(f"Errores: {len(result['errors'])}")
    print(f"Informe escrito en: {DEBUG_OUTPUT}")

    if result["pediatricCandidates"]:
        print()
        print("Candidatos pediátricos:")
        for link in result["pediatricCandidates"]:
            print(f"- {link}")


if __name__ == "__main__":
    main()
