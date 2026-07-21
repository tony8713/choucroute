# earbox — architecture

*"l'oreille de la maison"* — a 24/7-listening home device that turns ambient
speech into the owner's private, searchable memory, queried through the agent
they already use. **Raw audio never leaves the home.**

## 0. What changed since D1

D1 was a single-box Raspberry Pi 5 running whisper.cpp on CPU. D2 locks a
**two-tier** design and a more capable brain:

- **The brain is a Jetson Orin Nano Super.** STT is **faster-whisper**
  (CTranslate2) on the Orin **GPU** (CUDA, int8), not CPU whisper.cpp. This buys
  headroom for larger models and multiple mics.
- **The founder unit is ONE box: Orin + a reSpeaker XMOS XVF3800 USB 4-mic
  array.** The XVF3800 does beamforming, noise suppression, AEC and AGC
  *on-chip* and plugs straight into the Orin over USB. **No Pi. No LAN hop.**
  This is v1.
- **The Pi 4 satellite tier stays, demoted to an OPTIONAL multi-room
  extension.** A cheap Pi in another room streams that room to the Orin over an
  encrypted LAN hop. Not needed for the founder unit.

Privacy invariants are unchanged. The Pi→Orin hop (when used) is LAN-only and
encrypted; nothing audio ever touches the internet.

## 1. Topology

```
 FOUNDER UNIT (v1, single box, no network):

   reSpeaker XVF3800 ──USB──▶┌──────────────── Jetson Orin Nano Super ─────────────────┐
   (4-mic, on-chip DSP:      │  capture (ALSA, processed ASR channel)                   │
    beamform/NS/AEC/AGC)     │     │                                                     │
                             │     ▼   raw audio in tmpfs (/dev/shm) — DELETED per seg   │
   physical mute ───────────▶│   VAD gate ─▶ [denoise: BYPASS] ─▶ faster-whisper (CUDA   │
                             │                                     int8, small/medium)  │
                             │                       │                                   │
                             │                       ▼   git commit (earbox-memory)      │
                             │                  transcript text ─────────┐               │
                             └───────────────────────────────────────────┼──────────────┘
                                                                          │ TEXT ONLY
                                       daily summary (summarize.py) ──────┘
                                                     ▼
                                     owner's agent ◀── Metro (Telegram/WhatsApp/…)

 OPTIONAL MULTI-ROOM (satellite tier):

   Pi 4 + mic ──▶ VAD gate ──▶ opus encode ──▶ TLS/LAN ──▶ Orin (same pipeline above)
   (bedroom)      zero storage on the Pi; audio deleted right after streaming
```

## 2. Components

### Orin brain — `orin/`
- **`orind.py`** — the brain daemon. Two input modes feed **one** pipeline:
  - `direct` (PRIMARY): capture the local XVF3800 over ALSA. No network.
  - `lan` (OPTIONAL): a TLS server; satellites stream encrypted segments in.
  - Pipeline: VAD (`common`) → **denoise (bypass by default)** → STT backend →
    `clean_transcript` → append to git memory tagged with the source room →
    **delete the raw audio in a `finally`**.
- **`capture.py`** — direct USB capture from the XVF3800. It exposes several
  channels; we feed whisper the **DSP-processed ASR channel** (post
  beamforming/NS/AEC/AGC), *not* the raw per-mic channels. Device + channel
  index are config (`usb_capture_device`, `usb_channels`, `usb_asr_channel`) and
  **must be confirmed on-device** against the reSpeaker XVF3800 docs (D3).
- **`stt.py`** — STT backends: `faster_whisper` (CUDA int8, production),
  `whisper_cli` (whisper.cpp — the D1 path, runs on a Mac, used by the harness),
  `echo` (plumbing).
- **`denoise.py`** — the **optional, default-OFF** pre-processing stage. The
  XVF3800 already denoises on-chip, so software denoise defaults off. It stays
  pluggable for the raw-mic satellite path and for **Laurent's chain (name
  PENDING)**: set `denoise_cmd` (wav-in/wav-out) or replace `_builtin_denoise`.
- **`provision.sh`** — JetPack 6.x: venv + faster-whisper, install code, tmpfs
  scratch, TLS certs (lan mode), memory repo, systemd. **UNTESTED-ON-TARGET.**

### Pi satellite — `satellite/` (optional)
- **`satellited.py`** — mic capture (`arecord`) → VAD gate → opus/pcm encode →
  stream to the Orin over TLS. **Zero storage on the Pi**: every wav is deleted
  right after it is sent (or skipped). No transcripts, no memory on the Pi.
- **`provision.sh`** — Pi OS Lite (64-bit): install code, opus-tools, zeroconf,
  tmpfs scratch, systemd. The Orin's `orin.crt` is copied here as the pinned CA.

### Shared — `common/`
- **`earbox_core.py`** — the single source of truth for the privacy-critical
  pieces (VAD, `clean_transcript`, git memory, mute, the delete-in-`finally`
  `process_segment`). Both tiers import it so the logic can't drift. Refactored
  out of the D1 `earboxd.py`.
- **`wire.py`** — the LAN hop protocol: a JSON header + length-prefixed frames
  over TLS. Server/client TLS context helpers.
- **`codec.py`** — per-segment encode/decode: `pcm` (zero-dep WAV bytes) or
  `opus` (Ogg/Opus via opus-tools).

### Egress / query — `daemon/` (reused from D1)
- **`summarize.py`** — the only networked component: reads the day's *text*,
  asks the owner's agent to summarize, writes it back, optionally notifies via
  Metro. Parsimony-gated (at most one digest/day, silent if nothing notable).
- **`query.py`** — local read-only search over the markdown. In production the
  owner just asks their agent, which reads the same repo.
- **`earboxd.py`** — the D1 single-box (Pi 5 + whisper.cpp) all-in-one daemon,
  kept as a legacy/reference path. Superseded by the Orin `direct` mode.

## 3. Discovery / pairing (satellite tier)

- The Orin advertises `_earbox._tcp` over **mDNS** (`orind.py` `_advertise_mdns`,
  python `zeroconf`; falls back to a static host if unavailable).
- A satellite either points at a static `orin_host` or mDNS-discovers the Orin.
- The LAN hop is **TLS** with a **self-signed cert** the satellite pins
  (`tls_cafile` = the Orin's `orin.crt`). `gen_certs.sh` mints it. A PSK/mutual
  scheme is a drop-in alternative.
- **PRODUCTION HARDENING TODO:** run the hop inside **WireGuard** and/or move to
  **mutual-TLS with per-satellite client certs** and hostname pinning. The
  self-signed-only path is fine for a trusted home LAN, not for untrusted ones.

## 4. Dataflow (one segment)

1. Muted? → skip (mic never opened).
2. Capture 30s to **tmpfs** (`/dev/shm/earbox`) — RAM, never the SSD/SD.
   - founder: Orin captures the XVF3800 processed channel.
   - satellite: Pi captures its mic, VAD-gates, opus-encodes, streams over TLS;
     the Orin decodes the segment back to a tmpfs wav.
3. VAD: silent? → delete wav, done.
4. Denoise stage: **bypass by default** (XVF3800 did DSP). Optional plug.
5. faster-whisper (CUDA int8) transcribes → text; hallucination/silence filtered.
6. Non-empty text → append to `transcripts/YYYY-MM-DD.md` tagged `_(room)_`,
   `git commit`.
7. **`finally`: delete the wav.** Audio is destroyed whether or not 4–6
   succeeded. This is in a `finally` by design, in `common.process_segment`.

## 5. Privacy invariants (the product promise)

| # | Invariant | How it is enforced |
|---|-----------|--------------------|
| 1 | Raw audio never leaves the **home** | Founder unit: the Orin captures locally and (mode=direct) opens **no socket at all**. Satellite hop is **LAN-only and TLS-encrypted**; the Orin binds a private LAN address, never a public one. Nothing audio is ever addressed to the internet. |
| 2 | No audio at rest | Scratch is tmpfs (`/dev/shm`, `noexec,nosuid`); every segment deleted in a `finally`; the Pi keeps **zero** storage; `keep_debug_audio` guarded off; `.gitignore` bans audio extensions. |
| 3 | Physical mute | GPIO switch (or `~/.earbox-muted` flag) checked before each capture; muted = mic never opened. |
| 4 | Transcripts stay local | git repo on the Orin; no remote configured by default. |
| 5 | Text-only egress | Only `summarize.py` touches the network; it reads markdown, never audio; runs as a separate unit on a timer. |
| 6 | Parsimony | Device speaks at most once/day, only if the summary is non-empty. |

**Honest note on invariant #1 vs D1:** the D1 Pi-5 capture daemon ran with
`PrivateNetwork=yes` (no network namespace — it *physically* could not
transmit). The Orin brain cannot do that in `lan` mode (it must accept the
satellite socket) and the summary step needs egress. So on the Orin the promise
is enforced by *what the code sends* (only tmpfs-scoped audio that is deleted;
only text committed/egressed), not by a kernel namespace. In `direct` mode the
Orin opens no socket, which is the strongest configuration and the founder
default. Iris's D5 protocol must make this un-footgunnable (asserted at boot).

## 6. Hardware decisions

### Why the Orin (brain), not a Pi 5
The Pi 5 (D1) transcribes **base** at ≈1× real time on CPU — no headroom for
larger models, denoise, or multiple rooms, and it throttles under 24/7 load. The
**Jetson Orin Nano Super** has a CUDA GPU; **faster-whisper small/medium int8**
is *expected* to run comfortably faster than real time there, which is what lets
one box serve good WER plus (optionally) several satellites.

> **This number is NOT yet measured.** There is no Orin in the dev environment.
> All Orin-specific code (`faster_whisper` backend, `capture.py`, `provision.sh`)
> is **UNTESTED-ON-TARGET** and marked as such. The small-vs-medium int8 RTF, in
> **real kitchen noise**, MUST be benchmarked on the device on **D3**.

### Why the XVF3800 (mic), and why software denoise is off
The reSpeaker **XMOS XVF3800** is a 4-mic USB array with **on-chip** beamforming,
noise suppression, AEC and AGC. It plugs directly into the Orin over USB and
enumerates as a standard USB audio class device, collapsing the founder unit to
a single enclosure with no satellite. Because the DSP is on-chip, the software
`denoise` stage **defaults to bypass** — stacking a second denoiser on already
cleaned audio usually *raises* WER. The stage stays pluggable for the raw-mic
satellite path and for Laurent's chain.

> **UNTESTED-ON-TARGET:** the XVF3800 channel layout (which output channel is the
> processed ASR mono) is firmware-dependent and must be confirmed with
> `arecord -l`/`-L` on the real device (D3). `usb_asr_channel` defaults to 0.

### Hailo — excluded for STT (correctly)
If a Hailo module is present on the carrier, note it is a **vision/CNN
accelerator** (INT8 conv nets — detection/classification). It does **not** run
Whisper's transformer encoder/decoder; there is no supported faster-whisper /
CTranslate2 path on Hailo. STT stays on the **Orin GPU via faster-whisper CUDA**.
Hailo is only relevant if we later add on-device vision, which is out of scope.

## 7. Sizing / gotchas
- **Benchmark faster-whisper small vs medium int8 on the Orin (D3)** under
  thermal load and in kitchen noise; pin whichever holds real time.
- CTranslate2 on JetPack must be a **CUDA aarch64** build; the stock PyPI wheel
  may be CPU/desktop-CUDA only. Verify `device=cuda` works on-device or build
  from source. (Noted in `provision.sh`.)
- tmpfs scratch sized small (64–128M) — segments are ~1MB each at 16kHz mono.
- Language pinned (`fr`) is faster than `auto`; `auto` misdetects short chunks.
- Active cooling for 24/7 inference on the Orin.
- Chunk-boundary word cuts (fixed 30s) still apply — VAD-aligned segmentation is
  the fix (carried from D1 risks).

## 8. Seven-day plan

- **D1 (done):** repo + buildable single-box skeleton; pipeline validated on the
  Mac harness (chunk → VAD → whisper → git commit → audio deleted, 0 stray).
- **D2 (done):** two-tier restructure — `orin/` brain (direct XVF3800 + optional
  LAN server; faster-whisper CUDA backend; denoise-bypass plug; git memory;
  delete-in-finally), `satellite/` Pi tier (capture→VAD→opus→TLS, zero storage),
  `common/` shared core + wire + codec, mDNS + self-signed TLS pairing,
  provisioning + systemd for both. **Mac two-tier harness proves the full
  plumbing end-to-end** (loopback satellite → real TLS → Orin daemon → real
  transcription → git → audio destroyed).
- **D3:** **on-Orin benchmark** — flash JetPack 6.x, run `provision.sh`, get
  faster-whisper on CUDA, measure **small vs medium int8 RTF in real kitchen
  noise** with the **XVF3800** as the mic (confirm the ASR channel with
  `arecord`); tune VAD + segment length to the array; confirm thermals under
  24/7 load. Real Pi-4 satellite as a stretch.
- **D4:** Metro/agent query integration — owner asks their agent and it reads
  `earbox-memory`; wire `summarize.py`'s `EARBOX_SUMMARY_CMD`/`EARBOX_NOTIFY_CMD`
  to the agent + Metro channel.
- **D5:** physical mute switch (GPIO) + state LED/display; parsimony tuning
  (only-speak-when-real); land **Iris's privacy protocol** as a written,
  testable checklist mapped to the invariants above (incl. the Orin invariant-#1
  nuance from §5).
- **D6:** assembly + golden images — Orin+XVF3800 enclosure; `dd`/`rpi-image-gen`
  for the (optional) satellite; per-unit identity + owner memory bootstrap;
  first-boot config wizard.
- **D7:** demo (speak → query over Telegram); preorder page; pricing.

## 9. Top risks (honest)

1. **faster-whisper RTF on the Orin is unproven here.** small/medium int8 is
   *expected* faster-than-real-time but is **not measured** — no Orin in dev.
   D3 must confirm it (in kitchen noise, under thermal load) or we drop model
   size / shorten segments.
2. **CTranslate2 CUDA on JetPack is a known packaging hazard** — the wheel may
   not be a Jetson CUDA build; may need a source build on-device.
3. **XVF3800 channel layout is firmware-dependent** — feeding whisper the wrong
   (raw) channel would tank WER. Confirm the ASR channel on-device.
4. **LAN hop trust.** Self-signed-pinned TLS is fine on a trusted home LAN; an
   untrusted LAN needs WireGuard/mutual-TLS (hardening TODO). The founder unit
   sidesteps this entirely (no hop).
5. **Orin invariant-#1 is code-enforced, not namespace-enforced** (see §5). Needs
   Iris's boot-time asserts so a misconfig can't leak.
6. **Whisper hallucination on ambient noise/music** — filter list + VAD help but
   aren't perfect.
7. **Always-on mic in a home is a consent/legal surface** (bystanders, other
   members, jurisdictions). Product + legal, not just tech.
8. **A private git remote is still needed for the team.** Everything is
   local-first and unpushed; we need a private remote before D6 fleet work.
