/* Authentication context and session handling. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { get, post } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ai, setAi] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await get("/auth/me");
      setUser(data.user);
      setAi(data.ai);
      return data.user;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const onUnauthorized = () => setUser(null);
    window.addEventListener("hs:unauthorized", onUnauthorized);
    return () => window.removeEventListener("hs:unauthorized", onUnauthorized);
  }, [refresh]);

  const login = async (email, password) => {
    await post("/auth/login", { email, password });
    return refresh();
  };

  const logout = async () => {
    try {
      await post("/auth/logout");
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, ai, loading, login, logout, refresh, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
