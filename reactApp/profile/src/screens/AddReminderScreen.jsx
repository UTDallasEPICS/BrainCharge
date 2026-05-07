import { useState } from "react";
import "../styles/addreminder.css";

const DAYS = ["M", "T", "W", "Th", "F", "S", "Su"];

export default function AddReminderScreen({ navigate }) {
  const [name, setName] = useState("");
  const [time, setTime] = useState("08:00"); // Default to 8 AM
  const [selectedDays, setSelectedDays] = useState(["M", "T", "W", "Th", "F", "S", "Su"]);
  const [note, setNote] = useState("");

  const toggleDay = (day) => {
    setSelectedDays(prev => 
      prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]
    );
  };

  // Helper to format 24h time to 12h for the Home Screen
  const formatTime12h = (t24) => {
    const [h, m] = t24.split(":");
    let hours = parseInt(h, 10);
    const suffix = hours >= 12 ? "PM" : "AM";
    hours = hours % 12 || 12;
    return `${hours}:${m} ${suffix}`;
  };

  const handleSave = () => {
    if (!name.trim()) return;

    // 1. Load existing
    const existing = JSON.parse(localStorage.getItem("app_reminders") || "[]");

    // 2. Create new reminder (formatted for our home screen logic)
    const newRem = {
      id: Date.now(),
      name: name.trim(),
      time: formatTime12h(time),
      meta: selectedDays.length === 7 ? "Daily" : selectedDays.join(", "),
      note: note.trim(),
      type: "Reminder" // Identifies it as caregiver-care on the home screen
    };

    // 3. Save to localStorage
    const updated = [...existing, newRem];
    localStorage.setItem("app_reminders", JSON.stringify(updated));

    // 4. Navigate back to reminders list
    navigate("reminders");
  };

  return (
    <div className="add-rem-screen">
      <div className="arh">
        <button className="back-btn" onClick={() => navigate("reminders")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1a2a32" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <h1>Self-Care Goal</h1>
        <p>Set a reminder to prioritize your health.</p>
      </div>

      <div className="ar-body">
        {/* Name Input */}
        <div className="form-group">
          <label className="form-label">I want to...</label>
          <input 
            className="form-input" 
            placeholder="e.g., Meditate, drink water, take a walk" 
            value={name} 
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Frequency Bar (Day Picker) */}
        <div className="form-group">
          <label className="form-label">Repeat on</label>
          <div className="day-picker-bar">
            {DAYS.map((day) => (
              <button 
                key={day} 
                className={`day-chip ${selectedDays.includes(day) ? "active" : ""}`}
                onClick={() => toggleDay(day)}
              >
                {day}
              </button>
            ))}
          </div>
        </div>

        {/* Clock Picker */}
        <div className="form-group">
          <label className="form-label">What time?</label>
          <input 
            type="time" 
            className="form-input clock-input" 
            value={time} 
            onChange={(e) => setTime(e.target.value)}
          />
        </div>

        {/* Note Input */}
        <div className="form-group">
          <label className="form-label">Extra Note (Optional)</label>
          <input 
            className="form-input" 
            placeholder="e.g., You've got this!" 
            value={note} 
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        <button className="submit-btn" onClick={handleSave}>Set Reminder</button>
      </div>
    </div>
  );
}