# Registry Dashboard Layout Bugfix Design

## Overview

The registry web app (`registry.apps.cloud.org.bo`) incorrectly hosts a `/dashboard` route that
renders user-profile sections (`ProfileSection`, `PasswordChange`, `SubscriptionList`). These
belong in the user-profile-service frontend (`profile.apps.cloud.org.bo`), not in a projects
registry. Additionally, the `UserMenu` `profileHref` prop points to the local `/dashboard` route
instead of the external profile service URL, and the post-login redirect lands on `/dashboard`
instead of `/`.

The fix is a pure frontend deletion + redirect + prop update: remove the route, delete the
misplaced components, redirect bookmarked URLs to `/`, update `profileHref`, and fix the
post-login fallback redirect.

---

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — the `/dashboard` route exists in
  the registry router and `profileHref` points to it instead of the external profile service.
- **Property (P)**: The desired behavior — `/dashboard` does not exist as a route, navigating
  there redirects to `/`, `profileHref` is `"https://profile.apps.cloud.org.bo"`, and post-login
  redirects to `/`.
- **Preservation**: All other routes, nav links, `UserMenu` props (user, roles, adminPanelUrl,
  onLogout), and auth flows that must remain unchanged by this fix.
- **`router.tsx`**: `web/src/app/router.tsx` — defines the `createBrowserRouter` route tree.
- **`Layout.tsx`**: `web/src/components/layout/Layout.tsx` — renders `AppNavbar`, `UserMenu`,
  `Footer`, and the `<Outlet />`.
- **`LoginForm.tsx`**: `web/src/components/auth/LoginForm.tsx` — handles login submission and
  post-login navigation.
- **`profileHref`**: The prop passed to `UserMenu` that controls where "Mi Perfil" links to.
- **`renderLink`**: The prop passed to `UserMenu` and `Footer` that renders internal links as
  `NavLink`. External URLs in `profileHref` are handled natively by `UserMenu` (plain `<a>`).

---

## Bug Details

### Bug Condition

The bug manifests in two related places:

1. The router contains a `/dashboard` route that renders `DashboardPage` — a page composed
   entirely of profile-service components (`ProfileSection`, `PasswordChange`,
   `SubscriptionList`) that have no place in the projects registry.
2. `Layout.tsx` passes `profileHref="/dashboard"` to `UserMenu`, routing "Mi Perfil" clicks to
   the local (wrong) route instead of the external profile service.
3. `LoginForm.tsx` uses `"/dashboard"` as the fallback redirect after a successful login.

**Formal Specification:**
```
FUNCTION isBugCondition(routerConfig, layoutProps, loginFormFallback)
  INPUT:
    routerConfig       — the array of route objects from createBrowserRouter
    layoutProps        — the props passed to UserMenu in Layout
    loginFormFallback  — the default redirect path used in LoginForm on login success

  OUTPUT: boolean

  dashboardRouteExists  := EXISTS route IN routerConfig WHERE route.path = '/dashboard'
                           AND route renders DashboardPage (profile sections)
  profileHrefIsLocal    := layoutProps.profileHref = '/dashboard'
  loginRedirectIsWrong  := loginFormFallback = '/dashboard'

  RETURN dashboardRouteExists OR profileHrefIsLocal OR loginRedirectIsWrong
END FUNCTION
```

### Examples

- User navigates to `/dashboard` → sees "Mi Panel" with "Mi Perfil", "Cambiar Contraseña",
  "Mis Suscripciones" sections. Expected: redirect to `/`.
- Authenticated user clicks "Mi Perfil" in `UserMenu` → browser navigates to
  `/dashboard` (local). Expected: browser navigates to `https://profile.apps.cloud.org.bo`.
- User logs in successfully with no `?redirect=` param → navigates to `/dashboard`. Expected:
  navigates to `/`.
- User bookmarks `/dashboard` and returns later → sees profile sections. Expected: redirect to `/`.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `/` continues to render `HomePage` (public project catalog with pagination and view toggle)
  for all users, authenticated or not.
- Unauthenticated users navigating to any protected route continue to be redirected to `/login`
  via `useProtectedRoute`.
- `/login`, `/register`, `/subscribe/:projectId`, and `/reset-password/:token` routes continue
  to render their respective pages without disruption.
- `UserMenu` continues to receive the same `user` (email, roles), `adminPanelUrl`, `onLogout`,
  and `renderLink` props — only `profileHref` changes.
- Logout via `UserMenu` continues to call `logout()` and redirect to `/`.
- Nav links ("Proyectos", "Sitio Principal", "Eventos") remain unchanged.
- The `renderLink` prop passed to `UserMenu` and `Footer` is unchanged — it still renders
  internal paths as `NavLink`. `UserMenu` handles the external `profileHref` URL natively.

**Scope:**
All inputs that do NOT involve the `/dashboard` route, the `profileHref` prop value, or the
post-login fallback redirect are completely unaffected by this fix.

---

## Hypothesized Root Cause

The `/dashboard` route and its components were scaffolded during early development as a
placeholder for user profile functionality, before the service boundary between
`ugsys-projects-registry` and `ugsys-user-profile-service` was finalized. The route was never
removed when the architecture decision was made to host profile management at
`profile.apps.cloud.org.bo`. As a result:

1. **Wrong service boundary**: `ProfileSection`, `PasswordChange`, and `SubscriptionList` were
   built inside the registry repo instead of the profile-service repo.
2. **Stale `profileHref`**: `Layout.tsx` was written when `/dashboard` was the intended
   destination; it was never updated to point to the external profile service URL.
3. **Stale login redirect fallback**: `LoginForm.tsx` defaults to `"/dashboard"` as the
   post-login destination, which was correct when the dashboard existed but is now wrong.

There are no runtime errors — the bug is a routing/ownership mismatch, not a crash.

---

## Correctness Properties

Property 1: Bug Condition — Dashboard Route Removed and profileHref Points Externally

_For any_ render of the registry application, the router SHALL NOT contain a route with
`path="/dashboard"` that renders profile-service components, the `UserMenu` SHALL receive
`profileHref="https://profile.apps.cloud.org.bo"`, navigating to `/dashboard` SHALL redirect
to `/`, and a successful login with no `?redirect=` param SHALL navigate to `/`.

**Validates: Requirements 2.1, 2.2, 2.3, 2.5**

Property 2: Preservation — All Other Routes and UserMenu Props Unchanged

_For any_ navigation to `/`, `/login`, `/register`, `/subscribe/:projectId`, or
`/reset-password/:token`, and for any render of `UserMenu` with an authenticated user, the
fixed code SHALL produce exactly the same behavior as the original code — same pages rendered,
same `user`/`adminPanelUrl`/`onLogout`/`renderLink` props on `UserMenu`, same nav links, same
logout behavior.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

---

## Fix Implementation

### Changes Required

**File: `web/src/app/router.tsx`**

1. Remove the `import DashboardPage` statement.
2. Remove the `{ path: '/dashboard', element: <DashboardPage /> }` route object.
3. Add a redirect entry: `{ path: '/dashboard', element: <Navigate to="/" replace /> }` (using
   `Navigate` from `react-router-dom`).

**File: `web/src/components/layout/Layout.tsx`**

4. Change `profileHref="/dashboard"` → `profileHref="https://profile.apps.cloud.org.bo"` in
   the `UserMenu` props.

**File: `web/src/components/auth/LoginForm.tsx`**

5. Change the fallback redirect default from `"/dashboard"` → `"/"`:
   ```ts
   const redirect = searchParams.get('redirect') ?? '/';
   ```

**Files to delete:**

6. `web/src/pages/DashboardPage.tsx`
7. `web/src/components/dashboard/ProfileSection.tsx`
8. `web/src/components/dashboard/PasswordChange.tsx`
9. `web/src/components/dashboard/SubscriptionList.tsx`

No backend changes. No new dependencies. No changes to `useProtectedRoute`, `useAuth`,
`authStore`, or any other hook/store.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing
behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm
the root cause analysis.

**Test Plan**: Render the router and assert that `/dashboard` resolves to `DashboardPage`
(profile sections). Render `Layout` with an authenticated user and assert `profileHref` is
`"/dashboard"`. Simulate a login submission with no `?redirect=` param and assert `navigate` is
called with `"/dashboard"`. Run these on the UNFIXED code to observe failures.

**Test Cases**:
1. **Router contains /dashboard**: Assert `router.routes` includes a route with
   `path="/dashboard"` that renders `DashboardPage` (will pass on unfixed code, fail after fix).
2. **profileHref is local**: Render `Layout` with authenticated user, assert `UserMenu` receives
   `profileHref="/dashboard"` (will pass on unfixed code, fail after fix).
3. **Post-login redirect is /dashboard**: Simulate login success with no redirect param, assert
   `navigate("/dashboard")` is called (will pass on unfixed code, fail after fix).

**Expected Counterexamples**:
- After fix, assertions above flip: `/dashboard` route no longer renders `DashboardPage`,
  `profileHref` is the external URL, and post-login navigates to `/`.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the
expected behavior.

**Pseudocode:**
```
FOR ALL state WHERE isBugCondition(routerConfig, layoutProps, loginFormFallback) DO
  result := evaluate_fixed(state)
  ASSERT result.dashboardRouteRendersProfileSections = false
  ASSERT result.profileHref = 'https://profile.apps.cloud.org.bo'
  ASSERT result.dashboardNavigatesTo = '/'
  ASSERT result.postLoginFallback = '/'
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code
produces the same result as the original code.

**Pseudocode:**
```
FOR ALL route IN ['/', '/login', '/register', '/subscribe/:projectId', '/reset-password/:token'] DO
  ASSERT render_original(route) = render_fixed(route)
END FOR

FOR ALL userMenuProp IN ['user', 'adminPanelUrl', 'onLogout', 'renderLink'] DO
  ASSERT original_Layout[userMenuProp] = fixed_Layout[userMenuProp]
END FOR
```

**Testing Approach**: Example-based tests are sufficient here — the change set is small and
well-bounded. Property-based testing would add value for the router route enumeration (verifying
no other routes were accidentally removed), but is optional given the low complexity.

**Test Cases**:
1. **HomePage preserved**: Render router at `/`, assert `HomePage` is rendered.
2. **LoginPage preserved**: Render router at `/login`, assert `LoginPage` is rendered.
3. **UserMenu props preserved**: Render `Layout` with authenticated user, assert `user`,
   `adminPanelUrl`, `onLogout`, `renderLink` props are unchanged.
4. **Nav links preserved**: Render `Layout`, assert nav contains "Proyectos", "Sitio Principal",
   "Eventos".
5. **Logout preserved**: Trigger `onLogout` in `UserMenu`, assert `logout()` is called.
6. **Post-login with explicit redirect**: Simulate login with `?redirect=/subscribe/abc`, assert
   `navigate("/subscribe/abc")` is called (existing behavior unchanged).

### Unit Tests

- Assert router routes array does not contain `path="/dashboard"` rendering `DashboardPage`.
- Assert router routes array contains `path="/dashboard"` rendering `<Navigate to="/" replace />`.
- Assert `UserMenu` in `Layout` receives `profileHref="https://profile.apps.cloud.org.bo"`.
- Assert `LoginForm` navigates to `/` on success when no `?redirect=` param is present.
- Assert `LoginForm` still respects an explicit `?redirect=` param.

### Property-Based Tests

- For any route path in the router that is NOT `/dashboard`, the rendered element is unchanged
  between original and fixed router (no accidental route deletions).
- For any authenticated user object passed to `Layout`, all `UserMenu` props except `profileHref`
  are identical between original and fixed `Layout`.

### Integration Tests

- Navigate to `/dashboard` in a test browser environment, assert the final URL is `/` (redirect
  followed).
- Click "Mi Perfil" in `UserMenu` for an authenticated user, assert the `href` attribute of the
  rendered link is `https://profile.apps.cloud.org.bo`.
- Complete a login flow with no redirect param, assert the app lands on `/` (HomePage visible).
