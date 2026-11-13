# Eden results (2026-11-12 to 11-13)

## 0.1.0: `dbl-v-94eda31`, `dbl-f-8302362` and `dbl-g2-a666812` (2026-11-12)

**Setup:**
- **Host:** the Yoga. Quickplay pairs: two Eden instances on one host, TLS on, this pair the only one on the host.
- **Eden:** the SVC build `7d5de744`. GDB stub on both instances, no tracing, volume 0.
- **Save:** the 1-stock save `94e9b79e`.
- **Play:** the CPU pilot (0.2.4 diag, `diag.txt` p1=cpu, level 3) plays P1 on both consoles. The runner sends nothing
  during a match.
- **Measurement:** `ssbu-input-cadence-probe` 0.1.0 (`98e93a84…`) on both consoles. It judges each press seen first in
  a sample the lockstep dropped by the input the game frame of the next commit consumed. Its
  `docs/EDEN-RESULTS.md` has the per-session tables.

**Install line, both consoles, both runs** (the probe loaded first, so this plugin chained onto its branches):
`plugin=ssbu-stall-press-carry/0.1.0 commit=branch/near decided=branch/near result=installed heap_allocations=0`
(plus `diag_log=on` in F2).

| run | this plugin | matches (frames) | rows | `sync_end` |
|---|---|---|---|---|
| `dbl-v-94eda31` (V, before) | absent | 1,637 and ~5,880 | 13/13 PASS | normal, `desync_seen=0` on both at the same frame |
| `dbl-f-8302362` (F) | release `72c1acb2` (`8302362`) | 4,704, ~2,250 and ~4,810 | 14/14 PASS | normal, `desync_seen=0` on both at the same frame |
| `dbl-g2-a666812` (F2) | diag `dcec9d1a` (`a666812`, one line per carry); instance a capped at 85% speed (Eden `core.speed_limit`), so b waits for its input on about 15% of passes | 4,127, ~3,850 and ~4,610 | 14/14 PASS | normal, `desync_seen=0` on both at the same frame |

| run | console-frames | stalled passes | drops on stall | presses committed | first in a drop | delivered | lost | carried by this plugin |
|---|---|---|---|---|---|---|---|---|
| V | 15,049 | 237 | 221 | 344 | 2 | 0 | **2** | — |
| F | 23,549 | 288 | 264 | 507 | 5 | 5 | 0 | (no diag log) |
| F2 | 25,190 | 2,180 | 2,156 | 493 | 38 | 38 | 0 | 9 |

**Every carry in F2, console b:** this plugin's diag line (the first local sample before and after the carry), matched
to the probe's record of the same pass by the console's system tick
(`tools/cadence_report.py --carry-log carry-events.log passes-00.bin` in the probe repo):

| carry | bits | before | after | pass | committed | frame | consumed | delivered |
|---|---|---|---|---|---|---|---|---|
| 1 | 0x4 | 0x8000 | 0x8004 | 4774 | True | 957 | 0x8004 | True |
| 2 | 0x4 | 0xd000008000 | 0xd000008004 | 5498 | True | 1572 | 0x8004 | True |
| 3 | 0x201 | 0x8000 | 0x8201 | 5883 | True | 1907 | 0x8201 | True |
| 4 | 0x201 | 0x8008 | 0x8209 | 6854 | True | 2726 | 0x8209 | True |
| 5 | 0x4 | 0x8000 | 0x8004 | 8357 | True | 4016 | 0x8004 | True |
| 6 | 0x4 | 0x8000 | 0x8004 | 16271 | True | 3460 | 0x8004 | True |
| 7 | 0x4 | 0x8000 | 0x8004 | 16277 | True | 3465 | 0x8004 | True |
| 8 | 0x8 | 0x8000 | 0x8008 | 24148 | True | 3462 | 0x8008 | True |
| 9 | 0x4 | 0x8000 | 0x8004 | 25049 | True | 4236 | 0x8004 | True |

**What the carries show:**
- In each case the press (Jump `0x4`, Attack + AttackRaw `0x201`, Guard `0x8`) existed only in the dropped samples.
- The sample about to be committed no longer had it (`before`).
- The plugin added it (`after`), and the game frame consumed it.
- In the probe's own sequence, carry 1 is `4772D:0x8004 4773D:0x8000 4774C:0x8004 4775C:0x8000` (D = dropped,
  C = committed; the probe reads after this plugin).
- Without the plugin these nine presses would have been lost, as V's `0x802` press was.

## Card readiness: `dbl-k-02420ee` (2026-11-12 12:51–13:09Z)

**Plugins and settings:**
- **Both consoles:** the exact rc.10 card set (19 NROs from the 2026-11-12 install readback: TrainingRooms
  `97132e12`, Online Deluxe 0.10.5 `c37ee0ff`, CPU pilot 0.2.4 `abd305e6`, imgui_smash 1.0.2 `f72a6b8d` and the rest),
  this plugin's release `2b6ff493` (`02420ee`), the probe (measurement only) and the tile cursor.
- **The pilot** was armed through Online Deluxe's overlay on both consoles.
- **Instance a at 85% speed.** The GDB stub was on, TLS on, volume 0, and the 1-stock save was used.

**Release reproducibility:** `02420ee` built twice with fresh `CARGO_TARGET_DIR`s gives `2b6ff493…` both times
(`smash-training-lobby/artifacts/phase23/double-input/COMPLIANCE-stall-press-carry.md`).

**Results:**

| match | frames | `sync_end` (both consoles) | b: presses first in a drop | delivered | lost |
|---|---|---|---|---|---|
| m1 | 4,842 | `trigger=normal … desync_seen=0` at the same frame | 28 | 28 | 0 |
| m2 | 5,707 | `trigger=normal … desync_seen=0` at the same frame | 18 | 18 | 0 |

- **Stalls:** b stalled on 14% of its sampled passes (814 of 5,660 in m1, 931 of 6,642 in m2) and dropped 1,737
  samples on stalled passes. Consumed = committed on every frame on both consoles (4,846 and 5,711 frames checked).
- **Install lines:**
  - **This plugin:** `commit=branch/near decided=branch/near result=installed heap_allocations=0` on both (chained onto
    the probe's hooks, which loaded first).
  - **TrainingRooms:** `seams_skipped=[] seams_shadow_diff=[] seams_missing=[] result=installed heap_allocations=0` on
    both.
  - **Online Deluxe:** 0.10.5's overlay loaded (the pilot's `deluxe_overlay=found`, 54 overlay entries per console).
- **No crash:** no panic, abort, crash or Unmapped line on either console.
- **Without the probe:** not run in 0.1.0. 0.2.0 ran without it in integration's local wireless run (below) and
  took the stock path there (`stock/near`).

## The before/after GIF: `dbl-gb2-02420ee` and `dbl-ga-02420ee` (2026-11-12 13:21–13:40Z)

**Setup, both boots:**
- **Pair:** a Quickplay pair on the Yoga, GDB stub on, TLS on, muted, the 1-stock save.
- **Plugins:** the probe, the desync detector and the tile cursor; no CPU pilot. `dbl-ga-02420ee` adds this plugin's
  diag build `dcec9d1a` (the source of `02420ee`, plus one log line per carry).
- **Speed:** instance a at 70%, so b waits on about 30% of its passes.
- **Inputs:**
  - the runner taps Jump (X) on b 60 times, 16 ms each, 0.8 s apart by wall clock;
  - a gets a shield tap every 2 s so it isn't dropped as idle;
  - b is recorded at 640 px and 30 fps.
- **Analysis:** `tools/press_clip.py` (host tests in `tools/test_press_clip.py`):
  - **A tap** is a Jump tap call that reached b's mapping.
  - **A jump** is a tap the game frame received (the probe's consumed input).
  - **Placement in the video:** each tap is matched to its tap call through the probe's clock.

| boot | this plugin | taps | jumps | lost | carried (this plugin's carry lines matched to taps) |
|---|---|---|---|---|---|
| `dbl-gb2-02420ee` | absent | 60 | 52 | 8 (taps 5, 9, 15, 20, 39, 45, 49, 53) | — |
| `dbl-ga-02420ee` | diag `dcec9d1a` | 60 | 60 | 0 | 10 (10 of 10 carry lines, each `bits=0x4 before=0x8000 after=0x8004`) |

**An earlier boot, `dbl-gb-02420ee`** (a at 85%, 30 taps, 1280 px), lost none: 29 taps reached the mapping and 29
jumped. At 14% stalls no tap fell entirely on dropped passes, so the GIF boots used 70%.

**`docs/evidence/before.gif`** (tap 9 of `dbl-gb2-02420ee`):
- Tap 8 jumps and b lands.
- Tap 9's only sample is on a dropped pass, and b stays on the ground until tap 10.

**`docs/evidence/after.gif`** (tap 13 of `dbl-ga-02420ee`):
- Tap 13's sample is dropped as well.
- This plugin's carry line names it, the next frame receives it, and b jumps.

Both clips are 0.9 s before to 1.4 s after the tap, at quarter speed, 640 px wide. `before-after.gif` put them side
by side; it was the README GIF until 2026-11-13, when the three pairs below replaced it (it is in git history at
`2849027`).

## 0.2.0 with the desync detector 0.5.0: `proof-dc8ee988-r4` (2026-11-12 19:57–20:07Z)

Integration's Yoga pair (`smash-training-lobby/artifacts/phase23/double-input/runs/proof-dc8ee988-r4/`):
- **Builds:** the rc.11 card set (22 NROs) with this plugin's release `29dfd4ab` (`90cc614`, left stick only), the
  desync detector 0.5.0 `dc8ee988`, the probe and the tile cursor, on both consoles.
- **Setup:** a at 70% speed, played by the CPU pilot.
- **Inputs on b (m2):** in turn, a Jump tap (X, 16 ms), a dash flick (left stick ±1.0, 33 ms), a smash flick (the same
  plus an A tap), and a fast-fall (X, then the stick down for 33 ms); 0.8 s apart.
- **Install line:** `plugin=ssbu-stall-press-carry/0.2.0 commit=branch/near decided=branch/near stats=v1
  result=installed heap_allocations=0`.

**Counted by `tools/delivery.py`** (`dcc955f`) on b's probe records:

| input | calls | runs in b's samples | reached the game | carried (this plugin's counters) |
|---|---|---|---|---|
| Jump | 55 | 54 | 54 | 7 |
| A | 27 | 26 | 26 | 1 |
| left stick, sideways | 54 | 54 | 54 | 0 |
| left stick, down | 27 | 27 | 27 | 0 |

- **The probe's own count:** 21 press bits first seen in a dropped sample; 21 present at the next commit, 0 lost.
- **The detector's summary on b:** `stall_press rescued=8 (jump=7 attack=1 …) dropped=1729 committed=106 stalled=1729
  flick_carried=0 flick_lost=0`.
- **Why no flick carries:** b's stalls were nearly all one pass long (`stall_runs=0,1400,130,9,5,1,0,2`). The two-pass
  flicks always overlapped a committed pass, so the game got them without help. The flick rule and the right stick
  (`dcc955f`) are covered by host tests.
- **The match:** `sync_end trigger=normal … desync_seen=0` on both.

## 0.2.0 with both sticks: `proof-dc8ee988-r5` (2026-11-12 20:17–20:27Z)

The same pair and card set with this plugin's release `1bbc2d7b` (`dcc955f`). b's m2 inputs: 40 C-stick flicks and 16
diagonals on both sticks, one frame (16 ms) each, then Jump taps and left-stick dash, smash and fast-fall flicks; the
match ended at frame 2824.
- **Reached b's samples, and the game:** A 53/53, Jump 9/9, left stick left 18/18, right 20/20, up 14/14, down 18/18
  (`tools/delivery.py`; `runs/proof-dc8ee988-r5/delivery-b.json`).
- **This plugin's counters** (the detector's summary on b): `rescued=5 (attack=5) dropped=1220 committed=115
  flick_carried=11 flick_lost=0`.
- **The probe:** 40 press bits first seen in a dropped sample, 37 at the next commit; the 3 others are all `0x80`
  (C-stick in use), which the game's no-input test ignores and this plugin does not carry (`lostbits.py` beside the
  report).
- **The right stick's bytes (6–7) were 0 on all 4051 decided passes:** the game maps the C-stick into Attack, Smash,
  AttackRaw and `0x80` plus the left stick's direction.
- **The match:** `sync_end trigger=normal … desync_seen=0` on both.

## 0.2.0 with the C-stick bit: `proof-dc8ee988-r7` (2026-11-12 21:25–21:34Z)

The same pair with this plugin's release `749ed165` (`1d8d601`), the build on the card. r6 (same build) ended after 9
of 216 inputs; r7 ran 104 (40 C-stick flicks, 16 diagonals, 12 each of Jump, dash, smash and fast-fall) before the match
ended at frame 3000.
- **Reached b's samples, and the game:** Jump 23/23, A 59/59, C-stick bit (`0x80`) 46/46, left stick left 26/26,
  right 26/26, up 10/10, down 28/28 (`runs/proof-dc8ee988-r7/delivery-b.json`).
- **This plugin's counters:** `rescued=12 (jump=2 attack=10) dropped=1277 committed=139 flick_carried=15
  flick_lost=0`.
- **The probe:** 65 press bits first seen in a dropped sample, 65 at the next commit, **0 lost**. By bit
  (`lostbits-b.txt`): `0x80` present at the next commit 18 times, lost 0; r5 (`1bbc2d7b`, no C-stick bit): 8 and 3.
- **The match:** `sync_end trigger=normal … desync_seen=0` on both; the right-stick bytes 0 on all 4284 decided passes.

In the earlier attempt `proof-dc8ee988-r2`, the flicks were sent as a 16 ms stick lease followed at once by a neutral
call, and none reached the samples. The idle console a was removed by the game's own penalty evaluator
(`fault code=1`).

## The C-stick before/after GIF: `gif020-before-1` and `gif020-after-4` (2026-11-13 00:33–01:37Z)

The primary's order of 00:23Z (the operator asked whether the GIFs were updated): a C-stick flick that the game drops, lost without this
plugin and carried with it, made the way the 0.1.0 GIF was.

**Setup, every boot:** integration's proof pair (`proof-36027bb7-r10`'s setup): a Quickplay pair on the Yoga, the GDB
stub on both, TLS on, muted, the 1-stock save. Stage: `~/eden-runs/inputs-gif020/` on the Yoga.
- **Plugins:** the rc.11 card set with the desync detector 0.5.1 `36027bb7`, the probe and the tile cursor on both.
  - `gif020-before-1`: this plugin is not loaded (not in either plugin folder, no install line).
  - `gif020-after-2`, `gif020-after-4`: this plugin's diag build `89980fba`. That is the source of `1d8d601` (the
    card's release `749ed165`) plus one log line per carry. The release logs nothing per carry, so only the diag build
    lets each carry be matched to its frame, as 0.1.0's after clip was (`dcec9d1a`).
  - The diag build's install line: `plugin=ssbu-stall-press-carry/0.2.0 commit=branch/near decided=branch/near
    diag_log=on stats=v1 result=installed heap_allocations=0`.
- **Speed:** instance a at 70%.
- **Play:** a's CPU pilot (armed through Online Deluxe) attacks b. b fights with one-frame C-stick flicks:
  - one `input.stick` call on the right stick with a 16 ms lease and no neutral call;
  - right, left, up and down in turn, one every 2.5 s, until the match ends on a KO;
  - no walk-off.
- **Recording:** b, 640 px wide, 15 fps, from the end of the countdown to the match's end.
- **Matches:** two per boot (four in `gif020-after-4`), each after a check for pop-ups. Every match ended with
  `sync_end trigger=normal … desync_seen=0` on both consoles at the same frame, with no `notice_text` line. Every boot
  passed all its rows.
- **Analysis:** `tools/flick_clip.py` (host tests in `tools/test_flick_clip.py`).
  - **A flick** is a call that reached b's samples: a run of decided passes whose sample has the C-stick bit `0x80`.
  - **Reached the game** means the game frame of the next commit consumed `0x80`.
  - **Placement in the video:** through the probe's clock, lined up with the calls. The clock offset came out the same
    in every match of the three boots (1793101973.00 to .03 s).

| boot | match | calls | reached b's samples | reached the game | lost | carried (`cstick=yes` carry lines) |
|---|---|---|---|---|---|---|
| `gif020-before-1` | m-cs1 | 28 | 27 | 25 | 2 (flicks 6, 25) | — |
| `gif020-before-1` | m-cs2 | 16 | 9 | 9 | 0 | — |
| `gif020-after-2` | m-cs1 | 7 | 7 | 7 | 0 | 0 |
| `gif020-after-2` | m-cs2 | 12 | 10 | 10 | 0 | 2 |
| `gif020-after-4` | m-cs1 | 11 | 11 | 11 | 0 | 1 |
| `gif020-after-4` | m-cs2 | 49 | 48 | 48 | 0 | 8 |
| `gif020-after-4` | m-cs3 | 19 | 19 | 19 | 0 | 3 |
| `gif020-after-4` | m-cs4 | 17 | 17 | 17 | 0 | 4 |

- **The two lost flicks** were each in a single dropped pass, and the next frame consumed `0x8000` (no input).
- **Why m-cs2 of the before boot had few flicks:** b ran at about 44 passes a second there (62 in m-cs1). So it
  waited for a on only 9% of its decided passes (30% in m-cs1), and a 16 ms lease often fell between two of b's
  samples.
- **The detector's summaries on b:**
  - `gif020-after-4`: `flick_carried=2`, `13`, `4` and `4` (23 in all), `flick_lost=0` in every match.
  - `gif020-before-1`: no `stall_press` part, since this plugin wasn't loaded.

**Every carry in `gif020-after-4`, console b:**
- **How they are matched:** each of the 23 diag lines is matched to the probe's record of the same commit. The two
  ticks are 0.01–0.57 ms apart.
- **What the game got:** in every case the game frame consumed exactly the carried sample (`after`).
- **The 16 C-stick carries with `bits=0x21`** are the 16 carried flicks above. The dropped samples held Attack and
  Smash (`0x21`), the C-stick bit and the left stick at ±100 in the flick's direction. The commit's own sample had no
  `0x80`.
- **Carry 15** (`cstick=yes`, `bits=0x0`) is the seventeenth line with the C-stick bit; see below the table.
- **The 6 with `cstick=no`** are left-stick flicks without the C-stick bit: (0, ±45) in a dropped sample right after
  an up or down flick.

| carry | `cstick` | bits | before | after | dropped since the last commit → commit | frame | consumed |
|---|---|---|---|---|---|---|---|
| 1 | no | 0x0 | 0x8000 | 0xd30000008000 | 5166D → 5167 | 636 | 0xd30000008000 |
| 2 | yes | 0x21 | 0x8000 | 0x9c000080a1 | 6083D → 6084 | 1269 | 0x9c000080a1 |
| 3 | yes | 0x21 | 0x8000 | 0x64000080a1 | 10352D → 10353 | 275 | 0x64000080a1 |
| 4 | yes | 0x21 | 0x8000 | 0x9c00000080a1 | 11417D → 11418 | 1028 | 0x9c00000080a1 |
| 5 | yes | 0x21 | 0x8000 | 0x9c000080a1 | 11706D, 11707D → 11708 | 1243 | 0x9c000080a1 |
| 6 | yes | 0x21 | 0x2d0000008000 | 0x6400000080a1 | 12475D, 12476D → 12477 | 1786 | 0x6400000080a1 |
| 7 | yes | 0x21 | 0x8000 | 0x9c000080a1 | 12940D → 12941 | 2105 | 0x9c000080a1 |
| 8 | yes | 0x21 | 0x8000 | 0x6400000080a1 | 13091D → 13092 | 2212 | 0x6400000080a1 |
| 9 | yes | 0x21 | 0x2d0000008000 | 0x6400000080a1 | 14314D, 14315D → 14316 | 3072 | 0x6400000080a1 |
| 10 | no | 0x0 | 0x8000 | 0xd30000008000 | 14474D → 14475 | 3181 | 0xd30000008000 |
| 11 | no | 0x0 | 0x8000 | 0x2d0000008000 | 15544D → 15545 | 3935 | 0x2d0000008000 |
| 12 | yes | 0x21 | 0x8000 | 0x9c00000080a1 | 15695D → 15696 | 4039 | 0x9c00000080a1 |
| 13 | no | 0x0 | 0x8000 | 0x2d0000008000 | 16164D → 16165 | 4365 | 0x2d0000008000 |
| 14 | no | 0x0 | 0x8000 | 0x2d0000008000 | 17398D → 17399 | 5229 | 0x2d0000008000 |
| 15 | yes | 0x0 | 0x8000 | 0x6400008080 | 17707D → 17708 | 5441 | 0x6400008080 |
| 16 | yes | 0x21 | 0x8000 | 0x9c000080a1 | 22097D → 22098 | 413 | 0x9c000080a1 |
| 17 | yes | 0x21 | 0x8000 | 0x6400000080a1 | 23481D → 23482 | 1387 | 0x6400000080a1 |
| 18 | yes | 0x21 | 0x2d0000008000 | 0x6400000080a1 | 24092D, 24093D → 24094 | 1815 | 0x6400000080a1 |
| 19 | no | 0x0 | 0x8000 | 0x2d0000008000 | 24713D → 24714 | 2250 | 0x2d0000008000 |
| 20 | yes | 0x21 | 0x8000 | 0x9c00000080a1 | 29933D → 29934 | 1037 | 0x9c00000080a1 |
| 21 | yes | 0x21 | 0x8000 | 0x64000080a1 | 30086D → 30087 | 1143 | 0x64000080a1 |
| 22 | yes | 0x21 | 0x8000 | 0x64000080a1 | 30699D → 30700 | 1573 | 0x64000080a1 |
| 23 | yes | 0x21 | 0x8000 | 0x6400000080a1 | 31004D → 31005 | 1787 | 0x6400000080a1 |

Carry 15 added no buttons (`bits=0x0`), because the commit before it already had Attack and Smash; it added the stick
and the C-stick bit. `gif020-after-2`'s three carries (two C-stick, one at (0, -45)) matched the same way.

**The clips** (removed on 2026-11-13; in git history at `2849027`):
- `docs/evidence/cstick-before.gif`: flick 6 of `gif020-before-1` m-cs1, lost; the next frame got `0x8000`.
- `docs/evidence/cstick-after.gif`: flick 18 of `gif020-after-4` m-cs2, carry 7 above.
- `docs/media/cstick-before-after.gif` put them side by side.

The operator's review of these GIFs (2026-11-13, via the primary 01:55Z): the two sides were different situations, and
nothing showed what was pressed. So the README GIFs were made again (below).

**Not used:**
- **`gif020-after-1`** was refused at Up: another user's compile on the Yoga left too little free memory.
- **`gif020-after-3`:** b stayed on "Launching…" past the 180 s load gate, so no match was played; Down and a fresh
  boot (`-4`).
- **`gif020-after-2`'s carried flick 2:** a clean clip, but the camera was zoomed far out.
- **The other lost flick (25):** b was being hit at the time, so the missing move can't be seen on screen.


## Three kinds of input, mid-match: `gif020-in-*` (2026-11-13 01:58–04:12Z)

The primary's order of 01:55Z, after the operator's review: three pairs (a Jump tap, a left-stick input, a C-stick
smash toward the opponent), each with the same situation on both sides, and an input display. These boots looked for
inputs the game dropped on its own, mid-match. Their counts stand; their pairs were not used, because the two sides of
each pair weren't set up the same way (the primary's review). The README GIFs come from the next section.

**Setup, every boot:** as above (the stage `~/eden-runs/inputs-gif020/`), with:
- **Eden:** the GDB-stub fix `2f315fc4` (`20261113-973abf9c2e3f-…`).
- **Speed:** a at 70% (`-before-1`, `-after-1`, `-after-2`) or 60% (`-before-2`, `-after-3`, `-after-4`).
- **Play:** a's CPU pilot attacks; b fights with one one-frame input every 2.2 s until the match ends on a KO, with no
  walk-off.
  - **The inputs:** a Jump tap (X); the left stick to one side with an A tap (left stick + A); or the C-stick to one
    side. Each lease is 12 ms.
  - **Order:** in turn (`-after-4`: left stick + A only).
  - **Direction:** each stick input points toward a, from b's side of a's screen (the name tags); otherwise toward the
    middle of the stage from b's spawn point.
- **Recording:** b, 640 wide, 30 fps, in 40 s chunks.
- **Analysis:** `tools/input_clip.py` (host tests in `tools/test_input_clip.py`).
  - **A run:** each input kind has a signature in b's samples: Jump `0x4`; Attack `0x1` with the left stick at 84 or
    more and no C-stick bit; the C-stick bit `0x80`.
  - **Lining up:** runs are lined up with the calls of the same kind through one clock offset per match. It came out
    the same in every match, 1793101973.05 to .12 s.
  - **Lost:** every sample was dropped, and neither neighbouring game frame got any piece of the input.
  - **Carried:** the carry line on the next commit shows the commit's own sample without the input and with it after
    the carry, and the frame before got none of it.

| boot | this plugin | matches | inputs | reached the game anyway | carried (each by a matching carry line) | lost | partly lost | never sampled |
|---|---|---|---|---|---|---|---|---|
| `gif020-in-before-1` | not loaded | 4 | 102 | 83 | — | 15 | 1 | 3 |
| `gif020-in-before-2` | not loaded | 6 | 99 | 64 | — | 27 | 0 | 8 |
| `gif020-in-after-1` | diag `89980fba` | 4 | 58 | 41 | 11 | 0 | 0 | 6 |
| `gif020-in-after-2` | diag `89980fba` | 4 | 55 | 47 | 7 | 0 | 1 | 0 |
| `gif020-in-after-3` | diag `89980fba` | 6 | 169 | 112 | 45 | 0 | 3 | 9 |
| `gif020-in-after-4` | diag `89980fba` | 6 | 164 | 111 | 40 | 0 | 1 | 12 |

- **The runs:** every row passed in all six boots. All 30 matches ended with `sync_end … desync_seen=0` on both
  consoles, with no notice.
- **Carry lines:** 103 of the 108 matched a carried input. The other 5 belong to the partial cases with the plugin.
- **The partial cases with the plugin:**
  - **3 split left stick + A inputs:** the stick reached a committed frame, and A was in the next sample, which was
    dropped. The plugin carried A (`bits=0x201 flick=none`), so the game got both, one frame apart.
  - **2 C-stick samples `0x80a1`:** they had the C-stick bit and Attack+Smash, but the left stick was neutral. The
    plugin carried Attack+Smash (`bits=0x21 flick=none`) but not the C-stick bit, which 0.2.0 sets only with a carried
    stick flick.
  - The two C-stick cases are `gif020-in-after-2` m-in2 attempt 9 (frame 1091) and `gif020-in-after-3` m-in6
    attempt 11 (frame 1118).

**Why no matched pair came from these boots:**
- **Most dropped inputs** fell while a was attacking, b was in hitstun or knocked down, or the fighters stood on
  opposite sides from the other run's moment.
- **GO:** an input at GO (both at their spawn points) was planned as the best-matched moment. None of those reached
  b's samples on a dropped pass with the plugin absent.
- **A later boot, `gif020-go-before-1`** (9 matches, one press just after GO each, no stall), lost none of those
  presses. 3 came before the game took input (GO was first read from the name tags, which show before it), and the
  game got the other 6. Hence the set-up stall below.

## The README GIFs: `gif020-stall-before-1` and `gif020-stall-after-1` (2026-11-13 05:13–06:18Z)

The primary's order of 05:13Z: pause console a for 0.7 s around b's one press at GO, the same on both sides, so only
this plugin differs. The stall is set up so that the game drops the press every time; the README and the GIF captions
say so.

**Setup, both boots:** the stage and plugins above (the rc.11 card set with the desync detector 0.5.1, the probe and
the tile cursor on both consoles), the fixed Eden `2f315fc4`, the GDB stub on before the game loads, muted.
- **This plugin:** not loaded in `gif020-stall-before-1`; the diag build `89980fba` in `gif020-stall-after-1`.
- **Speed:** a at 70%, played by its CPU pilot.
- **Each match:** both fighters on their spawn points at 0%. GO is read live from b's probe records (b's sample turns
  nonzero). 0.6 s after GO, b gets one one-frame input toward a (a 16 ms lease): a Jump tap (X), the left stick + A,
  or the C-stick, in turn from match to match.
- **The stall:** a's emulator is paused (`game.pause`) 0.35 s before b's input and resumed 0.35 s after it. Meanwhile
  b's game waits for a, and b's lockstep drops about 21 samples in a row, the input's among them.
- **After that:** b fights on with an input every 2.2 s, a's pilot attacks, and the match ends on a KO. There was no
  stall after GO.
- **Recording:** b, 640×360 at 30 fps, 20 s from just before GO.
- **Analysis:** `tools/input_clip.py`, as above.

| boot | this plugin | matches | GO inputs lost | GO inputs carried (each by a matching carry line) | later inputs: reached the game anyway | carried | lost | never sampled |
|---|---|---|---|---|---|---|---|---|
| `gif020-stall-before-1` | not loaded | 9 | 9 | — | 181 | — | 27 | 5 |
| `gif020-stall-after-1` | diag `89980fba` | 9 | 0 | 9 | 147 | 27 | 0 | 5 |

- **The GO inputs:**
  - **Without the plugin:** every one was lost: 3 Jump, 3 left stick + A and 3 C-stick, the press in 1 or 2
    dropped samples, at frames 232–234.
  - **With it:** every one was carried, at frames 231–233.
- **No match was dropped or rerun,** and there were no partial cases. Two more inputs of the after boot came after
  their match had ended (past `sync_end`), so no frame consumed them; they aren't counted.
- **Carry lines:** 36 in the after boot, each matched to one of its 36 carried inputs.
- **Every match** ended with `sync_end … desync_seen=0` on both consoles, with no notice, and every row passed.

**The pairs** (left: without this plugin; right: with it; the same layout on both sides: K. Rool left, Sephiroth
right, 0%). The README GIFs are `docs/media/<pair>.gif`; the clips are `docs/evidence/<pair>-before.gif` and
`-after.gif`.

| pair | without: match, dropped samples, what the game got | with: match, dropped samples, carry line, what the game got |
|---|---|---|
| `jump` | m-go1: pass 4679; frame 232 `0x8000` | m-go1: pass 4724; n=1 `bits=0x4 before=0x8000 after=0x8004`; frame 233 `0x8004` |
| `left-stick` | m-go2: pass 11635; frame 232 `0x8000` | m-go2: passes 13424–13425; n=4 `bits=0x201 flick=carried before=0x8000 after=0x8100008201`; frame 233 `0x8100008201` |
| `c-stick` | m-go9: passes 63308–63309; frame 232 `0x8000` | m-go3: passes 21390–21391; n=12 `bits=0x21 flick=carried cstick=yes before=0x8000 after=0x9c000080a1`; frame 231 `0x9c000080a1` |

- **Which matches:** the first of each kind with Sephiroth on the right on both sides. The before boot's first C-stick
  matches (m-go3, m-go6) had the fighters the other way round, so its C-stick side is m-go9.
- **What they show:** on the right, Sephiroth jumps, or swings a forward smash to the left. On the left he stands still
  until the clip ends, 1.8 s after the press.
- **The clips:** full speed until 0.2 s before the press, a 0.5 s hold on its frame, then half speed.
  - The caption bar says "other console stalls (set up)" in orange inside the stall (measured: 0.34–0.35 s before the
    press to 0.35 s after it).
  - The input display is titled "Sephiroth's input (harness)" (`--who Sephiroth`), since K. Rool, a's CPU, moves on
    its own and could be taken for the one pressing.
  - The README GIFs are 1280×540, 5.5–5.6 s, 3.2–6.6 MB. The clips are 640×540, 1.1–3.3 MB, at most 14.3 frames a
    second, with no frame shorter than 70 ms.
  - `docs/evidence/<pair>-{before,after}-clip.json`: the attempt each clip shows (its passes, frame, consumed input
    and carry line), the stall window and every output frame's start time.

## Local wireless and offline

**Local wireless:** integration's `a-ldn-fix020t-0c628724` (2026-11-12,
`smash-training-lobby/artifacts/phase23/rc10-cores/ldn-fix020t/`), a local wireless match between two Eden instances.
- **This plugin:** the 0.2.0 diag build `711db630` (`90cc614`), with the desync detector and without the probe.
- **Install line, both:** `plugin=ssbu-stall-press-carry/0.2.0 commit=stock/near decided=stock/near diag_log=on
  stats=v1 result=installed heap_allocations=0`.
- **The detector's summaries:** this plugin's hooks saw the lockstep drop samples (`dropped=18` on one console, `9` on
  the other). No press fell on a dropped sample, so nothing was carried (`rescued=0 … flick_carried=0`).
- **The match:** `sync_end trigger=normal … desync_seen=0` on both at frame 815. All 14 rows passed.

**Offline:** `dbl-off2-dcec9d1a` (2026-11-12 15:17–15:36Z, the XPS), one console with 0.1.0's diag build `dcec9d1a`
and the probe. 40 Jump taps in Training and 60 in an offline 1-stock match against a CPU gave 0 probe records (the
lockstep never ran) and 0 carry lines. Offline play doesn't go through the lockstep that this plugin hooks.

## Across the runs

- **Desync:** every match above with a `sync_end` result ended with `desync_seen=0` on both consoles at the same
  frame. The evidence kept for `dbl-gb2-02420ee` and `dbl-ga-02420ee` has no `sync_end` line.
- **Consumed = committed:** the probe's check that each game frame consumed exactly the committed record found 0
  mismatches on both consoles in V, F, F2 and `dbl-k-02420ee`. It wasn't run on the later boots.
- **Console a**, which waits rarely, needed no carry in F2: its carry log has only the install line.

**Not run:**
- the hook-sharing stand-in modes (`foreign=inline`/`far`) and the reverse load order;
- a replay A/B;
- a measured match on a Switch. The release `749ed165` is on the card (the primary's install), but no Switch match
  has been measured.
