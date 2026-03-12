import { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { LoginCard } from '@ugsys/ui-lib';
import { login } from '../stores/authStore';
import { ForgotPasswordModal } from '../components/auth/ForgotPasswordModal';

/**
 * LoginPage — delegates card rendering to LoginCard from @ugsys/ui-lib.
 * Owns: auth state, redirect logic, forgot-password modal trigger.
 */
export function LoginPage() {
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
      const redirect = searchParams.get('redirect') ?? '/';
      navigate(redirect, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Credenciales inválidas');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <LoginCard
        title="AWS User Group Cbba"
        emailLabel="Correo electrónico"
        passwordLabel="Contraseña"
        submitLabel="Iniciar sesión"
        loadingLabel="Ingresando..."
        email={email}
        password={password}
        isLoading={isLoading}
        error={error}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onSubmit={handleSubmit}
        footer={
          <div className="flex items-center justify-between text-sm">
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
        }
      />

      <ForgotPasswordModal isOpen={showForgot} onClose={() => setShowForgot(false)} />
    </>
  );
}
