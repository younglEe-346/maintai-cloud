import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Configuration des tests du front-end (Vitest). Elle est séparée de vite.config.ts
// pour ne pas le modifier : le site et le serveur de développement restent identiques.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/__tests__/setup.ts"],
  },
});
