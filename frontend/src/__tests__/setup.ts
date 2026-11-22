// Remise à zéro après chaque test : écran démonté, navigateur vidé (jeton, langue), horloge réelle.
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  localStorage.clear();
});
