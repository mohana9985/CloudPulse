# `src/services/` — Backend API client

| File | Purpose |
|---|---|
| `api.js` | The only place that talks to the backend. Axios instance with base URL `import.meta.env.VITE_API_BASE_URL` or `/api` and a 10 s timeout. Exports `productApi`, `orderApi`, `contactApi`, `healthApi` and `getErrorMessage()` |

Endpoint reference: [`docs/API_DOCUMENTATION.md`](../../../docs/API_DOCUMENTATION.md).
