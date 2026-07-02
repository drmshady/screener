# Release secret scan for feature 010 (online deployment).
#
# Scans the repository AND the exact file set the backend Docker image bakes in
# (the "assembled image copy list" parsed from backend/Dockerfile) for provider
# API keys and owner/session secrets. Exits 1 on any hit.
#
# Enforces SC-008 / FR-010: secrets are runtime env only and must never appear in
# the repo or any deployed artifact. Run as a release check (tasks T033, T039).
#
# It flags secret *values*, not env-var *names*: runbooks, contracts,
# render.yaml (sync: false) and code reading process.env / os.getenv reference
# the names without values and must not trip the scan.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/secret_scan.ps1

[CmdletBinding()]
param(
    [string]$RepoRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $RepoRoot) {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $RepoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
}

# Key-material formats — always a finding.
$MaterialPatterns = @(
    @{ Name = 'PEM private key';      Regex = '-----BEGIN [A-Z ]*PRIVATE KEY-----' },
    @{ Name = 'Google OAuth secret';  Regex = 'GOCSPX-[A-Za-z0-9_-]{10,}' },
    @{ Name = 'Google API key';       Regex = 'AIza[0-9A-Za-z_-]{35}' },
    @{ Name = 'AWS access key id';    Regex = 'AKIA[0-9A-Z]{16}' }
)

# Secret-bearing env var names: flag NAME=<value> only when <value> looks like
# real entropy and is not an obvious placeholder / code reference.
$SecretNames = @(
    'SCREENER_OWNER_SECRET',
    'AUTH_SECRET',
    'AUTH_GOOGLE_SECRET',
    'AUTH_GOOGLE_ID',
    'EODHD_API_KEY',
    'EOD_HISTORICAL_DATA_API_KEY',
    'SCREENER_PROVIDER_KEY',
    'FINNHUB_API_KEY',
    'ALPHAVANTAGE_API_KEY',
    'GEMINI_API_KEY',
    'ANTHROPIC_API_KEY'
)

$PlaceholderRegex = '(?i)(\$env:|process\.env|os\.getenv|os\.environ|getenv|sync:|your[-_]|example|changeme|placeholder|xxxx|from a2|same as|token_urlsafe|replace|redacted)'

$TextExtensions = @(
    '.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.yaml', '.yml', '.md',
    '.txt', '.env', '.cfg', '.ini', '.toml', '.sh', '.ps1', '.html', '.css', '.example'
)

# Bulk public-data trees (baked into the image): key-material scan only, no
# per-name config heuristic (these are SEC/price data, not config files).
$BulkDataRegex = '(?i)[\\/]data[\\/](edgar_cache|prices|backtests|regime|halal_terminal_cache)[\\/]'

$findings = New-Object System.Collections.Generic.List[object]

function Scan-File {
    param([string]$FullPath, [string]$DisplayPath)

    $ext = [System.IO.Path]::GetExtension($FullPath).ToLowerInvariant()
    if ($TextExtensions -notcontains $ext) { return }
    if (-not (Test-Path -LiteralPath $FullPath)) { return }
    if ($DisplayPath -match 'secret_scan\.ps1$') { return }

    $text = [System.IO.File]::ReadAllText($FullPath)

    # Key-material patterns run on every scanned file (fast, whole-content).
    foreach ($m in $MaterialPatterns) {
        if ($text -match $m.Regex) {
            $findings.Add([pscustomobject]@{ File = $DisplayPath; Kind = $m.Name })
        }
    }

    # The NAME=<value> heuristic is for config/source files only — skip the bulk
    # public-data trees (no secrets there, and full line scans are needlessly slow).
    if ($DisplayPath -match $BulkDataRegex) { return }

    foreach ($name in $SecretNames) {
        $assign = [regex]::Match($text, ($name + '\s*[:=]\s*"?([A-Za-z0-9_\-\.\/+]+)'))
        if ($assign.Success) {
            $val = $assign.Groups[1].Value
            $looksReal = ($val.Length -ge 12) -and ($val -match '[0-9]') -and ($val -match '[A-Za-z]')
            $context = [regex]::Match($text, ($name + '\s*[:=]\s*"?<')).Success
            if ($looksReal -and -not $context) {
                # Re-check the specific line for placeholder/reference markers.
                $lineMatch = [regex]::Match($text, ('.*' + [regex]::Escape($name) + '.*'))
                if ($lineMatch.Value -notmatch $PlaceholderRegex) {
                    $findings.Add([pscustomobject]@{ File = $DisplayPath; Kind = ('Assigned ' + $name) })
                }
            }
        }
    }
}

Write-Host "Secret scan over repo: $RepoRoot"

# 1. Repo: all git-tracked files (working tree).
Push-Location $RepoRoot
try {
    $tracked = & git ls-files
} finally {
    Pop-Location
}
foreach ($rel in $tracked) {
    if ([string]::IsNullOrWhiteSpace($rel)) { continue }
    Scan-File -FullPath (Join-Path $RepoRoot $rel) -DisplayPath $rel
}

# 2. Assembled image copy list: the files the backend Dockerfile bakes in.
$dockerfile = Join-Path $RepoRoot 'backend/Dockerfile'
$copySources = @()
if (Test-Path -LiteralPath $dockerfile) {
    foreach ($line in [System.IO.File]::ReadLines($dockerfile)) {
        $cm = [regex]::Match($line, '^\s*COPY\s+(\S+)\s+\S+')
        if ($cm.Success) {
            $src = $cm.Groups[1].Value
            if ($src -notmatch '^/tmp' -and $src -notmatch '^/') { $copySources += $src }
        }
    }
}
Write-Host ("Assembled image copy list: {0} source path(s)" -f $copySources.Count)
foreach ($src in $copySources) {
    $full = Join-Path $RepoRoot $src
    if (Test-Path -LiteralPath $full -PathType Container) {
        Get-ChildItem -LiteralPath $full -Recurse -File | ForEach-Object {
            $rel = $_.FullName.Substring($RepoRoot.Length).TrimStart('\', '/')
            Scan-File -FullPath $_.FullName -DisplayPath $rel
        }
    } elseif (Test-Path -LiteralPath $full -PathType Leaf) {
        Scan-File -FullPath $full -DisplayPath $src
    }
}

# Report.
if ($findings.Count -gt 0) {
    Write-Host ''
    Write-Host ("SECRET SCAN FAILED - {0} potential secret(s) found:" -f $findings.Count) -ForegroundColor Red
    foreach ($f in $findings) {
        Write-Host ("  {0}  [{1}]" -f $f.File, $f.Kind) -ForegroundColor Red
    }
    exit 1
}

Write-Host ''
Write-Host "SECRET SCAN PASSED - no provider keys or owner secrets found in repo or image copy list." -ForegroundColor Green
exit 0
