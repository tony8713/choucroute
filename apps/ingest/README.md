# @choucroute/ingest — Fly audio-ingest API

A small Bun WebSocket server that accepts a **live binary audio stream** from the
earbox and measures it, exposing a clean seam where cloud STT (Parakeet/Canary on
a GPU) attaches next. Deployed on Fly.io in **region `sin`** (Singapore — closest
to the box in Thailand, UTC+7).

This reverses the earlier "audio never leaves the box" model. That is a deliberate
product decision (Less, 2026-07-23). The **irreversible flip of pointing the real
box at this endpoint is still pending Less + Laurent alignment** — this repo ships
the plumbing and a local/test client proof only; do not auto-start the box streamer
against prod.

## Audio format (the wire contract)

Raw **PCM S16LE, 16 kHz, mono** — exactly what `orin/capture.py` produces. Binary
WS frames of raw PCM, ~100 ms each (3200 bytes). Continuous 16k PCM ≈ **256 kbps**;
Opus would cut that ~10x and is the obvious next optimization (the box already has
`opusenc`; see `common/codec.py`). Start with PCM for simplicity.

## Endpoints

- `GET /health` → `{ status, uptimeSeconds, openConnections, totalConnections, format }`
- `WS /ingest` → live PCM stream. On connect the server sends
  `{ type: "hello", streamId, format }`, then periodic
  `{ type: "ack", bytes, samples, audioSeconds, wallSeconds, chunks, gaps }`
  every `ACK_INTERVAL_MS`. Send a text `{ "type": "ping" }` for an immediate
  `pong` snapshot. Binary frames are the audio.

## Server behavior (MVP)

- Authenticates the connection (see Auth), assigns a `streamId`, tracks stats
  (bytes, samples, audio vs wall seconds, chunk count, gap detection).
- Feeds every chunk to an `AudioSink` (`src/sink.ts`) — **this is the STT seam**.
  The default `MeasuringSink` only measures. Swapping in a real STT sink is a
  drop-in: implement `AudioSink.write(chunk)` / `close()` and pass a `SinkFactory`
  to `createServer(config, sinkFactory)`.
- Keeps only an **in-memory rolling buffer** (`ROLLING_BUFFER_SECONDS`, default 30s).
  **Never writes audio to disk** (`PERSIST_DIR` empty by default — a privacy
  invariant, matching the box's tmpfs-only rule).

## Auth — deferred, not removed

Per Less ("no auth for now", 2026-07-23) and the Iris security review: the
bearer / `?token=` check ships **present in the code** but **gated off by default**
(`AUTH_ENABLED=0`). Re-enabling is a one-line flag flip plus a secret, no rebuild:

```sh
fly secrets set STREAM_TOKEN=$(openssl rand -hex 32) --app earbox-ingest
fly secrets set AUTH_ENABLED=1 --app earbox-ingest
```

Then clients must present `?token=<t>` or `Authorization: Bearer <t>`. A public
unauthenticated live-audio endpoint is a known hole for a confidentiality-critical
product — turn this on before any non-test use.

## Run locally

```sh
bun install
bun run --filter @choucroute/ingest dev        # or: cd apps/ingest && bun run dev
curl localhost:8080/health
# stream a wav through it (REALTIME=0 = as fast as possible):
REALTIME=0 bun apps/ingest/scripts/stream-file.ts ws://localhost:8080/ingest scratch/long_fr.wav
```

## Deploy (Fly)

```sh
cd apps/ingest
fly apps create earbox-ingest --org snack-labs   # once
fly deploy --ha=false --now
fly status --app earbox-ingest
```

Single always-on `shared-cpu-1x` / 512 MB machine in `sin`, WebSocket over the
standard Fly HTTPS handler (`internal_port = 8080`, `force_https = true`).
Live endpoint: `wss://earbox-ingest.fly.dev/ingest`.

## Box streamer

See `orin/stream.py` (captures the reSpeaker Array, streams PCM16 16k mono here
with reconnect + mute-flag coordination). It opens the **same ALSA device orind
holds exclusively**, so it cannot run alongside prod orind — stop orind (or set
the mute flag) first. Run command is documented in that file's header.
