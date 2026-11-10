// Fenêtre qui montre la clé d'API complète, UNE seule fois (l'API ne la renverra jamais).
// On ne peut la fermer qu'après avoir coché « j'ai copié la clé » : impossible de la perdre par un clic distrait.
import { useEffect, useRef, useState } from "react";
import type { MachineWithKey } from "../api";
import { useI18n } from "../i18n";
import { Button } from "./ui";

export default function NewKeyDialog({ machine, onClose }: { machine: MachineWithKey; onClose: () => void }) {
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
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-lg p-0 shadow-xl backdrop:bg-slate-900/50"
    >
      <div className="space-y-4 p-6">
        <h2 id="new-key-title" className="text-lg font-semibold">{t("newKey.title", { name: machine.name })}</h2>

        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" role="alert">
          {t("newKey.warning")}
        </div>

        <div className="space-y-1">
          <label htmlFor="new-key" className="block text-sm font-medium text-slate-700">{t("newKey.label")}</label>
          <div className="flex gap-2">
            <input
              id="new-key"
              ref={keyRef}
              readOnly
              value={machine.api_key}
              onFocus={(e) => e.target.select()}
              className="min-w-0 flex-1 rounded-md border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-sm"
            />
            <Button variant="secondary" onClick={copyKey}>
              {copy === "copied" ? t("newKey.copied") : t("newKey.copy")}
            </Button>
          </div>
          {copy === "failed" && <p className="text-xs text-red-600">{t("newKey.copyFailed")}</p>}
          <p className="text-xs text-slate-500">{t("newKey.howTo")}</p>
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
