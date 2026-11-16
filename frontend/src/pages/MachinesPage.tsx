// Écran 2 : liste des machines de l'usine et ajout d'une machine.
// La clé d'API complète n'est montrée qu'une fois, juste après l'ajout (NewKeyDialog).
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ApiError, machinesApi, orgApi, parseApiDate,
  type Machine, type MachineWithKey, type Organization,
} from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { Badge, Button, EmptyState, ErrorBox, Field, Notice, Spinner } from "../components/ui";
import NewKeyDialog from "../components/NewKeyDialog";
import { hrefFor } from "../router";

export default function MachinesPage() {
  const { t } = useI18n();
  const { me } = useAuth();
  const canManage = me?.role === "owner" || me?.role === "admin";

  const [machines, setMachines] = useState<Machine[] | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [newMachine, setNewMachine] = useState<MachineWithKey | null>(null);

  // Charge (ou recharge) la liste et la consommation du plan, en parallèle.
  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [list, organization] = await Promise.all([machinesApi.list(), orgApi.get()]);
      setMachines(list);
      setOrg(organization);
    } catch (err) {
      setLoadError(err);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const limitReached = org != null && org.machines >= org.limits.max_machines;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t("machines.title")}</h1>
        <p className="text-ink-muted">{t("machines.intro")}</p>
        {org && (
          <p className="mt-1 text-sm text-ink-soft">
            {t("machines.usage", {
              count: String(org.machines), max: String(org.limits.max_machines), plan: t(`plan.${org.plan}`),
            })}
          </p>
        )}
      </div>

      {canManage ? (
        limitReached
          ? <Notice tone="warning">{t("machines.limitReached")}</Notice>
          : <AddMachineForm onCreated={(m) => { setNewMachine(m); void load(); }} />
      ) : (
        <Notice>{t("machines.memberOnly")}</Notice>
      )}

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t("machines.listTitle")}</h2>
        {loadError != null ? (
          <ErrorBox error={loadError} onRetry={() => void load()} />
        ) : machines == null ? (
          <Spinner />
        ) : machines.length === 0 ? (
          <EmptyState title={t("machines.emptyTitle")}>{t(canManage ? "machines.emptyText" : "machines.emptyMember")}</EmptyState>
        ) : (
          <MachineTable machines={machines} />
        )}
      </section>

      {newMachine && <NewKeyDialog key={newMachine.id} machine={newMachine} onClose={() => setNewMachine(null)} />}
    </div>
  );
}

function AddMachineForm({ onCreated }: { onCreated: (m: MachineWithKey) => void }) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [fieldError, setFieldError] = useState<string>();
  const [apiError, setApiError] = useState<unknown>(null);
  const [sending, setSending] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setApiError(null);
    const clean = name.trim();
    // Mêmes règles que l'API (MachineCreate) : 1 à 100 caractères.
    if (!clean) return setFieldError(t("valid.required"));
    if (clean.length > 100) return setFieldError(t("machines.nameTooLong"));
    setFieldError(undefined);

    setSending(true);
    try {
      const created = await machinesApi.create(clean);
      setName("");
      onCreated(created);
    } catch (err) {
      if (err instanceof ApiError && err.kind === "validation") setFieldError(t("valid.required"));
      setApiError(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3 rounded-lg border border-line bg-surface p-4 shadow-sm">
      <h2 className="text-lg font-semibold">{t("machines.addTitle")}</h2>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="flex-1">
          <Field id="machine-name" label={t("machines.name")} hint={t("machines.nameHint")} maxLength={100}
            value={name} onChange={(e) => setName(e.target.value)} error={fieldError} />
        </div>
        <Button type="submit" disabled={sending} className="sm:mt-6">
          {sending ? t("machines.adding") : t("machines.add")}
        </Button>
      </div>
      {apiError != null && <ErrorBox error={apiError} />}
    </form>
  );
}

function MachineTable({ machines }: { machines: Machine[] }) {
  const { t, formatDate } = useI18n();
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-lg border border-line bg-surface shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line text-ink-muted">
            <tr>
              <th className="px-4 py-2 font-medium">{t("machines.colName")}</th>
              <th className="px-4 py-2 font-medium">{t("machines.colStatus")}</th>
              <th className="px-4 py-2 font-medium">{t("machines.colKey")}</th>
              <th className="px-4 py-2 font-medium">{t("machines.colCreated")}</th>
            </tr>
          </thead>
          <tbody>
            {machines.map((m) => (
              <tr key={m.id} className="border-b border-line last:border-0">
                <td className="px-4 py-2 font-medium">
                  <a href={hrefFor({ page: "machine", id: m.id })} className="text-accent-ink hover:underline">{m.name}</a>
                </td>
                <td className="px-4 py-2">
                  <Badge tone={m.status === "ACTIVE" ? "success" : "neutral"}>{t(`status.${m.status}`)}</Badge>
                </td>
                <td className="px-4 py-2">
                  <code className="text-xs">{m.api_key_prefix}…</code>{" "}
                  <span className={`text-xs ${m.api_key_revoked_at ? "text-danger-ink" : "text-ink-muted"}`}>
                    ({t(m.api_key_revoked_at ? "key.revoked" : "key.active")})
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-2 text-ink-soft">{formatDate(parseApiDate(m.created_at))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-ink-muted">{t("machines.openHint")} {t("machines.keyHelp")}</p>
    </div>
  );
}
