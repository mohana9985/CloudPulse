// Client-side checks only; the backend validates every request again.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export const isValidEmail = (value) => EMAIL_RE.test(String(value).trim())

// rules: { field: [ [predicate, message], ... ] }  -> returns { field: message }
export function validate(values, rules) {
  const errors = {}
  for (const [field, checks] of Object.entries(rules)) {
    for (const [isOk, message] of checks) {
      if (!isOk(values[field] ?? '')) {
        errors[field] = message
        break
      }
    }
  }
  return errors
}

export const minLength = (n) => (v) => String(v).trim().length >= n
export const maxLength = (n) => (v) => String(v).trim().length <= n
