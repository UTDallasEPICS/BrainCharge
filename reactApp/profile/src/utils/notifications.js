const DAY_MAP = { 0: "Su", 1: "M", 2: "T", 3: "W", 4: "Th", 5: "F", 6: "S" };

const URGENT_MINUTES = 15;
const SOON_MINUTES = 120;
const UPCOMING_DAYS = 7;

export function loadNotificationSettings() {
  try {
    const s = localStorage.getItem("app_settings");
    if (s) return JSON.parse(s).notifications !== false;
  } catch {
    /* use default */
  }
  return true;
}

export function parseTime12h(timeStr) {
  if (!timeStr || timeStr === "All day") return null;
  const match = timeStr.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!match) return null;

  let hours = parseInt(match[1], 10);
  const minutes = parseInt(match[2], 10);
  const period = match[3].toUpperCase();

  if (period === "PM" && hours !== 12) hours += 12;
  if (period === "AM" && hours === 12) hours = 0;

  return { hours, minutes };
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function reminderAppliesOnDate(reminder, date) {
  const meta = reminder.meta || "Daily";
  if (meta === "Daily") return true;
  const day = DAY_MAP[date.getDay()];
  return meta.split(", ").includes(day);
}

export function buildDateTime(dateStr, timeStr) {
  const parsed = parseTime12h(timeStr);
  if (!parsed) return null;

  const base = dateStr ? new Date(`${dateStr}T00:00:00`) : new Date();
  if (Number.isNaN(base.getTime())) return null;

  return new Date(
    base.getFullYear(),
    base.getMonth(),
    base.getDate(),
    parsed.hours,
    parsed.minutes,
    0
  );
}

function classifyByMinutes(minutesUntil) {
  if (minutesUntil < -URGENT_MINUTES) return "past";
  if (minutesUntil <= URGENT_MINUTES) return "urgent";
  if (minutesUntil <= SOON_MINUTES) return "soon";
  return "later";
}

function urgencyLabel(urgency, minutesUntil) {
  if (urgency === "urgent") {
    if (minutesUntil < 0) return "Happening now";
    if (minutesUntil === 0) return "Starting now";
    return `In ${minutesUntil} min`;
  }
  if (urgency === "soon") return `In ${minutesUntil} min`;
  if (urgency === "later") return "Later today";
  return "Upcoming";
}

function normalizeReminder(reminder, referenceDate = new Date()) {
  if (!reminderAppliesOnDate(reminder, referenceDate)) return null;

  const dateStr = [
    referenceDate.getFullYear(),
    String(referenceDate.getMonth() + 1).padStart(2, "0"),
    String(referenceDate.getDate()).padStart(2, "0"),
  ].join("-");

  const at = buildDateTime(dateStr, reminder.time);
  if (!at) return null;

  const minutesUntil = Math.round((at - referenceDate) / 60000);
  const urgency = classifyByMinutes(minutesUntil);
  if (urgency === "past") return null;

  return {
    id: `reminder-${reminder.id}-${dateStr}`,
    sourceId: reminder.id,
    source: "reminder",
    title: reminder.name,
    subtitle: reminder.meta || "Self-care reminder",
    note: reminder.note || "",
    time: reminder.time,
    date: dateStr,
    at,
    minutesUntil,
    urgency,
    urgencyLabel: urgencyLabel(urgency, minutesUntil),
  };
}

function normalizeCalendarEvent(event, referenceDate = new Date()) {
  if (!event.date || !event.time || event.time === "All day") return null;

  const at = buildDateTime(event.date, event.time);
  if (!at) return null;

  const eventDay = startOfDay(at);
  const today = startOfDay(referenceDate);
  const maxDay = new Date(today);
  maxDay.setDate(maxDay.getDate() + UPCOMING_DAYS);

  if (eventDay < today || eventDay > maxDay) return null;

  const minutesUntil = Math.round((at - referenceDate) / 60000);
  let urgency;

  if (eventDay.getTime() > today.getTime()) {
    urgency = "upcoming";
  } else {
    urgency = classifyByMinutes(minutesUntil);
    if (urgency === "past") return null;
  }

  return {
    id: `calendar-${event.id}`,
    sourceId: event.id,
    source: "calendar",
    title: event.title,
    subtitle: "Care recipient appointment",
    note: event.note || "",
    time: event.time,
    date: event.date,
    at,
    minutesUntil,
    urgency,
    urgencyLabel:
      urgency === "upcoming"
        ? formatUpcomingDate(event.date)
        : urgencyLabel(urgency, minutesUntil),
  };
}

function formatUpcomingDate(dateStr) {
  const date = new Date(`${dateStr}T00:00:00`);
  const today = startOfDay(new Date());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  if (date.getTime() === tomorrow.getTime()) return "Tomorrow";
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function buildNotificationItems({ reminders = [], calendarEvents = [], now = new Date() }) {
  const items = [];

  for (const reminder of reminders) {
    const item = normalizeReminder(reminder, now);
    if (item) items.push(item);
  }

  for (const event of calendarEvents) {
    const item = normalizeCalendarEvent(event, now);
    if (item) items.push(item);
  }

  return items.sort((a, b) => a.at - b.at);
}

export function getBadgeCount(items) {
  return items.filter((item) => item.urgency === "urgent" || item.urgency === "soon").length;
}

export function groupNotifications(items) {
  const groups = [
    { key: "urgent", label: "Due now", items: [] },
    { key: "soon", label: "Coming up soon", items: [] },
    { key: "later", label: "Later today", items: [] },
    { key: "upcoming", label: "Upcoming", items: [] },
  ];

  for (const item of items) {
    const group = groups.find((g) => g.key === item.urgency);
    if (group) group.items.push(item);
  }

  return groups.filter((g) => g.items.length > 0);
}
