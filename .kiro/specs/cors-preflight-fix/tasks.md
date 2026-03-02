# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Fault Condition** - OPTIONS Preflight Blocked by CORP Header
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to the concrete failing case — OPTIONS requests from an allowed origin with `Access-Control-Request-Method` present
  - Add to `tests/unit/presentation/test_middleware.py` under a new `TestSecurityHeadersMiddlewareCORSFix` class
  - Use `hypothesis` with `@given(st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"]))` for the method dimension and a fixed OPTIONS case for the bug condition
  - Test 1 — Fault Condition property: instantiate `SecurityHeadersMiddleware` wrapping a mock `call_next` that returns a plain 200 response; fire an OPTIONS request with `Origin: https://registry.apps.cloud.org.bo` and `Access-Control-Request-Method: GET`; assert `Cross-Origin-Resource-Policy` is NOT in the response headers (this assertion will FAIL on unfixed code because CORP is present — confirming the bug)
  - Test 2 — Comma-separated `ALLOWED_ORIGINS` parse failure: instantiate `Settings` with `ALLOWED_ORIGINS="https://registry.apps.cloud.org.bo,https://admin.cloud.org.bo"`; assert the parsed list contains exactly two separate origins (will FAIL on unfixed code — pydantic-settings v2 does not split comma-separated strings)
  - Run tests on UNFIXED code (current `main` or the state before the branch changes)
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bug exists)
  - Document counterexamples found: e.g. "OPTIONS response contains `cross-origin-resource-policy: same-origin`" and "ALLOWED_ORIGINS parsed as single-element list"
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-OPTIONS Requests Retain All Security Headers
  - **IMPORTANT**: Follow observation-first methodology
  - Observe on unfixed code: GET /ping → all `_SECURITY_HEADERS` keys present in response
  - Observe on unfixed code: GET /api/v1/ping → `Cache-Control: no-store, no-cache, must-revalidate` present
  - Observe on unfixed code: any request → `server` header absent
  - Add property-based tests to `tests/unit/presentation/test_middleware.py` using `hypothesis`
  - **Property 2a — Security headers on non-OPTIONS**: `@given(st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE"]))` — for any non-OPTIONS method, all keys in `_SECURITY_HEADERS` (excluding `Cross-Origin-Resource-Policy` which is being removed) must be present in the response
  - **Property 2b — Cache-Control on `/api/*`**: `@given(st.from_regex(r"/api/v1/[a-z]+", fullmatch=True))` — for any non-OPTIONS request to a path starting with `/api/`, `Cache-Control: no-store, no-cache, must-revalidate` must be present
  - **Property 2c — Server header always absent**: `@given(st.sampled_from(["GET", "POST", "OPTIONS", "PUT", "DELETE"]))` — for any HTTP method, `server` must not appear in the response headers
  - Verify all three property tests PASS on unfixed code (confirms baseline behavior to preserve)
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.4_

- [x] 3. Fix for CORS preflight blocked by SecurityHeadersMiddleware and ALLOWED_ORIGINS format

  - [x] 3.1 Implement the fix in `src/presentation/middleware/security_headers.py`
    - Remove `"Cross-Origin-Resource-Policy": "same-origin"` from the `_SECURITY_HEADERS` dict — this header is inappropriate for a cross-origin API and directly contradicts CORS
    - Add OPTIONS short-circuit at the top of `SecurityHeadersMiddleware.dispatch()`: if `request.method == "OPTIONS"`, call `await call_next(request)` and return immediately without stamping any security headers
    - _Bug_Condition: isBugCondition(X) where X.method = "OPTIONS" AND X.headers["Origin"] IS IN allowed_origins AND X.headers["Access-Control-Request-Method"] IS NOT NULL_
    - _Expected_Behavior: response.status = 200 AND "Cross-Origin-Resource-Policy" NOT IN response.headers AND "Access-Control-Allow-Origin" IN response.headers_
    - _Preservation: non-OPTIONS requests must continue to receive all remaining _SECURITY_HEADERS keys, Cache-Control on /api/* routes, and Server header removal_
    - _Requirements: 2.1, 2.2, 3.1, 3.4_

  - [x] 3.2 Update the existing unit tests in `tests/unit/presentation/test_middleware.py` for the changed behavior
    - Remove `"cross-origin-resource-policy"` from the `_REQUIRED_HEADERS` list at the top of the test file — CORP is no longer emitted by the middleware
    - Add a test asserting `"cross-origin-resource-policy"` is NOT a key in `_SECURITY_HEADERS` (import the dict directly)
    - Add a test asserting OPTIONS requests do NOT receive any of the `_SECURITY_HEADERS` keys in the response
    - _Requirements: 2.2, 3.1_

  - [x] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - OPTIONS Preflight Blocked by CORP Header
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - Run `uv run pytest tests/unit/presentation/test_middleware.py -v -k "CORSFix"` from inside `ugsys-projects-registry/`
    - **EXPECTED OUTCOME**: Tests PASS (confirms CORP is absent on OPTIONS responses and ALLOWED_ORIGINS parses correctly with JSON array format)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-OPTIONS Requests Retain All Security Headers
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `uv run pytest tests/unit/presentation/test_middleware.py -v` from inside `ugsys-projects-registry/`
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions — security headers still applied to non-OPTIONS requests)

- [x] 4. Write integration test for the full middleware stack
  - Add `tests/integration/test_middleware_stack.py`
  - Build a full middleware stack: `CorrelationIdMiddleware` → `SecurityHeadersMiddleware` → `RateLimitMiddleware` → `CORSMiddleware` (matching `main.py` order via `add_middleware`)
  - Configure `CORSMiddleware` with `allow_origins=["https://registry.apps.cloud.org.bo"]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`
  - **Integration test 1 — OPTIONS preflight from allowed origin**: fire OPTIONS with `Origin: https://registry.apps.cloud.org.bo` and `Access-Control-Request-Method: GET`; assert status 200, `access-control-allow-origin` present, `cross-origin-resource-policy` absent
  - **Integration test 2 — GET from allowed origin**: fire GET with `Origin: https://registry.apps.cloud.org.bo`; assert `access-control-allow-origin` present and all security headers (excluding CORP) present
  - **Integration test 3 — GET from disallowed origin**: fire GET with `Origin: https://evil.example.com`; assert no `access-control-allow-origin` and all security headers still present
  - Run `uv run pytest tests/integration/test_middleware_stack.py -v` from inside `ugsys-projects-registry/`
  - _Requirements: 2.1, 3.1, 3.2, 3.3_

- [x] 5. Checkpoint — Ensure all tests pass and CI is green on the branch
  - Run full unit suite: `uv run pytest tests/unit/ -v --tb=short` from inside `ugsys-projects-registry/`
  - Run full integration suite: `uv run pytest tests/integration/ -v --tb=short` from inside `ugsys-projects-registry/`
  - Run linter: `uv run ruff check src/ tests/` from inside `ugsys-projects-registry/`
  - Confirm branch `fix/cors-preflight-security-headers` CI passes (lint, typecheck, test, sast, arch-guard jobs)
  - Ensure all tests pass; ask the user if questions arise
