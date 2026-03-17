# Requirements Document

## Introduction

The `ugsys-projects-registry` service currently returns 404 on `GET /plugin-manifest.json`, causing the admin panel's BFF seed loader to mark the service as `DEGRADED` and leave the sidebar empty. This feature adds a static `GET /plugin-manifest.json` endpoint to the presentation layer that returns a valid Plugin Manifest document, enabling the admin panel to register the service successfully and render its sidebar navigation entries.

The endpoint is public (no auth required), lives entirely in the presentation layer, and returns a hardcoded JSON document that satisfies the admin panel's JSON Schema contract.

The manifest exposes full project administration functionality — the same scope as the old registry admin panel: create/edit/delete projects, manage subscriptions, manage form schemas. All routes and navigation entries require `admin` or `super_admin` role — `moderator` access is intentionally excluded from the admin panel. User management is out of scope for this manifest; it will be declared by `ugsys-user-profile-service` in its own manifest.

Additionally, `seed_services.json` in `ugsys-admin-panel` must be updated to set `min_role: "admin"` for `projects-registry` (currently `"moderator"`).

## Glossary

- **Plugin_Manifest_Endpoint**: The `GET /plugin-manifest.json` HTTP endpoint exposed by `ugsys-projects-registry` at the service root (no `/api/v1/` prefix).
- **Manifest**: The JSON document returned by the Plugin_Manifest_Endpoint, conforming to the admin panel's Plugin Manifest JSON Schema.
- **BFF**: The Backend-for-Frontend component of `ugsys-admin-panel` that fetches manifests from registered services during seed loading.
- **Seed_Loader**: The startup process in `ugsys-admin-panel` that reads `seed_services.json` and fetches each service's manifest via its `manifest_url`.
- **Navigation_Entry**: A sidebar item contributed by the Manifest, with required fields `label`, `icon`, `path`, and `requiredRoles`.
- **Route_Descriptor**: A route entry contributed by the Manifest, with required fields `path`, `requiredRoles`, and `label`.
- **Platform_Role**: A valid role string from the platform role set: `super_admin`, `admin`, `moderator`, `auditor`, `member`, `guest`, `system`.
- **Admin_Panel_Schema**: The JSON Schema defined in `ugsys-admin-panel/src/application/interfaces/manifest_validator.py` that all manifests must pass.
- **AuthMiddleware**: The `ugsys-auth-client` middleware applied globally in `src/main.py` that validates JWT tokens on protected routes.
- **Icon_String**: A plain string rendered as raw text inside a `<span aria-hidden="true">` element in the admin panel's Sidebar component. No icon library is used — the value is displayed literally (emoji or unicode symbols are appropriate).
- **EntryPoint**: The URL of the JavaScript bundle that the admin shell loads as a micro-frontend module. For projects-registry, this is the Vite-built JS bundle served from `https://registry.apps.cloud.org.bo`. The asset filename includes a content hash that changes on every build; the manifest must reference the current build's filename.
- **Scope_Boundary**: User management (viewing/editing user profiles, preferences, avatars) is owned by `ugsys-user-profile-service` and is out of scope for this manifest. This manifest covers only projects, subscriptions, and form schemas.

## Requirements

### Requirement 1: Plugin Manifest Endpoint

**User Story:** As the admin panel BFF, I want to fetch a plugin manifest from `ugsys-projects-registry`, so that I can register the service, populate the sidebar, and mark it as healthy instead of DEGRADED.

#### Acceptance Criteria

1. THE `Plugin_Manifest_Endpoint` SHALL respond to `GET /plugin-manifest.json` with HTTP status 200.
2. THE `Plugin_Manifest_Endpoint` SHALL return a response with `Content-Type: application/json`.
3. THE `Plugin_Manifest_Endpoint` SHALL return a response body that is valid JSON.
4. THE `Plugin_Manifest_Endpoint` SHALL return a response body that passes the `Admin_Panel_Schema` validator without errors.
5. THE `Plugin_Manifest_Endpoint` SHALL be accessible without an `Authorization` header (no authentication required).
6. WHEN the `AuthMiddleware` processes a request to `/plugin-manifest.json`, THE `AuthMiddleware` SHALL allow the request to proceed without requiring a JWT token.
7. THE `Plugin_Manifest_Endpoint` SHALL be registered in `src/main.py` at the service root, without the `/api/v1/` prefix.
8. THE `Plugin_Manifest_Endpoint` SHALL be implemented in `src/presentation/api/v1/plugin_manifest.py` with no imports from `src.domain` or `src.infrastructure`.

---

### Requirement 2: Manifest Content — Required Fields

**User Story:** As the admin panel BFF, I want the manifest to contain all required fields with correct values, so that the schema validator accepts it and the service is registered successfully.

#### Acceptance Criteria

1. THE `Manifest` SHALL contain a `name` field with the string value `"projects-registry"`.
2. THE `Manifest` SHALL contain a `version` field whose value matches the pattern `^\d+\.\d+\.\d+$` (semver).
3. THE `Manifest` SHALL contain an `entryPoint` field with a valid URI pointing to the Vite-built JS bundle served from `https://registry.apps.cloud.org.bo/assets/`. The exact filename (including content hash) SHALL match the current build artifact in `web/dist/assets/index-*.js`. At the time of writing, the current build artifact is `index-z0tV6sve.js`, making the value `"https://registry.apps.cloud.org.bo/assets/index-z0tV6sve.js"`. This value MUST be updated whenever the web frontend is rebuilt.
4. THE `Manifest` SHALL contain a `healthEndpoint` field with the value `"/health"`.
5. THE `Manifest` SHALL contain a non-empty `routes` array.
6. THE `Manifest` SHALL contain a non-empty `navigation` array.

---

### Requirement 3: Manifest Content — Routes

**User Story:** As the admin panel BFF, I want the manifest to declare the admin routes exposed by projects-registry, so that the admin panel can register them for role-based access control.

#### Acceptance Criteria

1. THE `Manifest` SHALL include a `Route_Descriptor` with `path` `"/projects"`, `label` `"Projects"`, and `requiredRoles` containing `"admin"`.
2. THE `Manifest` SHALL include a `Route_Descriptor` with `path` `"/subscriptions"`, `label` `"Subscriptions"`, and `requiredRoles` containing `"admin"`.
3. THE `Manifest` SHALL include a `Route_Descriptor` with `path` `"/form-schemas"`, `label` `"Form Schemas"`, and `requiredRoles` containing `"admin"`.
4. FOR ALL `Route_Descriptor` entries in the `Manifest`, the `path` field SHALL start with `"/"`.
5. FOR ALL `Route_Descriptor` entries in the `Manifest`, every value in `requiredRoles` SHALL be a valid `Platform_Role` string.
6. FOR ALL `Route_Descriptor` entries in the `Manifest`, the `label` field SHALL be a non-empty string.
7. NO `Route_Descriptor` entry SHALL include `"moderator"` in `requiredRoles` — all admin panel routes require at minimum `"admin"` role.
8. THE `Manifest` SHALL NOT include a `Route_Descriptor` with `path` `"/users"` — user management is owned by `ugsys-user-profile-service`.

---

### Requirement 4: Manifest Content — Navigation

**User Story:** As the admin panel BFF, I want the manifest to declare sidebar navigation entries for projects-registry, so that the admin panel can render them for users with sufficient roles.

#### Acceptance Criteria

1. THE `Manifest` SHALL include a `Navigation_Entry` with `label` `"Projects"`, `icon` `"📁"`, `path` `"/projects"`, `group` `"Registry"`, `order` `1`, and `requiredRoles` containing `"admin"`.
2. THE `Manifest` SHALL include a `Navigation_Entry` with `label` `"Subscriptions"`, `icon` `"👥"`, `path` `"/subscriptions"`, `group` `"Registry"`, `order` `2`, and `requiredRoles` containing `"admin"`.
3. THE `Manifest` SHALL include a `Navigation_Entry` with `label` `"Form Schemas"`, `icon` `"📋"`, `path` `"/form-schemas"`, `group` `"Registry"`, `order` `3`, and `requiredRoles` containing `"admin"`.
4. THE `Manifest` SHALL NOT include a `Navigation_Entry` with `path` `"/users"` — user management navigation is owned by `ugsys-user-profile-service`.
5. FOR ALL `Navigation_Entry` items in the `Manifest`, the `label` field SHALL be a non-empty string.
6. FOR ALL `Navigation_Entry` items in the `Manifest`, the `icon` field SHALL be a non-empty `Icon_String` (emoji or unicode symbol rendered as raw text by the Sidebar component).
7. FOR ALL `Navigation_Entry` items in the `Manifest`, the `path` field SHALL be a non-empty string starting with `"/"`.
8. FOR ALL `Navigation_Entry` items in the `Manifest`, every value in `requiredRoles` SHALL be a valid `Platform_Role` string.
9. FOR ALL `Navigation_Entry` items in the `Manifest`, the `group` field, when present, SHALL be a non-empty string.
10. NO `Navigation_Entry` SHALL include `"moderator"` in `requiredRoles` — all sidebar entries require at minimum `"admin"` role.

---

### Requirement 5: Seed Services Update

**User Story:** As the admin panel operator, I want `projects-registry` to require `admin` role in `seed_services.json`, so that the service's minimum access level is consistent with the manifest's `requiredRoles`.

#### Acceptance Criteria

1. THE `min_role` field for `projects-registry` in `ugsys-admin-panel/config/seed_services.json` SHALL be changed from `"moderator"` to `"admin"`.
2. ALL other fields for the `projects-registry` entry in `seed_services.json` SHALL remain unchanged.

---

### Requirement 6: Manifest Correctness Properties (PBT)

**User Story:** As a developer, I want property-based tests to verify the manifest's structural invariants, so that any future change to the manifest content is caught before it breaks the admin panel integration.

#### Acceptance Criteria

1. FOR ALL invocations of `GET /plugin-manifest.json`, the response body SHALL pass the `Admin_Panel_Schema` validator (schema-conformance invariant).
2. FOR ALL invocations of `GET /plugin-manifest.json`, serializing the response body to JSON and parsing it back SHALL produce a document equal to the original (JSON round-trip property).
3. FOR ALL `Route_Descriptor` entries in the `Manifest`, the `path` value SHALL satisfy `path.startswith("/")` (path prefix invariant).
4. FOR ALL `Navigation_Entry` items in the `Manifest`, the `label`, `icon`, and `path` fields SHALL each be non-empty strings (non-empty fields invariant).
5. FOR ALL role strings in any `requiredRoles` array within the `Manifest`, the value SHALL be a member of the set `{"super_admin", "admin", "moderator", "auditor", "member", "guest", "system"}` (valid role invariant).
6. NO role string in any `requiredRoles` array within the `Manifest` SHALL equal `"moderator"` — all entries require at minimum `"admin"` (admin-only invariant).

---

### Requirement 7: Unit Tests

**User Story:** As a developer, I want unit tests for the plugin manifest endpoint in `tests/unit/presentation/`, so that regressions are caught in CI before deployment.

#### Acceptance Criteria

1. THE test suite SHALL include a test that verifies `GET /plugin-manifest.json` returns HTTP 200 without an `Authorization` header.
2. THE test suite SHALL include a test that verifies the response `Content-Type` is `application/json`.
3. THE test suite SHALL include a test that verifies the response body passes the `Admin_Panel_Schema` validator.
4. THE test suite SHALL include a test that verifies the response body contains all required fields: `name`, `version`, `entryPoint`, `routes`, and `navigation`.
5. THE test suite SHALL include a test that verifies `name` equals `"projects-registry"` and `healthEndpoint` equals `"/health"`.
6. THE test suite SHALL include a test that verifies no `requiredRoles` array in the manifest contains `"moderator"`.
7. THE test suite SHALL include a property-based test that verifies all `path` values in `routes` start with `"/"`.
8. THE test suite SHALL include a property-based test that verifies all `requiredRoles` values across `routes` and `navigation` are valid `Platform_Role` strings.
9. THE test suite SHALL include a property-based test that verifies the JSON round-trip property: `json.loads(json.dumps(manifest)) == manifest`.
10. THE test suite SHALL include a property-based test that verifies all `Navigation_Entry` fields `label`, `icon`, and `path` are non-empty strings.
