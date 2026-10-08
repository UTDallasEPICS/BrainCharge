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

  // An expression only lasts until the next state change.
  if (message.type === TYPES.ROBOT_STATE) latest.delete(TYPES.ROBOT_EXPRESSION);
  latest.set(message.type, message);

  for (const res of clients) writeEvent(res, message);
  return true;
}

/** Snapshot for a debug/status route. */
export function getStatus() {
  return {
    clients: clients.size,
    latest: Object.fromEntries(latest),
  };
}

const heartbeat = setInterval(() => {
  // Named event (not a comment) so EventSource exposes it to JS; it needs a data line to be dispatched.
  for (const res of clients) res.write("event: ping\ndata: {}\n\n");
}, HEARTBEAT_MS);
// Don't keep the Node process alive just for the heartbeat.
heartbeat.unref();
