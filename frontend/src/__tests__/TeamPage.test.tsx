
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import TeamPage from "../pages/TeamPage";
import type { Invitation, Member } from "../api";

const mocks = vi.hoisted(() => ({
  me: null as { id: string; role: "owner" | "admin" | "member" } | null,
  members: vi.fn(),
  invitations: vi.fn(),
  invite: vi.fn(),
  remove: vi.fn(),
  changeRole: vi.fn(),
  revoke: vi.fn(),
}));

vi.mock("../auth", () => ({
  useAuth: () => ({ me: mocks.me }),
}));

vi.mock("../i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params ? `${key} ${Object.values(params).join(" ")}` : key,
    formatDate: (value: Date | null) =>
      value instanceof Date ? value.toISOString().slice(0, 10) : "",
  }),
}));

vi.mock("../api", () => {
  class ApiError extends Error {
    kind: string;

    constructor(message: string, kind: string) {
      super(message);
      this.kind = kind;
    }
  }

  return {
    ApiError,
    parseApiDate: (value: string) => new Date(value),
    teamApi: {
      members: mocks.members,
      invitations: mocks.invitations,
      invite: mocks.invite,
      remove: mocks.remove,
      changeRole: mocks.changeRole,
      revoke: mocks.revoke,
    },
  };
});

function makeMember(overrides: Partial<Member> = {}): Member {
  return {
    id: "member-1",
    full_name: "Sam Member",
    email: "sam@example.com",
    role: "member",
    created_at: "2025-01-01T00:00:00.000Z",
    ...overrides,
  } as Member;
}

function makeInvitation(overrides: Partial<Invitation> = {}): Invitation {
  return {
    id: "invitation-1",
    email: "new@example.com",
    role: "member",
    accepted_at: null,
    revoked_at: null,
    expires_at: "2099-01-01T00:00:00.000Z",
    ...overrides,
  } as Invitation;
}

const owner = makeMember({
  id: "owner-1",
  full_name: "Olivia Owner",
  email: "owner@example.com",
  role: "owner",
});

const member = makeMember();

const pendingInvitation = makeInvitation();

beforeEach(() => {
  vi.clearAllMocks();

  mocks.me = { id: "owner-1", role: "owner" };

  mocks.members.mockResolvedValue([owner, member]);
  mocks.invitations.mockResolvedValue([pendingInvitation]);
  mocks.invite.mockResolvedValue({
    email: "new@example.com",
    email_sent: true,
  });
  mocks.remove.mockResolvedValue(undefined);
  mocks.changeRole.mockResolvedValue(undefined);
  mocks.revoke.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
});

describe("TeamPage", () => {
  it("charge les membres et les invitations pour le propriétaire", async () => {
    render(<TeamPage />);

    expect(await screen.findByText("Sam Member")).toBeTruthy();
    expect(mocks.members).toHaveBeenCalledOnce();
    expect(mocks.invitations).toHaveBeenCalledOnce();
    expect(screen.getByText("team.invitationsTitle")).toBeTruthy();
  });

  it("n'affiche pas le formulaire d'invitation pour un membre", async () => {
    mocks.me = { id: "member-1", role: "member" };

    render(<TeamPage />);

    expect(await screen.findByText("Sam Member")).toBeTruthy();
    expect(screen.getByText("team.memberOnly")).toBeTruthy();
    expect(screen.queryByLabelText("auth.email")).toBeNull();
    expect(mocks.invitations).not.toHaveBeenCalled();
  });

  it("empêche un administrateur d'inviter un autre administrateur", async () => {
    mocks.me = { id: "admin-1", role: "admin" };

    render(<TeamPage />);

    expect(await screen.findByText("Sam Member")).toBeTruthy();

    const adminOption = screen.getByRole("option", {
      name: "role.admin",
    }) as HTMLOptionElement;

    expect(adminOption.disabled).toBe(true);
  });

  it("refuse une adresse e-mail invalide", async () => {
    render(<TeamPage />);

    const email = await screen.findByLabelText("auth.email");
    fireEvent.change(email, { target: { value: "email-invalide" } });

    const form = email.closest("form");
    if (!form) throw new Error("Formulaire introuvable");

    fireEvent.submit(form);

    expect(await screen.findByText("valid.email")).toBeTruthy();
    expect(mocks.invite).not.toHaveBeenCalled();
  });

  it("envoie une invitation avec une adresse normalisée", async () => {
    render(<TeamPage />);

    const email = await screen.findByLabelText("auth.email");
    fireEvent.change(email, {
      target: { value: "  NEW@Example.com  " },
    });

    const form = email.closest("form");
    if (!form) throw new Error("Formulaire introuvable");

    fireEvent.submit(form);

    await waitFor(() => {
      expect(mocks.invite).toHaveBeenCalledWith(
        "new@example.com",
        "member"
      );
    });

    expect(await screen.findByText(/team\.invited/)).toBeTruthy();
  });

  it("permet au propriétaire de changer le rôle d'un membre", async () => {
    render(<TeamPage />);

    const roleSelect = await screen.findByLabelText(
      "team.roleOf Sam Member"
    );

    fireEvent.change(roleSelect, {
      target: { value: "admin" },
    });

    await waitFor(() => {
      expect(mocks.changeRole).toHaveBeenCalledWith(
        "member-1",
        "admin"
      );
    });
  });
});
