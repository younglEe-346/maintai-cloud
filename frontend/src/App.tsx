// Squelette de l'application : en-tête (langue, déconnexion) + écran selon l'état de connexion.
import { useAuth } from "./auth";
import { useI18n } from "./i18n";
import { Button, Spinner } from "./components/ui";
import AuthPage from "./pages/AuthPage";
import HomePage from "./pages/HomePage";

function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <button onClick={() => setLang(lang === "fr" ? "en" : "fr")}
      className="text-sm text-slate-600 underline-offset-2 hover:underline">
      {t("lang.switch")}
    </button>
  );
}

export default function App() {
  const { status, me, logout } = useAuth();
  const { t } = useI18n();

  if (status === "loading") {
    return <div className="flex min-h-screen items-center justify-center"><Spinner /></div>;
  }

  if (status === "signedOut") {
    return (
      <>
        <div className="flex justify-end p-4"><LangSwitch /></div>
        <AuthPage />
      </>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <span className="font-bold">{t("app.name")}</span>
          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-slate-500 sm:inline">{me?.email}</span>
            <LangSwitch />
            <Button variant="secondary" onClick={logout}>{t("auth.logout")}</Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <HomePage />
      </main>
    </div>
  );
}
