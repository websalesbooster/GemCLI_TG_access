<#
.SYNOPSIS
    Set up the Telecodex submodule for the GemCLI TG access project.
.DESCRIPTION
    Checks prerequisites (Git, Node 22+, npm, codex), initialises the
    vendor/telecodex git submodule, verifies the pinned commit, runs npm ci
    and npm run build, and creates the repository-root .env when absent.

    Pinned SHA: fd2a24134f0459e15df877bd5c8c7fc7455253fd
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PIN - exact commit that this integration was tested against
$PINNED_SHA = 'fd2a24134f0459e15df877bd5c8c7fc7455253fd'

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$Vendor    = Join-Path $RepoRoot 'vendor\telecodex'
$EnvDest = Join-Path $RepoRoot '.env'
$EnvSource = Join-Path $RepoRoot '.env.telecodex.example'

function Require-Command {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "Required command not found: $Name. $Hint"
        exit 1
    }
}

# ── 1. Prerequisite checks ─────────────────────────────────────────────────
Write-Host "Checking prerequisites..." -ForegroundColor Cyan

# git
Require-Command 'git' 'Install Git from https://git-scm.com'

# node – require major version 22+
Require-Command 'node' 'Install Node.js 22 LTS from https://nodejs.org'
$nodeVersion = (node --version) -replace '^v',''
$nodeMajor   = [int]($nodeVersion -split '\.')[0]
if ($nodeMajor -lt 22) {
    Write-Error "Node version 22+ required; found v$nodeVersion. Install Node 22 LTS."
    exit 1
}
Write-Host "  node v$nodeVersion  OK" -ForegroundColor Green

# npm
Require-Command 'npm' 'npm ships with Node.js; reinstall Node 22.'

# codex
Require-Command 'codex' 'Install codex: npm install -g @openai/codex'

Write-Host "All prerequisites satisfied." -ForegroundColor Green

# Initialize the git submodule using OpenSSL instead of Windows Schannel.
Write-Host "Initialising git submodule vendor/telecodex..." -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    git -c http.sslBackend=openssl submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) {
        throw "Git submodule initialization failed."
    }
} finally {
    Pop-Location
}

# ── 4. Check out the exact pinned SHA ───────────────────────────────────────
Write-Host "Checking out pinned SHA $PINNED_SHA..." -ForegroundColor Cyan
Push-Location $Vendor
try {
    git checkout --detach $PINNED_SHA
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to check out the pinned Telecodex commit."
    }
    $actualSha = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualSha -ne $PINNED_SHA) {
        throw "Telecodex pin verification failed. Expected $PINNED_SHA; found $actualSha."
    }
} finally {
    Pop-Location
}

# ── 5. Install dependencies (no network beyond what npm ci uses) ─────────────
Write-Host "Running npm ci in vendor/telecodex..." -ForegroundColor Cyan
Push-Location $Vendor
try {
    npm ci --prefer-offline
    if ($LASTEXITCODE -ne 0) {
        throw "npm ci failed."
    }
} finally {
    Pop-Location
}

# ── 6. Build ─────────────────────────────────────────────────────────────────
Write-Host "Running npm run build in vendor/telecodex..." -ForegroundColor Cyan
Push-Location $Vendor
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run build failed."
    }
} finally {
    Pop-Location
}

# ── 7. Copy .env only when absent ───────────────────────────────────────────
if (Test-Path $EnvDest) {
    Write-Host ".env already exists at the repository root; skipping copy." -ForegroundColor Yellow
} else {
    Copy-Item $EnvSource $EnvDest
    Write-Host "Copied .env.telecodex.example to the repository-root .env." -ForegroundColor Green
    Write-Host "Open .env and fill in your secrets before starting." -ForegroundColor Yellow
}

Write-Host "`nSetup complete. Run scripts\start-telecodex.ps1 to launch." -ForegroundColor Cyan
