import { useState } from 'react';
import { authService } from '@/services/authService';
import { addToast } from '@/stores/toastStore';

const inputClass =
  'w-full rounded-lg border border-white/[0.1] bg-[#252f42] px-3 py-2 text-sm text-white/90 ' +
  'focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150';

export default function PasswordChange() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError('Las contraseñas nuevas no coinciden.');
      return;
    }

    setIsSubmitting(true);
    try {
      await authService.changePassword(currentPassword, newPassword);
      addToast('success', 'Contraseña actualizada correctamente');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setSuccess(true);
    } catch {
      setError('No se pudo actualizar la contraseña. Verifica tu contraseña actual.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div
      className="
        rounded-2xl p-5
        bg-[#1e2738] border border-white/[0.07]
        shadow-[0_4px_24px_rgba(0,0,0,0.3)]
      "
    >
      <h2 className="mb-4 text-base font-semibold text-white/80">Cambiar contraseña</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label htmlFor="current-password" className="mb-1.5 block text-xs font-medium text-white/50">
            Contraseña actual
          </label>
          <input
            id="current-password"
            type="password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="new-password" className="mb-1.5 block text-xs font-medium text-white/50">
            Nueva contraseña
          </label>
          <input
            id="new-password"
            type="password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="confirm-password" className="mb-1.5 block text-xs font-medium text-white/50">
            Confirmar nueva contraseña
          </label>
          <input
            id="confirm-password"
            type="password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className={inputClass}
          />
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2" role="alert">
            {error}
          </p>
        )}
        {success && !error && (
          <p className="text-xs text-emerald-400">Contraseña actualizada correctamente.</p>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="
            w-full rounded-lg bg-[#FF9900] px-4 py-2 text-sm font-semibold text-[#161d2b]
            hover:bg-[#ffb84d] disabled:opacity-50 disabled:cursor-not-allowed
            transition-all duration-150
            focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
            shadow-[0_2px_8px_rgba(255,153,0,0.2)]
          "
        >
          {isSubmitting ? 'Actualizando...' : 'Actualizar contraseña'}
        </button>
      </form>
    </div>
  );
}
