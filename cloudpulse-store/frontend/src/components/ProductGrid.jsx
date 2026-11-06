import ProductCard from './ProductCard.jsx'

export default function ProductGrid({ products, emptyMessage = 'No products found.' }) {
  if (!products || products.length === 0) {
    return (
      <div className="card px-6 py-12 text-center">
        <p className="text-base font-semibold text-navy-900">{emptyMessage}</p>
        <p className="mt-1 text-sm text-slate-500">Try a different search term or category.</p>
      </div>
    )
  }
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  )
}
