"""CLI-based LLM providers (sync): Gemini CLI → Codex → Claude Code fallback chain."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 240


def _enabled(name: str, default: bool = True) -> bool:
    val = os.getenv(name, "true" if default else "false").lower()
    return val == "true"


def _timeout(name: str, default: int = DEFAULT_TIMEOUT) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def call_gemini_cli(prompt: str, context: str = "") -> str:
    timeout = _timeout("GEMINI_CLI_TIMEOUT")
    result = subprocess.run(
        ["gemini", "-p", "", "--output-format", "text", "--skip-trust"],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Gemini CLI exit {result.returncode}: {result.stderr[:500]}")
    out = result.stdout.strip()
    if not out:
        raise RuntimeError("Gemini CLI empty")
    logger.info(f"Gemini CLI OK ({context}, {len(out)} chars)")
    return out


def call_codex(prompt: str, context: str = "") -> str:
    timeout = _timeout("CODEX_TIMEOUT")
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
        out_path = f.name
    try:
        result = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check",
             "--output-last-message", out_path, "-"],
            input=prompt, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Codex exit {result.returncode}: {result.stderr[:500]}")
        out = Path(out_path).read_text(encoding="utf-8").strip()
        if not out:
            raise RuntimeError("Codex empty")
        logger.info(f"Codex OK ({context}, {len(out)} chars)")
        return out
    finally:
        try: os.unlink(out_path)
        except Exception: pass


def call_claude_code(prompt: str, context: str = "") -> str:
    model = os.getenv("CLAUDE_CODE_MODEL", "sonnet")
    timeout = _timeout("CLAUDE_CODE_TIMEOUT")
    result = subprocess.run(
        ["claude", "--print", "--model", model],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude Code exit {result.returncode}: {result.stderr[:500]}")
    out = result.stdout.strip()
    if not out:
        raise RuntimeError("Claude Code empty")
    logger.info(f"Claude Code OK ({context}, {len(out)} chars)")
    return out


def call_cli_with_fallback(prompt: str, context: str = "") -> str:
    """Try Gemini CLI → Codex → Claude Code in order."""
    last_err = None
    if _enabled("USE_GEMINI_CLI"):
        try: return call_gemini_cli(prompt, context)
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini CLI failed ({context}), trying Codex: {e}")
    if _enabled("USE_CODEX"):
        try: return call_codex(prompt, context)
        except Exception as e:
            last_err = e
            logger.warning(f"Codex failed ({context}), trying Claude Code: {e}")
    if _enabled("USE_CLAUDE_CODE"):
        try: return call_claude_code(prompt, context)
        except Exception as e:
            last_err = e
            logger.warning(f"Claude Code failed ({context}): {e}")
    raise RuntimeError(f"All CLI providers failed ({context}): {last_err}")


def is_enabled() -> bool:
    """Backward-compat: any CLI provider enabled."""
    return _enabled("USE_GEMINI_CLI") or _enabled("USE_CODEX") or _enabled("USE_CLAUDE_CODE")
