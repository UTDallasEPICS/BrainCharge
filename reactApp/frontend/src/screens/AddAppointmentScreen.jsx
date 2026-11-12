import { useLanguage } from "../i18n/language.js";
import { useState, useEffect } from "react";
import { createEvent, updateEvent, time12hTo24h } from "../api/calendar";
import "../styles/addappointment.css";

export default function AddAppointmentScreen({
  navigate,
  editingAppointment,
  prefillDefaults,
  returnScreen = "schedule",
  onClearEdit,
}) {
  const { t } = useLanguage();
  const [reminder, setReminder] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    date: "",
    time: "12:00",
    notes: "",
  });

  const isEditing = Boolean(editingAppointment?.id);

  useEffect(() => {
    if (editingAppointment) {
      setForm({
        title: editingAppointment.title || "",
        date: editingAppointment.date || "",
        time: time12hTo24h(editingAppointment.time) || "12:00",
        notes: editingAppointment.note || "",
      });
      return;
    }

    if (prefillDefaults) {
      setForm({
        title: prefillDefaults.title || "",
        date: prefillDefaults.date || "",
        time: prefillDefaults.time || "12:00",
        notes: prefillDefaults.notes || "",
      });
    }
  }, [editingAppointment, prefillDefaults]);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const goBack = () => {
    onClearEdit?.();
    navigate(returnScreen);
  };

  const handleSubmit = async () => {
    if (!form.title.trim()) return;

    setSaving(true);
    setError("");

    const payload = {
      title: form.title.trim(),
      date: form.date,
      time: form.time,
      note: form.notes.trim(),
    };

    try {
      if (isEditing) {
        await updateEvent(editingAppointment.id, payload);
      } else {
        await createEvent(payload);
      }

      window.dispatchEvent(new Event("calendar-updated"));
      onClearEdit?.();
      navigate(returnScreen);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="add-screen">
      <div className="add-header">
        <button className="back-btn" onClick={goBack}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h1>{isEditing ? t("Edit Appointment") : t("Recipient Appointment")}</h1>
        <p>
          {isEditing
            ? t("Update this event in Google Calendar.")
            : t("Schedule medical visits or events for the care recipient.")}
        </p>
      </div>

      <div className="add-body">
        {error && <p className="form-error">{error}</p>}

        <div className="form-group">
          <label className="form-label">{t("Appointment Title")}</label>
          <input
            className="form-input"
            type="text"
            name="title"
            placeholder={t("e.g., General Physician Visit")}
            value={form.title}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label className="form-label">{t("Date")}</label>
          <input
            className="form-input native-picker"
            type="date"
            name="date"
            value={form.date}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label className="form-label">{t("Time")}</label>
          <input
            className="form-input native-picker"
            type="time"
            name="time"
            value={form.time}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label className="form-label">{t("Notes")}</label>
          <textarea
            className="form-textarea"
            name="notes"
            placeholder={t("Add specific instructions, e.g., fasting required...")}
            value={form.notes}
            onChange={handleChange}
          />
        </div>

        <div className="toggle-row">
          <span className="toggle-label">{t("Alert me before this event")}</span>
          <button
            className={`toggle-switch ${reminder ? "on" : "off"}`}
            onClick={() => setReminder(!reminder)}
            type="button"
          >
            <span className="toggle-thumb" />
          </button>
        </div>

        <button className="submit-btn" onClick={handleSubmit} disabled={saving}>
          {saving ? t("Saving...") : isEditing ? t("Update Appointment") : t("Save Appointment")}
        </button>
      </div>
    </div>
  );
}
