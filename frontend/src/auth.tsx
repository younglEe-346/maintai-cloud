// Session de l'utilisateur : jeton JWT + profil (GET /auth/me), partagés par toute l'application.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { authApi, setUnauthorizedHandler, tokenStore, type Me, type RegisterInput } from "./api";

type Status = "loading" | "signedOut" | "signedIn";

interface Auth {
  status: Status;
  me: Me | null;
  /** Vrai si l'utilisateur a été déconnecté parce que son jeton a expiré. */
  expired: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(tokenStore.get() ? "loading" : "signedOut");
  const [me, setMe] = useState<Me | null>(null);
  const [expired, setExpired] = useState(false);

  const logout = useCallback(() => {
    tokenStore.clear();
    setMe(null);
    setStatus("signedOut");
  }, []);

  // Jeton reçu -> on le garde, puis on demande qui est connecté.
  const startSession = useCallback(async (token: string) => {
    tokenStore.set(token);
    setMe(await authApi.me());
    setExpired(false);
    setStatus("signedIn");
  }, []);

  useEffect(() => {
    // Toute réponse 401 de l'API (jeton expiré) ramène à l'écran de connexion.
    setUnauthorizedHandler(() => { setExpired(true); logout(); });
    // Au chargement de la page : un jeton est déjà gardé ? on vérifie qu'il est encore valide.
    if (tokenStore.get()) {
      authApi.me()
        .then((profile) => { setMe(profile); setStatus("signedIn"); })
        .catch(() => logout());
    }
  }, [logout]);

  const login = async (email: string, password: string) =>
    startSession((await authApi.login(email, password)).access_token);

  const register = async (input: RegisterInput) =>
    startSession((await authApi.register(input)).access_token);

  return (
    <AuthContext.Provider value={{ status, me, expired, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans <AuthProvider>");
  return ctx;
}
