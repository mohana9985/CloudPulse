# CloudPulse Store — Frontend

React 18 single-page application (Vite, Tailwind CSS, React Router, Axios) for the CloudPulse
Store demonstration shop: home, product listing and search, product details, cart, checkout,
order confirmation, about and contact pages. No real products are sold and no payment is taken.

All API calls use the relative base URL `/api`. In Docker, Nginx serves the built files and
proxies `/api/*` to the backend; in development the Vite dev server proxies `/api` to
`http://localhost:8000`. The browser therefore never makes cross-origin requests.

## Contents

| Path | Responsibility |
|---|---|
| [`src/`](src/README.md) | Application source (pages, components, context, hooks, services, utils) |
| [`public/`](public/README.md) | Static files copied unchanged into the build (favicon, product images) |
| [`scripts/`](scripts/README.md) | Generator for the SVG product images |
| `index.html` | Vite HTML entry point |
| `package.json`, `package-lock.json` | Dependencies and npm scripts |
| `vite.config.js` | React plugin, dev server on port 5173 with `/api` proxy (`VITE_PROXY_TARGET` overrides the target), output to `dist/` |
| `tailwind.config.js`, `postcss.config.js` | Styling build configuration |
| `Dockerfile` | Multi-stage build: `node:22-alpine` runs `npm ci` + `npm run build`, `nginx:1.27-alpine` serves `dist/` |
| `nginx.conf` | SPA routing, `/api/` reverse proxy, `/nginx-health`, private-network-only `/nginx-status`, deny rules for dot-files and database files |
| `.dockerignore` | Keeps `node_modules`, `dist` and env files out of the build context |

`dist/` and `node_modules/` are generated and are not tracked in Git.

## npm scripts

Requires Node.js 20.19+ (22 recommended).

```bash
cd cloudpulse-store/frontend
npm ci                    # install exact versions from package-lock.json
npm run dev               # http://localhost:5173 (start the backend on port 8000 first)
npm run build             # production build into dist/
npm run preview           # serve the production build locally
npm run generate:images   # regenerate public/products/*.svg
```

## Related documentation
- [Store README](../README.md) · [Local setup](../docs/LOCAL_SETUP.md) · [Architecture](../docs/ARCHITECTURE.md)
