# Bugfix Requirements Document

## Introduction

The React SPA at `https://registry.apps.cloud.org.bo` renders a completely black/blank page on load.
Infrastructure is confirmed working (S3, CloudFront, CORS, DNS). The root cause is a combination of
two defects: (1) an unhandled React render crash propagates silently because no `ErrorBoundary` wraps
`<RouterProvider>`, leaving `#root` empty; and (2) the `httpClient` calls `forceLogout()` →
`window.location.href = '/login'` whenever a 401 is received with no refresh token in memory — which
can happen on any unauthenticated public API call if the server returns 401, causing an infinite
redirect loop or a navigation that interrupts the initial render. Either defect alone can produce the
black page; both are present in the current bundle.

Bug condition `C(X)`: the app is loaded in a browser session where no tokens are held in memory
(fresh page load / hard refresh) AND either (a) a React component throws during render with no
`ErrorBoundary` ancestor, or (b) the `httpClient` receives a 401 response on a public endpoint and
calls `forceLogout()` before the page has finished mounting.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a React component throws an unhandled exception during the initial render cycle THEN the
system leaves `#root` empty and displays a completely black/blank page with no error message visible
to the user

1.2 WHEN `<RouterProvider>` or any eagerly-imported route component throws during module evaluation
or first render THEN the system propagates the error to the React root with no `ErrorBoundary`
present, causing the entire component tree to unmount silently

1.3 WHEN the `httpClient` receives an HTTP 401 response on a public endpoint (e.g.
`/api/v1/projects/public`) while no refresh token is held in memory THEN the system calls
`forceLogout()` which immediately sets `window.location.href = '/login'`, interrupting the render
and producing a navigation loop or a blank intermediate state

1.4 WHEN `main.tsx` calls `ReactDOM.createRoot(document.getElementById('root')!)` and the element
is `null` (e.g. due to an HTML parsing error or a script-load race) THEN the system throws a
`TypeError` with no recovery path, leaving the page blank

### Expected Behavior (Correct)

2.1 WHEN a React component throws an unhandled exception during the initial render cycle THEN the
system SHALL display a user-visible fallback UI (e.g. "Algo salió mal — Reintentar") instead of a
blank page, and SHALL log the error to the console for debugging

2.2 WHEN `<RouterProvider>` or any eagerly-imported route component throws during render THEN the
system SHALL catch the error at an `ErrorBoundary` wrapping `<RouterProvider>` in `App.tsx` and
SHALL render the fallback UI without unmounting the entire page

2.3 WHEN the `httpClient` receives an HTTP 401 response on a public endpoint while no refresh token
is held in memory THEN the system SHALL throw an `Error` to the caller (allowing `useProjects` to
set its `error` state and render the retry UI) WITHOUT calling `forceLogout()` or redirecting the
user, because no authenticated session exists to invalidate

2.4 WHEN `document.getElementById('root')` returns `null` at startup THEN the system SHALL fail
with a visible console error and SHALL NOT throw an unhandled `TypeError` that silently swallows
the crash

### Unchanged Behavior (Regression Prevention)

3.1 WHEN an authenticated user's access token expires and the `httpClient` receives a 401 on a
protected endpoint THEN the system SHALL CONTINUE TO attempt one token refresh using the in-memory
refresh token and retry the original request before considering the session expired

3.2 WHEN the token refresh itself fails (refresh token invalid or expired) THEN the system SHALL
CONTINUE TO call `forceLogout()` and redirect the authenticated user to `/login`

3.3 WHEN the public projects API returns HTTP 200 with a valid payload THEN the system SHALL
CONTINUE TO render the project grid/list/compact view on the home page without any change in
behavior

3.4 WHEN the public projects API returns HTTP 500 THEN the system SHALL CONTINUE TO display the
error message and "Reintentar" button via the existing `useProjects` error state — the `ErrorBoundary`
fallback SHALL NOT be shown for API errors that are already handled by the hook

3.5 WHEN a user navigates to `/login`, `/register`, or any other route THEN the system SHALL
CONTINUE TO render the correct page component without regression

3.6 WHEN `localStorage` is unavailable (e.g. private browsing with strict settings) THEN the
system SHALL CONTINUE TO fall back to the default `'grid'` view via the existing `try/catch` in
`loadSavedView`

---

## Bug Condition Pseudocode

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type AppLoadContext
  OUTPUT: boolean

  // Bug manifests when EITHER:
  // (a) a render-time exception has no ErrorBoundary to catch it, OR
  // (b) a 401 on a public endpoint triggers forceLogout() with no session to clear
  RETURN (X.hasErrorBoundaryAroundRouter = false AND X.componentThrowsDuringRender = true)
      OR (X.accessToken = null AND X.refreshToken = null AND X.apiReturns401 = true)
END FUNCTION

// Property: Fix Checking
FOR ALL X WHERE isBugCondition(X) DO
  result ← renderApp'(X)
  ASSERT result.rootIsEmpty = false
  ASSERT result.fallbackUIVisible = true OR result.errorStateVisible = true
  ASSERT result.pageIsBlank = false
END FOR

// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT renderApp(X) = renderApp'(X)
END FOR
```
