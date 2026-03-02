import { useStore } from '@nanostores/react';
import { $user, $isLoading, $isAuthenticated, login, logout } from '../stores/authStore';

export function useAuth() {
  const user = useStore($user);
  const isLoading = useStore($isLoading);
  const isAuthenticated = useStore($isAuthenticated);
  return { user, isLoading, isAuthenticated, login, logout };
}
