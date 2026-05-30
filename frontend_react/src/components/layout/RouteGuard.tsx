import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

interface GuardProps {
  children: React.ReactNode;
  allowedRoles?: ('admin' | 'csgt' | 'user')[];
}

export const RouteGuard: React.FC<GuardProps> = ({ children, allowedRoles }) => {
  const { isLoggedIn, user } = useAuthStore();

  if (!isLoggedIn || !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role as any)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
