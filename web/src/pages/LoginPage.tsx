import { LoginForm } from '../components/auth/LoginForm';

export function LoginPage() {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-16">
      {/* Subtle radial glow behind the card */}
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(ellipse 60% 40% at 50% 40%, rgba(255,153,0,0.06) 0%, transparent 70%)',
        }}
      />

      <div className="relative w-full max-w-md">
        {/* Card */}
        <div
          className="
            rounded-2xl p-8
            bg-[#1e2738] border border-white/[0.08]
            shadow-[0_8px_48px_rgba(0,0,0,0.5)]
          "
        >
          {/* Brand mark */}
          <div className="flex justify-center mb-6">
            <span
              className="text-2xl font-bold tracking-tight"
              style={{
                background: 'linear-gradient(135deg, #FF9900 0%, #ffb84d 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              AWS User Group Cbba
            </span>
          </div>

          <h1 className="mb-1 text-center text-xl font-semibold text-white/90">
            Iniciar sesión
          </h1>
          <p className="mb-7 text-center text-sm text-white/40">
            Accede a tu cuenta para gestionar proyectos
          </p>

          <LoginForm />
        </div>
      </div>
    </div>
  );
}
