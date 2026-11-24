
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AlertsPage from "../pages/AlertsPage";
import type { Alert } from "../api";

const mocks = vi.hoisted(() => ({
    me: {
        full_name: "Jamal Test",
        email: "jamal@example.com",
    },
    alertsList: vi.fn(),
    machinesList: vi.fn(),
    acknowledge: vi.fn(),
    later: vi.fn(),
}));

vi.mock("../auth", () => ({
    useAuth: () => ({ me: mocks.me }),
}));

vi.mock("../i18n", () => ({
    useI18n: () => ({
        t: (key: string, params?: Record<string, string>) =>
            params ? `${key} ${Object.values(params).join(" ")}` : key,
        formatDate: (value: Date) => value.toISOString().slice(0, 10),
        formatTime: (value: Date) => value.toISOString().slice(11, 19),
        formatPercent: (value: number) => `${Math.round(value * 100)}%`,
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
    alertsApi: {
        list: mocks.alertsList,
        acknowledge: mocks.acknowledge,
    },
    machinesApi: {
        list: mocks.machinesList,
    },
}));

vi.mock("../hooks", async () => {
    const React = await import("react");

    return {
        usePolling: (callback: () => void | Promise<void>, interval: number) => {
            React.useEffect(() => {
                void callback();

                const timer = window.setInterval(() => {
                    void callback();
                }, interval);

                return () => window.clearInterval(timer);
            }, [callback, interval]);
        },
        useTimeout: () => mocks.later,
    };
});

function makeAlert(overrides: Partial<Alert> = {}): Alert {
    return {
        id: "alert-1",
        machine_id: "machine-1",
        status: "OPEN",
        created_at: "2026-01-01T10:00:00.000Z",
        closed_at: null,
        risk_score: 0.75,
        peak_risk_score: 0.95,
        last_risk_score: 0.65,
        probable_mode: "mechanical",
        details: "Vibration anormale détectée",
        acknowledged_by_name: null,
        acknowledged_at: null,
        ack_comment: null,
        ...overrides,
    } as unknown as Alert;
}

const activeAlert = makeAlert();

const closedAlert = makeAlert({
    id: "alert-2",
    status: "CLOSED",
    created_at: "2026-01-02T10:00:00.000Z",
    closed_at: "2026-01-02T12:00:00.000Z",
    details: null,
});

const acknowledgedAlert = makeAlert({
    status: "ACKNOWLEDGED",
    acknowledged_by_name: "Admin Test",
    acknowledged_at: "2026-01-01T11:00:00.000Z",
    ack_comment: "Inspection effectuée",
});

beforeEach(() => {
    vi.clearAllMocks();

    mocks.alertsList.mockImplementation(async (status: string) =>
        status === "active" ? [activeAlert] : [closedAlert]
    );

    mocks.machinesList.mockResolvedValue([
        { id: "machine-1", name: "Tour CN 1" },
    ]);

    mocks.acknowledge.mockResolvedValue(undefined);
});

afterEach(() => {
    cleanup();
});

describe("AlertsPage", () => {
    it("charge les alertes actives et l'historique", async () => {
        render(<AlertsPage />);

        expect(
            await screen.findByRole("heading", { name: "Tour CN 1" })
        ).toBeTruthy();

        expect(
            screen.getByRole("heading", {
                name: /alerts\.activeTitle\s*\(1\)/,
            })
        ).toBeTruthy();
        expect(screen.getByText("alerts.historyTitle")).toBeTruthy();

        expect(mocks.alertsList).toHaveBeenCalledWith("active");
        expect(mocks.alertsList).toHaveBeenCalledWith("CLOSED", 20);
        expect(mocks.machinesList).toHaveBeenCalledOnce();
    });

    it("affiche un nom de remplacement si la machine est inconnue", async () => {
        mocks.alertsList.mockImplementation(async (status: string) =>
            status === "active"
                ? [makeAlert({ machine_id: "unknown-machine" })]
                : []
        );

        render(<AlertsPage />);

        expect(
            await screen.findByRole("heading", { name: "alerts.unknownMachine" })
        ).toBeTruthy();
    });

    it("affiche les états vides sans alerte", async () => {
        mocks.alertsList.mockResolvedValue([]);

        render(<AlertsPage />);

        expect(await screen.findByText("alerts.emptyActiveTitle")).toBeTruthy();
        expect(screen.getByText("alerts.emptyHistory")).toBeTruthy();
    });

    it("recharge les données lorsque l'utilisateur clique sur actualiser", async () => {
        render(<AlertsPage />);

        await screen.findByRole("heading", { name: "Tour CN 1" });

        fireEvent.click(
            screen.getByRole("button", { name: "common.refresh" })
        );

        await waitFor(() => {
            expect(mocks.alertsList).toHaveBeenCalledTimes(4);
            expect(mocks.machinesList).toHaveBeenCalledTimes(2);
        });
    });

    it("acquitte une alerte avec un commentaire et recharge la liste", async () => {
        render(<AlertsPage />);

        await screen.findByRole("heading", { name: "Tour CN 1" });

        fireEvent.click(
            screen.getByRole("button", { name: "alerts.ackButton" })
        );

        const comment = screen.getByLabelText("alerts.comment");

        fireEvent.change(comment, {
            target: { value: "Inspection effectuée" },
        });

        fireEvent.click(
            screen.getByRole("button", { name: "alerts.ackConfirm" })
        );

        await waitFor(() => {
            expect(mocks.acknowledge).toHaveBeenCalledWith(
                "alert-1",
                "Inspection effectuée"
            );
        });

        await waitFor(() => {
            expect(mocks.alertsList).toHaveBeenCalledTimes(4);
        });
    });

    it("refuse un commentaire de plus de 2000 caractères", async () => {
        render(<AlertsPage />);

        await screen.findByRole("heading", { name: "Tour CN 1" });

        fireEvent.click(
            screen.getByRole("button", { name: "alerts.ackButton" })
        );

        const comment = screen.getByLabelText("alerts.comment");

        fireEvent.change(comment, {
            target: { value: "A".repeat(2001) },
        });

        expect(
            screen.getByRole("heading", { name: "alerts.activeTitle (1)" })
        ).toBeTruthy();

        const confirmButton = screen.getByRole("button", {
            name: "alerts.ackConfirm",
        }) as HTMLButtonElement;

        expect(confirmButton.disabled).toBe(true);

        expect(mocks.acknowledge).not.toHaveBeenCalled();
    });

    it("affiche les informations d'une alerte déjà acquittée", async () => {
        mocks.alertsList.mockImplementation(async (status: string) =>
            status === "active" ? [acknowledgedAlert] : []
        );

        render(<AlertsPage />);

        expect(
            await screen.findByRole("heading", { name: "Tour CN 1" })
        ).toBeTruthy();

        expect(screen.getByText(/alerts\.ackBy/)).toBeTruthy();
        expect(screen.getByText(/alerts\.ackComment/)).toBeTruthy();
        expect(screen.queryByRole("button", { name: "alerts.ackButton" })).toBeNull();
        expect(screen.getByText("alerts.ackStaysActive")).toBeTruthy();
    });
});
