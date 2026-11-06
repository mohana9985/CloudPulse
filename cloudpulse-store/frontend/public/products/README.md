# `public/products/` — Product images

24 flat SVG placeholder images, one per demo product, served at `/products/<slug>.svg`
(Nginx rule in `../../nginx.conf`). No external image service is used.

The file names (slugs) match the `image_path` values seeded by
`backend/app/database/seed.py`. The images are generated, not hand-drawn:

```bash
cd cloudpulse-store/frontend
npm run generate:images      # rewrites every *.svg here
```

Generator: [`scripts/generate-product-images.mjs`](../../scripts/README.md).
