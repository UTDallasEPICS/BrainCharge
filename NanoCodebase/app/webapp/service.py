"""Face events + settings bridge for the BrainCharge web app.

Two directions, both HTTP to the local Node backend (stdlib urllib only):

Outbound (Nano → webapp)
  Queue ``robot.state`` / ``robot.expression``, POST ``/api/nano/event``.
  The backend relays those to the face UI over SSE. Never blocks the
  orchestrator; a background thread owns the HTTP.

Inbound (webapp → Nano)
  Poll ``GET /api/nano/inbox`` for queued UI messages (e.g. ``ui.settings``).
  After handling, POST ``link.ack`` on the same event URL (stored by the
  backend for status; not broadcast on the face SSE).

Envelope shape matches reactApp/backend/nanoLink/protocol.js:
  ``{ v, id, ts, type, payload }``.

Language changes from the UI are stored and logged only — applying a new
language still requires restarting Nano (no hot-reload here).

Wire-up (from main / composition root when ready)::

    from app.webapp import WebAppEvents, DisabledWebAppEvents
    cfg = config.get("webapp") or {}
    webapp = (
        WebAppEvents(
            url=cfg["url"],
            token=cfg["token"],
            inbox_url=cfg.get("inbox_url", ""),
            settings_url=cfg.get("settings_url", ""),
            poll_interval_s=cfg.get("poll_interval_s", 2.0),
            initial_language=config.get("language", "en"),
        )
        if cfg.get("enabled")
        else DisabledWebAppEvents()
    )
    webapp.sync_settings_from_server()
"""
import json
import queue
import threading
import time
import uuid
from enum import StrEnum
from typing import Any, Callable
from urllib import error, request

# Must match PROTOCOL_VERSION in reactApp/backend/nanoLink/protocol.js.
PROTOCOL_VERSION = 1

QUEUE_SIZE = 50              # Outbound queue: drop oldest when full
REQUEST_TIMEOUT_S = 1.0      # Local backend; slower usually means it's down
RESYNC_INTERVAL_S = 30.0     # Re-POST latest face state/expression when idle
DEFAULT_POLL_INTERVAL_S = 2.0  # How often to drain /api/nano/inbox


class RobotState(StrEnum):
    """Robot states understood by the face screen."""
    SLEEPING = "sleeping"
    ACTIVE = "active"


class Expression(StrEnum):
    """Face expressions. Must match reactApp/frontend/src/face/expressions.js."""
    NEUTRAL = "Neutral"
    HAPPY = "Happy"
    SURPRISED = "Surprised"
    ANGRY = "Angry"
    CONTEMPT = "Contempt"
    DISGUST = "Disgust"
    FEAR = "Fear"
    SAD = "Sad"
    BLINK = "Blink"
    THINKING = "Thinking"


class WebAppEvents:
    """Bidirectional link to the webapp backend.

    Threads
      * ``WebAppEvents`` — drains the outbound face-event queue and POSTs.
      * ``WebAppInbox``  — optional; polls the inbox when ``inbox_url`` is set.

    Both are daemons. Call ``close()`` on shutdown if you need a clean stop.
    """

    def __init__(
        self,
        url: str,
        token: str,
        *,
        inbox_url: str = "",
        settings_url: str = "",
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        initial_language: str = "",
    ) -> None:
        # url = POST /api/nano/event (face events + link.ack)
        self._url = url
        self._token = token
        # inbox_url empty → no poll thread (outbound-only, old behavior)
        self._inbox_url = inbox_url.strip()
        self._settings_url = settings_url.strip()
        self._poll_interval_s = max(0.5, float(poll_interval_s))
        # Compared to ui.settings.language so we can warn without hot-reloading.
        self._initial_language = initial_language

        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=QUEUE_SIZE)
        # Latest face message per type — re-sent on idle so a restarted UI resyncs.
        self._latest: dict[str, dict[str, Any]] = {}
        self._latest_lock = threading.Lock()
        # Log connect/disconnect once, not on every failed request.
        self._online = True
        # Backend is always local; ignore any system HTTP proxy.
        self._opener = request.build_opener(request.ProxyHandler({}))

        # Last ui.settings payload (and future applied fields).
        self._settings: dict[str, Any] = {}
        self._settings_lock = threading.Lock()
        # Inbox dispatch table — extend with webapp.on("ui.wake", ...) later.
        self._handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            "ui.settings": self._handle_settings,
        }

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="WebAppEvents", daemon=True)
        self._thread.start()

        self._poll_thread: threading.Thread | None = None
        if self._inbox_url:
            self._poll_thread = threading.Thread(
                target=self._poll_loop, name="WebAppInbox", daemon=True
            )
            self._poll_thread.start()

    # --- public API ---------------------------------------------------------

    @property
    def settings(self) -> dict[str, Any]:
        """Copy of the latest settings received from the webapp."""
        with self._settings_lock:
            return dict(self._settings)

    def on(self, message_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register (or replace) a handler for an inbox ``type`` string."""
        self._handlers[message_type] = handler

    def send_state(self, state: RobotState) -> None:
        """Tell the face the robot is sleeping or active."""
        self._send("robot.state", {"state": str(state)})

    def send_expression(self, expression: Expression) -> None:
        """Show an expression on the face until the next state change."""
        self._send("robot.expression", {"name": str(expression)})

    def sync_settings_from_server(self) -> dict[str, Any] | None:
        """One-shot ``GET /api/settings`` (e.g. at process start).

        Returns the applied settings dict, or None if the URL is unset / unreachable
        / nothing has been saved in the webapp yet.
        """
        if not self._settings_url:
            return None
        data = self._http_json("GET", self._settings_url)
        if not isinstance(data, dict):
            return None
        saved = data.get("settings")
        if not isinstance(saved, dict):
            return None
        self._apply_settings(saved, source="startup GET")
        return self.settings

    def close(self, timeout: float = 2.0) -> None:
        """Stop poll + outbound threads (best effort)."""
        self._stop.set()
        self._enqueue(None)  # wake the outbound worker so it can exit
        self._thread.join(timeout)
        if self._poll_thread is not None:
            self._poll_thread.join(timeout)

    # --- outbound face queue ------------------------------------------------

    def _send(self, message_type: str, payload: dict[str, Any]) -> None:
        """Remember as latest-of-type and enqueue for POST."""
        message = {"type": message_type, "payload": payload}
        with self._latest_lock:
            self._latest[message_type] = message
        self._enqueue(message)

    def _enqueue(self, item: dict[str, Any] | None) -> None:
        """Non-blocking put; if full, drop the oldest queued item and retry."""
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
        """Outbound worker: POST queued face events; on idle timeout, resync."""
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=RESYNC_INTERVAL_S)
            except queue.Empty:
                self._resync()
                continue
            if item is None:
                return
            self._post(item)

    def _resync(self) -> None:
        """Re-POST latest state then expression (state first clears expression on the face)."""
        with self._latest_lock:
            pending = [self._latest.get(t) for t in ("robot.state", "robot.expression")]
        for message in pending:
            if message is not None:
                self._post(message)

    # --- inbound inbox poll -------------------------------------------------

    def _poll_loop(self) -> None:
        """Sleep ``poll_interval_s``, then drain the inbox; exit when ``close()`` sets stop."""
        while not self._stop.wait(self._poll_interval_s):
            self._poll_inbox_once()

    def _poll_inbox_once(self) -> None:
        """GET inbox, dispatch each message, ack success/failure/unknown type."""
        data = self._http_json("GET", self._inbox_url)
        if not isinstance(data, dict):
            return
        messages = data.get("messages")
        if not isinstance(messages, list):
            return
        for raw in messages:
            if not isinstance(raw, dict):
                continue
            message_type = raw.get("type")
            payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
            message_id = raw.get("id") if isinstance(raw.get("id"), str) else ""
            if not isinstance(message_type, str) or not message_type:
                continue
            handler = self._handlers.get(message_type)
            try:
                if handler is None:
                    # Still ack so the UI/backend know we saw it and chose to ignore.
                    print(f"[WebApp] Ignoring unknown inbox type {message_type!r}")
                    self._ack(message_id, message_type, ok=True, detail="ignored")
                    continue
                handler(payload)
                self._ack(message_id, message_type, ok=True)
            except Exception as exc:
                print(f"[WebApp] Handler for {message_type!r} failed: {exc!r}")
                self._ack(message_id, message_type, ok=False, detail=str(exc))

    def _handle_settings(self, payload: dict[str, Any]) -> None:
        """Inbox handler for ``ui.settings``."""
        self._apply_settings(payload, source="inbox")

    def _apply_settings(self, payload: dict[str, Any], *, source: str) -> None:
        """Store settings and log notable fields.

        Does **not** hot-swap language packs / Piper / Vosk — that still needs a restart.
        Other fields (e.g. companionName) are kept in ``self.settings`` for callers.
        """
        with self._settings_lock:
            self._settings = dict(payload)

        companion = payload.get("companionName")
        if isinstance(companion, str) and companion.strip():
            print(f"[WebApp] Settings ({source}): companionName={companion.strip()!r}")

        language = payload.get("language")
        if isinstance(language, str) and language.strip():
            lang = language.strip()
            if self._initial_language and lang != self._initial_language:
                print(
                    f"[WebApp] Settings ({source}): language={lang!r} "
                    f"(runtime language is {self._initial_language!r}; "
                    "restart Nano to apply language)"
                )
            else:
                print(f"[WebApp] Settings ({source}): language={lang!r}")

        print(f"[WebApp] Settings snapshot ({source}): {json.dumps(payload, default=str)}")

    def _ack(
        self,
        ref: str,
        message_type: str,
        *,
        ok: bool,
        detail: str = "",
    ) -> None:
        """POST ``link.ack`` so the backend can show status (not sent to the face SSE)."""
        payload: dict[str, Any] = {"ok": ok, "type": message_type}
        if ref:
            payload["ref"] = ref
        if detail:
            payload["detail"] = detail
        self._post({"type": "link.ack", "payload": payload})

    # --- HTTP helpers -------------------------------------------------------

    def _post(self, message: dict[str, Any]) -> None:
        """POST one envelope to ``/api/nano/event`` (face types or link.ack)."""
        # Fresh id/ts per attempt so resyncs / retries are not treated as duplicates.
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
            # Reachable but rejected (bad token / unknown type) — always log.
            self._mark_online()
            detail = http_error.read().decode("utf-8", errors="replace")
            print(f"[WebApp] {message['type']} rejected ({http_error.code}): {detail}")
        except (error.URLError, OSError) as connection_error:
            reason = getattr(connection_error, "reason", connection_error)
            self._mark_offline(f"Can't reach {self._url} ({reason})")
        except Exception as unexpected:
            # Keep the thread alive so a bad URL cannot take down the robot.
            self._mark_offline(f"Couldn't send to {self._url!r}: {unexpected!r}")

    def _http_json(self, method: str, url: str) -> Any | None:
        """Authenticated JSON GET/etc. for inbox and settings. Returns parsed body or None."""
        try:
            req = request.Request(
                url,
                method=method,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            with self._opener.open(req, timeout=REQUEST_TIMEOUT_S) as response:
                body = response.read().decode("utf-8")
            self._mark_online()
            return json.loads(body) if body else None
        except error.HTTPError as http_error:
            self._mark_online()
            detail = http_error.read().decode("utf-8", errors="replace")
            print(f"[WebApp] {method} {url} rejected ({http_error.code}): {detail}")
            return None
        except (error.URLError, OSError) as connection_error:
            reason = getattr(connection_error, "reason", connection_error)
            self._mark_offline(f"Can't reach {url} ({reason})")
            return None
        except Exception as unexpected:
            self._mark_offline(f"Couldn't {method} {url!r}: {unexpected!r}")
            return None

    def _mark_online(self) -> None:
        if not self._online:
            print(f"[WebApp] Reconnected to {self._url}")
            self._online = True

    def _mark_offline(self, reason: str) -> None:
        if self._online:
            print(f"[WebApp] {reason}; face events / inbox poll paused until it's back.")
            self._online = False


class DisabledWebAppEvents:
    """No-op stand-in when ``webapp.enabled`` is false — callers skip ``if`` checks."""

    @property
    def settings(self) -> dict[str, Any]:
        return {}

    def on(self, message_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        pass

    def send_state(self, state: RobotState) -> None:
        pass

    def send_expression(self, expression: Expression) -> None:
        pass

    def sync_settings_from_server(self) -> dict[str, Any] | None:
        return None

    def close(self, timeout: float = 2.0) -> None:
        pass
