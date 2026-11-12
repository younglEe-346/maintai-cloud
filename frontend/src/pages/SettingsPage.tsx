// Écran 5 : réglages de l'usine.
// 1. Coût d'une panne manquée -> seuil d'alerte recalculé (aperçu en direct avant d'enregistrer).
// 2. Règles d'ouverture / fermeture des alertes.
// 3. Plan et consommation (changement de plan par le propriétaire, paiement simulé).
// 4. Export CSV (plan Pro) et 5. modèle d'IA (réentraînement, plan Pro).
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  exportApi, modelsApi, orgApi, parseApiDate,
  type ModelsOverview, type Organization, type OrgSettings, type SettingsInput, type ThresholdPreview,
} from "../api";
import { useAuth } from "../auth";
import { useI18n, type TranslationKey } from "../i18n";
import { usePolling } from "../hooks";
import {
  Badge, Button, Card, ErrorBox, Field, Meter, Notice, PageHeader, Spinner, table,
} from "../components/ui";
import ConfirmAction from "../components/ConfirmAction";

/** Lit un nombre tapé par l'utilisateur ; accepte la virgule française (« 0,5 »). */
function parseNumber(text: string): number {
  const clean = text.trim().replace(",", ".");
  return clean === "" ? NaN : Number(clean);
}

const isInt = (n: number) => Number.isInteger(n);

export default function SettingsPage() {
  const { t } = useI18n();
  const { me } = useAuth();
  const canEdit = me?.role === "owner" || me?.role === "admin";

  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [s, o] = await Promise.all([orgApi.settings(), orgApi.get()]);
      setSettings(s);
      setOrg(o);
    } catch (err) {
      setLoadError(err);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="space-y-6">
      <PageHeader title={t("settings.title")} intro={t("settings.intro")} />
      {!canEdit && <Notice>{t("settings.readOnly")}</Notice>}
      {loadError != null && <ErrorBox error={loadError} onRetry={() => void load()} />}
      {settings == null || org == null ? (loadError == null && <Spinner />) : (
        <>
          <ThresholdForm settings={settings} canEdit={canEdit} onSaved={setSettings} />
          <PlanCard org={org} onChanged={setOrg} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ExportCard org={org} canEdit={canEdit} />
            <ModelCard canEdit={canEdit} />
          </div>
        </>
      )}
    </div>
  );
}

// ---------- 1 et 2 : seuil d'alerte et règles des alertes ----------

type Form = Record<keyof SettingsInput, string>;
type Errors = Partial<Record<keyof SettingsInput, TranslationKey>>;

const PRESETS = [1, 10, 50, 100, 1000];

function ThresholdForm({ settings, canEdit, onSaved }:
  { settings: OrgSettings; canEdit: boolean; onSaved: (s: OrgSettings) => void }) {
  const { t, formatPercent, formatNumber } = useI18n();
  const [form, setForm] = useState<Form>({
    cost_ratio: String(settings.cost_ratio),
    alert_open_k: String(settings.alert_open_k),
    alert_close_k: String(settings.alert_close_k),
    alert_close_factor: String(settings.alert_close_factor),
  });
  const [errors, setErrors] = useState<Errors>({});
  const [apiError, setApiError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<OrgSettings | null>(null);

  const ratio = parseNumber(form.cost_ratio);
  const ratioValid = ratio > 0 && ratio <= 10_000;
  const preview = useThresholdPreview(ratioValid && ratio !== settings.cost_ratio ? ratio : null);

  const set = (name: keyof Form) => (e: { target: { value: string } }) => {
    setForm((prev) => ({ ...prev, [name]: e.target.value }));
    setSaved(null);
  };

  // Mêmes règles que l'API (SettingsIn dans app/api/v1/organization.py).
  function validate(): Errors {
    const found: Errors = {};
    if (!ratioValid) found.cost_ratio = "valid.costRatio";
    for (const k of ["alert_open_k", "alert_close_k"] as const) {
      const n = parseNumber(form[k]);
      if (!isInt(n) || n < 1 || n > 50) found[k] = "valid.k";
    }
    const f = parseNumber(form.alert_close_factor);
    if (!(f > 0 && f < 1)) found.alert_close_factor = "valid.factor";
    return found;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found = validate();
    setErrors(found);
    setApiError(null);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      const result = await orgApi.updateSettings({
        cost_ratio: ratio,
        alert_open_k: parseNumber(form.alert_open_k),
        alert_close_k: parseNumber(form.alert_close_k),
        alert_close_factor: parseNumber(form.alert_close_factor),
      });
      setSaved(result);
      onSaved(result);
    } catch (err) {
      setApiError(err);
    } finally {
      setSaving(false);
    }
  }

  const factor = parseNumber(form.alert_close_factor);
  const highThreshold = preview.data?.threshold ?? settings.threshold_high;
  const low = factor > 0 && factor < 1 ? formatPercent(highThreshold * factor) : "—";
  const err = (k: keyof Form) => errors[k] && t(errors[k]!);

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <Card className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">{t("settings.costTitle")}</h2>
          <p className="text-sm text-ink-muted">{t("settings.costIntro")}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="cost-ratio" label={t("settings.costRatio")} hint={t("settings.costRatioHint")} inputMode="decimal"
            value={form.cost_ratio} onChange={set("cost_ratio")} error={err("cost_ratio")} disabled={!canEdit} />
          {canEdit && (
            <div className="space-y-1">
              <p className="text-sm font-medium text-ink-soft">{t("settings.presets")}</p>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <button key={p} type="button"
                    onClick={() => set("cost_ratio")({ target: { value: String(p) } })}
                    aria-pressed={ratio === p}
                    className={`rounded-full border px-3 py-1 text-sm ${ratio === p
                      ? "border-accent bg-accent text-on-accent" : "border-line-strong text-ink-soft hover:bg-surface-2"}`}>
                    {formatNumber(p, 0)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <CompareTable settings={settings} ratio={ratioValid ? ratio : null} preview={preview} />
      </Card>

      <Card className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">{t("settings.rulesTitle")}</h2>
          <p className="text-sm text-ink-muted">{t("settings.rulesIntro")}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <Field id="open-k" label={t("settings.openK")} hint={t("settings.kHint")} inputMode="numeric"
            value={form.alert_open_k} onChange={set("alert_open_k")} error={err("alert_open_k")} disabled={!canEdit} />
          <Field id="close-k" label={t("settings.closeK")} hint={t("settings.kHint")} inputMode="numeric"
            value={form.alert_close_k} onChange={set("alert_close_k")} error={err("alert_close_k")} disabled={!canEdit} />
          <Field id="close-factor" label={t("settings.closeFactor")} hint={t("settings.closeFactorHint", { low })}
            inputMode="decimal" value={form.alert_close_factor} onChange={set("alert_close_factor")}
            error={err("alert_close_factor")} disabled={!canEdit} />
        </div>
      </Card>

      {canEdit && (
        <div className="space-y-3">
          {apiError != null && <ErrorBox error={apiError} />}
          {saved && <Notice tone="success">{t("settings.saved", { threshold: formatPercent(saved.threshold_high) })}</Notice>}
          <Button type="submit" disabled={saving}>{saving ? t("settings.saving") : t("settings.save")}</Button>
        </div>
      )}
    </form>
  );
}

/** Aperçu du seuil pour un ratio, demandé à l'API 400 ms après la dernière frappe. */
function useThresholdPreview(ratio: number | null) {
  const [data, setData] = useState<ThresholdPreview | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setData(null);
    setError(null);
    if (ratio == null) { setLoading(false); return; }
    setLoading(true);
    let cancelled = false;   // une réponse arrivée trop tard (ratio déjà changé) est ignorée
    const timer = window.setTimeout(() => {
      orgApi.preview(ratio)
        .then((d) => { if (!cancelled) setData(d); })
        .catch((e: unknown) => { if (!cancelled) setError(e); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 400);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [ratio]);

  return { data, error, loading };
}

function CompareTable({ settings, ratio, preview }:
  { settings: OrgSettings; ratio: number | null; preview: ReturnType<typeof useThresholdPreview> }) {
  const { t, formatPercent, formatNumber } = useI18n();
  const cur = settings.expected;
  const next = preview.data;
  const showNew = ratio != null && ratio !== settings.cost_ratio;
  const rows: [TranslationKey, string, string | null][] = [
    ["settings.threshold", formatPercent(settings.threshold_high), next && formatPercent(next.threshold)],
    ["settings.recall", formatPercent(cur.recall), next && formatPercent(next.recall)],
    ["settings.missed", formatNumber(cur.missed_failures, 0), next && formatNumber(next.missed_failures, 0)],
    ["settings.falseAlarms", formatNumber(cur.false_alarms, 0), next && formatNumber(next.false_alarms, 0)],
    ["settings.precision", formatPercent(cur.precision), next && formatPercent(next.precision)],
  ];

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{t("settings.compareTitle", { n: formatNumber(cur.evaluated_on, 0) })}</h3>
      <div className={table.wrap}>
        <table className={table.table}>
          <thead className={table.head}>
            <tr>
              <th className={table.th}>{t("settings.colIndicator")}</th>
              <th className={`${table.th} text-right`}>{t("settings.colCurrent", { ratio: formatNumber(settings.cost_ratio, 2) })}</th>
              {showNew && <th className={`${table.th} text-right`}>{t("settings.colNew", { ratio: formatNumber(ratio, 2) })}</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, current, next]) => (
              <tr key={label} className={table.row}>
                <td className={table.td}>{t(label)}</td>
                <td className={`${table.td} text-right`}>{current}</td>
                {showNew && <td className={`${table.td} text-right font-semibold`}>{next ?? "…"}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showNew && preview.loading && <Spinner label={t("settings.previewLoading")} />}
      {showNew && preview.error != null && <ErrorBox error={preview.error} />}
      {showNew && next && <p className="text-xs text-ink-muted">{t("settings.previewHelp")}</p>}
    </div>
  );
}

// ---------- 3 : plan et consommation ----------

function PlanCard({ org, onChanged }: { org: Organization; onChanged: (o: Organization) => void }) {
  const { t } = useI18n();
  const { me, refreshMe } = useAuth();
  const isOwner = me?.role === "owner";
  const [done, setDone] = useState<string | null>(null);
  const target = org.plan === "FREE" ? "PRO" : "FREE";

  async function change() {
    const usage = await orgApi.changePlan(target);
    onChanged({ ...org, ...usage });
    setDone(t("plan.changed", { plan: t(`plan.${usage.plan}`) }));
    await refreshMe();   // l'en-tête et les autres écrans voient le nouveau plan
  }

  const features: [TranslationKey, boolean][] = [
    ["plan.customModel", org.limits.custom_model],
    ["plan.export", org.limits.export],
  ];

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">{t("plan.title")}</h2>
        <Badge tone={org.plan === "PRO" ? "info" : "neutral"}>{t(`plan.${org.plan}`)}</Badge>
      </div>
      {done && <Notice tone="success">{done}</Notice>}
      <div className="grid gap-4 md:grid-cols-2">
        <UsageLine label={t("plan.machines")} value={org.machines} max={org.limits.max_machines} />
        <UsageLine label={t("plan.measures")} value={org.measures_today} max={org.limits.max_measures_per_day}
          hint={t("plan.resetDaily")} />
      </div>
      <ul className="space-y-1 text-sm">
        {features.map(([label, included]) => (
          <li key={label} className="flex items-center gap-2">
            <span aria-hidden="true" className={included ? "text-success-ink" : "text-ink-faint"}>{included ? "✓" : "✗"}</span>
            <span className={included ? "" : "text-ink-muted"}>
              {t("plan.featureLine", { feature: t(label), state: t(included ? "plan.included" : "plan.notIncluded") })}
            </span>
          </li>
        ))}
      </ul>
      {isOwner ? (
        <ConfirmAction
          key={org.plan}
          label={t(target === "PRO" ? "plan.toPro" : "plan.toFree")}
          help={t(target === "PRO" ? "plan.toProHelp" : "plan.toFreeHelp")}
          confirmLabel={t(target === "PRO" ? "plan.toProConfirm" : "plan.toFreeConfirm")}
          onConfirm={change}
        />
      ) : <p className="text-sm text-ink-muted">{t("plan.ownerOnly")}</p>}
    </Card>
  );
}

function UsageLine({ label, value, max, hint }: { label: string; value: number; max: number; hint?: string }) {
  const { t, formatNumber } = useI18n();
  return (
    <div className="space-y-1">
      <div className="flex justify-between gap-2 text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-ink-soft">{t("plan.of", { value: formatNumber(value, 0), max: formatNumber(max, 0) })}</span>
      </div>
      <Meter value={value} max={max} label={label} />
      {hint && <p className="text-xs text-ink-muted">{hint}</p>}
    </div>
  );
}

// ---------- 4 : export CSV ----------

function ExportCard({ org, canEdit }: { org: Organization; canEdit: boolean }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState<"measures" | "alerts" | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function run(kind: "measures" | "alerts") {
    setBusy(kind);
    setError(null);
    try {
      await exportApi[kind]();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  const blocked = !org.limits.export ? t("export.proOnly") : !canEdit ? t("export.roleOnly") : null;

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-semibold">{t("export.title")}</h2>
      <p className="text-sm text-ink-muted">{t("export.intro")}</p>
      {blocked ? <Notice>{blocked}</Notice> : (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy != null} onClick={() => void run("measures")}>
            {busy === "measures" ? t("export.downloading") : t("export.measures")}
          </Button>
          <Button variant="secondary" disabled={busy != null} onClick={() => void run("alerts")}>
            {busy === "alerts" ? t("export.downloading") : t("export.alerts")}
          </Button>
        </div>
      )}
      {error != null && <ErrorBox error={error} />}
    </Card>
  );
}

// ---------- 5 : modèle d'IA ----------

const JOB_TONE = { training: "info", active: "success", rejected: "warning", failed: "danger", retired: "neutral" } as const;

function ModelCard({ canEdit }: { canEdit: boolean }) {
  const { t, formatDate, serverText } = useI18n();
  const [data, setData] = useState<ModelsOverview | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    try {
      setData(await modelsApi.overview());
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, []);

  // Un entraînement tourne en arrière-plan : on relit l'historique régulièrement.
  usePolling(load, 10_000);

  const training = data?.history.some((j) => j.status === "training") ?? false;

  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-semibold">{t("model.title")}</h2>
      {error != null && <ErrorBox error={error} onRetry={() => void load()} />}
      {data == null ? (error == null && <Spinner />) : (
        <>
          <p className="text-sm">{t("model.current", { name: data.current_model })}</p>
          {!data.custom_model_allowed ? <Notice>{t("model.commonModel")}</Notice> : (
            <>
              <p className="text-sm text-ink-muted">{t("model.retrainIntro")}</p>
              {canEdit && (
                <ConfirmAction label={t("model.retrain")} help={t("model.retrainHelp")}
                  confirmLabel={t("model.retrainConfirm")} disabled={training}
                  onConfirm={async () => { await modelsApi.retrain(); await load(); }} />
              )}
              <h3 className="pt-2 text-sm font-semibold">{t("model.historyTitle")}</h3>
              {data.history.length === 0 ? <p className="text-sm text-ink-muted">{t("model.noHistory")}</p> : (
                <ul className="space-y-2">
                  {data.history.slice(0, 5).map((job) => (
                    <li key={job.id} className="rounded-md border border-line p-2 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">v{job.version}</span>
                        <Badge tone={JOB_TONE[job.status]}>{t(`model.status.${job.status}`)}</Badge>
                      </div>
                      <p className="text-xs text-ink-muted">{formatDate(parseApiDate(job.created_at))}</p>
                      {job.message && <p className="mt-1 text-xs text-ink-soft">{serverText(job.message)}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </>
      )}
    </Card>
  );
}
