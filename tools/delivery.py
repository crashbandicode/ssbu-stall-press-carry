#!/usr/bin/env python3
"""Which one-frame inputs reached the game: Jump and A presses, and left-stick flicks (left, right, down).

/usr/bin/python3 -I tools/delivery.py --passes passes-00.bin [--passes passes-01.bin ...] [--inputs m2-inputs.json] \
    [--out report.json]

Reads one console's ssbu-input-cadence-probe records (64-byte, `passes-NN.bin`). A stimulus run is a run of decided
passes whose local sample shows the input: the Jump bit (0x4), the Attack bit (0x1), or the left stick at flick strength
(84 of 120) to the left, the right or down. Each run is judged by the input the game frame consumed for the first
commit at or after the run's first pass (the probe's consumed cell, matched to committed frames as `press_clip.py`
does):
- `delivered`: the consumed input shows the stimulus;
- `all_dropped`: every pass of the run was dropped (a stalled pass at the steady lead), so the plain game loses it;
- `carried`: all dropped and still delivered: ssbu-stall-press-carry's doing.
- `lost_under_0_1_0`: all dropped and a stick flick. 0.1.0 carries buttons only and never writes the stick bytes, so
  it can't deliver these. Buttons carry the same way in both versions.
`--inputs` adds the harness's call counts per kind (the wall-time log). Per probe session. Read-only on its inputs."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import press_clip as pc  # noqa: E402

FLICK = 84
STIMULI = ('jump', 'attack', 'stick_left', 'stick_right', 'stick_down')


def stick(value):
    """The left stick (x, y) of a 64-bit mapped input: bytes 4 and 5 as i8."""
    x = (value >> 32) & 0xff
    y = (value >> 40) & 0xff
    return (x - 256 if x > 127 else x, y - 256 if y > 127 else y)


def shows(value, kind):
    if value is None:
        return False
    x, y = stick(value)
    return {'jump': bool(value & 0x4), 'attack': bool(value & 0x1), 'stick_left': x <= -FLICK,
            'stick_right': x >= FLICK, 'stick_down': y <= -FLICK}[kind]


def consumed_full(records):
    """frame -> the local slot's whole consumed input (sticks included), at `press_clip`'s frame offset."""
    _, offset, rate = pc.consumed_by_frame(records)
    slot = next(((r['mask'] & -r['mask']).bit_length() - 1 for r in records if r['flags'] & pc.LOCKSTEP and r['mask']), 0)
    slot = min(slot, 1)
    updates = [r for r in records if r['flags'] & pc.UPDATE and r['flags'] & pc.LOCKSTEP and r['flags'] & pc.MANAGER]
    return {(r['current'] + offset) & 0xffff: r['consumed'][slot] for r in updates}, offset, rate


def runs(records, kind):
    decided = sorted((r for r in records if r['flags'] & pc.LOCKSTEP and r['samples']), key=lambda r: r['pass'])
    used, offset, rate = consumed_full(records)
    out, current = [], None
    for r in decided:
        if shows(r['sample'], kind):
            if current is None:
                current = {'passes': [], 'first_pass': r['pass'], 'first_tick': r['tick']}
                out.append(current)
            current['passes'].append('%d%s' % (r['pass'], 'C' if r['flags'] & pc.COMMIT else 'D'))
        else:
            current = None
    for run in out:
        commit = next((r for r in decided if r['pass'] >= run['first_pass'] and r['flags'] & pc.COMMIT), None)
        got = used.get(commit['send']) if commit else None
        run['frame'] = commit['send'] if commit else None
        run['consumed'] = None if got is None else '%#x' % got
        run['delivered'] = shows(got, kind)
        run['all_dropped'] = all(p.endswith('D') for p in run['passes'])
        run['carried'] = run['all_dropped'] and run['delivered']
        run['lost_under_0_1_0'] = run['all_dropped'] and kind.startswith('stick')
    return out, {'offset': offset, 'match_rate': rate}


def summarize(records):
    sessions = sorted({r['session'] for r in records})
    report = {}
    for s in sessions:
        recs = [r for r in records if r['session'] == s]
        per = {}
        for kind in STIMULI:
            found, check = runs(recs, kind)
            per[kind] = {'runs': len(found),
                         'delivered': sum(r['delivered'] for r in found),
                         'all_dropped': sum(r['all_dropped'] for r in found),
                         'carried': sum(r['carried'] for r in found),
                         'lost_under_0_1_0': sum(r['lost_under_0_1_0'] for r in found),
                         'not_delivered': [r for r in found if not r['delivered']][:10]}
            per['frame_match'] = check
        report[str(s)] = per
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--passes', action='append', required=True)
    ap.add_argument('--inputs')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    records = []
    for p in a.passes:
        records += pc.decode(Path(p).read_bytes())
    out = {'passes': a.passes, 'sessions': summarize(records)}
    if a.inputs:
        sent = json.loads(Path(a.inputs).read_text()).get('inputs', [])
        kinds = sorted({i.get('kind') for i in sent})
        out['calls'] = {k: sum(1 for i in sent if i.get('kind') == k) for k in kinds}
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
