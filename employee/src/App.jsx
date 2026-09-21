import { useEffect, useMemo, useState } from 'react'
import { api, clearTokens, getAccessToken, saveTokens } from './api'
import Scene from './Scene'

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
})

function Login({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

  useEffect(() => {
    if (!googleClientId) return undefined
    const renderGoogleButton = () => {
      if (!window.google?.accounts?.id) return false
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async ({ credential }) => {
          setError('')
          setLoading(true)
          try {
            const tokens = await api.googleLogin(credential)
            saveTokens(tokens)
            onLogin()
          } catch (err) {
            setError(err.message)
          } finally {
            setLoading(false)
          }
        },
      })
      window.google.accounts.id.renderButton(
        document.getElementById('google-login'),
        { theme: 'filled_black', size: 'large', width: 360, text: 'continue_with' },
      )
      return true
    }
    if (renderGoogleButton()) return undefined
    const timer = window.setInterval(() => {
      if (renderGoogleButton()) window.clearInterval(timer)
    }, 250)
    return () => window.clearInterval(timer)
  }, [googleClientId, onLogin])

  async function submit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokens = await api.login(email, password)
      saveTokens(tokens)
      onLogin()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="brand-mark">RR</div>
        <p className="eyebrow">EMPLOYEE PORTAL</p>
        <h1>Move faster.<br /><span>Work smarter.</span></h1>
        <p className="muted">Sign in to browse the catalog and place a secure Stripe order.</p>
        <form onSubmit={submit}>
          <label>Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
          <label>Password<input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••••" /></label>
          {error && <div className="alert error">{error}</div>}
          <button className="primary wide" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>
        </form>
        {googleClientId && <><div className="login-divider"><span>or</span></div><div id="google-login" className="google-login" /></>}
        {!googleClientId && <small>Google login requires VITE_GOOGLE_CLIENT_ID in employee/.env</small>}
        <small>API: 13.60.20.155 · Employee access only</small>
      </section>
      <section className="login-art"><Scene /><div className="art-copy"><span>01</span><p>One catalog.<br /><strong>Every decision.</strong></p></div></section>
    </main>
  )
}

function App() {
  const [loggedIn, setLoggedIn] = useState(Boolean(getAccessToken()))
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [payments, setPayments] = useState([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [cart, setCart] = useState([])
  const [notice, setNotice] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('catalog')
  const [paymentMethod, setPaymentMethod] = useState('')

  useEffect(() => {
    if (!loggedIn) return
    setLoading(true)
    Promise.all([api.products(), api.categories()])
      .then(([productData, categoryData]) => {
        setProducts(Array.isArray(productData) ? productData : productData.results || [])
        setCategories(Array.isArray(categoryData) ? categoryData : categoryData.results || [])
      })
      .catch((err) => setNotice({ type: 'error', text: err.message }))
      .finally(() => setLoading(false))
  }, [loggedIn])

  useEffect(() => {
    if (activeTab !== 'orders') return
    api.payments().then(setPayments).catch((err) => setNotice({ type: 'error', text: err.message }))
  }, [activeTab])

  const visibleProducts = useMemo(() => products.filter((product) => {
    const matchesQuery = `${product.name} ${product.description || ''}`.toLowerCase().includes(query.toLowerCase())
    const matchesCategory = category === 'all' || String(product.category) === category
    return matchesQuery && matchesCategory
  }), [products, query, category])

  const cartTotal = cart.reduce((sum, item) => sum + Number(item.price) * item.quantity, 0)

  function addToCart(product) {
    setCart((current) => {
      const existing = current.find((item) => item.id === product.id)
      if (existing) return current.map((item) => item.id === product.id ? { ...item, quantity: item.quantity + 1 } : item)
      return [...current, { ...product, quantity: 1 }]
    })
    setNotice({ type: 'success', text: `${product.name} added to order` })
  }

  function changeQuantity(id, delta) {
    setCart((current) => current.map((item) => item.id === id ? { ...item, quantity: Math.max(0, item.quantity + delta) } : item).filter((item) => item.quantity))
  }

  async function checkout(item) {
    try {
      const result = await api.checkout(item.id, item.quantity, paymentMethod.trim())
      setCart((current) => current.filter((cartItem) => cartItem.id !== item.id))
      setNotice({ type: 'success', text: result.message || 'Payment successful. Stock updated.' })
      setProducts((current) => current.map((product) => product.id === item.id ? { ...product, stock_quantity: product.stock_quantity - item.quantity, count: product.count - item.quantity } : product))
    } catch (err) {
      setNotice({ type: 'error', text: err.message })
    }
  }

  if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} />

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="logo"><span>◈</span> RISK<span className="mint">RADAR</span></div>
        <nav><button className={activeTab === 'catalog' ? 'nav-active' : ''} onClick={() => setActiveTab('catalog')}>Catalog</button><button className={activeTab === 'orders' ? 'nav-active' : ''} onClick={() => setActiveTab('orders')}>My orders</button></nav>
        <button className="logout" onClick={() => { clearTokens(); setLoggedIn(false) }}>Sign out <span>↗</span></button>
      </header>
      <main>
        <section className="hero">
          <div><p className="eyebrow">EMPLOYEE STORE / 2026</p><h1>Choose with<br /><span>confidence.</span></h1><p className="hero-text">Everything your team needs, curated in one place.</p></div>
          <Scene />
          <div className="hero-stat"><strong>{products.length || '—'}</strong><span>ACTIVE<br />PRODUCTS</span></div>
        </section>
        {notice && <div className={`alert ${notice.type}`} onClick={() => setNotice(null)}>{notice.text}<b>×</b></div>}
        {activeTab === 'orders' ? (
          <section className="orders"><div className="section-heading"><div><p className="eyebrow">ACCOUNT ACTIVITY</p><h2>My orders</h2></div></div>{payments.length ? payments.map((payment) => <div className="order-row" key={payment.id}><div><strong>{payment.product_name}</strong><span>{payment.created_at ? new Date(payment.created_at).toLocaleString() : 'Recent order'}</span></div><span>× {payment.quantity}</span><b className={`status ${payment.status.toLowerCase()}`}>{payment.status}</b><strong>{money.format(Number(payment.amount_total))}</strong></div>) : <div className="empty">No orders yet.</div>}</section>
        ) : (
          <>
            <section className="toolbar"><div className="search"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search products…" /></div><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><span className="result-count">{visibleProducts.length} results</span></section>
            <section className="catalog-layout"><div className="product-grid">{loading ? <div className="empty">Loading catalog…</div> : visibleProducts.map((product) => <article className="product-card" key={product.id}><div className="product-image">{product.image ? <img src={product.image} alt="" /> : <div className="image-placeholder"><span>◈</span></div>}<span className="stock">{product.stock_quantity ?? product.count ?? 0} in stock</span></div><div className="product-info"><p className="product-category">{product.category_name || 'CATALOG'}</p><h3>{product.name}</h3><p className="description">{product.description || 'Ready for your next decision.'}</p><div className="product-bottom"><strong>{money.format(Number(product.price))}</strong><button onClick={() => addToCart(product)} disabled={!Number(product.stock_quantity ?? product.count)}>Add to order <span>+</span></button></div></div></article>)}</div><aside className="cart"><div className="cart-head"><div><p className="eyebrow">YOUR SELECTION</p><h2>Order <span>{cart.length}</span></h2></div><span className="cart-icon">↗</span></div>{cart.length ? <>{cart.map((item) => <div className="cart-item" key={item.id}><div><strong>{item.name}</strong><span>{money.format(Number(item.price))}</span></div><div className="stepper"><button onClick={() => changeQuantity(item.id, -1)}>−</button><b>{item.quantity}</b><button onClick={() => changeQuantity(item.id, 1)}>+</button></div><button className="buy" onClick={() => checkout(item)}>Pay with Stripe</button></div>)}<div className="payment-method"><label>Stripe PaymentMethod ID (optional)<input value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)} placeholder="pm_card_visa" /></label><small>Test mode uses <code>pm_card_visa</code> when empty.</small></div><div className="cart-total"><span>Total</span><strong>{money.format(cartTotal)}</strong></div></> : <div className="empty cart-empty">Your order is empty.<br /><span>Select a product to get started.</span></div>}</aside></section>
          </>
        )}
      </main>
      <footer><span>Risk Radar Employee Portal</span><span>Secure checkout powered by Stripe</span></footer>
    </div>
  )
}

export default App
