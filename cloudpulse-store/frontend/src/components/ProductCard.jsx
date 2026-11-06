import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCart } from '../context/CartContext.jsx'
import { formatPrice } from '../utils/format.js'
import ProductImage from './ProductImage.jsx'

export default function ProductCard({ product }) {
  const { addItem } = useCart()
  const [added, setAdded] = useState(false)
  const inStock = product.stock_quantity > 0

  const handleAdd = () => {
    addItem(product, 1)
    setAdded(true)
    setTimeout(() => setAdded(false), 1500)
  }

  return (
    <article className="card flex flex-col overflow-hidden transition-shadow hover:shadow-md">
      <Link to={`/products/${product.id}`} className="block aspect-square bg-slate-100">
        <ProductImage src={product.image_path} alt={product.name} className="h-full w-full" />
      </Link>
      <div className="flex flex-1 flex-col p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-navy-500">{product.category}</p>
        <h3 className="mt-1 text-base font-semibold leading-snug text-navy-900">
          <Link to={`/products/${product.id}`} className="hover:underline">
            {product.name}
          </Link>
        </h3>
        <p className="mt-1 line-clamp-2 text-sm text-slate-600">{product.description}</p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-4">
          <span className="text-lg font-bold text-navy-900">{formatPrice(product.price)}</span>
          <button type="button" className="btn-primary px-3 py-2" onClick={handleAdd} disabled={!inStock}>
            {!inStock ? 'Out of stock' : added ? 'Added ✓' : 'Add to cart'}
          </button>
        </div>
      </div>
    </article>
  )
}
