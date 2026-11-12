# ssbu-stall-press-carry (prototype)

A Skyline plugin for Super Smash Bros. Ultimate 13.0.5. In online matches the game samples local input once per game
pass and, while it waits for the other console's input (a pass with no game frame), throws that pass's sample away
once its input buffer is full; a button press that lasts only through such a wait never reaches the game. This plugin
keeps the presses of a discarded sample and adds them to the next input record the game commits, so the press lands
one frame later instead of not at all. It changes only this console's own input record before the game packs and sends
it, so both consoles simulate the same input. Releases, sticks and the input delay are unchanged. It draws nothing, so
there is no GIF.

- **Install:** `atmosphere/contents/01006A800016E000/romfs/skyline/plugins/libssbu_stall_press_carry.nro`.
- **Log:** `sd:/ultimate/ssbu-stall-press-carry/events.log`, the install line only.
- **Hook sites** (13.0.5 `.text`, 64-byte guards, inline): `0x16d81dc` (the lockstep's commit path, before the record
  is packed) and `0x16d8714` (after the commit or the drop). Both or neither are installed.
- **Not covered:** a stick flick shorter than a wait; releasing and pressing again a held button within one wait.

## Build

```text
pwsh -File tools/build.ps1 -Kind test        # cargo test
pwsh -File tools/build.ps1 -Kind clippy      # cargo clippy --all-targets -- -D warnings
pwsh -File tools/build.ps1 -Kind nodefault   # cargo build --no-default-features
pwsh -File tools/build.ps1 -Kind release     # cargo skyline build --release -> dist/release
pwsh -File tools/build.ps1 -Kind diag        # the Eden diagnostic build -> dist/diag
```

## License

MIT; see `LICENSE`.

This plugin was written with AI assistance (Claude). Review it before relying on it.
