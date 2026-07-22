import { useState } from "react";
import { signIn, getSession } from "../lib/auth-client";
import "../styles/signin.css";

export default function SignIn({ navigate }) {
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const { error: signInError } = await signIn.email({
      email: form.email.trim(),
      password: form.password,
    });

    if (signInError) {
      setLoading(false);
      setError(signInError.message || "Sign in failed. Check your email and password.");
      return;
    }

    await getSession();
    setLoading(false);
    navigate("home");
  };

  return (
    <div className="sign-in">
      <button className="back-arrow" onClick={() => navigate("splash")} aria-label="Go back">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

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

      {error && <p className="error-banner">{error}</p>}

      <form onSubmit={handleSubmit} noValidate>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={form.email}
            onChange={set("email")}
            placeholder="jane@example.com"
            autoComplete="email"
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">
            Password
            <button
              type="button"
              className="forgot-link"
              onClick={() => {/* future: forgot password */}}
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
