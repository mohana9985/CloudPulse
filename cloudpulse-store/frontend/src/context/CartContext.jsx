import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { MAX_QTY_PER_ITEM, shippingFor } from '../utils/format.js'

const STORAGE_KEY = 'cloudpulse_cart_v1'
const CartContext = createContext(null)

function loadCart() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((i) => i && i.id && i.quantity > 0) : []
  } catch {
    return []
  }
}

const maxFor = (item) => Math.max(1, Math.min(MAX_QTY_PER_ITEM, item.stock_quantity ?? MAX_QTY_PER_ITEM))

export function CartProvider({ children }) {
  const [items, setItems] = useState(loadCart)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    } catch {
      // Storage may be unavailable (private mode); the cart still works in memory.
    }
  }, [items])

  const addItem = (product, quantity = 1) => {
    setItems((current) => {
      const existing = current.find((i) => i.id === product.id)
      if (existing) {
        return current.map((i) =>
          i.id === product.id ? { ...i, quantity: Math.min(maxFor(i), i.quantity + quantity) } : i,
        )
      }
      const item = {
        id: product.id,
        name: product.name,
        price: product.price,
        image_path: product.image_path,
        category: product.category,
        stock_quantity: product.stock_quantity,
        quantity: 1,
      }
      return [...current, { ...item, quantity: Math.min(maxFor(item), quantity) }]
    })
  }

  const updateQuantity = (id, quantity) => {
    setItems((current) =>
      current.map((i) => (i.id === id ? { ...i, quantity: Math.max(1, Math.min(maxFor(i), quantity)) } : i)),
    )
  }

  const removeItem = (id) => setItems((current) => current.filter((i) => i.id !== id))
  const clearCart = () => setItems([])

  const value = useMemo(() => {
    const itemCount = items.reduce((sum, i) => sum + i.quantity, 0)
    const subtotal = Math.round(items.reduce((sum, i) => sum + i.price * i.quantity, 0) * 100) / 100
    const shipping = shippingFor(subtotal)
    return {
      items,
      itemCount,
      subtotal,
      shipping,
      total: subtotal + shipping,
      addItem,
      updateQuantity,
      removeItem,
      clearCart,
      maxQuantity: maxFor,
    }
  }, [items])

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used inside <CartProvider>')
  return ctx
}
