// Page d'accueil après connexion. Les écrans Machines, Alertes, etc. viendront ensuite.
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { Notice } from "../components/ui";

export default function HomePage() {
  const { t } = useI18n();
  const { me } = useAuth();
  if (!me) return null;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("home.welcome", { name: me.full_name || me.email })}</h1>

      {me.organization ? (
        <>
          <ul className="rounded-lg bg-white p-4 text-sm shadow">
            <li>{t("home.org", { org: me.organization.name })}</li>
            <li>{t("home.role", { role: t(`role.${me.role}`) })}</li>
            <li>{t("home.plan", { plan: t(`plan.${me.organization.plan}`) })}</li>
          </ul>
          <Notice>
            <p className="font-medium">{t("home.soonTitle")}</p>
            <p>{t("home.soonText")}</p>
          </Notice>
        </>
      ) : (
        <Notice tone="warning">
          <p className="font-medium">{t("home.superadminTitle")}</p>
          <p>{t("home.superadminText")}</p>
        </Notice>
      )}
    </div>
  );
}
