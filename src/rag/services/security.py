"""Security guard for prompt injection defense and PII masking."""
import hashlib
import re
import secrets
from datetime import UTC, datetime

from src.core import get_logger, settings

logger = get_logger(__name__)


class CanaryToken:
    """Canary token generator and validator for injection detection."""

    def __init__(self) -> None:
        self._current_token: str | None = None
        self._token_hash: str | None = None

    def generate(self) -> str:
        """Generate a unique canary token for this request."""
        timestamp = datetime.now(tz=UTC).isoformat()
        random_part = secrets.token_hex(8)
        self._current_token = f"CANARY_{random_part}_{timestamp[:10]}"
        self._token_hash = hashlib.sha256(self._current_token.encode()).hexdigest()[:16]
        return self._current_token

    def get_instruction(self) -> str:
        """Get the canary instruction to embed in system prompt."""
        if not self._current_token:
            self.generate()
        return settings.security.canary_instruction_template.format(token=self._current_token)

    def validate_output(self, output: str) -> bool:
        """Check if output contains the canary token (leak detection)."""
        if not self._current_token:
            return True

        if self._current_token in output:
            logger.warning("CANARY LEAK: Token found in output - injection suspected")
            return False

        if self._token_hash and self._token_hash in output:
            logger.warning("CANARY LEAK: Token hash found in output")
            return False

        return True


canary = CanaryToken()


def mask_pii(text: str) -> str:
    """Mask personally identifiable information in text."""
    result = text
    for pattern, replacement in settings.security.pii_patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def detect_injection(text: str) -> bool:
    """Detect potential prompt injection attempts in user input."""
    text_lower = text.lower()
    for pattern in settings.security.user_injection_patterns:
        if re.search(pattern, text_lower):
            logger.warning("Potential user injection detected: %s", pattern)
            return True
    return False


def detect_context_injection(text: str) -> bool:
    """Detect potential indirect injection in retrieved context."""
    text_lower = text.lower()

    for pattern in settings.security.context_injection_patterns:
        if re.search(pattern, text_lower):
            logger.warning("Potential context injection detected: %s", pattern)
            return True

    for marker in settings.security.boundary_markers:
        if marker.lower() in text_lower:
            logger.warning("Boundary marker found in context: %s", marker)
            return True

    return False


def escape_context_boundaries(text: str) -> str:
    """Escape potential boundary markers in context to prevent breakout."""
    result = text
    for marker in settings.security.boundary_markers:
        result = result.replace(marker, f"[ESCAPED:{marker}]")
    return result


def sanitize_query(query: str) -> tuple[str, bool]:
    """Sanitize user query: mask PII and detect injections."""
    masked = mask_pii(query)
    is_injection = detect_injection(masked)

    if is_injection:
        logger.warning("Injection attempt blocked in query")

    return masked, not is_injection


def sanitize_context(context: str) -> tuple[str, bool]:
    """Sanitize retrieved context: mask PII, escape boundaries, detect injections."""
    masked = mask_pii(context)
    escaped = escape_context_boundaries(masked)
    has_injection = detect_context_injection(masked)

    if has_injection:
        logger.warning("Indirect injection detected in context - chunk filtered")

    return escaped, not has_injection


def validate_output(output: str) -> tuple[str, bool]:
    """Validate LLM output for security issues."""
    is_canary_safe = canary.validate_output(output)

    if not is_canary_safe:
        return settings.responses.canary_blocked, False

    if detect_injection(output):
        logger.warning("Injection pattern detected in LLM output")
        return settings.responses.canary_blocked, False

    sanitized = mask_pii(output)
    return sanitized, True


def get_canary_instruction() -> str:
    """Get canary instruction to embed in system prompt."""
    return canary.get_instruction()


def reset_canary() -> None:
    """Reset canary for new session."""
    canary.generate()
