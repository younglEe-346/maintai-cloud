// Tests de usePolling (src/hooks.ts) : pas d'appel onglet caché, pas deux chargements en même temps,
// rechargement au retour sur l'onglet.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePolling } from "../hooks";

const MS = 1000;
let hidden = false;

function setHidden(value: boolean) {
  hidden = value;
  document.dispatchEvent(new Event("visibilitychange"));
}

/** Avance l'horloge simulée et laisse les promesses se terminer. */
async function advance(ms: number) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    hidden = false;
    Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  });
  afterEach(() => {
    hidden = false;
  });

  it("charge tout de suite, puis toutes les ms millisecondes", async () => {
    const load = vi.fn(async () => {});
    renderHook(() => usePolling(load, MS));
    await advance(0);
    expect(load).toHaveBeenCalledTimes(1);
    await advance(MS);
    expect(load).toHaveBeenCalledTimes(2);
    await advance(MS);
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("n'appelle pas l'API quand l'onglet est caché", async () => {
    const load = vi.fn(async () => {});
    renderHook(() => usePolling(load, MS));
    await advance(0);
    expect(load).toHaveBeenCalledTimes(1);
    hidden = true;
    await advance(5 * MS);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("recharge tout de suite quand l'utilisateur revient sur l'onglet", async () => {
    const load = vi.fn(async () => {});
    renderHook(() => usePolling(load, 60 * MS));
    await advance(0);
    expect(load).toHaveBeenCalledTimes(1);
    hidden = true;
    await advance(10 * MS);
    await act(async () => { setHidden(false); });
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("ne lance jamais deux chargements en même temps (API lente : on saute un tour)", async () => {
    let finish: () => void = () => {};
    const load = vi.fn(() => new Promise<void>((resolve) => { finish = resolve; }));
    renderHook(() => usePolling(load, MS));
    await advance(0);
    expect(load).toHaveBeenCalledTimes(1);
    await advance(3 * MS);              // plusieurs tours passent pendant que le premier chargement dure
    expect(load).toHaveBeenCalledTimes(1);
    await act(async () => { finish(); });
    await advance(MS);                  // le chargement est fini : le tour suivant peut partir
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("s'arrête quand l'écran disparaît", async () => {
    const load = vi.fn(async () => {});
    const { unmount } = renderHook(() => usePolling(load, MS));
    await advance(0);
    unmount();
    await advance(5 * MS);
    expect(load).toHaveBeenCalledTimes(1);
  });
});
