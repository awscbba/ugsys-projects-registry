import { useState } from 'react';
import { Outlet, NavLink, Link, useLocation } from 'react-router-dom';
import { Footer, UserMenu } from '@ugsys/ui-lib';
import type { RenderLink, LinkItem } from '@ugsys/ui-lib';
import { useAuth } from '../../hooks/useAuth';

const renderLink: RenderLink = (props) => {
  const { href, children, className, onClick, role, tabIndex, 'aria-current': ariaCurrent } = props;
  return (
    <NavLink
      to={href}
      className={className}
      onClick={onClick}
      role={role}
      tabIndex={tabIndex}
      aria-current={ariaCurrent}
    >
      {children}
    </NavLink>
  );
};

const focusClass =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2';

function AuthButtons() {
  return (
    <div className="flex items-center gap-2">
      <Link
        to="/register"
        className={`hidden sm:inline-flex px-3 py-1.5 rounded text-sm font-semibold border border-[#FF9900] text-[#FF9900] bg-transparent hover:bg-[#FF9900]/10 transition-colors ${focusClass}`}
      >
        Registrarse
      </Link>
      <Link
        to="/login"
        className={`px-3 py-1.5 rounded text-sm font-semibold bg-[#FF9900] text-[#161d2b] hover:bg-[#ffb84d] transition-colors ${focusClass}`}
      >
        Iniciar Sesión
      </Link>
    </div>
  );
}

interface AppNavbarProps {
  links: { label: string; href: string; active: boolean; external?: boolean }[];
  userMenuSlot: React.ReactNode;
}

function AppNavbar({ links, userMenuSlot }: AppNavbarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header
      className="sticky top-0 z-50"
      style={{
        backgroundColor: '#1e2738',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        backdropFilter: 'blur(12px)',
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex-shrink-0">
            <span className="text-white font-bold text-base leading-tight">
              AWS User Group Cochabamba
            </span>
            <span className="block text-[#FF9900] text-xs font-medium">Registro de Proyectos</span>
          </div>

          {/* Desktop nav links — always visible on md+ */}
          <nav aria-label="Main navigation" className="hidden md:flex items-center gap-1">
            {links.map((link) =>
              link.external ? (
                <a
                  key={link.href}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-2 rounded text-sm font-medium text-white/70 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  {link.label}
                </a>
              ) : (
                <NavLink
                  key={link.href}
                  to={link.href}
                  className={({ isActive }) =>
                    `px-3 py-2 rounded text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-[#FF9900]/15 text-[#FF9900]'
                        : 'text-white/70 hover:text-white hover:bg-white/[0.06]'
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              )
            )}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-3">
            {/* User menu / auth buttons — desktop */}
            <div className="hidden md:block">{userMenuSlot}</div>

            {/* Hamburger — mobile only */}
            <button
              type="button"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileOpen}
              aria-controls="mobile-menu"
              onClick={() => setMobileOpen((v) => !v)}
              className="md:hidden p-2 rounded text-white/60 hover:text-white hover:bg-white/[0.06] transition-colors"
            >
              {mobileOpen ? (
                <svg
                  aria-hidden="true"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              ) : (
                <svg
                  aria-hidden="true"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <nav
          id="mobile-menu"
          aria-label="Mobile navigation"
          className="md:hidden px-4 py-3 flex flex-col gap-1 border-t border-white/[0.07]"
          style={{ backgroundColor: '#1e2738' }}
        >
          {links.map((link) =>
            link.external ? (
              <a
                key={link.href}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-2 rounded text-sm font-medium text-white/70 hover:text-white hover:bg-white/[0.06] transition-colors"
              >
                {link.label}
              </a>
            ) : (
              <NavLink
                key={link.href}
                to={link.href}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `px-3 py-2 rounded text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-[#FF9900]/15 text-[#FF9900]'
                      : 'text-white/70 hover:text-white hover:bg-white/[0.06]'
                  }`
                }
              >
                {link.label}
              </NavLink>
            )
          )}
          <div className="pt-2 border-t border-white/[0.07]">{userMenuSlot}</div>
        </nav>
      )}
    </header>
  );
}

export default function Layout() {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();

  const navLinks = [
    { label: 'Proyectos', href: '/', active: location.pathname === '/' },
    {
      label: 'Sitio Principal',
      href: 'https://cbba.cloud.org.bo/aws',
      active: false,
      external: true,
    },
    {
      label: 'Eventos',
      href: 'https://cbba.cloud.org.bo/aws/events',
      active: false,
      external: true,
    },
  ];

  const footerLinks: LinkItem[] = [
    { label: 'Sitio Principal', href: 'https://cbba.cloud.org.bo/aws', external: true },
    { label: 'Eventos', href: 'https://cbba.cloud.org.bo/aws/events', external: true },
    { label: 'Contacto', href: 'https://cbba.cloud.org.bo/aws/contact', external: true },
  ];

  const userMenuSlot =
    isAuthenticated && user ? (
      <UserMenu
        user={{ name: user.email, email: user.email, roles: user.roles, avatarUrl: undefined }}
        onLogout={logout}
        adminPanelUrl="https://admin.apps.cloud.org.bo"
        profileHref="/dashboard"
        renderLink={renderLink}
      />
    ) : (
      <AuthButtons />
    );

  return (
    <div className="flex flex-col min-h-screen">
      <AppNavbar links={navLinks} userMenuSlot={userMenuSlot} />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer year={new Date().getFullYear()} links={footerLinks} renderLink={renderLink} />
    </div>
  );
}
