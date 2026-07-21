# earbox

*l'oreille de la maison* — a 24/7-listening home device that turns ambient
speech into your private, searchable memory, queried through the agent you
already use. **Raw audio never leaves the home.**

Listen → transcribe **locally** → write text into a git-backed memory → ask your
agent about your day over Telegram/WhatsApp. No audio is ever stored or sent.

## Architecture (two-tier)

- **Founder unit (v1): one box** = a **Jetson Orin Nano Super** brain + a
  **reSpeaker XMOS XVF3800** USB 4-mic array (on-chip beamforming/NS/AEC/AGC).
  The mic plugs into the Orin over USB; the Orin transcribes on its GPU with
  **faster-whisper** (CUDA int8) and writes text to a local git memory. **No
  network.**
- **Optional multi-room:** cheap **Pi 4 satellites** stream other rooms to the
  Orin over an **encrypted LAN hop** (TLS). Satellites keep zero storage.

Full design + privacy invariants: `docs/architecture.md`.

## Repo layout

```
orin/        the brain: orind.py (direct XVF3800 OR lan satellite server),
             capture.py (USB mic), stt.py (faster-whisper CUDA / whisper.cpp),
             denoise.py (optional, default-OFF), provision.sh (JetPack 6.x),
             gen_certs.sh, systemd/, config.example.toml
satellite/   optional Pi tier: satellited.py (capture→VAD→opus→TLS, zero
             storage), provision.sh (Pi OS Lite), systemd/, config.example.toml
common/      shared source of truth: earbox_core.py (VAD, cleaning, git memory,
             mute, delete-in-finally), wire.py (LAN protocol+TLS), codec.py
daemon/      summarize.py (text-only egress), query.py, and earboxd.py (the D1
             single-box legacy daemon), harness.py (D1 single-segment harness)
docs/        architecture.md
harness_twotier.py   prove the FULL two-tier plumbing on a Mac (below)
```

## Prove the two-tier plumbing on a Mac (no Pi, no Orin)

`harness_twotier.py` runs the **real** Orin daemon (`orin/orind.py`) in `lan`
mode with real self-signed TLS, then streams a wav through a loopback
"satellite" over the real TLS socket, using the exact wire framing + codec the
Pi uses. The Orin decodes each segment in tmpfs → transcribes → commits to git →
deletes the audio.

```bash
python3 harness_twotier.py scratch/test_fr.wav --seconds 30 --codec pcm
```

It uses the `whisper_cli` STT backend (whisper.cpp, needs `whisper-cli` + a ggml
model on PATH) because faster-whisper needs the Orin's CUDA. So it proves the
whole chain **except** faster-whisper itself, which is benchmarked on the device
(D3). Expect: `TWO-TIER PLUMBING: WORKED`, transcript committed, `stray audio: 0`.

The D1 single-box harness still works too: `cd daemon && python3 harness.py <wav>`.

## Deploy

**Founder unit (Orin + XVF3800), JetPack 6.x:**
```bash
sudo EARBOX_MODE=direct bash orin/provision.sh   # UNTESTED-ON-TARGET (no Orin in dev)
```
Then `arecord -l` to find the reSpeaker card and set `usb_capture_device` /
`usb_asr_channel` in `~/.config/earbox/orin.toml`.

**Optional Pi 4 satellite, Pi OS Lite (64-bit):**
```bash
sudo bash orin/provision.sh with EARBOX_MODE=lan on the Orin   # enables the TLS server + certs
sudo bash satellite/provision.sh                               # on the Pi
scp earbox@<orin>:/opt/earbox/tls/orin.crt /opt/earbox/tls/    # pin the Orin cert
# set satellite_id + orin_host (or leave empty for mDNS), then enable the unit
```

## Privacy in one line

Raw audio lives only in tmpfs and is deleted in a `finally` after each segment;
the founder unit opens no network at all; the optional satellite hop is TLS and
LAN-only; only a separate daily **text** summary may ever touch the network. Full
invariant table in `docs/architecture.md` §5.

## Status

Local-first, nothing pushed. **A private git remote is still needed for the
team** before fleet/golden-image work (D6).
