// Petits composants réutilisés par tous les écrans (boutons, champs, cartes, messages).
// Les couleurs viennent du thème (index.css) : bg-surface, text-ink-muted… et non slate-200,
// ce qui fait marcher le mode sombre partout sans rien ajouter dans les écrans.
import type {
  ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes,
} from "react";
import { useI18n } from "../i18n";

type Variant = "primary" | "secondary" | "danger";

const BUTTON_STYLES: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:bg-accent-hover disabled:bg-accent-muted",
  secondary: "border border-line-strong bg-surface text-ink-soft hover:bg-surface-2 disabled:text-ink-faint",
  danger: "border border-danger-line bg-surface text-danger-ink hover:bg-danger-soft disabled:text-ink-faint",
};

export function Button({ variant = "primary", className = "", type = "button", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed ${BUTTON_STYLES[variant]} ${className}`}
      {...props}
    />
  );
}

/** Classes communes aux champs (input, select, textarea). */
export function inputClass(error?: boolean): string {
  return `block w-full rounded-md border bg-surface px-3 py-2 text-sm text-ink shadow-sm placeholder:text-ink-faint focus:outline-none focus:ring-2 disabled:bg-surface-2 disabled:text-ink-muted ${
    error ? "border-danger focus:ring-danger-line" : "border-line-strong focus:ring-ring"}`;
}

/** Étiquette + aide (ou erreur) sous un champ, reliées pour les lecteurs d'écran. */
function FieldShell({ id, label, hint, error, children }:
  { id: string; label: string; hint?: string; error?: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-ink-soft">{label}</label>
      {children}
      {error
        ? <p id={`${id}-error`} className="text-xs text-danger-ink">{error}</p>
        : hint && <p id={`${id}-hint`} className="text-xs text-ink-muted">{hint}</p>}
    </div>
  );
}

const describedBy = (id: string, error?: string, hint?: string) =>
  error ? `${id}-error` : hint ? `${id}-hint` : undefined;

export function Field({ label, hint, error, id, ...props }:
  InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string; id: string }) {
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <input id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, error, hint)}
        className={inputClass(!!error)} {...props} />
    </FieldShell>
  );
}

export function SelectField({ label, hint, error, id, children, ...props }:
  SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: string; error?: string; id: string }) {
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <select id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, error, hint)}
        className={inputClass(!!error)} {...props}>{children}</select>
    </FieldShell>
  );
}

export function TextAreaField({ label, hint, error, id, ...props }:
  TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; hint?: string; error?: string; id: string }) {
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <textarea id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, error, hint)}
        className={inputClass(!!error)} {...props} />
    </FieldShell>
  );
}

/** Encadré rouge qui explique une erreur, avec le message du serveur s'il y en a un. */
export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t, errorText } = useI18n();
  const { title, detail } = errorText(error);
  return (
    <div role="alert" className="rounded-md border border-danger-line bg-danger-soft p-3 text-sm text-danger-ink">
      <p className="font-medium">{title}</p>
      {detail && <p className="mt-1">{t("common.serverSays")} {detail}</p>}
      {onRetry && <Button variant="secondary" className="mt-2" onClick={onRetry}>{t("common.retry")}</Button>}
    </div>
  );
}

type Tone = "info" | "warning" | "success" | "danger";

const NOTICE_STYLES: Record<Tone, string> = {
  info: "border-info-line bg-info-soft text-info-ink",
  warning: "border-warning-line bg-warning-soft text-warning-ink",
  success: "border-success-line bg-success-soft text-success-ink",
  danger: "border-danger-line bg-danger-soft text-danger-ink",
};

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: Tone }) {
  return <div role="status" className={`rounded-md border p-3 text-sm ${NOTICE_STYLES[tone]}`}>{children}</div>;
}

const BADGE_STYLES: Record<Tone | "neutral", string> = {
  neutral: "bg-surface-2 text-ink-soft",
  info: "bg-info-soft text-info-ink",
  warning: "bg-warning-soft text-warning-ink",
  success: "bg-success-soft text-success-ink",
  danger: "bg-danger-soft text-danger-ink",
};

/** Petite pastille (« Active », « Ouverte », « Pro »…). */
export function Badge({ tone = "neutral", children }: { tone?: Tone | "neutral"; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${BADGE_STYLES[tone]}`}>{children}</span>;
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div role="status" className="flex items-center gap-2 text-sm text-ink-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
      {label ?? t("common.loading")}
    </div>
  );
}

/** Carte blanche (gris foncé en mode sombre) qui regroupe un bloc de l'écran. */
export function Card({ children, className = "", as: Tag = "section" }:
  { children: ReactNode; className?: string; as?: "section" | "div" | "article" | "form" }) {
  return <Tag className={`rounded-lg border border-line bg-surface p-4 shadow-sm ${className}`}>{children}</Tag>;
}

/** Écran (ou liste) vide : on explique pourquoi et quoi faire. */
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border-2 border-dashed border-line-strong p-6 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 text-sm text-ink-muted">{children}</div>}
    </div>
  );
}

/** Titre d'écran, phrase d'explication et boutons éventuels à droite. */
export function PageHeader({ title, intro, actions, children }:
  { title: string; intro?: string; actions?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-bold">{title}</h1>
        {intro && <p className="text-ink-muted">{intro}</p>}
        {children}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

/** Barre de progression simple (consommation du plan…). */
export function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  const ratio = max > 0 ? Math.min(1, value / max) : 0;
  const color = ratio >= 1 ? "bg-danger" : ratio >= 0.8 ? "bg-warning" : "bg-accent";
  return (
    <div role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}
      className="h-2 w-full rounded bg-track">
      <div className={`h-2 rounded ${color}`} style={{ width: `${Math.max(ratio * 100, value > 0 ? 2 : 0)}%` }} />
    </div>
  );
}

/** Classes partagées par les tableaux. */
export const table = {
  wrap: "overflow-x-auto rounded-lg border border-line bg-surface shadow-sm",
  table: "w-full text-left text-sm",
  head: "border-b border-line text-ink-muted",
  th: "px-4 py-2 font-medium",
  row: "border-b border-line last:border-0",
  td: "px-4 py-2",
};
