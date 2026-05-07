import { useState, useEffect } from "react";
import "../styles/schedule.css";

// Helper for the icon
function CalendarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2596BE" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

export default function ScheduleScreen({ navigate }) {
  const [appointments, setAppointments] = useState([]);

  useEffect(() => {
    // Specifically loading from the recipient-specific schedule key
    const saved = JSON.parse(localStorage.getItem("app_schedule") || "[]");
    setAppointments(saved);
  }, []);

  const deleteAppt = (id) => {
    const updated = appointments.filter((a) => a.id !== id);
    setAppointments(updated);
    localStorage.setItem("app_schedule", JSON.stringify(updated));
    // Dispatch event so Home Screen knows to update if open in another tab
    window.dispatchEvent(new Event("storage"));
  };

  return (
    <div className="schedule">
      {/* ── Header ── */}
      <div className="sched-header">
        <button className="back-btn-simple" onClick={() => navigate("home")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <h1>Recipient Schedule</h1>
        <p>
          Manage appointments and tasks for the 
          <strong> person you are caring for</strong>.
        </p>
      </div>

      {/* ── Body ── */}
      <div className="sched-body">
        <button className="add-appt-btn" onClick={() => navigate("add-appointment")}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Recipient Appointment
        </button>

        <h2 className="section-title">Medical & Daily Care</h2>
        
        <div className="appt-list">
          {appointments.map((appt) => (
            <div className="appt-card" key={appt.id}>
              <div className="appt-icon">
                <CalendarIcon />
              </div>
              <div className="appt-info">
                <p className="appt-title">{appt.title}</p>
                <div className="appt-meta">
                  <span className="meta-date">{appt.date || "Today"}</span>
                  <span className="meta-divider">·</span>
                  <span className="meta-time">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{marginRight: '4px'}}>
                      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                    </svg>
                    {appt.time}
                  </span>
                </div>
                {appt.note && <p className="appt-note">{appt.note}</p>}
              </div>
              <button 
                className="delete-reminder-btn" 
                onClick={() => deleteAppt(appt.id)}
                title="Remove Appointment"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ff4d4d" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/>
                </svg>
              </button>
            </div>
          ))}

          {appointments.length === 0 && (
            <div className="empty-state-container">
              <p className="empty-state-text">
                No appointments scheduled for the patient. 
                Keep track of their doctor visits and routines here.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}