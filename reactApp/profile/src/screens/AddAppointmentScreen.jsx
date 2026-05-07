import { useState } from "react";
import "../styles/addappointment.css";

export default function AddAppointmentScreen({ navigate }) {
  const [reminder, setReminder] = useState(true);
  const [form, setForm] = useState({ 
    title: "", 
    date: "", 
    time: "12:00", 
    notes: "" 
  });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  // Formats 24h time to 12h for consistency on Home Screen
  const formatTime12h = (t24) => {
    if (!t24) return "";
    const [h, m] = t24.split(":");
    let hours = parseInt(h, 10);
    const suffix = hours >= 12 ? "PM" : "AM";
    hours = hours % 12 || 12;
    return `${hours}:${m} ${suffix}`;
  };

  const handleSubmit = () => {
    if (!form.title.trim()) return;

    // 1. Get existing recipient schedule
    const existing = JSON.parse(localStorage.getItem("app_schedule") || "[]");

    // 2. Create new appointment object
    const newAppt = {
      id: Date.now(),
      title: form.title.trim(),
      date: form.date, // Native date picker format YYYY-MM-DD
      time: formatTime12h(form.time),
      note: form.notes.trim(),
      type: "Scheduled Item" // Key for Home Screen identification
    };

    // 3. Save to localStorage
    const updated = [...existing, newAppt];
    localStorage.setItem("app_schedule", JSON.stringify(updated));

    // 4. Update the storage event for the Home Screen
    window.dispatchEvent(new Event("storage"));
    
    // 5. Head back to the schedule view
    navigate("schedule");
  };

  return (
    <div className="add-screen">
      {/* ── Header ── */}
      <div className="add-header">
        <button className="back-btn" onClick={() => navigate("schedule")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h1>Recipient Appointment</h1>
        <p>Schedule medical visits or events for the care recipient.</p>
      </div>

      <div className="add-body">
        {/* Title Input */}
        <div className="form-group">
          <label className="form-label">Appointment Title</label>
          <input
            className="form-input"
            type="text"
            name="title"
            placeholder="e.g., General Physician Visit"
            value={form.title}
            onChange={handleChange}
          />
        </div>

        {/* Native Date Picker */}
        <div className="form-group">
          <label className="form-label">Date</label>
          <input
            className="form-input native-picker"
            type="date"
            name="date"
            value={form.date}
            onChange={handleChange}
          />
        </div>

        {/* Native Time Picker */}
        <div className="form-group">
          <label className="form-label">Time</label>
          <input
            className="form-input native-picker"
            type="time"
            name="time"
            value={form.time}
            onChange={handleChange}
          />
        </div>

        {/* Notes */}
        <div className="form-group">
          <label className="form-label">Notes</label>
          <textarea
            className="form-textarea"
            name="notes"
            placeholder="Add specific instructions, e.g., fasting required..."
            value={form.notes}
            onChange={handleChange}
          />
        </div>

        {/* Reminder Toggle */}
        <div className="toggle-row">
          <span className="toggle-label">Alert me before this event</span>
          <button
            className={`toggle-switch ${reminder ? "on" : "off"}`}
            onClick={() => setReminder(!reminder)}
          >
            <span className="toggle-thumb" />
          </button>
        </div>

        <button className="submit-btn" onClick={handleSubmit}>
          Save Appointment
        </button>
      </div>
    </div>
  );
}