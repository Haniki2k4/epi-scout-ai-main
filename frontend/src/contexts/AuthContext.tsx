import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { toast } from 'sonner';

const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000;
const LAST_ACTIVITY_STORAGE_KEY = 'epi_scout_last_activity_at';
const ACTIVITY_EVENTS: Array<keyof WindowEventMap> = ['pointerdown', 'keydown', 'scroll', 'touchstart'];

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
  role: 'guest' | 'user' | 'admin';
  isGuest: boolean;
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
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const fetchUser = async () => {
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
        const response = await fetch(`${apiBase}/api/auth/me`, {
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

  useEffect(() => {
    if (!token) {
      return;
    }

    const logoutForInactivity = () => {
      localStorage.removeItem('token');
      localStorage.removeItem(LAST_ACTIVITY_STORAGE_KEY);
      sessionStorage.removeItem('epi_scout_scan_state');
      setToken(null);
      setUser(null);
      toast.success('Phiên đăng nhập đã hết hạn do không hoạt động trong 15 phút');
      window.location.href = '/';
    };

    const scheduleLogout = () => {
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
      }

      const lastActivityAt = Number(localStorage.getItem(LAST_ACTIVITY_STORAGE_KEY)) || Date.now();
      const remainingTime = Math.max(0, INACTIVITY_TIMEOUT_MS - (Date.now() - lastActivityAt));
      inactivityTimerRef.current = setTimeout(logoutForInactivity, remainingTime);
    };

    const recordActivity = () => {
      const lastActivityAt = Number(localStorage.getItem(LAST_ACTIVITY_STORAGE_KEY)) || Date.now();
      if (Date.now() - lastActivityAt >= INACTIVITY_TIMEOUT_MS) {
        logoutForInactivity();
        return;
      }

      localStorage.setItem(LAST_ACTIVITY_STORAGE_KEY, Date.now().toString());
      scheduleLogout();
    };

    const syncActivityAcrossTabs = (event: StorageEvent) => {
      if (event.key === 'token' && !event.newValue) {
        setToken(null);
        setUser(null);
        window.location.href = '/';
        return;
      }
      if (event.key === LAST_ACTIVITY_STORAGE_KEY) {
        scheduleLogout();
      }
    };

    if (!localStorage.getItem(LAST_ACTIVITY_STORAGE_KEY)) {
      localStorage.setItem(LAST_ACTIVITY_STORAGE_KEY, Date.now().toString());
    }

    scheduleLogout();
    ACTIVITY_EVENTS.forEach((eventName) => window.addEventListener(eventName, recordActivity, { passive: true }));
    window.addEventListener('storage', syncActivityAcrossTabs);

    return () => {
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
      }
      ACTIVITY_EVENTS.forEach((eventName) => window.removeEventListener(eventName, recordActivity));
      window.removeEventListener('storage', syncActivityAcrossTabs);
    };
  }, [token]);

  // Global Fetch Interceptor to attach Authorization header
  useEffect(() => {
    const originalFetch = window.fetch;
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const token = localStorage.getItem('token');
      // Only attach to API routes
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const apiBase = import.meta.env.VITE_API_BASE_URL ?? '';
      // Rewrite relative /api/ calls to absolute URL when apiBase is set
      let resolvedInput = input;
      if (apiBase && typeof url === 'string' && url.startsWith('/api/')) {
        resolvedInput = `${apiBase}${url}`;
      }
      if (token && url.includes('/api/')) {
        init = init || {};
        init.headers = {
          ...init.headers,
          Authorization: `Bearer ${token}`
        };
      }
      // Add ngrok bypass header for ALL requests
      init = init || {};
      init.headers = {
        ...init.headers,
        "ngrok-skip-browser-warning": "true"
      };
      const response = await originalFetch(resolvedInput, init);
      // Auto logout on 401 Unauthorized (unless it's the login endpoint)
      if (response.status === 401 && token && !url.includes('/api/auth/login')) {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
      }
      return response;
    };

    return () => {
      window.fetch = originalFetch; // restore on unmount
    };
  }, []);

  const login = (newToken: string) => {
    localStorage.setItem('token', newToken);
    localStorage.setItem(LAST_ACTIVITY_STORAGE_KEY, Date.now().toString());
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem(LAST_ACTIVITY_STORAGE_KEY);
    sessionStorage.removeItem('epi_scout_scan_state');
    setToken(null);
    setUser(null);
    toast.success('Đã đăng xuất thành công');
    window.location.href = '/';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        role: user?.role ?? 'guest',
        isGuest: !user,
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
