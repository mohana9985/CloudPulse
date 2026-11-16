# `frontend/scripts/` — Build helper scripts

| File | Purpose |
|---|---|
| `generate-product-images.mjs` | Writes one SVG per demo product to `../public/products/<slug>.svg`, using a colour and icon per category (Electronics, Home & Kitchen, Books, Sports & Fitness, Fashion, Office Supplies) |

```bash
cd cloudpulse-store/frontend
npm run generate:images
```

The same commands work in Windows PowerShell (`cd cloudpulse-store\frontend`).

The product list in the script must match `backend/app/database/seed.py` (slug, name, category).
