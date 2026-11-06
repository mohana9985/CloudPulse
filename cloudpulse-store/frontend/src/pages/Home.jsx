import { Link } from 'react-router-dom'
import SearchBar from '../components/SearchBar.jsx'
import ProductGrid from '../components/ProductGrid.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import useFetch from '../hooks/useFetch.js'
import { productApi } from '../services/api.js'
import { FREE_SHIPPING_THRESHOLD, formatPrice } from '../utils/format.js'

export default function Home() {
  const featured = useFetch(() => productApi.list({ sort: 'price_desc', page_size: 8 }), [])
  const categories = useFetch(() => productApi.categories(), [])

  return (
    <>
      <section className="bg-navy-900 text-white">
        <div className="container-page grid gap-10 py-14 md:grid-cols-5 md:py-20">
          <div className="md:col-span-3">
            <p className="text-sm font-semibold uppercase tracking-widest text-navy-300">CloudPulse Store</p>
            <h1 className="mt-3 text-3xl font-bold leading-tight text-white sm:text-4xl lg:text-5xl">
              Everyday essentials, delivered from the cloud.
            </h1>
            <p className="mt-4 max-w-xl text-base text-navy-100 sm:text-lg">
              Browse electronics, books, home goods and more. This is a demonstration store used to
              measure cloud application performance — checkout is free and no payment is taken.
            </p>
            <div className="mt-8 max-w-xl">
              <SearchBar size="lg" placeholder="Search for headphones, books, kettles…" />
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/products" className="btn bg-white text-navy-900 hover:bg-navy-50">Shop all products</Link>
              <Link to="/about" className="btn border border-navy-400 text-white hover:bg-navy-800">About this project</Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 self-center md:col-span-2">
            {[
              ['24+', 'Products'],
              ['6', 'Categories'],
              [formatPrice(FREE_SHIPPING_THRESHOLD).replace('.00', ''), 'Free shipping from'],
              ['0', 'Real payments'],
            ].map(([value, label]) => (
              <div key={label} className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="mt-1 text-sm text-navy-200">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container-page py-12">
        <div className="flex items-end justify-between gap-4">
          <h2 className="section-title">Shop by category</h2>
          <Link to="/products" className="text-sm font-semibold text-navy-600 hover:text-navy-800">View all →</Link>
        </div>
        <div className="mt-6">
          {categories.loading && <LoadingSpinner label="Loading categories…" />}
          {categories.error && <ErrorMessage message={categories.error} onRetry={categories.reload} />}
          {categories.data && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {categories.data.map((c) => (
                <Link
                  key={c.name}
                  to={`/products?category=${encodeURIComponent(c.name)}`}
                  className="card p-4 transition-colors hover:border-navy-300 hover:bg-navy-50"
                >
                  <p className="font-semibold text-navy-900">{c.name}</p>
                  <p className="mt-1 text-sm text-slate-500">{c.product_count} products</p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="container-page pb-12">
        <h2 className="section-title">Featured products</h2>
        <p className="mt-1 text-slate-600">Our most popular premium picks this week.</p>
        <div className="mt-6">
          {featured.loading && <LoadingSpinner label="Loading products…" />}
          {featured.error && <ErrorMessage message={featured.error} onRetry={featured.reload} />}
          {featured.data && <ProductGrid products={featured.data.items} />}
        </div>
      </section>

      <section className="container-page">
        <div className="flex flex-col items-start justify-between gap-6 rounded-2xl border border-navy-100 bg-navy-50 p-8 md:flex-row md:items-center">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-navy-500">Limited-time offer</p>
            <h2 className="mt-1 text-2xl font-bold text-navy-900">
              Free shipping on orders over {formatPrice(FREE_SHIPPING_THRESHOLD)}
            </h2>
            <p className="mt-2 text-slate-600">Stock up on books and office supplies for the new semester.</p>
          </div>
          <Link to="/products?category=Books" className="btn-primary">Browse books</Link>
        </div>
      </section>
    </>
  )
}
