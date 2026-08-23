#!/usr/bin/env python3
"""Generate Unity skin colour theme files.

Creates colors/<Accent>-<light|dark>.xml for every accent preset
(values mirror the swatches in xml/Custom_Colours.xml) plus a dynamic
colors/custom.xml used by the colour-picker flow.

Kodi loads colours/defaults.xml always, and additionally loads
colours/<value of the skin string "colors">.xml when that string is set,
so theme files only need to override the nine semantic colour names.
"""
from pathlib import Path

# name -> (color.500, color.900, color.400, color.alt)  [matches Custom_Colours.xml]
ACCENTS = {
    "Default":     ("FFE51C23", "FF850A04", "FFE84E40", "FFFFEB3B"),
    "Red":         ("FFE51C23", "FF850A04", "FFE84E40", "FFFFEB3B"),
    "Pink":        ("FFE91E63", "FF880E4F", "FFEC407A", "FFFFEB3B"),
    "Purple":      ("FF9C27B0", "FF5B1287", "FFAB47BC", "FFFFEB3B"),
    "DeepPurple":  ("FF673AB7", "FF341E96", "FF7E57C2", "FFFFEB3B"),
    "Indigo":      ("FF3F51B5", "FF1C2688", "FF5C6BC0", "FFFFEB3B"),
    "Blue":        ("FF5677FC", "FF313EBC", "FF738FFE", "FFFFEB3B"),
    "LightBlue":   ("FF03A9F4", "FF1275C4", "FF3EBCF5", "FFFFEB3B"),
    "Cyan":        ("FF00BCD4", "FF057A7F", "FF3FD8EB", "FFFFEB3B"),
    "Teal":        ("FF009688", "FF056857", "FF2EBEB0", "FFFFEB3B"),
    "Green":       ("FF259B24", "FF156808", "FF39C439", "FFFFEB3B"),
    "LightGreen":  ("FF8BC34A", "FF4F9833", "FFA0D068", "FFFFEB3B"),
    "Lime":        ("FFCDDC39", "FFA89B26", "FFDDEA60", "FFE51C23"),
    "Yellow":      ("FFF6E233", "FFEFB415", "FFFFEE58", "FFE51C23"),
    "Amber":       ("FFF6B904", "FFFF8A00", "FFFBCB37", "FFE51C23"),
    "Orange":      ("FFFF9800", "FFE06603", "FFFAAC3A", "FFFFEB3B"),
    "DeepOrange":  ("FFFF5722", "FFB9330A", "FFFB6536", "FFFFEB3B"),
    "Brown":       ("FF795548", "FF55322C", "FF8D6E63", "FFFFEB3B"),
    "BlueGrey":    ("FF587482", "FF3A4B5C", "FF78909C", "FFFFEB3B"),
    "Grey":        ("FF908E8E", "FF5D5C5C", "FFBDBDBD", "FFFFEB3B"),
}

# surface -> (primary, tertiary, disabled, text, border)  [matches Light/Dark buttons]
SURFACES = {
    "light": ("FFFFFFFF", "FFF1F1F1", "AABBBBBB", "FF666666", "FFCCCCCC"),
    "dark":  ("FF4BBEFC", "FF444444", "AA606060", "FFEEEEEE", "FF555555"),
}

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Unity colour theme: {accent} / {surface}. Selected via the skin string "colors". -->
<colors>
	<color name="accent">{c500}</color>
	<color name="accent.dark">{c900}</color>
	<color name="accent.light">{c400}</color>
	<color name="accent.alt">{calt}</color>
	<color name="text.primary">{text}</color>
	<color name="text.disabled">{disabled}</color>
	<color name="surface.primary">{primary}</color>
	<color name="surface.secondary">{tertiary}</color>
	<color name="border">{border}</color>
</colors>
"""

CUSTOM = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Unity custom colour theme: follows the user's colour-picker skin strings.
     Only users of the "Custom" colour option pay any runtime lookup cost;
     preset themes are fully static. -->
<colors>
	<color name="accent">$INFO[Skin.String(color.500)]</color>
	<color name="accent.dark">$INFO[Skin.String(color.900)]</color>
	<color name="accent.light">$INFO[Skin.String(color.400)]</color>
	<color name="accent.alt">$INFO[Skin.String(color.alt)]</color>
	<color name="text.primary">$INFO[Skin.String(color.text)]</color>
	<color name="text.disabled">$INFO[Skin.String(color.disabled)]</color>
	<color name="surface.primary">$INFO[Skin.String(color.primary)]</color>
	<color name="surface.secondary">$INFO[Skin.String(color.tertiary)]</color>
	<color name="border">$INFO[Skin.String(color.border)]</color>
</colors>
"""


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "colors"
    out_dir.mkdir(exist_ok=True)

    count = 0
    for accent, (c500, c900, c400, calt) in ACCENTS.items():
        for surface, (primary, tertiary, disabled, text, border) in SURFACES.items():
            content = TEMPLATE.format(
                accent=accent,
                surface=surface,
                c500=c500,
                c900=c900,
                c400=c400,
                calt=calt,
                text=text,
                disabled=disabled,
                primary=primary,
                tertiary=tertiary,
                border=border,
            )
            path = out_dir / f"{accent}-{surface}.xml"
            path.write_text(content, encoding="utf-8")
            count += 1

    (out_dir / "custom.xml").write_text(CUSTOM, encoding="utf-8")
    print(f"Wrote {count} theme files + custom.xml to {out_dir}")


if __name__ == "__main__":
    main()