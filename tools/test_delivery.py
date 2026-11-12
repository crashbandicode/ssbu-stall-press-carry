#!/usr/bin/env python3
"""Host tests for delivery.py: /usr/bin/python3 -I tools/test_delivery.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import delivery as dv  # noqa: E402
import press_clip as pc  # noqa: E402

NEUTRAL = 0x8000


def with_stick(buttons, x, y, right=False):
    s = 48 if right else 32
    return buttons | (x & 0xff) << s | (y & 0xff) << (s + 8)


def record(p, flags, send, current, sample, consumed):
    values = (1000 + p * 320000, p, flags, 1, 3, 3, send & 0xffff, current & 0xffff, 1, 1, 0, 1, sample, 0,
              consumed, 0, 1, pc.MAGIC)
    return pc.RECORD.pack(*values)


def simulate(inputs, stalls, carry, n=200):
    """The lockstep at the steady lead (drop on a stall), each update consuming the committed sample of `current`.
    `inputs`: pass -> sample. `carry`: None (the plain game), '0.1.0' (dropped press bits ORed into the next commit)
    or '0.2.0' (that, plus a dropped flick put into the next commit when the stick has gone back)."""
    blob, committed = b'', {}
    current, send, last, pending, flick = 100, 104, NEUTRAL, 0, None
    for p in range(n):
        stalled = p in stalls
        if not stalled:
            current += 1
        sample = inputs.get(p, NEUTRAL)
        commit = send - current <= 3
        flags = pc.LOCKSTEP | pc.MANAGER | (pc.COMMIT if commit else 0) | (0 if stalled else pc.UPDATE)
        s_send = send
        if commit:
            out = sample
            if carry:
                out |= pending
            if carry == '0.2.0' and flick is not None:
                for mask, right in ((0xffff << 32, False), (0xffff << 48, True)):
                    if dv.stick(sample, right) == (0, 0) and dv.stick(flick, right) != (0, 0):
                        out = (out & ~mask) | (flick & mask)
            committed[send] = out
            last, pending, flick, send = sample, 0, None, send + 1
        else:
            pending |= sample & ~last & 0xffff7f7f
            if dv.stick(sample) != (0, 0) or dv.stick(sample, True) != (0, 0):
                flick = sample
        blob += record(p, flags, s_send, current, sample, committed.get(current, 0))
    return pc.decode(blob)


INPUTS = {30: NEUTRAL | 0x4,                       # a Jump tap on a committed pass
          60: with_stick(NEUTRAL, 120, 0),         # a dash flick on a committed pass
          90: NEUTRAL | 0x4,                       # a Jump tap on a dropped pass
          120: with_stick(NEUTRAL, -120, 0),       # a dash flick on a dropped pass
          150: with_stick(NEUTRAL, 0, -120),       # a fast-fall flick on a dropped pass
          170: with_stick(NEUTRAL, 0, 120, True)}  # a C-stick up flick on a dropped pass
STALLS = {90, 120, 150, 170}


def count(records, kind):
    found, check = dv.runs(records, kind)
    # A carried press makes its frame's consumed input differ from the local sample, so a carry run is just under 1.
    assert check['offset'] == 0 and check['match_rate'] > 0.98, check
    return [(r['delivered'], r['all_dropped'], r['carried'], r['lost_under_0_1_0']) for r in found]


class Delivery(unittest.TestCase):
    def test_the_plain_game_loses_every_input_on_a_dropped_pass(self):
        recs = simulate(INPUTS, STALLS, None)
        self.assertEqual(count(recs, 'jump'), [(True, False, False, False), (False, True, False, False)])
        self.assertEqual(count(recs, 'stick_right'), [(True, False, False, False)])
        self.assertEqual(count(recs, 'stick_left'), [(False, True, False, True)])
        self.assertEqual(count(recs, 'stick_down'), [(False, True, False, True)])

    def test_0_1_0_carries_the_jump_but_not_the_flicks(self):
        recs = simulate(INPUTS, STALLS, '0.1.0')
        self.assertEqual(count(recs, 'jump')[1], (True, True, True, False))
        self.assertEqual(count(recs, 'stick_left'), [(False, True, False, True)])
        self.assertEqual(count(recs, 'stick_down'), [(False, True, False, True)])

    def test_0_2_0_carries_both(self):
        recs = simulate(INPUTS, STALLS, '0.2.0')
        self.assertEqual(count(recs, 'jump')[1], (True, True, True, False))
        self.assertEqual(count(recs, 'stick_left'), [(True, True, True, True)])
        self.assertEqual(count(recs, 'stick_down'), [(True, True, True, True)])
        self.assertEqual(count(recs, 'cstick_up'), [(True, True, True, True)])
        self.assertEqual(count(recs, 'stick_up'), [])

    def test_the_c_stick_is_lost_without_0_2_0(self):
        for carry in (None, '0.1.0'):
            self.assertEqual(count(simulate(INPUTS, STALLS, carry), 'cstick_up'), [(False, True, False, True)])

    def test_the_summary_counts_per_session(self):
        report = dv.summarize(simulate(INPUTS, STALLS, '0.2.0'))
        s = report['1']
        self.assertEqual((s['jump']['runs'], s['jump']['delivered'], s['jump']['carried']), (2, 2, 1))
        self.assertEqual((s['stick_left']['runs'], s['stick_left']['carried'], s['stick_left']['lost_under_0_1_0']),
                         (1, 1, 1))
        self.assertEqual(s['attack']['runs'], 0)

    def test_stick_bytes_are_signed(self):
        self.assertEqual(dv.stick(with_stick(0, -120, 87)), (-120, 87))
        self.assertEqual(dv.stick(with_stick(0, -120, 87, True), True), (-120, 87))
        self.assertEqual(dv.stick(with_stick(0, -120, 87, True)), (0, 0))
        self.assertTrue(dv.shows(with_stick(0, 0, -84), 'stick_down'))
        self.assertFalse(dv.shows(with_stick(0, 83, 0), 'stick_right'))
        self.assertTrue(dv.shows(with_stick(0, -90, 0, True), 'cstick_left'))
        self.assertFalse(dv.shows(with_stick(0, -90, 0, True), 'stick_left'))
        self.assertFalse(dv.shows(None, 'jump'))


if __name__ == '__main__':
    unittest.main()
