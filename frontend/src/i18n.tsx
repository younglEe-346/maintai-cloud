// Traductions français / anglais, sans bibliothèque : un dictionnaire par langue,
// rangés dans src/locales/ (fr.ts = référence, en.ts = même clés, TypeScript vérifie).
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError } from "./api";
import { fr, type TranslationKey } from "./locales/fr";
import { en, SERVER_MESSAGES_EN, SERVER_PATTERNS_EN } from "./locales/en";

export type { TranslationKey };
type Key = TranslationKey;

function translateServerMessage(message: string): string {
  if (SERVER_MESSAGES_EN[message]) return SERVER_MESSAGES_EN[message];
  for (const [pattern, english] of SERVER_PATTERNS_EN) {
    if (pattern.test(message)) return message.replace(pattern, english);
  }
  return message;
}

export type Lang = "fr" | "en";
const DICTS: Record<Lang, Record<Key, string>> = { fr, en };
const LANG_KEY = "maintai.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved === "fr" || saved === "en") return saved;
  } catch { /* stockage indisponible */ }
  return navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en";
}

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Texte traduit ; {nom} est remplacé par vars.nom. */
  t: (key: Key, vars?: Record<string, string>) => string;
  /** Date et heure dans la langue choisie (ex. 10 nov. 2026, 23:31). */
  formatDate: (date: Date) => string;
  /** Heure seule (ex. 23:31:05). */
  formatTime: (date: Date) => string;
  /** Pourcentage (0,987 -> 98,7 %). */
  formatPercent: (value: number) => string;
  /** Nombre dans la langue choisie (ex. 39,9 ou 39.9). */
  formatNumber: (value: number, maxDigits?: number) => string;
  /** Message lisible pour une erreur (ApiError ou autre). */
  errorText: (error: unknown) => { title: string; detail: string };
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  // Langue de la page (lecteurs d'écran, césure) : effet de bord, donc dans un useEffect.
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  // Toutes les fonctions ne changent que si la langue change : les écrans ne se redessinent pas pour rien.
  const value = useMemo<I18n>(() => {
    const locale = lang === "fr" ? "fr-FR" : "en-GB";
    const t: I18n["t"] = (key, vars) =>
      DICTS[lang][key].replace(/\{(\w+)\}/g, (_, name: string) => vars?.[name] ?? "");
    return {
      lang,
      t,
      setLang: (next) => {
        setLangState(next);
        try { localStorage.setItem(LANG_KEY, next); } catch { /* rien */ }
      },
      formatDate: (date) => date.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" }),
      formatTime: (date) => date.toLocaleTimeString(locale),
      formatPercent: (value) =>
        value.toLocaleString(locale, { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }),
      formatNumber: (value, maxDigits = 1) => value.toLocaleString(locale, { maximumFractionDigits: maxDigits }),
      errorText: (error) => {
        if (!(error instanceof ApiError)) return { title: t("error.other"), detail: String(error) };
        const detail = lang === "en" ? translateServerMessage(error.detail) : error.detail;
        // Refus simple (400) avec une explication du serveur : l'explication suffit comme titre.
        if (error.kind === "other" && detail) return { title: detail, detail: "" };
        return { title: t(`error.${error.kind}`), detail };
      },
    };
  }, [lang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n doit être utilisé dans <I18nProvider>");
  return ctx;
}
