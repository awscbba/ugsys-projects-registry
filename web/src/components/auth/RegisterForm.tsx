import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authService } from '../../services/authService';

const inputClass =
  'w-full rounded-lg border border-white/[0.1] bg-[#252f42] px-3 py-2.5 text-sm text-white/90 placeholder-white/25 ' +
  'focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50 ' +
  'transition-colors duration-150';

const labelClass = 'mb-1.5 block text-sm font-medium text-white/60';

export function RegisterForm() {
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await authService.register({ email, full_name: fullName, password });
      navigate('/login', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear la cuenta');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div>
        <label htmlFor="register-email" className={labelClass}>
          Correo electrónico
        </label>
        <input
          id="register-email"
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
        <label htmlFor="register-fullname" className={labelClass}>
          Nombre completo
        </label>
        <input
          id="register-fullname"
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
          autoComplete="name"
          className={inputClass}
          placeholder="Tu Nombre"
        />
      </div>

      <div>
        <label htmlFor="register-password" className={labelClass}>
          Contraseña
        </label>
        <input
          id="register-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
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
        {isLoading ? 'Creando cuenta...' : 'Crear cuenta'}
      </button>

      <p className="text-center text-sm text-white/40">
        ¿Ya tienes cuenta?{' '}
        <Link to="/login" className="text-[#FF9900] hover:text-[#ffb84d] transition-colors">
          Iniciar sesión
        </Link>
      </p>
    </form>
  );
}
