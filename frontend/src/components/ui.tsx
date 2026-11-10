// Petits composants réutilisés par tous les écrans (boutons, champs, messages).
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { useI18n } from "../i18n";

export function Button({ variant = "primary", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  const styles = variant === "primary"
    ? "bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300"
    : "bg-white text-slate-700 border border-slate-300 hover:bg-slate-100 disabled:text-slate-400";
  return (
    <button
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    />
  );
}

export function Field({ label, hint, error, id, ...props }:
  InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string; id: string }) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">{label}</label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 ${
          error ? "border-red-400 focus:ring-red-300" : "border-slate-300 focus:ring-blue-300"}`}
        {...props}
      />
      {error
        ? <p id={`${id}-error`} className="text-xs text-red-600">{error}</p>
        : hint && <p id={`${id}-hint`} className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

/** Encadré rouge qui explique une erreur, avec le message du serveur s'il y en a un. */
export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t, errorText } = useI18n();
  const { title, detail } = errorText(error);
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <p className="font-medium">{title}</p>
      {detail && <p className="mt-1">{t("common.serverSays")} {detail}</p>}
      {onRetry && <Button variant="secondary" className="mt-2" onClick={onRetry}>{t("common.retry")}</Button>}
    </div>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" }) {
  const styles = tone === "info" ? "border-blue-200 bg-blue-50 text-blue-900" : "border-amber-200 bg-amber-50 text-amber-900";
  return <div role="status" className={`rounded-md border p-3 text-sm ${styles}`}>{children}</div>;
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div role="status" className="flex items-center gap-2 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
      {label ?? t("common.loading")}
    </div>
  );
}
