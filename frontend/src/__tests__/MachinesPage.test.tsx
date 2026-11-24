
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import MachinesPage from "../pages/MachinesPage";

const mocks = vi.hoisted(() => ({
  role: "owner" as "owner" | "admin" | "member",
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
}));

vi.mock("../auth", () => ({
  useAuth: () => ({
    me: { id: "user-1", role: mocks.role },
  }),
}));

vi.mock("../i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params ? `${key} ${Object.values(params).join(" ")}` : key,
    formatDate: (value: Date) => value.toISOString().slice(0, 10),
  }),
}));

vi.mock("../api", () => ({
  parseApiDate: (value: string) => new Date(value),
  ApiError: class ApiError extends Error {
    kind: string;
    constructor(message: string, kind: string) {
      super(message);
      this.kind = kind;
    }
  },
  machinesApi: {
    list: mocks.list,
    create: mocks.create,
  },
  orgApi: {
    get: mocks.get,
  },
}));

vi.mock("../router", () => ({
  hrefFor: () => "/machine/test-machine",
}));

vi.mock("../components/NewKeyDialog", () => ({
  default: ({
    machine,
    onClose,
  }: {
    machine: { name: string };
    onClose: () => void;
  }) => (
    <div data-testid="new-key-dialog">
      <p>{machine.name}</p>
      <button onClick={onClose}>Fermer</button>
    </div>
  ),
}));

const machine = {
  id: "machine-1",
  name: "Presse hydraulique",
  status: "ACTIVE",
  api_key_prefix: "mai_123",
  api_key_revoked_at: null,
  created_at: "2026-01-01T10:00:00.000Z",
};

const organization = {
  plan: "FREE",
  machines: 1,
  limits: {
    max_machines: 10,
  },
};

const createdMachine = {
  id: "machine-2",
  name: "Nouvelle machine",
  status: "ACTIVE",
  api_key_prefix: "mai_456",
  api_key: "secret-test-key",
  api_key_revoked_at: null,
  created_at: "2026-01-02T10:00:00.000Z",
};

beforeEach(() => {
  vi.clearAllMocks();

  mocks.role = "owner";
  mocks.list.mockResolvedValue([machine]);
  mocks.get.mockResolvedValue(organization);
  mocks.create.mockResolvedValue(createdMachine);
});

afterEach(() => {
  cleanup();
});

describe("MachinesPage", () => {
  it("charge et affiche la liste des machines", async () => {
    render(<MachinesPage />);

    expect(
      await screen.findByText("Presse hydraulique")
    ).toBeTruthy();

    expect(mocks.list).toHaveBeenCalledOnce();
    expect(mocks.get).toHaveBeenCalledOnce();
  });

  it("affiche un état vide si aucune machine n'existe", async () => {
    mocks.list.mockResolvedValue([]);

    render(<MachinesPage />);

    expect(await screen.findByText("machines.emptyTitle")).toBeTruthy();
  });

  it("n'autorise pas un membre à ajouter une machine", async () => {
    mocks.role = "member";

    render(<MachinesPage />);

    expect(await screen.findByText("machines.memberOnly")).toBeTruthy();
    expect(screen.queryByLabelText("machines.name")).toBeNull();
    expect(screen.queryByRole("button", { name: "machines.add" })).toBeNull();
  });

  it("autorise un administrateur à ajouter une machine", async () => {
    mocks.role = "admin";

    render(<MachinesPage />);

    expect(await screen.findByLabelText("machines.name")).toBeTruthy();
    expect(screen.getByRole("button", { name: "machines.add" })).toBeTruthy();
  });

  it("bloque l'ajout lorsque la limite du plan est atteinte", async () => {
    mocks.get.mockResolvedValue({
      ...organization,
      machines: 10,
      limits: { max_machines: 10 },
    });

    render(<MachinesPage />);

    expect(await screen.findByText("machines.limitReached")).toBeTruthy();
    expect(screen.queryByLabelText("machines.name")).toBeNull();
  });

  it("refuse un nom vide", async () => {
    render(<MachinesPage />);

    const name = await screen.findByLabelText("machines.name");
    const form = name.closest("form");

    if (!form) throw new Error("Formulaire introuvable");

    fireEvent.submit(form);

    expect(await screen.findByText("valid.required")).toBeTruthy();
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("refuse un nom dépassant 100 caractères", async () => {
    render(<MachinesPage />);

    const name = await screen.findByLabelText("machines.name");
    fireEvent.change(name, {
      target: { value: "M".repeat(101) },
    });

    const form = name.closest("form");
    if (!form) throw new Error("Formulaire introuvable");

    fireEvent.submit(form);

    expect(await screen.findByText("machines.nameTooLong")).toBeTruthy();
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("crée une machine, recharge la liste et affiche le dialogue de clé", async () => {
    const { container } = render(<MachinesPage />);

    const name = await screen.findByLabelText("machines.name");
    fireEvent.change(name, {
      target: { value: "  Nouvelle machine  " },
    });

    fireEvent.click(screen.getByRole("button", { name: "machines.add" }));

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith("Nouvelle machine");
    });

    expect(await screen.findByTestId("new-key-dialog")).toBeTruthy();
    expect(screen.getByText("Nouvelle machine")).toBeTruthy();

    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });

    fireEvent.click(screen.getByRole("button", { name: "Fermer" }));

    expect(container.querySelector('[data-testid="new-key-dialog"]')).toBeNull();
  });
});
