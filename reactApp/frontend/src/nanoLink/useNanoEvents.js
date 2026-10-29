import { useEffect, useRef, useState } from "react";

// Must match PROTOCOL_VERSION in backend/nanoLink/protocol.js.
const PROTOCOL_VERSION = 1;
const EVENTS_URL = "/api/nano/events";
// Backoff for reopening the stream after the browser gives up on it.
const MIN_RETRY_MS = 1_000;
const MAX_RETRY_MS = 10_000;
// The backend sends a "ping" event every 15s (HEARTBEAT_MS in backend/nanoLink/hub.js);
// ~3 missed pings means the stream is dead.
const STALE_MS = 45_000;
const WATCHDOG_INTERVAL_MS = 5_000;

/**
 * Subscribes to the Nano's face events (SSE) relayed by the backend.
 * The stream reconnects after drops or backend restarts, and the backend replays the
 * latest state/expression on connect, so the face resyncs on its own.
 *
 * @param {{ onRobotStateChange?: (state: "sleeping" | "active") => void }} [options]
 *   onRobotStateChange is called when the robot's state actually changes (not on replays).
 * @returns {{ connected: boolean, robotState: "sleeping" | "active" | null, expression: string | null }}
 *   robotState is null until the Nano has reported in; expression is null when none is set.
 */
export function useNanoEvents({ onRobotStateChange } = {}) {
  const [connected, setConnected] = useState(false);
  const [robotState, setRobotState] = useState(null);
  const [expression, setExpression] = useState(null);

  // Latest callback, so the stream doesn't reconnect when the parent re-renders.
  const onStateChangeRef = useRef(onRobotStateChange);
  useEffect(() => {
    onStateChangeRef.current = onRobotStateChange;
  });

  useEffect(() => {
    if (typeof EventSource === "undefined") return undefined;

    // The backend replays the latest state on every reconnect; only real changes notify the caller.
    let lastState = null;
    let source = null;
    let retryTimer = null;
    let retryMs = MIN_RETRY_MS;
    let stopped = false;
    // Last time anything (message, ping, open) arrived on the stream.
    let lastSeen = Date.now();

    const handleMessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!message || message.v !== PROTOCOL_VERSION) return;

      if (message.type === "robot.state") {
        const state = message.payload?.state;
        if (state !== "sleeping" && state !== "active") return;
        setRobotState(state);
        // An expression only lasts until the state changes (a repeated state, e.g. a resync, keeps it).
        if (state !== lastState) {
          lastState = state;
          setExpression(null);
          onStateChangeRef.current?.(state);
        }
      } else if (message.type === "robot.expression") {
        const name = message.payload?.name;
        if (typeof name === "string" && name.trim()) setExpression(name.trim());
      }
    };

    // Close the current stream and open a new one after the backoff delay.
    const reopen = () => {
      setConnected(false);
      source?.close();
      if (stopped) return;
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
    };

    const connect = () => {
      retryTimer = null;
      lastSeen = Date.now();
      source = new EventSource(EVENTS_URL);
      source.onmessage = (event) => {
        lastSeen = Date.now();
        handleMessage(event);
      };
      source.addEventListener("ping", () => {
        lastSeen = Date.now();
      });
      source.onopen = () => {
        lastSeen = Date.now();
        retryMs = MIN_RETRY_MS;
        setConnected(true);
      };
      source.onerror = () => {
        setConnected(false);
        // A dropped connection is retried by EventSource itself, but an HTTP error response
        // (e.g. the Vite proxy's 502 while the backend is down) closes it for good.
        if (source.readyState === EventSource.CLOSED) reopen();
      };
    };

    // Watchdog: a proxy can keep a dead stream open without ever erroring,
    // so treat a long silence (no messages or pings) as a dropped connection.
    const watchdog = window.setInterval(() => {
      // Skip while a reconnect is already scheduled.
      if (retryTimer == null && Date.now() - lastSeen > STALE_MS) reopen();
    }, WATCHDOG_INTERVAL_MS);

    connect();

    return () => {
      stopped = true;
      window.clearInterval(watchdog);
      window.clearTimeout(retryTimer);
      source?.close();
    };
  }, []);

  return { connected, robotState, expression };
}
