# Design Document

## Overview

This design replicates the Registry Astro frontend's layout shell and navigation into the `ugsys-projects-registry` React 19 + TypeScript + Vite 6 + Tailwind 4 SPA. It adapts Astro-specific patterns (slots, `client:only`) to React Router v6 layout routes, integrates with the Nanostores-based auth store already in place, and applies `useFocusManagement` for WCAG 2.1 focus management.

Admin functionality is explicitly out of scope — it belongs to the dedicated `ugsys-admin-panel` service.

No new npm dependencies are introduced. The existing stack (React 19, React Router v6, Nanostores + `@nanostores/react`, Tailwind 4, Vite 6, `@testing-library/react`, `vitest`, `fast-check`) is sufficient for all requirements.

---

## Architecture

### Component Tree

```
App
└── RouterProvider
    └── Layout                          (React Router layout route)
        ├── Navbar
        │   ├── NavBrand                (logo + title + subtitle)
        │   ├── NavLinks                (active-link detection via useLocation)
        │   └── UserMenu
        │       ├── AuthButtons         (unauthenticated branch)
        │       └── AvatarDropdown      (authenticated branch)
        ├── <Outlet />                  (page content)
        └── Footer
            ├── FooterBrand
            ├── FooterLinks
            └── FooterSocial
```

### Router Structure

React Router v6 layout routes wrap all pages in `Layout` without repeating chrome per-page.

```
/                   → Layout > HomePage
/login              → Layout > LoginPage
/register           → Layout > RegisterPage
/reset-password/:t  → Layout > ResetPasswordPage
/subscribe/:id      → Layout > SubscribePage
/dashboard          → Layout > DashboardPage
```

---

## File Structure

### New files

```
web/src/
├── components/
│   └── layout/
│       ├── Layout.tsx              # Layout shell — Navbar + Outlet + Footer
│       ├── Navbar.tsx              # Sticky header with logo, nav links, UserMenu
│       ├── UserMenu.tsx            # Auth-aware header dropdown
│       └── Footer.tsx              # Footer with links and social icons
└── hooks/
    └── useFocusManagement.ts       # WCAG 2.1 focus management (ported from Registry)
```

### Modified files

```
web/src/app/router.tsx              # Add layout route wrapper
```

---

## Component Design

### Layout.tsx

```tsx
import { Outlet } from 'react-router-dom';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';

export default function Layout() {
  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
```

`flex-col min-h-screen` on the wrapper + `flex-1` on `<main>` ensures the footer is always pushed to the bottom regardless of page content height (Requirement 1.4).

### Navbar.tsx

- Background: `bg-[#161d2b]` (dark navy), `text-white`
- Sticky: `sticky top-0 z-50 shadow-sm`
- Logo area: globe emoji + "AWS User Group Cochabamba" (h1) + "Registro de Proyectos" (subtitle in `text-[#FF9900]`)
- Nav links: `Proyectos` → `/` (internal, `<NavLink>`), `Sitio Principal` → external, `Eventos` → external
- Active link: `useLocation()` + React Router `<NavLink>` with `className` callback — active link gets `bg-[#FF9900] text-[#161d2b]`
- `prefers-reduced-motion`: `motion-reduce:transition-none` on all transition classes
- Focus indicator: `focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2`

### UserMenu.tsx

Ported from `Registry/registry-frontend/src/components/UserMenu.tsx` with these adaptations:

| Registry pattern | SPA adaptation |
|---|---|
| `useAuthStore()` (Registry hook) | `useAuth()` from `src/hooks/useAuth.ts` |
| `useToastStore().showSuccessToast()` | `toastStore` from `src/stores/toastStore.ts` |
| `styled-jsx` (`<style jsx>`) | Tailwind utility classes |
| `user.isAdmin` (boolean field) | removed — no admin link in this SPA |
| `window.location.href = '/dashboard'` | `useNavigate()` from React Router |
| `menuRef = useRef<HTMLElement>` | `menuRef = useRef<HTMLDivElement>` |
| Focus management inline | `useFocusManagement(isOpen)` hook |

All keyboard accessibility from the original is preserved: Escape closes and returns focus to trigger, ArrowDown/Up/Home/End navigate items, Enter/Space activate items. `aria-expanded`, `aria-haspopup="menu"`, `role="menu"`, `role="menuitem"` attributes are all present.

The "Panel Admin" link is intentionally omitted — admin access is handled by `ugsys-admin-panel`.

### Footer.tsx

Static component. Text adapted for this service:
- Brand: "AWS User Group Cochabamba - Registro de Proyectos"
- Copyright: "© 2025 AWS User Group Cochabamba. Todos los derechos reservados."
- Background: `bg-[#333333] text-white`
- Responsive: `grid-cols-1 md:grid-cols-3`
- Social links have `aria-label` attributes (LinkedIn, Twitter/X)

---

## Custom Hooks

### useFocusManagement.ts

Ported directly from `Registry/registry-frontend/src/hooks/useFocusManagement.ts`. Implements WCAG 2.1 focus management for any modal/dropdown:

```ts
export function useFocusManagement(isOpen: boolean): { modalRef: React.RefObject<HTMLElement> }
```

- Stores `document.activeElement` before opening
- Moves focus to `modalRef.current` after a 100ms delay (allows render to complete)
- Restores focus to the stored element on close, with `document.body.contains()` guard
- SSR-safe: `typeof document === 'undefined'` guard
- Cleans up the timeout on unmount or rapid open/close (no memory leaks)

Used by `UserMenu.tsx` to manage focus on the avatar dropdown.

---

## Router Changes

```tsx
// src/app/router.tsx
import Layout from '@/components/layout/Layout';

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/reset-password/:token', element: <ResetPasswordPage /> },
      { path: '/subscribe/:projectId', element: <SubscribePage /> },
      { path: '/dashboard', element: <DashboardPage /> },
    ],
  },
]);
```

---

## Styling Approach

Tailwind 4 utility classes throughout. Registry CSS custom properties mapped to Tailwind arbitrary values:

| Registry CSS var | Value | Tailwind usage |
|---|---|---|
| `--primary-color` | `#161d2b` | `bg-[#161d2b]`, `text-[#161d2b]` |
| `--secondary-color` | `#FF9900` | `bg-[#FF9900]`, `text-[#FF9900]`, `border-[#FF9900]` |
| `--dark-color` | `#333333` | `bg-[#333333]` |
| `--focus-color` | `#4A90E2` | `outline-[#4A90E2]` |

The existing `index.css` `body { @apply bg-gray-50 text-gray-900 min-h-screen; }` is preserved unchanged.

`prefers-reduced-motion` handled via `motion-reduce:transition-none motion-reduce:animate-none` on all animated elements.

---

## Correctness Properties

**P1 — Layout wraps all routes**: Every route in `router.tsx` is a child of the layout route. No page renders without `<Navbar />` and `<Footer />`.

**P2 — UserMenu unauthenticated state**: When `$user` is `null`, `UserMenu` renders exactly two links — one to `/register` and one to `/login`. No avatar, no dropdown.

**P3 — UserMenu authenticated state**: When `$user` is set, `UserMenu` renders the avatar button with correct initials. Dropdown is hidden until button is clicked.

**P4 — Dropdown closes on outside click**: A `mousedown` event on an element outside the `UserMenu` container sets `isOpen` to `false`.

**P5 — Dropdown closes on Escape**: A `keydown` event with `key === 'Escape'` sets `isOpen` to `false` and returns focus to the avatar button.

**P6 — Initials fallback**: When `full_name` is absent or empty, initials fall back to the first character of `user.email` uppercased.

**P7 — useFocusManagement restores focus**: When `isOpen` transitions from `true` to `false`, focus is restored to the element that was active when `isOpen` became `true`, provided that element is still in the DOM.

**P8 — useFocusManagement SSR-safe**: The hook does not access `document` when `typeof document === 'undefined'`.

**P9 — useFocusManagement no memory leak**: When the component unmounts while `isOpen` is `true`, the pending focus timeout is cleared and no state update occurs.

---

## Test Plan

All tests follow the AAA pattern (Arrange / Act / Assert). Auth store state is set directly via `$user.set(...)` — no module mocking of the store.

| Test file | Properties covered | Test type |
|---|---|---|
| `hooks/useFocusManagement.test.ts` | P7, P8, P9 — focus storage, restoration, SSR, memory leak, rapid cycles | Unit (20+ cases) |
| `components/layout/UserMenu.test.tsx` | P2, P3, P4, P5, P6, P7 | Unit + PBT |
| `components/layout/Navbar.test.tsx` | P1 (Navbar renders), active link, external links | Unit |

### useFocusManagement.test.ts — required test groups

- `Initial State` — returns modalRef, does not change focus when closed
- `Focus Storage` — stores previously focused element on open, handles multiple focus changes
- `Focus Restoration` — restores on close, handles element removed from DOM, clears ref after restoration
- `Modal Focus` — moves focus to modal, handles missing ref, delays focus to allow render
- `Multiple Open/Close Cycles` — correct across cycles, handles rapid open/close
- `Accessibility Compliance` — WCAG 2.1 requirements, elements with tabIndex
- `SSR Compatibility` — no crash when document is undefined
- `Memory Leak Prevention` — cleans up timeout on unmount, cleans up on rapid isOpen change
- `Edge Cases` — body as active element, null activeElement, non-focusable modal element

### PBT properties (using `fast-check`)

- `UserMenu` initials: for any `{ email, full_name }` combination, initials are always 1–2 uppercase characters
