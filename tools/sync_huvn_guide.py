from __future__ import annotations

import json
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

# DEMO:
# La web HUVN dio problemas de cadena SSL en Android.
# En esta primera prueba desactivamos la verificación SSL para comprobar
# si GitHub Actions puede descargar el contenido.
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


def main() -> None:
    if not VERIFY_SSL:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Descargando índice HUVN: {SEED_URL}")
    html = download_text(SEED_URL)

    guide_links, pdf_links = discover_links(html, SEED_URL)

    result = {
        "generatedAt": now_iso(),
        "seedUrl": SEED_URL,
        "htmlLength": len(html),
        "guideLinkCount": len(guide_links),
        "pdfLinkCount": len(pdf_links),
        "guideLinks": guide_links,
        "pdfLinks": pdf_links,
    }

    DEBUG_OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"HTML descargado: {len(html)} caracteres")
    print(f"Enlaces de guía encontrados: {len(guide_links)}")
    print(f"PDFs encontrados: {len(pdf_links)}")
    print(f"Informe escrito en: {DEBUG_OUTPUT}")

    if guide_links:
        print("\nPrimeros enlaces de guía:")
        for link in guide_links[:10]:
            print(f"- {link}")

    if pdf_links:
        print("\nPrimeros PDFs:")
        for link in pdf_links[:10]:
            print(f"- {link}")


if __name__ == "__main__":
    main()
