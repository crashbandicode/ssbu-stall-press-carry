#!/usr/bin/env python3
"""Host tests for flick_clip.py: /usr/bin/python3 -I tools/test_flick_clip.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flick_clip as fc  # noqa: E402
import press_clip as pc  # noqa: E402

NEUTRAL = 0x8000
TICK0, PERIOD = 1000, 320000          # one pass every 16.7 ms of the 19.2 MHz tick
WALL = 5000.0                          # wall time = tick / 19.2 MHz + WALL


def cstick(x, y):
    """A C-stick flick as the game maps it: Attack, Smash, AttackRaw, the C-stick bit and the left stick."""
    return NEUTRAL | 0x221 | fc.CSTICK_ON | (x & 0xff) << 32 | (y & 0xff) << 40


def record(p, flags, send, current, sample, consumed, session):
    values = (TICK0 + p * PERIOD, p, flags, 1, 3, 3, send & 0xffff, current & 0xffff, 1, 1, 0, 1, sample, 0,
              consumed, 0, session, pc.MAGIC)
    return pc.RECORD.pack(*values)


def simulate(inputs, stalls, fix, session=1, n=120):
    """The lockstep at the steady lead (a stalled pass drops its sample); each update consumes the committed record.
    The probe reads the commit after the fix (as on the Yoga). `fix`: the C-stick flick of a dropped sample is put into
    the next commit when that commit's own sample lacks it, with one diag carry line."""
    blob, committed, lines = b'', {}, []
    current, send, pending = 100, 104, None
    for p in range(n):
        stalled = p in stalls
        if not stalled:
            current += 1
        sample = inputs.get(p, NEUTRAL)
        commit = not stalled
        flags = pc.LOCKSTEP | pc.MANAGER | (pc.COMMIT if commit else 0) | (0 if stalled else pc.UPDATE)
        s_send, seen = send, sample
        if commit:
            if fix and pending is not None and not sample & fc.CSTICK_ON:
                seen = sample | pending
                lines.append('%d carry n=%d bits=0x221 flick=carried stick=left cstick=yes before=%#x after=%#x '
                             'ring_lost=0' % (TICK0 + p * PERIOD + 50, len(lines) + 1, sample, seen))
            committed[send] = seen
            pending, send = None, send + 1
        elif sample & fc.CSTICK_ON:
            pending = sample
        blob += record(p, flags, s_send, current, seen, committed.get(current, 0), session)
    return pc.decode(blob), lines


def calls_for(passes, xy=((1.0, 0.0),)):
    return [{'k': i, 'sent': (TICK0 + p * PERIOD) / pc.TICKS_PER_S + WALL - 0.004, 'x': xy[i % len(xy)][0],
             'y': xy[i % len(xy)][1]} for i, p in enumerate(passes)]


# Flick 1 on a committed pass; flick 2 on a dropped pass; flick 3 on a dropped pass that lasts into the commit.
INPUTS = {20: cstick(120, 0), 50: cstick(-120, 0), 80: cstick(0, 120), 81: cstick(0, 120)}
STALLS = {50, 80}
CALLS = calls_for([20, 50, 80], ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0)))


def run(fix):
    records, lines = simulate(INPUTS, STALLS, fix)
    session, runs, check, offset = fc.choose_session(records, CALLS)
    fc.match_carries(runs, fc.parse_carries(lines))
    return fc.judge(runs, CALLS), offset


class FlickClip(unittest.TestCase):
    def test_without_the_fix_a_flick_on_a_dropped_pass_is_lost(self):
        flicks, offset = run(False)
        self.assertAlmostEqual(offset, WALL, places=2)
        self.assertEqual([(f['flick'], f['direction'], f['delivered'], f['lost'], f['carried']) for f in flicks],
                         [(1, 'right', True, False, False), (2, 'left', False, True, False),
                          (3, 'up', True, False, False)])

    def test_with_the_fix_the_dropped_flick_is_carried_and_its_run_is_dropped_then_committed(self):
        flicks, _ = run(True)
        self.assertEqual([(f['flick'], f['delivered'], f['lost'], f['carried']) for f in flicks],
                         [(1, True, False, False), (2, True, False, True), (3, True, False, False)])
        self.assertEqual(flicks[1]['patterns'], ['DC'])
        self.assertEqual(flicks[1]['carry']['raw_had_it'], False)

    def test_a_flick_that_lasted_into_the_commit_is_not_called_carried(self):
        flicks, _ = run(True)
        self.assertEqual(flicks[2]['patterns'], ['DC'])
        self.assertIsNone(flicks[2]['carry'])
        self.assertFalse(flicks[2]['carried'])

    def test_a_carry_line_whose_commit_already_had_the_bit_is_not_a_carry(self):
        records, lines = simulate(INPUTS, STALLS, True)
        _, runs, _, _ = fc.choose_session(records, CALLS)
        fake = [l.replace('before=0x8000', 'before=0x80a1') for l in lines]
        fc.match_carries(runs, fc.parse_carries(fake))
        flicks = fc.judge(runs, CALLS)
        self.assertTrue(flicks[1]['carry']['raw_had_it'])
        self.assertFalse(flicks[1]['carried'])

    def test_a_carry_line_of_another_commit_is_not_matched(self):
        records, lines = simulate(INPUTS, STALLS, True)
        _, runs, _, _ = fc.choose_session(records, CALLS)
        later = ['%d%s' % (int(l.split()[0]) + PERIOD, l[len(l.split()[0]):]) for l in lines]
        self.assertEqual(fc.match_carries(runs, fc.parse_carries(later)), 0)
        self.assertFalse(any(f['carried'] for f in fc.judge(runs, CALLS)))

    def test_the_session_the_calls_line_up_with_is_used(self):
        # The other match's one flick can line up with one call at most.
        other, _ = simulate({30: cstick(120, 0)}, set(), False, session=1)
        mine, _ = simulate(INPUTS, STALLS, False, session=2)
        session, runs, _, _ = fc.choose_session(other + mine, CALLS)
        self.assertEqual(session, 2)
        self.assertEqual(len(runs), 3)

    def test_a_longer_session_at_the_same_spacing_does_not_win_a_tie(self):
        # The first match had more flicks at the same spacing, so it lines up with every call of the second one too.
        first, _ = simulate({p: cstick(120, 0) for p in range(20, 200, 30)}, set(), False, session=1, n=220)
        second, _ = simulate({20: cstick(120, 0), 50: cstick(120, 0), 80: cstick(120, 0)}, set(), False, session=2)
        session, runs, _, _ = fc.choose_session(first + second, calls_for([20, 50, 80]))
        self.assertEqual((session, len(runs)), (2, 3))
        self.assertEqual(fc.choose_session(first + second, calls_for([20, 50, 80]), session=1)[0], 1)

    def test_carry_lines_parse(self):
        line = ('27340000000000 carry n=7 bits=0x221 flick=carried stick=left cstick=yes before=0x8000 '
                'after=0x780000080a1 ring_lost=0')
        c = fc.parse_carries([line, '27340000000001 plugin=ssbu-stall-press-carry/0.2.0 result=installed'])
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0]['tick'], c[0]['n'], c[0]['cstick'], c[0]['before'], c[0]['after']),
                         (27340000000000, 7, 'yes', 0x8000, 0x780000080a1))

    def test_a_clip_stays_within_15_fps(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'rec.gif'
            frames = [Image.new('RGB', (320, 180), (i * 8 % 256, 0, 0)) for i in range(60)]
            frames[0].save(src, save_all=True, append_images=frames[1:], duration=[30] * 60, loop=0)
            path, n, seconds = fc.clip(src, 0.9, 'after', 'caption', 'marker', Path(d), 0.6, 0.6, slow=1.0)
            with Image.open(path) as im:
                durations = []
                for i in range(im.n_frames):
                    im.seek(i)
                    durations.append(im.info['duration'])
            self.assertEqual(len(durations), n)
            self.assertTrue(all(ms >= 67 for ms in durations), durations)
            self.assertAlmostEqual(seconds, 1.2, delta=0.1)
            self.assertEqual(im.size, (640, 394))

    def test_directions(self):
        self.assertEqual([fc.direction(*xy) for xy in ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (1.0, 1.0))],
                         ['right', 'left', 'up', 'down', 'diagonal'])


if __name__ == '__main__':
    unittest.main()
