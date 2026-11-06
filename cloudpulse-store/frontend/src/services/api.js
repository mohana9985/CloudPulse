import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

export function getErrorMessage(error) {
  if (error?.response) {
    const { status, data } = error.response
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((d) => `${d.loc?.slice(1).join('.') || 'field'}: ${d.msg}`)
        .join('; ')
    }
    return `Request failed with status ${status}`
  }
  if (error?.code === 'ECONNABORTED') return 'The server took too long to respond. Please try again.'
  if (error?.request) return 'Cannot reach the server. Please check that the backend is running.'
  return error?.message || 'Something went wrong.'
}

export const productApi = {
  list: (params = {}) => api.get('/products', { params }).then((r) => r.data),
  get: (id) => api.get(`/products/${id}`).then((r) => r.data),
  search: (q, limit = 20) => api.get('/products/search', { params: { q, limit } }).then((r) => r.data),
  categories: () => api.get('/categories').then((r) => r.data),
}

export const orderApi = {
  create: (payload) => api.post('/orders', payload).then((r) => r.data),
  get: (id) => api.get(`/orders/${id}`).then((r) => r.data),
  recent: (limit = 10) => api.get('/orders', { params: { limit } }).then((r) => r.data),
}

export const contactApi = {
  submit: (payload) => api.post('/contact', payload).then((r) => r.data),
}

export const healthApi = {
  health: () => api.get('/health').then((r) => r.data),
}

export default api
