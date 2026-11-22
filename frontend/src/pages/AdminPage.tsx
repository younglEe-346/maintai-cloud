// Écran du super-administrateur (équipe MaintAI) : suivi des usines et des workers.
// Il voit des compteurs (machines, mesures du jour, alertes actives), jamais les mesures
// ni les clés d'une usine : les données des clients restent privées.
import { useCallback, useMemo, useState } from "react";
import { adminApi, parseApiDate, type AdminOrganization, type WorkersStatus } from "../api";
import { useI18n } from "../i18n";
import { usePolling } from "../hooks";
import { Badge, Card, EmptyState, ErrorBox, Field, Meter, Notice, PageHeader, SelectField, Spinner, Button, table } from "../components/ui";
import ConfirmAction from "../components/ConfirmAction";

const REFRESH_MS = 15_000;

type SortKey = "name" | "machines" | "alerts" | "last";

/** Texte sans accents ni majuscules : « Équipe » est trouvé en tapant « equipe ». */
const normalize = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

export default function AdminPage() {
  const { t, formatTime } = useI18n();
  const [orgs, setOrgs] = useState<AdminOrganization[] | null>(null);
  const [workers, setWorkers] = useState<WorkersStatus | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const [o, w] = await Promise.all([adminApi.organizations(), adminApi.workers()]);
      setOrgs(o);
      setWorkers(w);
      setLoadedAt(new Date());
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, []);

  usePolling(load, REFRESH_MS);

  return (
    <div className="space-y-6">
      <PageHeader title={t("admin.title")} intro={t("admin.intro")}
        actions={<>
          {loadedAt && <span className="text-xs text-ink-muted">{t("common.updatedAt", { time: formatTime(loadedAt) })}</span>}
          <Button variant="secondary" onClick={() => void load()}>{t("common.refresh")}</Button>
        </>} />
      {error != null && <ErrorBox error={error} onRetry={() => void load()} />}
      {workers && <WorkersCard status={workers} />}
      {orgs == null ? (error == null && <Spinner />) : orgs.length === 0
        ? <EmptyState title={t("admin.noOrgs")}>{t("admin.noOrgsText")}</EmptyState>
        : <OrgsTable orgs={orgs} onChanged={load} />}
    </div>
  );
}

function WorkersCard({ status }: { status: WorkersStatus }) {
  const { t, formatNumber } = useI18n();
  const online = status.workers.length;
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">{t("admin.workersTitle")}</h2>
        <Badge tone={online > 0 ? "success" : "danger"}>{t("admin.workersOnline", { n: String(online) })}</Badge>
        <span className="text-sm text-ink-muted">
          {status.queued_tasks == null ? t("admin.queueUnknown") : t("admin.queue", { n: formatNumber(status.queued_tasks, 0) })}
        </span>
      </div>
      {online === 0 ? <Notice tone="danger">{t("admin.noWorker")}</Notice> : (
        <ul className="grid gap-2 md:grid-cols-2">
          {status.workers.map((w) => (
            <li key={w.name} className="rounded-md border border-line p-3 text-sm">
              <p className="break-all font-medium">{w.name}</p>
              <p className="text-ink-soft">{t("admin.workerLine", {
                active: String(w.active_tasks), processes: String(w.processes),
                done: formatNumber(Object.values(w.tasks_done).reduce((a, b) => a + b, 0), 0),
              })}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function OrgsTable({ orgs, onChanged }: { orgs: AdminOrganization[]; onChanged: () => Promise<void> }) {
  const { t, lang, formatDate, formatNumber } = useI18n();
  // Recherche, filtre et tri se font ici, dans le navigateur, sur les données déjà reçues : l'API ne change pas.
  // Ces choix sont gardés quand la liste se rafraîchit toute seule (le composant reste affiché).
  const [query, setQuery] = useState("");
  const [onlyAlerts, setOnlyAlerts] = useState(false);
  const [sort, setSort] = useState<SortKey>("name");

  const shown = useMemo(() => {
    const needle = normalize(query);
    const lastTime = (o: AdminOrganization) => (o.last_measure_at ? parseApiDate(o.last_measure_at).getTime() : 0);
    const compare: Record<SortKey, (a: AdminOrganization, b: AdminOrganization) => number> = {
      name: (a, b) => a.name.localeCompare(b.name, lang),
      machines: (a, b) => b.machines - a.machines,
      alerts: (a, b) => b.active_alerts - a.active_alerts,
      last: (a, b) => lastTime(b) - lastTime(a),
    };
    return orgs
      .filter((o) => (needle === "" || normalize(o.name).includes(needle)) && (!onlyAlerts || o.active_alerts > 0))
      .sort((a, b) => compare[sort](a, b) || a.name.localeCompare(b.name, lang));
  }, [orgs, query, onlyAlerts, sort, lang]);

  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{t("admin.orgsTitle", { n: String(orgs.length) })}</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <Field id="admin-search" type="search" label={t("admin.search")} placeholder={t("admin.searchPlaceholder")}
          value={query} onChange={(e) => setQuery(e.target.value)} />
        <SelectField id="admin-sort" label={t("admin.sort")} value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
          <option value="name">{t("admin.sortName")}</option>
          <option value="machines">{t("admin.sortMachines")}</option>
          <option value="alerts">{t("admin.sortAlerts")}</option>
          <option value="last">{t("admin.sortLast")}</option>
        </SelectField>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <label className="flex items-center gap-2 text-ink-soft">
          <input type="checkbox" checked={onlyAlerts} onChange={(e) => setOnlyAlerts(e.target.checked)} />
          {t("admin.onlyAlerts")}
        </label>
        <span className="text-ink-muted" aria-live="polite">
          {t("admin.count", { shown: String(shown.length), total: String(orgs.length) })}
        </span>
      </div>
      {shown.length === 0 && <Notice tone="info">{t("admin.noMatch")}</Notice>}
      <div className={table.wrap}>
        <table className={table.table}>
          <thead className={table.head}>
            <tr>
              <th className={table.th}>{t("admin.colOrg")}</th>
              <th className={table.th}>{t("admin.colPlan")}</th>
              <th className={table.th}>{t("plan.machines")}</th>
              <th className={table.th}>{t("plan.measures")}</th>
              <th className={table.th}>{t("admin.colAlerts")}</th>
              <th className={table.th}>{t("admin.colLast")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((o) => (
              <tr key={o.id} className={`${table.row} align-top`}>
                <td className={table.td}>
                  <p className="font-medium">{o.name}</p>
                  <p className="text-xs text-ink-muted">{t("admin.orgMeta", {
                    members: String(o.members), model: o.model, date: formatDate(parseApiDate(o.created_at)),
                  })}</p>
                </td>
                <td className={`${table.td} min-w-44 space-y-2`}>
                  <Badge tone={o.plan === "PRO" ? "info" : "neutral"}>{t(`plan.${o.plan}`)}</Badge>
                  <ConfirmAction
                    key={o.plan}
                    label={t(o.plan === "FREE" ? "admin.toPro" : "admin.toFree")}
                    help={t("admin.planHelp", { org: o.name })}
                    confirmLabel={t("admin.planConfirm")}
                    onConfirm={async () => { await adminApi.setPlan(o.id, o.plan === "FREE" ? "PRO" : "FREE"); await onChanged(); }}
                  />
                </td>
                <td className={`${table.td} min-w-32 space-y-1`}>
                  <span>{formatNumber(o.machines, 0)} / {formatNumber(o.max_machines, 0)}</span>
                  <Meter value={o.machines} max={o.max_machines} label={t("plan.machines")} />
                </td>
                <td className={`${table.td} min-w-36 space-y-1`}>
                  <span>{formatNumber(o.measures_today, 0)} / {formatNumber(o.max_measures_per_day, 0)}</span>
                  <Meter value={o.measures_today} max={o.max_measures_per_day} label={t("plan.measures")} />
                </td>
                <td className={table.td}>
                  {o.active_alerts > 0 ? <Badge tone="danger">{formatNumber(o.active_alerts, 0)}</Badge> : <span className="text-ink-muted">0</span>}
                </td>
                <td className={`${table.td} whitespace-nowrap text-ink-soft`}>
                  {o.last_measure_at ? formatDate(parseApiDate(o.last_measure_at)) : t("admin.never")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
