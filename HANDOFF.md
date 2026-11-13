# Handoff

- **Playbook:** `ssbu-mod-playbook` `913fa6e`, read in full from a `git archive` export; `1ee0a08` (`origin/main` on
  2026-11-13 06:30Z) changes docs only, and its diff was read. The compliance check runs from a `1ee0a08` export.
- **Orders (2026-11-13):**
  - the primary, 05:13Z: the README GIFs at GO with a stall of the other console set up and disclosed;
  - the operator, via the primary: check every doc for staleness.
  - Push: fast-forward to `main` only, no tag and no release, as `crashbandicode`.
- **Branch:** `main` only, locally and on Forgejo.
- **Card (2026-11-13):** this plugin's release `749ed165`, with the desync detector 0.5.1 `36027bb7` and TrainingRooms
  rc.11 (`smash-training-lobby/artifacts/card-install-rc11/`).
- **Measured with:** `ssbu-input-cadence-probe` (`/home/intpa/ssbu-input-cadence-probe`). It judges each press seen
  first in a dropped lockstep sample by the input the game frame consumed.
- **Design and results:**
  - `smash-training-lobby/artifacts/phase23/double-input/DESIGN-stall-press-carry.md`;
  - `smash-training-lobby/artifacts/phase23/LANE-DOUBLE-INPUT-RESEARCH.md`;
  - `docs/EDEN-RESULTS.md`.

## 0.2.0 (2026-11-12 to 11-13, current)

- **Order:** the primary, 17:01Z, relaying the operator: counters, a stats export for the desync detector's
  end-of-session summary, and a flick carry. No tag. The primary installs it on the card.
- **Commits:** `51c5145` (flick carry, counters, export) and `90cc614` (a pass more than 2 s after the last one
  starts a new session), pushed after the Eden proof.
- **Design and trace:** `smash-training-lobby/artifacts/phase23/double-input/DESIGN-stall-press-carry-0.2.0.md`.
- **Builds:** `90cc614` release `29dfd4ab…`, diag `711db630…` (left stick only). The right stick (C-stick) added on
  the operator's order to add it to 0.2.0 (via the primary 20:03Z), version unchanged: release `1bbc2d7b…`, diag
  `b303fede…`, 33 host tests. `tools/delivery.py` judges one-frame inputs from the probe's records.
- **Eden:** `proof-dc8ee988-r4` (`29dfd4ab`) and `-r5` (`1bbc2d7b`), integration's Yoga pair; see `docs/EDEN-RESULTS.md`.
- **Card (the primary, 2026-11-12 ~20:30Z):** `1bbc2d7b…` installed over `2b6ff493…`, `installed_verified`;
  rollback `ultimate/ssbu-stall-press-carry/backups/pre-1bbc2d7bc15ebfd1.nro`; receipts
  `smash-training-lobby/artifacts/card-install-stall-press-carry-0.2.0/`.
- **Pushed:** `main` to Forgejo, no tag (tags and releases wait until the operator has played).
- **The C-stick bit** (the operator's order via the primary 20:40Z to add the `0x80` bit to 0.2.0): `0x80` rides
  along with a carried left-stick flick from a C-stick sample. Release `749ed165…`, diag `89980fba…`, 37 host tests.
  - Eden r6 (`proof-dc8ee988-r6`): m2 PASS but only 9 of 216 inputs ran; the `0x80` branch had no chance to act.
  - Card (the primary, ~21:07Z): `1bbc2d7b` → `749ed165`, `installed_verified` then `verified_in_place`; rollback
    `ultimate/ssbu-stall-press-carry/backups/pre-749ed165c6b941dd.nro`; receipts
    `smash-training-lobby/artifacts/card-install-stall-press-carry-0.2.0-cs/`.
  - Pushed: `main` `1d8d601`, no tag.
  - Next: integration's r7, a full-length m2; `tools/delivery.py` on its `collect`.
  - r7 (`proof-dc8ee988-r7`): 0 C-stick bits lost; the primary accepted it. The card is final (the primary,
    2026-11-13 00:23Z): this plugin `749ed165`, detector 0.5.1 `36027bb7`, TrainingRooms rc.11.
- **The C-stick GIF** (the primary 2026-11-13 00:23Z; the operator asked whether the GIFs were updated):
  `docs/media/cstick-before-after.gif`, with the clips `docs/evidence/cstick-before.gif` and `cstick-after.gif`.
  - Runs on the Yoga, stage `~/eden-runs/inputs-gif020/`: `gif020-before-1` (this plugin not loaded) and
    `gif020-after-4` (diag `89980fba`, one line per carry; `-2` also ran, `-1` and `-3` didn't reach a match); see
    `docs/EDEN-RESULTS.md`.
  - After clip: diag, not the release, because only the diag build's carry lines tie a carry to its frame (as 0.1.0's
    after clip did). 23 of 23 carries in `gif020-after-4` matched and delivered; 0 C-stick flicks lost with the plugin
    (112 of 112 reached the game), 2 of 36 without it.
  - Made with `tools/flick_clip.py`. Pushed as `2849027`, no tag.
- **The README redo** (the operator's review via the primary 01:55Z: the GIFs looked off, and the README was too long
  a wall of text):
  - **Three pairs:** `docs/media/jump.gif`, `left-stick.gif`, `c-stick.gif`, with an input display drawn from the
    harness log and the probe (`tools/input_clip.py`).
  - **The README is GIF-led;** everything technical moved to `docs/TECHNICAL.md`. The old README GIFs
    `before-after.gif` and `cstick-before-after.gif` and the C-stick clips are removed (in git history at `2849027`).
  - **First try:** `gif020-in-before-1`, `-before-2`, `-after-1` to `-after-4`, inputs the game dropped on its own
    mid-match. The primary's review: the two sides of each pair weren't set up the same way. Not pushed; the counts
    are in `docs/EDEN-RESULTS.md`.
  - **The pushed pairs:** `gif020-stall-before-1` and `gif020-stall-after-1`, one press 0.6 s after GO, with console a
    paused for 0.7 s around it on both sides (the primary's 05:13Z order). The README and every caption say the stall
    is set up, and that the press is Sephiroth's while K. Rool (a's CPU) moves on its own. 9 of 9 presses lost without
    the plugin, 9 of 9 carried with it.
  - **The primary reviewed the stills before the push**
    (`smash-training-lobby/artifacts/phase23/double-input/gif-020-stall/`; 07:28Z: approved, asking that the text name
    whose press it is).
  - **Open:** a dropped C-stick sample with a neutral left stick (`0x80a1`) gets Attack+Smash carried but not the
    C-stick bit (2 cases). 0.2.0 sets `0x80` only with a carried stick flick (`docs/TECHNICAL.md`, "Not covered").
- **Pushed:** `2a78cc8` (the stall GIFs and the docs about them), fast-forward on `2849027`, no tag.
- **Stale-doc check (2026-11-13):** every doc checked claim by claim; the report is
  `smash-training-lobby/artifacts/doc-stale-check-20261113/ssbu-stall-press-carry.md`. The fixes outside the GIF
  lines are one commit on `2a78cc8`, held locally (the primary, 07:28Z: the operator gets one question covering
  every lane's doc pushes).

## State (0.1.0)

- **Earlier Eden arms** (2026-11-12 03:00–04:00Z):
  - F ran release `72c1acb2…` (`8302362`);
  - F2 ran diag `dcec9d1a…` (`a666812`).
- **Card readiness** (12:45Z on): reproducible release builds, the gates, one Eden pair with the exact rc.10 card set
  plus this release NRO, and the card staging in
  `smash-training-lobby/artifacts/card-install-stall-press-carry-0.1.0/` (the primary runs the install).
- **Release hashes across commits:** a diag-only edit can change the release NRO. Moving code lines moves the line
  numbers in the panic-location strings the release build embeds. A rebuild of the same commit is checked twice from
  fresh targets.

## Checklist (from `docs/CHECKLIST.md`)

M items: all apply. C items:
- **Hook sharing:** no card plugin hooks `0x16d81dc` or `0x16d8714` (scan of the rc.9 and rc.10 readbacks). Online
  Deluxe reads `0x16d81a8` with its guard at `0x16d81a4`–`0x16d81b7`, outside this plugin's windows. On rc.11, the
  desync detector 0.5.1 was checked (2026-11-13): none of the 13.0.5 addresses in its source is within 64 bytes of
  this plugin's windows (`0x16d81dc`–`0x16d821b`, `0x16d8714`–`0x16d8753`).
  - `chain.rs` handles a foreign hook. Chaining onto the probe's branches worked in Eden (`branch/near`), in one load
    order.
  - The stand-in tests (`foreign=inline`/`far`) and the reverse load order were skipped on the primary's 12:43Z order,
    since no card plugin is at these sites.
- **Guards:** both 64-byte guards in `src/model.rs` match the 13.0.5 main ELF (`0789f0a4…`) at their offsets
  (`tools/site_bytes.py`, 2026-11-13).
- **Online rules:** the plugin writes this console's own local samples before they are packed into its input record.
  It draws no random number, writes no simulated state and skips nothing. Both consoles consume the same record
  (`desync_seen=0` checked in Eden).
- **Replay A/B:** not run. The change is to inputs, which the replay records.
- **Release and card:**
  - push `main`: ordered;
  - tag and release: after the operator confirms the card install;
  - card install: the primary runs it.
