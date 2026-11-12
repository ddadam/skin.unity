#!/usr/bin/env python3
"""Generate the playback info row's media badges for the Unity skin.

Writes:
  xml/includes.xml               region "flag-labels": label lookups
  xml/IncludesCodecFlagging.xml  region "flag-row":    the badge row in playback (video.flags.info)
                                 region "flag-row-library": the same row for the focused library
                                 item (media.flags.small: library views, info screen, search)

Run from anywhere:  python3 tools/gen_flag_labels.py
Needs pycountry for the language table (pip install pycountry).

The badges are real text in Roboto Condensed Bold Italic (fonts flag.text /
flag.text.caps), the typeface of the old pre-drawn flag images, with the same
padding everywhere: [icon][7 px][text][7 px]. Every text segment is a disabled
button with auto width (disabled: it can never take focus in the fullscreen
video window). Every control carries an id: in testing, Kodi's grouplist
skipped id-less controls entirely. Filled badges use a solid fill so neighbouring segments join
without seams; outlined badges use flags/base 2.png (top and bottom lines only)
and the row's open ends get explicit thin cap segments.

What Kodi hands the skin during playback (checked against the Kodi 21 source):
  VideoPlayer.VideoCodec / AudioCodec  FFmpeg codec names (avcodec_get_name),
                                       DTS as dca / dtshd_ma / dtshd_hra
  VideoPlayer.AudioChannels            channel count ("6")
  VideoPlayer.VideoResolution          480 540 576 720 1080 4K 8K (or empty)
  VideoPlayer.AudioLanguage /
  VideoPlayer.SubtitlesLanguage        ISO 639-2/B ("eng", "ger"), "und" or empty
Library stream details (ListItem.*) use the same names plus some others (avc1, hvc1,
xvid ...); the tables cover both. ListItem.SubtitleLanguage is singular.
"""
import os
import re
import sys

# ---------------------------------------------------------------- lookups
# Labels follow the old flag artwork (media/flags/...) unless noted.
VIDEO_CODECS = {
    'H.264': ['h264', 'avc1', 'x264', 'hdmv'],          # avc1 showed "VC-1" in the old art: fixed
    'H.265': ['hevc', 'hev1', 'hvc1'],
    'H.266': ['vvc'],                                    # new
    'AV1': ['av1', 'libdav1d', 'av01'],                  # new
    'VP9': ['vp9', 'vp09'],                              # new
    'VP8': ['vp8'],                                      # new
    'VP6': ['vp6', 'vp6f', 'vp6a'],                      # old art said FLV
    'MPEG-1': ['mpeg1video'],
    'MPEG-2': ['mpeg2video', 'mpeg2', 'h262', 'v_mpeg2', 'hdv'],
    'MPEG-4': ['mpeg4', 'mp4v', 'fmp4', 'mpg4', 'msmpeg4v1', 'msmpeg4v2', 'msmpeg4v3', 'msmpeg4', 'mpeg-4 visual', 'mpeg4video'],
    'MPEG': ['mpeg video'],
    'H.263': ['h263', 'h263p', 'h263i'],
    'VC-1': ['vc1', 'wvc1', 'vc-1', 'wmv3image'],
    'WMV': ['wmv1', 'wmv2', 'wmv3', 'wmv'],
    'WMV HD': ['wmvhd'],
    'XVID': ['xvid'],
    'DIVX': ['divx', 'dx50', 'div3', 'div2', 'divx 4'],
    '3IVX': ['3iv2'],
    'FLV': ['flv1', 'flv', 'flash'],
    'THEORA': ['theora', 'oggtheora'],                   # old art said OGG
    'REAL': ['rv10', 'rv20', 'rv30', 'rv40', 'real'],
    'PRORES': ['prores'],                                # new
    'MJPEG': ['mjpeg'],                                  # new
    'DNXHD': ['dnxhd'],                                  # new
}
AUDIO_CODECS = {
    'AAC': ['aac', 'aac_latm'],
    'DOLBY': ['ac3', 'dolbydigital'],
    'DOLBY +': ['eac3', 'dolbydigitalplus'],
    'DOLBY HD': ['truehd', 'dolbytruehd'],
    'DTS': ['dca', 'dts', 'dtses', 'dtsex', 'dts9624'],
    'DTS HD': ['dtshd_ma', 'dtshd_hra', 'dtsma', 'dtshra', 'dtshd', 'dtsmsa-1'],
    'DTS:X': ['dtshd_ma_x'],                             # Kodi 22 (Blu-ray stream parsing)
    'DTS:X IMAX': ['dtshd_ma_x_imax'],                   # Kodi 22
    'FLAC': ['flac'],
    'ALAC': ['alac'],                                    # new
    'OPUS': ['opus'],                                    # new
    'VORBIS': ['vorbis'],                                # old art said OGG
    'MP3': ['mp3', 'mp3float'],
    'MP2': ['mp2', 'mp2float'],
    'MP1': ['mp1', 'mp1float'],
    'WMA': ['wmav1', 'wmav2', 'wma'],
    'WMA HD': ['wmapro', 'wmahd', 'wmalossless'],
    'REAL': ['ra_144', 'ra_288', 'cook', 'ra'],
}
# VideoPlayer.HdrType (empty for SDR); joins the resolution badge ("4K HDR10"). The badge font is
# uppercase, so only names that read badly need a label; others show as reported (hdr10, hlg).
HDR_TYPES = {
    'HDR10+': ['hdr10plus'],            # Kodi 22
}
# Two-line badges ("DOLBY" over "VISION"): our own type, not Dolby's logo. Kodi can't auto-size a
# two-label box, so the width is measured from the font file here.
STACKED_HDR = {'dolbyvision': ('DOLBY', 'VISION')}                   # after the resolution: "4K" + stack
STACKED_AUDIO = {'eac3_ddp_atmos': ('DOLBY +', 'ATMOS'),            # Kodi 22 (Blu-ray stream parsing)
                 'truehd_atmos': ('DOLBY HD', 'ATMOS')}
STACK_FONTS = (('flag.stack.top', 13), ('flag.stack.bottom', 10))   # must match xml/Font.xml
FONT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts', 'RobotoCondensed-BoldItalic.ttf')
AUDIO_PREFIXES = {'PCM': 'pcm'}                          # pcm_s16le, pcm_s24le, pcm_bluray ... (was "?")
CHANNELS = {'1': '1.0', '2': '2.0', '3': '2.1', '4': '4.0', '5': '4.1', '6': '5.1',
            '7': '6.1', '8': '7.1', '10': '9.1'}         # count only: 3 and 5 are ambiguous, kept as the old art
RESOLUTIONS = ['480', '540', '576', '720', '1080', '4K', '8K']
# Kodi rounds the aspect ratio to these values (CStreamDetails::VideoAspectToAspectDescription), in
# playback and in the library. Badges show the value; the info screen also shows the exact
# whole-number ratio, odd ones included on purpose ("47:20 (2.35)").
ASPECT_RATIOS = {'1.00': '1:1', '1.19': '19:16', '1.33': '4:3', '1.37': '11:8', '1.66': '5:3',
                 '1.78': '16:9', '1.85': '37:20', '2.00': '2:1', '2.20': '11:5', '2.35': '47:20',
                 '2.40': '12:5', '2.55': '51:20', '2.76': '69:25'}
UNDETERMINED = ['und', 'mis', 'zxx', 'unk']              # shown as "?"


def language_table():
    import pycountry
    table = {}
    for lang in pycountry.languages:
        a2 = getattr(lang, 'alpha_2', None)
        if not a2:
            continue
        for code in {lang.alpha_3, getattr(lang, 'bibliographic', None), a2}:
            if code:
                table[code.lower()] = a2.upper()
    return table


# ---------------------------------------------------------------- label variables
def _value(cond, text):
    return '\t<value condition="%s">%s</value>' % (cond, text)


def lookup_variable(name, info, mapping, fallback, prefixes=None, extra=()):
    lines = ['<variable name="%s">' % name]
    lines += list(extra)
    for label, ids in mapping.items():
        cond = ' | '.join('String.IsEqual(%s,%s)' % (info, i) for i in ids)
        lines.append(_value(cond, label))
    for label, prefix in (prefixes or {}).items():
        lines.append(_value('String.StartsWith(%s,%s)' % (info, prefix), label))
    lines += ['\t<value>%s</value>' % fallback, '</variable>']
    return lines


# Where the badge values come from: the playing video, or the focused library item
# (stream details stored when the library was scanned; same codec names as playback).
class Source:
    def __init__(self, info, var, subtitles):
        self.info, self.var, self.subtitles = info, var, subtitles

    def __call__(self, name):            # infolabel, e.g. VideoPlayer.AudioCodec
        return '%s.%s' % (self.info, name)


PLAYER = Source('VideoPlayer', 'Flag', 'SubtitlesLanguage')
LIBRARY = Source('ListItem', 'FlagLib', 'SubtitleLanguage')


def labels_for(src, langs):
    s, v = src, src.var
    out = []
    out += lookup_variable(v + 'VideoCodec', s('VideoCodec'), VIDEO_CODECS,
                           '$INFO[%s]' % s('VideoCodec'),
                           extra=[_value('String.IsEmpty(%s)' % s('VideoCodec'), '?')])
    out += lookup_variable(v + 'AudioCodec', s('AudioCodec'), AUDIO_CODECS,
                           '$INFO[%s]' % s('AudioCodec'), prefixes=AUDIO_PREFIXES,
                           extra=[_value('String.IsEmpty(%s)' % s('AudioCodec'), '?')])
    out += lookup_variable(v + 'AudioChannels', s('AudioChannels'),
                           {c: [k] for k, c in CHANNELS.items()}, '$INFO[%s]' % s('AudioChannels'),
                           extra=[_value('String.IsEmpty(%s)' % s('AudioChannels'), '?')])
    out += lookup_variable(v + 'Hdr', s('HdrType'), HDR_TYPES, '$INFO[%s]' % s('HdrType'))
    out += ['<variable name="%sAspect">' % v,
            _value('String.IsEmpty(%s)' % s('VideoAspect'), '?'),
            '\t<value>$INFO[%s]</value>' % s('VideoAspect'), '</variable>']
    if src is LIBRARY:     # info screen: "16:9 (1.78)"
        out += lookup_variable(v + 'AspectLong', s('VideoAspect'),
                               {'%s (%s)' % (r, k): [k] for k, r in ASPECT_RATIOS.items()},
                               '$INFO[%s]' % s('VideoAspect'),
                               extra=[_value('String.IsEmpty(%s)' % s('VideoAspect'), '?')])
    # stacked HDR types get their own segment; the label only carries the single-line ones
    hdr = '!String.IsEmpty(%s)' % s('HdrType') + ''.join(' + !String.IsEqual(%s,%s)' % (s('HdrType'), k) for k in STACKED_HDR)
    out += ['<variable name="%sResolution">' % v,
            _value('String.IsEmpty(%s) + String.IsEmpty(%s)' % (s('VideoResolution'), s('HdrType')), '?'),
            _value(hdr, '$INFO[%s,, ]$VAR[%sHdr]' % (s('VideoResolution'), v)),
            '\t<value>$INFO[%s]</value>' % s('VideoResolution'), '</variable>']
    for name, info in ((v + 'AudioLanguage', s('AudioLanguage')),
                       (v + 'SubtitleLanguage', s(src.subtitles))):
        by_code = {}
        for code, a2 in sorted(langs.items()):
            by_code.setdefault(a2, []).append(code)
        und = [_value(' | '.join(['String.IsEmpty(%s)' % info] + ['String.IsEqual(%s,%s)' % (info, c) for c in UNDETERMINED]), '?')]
        out += lookup_variable(name, info, by_code, '$INFO[%s]' % info, extra=und)
    return out


def labels(ind):
    langs = language_table()
    out = ['<!-- playback: the playing video -->'] + labels_for(PLAYER, langs)
    out += ['<!-- library views and info screen: the focused item -->'] + labels_for(LIBRARY, langs)
    return ''.join(ind + l + '\n' for l in out)


# ---------------------------------------------------------------- the row
ACCENT = '$INFO[Skin.String(color.500)]'
FILL = 'backgrounds/white.png'
LINES = 'flags/base 2.png'                 # top + bottom lines only
ICON_W = 26                                # 5 px lead + 21 px icon; the text's 7 px pad follows
PAD = 7
H = 27


def icon_segment(icon, filled, visible, colored_icon=None):
    icon_color = 'white' if filled else ACCENT
    if colored_icon is not None:
        icon_color = colored_icon
    return '''<control type="group" id="1">
	<width>{w}</width>
	<height>{h}</height>
	<visible>{vis}</visible>
	<control type="image" id="1">
		<width>{w}</width>
		<height>{h}</height>
		<texture>{bg}</texture>
		<colordiffuse>{acc}</colordiffuse>
	</control>
	<control type="image" id="1">
		<left>5</left>
		<top>3</top>
		<width>21</width>
		<height>21</height>
		<texture>{icon}</texture>
		<aspectratio>keep</aspectratio>
		<colordiffuse>{ic}</colordiffuse>
	</control>
</control>'''.format(w=ICON_W, h=H, vis=visible, bg=FILL if filled else LINES, acc=ACCENT, icon=icon, ic=icon_color)


def text_segment(label, filled, visible, font='flag.text.caps', pad=PAD):
    color = 'white' if filled else ACCENT
    tex = FILL if filled else LINES
    return '''<control type="button" id="1">
	<width min="10">auto</width>
	<height>{h}</height>
	<label>{label}</label>
	<font>{font}</font>
	<textcolor>{c}</textcolor>
	<disabledcolor>{c}</disabledcolor>
	<textoffsetx>{pad}</textoffsetx>
	<aligny>center</aligny>
	<texturefocus colordiffuse="{acc}">{tex}</texturefocus>
	<texturenofocus colordiffuse="{acc}">{tex}</texturenofocus>
	<enable>false</enable>
	<visible>{vis}</visible>
</control>'''.format(h=H, label=label, font=font, c=color, pad=pad, acc=ACCENT, tex=tex, vis=visible)


def stack_width(top, bottom):
    from PIL import ImageFont   # only needed when generating
    w = max(ImageFont.truetype(FONT_FILE, size).getlength(s) for s, (_, size) in zip((top, bottom), STACK_FONTS))
    return int(w + 0.999) + 2   # + italic overhang


def stack_segment(top, bottom, filled, visible, lpad=PAD):
    """Two-line badge text (fixed width, see STACKED_*): top line 13 px, bottom line 10 px."""
    color = 'white' if filled else ACCENT
    tex = FILL if filled else LINES
    tw = stack_width(top, bottom)
    return '''<control type="group" id="1">
	<width>{w}</width>
	<height>{h}</height>
	<visible>{vis}</visible>
	<control type="image" id="1">
		<width>{w}</width>
		<height>{h}</height>
		<texture colordiffuse="{acc}">{tex}</texture>
	</control>
	<control type="label" id="1">
		<left>{lpad}</left>
		<top>2</top>
		<width>{tw}</width>
		<height>13</height>
		<font>{f1}</font>
		<align>center</align>
		<aligny>center</aligny>
		<textcolor>{c}</textcolor>
		<label>{top}</label>
	</control>
	<control type="label" id="1">
		<left>{lpad}</left>
		<top>14</top>
		<width>{tw}</width>
		<height>11</height>
		<font>{f2}</font>
		<align>center</align>
		<aligny>center</aligny>
		<textcolor>{c}</textcolor>
		<label>{bottom}</label>
	</control>
</control>'''.format(w=lpad + tw + PAD, h=H, vis=visible, acc=ACCENT, tex=tex, lpad=lpad, tw=tw, c=color,
                     f1=STACK_FONTS[0][0], f2=STACK_FONTS[1][0], top=top, bottom=bottom)


def cap(visible):
    return '''<control type="image" id="1">
	<width>1.4</width>
	<height>{h}</height>
	<texture>{fill}</texture>
	<colordiffuse>{acc}</colordiffuse>
	<visible>{vis}</visible>
</control>'''.format(h=H, fill=FILL, acc=ACCENT, vis=visible)


def row(ind, src=PLAYER):
    s, v = src, src.var
    fps = '$EXP[OSDFpsKnown]' if src is PLAYER else None     # no frame rate in the library
    # Kodi turns 'und' into an empty language, so show the audio-language badge whenever there
    # is an audio track and let the language label say '?' (subtitles: empty also means 'none')
    alang = '!String.IsEmpty(%s)' % s('AudioCodec')
    slang = '!String.IsEmpty(%s)' % s(src.subtitles)
    aspect_label = '$VAR[%sAspect]' % v if src is PLAYER else '$PARAM[aspect]'
    stacked_audio_none = ' + '.join('!String.IsEqual(%s,%s)' % (s('AudioCodec'), k) for k in sorted(STACKED_AUDIO))
    parts = [
        '<!-- Generated by tools/gen_flag_labels.py - edit the script, not this block.',
        '     Badges: [icon][7][text][7]; filled and outlined badges alternate. -->',
    ]
    if fps:
        parts += [
            '<!-- left cap: the row starts with an outlined badge when no frame rate is shown -->',
            cap('![%s]' % fps),   # $EXP is pasted in unbracketed: negate it whole
            '<!-- frame rate (filled): icon, number, then a tick on a matching display or "@ xx Hz" (tools/gen_fps_flags.py) -->',
            icon_segment('flags/icon_fps.png', True, fps),
            text_segment('$VAR[OSDFpsBadgeLabel]', True, fps, font='flag.text'),
            '''<control type="group" id="1">
	<width>24</width>
	<height>{h}</height>
	<visible>{fps} + $EXP[OSDFpsMatch]</visible>
	<control type="image" id="1">
		<width>24</width>
		<height>{h}</height>
		<texture>{fill}</texture>
		<colordiffuse>{acc}</colordiffuse>
	</control>
	<control type="image" id="1">
		<top>4</top>
		<width>19</width>
		<height>19</height>
		<texture>flags/fps_match.png</texture>
		<aspectratio>keep</aspectratio>
	</control>
</control>'''.format(h=H, fps=fps, fill=FILL, acc=ACCENT)]
    else:
        parts += ['<!-- left cap: the row starts with an outlined badge -->', cap('true')]
    parts += [
        '<!-- resolution (outlined), with the HDR type when there is one: "4K HDR10" -->',
        icon_segment('flags/icon_resolution.png', False, 'true'),
        text_segment('$VAR[%sResolution]' % v, False, 'true'),
    ] + [stack_segment(a, b, False, 'String.IsEqual(%s,%s)' % (s('HdrType'), k), lpad=0)   # "4K" + DOLBY/VISION
         for k, (a, b) in sorted(STACKED_HDR.items())] + [
        '<!-- video codec (filled) -->',
        text_segment('$VAR[%sVideoCodec]' % v, True, 'true'),
        '<!-- aspect ratio (outlined): "2.40" ($PARAM[aspect] in the library: the info screen shows "12:5 (2.40)") -->',
        icon_segment('flags/icon_aspect.png', False, 'true'),
        text_segment(aspect_label, False, 'true', font='flag.text'),
        '<!-- audio codec (filled) -->',
        text_segment('$VAR[%sAudioCodec]' % v, True, stacked_audio_none),
    ] + [stack_segment(a, b, True, 'String.IsEqual(%s,%s)' % (s('AudioCodec'), k))
         for k, (a, b) in sorted(STACKED_AUDIO.items())] + [
        '<!-- audio channels (outlined) -->',
        icon_segment('flags/icon_channels.png', False, 'true'),
        text_segment('$VAR[%sAudioChannels]' % v, False, 'true'),
        '<!-- audio language (filled) -->',
        icon_segment('OSDAudioNF.png', True, alang),
        text_segment('$VAR[%sAudioLanguage]' % v, True, alang),
        '<!-- subtitle language: outlined after an audio language, filled when it is the first language -->',
        icon_segment('OSDSubtitlesNF.png', False, alang + ' + ' + slang),
        text_segment('$VAR[%sSubtitleLanguage]' % v, False, alang + ' + ' + slang),
        icon_segment('OSDSubtitlesNF.png', True, '!' + alang + ' + ' + slang),
        text_segment('$VAR[%sSubtitleLanguage]' % v, True, '!' + alang + ' + ' + slang),
        '<!-- right cap: the row ends with an outlined badge -->',
        cap('[%s + %s] | [!%s + !%s]' % (alang, slang, alang, slang)),
    ]
    text = '\n'.join(parts)
    return ''.join(ind + l + '\n' for l in text.split('\n'))


def library_row(ind):
    return row(ind, LIBRARY)


# ---------------------------------------------------------------- write
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
    seen = {}
    for table in (VIDEO_CODECS, AUDIO_CODECS):
        for label, ids in table.items():
            for i in ids:
                if (id(table), i) in seen:
                    sys.exit('duplicate codec id %s' % i)
                seen[(id(table), i)] = label
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xml')
    fill(os.path.join(root, 'includes.xml'), 'flag-labels', labels)
    fill(os.path.join(root, 'IncludesCodecFlagging.xml'), 'flag-row', row)
    fill(os.path.join(root, 'IncludesCodecFlagging.xml'), 'flag-row-library', library_row)
