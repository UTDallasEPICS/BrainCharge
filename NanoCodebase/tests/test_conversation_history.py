"""Durability, context boundaries, and failure handling for Phase 2."""

import io
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.conversation import SYSTEM_PROMPT, ConversationService
from app.conversation_store import ConversationStore
from app.ollama_client import OllamaError
from terminal_chat import run_chat


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "nested" / "history.sqlite3"
        self.store = ConversationStore(self.path)
        self.addCleanup(self.store.close)
        self.client = MagicMock()
        self.client.chat.return_value = "Reply"
        self.service = ConversationService(self.client, self.store)
        self.conversation_id = self.service.start_conversation()

    def test_messages_are_committed_before_model_call_and_before_return(self):
        def check_saved_input(messages):
            observer = ConversationStore(self.path)
            try:
                saved = observer.get_messages(self.conversation_id)
                self.assertEqual([(m["role"], m["content"], m["status"]) for m in saved],
                                 [("user", "Hello", "pending")])
            finally:
                observer.close()
            return "Hi!"
        self.client.chat.side_effect = check_saved_input
        self.assertEqual(self.service.respond(self.conversation_id, "Hello"), "Hi!")
        observer = ConversationStore(self.path)
        try:
            messages = observer.get_messages(self.conversation_id)
            self.assertEqual([m["content"] for m in messages], ["Hello", "Hi!"])
            self.assertTrue(all(m["status"] == "completed" for m in messages))
        finally:
            observer.close()

    def test_new_conversation_closes_previous_and_isolates_context(self):
        self.service.respond(self.conversation_id, "Old detail")
        new_id = self.service.start_conversation(previous_id=self.conversation_id)
        self.service.respond(new_id, "New question")
        messages = self.client.chat.call_args.args[0]
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertNotIn("Old detail", str(messages))
        self.assertEqual(len(self.service.get_history(self.conversation_id)), 2)
        previous = next(c for c in self.service.list_conversations() if c["id"] == self.conversation_id)
        self.assertIsNotNone(previous["ended_at"])
        with self.assertRaises(ValueError):
            self.service.respond(self.conversation_id, "Closed")

    def test_budget_keeps_latest_complete_pairs_and_full_history(self):
        self.service.respond(self.conversation_id, "old")
        self.service.respond(self.conversation_id, "recent")
        budget = len(SYSTEM_PROMPT) + len("recentReplynow")
        limited = ConversationService(self.client, self.store, context_chars=budget)
        limited.respond(self.conversation_id, "now")
        messages = self.client.chat.call_args.args[0]
        self.assertEqual([m["content"] for m in messages[1:]], ["recent", "Reply", "now"])
        self.assertLessEqual(sum(len(m["content"]) for m in messages), budget)
        self.assertEqual(len(self.service.get_history(self.conversation_id)), 6)

    def test_small_budget_keeps_system_and_full_current_input(self):
        self.service.respond(self.conversation_id, "Previous")
        limited = ConversationService(self.client, self.store, context_chars=len(SYSTEM_PROMPT) + 3)
        limited.respond(self.conversation_id, "now")
        messages = self.client.chat.call_args.args[0]
        self.assertEqual(messages, [{"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": "now"}])
        count = len(self.service.get_history(self.conversation_id))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            limited.respond(self.conversation_id, "too long")
        self.assertEqual(len(self.service.get_history(self.conversation_id)), count)
        with self.assertRaises(ValueError):
            ConversationService(self.client, self.store, context_chars=0)

    def test_failed_turn_is_visible_but_excluded_from_followup_context(self):
        self.client.chat.side_effect = ["First reply", OllamaError("unavailable"), "Next reply"]
        self.service.respond(self.conversation_id, "First")
        with self.assertRaises(OllamaError):
            self.service.respond(self.conversation_id, "Failed input")
        self.service.respond(self.conversation_id, "Next")
        messages = self.client.chat.call_args.args[0]
        self.assertEqual([m["content"] for m in messages[1:]], ["First", "First reply", "Next"])
        history = self.service.get_history(self.conversation_id)
        self.assertEqual(len(history), 5)
        self.assertEqual(history[2]["status"], "failed")
        self.assertEqual(history[2]["content"], "Failed input")

    def test_interrupt_preserves_input_and_closes_terminal_conversation(self):
        self.client.chat.side_effect = KeyboardInterrupt
        with patch("builtins.input", return_value="Keep this"), redirect_stdout(io.StringIO()):
            self.assertEqual(run_chat(self.service), 0)
        conversation = self.service.list_conversations()[0]
        self.assertIsNotNone(conversation["ended_at"])
        history = self.service.get_history(conversation["id"])
        self.assertEqual([(m["content"], m["status"]) for m in history], [("Keep this", "interrupted")])

    def test_history_commands_do_not_call_the_model_or_change_context(self):
        self.service.respond(self.conversation_id, "Saved")
        self.client.chat.reset_mock()
        with patch("builtins.input", side_effect=["/history", f"/history\t{self.conversation_id}",
                                                "/history bad", "/history 999", "/history -1",
                                                "/history 999999999999999999999999", "/exit"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run_chat(self.service), 0)
        self.client.chat.assert_not_called()
        self.assertIn("You: Saved", output.getvalue())
        self.assertIn("Supply a conversation ID", output.getvalue())
        self.assertIn("does not exist", output.getvalue())
        self.assertEqual(output.getvalue().count("valid conversation ID"), 2)

    def test_storage_failure_prevents_inference(self):
        with patch.object(self.store, "add_user_message", side_effect=sqlite3.OperationalError("disk full")):
            with patch("builtins.input", return_value="Cannot save"), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(run_chat(self.service), 1)
        self.client.chat.assert_not_called()
        self.assertIn("History storage error", output.getvalue())

    def test_partial_assistant_write_rolls_back_turn_completion(self):
        message_id = self.store.add_user_message(self.conversation_id, "Save atomically")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.complete_turn(message_id, None)
        history = self.store.get_messages(self.conversation_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "pending")
        self.store.end_conversation(self.conversation_id)
        self.assertEqual(self.store.get_messages(self.conversation_id)[0]["status"], "interrupted")

    def test_abrupt_process_exit_preserves_committed_input(self):
        script = (
            "import os, sys; from pathlib import Path; "
            "from app.conversation_store import ConversationStore; "
            "store = ConversationStore(Path(sys.argv[1])); "
            "cid = store.start_conversation(); "
            "store.add_user_message(cid, 'Before crash'); os._exit(0)"
        )
        result = subprocess.run([sys.executable, "-c", script, str(self.path)],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        unfinished = self.store.list_conversations()[0]
        self.assertIsNone(unfinished["ended_at"])
        messages = self.store.get_messages(unfinished["id"])
        self.assertEqual([(m["content"], m["status"]) for m in messages], [("Before crash", "pending")])
        new_id = self.service.start_conversation()
        self.service.respond(new_id, "After restart")
        self.assertEqual(len(self.client.chat.call_args.args[0]), 2)


if __name__ == "__main__":
    unittest.main()
