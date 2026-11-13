# How ssbu-stall-press-carry works

A Skyline plugin for Super Smash Bros. Ultimate 13.0.5. The README shows what it does; this page is how.

## The problem and the carry

- **How the game samples input:** in an online or local wireless match it samples local input once per game pass.
- **Dropped samples:** while the game waits for the other console's input (a pass with no game frame), it throws that
  pass's sample away once its input buffer is full. So a button press or stick flick that lasts only through such a
  wait never reaches the game.
- **The carry:** this plugin keeps what a discarded sample held and adds it to the next input record the game
  commits. The input lands one frame later instead of not at all.
- **What it changes:** only this console's own input record, before the game packs and sends it. Releases and the
  input delay are unchanged.

**Why both consoles stay in sync:**
- The plugin writes only this console's own local samples, in the commit path, before the game packs them into the
  input record it both sends and consumes.
- The other console receives that record and simulates the same frame from it.
- No simulated state is written and no random number is drawn.

**Install and log:**
- **Install:** `atmosphere/contents/01006A800016E000/romfs/skyline/plugins/libssbu_stall_press_carry.nro`.
- **Log:** `sd:/ultimate/ssbu-stall-press-carry/events.log`, the install line only (the diag build adds a line per
  carry).

**Hook sites** (13.0.5 `.text`, 64-byte guards, inline):
- `0x16d81dc`: the lockstep's commit path, before the record is packed;
- `0x16d8714`: after the commit or the drop.

**When the hooks go in:** if either site holds a foreign hook this plugin can't chain onto, neither is hooked
(`result=not_installed`). If only one of the two hooks goes in, the install line says `result=partial`, and nothing
is carried: the commit hook alone has nothing to add, and the drop hook alone only collects. On a game version other
than 13.0.5 nothing is hooked (`result=unsupported_version`).

**Not covered:**
- a flick that becomes a different direction by the next frame (a dash-dance reversal, left alone);
- releasing a held button and pressing it again within one wait;
- a dropped C-stick sample whose left stick is neutral (`0x80a1`: the C-stick bit with Attack and Smash). Attack and
  Smash are carried, but the C-stick bit isn't, since 0.2.0 sets it only with a carried stick flick. Seen twice in
  Eden (`docs/EDEN-RESULTS.md`, `gif020-in-*`).

## Buttons (0.1.0)

The press edges (bits newly set against the last committed sample) seen only in dropped samples are ORed into the next
commit. The bits are masked with `0xffff7f7f`, so the C-stick bit `0x80` is never carried as a press.

## Stick flicks (0.2.0)

**What can be lost:** a sample the game throws away can hold a stick flick that is gone again by the next frame: a
dash, a smash attack, a fast fall, or a C-stick smash or aerial.

**The C-stick:**
- In Eden with the default controls, the game maps the C-stick into the attack bits plus the left stick's direction,
  and sets its "C-stick in use" bit (`0x80`). So a C-stick input is carried by the button carry and the left-stick
  rule.
- When a carried left-stick flick came from such a sample, `0x80` is set in that commit too, for that one frame.
- `0x80` is never carried on its own: the game's no-input test does not count it as a press.
- A sample that does carry right-stick bytes gets the same rule on the right stick.

**Thresholds:**
- Each stick is judged on its own, so one wait can carry both.
- The stick bytes are a float times 120.
- The plugin uses its own thresholds, not the game's parameters: a dead zone of 24 (0.2) and a flick strength of
  84 (0.7).
- A stick's bin is the sign of each axis beyond the dead zone.

**The rule:**
- **A dropped sample's stick is a flick** when it leaves the last committed bin for another non-neutral bin, or reaches
  flick strength in the same bin from below it. Going back to neutral is a release.
- **At the next commit:**
  - **Carried:** if the stick has gone back (dead zone, the last committed bin, or weaker in the flick's bin), the
    dropped position is put into that one commit's bytes for that stick.
  - **Left alone:** if the stick still shows the flick, it arrives anyway.
  - **Lost (reversal):** if the stick now points in a new direction (a dash-dance reversal), the new direction wins.
  - **Lost (superseded):** two flicks in different directions in one wait keep the later one.

## Counters (0.2.0)

**When the counters reset:**
- They are kept per lockstep session and mirrored into atomics by the two hooks.
- A session starts when the session address changes, or when a pass comes more than 2 s after the last one. The next
  match can reuse the address; within a match the hooks run every pass, stalled or not.
- A new session also drops any carry still pending.

**What is counted:**
- the decisions, commits and dropped samples (each drop is a stalled pass at the steady lead);
- the press edges in committed samples;
- the commits that received carried presses, with the press bits and the groups: jump, attack, special, shield, grab
  and other;
- `flick_carried`, and `flick_lost` by reason (`reversal`, `superseded`). Both sticks count into the same fields.

**The export:** `ssbu_stall_press_carry_stats_v1(out: *mut StatsV1) -> bool`, an `extern "C"` function looked up with
`nn::ro::LookupSymbol`.
- `StatsV1` is 18 `u32` fields, `size` (72) and `version` (1) first. The order is in `src/model.rs`.
- It returns false only for a null `out`. Lock-free, any thread.
- The desync detector 0.5.0 and later appends these counters to its session-end summary (`stall_press rescued=…
  flick_carried=… flick_lost=…`).
- The release build adds no log line; its install line says `stats=v1`.

**The diag build** (Eden only) also logs one line per carry: the bits added, what happened to a stick flick
(`flick=none|carried|reversal`), which stick (`stick=none|left|right`), whether the C-stick bit came along
(`cstick=yes|no`), and the first local sample before and after.

## Build

```text
pwsh -File tools/build.ps1 -Kind test        # cargo test
pwsh -File tools/build.ps1 -Kind clippy      # cargo clippy --all-targets -- -D warnings
pwsh -File tools/build.ps1 -Kind nodefault   # cargo build --no-default-features
pwsh -File tools/build.ps1 -Kind release     # cargo skyline build --release -> dist/release
pwsh -File tools/build.ps1 -Kind diag        # the Eden diagnostic build -> dist/diag
```

## How the README GIFs are made

`tools/input_clip.py` (host tests in `tools/test_input_clip.py`); the runs are in `docs/EDEN-RESULTS.md`.

**What is matched:**
- Each GIF pairs two Eden matches set up the same way: one without this plugin and one with its diag build (the
  release plus one log line per carry; only that line ties a carry to its frame).
- Both fighters are on their spawn points at 0%. 0.6 s after GO, read from console b's probe records, b gets one
  one-frame input (a 16 ms lease) toward the other fighter.
- **The stall is set up:** the other console's emulator is paused from 0.35 s before the input to 0.35 s after it,
  the same on both sides. b's game waits for it meanwhile and drops b's samples, the input's among them, so the drop
  happens every time, as an online lag spike would make it. The caption bar says so in orange ("other console stalls
  (set up)") on every frame inside that window.
- A match whose "without" side didn't lose the input would have been dropped and run again (none was). No frame is
  edited.
- The input display is drawn afterwards from the harness's log of what it pressed and from the
  `ssbu-input-cadence-probe` records of what each pass sampled, dropped and consumed. Nothing in the game is changed
  for it.
- On the "with the fix" side, the diag build's carry line for that commit shows the commit's own sample without the
  input and with it after the carry.

**What the input display shows:**
- **"Sephiroth's input (harness)":** the stick circles and button lamps show what was sent to Sephiroth's console, lit
  on the frame the input was sampled. The title names the fighter (`--who`), so the press isn't credited to K. Rool,
  the other console's CPU, who moves on its own.
- **The strip:** pressed → dropped by the game → received by the game (or lost). It fills in during a 0.5 s hold on
  that frame.

**The clips:** full speed until 0.2 s before the input, the 0.5 s hold, then half speed until 1.8 s after the input.
The README GIFs put the two clips side by side, 1280 wide. The clips alone are in `docs/evidence/`, 640 wide, at
most 15 frames a second.
