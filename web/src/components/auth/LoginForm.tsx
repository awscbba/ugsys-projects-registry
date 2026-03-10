import { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { login } from '../../stores/authStore';
import { ForgotPasswordModal } from './ForgotPasswordModal';

const inputClass =
  'w-full rounded-lg border border-white/[0.1] bg-[#252f42] px-3 py-2.5 text-sm text-white/90 placeholder-white/25 ' +
  'focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50 ' +
  'transition-colors duration-150';

const labelClass = 'mb-1.5 block text-sm font-medium text-white/60';

export function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForgot, setShowForgot] = useState(false);

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await login(email, password);
      const redirect = searchParams.get('redirect') ?? '/dashboard';
      navigate(redirect, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Credenciales inválidas');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div>
          <label htmlFor="login-email" className={labelClass}>
            Correo electrónico
          </label>
          <input
            id="login-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className={inputClass}
            placeholder="tu@correo.com"
          />
        </div>

        <div>
          <label htmlFor="login-password" className={labelClass}>
            Contraseña
          </label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className={inputClass}
          />
        </div>

        {error && (
          <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="
            w-full rounded-lg bg-[#FF9900] px-4 py-2.5 text-sm font-semibold text-[#161d2b]
            hover:bg-[#ffb84d] disabled:opacity-50 disabled:cursor-not-allowed
            transition-all duration-150 active:scale-[0.99]
            focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
            shadow-[0_2px_12px_rgba(255,153,0,0.25)]
          "
        >
          {isLoading ? 'Ingresando...' : 'Iniciar sesión'}
        </button>

        <div className="flex items-center justify-between text-sm pt-1">
          <Link to="/register" className="text-[#FF9900] hover:text-[#ffb84d] transition-colors">
            Crear cuenta
          </Link>
          <button
            type="button"
            onClick={() => setShowForgot(true)}
            className="text-white/40 hover:text-white/60 transition-colors"
          >
            ¿Olvidaste tu contraseña?
          </button>
        </div>
      </form>

      <ForgotPasswordModal isOpen={showForgot} onClose={() => setShowForgot(false)} />
    </>
  );
}
