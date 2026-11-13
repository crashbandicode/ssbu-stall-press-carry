#!/usr/bin/env python3
"""Before/after clips of a one-frame input that the game drops, with an input display drawn from the harness's log and
the probe's records: lost without this plugin, carried with it.

/usr/bin/python3 -I tools/input_clip.py list --passes passes-00.bin --inputs m-in1-inputs.json [--carry-log events.log] \
    [--session N] --out attempts.json
/usr/bin/python3 -I tools/input_clip.py clip --attempts attempts.json --attempt K --label before|after --out-dir DIR \
    [--pre-s 0.6] [--post-s 1.2] [--who NAME]
/usr/bin/python3 -I tools/input_clip.py compose before.gif after.gif pair.gif
/usr/bin/python3 -I tools/input_clip.py stills pair.gif DIR SECONDS...

`list` reads console b's ssbu-input-cadence-probe records (64-byte, `passes-NN.bin`), the harness's log of every input
(`gif.py:match_three` or `match_go`: the kind, the wall time of each call, the recordings' start times, and a set-up
stall of the other console, `stall`, if any) and, for the after side, this
plugin's diag carry lines. Each input kind has a signature in the local sample (the game's mapped input):
- `jump`: the Jump bit `0x4` (an X tap);
- `lsmash`: Attack `0x1` with the left stick at flick strength (84 of 120) sideways, without the C-stick bit;
- `cstick`: the C-stick bit `0x80` (with the default controls the game maps a C-stick input into the attack bits, the
  left stick's direction and `0x80`).
A run is a stretch of decided passes whose sample shows the signature; it is judged by the input the game frame of the
next commit consumed (`delivery.py`). Runs are lined up with the calls of the same kind through one clock offset for the
whole session. An attempt is:
- `lost`: every pass of its run was dropped, and neither the game frame before it nor the one after got any piece of it
  (`partly_lost` when one did: a split input, such as the stick a sample before A);
- `carried`: its run starts on a dropped pass, and the diag carry line written on the next commit (its tick within 2 ms
  of the probe's record of that commit) shows the commit's own sample without the input and with it after the carry;
  the game frame got it, and the frame before got no piece of it;
- `delivered` (the game got it some other way) or `missed` (no sample held it).
`clip` draws one attempt: a caption bar, the game, and the input display (titled "<NAME>'s input (harness)" with
`--who`, so the press isn't credited to the other fighter): the left stick and C-stick circles with a dot at the sent
position, the A and Jump lamps, and the strip pressed → dropped by the game → received by the game (or lost). The clip
runs at full speed up to 0.2 s before the input, then at half speed, and holds the input's frame for 0.5 s while the
strip fills in. 640 wide, at most 15 frames a second. `compose` puts two clips side by side, with no
frame shorter than 70 ms. Read-only on its inputs."""
import argparse
import bisect
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import delivery as dv  # noqa: E402
import press_clip as pc  # noqa: E402

KINDS = ('jump', 'lsmash', 'cstick')
JUMP, ATTACK, CSTICK_ON = 0x4, 0x1, 0x80
FLICK = 84
NAMES = {'jump': 'Jump tap', 'lsmash': 'left stick + A', 'cstick': 'C-stick'}
MOVES = {'jump': 'jump', 'lsmash': 'smash', 'cstick': 'smash'}
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
WIDTH, CAPTION, GAME_H, PANEL = 640, 30, 360, 150


def shows(value, kind):
    if value is None:
        return False
    if kind == 'jump':
        return bool(value & JUMP)
    if kind == 'cstick':
        return bool(value & CSTICK_ON)
    x, _ = dv.stick(value)
    return bool(value & ATTACK) and abs(x) >= FLICK and not value & CSTICK_ON


def part(value, kind):
    """Any piece of the input: the Jump bit; the Attack bit or the left stick past the dead zone (24); for the C-stick
    also its bit. A split input (the stick in one sample, A in the next) shows a piece where the whole isn't."""
    if value is None:
        return False
    if kind == 'jump':
        return bool(value & JUMP)
    x, _ = dv.stick(value)
    return bool(value & (ATTACK | CSTICK_ON)) or abs(x) > 24


def parse_carries(lines):
    """This plugin's diag lines: `<tick> carry n= bits= flick= stick= cstick= before= after= ring_lost=`."""
    out = []
    for line in lines:
        parts = line.split()
        if len(parts) > 3 and parts[1] == 'carry':
            f = dict(p.split('=', 1) for p in parts[2:] if '=' in p)
            out.append({'tick': int(parts[0]), 'n': int(f.get('n', '0')), 'bits': f.get('bits'),
                        'flick': f.get('flick'), 'stick': f.get('stick'), 'cstick': f.get('cstick'),
                        'before': int(f.get('before', '0'), 16), 'after': int(f.get('after', '0'), 16)})
    return out


def runs(records, kind, used=None):
    """Runs of decided passes whose sample shows `kind`; each with its passes, its commit (the first committed pass in
    the run, or the next one) and what that frame consumed."""
    decided = sorted((r for r in records if r['flags'] & pc.LOCKSTEP and r['samples']), key=lambda r: r['pass'])
    if used is None:
        used, _, _ = dv.consumed_full(records)
    out, current = [], None
    for r in decided:
        if shows(r['sample'], kind):
            if current is None:
                current = {'kind': kind, 'passes': [], 'first_pass': r['pass'], 'first_tick': r['tick']}
                out.append(current)
            current['passes'].append('%d%s' % (r['pass'], 'C' if r['flags'] & pc.COMMIT else 'D'))
        else:
            current = None
    commits = [r for r in decided if r['flags'] & pc.COMMIT]
    passes = [r['pass'] for r in commits]
    for run in out:
        at = bisect.bisect_left(passes, run['first_pass'])
        commit = commits[at] if at < len(commits) else None
        prev = commits[at - 1] if at > 0 else None
        got = used.get(commit['send']) if commit else None
        prev_got = used.get(prev['send']) if prev else None
        run.update(pattern=''.join(p[-1] for p in run['passes']), commit_pass=commit['pass'] if commit else None,
                   commit_tick=commit['tick'] if commit else None, frame=commit['send'] if commit else None,
                   consumed=None if got is None else '%#x' % got, delivered=shows(got, kind),
                   # No piece of the input in the frames on either side: the game got none of it.
                   clean=not part(got, kind) and not part(prev_got, kind), prev_clean=not part(prev_got, kind))
        run['all_dropped'] = 'C' not in run['pattern']
        run['dropped_first'] = run['pattern'].startswith('D')
    return out


def align(found, calls, window_s=0.15):
    """The clock offset (wall time = tick / 19.2 MHz + offset) that puts the most runs within `window_s` of a call of
    their kind, from every same-kind run/call pair; then each run's call. (`press_clip.align` tries every pair against
    every pair, which is too slow for a whole match.)"""
    by_kind = {}
    for i, c in enumerate(calls):
        by_kind.setdefault(c['kind'], []).append((c['sent'], i))
    for v in by_kind.values():
        v.sort()
    cands = [c - r['first_tick'] / pc.TICKS_PER_S for r in found for c, _ in by_kind.get(r['kind'], [])]
    if not cands:
        return None

    def near(r, off):
        v = by_kind.get(r['kind'], [])
        t = r['first_tick'] / pc.TICKS_PER_S + off
        at = bisect.bisect_left(v, (t, -1))
        best = None
        for j in (at - 1, at):
            if 0 <= j < len(v) and (best is None or abs(v[j][0] - t) < abs(best[0] - t)):
                best = (v[j][0], v[j][1])
        return (abs(best[0] - t), best[1]) if best else (None, None)
    scored = []
    for off in cands:
        gaps = [near(r, off)[0] for r in found]
        hits = [g for g in gaps if g is not None and g <= window_s]
        scored.append(((len(hits), -sum(hits)), off))
    _, off = max(scored)
    for r in found:
        gap, call = near(r, off)
        r['call'] = call if gap is not None and gap <= window_s else None
        r['call_gap_s'] = None if gap is None else round(gap, 4)
    return off


def match_carries(found, carries, within_s=0.002):
    """Each run that starts on a dropped pass takes the carry line written on its commit (the two ticks within
    `within_s`) when that line added the run's input: its `before` lacks it and its `after` shows it."""
    by_tick = sorted(carries, key=lambda c: c['tick'])
    ticks = [c['tick'] for c in by_tick]
    n = 0
    for run in found:
        if not run['dropped_first'] or run['commit_tick'] is None:
            continue
        at = bisect.bisect_left(ticks, run['commit_tick'] - within_s * pc.TICKS_PER_S)
        while at < len(by_tick) and by_tick[at]['tick'] <= run['commit_tick'] + within_s * pc.TICKS_PER_S:
            c = by_tick[at]
            if not shows(c['before'], run['kind']) and shows(c['after'], run['kind']):
                run['carry'] = {'n': c['n'], 'bits': c['bits'], 'flick': c['flick'], 'stick': c['stick'],
                                'cstick': c['cstick'], 'before': '%#x' % c['before'], 'after': '%#x' % c['after']}
                n += 1
                break
            at += 1
    return n


def session_runs(records, calls, session=None):
    """The probe session the calls line up with: the most runs on calls less the runs left over. The inputs come at a
    steady spacing, so a longer match's session can line up with every call of a shorter one; its leftover runs give
    it away. (session, runs of every kind, offset)."""
    sessions = {}
    for r in records:
        sessions.setdefault(r['session'], []).append(r)
    best = None
    for s, recs in sorted(sessions.items()):
        if s == 0 or (session is not None and s != session):
            continue
        used, _, _ = dv.consumed_full(recs)
        found = [run for kind in KINDS for run in runs(recs, kind, used)]
        if not found:
            continue
        off = align(found, calls)
        matched = sum(r.get('call') is not None for r in found)
        score = (matched - sum(r.get('call') is None for r in found), matched)
        if best is None or score > best[0]:
            best = (score, s, found, off)
    return (best[1], best[2], best[3]) if best else (None, [], None)


def judge(found, calls, recordings):
    """One entry per call: its runs and outcome, and where it falls in the recordings (`at_s` in recording `rec`)."""
    out = []
    for i, c in enumerate(calls):
        mine = sorted((r for r in found if r.get('call') == i), key=lambda r: r['first_tick'])
        e = {'attempt': i, 'kind': c['kind'], 'at': c.get('at'), 'x': c.get('x', 0.0), 'y': c.get('y', 0.0),
             'buttons': c.get('buttons', []), 'sent': c['sent'], 'rec': c.get('rec'),
             'patterns': [r['pattern'] for r in mine], 'passes': [r['passes'] for r in mine]}
        if not mine:
            e['outcome'] = 'missed'
            out.append(e)
            continue
        first = mine[0]
        got = any(r['delivered'] for r in mine)
        carry = next((r['carry'] for r in mine if r.get('carry')), None)
        if not got and all(r['all_dropped'] for r in mine):
            # A piece in the frames on either side (a split input) means the game got part of it: not shown as lost.
            e['outcome'] = 'lost' if all(r['clean'] for r in mine) else 'partly_lost'
        elif got and first['dropped_first'] and carry and first['prev_clean']:
            e['outcome'] = 'carried'
        else:
            e['outcome'] = 'delivered' if got else 'not_delivered'
        e.update(first_tick=first['first_tick'], frame=first['frame'], consumed=first['consumed'], carry=carry,
                 dropped=[p for p in first['passes'] if p.endswith('D')], commit_pass=first['commit_pass'],
                 call_gap_s=first['call_gap_s'])
        out.append(e)
    return out


def listing(passes, inputs, carry_log=None, session=None):
    records = []
    for f in passes:
        records += pc.decode(Path(f).read_bytes())
    log = json.loads(Path(inputs).read_text())
    calls = log['flicks']
    s, found, off = session_runs(records, calls, session)
    summary = {'inputs': str(inputs), 'session': s, 'wall_offset_s': off, 'calls': len(calls), 'runs': len(found),
               'recordings': log.get('recordings', []), 'b_side': log.get('b_side'), 'toward': log.get('toward'),
               'stall': log.get('stall')}
    if carry_log:
        carries = parse_carries(Path(carry_log).read_text(errors='replace').splitlines())
        summary.update(carry_lines=len(carries), carry_lines_matched=match_carries(found, carries))
    attempts = judge(found, calls, log.get('recordings', []))
    for e in attempts:
        rec = e.get('rec')
        recs = log.get('recordings', [])
        if off is not None and 'first_tick' in e and rec is not None and rec < len(recs):
            e['gif'] = recs[rec]['path']
            e['at_s'] = round(e['first_tick'] / pc.TICKS_PER_S + off - recs[rec]['start_acked'], 3)
    summary['by_kind'] = {k: {o: sum(1 for e in attempts if e['kind'] == k and e['outcome'] == o)
                              for o in ('lost', 'partly_lost', 'carried', 'delivered', 'not_delivered', 'missed')}
                          for k in KINDS}
    summary['attempts'] = attempts
    return summary


# ---------------------------------------------------------------------------
# Drawing.

def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def panel_title(who=None):
    """The input display's title: whose input it is, when the fighter is named."""
    return "%s's input (harness)" % who if who else 'input pressed (harness)'


def draw_panel(draw, top, kind, sent, pressed, lit, outcome, width=WIDTH, who=None):
    """The input display under the game: what the harness pressed (two stick circles with a dot at the sent position,
    the A and Jump lamps) and what the game did with it (the strip). `lit`: how many strip cells are on (0-3). `who`:
    the fighter the input belongs to, for the title."""
    grey, dim, white = (150, 150, 150), (70, 70, 70), (255, 255, 255)
    yellow, red, green = (245, 200, 40), (200, 40, 40), (40, 160, 70)
    draw.rectangle((0, top, width, top + PANEL), fill=(16, 16, 16))
    draw.text((10, top + 4), panel_title(who), fill=grey, font=_font(13))
    draw.text((width - 10 - draw.textlength(NAMES[kind], font=_font(18)), top + 30), NAMES[kind], fill=white,
              font=_font(18))
    cy = top + 47
    for cx, name, which in ((44, 'L stick', 'left'), (124, 'C-stick', 'right')):
        r = 24
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=grey, width=2)
        draw.line((cx - r, cy, cx + r, cy), fill=dim)
        draw.line((cx, cy - r, cx, cy + r), fill=dim)
        x, y = (sent.get('x', 0.0), sent.get('y', 0.0)) if sent.get('stick') == which else (0.0, 0.0)
        on = pressed and (x or y)
        dx, dy = cx + x * (r - 6), cy - y * (r - 6)
        if on:
            draw.line((cx, cy, dx, dy), fill=yellow, width=3)
        draw.ellipse((dx - 6, dy - 6, dx + 6, dy + 6), fill=yellow if on else dim)
        draw.text((cx - draw.textlength(name, font=_font(12)) / 2, cy + r + 2), name, fill=grey, font=_font(12))
    for cx, name, button in ((204, 'A', 'a'), (264, 'Jump', 'x')):
        r = 17
        on = pressed and button in sent.get('buttons', [])
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=yellow if on else (40, 40, 40), outline=grey, width=2)
        label = 'A' if name == 'A' else 'X'
        draw.text((cx - draw.textlength(label, font=_font(16)) / 2, cy - 10), label, fill=(0, 0, 0) if on else grey,
                  font=_font(16))
        draw.text((cx - draw.textlength(name, font=_font(12)) / 2, cy + 26), name, fill=grey, font=_font(12))
    draw.text((10, top + 94), 'what the game did (probe)', fill=grey, font=_font(13))
    cells = [('pressed: one frame', yellow, (0, 0, 0)), ('dropped by the game', red, white),
             ('received by the game' if outcome == 'received' else 'lost: never received',
              green if outcome == 'received' else red, white)]
    cw, gap, y0 = (width - 20 - 2 * 18) // 3, 18, top + 114
    for i, (text, fill, ink) in enumerate(cells):
        x0 = 10 + i * (cw + gap)
        on = i < lit
        draw.rectangle((x0, y0, x0 + cw, y0 + 26), fill=fill if on else (32, 32, 32), outline=fill if on else dim,
                       width=2)
        f = _font(14)
        draw.text((x0 + (cw - draw.textlength(text, font=f)) / 2, y0 + 4), text, fill=ink if on else dim, font=f)
        if i < 2:
            ax = x0 + cw + 3
            draw.polygon(((ax, y0 + 7), (ax + 11, y0 + 13), (ax, y0 + 19)), fill=grey if i + 1 < lit else dim)


STALL_NOTE = 'other console stalls (set up)'


def render(gif, at_s, kind, sent, outcome, caption, out_dir, label, pre_s=0.6, post_s=1.2, slow_from_s=0.2,
           slow=2.0, hold_s=0.5, max_fps=15, hold_at_s=None, stall=None, who=None):
    """The clip: the game from `pre_s` before the input to `post_s` after, full speed until `slow_from_s` before it,
    then slowed `slow` times; the input's frame held `hold_s` while the strip fills in. No frame is shorter than
    1/`max_fps` s: full-speed frames are merged, slowed ones stretched a little. `hold_at_s` lengthens the first frame
    so the hold starts at that time (two clips side by side then hold together). `stall`: (start, end) in seconds from
    the input, a stall of the other console set up for the clip; while it lasts the caption bar says so (`STALL_NOTE`).
    `who`: the fighter whose input it is, named in the input display's title (`panel_title`).
    Returns (path, frames, seconds, the PNG of each output frame with its start time in the clip)."""
    from PIL import Image, ImageDraw
    times = pc.gif_times(gif)
    picks = [i for i, t in enumerate(times) if at_s - pre_s <= t <= at_s + post_s]
    key = max((i for i in picks if times[i] <= at_s + 0.034), default=picks[0])
    frames_dir = out_dir / ('%s-frames' % label)
    frames_dir.mkdir(parents=True, exist_ok=True)
    shortest = -(-1000 // (max_fps * 10)) * 10     # GIF delays are whole centiseconds
    out, durations, canvases, hold_index = [], [], [], []

    def emit(base, rel, pressed, lit, speed, ms, stretch):
        if stretch:
            ms = max(ms, shortest)
            if durations and durations[-1] < shortest:
                durations[-1] = shortest
        elif durations and durations[-1] < shortest:
            durations[-1] += ms
            return
        canvas = Image.new('RGB', (WIDTH, CAPTION + GAME_H + PANEL), (0, 0, 0))
        canvas.paste(base, (0, CAPTION))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 5), caption, fill=(255, 255, 255), font=_font(19))
        note = '%+.2f s  %s' % (rel, speed)
        draw.text((WIDTH - 8 - draw.textlength(note, font=_font(15)), 7), note, fill=(200, 200, 200), font=_font(15))
        if stall is not None and stall[0] <= rel <= stall[1]:
            x0 = 8 + draw.textlength(caption, font=_font(19)) + 12
            draw.text((x0, 8), STALL_NOTE, fill=(255, 170, 40), font=_font(14))
        draw_panel(draw, CAPTION + GAME_H, kind, sent, pressed, lit, outcome, who=who)
        if pressed and not hold_index:
            hold_index.append(len(canvases))
        canvases.append(canvas)
        durations.append(ms)
    with Image.open(gif) as im:
        for i in picks:
            im.seek(i)
            base = im.convert('RGB')
            base = base.resize((WIDTH, round(base.height * WIDTH / base.width)), Image.LANCZOS)
            if base.height != GAME_H:
                base = base.resize((WIDTH, GAME_H), Image.LANCZOS)
            rel = times[i] - at_s
            nxt = times[i + 1] if i + 1 < len(times) else times[i] + 1.0 / 30
            factor = slow if rel >= -slow_from_s else 1.0
            ms = max(20, int(round((nxt - times[i]) * 1000 * factor)))
            speed = 'slow x1/%g' % slow if factor != 1.0 else 'x1'
            stretch = factor != 1.0
            if i < key:
                emit(base, rel, False, 0, speed, ms, stretch)
            elif i == key:
                step = -(-int(round(hold_s * 1000 / 3)) // 10) * 10
                for lit in (1, 2, 3):
                    emit(base, rel, True, lit, 'held', step, True)
                emit(base, rel, False, 3, speed, ms, stretch)
            else:
                emit(base, rel, False, 3, speed, ms, stretch)
    durations[-1] = max(durations[-1], shortest)
    if hold_at_s is not None and hold_index:
        durations[0] += max(0, int(round(hold_at_s * 1000)) - sum(durations[:hold_index[0]]))
    pngs, at = [], 0
    for n, (canvas, ms) in enumerate(zip(canvases, durations)):
        path = frames_dir / ('%04d.png' % n)
        canvas.save(path)
        pngs.append((at, str(path)))
        at += ms
        out.append(canvas.convert('P', palette=Image.ADAPTIVE, colors=160))
    path = out_dir / ('%s.gif' % label)
    out[0].save(path, save_all=True, append_images=out[1:], duration=durations, loop=0, optimize=True)
    return path, len(out), sum(durations) / 1000.0, pngs


def compose(left, right, out, min_ms=70):
    """Two clips side by side on a shared timeline. A new frame starts at every frame change of either clip, except
    one less than `min_ms` after the last: browsers stretch very short GIF delays (10 ms) to 100 ms, which would put
    the two sides out of step."""
    from PIL import Image

    def timeline(path):
        frames, at = [], 0
        with Image.open(path) as im:
            for i in range(im.n_frames):
                im.seek(i)
                frames.append((at, im.convert('RGB')))
                at += im.info.get('duration') or 100
        return frames, at
    (lf, lt), (rf, rt) = timeline(left), timeline(right)
    total = max(lt, rt)
    keep = []
    for t in sorted({s for s, _ in lf} | {s for s, _ in rf}):
        if not keep or t - keep[-1] >= min_ms:
            keep.append(t)
    if len(keep) > 1 and total - keep[-1] < min_ms:
        keep.pop()
    out_frames = []
    for t in keep:
        a = [f for s, f in lf if s <= t][-1]
        b = [f for s, f in rf if s <= t][-1]
        canvas = Image.new('RGB', (a.width + b.width, max(a.height, b.height)), (0, 0, 0))
        canvas.paste(a, (0, 0))
        canvas.paste(b, (a.width, 0))
        out_frames.append(canvas.convert('P', palette=Image.ADAPTIVE, colors=160))
    durations = [b - a for a, b in zip(keep, keep[1:] + [total])]
    out_frames[0].save(out, save_all=True, append_images=out_frames[1:], duration=durations, loop=0, optimize=True)
    return len(out_frames), total / 1000.0


def stills(gif, out_dir, seconds):
    """Frames of a GIF at the given times (in the GIF's own timeline) as PNGs."""
    from PIL import Image
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    times = pc.gif_times(gif)
    saved = []
    with Image.open(gif) as im:
        for s in seconds:
            i = max((j for j, t in enumerate(times) if t <= s), default=0)
            im.seek(i)
            p = out_dir / ('still-%05.2fs.png' % s)
            im.convert('RGB').save(p)
            saved.append(str(p))
    return saved


def main(argv):
    if argv[:1] == ['compose']:
        n, seconds = compose(Path(argv[1]), Path(argv[2]), Path(argv[3]))
        print(json.dumps({'compose': argv[3], 'frames': n, 'seconds': seconds, 'bytes': Path(argv[3]).stat().st_size}))
        return 0
    if argv[:1] == ['stills']:
        print(json.dumps(stills(Path(argv[1]), argv[2], [float(x) for x in argv[3:]])))
        return 0
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('command', choices=('list', 'clip'))
    p.add_argument('--passes', action='append')
    p.add_argument('--inputs')
    p.add_argument('--carry-log')
    p.add_argument('--session', type=int)
    p.add_argument('--out')
    p.add_argument('--attempts')
    p.add_argument('--attempt', type=int)
    p.add_argument('--label', choices=('before', 'after'))
    p.add_argument('--out-dir')
    p.add_argument('--pre-s', type=float, default=0.6)
    p.add_argument('--post-s', type=float, default=1.2)
    p.add_argument('--hold-at-s', type=float, default=1.0, help='when the hold starts in the clip')
    p.add_argument('--gif', help='the recording (default: the path in the log, under --gif-dir)')
    p.add_argument('--gif-dir', help='where the recordings are, when not at the logged path')
    p.add_argument('--any', action='store_true', help='draw an attempt whatever its outcome (for looking)')
    p.add_argument('--who', help="the fighter whose input it is (the display's title: \"<who>'s input (harness)\")")
    a = p.parse_args(argv)
    if a.command == 'list':
        summary = listing(a.passes, a.inputs, a.carry_log, a.session)
        text = json.dumps(summary, indent=1)
        if a.out:
            Path(a.out).write_text(text + '\n')
        print(json.dumps({k: v for k, v in summary.items() if k not in ('attempts', 'recordings')}, indent=1))
        return 0
    summary = json.loads(Path(a.attempts).read_text())
    e = summary['attempts'][a.attempt]
    want = 'lost' if a.label == 'before' else 'carried'
    if e['outcome'] != want and not a.any:
        raise SystemExit('attempt %d is %s, not %s' % (a.attempt, e['outcome'], want))
    gif = Path(a.gif) if a.gif else Path(a.gif_dir) / Path(e['gif']).name if a.gif_dir else Path(e['gif'])
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sent = {'stick': {'lsmash': 'left', 'cstick': 'right'}.get(e['kind']), 'x': e['x'], 'y': e['y'],
            'buttons': e['buttons']}
    caption = 'Without the fix' if a.label == 'before' else 'With the fix (0.2.0)'
    outcome = 'lost' if e['outcome'] in ('lost', 'not_delivered', 'missed') else 'received'
    stall = summary.get('stall')
    window = None
    if stall and e.get('at') == 'go' and stall.get('pause_sent') and stall.get('resume_sent'):
        window = (stall['pause_sent'] - e['sent'], stall['resume_sent'] - e['sent'])
    path, n, seconds, pngs = render(gif, e['at_s'], e['kind'], sent, outcome, caption, out_dir, a.label, a.pre_s,
                                    a.post_s, hold_at_s=a.hold_at_s, stall=window, who=a.who)
    info = {'attempt': e, 'stall_window_s': window, 'who': a.who, 'clip': str(path), 'frames': n, 'seconds': seconds,
            'bytes': path.stat().st_size, 'pngs': pngs}
    (out_dir / ('%s-clip.json' % a.label)).write_text(json.dumps(info, indent=1) + '\n')
    print(json.dumps({k: v for k, v in info.items() if k != 'pngs'}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
