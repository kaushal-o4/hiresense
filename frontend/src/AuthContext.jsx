// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/AuthContext.jsx
//
// FILE PURPOSE:
// Keeps track of the logged-in user for the whole frontend.
//
// MAIN RESPONSIBILITY:
// React context for authentication (login, logout, current user).
//
// WHAT THIS FILE DOES:
// 1. On page load calls GET /auth/me to restore the session from the cookie.
// 2. Stores the user object and the AI availability info.
// 3. Provides login() (POST /auth/login) and logout() (POST /auth/logout).
// 4. Clears the user when any API call reports 401 (session expired).
//
// HOW THIS FILE WORKS:
// AuthProvider holds user, ai and loading in React state and shares them with useAuth(). Pages call
// useAuth() to read the user or to log in/out.
//
// IMPORTANT FUNCTIONS:
//    - AuthProvider()
//        Context provider that loads /auth/me and exposes user, ai, loading, login, logout,
//        refresh, setUser.
//    - useAuth()
//        Hook that pages use to read the authentication context.
//
// IMPORTANT VARIABLES / STATE:
//    - user
//        The logged-in user (id, name, email, role) or null.
//    - ai
//        Whether AI features are available.
//    - loading
//        True until the first /auth/me check finishes.
//
// INPUT:
// Responses of /auth/me, /auth/login and /auth/logout.
//
// OUTPUT:
// The shared authentication state used by App.jsx and every page.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js
//    Used by: App.jsx, components/AppShellLayout.jsx, components/HostedAiConsentGate.jsx,
//    components/useSpeechAndPreferences.jsx, main.jsx, pages/AccountSettings.jsx, pages/Login.jsx,
//    pages/Privacy.jsx, pages/ProfileEditor.jsx, pages/Register.jsx,
//    pages/admin/PlatformSettings.jsx, pages/admin/UserManagement.jsx,
//    pages/shared/AssessmentManager.jsx, pages/shared/IntegrityReview.jsx,
//    pages/student/EnglishPracticeHome.jsx, pages/student/MockInterviewHome.jsx,
//    pages/student/StudentDashboard.jsx
//
// EXECUTION FLOW:
//    App starts
//       |
//       v
//    AuthProvider calls /auth/me
//       |
//       v
//    User saved in state (or null)
//       |
//       v
//    App.jsx shows the right portal
//
// IMPORTANT DEPENDENCIES:
//    react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Authentication context and session handling. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { get, post } from "./apiClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // the signed-in user (null = signed out)
  const [ai, setAi] = useState(null); // AI availability reported by the server (shown in the UI)
  const [loading, setLoading] = useState(true); // true until the first /auth/me check has finished

  // Ask the server who is signed in. The httpOnly cookie is sent automatically, so a page refresh keeps the session.
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

  // On first load: restore the session, and sign out whenever apiClient.js reports a 401 (expired session).
  useEffect(() => {
    refresh();
    const onUnauthorized = () => setUser(null);
    window.addEventListener("hs:unauthorized", onUnauthorized);
    return () => window.removeEventListener("hs:unauthorized", onUnauthorized);
  }, [refresh]);

  // Login: the server checks the password and sets the cookie; then we load the user's profile.
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
