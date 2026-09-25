import "dotenv/config";
import cors from "cors";
import express from "express";
import { toNodeHandler, fromNodeHeaders } from "better-auth/node";
import { auth } from "./auth.js";
import { ensureAuthDatabase } from "./migrate-auth.js";
import { requireAuth } from "./middleware/requireAuth.js";
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
const CLIENT_ORIGIN = process.env.CLIENT_ORIGIN || "http://localhost:5173";

app.use(
  cors({
    origin: [CLIENT_ORIGIN, "http://127.0.0.1:5173"],
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    credentials: true,
  })
);

app.all("/api/auth/*", toNodeHandler(auth));

app.use(express.json());

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, service: "braincharge-calendar-api" });
});

app.get("/api/me", async (req, res) => {
  try {
    const session = await auth.api.getSession({
      headers: fromNodeHeaders(req.headers),
    });

    if (!session) {
      return res.status(401).json({ user: null, session: null });
    }

    return res.json(session);
  } catch (error) {
    console.error("Session lookup failed:", error.message);
    return res.status(500).json({ error: "Failed to load session" });
  }
});

app.get("/api/calendar/verify", requireAuth, async (_req, res) => {
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

app.get("/api/events", requireAuth, async (req, res) => {
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

app.get("/api/events/:eventId", requireAuth, async (req, res) => {
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

app.post("/api/events", requireAuth, async (req, res) => {
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

app.put("/api/events/:eventId", requireAuth, async (req, res) => {
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

app.delete("/api/events/:eventId", requireAuth, async (req, res) => {
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

await ensureAuthDatabase();

const server = app.listen(PORT, HOST, () => {
  console.log(`Calendar API running at http://${HOST}:${PORT}`);
  console.log(`Health check: http://${HOST}:${PORT}/api/health`);
  console.log(`Auth routes: http://${HOST}:${PORT}/api/auth/*`);
});

server.on("error", (error) => {
  if (error.code === "EADDRINUSE") {
    console.error(`\nPort ${PORT} is already in use. Stop the old server first:`);
    console.error(`  netstat -ano | findstr :${PORT}`);
    console.error(`  taskkill /PID <PID> /F\n`);
    process.exit(1);
  }
  throw error;
});
