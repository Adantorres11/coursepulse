import React, { createContext, useContext, useEffect, useState } from "react";
import {
  type User,
  type UserRole,
  getStoredToken,
  getStoredUser,
  clearSession,
  login as apiLogin,
  register as apiRegister,
  getCurrentUser as apiGetCurrentUser,
} from "../lib/apiClient";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (
    email: string,
    password: string,
    role?: UserRole
  ) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [user, setUser] = useState<User | null>(() => getStoredUser());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Validate or refresh session on mount if token exists
  useEffect(() => {
    let isMounted = true;

    async function initSession() {
      const storedToken = getStoredToken();
      if (!storedToken) {
        if (isMounted) {
          setIsLoading(false);
        }
        return;
      }

      // Verify token with backend /api/auth/me/
      const result = await apiGetCurrentUser();
      if (!isMounted) return;

      if (result.data) {
        setUser(result.data);
      } else if (
        result.error &&
        (result.error.includes("401") ||
          result.error.includes("Invalid token") ||
          result.error.includes("credentials were not provided"))
      ) {
        // Token is invalid on server, clear session
        setToken(null);
        setUser(null);
        clearSession();
      }
      // If network unreachable, keep local session so student stays signed in offline
      setIsLoading(false);
    }

    initSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (email: string, password: string) => {
    const result = await apiLogin({ email, password });
    if (result.error || !result.data) {
      return { success: false, error: result.error || "Failed to log in." };
    }

    setToken(result.data.token);
    setUser(result.data.user);
    return { success: true };
  };

  const signup = async (email: string, password: string, role: UserRole = "student") => {
    const result = await apiRegister({ email, password, role });
    if (result.error || !result.data) {
      return { success: false, error: result.error || "Failed to create account." };
    }

    setToken(result.data.token);
    setUser(result.data.user);
    return { success: true };
  };

  const logout = () => {
    clearSession();
    setToken(null);
    setUser(null);
  };

  const isAuthenticated = Boolean(token);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        isLoading,
        login,
        signup,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
