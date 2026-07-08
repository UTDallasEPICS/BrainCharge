const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message =
      response.status === 502
        ? "Calendar server is not running. In a second terminal, run: npm run server"
        : data.details || data.error || `Request failed (${response.status})`;
    throw new Error(message);
  }

  return data;
}

export function listEvents(params = {}) {
  const search = new URLSearchParams();
  if (params.timeMin) search.set("timeMin", params.timeMin);
  if (params.timeMax) search.set("timeMax", params.timeMax);
  if (params.maxResults) search.set("maxResults", String(params.maxResults));

  const query = search.toString();
  return request(`/events${query ? `?${query}` : ""}`);
}

export function getEvent(eventId) {
  return request(`/events/${eventId}`);
}

export function createEvent(event) {
  return request("/events", {
    method: "POST",
    body: JSON.stringify(event),
  });
}

export function updateEvent(eventId, event) {
  return request(`/events/${eventId}`, {
    method: "PUT",
    body: JSON.stringify(event),
  });
}

export function deleteEvent(eventId) {
  return request(`/events/${eventId}`, {
    method: "DELETE",
  });
}

export function verifyCalendar() {
  return request("/calendar/verify");
}

/** Convert 12h display time back to HH:MM for the API */
export function time12hTo24h(time12) {
  if (!time12 || time12 === "All day") return "";
  const match = time12.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!match) return "";

  let hours = parseInt(match[1], 10);
  const minutes = match[2];
  const period = match[3].toUpperCase();

  if (period === "PM" && hours !== 12) hours += 12;
  if (period === "AM" && hours === 12) hours = 0;

  return `${String(hours).padStart(2, "0")}:${minutes}`;
}
