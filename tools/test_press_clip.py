#!/usr/bin/env python3
"""Host tests for press_clip.py's tap analysis: /usr/bin/python3 -I tools/test_press_clip.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import press_clip as pc  # noqa: E402


def record(p, flags, send, current, sample, consumed):
    values = (1000 + p * 320000, p, flags, 1, 3, 3, send & 0xffff, current & 0xffff, 1, 1, 0, 1, sample, 0,
              consumed, 0, 1, pc.MAGIC)
    return pc.RECORD.pack(*values)


def simulate(taps_at, stalls, carry, n=200):
    """The lockstep at the steady lead (drop on a stall), each update consuming the committed sample of `current`;
    `carry` ORs dropped presses into the next commit as the plugin does."""
    blob, committed = b'', {}
    current, send, last, pending = 100, 104, 0, 0
    for p in range(n):
        stalled = p in stalls
        if not stalled:
            current += 1
        sample = 0x8004 if p in taps_at else 0x8000
        commit = send - current <= 3
        flags = pc.LOCKSTEP | pc.MANAGER | (pc.COMMIT if commit else 0) | (0 if stalled else pc.UPDATE)
        s_send = send
        if commit:
            committed[send] = sample | (pending if carry else 0)
            last, pending, send = sample, 0, send + 1
        else:
            pending |= sample & ~last & 0xffff7f7f
        blob += record(p, flags, s_send, current, sample, committed.get(current, 0))
    return pc.decode(blob)


class Taps(unittest.TestCase):
    def test_a_tap_on_a_dropped_pass_is_lost_without_the_carry(self):
        recs = simulate({40, 41, 90, 120}, stalls={90}, carry=False)
        found, check = pc.taps(recs)
        self.assertEqual(check['match_rate'], 1.0)
        self.assertEqual([t['jumped'] for t in found], [True, False, True])
        self.assertEqual(found[1]['passes'], ['90D'])
        self.assertFalse(found[1]['carried'])

    def test_the_carry_delivers_it(self):
        recs = simulate({40, 41, 90, 120}, stalls={90}, carry=True)
        found, _ = pc.taps(recs)
        self.assertEqual([t['jumped'] for t in found], [True, True, True])
        self.assertTrue(found[1]['carried'])
        self.assertEqual([t['carried'] for t in found], [False, True, False])

    def test_a_tap_spanning_a_drop_and_a_commit_is_not_a_carry(self):
        recs = simulate({90, 91}, stalls={90}, carry=False)
        (t,) = pc.taps(recs)[0]
        self.assertEqual((t['passes'], t['jumped'], t['carried']), (['90D', '91C'], True, False))


class Align(unittest.TestCase):
    def test_a_missing_tap_does_not_shift_the_others(self):
        # Five calls 0.8 s apart; the probe saw taps for calls 0, 1, 3, 4 (call 2 never reached the game), on a clock
        # 1000 s behind wall time with 20 ms latency.
        calls = [{'sent': 5000.0 + 0.8 * k} for k in range(5)]
        found = [{'first_tick': int((c['sent'] - 1000.0 + 0.02) * pc.TICKS_PER_S)} for k, c in enumerate(calls)
                 if k != 2]
        off = pc.align(found, calls)
        self.assertAlmostEqual(off, 1000.0, delta=0.05)
        self.assertEqual([t['call'] for t in found], [0, 1, 3, 4])


class Carries(unittest.TestCase):
    def test_carry_lines_mark_runs_and_split_runs_count_once(self):
        # Call 0: one run; call 1: a press in a dropped pass, released, then put into a commit by the carry: two runs.
        found = [{'first_tick': 1000, 'call': 0, 'jumped': True, 'carried': False},
                 {'first_tick': 20_000_000, 'call': 1, 'jumped': True, 'carried': True},
                 {'first_tick': 20_000_000 + 960_000, 'call': 1, 'jumped': True, 'carried': False}]
        lines = ['%d carry n=1 bits=0x4 before=0x8000 after=0x8004 ring_lost=0' % (20_000_000 + 960_000),
                 '%d carry n=2 bits=0x2 before=0x8000 after=0x8002 ring_lost=0' % 1000]
        total, matched = pc.carries(found, lines)
        self.assertEqual((total, matched), (1, 1))
        self.assertEqual([t.get('carry_line') for t in found], [None, 1, None])
        self.assertEqual(pc.by_call(found), [[0], [1, 2]])


if __name__ == '__main__':
    unittest.main()
