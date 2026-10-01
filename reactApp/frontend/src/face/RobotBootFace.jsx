import { useEffect, useMemo, useState } from "react";
import {
  ACCENT_COLOR,
  FACE_BG,
  IDLE_SCRIPT,
  getExpression,
  sanitizeIdleScript,
} from "./expressions";
import "./robotBootFace.css";

// Face is drawn in the same 1024×600 space as the original pygame window.
const VIEW_W = 1024;
const VIEW_H = 600;
const CX = VIEW_W / 2; // horizontal center of the face
const CY = VIEW_H / 2; // vertical center of the face
const EYE_X_OFFSET = 150; // distance of each eye from center X
const EYE_Y_OFFSET = -150; // eyes sit above center Y
const MOUTH_Y = CY + 100; // mouth sits below center Y
const EYEBROW_LENGTH = 70;
const EYEBROW_GAP = 15; // gap between top of eye and brow line

/**
 * Compute the two endpoints of an eyebrow line above one eye.
 * angleDegree tilts the brow (mirrored for left vs right by the caller).
 */
function eyebrowEndpoints(xCenter, yEye, angleDegree, eyeHeight) {
  const angleDeg = Number.isFinite(angleDegree) ? angleDegree : 0;
  const height = Number.isFinite(eyeHeight) ? Math.max(1, eyeHeight) : 55;
  const angle = (angleDeg * Math.PI) / 180;
  const half = EYEBROW_LENGTH / 2;
  const dx = half * Math.cos(angle);
  const dy = half * Math.sin(angle);
  const y = yEye - height / 2 - EYEBROW_GAP;
  return {
    x1: xCenter - dx,
    y1: y - dy,
    x2: xCenter + dx,
    y2: y + dy,
  };
}

/** Draws the mouth for the current expression type. */
function Mouth({ type, color }) {
  if (type === "smile") {
    // Quadratic curve opening upward (happy).
    return (
      <path
        d={`M ${CX - 90} ${MOUTH_Y} Q ${CX} ${MOUTH_Y + 70} ${CX + 90} ${MOUTH_Y}`}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
      />
    );
  }
  if (type === "frown") {
    // Quadratic curve opening downward (sad).
    return (
      <path
        d={`M ${CX - 90} ${MOUTH_Y + 40} Q ${CX} ${MOUTH_Y - 30} ${CX + 90} ${MOUTH_Y + 40}`}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
      />
    );
  }
  if (type === "open") {
    // Oval open mouth (surprised).
    return <ellipse cx={CX} cy={MOUTH_Y + 10} rx={50} ry={50} fill={color} />;
  }
  // Default: straight line (neutral / thinking / blink / unknown).
  return (
    <line
      x1={CX - 60}
      y1={MOUTH_Y}
      x2={CX + 60}
      y2={MOUTH_Y}
      stroke={color}
      strokeWidth="5"
      strokeLinecap="round"
    />
  );
}

/**
 * Full-screen boot/idle face using premade expression geometry from robot_face.py.
 *
 * Props:
 * - onDismiss: called when the user taps/clicks (parent usually calls goApp())
 * - playIdle: when true, cycles IDLE_SCRIPT expressions on a timer
 */
export default function RobotBootFace({ onDismiss, playIdle = true }) {
  // Validated idle steps (an empty / fully-invalid script leaves the face on Neutral).
  const script = useMemo(() => sanitizeIdleScript(IDLE_SCRIPT), []);
  const isAnimating = playIdle && script.length > 0;
  // Index into the idle script; wraps around so the loop repeats forever.
  const [step, setStep] = useState(0);
  const currentStep = isAnimating ? script[step % script.length] : null;
  const expressionName = currentStep?.expression ?? "Neutral";
  // Geometry knobs for the current expression.
  const emo = useMemo(() => getExpression(expressionName), [expressionName]);

  // Hold the current expression for its duration, then advance to the next step.
  useEffect(() => {
    if (!currentStep) return undefined;
    const timerId = window.setTimeout(() => setStep((s) => s + 1), currentStep.ms);
    // Clear on unmount (e.g. user entered the app) or when the step changes.
    return () => window.clearTimeout(timerId);
  }, [step, currentStep]);

  // Eye / brow positions for the current expression.
  const yEye = CY + EYE_Y_OFFSET;
  const leftEyeX = CX - EYE_X_OFFSET;
  const rightEyeX = CX + EYE_X_OFFSET;
  // Right brow uses the negated angle so both brows mirror each other.
  const leftBrow = eyebrowEndpoints(leftEyeX, yEye, emo.eyebrow_angle, emo.eye_h);
  const rightBrow = eyebrowEndpoints(rightEyeX, yEye, -emo.eyebrow_angle, emo.eye_h);
  // Corner radius so the eye rect looks like a soft capsule / oval.
  const eyeRx = Math.min(emo.eye_w, emo.eye_h) / 2;

  // Tap / keyboard → leave face mode and enter the app.
  const handleDismiss = (event) => {
    event.preventDefault();
    onDismiss?.();
  };

  return (
    // Full-screen hit target: any tap/click dismisses the face.
    <div
      className="robot-boot-face"
      role="button"
      tabIndex={0}
      aria-label="Robot face. Tap to open the app."
      onPointerUp={handleDismiss}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") handleDismiss(event);
      }}
    >
      <svg
        className="robot-boot-face__svg"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="xMidYMid meet"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Background fill */}
        <rect width={VIEW_W} height={VIEW_H} fill={FACE_BG} />

        {/* Left eye */}
        <rect
          className="robot-boot-face__eye"
          x={leftEyeX - emo.eye_w / 2}
          y={yEye - emo.eye_h / 2}
          width={emo.eye_w}
          height={emo.eye_h}
          rx={eyeRx}
          ry={eyeRx}
          fill={ACCENT_COLOR}
        />
        {/* Right eye */}
        <rect
          className="robot-boot-face__eye"
          x={rightEyeX - emo.eye_w / 2}
          y={yEye - emo.eye_h / 2}
          width={emo.eye_w}
          height={emo.eye_h}
          rx={eyeRx}
          ry={eyeRx}
          fill={ACCENT_COLOR}
        />

        {/* Eyebrows */}
        <line
          x1={leftBrow.x1}
          y1={leftBrow.y1}
          x2={leftBrow.x2}
          y2={leftBrow.y2}
          stroke={ACCENT_COLOR}
          strokeWidth="5"
          strokeLinecap="round"
        />
        <line
          x1={rightBrow.x1}
          y1={rightBrow.y1}
          x2={rightBrow.x2}
          y2={rightBrow.y2}
          stroke={ACCENT_COLOR}
          strokeWidth="5"
          strokeLinecap="round"
        />

        <Mouth type={emo.mouth} color={ACCENT_COLOR} />
      </svg>

      {/* Visual cue only — pointer-events disabled in CSS so taps still hit the parent */}
      <p className="robot-boot-face__hint">Tap anywhere to continue</p>
    </div>
  );
}
