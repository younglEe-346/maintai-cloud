// Écran 3 : alertes actives (avec acquittement) et historique des alertes fermées.
// La page se recharge toute seule toutes les 10 secondes : une nouvelle alerte apparaît sans rien faire.
import { useCallback, useState, type FormEvent } from "react";
import { ApiError, alertsApi, machinesApi, parseApiDate, type Alert } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { Button, ErrorBox, Notice, Spinner } from "../components/ui";
import { usePolling, useTimeout } from "../hooks";

const REFRESH_MS = 10_000;

interface Data { active: Alert[]; closed: Alert[]; machineNames: Map<string, string>; loadedAt: Date; }

export default function AlertsPage() {
  const { t, formatTime } = useI18n();
  const [data, setData] = useState<Data | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  const load = useCallback(async () => {
    try {
      // Trois appels en parallèle ; les noms des machines servent à afficher « Tour CN 1 » au lieu d'un identifiant.
      const [active, closed, machines] = await Promise.all([
        alertsApi.list("active"), alertsApi.list("CLOSED", 20), machinesApi.list(),
      ]);
      setData({ active, closed, machineNames: new Map(machines.map((m) => [m.id, m.name])), loadedAt: new Date() });
      setLoadError(null);
    } catch (err) {
      setLoadError(err);   // on garde les dernières données affichées, avec le message d'erreur au-dessus
    }
  }, []);

  usePolling(load, REFRESH_MS);   // s'arrête tout seul quand on quitte la page

  const machineName = (id: string) => data?.machineNames.get(id) ?? t("alerts.unknownMachine");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-bold">{t("alerts.title")}</h1>
          <p className="text-slate-500">{t("alerts.intro")}</p>
        </div>
        <div className="flex items-center gap-3">
          {data && <span className="text-xs text-slate-500">{t("common.updatedAt", { time: formatTime(data.loadedAt) })}</span>}
          <Button variant="secondary" onClick={() => void load()}>{t("common.refresh")}</Button>
        </div>
      </div>

      {loadError != null && <ErrorBox error={loadError} onRetry={() => void load()} />}
      {data == null ? (loadError == null && <Spinner />) : (
        <>
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">{t("alerts.activeTitle")} ({data.active.length})</h2>
            {data.active.length === 0 ? (
              <div className="rounded-lg border-2 border-dashed border-slate-300 p-6 text-center">
                <p className="font-medium">{t("alerts.emptyActiveTitle")}</p>
                <p className="mt-1 text-sm text-slate-500">{t("alerts.emptyActiveText")}</p>
              </div>
            ) : (
              data.active.map((a) => (
                <AlertCard key={a.id} alert={a} machineName={machineName(a.machine_id)} onChanged={() => void load()} />
              ))
            )}
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">{t("alerts.historyTitle")}</h2>
            {data.closed.length === 0
              ? <p className="text-sm text-slate-500">{t("alerts.emptyHistory")}</p>
              : <HistoryTable alerts={data.closed} machineName={machineName} />}
          </section>
        </>
      )}
    </div>
  );
}

function ModeText({ alert }: { alert: Alert }) {
  const { t } = useI18n();
  return <>{alert.probable_mode ? t(`mode.${alert.probable_mode}`) : t("mode.none")}</>;
}

function AlertCard({ alert, machineName, onChanged }: { alert: Alert; machineName: string; onChanged: () => void }) {
  const { t, formatDate, formatPercent } = useI18n();
  const [ackOpen, setAckOpen] = useState(false);
  const open = alert.status === "OPEN";

  const risks: [string, number | null][] = [
    [t("alerts.riskOpen"), alert.risk_score],
    [t("alerts.riskPeak"), alert.peak_risk_score],
    [t("alerts.riskLast"), alert.last_risk_score],
  ];

  return (
    <article className={`rounded-lg border-l-4 bg-white p-4 shadow ${open ? "border-red-500" : "border-amber-400"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">{machineName}</h3>
          <p className="text-xs text-slate-500">{t("alerts.openedAt", { date: formatDate(parseApiDate(alert.created_at)) })}</p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
          open ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>
          {t(`alerts.status.${alert.status}`)}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {risks.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="font-semibold">{value == null ? "—" : formatPercent(value)}</dd>
          </div>
        ))}
        <div>
          <dt className="text-xs text-slate-500">{t("alerts.mode")}</dt>
          <dd className="font-semibold"><ModeText alert={alert} /></dd>
        </div>
      </dl>

      {alert.details && (
        <p className="mt-3 text-sm text-slate-700">
          <span className="text-slate-500">{t("alerts.details")} </span>{alert.details}
        </p>
      )}

      {alert.status === "ACKNOWLEDGED" ? (
        <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          <p>{t("alerts.ackBy", {
            name: alert.acknowledged_by_name ?? "—",
            date: alert.acknowledged_at ? formatDate(parseApiDate(alert.acknowledged_at)) : "—",
          })}</p>
          {alert.ack_comment && <p className="mt-1">{t("alerts.ackComment", { comment: alert.ack_comment })}</p>}
          <p className="mt-1 text-xs">{t("alerts.ackStaysActive")}</p>
        </div>
      ) : ackOpen ? (
        <AckForm alertId={alert.id} onCancel={() => setAckOpen(false)} onDone={() => { setAckOpen(false); onChanged(); }} />
      ) : (
        <div className="mt-3">
          <Button onClick={() => setAckOpen(true)}>{t("alerts.ackButton")}</Button>
        </div>
      )}
    </article>
  );
}

function AckForm({ alertId, onCancel, onDone }: { alertId: string; onCancel: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const { me } = useAuth();
  const [comment, setComment] = useState("");
  const [apiError, setApiError] = useState<unknown>(null);
  const [sending, setSending] = useState(false);
  const later = useTimeout();
  const tooLong = comment.trim().length > 2000;   // même limite que l'API (AcknowledgeIn)

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (tooLong) return;
    setSending(true);
    setApiError(null);
    try {
      await alertsApi.acknowledge(alertId, comment.trim());
      onDone();
    } catch (err) {
      setApiError(err);
      // 409 : quelqu'un d'autre l'a acquittée (ou elle s'est fermée) entre-temps : on recharge la liste.
      if (err instanceof ApiError && err.kind === "conflict") later(onDone, 3000);
    } finally {
      setSending(false);
    }
  }

  const name = me?.full_name || me?.email || "";
  const commentId = `ack-comment-${alertId}`;

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
      <h4 className="text-sm font-semibold">{t("alerts.ackFormTitle")}</h4>
      <div>
        <p className="text-xs text-slate-500">{t("alerts.ackAs")}</p>
        <p className="text-sm font-medium">{name}</p>
        <p className="text-xs text-slate-500">{t("alerts.ackAsHint")}</p>
      </div>
      <div className="space-y-1">
        <label htmlFor={commentId} className="block text-sm font-medium text-slate-700">{t("alerts.comment")}</label>
        <textarea
          id={commentId}
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          aria-invalid={tooLong || undefined}
          className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 ${
            tooLong ? "border-red-400 focus:ring-red-300" : "border-slate-300 focus:ring-blue-300"}`}
        />
        <p className={`text-xs ${tooLong ? "text-red-600" : "text-slate-500"}`}>
          {tooLong ? t("alerts.commentTooLong") : t("alerts.commentHint")}
        </p>
      </div>
      {apiError != null && <ErrorBox error={apiError} />}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={sending || tooLong}>{sending ? t("alerts.acking") : t("alerts.ackConfirm")}</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>{t("common.cancel")}</Button>
      </div>
      <Notice>{t("alerts.ackStaysActive")}</Notice>
    </form>
  );
}

function HistoryTable({ alerts, machineName }: { alerts: Alert[]; machineName: (id: string) => string }) {
  const { t, formatDate, formatPercent } = useI18n();
  const cell = "px-4 py-2";
  return (
    <div className="overflow-x-auto rounded-lg bg-white shadow">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500">
          <tr>
            {(["alerts.colMachine", "alerts.colOpened", "alerts.colClosed", "alerts.colPeak", "alerts.colMode", "alerts.colAck"] as const)
              .map((key) => <th key={key} className={`${cell} font-medium`}>{t(key)}</th>)}
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => (
            <tr key={a.id} className="border-b border-slate-100 last:border-0">
              <td className={`${cell} font-medium`}>{machineName(a.machine_id)}</td>
              <td className={`${cell} whitespace-nowrap`}>{formatDate(parseApiDate(a.created_at))}</td>
              <td className={`${cell} whitespace-nowrap`}>{a.closed_at ? formatDate(parseApiDate(a.closed_at)) : "—"}</td>
              <td className={cell}>{formatPercent(a.peak_risk_score ?? a.risk_score)}</td>
              <td className={cell}><ModeText alert={a} /></td>
              <td className={cell}>
                {a.acknowledged_by_name ?? "—"}
                {a.ack_comment && <span className="block text-xs text-slate-500">{a.ack_comment}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
