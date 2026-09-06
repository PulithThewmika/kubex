from __future__ import annotations

from unittest.mock import patch

import pytest

from cluster_agent import config


def test_validate_rejects_http_endpoint_by_default() -> None:
    with (
        patch.object(config, "CLUSTER_TOKEN", "kbx_test"),
        patch.object(config, "DEPLOYLENS_ENDPOINT", "http://ingest.example.com"),
        patch.object(config, "ALLOW_INSECURE_ENDPOINT", False),
    ):
        with pytest.raises(RuntimeError, match="https"):
            config.validate()


def test_validate_allows_http_endpoint_with_escape_hatch() -> None:
    with (
        patch.object(config, "CLUSTER_TOKEN", "kbx_test"),
        patch.object(config, "DEPLOYLENS_ENDPOINT", "http://host.docker.internal:8000"),
        patch.object(config, "ALLOW_INSECURE_ENDPOINT", True),
    ):
        config.validate()  # must not raise


def test_validate_accepts_https_endpoint() -> None:
    with (
        patch.object(config, "CLUSTER_TOKEN", "kbx_test"),
        patch.object(config, "DEPLOYLENS_ENDPOINT", "https://ingest.example.com"),
        patch.object(config, "ALLOW_INSECURE_ENDPOINT", False),
    ):
        config.validate()  # must not raise
