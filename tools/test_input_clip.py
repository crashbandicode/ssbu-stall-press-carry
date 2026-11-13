#!/usr/bin/env python3
"""Host tests for input_clip.py: /usr/bin/python3 -I tools/test_input_clip.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import input_clip as ic  # noqa: E402
import press_clip as pc  # noqa: E402

NEUTRAL = 0x8000
TICK0, PERIOD = 1000, 320000          # one pass every 16.7 ms of the 19.2 MHz tick
WALL = 5000.0                          # wall time = tick / 19.2 MHz + WALL


def left(x):
    return (x & 0xff) << 32


SAMPLES = {'jump': NEUTRAL | 0x4,
           'lsmash': NEUTRAL | 0x201 | left(120),
           'cstick': NEUTRAL | 0x21 | 0x80 | left(-100)}


def record(p, flags, send, current, sample, consumed, session):
    values = (TICK0 + p * PERIOD, p, flags, 1, 3, 3, send & 0xffff, current & 0xffff, 1, 1, 0, 1, sample, 0,
              consumed, 0, session, pc.MAGIC)
    return pc.RECORD.pack(*values)


def simulate(inputs, stalls, fix, session=1, n=140):
    """The lockstep at the steady lead (a stalled pass drops its sample); each update consumes the committed record.
    The probe reads the commit after the fix. `fix`: what a dropped sample held is put into the next commit when that
    commit's own sample lacks it, with one diag carry line."""
    blob, committed, lines = b'', {}, []
    current, send, pending = 100, 104, None
    for p in range(n):
        stalled = p in stalls
        if not stalled:
            current += 1
        sample = inputs.get(p, NEUTRAL)
        flags = pc.LOCKSTEP | pc.MANAGER | (0 if stalled else pc.COMMIT | pc.UPDATE)
        s_send, seen = send, sample
        if not stalled:
            if fix and pending is not None and sample == NEUTRAL:
                seen = pending
                lines.append('%d carry n=%d bits=0x1 flick=carried stick=left cstick=no before=%#x after=%#x '
                             'ring_lost=0' % (TICK0 + p * PERIOD + 50, len(lines) + 1, sample, seen))
            committed[send] = seen
            pending, send = None, send + 1
        elif sample != NEUTRAL:
            pending = sample
        blob += record(p, flags, s_send, current, seen, committed.get(current, 0), session)
    return pc.decode(blob), lines


def calls_for(plan):
    """plan: (pass, kind, x)."""
    return [{'kind': kind, 'sent': (TICK0 + p * PERIOD) / pc.TICKS_PER_S + WALL - 0.004, 'x': x, 'y': 0.0,
             'buttons': {'jump': ['x'], 'lsmash': ['a']}.get(kind, []), 'rec': 0} for p, kind, x in plan]


# One of each kind on a dropped pass (30, 60, 90), one of each on a committed pass (110, 120, 130).
PLAN = [(30, 'jump', 0.0), (60, 'lsmash', 1.0), (90, 'cstick', -1.0),
        (110, 'jump', 0.0), (120, 'lsmash', 1.0), (130, 'cstick', -1.0)]
INPUTS = {p: SAMPLES[k] for p, k, _ in PLAN}
STALLS = {30, 60, 90}


def judged(fix):
    records, lines = simulate(INPUTS, STALLS, fix)
    calls = calls_for(PLAN)
    s, found, off = ic.session_runs(records, calls)
    ic.match_carries(found, ic.parse_carries(lines))
    return ic.judge(found, calls, []), off


class InputClip(unittest.TestCase):
    def test_signatures(self):
        self.assertEqual([k for k in ic.KINDS if ic.shows(SAMPLES['lsmash'], k)], ['lsmash'])
        self.assertEqual([k for k in ic.KINDS if ic.shows(SAMPLES['cstick'], k)], ['cstick'])
        self.assertEqual([k for k in ic.KINDS if ic.shows(SAMPLES['jump'], k)], ['jump'])
        self.assertFalse(ic.shows(NEUTRAL | 0x201 | left(60), 'lsmash'))     # a tilt, not a flick

    def test_without_the_fix_the_inputs_on_dropped_passes_are_lost(self):
        attempts, off = judged(False)
        self.assertAlmostEqual(off, WALL, places=2)
        self.assertEqual([(e['kind'], e['outcome']) for e in attempts],
                         [('jump', 'lost'), ('lsmash', 'lost'), ('cstick', 'lost'),
                          ('jump', 'delivered'), ('lsmash', 'delivered'), ('cstick', 'delivered')])

    def test_with_the_fix_they_are_carried(self):
        attempts, _ = judged(True)
        self.assertEqual([e['outcome'] for e in attempts], ['carried'] * 3 + ['delivered'] * 3)
        self.assertEqual(attempts[1]['patterns'], ['DC'])
        self.assertEqual(attempts[1]['carry']['before'], '0x8000')

    def test_a_split_input_is_not_called_lost(self):
        # The stick reached a committed sample a pass before the dropped one with A: the game got the stick.
        inputs = dict(INPUTS)
        inputs[59] = NEUTRAL | left(120)
        records, _ = simulate(inputs, STALLS, False)
        calls = calls_for(PLAN)
        _, found, _ = ic.session_runs(records, calls)
        self.assertEqual(ic.judge(found, calls, [])[1]['outcome'], 'partly_lost')
        self.assertTrue(ic.part(NEUTRAL | left(120), 'lsmash'))
        self.assertFalse(ic.part(NEUTRAL | left(20), 'lsmash'))

    def test_a_carry_line_on_another_commit_is_not_matched(self):
        records, lines = simulate(INPUTS, STALLS, True)
        calls = calls_for(PLAN)
        _, found, _ = ic.session_runs(records, calls)
        later = ['%d%s' % (int(l.split()[0]) + PERIOD, l[len(l.split()[0]):]) for l in lines]
        self.assertEqual(ic.match_carries(found, ic.parse_carries(later)), 0)
        self.assertEqual([e['outcome'] for e in ic.judge(found, calls, [])][:3], ['delivered'] * 3)

    def test_the_session_the_calls_line_up_with_is_used(self):
        other, _ = simulate({40: SAMPLES['jump']}, set(), False, session=1)
        mine, _ = simulate(INPUTS, STALLS, False, session=2)
        s, found, _ = ic.session_runs(other + mine, calls_for(PLAN))
        self.assertEqual((s, len(found)), (2, 6))

    def test_listing_places_each_input_in_its_recording(self):
        records, _ = simulate(INPUTS, STALLS, False)
        with tempfile.TemporaryDirectory() as d:
            passes = Path(d) / 'passes-00.bin'
            passes.write_bytes(b''.join(pc.RECORD.pack(r['tick'], r['pass'], r['flags'], 1, 3, 3, r['send'],
                                                       r['current'], r['samples'], r['mask'], 0, 1, r['sample'], 0,
                                                       r['consumed'][0], r['consumed'][1], r['session'], pc.MAGIC)
                                        for r in records))
            start = (TICK0 + 20 * PERIOD) / pc.TICKS_PER_S + WALL
            log = {'flicks': calls_for(PLAN), 'recordings': [{'path': str(Path(d) / 'rec.gif'), 'start_acked': start}]}
            inputs = Path(d) / 'inputs.json'
            inputs.write_text(json.dumps(log))
            summary = ic.listing([str(passes)], str(inputs))
        self.assertEqual(summary['by_kind']['jump']['lost'], 1)
        self.assertAlmostEqual(summary['attempts'][0]['at_s'], 10 * PERIOD / pc.TICKS_PER_S, places=2)

    def test_a_clip_holds_the_input_and_stays_within_15_fps(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'rec.gif'
            frames = [Image.new('RGB', (640, 360), (i * 4 % 256, 0, 0)) for i in range(90)]
            frames[0].save(src, save_all=True, append_images=frames[1:], duration=[33] * 90, loop=0)
            sent = {'stick': 'right', 'x': -1.0, 'y': 0.0, 'buttons': []}
            path, n, seconds, pngs = ic.render(src, 1.5, 'cstick', sent, 'received', 'With the fix (0.2.0)', Path(d),
                                               'after', 0.6, 1.2, hold_at_s=1.0, stall=(-0.35, 0.35))
            with Image.open(path) as im:
                size = im.size
                durations = []
                for i in range(im.n_frames):
                    im.seek(i)
                    durations.append(im.info['duration'])

            def orange(png):
                with Image.open(png) as f:
                    bar = f.convert('RGB').crop((200, 0, 480, 28))
                    return any(r > 200 and 120 < g < 200 and b < 90
                               for r, g, b in (bar.getpixel((x, y)) for x in range(bar.width) for y in range(bar.height)))
            starts = [at for at, _ in pngs]
            self.assertTrue(orange(pngs[starts.index(1000)][1]))     # the stall note during the hold
            self.assertFalse(orange(pngs[0][1]))                     # not 0.6 s before the input
        self.assertEqual(size, (640, 540))
        self.assertTrue(all(ms >= 70 for ms in durations), durations)
        self.assertIn(1000, starts)                          # the hold starts at 1.0 s
        k = starts.index(1000)
        self.assertEqual(durations[k:k + 3], [170, 170, 170])  # the 0.5 s hold, in three steps
        self.assertLess(seconds, 4.5)

    def test_the_display_names_whose_input_it_is(self):
        from PIL import Image, ImageDraw
        self.assertEqual(ic.panel_title('Sephiroth'), "Sephiroth's input (harness)")
        self.assertEqual(ic.panel_title(), 'input pressed (harness)')
        sent = {'stick': None, 'x': 0.0, 'y': 0.0, 'buttons': ['x']}
        titles = []
        for who in (None, 'Sephiroth'):
            im = Image.new('RGB', (640, 150))
            ic.draw_panel(ImageDraw.Draw(im), 0, 'jump', sent, True, 1, 'received', who=who)
            titles.append(im.crop((0, 0, 300, 22)).tobytes())
        self.assertNotEqual(titles[0], titles[1])

    def test_two_clips_side_by_side_have_no_short_frames(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            left, right, out = Path(d) / 'l.gif', Path(d) / 'r.gif', Path(d) / 'pair.gif'
            for path, ms in ((left, [70, 80] * 20), (right, [75] * 39)):
                frames = [Image.new('RGB', (64, 54), (i * 6 % 256, 0, 0)) for i in range(len(ms))]
                frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0)
            n, seconds = ic.compose(left, right, out)
            with Image.open(out) as im:
                size = im.size
                durations = []
                for i in range(im.n_frames):
                    im.seek(i)
                    durations.append(im.info['duration'])
        self.assertEqual(size, (128, 54))
        self.assertGreaterEqual(min(durations), 70)
        self.assertEqual(sum(durations), 3000)
        self.assertAlmostEqual(seconds, 3.0)


if __name__ == '__main__':
    unittest.main()
