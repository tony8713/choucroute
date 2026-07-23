# @choucroute/ui

A simple web timeline for monitoring every transcription the box produces:
a reverse-chronological feed grouped by day, with full-text search, a date range,
and per-room filters. Built with the real `@stage-labs/kit` (the Stage design
system's React Native component family) rendered on the web via
`react-native-web`, so it matches the Stage / Snapshot design language. The
feed shows sample data by default; a remote source is opt-in via
`VITE_TRANSCRIPTS_URL`.

```
bun install
bun run --filter @choucroute/ui dev     # http://localhost:5175
```

Out of the box it renders fabricated sample transcripts (`src/data/mock.ts`) so it
runs with zero setup.

## Pointing at real transcripts

Real transcripts live in the **private** `earbox-memory` repo as day-keyed
markdown (`transcripts/YYYY-MM-DD.md`) and contain personal data — they are never
committed here. The UI reads from a configurable source instead:

Set `VITE_TRANSCRIPTS_URL` (copy `.env.example` to `.env.local`) to a URL that
returns either:

- **markdown** — one or more day files concatenated, in the box's native format
  (`# YYYY-MM-DD` headers, `- **HH:MM** _(room)_ text` lines), or
- **JSON** (`content-type: application/json`) — an array of
  `{ day, time, timestamp, room, text }` entries.

Two easy ways to serve the private memory locally:

```
# static: serve the memory repo, bundle the day files, point the UI at it
cd /path/to/earbox-memory && python -m http.server 8099
# then VITE_TRANSCRIPTS_URL=http://localhost:8099/transcripts/2026-07-22.md

# or expose your own private read-only API returning the JSON shape above
```

No audio and no real transcript text is ever stored in this repo.
