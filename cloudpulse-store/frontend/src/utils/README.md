# `src/utils/` — Helper functions

| File | Purpose |
|---|---|
| `format.js` | `formatPrice()` (INR), `formatDateTime()`, constants `FREE_SHIPPING_THRESHOLD` (999), `SHIPPING_FEE` (99), `MAX_QTY_PER_ITEM` (20) and `shippingFor()` |
| `validation.js` | `isValidEmail()`, `minLength()`, `maxLength()` and `validate(values, rules)` for client-side form checks |

The shipping rule must match `backend/app/services/order_service.py`
([services README](../../../backend/app/services/README.md)). The backend validates every request
again; client validation is only for user feedback.
