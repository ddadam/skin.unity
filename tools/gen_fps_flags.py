#!/usr/bin/env python3
"""Generate the frame-rate badge lookups for the Unity skin.

Writes variables and expressions between
    <!-- BEGIN generated: fps-match ... -->   and   <!-- END generated: fps-match -->
in xml/includes.xml. Run from anywhere:  python3 tools/gen_fps_flags.py

A skin can only compare strings, so the arithmetic is done here:

  * Kodi reports the frame rate as Player.Process(videofps), formatted "%.3f"
    ("23.976", "25.000"). It may replace the nominal rate with a measured one
    ("23.975"), so each standard rate accepts a narrow window of strings.
  * Kodi reports the display as System.ScreenResolution:
    "1920x1080 @ 23.98 Hz - Full screen" (refresh "%.2f"; no refresh at all
    when windowed). Each standard refresh rate also accepts a narrow window.
  * A display rate matches when it is a whole multiple of the frame rate
    (25 fps on 50 Hz, 23.976 fps on 119.88 Hz). Near misses such as 23.976 fps
    on 24.00 / 120.00 Hz (0.1 % off: a dropped or repeated frame every ~40 s)
    or 24 fps on 60 Hz (2.5x: 3:2 judder) do not.

Outputs:
  $VAR[OSDFpsLabel]      "23.976", "24", "25", ... (raw value for unusual rates)
  $VAR[OSDRefreshLabel]  "23.98", "60", "119.88", ...
  $VAR[OSDFpsBadgeLabel] badge text: "23.976", or "23.976 @ 60 Hz" on a mismatch
                         (one label, thin spaces around the @)
  $EXP[OSDFpsKnown]      a frame rate is being reported
  $EXP[OSDFpsMatch]      known frame rate + known refresh rate, whole multiple
  $EXP[OSDFpsMismatch]   known frame rate + known refresh rate, not a multiple
(Unusual frame rates or refresh rates are neither match nor mismatch.)
"""
import os
import re
import sys
from fractions import Fraction as Fr

# Standard content frame rates (name shown on the badge, exact value)
FRAME_RATES = [
    ('23.976', Fr(24000, 1001)), ('24', Fr(24)), ('25', Fr(25)),
    ('29.97', Fr(30000, 1001)), ('30', Fr(30)), ('47.952', Fr(48000, 1001)),
    ('48', Fr(48)), ('50', Fr(50)), ('59.94', Fr(60000, 1001)), ('60', Fr(60)),
    ('100', Fr(100)), ('119.88', Fr(120000, 1001)), ('120', Fr(120)),
]
# Display refresh rates TVs and monitors commonly offer
REFRESH_RATES = [
    ('23.98', Fr(24000, 1001)), ('24', Fr(24)), ('25', Fr(25)), ('29.97', Fr(30000, 1001)),
    ('30', Fr(30)), ('47.95', Fr(48000, 1001)), ('48', Fr(48)), ('50', Fr(50)),
    ('59.94', Fr(60000, 1001)), ('60', Fr(60)), ('71.93', Fr(72000, 1001)), ('72', Fr(72)),
    ('75', Fr(75)), ('90', Fr(90)), ('96', Fr(96)), ('100', Fr(100)),
    ('119.88', Fr(120000, 1001)), ('120', Fr(120)), ('143.86', Fr(144000, 1001)), ('144', Fr(144)),
    ('165', Fr(165)), ('200', Fr(200)), ('239.76', Fr(240000, 1001)), ('240', Fr(240)),
]
WINDOW = Fr(3, 10000)      # +-0.03 % accepted around each standard rate (keeps 23.976 and 24 apart)
MATCH_TOL = Fr(5, 10000)   # a refresh rate within 0.05 % of n x frame rate is a match

FPS = 'Player.Process(videofps)'
RES = 'System.ScreenResolution'


def strings_in_window(value, decimals):
    """All strings Kodi could print ("%.{decimals}f") for a rate within the window."""
    step = Fr(1, 10 ** decimals)
    lo, hi = value * (1 - WINDOW), value * (1 + WINDOW)
    k = -(-lo // step)                   # ceil
    out = []
    while k * step <= hi:
        out.append('%.*f' % (decimals, float(k * step)))
        k += 1
    return out


def fps_is(value):
    return '[%s]' % ' | '.join('String.IsEqual(%s,%s)' % (FPS, s) for s in strings_in_window(value, 3))


def refresh_is(value):
    return '[%s]' % ' | '.join('String.Contains(%s,@ %s Hz)' % (RES, s) for s in strings_in_window(value, 2))


def matches(fps, hz):
    n = round(hz / fps)
    return n >= 1 and abs(hz - n * fps) <= MATCH_TOL * n * fps


def check_windows():
    for rates, dec in ((FRAME_RATES, 3), (REFRESH_RATES, 2)):
        seen = {}
        for name, v in rates:
            for s in strings_in_window(v, dec):
                if s in seen:
                    sys.exit('window overlap: %s is in both %s and %s' % (s, seen[s], name))
                seen[s] = name


def generate(ind):
    out = []
    # badge labels
    out.append('<variable name="OSDFpsLabel">')
    out += ['\t<value condition="%s">%s</value>' % (fps_is(v), name) for name, v in FRAME_RATES]
    out += ['\t<value>$INFO[%s]</value>' % FPS, '</variable>']
    out.append('<variable name="OSDRefreshLabel">')
    out += ['\t<value condition="%s">%s</value>' % (refresh_is(v), name) for name, v in REFRESH_RATES]
    out.append('</variable>')
    thin = '\u2009'   # thin space (Roboto has it): "23.976 @ 60 Hz" without a wide gap
    out += ['<variable name="OSDFpsBadgeLabel">',
            '\t<value condition="$EXP[OSDFpsMismatch]">$VAR[OSDFpsLabel]%s@%s$VAR[OSDRefreshLabel] Hz</value>' % (thin, thin),
            '\t<value>$VAR[OSDFpsLabel]</value>', '</variable>']
    # per-rate expressions, so the match table stays readable
    for name, v in FRAME_RATES:
        out.append('<expression name="OSDFps_%s">%s</expression>' % (name.replace('.', '_'), fps_is(v)))
    for name, v in REFRESH_RATES:
        out.append('<expression name="OSDHz_%s">%s</expression>' % (name.replace('.', '_'), refresh_is(v)))
    exp_f = lambda n: '$EXP[OSDFps_%s]' % n.replace('.', '_')
    exp_h = lambda n: '$EXP[OSDHz_%s]' % n.replace('.', '_')
    out.append('<expression name="OSDFpsKnown">[!String.IsEmpty(%s) + !String.IsEqual(%s,0.000)]</expression>'
               % (FPS, FPS))
    out.append('<expression name="OSDFpsStandard">[%s]</expression>' % ' | '.join(exp_f(n) for n, _ in FRAME_RATES))
    out.append('<expression name="OSDRefreshStandard">[%s]</expression>' % ' | '.join(exp_h(n) for n, _ in REFRESH_RATES))
    pairs = []
    for fname, fv in FRAME_RATES:
        hz = [hname for hname, hv in REFRESH_RATES if matches(fv, hv)]
        if hz:
            pairs.append('[%s + [%s]]' % (exp_f(fname), ' | '.join(exp_h(h) for h in hz)))
    out.append('<expression name="OSDFpsMatch">[%s]</expression>' % ' | '.join(pairs))
    out.append('<expression name="OSDFpsMismatch">[$EXP[OSDFpsStandard] + $EXP[OSDRefreshStandard] + !$EXP[OSDFpsMatch]]</expression>')
    return ''.join(ind + l + '\n' for l in out)


def fill(path, name, generator):
    text = open(path, encoding='utf8').read()
    pat = re.compile(r'([ \t]*)(<!-- BEGIN generated: %s(?= )[^>]*-->\n)(.*?)([ \t]*<!-- END generated: %s -->)'
                     % (re.escape(name), re.escape(name)), re.S)
    m = pat.search(text)
    if not m or len(pat.findall(text)) != 1:
        sys.exit('marker "%s" not found exactly once in %s' % (name, path))
    new = text[:m.start()] + m.group(1) + m.group(2) + generator(m.group(1)) + m.group(4) + text[m.end():]
    if new != text:
        open(path, 'w', encoding='utf8').write(new)
    print('%-22s %s' % (name, 'updated' if new != text else 'unchanged'))


if __name__ == '__main__':
    check_windows()
    if '--table' in sys.argv:          # print the match table for review
        for fname, fv in FRAME_RATES:
            print('%-7s fps -> %s' % (fname, ' '.join(h for h, hv in REFRESH_RATES if matches(fv, hv))))
        sys.exit()
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xml')
    fill(os.path.join(root, 'includes.xml'), 'fps-match', generate)
