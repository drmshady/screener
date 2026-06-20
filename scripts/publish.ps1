# Publish a fresh data snapshot to the hosted screener (feature 010).
#
# Windows/local wrapper: Docker-Desktop preflight, then delegates the actual
# publish chain (refresh -> integrity -> secret-scan -> build -> push GHCR ->
# optional Factory-rebuild) to `scripts/publish_chain.ps1`, the SAME codepath
# the unattended `.github/workflows/daily-refresh.yml` CI job invokes, so
# local and CI publishes never drift (research.md Decision 5, feature 011).
#
# The hosted backend is a Hugging Face Docker Space whose Dockerfile is
# `FROM ghcr.io/drmshady/screener:latest`, so a published image only goes live
# when the Space is *Factory rebuilt* (which re-pulls :latest). By default this
# script stops after push and tells you how to deploy -- the "build + notify,
# you deploy" gate. Pass -Deploy (with $env:HF_TOKEN) to trigger the rebuild
# automatically.
#
# The host runs NO ingest and serves a read-only baked snapshot (FR-004/005/006/007).
# Refresh is always local-then-republish. This changes data only -- no strategy
# rule, default, citation, or backtest baseline change (FR-013).
#
# SECRETS: none are stored here. GHCR push uses your existing `docker login ghcr.io`
# session (PAT with write:packages). The optional -Deploy path reads $env:HF_TOKEN
# at runtime. Nothing is ever written to a file (FR-010, SC-008).
#
# Usage (run from anywhere; paths are resolved from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\publish.ps1
#   ...\publish.ps1 -FullStooq          # also run the heavy ~90-day Stooq refresh
#   ...\publish.ps1 -SkipRefresh        # rebuild+push current data, no re-fetch
#   ...\publish.ps1 -SkipGuard          # publish even with no new completed session
#   $env:HF_TOKEN='hf_...'; ...\publish.ps1 -Deploy   # auto Factory-rebuild the Space

[CmdletBinding()]
param(
    [switch]$SkipGuard,
    [switch]$SkipRefresh,
    [switch]$FullStooq,
    [switch]$SkipSecretScan,
    [switch]$Deploy,
    [string]$Image    = 'ghcr.io/drmshady/screener',
    [string]$Tag      = (Get-Date -Format 'yyyy-MM-dd'),
    [string]$SpaceId  = 'occlusion2/screener',
    [string]$BackendHealthUrl = 'https://occlusion2-screener.hf.space/health'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

function Die($msg) { Write-Host "FAILED: $msg" -ForegroundColor Red; exit 1 }

# --- Windows-local preflight (Docker Desktop, py launcher) ------------------
Write-Host "`n=== Preflight ===" -ForegroundColor Cyan
$python = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) { Die 'py launcher not found (need Python 3.12 to refresh data).' }
# Route through cmd so PowerShell 5.1 doesn't wrap Docker's stderr as a
# terminating error (it does that for redirected native stderr under -Stop).
cmd /c "docker info >NUL 2>&1"
if ($LASTEXITCODE -ne 0) { Die 'Docker Desktop is not running -- start it, wait for the whale icon to settle, then re-run.' }
Write-Host "Repo root: $RepoRoot"

# --- Delegate to the shared publish chain (CI runs the same script) --------
$chainArgs = @{
    SkipGuard      = $SkipGuard
    SkipRefresh    = $SkipRefresh
    FullStooq      = $FullStooq
    SkipSecretScan = $SkipSecretScan
    Deploy         = $Deploy
    Image          = $Image
    Tag            = $Tag
    SpaceId        = $SpaceId
}
& (Join-Path $PSScriptRoot 'publish_chain.ps1') @chainArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $Deploy) {
    Write-Host @"

NEXT STEP -- you deploy:
  1. Open  https://huggingface.co/spaces/$SpaceId
  2. Settings -> Factory reboot   (a plain Restart will NOT re-pull the new image)
  3. Wait for 'Running', then verify:
       curl $BackendHealthUrl      (expect 200, snapshot_ok)
     and run a screen in the app (first run after sleep is a slow cold start).

(Or re-run with:  `$env:HF_TOKEN='hf_...'; scripts\publish.ps1 -Deploy -SkipRefresh  to skip the rebuild click.)
"@ -ForegroundColor Yellow
}
