import { render, screen } from '@testing-library/react';
import { MemoryRouter, createMemoryRouter, RouterProvider } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Navbar } from './Navbar';
import { $user } from '../../stores/authStore';

// Prevent module-level side effects
vi.mock('../../services/httpClient', () => ({
  httpClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  setRefreshTokenFn: vi.fn(),
}));
vi.mock('../../services/authService', () => ({
  authService: { login: vi.fn(), register: vi.fn(), refreshToken: vi.fn() },
}));

function renderNavbar(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Navbar />
    </MemoryRouter>
  );
}

beforeEach(() => {
  $user.set(null);
});

afterEach(() => {
  $user.set(null);
  vi.clearAllMocks();
});

// ── Brand ─────────────────────────────────────────────────────────────────────

describe('Navbar — brand', () => {
  it('renders globe emoji', () => {
    renderNavbar();
    expect(screen.getByText('🌍')).toBeInTheDocument();
  });

  it('renders title "AWS User Group Cochabamba"', () => {
    renderNavbar();
    expect(screen.getByRole('heading', { name: /aws user group cochabamba/i })).toBeInTheDocument();
  });

  it('renders subtitle "Registro de Proyectos"', () => {
    renderNavbar();
    expect(screen.getByText(/registro de proyectos/i)).toBeInTheDocument();
  });
});

// ── Navigation links ──────────────────────────────────────────────────────────

describe('Navbar — navigation links', () => {
  it('"Proyectos" NavLink points to /', () => {
    renderNavbar();
    const link = screen.getByRole('link', { name: /proyectos/i });
    expect(link).toHaveAttribute('href', '/');
  });

  it('"Sitio Principal" is an external link with target="_blank"', () => {
    renderNavbar();
    const link = screen.getByRole('link', { name: /sitio principal/i });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('"Eventos" is an external link with target="_blank"', () => {
    renderNavbar();
    const link = screen.getByRole('link', { name: /eventos/i });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });
});

// ── Active link highlight ─────────────────────────────────────────────────────

describe('Navbar — active link highlight', () => {
  it('"Proyectos" gets orange highlight class when at /', () => {
    const router = createMemoryRouter(
      [
        { path: '/', element: <Navbar /> },
        { path: '*', element: <Navbar /> },
      ],
      { initialEntries: ['/'] }
    );
    render(<RouterProvider router={router} />);
    const link = screen.getByRole('link', { name: /proyectos/i });
    expect(link.className).toContain('bg-[#FF9900]');
  });

  it('"Proyectos" does not get orange highlight class when at /other', () => {
    const router = createMemoryRouter(
      [
        { path: '/', element: <Navbar /> },
        { path: '/other', element: <Navbar /> },
      ],
      { initialEntries: ['/other'] }
    );
    render(<RouterProvider router={router} />);
    const link = screen.getByRole('link', { name: /proyectos/i });
    expect(link.className).not.toContain('bg-[#FF9900]');
  });
});

// ── Accessibility ─────────────────────────────────────────────────────────────

describe('Navbar — accessibility', () => {
  it('nav has aria-label "Navegación principal"', () => {
    renderNavbar();
    expect(screen.getByRole('navigation', { name: /navegación principal/i })).toBeInTheDocument();
  });

  it('interactive elements have motion-reduce:transition-none class', () => {
    renderNavbar();
    const link = screen.getByRole('link', { name: /proyectos/i });
    expect(link.className).toContain('motion-reduce:transition-none');
  });
});
