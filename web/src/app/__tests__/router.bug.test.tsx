/**
 * Bug condition exploration tests — Task 1
 *
 * These tests assert the BUGGY state and are INTENTIONALLY SKIPPED after the fix.
 * They served their purpose: confirming the bug existed before the fix was applied.
 *
 * History:
 *   - Written on unfixed code: all 3 PASSED (confirmed bug existed)
 *   - After fix applied (Task 3.5): all 3 FAILED (confirmed fix removed the bug)
 *   - Skipped permanently so CI stays green while preserving the documentation
 *
 * Bug condition C(X):
 *   dashboardRouteExists  = router contains path="/dashboard" rendering DashboardPage
 *   profileHrefIsLocal    = Layout passes profileHref="/dashboard" to UserMenu
 *   loginRedirectIsWrong  = LoginForm fallback redirect is "/dashboard"
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

// ── Mock heavy dependencies ───────────────────────────────────────────────────

vi.mock('@ugsys/ui-lib', () => ({
  UserMenu: ({ profileHref }: { profileHref: string }) => (
    <div data-testid="user-menu" data-profile-href={profileHref}>
      UserMenu
    </div>
  ),
  Footer: () => <footer>Footer</footer>,
  LoginCard: ({
    title,
    emailLabel = 'Email',
    passwordLabel = 'Password',
    submitLabel = 'Sign in',
    loadingLabel = 'Signing in…',
    email,
    password,
    isLoading,
    error,
    onEmailChange,
    onPasswordChange,
    onSubmit,
    footer,
  }: {
    title: string;
    emailLabel?: string;
    passwordLabel?: string;
    submitLabel?: string;
    loadingLabel?: string;
    email: string;
    password: string;
    isLoading: boolean;
    error: string | null;
    onEmailChange: (v: string) => void;
    onPasswordChange: (v: string) => void;
    onSubmit: (e: React.FormEvent) => void;
    footer?: React.ReactNode;
  }) => (
    <form onSubmit={onSubmit} aria-label={title}>
      {error && <p role="alert">{error}</p>}
      <label>
        {emailLabel}
        <input type="email" value={email} onChange={(e) => onEmailChange(e.target.value)} />
      </label>
      <label>
        {passwordLabel}
        <input type="password" value={password} onChange={(e) => onPasswordChange(e.target.value)} />
      </label>
      <button type="submit" disabled={isLoading}>
        {isLoading ? loadingLabel : submitLabel}
      </button>
      {footer}
    </form>
  ),
}));

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { sub: 'u1', email: 'dev@example.com', roles: ['member'] },
    isAuthenticated: true,
    isLoading: false,
    logout: vi.fn(),
  }),
}));

vi.mock('../../stores/authStore', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  $user: { subscribe: vi.fn(() => () => {}), get: () => null },
  $isLoading: { subscribe: vi.fn(() => () => {}), get: () => false },
  $isAuthenticated: { subscribe: vi.fn(() => () => {}), get: () => false },
}));

// ── Test 1: Router contains /dashboard rendering DashboardPage ────────────────

describe.skip('Bug condition: /dashboard route renders DashboardPage', () => {
  it('router.routes includes a route with path="/dashboard"', async () => {
    const { router } = await import('../router');

    // The router wraps all routes under a Layout parent — children are in the first route
    const children = router.routes[0]?.children ?? [];
    const dashboardRoute = children.find((r) => r.path === '/dashboard');

    // On UNFIXED code: dashboardRoute exists → PASSES (confirms bug)
    // After fix: dashboardRoute is a Navigate redirect, not DashboardPage → FAILS
    expect(dashboardRoute).toBeDefined();

    // Verify it renders DashboardPage (not a Navigate redirect)
    // We check the element type name — Navigate has displayName 'Navigate'
    // Cast through unknown since react-router's AgnosticRouteObject doesn't expose element in its type
    const routeWithElement = dashboardRoute as unknown as { element?: React.ReactElement };
    const element = routeWithElement.element;
    expect(element?.type).not.toBeUndefined();
    const typeName =
      typeof element?.type === 'function'
        ? ((element.type as { name?: string; displayName?: string }).name ??
          (element.type as { name?: string; displayName?: string }).displayName)
        : String(element?.type);
    // On UNFIXED code: typeName is "DashboardPage" → PASSES
    // After fix: typeName is "Navigate" → FAILS
    expect(typeName).toBe('DashboardPage');
  });
});

// ── Test 2: Layout passes profileHref="/dashboard" to UserMenu ────────────────

describe.skip('Bug condition: Layout passes profileHref="/dashboard" to UserMenu', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('UserMenu receives profileHref="/dashboard" (local route, not external URL)', async () => {
    const { default: Layout } = await import('../../components/layout/Layout');

    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );

    const userMenu = screen.getByTestId('user-menu');
    // On UNFIXED code: profileHref="/dashboard" → PASSES (confirms bug)
    // After fix: profileHref="https://profile.apps.cloud.org.bo" → FAILS
    expect(userMenu.getAttribute('data-profile-href')).toBe('/dashboard');
  });
});

// ── Test 3: LoginForm navigates to /dashboard on success with no redirect param ─

describe.skip('Bug condition: LoginForm fallback redirect is "/dashboard"', () => {
  it('navigates to "/dashboard" after login when no ?redirect= param is present', async () => {
    const navigateMock = vi.fn();
    vi.doMock('react-router-dom', async (importOriginal) => {
      const actual = await importOriginal<typeof import('react-router-dom')>();
      return {
        ...actual,
        useNavigate: () => navigateMock,
        useSearchParams: () => [new URLSearchParams(), vi.fn()],
        Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
          <a href={to}>{children}</a>
        ),
      };
    });

    const { login: loginMock } = await import('../../stores/authStore');
    (loginMock as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

    const { LoginForm } = await import('../../components/auth/LoginForm');

    render(
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText(/correo/i), 'dev@example.com');
    await userEvent.type(screen.getByLabelText(/contraseña/i), 'password123');
    await userEvent.click(screen.getByRole('button', { name: /iniciar sesión/i }));

    // On UNFIXED code: navigate called with "/dashboard" → PASSES (confirms bug)
    // After fix: navigate called with "/" → FAILS
    expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true });
  });
});
