import { RegisterForm } from '../components/auth/RegisterForm';

export function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-md">
        <h1 className="mb-6 text-center text-2xl font-bold text-gray-900">Crear cuenta</h1>
        <RegisterForm />
      </div>
    </div>
  );
}
