import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getUserRole } from "../lib/apiClient";
import type { UserRole } from "../types/api";

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRole?: UserRole;
}

/**
 * Route guard that:
 * 1. Shows a loading indicator while the auth session initializes.
 * 2. Redirects unauthenticated / logged-out users to the Login page.
 * 3. Enforces role-based access control:
 *    - Students attempting to open a professor URL are redirected to their home (/hub).
 *    - Professors attempting to open a student URL are redirected to their home (/professor).
 */
export function ProtectedRoute({ children, allowedRole }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0B1220] flex items-center justify-center text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Checking session...</span>
        </div>
      </div>
    );
  }

  // Acceptance criteria 3: Logged-out users are sent to login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Acceptance criteria 2: Students who open a professor URL, and professors who open a student URL, are redirected to their own home
  const userRole = user?.role || (getUserRole() as UserRole | null);

  if (allowedRole && userRole && userRole !== allowedRole) {
    const homeRoute = userRole === "professor" ? "/professor" : "/hub";
    return <Navigate to={homeRoute} replace />;
  }

  return <>{children}</>;
}

/**
 * Route guard for auth pages (Login / Sign Up).
 * If the user is already authenticated, redirects them directly to their role-appropriate home screen.
 */
export function PublicOnlyRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return null;
  }

  if (isAuthenticated) {
    const userRole = user?.role || (getUserRole() as UserRole | null);
    return <Navigate to={userRole === "professor" ? "/professor" : "/hub"} replace />;
  }

  return <>{children}</>;
}

