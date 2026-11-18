import crypto from "node:crypto";
import { Router } from "express";
import {
  addClient,
  broadcast,
  drainNanoInbox,
  enqueueForNano,
  getSettings,
  getStatus,
  setNanoStatus,
  setSettings,
} from "./hub.js";
import {
  FACE_EVENT_TYPES,
  NANO_INBOX_TYPES,
  NANO_STATUS_TYPES,
  TYPES,
  makeMessage,
  parseMessage,
  toFacePayload,
} from "./protocol.js";

const router = Router();

/** Constant-time comparison so the token can't be guessed from response timing. */
function tokensMatch(given, expected) {
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

/** Only the Nano (holding NANO_TOKEN) may publish face events / drain the inbox. */
function requireNanoToken(req, res, next) {
  const expected = process.env.NANO_TOKEN;
  if (!expected) {
    return res.status(503).json({ error: "NANO_TOKEN is not set in backend/.env" });
  }

  const header = req.get("authorization") || "";
  const given = header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
  if (!given || !tokensMatch(given, expected)) {
    return res.status(401).json({ error: "Invalid Nano token" });
  }
  return next();
}

function enqueueSettingsForNano(saved) {
  const message = parseMessage(makeMessage(TYPES.UI_SETTINGS, saved));
  if (message) enqueueForNano(message);
}

// Face screen subscribes here. No login required: the face shows before sign-in and
// this stream only carries robot.state / robot.expression (never transcripts).
router.get("/api/nano/events", (_req, res) => {
  addClient(res);
});

// The Nano posts face events or link status/acks (acks are not broadcast to the face).
router.post("/api/nano/event", requireNanoToken, (req, res) => {
  const message = parseMessage(req.body);
  if (!message) {
    return res.status(400).json({ error: "Invalid message or protocol version" });
  }

  if (NANO_STATUS_TYPES.has(message.type)) {
    setNanoStatus(message);
    return res.status(202).json({ ok: true, id: message.id });
  }

  if (!FACE_EVENT_TYPES.has(message.type)) {
    return res.status(422).json({ error: `Type "${message.type}" is not allowed on the face stream` });
  }
  const payload = toFacePayload(message);
  if (!payload) {
    return res.status(422).json({ error: `Invalid payload for "${message.type}"` });
  }

  broadcast({ ...message, payload });
  return res.status(202).json({ ok: true, id: message.id });
});

// Nano polls here for UI → robot messages (settings, future ui.wake / ui.say).
router.get("/api/nano/inbox", requireNanoToken, (_req, res) => {
  return res.json({ messages: drainNanoInbox() });
});

// Generic enqueue for later UI actions / curl testing.
router.post("/api/nano/command", (req, res) => {
  const type = typeof req.body?.type === "string" ? req.body.type : "";
  if (!NANO_INBOX_TYPES.has(type)) {
    return res.status(422).json({
      error: `Type must be one of: ${[...NANO_INBOX_TYPES].join(", ")}`,
    });
  }
  const payload =
    req.body?.payload && typeof req.body.payload === "object" ? req.body.payload : {};
  const message = parseMessage(makeMessage(type, payload));
  if (!message || !enqueueForNano(message)) {
    return res.status(400).json({ error: "Could not enqueue message" });
  }
  return res.status(202).json({ ok: true, id: message.id });
});

// Webapp settings: browser saves here; Nano can read the snapshot too.
router.get("/api/settings", (_req, res) => {
  return res.json({ settings: getSettings() });
});

router.put("/api/settings", (req, res) => {
  try {
    const saved = setSettings(req.body ?? {});
    enqueueSettingsForNano(saved);
    return res.json({ ok: true, settings: saved });
  } catch (err) {
    return res.status(400).json({ error: err.message || "Invalid settings" });
  }
});

// Debug view of connected face clients, inbox, settings, and latest Nano ack.
router.get("/api/nano/status", (_req, res) => {
  res.json(getStatus());
});

export default router;
