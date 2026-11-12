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

## State

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
