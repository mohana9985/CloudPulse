export default function ErrorMessage({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800" role="alert">
      <p className="font-semibold">{title}</p>
      {message && <p className="mt-1 text-sm">{message}</p>}
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn mt-3 border border-red-300 bg-white px-3 py-1.5 text-red-700 hover:bg-red-100">
          Try again
        </button>
      )}
    </div>
  )
}
