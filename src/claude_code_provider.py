"""Claude Code CLI provider (sync version) for text-only tasks.

Used as Gemini replacement for: summarize_text, generate_concise_title,
classify_bookmark, analyze_visual_cues (text-only). Multimodal calls
(audio/video) stay on Gemini.
"""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def call_claude_code(prompt: str, context: str = "", timeout: int = 180) -> str:
    """Call Claude Code CLI synchronously via subprocess.

    Args:
        prompt: Full prompt text (sent via stdin)
        context: Logging label
        timeout: Max seconds to wait

    Returns:
        Claude's text response
    """
    model = os.getenv("CLAUDE_CODE_MODEL", "sonnet")

    try:
        result = subprocess.run(
            ["claude", "--print", "--model", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            err = result.stderr[:500] if result.stderr else ""
            raise RuntimeError(f"Claude Code exit {result.returncode}: {err}")
        output = result.stdout.strip()
        if not output:
            raise RuntimeError("Claude Code empty response")
        logger.info(f"Claude Code OK ({context}, {len(output)} chars)")
        return output
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude Code timeout ({context}, {timeout}s)")


def is_enabled() -> bool:
    return os.getenv("USE_CLAUDE_CODE", "false").lower() == "true"
