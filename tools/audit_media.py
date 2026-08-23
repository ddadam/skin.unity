#!/usr/bin/env python3
"""Audit media/ for files never referenced by the skin's XML.

Tiers:
  referenced    - path/filename (case-insensitive) found in XML, or parent dir used dynamically
  core-dynamic  - Default*/Overlay*/epg-genres/* resolved by Kodi core at runtime (keep)
  unreferenced  - safe-to-remove candidates (report only, nothing deleted)
"""
from pathlib import Path
import re

BASE = Path.cwd()
MEDIA = BASE / "media"
XML_FILES = sorted((BASE / "xml").rglob("*.xml")) + \
            sorted((BASE / "shortcuts").rglob("*.xml")) + \
            sorted((BASE / "extras").rglob("*.xml"))
corpus = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in XML_FILES)
low = corpus.lower()
CORE_DYNAMIC = re.compile(r"^(Default.*|Overlay.*)\.png$", re.IGNORECASE)


def classify(path: Path) -> str:
    rel = path.relative_to(MEDIA).as_posix()
    if rel.lower() in low or path.name.lower() in low:
        return "referenced"
    parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
    if parent and parent.lower() in low:
        return "referenced"
    if CORE_DYNAMIC.match(path.name) or rel.startswith("epg-genres/"):
        return "core-dynamic"
    return "unreferenced"


def main() -> None:
    tiers = {"unreferenced": [], "core-dynamic": []}
    for f in sorted(MEDIA.rglob("*")):
        if f.is_file() and classify(f) != "referenced":
            tiers[classify(f)].append((f.relative_to(MEDIA).as_posix(), f.stat().st_size))

    total = sum(s for _, s in tiers["unreferenced"])
    print(f"safe-to-remove candidates: {len(tiers['unreferenced'])} files ({total/1024:.0f} KB)")
    for rel, size in tiers["unreferenced"]:
        print(f"    {size/1024:8.1f} KB  {rel}")
    print(f"\nkept (Kodi core resolves at runtime): {len(tiers['core-dynamic'])} files")


if __name__ == "__main__":
    main()
