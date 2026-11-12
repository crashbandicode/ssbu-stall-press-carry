//! Switch only: version check, site guards, the two inline hooks and the
//! install line.
//!
//! Both hooks run on the game thread, in the lockstep post-tick, so the carry
//! state has one user. The commit hook writes only this console's own local
//! samples (`session+0x49508`) before the game packs them into the input
//! record it sends and consumes; nothing else in the game is written. No heap,
//! no locks, no thread.
use crate::chain::{self, hook::Outcome, Entry};
use crate::model::{self, Carry, Site, MAX_SAMPLES, SAMPLES};
use core::cell::UnsafeCell;
use core::fmt::Write as _;
use skyline::hooks::{getRegionAddress, InlineCtx, Region};
use skyline::nn;
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

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

unsafe extern "C" fn on_commit(ctx: &mut InlineCtx) {
    let (session, samples) = samples(ctx);
    (*CARRY.0.get()).on_commit(session, samples);
}

unsafe extern "C" fn on_decided(ctx: &mut InlineCtx) {
    let (session, samples) = samples(ctx);
    (*CARRY.0.get()).on_decided(session, samples);
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
    let _ = write!(report, " result={result} heap_allocations={}", HEAP_ALLOCATIONS.load(Ordering::Relaxed));
    report_install(&mut report);
}
