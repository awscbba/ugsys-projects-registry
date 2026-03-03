import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';
import { UserMenu } from './UserMenu';
import { $user } from '../../stores/authStore';
import type { AuthUser } from '../../types/auth';

// Prevent module-level side effects from httpClient / authService
vi.mock('../../services/httpClient', () => ({
  httpClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  setRefreshTokenFn: vi.fn(),
}));
vi.mock('../../services/authService', () => ({
  authService: { login: vi.fn(), register: vi.fn(), refreshToken: vi.fn() },
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return { sub: 'sub-123', email: 'dev@example.com', roles: [], ...overrides };
}

function renderMenu() {
  return render(
    <MemoryRouter>
      <UserMenu />
    </MemoryRouter>
  );
}

// ── Setup / Teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  $user.set(null);
});

afterEach(() => {
  $user.set(null);
  vi.clearAllMocks();
});

// ── Unauthenticated ───────────────────────────────────────────────────────────

describe('UserMenu — unauthenticated', () => {
  it('renders "Registrarse" link pointing to /register (P2)', () => {
    renderMenu();
    const link = screen.getByRole('link', { name: /registrarse/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/register');
  });

  it('renders "Iniciar Sesión" link pointing to /login', () => {
    renderMenu();
    const link = screen.getByRole('link', { name: /iniciar sesión/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/login');
  });

  it('does not render avatar button when unauthenticated', () => {
    renderMenu();
    expect(screen.queryByRole('button', { name: /menú de usuario/i })).not.toBeInTheDocument();
  });
});

// ── Authenticated — initial state ─────────────────────────────────────────────

describe('UserMenu — authenticated initial state', () => {
  it('renders avatar button with correct initials (P3)', () => {
    act(() => $user.set(makeUser({ email: 'dev@example.com' })));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent('D');
  });

  it('dropdown is hidden initially', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('avatar button has aria-expanded=false initially', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    expect(btn).toHaveAttribute('aria-expanded', 'false');
  });
});

// ── Dropdown open ─────────────────────────────────────────────────────────────

describe('UserMenu — dropdown open', () => {
  it('clicking avatar opens dropdown', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));
    expect(screen.getByRole('menu')).toBeInTheDocument();
  });

  it('avatar button has aria-expanded=true when open', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'true');
  });

  it('dropdown shows user email', () => {
    act(() => $user.set(makeUser({ email: 'dev@example.com' })));
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));
    expect(screen.getByText('dev@example.com')).toBeInTheDocument();
  });

  it('dropdown contains "Mi Perfil" link', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));
    expect(screen.getByRole('menuitem', { name: /mi perfil/i })).toBeInTheDocument();
  });

  it('dropdown contains "Cerrar Sesión" button', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));
    expect(screen.getByRole('menuitem', { name: /cerrar sesión/i })).toBeInTheDocument();
  });

  it('no "Panel Admin" link present — admin belongs to ugsys-admin-panel', () => {
    act(() => $user.set(makeUser({ roles: ['admin'] })));
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));
    expect(screen.queryByText(/panel admin/i)).not.toBeInTheDocument();
  });

  it('clicking avatar again closes dropdown', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    fireEvent.click(btn);
    expect(screen.getByRole('menu')).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});

// ── Outside click ─────────────────────────────────────────────────────────────

describe('UserMenu — outside click (P4)', () => {
  it('mousedown outside container closes dropdown', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));
    expect(screen.getByRole('menu')).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('mousedown inside container does not close dropdown', () => {
    act(() => $user.set(makeUser()));
    const { container } = renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));

    const menuContainer = container.firstChild as HTMLElement;
    fireEvent.mouseDown(menuContainer);
    expect(screen.getByRole('menu')).toBeInTheDocument();
  });
});

// ── Keyboard — Escape (P5) ────────────────────────────────────────────────────

describe('UserMenu — Escape key (P5)', () => {
  it('Escape closes dropdown', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /menú de usuario/i }));
    expect(screen.getByRole('menu')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('Escape returns focus to avatar button', () => {
    act(() => $user.set(makeUser()));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    fireEvent.click(btn);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.activeElement).toBe(btn);
  });
});

// ── Initials (P6) ─────────────────────────────────────────────────────────────

describe('UserMenu — initials (P6)', () => {
  it('uses first char of email uppercased when email starts with lowercase', () => {
    act(() => $user.set(makeUser({ email: 'alice@example.com' })));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    expect(btn).toHaveTextContent('A');
  });

  it('uses first char of email uppercased when email starts with uppercase', () => {
    act(() => $user.set(makeUser({ email: 'Bob@example.com' })));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    expect(btn).toHaveTextContent('B');
  });

  it('initials are always a single uppercase character', () => {
    act(() => $user.set(makeUser({ email: 'zara@example.com' })));
    renderMenu();
    const btn = screen.getByRole('button', { name: /menú de usuario/i });
    const text = btn.querySelector('span')?.textContent ?? '';
    expect(text).toHaveLength(1);
    expect(text).toBe(text.toUpperCase());
  });

  // PBT: for any email, initials are always 1 uppercase character
  it('PBT: for any email, initials are always 1 uppercase character', async () => {
    await fc.assert(
      fc.asyncProperty(fc.emailAddress(), async (email) => {
        act(() => $user.set(makeUser({ email })));
        const { unmount } = renderMenu();

        const btn = screen.getByRole('button', { name: /menú de usuario/i });
        const span = btn.querySelector('span');
        const text = span?.textContent ?? '';

        expect(text).toHaveLength(1);
        expect(text).toBe(text.toUpperCase());

        unmount();
        act(() => $user.set(null));
      }),
      { numRuns: 50 }
    );
  });
});
