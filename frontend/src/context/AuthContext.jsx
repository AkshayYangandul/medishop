import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getAccessToken, clearAccessToken, login as apiLogin, getCurrentUser } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  // Restore / validate session on mount using the stored bearer token.
  useEffect(() => {
    let cancelled = false;

    const validate = async () => {
      const token = getAccessToken();

      if (!token) {
        if (!cancelled) {
          setIsAuthenticated(false);
          setUser(null);
          setIsInitializing(false);
        }
        return;
      }

      try {
        const profile = await getCurrentUser(token);
        if (cancelled) return;
        setUser(profile);
        setIsAuthenticated(true);
      } catch {
        // Missing, malformed or expired token -> start unauthenticated.
        if (!cancelled) {
          clearAccessToken();
          setUser(null);
          setIsAuthenticated(false);
        }
      } finally {
        if (!cancelled) {
          setIsInitializing(false);
        }
      }
    };

    validate();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async ({ email, password, rememberMe = true }) => {
    const result = await apiLogin({ email, password, rememberMe });
    setUser(result.user);
    setIsAuthenticated(true);
    return result.user;
  }, []);

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const value = {
    user,
    isAuthenticated,
    isInitializing,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
