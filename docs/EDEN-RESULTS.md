# Eden results (2026-11-12)

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

**Release reproducibility:** `02420ee` built twice with fresh `CARGO_TARGET_DIR`s gives `2b6ff493…` both times.

**Results:**

| match | frames | `sync_end` (both consoles) | b: presses first in a drop | delivered | lost |
|---|---|---|---|---|---|
| m1 | 4,842 | `trigger=normal … desync_seen=0` at the same frame | 28 | 28 | 0 |
| m2 | 5,707 | `trigger=normal … desync_seen=0` at the same frame | 18 | 18 | 0 |

- **Stalls:** b stalled on 13–14% of its frames and dropped 1,737 samples on stalled passes. Consumed = committed on
  every frame on both consoles.
- **Install lines:**
  - **This plugin:** `commit=branch/near decided=branch/near result=installed heap_allocations=0` on both (chained onto
    the probe's hooks, which loaded first).
  - **TrainingRooms:** `seams_skipped=[] seams_shadow_diff=[] seams_missing=[] result=installed heap_allocations=0` on
    both.
  - **Online Deluxe:** 0.10.5's overlay loaded (the pilot's `deluxe_overlay=found`, 54 overlay entries per console).
- **No crash:** no panic, abort, crash or Unmapped line on either console.
- **Not run:** no Eden run had this plugin without the probe. That case takes the stock path, the one the probe took at
  these same two instructions (`stock/near`).

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

Both clips are 0.9 s before to 1.4 s after the tap, at quarter speed, 640 px wide. `before-after.gif` puts them side
by side.

## In all runs
- Console a, which waits rarely, needed no carry.
- The game consumed exactly the committed records on every frame (0 mismatches).
- Every session ended with `desync_seen=0` on both consoles at the same frame.

**Not run:**
- the hook-sharing stand-in modes (`foreign=inline`/`far`) and the reverse load order;
- a replay A/B;
- a Switch (no install order).
