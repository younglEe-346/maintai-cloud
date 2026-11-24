
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SettingsPage from "../pages/SettingsPage";

const mocks = vi.hoisted(() => ({
  role: "owner" as "owner" | "admin" | "member",
  settings: vi.fn(),
  get: vi.fn(),
  updateSettings: vi.fn(),
  preview: vi.fn(),
  changePlan: vi.fn(),
  overview: vi.fn(),
  measures: vi.fn(),
  alerts: vi.fn(),
  retrain: vi.fn(),
  refreshMe: vi.fn(),
}));

vi.mock("../auth", () => ({
  useAuth: () => ({
    me: { id: "user-1", role: mocks.role },
    refreshMe: mocks.refreshMe,
  }),
}));

vi.mock("../i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      params ? `${key} ${Object.values(params).join(" ")}` : key,
    formatPercent: (value: number) => `${value * 100}%`,
    formatNumber: (value: number) => String(value),
    formatDate: (value: Date) => value.toISOString().slice(0, 10),
    serverText: (value: string) => value,
  }),
}));

vi.mock("../hooks", () => ({
  usePolling: vi.fn(),
}));

vi.mock("../api", () => ({
  parseApiDate: (value: string) => new Date(value),
  orgApi: {
    settings: mocks.settings,
    get: mocks.get,
    updateSettings: mocks.updateSettings,
    preview: mocks.preview,
    changePlan: mocks.changePlan,
  },
  modelsApi: {
    overview: mocks.overview,
    retrain: mocks.retrain,
  },
  exportApi: {
    measures: mocks.measures,
    alerts: mocks.alerts,
  },
}));

const initialSettings = {
  cost_ratio: 1,
  alert_open_k: 3,
  alert_close_k: 2,
  alert_close_factor: 0.8,
  threshold_high: 0.75,
  expected: {
    recall: 0.9,
    missed_failures: 2,
    false_alarms: 3,
    precision: 0.95,
    evaluated_on: 100,
  },
};

const organization = {
  plan: "FREE",
  machines: 2,
  measures_today: 50,
  limits: {
    custom_model: false,
    export: false,
    max_machines: 10,
    max_measures_per_day: 1000,
  },
};

function renderPage() {
  return render(<SettingsPage />);
}

function submitForm() {
  const input = screen.getByLabelText("settings.costRatio");
  const form = input.closest("form");

  if (!form) throw new Error("Formulaire introuvable");

  fireEvent.submit(form);
}

beforeEach(() => {
  vi.clearAllMocks();

  mocks.role = "owner";
  mocks.settings.mockResolvedValue(initialSettings);
  mocks.get.mockResolvedValue(organization);
  mocks.updateSettings.mockResolvedValue(initialSettings);
  mocks.preview.mockResolvedValue({
    threshold: 0.8,
    recall: 0.91,
    missed_failures: 1,
    false_alarms: 2,
    precision: 0.96,
  });
  mocks.changePlan.mockResolvedValue({ ...organization, plan: "PRO" });
  mocks.overview.mockResolvedValue({
    current_model: "test-model",
    custom_model_allowed: false,
    history: [],
  });
});

afterEach(() => {
  cleanup();
});

describe("SettingsPage", () => {
  it("affiche les réglages en lecture seule pour un membre", async () => {
    mocks.role = "member";

    renderPage();

    const costRatio = await screen.findByLabelText("settings.costRatio");

    expect(screen.getByText("settings.readOnly")).toBeTruthy();
    expect((costRatio as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "settings.save" })).toBeNull();
  });

  it("autorise l'administrateur à modifier les réglages mais pas le plan", async () => {
    mocks.role = "admin";

    renderPage();

    const costRatio = await screen.findByLabelText("settings.costRatio");

    expect((costRatio as HTMLInputElement).disabled).toBe(false);
    expect(screen.getByText("plan.ownerOnly")).toBeTruthy();
    expect(screen.getByRole("button", { name: "settings.save" })).toBeTruthy();
  });

  it("refuse un coût de panne nul", async () => {
    renderPage();

    const costRatio = await screen.findByLabelText("settings.costRatio");

    fireEvent.change(costRatio, { target: { value: "0" } });
    submitForm();

    expect(await screen.findByText("valid.costRatio")).toBeTruthy();
    expect(mocks.updateSettings).not.toHaveBeenCalled();
  });

  it("refuse une valeur K supérieure à 50 et un facteur égal à 1", async () => {
    renderPage();

    const openK = await screen.findByLabelText("settings.openK");
    const closeFactor = screen.getByLabelText("settings.closeFactor");

    fireEvent.change(openK, { target: { value: "51" } });
    fireEvent.change(closeFactor, { target: { value: "1" } });

    submitForm();

    expect(await screen.findAllByText("valid.k")).toHaveLength(1);
    expect(screen.getByText("valid.factor")).toBeTruthy();
    expect(mocks.updateSettings).not.toHaveBeenCalled();
  });

  it("accepte la virgule française et enregistre le nombre correctement", async () => {
    renderPage();

    const costRatio = await screen.findByLabelText("settings.costRatio");

    fireEvent.change(costRatio, { target: { value: "2,5" } });
    submitForm();

    await waitFor(() => {
      expect(mocks.updateSettings).toHaveBeenCalledWith({
        cost_ratio: 2.5,
        alert_open_k: 3,
        alert_close_k: 2,
        alert_close_factor: 0.8,
      });
    });

    expect(await screen.findByText(/settings\.saved/)).toBeTruthy();
  });
});
