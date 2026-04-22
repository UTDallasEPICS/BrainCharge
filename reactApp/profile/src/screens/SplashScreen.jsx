import "../styles/splash.css";

export default function SplashScreen({ navigate }) {
  return (
    <div className="splash">
      <div className="splash-icon">
        <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M20 33s-13-8.5-13-16.5a8 8 0 0116 0 8 8 0 0116 0C39 24.5 20 33 20 33z"
            fill="#fff"
          />
        </svg>
      </div>
      <h1 className="splash-title">BrainCharge</h1>
      <p className="splash-subtitle">Support when you need it most</p>
      <div className="splash-actions">
        <button className="btn-primary" onClick={() => navigate("home")}>
          Sign In
        </button>
        <button className="btn-outline" onClick={() => navigate("make-account")}>
          Get Started
        </button>
      </div>
    </div>
  );
}
