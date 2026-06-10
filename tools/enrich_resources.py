from __future__ import annotations

import hashlib
import json
from pathlib import Path


DOCS_DIR = Path("docs")
RESOURCES_DIR = DOCS_DIR / "resources"
MANIFEST_PATH = DOCS_DIR / "manifest.json"
TOPICS_PATH = DOCS_DIR / "guide_topics.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def enrich_resource(resource: dict) -> dict:
    enriched = dict(resource)
    resource_url = str(enriched.get("url") or "")

    if not enriched.get("downloaded"):
        return enriched

    if not resource_url.startswith("resources/"):
        return enriched

    resource_path = DOCS_DIR / resource_url

    if not resource_path.exists():
        enriched["downloaded"] = False
        enriched["error"] = f"Resource file not found: {resource_url}"
        return enriched

    sha256 = sha256_file(resource_path)
    size_bytes = resource_path.stat().st_size

    enriched["sha256"] = sha256
    enriched["version"] = sha256[:12]
    enriched["sizeBytes"] = size_bytes

    return enriched


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    topics = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))

    resource_by_source: dict[str, dict] = {}
    enriched_global_resources = []

    for resource in manifest.get("globalResources", []):
        enriched = enrich_resource(resource)
        source_url = enriched.get("sourceUrl") or enriched.get("url")
        if source_url:
            resource_by_source[source_url] = enriched
        enriched_global_resources.append(enriched)

    for topic in topics:
        topic_resources = []
        for resource in topic.get("resources", []):
            source_url = resource.get("sourceUrl") or resource.get("url")
            topic_resources.append(resource_by_source.get(source_url, enrich_resource(resource)))
        topic["resources"] = topic_resources

    manifest["globalResources"] = enriched_global_resources
    manifest["resourceHashAlgorithm"] = "sha256"

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    TOPICS_PATH.write_text(
        json.dumps(topics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    hashed_count = sum(1 for resource in enriched_global_resources if resource.get("sha256"))
    print(f"Resources enriched with SHA-256: {hashed_count}")


if __name__ == "__main__":
    main()
