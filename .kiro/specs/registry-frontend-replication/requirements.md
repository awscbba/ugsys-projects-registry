# Requirements Document

## Introduction

The `ugsys-projects-registry` web SPA (`ugsys-projects-registry/web/`) currently renders pages without any shared chrome — no Navbar, no header, no footer. The Registry monolith frontend (`Registry/registry-frontend/`) has a full layout shell with AWS User Group Cochabamba branding, a sticky header with navigation links, a `UserMenu` dropdown (login/register buttons when unauthenticated, avatar + dropdown when authenticated), and a footer with social links.

This feature replicates the layout shell, navigation, and user menu into the React 19 + TypeScript + Vite 6 + Tailwind 4 SPA, adapting the Astro-based Registry frontend patterns to the existing React Router v6 architecture.

Admin functionality is explicitly out of scope — it belongs to the dedicated `ugsys-admin-panel` service.

## Glossary

- **SPA**: The `ugsys-projects-registry/web/` React single-page application.
- **Layout**: A React component that wraps all pages with a shared Navbar and Footer.
- **Navbar**: The sticky top header containing the AWS UG Cbba logo, navigation links, and the `UserMenu`.
- **UserMenu**: The header component that shows "Registrarse" + "Iniciar Sesión" buttons when unauthenticated, and an avatar dropdown with profile/logout options when authenticated.
- **Footer**: The bottom section with branding, navigation links, and social icons.
- **Auth_Store**: The existing Zustand store at `src/stores/authStore.ts` that holds the authenticated user state.

---

## Requirements

### Requirement 1: Layout Shell

**User Story:** As a visitor, I want every page to have a consistent header and footer, so that I can navigate the site and understand the branding without each page reinventing its own chrome.

#### Acceptance Criteria

1. THE `Layout` SHALL render a sticky `Navbar` at the top of every page and a `Footer` at the bottom.
2. THE `Layout` SHALL wrap all routes defined in `src/app/router.tsx` so that no page renders without the shared chrome.
3. WHEN the viewport width is below 768px, THE `Navbar` SHALL collapse navigation links and the `UserMenu` into a mobile-friendly layout.
4. THE `Layout` SHALL apply `min-h-screen` to the main content area so the footer stays at the bottom even on short pages.
5. THE `Layout` SHALL preserve the existing `body { @apply bg-gray-50 text-gray-900 min-h-screen; }` baseline from `index.css`.

---

### Requirement 2: Navbar with AWS UG Cbba Branding

**User Story:** As a visitor, I want to see the AWS User Group Cochabamba brand in the header, so that I know which community platform I am on.

#### Acceptance Criteria

1. THE `Navbar` SHALL display the globe emoji icon (`🌍`), the title "AWS User Group Cochabamba", and the subtitle "Registro de Proyectos" in the header logo area.
2. THE `Navbar` SHALL use a dark navy background (`#161d2b`) with white text and AWS orange (`#FF9900`) accents, matching the Registry frontend color scheme.
3. THE `Navbar` SHALL render navigation links: "Proyectos" (links to `/`), "Sitio Principal" (links to `https://cbba.cloud.org.bo/aws`, opens in new tab), and "Eventos" (links to `https://cbba.cloud.org.bo/aws/events`, opens in new tab).
4. THE `Navbar` SHALL be `position: sticky; top: 0` with a z-index that keeps it above page content.
5. WHEN a navigation link is the active route, THE `Navbar` SHALL apply the AWS orange background highlight to that link.
6. THE `Navbar` SHALL render the `UserMenu` component on the right side of the header.

---

### Requirement 3: UserMenu — Unauthenticated State

**User Story:** As an unauthenticated visitor, I want to see "Registrarse" and "Iniciar Sesión" buttons in the header, so that I can quickly access auth flows from any page.

#### Acceptance Criteria

1. WHEN the `Auth_Store` has no authenticated user, THE `UserMenu` SHALL render a "Registrarse" button linking to `/register` and an "Iniciar Sesión" button linking to `/login`.
2. THE `UserMenu` SHALL style "Registrarse" as a ghost button (transparent background, AWS orange border) and "Iniciar Sesión" as a filled button (AWS orange background, dark navy text).
3. WHEN the viewport is below 768px, THE `UserMenu` SHALL stack the two buttons vertically and expand them to full width.

---

### Requirement 4: UserMenu — Authenticated State

**User Story:** As an authenticated user, I want a dropdown menu in the header showing my identity and quick links, so that I can navigate to my profile or log out without leaving the current page.

#### Acceptance Criteria

1. WHEN the `Auth_Store` has an authenticated user, THE `UserMenu` SHALL render an avatar button showing the user's initials (first letter of `firstName` + first letter of `lastName`, or first letter of `email` as fallback).
2. WHEN the avatar button is clicked, THE `UserMenu` SHALL open a dropdown showing the user's full name, email, a "Mi Perfil" link to `/dashboard`, and a "Cerrar Sesión" button.
3. WHEN "Cerrar Sesión" is clicked, THE `UserMenu` SHALL call the `Auth_Store` logout action and redirect to `/`.
4. WHEN the dropdown is open and the user clicks outside it, THE `UserMenu` SHALL close the dropdown.
5. WHEN the dropdown is open and the `Escape` key is pressed, THE `UserMenu` SHALL close the dropdown and return focus to the avatar button.
6. THE `UserMenu` dropdown SHALL support keyboard navigation: `ArrowDown`/`ArrowUp` move focus between items, `Home` focuses the first item, `End` focuses the last item.

---

### Requirement 5: Footer

**User Story:** As a visitor, I want a footer with community links and social icons, so that I can find the main site, events, and contact information from any page.

#### Acceptance Criteria

1. THE `Footer` SHALL display the globe emoji icon, the text "AWS User Group Cochabamba - Registro de Proyectos", and a copyright notice "© 2025 AWS User Group Cochabamba. Todos los derechos reservados."
2. THE `Footer` SHALL render an "Enlaces" section with links to "Sitio Principal" (`https://cbba.cloud.org.bo/aws`), "Eventos" (`https://cbba.cloud.org.bo/aws/events`), and "Contacto" (`https://cbba.cloud.org.bo/aws/contact`), all opening in a new tab.
3. THE `Footer` SHALL render a "Síguenos" section with LinkedIn and Twitter/X social icon links.
4. THE `Footer` SHALL use a dark background (`#333333`) with white text.
5. WHEN the viewport is below 768px, THE `Footer` SHALL stack its columns into a single column layout.

---

### Requirement 6: Existing Pages Wrapped in Layout

**User Story:** As a user, I want all existing pages (Home, Login, Register, Reset Password, Subscribe, Dashboard) to render inside the shared Layout, so that the Navbar and Footer are always visible.

#### Acceptance Criteria

1. THE `HomePage` SHALL render inside the `Layout` shell with the Navbar and Footer visible.
2. THE `LoginPage` SHALL render inside the `Layout` shell, with the login form centered in the main content area.
3. THE `RegisterPage` SHALL render inside the `Layout` shell, with the registration form centered in the main content area.
4. THE `ResetPasswordPage` SHALL render inside the `Layout` shell.
5. THE `SubscribePage` SHALL render inside the `Layout` shell.
6. THE `DashboardPage` SHALL render inside the `Layout` shell.
7. WHEN the `Layout` is applied, THE existing page-level `min-h-screen` centering on `LoginPage` and `RegisterPage` SHALL be adjusted so the centering applies only to the main content area, not the full viewport.

---

### Requirement 7: Accessibility

**User Story:** As a user relying on keyboard navigation or assistive technology, I want the Navbar, UserMenu, and Footer to be fully keyboard-accessible, so that I can use the site without a mouse.

#### Acceptance Criteria

1. THE `Navbar` navigation links SHALL be reachable and activatable via keyboard (`Tab` to focus, `Enter` to activate).
2. THE `UserMenu` avatar button SHALL have `aria-expanded` and `aria-haspopup="menu"` attributes reflecting the dropdown state.
3. THE `UserMenu` dropdown items SHALL have `role="menuitem"` and be focusable via `Tab` and arrow keys.
4. THE `Footer` links SHALL have descriptive `aria-label` attributes where the visible text alone is insufficient.
5. THE `Navbar` SHALL respect `prefers-reduced-motion` by disabling CSS transitions when the user has requested reduced motion.
6. ALL interactive elements in the `Navbar`, `UserMenu`, and `Footer` SHALL have a visible focus indicator with at least 2px contrast outline.
