"""Terminal and local adapter checks without installed models or robot dependencies."""

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from app.conversation import ConversationService
from app.conversation_store import ConversationStore
from app.ollama_client import OllamaClient, OllamaError
from terminal_chat import run_chat


class OllamaClientTests(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient()
        self.local_model = {"details": {"format": "gguf"}}
        self.reply = {"done": True, "message": {"role": "assistant", "content": "Hello!"}}

    def response(self, body):
        context = MagicMock()
        context.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
        return context

    def test_chat_checks_local_model_then_sends_nonstreaming_request(self):
        with patch.object(self.client._opener, "open", side_effect=[
            self.response(self.local_model), self.response(self.reply)
        ]) as opened:
            self.assertEqual(self.client.chat([{"role": "user", "content": "Hi"}]), "Hello!")
        self.assertEqual(opened.call_args_list[0].args[0].full_url, "http://127.0.0.1:11434/api/show")
        request = opened.call_args_list[1].args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(json.loads(request.data), {
            "model": "gemma3n:e4b", "stream": False,
            "messages": [{"role": "user", "content": "Hi"}],
        })

    def test_rejects_external_hosts_cloud_models_and_invalid_timeouts(self):
        for host in ["https://ollama.com", "http://example.com", "http://127.0.0.1.evil.test",
                     "http://user@localhost", "http://localhost/api", "http://localhost:0"]:
            with self.subTest(host=host), self.assertRaises(ValueError):
                OllamaClient(base_url=host)
        for timeout in [0, -1, float("nan"), float("inf")]:
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                OllamaClient(timeout=timeout)
        with self.assertRaises(ValueError):
            OllamaClient(model="gpt-oss:120b-cloud")

    def test_json_mode_uses_same_local_adapter(self):
        with patch.object(self.client._opener, "open", side_effect=[
            self.response(self.local_model), self.response(self.reply)
        ]) as opened:
            self.client.chat([{"role": "user", "content": "Summarize"}], json_mode=True)
        self.assertEqual(json.loads(opened.call_args.args[0].data)["format"], "json")

    def test_accepts_and_pins_loopback_hosts(self):
        self.assertEqual(OllamaClient(base_url="http://localhost:1234/").base_url, "http://127.0.0.1:1234")
        self.assertEqual(OllamaClient(base_url="http://[::1]:1234").base_url, "http://[::1]:1234")

    def test_cloud_alias_and_unverifiable_metadata_never_receive_prompt(self):
        for metadata in [{"remote_host": "https://ollama.com"}, {"remote_model": "remote"}, {}]:
            with self.subTest(metadata=metadata), patch.object(
                self.client._opener, "open", return_value=self.response(metadata)
            ) as opened, self.assertRaises(OllamaError):
                self.client.chat([{"role": "user", "content": "private"}])
            self.assertEqual(opened.call_count, 1)

    def test_connection_timeout_and_missing_model_are_actionable(self):
        for error, expected in [
            (URLError(ConnectionRefusedError()), "Start Ollama"),
            (socket.timeout(), "timed out"),
            (URLError(socket.timeout()), "timed out"),
            (HTTPError("local", 404, "missing", {}, None), "ollama pull"),
            (HTTPError("local", 500, "failed", {}, None), "HTTP 500"),
            (HTTPError("local", 307, "redirect", {}, None), "HTTP 307"),
        ]:
            with self.subTest(error=error), patch.object(self.client._opener, "open", side_effect=error):
                with self.assertRaisesRegex(OllamaError, expected):
                    self.client.chat([])

    def test_invalid_json_and_empty_or_incomplete_replies(self):
        for body in [[], {"error": "failed"}, {"done": False, "message": {"content": "partial"}},
                     {"done": True, "message": {"role": "assistant", "content": " "}}]:
            with self.subTest(body=body), patch.object(self.client._opener, "open", side_effect=[
                self.response(self.local_model), self.response(body)
            ]), self.assertRaises(OllamaError):
                self.client.chat([])
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(b"not json")
        with patch.object(self.client._opener, "open", return_value=response):
            with self.assertRaisesRegex(OllamaError, "invalid JSON"):
                self.client.chat([])


class ConversationTests(unittest.TestCase):
    def test_recent_turns_are_included_and_blank_input_is_rejected(self):
        client = MagicMock()
        client.chat.return_value = "Reply"
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = ConversationStore(Path(temporary.name) / "history.sqlite3")
        self.addCleanup(store.close)
        service = ConversationService(client, store)
        conversation_id = service.start_conversation()
        service.respond(conversation_id, " First ")
        service.respond(conversation_id, "Second")
        messages = client.chat.call_args.args[0]
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "user"])
        self.assertEqual(messages[-1]["content"], "Second")
        self.assertEqual(messages[1]["content"], "First")
        with self.assertRaises(ValueError):
            service.respond(conversation_id, " ")
        self.assertEqual(client.chat.call_count, 2)

    def test_terminal_ignores_blank_and_commands_and_recovers_after_error(self):
        service = MagicMock()
        service.respond.side_effect = [OllamaError("Start Ollama"), "Hello!"]
        output = io.StringIO()
        with patch("builtins.input", side_effect=[" ", "/history", "Hi", "Again", "/exit"]), redirect_stdout(output):
            run_chat(service)
        self.assertEqual(service.respond.call_count, 2)
        self.assertIn("Error: Start Ollama", output.getvalue())
        self.assertIn("BrainCharge: Hello!", output.getvalue())
        self.assertIn("Goodbye.", output.getvalue())

    def test_eof_and_interrupt_exit_cleanly_including_during_generation(self):
        for signal in [EOFError, KeyboardInterrupt]:
            with self.subTest(signal=signal), patch("builtins.input", side_effect=signal), redirect_stdout(io.StringIO()) as output:
                run_chat(MagicMock())
            self.assertIn("Goodbye.", output.getvalue())
        service = MagicMock()
        service.respond.side_effect = KeyboardInterrupt
        with patch("builtins.input", return_value="Hi"), redirect_stdout(io.StringIO()) as output:
            run_chat(service)
        self.assertIn("Goodbye.", output.getvalue())


class LocalHTTPTests(unittest.TestCase):
    """Exercise the actual HTTP adapter and terminal without external services."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "history.sqlite3"
        self.requests = []
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, payload))
                if payload["model"] == "redirect":
                    self.send_response(307)
                    self.send_header("Location", "/redirected")
                    self.end_headers()
                    return
                if self.path == "/api/show":
                    body = {"details": {"format": "gguf"}}
                    if payload["model"] == "remote-alias":
                        body["remote_host"] = "https://ollama.com"
                else:
                    content = "Local reply."
                    if payload.get("format") == "json":
                        source = json.loads(payload["messages"][-1]["content"])
                        facts = [source["previous_summary"]] if source["previous_summary"] else []
                        facts.extend(m["content"] for m in source["messages"] if m["role"] == "user")
                        content = json.dumps({"summary": "; ".join(facts) or "The user chatted."})
                    body = {"done": True, "message": {"role": "assistant", "content": content}}
                encoded = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_terminal_works_with_only_local_server_and_ignores_proxies(self):
        env = dict(os.environ, HTTP_PROXY="http://127.0.0.1:1", http_proxy="http://127.0.0.1:1",
                   ALL_PROXY="http://127.0.0.1:1", NO_PROXY="", no_proxy="")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / "terminal_chat.py"),
             "--host", self.host, "--model", "local-test", "--database", str(self.database)],
            input="\nHi\n/exit\n", text=True, capture_output=True, timeout=10, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BrainCharge: Local reply.", result.stdout)
        self.assertIn("Goodbye.", result.stdout)
        self.assertEqual([path for path, _ in self.requests], ["/api/show", "/api/chat"] * 2)
        self.assertEqual(self.requests[1][1]["messages"][-1], {"role": "user", "content": "Hi"})

    def test_followups_new_conversation_and_history_across_launches(self):
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "terminal_chat.py"),
                   "--host", self.host, "--model", "local-test", "--database", str(self.database)]
        first = subprocess.run(command, input="My name is Ari\nWhat is my name?\n/new\nFresh start\n/history 1\n/exit\n",
                               text=True, capture_output=True, timeout=10)
        self.assertEqual(first.returncode, 0, first.stderr)
        prompts = [body["messages"] for path, body in self.requests
                   if path == "/api/chat" and body.get("format") != "json"]
        self.assertEqual(prompts[1][1]["content"], "My name is Ari")
        self.assertEqual([m["role"] for m in prompts[1]], ["system", "user", "assistant", "user"])
        self.assertEqual([m["role"] for m in prompts[2]], ["system", "user"])
        self.assertIn("My name is Ari", prompts[2][0]["content"])
        self.assertIn("You: My name is Ari", first.stdout)
        self.requests.clear()
        second = subprocess.run(command, input="/history\n/history 1\n/summary 1\nNew launch\n/exit\n",
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("You: My name is Ari", second.stdout)
        self.assertIn("#1 |", second.stdout)
        self.assertIn("Started conversation #3", second.stdout)
        self.assertIn("Summary for conversation #1: My name is Ari", second.stdout)
        prompt = next(body["messages"] for path, body in self.requests
                      if path == "/api/chat" and body.get("format") != "json")
        self.assertEqual([m["role"] for m in prompt], ["system", "user"])
        self.assertIn("My name is Ari", prompt[0]["content"])
        store = ConversationStore(self.database)
        try:
            self.assertTrue(all(c["ended_at"] for c in store.list_conversations()))
        finally:
            store.close()

    def test_redirect_is_not_followed(self):
        client = OllamaClient(model="redirect", base_url=self.host)
        with self.assertRaisesRegex(OllamaError, "HTTP 307"):
            client.chat([{"role": "user", "content": "private"}])
        self.assertEqual([path for path, _ in self.requests], ["/api/show"])

    def test_cloud_alias_is_rejected_before_prompt_is_sent(self):
        client = OllamaClient(model="remote-alias", base_url=self.host)
        with self.assertRaisesRegex(OllamaError, "remote service"):
            client.chat([{"role": "user", "content": "private"}])
        self.assertEqual(self.requests, [("/api/show", {"model": "remote-alias"})])


if __name__ == "__main__":
    unittest.main()
