import "../styles/home.css";

export default function HomeScreen({ navigate }) {
  return (
    <div className="home">
      <div className="home-header">
        <div className="header-top">
          <div>
            <p className="connected-to">Connected to</p>
            <h1>User's Companion</h1>
          </div>
          <button className="icon-btn">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="1.8">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </button>
        </div>
        <div className="status-row">
          <span className="status-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
              <path d="M5 12.55a11 11 0 0114.08 0M1.42 9a16 16 0 0121.16 0M8.53 16.11a6 6 0 016.95 0M12 20h.01" />
            </svg>
            Connected
          </span>
          <span className="status-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
              <rect x="2" y="7" width="18" height="10" rx="2" /><path d="M22 11v2" />
            </svg>
            87%
          </span>
        </div>
      </div>
      <div className="home-body">
        <div className="companion-card">
          <div>
            <p className="companion-cta-label">How are you feeling?</p>
            <p className="companion-cta-title">Talk to your companion</p>
          </div>
          <button className="chat-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
            </svg>
          </button>
        </div>
        <h2 className="section-title">Quick Overview</h2>
        <div className="overview-card">
          <div className="card-icon blue">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2596BE" strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          </div>
          <div className="card-text">
            <p className="card-title">Next Appointment</p>
            <p className="card-sub">Dr. Patel – Neurology</p>
            <p className="card-alert">Tomorrow at 10:00 AM</p>
          </div>
        </div>
        <div className="overview-card">
          <div className="card-icon green">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1d9e75" strokeWidth="2">
              <path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/>
            </svg>
          </div>
          <div className="card-text">
            <p className="card-title">Medication Reminder</p>
            <p className="card-sub">Metformin 500mg – with breakfast</p>
            <p className="card-alert">Due in 45 minutes</p>
          </div>
        </div>
        <div className="overview-card">
          <div className="card-icon blue">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2596BE" strokeWidth="2">
              <path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/>
            </svg>
          </div>
          <div className="card-text">
            <p className="card-title">Atorvastatin 20mg</p>
            <p className="card-sub">Evening dose – 8:00 PM</p>
            <p className="card-alert">Scheduled for tonight</p>
          </div>
        </div>
        <div className="overview-card">
          <div className="card-icon amber">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ba7517" strokeWidth="2">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div className="card-text">
            <p className="card-title">Daily Tip</p>
            <p className="card-tip">Take Metformin with food to reduce stomach upset. Consistent timing each day improves effectiveness.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
