#!/usr/bin/env python3
"""Before/after clips of a Jump tap: lost without this plugin, carried with it.

/usr/bin/python3 -I tools/press_clip.py --passes passes-00.bin --taps taps.json --gif b.gif --label before|after \
    --out-dir DIR [--carry-log events.log] [--bit 0x4]
/usr/bin/python3 -I tools/press_clip.py compose before.gif after.gif side-by-side.gif

Reads console b's ssbu-input-cadence-probe records (64-byte, `passes-NN.bin`), the harness's tap log (the wall time of
every tap call and of `recording.start`) and Eden's recording of b. A tap is a run of passes whose local sample has the
Jump bit; it counts as a jump when the input the game frame consumed for the first commit at or after the tap has the
bit. Taps are placed in the video through the clock offset that lines the probe's taps up with the tap calls in
`taps.json` (`align`), so a tap Eden never delivered does not shift the others. Writes
`<label>-taps.json` (every tap), `<label>.gif` (640 wide, the chosen tap from 0.9 s before to 1.4 s after, slowed 4x,
captioned, the chosen tap and its neighbours marked as they happen) and `<label>-frames/` (the clip's PNGs). The chosen tap: before, the first one the game did not get; after,
the first one whose samples were all dropped and that the game still got (a carry). Read-only on its inputs."""
import argparse
import json
import struct
import sys
from pathlib import Path

RECORD = struct.Struct('<QIBBBBHHBBBBQQQQII')
MAGIC = 0x31445043
UPDATE, LOCKSTEP, COMMIT, MANAGER = 4, 8, 16, 64


def decode(blob):
    out = []
    for at in range(0, len(blob) - RECORD.size + 1, RECORD.size):
        v = RECORD.unpack_from(blob, at)
        if v[17] != MAGIC:
            continue
        out.append({'tick': v[0], 'pass': v[1], 'flags': v[2], 'send': v[6], 'current': v[7], 'samples': v[8],
                    'mask': v[9], 'sample': v[12], 'consumed': (v[14], v[15]), 'session': v[16]})
    return out


def consumed_by_frame(records):
    """frame -> the local slot's consumed input, at the offset where consumed equals the committed sample most often."""
    slot = next(((r['mask'] & -r['mask']).bit_length() - 1 for r in records if r['flags'] & LOCKSTEP and r['mask']), 0)
    slot = min(slot, 1)
    committed = {r['send']: r['sample'] & 0xffffffff for r in records if r['flags'] & COMMIT and r['samples']}
    updates = [r for r in records if r['flags'] & UPDATE and r['flags'] & LOCKSTEP and r['flags'] & MANAGER]
    best = None
    for d in range(-4, 5):
        pairs = [(committed[(r['current'] + d) & 0xffff], r['consumed'][slot] & 0xffffffff) for r in updates
                 if (r['current'] + d) & 0xffff in committed]
        rate = sum(a == b for a, b in pairs) / len(pairs) if pairs else 0.0
        if best is None or (rate, -abs(d)) > best[0]:
            best = ((rate, -abs(d)), d)
    d = best[1]
    return {(r['current'] + d) & 0xffff: r['consumed'][slot] & 0xffffffff for r in updates}, d, best[0][0]


def taps(records, bit=0x4):
    """Every tap: its passes (dropped or committed), whether the game got it, and whether it was carried."""
    decided = sorted((r for r in records if r['flags'] & LOCKSTEP and r['samples']), key=lambda r: r['pass'])
    used, offset, rate = consumed_by_frame(records)
    out, current = [], None
    for i, r in enumerate(decided):
        held = bool(r['sample'] & bit)
        if held and current is None:
            current = {'passes': [], 'first_tick': r['tick']}
            out.append(current)
        if current is not None and held:
            current['passes'].append('%d%s' % (r['pass'], 'C' if r['flags'] & COMMIT else 'D'))
            current['last_index'] = i
        if not held:
            current = None
    for t in out:
        first = int(t['passes'][0][:-1])
        commit = next((r for r in decided if r['pass'] >= first and r['flags'] & COMMIT), None)
        got = used.get(commit['send']) if commit else None
        t['frame'] = commit['send'] if commit else None
        t['consumed'] = None if got is None else '%#x' % got
        t['jumped'] = bool(got is not None and got & bit)
        t['all_dropped'] = all(p.endswith('D') for p in t['passes'])
        t['carried'] = t['all_dropped'] and t['jumped']
        del t['last_index']
    return out, {'offset': offset, 'match_rate': rate}


TICKS_PER_S = 19_200_000.0


def align(found, sent, window_s=0.15):
    """Wall time = tick / 19.2 MHz + offset: the offset (from every tap-call / tap pair) that puts the most taps within
    `window_s` of a tap call; then each tap's matching call. Robust to a tap Eden never delivered (shorter than a
    frame), which breaks matching by count."""
    seconds = [t['first_tick'] / TICKS_PER_S for t in found]
    calls = [c['sent'] for c in sent]
    best = None
    for c in calls:
        for s in seconds:
            off = c - s
            hits = [min(range(len(calls)), key=lambda i: abs(calls[i] - (x + off))) for x in seconds]
            near = [abs(calls[i] - (x + off)) for i, x in zip(hits, seconds)]
            score = (sum(d <= window_s for d in near), -sum(d for d in near if d <= window_s))
            if best is None or score > best[0]:
                best = (score, off, hits, near)
    _, off, hits, near = best
    for t, i, d in zip(found, hits, near):
        t['call'] = i if d <= window_s else None
        t['call_gap_s'] = round(d, 3)
    return off


def carries(found, lines, bit=0x4, within_s=0.2):
    """Marks each tap run that a carry line (`<tick> carry n= bits= …`, the same console's tick) delivered: the first
    line with the bit at or within `within_s` after the run's first tick."""
    parsed = []
    for line in lines:
        parts = line.split()
        if len(parts) > 3 and parts[1] == 'carry':
            fields = dict(p.split('=', 1) for p in parts[2:] if '=' in p)
            if int(fields.get('bits', '0'), 16) & bit:
                parsed.append((int(parts[0]), int(fields.get('n', '0'))))
    used = set()
    for t in found:
        for tick, n in parsed:
            if n not in used and 0 <= tick - t['first_tick'] <= within_s * TICKS_PER_S:
                t['carry_line'] = n
                used.add(n)
                break
    return len(parsed), len(used)


def by_call(found):
    """Tap runs grouped by the tap call they matched (a carried press can show as two runs: the dropped pass, then the
    commit the carry put it in); a run with no call is its own tap."""
    groups = {}
    for i, t in enumerate(found):
        key = ('call', t['call']) if t.get('call') is not None else ('run', i)
        groups.setdefault(key, []).append(i)
    return list(groups.values())


def gif_times(path):
    from PIL import Image
    times, at = [], 0.0
    with Image.open(path) as im:
        for i in range(getattr(im, 'n_frames', 1)):
            im.seek(i)
            times.append(at)
            at += (im.info.get('duration') or 33) / 1000.0
    return times


def clip(gif, at_s, label, caption, marker, out_dir, before_s=0.9, after_s=1.4, slow=4.0, width=640, others=()):
    """`others`: (seconds from the chosen tap, text) of the neighbouring taps, marked in green while they happen."""
    from PIL import Image, ImageDraw, ImageFont
    times = gif_times(gif)
    picks = [i for i, t in enumerate(times) if at_s - before_s <= t <= at_s + after_s]
    frames_dir = out_dir / ('%s-frames' % label)
    frames_dir.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
        small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
    except OSError:
        font = small = ImageFont.load_default()
    out_frames, durations = [], []
    with Image.open(gif) as im:
        for n, i in enumerate(picks):
            im.seek(i)
            frame = im.convert('RGB')
            h = round(frame.height * width / frame.width)
            frame = frame.resize((width, h), Image.LANCZOS)
            canvas = Image.new('RGB', (width, h + 34), (0, 0, 0))
            canvas.paste(frame, (0, 34))
            draw = ImageDraw.Draw(canvas)
            draw.text((8, 6), caption, fill=(255, 255, 255), font=font)
            t = times[i] - at_s
            draw.text((width - 150, 6), '%+.2f s  x1/%d' % (t, slow), fill=(200, 200, 200), font=small)
            box = (8, h - 6, width - 8, h + 28)
            if 0.0 <= t <= 0.45:
                draw.rectangle(box, fill=(200, 30, 30) if label == 'before' else (20, 120, 200))
                draw.text((16, h - 2), marker, fill=(255, 255, 255), font=small)
            else:
                for at, text in others:
                    if 0.0 <= t - at <= 0.45:
                        draw.rectangle(box, fill=(20, 140, 40))
                        draw.text((16, h - 2), text, fill=(255, 255, 255), font=small)
            canvas.save(frames_dir / ('%04d.png' % n))
            nxt = times[i + 1] if i + 1 < len(times) else times[i] + 0.033
            durations.append(max(20, int(round((nxt - times[i]) * 1000 * slow))))
            out_frames.append(canvas.convert('P', palette=Image.ADAPTIVE, colors=128))
    path = out_dir / ('%s.gif' % label)
    out_frames[0].save(path, save_all=True, append_images=out_frames[1:], duration=durations, loop=0, optimize=True)
    return path, len(out_frames), sum(durations) / 1000.0


def compose(left, right, out):
    """The two clips side by side (640 + 640 = 1280 wide), frame by frame on a shared timeline; the shorter clip
    holds its last frame."""
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
    cuts = sorted({t for t, _ in lf} | {t for t, _ in rf})
    total = max(lt, rt)
    out_frames, durations = [], []
    for n, t in enumerate(cuts):
        a = [f for s, f in lf if s <= t][-1]
        b = [f for s, f in rf if s <= t][-1]
        canvas = Image.new('RGB', (a.width + b.width, max(a.height, b.height)), (0, 0, 0))
        canvas.paste(a, (0, 0))
        canvas.paste(b, (a.width, 0))
        out_frames.append(canvas.convert('P', palette=Image.ADAPTIVE, colors=128))
        durations.append((cuts[n + 1] if n + 1 < len(cuts) else total) - t)
    out_frames[0].save(out, save_all=True, append_images=out_frames[1:], duration=durations, loop=0, optimize=True)
    return len(out_frames), total / 1000.0


def main(argv):
    if argv[:1] == ['compose']:
        n, seconds = compose(Path(argv[1]), Path(argv[2]), Path(argv[3]))
        print(json.dumps({'compose': argv[3], 'frames': n, 'seconds': seconds, 'bytes': Path(argv[3]).stat().st_size}))
        return 0
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--passes', required=True)
    p.add_argument('--taps', required=True)
    p.add_argument('--gif')
    p.add_argument('--label', choices=('before', 'after'), required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--carry-log')
    p.add_argument('--bit', default='0x4')
    p.add_argument('--latency-s', type=float, default=0.0, help='added to a tap call time to place it in the video')
    p.add_argument('--tap', type=int, help='the tap to show (0-based; default: the first lost / carried one)')
    a = p.parse_args(argv)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = decode(Path(a.passes).read_bytes())
    found, check = taps(records, int(a.bit, 16))
    log = json.loads(Path(a.taps).read_text())
    sent = log['taps']
    offset = align(found, sent) if found and sent else None
    summary = {'label': a.label, 'tap_runs': len(found), 'taps_sent': len(sent), 'consumption': check,
               'wall_offset_s': offset, 'matched_calls': len({t['call'] for t in found if t.get('call') is not None})}
    if a.carry_log:
        lines = [l for l in Path(a.carry_log).read_text().splitlines() if ' carry ' in l]
        total, matched = carries(found, lines, int(a.bit, 16))
        summary.update(carry_lines=total, carry_lines_matched=matched)
    groups = by_call(found)
    # A tap: one tap call (or an unmatched run); a jump: the game received it in at least one of its runs.
    summary['taps'] = len(groups)
    summary['jumps'] = sum(any(found[i]['jumped'] for i in g) for g in groups)
    summary['lost'] = [g[0] for g in groups if not any(found[i]['jumped'] for i in g)]
    summary['carried'] = [g[-1] for g in groups if any(found[i].get('carry_line') or found[i]['carried'] for i in g)]
    summary['runs'] = found
    taps_n, jumps = summary['taps'], summary['jumps']
    pick = [i for i in (summary['lost'] if a.label == 'before' else summary['carried'])
            if found[i].get('call') is not None and (a.tap is None or i == a.tap)][:1]
    if a.gif and pick:
        k = pick[0]
        t0 = log['recording_start_acked']
        at_s = found[k]['first_tick'] / TICKS_PER_S + offset - t0 + a.latency_s
        # "jumps": Jump inputs the game frame received (the probe's consumed input), not airborne frames on screen.
        caption = ('Before (no fix): %d taps -> %d jumps' if a.label == 'before'
                   else 'After (with fix): %d taps -> %d jumps') % (taps_n, jumps)
        number = {i: n + 1 for n, g in enumerate(groups) for i in g}
        mine = next(g for g in groups if k in g)
        first = found[mine[0]]
        at_s = first['first_tick'] / TICKS_PER_S + offset - log['recording_start_acked'] + a.latency_s
        marker = ('Jump tapped (tap %d): dropped, no jump' if a.label == 'before'
                  else 'Jump tapped (tap %d): dropped, carried: jump') % number[k]
        others = []
        for g in groups:
            if g is mine:
                continue
            t = found[g[0]]
            gap = (t['first_tick'] - first['first_tick']) / TICKS_PER_S
            if abs(gap) < 2.0:
                got = any(found[i]['jumped'] for i in g)
                carried = any(found[i].get('carry_line') for i in g)
                text = 'Jump tapped (tap %d): %s' % (number[g[0]], 'dropped, carried: jump' if carried else
                                                     'jump' if got else 'dropped, no jump')
                others.append((gap, text))
        path, n, seconds = clip(Path(a.gif), at_s, a.label, caption, marker, out_dir, others=others)
        summary['clip'] = {'tap': k, 'at_s': round(at_s, 3), 'path': str(path), 'frames': n, 'seconds': seconds,
                           'bytes': path.stat().st_size}
    elif a.gif:
        summary['clip'] = 'not made: no %s tap matched to a tap call' % ('lost' if a.label == 'before' else 'carried')
    (out_dir / ('%s-taps.json' % a.label)).write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'runs'}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
