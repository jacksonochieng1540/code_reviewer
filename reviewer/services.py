"""
AI review engine.

Wraps the Anthropic Messages API to turn a pasted code snippet into a
structured review: a summary, a 0-100 quality score, a list of line-anchored
issues (bug / security / performance / style / best-practice), and an
optional refactored version of the snippet.

Kept deliberately separate from views.py so the AI provider can be swapped
(e.g. for OpenAI) without touching request handling, and so it can be unit
tested by mocking `get_client()` / `review_code()` directly.
"""

import json
import logging

from anthropic import Anthropic, APIError
from django.conf import settings

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """You are a senior software engineer performing a rigorous code review.
You will be given a code snippet and its language. Respond with ONLY a single JSON object
(no markdown fences, no prose before or after) matching exactly this schema:

{
  "summary": "2-4 sentence plain-English summary of the code's overall quality and purpose",
  "overall_score": <integer 0-100, quality score>,
  "issues": [
    {
      "line": <integer or null if not line-specific>,
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "category": "bug" | "security" | "performance" | "style" | "best_practice" | "maintainability",
      "title": "short issue title, under 8 words",
      "description": "what is wrong and why it matters, 1-3 sentences",
      "suggestion": "concrete fix, described in words (not a diff)"
    }
  ],
  "suggested_refactor": "a revised version of the ENTIRE snippet with the most important fixes applied, as plain code text with no markdown fences. Use an empty string if the original code needs no changes or is too incomplete to safely rewrite."
}

Rules:
- Find real issues: bugs, edge cases, security vulnerabilities (injection, unsafe deserialization,
  hardcoded secrets, etc.), performance problems, poor naming, missing error handling, and
  violations of idiomatic style for the given language.
- Order `issues` by severity, most severe first.
- If the code is already excellent, return a short issues list (it can be empty) and a high score.
- Never invent line numbers you are not confident about — use null instead.
- Output must be valid JSON and nothing else.
"""


class AIReviewError(Exception):
    """Raised when the AI provider cannot produce a usable review."""


def get_client() -> Anthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise AIReviewError("ANTHROPIC_API_KEY is not configured on the server.")
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _extract_json(raw_text: str) -> dict:
    """Best-effort extraction of a JSON object from the model's text output."""
    text = raw_text.strip()
    # Strip accidental markdown fences even though the prompt forbids them.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def review_code(source_code: str, language: str) -> dict:
    """
    Send `source_code` to Claude and return a parsed dict matching the schema
    described in REVIEW_SYSTEM_PROMPT. Raises AIReviewError on any failure
    (network, auth, malformed response) so callers can handle it uniformly.
    """
    client = get_client()
    user_prompt = f"Language: {language}\n\nCode:\n```{language}\n{source_code}\n```"

    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=4000,
            system=REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except APIError as exc:
        logger.exception("Anthropic API error during code review")
        raise AIReviewError(f"AI provider error: {exc}") from exc

    raw_text = "".join(block.text for block in response.content if block.type == "text")

    try:
        parsed = _extract_json(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.exception("Failed to parse AI response as JSON: %s", raw_text[:500])
        raise AIReviewError("The AI response could not be parsed as JSON.") from exc

    parsed.setdefault("issues", [])
    parsed.setdefault("summary", "")
    parsed.setdefault("suggested_refactor", "")
    parsed["_raw_model"] = settings.ANTHROPIC_MODEL
    parsed["_usage"] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return parsed
