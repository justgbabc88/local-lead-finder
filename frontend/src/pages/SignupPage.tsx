import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { signIn, signUp } from '@/hooks/useAuth'

export function SignupPage() {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      await signUp(email, password)
      await signIn(email, password)
      toast.success('Account created!')
      nav('/', { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Signup failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <form onSubmit={onSubmit} className="card w-full max-w-sm space-y-4">
        <div>
          <div className="text-indigo-400 text-sm font-semibold">LocalLeadEngine</div>
          <h1 className="text-xl font-semibold mt-1">Create account</h1>
        </div>
        <div>
          <label className="label">Email</label>
          <input
            type="email"
            required
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Password</label>
          <input
            type="password"
            required
            minLength={8}
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting ? 'Creating...' : 'Sign up'}
        </button>
        <div className="text-xs text-slate-400 text-center">
          Have an account? <Link to="/login" className="text-indigo-400 hover:underline">Sign in</Link>
        </div>
      </form>
    </div>
  )
}
