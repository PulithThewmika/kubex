import pytest

from app.db import prepare_database_url


def test_local_url_passes_through_unchanged() -> None:
    url, connect_args = prepare_database_url("postgresql+asyncpg://kubex:kubex@localhost:5432/kubex")
    assert url == "postgresql+asyncpg://kubex:kubex@localhost:5432/kubex"
    assert connect_args == {}


def test_plain_postgresql_url_gets_asyncpg_dialect() -> None:
    url, _ = prepare_database_url("postgresql://kubex:kubex@localhost:5432/kubex")
    assert url.startswith("postgresql+asyncpg://")


def test_supabase_session_pooler_gets_ssl_only() -> None:
    url, connect_args = prepare_database_url(
        "postgresql://postgres.ref:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    assert url.startswith("postgresql+asyncpg://")
    assert "ssl" in connect_args
    assert "statement_cache_size" not in connect_args


def test_supabase_transaction_pooler_is_rejected() -> None:
    with pytest.raises(ValueError, match="transaction-mode pooler"):
        prepare_database_url(
            "postgresql://postgres.ref:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        )


def test_mixed_case_supabase_host_still_detected() -> None:
    _, connect_args = prepare_database_url(
        "postgresql://postgres.ref:pw@AWS-0-US-EAST-1.POOLER.SUPABASE.COM:5432/postgres"
    )
    assert "ssl" in connect_args


def test_trailing_dot_fqdn_still_detected() -> None:
    _, connect_args = prepare_database_url(
        "postgresql://postgres.ref:pw@aws-0-us-east-1.pooler.supabase.com.:5432/postgres"
    )
    assert "ssl" in connect_args


def test_mixed_case_supabase_host_still_rejects_transaction_pooler() -> None:
    with pytest.raises(ValueError, match="transaction-mode pooler"):
        prepare_database_url(
            "postgresql://postgres.ref:pw@AWS-0-US-EAST-1.POOLER.SUPABASE.COM:6543/postgres"
        )


def test_non_port_6543_in_url_does_not_trigger_rejection() -> None:
    # ":6543" appearing somewhere other than the port (e.g. in a path or
    # password) must not be mistaken for the transaction-mode pooler.
    _, connect_args = prepare_database_url(
        "postgresql://postgres.ref:my6543pass@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    assert "ssl" in connect_args
