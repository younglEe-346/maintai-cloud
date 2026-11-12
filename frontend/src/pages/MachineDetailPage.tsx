// Écran 4 : détail d'une machine. Graphique du risque, puis, pour la mesure choisie
// (la plus récente par défaut) : risque, mode de panne probable et contributions de chaque mesure.
import { useCallback, useState } from "react";
import {
  ApiError, machinesApi, parseApiDate, SENSORS,
  type FailureMode, type Machine, type MachineWithKey, type Measure, type Prediction, type Sensor,
} from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { hrefFor } from "../router";
import { Badge, Card, EmptyState, ErrorBox, Notice, Spinner } from "../components/ui";
import ConfirmAction from "../components/ConfirmAction";
import NewKeyDialog from "../components/NewKeyDialog";
import RiskChart from "../components/RiskChart";
import { usePolling } from "../hooks";

const REFRESH_MS = 10_000;

type Scored = Measure & { prediction: Prediction };

export default function MachineDetailPage({ id }: { id: string }) {
  const { t, formatDate } = useI18n();
  const { me } = useAuth();
  const canManage = me?.role === "owner" || me?.role === "admin";
  const [machine, setMachine] = useState<Machine | null | undefined>(undefined); // null = introuvable
  const [measures, setMeasures] = useState<Measure[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  // Mesure choisie, retenue par son identifiant : quand de nouvelles mesures arrivent,
  // la sélection ne glisse pas sur une autre. null = toujours montrer la plus récente.
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      // Pas de route « une machine » dans l'API : on prend la liste et on cherche la bonne.
      // Les deux appels partent en même temps ; une machine inconnue fait répondre 404 aux mesures.
      const [list, rows] = await Promise.all([machinesApi.list(), machinesApi.measures(id, 200)]);
      setMachine(list.find((m) => m.id === id) ?? null);
      setMeasures(rows);
      setLoadError(null);
    } catch (err) {
      if (err instanceof ApiError && err.kind === "notFound") setMachine(null);
      else setLoadError(err);
    }
  }, [id]);

  usePolling(load, REFRESH_MS);

  const back = <a href={hrefFor({ page: "machines" })} className="text-sm text-accent-ink hover:underline">{t("detail.back")}</a>;

  if (loadError != null && machine === undefined) return <div className="space-y-4">{back}<ErrorBox error={loadError} onRetry={() => void load()} /></div>;
  if (machine === undefined) return <Spinner />;
  if (machine === null) return <div className="space-y-4">{back}<Notice tone="warning">{t("detail.notFound")}</Notice></div>;

  // L'API renvoie les plus récentes d'abord ; le graphique veut l'ordre du temps.
  const scored = (measures ?? []).filter((m): m is Scored => m.prediction != null).reverse();
  const pending = (measures?.length ?? 0) - scored.length;
  const found = selectedId == null ? -1 : scored.findIndex((m) => m.id === selectedId);
  const index = found >= 0 ? found : scored.length - 1;
  const select = (i: number) => setSelectedId(i >= scored.length - 1 ? null : scored[i].id);

  return (
    <div className="space-y-6">
      {back}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-2xl font-bold">{machine.name}</h1>
        <Badge tone={machine.status === "ACTIVE" ? "success" : "neutral"}>{t(`status.${machine.status}`)}</Badge>
        <code className="text-xs text-ink-muted">{t("detail.keyPrefix", { prefix: machine.api_key_prefix })}</code>
      </div>

      {machine.status === "ARCHIVED" ? <Notice tone="warning">{t("manage.archivedNotice")}</Notice>
        : machine.api_key_revoked_at && (
          <Notice tone="danger">
            {t("manage.revokedNotice", { date: formatDate(parseApiDate(machine.api_key_revoked_at)) })}
          </Notice>
        )}
      {loadError != null && <ErrorBox error={loadError} onRetry={() => void load()} />}
      {pending > 0 && <Notice>{t("detail.pending", { n: String(pending) })}</Notice>}

      {measures == null ? <Spinner /> : scored.length === 0 ? (
        <EmptyState title={t("detail.emptyTitle")}>{t("detail.emptyText")}</EmptyState>
      ) : (
        <>
          <section className="space-y-2 rounded-lg border border-line bg-surface p-4 shadow-sm">
            <h2 className="text-lg font-semibold">{t("detail.chartTitle", { n: String(scored.length) })}</h2>
            <p className="text-sm text-ink-muted">{t("detail.chartHelp")}</p>
            <RiskChart
              points={scored.map((m) => ({ risk: m.prediction.risk_score, threshold: m.prediction.threshold }))}
              selected={index}
              onSelect={select}
            />
            <MeasureNav index={index} count={scored.length} measure={scored[index]} onSelect={select} />
          </section>

          <RiskSummary prediction={scored[index].prediction} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ModesPanel prediction={scored[index].prediction} />
            <ContributionsPanel measure={scored[index]} />
          </div>
        </>
      )}

      {canManage && machine.status === "ACTIVE" && <ManagePanel machine={machine} onChanged={load} />}
    </div>
  );
}

/** Remplacer / révoquer la clé, archiver la machine (propriétaire et administrateurs). */
function ManagePanel({ machine, onChanged }: { machine: Machine; onChanged: () => Promise<void> }) {
  const { t } = useI18n();
  const [newKey, setNewKey] = useState<MachineWithKey | null>(null);
  const [done, setDone] = useState<string | null>(null);

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">{t("manage.title")}</h2>
        <p className="text-sm text-ink-muted">{t("manage.intro")}</p>
      </div>
      {done && <Notice tone="success">{done}</Notice>}
      <div className="grid gap-3 md:grid-cols-3">
        <ConfirmAction label={t("manage.rotate")} help={t("manage.rotateHelp")} confirmLabel={t("manage.rotateConfirm")}
          onConfirm={async () => { setNewKey(await machinesApi.rotateKey(machine.id)); setDone(null); await onChanged(); }} />
        <ConfirmAction label={t("manage.revoke")} help={t("manage.revokeHelp")} confirmLabel={t("manage.revokeConfirm")}
          danger disabled={machine.api_key_revoked_at != null}
          onConfirm={async () => { await machinesApi.revokeKey(machine.id); setDone(t("manage.revokeDone")); await onChanged(); }} />
        <ConfirmAction label={t("manage.archive")} help={t("manage.archiveHelp")} confirmLabel={t("manage.archiveConfirm")}
          danger
          onConfirm={async () => { await machinesApi.archive(machine.id); setDone(t("manage.archiveDone")); await onChanged(); }} />
      </div>
      {newKey && (
        <NewKeyDialog key={newKey.api_key_created_at ?? newKey.id} machine={newKey} title={t("newKey.rotatedTitle", { name: newKey.name })}
          onClose={() => setNewKey(null)} />
      )}
    </Card>
  );
}

/** Boutons pour passer d'une mesure à l'autre au clavier (le graphique, lui, se clique). */
function MeasureNav({ index, count, measure, onSelect }:
  { index: number; count: number; measure: Measure; onSelect: (i: number) => void }) {
  const { t, formatDate } = useI18n();
  const btn = "rounded-md border border-line-strong bg-surface px-2 py-1 text-sm hover:bg-track disabled:text-ink-faint";
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm text-ink-soft" aria-live="polite">
        {t("detail.selected", {
          date: formatDate(parseApiDate(measure.timestamp)), pos: String(index + 1), n: String(count),
        })}
      </p>
      <div className="flex gap-2">
        <button className={btn} disabled={index === 0} onClick={() => onSelect(index - 1)}>{t("detail.prev")}</button>
        <button className={btn} disabled={index === count - 1} onClick={() => onSelect(index + 1)}>{t("detail.next")}</button>
        <button className={btn} disabled={index === count - 1} onClick={() => onSelect(count - 1)}>{t("detail.latest")}</button>
      </div>
    </div>
  );
}

function RiskSummary({ prediction: p }: { prediction: Prediction }) {
  const { t, formatPercent } = useI18n();
  return (
    <section className={`rounded-lg border-l-4 bg-surface p-4 shadow ${p.decision ? "border-l-danger" : "border-l-success"}`}>
      <p className="text-xs text-ink-muted">{t("detail.risk")}</p>
      <p className={`text-3xl font-bold ${p.decision ? "text-danger-ink" : "text-success-ink"}`}>{formatPercent(p.risk_score)}</p>
      <p className="text-sm">{t(p.decision ? "detail.above" : "detail.below", { threshold: formatPercent(p.threshold) })}</p>
      {p.explanation && <p className="mt-2 text-sm text-ink-soft">{t("alerts.details")} {p.explanation}</p>}
      <p className="mt-1 text-xs text-ink-faint">{t("detail.model", { version: p.model_version })}</p>
    </section>
  );
}

function ModesPanel({ prediction: p }: { prediction: Prediction }) {
  const { t, formatPercent } = useI18n();
  const probs = Object.entries(p.mode_probabilities ?? {}) as [FailureMode, number][];
  probs.sort((a, b) => b[1] - a[1]);
  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4 shadow-sm">
      <h2 className="text-lg font-semibold">{t("detail.modeTitle")}</h2>
      <p className="text-base font-semibold">{p.probable_mode ? t(`mode.${p.probable_mode}`) : t("detail.modeNone")}</p>
      {probs.length === 0 ? <p className="text-sm text-ink-muted">{t("detail.modesUnavailable")}</p> : (
        <>
          <p className="text-sm text-ink-muted">{t("detail.modeHelp")}</p>
          <ul className="space-y-2">
            {probs.map(([mode, value]) => {
              const flagged = p.flagged_modes?.includes(mode) ?? false;
              return (
                <li key={mode} className="text-sm">
                  <div className="flex justify-between gap-2">
                    <span className={flagged ? "font-semibold" : ""}>{t(`mode.${mode}`)}</span>
                    <span className={flagged ? "font-semibold" : "text-ink-soft"}>{formatPercent(value)}</span>
                  </div>
                  <div className="mt-1 h-2 rounded bg-track">
                    <div className={`h-2 rounded ${flagged ? "bg-danger" : "bg-ink-faint"}`}
                      style={{ width: `${Math.max(1, value * 100)}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}

function ContributionsPanel({ measure }: { measure: Scored }) {
  const { t, formatPercent, formatNumber } = useI18n();
  const p = measure.prediction;
  if (!p.contributions) {
    return (
      <section className="rounded-lg border border-line bg-surface p-4 shadow-sm">
        <h2 className="text-lg font-semibold">{t("detail.contribTitle")}</h2>
        <p className="text-sm text-ink-muted">{t("detail.contribUnavailable")}</p>
      </section>
    );
  }
  const unit = (s: Sensor) => (s === "rotational_speed" ? t("unit.rotational_speed")
    : s === "torque" ? "N·m" : s === "tool_wear" ? "min" : "K");
  const max = Math.max(...SENSORS.map((s) => Math.abs(p.contributions![s])), 1e-9);
  const rows = [...SENSORS].sort((a, b) => Math.abs(p.contributions![b]) - Math.abs(p.contributions![a]));

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4 shadow-sm">
      <h2 className="text-lg font-semibold">{t("detail.contribTitle")}</h2>
      {p.base_risk != null && (
        <p className="text-sm text-ink-muted">
          {t("detail.contribHelp", { base: formatPercent(p.base_risk), risk: formatPercent(p.risk_score) })}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-ink-muted">
            <tr>
              <th className="py-1 pr-2 font-medium">{t("detail.colSensor")}</th>
              <th className="py-1 pr-2 text-right font-medium">{t("detail.colValue")}</th>
              <th className="py-1 pr-2 text-right font-medium">{t("detail.colNormal")}</th>
              <th className="py-1 font-medium">{t("detail.colEffect")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const c = p.contributions![s];
              const pts = c * 100;   // 1 point = 1 % de risque
              return (
                <tr key={s} className="border-t border-line">
                  <td className="py-1.5 pr-2">{t(`sensor.${s}`)}</td>
                  <td className="whitespace-nowrap py-1.5 pr-2 text-right">{formatNumber(measure[s])} {unit(s)}</td>
                  <td className="whitespace-nowrap py-1.5 pr-2 text-right text-ink-muted">
                    {p.reference ? `${formatNumber(p.reference[s])} ${unit(s)}` : "—"}
                  </td>
                  <td className="min-w-40 py-1.5">
                    {/* barre centrée sur 0 : à droite (rouge) fait monter, à gauche (vert) fait baisser */}
                    <div className="flex items-center gap-2">
                      <div className="relative h-3 flex-1 rounded bg-track">
                        <div className="absolute inset-y-0 left-1/2 w-px bg-ink-faint" />
                        <div className={`absolute inset-y-0 rounded ${c >= 0 ? "left-1/2 bg-danger" : "right-1/2 bg-success"}`}
                          style={{ width: `${(Math.abs(c) / max) * 50}%` }} />
                      </div>
                      <span className={`w-16 text-right text-xs ${c > 0.005 ? "text-danger-ink" : c < -0.005 ? "text-success-ink" : "text-ink-muted"}`}>
                        {t("detail.points", { value: `${pts >= 0 ? "+" : ""}${formatNumber(pts, 1)}` })}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
