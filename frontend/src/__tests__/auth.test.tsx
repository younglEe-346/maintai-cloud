// Tests de la session (src/auth.tsx) : API éteinte = l'utilisateur reste connecté (« injoignable »),
// réponse 401 = déconnexion, jeton invalide = déconnexion.
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, authApi, setUnauthorizedHandler, tokenStore, type Me } from "../api";
import { AuthProvider, useAuth } from "../auth";

// On garde la vraie ApiError et le vrai tokenStore ; on remplace seulement les appels réseau.
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    authApi: { me: vi.fn(), login: vi.fn(), register: vi.fn() },
    setUnauthorizedHandler: vi.fn(),
  };
});

const me = vi.mocked(authApi.me);
const PROFILE = { id: "u1", email: "ada@usine.test" } as unknown as Me;

function Probe() {
  const { status, expired, retry } = useAuth();
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="expired">{String(expired)}</p>
      <button onClick={retry}>réessayer</button>
    </div>
  );
}

const status = () => screen.getByTestId("status").textContent;

/** Monte la session et laisse la vérification du jeton se terminer. */
async function mountSession() {
  render(<AuthProvider><Probe /></AuthProvider>);
  await act(async () => {});
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    me.mockReset();
  });

  it("sans jeton : déconnecté, sans appeler l'API", async () => {
    await mountSession();
    expect(status()).toBe("signedOut");
    expect(me).not.toHaveBeenCalled();
  });

  it("jeton valide : connecté", async () => {
    tokenStore.set("jeton-valide");
    me.mockResolvedValue(PROFILE);
    await mountSession();
    expect(status()).toBe("signedIn");
  });

  it("API éteinte : reste connecté (injoignable) et garde le jeton", async () => {
    tokenStore.set("jeton-valide");
    me.mockRejectedValue(new ApiError(0, "réseau coupé"));
    await mountSession();
    expect(status()).toBe("unreachable");
    expect(tokenStore.get()).toBe("jeton-valide");
  });

  it("API en panne (500) : injoignable aussi, jeton gardé", async () => {
    tokenStore.set("jeton-valide");
    me.mockRejectedValue(new ApiError(500, "panne"));
    await mountSession();
    expect(status()).toBe("unreachable");
    expect(tokenStore.get()).toBe("jeton-valide");
  });

  it("jeton invalide (401 au chargement) : déconnexion et jeton effacé", async () => {
    tokenStore.set("jeton-perime");
    me.mockRejectedValue(new ApiError(401, "jeton invalide"));
    await mountSession();
    expect(status()).toBe("signedOut");
    expect(tokenStore.get()).toBeNull();
  });

  it("réponse 401 plus tard : déconnexion, jeton effacé, bandeau « session expirée »", async () => {
    tokenStore.set("jeton-valide");
    me.mockResolvedValue(PROFILE);
    await mountSession();
    expect(status()).toBe("signedIn");
    const onUnauthorized = vi.mocked(setUnauthorizedHandler).mock.calls.at(-1)?.[0];
    expect(onUnauthorized).toBeTypeOf("function");
    act(() => { onUnauthorized!(); });
    expect(status()).toBe("signedOut");
    expect(screen.getByTestId("expired").textContent).toBe("true");
    expect(tokenStore.get()).toBeNull();
  });

  it("« réessayer » après une API injoignable : connecté quand l'API revient", async () => {
    tokenStore.set("jeton-valide");
    me.mockRejectedValueOnce(new ApiError(0, "réseau coupé"));
    await mountSession();
    expect(status()).toBe("unreachable");
    me.mockResolvedValue(PROFILE);
    await act(async () => { screen.getByRole("button", { name: "réessayer" }).click(); });
    expect(status()).toBe("signedIn");
  });
});
