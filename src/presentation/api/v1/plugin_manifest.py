"""Plugin manifest endpoint — static JSON, no auth required.

Returns the plugin manifest for the admin panel's micro-frontend loader.
Presentation layer only — no domain, application, or infrastructure imports.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Plugin Manifest"])


@router.get("/plugin-manifest.json")
async def get_plugin_manifest() -> dict[str, object]:
    """Return the static plugin manifest for admin panel integration."""
    return {
        "name": "projects-registry",
        "version": "0.1.0",
        "entryPoint": "https://registry.apps.cloud.org.bo/plugins/projects-plugin.js",
        "healthEndpoint": "/health",
        "routes": [
            {
                "path": "/app/projects-registry/projects",
                "label": "Projects",
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "path": "/app/projects-registry/subscriptions",
                "label": "Subscriptions",
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "path": "/app/projects-registry/form-schemas",
                "label": "Form Schemas",
                "requiredRoles": ["admin", "super_admin"],
            },
        ],
        "navigation": [
            {
                "label": "Projects",
                "icon": "📁",
                "path": "/app/projects-registry/projects",
                "group": "Registry",
                "order": 1,
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "label": "Subscriptions",
                "icon": "👥",
                "path": "/app/projects-registry/subscriptions",
                "group": "Registry",
                "order": 2,
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "label": "Form Schemas",
                "icon": "📋",
                "path": "/app/projects-registry/form-schemas",
                "group": "Registry",
                "order": 3,
                "requiredRoles": ["admin", "super_admin"],
            },
        ],
    }
