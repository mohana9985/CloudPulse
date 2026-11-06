# `app/schemas/` — Pydantic models

Request validation and response shapes used by the routers in [`api/`](../api/README.md).

| File | Models |
|---|---|
| `product.py` | `ProductOut`, `ProductList` (paginated listing), `CategoryOut` |
| `order.py` | `OrderItemCreate`, `OrderCreate` (customer name, e-mail, address, items — no payment data), `OrderItemOut`, `OrderOut`, `OrderSummary` |
| `contact.py` | `ContactCreate`, `ContactOut` |

Invalid input is rejected by FastAPI with `422` before any service code runs.
