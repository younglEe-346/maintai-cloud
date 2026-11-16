import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Le front-end tourne sur http://localhost:5173 : c'est cette adresse précise
// que l'API autorise dans ALLOWED_ORIGINS (CORS). strictPort : si le port est
// pris, Vite s'arrête au lieu d'en choisir un autre que l'API refuserait.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: "localhost", port: 5173, strictPort: true },
  preview: { host: "localhost", port: 5173, strictPort: true },
});
