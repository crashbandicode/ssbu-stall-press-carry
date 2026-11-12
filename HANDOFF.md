# Handoff

- **Playbook:** `ssbu-mod-playbook` `4ca80e1`, read in full from a `git archive` export at `/tmp/opencode/pb-4ca80e1`
  (the clone at `~/ssbu-mod-playbook` is at `7fd362e` with another agent's uncommitted runner-library changes).
- **Branch:** `main` only. A prototype: nothing pushed, tagged or installed (no order).
- **Measured with:** `ssbu-input-cadence-probe` (`/home/intpa/ssbu-input-cadence-probe`), before (arm V) and after
  (arm F = V + this plugin), judged by the input each game frame consumed.
- **Design and results:** `smash-training-lobby/artifacts/phase23/double-input/DESIGN-input-cadence-probe.md` and
  `smash-training-lobby/artifacts/phase23/LANE-DOUBLE-INPUT-RESEARCH.md`.

## State (2026-11-12 04:05Z)

- **Gates on `a666812`:** 19 tests, clippy, `--no-default-features`, release `2b6ff493…`, diag `dcec9d1a…`.
- **Eden:**
  - F ran release `72c1acb2…` (`8302362`);
  - F2 ran diag `dcec9d1a…` (`a666812`).
  - Results: `docs/EDEN-RESULTS.md`.
- **Open before any ship decision:**
  - the stand-in modes (`foreign=inline`/`far`) and the reverse load order;
  - a replay A/B;
  - a Switch run;
  - the release build's reproducibility (its hash changed across diag-only edits).

## Checklist (from `docs/CHECKLIST.md`)

M items: all apply. C items:
- Hook sharing: applies; the probe hooks the same two instructions. Both install through `chain.rs` (branch rule);
  the stand-in tests (`foreign=inline`/`far`) were not run for this prototype.
- Online rules: the plugin writes this console's own local samples before they are packed into its input record; no
  random number, no simulated state, nothing skipped. Both consoles consume the same record (`desync_seen=0` checked
  in Eden).
- Replay A/B: not run (the change is to inputs, which the replay records).
- Release and card: not authorized.
