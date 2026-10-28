"""Run with python3 terminal_chat.py; no robot dependencies are required."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.conversation import ConversationService
from app.conversation_store import ConversationStore
from app.ollama_client import OllamaClient, OllamaError


DEFAULT_DATABASE = Path(__file__).resolve().parent / "data" / "conversations.sqlite3"
COMMANDS = "Commands: /new, /history [ID], /summary [ID], /exit."


def show_notices(service: ConversationService) -> None:
    for notice in service.drain_notices():
        print(f"Note: {notice}\n")


def selected_conversation(argument: str) -> int:
    try:
        selected_id = int(argument)
    except ValueError:
        raise ValueError("Supply a conversation ID shown by /history.") from None
    if not 0 < selected_id < 2**63:
        raise ValueError("Use a valid conversation ID from /history.")
    return selected_id


def show_history(service: ConversationService, conversation_id: int, argument: str) -> None:
    if not argument:
        for conversation in service.list_conversations():
            if conversation["id"] == conversation_id:
                state = "current"
            else:
                state = "closed" if conversation["ended_at"] else "unfinished"
            print(
                f"#{conversation['id']} | {conversation['started_at']} | "
                f"{state} | {conversation['message_count']} messages"
            )
        print("Use /history ID to read a conversation.\n")
        return
    selected_id = selected_conversation(argument)
    messages = service.get_history(selected_id)
    print(f"Conversation #{selected_id}:")
    if not messages:
        print("No messages yet.")
    for message in messages:
        label = "You" if message["role"] == "user" else "BrainCharge"
        status = "" if message["status"] == "completed" else f" [{message['status']}; no saved reply]"
        print(f"{message['created_at']} {label}{status}: {message['content']}")
    print()


def run_chat(service: ConversationService) -> int:
    print("BrainCharge — local terminal chat")
    print("Phase 3: local history, conversation summaries, and continuity across chats.")
    print(COMMANDS + " Ctrl+C or end-of-input also exits.\n")
    conversation_id = None
    exit_code = 0
    interrupted = False
    try:
        conversation_id = service.start_conversation()
        show_notices(service)
        print(f"Started conversation #{conversation_id}.\n")
        while True:
            text = input("You: ").strip()
            if not text:
                continue
            try:
                parts = text.split(maxsplit=1)
                command = parts[0].casefold()
                argument = parts[1].strip() if len(parts) > 1 else ""
                if command == "/exit" and not argument:
                    break
                if command == "/new" and not argument:
                    conversation_id = service.start_conversation(previous_id=conversation_id)
                    print(f"Started conversation #{conversation_id}.\n")
                elif command == "/history":
                    show_history(service, conversation_id, argument)
                elif command == "/summary":
                    selected_id = selected_conversation(argument) if argument else conversation_id
                    summary = service.get_summary(selected_id)
                    if summary and summary["content"]:
                        print(f"Summary for conversation #{selected_id}: {summary['content']}\n")
                    else:
                        print("No summary saved yet. Summaries are created as chats grow or close.\n")
                    if summary and summary["pending"]:
                        print("An update is pending; the full transcript is saved.\n")
                elif text.startswith("/"):
                    print(COMMANDS + "\n")
                else:
                    print(f"BrainCharge: {service.respond(conversation_id, text)}\n")
            except (OllamaError, ValueError) as error:
                print(f"Error: {error}\n")
            show_notices(service)
    except EOFError:
        print()
    except KeyboardInterrupt:
        interrupted = True
        print()
    except (sqlite3.Error, OSError) as error:
        print(f"History storage error: {error}. Chat stopped to avoid losing messages.")
        exit_code = 1
    finally:
        if conversation_id is not None:
            try:
                service.end_conversation(conversation_id, summarize=not interrupted)
            except KeyboardInterrupt:
                print("Summary update interrupted. Saved history is intact; the update is deferred.")
            except (sqlite3.Error, OSError) as error:
                print(f"Could not close conversation history: {error}.")
                exit_code = 1
        show_notices(service)
    print("Goodbye.")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat with BrainCharge using local Ollama.")
    parser.add_argument("--model", default="gemma3n:e4b", help="Installed local model (default: gemma3n:e4b).")
    parser.add_argument("--host", default="http://127.0.0.1:11434", help="Local Ollama HTTP address.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Request timeout in seconds (default: 120).")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="Local SQLite history file.")
    parser.add_argument("--context-chars", type=int, default=12000, help="Maximum combined prompt content characters (default: 12000).")
    args = parser.parse_args()
    try:
        client = OllamaClient(model=args.model, base_url=args.host, timeout=args.timeout)
    except ValueError as error:
        parser.error(str(error))
    store = None
    try:
        store = ConversationStore(args.database)
        service = ConversationService(client, store, context_chars=args.context_chars)
        print(f"History file: {store.path}\n")
        return run_chat(service)
    except ValueError as error:
        parser.error(str(error))
    except (sqlite3.Error, OSError) as error:
        print(f"Cannot open local conversation history: {error}.")
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
