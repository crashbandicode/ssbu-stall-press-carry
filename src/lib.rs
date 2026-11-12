//! ssbu-stall-press-carry (prototype): in Smash Ultimate 13.0.5 online
//! matches, a button press that exists only in a local input sample the
//! lockstep drops (a pass that waits for the other console's input) is carried
//! into the next committed input record, so the game sees it one frame later
//! instead of never.
pub mod chain;
pub mod model;
#[cfg(target_os = "switch")]
mod runtime;
