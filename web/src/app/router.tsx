import { createBrowserRouter } from 'react-router-dom';
import Layout from '@/components/layout/Layout';
import HomePage from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { ResetPasswordPage } from '@/pages/ResetPasswordPage';
import SubscribePage from '@/pages/SubscribePage';
import DashboardPage from '@/pages/DashboardPage';

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/reset-password/:token', element: <ResetPasswordPage /> },
      { path: '/subscribe/:projectId', element: <SubscribePage /> },
      { path: '/dashboard', element: <DashboardPage /> },
    ],
  },
]);
