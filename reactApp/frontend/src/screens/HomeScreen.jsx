import "../styles/home.css";
import { useEffect, useState } from "react";
import { listEvents } from "../api/calendar";

function timeToMinutes(item) {
  const raw = item.time || "";
  const s = raw.trim().toUpperCase();
  const ampm = s.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/);
  if (ampm) {
    let h = parseInt(ampm[1], 10);
    const m = parseInt(ampm[2], 10);
    if (ampm[3] === "PM" && h !== 12) h += 12;
    if (ampm[3] === "AM" && h === 12) h = 0;
    return h * 60 + m;
  }
  return Infinity;
}

export default function HomeScreen({ navigate, user, onLogout }) {
  const [allEvents, setAllEvents] = useState([]);
  const [calendarError, setCalendarError] = useState("");

  useEffect(() => {
    const loadData = async () => {
      const rems = JSON.parse(localStorage.getItem("app_reminders") || "[]").map((r) => ({
        ...r,
        type: "Reminder for you",
      }));

      let sched = [];
      try {
        sched = (await listEvents({ maxResults: 50 })).map((s) => ({
          ...s,
          type: "Care giving scheduling",
        }));
        setCalendarError("");
      } catch (err) {
        setCalendarError(err.message);
      }

      const combined = [...rems, ...sched].sort((a, b) => timeToMinutes(a) - timeToMinutes(b));
      setAllEvents(combined);
    };

    loadData();
    window.addEventListener("calendar-updated", loadData);
    window.addEventListener("storage", loadData);

    return () => {
      window.removeEventListener("calendar-updated", loadData);
      window.removeEventListener("storage", loadData);
    };
  }, []);

  const top3 = allEvents.slice(0, 3);
  const hasAny = allEvents.length > 0;

  return (
    <div className="home">
      <div className="home-header">
        <div className="header-top">
          <button className="logout-btn" onClick={onLogout}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Log Out
            </button>
          <div>
            <p className="connected-to">Hello</p>
            <h1>{user?.name || "User's Companion"}</h1>
          </div>
          <button className="icon-btn" onClick={() => navigate("settings")}>
             {/* Settings SVG */}
          </button>
        </div>
      </div>

      <div className="home-body">
        {calendarError && (
          <p className="calendar-warning">Calendar sync unavailable: {calendarError}</p>
        )}

        <div className="companion-card">
          <div>
            <p className="companion-cta-label">Self-Care Check-in</p>
            <p className="companion-cta-title">Talk to your companion</p>
          </div>
  
        </div>

        <div className="reminders-row-header">
          <h2 className="section-title">Upcoming Today</h2>
        </div>

        {!hasAny ? (
          <div className="empty-state-card">
            <p>No reminders or anything to schedule, add some in the reminder or schedule page.</p>
          </div>
        ) : (
          top3.map((item) => (
            <div className="overview-card" key={`${item.type}-${item.id}`}>
              <div className={`card-icon ${item.type === "Reminder" ? "green" : "blue"}`}>
                {/* Icon logic */}
              </div>
              <div className="card-text">
                <div className="type-badge">{item.type}</div>
                <p className="card-title">{item.name || item.title}</p>
                <p className="card-sub">{item.time} {item.date ? `· ${item.date}` : ""}</p>
                {item.note && <p className="card-alert">{item.note}</p>}
              </div>
            </div>
          ))
        )}

        <button className="reminders-action-bar" onClick={() => navigate("reminders")}>
          <span className="rab-label">Manage Self-Care Reminders</span>
        </button>
        <button className="reminders-action-bar" style={{marginTop: '10px'}} onClick={() => navigate("schedule")}>
          <span className="rab-label">Manage Care Recipient Schedule</span>
        </button>
      </div>
    </div>
  );
}
