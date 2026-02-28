import { useProtectedRoute } from "@/hooks/useProtectedRoute";
import { useAuth } from "@/hooks/useAuth";
import ProfileSection from "@/components/dashboard/ProfileSection";
import PasswordChange from "@/components/dashboard/PasswordChange";
import SubscriptionList from "@/components/dashboard/SubscriptionList";

export default function DashboardPage() {
  useProtectedRoute();
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Mi Panel</h1>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column */}
        <div className="space-y-6 lg:col-span-1">
          <ProfileSection />
          <PasswordChange />
        </div>
        {/* Right column */}
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-base font-semibold text-gray-800">
              Mis suscripciones
            </h2>
            <SubscriptionList personId={user.sub} />
          </div>
        </div>
      </div>
    </main>
  );
}
