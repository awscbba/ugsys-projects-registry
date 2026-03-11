# Bugfix Requirements Document

## Introduction

The registry web app (`registry.apps.cloud.org.bo`) has a layout bug: the `/dashboard` route
renders user-specific profile sections — "Mi Perfil", "Cambiar Contraseña", and "Mis
Suscripciones" — that do not belong in the projects registry. These sections are the
responsibility of the user-profile-service frontend (`profile.apps.cloud.org.bo`).

Additionally, the `UserMenu` component's "Mi Perfil" link points to `/dashboard` (a local route)
instead of the external user-profile-service URL.

The fix removes the `/dashboard` route and its associated profile components entirely from the
registry, and updates `profileHref` in `UserMenu` to point to
`https://profile.apps.cloud.org.bo`.

Session persistence across subdomains is handled separately by the `cross-service-session`
bugfix spec in `ugsys-identity-manager`.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a logged-in user navigates to `/dashboard` THEN the system renders `ProfileSection`
("Mi Perfil"), `PasswordChange` ("Cambiar Contraseña"), and `SubscriptionList` ("Mis
Suscripciones") — sections that belong in the user-profile-service, not the projects registry.

1.2 WHEN a logged-in user clicks "Mi Perfil" in the `UserMenu` (top-right) THEN the system
navigates to `/dashboard` (a local route) instead of the user-profile-service frontend.

1.3 WHEN the registry router is inspected THEN the `/dashboard` route exists as a protected
route, serving profile content that has no place in a projects registry.

---

### Expected Behavior (Correct)

2.1 WHEN a logged-in user clicks "Mi Perfil" in the `UserMenu` THEN the system SHALL navigate
to `https://profile.apps.cloud.org.bo` (the `profileHref` prop passed to `UserMenu` SHALL be
`"https://profile.apps.cloud.org.bo"`).

2.2 WHEN the registry router is inspected THEN the `/dashboard` route SHALL NOT exist — it is
removed entirely.

2.3 WHEN a user navigates to `/dashboard` (e.g. via a bookmarked URL) THEN the system SHALL
redirect to `/` (the public project catalog).

2.4 WHEN the registry codebase is inspected THEN the components `ProfileSection`,
`PasswordChange`, and `SubscriptionList` SHALL NOT exist — they are deleted from the registry
entirely (they belong in the user-profile-service frontend).

2.5 WHEN a user successfully logs in THEN the system SHALL redirect to `/` (the public project
catalog), not to `/dashboard`.

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN any user (authenticated or not) navigates to `/` THEN the system SHALL CONTINUE TO
display the full public project catalog with pagination and view toggle.

3.2 WHEN an unauthenticated user navigates to any protected route THEN the system SHALL CONTINUE
TO redirect to `/login` via the existing `useProtectedRoute` hook.

3.3 WHEN a logged-in user navigates to `/login`, `/register`, `/subscribe/:projectId`, or
`/reset-password/:token` THEN the system SHALL CONTINUE TO render those pages without
disruption.

3.4 WHEN the `UserMenu` is rendered for an authenticated user THEN the system SHALL CONTINUE TO
display the user's email, roles, and the admin panel link unchanged — only `profileHref` changes
from `"/dashboard"` to `"https://profile.apps.cloud.org.bo"`.

3.5 WHEN a logged-in user logs out from the `UserMenu` THEN the system SHALL CONTINUE TO call
`logout()` and redirect to `/`.

3.6 WHEN the `Layout` component renders nav links THEN the system SHALL CONTINUE TO show
"Proyectos", "Sitio Principal", and "Eventos" — no new nav links are added.
