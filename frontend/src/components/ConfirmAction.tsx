// Action importante en deux temps : un premier clic explique ce qui va se passer,
// un second clic confirme. Évite les « oups » sans fenêtre surgissante du navigateur.
import { useState } from "react";
import { useI18n } from "../i18n";
import { Button, ErrorBox } from "./ui";

interface Props {
  label: string;            // texte du bouton (« Archiver la machine »)
  help: string;             // ce que fait l'action, montré avant de confirmer
  confirmLabel: string;     // texte du bouton de confirmation (« Oui, archiver »)
  onConfirm: () => Promise<void>;
  danger?: boolean;
  disabled?: boolean;
}

export default function ConfirmAction({ label, help, confirmLabel, onConfirm, danger, disabled }: Props) {
  const { t } = useI18n();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      setAsking(false);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (!asking) {
    return (
      <div className="space-y-1">
        <Button variant={danger ? "danger" : "secondary"} disabled={disabled} onClick={() => setAsking(true)}>{label}</Button>
      </div>
    );
  }

  return (
    <div className={`space-y-2 rounded-md border p-3 text-sm ${danger ? "border-danger-line bg-danger-soft" : "border-line bg-surface-2"}`}>
      <p className="font-medium">{t("common.areYouSure")}</p>
      <p className="text-ink-soft">{help}</p>
      {error != null && <ErrorBox error={error} />}
      <div className="flex flex-wrap gap-2">
        <Button variant={danger ? "danger" : "primary"} disabled={busy} onClick={() => void confirm()}>
          {busy ? t("common.working") : confirmLabel}
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => { setAsking(false); setError(null); }}>
          {t("common.cancel")}
        </Button>
      </div>
    </div>
  );
}
