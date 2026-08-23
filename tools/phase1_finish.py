#!/usr/bin/env python3
"""Finish Phase 1: theme-selection UI, picker OK handler, remove CheckSkinColorsSet, Startup migration."""
from pathlib import Path
import re

BASE = Path.cwd()

def read(rel): return (BASE / rel).read_text(encoding="utf-8")
def write(rel, s): (BASE / rel).write_text(s, encoding="utf-8")

report = []

# ------------------------------------------------ 1) xml/Custom_Colours.xml
rel = "xml/Custom_Colours.xml"
s = read(rel)
s = s.replace("<focusedcolor>$INFO[Skin.String(color.900)]</focusedcolor>",
              "<focusedcolor>accent.dark</focusedcolor>")

LIGHT_OLD = ("\t\t\t\t\t<onclick>Skin.SetString(color.primary, FFFFFFFF)</onclick>\n"
             "\t\t\t\t\t<onclick>Skin.SetString(color.tertiary, FFF1F1F1)</onclick>\n"
             "\t\t\t\t\t<onclick>Skin.SetString(color.disabled, AABBBBBB)</onclick>\n"
             "\t\t\t\t\t<onclick>Skin.SetString(color.text, FF666666)</onclick>\n"
             "\t\t\t\t\t<onclick>Skin.SetString(color.border, FFCCCCCC)</onclick>")
LIGHT_NEW = ("\t\t\t\t\t<onclick>Skin.SetString(theme.surface,light)</onclick>\n"
             "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.primary, FFFFFFFF)</onclick>\n"
             "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.tertiary, FFF1F1F1)</onclick>\n"
             "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.disabled, AABBBBBB)</onclick>\n"
             "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.text, FF666666)</onclick>\n"
             "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.border, FFCCCCCC)</onclick>\n"
             "\t\t\t\t\t<onclick condition=\"!String.IsEqual(Skin.String(colors),custom) + String.IsEmpty(Skin.String(theme.accent))\">Skin.ClearSetting(colors)</onclick>\n"
             "\t\t\t\t\t<onclick condition=\"!String.IsEqual(Skin.String(colors),custom) + !String.IsEmpty(Skin.String(theme.accent))\">Skin.SetString(colors,$INFO[Skin.String(theme.accent)]-light)</onclick>\n"
             "\t\t\t\t\t<onclick>ReloadSkin()</onclick>")
DARK_OLD = ("\t\t\t\t\t<onclick>Skin.SetString(color.primary, FF4BBEFC)</onclick>\n"
            "\t\t\t\t\t<onclick>Skin.SetString(color.tertiary, FF444444)</onclick>\n"
            "\t\t\t\t\t<onclick>Skin.SetString(color.disabled, AA606060)</onclick>\n"
            "\t\t\t\t\t<onclick>Skin.SetString(color.text, FFEEEEEE)</onclick>\n"
            "\t\t\t\t\t<onclick>Skin.SetString(color.border, FF555555)</onclick>")
DARK_NEW = ("\t\t\t\t\t<onclick>Skin.SetString(theme.surface,dark)</onclick>\n"
            "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.primary, FF4BBEFC)</onclick>\n"
            "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.tertiary, FF444444)</onclick>\n"
            "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.disabled, AA606060)</onclick>\n"
            "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.text, FFEEEEEE)</onclick>\n"
            "\t\t\t\t\t<onclick condition=\"String.IsEqual(Skin.String(colors),custom)\">Skin.SetString(color.border, FF555555)</onclick>\n"
            "\t\t\t\t\t<onclick condition=\"!String.IsEqual(Skin.String(colors),custom) + String.IsEmpty(Skin.String(theme.accent))\">Skin.SetString(colors,Default-dark)</onclick>\n"
            "\t\t\t\t\t<onclick condition=\"!String.IsEqual(Skin.String(colors),custom) + !String.IsEmpty(Skin.String(theme.accent))\">Skin.SetString(colors,$INFO[Skin.String(theme.accent)]-dark)</onclick>\n"
            "\t\t\t\t\t<onclick>ReloadSkin()</onclick>")
assert LIGHT_OLD in s, "light button block not found"
s = s.replace(LIGHT_OLD, LIGHT_NEW)
assert DARK_OLD in s, "dark button block not found"
s = s.replace(DARK_OLD, DARK_NEW)

THEME_MAP = {"Red":"Red","Pink":"Pink","Purple":"Purple","Deep Purple":"DeepPurple",
             "Indigo":"Indigo","Blue":"Blue","Light Blue":"LightBlue","Cyan":"Cyan",
             "Teal":"Teal","Green":"Green","Light Green":"LightGreen","Lime":"Lime",
             "Yellow":"Yellow","Amber":"Amber","Orange":"Orange","Deep Orange":"DeepOrange",
             "Brown":"Brown","Blue Grey":"BlueGrey","Grey":"Grey"}
item_re = re.compile(r"<item id=\"\d+\">.*?</item>", re.S)
patched = [0]
def fix_item(m):
    block = m.group(0)
    if "theme.accent" in block: return block
    tm = re.search(r"<thumb>colours/(.+?)\.png</thumb>", block)
    if not tm or tm.group(1) not in THEME_MAP: return block
    key = THEME_MAP[tm.group(1)]
    lab = re.search(r"^([ \t]*)<label>319\d+</label>[ \t]*$", block, re.M)
    ind = lab.group(1)
    inject = (ind + "<onclick>Skin.SetString(theme.accent," + key + ")</onclick>\n"
              + ind + "<onclick condition=\"String.IsEqual(Skin.String(theme.surface),dark)\">Skin.SetString(colors," + key + "-dark)</onclick>\n"
              + ind + "<onclick condition=\"!String.IsEqual(Skin.String(theme.surface),dark)\">Skin.SetString(colors," + key + "-light)</onclick>")
    block = block.replace(lab.group(0), lab.group(0) + "\n" + inject)
    alt = re.search(r"^([ \t]*)<onclick>Skin\.SetString\(color\.alt, [0-9A-Fa-f]+\)</onclick>[ \t]*$", block, re.M)
    block = block.replace(alt.group(0), alt.group(0) + "\n" + alt.group(1) + "<onclick>ReloadSkin()</onclick>")
    patched[0] += 1
    return block
s = item_re.sub(fix_item, s)
write(rel, s)
report.append(rel + ": buttons rewired, " + str(patched[0]) + " swatches patched")

# ------------------------------------------------ 2) xml/Custom_Colours_Select.xml
rel = "xml/Custom_Colours_Select.xml"
s = read(rel)
anchor = "<onclick>Skin.SetString(color.alt, $INFO[Skin.String(temp.color.alt)])</onclick>"
assert anchor in s, "OK anchor not found"
inject = anchor + "\n" + "\t"*7 + "<onclick>Skin.SetString(colors,custom)</onclick>" \
         + "\n" + "\t"*7 + "<onclick>ReloadSkin()</onclick>"
s = s.replace(anchor, inject)
b810 = "\t\t\t\t\t<onclick>Skin.SetString(temp.color.primary, FFFFFFFF)</onclick>"
assert b810 in s
s = s.replace(b810, "\t\t\t\t\t<onclick>Skin.SetString(theme.surface,light)</onclick>\n" + b810)
b811 = "\t\t\t\t\t<onclick>Skin.SetString(temp.color.primary, FF4BBEFC)</onclick>"
assert b811 in s
s = s.replace(b811, "\t\t\t\t\t<onclick>Skin.SetString(theme.surface,dark)</onclick>\n" + b811)
write(rel, s)
report.append(rel + ": OK applies custom theme + reload; preview tracks theme.surface")

# ------------------------------------------------ 3) remove CheckSkinColorsSet definition
rel = "xml/includes.xml"
s = read(rel)
m = re.search(r"\t<include name=\"CheckSkinColorsSet\">.*?</include>\n", s, re.S)
assert m, "CheckSkinColorsSet definition not found"
s = s.replace(m.group(0), "")
write(rel, s)
report.append(rel + ": CheckSkinColorsSet definition removed")

# ------------------------------------------------ 4) drop usages
for rel in ("xml/Home.xml", "xml/SkinSettings.xml"):
    s = read(rel)
    old = "\t<include>CheckSkinColorsSet</include>\n"
    assert old in s, rel
    s = s.replace(old, "", 1)
    write(rel, s)
    report.append(rel + ": CheckSkinColorsSet usage removed")

# ------------------------------------------------ 5) Startup.xml seeds + migration
rel = "xml/Startup.xml"
s = read(rel)
old = "\t<include>CheckSkinColorsSet</include>\n"
assert old in s, "startup include not found"
slots = [("500","FFE51C23"),("900","FF850A04"),("400","FFE84E40"),("alt","FFFFEB3B"),
         ("text","FF666666"),("disabled","AABBBBBB"),("primary","FFFFFFFF"),
         ("tertiary","FFF1F1F1"),("border","FFCCCCCC")]
lines = ["\t<!-- Seed default colour strings (data source for the custom colour picker) -->"]
lines += ["\t<onload condition=\"String.IsEmpty(Skin.String(color." + k + "))\">Skin.SetString(color." + k + ", " + v + ")</onload>" for k, v in slots]
lines += ["", "\t<!-- Migration: existing installs with non-default colours switch to the dynamic custom theme -->"]
lines += ["\t<onload condition=\"String.IsEmpty(Skin.String(colors)) + !String.IsEqual(Skin.String(color." + k + ")," + v + ")\">Skin.SetString(colors,custom)</onload>" for k, v in slots]
s = s.replace(old, "\n".join(lines) + "\n")
write(rel, s)
report.append(rel + ": seeds + one-time migration added")

# ------------------------------------------------ 6) verification
bad = []
pat = re.compile(re.escape("$INFO[Skin.String(color."))
for f in sorted((BASE / "xml").rglob("*.xml")):
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if pat.search(line) and "Skin.SetString" not in line:
            bad.append(str(f.relative_to(BASE)) + ":" + str(i))
print("=== CHANGES ===")
for r in report: print(" -", r)
print("=== VERIFY ===")
print("render-time colour lookups remaining:", len(bad))
for b in bad: print("   ", b)
