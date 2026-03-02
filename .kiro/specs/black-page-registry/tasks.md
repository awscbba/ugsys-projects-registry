# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Fault Condition** - Black Page on Render Crash and Public 401 with No Session
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope to three concrete failing cases for reproducibility:
    1. Render crash with no ErrorBoundary: render a component that throws synchronously inside a mock `<RouterProvider>` → assert `#root` is not empty and fallback text is visible. On unfixed code this FAILS because React empties `#root`.
    2. Public 401 with no session: call `httpClient.get('/public')` with mocked 401, both `getAccessToken()` and `getRefreshToken()` returning null → assert `window.location.href` setter is NOT called. On unfixed code this FAILS because `forceLogout()` fires unconditionally.
    3. Null root element: mock `document.getElementById` returning null → assert `console.error` is called and no `TypeError` is thrown. On unfixed code a `TypeError` is thrown.
  - Create test file `web/src/components/ui/ErrorBoundary.test.tsx` for cases 1 and 3
  - Create or extend `web/src/services/httpClient.test.ts` for case 2
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bug exists)
  - Document counterexamples found:
    - `#root` is empty after a render crash (no ErrorBoundary present)
    - `window.location.href` is set to `/login` on a public 401 with no session
    - `TypeError: Cannot read properties of null` thrown from `ReactDOM.createRoot`
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Authenticated 401→Refresh→Retry Flow and Error States Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (cases where `isBugCondition(X)` is false):
    - Observe: authenticated 401 with refresh token present → `_refreshTokenFn` is called, original request is retried, `forceLogout` is NOT called
    - Observe: refresh token present + `_refreshTokenFn` throws → `forceLogout` IS called
    - Observe: public API returns 200 → project grid renders, no fallback UI
    - Observe: public API returns 500 → `useProjects` error state ("Reintentar") is visible, ErrorBoundary fallback is NOT shown
  - Write property-based tests capturing these observed behaviors:
    - For any 401 where at least one token is present and refresh succeeds → original request is retried, `forceLogout` not called
    - For any 401 where refresh token is present but `_refreshTokenFn` throws → `forceLogout` is always called
    - For any non-401 API response → no redirect, no fallback UI from ErrorBoundary
  - Add preservation tests to `web/src/services/httpClient.test.ts`
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Fix: Black page at registry.apps.cloud.org.bo

  - [x] 3.1 Create ErrorBoundary component and wrap RouterProvider in App.tsx
    - Create `web/src/components/ui/ErrorBoundary.tsx` as a React class component:
      - `state: { hasError: boolean; error: Error | null }`
      - `static getDerivedStateFromError(error)` → returns `{ hasError: true, error }`
      - `componentDidCatch(error, info)` → `console.error` (development only guard optional)
      - Fallback UI: heading "Algo salió mal" + "Reintentar" button calling `window.location.reload()`
      - Renders `this.props.children` when `hasError` is false
    - Modify `web/src/app/App.tsx`:
      - Import `ErrorBoundary` from `../components/ui/ErrorBoundary`
      - Wrap `<RouterProvider router={router} />` with `<ErrorBoundary>`
      - Keep `<ToastContainer />` outside the boundary (must not unmount on router errors)
    - _Bug_Condition: isBugCondition(X) where X.hasErrorBoundaryAroundRouter = false AND X.componentThrowsDuringRender = true_
    - _Expected_Behavior: result.fallbackUIVisible = true, result.rootIsEmpty = false, result.pageIsBlank = false_
    - _Preservation: ToastContainer remains mounted; non-throwing render paths are unaffected_
    - _Requirements: 2.1, 2.2_

  - [x] 3.2 Guard forceLogout() with token-presence check in httpClient.ts
    - Modify `web/src/services/httpClient.ts` in the 401 `else` branch:
      - Before calling `forceLogout()`, check `getAccessToken() !== null || getRefreshToken() !== null`
      - If both are null → skip `forceLogout()`, just `throw error` to the caller
      - If at least one token was present → call `forceLogout()` as before (session existed, must be cleared)
    - _Bug_Condition: isBugCondition(X) where X.accessToken = null AND X.refreshToken = null AND X.apiReturns401 = true_
    - _Expected_Behavior: forceLogout() is NOT called; error is thrown to caller so useProjects sets its error state_
    - _Preservation: authenticated 401→refresh→retry flow (req 3.1) and refresh-failure→forceLogout (req 3.2) are unchanged_
    - _Requirements: 2.3, 3.1, 3.2_

  - [x] 3.3 Add null-safe root element check in main.tsx
    - Modify `web/src/main.tsx`:
      - Replace `document.getElementById('root')!` with `const rootElement = document.getElementById('root')`
      - If `rootElement` is null → `console.error('[App] #root element not found')` and return early
      - If present → `ReactDOM.createRoot(rootElement).render(...)`
    - _Bug_Condition: isBugCondition(X) where document.getElementById('root') returns null_
    - _Expected_Behavior: console.error is called, no TypeError is thrown, no unhandled crash_
    - _Preservation: normal startup path (rootElement present) is completely unchanged_
    - _Requirements: 2.4_

  - [x] 3.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Black Page Is Not Shown for Bug Condition Inputs
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied for all three bug paths
    - Run exploration tests from step 1 on the FIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms all three bug paths are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Authenticated Flow and Error States Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2 on the FIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in authenticated flow, error states, or route navigation)
    - Confirm all preservation tests still pass after fix
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 4. Checkpoint — Ensure all tests pass
  - Run full frontend test suite: `cd ugsys-projects-registry/web && npx vitest --run`
  - Verify build succeeds: `npm run build` (no TypeScript errors, no bundler errors)
  - Confirm all tasks 1–3.5 are complete and green
  - Ensure all tests pass; ask the user if questions arise
