import { useAuth } from '@/hooks/useAuth';

export default function ProfileSection() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div
      className="
        rounded-2xl p-5
        bg-[#1e2738] border border-white/[0.07]
        shadow-[0_4px_24px_rgba(0,0,0,0.3)]
      "
    >
      <h2 className="mb-3 text-base font-semibold text-white/80">Mi perfil</h2>
      <p className="text-sm text-white/50 break-all">{user.email}</p>
      {user.roles.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {user.roles.map((role) => (
            <span
              key={role}
              className="rounded-full bg-[#FF9900]/15 px-2.5 py-0.5 text-xs font-medium text-[#FF9900] ring-1 ring-[#FF9900]/25"
            >
              {role}
            </span>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={logout}
        className="
          mt-4 w-full rounded-lg border border-white/[0.1] px-4 py-2 text-sm font-medium text-white/50
          hover:border-white/20 hover:text-white/70 hover:bg-white/[0.04]
          transition-all duration-150
          focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
        "
      >
        Cerrar sesión
      </button>
    </div>
  );
}
