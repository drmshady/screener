# Publish a fresh data snapshot to the hosted screener (feature 010).
#
# Pipeline: refresh data locally -> verify -> secret-scan -> build the backend
# Docker image -> push to GHCR -> NOTIFY you to deploy. The hosted backend is a
# Hugging Face Docker Space whose Dockerfile is `FROM ghcr.io/drmshady/screener:latest`,
# so a published image only goes live when the Space is *Factory rebuilt* (which
# re-pulls :latest). By default this script stops after push and tells you how to
# deploy -- the "build + notify, you deploy" gate. Pass -Deploy (with $env:HF_TOKEN)
# to trigger the rebuild automatically.
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
#   $env:HF_TOKEN='hf_...'; ...\publish.ps1 -Deploy   # auto Factory-rebuild the Space

[CmdletBinding()]
param(
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

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Die($msg)  { Write-Host "FAILED: $msg" -ForegroundColor Red; exit 1 }

# Native-command runner that aborts on nonzero exit (PS 5.1 has no `&&`).
function Run($exe, [string[]]$cmdArgs) {
    Write-Host "> $exe $($cmdArgs -join ' ')" -ForegroundColor DarkGray
    & $exe @cmdArgs
    if ($LASTEXITCODE -ne 0) { Die "$exe exited $LASTEXITCODE" }
}

# --- Preflight -------------------------------------------------------------
Step 'Preflight'
$python = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) { Die 'py launcher not found (need Python 3.12 to refresh data).' }
# Route through cmd so PowerShell 5.1 doesn't wrap Docker's stderr as a
# terminating error (it does that for redirected native stderr under -Stop).
cmd /c "docker info >NUL 2>&1"
if ($LASTEXITCODE -ne 0) { Die 'Docker Desktop is not running -- start it, wait for the whale icon to settle, then re-run.' }
Write-Host "Repo root: $RepoRoot"

# --- 1. Refresh data locally (quickstart B) --------------------------------
if ($SkipRefresh) {
    Step 'Data refresh SKIPPED (-SkipRefresh) -- baking whatever is on disk'
} else {
    Step 'Refresh universe'
    Run 'py' @('-3.12', 'scripts\seed_universe.py')

    if ($FullStooq) {
        Step 'Refresh full Stooq deep-history bundle (heavy; ~90-day cadence)'
        Run 'py' @('-3.12', 'scripts\refresh_stooq_history.py')
    } else {
        Write-Host 'Skipping full Stooq bundle (use -FullStooq ~quarterly). Incremental bars come from ingest_daily.'
    }

    # NO --skip-events: earnings/8-K must refresh into catalog.db or the hosted
    # snapshot ships stale earnings badges (see deploy-010 gotchas).
    Step 'Incremental daily ingest (prices + events + Shariah + fundamentals)'
    Run 'py' @('-3.12', 'scripts\ingest_daily.py')
}

# --- 2. Verify freshness ---------------------------------------------------
Step 'Verify snapshot freshness (backend/data/manifest.json)'
$manifestPath = Join-Path $RepoRoot 'backend\data\manifest.json'
if (-not (Test-Path $manifestPath)) { Die "manifest.json not found at $manifestPath" }
Write-Host "manifest.json last written: $((Get-Item $manifestPath).LastWriteTime)"
Select-String -Path $manifestPath -Pattern 'data_as_of' |
    ForEach-Object { Write-Host ('  ' + $_.Line.Trim()) }

# --- 3. Secret scan (SC-008 / FR-010) --------------------------------------
if ($SkipSecretScan) {
    Step 'Secret scan SKIPPED (-SkipSecretScan)'
} else {
    Step 'Release secret scan (repo + image copy list)'
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'secret_scan.ps1')
    if ($LASTEXITCODE -ne 0) { Die 'secret scan found potential secrets -- aborting before build.' }
}

# --- 4. Build the backend image (context = repo root; Dockerfile COPYs backend/...) ---
Step "Build image  $Image`:latest  (+ :$Tag)"
Run 'docker' @('build', '-f', 'backend\Dockerfile', '-t', "$Image`:latest", '-t', "$Image`:$Tag", '.')

# --- 5. Push to GHCR (uses existing `docker login ghcr.io`) -----------------
Step 'Push to GHCR'
Run 'docker' @('push', "$Image`:latest")
Run 'docker' @('push', "$Image`:$Tag")
# No stderr redirection here -- same -Stop stderr-wrapping trap as the preflight.
$digest = $null
try { $digest = (& docker inspect --format '{{index .RepoDigests 0}}' "$Image`:latest") } catch { $digest = $null }
if ($digest) { Write-Host "Pushed digest: $digest" -ForegroundColor Green }

# --- 6. Deploy: notify, or auto Factory-rebuild with -Deploy ----------------
if ($Deploy) {
    Step 'Deploy: Factory-rebuild the Hugging Face Space'
    $hfToken = $env:HF_TOKEN
    if (-not $hfToken) { Die '-Deploy needs $env:HF_TOKEN (an HF write token); set it for this session only.' }
    $uri = "https://huggingface.co/api/spaces/$SpaceId/restart?factory=true"
    try {
        Invoke-RestMethod -Method Post -Uri $uri -Headers @{ Authorization = "Bearer $hfToken" } | Out-Null
        Write-Host "Triggered Factory rebuild of $SpaceId. It will re-pull :latest and restart." -ForegroundColor Green
    } catch {
        Die "HF rebuild call failed: $($_.Exception.Message)"
    }
    Write-Host "Watch build at: https://huggingface.co/spaces/$SpaceId  (Logs tab)"
} else {
    Step 'NEXT STEP -- you deploy'
    Write-Host @"
Image is published. To make it live on the hosted backend:

  1. Open  https://huggingface.co/spaces/$SpaceId
  2. Settings -> Factory reboot   (a plain Restart will NOT re-pull the new image)
  3. Wait for 'Running', then verify:
       curl $BackendHealthUrl      (expect 200, snapshot_ok)
     and run a screen in the app (first run after sleep is a slow cold start).

(Or re-run with:  `$env:HF_TOKEN='hf_...'; scripts\publish.ps1 -Deploy -SkipRefresh  to skip the rebuild click.)
"@ -ForegroundColor Yellow
}

Write-Host "`nDone." -ForegroundColor Green
