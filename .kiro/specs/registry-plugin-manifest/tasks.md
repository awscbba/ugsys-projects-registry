# Implementation Plan: registry-plugin-manifest

## Overview

Add a static `GET /plugin-manifest.json` endpoint to `ugsys-projects-registry` (presentation layer
only, no domain/infra changes) and update `seed_services.json` in `ugsys-admin-panel` to set
`min_role: "admin"` for `projects-registry`.

## Tasks

- [x] 1. Create `src/presentation/api/v1/plugin_manifest.py`
  - Define `router = APIRouter(tags=["Plugin Manifest"])`
  - Implement `async def get_plugin_manifest() -> dict[str, object]` decorated with `@router.get("/plugin-manifest.json")`
  - Return the hardcoded manifest dict exactly as specified in the design (name, version, entryPoint, healthEndpoint, routes, navigation)
  - No imports from `src.domain`, `src.application`, or `src.infrastructure` — FastAPI and stdlib only
  - _Requirements: 1.1, 1.2, 1.3, 1.7, 1.8, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4_

- [x] 2. Register the router in `src/main.py`
  - Add `from src.presentation.api.v1 import plugin_manifest` to the existing v1 imports block
  - Add `app.include_router(plugin_manifest.router)` inside `create_app()`, immediately after `app.include_router(health.router)` — no prefix
  - _Requirements: 1.7_

- [x] 3. Update `ugsys-admin-panel/config/seed_services.json`
  - Change `"min_role": "moderator"` to `"min_role": "admin"` for the `projects-registry` entry
  - All other fields for that entry remain unchanged
  - _Requirements: 5.1, 5.2_

- [x] 4. Write unit and property-based tests in `tests/unit/presentation/test_plugin_manifest.py`
  - [x] 4.1 Write concrete unit tests
    - Copy `PLUGIN_MANIFEST_SCHEMA` constant from `ugsys-admin-panel/src/application/interfaces/manifest_validator.py` into the test file (avoid cross-service import)
    - Use `httpx.AsyncClient` with `ASGITransport(app=app)` — same pattern as `test_middleware.py` and `test_projects_router.py`; import `app` from `src.main`
    - Test: `GET /plugin-manifest.json` without `Authorization` header → HTTP 200
    - Test: response `Content-Type` is `application/json`
    - Test: response body passes `PLUGIN_MANIFEST_SCHEMA` via `jsonschema.validate`
    - Test: response body contains all required top-level fields: `name`, `version`, `entryPoint`, `routes`, `navigation`
    - Test: `name == "projects-registry"` and `healthEndpoint == "/health"`
    - Test: no `requiredRoles` array in the manifest contains `"moderator"`
    - Test: specific route entries exist for `/projects`, `/subscriptions`, `/form-schemas` (no `/users` — user management is owned by `ugsys-user-profile-service`)
    - Test: specific navigation entries exist with correct `icon`, `group`, and `order` values
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 4.2 Write property-based test — Property 1: Schema conformance
    - **Property 1: Schema conformance** — `st.just(manifest)`, assert `jsonschema.validate(manifest, PLUGIN_MANIFEST_SCHEMA)` raises no exception
    - `@settings(max_examples=100)`
    - **Validates: Requirements 1.4, 6.1**

  - [ ]* 4.3 Write property-based test — Property 2: JSON round-trip
    - **Property 2: JSON round-trip** — `st.just(manifest)`, assert `json.loads(json.dumps(manifest)) == manifest`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 1.3, 6.2**

  - [ ]* 4.4 Write property-based test — Property 3: Path prefix invariant
    - **Property 3: Path prefix invariant** — `st.sampled_from(all_paths)` where `all_paths` is the flattened list of `path` values from `routes` and `navigation`; assert `path.startswith("/")`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 3.5, 4.7, 6.3, 7.7**

  - [ ]* 4.5 Write property-based test — Property 4: Non-empty navigation fields
    - **Property 4: Non-empty navigation fields** — `st.sampled_from(navigation)` where `navigation` is the list from the manifest; assert `len(entry["label"]) > 0`, `len(entry["icon"]) > 0`, `len(entry["path"]) > 0`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 4.5, 4.6, 4.7, 6.4, 7.10**

  - [ ]* 4.6 Write property-based test — Property 5: Valid roles
    - **Property 5: Valid roles** — `st.sampled_from(all_roles)` where `all_roles` is the flattened list of all role strings from `routes[*].requiredRoles` and `navigation[*].requiredRoles`; assert `role in {"super_admin", "admin", "moderator", "auditor", "member", "guest", "system"}`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 3.6, 4.8, 6.5, 7.8**

  - [ ]* 4.7 Write property-based test — Property 6: Admin-only invariant
    - **Property 6: Admin-only invariant** — `st.sampled_from(all_roles)` (same collection as Property 5); assert `role != "moderator"`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 3.8, 4.10, 6.6, 7.6**

- [x] 5. Final checkpoint — Ensure all tests pass
  - Run `uv run pytest tests/unit/presentation/test_plugin_manifest.py -v` and confirm all tests are green
  - Verify `grep -n "from src.domain\|from src.infrastructure" src/presentation/api/v1/plugin_manifest.py` returns empty (arch-guard compliance)
  - Ask the user if any questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Properties 5 and 6 share the same `all_roles` fixture but must remain separate tests for independent failure signals
- The `entryPoint` value (`index-z0tV6sve.js`) must be updated whenever the web frontend is rebuilt
- `hypothesis` is already in `pyproject.toml` as a dev dependency — no new dependencies needed
- `jsonschema` must be available for schema validation in tests; confirm it is in `pyproject.toml` before implementing task 4
