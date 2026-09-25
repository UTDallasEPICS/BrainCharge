import { useState, useEffect } from "react";
import "../styles/reminders.css";

// Helper for the icon (Medicine/Self-care icon)
function HeartIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#E91E63" strokeWidth="2">
      <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l8.78-8.78 1.06-1.06a5.5 5.5 0 000-7.78v0z" />
    </svg>
  );
}

export default function RemindersScreen({ navigate }) {
  const [reminders, setReminders] = useState([]);

  useEffect(() => {
    const saved = JSON.parse(localStorage.getItem("app_reminders") || "[]");
    setReminders(saved);
  }, []);

  const deleteReminder = (id) => {
    const updated = reminders.filter((r) => r.id !== id);
    setReminders(updated);
    localStorage.setItem("app_reminders", JSON.stringify(updated));
    // Dispatch event so Home Screen knows to update
    window.dispatchEvent(new Event("storage"));
  };

  return (
    <div className="reminders">
      {/* ── Header ── */}
      <div className="rem-header">
        <button className="back-btn-simple" onClick={() => navigate("home")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <h1>Self-Care Reminders</h1>
        <p><strong>Caretaker:</strong> Don't forget to take care of yourself today.</p>
      </div>

      {/* ── Body ── */}
      <div className="rem-body">
        <button className="add-rem-btn" onClick={() => navigate("add-reminder")}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Self-Care Task
        </button>

        <h2 className="section-title">My Well-being</h2>

        <div className="rem-list">
          {reminders.map((r) => (
            <div className="rem-card" key={r.id}>
              <div className="rem-icon">
                <HeartIcon />
              </div>
              <div className="rem-info">
                <p className="rem-title">{r.name}</p>
                <div className="rem-meta">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{marginRight: '4px'}}>
                    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                  </svg>
                  {r.time}
                </div>
              </div>
              
              {/* This is the red trash can button matching your Schedule screen */}
              <button 
                className="delete-reminder-btn" 
                onClick={() => deleteReminder(r.id)}
                title="Delete Reminder"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ff4d4d" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/>
                </svg>
              </button>
            </div>
          ))}

          {reminders.length === 0 && (
            <div className="empty-state-container">
              <p className="empty-state-text">
                No self-care reminders set. <br/>
                Remember, you can't pour from an empty cup!
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}