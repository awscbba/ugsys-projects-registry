import { Outlet, NavLink, Link, useLocation } from 'react-router-dom';
import { Navbar, Footer, UserMenu } from '@ugsys/ui-lib';
import type { RenderLink, LinkItem } from '@ugsys/ui-lib';
import { useAuth } from '../../hooks/useAuth';

/**
 * Router-aware link renderer wrapping react-router-dom v7 NavLink.
 * Passed to Navbar and Footer so they use client-side navigation.
 */
const renderLink: RenderLink = ({ href, children, className, onClick, role, tabIndex, 'aria-current': ariaCurrent }) => (
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

const focusClass =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2';

/** Unauthenticated auth buttons — rendered in the Navbar userMenuSlot */
function AuthButtons() {
  return (
    <div className="flex items-center gap-2 md:gap-3">
      <Link
        to="/register"
        className={`px-3 py-1.5 rounded text-sm font-semibold border-2 border-[#FF9900] text-white bg-transparent hover:bg-[#FF9900]/10 transition-colors motion-reduce:transition-none ${focusClass} md:inline-flex hidden`}
      >
        Registrarse
      </Link>
      <Link
        to="/login"
        className={`px-3 py-1.5 rounded text-sm font-semibold bg-[#FF9900] text-[#161d2b] border-2 border-[#FF9900] hover:opacity-90 transition-opacity motion-reduce:transition-none ${focusClass}`}
      >
        Iniciar Sesión
      </Link>
    </div>
  );
}

export default function Layout() {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();

  const navLinks: LinkItem[] = [
    { label: 'Proyectos', href: '/', active: location.pathname === '/' },
    { label: 'Sitio Principal', href: 'https://cbba.cloud.org.bo/aws', external: true },
    { label: 'Eventos', href: 'https://cbba.cloud.org.bo/aws/events', external: true },
  ];

  const footerLinks: LinkItem[] = [
    { label: 'Sitio Principal', href: 'https://cbba.cloud.org.bo/aws', external: true },
    { label: 'Eventos', href: 'https://cbba.cloud.org.bo/aws/events', external: true },
    { label: 'Contacto', href: 'https://cbba.cloud.org.bo/aws/contact', external: true },
  ];

  const userMenuSlot = isAuthenticated && user ? (
    <UserMenu
      user={{
        name: user.email,
        email: user.email,
        roles: user.roles,
        avatarUrl: undefined,
      }}
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
      <Navbar
        links={navLinks}
        renderLink={renderLink}
        brandSubtitle="Registro de Proyectos"
        userMenuSlot={userMenuSlot}
      />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer
        year={new Date().getFullYear()}
        links={footerLinks}
        renderLink={renderLink}
      />
    </div>
  );
}
