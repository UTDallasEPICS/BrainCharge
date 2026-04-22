import { useState } from "react";
import "../styles/addappointment.css";

export default function AddAppointmentScreen({ navigate }) {
  const [reminder, setReminder] = useState(true);
  const [form, setForm] = useState({ title: "", date: "", time: "", notes: "" });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = () => {
    navigate("schedule");
  };

  return (
    <div className="add-screen">
      <div className="add-header">
        <button className="back-btn" onClick={() => navigate("schedule")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-primary)" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h1>Add Appointment</h1>
        <p>Create a new appointment or reminder</p>
      </div>

      <div className="add-body">
        <div className="form-group">
          <label className="form-label">Title</label>
          <input
            className="form-input"
            type="text"
            name="title"
            placeholder="e.g., Doctor's appointment"
            value={form.title}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Date</label>
          <input
            className="form-input"
            type="text"
            name="date"
            placeholder="mm/dd/yyyy"
            value={form.date}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Time</label>
          <input
            className="form-input"
            type="text"
            name="time"
            placeholder="--:-- --"
            value={form.time}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Notes</label>
          <textarea
            className="form-textarea"
            name="notes"
            placeholder="Add any additional details..."
            value={form.notes}
            onChange={handleChange}
          />
        </div>

        <div className="toggle-row">
          <span className="toggle-label">Send reminder</span>
          <button
            className={`toggle-switch ${reminder ? "on" : "off"}`}
            onClick={() => setReminder(!reminder)}
            aria-label="Toggle reminder"
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
