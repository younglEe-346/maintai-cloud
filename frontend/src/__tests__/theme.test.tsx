
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider, useTheme } from "../theme";

function ThemeProbe() {
  const { theme, toggle } = useTheme();

  return (
    <div>
      <p data-testid="theme">{theme}</p>
      <button onClick={toggle}>Changer le thème</button>
    </div>
  );
}

function mockSystemPreference(initialMatches: boolean) {
  let matches = initialMatches;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();

  const mediaQuery = {
    get matches() {
      return matches;
    },
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: vi.fn(
      (type: string, listener: (event: MediaQueryListEvent) => void) => {
        if (type === "change") listeners.add(listener);
      }
    ),
    removeEventListener: vi.fn(
      (type: string, listener: (event: MediaQueryListEvent) => void) => {
        if (type === "change") listeners.delete(listener);
      }
    ),
  } as unknown as MediaQueryList;

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn(() => mediaQuery),
  });

  return {
    setMatches(value: boolean) {
      matches = value;
      const event = {
        matches,
        media: mediaQuery.media,
      } as MediaQueryListEvent;

      listeners.forEach((listener) => listener(event));
    },
  };
}

function renderTheme() {
  return render(
    <ThemeProvider>
      <ThemeProbe />
    </ThemeProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});

describe("ThemeProvider", () => {
  it("suit le thème du système au premier passage", () => {
    const system = mockSystemPreference(false);

    renderTheme();

    expect(screen.getByTestId("theme").textContent).toBe("light");

    act(() => system.setMatches(true));

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("enregistre le choix de l'utilisateur et ne le remplace plus", () => {
    const system = mockSystemPreference(false);

    renderTheme();

    fireEvent.click(screen.getByRole("button", { name: "Changer le thème" }));

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(localStorage.getItem("maintai.theme")).toBe("dark");

    act(() => system.setMatches(false));

    expect(screen.getByTestId("theme").textContent).toBe("dark");
  });

  it("restaure le thème enregistré au prochain chargement", () => {
    localStorage.setItem("maintai.theme", "dark");
    mockSystemPreference(false);

    renderTheme();

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
