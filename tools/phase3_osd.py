#!/usr/bin/env python3
"""Phase 3: consolidate OSD transport buttons into parametrized includes."""
from pathlib import Path
import re

BASE = Path.cwd()

OSD_BUTTON_INCLUDE = """
\t<include name="OSDButton">
\t\t<param name="id" />
\t\t<param name="texture" />
\t\t<param name="label" default="" />
\t\t<param name="onclick" />
\t\t<param name="visible" default="true" />
\t\t<definition>
\t\t\t<control type="button" id="$PARAM[id]">
\t\t\t\t<width>40</width>
\t\t\t\t<height>40</height>
\t\t\t\t<label>$PARAM[label]</label>
\t\t\t\t<font></font>
\t\t\t\t<texturefocus colordiffuse="accent">$PARAM[texture]</texturefocus>
\t\t\t\t<texturenofocus colordiffuse="text.primary">$PARAM[texture]</texturenofocus>
\t\t\t\t<onclick>$PARAM[onclick]</onclick>
\t\t\t\t<visible>$PARAM[visible]</visible>
\t\t\t</control>
\t\t</definition>
\t</include>
\t<include name="OSDToggleButton">
\t\t<param name="id" />
\t\t<param name="texture" />
\t\t<param name="alttexture" />
\t\t<param name="label" default="" />
\t\t<param name="altlabel" default="" />
\t\t<param name="usealttexture" />
\t\t<param name="onclick" />
\t\t<definition>
\t\t\t<control type="togglebutton" id="$PARAM[id]">
\t\t\t\t<width>40</width>
\t\t\t\t<height>40</height>
\t\t\t\t<label>$PARAM[label]</label>
\t\t\t\t<altlabel>$PARAM[altlabel]</altlabel>
\t\t\t\t<font></font>
\t\t\t\t<texturefocus colordiffuse="accent">$PARAM[texture]</texturefocus>
\t\t\t\t<texturenofocus colordiffuse="text.primary">$PARAM[texture]</texturenofocus>
\t\t\t\t<usealttexture>$PARAM[usealttexture]</usealttexture>
\t\t\t\t<alttexturefocus colordiffuse="accent">$PARAM[alttexture]</alttexturefocus>
\t\t\t\t<alttexturenofocus colordiffuse="text.primary">$PARAM[alttexture]</alttexturenofocus>
\t\t\t\t<onclick>$PARAM[onclick]</onclick>
\t\t\t</control>
\t\t</definition>
\t</include>
"""

BLOCK_RE = re.compile(r"([ \t]*)<control type=\"(button|togglebutton)\" id=\"(\d+)\">(.*?)</control>", re.S)
TAG_RE = re.compile(r"<(\w+)(?:\s[^>]*)?>(.*?)</\1>", re.S)

BUTTON_ALLOWED = {"width", "height", "label", "font", "texturefocus", "texturenofocus", "onclick"}
TOGGLE_ALLOWED = BUTTON_ALLOWED | {"altlabel", "usealttexture", "alttexturefocus", "alttexturenofocus"}


def parse_body(body):
    return {m.group(1): m.group(2).strip() for m in TAG_RE.finditer(body)}


def convert(m, stats):
    indent, kind, cid, body = m.group(1), m.group(2), m.group(3), m.group(4)
    fields = parse_body(body)
    allowed = TOGGLE_ALLOWED if kind == "togglebutton" else BUTTON_ALLOWED
    stats["seen"] += 1
    if (set(fields) - allowed
            or not set(fields) >= {"width", "height", "label", "font", "texturefocus", "texturenofocus", "onclick"}):
        stats["skipped"] += 1
        return m.group(0)
    if (fields["width"], fields["height"], fields["font"]) != ("40", "40", ""):
        stats["skipped"] += 1
        return m.group(0)
    tfocus = re.search(r"<texturefocus([^>]*)>(.*?)</texturefocus>", body, re.S)
    tnofocus = re.search(r"<texturenofocus([^>]*)>(.*?)</texturenofocus>", body, re.S)
    if not tfocus or not tnofocus:
        stats["skipped"] += 1
        return m.group(0)
    if ("colordiffuse=\"accent\"" not in tfocus.group(1)
            or "colordiffuse=\"text.primary\"" not in tnofocus.group(1)
            or tfocus.group(2).strip() != tnofocus.group(2).strip()):
        stats["skipped"] += 1
        return m.group(0)
    onclicks = re.findall(r"<onclick>(.*?)</onclick>", body, re.S)
    if len(onclicks) != 1:
        stats["skipped"] += 1
        return m.group(0)

    def esc(v):
        return v.replace("\"", "&quot;")

    inc = "OSDToggleButton" if kind == "togglebutton" else "OSDButton"
    p = [indent + "<include content=\"" + inc + "\">",
         indent + "\t<param name=\"id\" value=\"" + cid + "\" />",
         indent + "\t<param name=\"texture\" value=\"" + esc(tfocus.group(2).strip()) + "\" />"]
    if fields.get("label"):
        p.append(indent + "\t<param name=\"label\" value=\"" + esc(fields["label"]) + "\" />")
    p.append(indent + "\t<param name=\"onclick\" value=\"" + esc(onclicks[0].strip()) + "\" />")
    if kind == "togglebutton":
        altf = re.search(r"<alttexturefocus[^>]*>(.*?)</alttexturefocus>", body, re.S)
        p.append(indent + "\t<param name=\"alttexture\" value=\"" + esc(altf.group(1).strip()) + "\" />")
        if fields.get("altlabel"):
            p.append(indent + "\t<param name=\"altlabel\" value=\"" + esc(fields["altlabel"]) + "\" />")
        p.append(indent + "\t<param name=\"usealttexture\" value=\"" + esc(fields["usealttexture"]) + "\" />")
    if "visible" in fields:
        p.append(indent + "\t<param name=\"visible\" value=\"" + esc(fields["visible"]) + "\" />")
    p.append(indent + "</include>")
    stats["converted"] += 1
    return "\n".join(p)


def main():
    inc = BASE / "xml" / "includes.xml"
    s = inc.read_text(encoding="utf-8")
    if "OSDButton" not in s:
        s = s.replace("</includes>", OSD_BUTTON_INCLUDE + "</includes>")
        inc.write_text(s, encoding="utf-8")
        print("includes.xml: OSDButton + OSDToggleButton registered")
    for name in ("VideoOSD.xml", "MusicOSD.xml", "GameOSD.xml"):
        f = BASE / "xml" / name
        s = f.read_text(encoding="utf-8")
        stats = {"seen": 0, "converted": 0, "skipped": 0}
        s = BLOCK_RE.sub(lambda m: convert(m, stats), s)
        f.write_text(s, encoding="utf-8")
        print(name + ": " + str(stats["seen"]) + " blocks, " + str(stats["converted"])
              + " converted, " + str(stats["skipped"]) + " left as-is")


main()
