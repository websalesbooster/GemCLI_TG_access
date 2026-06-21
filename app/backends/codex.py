"""Codex CLI backend implementation."""

import asyncio
import json
import logging
import os
import re
from pathlib import Path

from app.types import AssistantReply

logger = logging.getLogger(__name__)

# Sensitive environment variables to remove from child process
SANITIZED_ENV_VARS = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CODEX_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "DATABASE_URL",
    "SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
}

# Output limit to prevent resource exhaustion
OUTPUT_LIMIT = 1024 * 1024  # 1MB


def sanitize_input(user_input: str) -> str:
    """Sanitize user input to prevent shell injection."""
    sanitized = user_input
    # Remove command substitution $(...)
    sanitized = re.sub(r"\$\(.*?\)", "", sanitized)
    # Remove backticks
    sanitized = re.sub(r"`.*?`", "", sanitized)
    # Escape quotes
    sanitized = sanitized.replace('"', '\\"').replace("'", "\\'")
    # Remove semicolons
    sanitized = sanitized.replace(";", "")
    # Replace newlines with spaces
    sanitized = sanitized.replace("\n", " ").replace("\r", "")
    return sanitized


def sanitize_environment(env: dict) -> dict:
    """Remove sensitive environment variables from child process."""
    return {k: v for k, v in env.items() if k not in SANITIZED_ENV_VARS}


class CodexCLIBackend:
    """Backend implementation using Codex CLI."""

    def __init__(self, workspace: Path, timeout: int = 60):
        self.workspace = workspace
        self.timeout = timeout

    async def ask(
        self, prompt: str, session_id: str | None = None
    ) -> AssistantReply:
        """
        Execute Codex CLI and return assistant reply.

        Args:
            prompt: The user's prompt to send to Codex CLI
            session_id: Optional thread ID to resume an existing session

        Returns:
            AssistantReply with text and session_id for continuation
        """
        sanitized_prompt = sanitize_input(prompt)

        if session_id:
            cmd = [
                "codex",
                "exec",
                "resume",
                session_id,
                "--json",
                "-",
            ]
        else:
            cmd = [
                "codex",
                "exec",
                "--json",
                "--sandbox",
                "read-only",
                "--ask-for-approval",
                "never",
                "--ignore-user-config",
                "--cd",
                str(self.workspace),
                "-",
            ]

        logger.info(
            "Executing Codex CLI command",
            extra={"command": " ".join(cmd[:6]) + " ..."},
        )

        try:
            thread_id, response_text = await self._run_command(
                cmd, sanitized_prompt
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Codex CLI timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"Codex CLI execution failed: {e}")
            raise

        # Use returned thread_id if available, otherwise keep existing session_id
        final_session_id = thread_id if thread_id else session_id

        return AssistantReply(
            text=response_text,
            session_id=final_session_id,
        )

    async def _run_command(
        self, cmd: list[str], prompt: str
    ) -> tuple[str | None, str]:
        """
        Run Codex CLI command with prompt through stdin.

        Args:
            cmd: Command to execute
            prompt: Prompt to send through stdin

        Returns:
            Tuple of (thread_id, response_text)
        """
        # Sanitize environment
        env = sanitize_environment(dict(os.environ))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(self.workspace),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode("utf-8")),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise

        # Cap output to prevent resource exhaustion
        stdout = stdout[:OUTPUT_LIMIT]
        stderr = stderr[:OUTPUT_LIMIT]

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            logger.error(f"Codex CLI returned non-zero: {error_msg}")
            raise RuntimeError(f"Codex CLI error: {error_msg}")

        # Parse JSONL response
        thread_id = None
        agent_message = None

        for line in stdout.decode("utf-8").strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)

                # Extract thread.started.thread_id
                if (
                    event.get("type") == "thread"
                    and event.get("event") == "started"
                ):
                    thread_id = event.get("thread_id")

                # Extract final agent_message
                if event.get("type") == "agent_message":
                    agent_message = event.get("content", "")

                # Also check for message content in other event types
                if "message" in event and isinstance(event["message"], dict):
                    content = event["message"].get("content", "")
                    if content:
                        agent_message = content

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSONL line: {line[:100]}")

        if not agent_message:
            # If no agent_message found, use any content from events
            logger.warning("No agent_message found in Codex CLI output")

        return thread_id, agent_message or "No response received from Codex CLI"

    async def health_check(self) -> bool:
        """
        Verify Codex CLI is available and logged in.

        Returns:
            True if Codex CLI is ready, False otherwise
        """
        try:
            # Check version
            version_process = await asyncio.create_subprocess_exec(
                "codex",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            version_out, version_err = await asyncio.wait_for(
                version_process.communicate(), timeout=10
            )

            if version_process.returncode != 0:
                logger.error(f"codex --version failed: {version_err.decode()}")
                return False

            # Check login status
            login_process = await asyncio.create_subprocess_exec(
                "codex",
                "login",
                "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            login_out, login_err = await asyncio.wait_for(
                login_process.communicate(), timeout=10
            )

            if login_process.returncode != 0:
                logger.error(f"codex login status failed: {login_err.decode()}")
                return False

            logger.info(
                f"Codex CLI health check passed: {version_out.decode().strip()}"
            )
            return True

        except asyncio.TimeoutError:
            logger.error("Codex CLI health check timed out")
            return False
        except FileNotFoundError:
            logger.error("Codex CLI not found in PATH")
            return False
        except Exception as e:
            logger.error(f"Codex CLI health check failed: {e}")
            return False