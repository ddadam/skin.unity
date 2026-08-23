#!/usr/bin/env python3
"""Unity skin linter - validates the skin and fails on real errors."""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BASE = Path.cwd()
MEDIA = BASE / "media"
XML_DIRS = ("xml", "colors", "shortcuts", "extras")
XML_FILES = sorted(p for d in XML_DIRS for p in (BASE / d).rglob("*.xml"))

errors = []
warns = []
infos = []

NL = chr(10)
BSLASH = chr(92)

corpus_by_file = {f: f.read_text(encoding="utf-8", errors="ignore") for f in XML_FILES}
full_corpus = NL.join(corpus_by_file.values())

# 1) well-formed
for f, s in corpus_by_file.items():
    try:
        ET.fromstring(s)
    except Exception as e:
        errors.append("malformed XML: %s: %s" % (f, e))

# 2) textures
media_files = {p.relative_to(MEDIA).as_posix(): p for p in MEDIA.rglob("*") if p.is_file()}
media_lower = {k.lower(): k for k in media_files}

TEXT_RE = re.compile(r">([^<>{}\[\]$]*?\.(?:png|jpg|jpeg|gif))<", re.IGNORECASE)
ATTR_RE = re.compile(r"[ ](?:fallback|thumb)=.([^\x22${}]+?\.(?:png|jpg|jpeg|gif)).", re.IGNORECASE)


def check_texture(raw, where):
    path = raw.strip().replace(BSLASH, "/")
    if not path or path.startswith(("special://home", "special://xbmc", "resource://", "plugin://")):
        return
    path = re.sub(r"^special://skin/", "", path)
    path = re.sub(r"^special://profile/", "", path)
    if path.startswith(("extras/", "resources/")):
        if not (BASE / path).exists():
            errors.append("missing file: %s: %s" % (where, path))
        return
    key = path.lower()
    if key in media_lower:
        actual = media_lower[key]
        if actual != path:
            errors.append("CASE MISMATCH (breaks Linux): %s: xml='%s' disk='%s'" % (where, path, actual))
        return
    name = Path(path).name
    if name.lower() in media_lower:
        actual = media_lower[name.lower()]
        if actual != name:
            errors.append("CASE MISMATCH (breaks Linux): %s: xml='%s' disk='media/%s'" % (where, path, actual))
        else:
            infos.append("path differs from disk layout (resolves by filename): %s: '%s'" % (where, path))
        return
    if re.match(r"^(default|overlay|unknownuser)", name, re.IGNORECASE):
        infos.append("not in skin media - relies on Kodi core default: %s: '%s'" % (where, path))
        return
    errors.append("missing texture: %s: '%s'" % (where, path))


for f, s in corpus_by_file.items():
    rel = str(f.relative_to(BASE))
    for m in TEXT_RE.finditer(s):
        check_texture(m.group(1), rel)
    for m in ATTR_RE.finditer(s):
        check_texture(m.group(1), rel)

# 3) includes
defined = set(re.findall(r"<include[ ]+name=.([^\x22]+).", full_corpus))
used_plain = set(re.findall(r"<include(?:\s[^>]*)?>([^<>]+)</include>", full_corpus))
used_content = set(re.findall(r"<include[ ]+content=.([^\x22]+).", full_corpus))
used = {u for u in (used_plain | used_content) if "$PARAM" not in u and not u.startswith("skinshortcuts-")}
for u in sorted(used - defined):
    errors.append("undefined include used: '%s'" % u)
for d in sorted(defined - used_plain - used_content):
    infos.append("include defined but never used: '%s'" % d)

# 4) fonts
font_defs = set()
for f, s in corpus_by_file.items():
    m = re.search(r"<fonts>.*?</fonts>", s, re.S)
    if m:
        font_defs |= set(re.findall(r"<name>([^<]+)</name>", m.group(0)))
if not font_defs:
    warns.append("no <fonts> block found - font check skipped")
for f, s in corpus_by_file.items():
    for m in re.finditer(r"<font>([^<$]+)</font>", s):
        fname = m.group(1).strip()
        if fname and fname not in font_defs:
            errors.append("undefined font '%s' in %s" % (fname, f.relative_to(BASE)))

# 5) colours
colour_defs = set(re.findall(r"<color[ ]+name=.([^\x22]+).", full_corpus))
BUILTIN = {"white", "black", "grey", "grey2", "grey3", "blue", "red", "green",
           "yellow", "cyan", "magenta", "selected", "invalid"}
ATTR_COLOUR_RE = re.compile(
    r"[ ](?:colordiffuse|textcolor|focusedcolor|disabledcolor|selectedcolor|shadowcolor|alttextcolor)"
    r"=.([^\x22]*).")
HEX_RE = re.compile(r"^[0-9A-Fa-f]{8}$")
for f, s in corpus_by_file.items():
    rel = str(f.relative_to(BASE))
    for m in ATTR_COLOUR_RE.finditer(s):
        v = m.group(1).strip()
        if not v or HEX_RE.match(v) or "$" in v or "[" in v:
            continue
        if re.fullmatch(r"[a-z][a-z0-9_.]*", v) and v not in colour_defs | BUILTIN:
            errors.append("unknown colour name '%s' in %s" % (v, rel))

# 6) localize - skin strings; $ADDON[] ids belong to other addons, timeperimage is ms
po = BASE / "language" / "resource.language.en_gb" / "strings.po"
if po.exists():
    po_text = po.read_text(encoding="utf-8")
    po_ids = set(int(x) for x in re.findall(r"msgctxt .#([0-9]+).", po_text))
    refs = set(int(x) for x in re.findall(r"(?<![0-9])(3[0-9]{4})(?![0-9])", full_corpus))
    addon_ids = set()
    for m in re.finditer(r"\$ADDON\[[^\]]*?([0-9]{4,6})\]", full_corpus):
        addon_ids.add(int(m.group(1)))
    for line in full_corpus.splitlines():
        if "<timeperimage>" in line:
            for m in re.finditer(r"(?<![0-9])(3[0-9]{4})(?![0-9])", line):
                refs.discard(int(m.group(1)))
    for rid in sorted(refs - addon_ids - po_ids):
        entry = "skin string #%d referenced but missing from en_gb strings.po" % rid
        if 31000 <= rid <= 31999:
            errors.append(entry)
        else:
            warns.append(entry + " (outside skin range - verify core/addon provides it)")
else:
    warns.append("en_gb strings.po not found - localize check skipped")

# 7) duplicate ids
for f, s in corpus_by_file.items():
    ids = re.findall(r"<control type=.[^\x22]+. id=.([0-9]+).", s)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        warns.append("duplicate control ids in %s: %s (ok if mutually exclusive)"
                     % (f.relative_to(BASE), ", ".join(dupes)))

# 8) regression guards - keep the completed optimisations in place
#    background pruning: async loading (background="true") is reserved for
#    dynamic art ($INFO/$VAR content); static UI textures load inline.
#    NOTE: colours intentionally stay as per-frame $INFO[Skin.String(...)]
#    lookups - Kodi parses <color> definitions as raw hex only and never reads
#    a skin string to select theme files, so named-colour themes cannot work.
REGRESSION_FILES = [f for f in corpus_by_file if f.parts[0] in ("xml", "shortcuts")]
STATIC_ASYNC_RE = re.compile(
    r"<(texture|imagepath)\b[^>\n]*?\s+background=\"true\"[^>\n]*>([^<>\n]*)</\1>",
    re.IGNORECASE,
)
for f in REGRESSION_FILES:
    s = corpus_by_file[f]
    rel = str(f.relative_to(BASE))
    for m in STATIC_ASYNC_RE.finditer(s):
        if any(ch in m.group(2) for ch in "$[{"):
            continue
        ln = s.count(NL, 0, m.start()) + 1
        errors.append("background=\"true\" on static texture (async loading is for dynamic art only): %s:%d"
                      % (rel, ln))

#    c) colour mechanism: semantic theme names must never be referenced -
#       core parses <color> definitions as raw hex and ignores skin strings,
#       so a named reference silently renders the static red default
SEMANTIC_COLOURS = ("accent.dark", "accent.light", "surface.primary", "surface.secondary",
                    "text.disabled", "text.primary", "accent.alt", "accent", "border")
for f in REGRESSION_FILES:
    s = corpus_by_file[f]
    rel = str(f.relative_to(BASE))
    for name in SEMANTIC_COLOURS:
        for token in ('="%s"' % name, ">%s<" % name):
            idx = s.find(token)
            while idx != -1:
                errors.append("static named colour '%s' (use $INFO[Skin.String(...)] lookups): %s:%d"
                              % (name, rel, s.count(NL, 0, idx) + 1))
                idx = s.find(token, idx + 1)

print("== Unity skin lint: %d errors, %d warnings, %d infos ==" % (len(errors), len(warns), len(infos)))
for e in errors:
    print("ERROR:", e)
for w in warns:
    print("WARN :", w)
for i in infos:
    print("INFO :", i)
sys.exit(1 if errors else 0)
