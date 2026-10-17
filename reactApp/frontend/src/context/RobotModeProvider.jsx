import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RobotModeContext } from "./robotModeContext.js";

// How long the user can sit idle in the app before we auto-return to the face screen.
const INACTIVITY_MS = 60_000;

// Unknown values coerce to "face" so a bad prop cannot blank the UI.
function normalizeMode(value) {
  return value === "app" || value === "face" ? value : "face";
}

/**
 * Wraps the PWA and owns high-level UI mode:
 * - "face": full-screen robot face (boot / idle)
 * - "app": normal caregiver web UI
 *
 * Also starts a 60s inactivity timer while in "app" so the robot face returns on its own.
 */
export function RobotModeProvider({ children, initialMode = "face" }) {
  // Current screen mode — defaults to face so the PWA boots on the robot face.
  const [mode, setMode] = useState(() => normalizeMode(initialMode));
  // Holds the pending setTimeout id for the inactivity → face transition.
  const timerRef = useRef(null);

  // Cancel any scheduled return-to-face timer.
  const clearInactivityTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Switch to the full-screen face and stop counting idle time.
  const goFace = useCallback(() => {
    clearInactivityTimer();
    setMode("face");
  }, [clearInactivityTimer]);

  // Switch to the normal app UI (e.g. after tapping the face).
  const goApp = useCallback(() => {
    setMode("app");
  }, []);

  // Reset the 60s idle countdown. Only meaningful while mode is "app".
  const bumpActivity = useCallback(() => {
    if (mode !== "app") return;
    clearInactivityTimer();
    // After INACTIVITY_MS with no further bumps, snap back to the face.
    timerRef.current = window.setTimeout(() => {
      setMode("face");
    }, INACTIVITY_MS);
  }, [mode, clearInactivityTimer]);

  // While in app mode, any user input resets the idle timer.
  useEffect(() => {
    if (mode !== "app") {
      clearInactivityTimer();
      return undefined;
    }

    // Start the first countdown as soon as we enter app mode.
    bumpActivity();

    // Pointer / keyboard / scroll all count as "still using the app".
    const events = ["pointerdown", "pointermove", "keydown", "touchstart", "scroll", "wheel"];
    const onActivity = () => bumpActivity();
    for (const eventName of events) {
      window.addEventListener(eventName, onActivity, { passive: true });
    }

    // Clean up listeners and timer when leaving app mode or unmounting.
    return () => {
      for (const eventName of events) {
        window.removeEventListener(eventName, onActivity);
      }
      clearInactivityTimer();
    };
  }, [mode, bumpActivity, clearInactivityTimer]);

  // Toggle CSS class on <html>/<body> so face mode can go true full-screen
  // (hide scrollbars / ignore the phone-shell max-width styles).
  useEffect(() => {
    document.documentElement.classList.toggle("robot-face-mode", mode === "face");
    document.body.classList.toggle("robot-face-mode", mode === "face");
    return () => {
      document.documentElement.classList.remove("robot-face-mode");
      document.body.classList.remove("robot-face-mode");
    };
  }, [mode]);

  // Stable object passed to consumers — avoids re-renders when unrelated state changes.
  const value = useMemo(
    () => ({
      mode, // "face" | "app"
      isFace: mode === "face",
      isApp: mode === "app",
      goFace, // force face mode
      goApp, // force app mode
      bumpActivity, // manually reset idle timer if needed
    }),
    [mode, goFace, goApp, bumpActivity],
  );

  return <RobotModeContext.Provider value={value}>{children}</RobotModeContext.Provider>;
}
