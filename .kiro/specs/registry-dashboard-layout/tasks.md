# Implementation Plan

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Dashboard Route Exists and profileHref Points Locally
  - **CRITICAL**: These tests MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior — they will validate the fix when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - File: `web/src/app/__tests__/router.bug.test.tsx`
  - Test 1 — Router contains `/dashboard` rendering `DashboardPage`:
    - Import the router config and assert `router.routes` includes a route with `path="/dashboard"` that renders `DashboardPage` (profile sections)
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test PASSES (confirms bug exists — route is there)
    - After fix: test FAILS (route is gone — bug is resolved)
  - Test 2 — `Layout` passes `profileHref="/dashboard"` to `UserMenu`:
    - Render `<Layout />` with an authenticated user in context
    - Assert `UserMenu` receives `profileHref="/dashboard"`
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test PASSES (confirms bug exists)
    - After fix: test FAILS (prop is now the external URL)
  - Test 3 — `LoginForm` navigates to `/dashboard` on success with no `?redirect=` param:
    - Render `<LoginForm />`, submit valid credentials, assert `navigate` was called with `"/dashboard"`
    - Run on UNFIXED code — **EXPECTED OUTCOME**: Test PASSES (confirms bug exists)
    - After fix: test FAILS (navigates to `/` instead)
  - Document counterexamples found to understand root cause
  - Mark task complete when tests are written, run, and results are documented
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Write preservation tests (BEFORE implementing fix)
  - **Property 2: Preservation** - All Other Routes and UserMenu Props Unchanged
  - **IMPORTANT**: Follow observation-first methodology — run on UNFIXED code first, observe outputs, then write assertions
  - File: `web/src/app/__tests__/router.preservation.test.tsx` and `web/src/components/layout/__tests__/Layout.preservation.test.tsx`
  - Observe on UNFIXED code:
    - `/` renders `HomePage`
    - `/login` renders `LoginPage`
    - `UserMenu` receives `user`, `adminPanelUrl`, `onLogout`, `renderLink` props unchanged
    - Nav contains "Proyectos", "Sitio Principal", "Eventos"
    - Logout calls `logout()` and redirects to `/`
    - Login with explicit `?redirect=/subscribe/abc` navigates to `/subscribe/abc`
  - Write tests asserting those observed behaviors:
    - Test: render router at `/`, assert `HomePage` is rendered
    - Test: render router at `/login`, assert `LoginPage` is rendered
    - Test: render `Layout` with authenticated user, assert `UserMenu` receives correct `user`, `adminPanelUrl`, `onLogout`, `renderLink` props
    - Test: render `Layout`, assert nav links "Proyectos", "Sitio Principal", "Eventos" are present
    - Test: trigger `onLogout`, assert `logout()` is called
    - Test: `LoginForm` with `?redirect=/subscribe/abc` navigates to `/subscribe/abc`
  - Run all tests on UNFIXED code — **EXPECTED OUTCOME**: All PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Fix: remove /dashboard route, delete misplaced components, update profileHref and post-login redirect

  - [x] 3.1 Update `web/src/app/router.tsx`
    - Remove `import DashboardPage from '../pages/DashboardPage'`
    - Remove the `{ path: '/dashboard', element: <DashboardPage /> }` route object
    - Add `import { Navigate } from 'react-router-dom'` if not already imported
    - Add redirect entry: `{ path: '/dashboard', element: <Navigate to="/" replace /> }`
    - _Bug_Condition: isBugCondition where dashboardRouteExists = true (route renders DashboardPage)_
    - _Expected_Behavior: `/dashboard` route renders `<Navigate to="/" replace />` — no DashboardPage_
    - _Preservation: all other routes (/, /login, /register, /subscribe/:projectId, /reset-password/:token) remain unchanged_
    - _Requirements: 2.2, 2.3_

  - [x] 3.2 Update `web/src/components/layout/Layout.tsx`
    - Change `profileHref="/dashboard"` → `profileHref="https://profile.apps.cloud.org.bo"` in the `UserMenu` props
    - _Bug_Condition: isBugCondition where profileHrefIsLocal = true (profileHref="/dashboard")_
    - _Expected_Behavior: UserMenu receives profileHref="https://profile.apps.cloud.org.bo"_
    - _Preservation: user, adminPanelUrl, onLogout, renderLink props on UserMenu are unchanged_
    - _Requirements: 2.1, 3.4_

  - [x] 3.3 Update `web/src/components/auth/LoginForm.tsx`
    - Change fallback redirect from `"/dashboard"` → `"/"`:
      `const redirect = searchParams.get('redirect') ?? '/'`
    - _Bug_Condition: isBugCondition where loginRedirectIsWrong = true (fallback="/dashboard")_
    - _Expected_Behavior: post-login fallback navigates to "/"_
    - _Preservation: explicit ?redirect= param behavior is unchanged_
    - _Requirements: 2.5, 3.3_

  - [x] 3.4 Delete misplaced dashboard components
    - Delete `web/src/pages/DashboardPage.tsx`
    - Delete `web/src/components/dashboard/ProfileSection.tsx`
    - Delete `web/src/components/dashboard/PasswordChange.tsx`
    - Delete `web/src/components/dashboard/SubscriptionList.tsx`
    - Confirm no remaining imports reference these files (TypeScript compiler will catch any)
    - _Requirements: 2.4_

  - [x] 3.5 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Dashboard Route Removed and profileHref Points Externally
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behavior (assertions now match fixed state)
    - Run bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: Tests FAIL (confirms the bug-state assertions no longer hold — fix is in place)
    - Note: the exploration tests assert the buggy state; after the fix they should fail, which is the correct outcome
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - All Other Routes and UserMenu Props Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation tests from step 2
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions introduced by the fix)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 4. Checkpoint — Ensure all tests pass
  - Run the full frontend test suite: `pnpm vitest --run` (or `npm run test -- --run`)
  - Confirm TypeScript compiles with no errors: `pnpm tsc --noEmit`
  - Confirm no dead imports remain referencing deleted files
  - Ensure all tests pass; ask the user if questions arise
