# `src/components/` — Reusable UI components

| File | Purpose |
|---|---|
| `Navbar.jsx` | Top navigation with logo (`../assets/logo.svg`) and cart link |
| `Footer.jsx` | Site footer |
| `SearchBar.jsx` | Search input; submitting navigates to `/products?q=…` |
| `ProductGrid.jsx` | Grid layout for a list of products |
| `ProductCard.jsx` | One product tile (image, name, price) |
| `ProductImage.jsx` | Loads `/products/<slug>.svg`; falls back to a CSS placeholder if the image fails |
| `LoadingSpinner.jsx` | Loading indicator |
| `ErrorMessage.jsx` | Readable error display, optionally with a retry action |

Used by the route components in [`../pages/`](../pages/README.md).
