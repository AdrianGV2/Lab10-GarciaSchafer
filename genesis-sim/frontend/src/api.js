// Where the simulator backend lives.
//
// Empty by default, meaning same-origin: in development Vite proxies /api to
// the backend (see vite.config.js), and in production the built files are
// served by the API itself. Set VITE_API_URL to point at a backend on another
// host or port.
const configured = (import.meta.env.VITE_API_URL ?? "").trim();

export const API_URL = configured.replace(/\/$/, "");

const wsBase = API_URL || window.location.origin;
export const WS_URL = wsBase.replace(/^http/, "ws");

export const api = (path) => `${API_URL}${path}`;
export const wsUrl = (path) => `${WS_URL}${path}`;
