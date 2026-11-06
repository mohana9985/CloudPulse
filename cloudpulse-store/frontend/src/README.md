# `frontend/src/` — React application source

| Path | Responsibility |
|---|---|
| `main.jsx` | Mounts the app into `index.html` |
| `App.jsx` | Router and layout. Routes: `/`, `/products`, `/products/:id`, `/cart`, `/checkout`, `/order-confirmation/:id`, `/about`, `/contact`, `*` (not found) |
| `index.css` | Tailwind entry point and shared styles |
| [`pages/`](pages/README.md) | One component per route |
| [`components/`](components/README.md) | Reusable UI pieces |
| [`context/`](context/README.md) | Shopping-cart state |
| [`hooks/`](hooks/README.md) | `useFetch` data-loading hook |
| [`services/`](services/README.md) | All backend API calls |
| [`utils/`](utils/README.md) | Formatting and validation helpers |
| [`assets/`](assets/README.md) | Images bundled by Vite |

Data flow: pages call `services/api.js` (usually through `hooks/useFetch.js`), and read/write the
cart through `context/CartContext.jsx`.
