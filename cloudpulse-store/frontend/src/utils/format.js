// The shipping rule must match backend/app/services/order_service.py.
export const FREE_SHIPPING_THRESHOLD = 999
export const SHIPPING_FEE = 99
export const MAX_QTY_PER_ITEM = 20

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
})

export const formatPrice = (value) => inr.format(Number(value) || 0)

export const shippingFor = (subtotal) =>
  subtotal === 0 || subtotal >= FREE_SHIPPING_THRESHOLD ? 0 : SHIPPING_FEE

export const formatDateTime = (iso) =>
  new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
