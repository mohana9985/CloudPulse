import { useState } from 'react'
import ErrorMessage from '../components/ErrorMessage.jsx'
import { contactApi, getErrorMessage } from '../services/api.js'
import { isValidEmail, maxLength, minLength, validate } from '../utils/validation.js'

const EMPTY = { name: '', email: '', subject: '', message: '' }
const RULES = {
  name: [[minLength(2), 'Please enter your name (at least 2 characters).'], [maxLength(100), 'Name is too long.']],
  email: [[isValidEmail, 'Please enter a valid email address.']],
  subject: [[minLength(3), 'Subject must be at least 3 characters.'], [maxLength(150), 'Subject is too long.']],
  message: [[minLength(10), 'Message must be at least 10 characters.'], [maxLength(2000), 'Message is too long (max 2000).']],
}

export default function Contact() {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [status, setStatus] = useState({ sending: false, success: '', error: '' })

  const onChange = (e) => {
    const { name, value } = e.target
    setForm((f) => ({ ...f, [name]: value }))
    if (errors[name]) setErrors((errs) => ({ ...errs, [name]: undefined }))
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    const found = validate(form, RULES)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setStatus({ sending: true, success: '', error: '' })
    try {
      const result = await contactApi.submit({
        name: form.name.trim(),
        email: form.email.trim(),
        subject: form.subject.trim(),
        message: form.message.trim(),
      })
      setStatus({ sending: false, success: `${result.message} (Reference #${result.id})`, error: '' })
      setForm(EMPTY)
    } catch (err) {
      setStatus({ sending: false, success: '', error: getErrorMessage(err) })
    }
  }

  const inputClass = (name) => `input ${errors[name] ? 'input-error' : ''}`

  return (
    <div className="container-page py-10">
      <div className="grid gap-10 lg:grid-cols-3">
        <div>
          <h1 className="section-title">Contact us</h1>
          <p className="mt-3 text-slate-700">
            Questions about the demo store or the CloudPulse project? Send a message and it will be stored by the
            backend API.
          </p>
          <div className="card mt-6 p-5 text-sm text-slate-600">
            <p className="font-semibold text-navy-900">CloudPulse Project Team</p>
            <p className="mt-1">Cloud Computing course project</p>
            <p>BITS Pilani</p>
          </div>
        </div>

        <form onSubmit={onSubmit} noValidate className="card space-y-5 p-6 lg:col-span-2">
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label htmlFor="name" className="label">Name</label>
              <input id="name" name="name" value={form.name} onChange={onChange} className={inputClass('name')} autoComplete="name" maxLength={100} />
              {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
            </div>
            <div>
              <label htmlFor="email" className="label">Email</label>
              <input id="email" name="email" type="email" value={form.email} onChange={onChange} className={inputClass('email')} autoComplete="email" maxLength={254} />
              {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
            </div>
          </div>
          <div>
            <label htmlFor="subject" className="label">Subject</label>
            <input id="subject" name="subject" value={form.subject} onChange={onChange} className={inputClass('subject')} maxLength={150} />
            {errors.subject && <p className="mt-1 text-sm text-red-600">{errors.subject}</p>}
          </div>
          <div>
            <label htmlFor="message" className="label">Message</label>
            <textarea id="message" name="message" rows={6} value={form.message} onChange={onChange} className={inputClass('message')} maxLength={2000} />
            <div className="mt-1 flex justify-between text-sm">
              <span className="text-red-600">{errors.message}</span>
              <span className="text-slate-400">{form.message.length}/2000</span>
            </div>
          </div>

          {status.error && <ErrorMessage title="Message not sent" message={status.error} />}
          {status.success && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">
              {status.success}
            </div>
          )}

          <button type="submit" className="btn-primary w-full py-3 sm:w-auto sm:px-8" disabled={status.sending}>
            {status.sending ? 'Sending…' : 'Send message'}
          </button>
        </form>
      </div>
    </div>
  )
}
