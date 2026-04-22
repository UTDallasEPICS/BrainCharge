import { useState } from "react";
import "../styles/reminders.css";

const PillIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2596BE" strokeWidth="2">
    <path d="M18 8h1a4 4 0 010 8h-1"/>
    <path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/>
    <line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/>
  </svg>
);

const defaultReminders = [
  { id: 1, name: "Workout", meta: "Daily · 6:00 PM", tag: "soon", tagLabel: "Due soon" },
  { id: 2, name: "Practice Mindfulness", meta: "Daily · 8:00 PM", tag: "ok", tagLabel: "Tonight" },
  { id: 3, name: "Walk", meta: "Daily · 9:00 AM · Morning", tag: "ok", tagLabel: "Tomorrow" },
  { id: 4, name: "Meditate", meta: "Daily · 7:00 AM · Before breakfast", tag: "ok", tagLabel: "Tomorrow" },
];

export default function RemindersScreen({ navigate }) {
  const [reminders, setReminders] = useState(defaultReminders);

  const deleteReminder = (id) => {
    setReminders((prev) => prev.filter((r) => r.id !== id));
  };

  return (
    <div className="reminders">
      <div className="rem-header">
        <h1>Reminders</h1>
        <p>Your medication schedule</p>
      </div>
      <div className="rem-body">
        <button className="add-rem-btn" onClick={() => navigate("add-reminder")}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Add Reminder
        </button>
        <h2 className="section-title">Active Reminders</h2>
        {reminders.map((r) => (
          <div className="rem-card" key={r.id}>
            <div className="rem-icon"><PillIcon /></div>
            <div className="rem-info">
              <p className="rem-title">{r.name}</p>
              <p className="rem-meta">{r.meta}</p>
            </div>
            <span className={`rem-tag ${r.tag}`}>{r.tagLabel}</span>
            <button className="del-btn" onClick={() => deleteReminder(r.id)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7a9aaa" strokeWidth="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        ))}
        {reminders.length === 0 && (
          <p className="empty-state">No reminders yet. Tap Add Reminder to get started.</p>
        )}
      </div>
    </div>
  );
}
