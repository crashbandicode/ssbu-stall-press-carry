#!/usr/bin/env python3
"""Before/after clips of a C-stick flick that the game drops: lost without this plugin, carried with it.

/usr/bin/python3 -I tools/flick_clip.py --passes passes-00.bin --flicks m-cs1-flicks.json --gif m-cs1-b.gif \
    --label before|after --out-dir DIR [--carry-log events.log] [--flick N] [--before-s 0.8] [--after-s 2.2] \
    [--slow 2] [--move smash]
/usr/bin/python3 -I tools/flick_clip.py compose before.gif after.gif side-by-side.gif

Reads console b's ssbu-input-cadence-probe records (64-byte, `passes-NN.bin`), the harness's flick log (the wall time
of every C-stick call and of `recording.start`, `gif.py:match_cstick`) and Eden's recording of b. With the default
controls the game maps a C-stick input into the attack bits, the left stick's direction and the C-stick bit `0x80`, so
a flick is a run of decided passes whose local sample has `0x80` (`delivery.py`'s `cstick_on`), judged by the input the
game frame consumed for the first commit at or after the run's first pass. Runs are matched to the calls through the
clock offset that lines them up (`press_clip.align`); a boot can hold two matches, so only the probe session the calls
line up with is used. A longer match's session can line up with every call of a shorter one (`gif020-before-1`
m-cs1's did with m-cs2's calls); pass `--session` then. `input_clip.py` picks the session by its leftover runs instead.
- **Lost:** every pass of the run was dropped and the game frame did not get `0x80`.
- **Carried:** the run starts on a dropped pass, and this plugin's diag carry line for the next commit (`flick=carried
  stick=left cstick=yes`, its tick within 2 ms of the probe's record of that commit) shows the commit's own sample
  without `0x80` (`before=`) and with it after the carry (`after=`); the game frame got `0x80`. The probe reads the commit after this plugin, so a
  carried flick's run is `D…DC`: the carry line is what tells it from a flick that lasted into the commit.
Writes `<label>-flicks.json` (every flick), `<label>.gif` (640 wide; the chosen flick from `before_s` before to
`after_s` after, slowed `slow` times, captioned, the flick marked as it happens) and `<label>-frames/`. The chosen
flick: before, the first lost one; after, the first carried one; `--flick` picks another. Read-only on its inputs."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import delivery as dv  # noqa: E402
import press_clip as pc  # noqa: E402

CSTICK_ON = 0x80
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def direction(x, y):
    if x and not y:
        return 'right' if x > 0 else 'left'
    if y and not x:
        return 'up' if y > 0 else 'down'
    return 'diagonal'


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


def flick_runs(records):
    """`delivery.runs(…, 'cstick_on')` plus each run's pass pattern and the tick of its commit: the first committed
    pass in the run or, for an all-dropped run, the next one."""
    found, check = dv.runs(records, 'cstick_on')
    decided = sorted((r for r in records if r['flags'] & pc.LOCKSTEP and r['samples']), key=lambda r: r['pass'])
    for run in found:
        run['pattern'] = ''.join(p[-1] for p in run['passes'])
        commit = next((r for r in decided if r['pass'] >= run['first_pass'] and r['flags'] & pc.COMMIT), None)
        run['commit_tick'] = commit['tick'] if commit else None
        run['dropped_first'] = run['pattern'].startswith('D')
    return found, check


def match_carries(runs, carries, within_s=0.002):
    """Each run that starts on a dropped pass takes the C-stick carry line (`cstick=yes`) written on its commit: the
    line's tick is within `within_s` of the probe's record of that commit (the two hooks run in the same pass)."""
    used = set()
    for run in runs:
        if not run['dropped_first'] or run['commit_tick'] is None:
            continue
        for c in carries:
            if c['n'] in used or c['cstick'] != 'yes' or c['flick'] != 'carried':
                continue
            if abs(c['tick'] - run['commit_tick']) <= within_s * pc.TICKS_PER_S:
                run['carry'] = {'n': c['n'], 'bits': c['bits'], 'before': '%#x' % c['before'],
                                'after': '%#x' % c['after'], 'raw_had_it': bool(c['before'] & CSTICK_ON),
                                'set_it': bool(c['after'] & CSTICK_ON)}
                used.add(c['n'])
                break
    return len(used)


def by_session(records):
    out = {}
    for r in records:
        out.setdefault(r['session'], []).append(r)
    return out


def choose_session(records, calls, session=None):
    """The probe session whose flick runs line up with the most calls and leave the fewest runs unmatched (the flicks
    come at a steady spacing, so another match's longer session can line up with as many calls):
    (session, runs, check, offset). `session` picks one."""
    best = None
    for s, recs in sorted(by_session(records).items()):
        if session is not None and s != session:
            continue
        runs, check = flick_runs(recs)
        if not runs:
            continue
        offset = pc.align(runs, calls)
        matched = len({r['call'] for r in runs if r.get('call') is not None})
        score = (matched, -sum(r.get('call') is None for r in runs))
        if best is None or score > best[0]:
            best = (score, s, runs, check, offset)
    if best is None:
        return None, [], None, None
    return best[1], best[2], best[3], best[4]


def judge(runs, calls):
    """One entry per call that reached b's samples: its runs, whether the game got it, lost (all dropped, never got)
    and carried (a carry line set `0x80` that the commit's own sample lacked, and the game got it)."""
    flicks = []
    for g in pc.by_call(runs):
        first = runs[g[0]]
        call = first.get('call')
        if call is None:
            continue
        got = any(runs[i]['delivered'] for i in g)
        carry = next((runs[i]['carry'] for i in g if runs[i].get('carry')), None)
        flicks.append({
            'flick': call + 1, 'call': call, 'direction': direction(calls[call].get('x'), calls[call].get('y')),
            'runs': g, 'patterns': [runs[i]['pattern'] for i in g], 'frame': first['frame'],
            'consumed': first['consumed'], 'delivered': got,
            'lost': not got and all(runs[i]['all_dropped'] for i in g),
            'carried': bool(got and carry and first['dropped_first'] and not carry['raw_had_it'] and carry['set_it']),
            'carry': carry, 'first_tick': first['first_tick'], 'call_gap_s': first.get('call_gap_s')})
    return sorted(flicks, key=lambda f: f['call'])


def fit(draw, text, size, width):
    from PIL import ImageFont
    while size > 10:
        try:
            font = ImageFont.truetype(FONT, size)
        except OSError:
            return ImageFont.load_default()
        if draw.textlength(text, font=font) <= width:
            return font
        size -= 1
    return font


def clip(gif, at_s, label, caption, marker, out_dir, before_s=0.8, after_s=2.2, slow=2.0, width=640, mark_s=0.45,
         max_fps=15):
    """`press_clip.clip`'s layout (a caption bar above the frame, the marker bar over its bottom while the flick
    happens), with the text sized to fit and any slow-down. While a frame lasts less than 1/`max_fps` s, the frames
    after it are left out and their time added to it, so the clip stays within `max_fps`."""
    from PIL import Image, ImageDraw
    times = pc.gif_times(gif)
    picks = [i for i, t in enumerate(times) if at_s - before_s <= t <= at_s + after_s]
    frames_dir = out_dir / ('%s-frames' % label)
    frames_dir.mkdir(parents=True, exist_ok=True)
    out_frames, durations, fonts = [], [], None
    shortest = -(-1000 // (max_fps * 10)) * 10     # GIF delays are whole centiseconds
    with Image.open(gif) as im:
        for i in picks:
            nxt = times[i + 1] if i + 1 < len(times) else times[i] + 0.067
            duration = max(20, int(round((nxt - times[i]) * 1000 * slow)))
            if durations and durations[-1] < shortest:
                durations[-1] += duration
                continue
            n = len(out_frames)
            im.seek(i)
            frame = im.convert('RGB')
            h = round(frame.height * width / frame.width)
            frame = frame.resize((width, h), Image.LANCZOS)
            canvas = Image.new('RGB', (width, h + 34), (0, 0, 0))
            canvas.paste(frame, (0, 34))
            draw = ImageDraw.Draw(canvas)
            if fonts is None:
                fonts = (fit(draw, caption, 20, width - 170), fit(draw, '+0.00 s  x1/4', 18, 150),
                         fit(draw, marker, 18, width - 32))
            draw.text((8, 6), caption, fill=(255, 255, 255), font=fonts[0])
            t = times[i] - at_s
            draw.text((width - 150, 6), '%+.2f s  x1/%g' % (t, slow), fill=(200, 200, 200), font=fonts[1])
            if 0.0 <= t <= mark_s:
                draw.rectangle((8, h - 6, width - 8, h + 28), fill=(200, 30, 30) if label == 'before' else (20, 120, 200))
                draw.text((16, h - 2), marker, fill=(255, 255, 255), font=fonts[2])
            canvas.save(frames_dir / ('%04d.png' % n))
            durations.append(duration)
            out_frames.append(canvas.convert('P', palette=Image.ADAPTIVE, colors=128))
    durations[-1] = max(durations[-1], shortest)
    path = out_dir / ('%s.gif' % label)
    out_frames[0].save(path, save_all=True, append_images=out_frames[1:], duration=durations, loop=0, optimize=True)
    return path, len(out_frames), sum(durations) / 1000.0


def main(argv):
    if argv[:1] == ['compose']:
        n, seconds = pc.compose(Path(argv[1]), Path(argv[2]), Path(argv[3]))
        print(json.dumps({'compose': argv[3], 'frames': n, 'seconds': seconds, 'bytes': Path(argv[3]).stat().st_size}))
        return 0
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--passes', action='append', required=True)
    p.add_argument('--flicks', required=True)
    p.add_argument('--gif')
    p.add_argument('--label', choices=('before', 'after'), required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--carry-log')
    p.add_argument('--flick', type=int, help='the flick to show (its number, 1-based; default: the first lost / carried)')
    p.add_argument('--session', type=int, help='the probe session (default: the one the calls line up with)')
    p.add_argument('--before-s', type=float, default=0.8)
    p.add_argument('--after-s', type=float, default=2.2)
    p.add_argument('--slow', type=float, default=2.0)
    p.add_argument('--latency-s', type=float, default=0.0, help='added to a flick time to place it in the video')
    p.add_argument('--move', default='smash', help='what the flick does on screen, for the marker text')
    a = p.parse_args(argv)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for f in a.passes:
        records += pc.decode(Path(f).read_bytes())
    log = json.loads(Path(a.flicks).read_text())
    calls = log['flicks']
    session, runs, check, offset = choose_session(records, calls, a.session)
    summary = {'label': a.label, 'session': session, 'consumption': check, 'wall_offset_s': offset,
               'calls': len(calls), 'flick_runs': len(runs)}
    if a.carry_log:
        carries = parse_carries(Path(a.carry_log).read_text(errors='replace').splitlines())
        summary.update(carry_lines=len(carries), cstick_carry_lines=sum(c['cstick'] == 'yes' for c in carries),
                       carry_lines_matched=match_carries(runs, carries))
    flicks = judge(runs, calls)
    t0 = log['recording_start_acked']
    for f in flicks:
        f['at_s'] = round(f['first_tick'] / pc.TICKS_PER_S + offset - t0 + a.latency_s, 3) if offset is not None else None
    summary.update(flicks=len(flicks), reached=sum(f['delivered'] for f in flicks),
                   lost=[f['flick'] for f in flicks if f['lost']], carried=[f['flick'] for f in flicks if f['carried']])
    duration = sum(pc.gif_times(a.gif)[-1:]) if a.gif and Path(a.gif).exists() else None
    summary['gif_seconds'] = duration
    wanted = 'lost' if a.label == 'before' else 'carried'
    pick = [f for f in flicks if (f['flick'] == a.flick if a.flick else f[wanted])
            and duration is not None and f['at_s'] is not None
            and f['at_s'] - a.before_s >= 0 and f['at_s'] + a.after_s <= duration][:1]
    if pick:
        f = pick[0]
        caption = ('Before (no fix): %d of %d C-stick flicks reached the game' if a.label == 'before'
                   else 'After (with fix): %d of %d C-stick flicks reached the game') % (summary['reached'],
                                                                                     summary['flicks'])
        state = ('dropped, carried: %s' % a.move if f['carried'] else a.move if f['delivered']
                 else 'dropped, no %s' % a.move)
        marker = 'C-stick %s (flick %d): %s' % (f['direction'], f['flick'], state)
        path, n, seconds = clip(Path(a.gif), f['at_s'], a.label, caption, marker, out_dir, a.before_s, a.after_s,
                                a.slow)
        summary['clip'] = {'flick': f['flick'], 'at_s': f['at_s'], 'marker': marker, 'caption': caption,
                           'path': str(path), 'frames': n, 'seconds': seconds, 'bytes': path.stat().st_size}
    elif a.gif:
        summary['clip'] = 'not made: no %s flick inside the recording' % wanted
    summary['per_flick'] = flicks
    (out_dir / ('%s-flicks.json' % a.label)).write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'per_flick'}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
