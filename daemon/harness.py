#!/usr/bin/env python3
"""
Dev harness: prove the earbox pipeline end-to-end WITHOUT a mic.

It slices a source wav into segment_seconds chunks and runs each through the
exact same process_segment() the daemon uses: VAD -> whisper -> git commit ->
audio delete. Then it prints the resulting git log + transcript so you can see
a queryable memory was produced.

Usage:
  python3 harness.py <source.wav> [--config cfg.toml] [--seconds 30]
"""
import argparse
import datetime as dt
import os
import sys
import wave
from pathlib import Path

import earboxd


def slice_wav(src, seconds, rate, scratch):
    with wave.open(str(src), "rb") as w:
        sw, ch, sr = w.getsampwidth(), w.getnchannels(), w.getframerate()
        frames = w.readframes(w.getnframes())
    assert sr == rate, f"source is {sr}Hz, expected {rate}Hz (resample first)"
    bytes_per_sec = sr * sw * ch
    step = seconds * bytes_per_sec
    out = []
    for i in range(0, len(frames), step):
        chunk = frames[i:i + step]
        p = scratch / f"harness_{i//step:04d}.wav"
        with wave.open(str(p), "wb") as o:
            o.setsampwidth(sw); o.setnchannels(ch); o.setframerate(sr)
            o.writeframes(chunk)
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--config", default=None)
    ap.add_argument("--seconds", type=int, default=None)
    args = ap.parse_args()

    cfg = earboxd.load_config(args.config)
    # isolate a throwaway memory + scratch so the harness never touches prod
    cfg["memory_repo"] = os.path.join(os.path.dirname(__file__), "..", "scratch", "harness-memory")
    cfg["scratch_dir"] = os.path.join(os.path.dirname(__file__), "..", "scratch", "harness-scratch")
    if args.seconds:
        cfg["segment_seconds"] = args.seconds
    Path(cfg["scratch_dir"]).mkdir(parents=True, exist_ok=True)

    repo = earboxd.ensure_repo(cfg)
    chunks = slice_wav(args.source, cfg["segment_seconds"], cfg["sample_rate"],
                       Path(cfg["scratch_dir"]))
    base = dt.datetime.now().replace(microsecond=0)
    print(f"[harness] {len(chunks)} chunk(s) from {args.source}")
    for idx, ch in enumerate(chunks):
        existed = ch.exists()
        when = base + dt.timedelta(seconds=idx * cfg["segment_seconds"])
        text = earboxd.process_segment(cfg, repo, ch, when=when)
        deleted = not ch.exists()
        tag = "speech" if text else "skipped(silence)"
        print(f"[harness] chunk {idx}: {tag}; audio_deleted={deleted}")
        if text:
            print(f"          -> {text[:120]}")
    # verify no audio survived anywhere in the memory repo
    stray = list(Path(repo).rglob("*.wav")) + list(Path(cfg["scratch_dir"]).glob("*.wav"))
    print(f"\n[harness] stray audio files remaining: {len(stray)} (MUST be 0)")
    print("[harness] git log of memory repo:")
    os.system(f"git -C {repo} log --oneline")
    print("\n[harness] transcript content:")
    for md in sorted(Path(repo).glob("transcripts/*.md")):
        print(f"--- {md.name} ---")
        print(md.read_text())


if __name__ == "__main__":
    sys.exit(main())
