import { Link } from 'react-router-dom'

const facts = [
  ['Frontend', 'React, Vite, Tailwind CSS and React Router, served by Nginx.'],
  ['Backend', 'Python 3.11 FastAPI service with SQLAlchemy and a SQLite database.'],
  ['Monitoring', 'Prometheus metrics at /api/metrics plus health and readiness checks.'],
  ['Deployment', 'Docker Compose locally on macOS and on an AWS EC2 Ubuntu instance.'],
]

export default function About() {
  return (
    <div className="container-page py-10">
      <div className="max-w-3xl">
        <h1 className="section-title">About CloudPulse Store</h1>
        <p className="mt-4 text-lg leading-relaxed text-slate-700">
          CloudPulse Store is a <strong>demonstration</strong> e-commerce website. It looks and behaves like a
          small online shop — you can browse products, search, fill a cart and place orders — but no real
          products are sold, no payments are taken and all customer data is fictional.
        </p>

        <h2 className="mt-10 text-xl font-bold">Project purpose</h2>
        <p className="mt-3 leading-relaxed text-slate-700">
          The store is the first component of the university Cloud Computing project
          <em> CloudPulse: Intelligent Cloud Resource Monitoring and Workload Scheduling System</em>. Its job is to
          generate realistic web and API traffic that the separate CloudPulse Monitoring Dashboard observes:
          availability, response times, API performance, traffic volume, errors and server resource usage.
          Load tests written with Locust simulate browsing, searching and ordering to create measurable workloads.
        </p>
      </div>

      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {facts.map(([title, text]) => (
          <div key={title} className="card p-5">
            <h3 className="font-semibold text-navy-900">{title}</h3>
            <p className="mt-2 text-sm text-slate-600">{text}</p>
          </div>
        ))}
      </div>

      <div className="mt-10 flex flex-wrap gap-3">
        <Link to="/products" className="btn-primary">Browse the store</Link>
        <a href="/api/docs" className="btn-secondary">View API documentation</a>
      </div>
    </div>
  )
}
