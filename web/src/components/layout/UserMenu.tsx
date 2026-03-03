import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useFocusManagement } from '../../hooks/useFocusManagement';

const focusClass =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2';

function getInitials(email: string): string {
  return email.charAt(0).toUpperCase();
}

export function UserMenu() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const avatarButtonRef = useRef<HTMLButtonElement>(null);

  // WCAG 2.1 focus management — moves focus into dropdown on open, restores on close
  const { modalRef } = useFocusManagement(isOpen);

  // Close on outside click
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, []);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const items = containerRef.current
        ? Array.from(containerRef.current.querySelectorAll<HTMLElement>('[role="menuitem"]'))
        : [];

      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          setIsOpen(false);
          avatarButtonRef.current?.focus();
          break;
        case 'ArrowDown': {
          e.preventDefault();
          const idx = items.indexOf(document.activeElement as HTMLElement);
          items[(idx + 1) % items.length]?.focus();
          break;
        }
        case 'ArrowUp': {
          e.preventDefault();
          const idx = items.indexOf(document.activeElement as HTMLElement);
          items[(idx - 1 + items.length) % items.length]?.focus();
          break;
        }
        case 'Home':
          e.preventDefault();
          items[0]?.focus();
          break;
        case 'End':
          e.preventDefault();
          items[items.length - 1]?.focus();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const handleLogout = useCallback(async () => {
    setIsOpen(false);
    await logout();
    navigate('/');
  }, [logout, navigate]);

  if (!isAuthenticated || !user) {
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

  const initials = getInitials(user.email);

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={avatarButtonRef}
        id="user-menu-button"
        onClick={() => setIsOpen((o) => !o)}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-label="Menú de usuario"
        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg bg-white/10 border border-white/20 text-white hover:bg-white/15 transition-colors motion-reduce:transition-none ${focusClass}`}
      >
        <span className="w-8 h-8 rounded-full bg-[#FF9900] text-[#161d2b] flex items-center justify-center font-bold text-sm select-none">
          {initials}
        </span>
        <svg
          className={`w-4 h-4 transition-transform motion-reduce:transition-none ${isOpen ? 'rotate-180' : ''}`}
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {isOpen && (
        <div
          ref={modalRef as React.RefObject<HTMLDivElement>}
          role="menu"
          aria-labelledby="user-menu-button"
          tabIndex={-1}
          className="absolute right-0 top-[calc(100%+8px)] min-w-[220px] bg-white rounded-lg shadow-lg overflow-hidden z-50 outline-none"
        >
          {/* Header */}
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <p className="text-sm font-semibold text-gray-900 truncate">{user.email}</p>
            <p className="text-xs text-gray-500 truncate">{user.sub}</p>
          </div>

          {/* Mi Perfil */}
          <Link
            to="/dashboard"
            role="menuitem"
            tabIndex={0}
            onClick={() => setIsOpen(false)}
            className={`flex items-center gap-3 px-4 py-3 text-sm text-gray-700 font-medium hover:bg-gray-100 transition-colors motion-reduce:transition-none ${focusClass}`}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M8 8C9.65685 8 11 6.65685 11 5C11 3.34315 9.65685 2 8 2C6.34315 2 5 3.34315 5 5C5 6.65685 6.34315 8 8 8Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M14 14C14 11.7909 11.3137 10 8 10C4.68629 10 2 11.7909 2 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Mi Perfil
          </Link>

          <div className="h-px bg-gray-200" />

          {/* Cerrar Sesión */}
          <button
            role="menuitem"
            tabIndex={0}
            onClick={handleLogout}
            className={`flex items-center gap-3 w-full px-4 py-3 text-sm text-red-600 font-medium hover:bg-red-50 transition-colors motion-reduce:transition-none text-left ${focusClass}`}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M6 14H3C2.44772 14 2 13.5523 2 13V3C2 2.44772 2.44772 2 3 2H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M11 11L14 8L11 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M14 8H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Cerrar Sesión
          </button>
        </div>
      )}
    </div>
  );
}
