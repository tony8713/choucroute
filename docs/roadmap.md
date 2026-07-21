# earbox — roadmap & ideas

Running log of agreed decisions and parked ideas so they don't get lost between
threads. Newest first. See `docs/architecture.md` for the settled design.

## Love-first easter egg — heartbeat LED (Laurent)

If the owner says **"je t'aime"** to the box, the LED ring plays a **heartbeat
pulse**. The phrase is matched **locally in the transcript** — nothing about it
ever leaves the device.

The point isn't cute: the easter egg **doubles as a live privacy proof**. The
heartbeat can only ever happen if the machine understood the phrase *on-device*.
A box that phoned home wouldn't light up on the same words with the network
pulled. So the gesture is also the demo.

## Audio never on disk

**Invariant:** raw audio is transient and must never durably land on the SD card.

- **v1 (quick win):** point the audio chunk temp dir at **tmpfs (`/dev/shm`)** so
  chunks live in RAM and never touch the SD card. Keep the existing
  **delete-in-`finally`** as a backstop — belt and suspenders.
- **v1.1 (target):** **full in-memory streaming** — no temp file at all, chunks
  handed straight from capture to STT.

## v1 UI decision

**No screen. LED ring only.** DisplayPort is reserved for **workshop debug**, not
an owner-facing surface.
