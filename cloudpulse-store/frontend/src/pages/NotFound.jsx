import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="container-page py-20 text-center">
      <p className="text-sm font-semibold uppercase tracking-widest text-navy-500">Error 404</p>
      <h1 className="mt-2 text-3xl font-bold text-navy-900">Page not found</h1>
      <p className="mt-3 text-slate-600">The page you are looking for does not exist or has been moved.</p>
      <div className="mt-8 flex justify-center gap-3">
        <Link to="/" className="btn-primary">Go to home page</Link>
        <Link to="/products" className="btn-secondary">Browse products</Link>
      </div>
    </div>
  )
}
