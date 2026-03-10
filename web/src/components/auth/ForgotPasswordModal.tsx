import { useState } from 'react';
import { authService } from '../../services/authService';

interface ForgotPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ForgotPasswordModal({ isOpen, onClose }: ForgotPasswordModalProps) {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await authService.forgotPassword(email);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ocurrió un error');
    } finally {
      setIsLoading(false);
    }
  }

  function handleClose() {
    setEmail('');
    setSuccess(false);
    setError(null);
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={handleClose}
    >
      <div
        className="
          w-full max-w-md rounded-2xl p-6
          bg-[#1e2738] border border-white/[0.08]
          shadow-[0_16px_64px_rgba(0,0,0,0.6)]
        "
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white/90">Recuperar contraseña</h2>
          <button
            type="button"
            onClick={handleClose}
            className="text-white/30 hover:text-white/60 transition-colors text-lg leading-none"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        {success ? (
          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 text-sm text-emerald-300">
            Revisa tu correo. Te enviamos un enlace para restablecer tu contraseña.
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-4">
              <label
                htmlFor="forgot-email"
                className="mb-1.5 block text-sm font-medium text-white/60"
              >
                Correo electrónico
              </label>
              <input
                id="forgot-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="
                  w-full rounded-lg border border-white/[0.1] bg-[#252f42]
                  px-3 py-2.5 text-sm text-white/90 placeholder-white/25
                  focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50
                  transition-colors duration-150
                "
                placeholder="tu@correo.com"
              />
            </div>

            {error && (
              <p className="mb-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="
                w-full rounded-lg bg-[#FF9900] px-4 py-2.5 text-sm font-semibold text-[#161d2b]
                hover:bg-[#ffb84d] disabled:opacity-50 disabled:cursor-not-allowed
                transition-all duration-150
                focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
                shadow-[0_2px_12px_rgba(255,153,0,0.25)]
              "
            >
              {isLoading ? 'Enviando...' : 'Enviar enlace'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
