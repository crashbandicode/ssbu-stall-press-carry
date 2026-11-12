//! Host-testable half: the version, the two hook sites with their 13.0.5
//! bytes, and the carry itself.
//!
//! Online, the lockstep's post-tick (`.16d7730`) maps local input every game
//! pass into `session+0x49508` (8 bytes per local slot) and commits it as the
//! input record for the next frame only while `lead <= [session+0x41]`. On a
//! pass that waits for the other console (no game frame) at the steady lead,
//! the sample is discarded, so a press shorter than the wait never reaches
//! the game. The carry keeps the press edges of a discarded sample and ORs
//! them into the next committed one, before the record is packed.

pub const PLUGIN: &str = "ssbu-stall-press-carry";
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const SUPPORTED_VERSION: &str = "13.0.5";
pub const DATA_DIR: &str = "sd:/ultimate/ssbu-stall-press-carry";

pub fn version_supported(version: &str) -> bool {
    version == SUPPORTED_VERSION
}

/// An inline hook site and the 64 bytes that are there in 13.0.5.
pub struct Site {
    pub name: &'static str,
    pub offset: usize,
    pub guard: [u8; 64],
}

impl Site {
    pub const fn stock(&self) -> [u32; crate::chain::WORDS] {
        crate::chain::words(&self.guard)
    }
}

/// `stur xzr, [sp, #0x4d]`: the lockstep's commit path, before the record is
/// packed from the samples (x19 = session, w22 = local samples).
pub const COMMIT: Site = Site {
    name: "commit",
    offset: 0x16d81dc,
    guard: [
        0xff, 0xd3, 0x04, 0xf8, 0xff, 0x7f, 0x04, 0xa9, 0xff, 0x7f, 0x03, 0xa9, 0xff, 0x7f, 0x02, 0xa9,
        0x69, 0x8e, 0x41, 0x39, 0xa9, 0x0d, 0x00, 0x34, 0x6a, 0x8a, 0x41, 0x39, 0x5f, 0x11, 0x00, 0x71,
        0xe1, 0x11, 0x00, 0x54, 0x3f, 0x05, 0x00, 0x71, 0xa0, 0x10, 0x00, 0x54, 0x3f, 0x09, 0x00, 0x71,
        0x21, 0x11, 0x00, 0x54, 0xe9, 0x0b, 0x00, 0x32, 0x82, 0x00, 0x00, 0x14, 0x08, 0xeb, 0x92, 0x52,
    ],
};

/// `ldrb w20, [x19, #1]`: after the commit path, or the drop
/// (`.16d81d0`/`.16d81d8`, where w22 still holds the sample count).
pub const DECIDED: Site = Site {
    name: "decided",
    offset: 0x16d8714,
    guard: [
        0x74, 0x06, 0x40, 0x39, 0x9f, 0xfe, 0x03, 0x71, 0x20, 0x1b, 0x00, 0x54, 0x68, 0xdf, 0x01, 0x90,
        0x08, 0x2d, 0x46, 0xf9, 0x16, 0x05, 0x40, 0xf9, 0xc8, 0x46, 0x40, 0xf9, 0x09, 0x00, 0x94, 0x52,
        0xea, 0x03, 0x00, 0x32, 0x09, 0x69, 0x69, 0xb8, 0x4a, 0x21, 0xd4, 0x1a, 0x3f, 0x01, 0x0a, 0x6a,
        0xe0, 0x19, 0x00, 0x54, 0x9f, 0x42, 0x00, 0x71, 0x42, 0x49, 0x00, 0x54, 0xe9, 0x0f, 0x1d, 0x32,
    ],
};

pub const SITES: [&Site; 2] = [&COMMIT, &DECIDED];

/// The local samples in the lockstep session, 8 bytes each (buttons in the low u32).
pub const SAMPLES: usize = 0x49508;
pub const MAX_SAMPLES: usize = 8;
/// The game's own "no input" test (`.1590a60`): bits 7 and 15 are not presses.
pub const PRESS_MASK: u32 = 0xffff_7f7f;

/// The carry's state. Game thread only (both hooks run in the lockstep's post-tick).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Carry {
    session: usize,
    committed: bool,
    /// Buttons of each slot's last committed sample, as the game received them.
    last: [u32; MAX_SAMPLES],
    /// Press edges seen only in dropped samples since that commit.
    pending: [u32; MAX_SAMPLES],
    /// Presses carried into a commit (bits), and commits that carried any.
    pub carried_bits: u64,
    pub carried_commits: u64,
    pub drops: u64,
}

impl Carry {
    pub const fn new() -> Self {
        Self {
            session: 0,
            committed: false,
            last: [0; MAX_SAMPLES],
            pending: [0; MAX_SAMPLES],
            carried_bits: 0,
            carried_commits: 0,
            drops: 0,
        }
    }

    fn enter(&mut self, session: usize) {
        if session != self.session {
            *self = Self { session, carried_bits: self.carried_bits, carried_commits: self.carried_commits,
                           drops: self.drops, ..Self::new() };
        }
    }

    /// The commit path: ORs the pending presses into the samples about to be
    /// packed. Returns the bits added.
    pub fn on_commit(&mut self, session: usize, samples: &mut [u64]) -> u32 {
        self.enter(session);
        self.committed = true;
        let mut added = 0;
        for (i, sample) in samples.iter_mut().enumerate().take(MAX_SAMPLES) {
            let buttons = *sample as u32;
            let add = self.pending[i] & !buttons;
            if add != 0 {
                *sample |= u64::from(add);
                added |= add;
                self.carried_bits += u64::from(add.count_ones());
            }
            self.last[i] = buttons | add;
            self.pending[i] = 0;
        }
        if added != 0 {
            self.carried_commits += 1;
        }
        added
    }

    /// After the decision: a drop when the commit path did not run this pass.
    pub fn on_decided(&mut self, session: usize, samples: &[u64]) {
        self.enter(session);
        if core::mem::take(&mut self.committed) {
            return;
        }
        self.drops += 1;
        for (i, sample) in samples.iter().enumerate().take(MAX_SAMPLES) {
            self.pending[i] |= (*sample as u32) & !self.last[i] & PRESS_MASK;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// One pass: (committed?, the slot-0 sample as mapped). Returns the record the game packs (None on a drop).
    fn pass(c: &mut Carry, commit: bool, sample: u64) -> Option<u64> {
        let mut s = [sample];
        if commit {
            c.on_commit(0x1000, &mut s);
        }
        c.on_decided(0x1000, &s);
        commit.then_some(s[0])
    }

    #[test]
    fn version_is_exact() {
        assert!(version_supported("13.0.5"));
        assert!(!version_supported("13.0.4"));
    }

    #[test]
    fn site_guards_start_with_the_hooked_instruction() {
        assert_eq!(COMMIT.stock()[0], 0xf804_d3ff);
        assert_eq!(DECIDED.stock()[0], 0x3940_0674);
    }

    #[test]
    fn dropped_tap_is_carried_into_the_next_commit() {
        let mut c = Carry::new();
        assert_eq!(pass(&mut c, true, 0x8000), Some(0x8000));
        assert_eq!(pass(&mut c, false, 0x8802), None);
        // The arm V event: Special + SpecialRaw only in the dropped sample.
        assert_eq!(pass(&mut c, true, 0x8000), Some(0x8802));
        assert_eq!(pass(&mut c, true, 0x8000), Some(0x8000));
        assert_eq!((c.carried_bits, c.carried_commits, c.drops), (2, 1, 1));
    }

    #[test]
    fn held_press_is_not_doubled() {
        let mut c = Carry::new();
        pass(&mut c, true, 0x1);
        pass(&mut c, false, 0x1);
        assert_eq!(pass(&mut c, true, 0x1), Some(0x1));
        // Pressed in a drop and still held at the commit: nothing to add.
        pass(&mut c, true, 0x0);
        pass(&mut c, false, 0x4);
        assert_eq!(pass(&mut c, true, 0x4), Some(0x4));
        assert_eq!(c.carried_bits, 0);
    }

    #[test]
    fn releases_and_non_press_bits_are_not_carried() {
        let mut c = Carry::new();
        pass(&mut c, true, 0x8004);
        pass(&mut c, false, 0x0080);
        assert_eq!(pass(&mut c, true, 0x0000), Some(0x0000));
        assert_eq!(c.carried_bits, 0);
    }

    #[test]
    fn presses_across_several_drops_are_all_carried_once() {
        let mut c = Carry::new();
        pass(&mut c, true, 0);
        pass(&mut c, false, 0x1);
        pass(&mut c, false, 0x2);
        pass(&mut c, false, 0x0);
        assert_eq!(pass(&mut c, true, 0x0), Some(0x3));
        assert_eq!(pass(&mut c, true, 0x0), Some(0x0));
    }

    #[test]
    fn a_new_session_starts_clean() {
        let mut c = Carry::new();
        pass(&mut c, true, 0);
        pass(&mut c, false, 0x10);
        let mut s = [0u64];
        assert_eq!(c.on_commit(0x2000, &mut s), 0);
        assert_eq!(s[0], 0);
    }

    #[test]
    fn sticks_pass_through() {
        let mut c = Carry::new();
        pass(&mut c, true, 0x7f00_0000_0000);
        pass(&mut c, false, 0x8100_0000_0002);
        assert_eq!(pass(&mut c, true, 0x0000_0000_0000), Some(0x2));
    }

    /// Every one-pass tap planted on a dropped pass reaches a committed record; untouched otherwise.
    #[test]
    fn fix_delivers_every_planted_tap() {
        let mut c = Carry::new();
        let mut delivered = 0;
        let mut planted = 0;
        for p in 0u32..2000 {
            let stalled = p % 37 == 5 || p % 101 == 7;
            let tap = stalled && p % 3 == 0;
            let bit = 1u64 << (p % 7);
            let sample = if tap { bit } else { 0 };
            planted += u32::from(tap);
            match pass(&mut c, !stalled, sample) {
                Some(record) if record != 0 => delivered += record.count_ones(),
                _ => {}
            }
        }
        assert!(planted > 20);
        assert_eq!(delivered, planted);
    }
}
