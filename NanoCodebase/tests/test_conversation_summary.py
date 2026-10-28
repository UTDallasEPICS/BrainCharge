"""Summary continuity, bounded inputs, source provenance, and resumable failures."""

import io
import json
import sqlite3
import tempfile
import unittest
from collections import defaultdict
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.conversation import ConversationService
from app.conversation_store import ConversationStore
from app.conversation_summary import ConversationSummarizer, SummaryError
from app.ollama_client import OllamaError
from terminal_chat import run_chat


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "history.sqlite3"
        self.store = ConversationStore(self.path)
        self.addCleanup(self.store.close)
        self.client = MagicMock()
        self.client.chat.side_effect = self.generate
        self.service = ConversationService(self.client, self.store)
        self.conversation_id = self.service.start_conversation()

    @staticmethod
    def generate(messages, *, json_mode=False):
        if json_mode:
            return json.dumps({"summary": "The user is Ari and prefers green."})
        return "Thanks for sharing."

    def seed_turn(self, text, reply="Reply", conversation_id=None):
        cid = conversation_id if conversation_id is not None else self.conversation_id
        message_id = self.store.add_user_message(cid, text)
        self.store.complete_turn(message_id, reply)

    def test_close_saves_summary_with_source_reference_and_new_chat_uses_it(self):
        self.service.respond(self.conversation_id, "My name is Ari and I prefer green")
        new_id = self.service.start_conversation(previous_id=self.conversation_id)
        state = self.store.get_summary(self.conversation_id)
        history = self.store.get_messages(self.conversation_id)
        self.assertEqual(state["content"], "The user is Ari and prefers green.")
        self.assertEqual(state["source_message_id"], history[-1]["id"])
        self.assertEqual(state["source_offset"], len(history[-1]["content"]))
        self.assertEqual(state["pending"], 0)
        self.service.respond(new_id, "What do you know about me?")
        messages = self.client.chat.call_args.args[0]
        self.assertIn("Ari", messages[0]["content"])
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertEqual(len(self.store.get_messages(self.conversation_id)), 2)

    def test_summary_survives_reopening_database(self):
        self.seed_turn("My name is Ari")
        self.service.end_conversation(self.conversation_id)
        observer = ConversationStore(self.path)
        try:
            service = ConversationService(self.client, observer)
            cid = service.start_conversation()
            service.respond(cid, "What is my name?")
            self.assertIn("Ari", self.client.chat.call_args.args[0][0]["content"])
        finally:
            observer.close()

    def test_rolling_summary_preserves_older_details_within_budget(self):
        self.seed_turn("My name is Ari. " + "early topic " * 25, "reply " * 35)
        self.seed_turn("A more recent topic " * 20, "recent reply " * 20)
        limited = ConversationService(self.client, self.store, context_chars=1500)
        limited.respond(self.conversation_id, "What was my name?")
        self.assertTrue(any(c.kwargs.get("json_mode") for c in self.client.chat.call_args_list))
        messages = self.client.chat.call_args.args[0]
        self.assertIn("The user is Ari", messages[0]["content"])
        self.assertLessEqual(sum(len(m["content"]) for m in messages), 1500)
        self.assertEqual(messages[-1]["content"], "What was my name?")
        self.assertEqual(len(self.store.get_messages(self.conversation_id)), 6)
        self.assertIsNotNone(self.store.get_summary(self.conversation_id)["source_message_id"])

    def test_oversized_messages_are_fully_processed_in_bounded_fragments(self):
        original = ('name \\"\n名字 ' * 180) + " final detail"
        self.seed_turn(original, "A long reply. " * 100)
        self.store.queue_summary(self.conversation_id)
        summarizer = ConversationSummarizer(self.client, self.store, 1100)
        summarizer.update(self.conversation_id)
        fragments = defaultdict(list)
        summary_calls = self.client.chat.call_args_list
        self.assertGreater(len(summary_calls), 2)
        for call in summary_calls:
            messages = call.args[0]
            self.assertTrue(call.kwargs["json_mode"])
            self.assertLessEqual(sum(len(m["content"]) for m in messages), 1100)
            source = json.loads(messages[-1]["content"])
            for fragment in source["messages"]:
                fragments[fragment["id"]].append(fragment)
        for message in self.store.get_messages(self.conversation_id):
            offset = 0
            for fragment in fragments[message["id"]]:
                self.assertEqual(fragment["offset"], offset)
                offset += len(fragment["content"])
            self.assertEqual("".join(f["content"] for f in fragments[message["id"]]), message["content"])
        self.assertEqual(self.store.get_summary(self.conversation_id)["pending"], 0)

    def test_failed_batch_resumes_at_saved_offset_on_next_launch(self):
        self.seed_turn("Important detail " * 120, "A reply")
        calls = []

        def fail_second_batch(messages, *, json_mode=False):
            calls.append(json.loads(messages[-1]["content"]))
            if len(calls) == 2:
                raise OllamaError("temporarily unavailable")
            return json.dumps({"summary": "Important detail."})

        self.client.chat.side_effect = fail_second_batch
        service = ConversationService(self.client, self.store, context_chars=1100)
        service.end_conversation(self.conversation_id)
        state = self.store.get_summary(self.conversation_id)
        self.assertEqual(state["content"], "Important detail.")
        self.assertGreater(state["source_offset"], 0)
        self.assertEqual(state["pending"], 1)
        self.assertIn("deferred", service.drain_notices()[0])
        resumed = []

        def finish(messages, *, json_mode=False):
            resumed.append(json.loads(messages[-1]["content"]))
            return json.dumps({"summary": "Important detail."})

        self.client.chat.side_effect = finish
        observer = ConversationStore(self.path)
        try:
            restarted = ConversationService(self.client, observer, context_chars=1100)
            restarted.start_conversation()
            self.assertEqual(resumed[0]["messages"][0]["offset"], state["source_offset"])
            self.assertEqual(resumed[0]["previous_summary"], "Important detail.")
            self.assertEqual(observer.get_summary(self.conversation_id)["pending"], 0)
        finally:
            observer.close()

    def test_invalid_summary_keeps_original_summary_and_pending_sources(self):
        self.seed_turn("My name is Ari")
        self.store.queue_summary(self.conversation_id)
        self.service.summarizer.update(self.conversation_id)
        original = self.store.get_summary(self.conversation_id)
        self.seed_turn("A new detail")
        self.store.queue_summary(self.conversation_id)
        for output in ["not JSON", "[]", '{}', '{"summary": 1}', '{"summary":" "}',
                       json.dumps({"summary": "x" * 1501})]:
            with self.subTest(output=output):
                self.client.chat.side_effect = None
                self.client.chat.return_value = output
                with self.assertRaises(SummaryError):
                    self.service.summarizer.update(self.conversation_id)
                state = self.store.get_summary(self.conversation_id)
                self.assertEqual(state["content"], original["content"])
                self.assertEqual(state["source_message_id"], original["source_message_id"])
                self.assertEqual(state["pending"], 1)
        self.assertEqual(len(self.store.get_messages(self.conversation_id)), 4)

    def test_failed_and_pending_messages_are_not_summarized(self):
        self.seed_turn("A completed turn")
        failed = self.store.add_user_message(self.conversation_id, "Failed input")
        self.store.fail_turn(failed)
        self.store.add_user_message(self.conversation_id, "Interrupted input")
        self.service.end_conversation(self.conversation_id)
        source = json.loads(self.client.chat.call_args.args[0][-1]["content"])
        self.assertEqual([m["content"] for m in source["messages"]], ["A completed turn", "Reply"])

    def test_model_failure_does_not_block_new_conversation(self):
        self.seed_turn("Saved detail")
        self.client.chat.side_effect = OllamaError("unavailable")
        new_id = self.service.start_conversation(previous_id=self.conversation_id)
        self.assertNotEqual(new_id, self.conversation_id)
        old = next(c for c in self.store.list_conversations() if c["id"] == self.conversation_id)
        self.assertIsNotNone(old["ended_at"])
        self.assertEqual(self.store.get_summary(self.conversation_id)["pending"], 1)
        self.assertTrue(self.service.drain_notices())

    def test_summary_failure_during_rolling_compaction_still_allows_reply(self):
        self.seed_turn("Old information " * 70, "reply " * 40)

        def fail_summary(messages, *, json_mode=False):
            if json_mode:
                raise OllamaError("summary unavailable")
            return "A normal reply"

        self.client.chat.side_effect = fail_summary
        limited = ConversationService(self.client, self.store, context_chars=1500)
        self.assertEqual(limited.respond(self.conversation_id, "Continue"), "A normal reply")
        self.assertEqual(self.store.get_summary(self.conversation_id)["pending"], 1)
        self.assertTrue(limited.drain_notices())
        self.assertLessEqual(sum(len(m["content"]) for m in self.client.chat.call_args.args[0]), 1500)

    def test_summary_job_is_not_repeated_without_new_messages(self):
        self.seed_turn("My name is Ari")
        self.service.end_conversation(self.conversation_id)
        self.client.chat.reset_mock()
        self.service.end_conversation(self.conversation_id)
        self.client.chat.assert_not_called()
        self.assertEqual(self.store.get_summary(self.conversation_id)["pending"], 0)

    def test_only_three_recent_summaries_are_selected_within_budget(self):
        for index in range(5):
            cid = self.store.start_conversation()
            self.seed_turn(f"Fact {index}", conversation_id=cid)
            self.store.end_conversation(cid)
            self.client.chat.side_effect = None
            self.client.chat.return_value = json.dumps({"summary": f"Remembered detail {index}."})
            self.service.summarizer.update(cid)
        self.client.chat.side_effect = self.generate
        self.service.respond(self.conversation_id, "What did we discuss?")
        messages = self.client.chat.call_args.args[0]
        self.assertNotIn("Remembered detail 0", messages[0]["content"])
        self.assertNotIn("Remembered detail 1", messages[0]["content"])
        self.assertIn("Remembered detail 4", messages[0]["content"])
        self.assertLessEqual(sum(len(m["content"]) for m in messages), self.service.context_chars)

    def test_summary_inspection_is_read_only_and_handles_invalid_ids(self):
        self.seed_turn("My name is Ari")
        self.service.end_conversation(self.conversation_id)
        self.client.chat.reset_mock()
        with patch("builtins.input", side_effect=["/summary", f"/summary {self.conversation_id}",
                                                "/summary bad", "/summary 999", "/exit"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run_chat(self.service), 0)
        self.client.chat.assert_not_called()
        self.assertIn("No summary saved yet", output.getvalue())
        self.assertIn("The user is Ari", output.getvalue())
        self.assertIn("does not exist", output.getvalue())

    def test_ctrl_c_during_exit_summary_is_clean_and_retryable(self):
        self.client.chat.side_effect = ["Reply", KeyboardInterrupt]
        with patch("builtins.input", side_effect=["Hello", "/exit"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run_chat(self.service), 0)
        closed = self.store.list_conversations()[0]
        self.assertIsNotNone(closed["ended_at"])
        self.assertEqual(self.store.get_summary(closed["id"])["pending"], 1)
        self.assertIn("update interrupted", output.getvalue())

    def test_phase_two_database_is_backfilled_without_changing_transcripts(self):
        self.seed_turn("An old conversation")
        self.store.end_conversation(self.conversation_id)
        before = self.store.get_messages(self.conversation_id)
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute("DROP TABLE conversation_summaries")
        observer = ConversationStore(self.path)
        try:
            self.assertEqual(observer.get_messages(self.conversation_id), before)
            self.assertEqual(observer.get_summary(self.conversation_id)["pending"], 1)
            restarted = ConversationService(self.client, observer)
            restarted.start_conversation()
            self.assertEqual(observer.get_summary(self.conversation_id)["pending"], 0)
        finally:
            observer.close()

    def test_stale_summary_update_cannot_overwrite_newer_progress(self):
        self.seed_turn("A detail")
        self.store.queue_summary(self.conversation_id)
        stale = self.store.get_summary(self.conversation_id)
        self.service.summarizer.update(self.conversation_id)
        last = self.store.get_messages(self.conversation_id)[-1]
        self.assertFalse(self.store.save_summary(stale, "Stale", last["id"], len(last["content"])))
        self.assertNotEqual(self.store.get_summary(self.conversation_id)["content"], "Stale")


if __name__ == "__main__":
    unittest.main()
