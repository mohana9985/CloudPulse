# `src/pages/` — Route components

Each file is one page registered in `../App.jsx`.

| File | Route | Purpose |
|---|---|---|
| `Home.jsx` | `/` | Landing page with featured products |
| `Products.jsx` | `/products` | Catalogue with search (`?q=`), category filter and sorting |
| `ProductDetails.jsx` | `/products/:id` | Single product, add to cart |
| `Cart.jsx` | `/cart` | Cart contents, quantities, totals with the shipping rule |
| `Checkout.jsx` | `/checkout` | Customer details form; submits a demonstration order (`POST /api/orders`) |
| `OrderConfirmation.jsx` | `/order-confirmation/:id` | Shows the created order |
| `About.jsx` | `/about` | About the demonstration store |
| `Contact.jsx` | `/contact` | Contact form (`POST /api/contact`) |
| `NotFound.jsx` | `*` | 404 page |

These pages are the user journeys exercised by the Locust scenarios in
[`load-testing/`](../../../load-testing/README.md).
