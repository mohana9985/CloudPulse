import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import { getErrorMessage, orderApi } from '../services/api.js'
import { formatPrice } from '../utils/format.js'
import { isValidEmail, maxLength, minLength, validate } from '../utils/validation.js'

const RULES = {
  customer_name: [[minLength(2), 'Please enter your full name.'], [maxLength(100), 'Name is too long.']],
  email: [[isValidEmail, 'Please enter a valid email address.']],
  address: [[minLength(5), 'Please enter a delivery address.'], [maxLength(300), 'Address is too long.']],
}

export default function Checkout() {
  const { items, subtotal, shipping, total, clearCart } = useCart()
  const navigate = useNavigate()
  const [form, setForm] = useState({ customer_name: '', email: '', address: '' })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState('')

  if (items.length === 0) {
    return (
      <div className="container-page py-16">
        <div className="card mx-auto max-w-lg px-6 py-12 text-center">
          <h1 className="text-2xl font-bold">Nothing to check out</h1>
          <p className="mt-2 text-slate-600">Your cart is empty. Add products before placing an order.</p>
          <Link to="/products" className="btn-primary mt-6">Browse products</Link>
        </div>
      </div>
    )
  }

  const onChange = (e) => {
    const { name, value } = e.target
    setForm((f) => ({ ...f, [name]: value }))
    if (errors[name]) setErrors((errs) => ({ ...errs, [name]: undefined }))
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    const found = validate(form, RULES)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSubmitting(true)
    setServerError('')
    try {
      const order = await orderApi.create({
        customer_name: form.customer_name.trim(),
        email: form.email.trim(),
        address: form.address.trim(),
        items: items.map((i) => ({ product_id: i.id, quantity: i.quantity })),
      })
      navigate(`/order-confirmation/${order.id}`, { replace: true })
      clearCart()
    } catch (err) {
      setServerError(getErrorMessage(err))
      setSubmitting(false)
    }
  }

  const field = (name, label, props = {}) => (
    <div>
      <label htmlFor={name} className="label">{label}</label>
      {props.as === 'textarea' ? (
        <textarea id={name} name={name} rows={3} value={form[name]} onChange={onChange} className={`input ${errors[name] ? 'input-error' : ''}`} aria-invalid={!!errors[name]} />
      ) : (
        <input id={name} name={name} value={form[name]} onChange={onChange} className={`input ${errors[name] ? 'input-error' : ''}`} aria-invalid={!!errors[name]} {...props} />
      )}
      {errors[name] && <p className="mt-1 text-sm text-red-600">{errors[name]}</p>}
    </div>
  )

  return (
    <div className="container-page py-10">
      <h1 className="section-title">Checkout</h1>
      <div className="mt-4 rounded-lg border border-navy-100 bg-navy-50 px-4 py-3 text-sm text-navy-800">
        This is a <strong>demonstration checkout</strong>. No payment is taken and no card details are requested.
      </div>

      <div className="mt-6 grid gap-8 lg:grid-cols-3">
        <form onSubmit={onSubmit} noValidate className="card space-y-5 p-6 lg:col-span-2">
          <h2 className="text-lg font-semibold">Customer details</h2>
          {field('customer_name', 'Full name', { autoComplete: 'name', maxLength: 100 })}
          {field('email', 'Email address', { type: 'email', autoComplete: 'email', maxLength: 254 })}
          {field('address', 'Delivery address', { as: 'textarea' })}
          {serverError && <ErrorMessage title="Order could not be placed" message={serverError} />}
          <button type="submit" className="btn-primary w-full py-3" disabled={submitting}>
            {submitting ? 'Placing order…' : `Place order · ${formatPrice(total)}`}
          </button>
        </form>

        <aside className="card h-fit p-6">
          <h2 className="text-lg font-semibold">Order summary</h2>
          <ul className="mt-4 divide-y divide-slate-100 text-sm">
            {items.map((i) => (
              <li key={i.id} className="flex justify-between gap-3 py-2">
                <span className="text-slate-700">{i.name} <span className="text-slate-400">× {i.quantity}</span></span>
                <span className="shrink-0 font-medium">{formatPrice(i.price * i.quantity)}</span>
              </li>
            ))}
          </ul>
          <dl className="mt-4 space-y-2 border-t border-slate-200 pt-4 text-sm">
            <div className="flex justify-between"><dt className="text-slate-600">Subtotal</dt><dd>{formatPrice(subtotal)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-600">Shipping</dt><dd>{shipping === 0 ? 'Free' : formatPrice(shipping)}</dd></div>
            <div className="flex justify-between pt-2 text-base"><dt className="font-semibold">Total</dt><dd className="font-bold text-navy-900">{formatPrice(total)}</dd></div>
          </dl>
          <Link to="/cart" className="mt-4 inline-block text-sm font-medium text-navy-600 hover:text-navy-800">← Edit cart</Link>
        </aside>
      </div>
    </div>
  )
}
