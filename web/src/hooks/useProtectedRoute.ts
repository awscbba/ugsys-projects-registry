import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useStore } from '@nanostores/react';
import { $isAuthenticated } from '../stores/authStore';

export function useProtectedRoute(): boolean {
  const isAuthenticated = useStore($isAuthenticated);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!isAuthenticated) {
      navigate(`/login?redirect=${encodeURIComponent(location.pathname)}`, { replace: true });
    }
  }, [isAuthenticated, navigate, location.pathname]);

  return isAuthenticated;
}
