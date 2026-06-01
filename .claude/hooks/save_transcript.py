#!/usr/bin/env python3
"""Stop hook for the Padea ops agent project.

Archives the full chat transcript into chat_history/transcripts/ and appends a
one-line index entry to chat_history/sessions.log so the log becomes a real
index of saved transcripts (rather than a bare "session ended" heartbeat).

Receives the Stop-hook payload as JSON on stdin (includes transcript_path and
session_id). Best-effort: never raises, so it can't disrupt a session.
"""
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    transcript_path = data.get("transcript_path")
    session_id = data.get("session_id") or "unknown"

    # project root = .../padea_ops_agent  (this file lives at .claude/hooks/)
    project = Path(__file__).resolve().parents[2]
    chat_history = project / "chat_history"
    transcripts = chat_history / "transcripts"
    transcripts.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")

    saved_name = None
    if transcript_path and Path(transcript_path).is_file():
        dest = transcripts / f"{date}_{session_id}.jsonl"
        try:
            shutil.copyfile(transcript_path, dest)
            saved_name = dest.name
        except Exception:
            saved_name = None

    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    if saved_name:
        line = f"{stamp} — session {session_id} — transcripts/{saved_name}"
    else:
        line = f"{stamp} — session {session_id} — session ended (no transcript)"

    try:
        with open(chat_history / "sessions.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
