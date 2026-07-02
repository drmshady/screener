# Shared publish chain for the hosted screener (features 010/011).
#
# One codepath for both the local owner-run publish (`scripts/publish.ps1`) and
# the unattended GitHub Actions daily-refresh workflow
# (`.github/workflows/daily-refresh.yml`), so CI and local never drift
# (research.md Decision 5).
#
# Ordered, abort-before-publish on any failed step:
#   new-session guard -> restore prior backend/data tree (best effort) ->
#   incremental ingest_daily -> integrity harness (008) -> release secret scan ->
#   docker build (only if a new session was published) -> push GHCR -> optional
#   HF Factory-rebuild.
#
# The heavy ~90-day Stooq deep-history bundle is NEVER on this path by default
# (-FullStooq opts in for the separate, infrequent job; research.md Decision 5).
#
# SECRETS: none are stored or written by this script. GHCR push uses the
# caller's existing `docker login ghcr.io` session; the optional Deploy step
# reads $env:HF_TOKEN at runtime only (FR-002a/006, SC-008).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\publish_chain.ps1 [-SkipGuard] [-SkipRefresh] ...

[CmdletBinding()]
param(
    [switch]$SkipGuard,
    [switch]$SkipRefresh,
    [switch]$FullStooq,
    [switch]$SkipSecretScan,
    [switch]$Deploy,
    [string]$Image    = 'ghcr.io/drmshady/screener',
    [string]$Tag      = (Get-Date -Format 'yyyy-MM-dd'),
    [string]$SpaceId  = 'occlusion2/screener'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# This script runs on BOTH local Windows PowerShell 5.1 and the CI Linux pwsh
# runner. It checks $LASTEXITCODE after every native command rather than catching
# exceptions, so opt out of pwsh 7.3+ turning nonzero native exits into throws
# (assigning this is a harmless no-op on Windows PowerShell 5.1).
$PSNativeCommandUseErrorActionPreference = $false

# Cross-platform launchers: Windows uses the py launcher + powershell.exe; the
# Linux CI runner uses python + pwsh. Detect once. (Guard the $IsWindows automatic
# var, which does not exist under StrictMode on Windows PowerShell 5.1.)
$IsWindowsHost = if ($PSVersionTable.PSEdition -eq 'Core') { [bool]$IsWindows } else { $true }
$PsHostExe     = if ($PSVersionTable.PSEdition -eq 'Core') { 'pwsh' } else { 'powershell' }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Die($msg)  { Write-Host "::error::FAILED: $msg" -ForegroundColor Red; exit 1 }

# Native-command runner that aborts on nonzero exit (PS 5.1 has no `&&`).
function Run($exe, [string[]]$cmdArgs) {
    Write-Host "> $exe $($cmdArgs -join ' ')" -ForegroundColor DarkGray
    & $exe @cmdArgs
    if ($LASTEXITCODE -ne 0) { Die "$exe exited $LASTEXITCODE" }
}

# Run a repo Python script with the right interpreter on each platform.
function RunPy([string[]]$scriptArgs) {
    if ($IsWindowsHost) { Run 'py' (@('-3.12') + $scriptArgs) }
    else { Run 'python' $scriptArgs }
}

function Restore-PriorSnapshot([string]$ImageName) {
    Step 'Restore prior snapshot state (best effort)'
    $dataDir = Join-Path $RepoRoot 'backend/data'
    if (-not (Test-Path -LiteralPath $dataDir)) {
        New-Item -ItemType Directory -Path $dataDir | Out-Null
    }

    docker pull "$ImageName`:latest" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'No prior :latest image available; treating this as a first run and continuing.' -ForegroundColor Yellow
        return
    }

    $containerId = (& docker create "$ImageName`:latest").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $containerId) {
        Write-Host 'Could not create a throwaway container for restore; continuing with a full refresh.' -ForegroundColor Yellow
        return
    }
    try {
        docker cp "$containerId`:/app/backend/data/." $dataDir | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Restored prior backend/data tree from $ImageName`:latest." -ForegroundColor Green
        } else {
            Write-Host 'Prior snapshot restore failed; continuing with a full refresh.' -ForegroundColor Yellow
        }
    } finally {
        docker rm $containerId | Out-Null
    }
}

# --- 0. New-session / idempotency guard (FR-005) ---------------------------
if ($SkipGuard) {
    Step 'New-session guard SKIPPED (-SkipGuard) -- publishing unconditionally'
} else {
    Step 'New-session guard'
    $publishedManifest = Join-Path ([System.IO.Path]::GetTempPath()) 'screener-published-manifest.json'
    if (Test-Path -LiteralPath $publishedManifest) { Remove-Item -LiteralPath $publishedManifest -Force }
    # Fetch the currently-published manifest from the live :latest image (byte-exact
    # via docker cp, so no PowerShell re-encoding). Cross-platform: no cmd.exe.
    & docker pull "$Image`:latest" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $guardCid = & docker create "$Image`:latest" 2>$null
        if ($LASTEXITCODE -eq 0 -and $guardCid) {
            $guardCid = ($guardCid | Select-Object -Last 1).ToString().Trim()
            & docker cp "$guardCid`:/app/backend/data/manifest.json" $publishedManifest 2>$null | Out-Null
            & docker rm $guardCid 2>$null | Out-Null
        }
    }
    $guardScript = @('scripts/_session_guard.py')
    if (Test-Path -LiteralPath $publishedManifest) {
        $guardScript += @('--published-manifest', $publishedManifest)
    }
    if ($IsWindowsHost) { $guardOutput = & py (@('-3.12') + $guardScript) }
    else { $guardOutput = & python $guardScript }
    if ($LASTEXITCODE -ne 0) { Die 'session guard failed to run' }
    $outcome = ($guardOutput | Select-Object -Last 1).Trim()
    $guardOutput | Select-Object -SkipLast 1 | ForEach-Object { Write-Host $_ }
    if ($outcome -eq 'noop') {
        Write-Host 'No new completed trading session to publish -- documented no-op.' -ForegroundColor Yellow
        exit 0
    }
    Write-Host "Guard: $outcome" -ForegroundColor Green
}

# --- 1. Refresh data locally (incremental only) -----------------------------
if ($SkipRefresh) {
    Step 'Data refresh SKIPPED (-SkipRefresh) -- baking whatever is on disk'
} else {
    Restore-PriorSnapshot $Image

    Step 'Refresh universe'
    RunPy @('scripts/seed_universe.py')

    if ($FullStooq) {
        Step 'Refresh full Stooq deep-history bundle (heavy; ~90-day cadence)'
        RunPy @('scripts/refresh_stooq_history.py')
    } else {
        Write-Host 'Skipping full Stooq bundle (use -FullStooq ~quarterly). Incremental bars come from ingest_daily.'
    }

    # NO --skip-events: earnings/8-K must refresh into catalog.db or the hosted
    # snapshot ships stale earnings badges (see deploy-010 gotchas).
    Step 'Incremental daily ingest (prices + events + Shariah + fundamentals)'
    RunPy @('scripts/ingest_daily.py')
}

# --- 2. Verify freshness ----------------------------------------------------
Step 'Verify snapshot freshness (backend/data/manifest.json)'
$manifestPath = Join-Path $RepoRoot 'backend/data/manifest.json'
if (-not (Test-Path $manifestPath)) { Die "manifest.json not found at $manifestPath" }
Write-Host "manifest.json last written: $((Get-Item $manifestPath).LastWriteTime)"
Select-String -Path $manifestPath -Pattern 'data_as_of' |
    ForEach-Object { Write-Host ('  ' + $_.Line.Trim()) }

# Non-fatal compliance-deadline heads-up: warn (loudly, into the CI step summary)
# when the Halal Terminal source is within its 90-day deadline or already past it,
# so the owner re-runs the refresh before the hosted universe bakes stale. Never
# a publish gate -- stale compliance is a warning, not a corrupt snapshot.
RunPy @('scripts/check_data_freshness.py')

# --- 3. Data-integrity harness (008) ----------------------------------------
Step 'Data-integrity harness'
$asOf = Get-Date -Format 'yyyy-MM-dd'
$harnessOut = Join-Path $RepoRoot 'backend/data/harness-report.md'
RunPy @('scripts/run_integrity_harness.py', '--as-of', $asOf, '--out', $harnessOut)

# --- 4. Release secret scan (SC-008 / FR-002a/006) --------------------------
if ($SkipSecretScan) {
    Step 'Secret scan SKIPPED (-SkipSecretScan)'
} else {
    Step 'Release secret scan (repo + image copy list)'
    & $PsHostExe -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'secret_scan.ps1')
    if ($LASTEXITCODE -ne 0) { Die 'secret scan found potential secrets -- aborting before build.' }
}

# --- 5. Export the local FinBERT ONNX artifact ------------------------------
Step 'Export FinBERT ONNX model (idempotent)'
RunPy @('scripts/export_finbert_onnx.py')

# --- 6. Build the backend image ---------------------------------------------
# Already gated on the snapshot having changed -- step 0's guard short-circuits
# the whole chain (no build/push) when there is no new completed session.
Step "Build image  $Image`:latest  (+ :$Tag)"
if ($env:GITHUB_ACTIONS -eq 'true') {
    # Persist Docker layer cache across CI runs via the GitHub Actions cache backend.
    Run 'docker' @(
        'buildx', 'build', '-f', 'backend/Dockerfile',
        '-t', "$Image`:latest", '-t', "$Image`:$Tag",
        '--cache-from', 'type=gha', '--cache-to', 'type=gha,mode=max',
        '--load', '.'
    )
} else {
    Run 'docker' @('build', '-f', 'backend/Dockerfile', '-t', "$Image`:latest", '-t', "$Image`:$Tag", '.')
}

# --- 7. Push to GHCR ----------------------------------------------------------
Step 'Push to GHCR'
Run 'docker' @('push', "$Image`:latest")
Run 'docker' @('push', "$Image`:$Tag")
$digest = $null
try { $digest = (& docker inspect --format '{{index .RepoDigests 0}}' "$Image`:latest") } catch { $digest = $null }
if ($digest) { Write-Host "Pushed digest: $digest" -ForegroundColor Green }

# --- 8. Deploy: notify, or auto Factory-rebuild with -Deploy ----------------
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
} else {
    Step 'NEXT STEP -- deploy manually'
    Write-Host "Image published. Factory-reboot https://huggingface.co/spaces/$SpaceId to go live (a plain Restart will NOT re-pull the new image)." -ForegroundColor Yellow
}

Write-Host "`nDone." -ForegroundColor Green
