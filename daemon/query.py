#!/usr/bin/env python3
"""
query.py - read-only search over the earbox memory.

This is a LOCAL convenience/test tool. In production the owner queries their
memory through their existing agent (Metro: Telegram/WhatsApp/etc), which reads
the same markdown files. Nothing here transmits anything.

Usage:
  python3 query.py "médecin"                 # grep transcripts
  python3 query.py --day 2026-07-21          # dump a day
  python3 query.py --repo ~/earbox-memory "pain"
"""
import argparse
import os
import re
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("term", nargs="?", default=None)
    ap.add_argument("--repo", default=os.path.expanduser("~/earbox-memory"))
    ap.add_argument("--day", default=None)
    args = ap.parse_args()

    tdir = Path(args.repo) / "transcripts"
    if not tdir.exists():
        print(f"no memory at {tdir}")
        return
    files = ([tdir / f"{args.day}.md"] if args.day
             else sorted(tdir.glob("*.md")))
    pat = re.compile(re.escape(args.term), re.I) if args.term else None
    hits = 0
    for md in files:
        if not md.exists():
            continue
        for line in md.read_text().splitlines():
            if pat is None or pat.search(line):
                print(f"{md.stem}  {line}")
                hits += 1
    if pat and not hits:
        print("(no matches)")


if __name__ == "__main__":
    main()
