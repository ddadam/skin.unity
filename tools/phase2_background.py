#!/usr/bin/env python3
"""Phase 2: remove background="true" from static texture/imagepath elements.

background="true" opts a texture into asynchronous loading - intended for large
images (fanart, posters, thumbs). Unity applies it to hundreds of small static
UI textures (white.png overlays, shadows, breadcrumbs), forcing needless thread
hand-offs. Dynamic textures ($INFO/$VAR content) keep the flag.
"""
from pathlib import Path
import re

BASE = Path.cwd()

PAT = re.compile(
    r"(<(texture|imagepath)\b[^>\n]*?)\s+background=\"true\"([^>\n]*>)([^<>\n]*)</\2>",
    re.IGNORECASE,
)


def main() -> None:
    files = sorted((BASE / "xml").glob("*.xml")) + sorted((BASE / "shortcuts").glob("*.xml"))
    changed: dict[str, int] = {}
    kept_dynamic: list[str] = []

    for f in files:
        s = f.read_text(encoding="utf-8")
        orig = s

        def repl(m: re.Match) -> str:
            content = m.group(4)
            if any(ch in content for ch in "$[{"):
                kept_dynamic.append(f"{f.name}: {m.group(0).strip()[:90]}")
                return m.group(0)
            key = str(f.relative_to(BASE))
            changed[key] = changed.get(key, 0) + 1
            return m.group(1) + m.group(3) + m.group(4) + "</" + m.group(2) + ">"

        s = PAT.sub(repl, s)
        if s != orig:
            f.write_text(s, encoding="utf-8")

    total = sum(changed.values())
    print(f"removed background='true' from {total} static textures in {len(changed)} files")
    for k in sorted(changed):
        print(f"  {changed[k]:3d}  {k}")

    print(f"\ndynamic textures kept as-is: {len(kept_dynamic)}")
    for x in kept_dynamic[:15]:
        print("  ", x)

    leftovers = []
    for f in files:
        rel = str(f.relative_to(BASE))
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if 'background="true"' in line and rel not in changed or \
               'background="true"' in line and not PAT.search(line):
                leftovers.append(f"{rel}:{i}: {line.strip()[:100]}")
    print(f"\nremaining background='true' lines needing manual review: {len(leftovers)}")
    for x in leftovers:
        print("  ", x)


if __name__ == "__main__":
    main()