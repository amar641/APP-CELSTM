import { defineConfig } from "vite";

// Built output is served directly by FastAPI (see src/industrial_fire/api/main.py's
// StaticFiles mount) as the same origin as the API — no BFF, no separate host.
export default defineConfig({
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      // `npm run dev` talks to a locally running `uv run uvicorn ...` — see frontend/README.md.
      "/api": "http://127.0.0.1:8000",
    },
  },
});
