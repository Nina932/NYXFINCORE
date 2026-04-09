"""
Test Suite: Security — SQL Injection, API Key Exposure, Auth
==============================================================
Verifies that security patches from Phase 0 are effective.
"""
import pytest
import os


class TestNoHardcodedKeys:
    def test_no_gemini_key_in_config(self):
        """config.py must not contain hardcoded API keys."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "app", "config.py")
        with open(config_path) as f:
            content = f.read()
        # The validator check string "AIzaSy" is allowed (it's detecting, not using)
        lines_with_key = [
            line for line in content.split("\n")
            if "AIzaSy" in line and "startswith" not in line
        ]
        assert len(lines_with_key) == 0, f"Hardcoded API key found: {lines_with_key}"

    def test_no_gemini_key_in_local_llm(self):
        """local_llm.py must not contain hardcoded API keys."""
        llm_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "local_llm.py")
        with open(llm_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines_with_key = [
            line.strip() for line in content.split("\n")
            if "AIzaSy" in line
        ]
        assert len(lines_with_key) == 0, f"Hardcoded key in local_llm.py: {lines_with_key}"

    def test_no_default_jwt_secret(self):
        """config.py must not use dev-* JWT secret as default."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "app", "config.py")
        with open(config_path) as f:
            content = f.read()
        # JWT_SECRET default should be empty, not "dev-jwt-secret-..."
        assert 'JWT_SECRET: str = "dev-' not in content


class TestSQLInjectionPrevention:
    def test_warehouse_has_execute_safe(self):
        """warehouse.py must have execute_safe method."""
        wh_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "warehouse.py")
        with open(wh_path) as f:
            content = f.read()
        assert "def execute_safe" in content

    def test_warehouse_has_validate_table_name(self):
        """warehouse.py must have validate_table_name method."""
        wh_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "warehouse.py")
        with open(wh_path) as f:
            content = f.read()
        assert "def validate_table_name" in content

    def test_ontology_uses_parameterized_queries(self):
        """ontology.py must not use f-string SQL for user-controlled data."""
        ont_path = os.path.join(os.path.dirname(__file__), "..", "app", "routers", "ontology.py")
        with open(ont_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        # The old pattern: f"SELECT * FROM \"{obj.backing_table}\" WHERE account_code = '{obj.backing_key}'"
        assert "WHERE account_code = '" not in content, "Raw SQL injection still present"


class TestAuthMiddleware:
    def test_middleware_exists(self):
        from app.middleware.auth_middleware import AuthMiddleware
        assert AuthMiddleware is not None

    def test_whitelist_includes_health(self):
        from app.middleware.auth_middleware import AUTH_WHITELIST_PREFIXES
        assert "/health" in AUTH_WHITELIST_PREFIXES
