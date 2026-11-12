#!/usr/bin/env python3
"""Generate the playback-speed XML for the Unity skin.

Rewrites the regions between
    <!-- BEGIN generated: NAME ... -->   and   <!-- END generated: NAME -->
in xml/VideoOSD.xml, xml/SkinSettings.xml, xml/includes.xml and xml/Timers.xml.
(Startup.xml, Home.xml and VideoOSD.xml use <include>OSDSpeedDefaults</include>.)

Edit SPEEDS / DEFAULTS / HIGH_LIMIT below, then run:
    python3 tools/gen_speed_menu.py
from the skin's root folder. Running it twice gives the same result.

Kodi facts this relies on (checked against the Kodi 21 source):
  * tempo must be > 0.75 and < 1.55, or < <maxtempo> from advancedsettings.xml
  * Player.PlaySpeed is formatted with two decimals ("1.25", "0.80")
  * conditional <onup> entries: the first one whose condition is true wins
  * all <onload>/<onclick> conditions are evaluated before any action runs
  * PlayerControl(Tempo(x)) is ignored while paused, and Player.PlaySpeed reads
    "0.00" while paused (the tempo is kept, but no infolabel shows it)

Speed while paused (skin timers, Kodi 20+, xml/Timers.xml):
  * Window(Home).Property(OSDTempo) remembers the last speed seen while playing,
    so the menu can tick it and the button can show it while paused.
  * Picking a speed while paused stores it in OSDPendingTempo (with the file name
    in OSDPendingFile); a timer applies it as soon as normal playback resumes,
    and another drops it if a different file (or nothing) is playing by then.
  * $EXP is not resolved in Timers.xml, so the timers get conditions written out.
"""
import os
import re
import sys

SPEEDS = [round(0.80 + 0.05 * i, 2) for i in range(25)]   # 0.80 .. 2.00
NORMAL = 1.00                                              # always in the menu
DEFAULTS = [0.80, 0.90, 1.10, 1.20, 1.30, 1.40, 1.50]      # besides Normal
HIGH_LIMIT = 1.50              # above this needs maxtempo + OSDShowHighSpeeds
HIGH_SETTING = 'OSDShowHighSpeeds'
DEFAULTS_FLAG = 'OSDSpeedDefaultsSet'

OSD_ROW_ID = 1600              # OSD menu rows: 1600 + index
OSD_ROW_GROUP_ID = 1650        # their wrapper groups (grouplists link neighbours by ID)
SETTINGS_ROW_ID = 610          # Skin Settings toggles: 610 + index
MENU_GROUPLIST = 580
MENU_MAX_ROWS = 10             # rows visible before the menu scrolls

ROW_H = 70
HEADER_H = 80
# The menu shows while it has focus, or while the speed button has focus after the
# menu was opened (mouse: after clicking, the pointer is still over the button and
# re-focuses it on the first move). SpeedMenuOpen is set when opening and cleared
# when picking a speed, leaving the button/menu with the remote, or closing the OSD.
OPEN_PROP = 'SpeedMenuOpen'
SET_OPEN = 'SetProperty(%s,1,videoosd)' % OPEN_PROP
CLEAR_OPEN = 'ClearProperty(%s,videoosd)' % OPEN_PROP
MENU_OPEN = ('[ControlGroup(%d).HasFocus | [Control.HasFocus(256) + !String.IsEmpty(Window(videoosd).Property(%s))]]'
             % (MENU_GROUPLIST, OPEN_PROP))
HINT_GROUP_ID = 1675           # "Choose speeds in Skin Settings" row, shown when only Normal is enabled
HINT_ID = 1676
CATCHER_ID = 1700              # invisible mouse catchers: 1699 header, 1700 + index rows, 1700 + len hint

TEMPO_PROP = 'Window(Home).Property(OSDTempo)'          # last speed seen while playing
PENDING_PROP = 'Window(Home).Property(OSDPendingTempo)' # picked while paused, applied on resume
PENDING_FILE = 'Window(Home).Property(OSDPendingFile)'  # ...for this file only


def key(s):
    return '%03d' % round(s * 100)          # 0.85 -> "085"


def setting(s):
    return 'OSDSpeed' + key(s)


def fmt(s):
    return '%.2f' % s                        # matches Player.PlaySpeed


def label(s):
    t = ('%.2f' % s).rstrip('0')
    if t.endswith('.'):
        t += '0'
    return t + '×'                           # 0.80 -> "0.8×", 1.25 -> "1.25×"


def playing_at(s):
    """Raw condition: playing (not paused, not fast-forwarding) at speed s. Player.IsTempo
    keeps the 2.00 row from lighting up during 2x fast-forward."""
    if s == NORMAL:
        return 'String.IsEqual(Player.PlaySpeed,%s)' % fmt(s)
    return 'Player.IsTempo + String.IsEqual(Player.PlaySpeed,%s)' % fmt(s)


def speed_is(s):
    """$EXP name: the current speed is s - while paused, the remembered or pending one."""
    return '$EXP[OSDSpeedIs%s]' % key(s)


def speed_is_body(s):
    return '[[!Player.Paused + %s] | [Player.Paused + String.IsEqual(%s,%s)]]' % (
        playing_at(s), TEMPO_PROP, fmt(s))


def shown(s):
    """Condition under which speed s appears in the OSD menu."""
    if s == NORMAL:
        return None
    cond = 'Skin.HasSetting(%s)' % setting(s)
    if s > HIGH_LIMIT:
        cond += ' + Skin.HasSetting(%s)' % HIGH_SETTING
    return cond


def osd_onup(ind):
    lines = ['<onup condition="!Player.TempoEnabled">1000</onup>',
             '<onup condition="Player.TempoEnabled">%s</onup>' % SET_OPEN]
    for i, s in enumerate(SPEEDS):
        if s == NORMAL:
            continue
        lines.append('<onup condition="Player.TempoEnabled + %s + %s">%d</onup>'
                     % (shown(s), speed_is(s), OSD_ROW_ID + i))
    lines.append('<!-- fallback: current speed not in the menu -> Normal -->')
    lines.append('<onup>%d</onup>' % (OSD_ROW_ID + SPEEDS.index(NORMAL)))
    return ''.join(ind + l + '\n' for l in lines)


def osd_menu(ind):
    """The OSD speed menu.

    Navigation: every row links straight to the previous/next *visible* row via
    conditional <onup>/<ondown> (first matching integer wins), so the remote never
    walks through hidden rows or onto the header. ClearProperty actions carry the
    same condition as the move to the speed button, because Kodi runs every
    builtin whose condition is true, whichever way focus moves.

    Mouse: Kodi drops focus when the pointer is over something unfocusable
    (CGUIWindow::UnfocusFromPoint), and the menu only shows while focused. Each
    row, the header and the hint row therefore have an invisible full-size
    "catcher" button underneath. Catchers sit before the visible button in their
    group, so the visible button still wins hit-testing where they overlap, and
    no keyboard link ever points at a catcher."""
    height = HEADER_H + MENU_MAX_ROWS * ROW_H
    n = len(SPEEDS)
    none_chosen = '![%s]' % ' | '.join('[%s]' % shown(s) for s in SPEEDS if s != NORMAL)

    def links(direction, i):
        tag = 'onup' if direction < 0 else 'ondown'
        out, conds = [], []
        j = i + direction
        while 0 <= j < n:
            c = shown(SPEEDS[j])
            if c is None:                                   # Normal: always visible, stop here
                out.append('<%s>%d</%s>' % (tag, OSD_ROW_ID + j, tag))
                return out
            out.append('<%s condition="%s">%d</%s>' % (tag, c, OSD_ROW_ID + j, tag))
            conds.append(c)
            j += direction
        if direction > 0:                                   # below the last speed: the hint row, if shown
            out.append('<%s condition="%s">%d</%s>' % (tag, none_chosen, HINT_ID, tag))
            conds.append(none_chosen)                       # i.e. the hint row is shown
        nothing = ' + '.join('![%s]' % c for c in conds) if conds else None
        cond = ' condition="%s"' % nothing if nothing else ''
        out.append('<%s%s>%s</%s>' % (tag, cond, CLEAR_OPEN, tag))
        out.append('<%s>256</%s>' % (tag, tag))
        return out

    def catcher(cid, h, target_up, target_down):
        return """		<control type="button" id="{id}">
			<description>mouse catcher</description>
			<width>365</width>
			<height>{h}</height>
			<label></label>
			<font></font>
			<texturefocus />
			<texturenofocus />
			<onup>{u}</onup>
			<ondown>{d}</ondown>
			<onleft>{d}</onleft>
			<onright>{d}</onright>
		</control>
""".format(id=cid, h=h, u=target_up, d=target_down)

    def bg(h):
        return """		<control type="image">
			<width>365</width>
			<height>{h}</height>
			<texture colordiffuse="$INFO[Skin.String(color.tertiary)]">backgrounds/white.png</texture>
		</control>
""".format(h=h)

    sep = '\n\t\t\t'
    rows = ''
    for i, s in enumerate(SPEEDS):
        vis = shown(s)
        vis_xml = '\n\t\t<visible>%s</visible>' % vis if vis else ''
        rid = OSD_ROW_ID + i
        rows += """	<control type="group" id="{gid}">
		<width>365</width>
		<height>{h}</height>{vis}
{bg}{catcher}		<control type="radiobutton" id="{id}">
			<left>15</left>
			<width>335</width>
			<include>ButtonCommonValues</include>
			<label>{lab}</label>
			{nav}
			<onclick>{clear}</onclick>
			<onclick condition="!Player.Paused">PlayerControl(Tempo({cmd}))</onclick>
			<!-- paused: Kodi ignores tempo changes, so keep it for when playback resumes (Timers.xml) -->
			<onclick condition="Player.Paused">SetProperty(OSDPendingTempo,{cmd},home)</onclick>
			<onclick condition="Player.Paused">SetProperty(OSDPendingFile,"$INFO[Player.Filename]",home)</onclick>
			<onclick condition="Player.Paused">SetProperty(OSDTempo,{cmd},home)</onclick>
			<onclick>SetFocus(256)</onclick>
			<selected>{sel}</selected>
		</control>
	</control>
""".format(gid=OSD_ROW_GROUP_ID + i, h=ROW_H, vis=vis_xml, bg=bg(ROW_H),
           catcher=catcher(CATCHER_ID + i, ROW_H, rid, rid), id=rid,
           lab='31962' if s == NORMAL else label(s),
           nav=sep.join(links(-1, i) + links(+1, i)), clear=CLEAR_OPEN, cmd=fmt(s), sel=speed_is(s))

    normal_id = OSD_ROW_ID + SPEEDS.index(NORMAL)
    header = """	<control type="group" id="{hid}">
		<description>Header</description>
		<width>365</width>
		<height>{hh}</height>
{bg}{catcher}		<control type="image">
			<width>365</width>
			<height>70</height>
			<texture colordiffuse="$INFO[Skin.String(color.500)]">backgrounds/white.png</texture>
		</control>
		<control type="image">
			<top>70</top>
			<width>365</width>
			<height>10</height>
			<texture>homeshadow.png</texture>
			<animation effect="fade" start="100" end="75" time="0" condition="true">Conditional</animation>
		</control>
		<control type="label">
			<left>15</left>
			<top>3</top>
			<width>335</width>
			<height>60</height>
			<label>31961</label>
			<textcolor>white</textcolor>
			<aligny>center</aligny>
		</control>
	</control>
""".format(hid=OSD_ROW_GROUP_ID - 1, hh=HEADER_H, bg=bg(HEADER_H),
           catcher=catcher(CATCHER_ID - 1, HEADER_H, normal_id, normal_id))

    hint = """	<!-- only Normal enabled: point to the settings page -->
	<control type="group" id="{gid}">
		<width>365</width>
		<height>{h}</height>
		<visible>{none}</visible>
{bg}{catcher}		<control type="button" id="{id}">
			<left>15</left>
			<width>335</width>
			<include>ButtonCommonValues</include>
			<label>31972</label>
			<onup>{normal}</onup>
			<ondown>{clear}</ondown>
			<ondown>256</ondown>
			<onclick>{clear}</onclick>
			<onclick>SetProperty(OpenSpeedSettings,1,home)</onclick>
			<!-- the OSD is modal: Kodi refuses to open a window over it -->
			<onclick>Dialog.Close(videoosd,true)</onclick>
			<onclick>ActivateWindow(SkinSettings)</onclick>
		</control>
	</control>
""".format(gid=HINT_GROUP_ID, h=ROW_H, none=none_chosen, bg=bg(ROW_H),
           catcher=catcher(CATCHER_ID + n, ROW_H, HINT_ID, HINT_ID), id=HINT_ID,
           normal=normal_id, clear=CLEAR_OPEN)

    xml = """<!-- Playback speed menu (not for LiveTV). Bottom-aligned grouplist
     (align=right on a vertical grouplist), so it always sits on the OSD bar
     however many speeds are enabled; scrolls beyond {maxrows} rows. -->
<control type="grouplist" id="{gl}">
	<visible>!VideoPlayer.Content(LiveTV) + Player.TempoEnabled</visible>
	<animation effect="slide" start="0,0" end="1462,0" time="300" condition="![{menu_open}]">Conditional</animation>
	<right>10</right>
	<bottom>80</bottom>
	<width>365</width>
	<height>{height}</height>
	<align>right</align>
	<itemgap>0</itemgap>
	<onleft>{gl}</onleft>
	<onright>{gl}</onright>
	<onup>{clear}</onup>
	<onup>256</onup>
	<ondown>{clear}</ondown>
	<ondown>256</ondown>
	<orientation>vertical</orientation>
""".format(gl=MENU_GROUPLIST, menu_open=MENU_OPEN, clear=CLEAR_OPEN, height=height, maxrows=MENU_MAX_ROWS)
    xml += header + rows + hint + '</control>\n'
    return ''.join(ind + l + '\n' if l else '\n' for l in xml.rstrip('\n').split('\n'))


def set_defaults_actions():
    """(condition, action) pairs. Each Skin.* builtin writes the settings file, so only
    the settings that differ from the defaults are touched."""
    acts = [('Skin.HasSetting(%s)' % setting(s), 'Skin.Reset(%s)' % setting(s))
            for s in SPEEDS if s != NORMAL and s not in DEFAULTS]
    acts += [('!Skin.HasSetting(%s)' % setting(s), 'Skin.SetBool(%s)' % setting(s)) for s in DEFAULTS]
    return acts


def settings_panel(ind):
    """Skin Settings category 6. Speeds above HIGH_LIMIT get their own sub-section
    with the maxtempo explanation and unlock toggle. While locked those rows are
    faded but stay focusable (disabled controls can't be focused, so a remote
    could never scroll down to them); selecting one shows a notification."""
    gl = 9005
    reset = ''.join('\t\t<onclick condition="%s">%s</onclick>\n' % ca for ca in set_defaults_actions())
    unlocked = 'Skin.HasSetting(%s)' % HIGH_SETTING

    def heading(cid, string):
        return '''	<control type="label" id="{id}">
		<width>995</width>
		<height>60</height>
		<font>button.bold</font>
		<textcolor>$INFO[Skin.String(color.500)]</textcolor>
		<textoffsetx>5</textoffsetx>
		<aligny>center</aligny>
		<label>{s}</label>
	</control>
'''.format(id=cid, s=string)

    def text(cid, string, height):
        return '''	<control type="group" id="{id}">
		<width>995</width>
		<height>{h}</height>
		<control type="textbox">
			<left>5</left>
			<width>985</width>
			<height>{h}</height>
			<font>font12</font>
			<textcolor>$INFO[Skin.String(color.text)]</textcolor>
			<label>{s}</label>
		</control>
	</control>
'''.format(id=cid, h=height, s=string)

    def toggle(i, s):
        cid = SETTINGS_ROW_ID + i
        if s == NORMAL:
            return '''	<control type="radiobutton" id="{id}">
		<width>995</width>
		<label>$LOCALIZE[31962] (1.0×) - $LOCALIZE[31966]</label>
		<selected>true</selected>
		<enable>false</enable>
	</control>
'''.format(id=cid)
        if s <= HIGH_LIMIT:
            click = '<onclick>Skin.ToggleSetting(%s)</onclick>' % setting(s)
            lock = ''
        else:
            click = ('<onclick condition="{u}">Skin.ToggleSetting({st})</onclick>\n'
                     '\t\t<onclick condition="!{u}">Notification($LOCALIZE[31961],"$LOCALIZE[31970]",6000)</onclick>'
                     ).format(u=unlocked, st=setting(s))
            lock = ('\n\t\t<animation effect="fade" start="100" end="40" time="0" '
                    'condition="!%s">Conditional</animation>' % unlocked)
        return '''	<control type="radiobutton" id="{id}">
		<width>995</width>
		<label>{lab}</label>
		{click}
		<selected>Skin.HasSetting({st})</selected>{lock}
	</control>
'''.format(id=cid, lab=label(s), click=click, st=setting(s), lock=lock)

    normal_rows = ''.join(toggle(i, s) for i, s in enumerate(SPEEDS) if s <= HIGH_LIMIT)
    high_rows = ''.join(toggle(i, s) for i, s in enumerate(SPEEDS) if s > HIGH_LIMIT)
    requirement = '''	<control type="button" id="608">
		<width>995</width>
		<label>31971</label>
		<label2>$VAR[OSDSyncStatusLabel]</label2>
		<onclick>ActivateWindow(PlayerSettings)</onclick>
	</control>
'''
    body = (heading(600, 31961) + text(606, 31964, 45) + requirement +
            '''	<control type="button" id="603">
		<width>995</width>
		<label>31965</label>
{reset}	</control>
'''.format(reset=reset) +
            heading(604, 31967) + normal_rows +
            heading(605, 31968) + text(607, 31969, 100) +
            '''	<control type="radiobutton" id="602">
		<width>995</width>
		<label>31963</label>
		<onclick>Skin.ToggleSetting({hs})</onclick>
		<selected>Skin.HasSetting({hs})</selected>
	</control>
'''.format(hs=HIGH_SETTING) + high_rows)
    xml = '''<!-- playback speed options -->
<control type="grouplist" id="{gl}">
	<include condition="$EXP[MouseScrollNoAnimation]">GroupListMouseScroll</include>
	<visible>Container(9000).Hasfocus(6)</visible>
	<left>385</left>
	<top>120</top>
	<width>995</width>
	<height>645</height>
	<itemgap>5</itemgap>
	<pagecontrol>60</pagecontrol>
	<onleft>9000</onleft>
	<onright>60</onright>
	<onup>{gl}</onup>
	<ondown>{gl}</ondown>
{body}</control>
<!--scrollbar-->
<control type="scrollbar" id="60">
	<left>1395</left>
	<top>110</top>
	<height>673</height>
	<onleft>{gl}</onleft>
	<onright>{gl}</onright>
	<visible>Container(9000).Hasfocus(6)</visible>
</control>
'''.format(gl=gl, body=body)
    return ''.join(ind + l + '\n' for l in xml.rstrip('\n').split('\n'))


def speed_label(ind):
    """$EXP[OSDSpeedIsXXX], $EXP[OSDSpeedChanged] and $VAR[OSDSpeedLabel] (the OSD
    button's text, formatted like the menu rows). Expression bodies are bracketed:
    Kodi pastes $EXP in as plain text, so '!$EXP[..]' would otherwise negate only
    the first term."""
    lines = ['<expression name="OSDSpeedIs%s">%s</expression>' % (key(s), speed_is_body(s)) for s in SPEEDS]
    lines += ['<!-- speed button shows a number instead of the icon -->',
              '<expression name="OSDSpeedChanged">[Player.IsTempo | [Player.Paused + !String.IsEmpty(%s) + '
              '!String.IsEqual(%s,%s)]]</expression>' % (TEMPO_PROP, TEMPO_PROP, fmt(NORMAL))]
    lines += ['<variable name="OSDSpeedLabel">']
    lines += ['\t<value condition="%s">%s</value>' % (speed_is(s), label(s)) for s in SPEEDS if s != NORMAL]
    lines += ['\t<value condition="Player.Paused">$INFO[%s,,×]</value>' % TEMPO_PROP,
              '\t<value>$INFO[Player.PlaySpeed,,×]</value>', '</variable>',
              '<variable name="OSDSyncStatusLabel">',
              '\t<value condition="System.GetBool(videoplayer.usedisplayasclock)">$LOCALIZE[31973]</value>',
              '\t<value>$LOCALIZE[31974]</value>', '</variable>']
    return ''.join(ind + l + '\n' for l in lines)


def defaults_include(ind):
    """<include name="OSDSpeedDefaults">: one-time defaults, used by Startup, Home and
    VideoOSD. Startup alone isn't enough: installing a skin update reloads the skin
    without showing the startup window."""
    flag = '!Skin.HasSetting(%s)' % DEFAULTS_FLAG
    lines = ['<include name="OSDSpeedDefaults">',
             '\t<!-- first run only: enable the default playback speeds -->']
    lines += ['\t<onload condition="%s">Skin.SetBool(%s)</onload>' % (flag, setting(s)) for s in DEFAULTS]
    lines += ['\t<onload condition="%s">Skin.SetBool(%s)</onload>' % (flag, DEFAULTS_FLAG), '</include>']
    return ''.join(ind + l + '\n' for l in lines)


def timers(ind):
    """Skin timers (xml/Timers.xml). A timer runs its <onstart> once when <start> becomes
    true and is re-armed when <stop> becomes true, so every stop is the start's opposite."""
    def timer(name, start, onstart, comment=None):
        out = ['<!-- %s -->' % comment] if comment else []
        out += ['<timer>', '\t<name>%s</name>' % name, '\t<start>%s</start>' % start,
                '\t<stop>![%s]</stop>' % start]
        out += ['\t<onstart>%s</onstart>' % a for a in onstart]
        return out + ['</timer>']

    resumed = 'Player.HasVideo + !Player.Paused + !Player.Forwarding + !Player.Rewinding'
    same_file = 'String.IsEqual(Player.Filename,%s)' % PENDING_FILE
    pending = '!String.IsEmpty(%s)' % PENDING_PROP
    lines = []
    for s in SPEEDS:
        lines += timer('OSDTempo%s' % key(s), 'Player.HasVideo + !Player.Paused + %s' % playing_at(s),
                       ['SetProperty(OSDTempo,%s,home)' % fmt(s)],
                       'remember the speed, so it can be shown while paused' if s == SPEEDS[0] else None)
    lines += timer('OSDPendingTempoApply', '%s + %s + %s' % (pending, resumed, same_file),
                   ['PlayerControl(Tempo($INFO[%s]))' % PENDING_PROP,
                    'ClearProperty(OSDPendingTempo,home)', 'ClearProperty(OSDPendingFile,home)'],
                   'a speed picked while paused: apply it once playback resumes')
    lines += timer('OSDPendingTempoDrop', '%s + !%s' % (pending, same_file),
                   ['ClearProperty(OSDPendingTempo,home)', 'ClearProperty(OSDPendingFile,home)'],
                   '...unless another file (or nothing) is playing by then')
    lines += timer('OSDTempoForget', '!Player.HasVideo + !String.IsEmpty(%s)' % TEMPO_PROP,
                   ['ClearProperty(OSDTempo,home)'], 'playback stopped')
    lines += timer('OSDSpeedMenuClose', 'Window.IsActive(videoosd) + !String.IsEmpty(Window(videoosd).Property(%s))'
                   ' + !Control.HasFocus(256) + !ControlGroup(%d).HasFocus' % (OPEN_PROP, MENU_GROUPLIST),
                   [CLEAR_OPEN], 'mouse: the pointer moved on to something else while the menu was open')
    return ''.join(ind + l + '\n' for l in lines)


def fill(path, name, generator):
    text = open(path, encoding='utf8').read()
    pat = re.compile(r'([ \t]*)(<!-- BEGIN generated: %s(?= )[^>]*-->\n)(.*?)([ \t]*<!-- END generated: %s -->)'
                     % (re.escape(name), re.escape(name)), re.S)
    m = pat.search(text)
    if not m or len(pat.findall(text)) != 1:
        sys.exit('marker "%s" not found exactly once in %s' % (name, path))
    ind = m.group(1)
    new = text[:m.start()] + ind + m.group(2) + generator(ind) + m.group(4) + text[m.end():]
    if new != text:
        open(path, 'w', encoding='utf8').write(new)
    print('%-22s %s' % (name, 'updated' if new != text else 'unchanged'))


if __name__ == '__main__':
    assert NORMAL in SPEEDS and all(d in SPEEDS for d in DEFAULTS)
    assert all(s > 0.75 for s in SPEEDS), 'Kodi refuses tempo <= 0.75'
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xml')
    fill(os.path.join(root, 'VideoOSD.xml'), 'speed-onup', osd_onup)
    fill(os.path.join(root, 'VideoOSD.xml'), 'speed-menu', osd_menu)
    fill(os.path.join(root, 'SkinSettings.xml'), 'speed-settings', settings_panel)
    fill(os.path.join(root, 'includes.xml'), 'speed-defaults', defaults_include)
    fill(os.path.join(root, 'includes.xml'), 'speed-label', speed_label)
    fill(os.path.join(root, 'Timers.xml'), 'speed-timers', timers)
