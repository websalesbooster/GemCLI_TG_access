<#
.SYNOPSIS
    Start the Telecodex Telegram bot.
.DESCRIPTION
    Parses the repository-root .env safely (no Invoke-Expression), validates
    required environment variables, verifies codex login status, confirms
    the dist/index.js entrypoint exists, then launches the bot with node
    from the repository root.

    Safe .env parser rules:
      - Blank lines and lines beginning with # are skipped.
      - Only the first '=' is used as the key/value separator.
      - No shell expansion or Invoke-Expression is used.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$Vendor    = Join-Path $RepoRoot 'vendor\telecodex'
$EnvFile = Join-Path $RepoRoot '.env'
$Entrypoint = Join-Path $Vendor 'dist\index.js'

# ── 1. Parse .env safely ────────────────────────────────────────────────────
if (-not (Test-Path $EnvFile)) {
    Write-Error "Repository-root .env not found. Run scripts\setup-telecodex.ps1 first."
    exit 1
}

Write-Host "Loading environment from repository-root .env..." -ForegroundColor Cyan
foreach ($line in (Get-Content $EnvFile)) {
    # Skip blank lines and comments
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $normalized = $line.Trim()
    if ($normalized.StartsWith('#')) { continue }
    if ($normalized.StartsWith('export ')) {
        $normalized = $normalized.Substring(7).Trim()
    }

    # Split on first '=' only
    $eqIdx = $normalized.IndexOf('=')
    if ($eqIdx -lt 1) { continue }

    $key = $normalized.Substring(0, $eqIdx).Trim()
    $value = $normalized.Substring($eqIdx + 1).Trim()
    if (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    $value = $value.Replace('\n', "`n")

    # Set in the current process environment (no Invoke-Expression)
    [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
}

# ── 2. Validate required variables ──────────────────────────────────────────
Write-Host "Validating configuration..." -ForegroundColor Cyan

$token = [System.Environment]::GetEnvironmentVariable('TELEGRAM_BOT_TOKEN')
if ([string]::IsNullOrWhiteSpace($token) -or $token -like 'replace_*') {
    Write-Error "TELEGRAM_BOT_TOKEN is not set. Edit the repository-root .env."
    exit 1
}

$allowedIds = [System.Environment]::GetEnvironmentVariable('TELEGRAM_ALLOWED_USER_IDS')
if ([string]::IsNullOrWhiteSpace($allowedIds) -or $allowedIds -like 'replace_*') {
    Write-Error "TELEGRAM_ALLOWED_USER_IDS is not set. Edit the repository-root .env."
    exit 1
}

# OPENAI_API_KEY is required on Windows for voice transcription via Whisper
# (parakeet-coreml is macOS-only and is not available on Windows)
$openaiKey = [System.Environment]::GetEnvironmentVariable('OPENAI_API_KEY')
if ([string]::IsNullOrWhiteSpace($openaiKey)) {
    Write-Warning "OPENAI_API_KEY is not set. Voice transcription via OpenAI Whisper will be unavailable."
}

Write-Host "  TELEGRAM_BOT_TOKEN   OK" -ForegroundColor Green
Write-Host "  TELEGRAM_ALLOWED_USER_IDS  OK" -ForegroundColor Green

# ── 3. Verify codex version and login status ─────────────────────────────────
Write-Host "Checking codex CLI..." -ForegroundColor Cyan

if (-not (Get-Command 'codex' -ErrorAction SilentlyContinue)) {
    Write-Error "codex not found. Install with: npm install -g @openai/codex"
    exit 1
}

$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    codex --version

    # Check login / auth status (read-only check, no inference request)
    Write-Host "Checking codex login status..." -ForegroundColor Cyan
    codex login status
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Codex is not authenticated. Run codex login and try again."
        exit 1
    }
} finally {
    $ErrorActionPreference = $oldErrorActionPreference
}

# ── 4. Confirm entrypoint exists ─────────────────────────────────────────────
if (-not (Test-Path $Entrypoint)) {
    Write-Error "dist/index.js not found. Run scripts\setup-telecodex.ps1 to build first."
    exit 1
}
Write-Host "  dist/index.js  OK" -ForegroundColor Green

# ── 5. Set working directory to repository root, then launch ─────────────────
Write-Host "Launching Telecodex..." -ForegroundColor Cyan

$originalLocation = Get-Location
Set-Location $RepoRoot
try {
    node $Entrypoint
} finally {
    # Restore original location regardless of how node exits
    Set-Location $originalLocation
}
