import { format } from "date-fns";

export function parseGoogleDate(googleDateField) {
  if (!googleDateField) return null;

  const raw = googleDateField.dateTime || googleDateField.date;
  if (!raw) return null;

  if (googleDateField.date && !googleDateField.dateTime) {
    const [year, month, day] = raw.split("-").map(Number);
    return new Date(year, month - 1, day);
  }

  return new Date(raw);
}

export function appEventToCalendarEvent(appEvent) {
  const start = parseGoogleDate(appEvent.start);
  const end = parseGoogleDate(appEvent.end);
  const allDay = Boolean(appEvent.start?.date && !appEvent.start?.dateTime);

  let calendarEnd = end;
  if (allDay && start) {
    calendarEnd = new Date(start);
    calendarEnd.setDate(calendarEnd.getDate() + 1);
  } else if (start && !end) {
    calendarEnd = new Date(start.getTime() + 60 * 60 * 1000);
  }

  return { id: appEvent.id, title: appEvent.title, start, end: calendarEnd, allDay, resource: appEvent };
}

export function slotToFormDefaults(start) {
  return {
    title: "",
    date: format(start, "yyyy-MM-dd"),
    time: format(start, "HH:mm"),
    notes: "",
  };
}
