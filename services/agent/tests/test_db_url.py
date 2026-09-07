from agent.config import prepare_database_url


def test_local_url_passes_through_unchanged():
    url, connect_args = prepare_database_url("postgresql+asyncpg://kubex:kubex@localhost:5432/kubex")
    assert url == "postgresql+asyncpg://kubex:kubex@localhost:5432/kubex"
    assert connect_args == {}


def test_plain_postgresql_url_gets_asyncpg_dialect():
    url, _ = prepare_database_url("postgresql://kubex:kubex@localhost:5432/kubex")
    assert url.startswith("postgresql+asyncpg://")


def test_supabase_session_pooler_gets_ssl_only():
    url, connect_args = prepare_database_url(
        "postgresql://postgres.ref:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    assert url.startswith("postgresql+asyncpg://")
    assert "ssl" in connect_args
    assert "statement_cache_size" not in connect_args


def test_supabase_transaction_pooler_disables_statement_cache():
    _, connect_args = prepare_database_url(
        "postgresql://postgres.ref:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )
    assert connect_args["statement_cache_size"] == 0
