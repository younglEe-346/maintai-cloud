// Fenêtre qui montre la clé d'API complète, UNE seule fois (l'API ne la renverra jamais).
// On ne peut la fermer qu'après avoir coché « j'ai copié la clé » : impossible de la perdre par un clic distrait.
import { useEffect, useRef, useState } from "react";
import type { MachineWithKey } from "../api";
import { useI18n } from "../i18n";
import { Button } from "./ui";

export default function NewKeyDialog({ machine, onClose, title }:
  { machine: MachineWithKey; onClose: () => void; title?: string }) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const keyRef = useRef<HTMLInputElement>(null);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    dialogRef.current?.showModal();   // fenêtre modale native du navigateur
    keyRef.current?.select();
  }, []);

  async function copyKey() {
    try {
      await navigator.clipboard.writeText(machine.api_key);
      setCopy("copied");
    } catch {
      // Presse-papiers moderne refusé (page non sécurisée, navigateur intégré…) :
      // ancienne méthode, on sélectionne le texte et on demande au navigateur de le copier.
      keyRef.current?.select();
      setCopy(document.execCommand("copy") ? "copied" : "failed");
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="new-key-title"
      // La touche Échap ne ferme pas la fenêtre tant que la copie n'est pas confirmée.
      onCancel={(e) => { if (!confirmed) e.preventDefault(); }}
      // Fermeture (bouton ou Échap après confirmation) : on prévient la page.
      onClose={onClose}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-lg border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-slate-950/60"
    >
      <div className="space-y-4 p-6">
        <h2 id="new-key-title" className="text-lg font-semibold">{title ?? t("newKey.title", { name: machine.name })}</h2>

        <div className="rounded-md border border-warning-line bg-warning-soft p-3 text-sm text-warning-ink" role="alert">
          {t("newKey.warning")}
        </div>

        <div className="space-y-1">
          <label htmlFor="new-key" className="block text-sm font-medium text-ink-soft">{t("newKey.label")}</label>
          <div className="flex gap-2">
            <input
              id="new-key"
              ref={keyRef}
              readOnly
              value={machine.api_key}
              onFocus={(e) => e.target.select()}
              className="min-w-0 flex-1 rounded-md border border-line-strong bg-surface-2 px-3 py-2 font-mono text-sm text-ink"
            />
            <Button variant="secondary" onClick={copyKey}>
              {copy === "copied" ? t("newKey.copied") : t("newKey.copy")}
            </Button>
          </div>
          {copy === "failed" && <p className="text-xs text-danger-ink">{t("newKey.copyFailed")}</p>}
          <p className="text-xs text-ink-muted">{t("newKey.howTo")}</p>
        </div>

        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
          {t("newKey.confirm")}
        </label>

        <div className="flex justify-end">
          <Button disabled={!confirmed} onClick={() => dialogRef.current?.close()}>
            {t("newKey.close")}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
