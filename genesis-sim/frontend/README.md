# Front end

React + Blockly interface for the Manito Genesis simulator.

```bash
pnpm install
pnpm run dev     # http://localhost:5173, proxies /api to the backend
pnpm run build   # emits dist/, which the API serves on its own port
```

The app talks to its own origin by default: in development Vite proxies `/api`
to `http://localhost:8000` (override with `VITE_PROXY_TARGET`), and a build is
served by the simulator itself. To point at a backend elsewhere, copy
`.env.example` to `.env` and set `VITE_API_URL`.

See the repository README for the simulator itself.
