#!/usr/bin/env python3
"""Measure Kodi skin performance from kodi.log.

Two measurement modes (auto-detected):

1. Classic: Kodi builds that log 'Loading skin file: X, load time: N ms'
2. Timestamp deltas (Kodi 19+): uses debug-level window lifecycle lines
     ------ Window Init (Home.xml)------
     ------ Window Deinit (Home.xml) ------
   Requires Settings -> System -> Logging -> Enable debug logging.

Usage:
  python tools/parse_kodi_log.py                        # summarize current kodi.log
  python tools/parse_kodi_log.py path/to/kodi.log       # summarize a specific log
  python tools/parse_kodi_log.py -a old.log -b new.log  # before/after comparison
"""
from pathlib import Path
import argparse
import os
import re
from collections import defaultdict
from datetime import datetime

LOAD_RE = re.compile(r"loading skin file:\s*([^\s,]+?)\s*,\s*load time:\s*(\d+)\s*ms", re.I)
WIN_RE = re.compile(r"window\s+(init|deinit)\s*\(\s*([^)]+?)\s*\)", re.I)
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}[ T][0-9:.]+)")
SKIN_ISSUE_RE = re.compile(r"(error|warning)\b.*skin", re.I)


def ts(line):
    m = TS_RE.match(line)
    if not m:
        return None
    s = m.group(1).replace("T", " ")
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def parse_log(path):
    loads = defaultdict(list)
    issues = []
    events = []  # (datetime, kind, window)
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        m = LOAD_RE.search(line)
        if m:
            loads[m.group(1)].append(int(m.group(2)))
            continue
        w = WIN_RE.search(line)
        if w:
            t = ts(line)
            if t:
                events.append((t, w.group(1).lower(), w.group(2)))
            continue
        if SKIN_ISSUE_RE.search(line):
            issues.append(line.strip()[:170])
    return loads, issues, events


def window_stats(events):
    """Per-window: activations, median activation gap (prev event -> Init),
    median dwell (Init -> matching Deinit)."""
    act_gaps = defaultdict(list)
    dwells = defaultdict(list)
    open_win = {}  # window -> init time
    prev_t = None
    for t, kind, win in sorted(events):
        if kind == "init":
            if prev_t is not None:
                act_gaps[win].append((t - prev_t).total_seconds() * 1000.0)
            open_win[win] = t
        else:
            if win in open_win:
                dwells[win].append((t - open_win.pop(win)).total_seconds() * 1000.0)
        prev_t = t
    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else 0.0
    stats = {}
    for win in set(list(act_gaps) + list(dwells)):
        stats[win] = (len(act_gaps.get(win, [])), med(act_gaps.get(win, [0])),
                      len(dwells.get(win, [])), med(dwells.get(win, [0])))
    return stats


def print_single(path):
    loads, issues, events = parse_log(path)
    print("== %s ==" % path)
    if loads:
        print("%-40s %5s %8s %9s %8s" % ("window/file", "loads", "min ms", "avg ms", "max ms"))
        rows = {n: (len(t), min(t), sum(t) / len(t), max(t)) for n, t in loads.items()}
        for n, (n_, mn, avg, mx) in sorted(rows.items(), key=lambda kv: -kv[1][2]):
            print("%-40s %5d %7d %8.1f %7d" % (n, n_, mn, avg, mx))
    elif events:
        st = window_stats(events)
        print("mode: window-lifecycle timestamp deltas (debug logging detected)")
        print("%-38s %6s %12s %8s %12s" % ("window", "switches", "switch ms*", "shows", "dwell ms"))
        for win, (sw, sgap, sh, sdwell) in sorted(st.items(), key=lambda kv: kv[1][3], reverse=True):
            print("%-38s %6d %11.0f %8d %11.0f" % (win, sw, sgap, sh, sdwell))
        print("* switch ms = time from previous window event until this window finished")
        print("  initializing (includes XML load when not cached). Median values.")
    else:
        print("No timing data found.")
        print("- Enable debug logging: Settings -> System -> Logging -> Enable debug logging")
        print("- Restart Kodi, navigate around, quit, re-run this tool.")
    if issues:
        print()
        print("== skin-related errors/warnings (%d unique) ==" % len({i[:80] for i in issues}))
        seen = set()
        for i in issues:
            key = i[:80]
            if key not in seen:
                seen.add(key)
                print(" ", i)


def print_compare(pa, pb):
    _, _, ea = parse_log(pa)[0], parse_log(pa)[1], parse_log(pa)[2]
    la, ia, eva = parse_log(pa)
    lb, ib, evb = parse_log(pb)
    if la or lb:
        ra = {n: sum(t) / len(t) for n, t in la.items()}
        rb = {n: sum(t) / len(t) for n, t in lb.items()}
        names = sorted(set(ra) | set(rb), key=lambda n: -(ra.get(n, 0) + rb.get(n, 0)))
        print("%-40s %12s %12s %10s" % ("window/file", "old avg ms", "new avg ms", "delta"))
        ta = tb = 0.0
        for n in names:
            a, b = ra.get(n), rb.get(n)
            sa = "%8.1f" % a if a is not None else "     n/a"
            sb = "%8.1f" % b if b is not None else "     n/a"
            if a and b:
                d = "%+8.1f%%" % ((b - a) / a * 100); ta += a; tb += b
            else:
                d = "       n/a"
            print("%-40s %12s %12s %10s" % (n, sa, sb, d))
        if ta and tb:
            print(); print("Overall mean: old %.1f ms -> new %.1f ms (%+.1f%%)" % (ta, tb, (tb - ta) / ta * 100))
        return
    sa_, sb_ = window_stats(eva), window_stats(evb)
    names = sorted(set(sa_) | set(sb_), key=lambda n: -(sa_.get(n, (0,0,0,0))[3] + sb_.get(n, (0,0,0,0))[3]))
    print("%-38s %14s %14s %10s" % ("window", "old switch ms", "new switch ms", "delta"))
    ta = tb = 0.0
    for n in names:
        a = sa_[n][1] if n in sa_ else None
        b = sb_[n][1] if n in sb_ else None
        oa = "%12.0f" % a if a is not None else "           n/a"
        ob = "%12.0f" % b if b is not None else "           n/a"
        if a and b:
            d = "%+9.1f%%" % ((b - a) / a * 100); ta += a; tb += b
        else:
            d = "        n/a"
        print("%-38s %14s %14s %10s" % (n, oa, ob, d))
    if ta and tb:
        print(); print("Overall mean switch: old %.0f ms -> new %.0f ms (%+.1f%%)" % (ta, tb, (tb - ta) / ta * 100))



def hunt_gaps(path, min_gap=60.0, ctx=3):
    """Find silent periods in the log: prints last lines before each gap and
    the first line after - shows what Kodi was doing when it stopped/stalled."""
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    stamped = []
    for i, l in enumerate(lines):
        t = ts(l)
        if t:
            stamped.append((i, t))
    print("== gap hunt: %s (gaps >= %.0fs) ==" % (path, min_gap))
    found = 0
    for k in range(1, len(stamped)):
        i_prev, t_prev = stamped[k - 1]
        i_cur, t_cur = stamped[k]
        gap = (t_cur - t_prev).total_seconds()
        if gap >= min_gap:
            found += 1
            print()
            print("--- gap #%d: %.1f minutes silent (%s -> %s) ---"
                  % (found, gap / 60.0, t_prev.time(), t_cur.time()))
            print("  last activity before silence:")
            for j in range(max(0, i_prev - ctx + 1), i_prev + 1):
                print("    |", lines[j][:165])
            print("  first activity after:")
            print("    |", lines[i_cur][:165])
    if not found:
        print("no gaps >= %.0fs found" % min_gap)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log", nargs="?", help="kodi.log to summarize")
    ap.add_argument("-a", help="baseline log (before)")
    ap.add_argument("-b", help="new log (after)")
    ap.add_argument("--hunt-gaps", action="store_true", help="find silent periods (hang diagnostics)")
    ap.add_argument("--min-gap", type=float, default=60.0, help="minimum gap seconds for --hunt-gaps")
    args = ap.parse_args()

    default = Path(os.environ.get("APPDATA", "")) / "Kodi" / "kodi.log"
    if args.hunt_gaps:
        hunt_gaps(args.log or str(default), args.min_gap)
    elif args.a and args.b:
        print_compare(args.a, args.b)
    elif args.log or default.exists():
        print_single(args.log or str(default))
    else:
        print("kodi.log not found at %s - pass a path explicitly." % default)


if __name__ == "__main__":
    main()
