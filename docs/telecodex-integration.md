# Telecodex Integration

Telecodex is a Telegram bridge for the OpenAI Codex CLI SDK.  
This document covers the integration of the `vendor/telecodex` submodule into this repository.

Pinned commit: `fd2a24134f0459e15df877bd5c8c7fc7455253fd`

---

## Architecture

```
Telegram user
     │  voice / text
     ▼
vendor/telecodex (Node.js, grammy)
     │  Codex SDK calls
     ▼
OpenAI Codex CLI SDK  ──►  sandboxed workspace (workspace-write)
     │
     ▼  (voice only, Windows)
OpenAI Whisper API  ←  OPENAI_API_KEY
```

- **Transport**: [grammy](https://grammy.dev/) Telegram Bot API library.
- **AI backend**: `@openai/codex-sdk` — same runtime as the local `codex` CLI.
- **Voice (Windows)**: OpenAI Whisper REST API via `OPENAI_API_KEY`.  
  `parakeet-coreml` (Apple Neural Engine) is **macOS-only** and is not available on Windows.
- **Security**: `CODEX_SANDBOX_MODE=workspace-write` limits writes to the selected workspace.
- **Workspace history**: `/new` and `/sessions` can list workspaces from the local
  Codex history in `~/.codex`. Keep `TELEGRAM_ALLOWED_USER_IDS` restricted to
  trusted users because they can select those historical workspaces.

---

## Setup

### Prerequisites

| Tool | Minimum version | Install |
|------|-----------------|---------|
| Git  | any recent      | <https://git-scm.com> |
| Node.js | **22 LTS**  | <https://nodejs.org> |
| npm  | bundled with Node | — |
| codex CLI | latest   | `npm install -g @openai/codex` |

### 1. Clone the submodule and build

Run the provided setup script from the repository root:

```powershell
.\scripts\setup-telecodex.ps1
```

This will:
1. Verify prerequisites (Git, Node 22+, npm, codex).
2. Initialise the `vendor/telecodex` submodule using Git's OpenSSL HTTP backend.
3. Check out and verify the pinned commit `fd2a24134f0459e15df877bd5c8c7fc7455253fd`.
4. Run `npm ci` and `npm run build` inside `vendor/telecodex`.
5. Copy `.env.telecodex.example` to the repository-root `.env` if absent.

### 2. Configure BotFather token

1. Open Telegram and message **@BotFather**.
2. Send `/newbot` and follow the prompts.
3. Copy the HTTP API token (format: `123456789:AAF...`).
4. Open the repository-root `.env` and set:  
   `TELEGRAM_BOT_TOKEN=<paste token here>`

### 3. Find your numeric Telegram user ID

1. Message **@userinfobot** or **@RawDataBot** on Telegram.
2. Copy the numeric ID shown (e.g. `987654321`).
3. Set `TELEGRAM_ALLOWED_USER_IDS=987654321` in the repository-root `.env`.

### 4. Codex login

Authenticate the local Codex CLI once:

```powershell
codex login
```

Follow the browser OAuth flow. The credentials are cached locally and reused by Telecodex.

### 5. Windows voice setup (OpenAI Whisper)

On Windows, voice-to-text uses the **OpenAI Whisper API** because `parakeet-coreml` requires Apple Silicon and is macOS-only.

Set your key in the repository-root `.env`:

```
OPENAI_API_KEY=sk-...
```

Whisper API pricing: <https://openai.com/pricing>

---

## Start

```powershell
.\scripts\start-telecodex.ps1
```

The start script:
1. Parses the repository-root `.env` safely — no `Invoke-Expression`, splits on the first `=` only, skips blank lines and comments.
2. Validates `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS`, and warns if `OPENAI_API_KEY` is missing.
3. Checks `codex --version` and `codex login status`.
4. Confirms `vendor/telecodex/dist/index.js` exists.
5. Sets working directory to the repository root.
6. Launches `node <absolute-path-to-dist/index.js>`.
7. Restores the original working directory on exit.

---

## Security

The default configuration is deliberately restrictive:

| Variable | Safe default | Effect |
|----------|-------------|--------|
| `CODEX_SANDBOX_MODE` | `workspace-write` | Codex can modify the selected project but not arbitrary paths |
| `CODEX_APPROVAL_POLICY` | `never` | Automated; no interactive prompts |
| `ENABLE_UNSAFE_LAUNCH_PROFILES` | `false` | Hides the `danger-full-access` profile |
| `ENABLE_TELEGRAM_LOGIN` | `false` | Disables Telegram Login widget |
| `TELEGRAM_ALLOWED_USER_IDS` | (your ID) | Only you can send messages |

> **Never commit the repository-root `.env` or any file containing real tokens.**

---

## Troubleshooting

### `codex not found`
```powershell
npm install -g @openai/codex
```

### `dist/index.js not found`
```powershell
.\scripts\setup-telecodex.ps1
```

### `TELEGRAM_BOT_TOKEN is not set`
Open the repository-root `.env` and paste your BotFather token.

### `OPENAI_API_KEY` missing / Whisper errors
Whisper is required for voice messages on Windows. Set `OPENAI_API_KEY` in `.env`.

### Bot does not respond to your messages
Confirm your numeric Telegram user ID is listed in `TELEGRAM_ALLOWED_USER_IDS`.

### Git TLS or Schannel errors
The setup script uses `git -c http.sslBackend=openssl` for submodule initialization.

### `codex login` expires
Run `codex login` again to refresh credentials.

---

## Upgrade

> [!CAUTION]
> Only upgrade to a reviewed and tested commit. Always update the pinned SHA in
> `scripts/setup-telecodex.ps1`, this document, and re-run the setup script after.

**Steps to upgrade:**

1. Read the upstream changelog at <https://github.com/benedict2310/telecodex>.
2. Review the diff between the current pin and the new commit.
3. Update `$PINNED_SHA` in `scripts/setup-telecodex.ps1`.
4. Update the pinned commit reference in this document.
5. Run `.\scripts\setup-telecodex.ps1` to rebuild.
6. Test with `.\scripts\start-telecodex.ps1`.

Current pin: `fd2a24134f0459e15df877bd5c8c7fc7455253fd`
