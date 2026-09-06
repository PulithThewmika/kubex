"""Tests for GitHub App JWT signing and installation token exchange (E21-T3-S1)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest

from app import github_app_auth


@pytest.fixture(autouse=True)
def _clear_token_cache():
    github_app_auth._token_cache.clear()
    yield
    github_app_auth._token_cache.clear()


def test_generate_app_jwt_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(github_app_auth, "GITHUB_APP_ID", "")
    monkeypatch.setattr(github_app_auth, "GITHUB_APP_PRIVATE_KEY_PATH", "")
    assert github_app_auth._generate_app_jwt() is None


def test_generate_app_jwt_signs_with_app_id_as_issuer(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path = tmp_path / "app.pem"
    key_path.write_bytes(pem)

    monkeypatch.setattr(github_app_auth, "GITHUB_APP_ID", "12345")
    monkeypatch.setattr(github_app_auth, "GITHUB_APP_PRIVATE_KEY_PATH", str(key_path))

    token = github_app_auth._generate_app_jwt()
    assert token is not None

    public_key = key.public_key()
    claims = jwt.decode(token, public_key, algorithms=["RS256"])
    assert claims["iss"] == "12345"
    assert claims["exp"] > claims["iat"]


@pytest.mark.asyncio
async def test_get_installation_token_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(github_app_auth, "GITHUB_APP_ID", "")
    monkeypatch.setattr(github_app_auth, "GITHUB_APP_PRIVATE_KEY_PATH", "")
    assert await github_app_auth.get_installation_token(42) is None


@pytest.mark.asyncio
async def test_get_installation_token_exchanges_and_caches(monkeypatch):
    monkeypatch.setattr(github_app_auth, "_generate_app_jwt", lambda: "fake-app-jwt")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"token": "ghs_fresh", "expires_at": "2099-01-01T00:00:00Z"}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        token = await github_app_auth.get_installation_token(42)

    assert token == "ghs_fresh"
    assert mock_client.post.call_count == 1

    # Second call within the token's lifetime must hit the cache, not GitHub.
    with patch("httpx.AsyncClient") as mock_client_cls:
        token_again = await github_app_auth.get_installation_token(42)
    assert token_again == "ghs_fresh"
    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_get_installation_token_refreshes_near_expiry(monkeypatch):
    monkeypatch.setattr(github_app_auth, "_generate_app_jwt", lambda: "fake-app-jwt")
    github_app_auth._token_cache[42] = ("ghs_stale", time.time() + 10)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"token": "ghs_new", "expires_at": "2099-01-01T00:00:00Z"}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        token = await github_app_auth.get_installation_token(42)

    assert token == "ghs_new"


@pytest.mark.asyncio
async def test_get_installation_token_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr(github_app_auth, "_generate_app_jwt", lambda: "fake-app-jwt")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        token = await github_app_auth.get_installation_token(42)

    assert token is None
