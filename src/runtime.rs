//! Switch only: version check, site guards, the two inline hooks and the
//! install line.
//!
//! Both hooks run on the game thread, in the lockstep post-tick, so the carry
//! state has one user. The commit hook writes only this console's own local
//! samples (`session+0x49508`) before the game packs them into the input
//! record it sends and consumes; nothing else in the game is written. No heap,
//! no locks, no thread. The per-session counters are mirrored into relaxed
//! atomics that the export `ssbu_stall_press_carry_stats_v1` reads from any
//! thread.
use crate::chain::{self, hook::Outcome, Entry};
use crate::model::{self, Carry, Site, Stats, StatsV1, MAX_SAMPLES, SAMPLES, STATS_FIELDS};
use core::cell::UnsafeCell;
use core::fmt::Write as _;
use skyline::hooks::{getRegionAddress, InlineCtx, Region};
use skyline::nn;
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};

const OPEN_WRITE_APPEND: i32 = 2 | 4;

/// Counts calls into the heap. Nothing here is meant to make one.
struct CountingAllocator;
static HEAP_ALLOCATIONS: AtomicU64 = AtomicU64::new(0);

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        HEAP_ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        System.alloc(layout)
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        HEAP_ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        System.alloc_zeroed(layout)
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, size: usize) -> *mut u8 {
        HEAP_ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        System.realloc(ptr, layout, size)
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        System.dealloc(ptr, layout)
    }
}

#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;

/// Game thread only (see the module comment).
struct Owned<T>(UnsafeCell<T>);
// SAFETY: only the two hooks touch it, both on the game thread.
unsafe impl<T> Sync for Owned<T> {}

static CARRY: Owned<Carry> = Owned(UnsafeCell::new(Carry::new()));

/// The local samples of the lockstep session `x19`, `w22` of them.
unsafe fn samples(ctx: &InlineCtx) -> (usize, &'static mut [u64]) {
    let session = ctx.registers[19].x() as usize;
    let n = (ctx.registers[22].w() as usize).min(MAX_SAMPLES);
    (session, core::slice::from_raw_parts_mut((session + SAMPLES) as *mut u64, n))
}

/// The current session's counters, in `StatsV1` field order (`Stats::fields`).
static STATS: [AtomicU32; STATS_FIELDS] = [
    AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0),
    AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0),
    AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0),
    AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0),
];

fn publish(stats: &Stats) {
    for (slot, value) in STATS.iter().zip(stats.fields()) {
        slot.store(value, Ordering::Relaxed);
    }
}

/// `extern "C" fn(out: *mut StatsV1) -> bool`: fills `*out` with the current
/// session's counters (`size` = 72, `version` = 1) and returns true; false if
/// `out` is null. Lock-free, any thread; the fields are read one by one.
///
/// # Safety
/// `out` is null or points to writable memory for one `StatsV1`.
#[no_mangle]
pub unsafe extern "C" fn ssbu_stall_press_carry_stats_v1(out: *mut StatsV1) -> bool {
    if out.is_null() {
        return false;
    }
    let mut fields = [0u32; STATS_FIELDS];
    for (value, slot) in fields.iter_mut().zip(STATS.iter()) {
        *value = slot.load(Ordering::Relaxed);
    }
    out.write_unaligned(StatsV1::from_fields(fields));
    true
}

unsafe extern "C" fn on_commit(ctx: &mut InlineCtx) {
    let (session, samples) = samples(ctx);
    #[cfg(feature = "diag")]
    let before = samples.first().copied().unwrap_or(0);
    let carry = &mut *CARRY.0.get();
    let _outcome = carry.on_commit(session, tick(), samples);
    publish(&carry.stats);
    #[cfg(feature = "diag")]
    {
        let flick = match _outcome.flick {
            Some((_, model::FlickRule::Carry)) => 1,
            Some((_, model::FlickRule::Reversal)) => 2,
            _ => 0,
        };
        if _outcome.added != 0 || flick != 0 {
            diag::push(before, samples.first().copied().unwrap_or(0), _outcome.added, flick);
        }
    }
}

unsafe extern "C" fn on_decided(ctx: &mut InlineCtx) {
    let (session, samples) = samples(ctx);
    let carry = &mut *CARRY.0.get();
    carry.on_decided(session, tick(), samples);
    publish(&carry.stats);
}

/// Eden-only: one line per carry (the first local sample before and after,
/// the bits added), from a static ring drained by a writer thread with a
/// static stack. Never in the shipped NRO.
#[cfg(feature = "diag")]
mod diag {
    use super::*;
    use std::sync::atomic::AtomicU32;

    const EVENTS: usize = 64;
    /// (tick, before, after, bits, flick); written by the game thread before it publishes `HEAD`.
    type Event = (u64, u64, u64, u32, u8);
    static RING: Owned<[Event; EVENTS]> = Owned(UnsafeCell::new([(0, 0, 0, 0, 0); EVENTS]));
    static HEAD: AtomicU32 = AtomicU32::new(0);
    static TAIL: AtomicU32 = AtomicU32::new(0);
    static LOST: AtomicU64 = AtomicU64::new(0);

    /// `flick`: 0 none, 1 a dropped flick put into this commit, 2 left alone (reversal).
    pub fn push(before: u64, after: u64, bits: u32, flick: u8) {
        let head = HEAD.load(Ordering::Relaxed);
        if head.wrapping_sub(TAIL.load(Ordering::Acquire)) as usize >= EVENTS {
            LOST.fetch_add(1, Ordering::Relaxed);
            return;
        }
        // SAFETY: the single producer owns slot `head` until it publishes `head + 1`.
        unsafe { (*RING.0.get())[head as usize % EVENTS] = (tick(), before, after, bits, flick) };
        HEAD.store(head.wrapping_add(1), Ordering::Release);
    }

    fn drain() {
        let mut line = Text::<256>::new();
        loop {
            let tail = TAIL.load(Ordering::Relaxed);
            if tail == HEAD.load(Ordering::Acquire) {
                return;
            }
            // SAFETY: published before `HEAD`; not reused until `TAIL` passes it.
            let (at, before, after, bits, flick) = unsafe { (*RING.0.get())[tail as usize % EVENTS] };
            TAIL.store(tail.wrapping_add(1), Ordering::Release);
            line.len = 0;
            let flick = ["none", "carried", "reversal"][usize::from(flick.min(2))];
            let _ = writeln!(
                line,
                "{at} carry n={} bits={bits:#x} flick={flick} before={before:#x} after={after:#x} ring_lost={}",
                tail.wrapping_add(1),
                LOST.load(Ordering::Relaxed)
            );
            append_log(line.as_bytes());
        }
    }

    const STACK: usize = 32 * 1024;
    #[repr(C, align(4096))]
    struct ThreadStack(UnsafeCell<[u8; STACK]>);
    #[repr(C, align(16))]
    struct ThreadObject(UnsafeCell<[u8; 0x1c0]>);
    // SAFETY: handed to nn::os once, at startup, and never touched again.
    unsafe impl Sync for ThreadStack {}
    unsafe impl Sync for ThreadObject {}
    static STACK_MEMORY: ThreadStack = ThreadStack(UnsafeCell::new([0; STACK]));
    static THREAD: ThreadObject = ThreadObject(UnsafeCell::new([0; 0x1c0]));

    extern "C" fn main(_: *mut skyline::libc::c_void) {
        loop {
            unsafe { nn::os::SleepThread(nn::TimeSpan { nanoseconds: 500_000_000 }) };
            drain();
        }
    }

    pub fn start() -> bool {
        unsafe {
            let thread = THREAD.0.get().cast::<nn::os::ThreadType>();
            let priority = nn::os::GetThreadPriority(nn::os::GetCurrentThread());
            if nn::os::CreateThread(thread, main, core::ptr::null_mut(), STACK_MEMORY.0.get().cast::<u8>(), STACK,
                                    priority) != 0 {
                return false;
            }
            nn::os::SetThreadNamePointer(thread, c"press-carry-diag".as_ptr().cast());
            nn::os::StartThread(thread);
        }
        true
    }
}

// ---------------------------------------------------------------------------
// Install.

type Line = Text<512>;

/// A fixed-capacity line (no heap). Text past the capacity is cut.
struct Text<const N: usize> {
    buf: [u8; N],
    len: usize,
}

impl<const N: usize> Text<N> {
    const fn new() -> Self {
        Self { buf: [0; N], len: 0 }
    }

    fn as_bytes(&self) -> &[u8] {
        &self.buf[..self.len]
    }

    fn with_nul(&mut self) -> Option<&[u8]> {
        if self.len >= N {
            return None;
        }
        self.buf[self.len] = 0;
        Some(&self.buf[..=self.len])
    }
}

impl<const N: usize> core::fmt::Write for Text<N> {
    fn write_str(&mut self, s: &str) -> core::fmt::Result {
        let take = s.len().min(N.saturating_sub(self.len));
        self.buf[self.len..self.len + take].copy_from_slice(&s.as_bytes()[..take]);
        self.len += take;
        Ok(())
    }
}

fn tick() -> u64 {
    unsafe { nn::os::GetSystemTick() as u64 }
}

fn append_log(bytes: &[u8]) {
    let mut path = Text::<96>::new();
    let _ = write!(path, "{}/events.log", model::DATA_DIR);
    let Some(path) = path.with_nul() else {
        return;
    };
    unsafe {
        nn::fs::CreateFile(path.as_ptr(), 0);
        let mut handle = nn::fs::FileHandle { handle: 0 };
        if nn::fs::OpenFile(&mut handle, path.as_ptr(), OPEN_WRITE_APPEND) != 0 {
            return;
        }
        let mut offset = 0;
        if nn::fs::GetFileSize(&mut offset, handle) == 0 {
            let option = nn::fs::WriteOption { flags: 0 };
            nn::fs::WriteFile(handle, offset, bytes.as_ptr(), bytes.len() as u64, &option);
            nn::fs::FlushFile(handle);
        }
        nn::fs::CloseFile(handle);
    }
}

fn report_install(report: &mut Line) {
    skyline::logging::log(core::str::from_utf8(report.as_bytes()).unwrap_or(""));
    let _ = report.write_char('\n');
    for directory in ["sd:/ultimate", model::DATA_DIR] {
        let mut path = Text::<96>::new();
        let _ = write!(path, "{directory}");
        if let Some(path) = path.with_nul() {
            unsafe { nn::fs::CreateDirectory(path.as_ptr()) };
        }
    }
    append_log(report.as_bytes());
}

fn version_is_supported() -> bool {
    let mut version = nn::oe::DisplayVersion { name: [0; 16] };
    unsafe { nn::oe::GetDisplayVersion(&mut version) };
    let end = version.name.iter().position(|v| *v == 0).unwrap_or(16);
    core::str::from_utf8(&version.name[..end]).is_ok_and(model::version_supported)
}

unsafe fn site_address(site: &Site) -> Option<u64> {
    let start = getRegionAddress(Region::Text) as u64;
    let end = getRegionAddress(Region::Rodata) as u64;
    let address = start + site.offset as u64;
    (address % 4 == 0 && address + 64 <= end).then_some(address)
}

/// `chain` has one stub: the first site that needs it takes it.
static STUB_USED: AtomicBool = AtomicBool::new(false);

unsafe fn hook(site: &Site, callback: unsafe extern "C" fn(&mut InlineCtx)) -> (Entry, Outcome) {
    let Some(address) = site_address(site) else {
        return (Entry::Foreign, Outcome::Skipped);
    };
    let stock = site.stock();
    let entry = chain::entry(&stock, &chain::hook::words_at(address), address);
    if matches!(entry, Entry::Chain(_)) && STUB_USED.swap(true, Ordering::Relaxed) {
        return (entry, Outcome::Skipped);
    }
    chain::hook::inline(address, &stock, callback)
}

#[skyline::main(name = "ssbu-stall-press-carry")]
pub fn main() {
    let mut report = Line::new();
    let _ = write!(report, "{} plugin={}/{}", tick(), model::PLUGIN, model::VERSION);
    if !version_is_supported() {
        let _ = write!(report, " result=unsupported_version");
        report_install(&mut report);
        return;
    }
    // Both or neither: a commit hook without the drop hook carries nothing; a
    // drop hook without the commit hook would only collect.
    let usable = model::SITES.iter().all(|site| unsafe {
        site_address(site).is_some_and(|a| {
            !matches!(chain::entry(&site.stock(), &chain::hook::words_at(a), a), Entry::Foreign)
        })
    });
    let mut hooked = 0;
    if usable {
        let callbacks: [unsafe extern "C" fn(&mut InlineCtx); 2] = [on_commit, on_decided];
        for (site, callback) in model::SITES.iter().zip(callbacks) {
            let (entry, outcome) = unsafe { hook(site, callback) };
            let _ = write!(report, " {}={}/{}", site.name, entry.name(), outcome.name());
            hooked += usize::from(outcome.hooked());
        }
    } else {
        for site in model::SITES {
            let state = unsafe { site_address(site) }
                .map(|a| unsafe { chain::entry(&site.stock(), &chain::hook::words_at(a), a) }.name())
                .unwrap_or("foreign");
            let _ = write!(report, " {}={}/skipped", site.name, state);
        }
    }
    let result = match hooked {
        2 => "installed",
        0 => "not_installed",
        _ => "partial",
    };
    #[cfg(feature = "diag")]
    if hooked == 2 {
        let _ = write!(report, " diag_log={}", if diag::start() { "on" } else { "not_started" });
    }
    if hooked == 2 {
        let _ = write!(report, " stats=v1");
    }
    let _ = write!(report, " result={result} heap_allocations={}", HEAP_ALLOCATIONS.load(Ordering::Relaxed));
    report_install(&mut report);
}
