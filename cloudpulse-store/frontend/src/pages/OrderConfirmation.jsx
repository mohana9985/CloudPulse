import { Link, useParams } from 'react-router-dom'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import useFetch from '../hooks/useFetch.js'
import { orderApi } from '../services/api.js'
import { formatDateTime, formatPrice } from '../utils/format.js'

export default function OrderConfirmation() {
  const { id } = useParams()
  const { data: order, loading, error, reload } = useFetch(() => orderApi.get(id), [id])

  if (loading) return <LoadingSpinner label="Loading your order…" />
  if (error) {
    return (
      <div className="container-page py-10">
        <ErrorMessage title="Order not available" message={error} onRetry={reload} />
        <Link to="/products" className="btn-secondary mt-6">Continue shopping</Link>
      </div>
    )
  }

  return (
    <div className="container-page py-10">
      <div className="card mx-auto max-w-3xl p-6 sm:p-8">
        <div className="flex flex-col gap-2 border-b border-slate-200 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-emerald-700">Thank you — order placed</p>
            <h1 className="mt-1 text-2xl font-bold text-navy-900">Order #{order.id}</h1>
            <p className="text-sm text-slate-500">Placed on {formatDateTime(order.created_at)}</p>
          </div>
          <span className="w-fit rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700">{order.status}</span>
        </div>

        <section className="grid gap-4 border-b border-slate-200 py-6 sm:grid-cols-2">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Customer</h2>
            <p className="mt-2 font-medium text-navy-900">{order.customer_name}</p>
            <p className="text-sm text-slate-600">{order.email}</p>
          </div>
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Delivery address</h2>
            <p className="mt-2 whitespace-pre-line text-sm text-slate-700">{order.address}</p>
          </div>
        </section>

        <section className="py-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Items</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500">
                <tr>
                  <th className="py-2 font-medium">Product</th>
                  <th className="py-2 text-right font-medium">Qty</th>
                  <th className="py-2 text-right font-medium">Unit price</th>
                  <th className="py-2 text-right font-medium">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {order.items.map((item) => (
                  <tr key={item.id}>
                    <td className="py-2"><Link to={`/products/${item.product_id}`} className="text-navy-800 hover:underline">{item.product_name}</Link></td>
                    <td className="py-2 text-right">{item.quantity}</td>
                    <td className="py-2 text-right">{formatPrice(item.unit_price)}</td>
                    <td className="py-2 text-right font-medium">{formatPrice(item.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <dl className="ml-auto mt-4 max-w-xs space-y-2 border-t border-slate-200 pt-4 text-sm">
            <div className="flex justify-between"><dt className="text-slate-600">Subtotal</dt><dd>{formatPrice(order.subtotal)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-600">Shipping</dt><dd>{order.shipping_fee === 0 ? 'Free' : formatPrice(order.shipping_fee)}</dd></div>
            <div className="flex justify-between text-base"><dt className="font-semibold">Total paid</dt><dd className="font-bold text-navy-900">{formatPrice(order.total_amount)}</dd></div>
          </dl>
        </section>

        <p className="rounded-lg bg-slate-50 px-4 py-3 text-xs text-slate-500">
          This is a demonstration order. No payment was taken and nothing will be shipped.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/products" className="btn-primary">Continue shopping</Link>
          <Link to="/" className="btn-secondary">Back to home</Link>
        </div>
      </div>
    </div>
  )
}
