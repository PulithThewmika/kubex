"""Tests for the correlation engine — pure functions and async DB logic."""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.sql import Select

from app.correlation.engine import (
    apply_terminal_guarded_status,
    extract_image_tag,
    extract_image_tag_from_images,
    parse_iso_timestamp,
    resolve_service,
    resolve_org_id,
    get_default_org_id,
    find_matching_deployment,
)


class _FakeNestedTransaction:
    """Minimal async-context-manager stand-in for SQLAlchemy's
    AsyncSessionTransaction — begin_nested() itself is a plain sync call
    that returns this, not a coroutine (see conftest.py's mock_session
    fixture for the same pattern)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _session_with_begin_nested() -> AsyncMock:
    """A session AsyncMock whose begin_nested() behaves like the real
    (sync-returning-async-context-manager) method — needed by any test
    that exercises resolve_service's auto-registration path, which wraps
    the insert in a savepoint to recover from a lost registration race."""
    session = AsyncMock()
    session.begin_nested = MagicMock(return_value=_FakeNestedTransaction())
    return session


# ── extract_image_tag ──────────────────────────────────────────────

class TestExtractImageTag:
    def test_full_sha_returns_first_7(self):
        assert extract_image_tag("abc1234567890") == "abc1234"

    def test_exactly_7_chars(self):
        assert extract_image_tag("abc1234") == "abc1234"

    def test_short_sha_returned_as_is(self):
        assert extract_image_tag("abc") == "abc"

    def test_none_returns_none(self):
        assert extract_image_tag(None) is None

    def test_empty_string_returned_as_is(self):
        assert extract_image_tag("") == ""


# ── extract_image_tag_from_images ──────────────────────────────────

class TestExtractImageTagFromImages:
    def test_comma_separated_same_tag(self):
        s = "ghcr.io/o/app-frontend:abc1234,ghcr.io/o/app-orders:abc1234"
        assert extract_image_tag_from_images(s) == "abc1234"

    def test_go_slice_space_separated(self):
        s = "[ghcr.io/o/app-frontend:abc1234 ghcr.io/o/app-orders:abc1234]"
        assert extract_image_tag_from_images(s) == "abc1234"

    def test_majority_wins_during_rolling_update(self):
        # payments still rolling: old tag lingers alongside the new one,
        # plus a sidecar image on its own tag — the bumped tag is on 3.
        s = ("[curlimages/curl:8.10.1 ghcr.io/o/app-frontend:6a80f84 "
             "ghcr.io/o/app-orders:6a80f84 ghcr.io/o/app-payments:6a80f84 "
             "ghcr.io/o/app-payments:e2edeg1]")
        assert extract_image_tag_from_images(s) == "6a80f84"

    def test_registry_port_not_mistaken_for_tag(self):
        assert extract_image_tag_from_images("[localhost:5000/app-x:v9]") == "v9"

    def test_latest_ignored(self):
        assert extract_image_tag_from_images("ghcr.io/o/app-x:latest") is None

    def test_empty_and_none(self):
        assert extract_image_tag_from_images(None) is None
        assert extract_image_tag_from_images("  ") is None
        assert extract_image_tag_from_images("[]") is None


# ── parse_iso_timestamp ────────────────────────────────────────────

class TestParseIsoTimestamp:
    def test_z_suffix(self):
        result = parse_iso_timestamp("2026-08-01T12:00:00Z")
        assert result == datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_offset_suffix(self):
        result = parse_iso_timestamp("2026-08-01T12:00:00+00:00")
        assert result == datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_none_returns_none(self):
        assert parse_iso_timestamp(None) is None

    def test_empty_returns_none(self):
        assert parse_iso_timestamp("") is None


# ── resolve_service ────────────────────────────────────────────────

class TestResolveService:
    @pytest.mark.asyncio
    async def test_finds_by_repo(self):
        org_id = uuid.uuid4()
        mock_service = MagicMock(id=42, org_id=org_id)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_service]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        service_id, resolved_org_id = await resolve_service(session, org_id=org_id, repo="PulithThewmika/kubex")
        assert service_id == 42
        assert resolved_org_id == org_id

    @pytest.mark.asyncio
    async def test_finds_by_argocd_app(self):
        org_id = uuid.uuid4()
        mock_service = MagicMock(id=31, org_id=org_id)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_service]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        service_id, resolved_org_id = await resolve_service(session, org_id=org_id, argocd_app="sample-app")
        assert service_id == 31
        assert resolved_org_id == org_id

    @pytest.mark.asyncio
    async def test_finds_oldest_by_repo_when_duplicates_exist(self) -> None:
        """Regression test: a repo-migration seed update (V011) racing an
        auto-registration can leave two rows sharing the same repo within
        one org (V018's (org_id, repo) uniqueness constrains across orgs,
        not the race window within one). resolve_service must not crash on
        MultipleResultsFound — it should prefer the oldest row, and the
        underlying query itself (not just the mock's return order) must be
        both org-scoped and ordered by id."""
        shared_org_id = uuid.uuid4()
        older = MagicMock(id=31, org_id=shared_org_id)
        newer = MagicMock(id=99, org_id=shared_org_id)
        captured_stmt = None

        async def mock_execute(stmt: object) -> MagicMock:
            nonlocal captured_stmt
            captured_stmt = stmt
            result = MagicMock()
            result.scalars.return_value.all.return_value = [older, newer]
            return result

        session = AsyncMock()
        session.execute = mock_execute

        service_id, org_id = await resolve_service(
            session, org_id=shared_org_id, repo="PulithThewmika/deploylens-sample-app"
        )
        assert service_id == 31
        assert org_id == shared_org_id

        where_clause = str(captured_stmt.whereclause.compile(compile_kwargs={"literal_binds": True}))
        assert shared_org_id.hex in where_clause.replace("-", "")
        assert "PulithThewmika/deploylens-sample-app" in where_clause
        assert any(
            "services.id" in str(col) for col in captured_stmt._order_by_clauses
        ), "expected the query itself to order by Service.id, not rely on mock return order"

    @pytest.mark.asyncio
    async def test_auto_registers_unknown_service_with_given_org_id(self) -> None:
        given_org_id = uuid.uuid4()

        async def mock_execute(_stmt: object) -> MagicMock:
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = None
            return result

        session = _session_with_begin_nested()
        session.execute = mock_execute
        session.flush = AsyncMock()
        session.add = MagicMock()

        service_id, org_id = await resolve_service(session, org_id=given_org_id, repo="org/new-service")
        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert org_id == given_org_id
        added_service = session.add.call_args_list[0][0][0]
        assert added_service.org_id == given_org_id

    @pytest.mark.asyncio
    async def test_recovers_from_lost_registration_race(self) -> None:
        """/code-review high + CodeRabbit on PR #796: two concurrent
        first-time requests for the same (org_id, name) can both pass the
        initial lookup and race to insert — the loser must reuse the
        winner's row (uq_services_org_name violation) instead of 500ing."""
        from sqlalchemy.exc import IntegrityError

        given_org_id = uuid.uuid4()
        winner = MagicMock(id=99, org_id=given_org_id)

        call_count = 0

        async def mock_execute(_stmt: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            # First SELECT (pre-insert lookup): nothing yet. Second SELECT
            # (post-IntegrityError recovery): the winner's row.
            result.scalar_one_or_none.return_value = None
            result.scalar_one.return_value = winner
            return result

        session = _session_with_begin_nested()
        session.execute = mock_execute
        session.flush = AsyncMock(side_effect=IntegrityError("insert", {}, Exception("unique violation")))
        session.add = MagicMock()
        session.expunge = MagicMock()

        service_id, org_id = await resolve_service(session, org_id=given_org_id, name="orders")

        assert service_id == 99
        assert org_id == given_org_id
        # CodeRabbit (2nd round, PR #796): rolling back to the savepoint on
        # this IntegrityError already evicts `service` to the transient
        # state — expunging it again would raise InvalidRequestError. This
        # mock can't reproduce that real SQLAlchemy behavior (a MagicMock
        # tolerates the call fine either way), so the assertion is the
        # regression guard: expunge must never be called here at all.
        session.expunge.assert_not_called()

    @pytest.mark.asyncio
    async def test_links_repo_to_existing_service_by_name(self):
        existing = MagicMock(id=10, name="myapp", repo=None, argocd_app="myapp", org_id=uuid.uuid4())
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.all.return_value = []
            else:
                result.scalar_one_or_none.return_value = existing
            return result

        session = AsyncMock()
        session.execute = mock_execute
        session.flush = AsyncMock()

        service_id, org_id = await resolve_service(session, org_id=existing.org_id, repo="org/myapp")
        assert service_id == 10
        assert org_id == existing.org_id
        assert existing.repo == "org/myapp"

    @pytest.mark.asyncio
    async def test_name_fallback_does_not_cross_org(self) -> None:
        """Regression test for #792: two orgs deriving the same `name` from
        different repos must not collide — the name-fallback lookup has to
        be scoped to the caller's org_id, not global, or it would match
        (and mis-attribute to) another org's row."""
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()
        captured_stmts = []

        async def mock_execute(stmt: object) -> MagicMock:
            captured_stmts.append(stmt)
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = None
            return result

        session = _session_with_begin_nested()
        session.execute = mock_execute
        session.flush = AsyncMock()
        session.add = MagicMock()

        def compiled_where(stmt: Select) -> str:
            return str(stmt.whereclause.compile(compile_kwargs={"literal_binds": True}))

        # org A registers "payments" via its own repo.
        await resolve_service(session, org_id=org_a, repo="org-a/payments")
        stmts_a = [compiled_where(s) for s in captured_stmts]
        captured_stmts.clear()

        # org B derives the same `name` from a different repo — the repo
        # lookup won't match (different repo string), so it falls through
        # to the name lookup, which must be scoped to org_b, not org_a.
        await resolve_service(session, org_id=org_b, repo="org-b/payments")
        stmts_b = [compiled_where(s) for s in captured_stmts]

        name_lookup_a = [s for s in stmts_a if "repo" not in s.lower()]
        name_lookup_b = [s for s in stmts_b if "repo" not in s.lower()]
        assert name_lookup_a and name_lookup_b, "expected a name-only lookup query on each call"

        for stmt in name_lookup_a:
            assert org_a.hex in stmt.replace("-", "") and org_b.hex not in stmt.replace("-", "")

        for stmt in name_lookup_b:
            assert org_b.hex in stmt.replace("-", "") and org_a.hex not in stmt.replace("-", "")

    @pytest.mark.asyncio
    async def test_repo_and_argocd_app_mismatch_creates_separate_rows(self):
        """Regression test for bug #112: when repo last segment != argocd_app,
        two separate resolve_service calls create two rows."""
        default_org_id = uuid.uuid4()

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = None
            return result

        session = _session_with_begin_nested()
        session.execute = mock_execute
        session.flush = AsyncMock()
        session.add = MagicMock()

        await resolve_service(session, org_id=default_org_id, repo="PulithThewmika/kubex")
        added_service_1 = session.add.call_args_list[0][0][0]
        assert added_service_1.name == "kubex"

        session.add.reset_mock()
        await resolve_service(session, org_id=default_org_id, argocd_app="sample-app")
        added_service_2 = session.add.call_args_list[0][0][0]
        assert added_service_2.name == "sample-app"

        assert added_service_1.name != added_service_2.name


class TestResolveOrgId:
    @pytest.mark.asyncio
    async def test_returns_existing_services_org(self):
        org_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [org_id]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        resolved = await resolve_org_id(session, repo="org/known-service")
        assert resolved == org_id

    @pytest.mark.asyncio
    async def test_falls_back_to_default_org_when_unmatched(self):
        default_org_id = uuid.uuid4()

        async def mock_execute(stmt):
            result = MagicMock()
            if "organizations" in str(stmt):
                result.scalar_one_or_none.return_value = default_org_id
            else:
                result.scalars.return_value.all.return_value = []
            return result

        session = AsyncMock()
        session.execute = mock_execute

        resolved = await resolve_org_id(session, repo="org/unknown-service")
        assert resolved == default_org_id

    @pytest.mark.asyncio
    async def test_raises_when_repo_ambiguous_across_orgs(self):
        """Regression test for #792/#793 review: a repo registered under
        more than one org (schema-legal since V018 scoped uniqueness
        per-org) must fail loudly, not silently pick one org."""
        org_a, org_b = uuid.uuid4(), uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [org_a, org_b]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(RuntimeError):
            await resolve_org_id(session, repo="shared/repo")

    @pytest.mark.asyncio
    async def test_get_default_org_id_raises_when_no_orgs_exist(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(RuntimeError):
            await get_default_org_id(session)


# ── find_matching_deployment ───────────────────────────────────────

class TestFindMatchingDeployment:
    @pytest.mark.asyncio
    async def test_matches_by_commit_sha(self):
        mock_deployment = MagicMock(id=100)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_deployment

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        deployment, method = await find_matching_deployment(
            session, service_id=1, commit_sha="abc1234"
        )
        assert deployment == mock_deployment
        assert method == "commit_sha"

    @pytest.mark.asyncio
    async def test_falls_back_to_image_tag(self):
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = None
            else:
                result.scalar_one_or_none.return_value = MagicMock(id=200)
            return result

        session = AsyncMock()
        session.execute = mock_execute

        deployment, method = await find_matching_deployment(
            session, service_id=1, commit_sha="nonexistent", image_tag="abc1234"
        )
        assert deployment is not None
        assert method == "image_tag"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_match(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        deployment, method = await find_matching_deployment(
            session, service_id=1, commit_sha="abc", image_tag="def"
        )
        assert deployment is None
        assert method == "none"

    @pytest.mark.asyncio
    async def test_skips_image_tag_when_not_provided(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        deployment, method = await find_matching_deployment(
            session, service_id=1, commit_sha="abc"
        )
        assert deployment is None
        assert method == "none"
        session.execute.assert_called_once()


class TestApplyTerminalGuardedStatus:
    """/code-review high + CodeRabbit on PR #796: this must be a
    WHERE-guarded UPDATE, not an in-memory ORM mutation, or a stale
    delivery can overwrite a status a concurrent transaction already
    committed to terminal between the caller's correlating SELECT and
    this call."""

    @pytest.mark.asyncio
    async def test_applies_when_not_terminal(self):
        captured = []

        async def mock_execute(stmt):
            captured.append(stmt)
            result = MagicMock()
            result.scalar_one_or_none.return_value = "deployed"
            return result

        session = AsyncMock()
        session.execute = mock_execute

        applied, persisted = await apply_terminal_guarded_status(session, deployment_id=100, new_status="deployed")

        assert applied is True
        assert persisted == "deployed"
        assert len(captured) == 1
        stmt = captured[0]
        assert stmt.is_update
        where_sql = str(stmt.whereclause.compile(compile_kwargs={"literal_binds": True}))
        assert "deployments.id = 100" in where_sql
        assert "NOT IN" in where_sql.upper() or "NOT (deployments.status IN" in where_sql

    @pytest.mark.asyncio
    async def test_skips_and_reports_real_status_when_already_terminal(self):
        """The UPDATE's WHERE excludes the row (simulating a concurrent
        transaction having already committed it to terminal), so this
        must fall back to a fresh SELECT rather than trust a stale
        in-memory value."""
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = None  # UPDATE matched no row
            else:
                result.scalar_one.return_value = "sync_failed"  # fallback SELECT
            return result

        session = AsyncMock()
        session.execute = mock_execute

        applied, persisted = await apply_terminal_guarded_status(session, deployment_id=100, new_status="deployed")

        assert applied is False
        assert persisted == "sync_failed"
        assert call_count == 2
