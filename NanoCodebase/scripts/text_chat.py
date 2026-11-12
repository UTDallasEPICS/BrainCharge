"""Text-mode chat with And-I, for testing without the voice stack.

Drives the REAL conversation LLM (ConversationModules/LLM/module.py) and the same
persistent long-term memory used by the robot, so you can verify memory behaviour
by typing instead of speaking.

A "session" mirrors a wake...sleep cycle:
  - On wake, any stored memory is loaded into the model's prompt.
  - On sleep, the conversation is summarized and saved to data/llm_memory.db.
Wake again (or relaunch) and it should remember.

Run from the NanoCodebase root:
    uv run python scripts/text_chat.py

In-session commands:
    bye / goodbye / bye companion   end the session (summarize + save memory)
    /memory                         show what is currently stored in the DB
    /reset                          erase all stored memory
    /quit                           exit immediately (no save)
"""
import contextlib
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")  # hide 3rd-party deprecation noise

# Make the project importable whether run via `uv run` or directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ConversationModules.LLM import memory          # noqa: E402
from ConversationModules.LLM.module import LLMModule  # noqa: E402

SLEEP_WORDS = ("bye companion", "goodbye", "bye")


@contextlib.contextmanager
def _quiet_load():
    """Silence the noisy C-level llama.cpp / loader logs during model load.

    Python exceptions still propagate (and print) after stderr is restored,
    so genuine load failures remain visible.
    """
    saved = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(devnull)
        os.close(saved)


def _print_memory(llm: LLMModule) -> None:
    current = memory.load_summary(llm.user_id)
    if current:
        print(f"  [memory] Stored: {current}")
    else:
        print("  [memory] Nothing stored yet (blank slate).")


def run_session(llm: LLMModule) -> bool:
    """Run one wake...sleep session. Returns True to offer another, False to quit."""
    print("\n" + "=" * 62)
    print("  companion is waking up (loading model)...")
    with _quiet_load():
        llm.startup()

    _print_memory(llm)
    print("=" * 62)
    print('  Type to chat. "bye" ends the session (saves memory).')
    print("  Commands: /memory  /reset  /quit")
    print("-" * 62)

    while True:
        try:
            text = input("\n  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  (ending session)")
            text = "bye"

        if not text:
            continue

        if text == "/quit":
            print("  Exiting without saving this session.")
            # Drop the runtime without summarizing: close the model directly.
            if llm._runtime is not None:
                llm._runtime.llm.close()
                llm._runtime = None
            return False

        if text == "/memory":
            _print_memory(llm)
            continue

        if text == "/reset":
            memory.save_summary("", llm.user_id)
            print("  [memory] Cleared.")
            continue

        if any(word in text.casefold() for word in SLEEP_WORDS):
            print("\n  companion is going to sleep (summarizing + saving)...")
            llm.shutdown()  # <- _update_memory() summarizes and saves here
            saved = memory.load_summary(llm.user_id)
            print(f"  [memory saved] {saved!r}")
            return True

        reply = llm.generate(text)
        print(f"  And-I: {reply}")


def main() -> None:
    print("\nAnd-I text chat (testing tool)")
    print("DB in use:", memory.DB_PATH)
    llm = LLMModule()  # user_id='default', language='en'
    while True:
        wake_again = run_session(llm)
        if not wake_again:
            break
        choice = input(
            "\n  Wake again for a new session? (y = yes, n = quit): "
        ).strip().casefold()
        if choice not in ("y", "yes", ""):
            print("\n  Done. Memory persists in the DB above for next time.\n")
            break


if __name__ == "__main__":
    main()
