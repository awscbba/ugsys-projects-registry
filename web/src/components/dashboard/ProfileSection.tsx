import { useAuth } from "@/hooks/useAuth";

export default function ProfileSection() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-gray-800">Mi perfil</h2>
      <p className="text-sm text-gray-600 break-all">{user.email}</p>
      {user.roles.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {user.roles.map((role) => (
            <span
              key={role}
              className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700"
            >
              {role}
            </span>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={logout}
        className="mt-4 w-full rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-400"
      >
        Cerrar sesión
      </button>
    </div>
  );
}
