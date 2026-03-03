import { NavLink } from 'react-router-dom';
import { UserMenu } from './UserMenu';

const focusClass =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2';

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 bg-[#161d2b] text-white shadow-sm">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-2 shrink-0">
          <span aria-hidden="true" className="text-xl">🌍</span>
          <div>
            <h1 className="text-sm font-bold leading-tight">AWS User Group Cochabamba</h1>
            <p className="text-xs text-[#FF9900] leading-tight">Registro de Proyectos</p>
          </div>
        </div>

        {/* Nav links */}
        <nav aria-label="Navegación principal" className="hidden md:flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm font-medium transition-colors motion-reduce:transition-none ${focusClass} ${
                isActive
                  ? 'bg-[#FF9900] text-[#161d2b]'
                  : 'text-gray-200 hover:text-white hover:bg-white/10'
              }`
            }
          >
            Proyectos
          </NavLink>
          <a
            href="https://cbba.cloud.org.bo/aws"
            target="_blank"
            rel="noopener noreferrer"
            className={`px-3 py-1.5 rounded text-sm font-medium text-gray-200 hover:text-white hover:bg-white/10 transition-colors motion-reduce:transition-none ${focusClass}`}
          >
            Sitio Principal
          </a>
          <a
            href="https://cbba.cloud.org.bo/aws/events"
            target="_blank"
            rel="noopener noreferrer"
            className={`px-3 py-1.5 rounded text-sm font-medium text-gray-200 hover:text-white hover:bg-white/10 transition-colors motion-reduce:transition-none ${focusClass}`}
          >
            Eventos
          </a>
        </nav>

        {/* User menu */}
        <UserMenu />
      </div>
    </header>
  );
}
