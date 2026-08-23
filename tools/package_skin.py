"""Package the skin into an installable zip (dist/skin.unity-<version>.zip).

Zip layout matches Kodi requirements: skin.unity/addon.xml at the root of the
top-level folder. Dev-only files (.git, tools, CI config, local zips) are excluded.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / "dist"

EXCLUDE_DIRS = {".git", ".github", "tools", "dist", "__pycache__"}
EXCLUDE_FILES = {
    ".gitignore", ".gitattributes", "Thumbs.db", "desktop.ini",
    "skin.estuary-master.zip",
}


def main():
    root = ET.parse(BASE / "addon.xml").getroot()
    version = root.get("version", "unknown")

    DIST.mkdir(exist_ok=True)
    out = DIST / ("skin.unity-" + version + ".zip")
    if out.exists():
        out.unlink()

    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(BASE.rglob("*")):
            rel = p.relative_to(BASE)
            parts = set(rel.parts)
            if parts & EXCLUDE_DIRS:
                continue
            if p.name in EXCLUDE_FILES or p.suffix == ".pyc":
                continue
            if p.is_file():
                z.write(p, Path("skin.unity") / rel)
                count += 1

    size = out.stat().st_size
    print("packaged %d files -> %s (%.1f MB)" % (count, out.name, size / 1048576))

    # sanity: addon.xml must be at skin.unity/addon.xml inside the zip
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "skin.unity/addon.xml" in names, "addon.xml missing at zip root"
        assert not any(n.startswith(("tools/", ".git")) for n in names), "dev files leaked"
    print("zip structure OK")


if __name__ == "__main__":
    main()