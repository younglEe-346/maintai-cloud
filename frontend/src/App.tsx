// Squelette de l'application : en-tête (menu, langue, déconnexion) + écran choisi dans l'adresse (#/...).
import { useAuth } from "./auth";
import { useI18n, type TranslationKey } from "./i18n";
import { hrefFor, menuPage, useRoute, type Route } from "./router";
import { Button, ErrorBox, Notice, Spinner } from "./components/ui";
import AuthPage from "./pages/AuthPage";
import AlertsPage from "./pages/AlertsPage";
import MachineDetailPage from "./pages/MachineDetailPage";
import MachinesPage from "./pages/MachinesPage";

// Menu : un écran sera ajouté ici à chaque étape.
const MENU: { route: Route; label: TranslationKey }[] = [
  { route: { page: "machines" }, label: "nav.machines" },
  { route: { page: "alerts" }, label: "nav.alerts" },
];

function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <button onClick={() => setLang(lang === "fr" ? "en" : "fr")}
      className="text-sm text-slate-600 underline-offset-2 hover:underline">
      {t("lang.switch")}
    </button>
  );
}

function Page({ route }: { route: Route }) {
  switch (route.page) {
    case "machines": return <MachinesPage />;
    case "machine": return <MachineDetailPage key={route.id} id={route.id} />;
    case "alerts": return <AlertsPage />;
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
      <div className="mx-auto max-w-md space-y-4 px-4 py-10">
        <Notice tone="warning">{t("auth.unreachable")}</Notice>
        <ErrorBox error={error} onRetry={retry} />
        <Button variant="secondary" onClick={logout}>{t("auth.logout")}</Button>
      </div>
    );
  }

  if (status === "signedOut" || !me) {
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
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="font-bold">{t("app.name")}</span>
            {me.organization && (
              <nav className="flex gap-4 text-sm">
                {MENU.map((item) => (
                  <a key={item.route.page} href={hrefFor(item.route)}
                    aria-current={menuPage(route) === item.route.page ? "page" : undefined}
                    className={menuPage(route) === item.route.page
                      ? "font-semibold text-blue-700" : "text-slate-600 hover:text-slate-900"}>
                    {t(item.label)}
                  </a>
                ))}
              </nav>
            )}
          </div>
          <div className="flex items-center gap-4">
            {me.organization && (
              <span className="hidden text-sm text-slate-500 md:inline">
                {t("header.org", { org: me.organization.name, role: t(`role.${me.role}`) })}
              </span>
            )}
            <LangSwitch />
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
