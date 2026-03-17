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
        "entryPoint": "https://registry.apps.cloud.org.bo/assets/index-z0tV6sve.js",
        "healthEndpoint": "/health",
        "routes": [
            {
                "path": "/projects",
                "label": "Projects",
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "path": "/subscriptions",
                "label": "Subscriptions",
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "path": "/form-schemas",
                "label": "Form Schemas",
                "requiredRoles": ["admin", "super_admin"],
            },
        ],
        "navigation": [
            {
                "label": "Projects",
                "icon": "📁",
                "path": "/projects",
                "group": "Registry",
                "order": 1,
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "label": "Subscriptions",
                "icon": "👥",
                "path": "/subscriptions",
                "group": "Registry",
                "order": 2,
                "requiredRoles": ["admin", "super_admin"],
            },
            {
                "label": "Form Schemas",
                "icon": "📋",
                "path": "/form-schemas",
                "group": "Registry",
                "order": 3,
                "requiredRoles": ["admin", "super_admin"],
            },
        ],
    }
