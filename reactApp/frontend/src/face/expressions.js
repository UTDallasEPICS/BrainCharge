/**
 * Premade robot-face expression parameters.
 * Ported from the legacy Pygame module display/robot_face.py.
 *
 * Each expression is a small set of geometry knobs:
 * - eye_w / eye_h: eye oval size in the 1024×600 face coordinate space
 * - eyebrow_angle: degrees; positive = raised outward / surprised tilt
 * - mouth: which mouth shape to draw ("flat" | "smile" | "frown" | "open")
 */

/** Cyan line/fill color used for eyes, brows, and mouth (matches pygame ACCENT_COLOR). */
export const ACCENT_COLOR = "#00DCFF";

/** Solid black background behind the face. */
export const FACE_BG = "#000000";

const VALID_MOUTHS = new Set(["flat", "smile", "frown", "open"]);

/** Safe defaults used when a lookup misses or a definition is incomplete. */
export const NEUTRAL_EXPRESSION = {
  eye_w: 80,
  eye_h: 55,
  eyebrow_angle: 0,
  mouth: "flat",
};

/** Keep SVG geometry drawable (no NaN / zero / extreme sizes). */
const MIN_EYE = 1;
const MAX_EYE = 400;
/** Avoid setTimeout(0)/NaN spinning the idle loop. */
export const MIN_STEP_MS = 50;
const MAX_STEP_MS = 120_000;

/** Named expressions the SVG face can morph between. */
export const EXPRESSIONS = {
  Neutral: { ...NEUTRAL_EXPRESSION },
  Happy: { eye_w: 90, eye_h: 40, eyebrow_angle: 0, mouth: "smile" },
  Surprised: { eye_w: 60, eye_h: 90, eyebrow_angle: 0, mouth: "open" },
  // Idle-only helpers using the same geometry language
  Blink: { eye_w: 88, eye_h: 4, eyebrow_angle: 0, mouth: "flat" }, // nearly closed lids
  Thinking: { eye_w: 72, eye_h: 48, eyebrow_angle: 12, mouth: "flat" }, // brows up a bit
};

/**
 * Ordered idle animation for the boot/face screen.
 * Each step shows `expression` for `ms` milliseconds, then advances (loops forever).
 */
export const IDLE_SCRIPT = [
  { expression: "Neutral", ms: 2800 },
  { expression: "Blink", ms: 140 },
  { expression: "Neutral", ms: 1800 },
  { expression: "Happy", ms: 3200 },
  { expression: "Blink", ms: 140 },
  { expression: "Thinking", ms: 2600 },
  { expression: "Blink", ms: 140 },
  { expression: "Neutral", ms: 2200 },
  { expression: "Surprised", ms: 1600 },
  { expression: "Blink", ms: 140 },
];

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n));
}

/**
 * Coerce a partial / invalid expression object into drawable geometry.
 * Null, non-objects, missing fields, NaN, and out-of-range sizes fall back safely.
 */
export function normalizeExpression(raw) {
  if (raw == null || typeof raw !== "object") {
    return { ...NEUTRAL_EXPRESSION };
  }

  const eye_w = Number(raw.eye_w);
  const eye_h = Number(raw.eye_h);
  const eyebrow_angle = Number(raw.eyebrow_angle);
  const mouth = VALID_MOUTHS.has(raw.mouth) ? raw.mouth : NEUTRAL_EXPRESSION.mouth;

  return {
    eye_w: Number.isFinite(eye_w)
      ? clamp(eye_w, MIN_EYE, MAX_EYE)
      : NEUTRAL_EXPRESSION.eye_w,
    eye_h: Number.isFinite(eye_h)
      ? clamp(eye_h, MIN_EYE, MAX_EYE)
      : NEUTRAL_EXPRESSION.eye_h,
    eyebrow_angle: Number.isFinite(eyebrow_angle) ? eyebrow_angle : NEUTRAL_EXPRESSION.eyebrow_angle,
    mouth,
  };
}

/** Look up expression params by name; falls back to Neutral if unknown / empty. */
export function getExpression(name) {
  if (name == null || name === "") {
    return normalizeExpression(NEUTRAL_EXPRESSION);
  }
  return normalizeExpression(EXPRESSIONS[name] ?? NEUTRAL_EXPRESSION);
}

/**
 * Drop null/empty script rows and clamp durations so the idle loop cannot
 * crash on `% 0` or spin on NaN / 0 / negative timeouts.
 */
export function sanitizeIdleScript(script = IDLE_SCRIPT) {
  if (!Array.isArray(script) || script.length === 0) return [];

  const steps = [];
  for (const step of script) {
    if (step == null || typeof step !== "object") continue;
    const expression =
      typeof step.expression === "string" && step.expression.trim()
        ? step.expression.trim()
        : "Neutral";
    const ms = Number(step.ms);
    if (!Number.isFinite(ms)) continue;
    steps.push({
      expression,
      ms: clamp(ms, MIN_STEP_MS, MAX_STEP_MS),
    });
  }
  return steps;
}
