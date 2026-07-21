# earbox — architecture

*"l'oreille de la maison"* — a 24/7-listening home device that turns ambient
speech into the owner's private, searchable memory, queried through the agent
they already use. Raw audio never leaves the box.

## 1. Components

```
                         ┌─────────────────────── the box (Raspberry Pi 5) ───────────────────────┐
                         │                                                                          │
  mic (WhisPlay HAT) ───▶│  arecord ──▶ VAD gate ──▶ whisper.cpp (LOCAL STT) ──▶ transcript text    │
                         │     │            │                                        │              │
  physical mute switch ──┼─────┘   raw audio in tmpfs (/dev/shm)                     ▼              │
   (GPIO)                │                  │  DELETED after each segment      git commit            │
                         │                  └──────────── never persisted        (earbox-memory)     │
                         │                                                          │               │
                         └──────────────────────────────────────────────────────────┼──────────────┘
                                                                                     │ TEXT ONLY
                                            daily summary (summarize.py) ────────────┘
                                                       │
                                                       ▼
                                       owner's agent  ◀── Metro (Telegram/WhatsApp/…)
                                       "what did I say about the doctor?"
```

- **Capture** (`daemon/earboxd.py`): records fixed segments (default 30s) from
  the HAT mic via `arecord`. Source-abstracted: `ffmpeg`/avfoundation on a Mac
  dev box, wav-replay in the test harness.
- **VAD gate**: dependency-free energy gate (RMS + voiced-frame ratio, pure
  stdlib) that skips near-silent segments so we don't burn CPU (or hallucinate)
  on an empty room.
- **STT**: `whisper.cpp` (`whisper-cli`) running **on the device**. base model
  (multilingual) recommended; tiny for the lowest-power path.
- **Memory**: transcripts appended to day-keyed markdown in a local **git**
  repo (`earbox-memory`), auto-committed. `.gitignore` bans every audio
  extension so audio can never be committed even by accident.
- **Summary/egress** (`daemon/summarize.py`): once a day, reads the day's
  *text*, asks the owner's server-side agent to summarize, writes it back, and
  optionally notifies via Metro. This is the only networked component.
- **Query** (`daemon/query.py` + the owner's agent): read-only search over the
  markdown. In production the owner just asks their agent.

## 2. Dataflow (one segment)

1. If muted → skip (no capture at all).
2. `arecord` writes `seg.wav` to **tmpfs** (`/dev/shm/earbox`) — RAM, never SD.
3. VAD: silent? → delete wav, done.
4. `whisper-cli` transcribes → text; hallucination/silence lines filtered.
5. Non-empty text → append to `transcripts/YYYY-MM-DD.md`, `git commit`.
6. **`finally`: delete the wav.** Audio is destroyed whether or not steps 4–5
   succeeded. This is in a `finally` block by design.

## 3. Privacy invariants (the product promise)

| # | Invariant | How it is enforced |
|---|-----------|--------------------|
| 1 | Raw audio never leaves the box | Capture daemon runs under systemd with `PrivateNetwork=yes` — it has **no network namespace at all**. It physically cannot transmit. |
| 2 | No audio at rest | Scratch is tmpfs (`/dev/shm`, `noexec,nosuid`); every segment deleted in a `finally`; `keep_debug_audio` guarded off; `.gitignore` bans audio extensions. |
| 3 | Physical mute | GPIO switch (or `~/.earbox-muted` flag) checked before each capture; muted = mic never opened. |
| 4 | Transcripts stay local | git repo on-device; no remote configured by default. |
| 5 | Text-only egress | Only `summarize.py` has network; it reads markdown, never audio; runs as a separate unit on a timer. |
| 6 | Parsimony | Device speaks at most once/day, and only if the summary is non-empty. |

## 4. Hardware decision: Pi Zero 2W vs Pi 5 — **use the Pi 5**

The core question was whether a Zero 2W can transcribe locally in real time.
**It cannot**, and the reason is decisive for the privacy promise.

**Zero 2W** (quad A53 @ 1GHz, **512MB RAM**): Pi-3-class compute and, critically,
512MB RAM. whisper base's runtime footprint (~400MB) does not fit alongside a
running OS; even tiny leaves almost no headroom and swaps to SD, which kills
real-time. This is why every real-world Zero 2W voice project (Home Assistant /
Wyoming satellites) uses it **only as a mic + wake-word and offloads STT to a
server**. Offloading means audio leaves the sensor — which **violates invariant
#1**. So the Zero 2W is disqualified for a device whose whole promise is
"audio never leaves the box."

**Pi 5** (quad A76 @ 2.4GHz, 4–8GB): the minimum board that transcribes locally
in real time. Published numbers (openHAB WhisperSTT, whisper.cpp benches):
tiny comfortably faster than real-time; **base ≈ real-time to ~2× with `-t 4`,
WER ~5%** — the sweet spot; small is *slower* than audio (batch only), skip it
for live use. Needs OpenBLAS (`-DGGML_BLAS=1`) and **active cooling** or 24/7
inference thermally throttles.

**Local measurement (this Mac, M4 + Metal, for pipeline validation only — NOT
Pi-representative):** 60s French clip, `-t 4`: **tiny.en 172ms (~350× RT),
base 1.58s (~38× RT)**. Transcription quality on French was near-perfect. This
proves the pipeline and the model quality; the Pi 5 is CPU-only ARM so expect
the published ~1× (base) / well-under-1× (tiny) real-time factors there, not
these Metal numbers.

**Verdict:** ship on **Raspberry Pi 5** running **base** (`-t 4`, OpenBLAS,
heatsink+fan). Keep tiny as the fallback for a cheaper/cooler SKU. The Zero 2W +
PiSugar can still ship as a **portable satellite** *later*, but only if we
accept audio→local-base-station egress, which is a different privacy story and
needs Iris's sign-off.

## 5. Sizing / gotchas

- Build a **native ARM64** whisper-cli (NEON is on by default) + OpenBLAS.
- tmpfs scratch sized small (64M) — segments are ~1MB each at 16kHz mono.
- Language pinned (`fr`) is faster than `auto`; `auto` misdetects short chunks.
- Quantized models (q5/q8) shrink RAM but do **not** speed the encoder — no RTF
  win on Pi; only relevant if we ever squeeze onto a smaller board.
- Active cooling is not optional for 24/7 inference on the Pi 5.

## 6. Seven-day plan

- **D1 (done):** repo + buildable skeleton; pipeline validated end-to-end on the
  Mac harness (chunk → VAD → whisper → git commit → audio deleted, 0 stray
  files); Zero-2W-vs-Pi-5 verdict with numbers; architecture + privacy spec.
- **D2:** flash Pi OS Lite (64-bit) to a Pi 5; `provision.sh` builds whisper.cpp
  + installs daemon + systemd; image boots, `earboxd` runs, memory repo inits.
- **D3:** WhisPlay HAT mic capture working (`arecord -l`, ALSA device wired);
  real ambient speech → committed transcripts on the device; tune VAD threshold
  and segment length to the mic; confirm base RTF on-Pi under load + thermals.
- **D4:** Metro/agent query integration — owner asks their agent over
  Telegram/WhatsApp and it reads `earbox-memory`; wire `summarize.py`'s
  `EARBOX_SUMMARY_CMD`/`EARBOX_NOTIFY_CMD` to the agent + Metro channel.
- **D5:** physical mute switch (GPIO) + LED/display state on the HAT; parsimony
  tuning (only-speak-when-real); land **Iris's privacy protocol** as a written,
  testable checklist mapped to the invariants above.
- **D6:** golden image (`dd`/`rpi-image-gen`); flash N units; per-unit identity +
  owner memory repo bootstrap; first-boot config wizard.
- **D7:** demo (speak → query over Telegram); preorder page; pricing.

## 7. Top risks (honest)

1. **On-Pi real-time under load is "≈1×" for base, not comfortable.** If a Pi 5
   at temperature can't stay ahead of continuous audio, drop to tiny (lower WER
   but real-time) or shorten segments. Must be measured on D3 — the Mac's Metal
   numbers do **not** de-risk this.
2. **Chunk-boundary word cuts.** Fixed 30s cuts split words ("passera" → "sera"
   in the harness). Fix: VAD-aligned segmentation (silero VAD / whisper-stream
   `--step/--length`) so we cut on silence, not mid-word.
3. **Language handling.** Pinned `fr` mis-transcribes English speech in a
   bilingual home; `auto` is slower and misdetects short chunks. Needs a policy.
4. **Whisper hallucination on ambient noise/music.** Filter list + VAD help but
   won't be perfect; a noisy room can inject garbage into memory.
5. **Privacy is only as strong as the weakest config.** `keep_debug_audio=true`,
   a non-tmpfs scratch, or a mis-set `EARBOX_NOTIFY_CMD` could leak. Iris's
   protocol must make these un-footgunnable (asserted at boot).
6. **Always-on mic in a home is a consent/legal surface** (bystanders, other
   household members, jurisdictions). Product + legal question, not just tech.
7. **Storage growth / speaker anonymity**: transcripts are unattributed text of
   everyone in earshot; retention + who-can-read policy needed.
