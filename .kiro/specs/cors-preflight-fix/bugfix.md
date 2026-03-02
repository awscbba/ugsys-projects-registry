# Bugfix Requirements Document

## Introduction

CORS preflight requests (HTTP OPTIONS) from the frontend SPA at `registry.apps.cloud.org.bo`
to the API at `api.apps.cloud.org.bo` were being blocked by the browser. Two independent root
causes were identified:

1. **Wrong `ALLOWED_ORIGINS` format** — the Lambda environment variable was set as a
   comma-separated string, but pydantic-settings v2 requires a JSON array for `list[str]`
   fields. This caused `CORSMiddleware` to receive an empty/malformed origins list and never
   emit `Access-Control-Allow-Origin` headers.

2. **`SecurityHeadersMiddleware` interfering with CORS preflights** — the middleware applied
   `Cross-Origin-Resource-Policy: same-origin` to every response (including OPTIONS preflight
   responses), which directly contradicts CORS headers and causes browsers to block the
   cross-origin load. Additionally, the middleware did not short-circuit for OPTIONS requests,
   so security headers were stamped onto preflight responses before `CORSMiddleware` could
   handle them correctly.

The combined effect was that every OPTIONS preflight from the SPA returned a response the
browser rejected, making all cross-origin API calls fail.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN an HTTP OPTIONS preflight request arrives from `registry.apps.cloud.org.bo` targeting
    `api.apps.cloud.org.bo` THEN the system returns a response that includes
    `Cross-Origin-Resource-Policy: same-origin`, causing the browser to block the cross-origin
    resource load.

1.2 WHEN an HTTP OPTIONS preflight request is processed by `SecurityHeadersMiddleware` THEN the
    system applies all security headers (including `Cross-Origin-Resource-Policy: same-origin`)
    to the preflight response instead of letting `CORSMiddleware` handle it unmodified.

1.3 WHEN `ALLOWED_ORIGINS` is set as a comma-separated string in the Lambda environment
    THEN the system parses it as a malformed `list[str]` (pydantic-settings v2 requires JSON
    array format), causing `CORSMiddleware` to use an empty or single-element origins list and
    never emit `Access-Control-Allow-Origin` on responses.

### Expected Behavior (Correct)

2.1 WHEN an HTTP OPTIONS preflight request arrives from `registry.apps.cloud.org.bo` targeting
    `api.apps.cloud.org.bo` THEN the system SHALL return a 200 response with a valid
    `Access-Control-Allow-Origin` header and WITHOUT a `Cross-Origin-Resource-Policy` header.

2.2 WHEN an HTTP OPTIONS preflight request is processed by `SecurityHeadersMiddleware` THEN the
    system SHALL bypass all security header injection and delegate the response entirely to
    `CORSMiddleware`.

2.3 WHEN `ALLOWED_ORIGINS` is set as a JSON array string in the Lambda environment
    (e.g. `'["https://registry.apps.cloud.org.bo","https://admin.cloud.org.bo"]'`) THEN the
    system SHALL parse it correctly into a `list[str]` and `CORSMiddleware` SHALL emit
    `Access-Control-Allow-Origin` for requests from those origins.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a non-OPTIONS request (GET, POST, PUT, PATCH, DELETE) arrives at any `/api/*` route
    THEN the system SHALL CONTINUE TO apply all required security headers
    (`X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`,
    `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy`,
    `Cross-Origin-Opener-Policy`) and `Cache-Control: no-store, no-cache, must-revalidate`.

3.2 WHEN a non-OPTIONS request arrives from an origin NOT in `ALLOWED_ORIGINS` THEN the system
    SHALL CONTINUE TO return a response without `Access-Control-Allow-Origin`, effectively
    blocking the cross-origin request.

3.3 WHEN a non-OPTIONS request arrives from an origin in `ALLOWED_ORIGINS` THEN the system
    SHALL CONTINUE TO return `Access-Control-Allow-Origin` with that origin's value.

3.4 WHEN any request arrives THEN the system SHALL CONTINUE TO remove the `Server` response
    header to prevent technology fingerprinting.

3.5 WHEN a non-OPTIONS request arrives THEN the system SHALL CONTINUE TO propagate the
    `X-Request-ID` correlation header through the response.

---

## Bug Condition Pseudocode

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type HttpRequest
  OUTPUT: boolean

  RETURN X.method = "OPTIONS"
         AND X.headers["Origin"] IS IN allowed_origins
         AND X.headers["Access-Control-Request-Method"] IS NOT NULL
END FUNCTION
```

```pascal
// Property: Fix Checking — OPTIONS preflight must succeed
FOR ALL X WHERE isBugCondition(X) DO
  response ← handleRequest'(X)
  ASSERT response.status = 200
  ASSERT response.headers["Access-Control-Allow-Origin"] = X.headers["Origin"]
  ASSERT "Cross-Origin-Resource-Policy" NOT IN response.headers
END FOR
```

```pascal
// Property: Preservation Checking — non-preflight requests unchanged
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT handleRequest(X) = handleRequest'(X)   // same headers, same status
END FOR
```
