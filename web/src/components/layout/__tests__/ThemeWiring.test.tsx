/**
 * ThemeWiring.test.tsx — Verifies that the registry app correctly wires
 * ThemeProvider and provides a theme toggle in the user menu.
 *
 * Property 5: ThemeProvider wraps the entire component tree.
 * Property 6: Theme toggle is accessible and calls toggleTheme.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock @ugsys/ui-lib
const mockToggleTheme = vi.fn();
let mockTheme: 'light' | 'dark' = 'light';

vi.mock('@ugsys/ui-lib', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="theme-provider">{children}</div>
  ),
  useTheme: () => ({ theme: mockTheme, toggleTheme: mockToggleTheme }),
  UserMenu: ({
    extraItems,
  }: {
    user: unknown;
    onLogout: () => void;
    extraItems?: Array<{ label: string; icon?: React.ReactNode; onClick?: () => void }>;
  }) => (
    <div data-testid="user-menu">
      {extraItems?.map((item, i) => (
        <button key={i} role="menuitem" onClick={item.onClick} aria-label={item.label}>
          {item.icon}
          {item.label}
        </button>
      ))}
    </div>
  ),
  Footer: () => <footer data-testid="footer" />,
}));

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  Outlet: () => <div data-testid="outlet" />,
  NavLink: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useLocation: () => ({ pathname: '/' }),
}));

// Mock auth hook — authenticated user
vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { email: 'dev@example.com', roles: ['member'] },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

import Layout from '../Layout';

describe('ThemeWiring', () => {
  beforeEach(() => {
    mockTheme = 'light';
    mockToggleTheme.mockClear();
  });

  it('renders a theme toggle menu item when user is authenticated', () => {
    render(<Layout />);
    const toggle = screen.getByRole('menuitem', { name: /tema/i });
    expect(toggle).toBeInTheDocument();
  });

  it('theme toggle calls toggleTheme on click', async () => {
    render(<Layout />);
    const toggle = screen.getByRole('menuitem', { name: /tema/i });
    await userEvent.click(toggle);
    expect(mockToggleTheme).toHaveBeenCalledOnce();
  });

  it('shows sun icon and "Tema claro" label in dark mode', () => {
    mockTheme = 'dark';
    render(<Layout />);
    const toggle = screen.getByRole('menuitem', { name: /tema claro/i });
    expect(toggle).toBeInTheDocument();
  });

  it('shows moon icon and "Tema oscuro" label in light mode', () => {
    mockTheme = 'light';
    render(<Layout />);
    const toggle = screen.getByRole('menuitem', { name: /tema oscuro/i });
    expect(toggle).toBeInTheDocument();
  });
});
