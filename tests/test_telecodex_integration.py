"""
Telecodex integration artifact tests.
All missing-file cases yield AssertionError, never FileNotFoundError.
Run: python -m pytest tests/test_telecodex_integration.py -v
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str | None:
    """Return file text or None if the file does not exist."""
    p = ROOT / rel
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def _powershell_parser_errors(rel: str) -> str:
    path = ROOT / rel
    command = (
        "$errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{path}', "
        "[ref]$null, [ref]$errors) | Out-Null; "
        "$errors | ForEach-Object { $_.Message }; "
        "if ($errors.Count -gt 0) { exit 1 }"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout + result.stderr).strip()


# ---------------------------------------------------------------------------
# .gitmodules
# ---------------------------------------------------------------------------
class TestGitmodules(unittest.TestCase):
    FILE = ".gitmodules"

    def setUp(self):
        self.text = _read(self.FILE)

    def test_file_exists(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")

    def test_vendor_telecodex_submodule_path(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn('path = vendor/telecodex', self.text)

    def test_vendor_telecodex_submodule_url(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        # URL must reference telecodex (any host)
        self.assertRegex(self.text, r'url\s*=.*telecodex')


# ---------------------------------------------------------------------------
# .env.telecodex.example
# ---------------------------------------------------------------------------
class TestEnvExample(unittest.TestCase):
    FILE = ".env.telecodex.example"

    def setUp(self):
        self.text = _read(self.FILE)

    def test_file_exists(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")

    def test_openai_api_key_placeholder(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        # Must declare the key without a real value (secure default)
        self.assertRegex(self.text, r'OPENAI_API_KEY\s*=\s*(?!sk-)\S*')

    def test_no_real_secret_committed(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertNotRegex(self.text, r'sk-[A-Za-z0-9]{20,}',
                            "Real OpenAI key must not appear in example env")

    def test_secure_defaults_present(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        for variable in (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_ALLOWED_USER_IDS",
            "OPENAI_API_KEY",
        ):
            self.assertIn(variable, self.text)
        self.assertIn("CODEX_SANDBOX_MODE=workspace-write", self.text)
        self.assertIn("ENABLE_UNSAFE_LAUNCH_PROFILES=false", self.text)


# ---------------------------------------------------------------------------
# scripts/setup-telecodex.ps1
# ---------------------------------------------------------------------------
class TestSetupScript(unittest.TestCase):
    FILE = "scripts/setup-telecodex.ps1"

    def setUp(self):
        self.text = _read(self.FILE)

    def test_file_exists(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")

    def test_node22_requirement(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'[Nn]ode\s*(?:v?22|version.*22)',
                         "Script must check/require Node 22")

    def test_git_requirement(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'\bgit\b', "Script must reference git")

    def test_codex_reference(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'\bcodex\b', "Script must reference codex")

    def test_submodule_init(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn(
            "git -c http.sslBackend=openssl submodule update --init --recursive",
            self.text,
        )

    def test_openssl_flag(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn("http.sslBackend=openssl", self.text)

    def test_pinned_sha(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        # A pinned SHA: 40-hex commit hash or explicit pin comment
        self.assertRegex(self.text, r'[0-9a-f]{40}|pinned|PIN',
                         "Script must contain a pinned SHA or pin marker")

    def test_npm_ci(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn('npm ci', self.text, "Script must run 'npm ci'")

    def test_build_step(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'npm\s+run\s+build|npm\s+build',
                         "Script must include a build step")

    def test_env_is_created_at_repository_root(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn("$EnvDest = Join-Path $RepoRoot '.env'", self.text)
        self.assertNotIn("$EnvDest = Join-Path $Vendor '.env'", self.text)

    def test_script_parses(self):
        self.assertEqual("", _powershell_parser_errors(self.FILE))


# ---------------------------------------------------------------------------
# scripts/start-telecodex.ps1
# ---------------------------------------------------------------------------
class TestStartScript(unittest.TestCase):
    FILE = "scripts/start-telecodex.ps1"

    def setUp(self):
        self.text = _read(self.FILE)

    def test_file_exists(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")

    def test_env_validation(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'OPENAI_API_KEY',
                         "Script must validate env (OPENAI_API_KEY)")

    def test_codex_login(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn("codex login status", self.text)
        self.assertNotIn("codex login --status", self.text)
        self.assertRegex(
            self.text,
            r"codex login status[\s\S]*?\$LASTEXITCODE",
            "Script must stop when Codex authentication is unavailable",
        )

    def test_dist_index_entrypoint(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'dist[/\\]index',
                         "Script must launch dist/index entrypoint")

    def test_node_interpreter(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'\bnode\b',
                         "Script must invoke node")

    def test_cwd_is_project_root(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        # Must set working directory to repo root, not a subdirectory
        self.assertRegex(self.text, r'PSScriptRoot|Set-Location|cd\s+\$',
                         "Script must set cwd to project root")

    def test_no_unsafe_flags(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertNotIn('--allow-all', self.text,
                         "Script must not use --allow-all (unsafe flag)")
        self.assertNotIn('--no-sandbox', self.text,
                         "Script must not use --no-sandbox")

    def test_env_is_loaded_from_repository_root(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn("$EnvFile = Join-Path $RepoRoot '.env'", self.text)
        self.assertNotIn("$EnvFile = Join-Path $Vendor '.env'", self.text)

    def test_env_parser_removes_matching_quotes(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn("$value.StartsWith('\"')", self.text)
        self.assertIn("$value.StartsWith(\"'\")", self.text)

    def test_script_parses(self):
        self.assertEqual("", _powershell_parser_errors(self.FILE))


# ---------------------------------------------------------------------------
# docs/telecodex-integration.md
# ---------------------------------------------------------------------------
class TestDocs(unittest.TestCase):
    FILE = "docs/telecodex-integration.md"

    def setUp(self):
        self.text = _read(self.FILE)

    def test_file_exists(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")

    def test_pinned_sha_documented(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'[0-9a-f]{40}|pinned|pin',
                         "Docs must document pinned SHA")

    def test_windows_openai_api_key(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertIn('OPENAI_API_KEY', self.text,
                      "Docs must mention OPENAI_API_KEY")
        self.assertRegex(self.text, r'[Ww]indows',
                         "Docs must cover Windows setup")

    def test_whisper_mentioned(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'[Ww]hisper',
                         "Docs must mention Whisper")

    def test_macos_parakeet_is_macos_only(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        text_lower = self.text.lower()
        if 'parakeet' in text_lower:
            # parakeet must be qualified as macOS-only
            idx = text_lower.index('parakeet')
            surrounding = text_lower[max(0, idx - 200): idx + 200]
            self.assertRegex(surrounding, r'mac(?:os|os x| only)|apple',
                             "parakeet must be marked macOS-only")

    def test_setup_section(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'(?i)#+\s*setup|##.*setup',
                         "Docs must have a Setup section")

    def test_start_section(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'(?i)#+\s*start|##.*start',
                         "Docs must have a Start/Usage section")

    def test_troubleshooting_section(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'(?i)#+\s*troubleshoot',
                         "Docs must have a Troubleshooting section")

    def test_upgrade_section(self):
        self.assertIsNotNone(self.text, f"{self.FILE} must exist")
        self.assertRegex(self.text, r'(?i)#+\s*upgrad',
                         "Docs must have an Upgrade section")


if __name__ == "__main__":
    unittest.main()
