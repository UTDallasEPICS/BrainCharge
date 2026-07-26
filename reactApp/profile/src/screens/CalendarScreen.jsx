import { useState, useEffect, useCallback } from "react";
import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import { format, startOfWeek, getDay, addMonths, subMonths } from "date-fns";
import enUS from "date-fns/locale/en-US";
import { listEvents, deleteEvent } from "../api/calendar";
import { appEventToCalendarEvent, slotToFormDefaults } from "../utils/calendarEvents";
import "react-big-calendar/lib/css/react-big-calendar.css";
import "../styles/calendar.css";

const locales = { "en-US": enUS };

const localizer = dateFnsLocalizer({
  format,
  startOfWeek,
  getDay,
  locales,
});

function isValidCalendarEvent(event) {
  return (
    event?.start instanceof Date &&
    !Number.isNaN(event.start.getTime()) &&
    event?.end instanceof Date &&
    !Number.isNaN(event.end.getTime())
  );
}

export default function CalendarScreen({
  navigate,
  onEditAppointment,
  onAddAppointment,
}) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [currentView, setCurrentView] = useState("month");
  const [range, setRange] = useState({
    start: subMonths(new Date(), 1),
    end: addMonths(new Date(), 2),
  });
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listEvents({
        timeMin: range.start.toISOString(),
        timeMax: range.end.toISOString(),
        maxResults: 250,
      });
      setEvents(
        data
          .map(appEventToCalendarEvent)
          .filter(isValidCalendarEvent),
      );
    } catch (err) {
      setError(err.message);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [range.start, range.end]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    const handleUpdate = () => loadEvents();
    window.addEventListener("calendar-updated", handleUpdate);
    return () => window.removeEventListener("calendar-updated", handleUpdate);
  }, [loadEvents]);

  const handleRangeChange = useCallback((newRange) => {
    if (Array.isArray(newRange)) {
      setRange({ start: newRange[0], end: newRange[newRange.length - 1] });
    } else if (newRange?.start && newRange?.end) {
      setRange({ start: newRange.start, end: newRange.end });
    }
  }, []);

  const handleSelectSlot = useCallback(
    ({ start }) => {
      setSelectedEvent(null);
      onAddAppointment(slotToFormDefaults(start));
    },
    [onAddAppointment],
  );

  const handleSelectEvent = useCallback((event) => {
    setSelectedEvent(event);
  }, []);

  const handleEditSelected = () => {
    if (!selectedEvent?.resource) return;
    setSelectedEvent(null);
    onEditAppointment(selectedEvent.resource);
  };

  const handleDeleteSelected = async () => {
    if (!selectedEvent?.id) return;
    setDeletingId(selectedEvent.id);
    setError("");
    try {
      await deleteEvent(selectedEvent.id);
      setSelectedEvent(null);
      window.dispatchEvent(new Event("calendar-updated"));
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="calendar-screen">
      <div className="calendar-header">
        <button className="back-btn-simple" onClick={() => navigate("home")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h1>Calendar</h1>
        <p>
          View and manage care events on a calendar grid.
          Synced with Google Calendar.
        </p>
      </div>

      <div className="calendar-body">
        <button
          className="add-appt-btn"
          onClick={() => onAddAppointment(null)}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Appointment
        </button>

        {error && (
          <div className="calendar-error">
            <p>{error}</p>
            <button type="button" className="retry-btn" onClick={loadEvents}>
              Retry
            </button>
          </div>
        )}

        <div className={`calendar-widget ${loading ? "loading" : ""}`}>
          <Calendar
            localizer={localizer}
            culture="en-US"
            events={events}
            startAccessor="start"
            endAccessor="end"
            allDayAccessor="allDay"
            date={currentDate}
            view={currentView}
            views={["month", "agenda"]}
            onNavigate={setCurrentDate}
            onView={setCurrentView}
            onRangeChange={handleRangeChange}
            onSelectSlot={handleSelectSlot}
            onSelectEvent={handleSelectEvent}
            selectable
            toolbar
            style={{ height: currentView === "agenda" ? 400 : 340 }}
          />
          {loading && <div className="calendar-loading-overlay">Loading events...</div>}
        </div>

        <p className="calendar-hint">Tap a day to add an event. Tap an event to view, edit, or remove it.</p>
      </div>

      {selectedEvent && (
        <div className="calendar-event-modal-backdrop" onClick={() => setSelectedEvent(null)}>
          <div className="calendar-event-modal" onClick={(e) => e.stopPropagation()}>
            <h3>{selectedEvent.title}</h3>
            <p className="event-modal-time">
              {selectedEvent.allDay
                ? format(selectedEvent.start, "MMM d, yyyy")
                : `${format(selectedEvent.start, "MMM d, yyyy · h:mm a")} – ${format(selectedEvent.end, "h:mm a")}`}
            </p>
            {selectedEvent.resource?.note && (
              <p className="event-modal-note">{selectedEvent.resource.note}</p>
            )}
            <div className="event-modal-actions">
              <button type="button" className="modal-btn edit" onClick={handleEditSelected}>
                Edit
              </button>
              <button
                type="button"
                className="modal-btn delete"
                onClick={handleDeleteSelected}
                disabled={deletingId === selectedEvent.id}
              >
                {deletingId === selectedEvent.id ? "Removing..." : "Remove"}
              </button>
              <button type="button" className="modal-btn cancel" onClick={() => setSelectedEvent(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
