// Thème clair / sombre.
// - Au premier passage, on suit le réglage du système (Windows, macOS, téléphone…).
// - Dès que l'utilisateur clique sur le bouton, son choix est gardé dans le navigateur.
// - Le thème est appliqué en posant la classe « dark » sur <html> (voir index.css).
// Un petit script dans index.html fait la même chose AVANT l'affichage, pour éviter un flash blanc.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";
const THEME_KEY = "maintai.theme";
const media = () => window.matchMedia("(prefers-color-scheme: dark)");

function savedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch { return null; }
}

interface ThemeState { theme: Theme; toggle: () => void; }
const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoice] = useState<Theme | null>(savedTheme);          // null = suivre le système
  const [system, setSystem] = useState<Theme>(() => (media().matches ? "dark" : "light"));
  const theme = choice ?? system;

  // Le système change de thème (ex. passage automatique en mode nuit) : on suit, si aucun choix n'a été fait.
  useEffect(() => {
    const mq = media();
    const onChange = () => setSystem(mq.matches ? "dark" : "light");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => { document.documentElement.classList.toggle("dark", theme === "dark"); }, [theme]);

  const value = useMemo<ThemeState>(() => ({
    theme,
    toggle: () => {
      const next: Theme = theme === "dark" ? "light" : "dark";
      setChoice(next);
      try { localStorage.setItem(THEME_KEY, next); } catch { /* choix non conservé */ }
    },
  }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme doit être utilisé dans <ThemeProvider>");
  return ctx;
}
