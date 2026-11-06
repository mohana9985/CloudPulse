# `frontend/public/` — Static files

Vite copies everything in this folder unchanged into `dist/` at build time, and Nginx serves it
from the site root.

| Path | Purpose |
|---|---|
| `favicon.svg` | Browser tab icon, referenced from `../index.html` |
| [`products/`](products/README.md) | 24 SVG product images served at `/products/<slug>.svg` |

Note: because of this copy step, this README is also copied into the build output. It contains
no configuration or secrets.
