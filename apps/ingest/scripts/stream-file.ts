import { BYTES_PER_SECOND } from '../src/audio';

const url = process.argv[2] ?? 'ws://localhost:8080/ingest';
const file = process.argv[3] ?? '';
const realtime = process.env.REALTIME !== '0';

if (!file) {
  process.stderr.write('usage: bun scripts/stream-file.ts <wsUrl> <file.wav|.pcm> [REALTIME=0]\n');
  process.exit(1);
}

function pcmFromFile(bytes: Uint8Array): Uint8Array {
  const isRiff = bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46;
  if (!isRiff) return bytes;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let pos = 12;
  while (pos + 8 <= bytes.byteLength) {
    const id = String.fromCharCode(
      view.getUint8(pos), view.getUint8(pos + 1), view.getUint8(pos + 2), view.getUint8(pos + 3),
    );
    const size = view.getUint32(pos + 4, true);
    if (id === 'data') return bytes.subarray(pos + 8, pos + 8 + size);
    pos += 8 + size + (size % 2);
  }
  return bytes.subarray(44);
}

const raw = new Uint8Array(await Bun.file(file).arrayBuffer());
const pcm = pcmFromFile(raw);
const chunkBytes = Math.floor(BYTES_PER_SECOND / 10);
const startWall = performance.now();

const ws = new WebSocket(url);
ws.binaryType = 'arraybuffer';
let acks = 0;
let lastAck = '';

ws.addEventListener('message', (ev) => {
  const text = typeof ev.data === 'string' ? ev.data : '';
  if (!text) return;
  const msg = JSON.parse(text) as { type: string };
  if (msg.type === 'ack') { acks += 1; lastAck = text; }
  else process.stdout.write(text + '\n');
});

async function streamAll(): Promise<void> {
  process.stdout.write(`streaming ${pcm.byteLength} PCM bytes to ${url}\n`);
  for (let off = 0; off < pcm.byteLength; off += chunkBytes) {
    ws.send(pcm.subarray(off, Math.min(off + chunkBytes, pcm.byteLength)));
    if (realtime) await Bun.sleep(100);
  }
  ws.send(JSON.stringify({ type: 'ping' }));
  await Bun.sleep(300);
  const wallSeconds = (performance.now() - startWall) / 1000;
  const audioSeconds = pcm.byteLength / BYTES_PER_SECOND;
  process.stdout.write(
    `done: ${pcm.byteLength} bytes / ${audioSeconds.toFixed(1)}s audio in ${wallSeconds.toFixed(1)}s wall, ` +
    `${acks} acks, throughput ${(pcm.byteLength / 1024 / wallSeconds).toFixed(0)} KiB/s\n`,
  );
  process.stdout.write(`last ack: ${lastAck}\n`);
  ws.close();
  process.exit(0);
}

ws.addEventListener('open', () => { void streamAll(); });

ws.addEventListener('error', (ev) => {
  const detail = (ev as Partial<ErrorEvent>).message ?? 'connection failed';
  process.stderr.write(`ws error: ${detail}\n`);
  process.exit(1);
});
