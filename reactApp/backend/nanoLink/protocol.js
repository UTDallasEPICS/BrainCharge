import crypto from "node:crypto";

export const PROTOCOL_VERSION = 1;

export const TYPES = {
  // Robot messages
  ROBOT_HELLO: "robot.hello",
  ROBOT_STATE: "robot.state",
  ROBOT_TRANSCRIPT: "robot.transcript",
  ROBOT_SPEAKING: "robot.speaking",
  ROBOT_EXPRESSION: "robot.expression",

  // Reserved for later (not sent over the face SSE stream yet)
  LINK_STATUS: "link.status",
  UI_WAKE: "ui.wake",
  UI_SAY: "ui.say",
};

// Set of message types that are permitted over the SSE stream for the face UI
export const FACE_EVENT_TYPES = new Set([TYPES.ROBOT_STATE, TYPES.ROBOT_EXPRESSION]);

const ROBOT_STATES = new Set(["sleeping", "active"]);

/**
 * Checks that a face message's payload has the fields the face UI needs.
 * Expression names are not checked here; the face falls back to Neutral for unknown names.
 * @param {{ type: string, payload: object }} message - Output of parseMessage().
 * @returns {boolean}
 */
export function isValidFacePayload(message) {
  if (message.type === TYPES.ROBOT_STATE) {
    return ROBOT_STATES.has(message.payload.state);
  }
  if (message.type === TYPES.ROBOT_EXPRESSION) {
    return typeof message.payload.name === "string" && message.payload.name.trim() !== "";
  }
  return false;
}

/**
 * Creates a JSON message string with protocol version (v), unique ID (id), and timestamp (ts).
 * @param {string} type
 * @param {object} [payload={}]
 * @returns {string}
 */
export function makeMessage(type, payload = {}) {
  return JSON.stringify({
    v: PROTOCOL_VERSION,
    id: crypto.randomUUID(),
    ts: Date.now(),
    type,
    payload,
  });
}

/**
 * Parses and validates an incoming JSON message frame.
 * Rejects messages with the wrong protocol version (v).
 * @param {string|object} raw
 * @returns {object|null}
 */
export function parseMessage(raw) {
  try {
    const data = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!data || typeof data !== "object") return null;

    // Validate version field
    if (data.v !== PROTOCOL_VERSION) return null;

    if (typeof data.type !== "string" || !data.type) return null;

    return {
      v: data.v,
      id: typeof data.id === "string" && data.id ? data.id : crypto.randomUUID(),
      ts: Number.isFinite(data.ts) ? data.ts : Date.now(),
      type: data.type,
      payload: data.payload && typeof data.payload === "object" ? data.payload : {},
    };
  } catch {
    return null;
  }
}