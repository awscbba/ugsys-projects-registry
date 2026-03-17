/**
 * Layout preservation tests — Task 2
 *
 * These tests assert the CORRECT baseline Layout behavior that must be preserved after the fix.
 * They MUST PASS on unfixed code — passing confirms the baseline is stable.
 * They MUST STILL PASS after the fix is applied (Task 3.6 verification).
 *
 * Preservation properties:
 *   - UserMenu receives correct user, adminPanelUrl, onLogout, renderLink props
 *   - Nav contains "Proyectos", "Sitio Principal", "Eventos"
 *   - Logout calls logout() from useAuth
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../Layout';

// ── Mocks ─────────────────────────────────────────────────────────────────────

const logoutMock = vi.fn();

vi.mock('@ugsys/ui-lib', () => ({
  UserMenu: ({
    user,
    onLogout,
    adminPanelUrl,
    profileHref,
  }: {
    user: { name: string; email: string; roles: string[] };
    onLogout: () => void;
    adminPanelUrl: string;
    profileHref: string;
  }) => (
    <div
      data-testid="user-menu"
      data-admin-panel-url={adminPanelUrl}
      data-profile-href={profileHref}
      data-user-email={user.email}
    >
      <button onClick={onLogout} data-testid="logout-btn">
        Logout
      </button>
    </div>
  ),
  Footer: () => <footer>Footer</footer>,
  useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }),
}));

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { sub: 'u1', email: 'dev@example.com', roles: ['member'] },
    isAuthenticated: true,
    isLoading: false,
    logout: logoutMock,
  }),
}));

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('Preservation: Layout nav links', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "Proyectos" nav link', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    expect(screen.getAllByText('Proyectos').length).toBeGreaterThan(0);
  });

  it('renders "Sitio Principal" nav link', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    expect(screen.getAllByText('Sitio Principal').length).toBeGreaterThan(0);
  });

  it('renders "Eventos" nav link', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    expect(screen.getAllByText('Eventos').length).toBeGreaterThan(0);
  });
});

describe('Preservation: UserMenu receives correct props', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('passes adminPanelUrl="https://admin.apps.cloud.org.bo" to UserMenu', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    const userMenu = screen.getByTestId('user-menu');
    expect(userMenu.getAttribute('data-admin-panel-url')).toBe('https://admin.apps.cloud.org.bo');
  });

  it('passes user.email to UserMenu', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    const userMenu = screen.getByTestId('user-menu');
    expect(userMenu.getAttribute('data-user-email')).toBe('dev@example.com');
  });
});

describe('Preservation: logout behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls logout() when UserMenu onLogout is triggered', async () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );

    await userEvent.click(screen.getByTestId('logout-btn'));
    expect(logoutMock).toHaveBeenCalledOnce();
  });
});
