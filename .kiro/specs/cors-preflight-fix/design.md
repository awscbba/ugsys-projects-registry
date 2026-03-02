# CORS Preflight Fix — Bugfix Design

## Overview

CORS preflight requests (HTTP OPTIONS) from the frontend SPA at `registry.apps.cloud.org.bo`
to the API at `api.apps.cloud.org.bo` were blocked by the browser due to two independent root
causes in `SecurityHeadersMiddleware` and the Lambda environment variable configuration.

The fix removes `Cross-Origin-Resource-Policy` from the security headers dict entirely (it is
inappropriate for a cross-origin API) and adds an OPTIONS short-circuit in
`SecurityHeadersMiddleware` so preflight responses are handled exclusively by `CORSMiddleware`.
The `ALLOWED_ORIGINS` env var must be set as a JSON array string to satisfy pydantic-settings v2.

## Glossary

- **Bug_Condition (C)**: An HTTP OPTIONS preflight request arriving from an origin in
  `ALLOWED_ORIGINS` with a non-null `Access-Control-Request-Method` header — the exact
  condition under which the browser's CORS handshake was broken.
- **Property (P)**: The desired behavior for buggy inputs — the response must carry
  `Access-Control-Allow-Origin` and must NOT carry `Cross-Origin-Resource-Policy`.
- **Preservation**: All non-OPTIONS request handling that must remain unchanged by the fix —
  security headers on regular requests, CORS blocking for disallowed origins, Server header
  removal, and correlation ID propagation.
- **SecurityHeadersMiddleware**: The middleware in
  `src/presentation/middleware/security_headers.py` that stamps security headers onto every
  response. It was the proximate cause of the bug.
- **CORSMiddleware**: Starlette's built-in CORS middleware, added last in `main.py` and
  therefore executed first on the way in. It is responsible for all CORS header emission.
- **ALLOWED_ORIGINS**: The `list[str]` setting in `src/config.py` populated from the Lambda
  env var. pydantic-settings v2 requires JSON array format for list fields.

## Bug Details

### Fault Condition

The bug manifests when an HTTP OPTIONS preflight request arrives from an allowed origin.
`SecurityHeadersMiddleware` intercepts the request before `CORSMiddleware` can short-circuit
it, stamps `Cross-Origin-Resource-Policy: same-origin` onto the response, and the browser
rejects the preflight. Simultaneously, if `ALLOWED_ORIGINS` is a comma-separated string,
`CORSMiddleware` never emits `Access-Control-Allow-Origin` at all.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X of type HttpRequest
  OUTPUT: boolean

  RETURN X.method = "OPTIONS"
         AND X.headers["Origin"] IS IN allowed_origins
         AND X.headers["Access-Control-Request-Method"] IS NOT NULL
END FUNCTION
```

### Examples

- OPTIONS from `https://registry.apps.cloud.org.bo` → response contained
  `Cross-Origin-Resource-Policy: same-origin` → browser blocked the preflight (bug).
- OPTIONS from `https://registry.apps.cloud.org.bo` with `ALLOWED_ORIGINS` set as
  `"https://registry.apps.cloud.org.bo,https://admin.cloud.org.bo"` → pydantic-settings v2
  parsed it as a single-element list `["https://registry.apps.cloud.org.bo,https://..."]` →
  `CORSMiddleware` never matched the origin → no `Access-Control-Allow-Origin` emitted (bug).
- GET from `https://registry.apps.cloud.org.bo` → security headers applied correctly,
  `Access-Control-Allow-Origin` emitted → no bug (must be preserved).
- OPTIONS from `https://evil.example.com` (not in `ALLOWED_ORIGINS`) → no ACAO emitted →
  browser blocks correctly (expected behavior, must be preserved).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Non-OPTIONS requests (GET, POST, PUT, PATCH, DELETE) to `/api/*` routes must continue to
  receive all required security headers: `X-Content-Type-Options`, `X-Frame-Options`,
  `Strict-Transport-Security`, `Content-Security-Policy`, `Referrer-Policy`,
  `Permissions-Policy`, `Cross-Origin-Opener-Policy`, and
  `Cache-Control: no-store, no-cache, must-revalidate`.
- Requests from origins NOT in `ALLOWED_ORIGINS` must continue to receive no
  `Access-Control-Allow-Origin` header.
- Requests from origins in `ALLOWED_ORIGINS` must continue to receive
  `Access-Control-Allow-Origin` on non-OPTIONS responses.
- The `Server` response header must continue to be removed on all responses.
- `X-Request-ID` correlation header must continue to be propagated on non-OPTIONS responses.

**Scope:**
All inputs where `isBugCondition` returns false must be completely unaffected by this fix.
This includes all non-OPTIONS HTTP methods, OPTIONS requests from disallowed origins, and
any request where `Access-Control-Request-Method` is absent.

## Hypothesized Root Cause

1. **`Cross-Origin-Resource-Policy: same-origin` in `_SECURITY_HEADERS`**: This header is
   correct for same-origin document loads but wrong for a cross-origin API. It was included
   in the security headers dict and applied to every response, including OPTIONS preflights,
   directly contradicting the CORS mechanism.

2. **No OPTIONS short-circuit in `SecurityHeadersMiddleware`**: The middleware called
   `call_next(request)` unconditionally and then stamped headers on the result. For OPTIONS
   requests, `CORSMiddleware` (which runs first on the way in due to reverse middleware order)
   returns a synthetic 200 response, but `SecurityHeadersMiddleware` then overwrites its
   headers with security headers including CORP.

3. **`ALLOWED_ORIGINS` env var format mismatch**: pydantic-settings v2 changed the default
   coercion behavior for `list[str]` fields — it no longer splits comma-separated strings
   automatically. The Lambda env var was set as
   `"https://registry.apps.cloud.org.bo,https://admin.cloud.org.bo"` instead of the required
   JSON array `'["https://registry.apps.cloud.org.bo","https://admin.cloud.org.bo"]'`.

4. **Middleware ordering interaction**: FastAPI/Starlette applies `add_middleware()` calls in
   reverse order, so the last-added middleware runs first. `CORSMiddleware` is added last and
   runs first on the way in — but `SecurityHeadersMiddleware` still processes the response on
   the way out, overwriting CORS-set headers.

## Correctness Properties

Property 1: Fault Condition — OPTIONS Preflight Succeeds Without CORP

_For any_ HTTP OPTIONS request where `isBugCondition` returns true (Origin is in
`ALLOWED_ORIGINS` and `Access-Control-Request-Method` is present), the fixed middleware stack
SHALL return a response with status 200, with `Access-Control-Allow-Origin` set to the
request's Origin, and WITHOUT a `Cross-Origin-Resource-Policy` header.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation — Non-OPTIONS Security Headers Unchanged

_For any_ HTTP request where `isBugCondition` returns false (any non-OPTIONS method, or
OPTIONS from a disallowed origin), the fixed middleware stack SHALL produce the same security
header set as the original middleware stack, preserving all required security headers on
regular requests and all CORS-blocking behavior for disallowed origins.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

**Root cause 1 & 2 — already implemented on `fix/cors-preflight-security-headers`:**

**File**: `src/presentation/middleware/security_headers.py`

**Specific Changes**:
1. **Remove `Cross-Origin-Resource-Policy`** from `_SECURITY_HEADERS`: The header is
   inappropriate for a cross-origin API. CORS headers (`Access-Control-Allow-Origin`) are the
   correct mechanism; CORP would block the very cross-origin fetches CORS is meant to allow.

2. **Add OPTIONS short-circuit** in `SecurityHeadersMiddleware.dispatch()`: If
   `request.method == "OPTIONS"`, call `call_next(request)` and return immediately without
   stamping any security headers. This delegates the preflight response entirely to
   `CORSMiddleware`.

**Root cause 3 — configuration fix (applied in Lambda env var, not in code):**

**Environment Variable**: `ALLOWED_ORIGINS`

**Change**: Set the value as a JSON array string:
```
'["https://registry.apps.cloud.org.bo","https://admin.cloud.org.bo"]'
```
instead of the comma-separated string:
```
"https://registry.apps.cloud.org.bo,https://admin.cloud.org.bo"
```

This is a pydantic-settings v2 requirement for `list[str]` fields and requires no code change.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate the bug on unfixed code, then verify the fix works correctly and preserves
existing behavior.

### Exploratory Fault Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE the fix. Confirm or refute
the root cause analysis.

**Test Plan**: Instantiate `SecurityHeadersMiddleware` wrapping a mock `call_next` that
returns a plain 200 response. Fire an OPTIONS request with a valid `Origin` and
`Access-Control-Request-Method`. Assert that the response contains
`Cross-Origin-Resource-Policy: same-origin` — this confirms root cause 2 on unfixed code.

**Test Cases**:
1. **OPTIONS with valid Origin** — fire OPTIONS from `https://registry.apps.cloud.org.bo`;
   assert `Cross-Origin-Resource-Policy` is present in response (will fail on fixed code,
   confirms bug on unfixed code).
2. **OPTIONS with CORP absent** — same request against fixed code; assert CORP is absent and
   `call_next` was called exactly once without header injection.
3. **Comma-separated ALLOWED_ORIGINS** — instantiate `Settings` with
   `ALLOWED_ORIGINS="https://a.example.com,https://b.example.com"`; assert the parsed list
   does NOT contain two separate origins (confirms pydantic-settings v2 behavior).
4. **JSON array ALLOWED_ORIGINS** — instantiate `Settings` with
   `ALLOWED_ORIGINS='["https://a.example.com","https://b.example.com"]'`; assert the parsed
   list contains exactly two origins.

**Expected Counterexamples**:
- On unfixed code: OPTIONS response contains `Cross-Origin-Resource-Policy: same-origin`.
- On unfixed code: comma-separated `ALLOWED_ORIGINS` parses to a single-element list.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed middleware
produces the expected behavior.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  response ← SecurityHeadersMiddleware_fixed.dispatch(X, call_next)
  ASSERT response.status = 200
  ASSERT "Cross-Origin-Resource-Policy" NOT IN response.headers
  ASSERT "Access-Control-Allow-Origin" IN response.headers  // set by CORSMiddleware upstream
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed
middleware produces the same result as the original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT SecurityHeadersMiddleware_original.dispatch(X, call_next)
       = SecurityHeadersMiddleware_fixed.dispatch(X, call_next)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many request combinations (methods, paths, headers) automatically.
- It catches edge cases like unusual HTTP methods or paths that manual tests miss.
- It provides strong guarantees that security headers are present across the full input domain.

**Test Plan**: Observe that GET/POST/PUT/PATCH/DELETE requests receive all required security
headers on unfixed code, then write property-based tests asserting the same on fixed code.

**Test Cases**:
1. **Security headers on non-OPTIONS** — for any non-OPTIONS method, all headers in
   `_SECURITY_HEADERS` must be present in the response.
2. **Cache-Control on `/api/*`** — for any non-OPTIONS request to a path starting with
   `/api/`, `Cache-Control: no-store, no-cache, must-revalidate` must be present.
3. **Server header absent** — for any request, `Server` must not appear in the response.
4. **OPTIONS does not inject headers** — for any OPTIONS request, none of the
   `_SECURITY_HEADERS` keys must appear in the response.

### Unit Tests

- Test `SecurityHeadersMiddleware.dispatch()` with `method=OPTIONS`: assert `call_next` is
  called once and no security headers are injected.
- Test `SecurityHeadersMiddleware.dispatch()` with `method=GET` to `/api/v1/projects`: assert
  all required security headers are present and `Cache-Control` is set.
- Test `SecurityHeadersMiddleware.dispatch()` with `method=GET` to `/health`: assert security
  headers are present but `Cache-Control` is absent.
- Test that `Cross-Origin-Resource-Policy` is NOT in `_SECURITY_HEADERS` dict.
- Test `Settings` with JSON array `ALLOWED_ORIGINS`: assert correct `list[str]` parsing.

### Property-Based Tests

- Generate random non-OPTIONS HTTP methods (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`) and
  random paths; assert all `_SECURITY_HEADERS` keys are present in every response.
- Generate random `/api/*` paths with non-OPTIONS methods; assert `Cache-Control` is always
  set to `no-store, no-cache, must-revalidate`.
- Generate random HTTP methods including `OPTIONS`; assert `Server` header is never present.
- Generate random `OPTIONS` requests with varying `Origin` values; assert none of the
  `_SECURITY_HEADERS` keys appear in the response (OPTIONS short-circuit is unconditional).

### Integration Tests

- Full middleware stack test (CorrelationId → SecurityHeaders → RateLimit → CORS): fire an
  OPTIONS preflight from `https://registry.apps.cloud.org.bo`; assert 200, ACAO present,
  CORP absent.
- Full stack test with a GET from `https://registry.apps.cloud.org.bo`; assert ACAO present
  and all security headers present.
- Full stack test with a GET from `https://evil.example.com`; assert no ACAO and security
  headers still present.
