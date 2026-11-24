
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AcceptInvitationPage, {
  readInvitationToken,
  clearInvitationFromUrl,
} from "../pages/AcceptInvitationPage";

const mocks = vi.hoisted(() => ({
  status: "signedOut" as "signedIn" | "signedOut",
  me: null as { email: string } | null,
  logout: vi.fn(),
  startSession: vi.fn(),
  invitationInfo: vi.fn(),
  acceptInvitation: vi.fn(),
}));

vi.mock("../auth", () => ({
  useAuth: () => ({
    status: mocks.status,
    me: mocks.me,
    logout: mocks.logout,
    startSession: mocks.startSession,
  }),
}));

vi.mock("../i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params ? `${key} ${Object.values(params).join(" ")}` : key,
    formatDate: (value: Date) => value.toISOString().slice(0, 10),
  }),
}));

vi.mock("../api", () => {
 class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

  return {
    ApiError,
    parseApiDate: (value: string) => new Date(value),
    authApi: {
      invitationInfo: mocks.invitationInfo,
      acceptInvitation: mocks.acceptInvitation,
    },
  };
});

const invitation = {
  email: "new@example.com",
  organization: "MaintAI Test",
  role: "member",
  expires_at: "2099-01-01T00:00:00.000Z",
};

function fillForm() {
  fireEvent.change(screen.getByLabelText("auth.fullName"), {
    target: { value: "  Jamal Test  " },
  });
  fireEvent.change(screen.getByLabelText("auth.password"), {
    target: { value: "password123" },
  });
  fireEvent.change(screen.getByLabelText("auth.passwordConfirm"), {
    target: { value: "password123" },
  });
}

beforeEach(() => {
  vi.clearAllMocks();

  mocks.status = "signedOut";
  mocks.me = null;
  mocks.invitationInfo.mockResolvedValue(invitation);
  mocks.acceptInvitation.mockResolvedValue({
    access_token: "test-access-token",
  });
  mocks.startSession.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
});

describe("AcceptInvitationPage", () => {
  it("lit le jeton d'invitation depuis l'adresse", () => {
    window.history.replaceState(
      null,
      "",
      "/?invitation=token123"
    );

    expect(readInvitationToken()).toBe("token123");
  });

  it("retire le jeton sans supprimer les autres paramètres", () => {
    window.history.replaceState(
      null,
      "",
      "/?invitation=token123&lang=fr#section"
    );

    clearInvitationFromUrl();

    expect(window.location.href).toContain("/?lang=fr#section");
    expect(readInvitationToken()).toBeNull();
  });

  it("charge les informations et affiche le formulaire", async () => {
    render(
      <AcceptInvitationPage token="token123" onDone={vi.fn()} />
    );

    expect(await screen.findByLabelText("auth.fullName")).toBeTruthy();
    expect(screen.getByLabelText("auth.email")).toBeTruthy();
    expect(mocks.invitationInfo).toHaveBeenCalledWith("token123");
    expect(screen.getByText(/invite\.intro/)).toBeTruthy();
  });

  it.each([
    [404, "", "invite.invalid"],
    [410, "", "invite.expired"],
    [409, "Invitation déjà utilisée", "invite.used"],
  ])(
    "affiche le bon message si l'invitation est refusée (%s)",
    async (status, detail, expected) => {
      const { ApiError } = await import("../api");
      mocks.invitationInfo.mockRejectedValue(
        new ApiError(status, detail || "Invitation refusée")
      );

      const onDone = vi.fn();

      render(
        <AcceptInvitationPage token="bad-token" onDone={onDone} />
      );

      expect(await screen.findByText(expected)).toBeTruthy();

      fireEvent.click(
        screen.getByRole("button", { name: "invite.goToLogin" })
      );

      expect(onDone).toHaveBeenCalledOnce();
    }
  );

  it("permet à un utilisateur déjà connecté de se déconnecter", async () => {
    mocks.status = "signedIn";
    mocks.me = { email: "existing@example.com" };

    render(
      <AcceptInvitationPage token="token123" onDone={vi.fn()} />
    );

    expect(
      await screen.findByText(/invite\.alreadySignedIn/)
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "auth.logout" }));

    expect(mocks.logout).toHaveBeenCalledOnce();
  });

  it("valide le nom et les deux mots de passe", async () => {
    render(
      <AcceptInvitationPage token="token123" onDone={vi.fn()} />
    );

    await screen.findByLabelText("auth.fullName");

    fireEvent.change(screen.getByLabelText("auth.password"), {
      target: { value: "123" },
    });
    fireEvent.change(screen.getByLabelText("auth.passwordConfirm"), {
      target: { value: "different" },
    });

    const form = screen.getByLabelText("auth.fullName").closest("form");
    if (!form) throw new Error("Formulaire introuvable");

    fireEvent.submit(form);

    expect(await screen.findByText("valid.required")).toBeTruthy();
    expect(screen.getByText("valid.password")).toBeTruthy();
    expect(screen.getByText("valid.passwordMatch")).toBeTruthy();
    expect(mocks.acceptInvitation).not.toHaveBeenCalled();
  });

  it("accepte l'invitation et ouvre une session", async () => {
    const onDone = vi.fn();

    render(
      <AcceptInvitationPage token="token123" onDone={onDone} />
    );

    await screen.findByLabelText("auth.fullName");
    fillForm();

    fireEvent.click(
      screen.getByRole("button", { name: "invite.accept" })
    );

    await waitFor(() => {
      expect(mocks.acceptInvitation).toHaveBeenCalledWith({
        token: "token123",
        full_name: "Jamal Test",
        password: "password123",
      });
    });

    expect(onDone).toHaveBeenCalledOnce();

    await waitFor(() => {
      expect(mocks.startSession).toHaveBeenCalledWith(
        "test-access-token"
      );
    });
  });
});
