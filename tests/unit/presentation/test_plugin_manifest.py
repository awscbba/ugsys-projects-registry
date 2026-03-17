"""Unit tests for the plugin manifest endpoint.

Validates: Requirements 1.1-1.8, 2.1-2.6, 3.1-3.8, 4.1-4.10, 5.1-5.2, 6.1-6.6, 7.1-7.10
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from jsonschema import validate

from src.main import app

# ── Schema (copied from ugsys-admin-panel manifest_validator.py — no cross-service import) ──

PLUGIN_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "version", "entryPoint", "routes", "navigation"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "entryPoint": {"type": "string", "format": "uri"},
        "stylesheetUrl": {"type": "string", "format": "uri"},
        "configSchema": {"type": "object"},
        "healthEndpoint": {"type": "string"},
        "requiredPermissions": {"type": "array", "items": {"type": "string"}},
        "routes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "requiredRoles", "label"],
                "properties": {
                    "path": {"type": "string"},
                    "requiredRoles": {"type": "array", "items": {"type": "string"}},
                    "label": {"type": "string"},
                },
            },
        },
        "navigation": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "icon", "path", "requiredRoles"],
                "properties": {
                    "label": {"type": "string"},
                    "icon": {"type": "string"},
                    "path": {"type": "string"},
                    "requiredRoles": {"type": "array", "items": {"type": "string"}},
                    "group": {"type": "string"},
                    "order": {"type": "integer"},
                },
            },
        },
    },
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def manifest_response():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/plugin-manifest.json")


# ── Unit Tests ────────────────────────────────────────────────────────────────


class TestPluginManifestEndpoint:
    """Concrete unit tests for GET /plugin-manifest.json."""

    async def test_returns_200_without_auth(self, manifest_response) -> None:
        """Endpoint is public — no Authorization header needed."""
        assert manifest_response.status_code == 200

    async def test_content_type_is_json(self, manifest_response) -> None:
        assert "application/json" in manifest_response.headers["content-type"]

    async def test_passes_schema_validation(self, manifest_response) -> None:
        body = manifest_response.json()
        validate(instance=body, schema=PLUGIN_MANIFEST_SCHEMA)

    async def test_contains_required_top_level_fields(self, manifest_response) -> None:
        body = manifest_response.json()
        for field in ("name", "version", "entryPoint", "routes", "navigation"):
            assert field in body, f"Missing required field: {field}"

    async def test_name_and_health_endpoint(self, manifest_response) -> None:
        body = manifest_response.json()
        assert body["name"] == "projects-registry"
        assert body["healthEndpoint"] == "/health"

    async def test_no_moderator_in_required_roles(self, manifest_response) -> None:
        body = manifest_response.json()
        all_roles: list[str] = []
        for route in body["routes"]:
            all_roles.extend(route["requiredRoles"])
        for nav in body["navigation"]:
            all_roles.extend(nav["requiredRoles"])
        assert "moderator" not in all_roles

    async def test_route_entries_exist(self, manifest_response) -> None:
        body = manifest_response.json()
        route_paths = [r["path"] for r in body["routes"]]
        assert "/projects" in route_paths
        assert "/subscriptions" in route_paths
        assert "/form-schemas" in route_paths
        assert "/users" not in route_paths  # owned by user-profile-service

    async def test_navigation_entries(self, manifest_response) -> None:
        body = manifest_response.json()
        nav_entries = {n["label"]: n for n in body["navigation"]}

        assert "Projects" in nav_entries
        assert nav_entries["Projects"]["icon"] == "📁"
        assert nav_entries["Projects"]["group"] == "Registry"
        assert nav_entries["Projects"]["order"] == 1

        assert "Subscriptions" in nav_entries
        assert nav_entries["Subscriptions"]["icon"] == "👥"
        assert nav_entries["Subscriptions"]["order"] == 2

        assert "Form Schemas" in nav_entries
        assert nav_entries["Form Schemas"]["icon"] == "📋"
        assert nav_entries["Form Schemas"]["order"] == 3
