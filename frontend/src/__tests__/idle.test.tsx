// Tests de la déconnexion automatique après inactivité (useIdleTimeout dans src/hooks.ts, branché dans src/auth.tsx).
import { act, render, renderHook, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { authApi, tokenStore, type Me } from "../api";
import { AuthProvider, IDLE_LOGOUT_MS, useAuth } from "../auth";
import { useIdleTimeout } from "../hooks";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    authApi: { me: vi.fn(), login: vi.fn(), register: vi.fn() },
    setUnauthorizedHandler: vi.fn(),
  };
});

const MIN = 60 * 1000;

/** Avance l'horloge simulée et laisse les promesses se terminer. */
async function advance(ms: number) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}
const activity = (name: string) => act(() => { window.dispatchEvent(new Event(name)); });

describe("useIdleTimeout", () => {
  beforeEach(() => { vi.useFakeTimers(); });

  it("n'appelle rien avant le délai, puis une seule fois", async () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleTimeout(onIdle, 10 * MIN, true));
    await advance(10 * MIN - 2000);
    expect(onIdle).not.toHaveBeenCalled();
    await advance(5000);
    expect(onIdle).toHaveBeenCalledTimes(1);
    await advance(60 * MIN);
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("une activité (souris, clavier, molette, toucher) remet le compteur à zéro", async () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleTimeout(onIdle, 10 * MIN, true));
    for (const name of ["pointermove", "keydown", "wheel", "touchstart", "pointerdown"]) {
      await advance(9 * MIN);
      await activity(name);
    }
    expect(onIdle).not.toHaveBeenCalled();
    await advance(11 * MIN);
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("ne fait rien quand personne n'est connecté (enabled = false)", async () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleTimeout(onIdle, 10 * MIN, false));
    await advance(3 * 60 * MIN);
    expect(onIdle).not.toHaveBeenCalled();
  });
});

describe("déconnexion automatique de la session", () => {
  const me = vi.mocked(authApi.me);

  function Probe() {
    const { status, expired } = useAuth();
    return <div><p data-testid="status">{status}</p><p data-testid="expired">{String(expired)}</p></div>;
  }
  const status = () => screen.getByTestId("status").textContent;

  async function signIn() {
    vi.useFakeTimers();
    tokenStore.set("jeton-valide");
    me.mockReset();
    me.mockResolvedValue({ id: "u1" } as unknown as Me);
    render(<AuthProvider><Probe /></AuthProvider>);
    await advance(0);
    expect(status()).toBe("signedIn");
  }

  beforeEach(() => { vi.clearAllMocks(); });

  it("le délai est de 60 minutes", () => {
    expect(IDLE_LOGOUT_MS).toBe(60 * MIN);
  });

  it("utilisateur inactif : déconnecté après le délai, avec le bandeau « session expirée »", async () => {
    await signIn();
    await advance(IDLE_LOGOUT_MS - 5000);
    expect(status()).toBe("signedIn");
    await advance(10_000);
    expect(status()).toBe("signedOut");
    expect(screen.getByTestId("expired").textContent).toBe("true");
    expect(tokenStore.get()).toBeNull();
  });

  it("utilisateur actif : jamais déconnecté (3 heures avec une action toutes les 30 minutes)", async () => {
    await signIn();
    for (let i = 0; i < 6; i++) {
      await advance(30 * MIN);
      await activity("keydown");
    }
    expect(status()).toBe("signedIn");
    expect(tokenStore.get()).toBe("jeton-valide");
  });
});
