const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://13.60.20.155'
).replace(/\/$/, '')

const accessKey = 'risk-radar-employee-access'
const refreshKey = 'risk-radar-employee-refresh'

export function getAccessToken() {
  return localStorage.getItem(accessKey)
}

export function saveTokens(data) {
  localStorage.setItem(accessKey, data.access)
  if (data.refresh) localStorage.setItem(refreshKey, data.refresh)
}

export function clearTokens() {
  localStorage.removeItem(accessKey)
  localStorage.removeItem(refreshKey)
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  headers.set('Content-Type', 'application/json')
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })
  const text = await response.text()
  let payload = {}
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = { detail: text }
    }
  }
  if (!response.ok) {
    const detail = payload.detail || payload.error || Object.values(payload).flat().join(' ')
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return payload
}

export const api = {
  login: (email, password) => request('/api/users/auth/jwt/create/', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }),
  googleLogin: (credential) => request('/api/users/auth/google/', {
    method: 'POST',
    body: JSON.stringify({ credential }),
  }),
  products: () => request('/api/catalog/products/'),
  categories: () => request('/api/catalog/categories/'),
  checkout: (productId, quantity, paymentMethodId) => request('/api/payments/checkout/', {
    method: 'POST',
    body: JSON.stringify({
      product_id: productId,
      quantity,
      ...(paymentMethodId ? { payment_method_id: paymentMethodId } : {}),
    }),
  }),
  payments: () => request('/api/payments/my/'),
}

export { API_BASE_URL }
