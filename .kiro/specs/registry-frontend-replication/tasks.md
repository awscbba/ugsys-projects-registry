# Implementation Plan: registry-frontend-replication

## Overview

Implement the Registry frontend layout shell and navigation into the `ugsys-projects-registry` React 19 + TypeScript + Vite 6 + Tailwind 4 SPA. Admin functionality is out of scope — it belongs to `ugsys-admin-panel`.

Tasks are ordered by dependency: hook → components → router → tests.

## Tasks

- [x] 1. ~~Add admin types~~ (removed — admin belongs to ugsys-admin-panel)

- [x] 2. ~~Implement domain layer — AdminTab entity and use case~~ (removed — admin belongs to ugsys-admin-panel)

- [x] 3. ~~Add IAdminApi port interface to ports.ts~~ (removed — admin belongs to ugsys-admin-panel)

- [x] 4. Implement useFocusManagement hook
  - Create `web/src/hooks/useFocusManagement.ts` ported from `Registry/registry-frontend/src/hooks/useFocusManagement.ts`
  - `useRef<HTMLElement>(null)` for `modalRef`; `useRef<HTMLElement | null>(null)` for `previousFocusRef`
  - On `isOpen === true`: store `document.activeElement` in `previousFocusRef`; `setTimeout(() => modalRef.current?.focus(), 100)`; return cleanup that calls `clearTimeout`
  - On `isOpen === false`: if `previousFocusRef.current` exists and `document.body.contains(it)`, call `.focus()`; set `previousFocusRef.current = null`
  - SSR guard: `if (typeof document === 'undefined') return` at top of effect
  - Return `{ modalRef }`
  - _Requirements: 7.2, 7.3, 7.6_

- [x] 5. Implement layout components — Footer and Navbar
  - Create `web/src/components/layout/Footer.tsx`: static component; brand text "AWS User Group Cochabamba - Registro de Proyectos"; copyright "© 2025 AWS User Group Cochabamba. Todos los derechos reservados."; "Enlaces" section with Sitio Principal, Eventos, Contacto links (all `target="_blank" rel="noopener noreferrer"`); "Síguenos" section with LinkedIn and Twitter/X links with `aria-label`; `bg-[#333333] text-white`; `grid-cols-1 md:grid-cols-3`
  - Create `web/src/components/layout/Navbar.tsx`: `sticky top-0 z-50 bg-[#161d2b] text-white shadow-sm`; logo area with globe emoji, "AWS User Group Cochabamba" h1, "Registro de Proyectos" subtitle in `text-[#FF9900]`; `<NavLink>` for "Proyectos" (`/`) with active class `bg-[#FF9900] text-[#161d2b]`; external links for "Sitio Principal" and "Eventos"; `motion-reduce:transition-none` on all transitions; `focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2` on all interactive elements; renders `<UserMenu />` on the right
  - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4, 5.5, 7.1, 7.5, 7.6_

- [x] 6. Implement UserMenu component
  - Create `web/src/components/layout/UserMenu.tsx`
  - Read auth state via `useAuth()`; manage `isOpen` with `useState(false)`
  - Use `useFocusManagement(isOpen)` — attach `modalRef` to the dropdown container div
  - Unauthenticated branch: "Registrarse" ghost button (`border-[#FF9900]`) linking to `/register`; "Iniciar Sesión" filled button (`bg-[#FF9900] text-[#161d2b]`) linking to `/login`; stack vertically on mobile
  - Authenticated branch: avatar button showing initials (first letter of each name word, fallback to first letter of email); `aria-expanded={isOpen}`, `aria-haspopup="menu"` on avatar button; dropdown with `role="menu"`, items with `role="menuitem"`; show user full name + email; "Mi Perfil" link to `/dashboard`; "Cerrar Sesión" button calls logout + `navigate('/')`
  - No "Panel Admin" link — admin access is handled by `ugsys-admin-panel`
  - Outside click: `useEffect` adds `mousedown` listener on `document`; closes if click target is outside container ref
  - Keyboard: `Escape` closes and returns focus to avatar button; `ArrowDown`/`ArrowUp`/`Home`/`End` navigate menu items
  - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 7.2, 7.3, 7.6_

- [x] 7. Implement Layout component and update router
  - Create `web/src/components/layout/Layout.tsx`: `<div className="flex flex-col min-h-screen">` wrapping `<Navbar />`, `<main className="flex-1"><Outlet /></main>`, `<Footer />`
  - Modify `web/src/app/router.tsx`: wrap all existing routes in a single layout route `{ element: <Layout />, children: [...] }`; import `Layout`
  - Adjust `LoginPage` and `RegisterPage` centering: replace any `min-h-screen` flex centering with `flex-1` so centering applies only within the main content area
  - _Requirements: 1.1, 1.2, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [x] 8. Write useFocusManagement tests
  - Create `web/src/hooks/useFocusManagement.test.ts` matching the depth of `Registry/registry-frontend/src/hooks/__tests__/useFocusManagement.test.ts`
  - Test groups (20+ cases total):
    - `Initial State`: returns `modalRef`; does not change focus when closed
    - `Focus Storage`: stores previously focused element on open; handles multiple focus changes before open
    - `Focus Restoration`: restores focus on close (P7); handles element removed from DOM; clears ref after restoration
    - `Modal Focus`: moves focus to modal after delay; handles missing ref; delays focus to allow render
    - `Multiple Open/Close Cycles`: correct across multiple cycles; handles rapid open/close
    - `Accessibility Compliance`: WCAG 2.1 — focus moves to modal on open, returns to trigger on close; works with `tabIndex` elements
    - `SSR Compatibility`: no crash when `document` is undefined (P8)
    - `Memory Leak Prevention`: cleans up timeout on unmount (P9); cleans up on rapid `isOpen` change
    - `Edge Cases`: body as active element; null `activeElement`; non-focusable modal element
  - _Requirements: 7.2, 7.3, 7.6_

- [x] 9. Write UserMenu tests
  - Create `web/src/components/layout/UserMenu.test.tsx`
  - Set auth state via `$user.set(...)` — no module mocking of the store
  - Test unauthenticated: renders "Registrarse" link to `/register` and "Iniciar Sesión" link to `/login`; no avatar rendered (P2)
  - Test authenticated: renders avatar button with correct initials; dropdown hidden initially (P3)
  - Test dropdown open: clicking avatar opens dropdown; no "Panel Admin" link present (admin is ugsys-admin-panel's concern)
  - Test outside click: `mousedown` outside container closes dropdown (P4)
  - Test Escape key: closes dropdown and returns focus to avatar button (P5)
  - Test initials fallback: empty `full_name` → first char of email uppercased (P6)
  - PBT with `fast-check`: for any `{ email, full_name }`, initials are always 1–2 uppercase characters
  - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 10. Write Navbar tests
  - Create `web/src/components/layout/Navbar.test.tsx`: renders globe emoji, title, subtitle; "Proyectos" link points to `/`; external links have `target="_blank"`; active link gets orange highlight class; `motion-reduce:transition-none` present on animated elements
  - _Requirements: 1.1, 2.3, 2.5_

- [x] 11. Final checkpoint — typecheck, lint, and tests
  - Run `npm run typecheck` inside `web/` — zero errors
  - Run `npm run lint` inside `web/` — zero errors
  - Run `npm run test:run` inside `web/` — all tests pass
  - Run `npm run build` inside `web/` — build succeeds

## Notes

- No admin functionality in this SPA — admin belongs to `ugsys-admin-panel`
- `useFocusManagement` is the single source of WCAG 2.1 focus management — used by `UserMenu`, available for any future modal/dropdown
- No new npm dependencies introduced — existing stack is sufficient
