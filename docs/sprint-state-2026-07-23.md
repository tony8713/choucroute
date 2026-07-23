# earbox — sprint state snapshot (2026-07-23)

A neutral, resumable snapshot of where the earbox/choucroute sprint stands, so
work can pause and pick back up without losing context. Factual only — this is a
state record, not a plan or a decision.

Repo state at time of writing: `main` at `87297fac` (PR #1, turbo/bun monorepo +
transcript-monitoring UI, merged 2026-07-23). The on-box pipeline sits under
`orin/` and `common/` and is fully committed and pushed.

## On-box pipeline — working

The end-to-end on-device chain is live and running on the Jetson Orin Nano Super.

- **Continuous 30 s capture → STT.** Audio is captured in rolling 30 s chunks and
  handed to speech-to-text.
- **faster-whisper `small`, int8, CPU, French-locked.** Model runs fully
  on-device on CPU; language is pinned to French.
- **Anti-hallucination fix (`0500328`, `fix(stt): reject hallucinations on
  silence`).** Overnight silence test after the fix: **0 hallucinations**, versus
  **14** on the pre-fix baseline over the same silent run.
- **Audio deleted after STT.** Chunks live in tmpfs (`/dev/shm`) and are removed
  once transcribed; `keep_debug_audio=false`. Raw audio never durably lands on
  the SD card — the standing privacy invariant.

## STT model findings — measured on the actual Orin Nano

Bench results below were measured on the real device, not estimated.

- **Parakeet-tdt-0.6b-v3, int8, via onnx-asr: RTF 0.12 (~8× realtime) on CPU.**
- **German accuracy: 0% CER (Parakeet)** vs **66.7% CER (whisper, fr-locked)** on
  the same German sample — whisper's French lock mangles German; Parakeet's
  multilingual model handles it clean.
- **int8 shows no measurable quant penalty** vs the higher-precision weights on
  this workload.
- **Runtime is `onnx-asr`, not `sherpa-onnx`.** (Recording this because the two
  are easy to confuse and the working path is onnx-asr.)
- **GPU RTF still unmeasured.** The jetson-ai-lab `jp6/cu126` wheel mirror was
  returning **502** during the sprint, blocking the CUDA wheel install; the GPU
  number is therefore still open. CPU RTF above is the measured floor, GPU is
  expected headroom.
- **Bench staged on the box at `~/parakeet-bench`** — `record_test.sh` and
  `transcribe_both.sh`. (Left in place on the device; not modified by this
  snapshot.)

## Open / pending

- **Static IP `.55` pin — blocked on box sudo.** The reservation to pin the box
  to `.55` needs root on the device and is not yet applied.
- **WireGuard tunnel cold-diagnosis owed.** Power-save was confirmed as *one*
  cause of the tunnel dropping but not the only one; a proper cold diagnosis is
  still outstanding.
- **Audio-streaming API direction — pending Less + Laurent alignment.** This is a
  separate, reversible layer on top of the current file-chunk pipeline, in flight
  as **PR #2 (`feat/fly-audio-ingest`, open):** a Fly audio-ingest streaming API
  (`apps/ingest/`) plus a box-side streamer (`orin/stream.py`). It is not yet
  settled and is being aligned between Less and Laurent. It does not change the
  existing on-box capture/STT code (see isolation note below).

## Isolation of the streaming / UI work

Both the streaming and UI workstreams are additive and leave Laurent's on-box
sprint code untouched.

- **Streaming — PR #2 (`feat/fly-audio-ingest`, open).** Adds `apps/ingest/`
  (the Fly ingest service) and a new `orin/stream.py` (box-side streamer). Its
  only edits to existing files are `bun.lock` and `choucroute.config.js` (shared
  monorepo config). It **does not modify** `orin/capture.py`, `orin/stt.py`, any
  other existing file under `orin/`, or anything in `common/` — `orin/stream.py`
  is a brand-new sibling module, not a change to the pipeline.
- **UI — PR #1 (`feat/monorepo-ui`, merged as `87297fac`).** Adds `apps/ui/`,
  `packages/config/`, and top-level monorepo scaffolding (`package.json`,
  `turbo.json`, `bun.lock`, `netlify.toml`, `choucroute.config.js`). It **does
  not touch** anything under `orin/` or `common/`.
