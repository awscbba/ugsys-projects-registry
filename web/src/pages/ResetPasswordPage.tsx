import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';

const inputClass =
  'w-full rounded-lg border border-white/[0.1] bg-[#252f42] px-3 py-2.5 text-sm text-white/90 placeholder-white/25 ' +
  'focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50 ' +
  'transition-colors duration-150';

export function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }

    if (!token) {
      setError('Token inválido');
      return;
    }

    setIsLoading(true);
    try {
      await authService.resetPassword(token, newPassword);
      navigate('/login', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al restablecer la contraseña');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-16">
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(ellipse 60% 40% at 50% 40%, rgba(255,153,0,0.06) 0%, transparent 70%)',
        }}
      />

      <div className="relative w-full max-w-md">
        <div
          className="
            rounded-2xl p-8
            bg-[#1e2738] border border-white/[0.08]
            shadow-[0_8px_48px_rgba(0,0,0,0.5)]
          "
        >
          <h1 className="mb-1 text-center text-xl font-semibold text-white/90">Nueva contraseña</h1>
          <p className="mb-7 text-center text-sm text-white/40">
            Elige una contraseña segura para tu cuenta
          </p>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div>
              <label
                htmlFor="new-password"
                className="mb-1.5 block text-sm font-medium text-white/60"
              >
                Nueva contraseña
              </label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                autoComplete="new-password"
                className={inputClass}
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="mb-1.5 block text-sm font-medium text-white/60"
              >
                Confirmar contraseña
              </label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
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
              {isLoading ? 'Guardando...' : 'Restablecer contraseña'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
