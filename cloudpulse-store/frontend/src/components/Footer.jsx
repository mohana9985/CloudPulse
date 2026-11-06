import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-navy-900 bg-navy-950 text-navy-100">
      <div className="container-page grid gap-8 py-10 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <p className="text-lg font-bold text-white">CloudPulse Store</p>
          <p className="mt-2 max-w-md text-sm text-navy-200">
            A demonstration e-commerce website built to generate realistic traffic for the CloudPulse
            cloud resource monitoring project. No real products are sold and no payments are taken.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-white">Shop</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link className="hover:text-white" to="/products">All products</Link></li>
            <li><Link className="hover:text-white" to="/cart">Cart</Link></li>
            <li><Link className="hover:text-white" to="/checkout">Checkout</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-white">Project</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link className="hover:text-white" to="/about">About</Link></li>
            <li><Link className="hover:text-white" to="/contact">Contact</Link></li>
            <li><a className="hover:text-white" href="/api/docs">API documentation</a></li>
            <li><a className="hover:text-white" href="/api/health">Health check</a></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-navy-900">
        <p className="container-page py-4 text-xs text-navy-300">
          © {new Date().getFullYear()} CloudPulse Store · Cloud Computing university project · Demonstration only
        </p>
      </div>
    </footer>
  )
}
