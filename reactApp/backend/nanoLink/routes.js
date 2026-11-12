import crypto from "node:crypto";
import { Router } from "express";
import { addClient, broadcast, getStatus } from "./hub.js";
import { FACE_EVENT_TYPES, parseMessage, toFacePayload } from "./protocol.js";

const router = Router();

/** Constant-time comparison so the token can't be guessed from response timing. */
function tokensMatch(given, expected) {
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

/** Only the Nano (holding NANO_TOKEN) may publish face events. */
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

// Face screen subscribes here. No login required: the face shows before sign-in and
// this stream only carries robot.state / robot.expression (never transcripts).
router.get("/api/nano/events", (_req, res) => {
  addClient(res);
});

// The Nano posts one protocol message per face change.
router.post("/api/nano/event", requireNanoToken, (req, res) => {
  const message = parseMessage(req.body);
  if (!message) {
    return res.status(400).json({ error: "Invalid message or protocol version" });
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

// Debug view of connected face clients and the latest state/expression.
router.get("/api/nano/status", (_req, res) => {
  res.json(getStatus());
});

export default router;
