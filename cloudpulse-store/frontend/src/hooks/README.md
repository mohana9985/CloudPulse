# `src/hooks/` — Custom React hooks

| File | Purpose |
|---|---|
| `useFetch.js` | `useFetch(loader, deps)` runs an async loader and returns `{ data, loading, error }` plus `reload()` for retries. Re-runs when `deps` change and ignores results from cancelled loads. Errors are converted with `getErrorMessage` from [`../services/api.js`](../services/README.md) |
