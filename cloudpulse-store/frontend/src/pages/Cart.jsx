import { Link } from 'react-router-dom'
import { useCart } from '../context/CartContext.jsx'
import ProductImage from '../components/ProductImage.jsx'
import { FREE_SHIPPING_THRESHOLD, formatPrice } from '../utils/format.js'

export default function Cart() {
  const { items, itemCount, subtotal, shipping, total, updateQuantity, removeItem, clearCart, maxQuantity } = useCart()

  if (items.length === 0) {
    return (
      <div className="container-page py-16">
        <div className="card mx-auto max-w-lg px-6 py-12 text-center">
          <h1 className="text-2xl font-bold text-navy-900">Your cart is empty</h1>
          <p className="mt-2 text-slate-600">Browse the catalogue and add a few products to get started.</p>
          <Link to="/products" className="btn-primary mt-6">Continue shopping</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="container-page py-10">
      <h1 className="section-title">Shopping cart</h1>
      <p className="mt-1 text-slate-600">{itemCount} item{itemCount === 1 ? '' : 's'} in your cart</p>

      <div className="mt-6 grid gap-8 lg:grid-cols-3">
        <ul className="card divide-y divide-slate-200 lg:col-span-2">
          {items.map((item) => (
            <li key={item.id} className="flex gap-4 p-4">
              <Link to={`/products/${item.id}`} className="h-24 w-24 shrink-0 overflow-hidden rounded-lg bg-slate-100">
                <ProductImage src={item.image_path} alt={item.name} className="h-full w-full" />
              </Link>
              <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Link to={`/products/${item.id}`} className="font-semibold text-navy-900 hover:underline">{item.name}</Link>
                  <p className="text-sm text-slate-500">{item.category}</p>
                  <p className="mt-1 text-sm text-slate-700">{formatPrice(item.price)} each</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex items-center">
                    <button type="button" className="btn-secondary rounded-r-none px-3 py-1.5" onClick={() => updateQuantity(item.id, item.quantity - 1)} disabled={item.quantity <= 1} aria-label={`Decrease quantity of ${item.name}`}>−</button>
                    <span className="w-10 border-y border-navy-200 py-1.5 text-center text-sm font-semibold" aria-live="polite">{item.quantity}</span>
                    <button type="button" className="btn-secondary rounded-l-none px-3 py-1.5" onClick={() => updateQuantity(item.id, item.quantity + 1)} disabled={item.quantity >= maxQuantity(item)} aria-label={`Increase quantity of ${item.name}`}>+</button>
                  </div>
                  <p className="w-28 text-right font-semibold text-navy-900">{formatPrice(item.price * item.quantity)}</p>
                  <button type="button" onClick={() => removeItem(item.id)} className="text-sm font-medium text-red-600 hover:text-red-800">Remove</button>
                </div>
              </div>
            </li>
          ))}
        </ul>

        <aside className="card h-fit p-6">
          <h2 className="text-lg font-semibold">Order summary</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-slate-600">Subtotal</dt><dd className="font-medium">{formatPrice(subtotal)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-600">Shipping</dt><dd className="font-medium">{shipping === 0 ? 'Free' : formatPrice(shipping)}</dd></div>
            {shipping > 0 && (
              <p className="text-xs text-slate-500">Add {formatPrice(FREE_SHIPPING_THRESHOLD - subtotal)} more for free shipping.</p>
            )}
            <div className="flex justify-between border-t border-slate-200 pt-3 text-base"><dt className="font-semibold">Total</dt><dd className="font-bold text-navy-900">{formatPrice(total)}</dd></div>
          </dl>
          <Link to="/checkout" className="btn-primary mt-6 w-full py-3">Proceed to checkout</Link>
          <div className="mt-3 flex justify-between">
            <Link to="/products" className="text-sm font-medium text-navy-600 hover:text-navy-800">← Continue shopping</Link>
            <button type="button" onClick={clearCart} className="text-sm font-medium text-slate-500 hover:text-red-600">Clear cart</button>
          </div>
        </aside>
      </div>
    </div>
  )
}
