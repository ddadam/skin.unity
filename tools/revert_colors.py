#!/usr/bin/env python3
"""Revert the colour-system rewrite to the proven dynamic-inline mechanism.

Why: the named-colour system assumed Kodi loads colors/<theme>.xml based on
the skin string "colors" - core never reads that string (it uses the GUI
setting lookandfeel.colortheme), and <color> definitions are parsed as raw
hex (sscanf %x), so the $INFO-backed colors/custom.xml could never resolve.
Result: every accent stayed at the defaults.xml red.

This restores the omega behaviour: semantic names are replaced by inline
$INFO[Skin.String(...)] lookups that CGUIInfoColor resolves per frame -
colour picks apply instantly, no ReloadSkin needed.

It also cleans Custom_Colours.xml back to the legacy click flow:
  * swatches/light-dark write color.* strings directly (instant effect)
  * removes the broken Skin.SetString(colors,...) routing and ReloadSkin()
"""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent.parent

# semantic name -> legacy inline lookup (inverse of migrate_colors.py)
REPLACEMENTS = {
    "accent.dark":       "$INFO[Skin.String(color.900)]",
    "accent.light":      "$INFO[Skin.String(color.400)]",
    "surface.primary":   "$INFO[Skin.String(color.primary)]",
    "surface.secondary": "$INFO[Skin.String(color.tertiary)]",
    "text.disabled":     "$INFO[Skin.String(color.disabled)]",
    "text.primary":      "$INFO[Skin.String(color.text)]",
    "accent.alt":        "$INFO[Skin.String(color.alt)]",
    "accent":            "$INFO[Skin.String(color.500)]",
    "border":            "$INFO[Skin.String(color.border)]",
}


def desemantic(s: str) -> tuple[str, int]:
    """Replace semantic colour names with inline dynamic lookups."""
    count = 0
    for name, repl in sorted(REPLACEMENTS.items(), key=lambda kv: -len(kv[0])):
        # attribute form: ="name"
        old, new = '="%s"' % name, '="%s"' % repl
        n = s.count(old)
        if n:
            count += n
            s = s.replace(old, new)
        # element-text form: >name<
        old, new = ">%s<" % name, ">%s<" % repl
        n = s.count(old)
        if n:
            count += n
            s = s.replace(old, new)
    return s, count


def cleanup_picker_dialog(s: str) -> tuple[str, int]:
    """Custom_Colours.xml: restore legacy instant-write click flow."""
    changes = 0

    # 1) drop preset-routing onclicks (skin-string 'colors' is never read by core)
    pat = re.compile(
        r"[ \t]*<onclick condition=\"[^\"]*theme\.surface[^\"]*\">"
        r"Skin\.SetString\(colors,[^<]*</onclick>[ \t]*\r?\n")
    s, n = pat.subn("", s)
    changes += n

    # 2) ReloadSkin() is unnecessary with per-frame colour resolution
    pat = re.compile(r"[ \t]*<onclick>ReloadSkin\(\)</onclick>[ \t]*\r?\n")
    s, n = pat.subn("", s)
    changes += n

    # 3) light/dark surface buttons: make their color.* writes unconditional
    #    (they were gated on the now-meaningless colors==custom check)
    old = "<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString("
    n = s.count(old)
    s = s.replace(old, "<onclick>Skin.SetString(")
    changes += n

    return s, changes


def main() -> None:
    total_names = 0
    changed_files = {}

    for f in sorted((BASE / "xml").rglob("*.xml")):
        s = f.read_text(encoding="utf-8")
        orig = s
        s, n = desemantic(s)
        if f.name == "Custom_Colours.xml":
            s, m = cleanup_picker_dialog(s)
            n += m
        if s != orig:
            f.write_text(s, encoding="utf-8", newline="\r\n" if "\r\n" in orig else "\n")
            changed_files[str(f.relative_to(BASE))] = n
            total_names += n

    print("replaced %d semantic colour references in %d files" %
          (total_names, len(changed_files)))
    for k in sorted(changed_files):
        print("  %3d  %s" % (changed_files[k], k))

    # verification
    leftovers = []
    for f in sorted((BASE / "xml").rglob("*.xml")):
        s = f.read_text(encoding="utf-8")
        rel = str(f.relative_to(BASE))
        for name in REPLACEMENTS:
            for token in ('="%s"' % name, ">%s<" % name):
                if token in s:
                    leftovers.append("%s still contains %r" % (rel, token))
    if leftovers:
        print("\nLEFTOVERS (manual review):")
        for x in leftovers:
            print(" ", x)
    else:
        print("\nno semantic colour references left in xml/")

    total = 0
    for f in sorted((BASE / "xml").rglob("*.xml")):
        total += f.read_text(encoding="utf-8").count("Skin.String(color.")
    print("inline Skin.String(color.*) occurrences now: %d (omega baseline: 1605)" % total)


if __name__ == "__main__":
    main()
