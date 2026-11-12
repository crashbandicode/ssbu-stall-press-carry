//! Host-testable half: the version, the two hook sites with their 13.0.5
//! bytes, the carry itself, its per-session counters and the stats export's
//! layout.
//!
//! Online, the lockstep's post-tick (`.16d7730`) maps local input every game
//! pass into `session+0x49508` (8 bytes per local slot) and commits it as the
//! input record for the next frame only while `lead <= [session+0x41]`. On a
//! pass that waits for the other console (no game frame) at the steady lead,
//! the sample is discarded, so a press shorter than the wait never reaches
//! the game. The carry keeps the press edges of a discarded sample and ORs
//! them into the next committed one, before the record is packed. A left-stick
//! flick that exists only in discarded samples is put into the next commit
//! for that one frame, when the stick has gone back by then (`FlickRule`).

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

/// The local samples in the lockstep session, 8 bytes each: the buttons in the
/// low u32, then the left stick x, y and the right stick x, y as i8 (a stick
/// float times 120, the final mapping `.1750dd0`).
pub const SAMPLES: usize = 0x49508;
pub const MAX_SAMPLES: usize = 8;
/// The game's own "no input" test (`.1590a60`): bits 7 and 15 are not presses.
pub const PRESS_MASK: u32 = 0xffff_7f7f;

/// Mapped button groups for the per-button counters (the game's mapped bits:
/// Attack 0x1, Special 0x2, Jump 0x4, Guard 0x8, Catch 0x10, Smash 0x20,
/// JumpMini 0x40, AttackRaw 0x200, SpecialRaw 0x800, GuardHold 0x10000,
/// SpecialRaw2 0x20000).
pub const JUMP_BITS: u32 = 0x4 | 0x40;
pub const ATTACK_BITS: u32 = 0x1 | 0x20 | 0x200;
pub const SPECIAL_BITS: u32 = 0x2 | 0x800 | 0x2_0000;
pub const SHIELD_BITS: u32 = 0x8 | 0x1_0000;
pub const GRAB_BITS: u32 = 0x10;

/// The left stick's dead zone and flick strength in mapped units (of 120).
/// Not the game's own parameters: 24 is 0.2 of the range, 84 is 0.7.
pub const DEAD: i16 = 24;
pub const FLICK: i16 = 84;

/// A left stick position from a sample.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Stick {
    pub x: i8,
    pub y: i8,
}

impl Stick {
    pub const fn of(sample: u64) -> Self {
        Self { x: (sample >> 32) as u8 as i8, y: (sample >> 40) as u8 as i8 }
    }

    /// `sample` with this left stick; buttons and the right stick unchanged.
    pub const fn put(self, sample: u64) -> u64 {
        (sample & !0xffff_0000_0000) | ((self.x as u8 as u64) << 32) | ((self.y as u8 as u64) << 40)
    }

    const fn axis(v: i8) -> i8 {
        let v = v as i16;
        if v > DEAD {
            1
        } else if v < -DEAD {
            -1
        } else {
            0
        }
    }

    /// One of nine bins: the sign of each axis beyond the dead zone.
    pub const fn bin(self) -> (i8, i8) {
        (Self::axis(self.x), Self::axis(self.y))
    }

    pub const fn neutral(self) -> bool {
        Self::axis(self.x) == 0 && Self::axis(self.y) == 0
    }

    pub const fn magnitude(self) -> i16 {
        let x = (self.x as i16).abs();
        let y = (self.y as i16).abs();
        if x > y {
            x
        } else {
            y
        }
    }

    pub const fn strong(self) -> bool {
        self.magnitude() >= FLICK
    }
}

/// A dropped sample's stick is a flick when it leaves the last committed bin
/// for another non-neutral bin, or reaches flick strength in the same bin from
/// below it. Going back to neutral is a release, not a flick.
pub fn is_flick(dropped: Stick, last: Stick) -> bool {
    if dropped.neutral() {
        return false;
    }
    dropped.bin() != last.bin() || (dropped.strong() && !last.strong())
}

/// What happens to a pending flick at the next commit.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FlickRule {
    /// The stick still shows it (same bin, at least as strong as needed).
    StillThere,
    /// The stick went back (dead zone, the last committed bin, or weaker in
    /// the same bin): the dropped position goes into this commit.
    Carry,
    /// The stick now points somewhere new: left alone, counted lost.
    Reversal,
}

pub fn flick_rule(pending: Stick, last: Stick, next: Stick) -> FlickRule {
    if next.bin() == pending.bin() && (next.strong() || !pending.strong()) {
        FlickRule::StillThere
    } else if next.neutral() || next.bin() == last.bin() || next.bin() == pending.bin() {
        FlickRule::Carry
    } else {
        FlickRule::Reversal
    }
}

/// Per-session counters (reset when the lockstep session changes).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Stats {
    pub sessions: u32,
    pub decisions: u32,
    pub commits: u32,
    /// Samples the lockstep discarded (each on a stalled pass at the steady lead).
    pub dropped: u32,
    /// Press edges in committed samples, carried ones included.
    pub committed_press_edges: u32,
    /// Commits that received carried presses, and the press bits added.
    pub rescued: u32,
    pub rescued_bits: u32,
    pub jump: u32,
    pub attack: u32,
    pub special: u32,
    pub shield: u32,
    pub grab: u32,
    pub other: u32,
    pub flick_carried: u32,
    pub flick_lost_reversal: u32,
    pub flick_lost_superseded: u32,
}

impl Stats {
    fn count_carry(&mut self, added: u32) {
        self.rescued_bits += added.count_ones();
        let mut rest = added;
        for (bits, field) in [
            (JUMP_BITS, &mut self.jump),
            (ATTACK_BITS, &mut self.attack),
            (SPECIAL_BITS, &mut self.special),
            (SHIELD_BITS, &mut self.shield),
            (GRAB_BITS, &mut self.grab),
        ] {
            if added & bits != 0 {
                *field += 1;
            }
            rest &= !bits;
        }
        if rest != 0 {
            self.other += 1;
        }
    }
}

/// The export's out value (`ssbu_stall_press_carry_stats_v1`), 4-byte fields.
#[repr(C)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct StatsV1 {
    pub size: u32,
    pub version: u32,
    pub sessions: u32,
    pub decisions: u32,
    pub commits: u32,
    pub dropped: u32,
    pub committed_press_edges: u32,
    pub rescued: u32,
    pub rescued_bits: u32,
    pub jump: u32,
    pub attack: u32,
    pub special: u32,
    pub shield: u32,
    pub grab: u32,
    pub other: u32,
    pub flick_carried: u32,
    pub flick_lost_reversal: u32,
    pub flick_lost_superseded: u32,
}

pub const STATS_SYMBOL: &[u8] = b"ssbu_stall_press_carry_stats_v1\0";
pub const STATS_V1_SIZE: u32 = core::mem::size_of::<StatsV1>() as u32;
/// The fields after `size` and `version`, in `StatsV1` order.
pub const STATS_FIELDS: usize = 16;

impl StatsV1 {
    pub const fn from_fields(f: [u32; STATS_FIELDS]) -> Self {
        Self {
            size: STATS_V1_SIZE,
            version: 1,
            sessions: f[0],
            decisions: f[1],
            commits: f[2],
            dropped: f[3],
            committed_press_edges: f[4],
            rescued: f[5],
            rescued_bits: f[6],
            jump: f[7],
            attack: f[8],
            special: f[9],
            shield: f[10],
            grab: f[11],
            other: f[12],
            flick_carried: f[13],
            flick_lost_reversal: f[14],
            flick_lost_superseded: f[15],
        }
    }
}

impl Stats {
    pub const fn fields(&self) -> [u32; STATS_FIELDS] {
        [
            self.sessions,
            self.decisions,
            self.commits,
            self.dropped,
            self.committed_press_edges,
            self.rescued,
            self.rescued_bits,
            self.jump,
            self.attack,
            self.special,
            self.shield,
            self.grab,
            self.other,
            self.flick_carried,
            self.flick_lost_reversal,
            self.flick_lost_superseded,
        ]
    }
}

/// What one commit did, for the diag build's lines.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct CommitOutcome {
    pub added: u32,
    pub flick: Option<(Stick, FlickRule)>,
}

/// The carry's state. Game thread only (both hooks run in the lockstep's post-tick).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Carry {
    session: usize,
    committed: bool,
    /// Each slot's last committed sample (buttons and left stick), as the game received it.
    last: [u32; MAX_SAMPLES],
    last_stick: [Stick; MAX_SAMPLES],
    /// Press edges seen only in dropped samples since that commit.
    pending: [u32; MAX_SAMPLES],
    /// The strongest flick seen only in dropped samples since that commit.
    flick: [Option<Stick>; MAX_SAMPLES],
    pub stats: Stats,
}

impl Carry {
    pub const fn new() -> Self {
        Self {
            session: 0,
            committed: false,
            last: [0; MAX_SAMPLES],
            last_stick: [Stick { x: 0, y: 0 }; MAX_SAMPLES],
            pending: [0; MAX_SAMPLES],
            flick: [None; MAX_SAMPLES],
            stats: Stats {
                sessions: 0,
                decisions: 0,
                commits: 0,
                dropped: 0,
                committed_press_edges: 0,
                rescued: 0,
                rescued_bits: 0,
                jump: 0,
                attack: 0,
                special: 0,
                shield: 0,
                grab: 0,
                other: 0,
                flick_carried: 0,
                flick_lost_reversal: 0,
                flick_lost_superseded: 0,
            },
        }
    }

    /// A new session starts clean, counters included.
    fn enter(&mut self, session: usize) {
        if session != self.session {
            let sessions = self.stats.sessions + 1;
            *self = Self { session, ..Self::new() };
            self.stats.sessions = sessions;
        }
    }

    /// The commit path: ORs the pending presses into the samples about to be
    /// packed and, by `flick_rule`, puts a dropped flick into the left stick.
    pub fn on_commit(&mut self, session: usize, samples: &mut [u64]) -> CommitOutcome {
        self.enter(session);
        self.committed = true;
        self.stats.decisions += 1;
        self.stats.commits += 1;
        let mut outcome = CommitOutcome::default();
        for (i, sample) in samples.iter_mut().enumerate().take(MAX_SAMPLES) {
            let buttons = *sample as u32;
            let add = self.pending[i] & !buttons;
            if add != 0 {
                *sample |= u64::from(add);
                outcome.added |= add;
            }
            let now = buttons | add;
            self.stats.committed_press_edges += (now & !self.last[i] & PRESS_MASK).count_ones();
            self.last[i] = now;
            self.pending[i] = 0;
            if let Some(dropped) = self.flick[i].take() {
                let rule = flick_rule(dropped, self.last_stick[i], Stick::of(*sample));
                match rule {
                    FlickRule::Carry => {
                        *sample = dropped.put(*sample);
                        self.stats.flick_carried += 1;
                    }
                    FlickRule::Reversal => self.stats.flick_lost_reversal += 1,
                    FlickRule::StillThere => {}
                }
                if outcome.flick.is_none() {
                    outcome.flick = Some((dropped, rule));
                }
            }
            self.last_stick[i] = Stick::of(*sample);
        }
        if outcome.added != 0 {
            self.stats.rescued += 1;
            self.stats.count_carry(outcome.added);
        }
        outcome
    }

    /// After the decision: a drop when the commit path did not run this pass.
    pub fn on_decided(&mut self, session: usize, samples: &[u64]) {
        self.enter(session);
        if core::mem::take(&mut self.committed) {
            return;
        }
        self.stats.decisions += 1;
        self.stats.dropped += 1;
        for (i, sample) in samples.iter().enumerate().take(MAX_SAMPLES) {
            self.pending[i] |= (*sample as u32) & !self.last[i] & PRESS_MASK;
            let stick = Stick::of(*sample);
            if !is_flick(stick, self.last_stick[i]) {
                continue;
            }
            match self.flick[i] {
                None => self.flick[i] = Some(stick),
                Some(held) if held.bin() == stick.bin() => {
                    if stick.magnitude() > held.magnitude() {
                        self.flick[i] = Some(stick);
                    }
                }
                Some(_) => {
                    // A second flick in another direction before any commit: the
                    // later one is the one the player ended on.
                    self.flick[i] = Some(stick);
                    self.stats.flick_lost_superseded += 1;
                }
            }
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

    fn stick(x: i8, y: i8) -> u64 {
        Stick { x, y }.put(0)
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
        assert_eq!((c.stats.rescued_bits, c.stats.rescued, c.stats.dropped), (2, 1, 1));
        assert_eq!(c.stats.special, 1);
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
        assert_eq!(c.stats.rescued_bits, 0);
    }

    #[test]
    fn releases_and_non_press_bits_are_not_carried() {
        let mut c = Carry::new();
        pass(&mut c, true, 0x8004);
        pass(&mut c, false, 0x0080);
        assert_eq!(pass(&mut c, true, 0x0000), Some(0x0000));
        assert_eq!(c.stats.rescued_bits, 0);
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
        assert_eq!(c.on_commit(0x2000, &mut s).added, 0);
        assert_eq!(s[0], 0);
        assert_eq!((c.stats.sessions, c.stats.dropped, c.stats.commits), (2, 0, 1));
    }

    #[test]
    fn sticks_pass_through_with_buttons() {
        let mut c = Carry::new();
        // The right stick (byte 6) swings full right to full left during a drop: never touched.
        pass(&mut c, true, 0x007f_0000_0000_0000);
        pass(&mut c, false, 0x0081_0000_0000_0002);
        assert_eq!(pass(&mut c, true, 0x0000_0000_0000), Some(0x2));
        assert_eq!(c.stats.flick_carried, 0);
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

    #[test]
    fn stick_bytes_round_trip() {
        let s = Stick { x: -120, y: 87 };
        let sample = s.put(0x1234_5678_9abc_def0);
        assert_eq!(Stick::of(sample), s);
        assert_eq!(sample & 0xffff_0000_ffff_ffff, 0x1234_0000_9abc_def0);
        assert_eq!(Stick { x: 0, y: 24 }.bin(), (0, 0));
        assert_eq!(Stick { x: 25, y: -25 }.bin(), (1, -1));
        assert!(Stick { x: -84, y: 0 }.strong() && !Stick { x: 83, y: 83 }.strong());
        assert_eq!(Stick { x: -128, y: 0 }.magnitude(), 128);
    }

    #[test]
    fn a_one_pass_flick_dropped_then_neutral_is_carried_for_one_frame() {
        let mut c = Carry::new();
        assert_eq!(pass(&mut c, true, stick(0, 0)), Some(stick(0, 0)));
        // A dash flick right that only the dropped pass saw.
        assert_eq!(pass(&mut c, false, stick(120, 0)), None);
        assert_eq!(pass(&mut c, true, stick(0, 0)), Some(stick(120, 0)));
        // One frame only: the next commit is the stick as mapped.
        assert_eq!(pass(&mut c, true, stick(0, 0)), Some(stick(0, 0)));
        assert_eq!((c.stats.flick_carried, c.stats.flick_lost_reversal), (1, 0));
    }

    #[test]
    fn a_smash_flick_back_to_a_tilt_and_a_fast_fall_tap_are_carried() {
        let mut c = Carry::new();
        pass(&mut c, true, stick(40, 0));
        pass(&mut c, false, stick(118, 0) | 0x1);
        // The stick fell back to the tilt it was at: the flick and the A press both arrive.
        assert_eq!(pass(&mut c, true, stick(40, 0)), Some(stick(118, 0) | 0x1));
        pass(&mut c, true, stick(0, 0));
        pass(&mut c, false, stick(0, -120));
        assert_eq!(pass(&mut c, true, stick(0, 0)), Some(stick(0, -120)));
        assert_eq!(c.stats.flick_carried, 2);
        assert_eq!(c.stats.attack, 1);
    }

    #[test]
    fn a_flick_then_a_reversal_is_left_alone_and_counted_lost() {
        let mut c = Carry::new();
        pass(&mut c, true, stick(0, 0));
        pass(&mut c, false, stick(120, 0));
        // Dash-dance: the next sample already points left.
        assert_eq!(pass(&mut c, true, stick(-120, 0)), Some(stick(-120, 0)));
        assert_eq!((c.stats.flick_carried, c.stats.flick_lost_reversal), (0, 1));
    }

    #[test]
    fn a_held_direction_and_a_slow_drift_are_untouched() {
        let mut c = Carry::new();
        // Held right through a drop.
        pass(&mut c, true, stick(120, 0));
        pass(&mut c, false, stick(120, 0));
        assert_eq!(pass(&mut c, true, stick(119, 0)), Some(stick(119, 0)));
        // A slow drift through the flick strength, still there at the commit.
        pass(&mut c, true, stick(70, 0));
        pass(&mut c, false, stick(86, 0));
        assert_eq!(pass(&mut c, true, stick(90, 0)), Some(stick(90, 0)));
        // A tilt that grows within the tilt range.
        pass(&mut c, true, stick(30, 0));
        pass(&mut c, false, stick(60, 0));
        assert_eq!(pass(&mut c, true, stick(50, 0)), Some(stick(50, 0)));
        // Letting go during a drop is a release, not a flick.
        pass(&mut c, true, stick(120, 0));
        pass(&mut c, false, stick(0, 0));
        assert_eq!(pass(&mut c, true, stick(0, 0)), Some(stick(0, 0)));
        assert_eq!(c.stats.flick_carried + c.stats.flick_lost_reversal, 0);
    }

    #[test]
    fn a_flick_still_showing_at_the_commit_needs_nothing() {
        let mut c = Carry::new();
        pass(&mut c, true, stick(0, 0));
        pass(&mut c, false, stick(120, 0));
        assert_eq!(pass(&mut c, true, stick(110, 0)), Some(stick(110, 0)));
        assert_eq!(c.stats.flick_carried, 0);
    }

    #[test]
    fn two_flicks_in_one_stall_keep_the_later_direction() {
        let mut c = Carry::new();
        pass(&mut c, true, stick(0, 0));
        pass(&mut c, false, stick(120, 0));
        pass(&mut c, false, stick(0, 120));
        assert_eq!(pass(&mut c, true, stick(0, 0)), Some(stick(0, 120)));
        assert_eq!((c.stats.flick_carried, c.stats.flick_lost_superseded), (1, 1));
    }

    #[test]
    fn counters_cover_drops_commits_edges_and_button_groups() {
        let mut c = Carry::new();
        pass(&mut c, true, 0);
        pass(&mut c, false, 0x4);
        pass(&mut c, true, 0);
        pass(&mut c, false, 0x10 | 0x8);
        pass(&mut c, true, 0);
        pass(&mut c, true, 0x1);
        let s = c.stats;
        assert_eq!((s.decisions, s.commits, s.dropped), (6, 4, 2));
        assert_eq!((s.rescued, s.rescued_bits), (2, 3));
        assert_eq!((s.jump, s.grab, s.shield, s.attack, s.special, s.other), (1, 1, 1, 0, 0, 0));
        // 0x4, then 0x18 (two bits), then 0x1.
        assert_eq!(s.committed_press_edges, 4);
    }

    #[test]
    fn the_stats_export_layout_is_the_contract() {
        assert_eq!(core::mem::size_of::<StatsV1>(), 72);
        assert_eq!(core::mem::align_of::<StatsV1>(), 4);
        assert_eq!(STATS_SYMBOL.last(), Some(&0));
        let mut c = Carry::new();
        pass(&mut c, true, 0);
        pass(&mut c, false, 0x4);
        pass(&mut c, true, 0);
        let v = StatsV1::from_fields(c.stats.fields());
        assert_eq!((v.size, v.version, v.sessions, v.rescued, v.jump, v.dropped), (72, 1, 1, 1, 1, 1));
        assert_eq!(v.flick_lost_superseded, 0);
    }
}
