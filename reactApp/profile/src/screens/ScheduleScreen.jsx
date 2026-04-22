import "../styles/schedule.css";

const appointments = [
  {
    id: 1,
    title: "Dr. Smith – Cardiology",
    date: "Tomorrow",
    time: "2:30 PM",
    note: "Annual checkup",
  },
  {
    id: 2,
    title: "Physical Therapy",
    date: "Apr 10",
    time: "10:00 AM",
    note: "Session 3 of 8",
  },
  {
    id: 3,
    title: "Lab Work",
    date: "Apr 14",
    time: "7:00 AM",
    note: "Fasting required",
  },
];

function CalendarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--green-icon)" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

export default function ScheduleScreen({ navigate }) {
  return (
    <div className="schedule">
      <div className="sched-header">
        <h1>Schedule</h1>
        <p>Manage your appointments and reminders</p>
      </div>
      <div className="sched-body">
        <button className="add-appt-btn" onClick={() => navigate("add-appointment")}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Appointment
        </button>


        <h2 className="section-title">Upcoming</h2>

        {appointments.map((appt) => (
          <div className="appt-card" key={appt.id}>
            <div className="appt-icon">
              <CalendarIcon />
            </div>
            <div className="appt-info">
              <p className="appt-title">{appt.title}</p>
              <div className="appt-meta">
                <span>{appt.date}</span>
                <span className="appt-time">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  {appt.time}
                </span>
              </div>
              <p className="appt-note">{appt.note}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
