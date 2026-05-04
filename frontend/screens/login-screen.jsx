// Login screen — entry point before main app
(function () {
  const { useState } = React;

  function LoginWaves() {
    return (
      <svg className="login-waves" viewBox="0 0 1200 800" preserveAspectRatio="none">
        <path className="wave-1"
          d="M0 400 Q 150 320 300 400 T 600 400 T 900 400 T 1200 400" />
        <path className="wave-2"
          d="M0 430 Q 200 510 400 430 T 800 430 T 1200 430" />
        <path className="wave-3"
          d="M0 380 Q 100 300 200 380 T 400 380 T 600 380 T 800 380 T 1000 380 T 1200 380" />
      </svg>
    );
  }

  function LoginScreen({ onLogin, lang, onLang }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [role, setRole] = useState("clinician");
    const [variant, setVariant] = useState("A");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const t = window.I18N[lang].auth;
    const top = window.I18N[lang];

    function submit(e) {
      e.preventDefault();
      if (!email.trim() || !password.trim()) {
        setError(t.errorRequired);
        return;
      }
      if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
        setError(t.errorEmail);
        return;
      }
      setError("");
      setLoading(true);
      setTimeout(() => {
        onLogin({ email: email.trim(), role, variant });
      }, 650);
    }

    function demoLogin() {
      onLogin({
        email: "demo@neuratriage.dev",
        role: "researcher",
        variant,
      });
    }

    return (
      <div className="login-page">
        <div className="login-bg-grid" />
        <LoginWaves />
        <div className="login-card">
          <div className="login-brand">
            <div className="login-logo" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 36 36" fill="none">
                <path
                  d="M2 18 L7 18 L10 8 L13 28 L16 12 L19 24 L22 14 L25 22 L28 18 L34 18"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div className="login-title">
              <h1>{top.appName}</h1>
              <p>{top.tagline}</p>
            </div>
          </div>

          <form onSubmit={submit} noValidate>
            <label className="login-field">
              <span>{t.email}</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="dr.le@hospital.vn"
                autoComplete="email"
                spellCheck="false"
              />
            </label>

            <label className="login-field">
              <span>{t.password}</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </label>

            <div className="login-row">
              <label className="login-field">
                <span>{t.role}</span>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="clinician">{t.roles.clinician}</option>
                  <option value="researcher">{t.roles.researcher}</option>
                  <option value="admin">{t.roles.admin}</option>
                </select>
              </label>
              <label className="login-field">
                <span>{t.layout}</span>
                <select value={variant} onChange={(e) => setVariant(e.target.value)}>
                  <option value="A">{t.layouts.A}</option>
                  <option value="B">{t.layouts.B}</option>
                  <option value="C">{t.layouts.C}</option>
                </select>
              </label>
            </div>

            {error && <div className="login-error">{error}</div>}

            <button type="submit" className="login-submit" disabled={loading}>
              {loading ? t.signingIn : t.signIn}
            </button>
            <button type="button" className="login-demo" onClick={demoLogin}>
              {t.demo}
            </button>
          </form>

          <div className="login-footer">
            <button
              type="button"
              className="lang-toggle"
              onClick={() => onLang(lang === "vi" ? "en" : "vi")}
              aria-label="Toggle language"
            >
              {lang === "vi" ? "EN" : "VI"}
            </button>
            <span className="version">v0.1.0 · research preview</span>
          </div>
        </div>
      </div>
    );
  }

  window.LoginScreen = LoginScreen;
})();
