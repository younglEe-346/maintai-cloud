// Tests de ConfirmAction (src/components/ConfirmAction.tsx) : un premier clic explique, un second confirme.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import ConfirmAction from "../components/ConfirmAction";
import { I18nProvider } from "../i18n";

function setup(onConfirm: () => Promise<void>, disabled = false) {
  render(
    <I18nProvider>
      <ConfirmAction label="Archiver" help="Cette machine sera archivée." confirmLabel="Oui, archiver"
        onConfirm={onConfirm} disabled={disabled} />
    </I18nProvider>,
  );
  return userEvent.setup();
}

describe("ConfirmAction", () => {
  it("au départ : seulement le bouton, rien n'est expliqué ni lancé", () => {
    const onConfirm = vi.fn(async () => {});
    setup(onConfirm);
    expect(screen.getByRole("button", { name: "Archiver" })).toBeTruthy();
    expect(screen.queryByText("Cette machine sera archivée.")).toBeNull();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("premier clic : explique ce qui va se passer, sans rien lancer", async () => {
    const onConfirm = vi.fn(async () => {});
    const user = setup(onConfirm);
    await user.click(screen.getByRole("button", { name: "Archiver" }));
    expect(screen.getByText("Cette machine sera archivée.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Oui, archiver" })).toBeTruthy();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("second clic : lance l'action une seule fois et revient à l'état de départ", async () => {
    const onConfirm = vi.fn(async () => {});
    const user = setup(onConfirm);
    await user.click(screen.getByRole("button", { name: "Archiver" }));
    await user.click(screen.getByRole("button", { name: "Oui, archiver" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Cette machine sera archivée.")).toBeNull();
    expect(screen.getByRole("button", { name: "Archiver" })).toBeTruthy();
  });

  it("erreur de l'API : le message d'erreur s'affiche et la confirmation reste ouverte", async () => {
    const onConfirm = vi.fn(async () => { throw new ApiError(409, "Déjà archivée"); });
    const user = setup(onConfirm);
    await user.click(screen.getByRole("button", { name: "Archiver" }));
    await user.click(screen.getByRole("button", { name: "Oui, archiver" }));
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Cette machine sera archivée.")).toBeTruthy();
  });

  it("Annuler : remet à zéro sans lancer l'action", async () => {
    const onConfirm = vi.fn(async () => {});
    const user = setup(onConfirm);
    await user.click(screen.getByRole("button", { name: "Archiver" }));
    // le bouton « Annuler » est le dernier de la zone de confirmation (son texte dépend de la langue)
    const buttons = screen.getAllByRole("button");
    await user.click(buttons[buttons.length - 1]);
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByText("Cette machine sera archivée.")).toBeNull();
    expect(screen.getByRole("button", { name: "Archiver" })).toBeTruthy();
  });

  it("bouton désactivé : n'ouvre pas la confirmation", async () => {
    const user = setup(vi.fn(async () => {}), true);
    await user.click(screen.getByRole("button", { name: "Archiver" }));
    expect(screen.queryByText("Cette machine sera archivée.")).toBeNull();
  });
});
