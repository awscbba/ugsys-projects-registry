# Black Page Registry — Bugfix Design

## Overview

The React SPA at `https://registry.apps.cloud.org.bo` renders a blank/black page on load due to
two independent defects that can each produce the symptom on their own:

1. **No ErrorBoundary around `<RouterProvider>`** — any render-time exception silently unmounts
   the entire React tree, leaving `#root` empty with no visible feedback.
2. **`forceLogout()` fires on 401 with no session** — when a public endpoint returns 401 and no
   tokens are in memory, `httpClient` calls `forceLogout()` → `window.location.href = '/login'`,
   interrupting the initial render or creating a redirect loop.

The fix is minimal and targeted: add an `ErrorBoundary` class component wrapping `<RouterProvider>`
in `App.tsx`, guard `forceLogout()` with a token-presence check in `httpClient.ts`, and add a
null-check for the `#root` element in `main.tsx`.

---

## Glossary

- **Bug_Condition (C)**: The condition that triggers the black page — either a render-time exception
  with no ErrorBoundary ancestor, or a 401 response on a public endpoint with no session tokens
- **Property (P)**: The desired behavior when C(X) holds — the page is NOT blank; either a fallback
  UI or an error state is visible to the user
- **Preservation**: Existing authenticated 401→refresh→retry flow, `useProjects` error state UI,
  and all route navigation that must remain unchanged by the fix
- **`forceLogout()`**: The function in `web/src/services/httpClient.ts` that calls `clearTokens()`
  and sets `window.location.href = '/login'`
- **`isBugCondition(X)`**: Pseudocode predicate that identifies inputs triggering the black page
- **`ErrorBoundary`**: React class component (required by the React error boundary API) that catches
  render-time exceptions via `componentDidCatch` and renders a fallback UI
- **`AppLoadContext`**: The set of conditions present when the app loads — token state, API
  responses, component render outcomes

---

## Bug Details

### Fault Condition

The black page manifests when the app loads in a browser session where either (a) a React component
throws during the render cycle and no `ErrorBoundary` is present to catch it, or (b) the
`httpClient` receives a 401 on a public endpoint while no tokens are held in memory and calls
`forceLogout()` before the page has finished mounting.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X of type AppLoadContext
  OUTPUT: boolean

  RETURN (X.hasErrorBoundaryAroundRouter = false AND X.componentThrowsDuringRender = true)
      OR (X.accessToken = null AND X.refreshToken = null AND X.apiReturns401 = true)
END FUNCTION
```

### Examples

- **Render crash, no boundary**: `<RouterProvider>` throws during module evaluation (e.g. a route
  component has a top-level `throw`) → React propagates to root → `#root` is empty → black page
- **Public 401, no session**: Fresh page load hits `/api/v1/projects/public` → server returns 401
  → `getRefreshToken()` is null → `forceLogout()` fires → `window.location.href = '/login'` →
  redirect loop or blank intermediate state
- **Null root element**: `document.getElementById('root')` returns null (HTML parse error or
  script-load race) → `ReactDOM.createRoot(null!)` throws `TypeError` → unhandled, page stays blank
- **Edge case — 401 with tokens present**: Access token expired, refresh token valid → this is NOT
  a bug condition; the refresh+retry flow must continue to work unchanged

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Authenticated 401 → one refresh attempt → retry original request must continue to work exactly
  as before (requirements 3.1)
- When the refresh token itself is invalid/expired, `forceLogout()` must still be called and the
  user redirected to `/login` (requirement 3.2)
- Public projects API returning 200 must continue to render the project grid/list/compact view
  without any change (requirement 3.3)
- Public projects API returning 500 must continue to show the `useProjects` error state with
  "Reintentar" button — the `ErrorBoundary` fallback must NOT appear for API errors already
  handled by the hook (requirement 3.4)
- Navigation to `/login`, `/register`, and all other routes must continue to render correctly
  (requirement 3.5)
- `localStorage` unavailable fallback to `'grid'` view via existing `try/catch` must be preserved
  (requirement 3.6)

**Scope:**
All inputs where `isBugCondition(X)` is false must be completely unaffected by this fix. This
includes:
- Any request where at least one token is present in memory
- Any API response that is not a 401 (200, 400, 500, etc.)
- Any render path where no component throws during the render cycle

---

## Hypothesized Root Cause

Based on code inspection of `App.tsx`, `httpClient.ts`, and `main.tsx`:

1. **Missing ErrorBoundary** (`App.tsx`): `<RouterProvider router={router} />` is rendered with no
   `ErrorBoundary` ancestor. React's error boundary mechanism requires a class component with
   `componentDidCatch` — without one, any render-time exception propagates to the React root and
   unmounts the entire tree silently, leaving `#root` empty.

2. **Unconditional `forceLogout()` on 401** (`httpClient.ts`): The `else` branch at line ~80
   calls `forceLogout()` whenever `!refreshToken || !_refreshTokenFn`, which is always true on a
   fresh page load. There is no check for whether an authenticated session actually existed. Any
   public endpoint that returns 401 (e.g. for unauthenticated access) will trigger a redirect.

3. **Non-null assertion on `#root`** (`main.tsx`): `document.getElementById('root')!` uses a
   TypeScript non-null assertion. If the element is absent, `ReactDOM.createRoot` receives `null`
   and throws a `TypeError` with no recovery path.

---

## Correctness Properties

Property 1: Fault Condition — Black Page Is Not Shown

_For any_ `AppLoadContext` where `isBugCondition(X)` returns true (either a render-time exception
with no ErrorBoundary, or a 401 on a public endpoint with no session tokens), the fixed application
SHALL NOT leave `#root` empty. It SHALL either render a visible fallback UI ("Algo salió mal —
Reintentar") when a render exception is caught, or propagate the error to the caller's error state
(e.g. `useProjects`) without redirecting, so the page remains mounted and visible.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation — Authenticated Flow and Error States Unchanged

_For any_ `AppLoadContext` where `isBugCondition(X)` returns false (tokens present, no render
crash, or API errors handled by hooks), the fixed application SHALL produce exactly the same
behavior as the original application, preserving the 401→refresh→retry flow, the `useProjects`
error state UI, all route rendering, and the `localStorage` fallback.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

---

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File 1**: `web/src/components/ui/ErrorBoundary.tsx` _(new file)_

**Specific Changes**:
1. **Create React class component** implementing the error boundary API:
   - `state: { hasError: boolean; error: Error | null }`
   - `static getDerivedStateFromError(error)` → sets `hasError: true`
   - `componentDidCatch(error, info)` → `console.error` in development only
   - Fallback UI: "Algo salió mal" heading + "Reintentar" button calling `window.location.reload()`
   - Renders `this.props.children` when no error

---

**File 2**: `web/src/app/App.tsx`

**Specific Changes**:
2. **Wrap `<RouterProvider>`** with the new `<ErrorBoundary>` component:
   ```tsx
   <ErrorBoundary>
     <RouterProvider router={router} />
   </ErrorBoundary>
   ```
   `<ToastContainer />` stays outside the boundary (it should not be unmounted on router errors).

---

**File 3**: `web/src/services/httpClient.ts`

**Specific Changes**:
3. **Guard `forceLogout()` with token-presence check** in the `else` branch of the 401 handler:
   - Before calling `forceLogout()`, check `getAccessToken() !== null || getRefreshToken() !== null`
   - If both are null → skip `forceLogout()`, just throw the error to the caller
   - If at least one token was present → call `forceLogout()` as before (session existed, must clear)

---

**File 4**: `web/src/main.tsx`

**Specific Changes**:
4. **Replace non-null assertion** with an explicit null check:
   - `const rootElement = document.getElementById('root')`
   - If null → `console.error('[App] #root element not found')` and return early
   - If present → `ReactDOM.createRoot(rootElement).render(...)`

---

## Testing Strategy

### Validation Approach

Two-phase approach: first run exploration tests on the **unfixed** code to confirm the bug
manifests as expected and validate the root cause analysis; then run fix-checking and preservation
tests on the **fixed** code.

Test stack: **Vitest** + **@testing-library/react** + **vi.fn()** mocks.

---

### Exploratory Fault Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or
refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Render `<App />` (or the relevant isolated component) with conditions that trigger
each bug path. Run on the UNFIXED code and observe failures.

**Test Cases**:
1. **Render crash, no boundary** (will fail on unfixed code): Render a component that throws
   synchronously inside a mock `<RouterProvider>` → assert `document.getElementById('root')` is
   not empty and a fallback message is visible. On unfixed code this assertion fails because
   `#root` is emptied by React.
2. **Public 401, no session** (will fail on unfixed code): Call `httpClient.get('/public')` with
   a mocked 401 response, `getAccessToken()` and `getRefreshToken()` both returning null → assert
   `forceLogout` (mocked `window.location.href` setter) is NOT called. On unfixed code this
   assertion fails because `forceLogout()` is called unconditionally.
3. **Null root element** (will fail on unfixed code): Mock `document.getElementById` to return
   null → assert `console.error` is called and no `TypeError` is thrown. On unfixed code a
   `TypeError` is thrown.

**Expected Counterexamples**:
- `#root` is empty after a render crash (no ErrorBoundary present)
- `window.location.href` is set to `/login` on a public 401 with no session
- `TypeError: Cannot read properties of null` thrown from `ReactDOM.createRoot`

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed application produces
the expected behavior (page not blank, fallback or error state visible).

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  result := renderApp_fixed(X)
  ASSERT result.rootIsEmpty = false
  ASSERT result.fallbackUIVisible = true OR result.errorStateVisible = true
  ASSERT result.pageIsBlank = false
END FOR
```

**Test Cases**:
1. **ErrorBoundary renders fallback on child throw**: Render `<ErrorBoundary><ThrowingChild /></ErrorBoundary>` → assert fallback text "Algo salió mal" is in the DOM
2. **ErrorBoundary does not show fallback on normal render**: Render `<ErrorBoundary><NormalChild /></ErrorBoundary>` → assert fallback text is NOT in the DOM, child content IS visible
3. **httpClient does not call forceLogout on 401 with no tokens**: Mock 401 response + both getters return null → assert `window.location.href` is not set to `/login`
4. **httpClient throws to caller on 401 with no tokens**: Same setup → assert the returned promise rejects with an `Error`
5. **Null root element logs error, does not throw**: Mock `getElementById` returning null → assert `console.error` called, no unhandled exception

---

### Preservation Checking

**Goal**: Verify that for all inputs where `isBugCondition(X)` is false, the fixed application
produces the same result as the original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT renderApp_original(X) = renderApp_fixed(X)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for authenticated flows and error states,
then write tests capturing that behavior to verify it is preserved after the fix.

**Test Cases**:
1. **Authenticated 401 → refresh → retry preserved**: Mock 401 response with refresh token present
   + `_refreshTokenFn` returning new tokens → assert original request is retried with new token,
   `forceLogout` is NOT called
2. **Refresh failure → forceLogout preserved**: Mock 401 + refresh token present + `_refreshTokenFn`
   throws → assert `forceLogout` IS called (session existed, must be cleared)
3. **useProjects 500 shows error state, not ErrorBoundary fallback**: Render the projects page with
   a mocked 500 API response → assert `useProjects` error UI ("Reintentar") is visible, assert
   "Algo salió mal" (ErrorBoundary fallback) is NOT visible
4. **200 response renders project grid**: Mock 200 with valid payload → assert project cards render
   correctly, no fallback UI visible
5. **Route navigation works**: Render `<App />` and navigate to `/login` → assert login page
   component renders without regression

---

### Unit Tests

- `ErrorBoundary` renders fallback when child throws synchronously
- `ErrorBoundary` renders children normally when no error occurs
- `ErrorBoundary` "Reintentar" button calls `window.location.reload()`
- `httpClient` does not call `forceLogout` on 401 when both tokens are null
- `httpClient` does call `forceLogout` on 401 when refresh token is present but refresh fails
- `httpClient` retries with new token after successful refresh on 401
- `main.tsx` null root element: `console.error` called, no TypeError thrown

### Property-Based Tests

- For any component that throws during render inside `<ErrorBoundary>`, the fallback UI is always
  shown and `#root` is never empty (generate random error types and messages)
- For any 401 response where both `getAccessToken()` and `getRefreshToken()` return null,
  `forceLogout` is never called (generate random request paths and response bodies)
- For any 401 response where at least one token is present and refresh fails, `forceLogout` is
  always called (generate random token values and refresh error types)

### Integration Tests

- Full app render with a throwing route component → ErrorBoundary fallback visible, rest of page
  mounted (ToastContainer still present)
- Full app render with public 401 → `useProjects` error state visible, no redirect
- Full app render with authenticated 401 → refresh → retry → project grid visible
