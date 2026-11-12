# Runs one gate or build: test, clippy, nodefault, release (dist/release) or diag (dist/diag).
# One cargo call per invocation, under nice 19 with two jobs (Eden hosts), colour and hyperlinks off.
param([ValidateSet('test', 'clippy', 'nodefault', 'release', 'diag')] [string]$Kind = 'release')
$ErrorActionPreference = 'Stop'
$env:PATH = '/home/intpa/.cargo/bin:' + $env:PATH
$env:CARGO_TERM_COLOR = 'never'
$env:CARGO_TERM_HYPERLINKS = 'false'
$env:CARGO_BUILD_JOBS = '2'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
switch ($Kind) {
    'test' { /usr/bin/nice -n 19 cargo test }
    'clippy' { /usr/bin/nice -n 19 cargo clippy --all-targets -- -D warnings }
    'nodefault' { /usr/bin/nice -n 19 cargo build --no-default-features }
    'release' { /usr/bin/nice -n 19 cargo skyline build --release }
    'diag' { /usr/bin/nice -n 19 cargo skyline build --release --features diag }
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Kind -in 'release', 'diag') {
    $out = Join-Path $repo "dist/$Kind"
    New-Item -ItemType Directory -Force $out | Out-Null
    $nro = Join-Path $repo 'target/aarch64-skyline-switch/release/libssbu_stall_press_carry.nro'
    Copy-Item $nro $out -Force
    $hash = (Get-FileHash (Join-Path $out 'libssbu_stall_press_carry.nro')).Hash.ToLower()
    "$Kind libssbu_stall_press_carry.nro sha256 $hash"
}
