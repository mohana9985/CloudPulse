import { useSearchParams } from 'react-router-dom'
import SearchBar from '../components/SearchBar.jsx'
import ProductGrid from '../components/ProductGrid.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import useFetch from '../hooks/useFetch.js'
import { productApi } from '../services/api.js'

const PAGE_SIZE = 8
const SORTS = [
  ['name', 'Name (A–Z)'],
  ['price_asc', 'Price: low to high'],
  ['price_desc', 'Price: high to low'],
  ['newest', 'Newest'],
]

export default function Products() {
  // All filters live in the URL (?q=&category=&sort=&page=) so they survive reloads.
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const category = params.get('category') || ''
  const sort = params.get('sort') || 'name'
  const page = Math.max(1, Number(params.get('page')) || 1)

  const categories = useFetch(() => productApi.categories(), [])
  const products = useFetch(
    () => productApi.list({ q: q || undefined, category: category || undefined, sort, page, page_size: PAGE_SIZE }),
    [q, category, sort, page],
  )

  const update = (changes) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    if (!('page' in changes)) next.delete('page') // new filter -> back to page 1
    setParams(next)
  }

  const data = products.data

  return (
    <div className="container-page py-10">
      <h1 className="section-title">All products</h1>
      <p className="mt-1 text-slate-600">Search, filter and sort the full CloudPulse catalogue.</p>

      <div className="card mt-6 space-y-4 p-4">
        <SearchBar initialValue={q} onSearch={(value) => update({ q: value })} />
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2" aria-label="Filter by category">
            <button
              type="button"
              onClick={() => update({ category: '' })}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium ${!category ? 'border-navy-800 bg-navy-800 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}
            >
              All
            </button>
            {categories.data?.map((c) => (
              <button
                key={c.name}
                type="button"
                onClick={() => update({ category: c.name })}
                className={`rounded-full border px-3 py-1.5 text-sm font-medium ${category === c.name ? 'border-navy-800 bg-navy-800 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}
              >
                {c.name}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="sort" className="text-sm font-medium text-slate-600">Sort by</label>
            <select id="sort" value={sort} onChange={(e) => update({ sort: e.target.value })} className="input w-auto py-2">
              {SORTS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="mt-6">
        {data && !products.loading && (
          <p className="mb-4 text-sm text-slate-500">
            Showing {data.items.length} of {data.total} products
            {q && <> for “<span className="font-medium text-navy-800">{q}</span>”</>}
            {category && <> in <span className="font-medium text-navy-800">{category}</span></>}
          </p>
        )}
        {products.loading && <LoadingSpinner label="Loading products…" />}
        {products.error && <ErrorMessage title="Could not load products" message={products.error} onRetry={products.reload} />}
        {data && !products.loading && (
          <>
            <ProductGrid products={data.items} emptyMessage={q ? `No products match “${q}”.` : 'No products found.'} />
            {data.total_pages > 1 && (
              <nav className="mt-8 flex items-center justify-center gap-2" aria-label="Pagination">
                <button type="button" className="btn-secondary" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
                  Previous
                </button>
                {Array.from({ length: data.total_pages }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => update({ page: String(n) })}
                    aria-current={n === page ? 'page' : undefined}
                    className={`h-10 w-10 rounded-lg text-sm font-semibold ${n === page ? 'bg-navy-800 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}
                  >
                    {n}
                  </button>
                ))}
                <button type="button" className="btn-secondary" disabled={page >= data.total_pages} onClick={() => update({ page: String(page + 1) })}>
                  Next
                </button>
              </nav>
            )}
          </>
        )}
      </div>
    </div>
  )
}
