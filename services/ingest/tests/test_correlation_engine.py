"""Tests for the correlation engine — pure functions and async DB logic."""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.correlation.engine import (
    extract_image_tag,
    parse_iso_timestamp,
    resolve_service,
    resolve_org_id,
    get_default_org_id,
    find_matching_deployment,
)


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

        service_id, resolved_org_id = await resolve_service(session, repo="PulithThewmika/kubex")
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

        service_id, resolved_org_id = await resolve_service(session, argocd_app="sample-app")
        assert service_id == 31
        assert resolved_org_id == org_id

    @pytest.mark.asyncio
    async def test_finds_oldest_by_repo_when_duplicates_exist(self):
        """Regression test: a repo-migration seed update (V011) racing an
        auto-registration can leave two rows sharing the same repo. Since
        services.repo has no unique constraint, resolve_service must not
        crash on MultipleResultsFound — it should prefer the oldest row."""
        older = MagicMock(id=31, org_id=uuid.uuid4())
        newer = MagicMock(id=99, org_id=uuid.uuid4())
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [older, newer]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        service_id, org_id = await resolve_service(session, repo="PulithThewmika/deploylens-sample-app")
        assert service_id == 31
        assert org_id == older.org_id

    @pytest.mark.asyncio
    async def test_auto_registers_unknown_service_with_default_org(self):
        default_org_id = uuid.uuid4()

        async def mock_execute(stmt):
            result = MagicMock()
            if "organizations" in str(stmt):
                result.scalar_one_or_none.return_value = default_org_id
            else:
                result.scalars.return_value.all.return_value = []
                result.scalar_one_or_none.return_value = None
            return result

        session = AsyncMock()
        session.execute = mock_execute
        session.flush = AsyncMock()
        session.add = MagicMock()

        service_id, org_id = await resolve_service(session, repo="org/new-service")
        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert org_id == default_org_id
        added_service = session.add.call_args_list[0][0][0]
        assert added_service.org_id == default_org_id

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

        service_id, org_id = await resolve_service(session, repo="org/myapp")
        assert service_id == 10
        assert org_id == existing.org_id
        assert existing.repo == "org/myapp"

    @pytest.mark.asyncio
    async def test_repo_and_argocd_app_mismatch_creates_separate_rows(self):
        """Regression test for bug #112: when repo last segment != argocd_app,
        two separate resolve_service calls create two rows."""
        default_org_id = uuid.uuid4()

        async def mock_execute(stmt):
            result = MagicMock()
            if "organizations" in str(stmt):
                result.scalar_one_or_none.return_value = default_org_id
            else:
                result.scalars.return_value.all.return_value = []
                result.scalar_one_or_none.return_value = None
            return result

        session = AsyncMock()
        session.execute = mock_execute
        session.flush = AsyncMock()
        session.add = MagicMock()

        await resolve_service(session, repo="PulithThewmika/kubex")
        added_service_1 = session.add.call_args_list[0][0][0]
        assert added_service_1.name == "kubex"

        session.add.reset_mock()
        await resolve_service(session, argocd_app="sample-app")
        added_service_2 = session.add.call_args_list[0][0][0]
        assert added_service_2.name == "sample-app"

        assert added_service_1.name != added_service_2.name


class TestResolveOrgId:
    @pytest.mark.asyncio
    async def test_returns_existing_services_org(self):
        org_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = org_id

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        resolved = await resolve_org_id(session, repo="org/known-service")
        assert resolved == org_id

    @pytest.mark.asyncio
    async def test_falls_back_to_default_org_when_unmatched(self):
        default_org_id = uuid.uuid4()

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = (
                default_org_id if "organizations" in str(stmt) else None
            )
            return result

        session = AsyncMock()
        session.execute = mock_execute

        resolved = await resolve_org_id(session, repo="org/unknown-service")
        assert resolved == default_org_id

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
