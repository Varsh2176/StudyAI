import { useCallback, useEffect, useMemo, useState } from "react";
import API from "../services/api";
import { AuthContext } from "./context";
import {
  clearAuthSession,
  getAccessToken,
  getAuthEmail,
  getAuthName,
  persistAuthSession,
} from "./authStorage";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getAccessToken());
  const [email, setEmail] = useState(() => getAuthEmail());
  const [name, setName] = useState(() => getAuthName());
  const [bootstrapping, setBootstrapping] = useState(() => Boolean(getAccessToken()));

  const syncFromStorage = useCallback(() => {
    setToken(getAccessToken());
    setEmail(getAuthEmail());
    setName(getAuthName());
  }, []);

  useEffect(() => {
    window.addEventListener("studyai-identity-changed", syncFromStorage);
    window.addEventListener("storage", syncFromStorage);
    return () => {
      window.removeEventListener("studyai-identity-changed", syncFromStorage);
      window.removeEventListener("storage", syncFromStorage);
    };
  }, [syncFromStorage]);

  useEffect(() => {
    let cancelled = false;
    async function validate() {
      const existing = getAccessToken();
      if (!existing) {
        if (!cancelled) setBootstrapping(false);
        return;
      }
      try {
        const res = await API.get("/auth/me");
        if (cancelled) return;
        persistAuthSession({
          accessToken: existing,
          email: res.data.email,
          name: res.data.name,
        });
        syncFromStorage();
      } catch {
        if (!cancelled) {
          clearAuthSession();
          syncFromStorage();
        }
      } finally {
        if (!cancelled) setBootstrapping(false);
      }
    }
    void validate();
    return () => {
      cancelled = true;
    };
  }, [syncFromStorage]);

  const applyAuthResponse = useCallback(
    (data) => {
      persistAuthSession({
        accessToken: data.access_token,
        email: data.email,
        name: data.name,
      });
      syncFromStorage();
    },
    [syncFromStorage]
  );

  const login = useCallback(
    async (payload) => {
      const res = await API.post("/auth/login", payload);
      applyAuthResponse(res.data);
      return res.data;
    },
    [applyAuthResponse]
  );

  const register = useCallback(
    async (payload) => {
      const res = await API.post("/auth/register", payload);
      applyAuthResponse(res.data);
      return res.data;
    },
    [applyAuthResponse]
  );

  const logout = useCallback(async () => {
    try {
      if (getAccessToken()) {
        await API.post("/auth/logout");
      }
    } catch {
      // Client discard is authoritative for stateless tokens.
    } finally {
      clearAuthSession();
      syncFromStorage();
    }
  }, [syncFromStorage]);

  const value = useMemo(
    () => ({
      token,
      email,
      name,
      bootstrapping,
      isAuthenticated: Boolean(token && email),
      login,
      register,
      logout,
      applyAuthResponse,
    }),
    [token, email, name, bootstrapping, login, register, logout, applyAuthResponse]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
