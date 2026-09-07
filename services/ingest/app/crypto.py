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

# Slack token shapes: xoxb-/xoxp-/xoxa-/xoxr-/xoxe- (legacy + granular),
# xapp-/xwfp- (app-level / workflow), and xoxe.xoxb-/xoxe.xoxp- (rotating).
_SLACK_TOKEN_RE = re.compile(
    r"(?:xoxe\.(?:xoxb|xoxp)-[A-Za-z0-9-]+|x(?:ox[bparoe]|app|wfp)-[A-Za-z0-9-]+)"
)


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

    # ponytail: only redacts %-style positional args (a tuple). Dict-style
    # args (logger.info("%(x)s", {...})) and pre-rendered messages via
    # extra= are left alone; nothing in this codebase logs a token that way.
    """

    @staticmethod
    def _looks_tokenish(s: str) -> bool:
        return "xox" in s or "xapp-" in s or "xwfp-" in s

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and self._looks_tokenish(record.msg):
            record.msg = redact_slack_tokens(record.msg)
        # Only positional (tuple) args are rewritten; a mapping (%(name)s
        # style) is left structurally intact — nothing here logs a token
        # that way, and converting it would break record.getMessage().
        if isinstance(record.args, tuple) and any(
            isinstance(a, str) and self._looks_tokenish(a) for a in record.args
        ):
            record.args = tuple(
                redact_slack_tokens(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def install_log_redaction() -> None:
    """Attach the redaction filter everywhere records actually get emitted:
    every configured handler (root + named loggers) and ``lastResort`` —
    the handler used when nothing else is configured, which is the case
    under a bare ``uvicorn app.main:app``."""
    redactor = _SlackTokenRedactionFilter()

    def _attach(target: logging.Handler | None) -> None:
        if target is not None and not any(
            isinstance(f, _SlackTokenRedactionFilter) for f in target.filters
        ):
            target.addFilter(redactor)

    _attach(logging.lastResort)
    loggers = [logging.getLogger()] + [
        logging.getLogger(name) for name in list(logging.root.manager.loggerDict)
    ]
    for lg in loggers:
        for handler in getattr(lg, "handlers", []):
            _attach(handler)
