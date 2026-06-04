import { useAuth } from '../context/AuthContext'

export function LoginScreen() {
  const { login, error } = useAuth()

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="brand-icon large">Q</div>
        <span className="eyebrow">QualityOps QA Console</span>
        <h1>Sign in to continue</h1>
        <p>
          Connect with UiPath to access agents, orchestrator jobs, execution history,
          and QA automation workflows.
        </p>

        {error && <div className="login-error">{error}</div>}

        <button className="primary-button login-button" onClick={login}>
          Sign in with UiPath
        </button>
      </section>
    </main>
  )
}