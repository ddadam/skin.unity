#!/usr/bin/env python3
"""Replace render-time colour lookups with named colours (Phase 1 of Unity skin optimisation).

Rewrites every occurrence of $INFO[Skin.String(color.<slot>)] with the matching
semantic colour name defined in colors/defaults.xml:

    color.500      -> accent
    color.900      -> accent.dark
    color.400      -> accent.light
    color.alt      -> accent.alt
    color.text     -> text.primary
    color.disabled -> text.disabled
    color.primary  -> surface.primary
    color.tertiary -> surface.secondary
    color.border   -> border

Lines containing "Skin.SetString" are left untouched: there the strings are used
as data (e.g. copying temp.* values in the colour picker), not as render-time
colours, and must keep their literal string names.
"""
from pathlib import Path

REPLACEMENTS = {
    "$INFO[Skin.String(color.500)]": "accent",
    "$INFO[Skin.String(color.900)]": "accent.dark",
    "$INFO[Skin.String(color.400)]": "accent.light",
    "$INFO[Skin.String(color.alt)]": "accent.alt",
    "$INFO[Skin.String(color.text)]": "text.primary",
    "$INFO[Skin.String(color.disabled)]": "text.disabled",
    "$INFO[Skin.String(color.primary)]": "surface.primary",
    "$INFO[Skin.String(color.tertiary)]": "surface.secondary",
    "$INFO[Skin.String(color.border)]": "border",
}

ROOTS = ("xml", "shortcuts", "extras")


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    per_file = {}

    for root in ROOTS:
        for path in sorted((base / root).rglob("*.xml")):
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            out, file_count = [], 0
            for line in lines:
                if "Skin.SetString" not in line:
                    for old, new in REPLACEMENTS.items():
                        n = line.count(old)
                        if n:
                            line = line.replace(old, new)
                            file_count += n
                out.append(line)
            if file_count:
                path.write_text("".join(out), encoding="utf-8")
                per_file[str(path.relative_to(base))] = file_count

    total = sum(per_file.values())
    print(f"{total} replacements across {len(per_file)} files")
    for name, count in sorted(per_file.items()):
        print(f"  {count:4d}  {name}")


if __name__ == "__main__":
    main()
