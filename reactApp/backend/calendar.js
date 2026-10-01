import { google } from "googleapis";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SCOPES = ["https://www.googleapis.com/auth/calendar"];

function getConfig() {
  const keyFile = process.env.GOOGLE_SERVICE_ACCOUNT_PATH;
  const calendarId = process.env.GOOGLE_CALENDAR_ID;
  const timeZone = process.env.CALENDAR_TIMEZONE || "America/Chicago";

  if (!keyFile) {
    throw new Error("GOOGLE_SERVICE_ACCOUNT_PATH is not set in .env");
  }
  if (!calendarId) {
    throw new Error("GOOGLE_CALENDAR_ID is not set in .env");
  }

  return {
    keyFile: path.isAbsolute(keyFile) ? keyFile : path.resolve(__dirname, keyFile),
    calendarId,
    timeZone,
  };
}

function getCalendarClient() {
  const { keyFile } = getConfig();
  const auth = new google.auth.GoogleAuth({
    keyFile,
    scopes: SCOPES,
  });

  return google.calendar({ version: "v3", auth });
}

function formatTime12h(hours, minutes) {
  const suffix = hours >= 12 ? "PM" : "AM";
  const h12 = hours % 12 || 12;
  const m = String(minutes).padStart(2, "0");
  return `${h12}:${m} ${suffix}`;
}

function toAppEvent(googleEvent) {
  const start = googleEvent.start?.dateTime || googleEvent.start?.date;
  const isAllDay = Boolean(googleEvent.start?.date && !googleEvent.start?.dateTime);

  let date = "";
  let time = "";

  if (start) {
    if (isAllDay) {
      date = start;
      time = "All day";
    } else {
      const dt = new Date(start);
      date = [
        dt.getFullYear(),
        String(dt.getMonth() + 1).padStart(2, "0"),
        String(dt.getDate()).padStart(2, "0"),
      ].join("-");
      time = formatTime12h(dt.getHours(), dt.getMinutes());
    }
  }

  return {
    id: googleEvent.id,
    title: googleEvent.summary || "(No title)",
    date,
    time,
    note: googleEvent.description || "",
    type: "Scheduled Item",
    htmlLink: googleEvent.htmlLink || null,
    start: googleEvent.start,
    end: googleEvent.end,
  };
}

function buildGoogleEventBody({ title, date, time, note }) {
  const { timeZone } = getConfig();

  if (!title?.trim()) {
    throw new Error("title is required");
  }
  if (!date) {
    throw new Error("date is required");
  }

  const summary = title.trim();
  const description = note?.trim() || undefined;

  if (!time || time === "All day") {
    return {
      summary,
      description,
      start: { date, timeZone },
      end: { date, timeZone },
    };
  }

  const match = time.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) {
    throw new Error("time must be in HH:MM format");
  }

  const hours = parseInt(match[1], 10);
  const minutes = parseInt(match[2], 10);
  const startDateTime = `${date}T${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:00`;

  const endHour = hours + 1;
  const endDateTime = `${date}T${String(endHour).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:00`;

  return {
    summary,
    description,
    start: { dateTime: startDateTime, timeZone },
    end: { dateTime: endDateTime, timeZone },
  };
}

export async function listEvents({ timeMin, timeMax, maxResults = 100 } = {}) {
  const calendar = getCalendarClient();
  const { calendarId } = getConfig();

  const now = new Date();
  const defaultMin = new Date(now);
  defaultMin.setDate(defaultMin.getDate() - 30);
  const defaultMax = new Date(now);
  defaultMax.setFullYear(defaultMax.getFullYear() + 1);

  const response = await calendar.events.list({
    calendarId,
    timeMin: (timeMin || defaultMin).toISOString(),
    timeMax: (timeMax || defaultMax).toISOString(),
    maxResults,
    singleEvents: true,
    orderBy: "startTime",
  });

  return (response.data.items || []).map(toAppEvent);
}

export async function getEvent(eventId) {
  const calendar = getCalendarClient();
  const { calendarId } = getConfig();
  const response = await calendar.events.get({ calendarId, eventId });
  return toAppEvent(response.data);
}

export async function createEvent(payload) {
  const calendar = getCalendarClient();
  const { calendarId } = getConfig();
  const requestBody = buildGoogleEventBody(payload);

  const response = await calendar.events.insert({
    calendarId,
    requestBody,
  });

  return toAppEvent(response.data);
}

export async function updateEvent(eventId, payload) {
  const calendar = getCalendarClient();
  const { calendarId } = getConfig();
  const requestBody = buildGoogleEventBody(payload);

  const response = await calendar.events.update({
    calendarId,
    eventId,
    requestBody,
  });

  return toAppEvent(response.data);
}

export async function deleteEvent(eventId) {
  const calendar = getCalendarClient();
  const { calendarId } = getConfig();
  await calendar.events.delete({ calendarId, eventId });
  return { success: true };
}

export async function verifyCalendarAccess() {
  const events = await listEvents({ maxResults: 5 });
  return {
    ok: true,
    calendarId: getConfig().calendarId,
    eventCount: events.length,
    sample: events.slice(0, 3),
  };
}
