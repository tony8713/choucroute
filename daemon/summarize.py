#!/usr/bin/env python3
"""
summarize.py - daily summary hook. TEXT-ONLY egress.

This is the ONLY component that talks to the network. It reads the day's
transcript markdown (text, never audio), asks the owner's server-side agent to
summarize it, writes the summary back into the git memory, and optionally
notifies the owner through their Metro channel.

PARSIMONY: the device should "only speak when there's something real". This
hook produces at most one daily digest, and the notify step is gated on the
agent returning a non-empty, non-"nothing notable" verdict.

The actual LLM call is intentionally pluggable. Set EARBOX_SUMMARY_CMD to a
command that reads the transcript on stdin and prints a summary on stdout, e.g.
a small script that calls Claude. If unset, a local extractive fallback runs so
the pipeline still works offline.
"""
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path


def read_day(repo, day):
    md = Path(repo) / "transcripts" / f"{day}.md"
    return md.read_text() if md.exists() else ""


def summarize_text(transcript):
    cmd = os.environ.get("EARBOX_SUMMARY_CMD")
    if cmd:
        p = subprocess.run(cmd, shell=True, input=transcript,
                           capture_output=True, text=True)
        return p.stdout.strip()
    return extractive_fallback(transcript)


def extractive_fallback(transcript):
    """Offline heuristic: surface lines that look actionable."""
    keys = ("rendez-vous", "médecin", "appel", "acheter", "n'oublie",
            "demain", "jeudi", "réunion", "urgent", "appointment",
            "call", "buy", "remember", "meeting", "tomorrow")
    picks = []
    for line in transcript.splitlines():
        low = line.lower()
        if line.startswith("- ") and any(k in low for k in keys):
            picks.append(line[2:])
    if not picks:
        return ""
    return "Points du jour:\n" + "\n".join(f"- {p}" for p in picks[:8])


def write_summary(repo, day, summary):
    sdir = Path(repo) / "summaries"
    sdir.mkdir(exist_ok=True)
    out = sdir / f"{day}.md"
    out.write_text(f"# Résumé {day}\n\n{summary}\n")
    subprocess.run(["git", "add", str(out)], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"summary {day}"], cwd=repo, check=True)
    return out


def main():
    repo = os.environ.get("EARBOX_MEMORY", os.path.expanduser("~/earbox-memory"))
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    transcript = read_day(repo, day)
    if not transcript.strip():
        print(f"[summarize] no transcript for {day}; nothing to do")
        return
    summary = summarize_text(transcript)
    if not summary:
        print("[summarize] nothing notable; staying silent (parsimony)")
        return
    out = write_summary(repo, day, summary)
    print(f"[summarize] wrote {out}")
    # Notify hook (text only). Left as an explicit, owner-configured command.
    notify = os.environ.get("EARBOX_NOTIFY_CMD")
    if notify:
        subprocess.run(notify, shell=True, input=summary, text=True)


if __name__ == "__main__":
    main()
