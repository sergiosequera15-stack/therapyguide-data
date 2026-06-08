from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse, urlunparse

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
RESOURCES_DIR = PUBLIC_DIR / "resources"

GUIDE_TOPICS_OUTPUT = PUBLIC_DIR / "guide_topics.json"
MANIFEST_OUTPUT = PUBLIC_DIR / "manifest.json"
DEBUG_OUTPUT = PUBLIC_DIR / "debug_discovery.json"

ALLOWED_HOSTS = {"www.huvn.es", "huvn.es"}

MAX_DEPTH = 2
MAX_PAGES = 80

VERIFY_SSL = False

MIN_CONTENT_LENGTH = 80
LOW_CONTENT_WARNING_LENGTH = 300

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


def strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return clean_text(soup.get_text(" "))


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    last = path.split("/")[-1] or "guia_de_antibioterapia"
    last = unquote(last)
    last = last.lower()
    last = re.sub(r"[^a-z0-9áéíóúüñ_-]+", "_", last)
    last = last.replace("-", "_")
    last = re.sub(r"_+", "_", last)
    return last.strip("_") or hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def extract_title(soup: BeautifulSoup, fallback_url: str) -> str:
    h1 = soup.select_one("h1")
    if h1 and clean_text(h1.get_text()):
        return clean_text(h1.get_text())

    if soup.title and clean_text(soup.title.get_text()):
        title = clean_text(soup.title.get_text())
        title = title.replace("Hospital Universitario Virgen de las Nieves", "")
        title = title.replace("Guía de Antibioterapia", "")
        title = clean_text(title.strip("-| "))
        if title:
            return title

    return slug_from_url(fallback_url).replace("_", " ").title()


def find_main_element(soup: BeautifulSoup):
    selectors = [
        "main",
        "article",
        "#content",
        "#contenido",
        "#main-content",
        ".content",
        ".contenido",
        ".region-content",
        ".main-content",
        ".node__content",
        ".field-name-body",
        ".field--name-body",
    ]

    for selector in selectors:
        candidate = soup.select_one(selector)
        if candidate and len(clean_text(candidate.get_text(" "))) > MIN_CONTENT_LENGTH:
            return candidate

    return soup.body or soup


def extract_main_html(soup: BeautifulSoup) -> str:
    main = find_main_element(soup)

    for bad in main.select(
        "script, style, nav, header, footer, form, iframe, button, "
        ".breadcrumb, .breadcrumbs, .migas, .social, .share"
    ):
        bad.decompose()

    return str(main).strip()


def make_summary(content_text: str) -> str:
    return clean_text(content_text)[:260]


def infer_tags(title: str, content_text: str, url: str) -> list[str]:
    combined = f"{title} {content_text} {url}".lower()

    tags = ["Guía de Antibioterapia"]

    if any(token in combined for token in ["pediatr", "pediátr", "niño", "neonato"]):
        tags.append("Pediatría")

    if any(token in combined for token in ["adulto", "adultos"]):
        tags.append("Adultos")

    if "sepsis" in combined:
        tags.append("Sepsis")

    if "neumon" in combined:
        tags.append("Neumonía")

    if "urinari" in combined or "itu" in combined:
        tags.append("ITU")

    if "intraabdominal" in combined:
        tags.append("Intraabdominal")

    if "orl" in combined:
        tags.append("ORL")

    if "meningitis" in combined:
        tags.append("Meningitis")

    if "piel" in combined or "partes blandas" in combined:
        tags.append("Piel y partes blandas")

    return list(dict.fromkeys(tags))


def discover_links(html: str, base_url: str) -> tuple[list[str], list[dict]]:
    soup = BeautifulSoup(html, "lxml")

    guide_links: set[str] = set()
    pdf_resources: dict[str, dict] = {}

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        normalized = normalize_url(base_url, href)

        if not normalized:
            continue

        if is_pdf_url(normalized):
            title = clean_text(a.get_text(" ")) or filename_from_url(normalized)
            pdf_resources[normalized] = {
                "title": title,
                "url": normalized,
                "localPath": None,
                "lastSyncEpochMs": None,
            }
            continue

        if is_guide_page(normalized):
            guide_links.add(normalized)

    return sorted(guide_links), list(pdf_resources.values())


def filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = unquote(path.split("/")[-1] or "documento.pdf")
    return name.replace("_", " ")


def crawl() -> tuple[list[dict], dict]:
    queue: deque[tuple[str, int, str | None]] = deque()
    queued: set[str] = set()
    visited: set[str] = set()

    topics_by_url: dict[str, dict] = {}
    pages: list[dict] = []
    all_guide_links: set[str] = set()
    all_pdf_links: dict[str, dict] = {}
    warnings: list[dict] = []
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

            guide_links, pdf_resources = discover_links(html, url)

            all_guide_links.update(guide_links)
            for resource in pdf_resources:
                all_pdf_links[resource["url"]] = resource

            if depth < MAX_DEPTH:
                for link in guide_links:
                    enqueue(link, depth + 1, url)

            title = extract_title(soup, url)
            main_html = extract_main_html(soup)
            content_text = strip_html(main_html)

            pages.append(
                {
                    "url": url,
                    "depth": depth,
                    "foundFrom": found_from,
                    "title": title,
                    "htmlLength": len(html),
                    "contentTextLength": len(content_text),
                    "guideLinkCount": len(guide_links),
                    "pdfLinkCount": len(pdf_resources),
                    "guideLinks": guide_links,
                    "pdfLinks": [r["url"] for r in pdf_resources],
                }
            )

            # La página índice se usa para descubrir enlaces, pero no la guardamos como tema clínico.
            if url == SEED_URL:
                continue

            if len(content_text) < MIN_CONTENT_LENGTH:
                errors.append(
                    {
                        "url": url,
                        "title": title,
                        "error": f"Contenido demasiado corto: {len(content_text)} caracteres",
                    }
                )
                continue

            if len(content_text) < LOW_CONTENT_WARNING_LENGTH:
                warnings.append(
                    {
                        "url": url,
                        "title": title,
                        "warning": f"Contenido breve: {len(content_text)} caracteres",
                    }
                )

            topic = {
                "id": slug_from_url(url),
                "title": title,
                "summary": make_summary(content_text),
                "tags": infer_tags(title, content_text, url),
                "resources": pdf_resources,
                "sourceUrl": url,
                "contentHtml": main_html,
                "contentText": content_text,
                "updatedAt": now_iso(),
                "lastSyncedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
            }

            topics_by_url[url] = topic

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
        url
        for url in sorted(topics_by_url)
        if any(
            token in url.lower()
            for token in ("pediatr", "pediatrico", "pediatrica", "neonato", "nino")
        )
    ]

    debug = {
        "generatedAt": now_iso(),
        "seedUrl": SEED_URL,
        "maxDepth": MAX_DEPTH,
        "maxPages": MAX_PAGES,
        "visitedPageCount": len(visited),
        "topicCount": len(topics_by_url),
        "allGuideLinkCount": len(all_guide_links),
        "allPdfLinkCount": len(all_pdf_links),
        "pediatricCandidateCount": len(pediatric_candidates),
        "pediatricCandidates": pediatric_candidates,
        "allGuideLinks": sorted(all_guide_links),
        "allPdfLinks": sorted(all_pdf_links),
        "pages": pages,
        "warnings": warnings,
        "errors": errors,
    }

    return list(topics_by_url.values()), debug


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    if not VERIFY_SSL:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

    topics, debug = crawl()

    global_resources = [
        {
            "title": filename_from_url(url),
            "url": url,
            "localPath": None,
            "lastSyncEpochMs": None,
        }
        for url in debug["allPdfLinks"]
    ]

    manifest = {
        "version": 1,
        "generatedAt": now_iso(),
        "source": SEED_URL,
        "topicsUrl": "guide_topics.json",
        "resourcesBaseUrl": "resources/",
        "topicCount": len(topics),
        "resourceCount": len(global_resources),
        "pediatricTopicCount": debug["pediatricCandidateCount"],
        "globalResources": global_resources,
        "warnings": debug["warnings"],
        "errors": debug["errors"],
    }

    write_json(GUIDE_TOPICS_OUTPUT, topics)
    write_json(MANIFEST_OUTPUT, manifest)
    write_json(DEBUG_OUTPUT, debug)

    print()
    print(f"Temas generados: {len(topics)}")
    print(f"PDFs detectados: {len(global_resources)}")
    print(f"Candidatos pediátricos: {debug['pediatricCandidateCount']}")
    print(f"Warnings: {len(debug['warnings'])}")
    print(f"Errores: {len(debug['errors'])}")
    print(f"Escrito: {GUIDE_TOPICS_OUTPUT}")
    print(f"Escrito: {MANIFEST_OUTPUT}")
    print(f"Escrito: {DEBUG_OUTPUT}")

    if debug["pediatricCandidates"]:
        print()
        print("Temas pediátricos:")
        for link in debug["pediatricCandidates"]:
            print(f"- {link}")


if __name__ == "__main__":
    main()
