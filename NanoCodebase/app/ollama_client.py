"""Small, local-only Ollama adapter using the Python standard library."""

from __future__ import annotations

import http.client
import json
import math
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class OllamaError(RuntimeError):
    """An actionable error that can be shown in the terminal."""


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A local endpoint must never redirect a prompt to another server.
        return None


class OllamaClient:
    def __init__(
        self,
        model: str = "gemma3n:e4b",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama must use a local HTTP address on localhost, 127.0.0.1, or ::1.")
        port = parsed.port
        if port is not None and port == 0:
            raise ValueError("Ollama port must be between 1 and 65535.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be a finite number greater than zero.")
        model = model.strip()
        if not model or "cloud" in model.casefold():
            raise ValueError("Choose a downloaded local model, such as gemma3n:e4b.")

        # Pin localhost to a loopback IP and ignore system proxies entirely.
        host = "[::1]" if parsed.hostname == "::1" else "127.0.0.1"
        self.base_url = f"http://{host}:{port or 11434}"
        self.model = model
        self.timeout = timeout
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())

    def _post(self, endpoint: str, payload: dict) -> dict:
        request = Request(
            self.base_url + endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as error:
            error.close()
            if error.code == 404:
                raise OllamaError(
                    f"Local model '{self.model}' is unavailable. Install it first with "
                    f"'ollama pull {self.model}', or choose an installed model with --model."
                ) from error
            raise OllamaError(f"Local Ollama returned HTTP {error.code}; check its server logs.") from error
        except (TimeoutError, socket.timeout) as error:
            raise OllamaError("Local Ollama timed out. Try again or increase --timeout.") from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise OllamaError("Local Ollama timed out. Try again or increase --timeout.") from error
            raise OllamaError(
                f"Cannot reach local Ollama at {self.base_url}. Start Ollama, then try again."
            ) from error
        except (OSError, http.client.HTTPException) as error:
            raise OllamaError("The connection to local Ollama was interrupted. Try again.") from error
        except (ValueError, UnicodeError) as error:
            raise OllamaError("Local Ollama returned invalid JSON.") from error

        if not isinstance(result, dict):
            raise OllamaError("Local Ollama returned an unexpected response.")
        if result.get("error"):
            raise OllamaError("Local Ollama reported an error; check its server logs.")
        return result

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        # Inspect before sending any conversation text: local Ollama can also
        # expose cloud-backed models, including models with custom aliases.
        metadata = self._post("/api/show", {"model": self.model})
        if metadata.get("remote_host") or metadata.get("remote_model"):
            raise OllamaError("This model uses a remote service. Choose a downloaded local model.")
        details = metadata.get("details")
        if not isinstance(details, dict) or not details.get("format"):
            raise OllamaError("Could not verify local model files. Choose a downloaded local model.")

        payload = {"model": self.model, "messages": messages, "stream": False}
        if json_mode:
            payload["format"] = "json"
        result = self._post("/api/chat", payload)
        message = result.get("message")
        if (
            result.get("done") is not True
            or not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or not message["content"].strip()
        ):
            raise OllamaError("Local Ollama did not return a complete text reply. Try again.")
        return message["content"].strip()
