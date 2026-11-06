# `src/context/` — Shared state

| File | Purpose |
|---|---|
| `CartContext.jsx` | `CartProvider` and `useCart()`. Holds the shopping cart for every page and persists it in `localStorage` (key `cloudpulse_cart_v1`) so it survives reloads. Enforces `MAX_QTY_PER_ITEM` and uses `shippingFor()` from [`../utils/format.js`](../utils/README.md) |

The cart lives only in the browser; the backend sees it only when checkout submits an order.
