// Squelette de l'application : en-tête (menu, langue, thème, déconnexion) + écran choisi dans l'adresse (#/...).
import { useAuth } from "./auth";
import { useI18n, type TranslationKey } from "./i18n";
import { hrefFor, menuPage, useRoute, type Route } from "./router";
import { Button, ErrorBox, Notice, Spinner } from "./components/ui";
import ThemeToggle from "./components/ThemeToggle";
import AuthPage from "./pages/AuthPage";
import AlertsPage from "./pages/AlertsPage";
import MachineDetailPage from "./pages/MachineDetailPage";
import MachinesPage from "./pages/MachinesPage";
import SettingsPage from "./pages/SettingsPage";

// Menu : un écran sera ajouté ici à chaque étape.
const MENU: { route: Route; label: TranslationKey }[] = [
  { route: { page: "machines" }, label: "nav.machines" },
  { route: { page: "alerts" }, label: "nav.alerts" },
  { route: { page: "settings" }, label: "nav.settings" },
];

function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <button type="button" onClick={() => setLang(lang === "fr" ? "en" : "fr")}
      className="rounded-md px-2 py-1 text-sm text-ink-soft underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      {t("lang.switch")}
    </button>
  );
}

/** Langue et thème : présents sur tous les écrans, même avant la connexion. */
function Preferences() {
  return <div className="flex items-center gap-1"><LangSwitch /><ThemeToggle /></div>;
}

function Page({ route }: { route: Route }) {
  switch (route.page) {
    case "machines": return <MachinesPage />;
    case "machine": return <MachineDetailPage key={route.id} id={route.id} />;
    case "alerts": return <AlertsPage />;
    case "settings": return <SettingsPage />;
  }
}

export default function App() {
  const { status, me, error, retry, logout } = useAuth();
  const { t } = useI18n();
  const route = useRoute();

  if (status === "loading") {
    return <div className="flex min-h-screen items-center justify-center"><Spinner /></div>;
  }

  if (status === "unreachable") {
    return (
      <>
        <div className="flex justify-end p-4"><Preferences /></div>
        <div className="mx-auto max-w-md space-y-4 px-4 py-6">
          <Notice tone="warning">{t("auth.unreachable")}</Notice>
          <ErrorBox error={error} onRetry={retry} />
          <Button variant="secondary" onClick={logout}>{t("auth.logout")}</Button>
        </div>
      </>
    );
  }

  if (status === "signedOut" || !me) {
    return (
      <>
        <div className="flex justify-end p-4"><Preferences /></div>
        <AuthPage />
      </>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="font-bold">{t("app.name")}</span>
            {me.organization && (
              <nav aria-label={t("nav.label")} className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                {MENU.map((item) => (
                  <a key={item.route.page} href={hrefFor(item.route)}
                    aria-current={menuPage(route) === item.route.page ? "page" : undefined}
                    className={menuPage(route) === item.route.page
                      ? "font-semibold text-accent-ink" : "text-ink-soft hover:text-ink"}>
                    {t(item.label)}
                  </a>
                ))}
              </nav>
            )}
          </div>
          <div className="flex items-center gap-3">
            {me.organization && (
              <span className="hidden text-sm text-ink-muted md:inline">
                {t("header.org", { org: me.organization.name, role: t(`role.${me.role}`) })}
              </span>
            )}
            <Preferences />
            <Button variant="secondary" onClick={logout}>{t("auth.logout")}</Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        {me.organization ? <Page route={route} /> : (
          <Notice tone="warning">
            <p className="font-medium">{t("home.superadminTitle")}</p>
            <p>{t("home.superadminText")}</p>
          </Notice>
        )}
      </main>
    </div>
  );
}
