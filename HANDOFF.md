# Handoff

- **Playbook:** `ssbu-mod-playbook` `4ca80e1` (= `origin/main` on 2026-11-12 12:44Z), read in full from a `git archive`
  export at `/tmp/opencode/pb-4ca80e1`. The clone at `~/ssbu-mod-playbook` is at `7fd362e` with another agent's
  uncommitted runner-library changes, so it was left alone.
- **Order:** the operator, 2026-11-12, via the primary at 12:43Z: install on the card and push. Push `main` only, with
  no tag and no release until the operator confirms the card install.
- **Branch:** `main` only.
- **Measured with:** `ssbu-input-cadence-probe` (`/home/intpa/ssbu-input-cadence-probe`). It judges each press seen
  first in a dropped lockstep sample by the input the game frame consumed.
- **Design and results:**
  - `smash-training-lobby/artifacts/phase23/double-input/DESIGN-stall-press-carry.md`;
  - `smash-training-lobby/artifacts/phase23/LANE-DOUBLE-INPUT-RESEARCH.md`;
  - `docs/EDEN-RESULTS.md`.

## 0.2.0 (2026-11-12, current)

- **Order:** the primary, 17:01Z, relaying the operator: counters, a stats export for the desync detector's
  end-of-session summary, and a flick carry. No tag. The primary installs it on the card.
- **Commits:** `51c5145` (flick carry, counters, export) and `90cc614` (a pass more than 2 s after the last one
  starts a new session). Local; `main` will be pushed after the Eden proof.
- **Design and trace:** `smash-training-lobby/artifacts/phase23/double-input/DESIGN-stall-press-carry-0.2.0.md`.
- **Builds:** `90cc614` release `29dfd4ab…`, diag `711db630…` (left stick only). The right stick (C-stick) added on
  the operator's "no add it to 0.2.0" (via the primary 20:03Z), version unchanged: release `1bbc2d7b…`, diag
  `b303fede…`, 33 host tests. `tools/delivery.py` judges one-frame inputs from the probe's records.
- **Eden:** `proof-dc8ee988-r4` (`29dfd4ab`) and `-r5` (`1bbc2d7b`), integration's Yoga pair; see `docs/EDEN-RESULTS.md`.
- **Card (the primary, 2026-11-12 ~20:30Z):** `1bbc2d7b…` installed over `2b6ff493…`, `installed_verified`;
  rollback `ultimate/ssbu-stall-press-carry/backups/pre-1bbc2d7bc15ebfd1.nro`; receipts
  `smash-training-lobby/artifacts/card-install-stall-press-carry-0.2.0/`.
- **Pushed:** `main` to Forgejo, no tag (tags and releases wait until the operator has played).
- **The C-stick bit** (the operator, via the primary 20:40Z: "yes add the 0x80 bit to 0.2.0"): `0x80` rides along with
  a carried left-stick flick from a C-stick sample. Release `749ed165…`, diag `89980fba…`, 37 host tests. Goes on the
  card after integration's r6 m2; pushed once the card has it.

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
  Deluxe reads `0x16d81a8` with its guard at `0x16d81a4`–`0x16d81b7`, outside this plugin's windows.
  - `chain.rs` handles a foreign hook. Chaining onto the probe's branches worked in Eden (`branch/near`), in one load
    order.
  - The stand-in tests (`foreign=inline`/`far`) and the reverse load order were skipped on the primary's 12:43Z order,
    since no card plugin is at these sites.
- **Online rules:** the plugin writes this console's own local samples before they are packed into its input record.
  It draws no random number, writes no simulated state and skips nothing. Both consoles consume the same record
  (`desync_seen=0` checked in Eden).
- **Replay A/B:** not run. The change is to inputs, which the replay records.
- **Release and card:**
  - push `main`: ordered;
  - tag and release: after the operator confirms the card install;
  - card install: the primary runs it.
