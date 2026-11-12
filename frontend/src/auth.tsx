// Session de l'utilisateur : jeton JWT + profil (GET /auth/me), partagés par toute l'application.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, authApi, setUnauthorizedHandler, tokenStore, type Me, type RegisterInput } from "./api";

/**
 * - loading     : on vérifie le jeton gardé dans le navigateur ;
 * - signedOut   : personne n'est connecté ;
 * - signedIn    : `me` contient le profil ;
 * - unreachable : un jeton existe mais l'API ne répond pas (on ne déconnecte PAS l'utilisateur).
 */
type Status = "loading" | "signedOut" | "signedIn" | "unreachable";

interface Auth {
  status: Status;
  me: Me | null;
  /** Vrai si l'utilisateur a été déconnecté parce que son jeton a expiré. */
  expired: boolean;
  /** Erreur du dernier essai quand status = unreachable. */
  error: unknown;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  /** Connexion avec un jeton déjà obtenu (ex. après acceptation d'une invitation). */
  startSession: (token: string) => Promise<void>;
  /** Relit le profil (après un changement de plan, de rôle…). */
  refreshMe: () => Promise<void>;
  /** Nouvel essai quand l'API était injoignable au chargement. */
  retry: () => void;
  logout: () => void;
}

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(tokenStore.get() ? "loading" : "signedOut");
  const [me, setMe] = useState<Me | null>(null);
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const logout = useCallback(() => {
    tokenStore.clear();
    setMe(null);
    setStatus("signedOut");
  }, []);

  // Jeton reçu -> on le garde, puis on demande qui est connecté.
  const startSession = useCallback(async (token: string) => {
    tokenStore.set(token);
    try {
      setMe(await authApi.me());
    } catch (err) {
      tokenStore.clear();   // profil illisible : on ne garde pas un jeton à moitié utilisé
      throw err;
    }
    setExpired(false);
    setStatus("signedIn");
  }, []);

  // Au chargement de la page : un jeton est déjà gardé ? on vérifie qu'il est encore valide.
  const restore = useCallback(() => {
    if (!tokenStore.get()) return;
    setStatus("loading");
    authApi.me()
      .then((profile) => { setMe(profile); setStatus("signedIn"); })
      .catch((err: unknown) => {
        // API éteinte ou en panne : le jeton est peut-être encore bon, on le garde et on propose de réessayer.
        if (err instanceof ApiError && (err.kind === "network" || err.kind === "server")) {
          setError(err);
          setStatus("unreachable");
        } else {
          logout();
        }
      });
  }, [logout]);

  useEffect(() => {
    // Toute réponse 401 de l'API (jeton expiré) ramène à l'écran de connexion.
    setUnauthorizedHandler(() => { setExpired(true); logout(); });
    restore();
  }, [logout, restore]);

  const refreshMe = useCallback(async () => { setMe(await authApi.me()); }, []);

  const value = useMemo<Auth>(() => ({
    status, me, expired, error, startSession, refreshMe, logout, retry: restore,
    login: async (email, password) => startSession((await authApi.login(email, password)).access_token),
    register: async (input) => startSession((await authApi.register(input)).access_token),
  }), [status, me, expired, error, startSession, refreshMe, logout, restore]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans <AuthProvider>");
  return ctx;
}
