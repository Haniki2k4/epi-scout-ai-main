import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

export interface User {
  id: number;
  username: string;
  role: 'user' | 'admin';
  is_active: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchUser = async () => {
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch('http://localhost:8000/api/auth/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
        } else {
          // Token invalid or expired
          localStorage.removeItem('token');
          setToken(null);
          setUser(null);
        }
      } catch (error) {
        console.error('Failed to fetch user', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchUser();
  }, [token]);

  // Global Fetch Interceptor to attach Authorization header
  useEffect(() => {
    const originalFetch = window.fetch;
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const token = localStorage.getItem('token');
      // Only attach to API routes
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (token && url.includes('/api/')) {
        init = init || {};
        init.headers = {
          ...init.headers,
          Authorization: `Bearer ${token}`
        };
      }
      const response = await originalFetch(input, init);
      // Auto logout on 401 Unauthorized (unless it's the login endpoint)
      if (response.status === 401 && !url.includes('/api/auth/login')) {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
        window.location.href = '/login';
      }
      return response;
    };

    return () => {
      window.fetch = originalFetch; // restore on unmount
    };
  }, []);

  const login = (newToken: string) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem('token');
    sessionStorage.removeItem('epi_scout_scan_state');
    setToken(null);
    setUser(null);
    toast.success('Đã đăng xuất thành công');
    window.location.href = '/login'; // Force reload and redirect to avoid stale state
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
