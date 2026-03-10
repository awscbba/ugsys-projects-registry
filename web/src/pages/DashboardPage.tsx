import { useProtectedRoute } from '@/hooks/useProtectedRoute';
import { useAuth } from '@/hooks/useAuth';
import ProfileSection from '@/components/dashboard/ProfileSection';
import PasswordChange from '@/components/dashboard/PasswordChange';
import SubscriptionList from '@/components/dashboard/SubscriptionList';

export default function DashboardPage() {
  useProtectedRoute();
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#FF9900]/30 border-t-[#FF9900]" />
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
      <h1 className="mb-8 text-2xl font-bold text-white/90 tracking-tight">Mi Panel</h1>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column */}
        <div className="space-y-6 lg:col-span-1">
          <ProfileSection />
          <PasswordChange />
        </div>
        {/* Right column */}
        <div className="lg:col-span-2">
          <div
            className="
              rounded-2xl p-6
              bg-[#1e2738] border border-white/[0.07]
              shadow-[0_4px_24px_rgba(0,0,0,0.3)]
            "
          >
            <h2 className="mb-5 text-base font-semibold text-white/80">Mis suscripciones</h2>
            <SubscriptionList personId={user.sub} />
          </div>
        </div>
      </div>
    </main>
  );
}
