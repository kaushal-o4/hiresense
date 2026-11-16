/*
 * Light / dark / system theme. index.html applies the saved choice before first paint; this context keeps
 * html[data-theme] in sync afterwards and tells charts (useChartTheme) to re-read their colours.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

const KEY = "hs-theme";
const ThemeContext = createContext({ theme: "light", resolved: "light", setTheme: () => {} });

const read = () => { try { return localStorage.getItem(KEY) || "light"; } catch { return "light"; } };
const systemDark = () => typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
const resolve = (t) => (t === "system" ? (systemDark() ? "dark" : "light") : t);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(read);
  const [resolved, setResolved] = useState(() => resolve(read()));

  useEffect(() => {
    const apply = () => {
      const r = resolve(theme);
      document.documentElement.dataset.theme = r;
      setResolved(r);
    };
    apply();
    if (theme !== "system" || typeof matchMedia !== "function") return undefined;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener?.("change", apply);
    return () => mq.removeEventListener?.("change", apply);
  }, [theme]);

  const setTheme = useCallback((t) => {
    try { localStorage.setItem(KEY, t); } catch { /* private mode: theme just isn't remembered */ }
    setThemeState(t);
  }, []);

  return <ThemeContext.Provider value={{ theme, resolved, setTheme }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
