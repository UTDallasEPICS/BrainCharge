import { useState } from "react";
import { signUp, getSession } from "../lib/auth-client";
import "../styles/makeaccount.css";

const PersonIcon = () => (
  <svg viewBox="0 0 24 24">
    <circle cx="12" cy="8" r="4" />
    <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
  </svg>
);

export default function MakeAccount({ navigate }) {
  const [form, setForm] = useState({
    firstName: "", lastName: "",
    username: "", email: "",
    dob: "", password: "",
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const validate = () => {
    const e = {};
    if (!form.firstName.trim())           e.firstName = "Required.";
    if (!form.lastName.trim())            e.lastName  = "Required.";
    if (form.username.trim().length < 3)  e.username  = "Min. 3 characters.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = "Enter a valid email.";
    if (!form.dob)                        e.dob       = "Required.";
    if (form.password.length < 8)         e.password  = "Min. 8 characters.";
    return e;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    setLoading(true);
    setErrors({});

    const { error } = await signUp.email({
      email: form.email.trim(),
      password: form.password,
      name: `${form.firstName.trim()} ${form.lastName.trim()}`,
    });

    if (error) {
      setLoading(false);
      setErrors({ general: error.message || "Could not create account. Try a different email." });
      return;
    }

    await getSession();
    setLoading(false);
    navigate("home");
  };

  return (
    <div className="make-account">
      <button className="back-arrow" onClick={() => navigate("splash")} aria-label="Go back">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

      <h1>Create Account</h1>
      <p className="subtitle">Enter information for your account</p>

      {errors.general && <p className="error-banner">{errors.general}</p>}

      <form onSubmit={handleSubmit} noValidate>
        <div className="row-2">
          <div className="form-group">
            <label htmlFor="firstName">First Name</label>
            <input
              id="firstName" type="text"
              value={form.firstName} onChange={set("firstName")}
              placeholder="Jane"
              className={errors.firstName ? "input-error" : ""}
            />
            {errors.firstName && <span className="field-error">{errors.firstName}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="lastName">Last Name</label>
            <input
              id="lastName" type="text"
              value={form.lastName} onChange={set("lastName")}
              placeholder="Doe"
              className={errors.lastName ? "input-error" : ""}
            />
            {errors.lastName && <span className="field-error">{errors.lastName}</span>}
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="username">Username</label>
          <input
            id="username" type="text"
            value={form.username} onChange={set("username")}
            placeholder="jane_doe"
            autoComplete="username"
            className={errors.username ? "input-error" : ""}
          />
          {errors.username && <span className="field-error">{errors.username}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            id="email" type="email"
            value={form.email} onChange={set("email")}
            placeholder="jane@example.com"
            autoComplete="email"
            className={errors.email ? "input-error" : ""}
          />
          {errors.email && <span className="field-error">{errors.email}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="dob">Date of Birth</label>
          <input
            id="dob" type="date"
            value={form.dob} onChange={set("dob")}
            autoComplete="bday"
            className={errors.dob ? "input-error" : ""}
          />
          {errors.dob && <span className="field-error">{errors.dob}</span>}
        </div>

        <div className="divider" />

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password" type="password"
            value={form.password} onChange={set("password")}
            placeholder="Min. 8 characters"
            autoComplete="new-password"
            className={errors.password ? "input-error" : ""}
          />
          {errors.password && <span className="field-error">{errors.password}</span>}
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Creating account…" : "Create Account"}
        </button>
      </form>
    </div>
  );
}
