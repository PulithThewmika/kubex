"""Symmetric encryption for third-party integration secrets stored at
rest (E23-T5).

``INTEGRATION_ENC_KEY`` is a urlsafe-base64 Fernet key. It is required
once any integration that persists a long-lived external token is
configured — currently the multi-tenant Slack app's per-org bot tokens
(``slack_workspaces.bot_token_encrypted``). The database only ever holds
ciphertext.
"""

from __future__ import annotations

import logging
import os
import re

from cryptography.fernet import Fernet

INTEGRATION_ENC_KEY = os.environ.get("INTEGRATION_ENC_KEY", "")

_fernet: Fernet | None = None

# xoxb- (bot), xoxp- (user), xapp- (app-level), xoxe- (refresh) Slack tokens.
_SLACK_TOKEN_RE = re.compile(r"xox[bpear]-[A-Za-z0-9-]+")


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not INTEGRATION_ENC_KEY:
            raise RuntimeError(
                "INTEGRATION_ENC_KEY is not set — required to encrypt integration "
                "secrets at rest. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        _fernet = Fernet(INTEGRATION_ENC_KEY.encode())
    return _fernet


def encryption_available() -> bool:
    return bool(INTEGRATION_ENC_KEY)


def require_encryption_key() -> None:
    """Eagerly build the Fernet so a missing/malformed key fails at
    startup, not on the first OAuth callback."""
    _get_fernet()


def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(bytes(ciphertext)).decode()


def redact_slack_tokens(text: str) -> str:
    return _SLACK_TOKEN_RE.sub("xox***", text)


class _SlackTokenRedactionFilter(logging.Filter):
    """Belt-and-suspenders: scrub any Slack token that slips into a log
    record (e.g. an httpx error echoing a request body). The real
    guarantee is never logging tokens in the first place — this is
    defense in depth.

    # ponytail: attached to root handlers so propagated child records
    # pass through it; if a handler is added after startup its records
    # are unfiltered until install_log_redaction() runs again.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and "xox" in record.msg:
            record.msg = redact_slack_tokens(record.msg)
        if record.args:
            record.args = tuple(
                redact_slack_tokens(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def install_log_redaction() -> None:
    """Attach the redaction filter to every root-logger handler. A plain
    logger-level filter would miss records propagated up from child
    loggers, which is most of them."""
    redactor = _SlackTokenRedactionFilter()
    for handler in logging.getLogger().handlers:
        if not any(isinstance(x, _SlackTokenRedactionFilter) for x in handler.filters):
            handler.addFilter(redactor)
