import React, { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { toast } from "sonner";
import { queryClient } from "@/lib/queryClient";

const INACTIVITY_TIMEOUT_MS = 2 * 60 * 60 * 1000;
const LAST_ACTIVITY_STORAGE_KEY = "epi_scout_last_activity_at";
const ACTIVITY_EVENTS: Array<keyof WindowEventMap> = ["pointerdown", "keydown", "scroll", "touchstart"];

export interface User {
  id: number;
  username: string;
  role: "user" | "analyst" | "admin";
  is_active: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  role: "guest" | "user" | "analyst" | "admin";
  isGuest: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  authCheckFailed: boolean;
  retryAuthCheck: () => Promise<boolean>;
  login: (token: string) => Promise<boolean>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"));
  const [isLoading, setIsLoading] = useState(true);
  const [authCheckFailed, setAuthCheckFailed] = useState(false);
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightSessionChecks = useRef(new Map<string, Promise<boolean>>());
  const terminationRef = useRef<Promise<void> | null>(null);
  const terminateSessionRef = useRef<() => Promise<void>>(async () => undefined);

  const terminateSession = useCallback(async (): Promise<void> => {
    if (terminationRef.current) return terminationRef.current;

    localStorage.removeItem("token");
    localStorage.removeItem(LAST_ACTIVITY_STORAGE_KEY);
    sessionStorage.removeItem("epi_scout_scan_state");
    setToken(null);
    setUser(null);
    setAuthCheckFailed(false);
    setIsLoading(false);

    const cleanup = (async () => {
      await queryClient.cancelQueries();
      queryClient.clear();
    })();
    terminationRef.current = cleanup;
    try {
      await cleanup;
    } finally {
      if (terminationRef.current === cleanup) terminationRef.current = null;
    }
  }, []);
  terminateSessionRef.current = terminateSession;

  const checkSession = useCallback((explicitToken?: string): Promise<boolean> => {
    const currentToken = explicitToken ?? localStorage.getItem("token");
    if (!currentToken) {
      setUser(null);
      setToken(null);
      setAuthCheckFailed(false);
      setIsLoading(false);
      return Promise.resolve(false);
    }

    const existingCheck = inFlightSessionChecks.current.get(currentToken);
    if (existingCheck) return existingCheck;

    const checkPromise = (async () => {
      setIsLoading(true);
      try {
        const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
        const response = await fetch(`${apiBase}/api/auth/me`, {
          headers: { Authorization: `Bearer ${currentToken}` },
        });

        if (localStorage.getItem("token") !== currentToken) return false;

        if (response.ok) {
          const userData = await response.json() as User;
          if (localStorage.getItem("token") !== currentToken) return false;
          setUser(userData);
          setAuthCheckFailed(false);
          return true;
        }

        if (response.status === 401) {
          await terminateSession();
          return false;
        }

        setAuthCheckFailed(true);
        return false;
      } catch (error) {
        if (localStorage.getItem("token") !== currentToken) return false;
        console.error("Auth check failed", error);
        setAuthCheckFailed(true);
        return false;
      } finally {
        if (localStorage.getItem("token") === currentToken) setIsLoading(false);
        inFlightSessionChecks.current.delete(currentToken);
      }
    })();

    inFlightSessionChecks.current.set(currentToken, checkPromise);
    return checkPromise;
  }, [terminateSession]);

  useEffect(() => {
    void checkSession(token ?? undefined);
  }, [token, checkSession]);

  const login = useCallback(async (newToken: string): Promise<boolean> => {
    await queryClient.cancelQueries();
    queryClient.clear();
    setIsLoading(true);
    setAuthCheckFailed(false);
    localStorage.setItem("token", newToken);
    localStorage.setItem(LAST_ACTIVITY_STORAGE_KEY, Date.now().toString());
    setToken(newToken);
    return checkSession(newToken);
  }, [checkSession]);

  const logout = useCallback(async (): Promise<void> => {
    await terminateSession();
    toast.success("Đã đăng xuất thành công");
    window.location.href = "/";
  }, [terminateSession]);

  useEffect(() => {
    if (!token) return;

    const logoutForInactivity = () => {
      void terminateSession().then(() => {
        toast.info("Phiên đăng nhập đã hết hạn do không hoạt động trong 2 giờ");
        window.location.href = "/";
      });
    };

    const scheduleLogout = () => {
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
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
      if (event.key === "token" && !event.newValue) {
        void terminateSession().then(() => { window.location.href = "/"; });
      } else if (event.key === LAST_ACTIVITY_STORAGE_KEY) {
        scheduleLogout();
      }
    };

    if (!localStorage.getItem(LAST_ACTIVITY_STORAGE_KEY)) {
      localStorage.setItem(LAST_ACTIVITY_STORAGE_KEY, Date.now().toString());
    }
    scheduleLogout();
    ACTIVITY_EVENTS.forEach((eventName) => window.addEventListener(eventName, recordActivity, { passive: true }));
    window.addEventListener("storage", syncActivityAcrossTabs);

    return () => {
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      ACTIVITY_EVENTS.forEach((eventName) => window.removeEventListener(eventName, recordActivity));
      window.removeEventListener("storage", syncActivityAcrossTabs);
    };
  }, [token, terminateSession]);

  useEffect(() => {
    const originalFetch = window.fetch;
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
      const resolvedInput = apiBase && typeof input === "string" && input.startsWith("/api/")
        ? `${apiBase}${input}`
        : input;
      const headers = new Headers(input instanceof Request ? input.headers : undefined);
      new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
      const currentToken = localStorage.getItem("token");
      if (currentToken && url.includes("/api/")) headers.set("Authorization", `Bearer ${currentToken}`);
      headers.set("ngrok-skip-browser-warning", "true");

      const response = await originalFetch(resolvedInput, { ...init, headers });
      const isAuthCheck = url.includes("/api/auth/me");
      if (
        response.status === 401
        && currentToken
        && localStorage.getItem("token") === currentToken
        && !url.includes("/api/auth/login")
        && !isAuthCheck
      ) {
        void terminateSessionRef.current();
      }
      return response;
    };

    return () => { window.fetch = originalFetch; };
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      token,
      role: user?.role ?? "guest",
      isGuest: !user,
      isAuthenticated: !!user,
      isLoading,
      authCheckFailed,
      retryAuthCheck: () => checkSession(),
      login,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};
