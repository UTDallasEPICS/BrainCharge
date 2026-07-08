import { useState } from "react";
import "../styles/signin.css";

export default function SignIn({ navigate }) {
  const [form, setForm] = useState({ identifier: "", password: "" });
  const [loading, setLoading] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    await new Promise((res) => setTimeout(res, 600));
    setLoading(false);
    navigate("home");
  };

  return (
    <div className="sign-in">

      {/* ── Back arrow ── */}
      <button className="back-arrow" onClick={() => navigate("splash")} aria-label="Go back">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

      {/* ── Logo / brand mark ── */}
      <div className="signin-brand">
        <div className="signin-logo">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
          </svg>
        </div>
        <h1>Welcome back</h1>
        <p className="subtitle">Sign in to your account</p>
      </div>

      <form onSubmit={handleSubmit} noValidate>

        <div className="form-group">
          <label htmlFor="identifier">Username or Email</label>
          <input
            id="identifier"
            type="text"
            value={form.identifier}
            onChange={set("identifier")}
            placeholder="jane_doe or jane@example.com"
            autoComplete="username"
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">
            Password
            <button
              type="button"
              className="forgot-link"
              onClick={() => {/* future: navigate("forgot-password") */}}
            >
              Forgot password?
            </button>
          </label>
          <input
            id="password"
            type="password"
            value={form.password}
            onChange={set("password")}
            placeholder="Enter your password"
            autoComplete="current-password"
          />
        </div>

        {/* ── Sign in button pinned toward bottom ── */}
        <div className="signin-footer">
          <button type="submit" className="signin-btn" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </button>

          <p className="signup-prompt">
            Don't have an account?{" "}
            <button type="button" className="signup-link" onClick={() => navigate("make-account")}>
              Create one
            </button>
          </p>
        </div>

      </form>
    </div>
  );
}