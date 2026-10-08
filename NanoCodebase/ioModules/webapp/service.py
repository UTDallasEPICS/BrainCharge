"""Face events for the BrainCharge web app.

Sends ``robot.state`` / ``robot.expression`` messages to the web app backend
(``POST /api/nano/event``), which relays them to the face screen over SSE.
The message format is defined in reactApp/backend/nanoLink/protocol.js.

Sending never blocks the orchestrator: messages are queued and posted from a
background thread. If the web app is down, messages are dropped; the latest
state and expression are re-sent periodically so the face resyncs once it's back.

Uses only the standard library (urllib), so no extra dependency is needed.
"""
import json
import queue
import threading
import time
import uuid
from enum import StrEnum
from typing import Any
from urllib import error, request

# Must match PROTOCOL_VERSION in reactApp/backend/nanoLink/protocol.js.
PROTOCOL_VERSION = 1

QUEUE_SIZE = 50             # Oldest messages are dropped past this
REQUEST_TIMEOUT_S = 1.0     # The backend is on the same machine; anything slower means it's down
RESYNC_INTERVAL_S = 30.0    # Re-send latest state/expression when idle (covers backend restarts)


class RobotState(StrEnum):
    """Robot states understood by the face screen."""
    SLEEPING = "sleeping"
    ACTIVE = "active"


class Expression(StrEnum):
    """Face expressions. Must match the names in reactApp/frontend/src/face/expressions.js."""
    NEUTRAL = "Neutral"
    HAPPY = "Happy"
    SURPRISED = "Surprised"
    BLINK = "Blink"
    THINKING = "Thinking"


class WebAppEvents:
    """Posts face events to the web app from a background thread.

    Call ``close()`` on shutdown to flush pending messages and stop the thread.
    """

    def __init__(self, url: str, token: str) -> None:
        self._url = url
        self._token = token
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=QUEUE_SIZE)
        # Latest message per type, re-sent on resync.
        self._latest: dict[str, dict[str, Any]] = {}
        self._latest_lock = threading.Lock()
        # Only log when reachability changes, not on every failed post.
        self._online = True
        # Bypass any system HTTP proxy; the backend is always local.
        self._opener = request.build_opener(request.ProxyHandler({}))

        self._thread = threading.Thread(target=self._run, name="WebAppEvents", daemon=True)
        self._thread.start()

    def send_state(self, state: RobotState) -> None:
        """Tell the face the robot is sleeping or active."""
        self._send("robot.state", {"state": str(state)})

    def send_expression(self, expression: Expression) -> None:
        """Show an expression on the face until the next state change."""
        self._send("robot.expression", {"name": str(expression)})

    def close(self, timeout: float = 2.0) -> None:
        """Flush queued messages (best effort) and stop the background thread."""
        self._enqueue(None)
        self._thread.join(timeout)

    def _send(self, message_type: str, payload: dict[str, Any]) -> None:
        message = {"type": message_type, "payload": payload}
        with self._latest_lock:
            self._latest[message_type] = message
        self._enqueue(message)

    def _enqueue(self, item: dict[str, Any] | None) -> None:
        """Queue without blocking, dropping the oldest message if the queue is full."""
        while True:
            try:
                self._queue.put_nowait(item)
                return
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass

    def _run(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=RESYNC_INTERVAL_S)
            except queue.Empty:
                self._resync()
                continue
            if item is None:
                return
            self._post(item)

    def _resync(self) -> None:
        # State first: on the face, a state change clears the expression.
        with self._latest_lock:
            pending = [self._latest.get(t) for t in ("robot.state", "robot.expression")]
        for message in pending:
            if message is not None:
                self._post(message)

    def _post(self, message: dict[str, Any]) -> None:
        # Fresh id/ts per post, so resyncs aren't mistaken for duplicates.
        envelope = {
            "v": PROTOCOL_VERSION,
            "id": str(uuid.uuid4()),
            "ts": int(time.time() * 1000),
            **message,
        }
        try:
            req = request.Request(
                self._url,
                data=json.dumps(envelope).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
            )
            with self._opener.open(req, timeout=REQUEST_TIMEOUT_S) as response:
                response.read()
            self._mark_online()
        except error.HTTPError as http_error:
            # The backend is up but refused the message: a config problem (token) or a bug, so always log it.
            self._mark_online()
            detail = http_error.read().decode("utf-8", errors="replace")
            print(f"[WebApp] {message['type']} rejected ({http_error.code}): {detail}")
        except (error.URLError, OSError) as connection_error:
            reason = getattr(connection_error, "reason", connection_error)
            self._mark_offline(f"Can't reach {self._url} ({reason})")
        except Exception as unexpected:
            # e.g. a malformed URL in the config; keep the thread alive so the robot is unaffected.
            self._mark_offline(f"Couldn't send to {self._url!r}: {unexpected!r}")

    def _mark_online(self) -> None:
        if not self._online:
            print(f"[WebApp] Reconnected to {self._url}")
            self._online = True

    def _mark_offline(self, reason: str) -> None:
        if self._online:
            print(f"[WebApp] {reason}; face events are dropped until it's back.")
            self._online = False


class DisabledWebAppEvents:
    """Stand-in when the web app link is turned off, so callers don't need ``if`` checks."""

    def send_state(self, state: RobotState) -> None:
        pass

    def send_expression(self, expression: Expression) -> None:
        pass

    def close(self, timeout: float = 2.0) -> None:
        pass
