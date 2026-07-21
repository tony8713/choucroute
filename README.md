# earbox

*l'oreille de la maison* — a 24/7-listening home device that turns ambient
speech into your private, searchable memory, queried through the agent you
already use. **Raw audio never leaves the box.**

Listen → transcribe **locally** (whisper.cpp) → write text into a git-backed
memory → ask your agent about your day over Telegram/WhatsApp. No audio is ever
stored or transmitted.

## Repo layout

```
image/         provision.sh (Pi OS Lite → whisper.cpp + daemon + systemd) + unit files
daemon/        earboxd.py (capture→VAD→whisper→git→delete), summarize.py, query.py, harness.py
docs/          architecture.md (components, privacy invariants, Pi5 decision, 7-day plan, risks)
```

## Try the pipeline on your Mac (no mic, no Pi)

```bash
cd daemon
# make a test wav (French), then run the full pipeline on it:
say -v Thomas -o /tmp/x.aiff "N'oublie pas le rendez-vous chez le médecin jeudi."
ffmpeg -y -i /tmp/x.aiff -ar 16000 -ac 1 /tmp/x.wav
python3 harness.py /tmp/x.wav
python3 query.py --repo ../scratch/harness-memory "médecin"
```

The harness runs the exact daemon path (VAD → whisper → git commit → **audio
deleted**) and prints the git log + transcript, proving a queryable memory.

Requires `whisper-cli` + a ggml model (base recommended) and `ffmpeg` on PATH.

## Deploy on the device

Target hardware: **Raspberry Pi 5** (the Zero 2W cannot transcribe locally in
real time — see `docs/architecture.md` §4). On a fresh Pi OS Lite (64-bit):

```bash
sudo EARBOX_MODEL=base bash image/provision.sh
```

Installs whisper.cpp (ARM64 + OpenBLAS), the daemon, and systemd units, wires a
tmpfs scratch, and starts listening. Mute with `touch ~/.earbox-muted` or the
GPIO switch.

## Privacy in one line

The capture daemon runs with **no network namespace** (`PrivateNetwork=yes`);
raw audio lives only in tmpfs and is deleted in a `finally` after each segment;
only a separate daily *text* summary is ever allowed to touch the network.
Full invariant table in `docs/architecture.md` §3.
