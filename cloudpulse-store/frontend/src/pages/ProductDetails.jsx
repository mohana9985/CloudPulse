import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ProductImage from '../components/ProductImage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import useFetch from '../hooks/useFetch.js'
import { productApi } from '../services/api.js'
import { useCart } from '../context/CartContext.jsx'
import { MAX_QTY_PER_ITEM, formatPrice } from '../utils/format.js'

export default function ProductDetails() {
  const { id } = useParams()
  const { data: product, loading, error, reload } = useFetch(() => productApi.get(id), [id])
  const { addItem, items } = useCart()
  const [quantity, setQuantity] = useState(1)
  const [message, setMessage] = useState('')

  if (loading) return <LoadingSpinner label="Loading product…" />
  if (error) {
    return (
      <div className="container-page py-10">
        <ErrorMessage title="Product unavailable" message={error} onRetry={reload} />
        <Link to="/products" className="btn-secondary mt-6">← Back to products</Link>
      </div>
    )
  }

  const inCart = items.find((i) => i.id === product.id)?.quantity || 0
  const maxQty = Math.min(MAX_QTY_PER_ITEM, product.stock_quantity)
  const lowStock = product.stock_quantity > 0 && product.stock_quantity <= 10

  const handleAdd = () => {
    addItem(product, quantity)
    setMessage(`${quantity} × ${product.name} added to your cart.`)
  }

  return (
    <div className="container-page py-10">
      <nav className="text-sm text-slate-500" aria-label="Breadcrumb">
        <Link to="/products" className="hover:text-navy-700">Products</Link>
        <span className="mx-2">/</span>
        <Link to={`/products?category=${encodeURIComponent(product.category)}`} className="hover:text-navy-700">{product.category}</Link>
        <span className="mx-2">/</span>
        <span className="text-slate-700">{product.name}</span>
      </nav>

      <div className="mt-6 grid gap-10 md:grid-cols-2">
        <div className="card overflow-hidden">
          <ProductImage src={product.image_path} alt={product.name} className="aspect-square w-full" />
        </div>

        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-navy-500">{product.category}</p>
          <h1 className="mt-2 text-3xl font-bold text-navy-900">{product.name}</h1>
          <p className="mt-4 text-3xl font-bold text-navy-900">{formatPrice(product.price)}</p>
          <p className="mt-1 text-sm text-slate-500">Inclusive of all taxes</p>

          <div className="mt-4">
            {product.stock_quantity === 0 ? (
              <span className="rounded-full bg-red-50 px-3 py-1 text-sm font-medium text-red-700">Out of stock</span>
            ) : (
              <span className={`rounded-full px-3 py-1 text-sm font-medium ${lowStock ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-700'}`}>
                {lowStock ? `Only ${product.stock_quantity} left` : `In stock (${product.stock_quantity} available)`}
              </span>
            )}
          </div>

          <p className="mt-6 leading-relaxed text-slate-700">{product.description}</p>

          {product.stock_quantity > 0 && (
            <div className="mt-8 flex flex-wrap items-end gap-4">
              <div>
                <label htmlFor="qty" className="label">Quantity</label>
                <div className="flex items-center">
                  <button type="button" className="btn-secondary rounded-r-none px-3" onClick={() => setQuantity((q) => Math.max(1, q - 1))} aria-label="Decrease quantity">−</button>
                  <input
                    id="qty"
                    type="number"
                    min="1"
                    max={maxQty}
                    value={quantity}
                    onChange={(e) => setQuantity(Math.max(1, Math.min(maxQty, Number(e.target.value) || 1)))}
                    className="input w-16 rounded-none text-center"
                  />
                  <button type="button" className="btn-secondary rounded-l-none px-3" onClick={() => setQuantity((q) => Math.min(maxQty, q + 1))} aria-label="Increase quantity">+</button>
                </div>
              </div>
              <button type="button" className="btn-primary px-6 py-3" onClick={handleAdd}>Add to cart</button>
            </div>
          )}

          {message && (
            <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">
              {message} <Link to="/cart" className="font-semibold underline">View cart</Link>
            </div>
          )}
          {inCart > 0 && !message && <p className="mt-4 text-sm text-slate-500">You already have {inCart} in your cart.</p>}

          <dl className="mt-8 grid grid-cols-2 gap-4 border-t border-slate-200 pt-6 text-sm">
            <div><dt className="text-slate-500">Product ID</dt><dd className="font-medium text-navy-900">#{product.id}</dd></div>
            <div><dt className="text-slate-500">Category</dt><dd className="font-medium text-navy-900">{product.category}</dd></div>
            <div><dt className="text-slate-500">Availability</dt><dd className="font-medium text-navy-900">{product.in_stock ? 'Available' : 'Unavailable'}</dd></div>
            <div><dt className="text-slate-500">Delivery</dt><dd className="font-medium text-navy-900">Demo only</dd></div>
          </dl>
        </div>
      </div>
    </div>
  )
}
