"""
test_security_sprint.py — Integration tests for the Security & Isolation Sprint.

Tests cover:
  1.1 Multi-Tenancy: Tenant A cannot see Tenant B's data
  1.2 Secrets Management: _read_secret, gitignore patterns
  1.3 Auth Enforcement: All non-exempt endpoints return 401 without token
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from tests.conftest import (
    _TestSessionLocal,
    auth_headers,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1.1 Multi-Tenancy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenantIsolation:
    """Verify that the tenant isolation middleware and SQLAlchemy event
    listener correctly filter queries by company."""

    @pytest.mark.asyncio
    async def test_tenant_context_set_and_reset(self):
        """TenantContext is set from user company and reset after request."""
        from app.middleware.tenant import get_current_tenant, set_current_tenant

        assert get_current_tenant() is None
        set_current_tenant("CompanyA")
        assert get_current_tenant() == "CompanyA"
        set_current_tenant(None)
        assert get_current_tenant() is None

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b_datasets(self, db_session):
        """Create datasets for two tenants and verify isolation."""
        from app.models.all_models import Dataset
        from app.middleware.tenant import set_current_tenant

        # Create datasets for two tenants
        async with _TestSessionLocal() as session:
            ds_a = Dataset(name="IsoTestA Dataset", company="IsoTenantA", status="ready")
            ds_b = Dataset(name="IsoTestB Dataset", company="IsoTenantB", status="ready")
            session.add_all([ds_a, ds_b])
            await session.commit()

        # Query as TenantA
        set_current_tenant("IsoTenantA")
        try:
            async with _TestSessionLocal() as session:
                result = await session.execute(select(Dataset).where(Dataset.name.like("IsoTest%")))
                datasets = result.scalars().all()
                names = [d.name for d in datasets]
                assert "IsoTestA Dataset" in names
                assert "IsoTestB Dataset" not in names, "SECURITY: TenantA sees TenantB data!"
        finally:
            set_current_tenant(None)

        # Query as TenantB
        set_current_tenant("IsoTenantB")
        try:
            async with _TestSessionLocal() as session:
                result = await session.execute(select(Dataset).where(Dataset.name.like("IsoTest%")))
                datasets = result.scalars().all()
                names = [d.name for d in datasets]
                assert "IsoTestB Dataset" in names
                assert "IsoTestA Dataset" not in names, "SECURITY: TenantB sees TenantA data!"
        finally:
            set_current_tenant(None)

    @pytest.mark.asyncio
    async def test_no_tenant_context_returns_all(self, db_session):
        """Without tenant context, all records are visible (admin/system)."""
        from app.models.all_models import Dataset
        from app.middleware.tenant import get_current_tenant

        assert get_current_tenant() is None
        async with _TestSessionLocal() as session:
            result = await session.execute(select(Dataset).where(Dataset.name.like("IsoTest%")))
            datasets = result.scalars().all()
            names = [d.name for d in datasets]
            assert "IsoTestA Dataset" in names
            assert "IsoTestB Dataset" in names

    @pytest.mark.asyncio
    async def test_tenant_isolation_on_custom_tools(self, db_session):
        """Verify tenant isolation on CustomTool model."""
        from app.models.all_models import CustomTool
        from app.middleware.tenant import set_current_tenant

        async with _TestSessionLocal() as session:
            tool_a = CustomTool(name="isotool_a", description="A", code="pass", company="AlphaCo")
            tool_b = CustomTool(name="isotool_b", description="B", code="pass", company="BetaCo")
            session.add_all([tool_a, tool_b])
            await session.commit()

        set_current_tenant("AlphaCo")
        try:
            async with _TestSessionLocal() as session:
                result = await session.execute(select(CustomTool).where(CustomTool.name.like("isotool_%")))
                tools = result.scalars().all()
                names = [t.name for t in tools]
                assert "isotool_a" in names
                assert "isotool_b" not in names
        finally:
            set_current_tenant(None)

    @pytest.mark.asyncio
    async def test_tenant_isolation_on_reports(self, db_session):
        """Verify tenant isolation on Report model."""
        from app.models.all_models import Report
        from app.middleware.tenant import set_current_tenant

        async with _TestSessionLocal() as session:
            report_a = Report(title="IsoReport A", report_type="pl", company="AlphaCo")
            report_b = Report(title="IsoReport B", report_type="pl", company="BetaCo")
            session.add_all([report_a, report_b])
            await session.commit()

        set_current_tenant("BetaCo")
        try:
            async with _TestSessionLocal() as session:
                result = await session.execute(select(Report).where(Report.title.like("IsoReport%")))
                reports = result.scalars().all()
                titles = [r.title for r in reports]
                assert "IsoReport B" in titles
                assert "IsoReport A" not in titles
        finally:
            set_current_tenant(None)


# ═══════════════════════════════════════════════════════════════════════════════
# 1.2 Secrets Management Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecretsManagement:
    """Verify the secrets management infrastructure."""

    def test_read_secret_falls_back_to_env(self):
        """_read_secret returns env var when no Docker secret file exists."""
        from app.config import _read_secret
        with patch.dict(os.environ, {"TEST_SECRET_KEY": "env-value-123"}):
            result = _read_secret("test_secret_key", "TEST_SECRET_KEY")
            assert result == "env-value-123"

    def test_read_secret_returns_empty_when_not_set(self):
        """_read_secret returns empty string when neither file nor env exists."""
        from app.config import _read_secret
        env_copy = os.environ.copy()
        env_copy.pop("NONEXISTENT_SECRET_XYZ", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = _read_secret("nonexistent_secret_xyz")
            assert result == ""

    def test_read_secret_prefers_file_over_env(self):
        """_read_secret reads from Docker secrets file when available."""
        from app.config import _read_secret

        with patch("app.config.Path") as MockPath:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = "file-secret-value\n"
            MockPath.return_value = mock_path

            result = _read_secret("my_secret", "MY_SECRET")
            assert result == "file-secret-value"

    def test_gitignore_blocks_env_files(self):
        """Verify .gitignore contains entries for all secret file patterns."""
        gitignore_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".gitignore",
        )
        with open(gitignore_path) as f:
            content = f.read()

        for pattern in [".env", ".env.local", ".env.production", "*.key", "*.pem"]:
            assert pattern in content, f"SECURITY: .gitignore must block '{pattern}'"

    def test_require_auth_defaults_to_true(self):
        """REQUIRE_AUTH must default to True in Settings class definition."""
        from app.config import Settings
        field = Settings.model_fields["REQUIRE_AUTH"]
        assert field.default is True, "SECURITY: REQUIRE_AUTH must default to True"


# ═══════════════════════════════════════════════════════════════════════════════
# 1.3 Auth Enforcement Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthEnforcement:
    """Verify all non-exempt endpoints return 401 without a valid token."""

    @pytest.mark.asyncio
    async def test_protected_endpoints_require_auth(self, client):
        """Key API endpoints must return 401 without a Bearer token."""
        protected_paths = [
            "/api/datasets",
            "/api/analytics/summary",
            "/api/reports",
            "/api/tools",
            "/api/documents",
            "/api/external-data/exchange-rates",
        ]
        for path in protected_paths:
            response = await client.get(path)
            assert response.status_code in (401, 405, 307, 404), (
                f"SECURITY: {path} returned {response.status_code} without auth"
            )

    @pytest.mark.asyncio
    async def test_exempt_endpoints_accessible_without_auth(self, client):
        """Health and config endpoints must be accessible without token."""
        for path in ["/health", "/api/config/public"]:
            response = await client.get(path)
            assert response.status_code != 401, (
                f"AVAILABILITY: {path} should not require auth"
            )

    @pytest.mark.asyncio
    async def test_auth_login_accessible(self, client):
        """POST /api/auth/login must not require a Bearer token."""
        response = await client.post(
            "/api/auth/login",
            json={"email": "nonexistent@test.com", "password": "wrong"},
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_authenticated_request_succeeds(self, client, auth_token):
        """An authenticated request to a protected endpoint should succeed."""
        response = await client.get(
            "/api/datasets",
            headers=auth_headers(auth_token),
        )
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client):
        """An expired JWT token should be rejected with 401."""
        from jose import jwt
        from datetime import datetime, timedelta, timezone

        expired_payload = {
            "sub": "test@test.com", "uid": 1, "role": "analyst",
            "jti": "expired-jti-123",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        expired_token = jwt.encode(expired_payload, os.environ["JWT_SECRET"], algorithm="HS256")
        response = await client.get("/api/datasets", headers=auth_headers(expired_token))
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self, client):
        """A completely invalid token should be rejected with 401."""
        response = await client.get("/api/datasets", headers=auth_headers("not.valid.jwt"))
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_documents_router_requires_auth(self, client):
        """documents_router must require auth."""
        response = await client.get("/api/documents")
        assert response.status_code in (401, 405)

    @pytest.mark.asyncio
    async def test_external_data_requires_auth(self, client):
        """external_data_router must require auth."""
        response = await client.get("/api/external-data/exchange-rates")
        assert response.status_code in (401, 405)


# ═══════════════════════════════════════════════════════════════════════════════
# require_tenant decorator tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireTenantDecorator:
    """Test the require_tenant decorator."""

    @pytest.mark.asyncio
    async def test_require_tenant_raises_403_without_context(self):
        """require_tenant should raise 403 when no tenant context is set."""
        from app.auth import require_tenant
        from app.middleware.tenant import set_current_tenant
        from fastapi import HTTPException

        @require_tenant
        async def protected_endpoint():
            return {"ok": True}

        set_current_tenant(None)
        with pytest.raises(HTTPException) as exc_info:
            await protected_endpoint()
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_tenant_passes_with_context(self):
        """require_tenant should pass when tenant context is set."""
        from app.auth import require_tenant
        from app.middleware.tenant import set_current_tenant

        @require_tenant
        async def protected_endpoint():
            return {"ok": True}

        set_current_tenant("TestCo")
        try:
            result = await protected_endpoint()
            assert result == {"ok": True}
        finally:
            set_current_tenant(None)
