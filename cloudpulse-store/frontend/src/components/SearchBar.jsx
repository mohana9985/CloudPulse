import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function SearchBar({ initialValue = '', placeholder = 'Search products…', size = 'md', onSearch }) {
  const [value, setValue] = useState(initialValue)
  const navigate = useNavigate()

  useEffect(() => {
    setValue(initialValue)
  }, [initialValue])

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = value.trim()
    if (onSearch) onSearch(q)
    else navigate(q ? `/products?q=${encodeURIComponent(q)}` : '/products')
  }

  const large = size === 'lg'
  return (
    <form onSubmit={handleSubmit} role="search" className="flex w-full gap-2">
      <label htmlFor="product-search" className="sr-only">Search products</label>
      <input
        id="product-search"
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        maxLength={100}
        className={`input ${large ? 'py-3 text-base' : ''}`}
      />
      <button type="submit" className={`btn-primary shrink-0 ${large ? 'px-6' : ''}`}>
        Search
      </button>
    </form>
  )
}
