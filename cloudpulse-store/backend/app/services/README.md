# `app/services/` — Business logic

Functions called by the routers. They work on a SQLAlchemy session and contain the rules of the
demonstration store.

| File | Responsibility |
|---|---|
| `product_service.py` | Listing with category filter, text search over name/description/category, sorting (`SORT_OPTIONS`), pagination, categories with counts |
| `order_service.py` | Creates an order in one transaction with an atomic stock check (`ProductNotFoundError` → 404, `InsufficientStockError` → 409, rollback on any error); shipping rule: ₹99 fee below a ₹999 subtotal; order lookup and recent-order listing |
| `contact_service.py` | Stores contact-form messages and counts them |

The shipping rule is duplicated on the client in
[`frontend/src/utils/format.js`](../../../frontend/src/utils/README.md); keep both in sync.
