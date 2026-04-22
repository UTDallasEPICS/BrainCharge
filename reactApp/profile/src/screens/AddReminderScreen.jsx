import { useState } from "react";
import "../styles/addreminder.css";

const FREQUENCIES = ["Daily", "Twice daily", "Weekly", "As needed"];

export default function AddReminderScreen({ navigate, onSave }) {
  const [form, setForm] = useState({ name: "", dosage: "", time: "", instructions: "" });
  const [freq, setFreq] = useState("Daily");
  const [notification, setNotification] = useState(true);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSave = () => {
    if (!form.name.trim()) return;
    if (onSave) {
      onSave({
        id: Date.now(),
        name: `${form.name}${form.dosage ? " – " + form.dosage : ""}`,
        meta: `${freq}${form.time ? " · " + form.time : ""}${form.instructions ? " · " + form.instructions : ""}`,
        tag: "ok",
        tagLabel: "Added",
      });
    }
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
        <h1>Add Reminder</h1>
        <p>Set up a new medication reminder</p>
      </div>
      <div className="ar-body">
        <div className="form-group">
          <label className="form-label">Medication name</label>
          <input className="form-input" name="name" type="text" placeholder="e.g., Metformin 500mg" value={form.name} onChange={handleChange}/>
        </div>
        <div className="form-group">
          <label className="form-label">Dosage</label>
          <input className="form-input" name="dosage" type="text" placeholder="e.g., 1 tablet" value={form.dosage} onChange={handleChange}/>
        </div>
        <div className="form-group">
          <label className="form-label">Frequency</label>
          <div className="freq-row">
            {FREQUENCIES.map((f) => (
              <button key={f} className={`freq-chip ${freq === f ? "sel" : ""}`} onClick={() => setFreq(f)}>{f}</button>
            ))}
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Time</label>
          <input className="form-input" name="time" type="text" placeholder="e.g., 8:00 AM" value={form.time} onChange={handleChange}/>
        </div>
        <div className="form-group">
          <label className="form-label">Instructions</label>
          <input className="form-input" name="instructions" type="text" placeholder="e.g., Take with food" value={form.instructions} onChange={handleChange}/>
        </div>
        <div className="toggle-row">
          <span className="toggle-label">Push notification</span>
          <button className={`toggle-switch ${notification ? "on" : "off"}`} onClick={() => setNotification(!notification)}>
            <span className="toggle-thumb"/>
          </button>
        </div>
        <button className="submit-btn" onClick={handleSave}>Save Reminder</button>
      </div>
    </div>
  );
}
