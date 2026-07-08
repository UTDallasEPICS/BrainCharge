import "dotenv/config";
import cors from "cors";
import express from "express";
import {
  createEvent,
  deleteEvent,
  getEvent,
  listEvents,
  updateEvent,
  verifyCalendarAccess,
} from "./calendar.js";

const app = express();
const PORT = process.env.PORT || 3001;
const HOST = process.env.HOST || "127.0.0.1";

app.use(cors());
app.use(express.json());

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, service: "braincharge-calendar-api" });
});

app.get("/api/calendar/verify", async (_req, res) => {
  try {
    const result = await verifyCalendarAccess();
    res.json(result);
  } catch (error) {
    console.error("Calendar verify failed:", error.message);
    res.status(500).json({
      error: "Failed to verify calendar access",
      details: error.message,
    });
  }
});

app.get("/api/events", async (req, res) => {
  try {
    const timeMin = req.query.timeMin ? new Date(req.query.timeMin) : undefined;
    const timeMax = req.query.timeMax ? new Date(req.query.timeMax) : undefined;
    const maxResults = req.query.maxResults ? Number(req.query.maxResults) : undefined;

    const events = await listEvents({ timeMin, timeMax, maxResults });
    res.json(events);
  } catch (error) {
    console.error("List events failed:", error.message);
    res.status(500).json({
      error: "Failed to list calendar events",
      details: error.message,
    });
  }
});

app.get("/api/events/:eventId", async (req, res) => {
  try {
    const event = await getEvent(req.params.eventId);
    res.json(event);
  } catch (error) {
    console.error("Get event failed:", error.message);
    res.status(500).json({
      error: "Failed to get calendar event",
      details: error.message,
    });
  }
});

app.post("/api/events", async (req, res) => {
  try {
    const event = await createEvent(req.body);
    res.status(201).json(event);
  } catch (error) {
    console.error("Create event failed:", error.message);
    res.status(400).json({
      error: "Failed to create calendar event",
      details: error.message,
    });
  }
});

app.put("/api/events/:eventId", async (req, res) => {
  try {
    const event = await updateEvent(req.params.eventId, req.body);
    res.json(event);
  } catch (error) {
    console.error("Update event failed:", error.message);
    res.status(400).json({
      error: "Failed to update calendar event",
      details: error.message,
    });
  }
});

app.delete("/api/events/:eventId", async (req, res) => {
  try {
    await deleteEvent(req.params.eventId);
    res.json({ success: true });
  } catch (error) {
    console.error("Delete event failed:", error.message);
    res.status(500).json({
      error: "Failed to delete calendar event",
      details: error.message,
    });
  }
});

app.listen(PORT, HOST, () => {
  console.log(`Calendar API running at http://${HOST}:${PORT}`);
  console.log(`Health check: http://${HOST}:${PORT}/api/health`);
  console.log(`Verify access: http://${HOST}:${PORT}/api/calendar/verify`);
});
