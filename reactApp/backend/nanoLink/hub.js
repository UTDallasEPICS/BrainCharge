import { FACE_EVENT_TYPES, TYPES } from "./protocol.js";

// A "ping" event on this interval keeps idle connections open and lets the browser detect
// a dead stream (proxies like Vite's can keep the browser side open after the backend dies).
// Clients treat ~3 missed pings as a dead stream, so keep this in sync with the frontend hook.
const HEARTBEAT_MS = 15_000;
// Tells EventSource how long to wait before reconnecting after a drop.
const RECONNECT_MS = 3_000;

// Open SSE responses (one per connected face/browser tab).
const clients = new Set();
// Latest face message per type, replayed to new clients so they start in the current state.
const latest = new Map();

// Messages enqueued for the Nano to process
const nanoInbox = [];
// Maximum number of messages to enqueue for the Nano to process
const NANO_INBOX_MAX_LENGTH = 50;
// Latest settings snapshot from the web UI (Nano polls inbox / GET /api/settings)
let settings = null;
// Latest link.ack / link.status from the Nano (for debug / UI later)
let latestNanoStatus = null;

/** Writes one parsed protocol message as an SSE event. */
function writeEvent(res, message) {
  res.write(`data: ${JSON.stringify(message)}\n\n`);
}

/**
 * Registers an SSE client: sends stream headers, replays the current face state,
 * and removes the client when the connection closes.
 * @param {import("express").Response} res
 */
export function addClient(res) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  res.write(`retry: ${RECONNECT_MS}\n\n`);

  // State before expression, so the client applies them in the right order.
  for (const type of [TYPES.ROBOT_STATE, TYPES.ROBOT_EXPRESSION]) {
    const message = latest.get(type);
    if (message) writeEvent(res, message);
  }

  clients.add(res);
  // Listen on res, not req: req "close" can fire once the request is read, not when the client leaves.
  res.on("close", () => clients.delete(res));
}

/**
 * Sends a parsed face message to every connected client and remembers it for replay.
 * @param {object} message - Output of parseMessage().
 * @returns {boolean} false if the type is not allowed on the face stream.
 */
export function broadcast(message) {
  if (!message || !FACE_EVENT_TYPES.has(message.type)) return false;

  // An expression only lasts until the state changes (a repeated state, e.g. a resync, keeps it).
  const stateChanged =
    message.type === TYPES.ROBOT_STATE &&
    latest.get(TYPES.ROBOT_STATE)?.payload.state !== message.payload.state;
  if (stateChanged) latest.delete(TYPES.ROBOT_EXPRESSION);
  latest.set(message.type, message);

  for (const res of clients) writeEvent(res, message);
  return true;
}

/** Snapshot for a debug/status route. */
export function getStatus() {
  return {
    clients: clients.size,
    latest: Object.fromEntries(latest),
    inboxLength: nanoInbox.length,
    settings,
    latestNanoStatus,
  };
}

const heartbeat = setInterval(() => {
  // Named event (not a comment) so EventSource exposes it to JS; it needs a data line to be dispatched.
  for (const res of clients) res.write("event: ping\ndata: {}\n\n");
}, HEARTBEAT_MS);
// Don't keep the Node process alive just for the heartbeat.
heartbeat.unref();

/** Queue one protocol message for the Nano to pull later. */
export function enqueueForNano(message) {
  if (!message || typeof message !== "object" || typeof message.type !== "string") {
    return false;
  }
  nanoInbox.push({
    v: message.v,
    id: message.id,
    ts: message.ts,
    type: message.type,
    payload:
      message.payload && typeof message.payload === "object" ? message.payload : {},
  });
  while (nanoInbox.length > NANO_INBOX_MAX_LENGTH) nanoInbox.shift();
  return true;
}

/** Return and clear all pending Nano messages. */
export function drainNanoInbox() {
  if (nanoInbox.length === 0) return [];
  return nanoInbox.splice(0, nanoInbox.length);
}

/** @returns {object|null} Shallow copy of latest settings, or null if none saved yet. */
export function getSettings() {
  return settings === null ? null : { ...settings };
}

/**
 * Replace/merge settings and return the new snapshot.
 * @param {object} next
 * @param {{ merge?: boolean }} [options]
 */
export function setSettings(next, { merge = true } = {}) {
  if (!next || typeof next !== "object" || Array.isArray(next)) {
    throw new TypeError("settings must be a plain object");
  }
  settings = merge && settings ? { ...settings, ...next } : { ...next };
  return { ...settings };
}

/** Remember a non-face status message from the Nano (e.g. link.ack). */
export function setNanoStatus(message) {
  if (!message || typeof message !== "object") return false;
  latestNanoStatus = message;
  return true;
}