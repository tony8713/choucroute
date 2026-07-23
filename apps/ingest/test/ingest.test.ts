import { afterAll, beforeAll, expect, test } from 'bun:test';
import { createServer } from '../src/server';
import { BYTES_PER_SECOND } from '../src/audio';
import type { Server } from 'bun';

let server: Server;
let base: string;

beforeAll(() => {
  server = createServer({
    port: 0,
    ingestPath: '/ingest',
    ackIntervalMs: 50,
    rollingBufferSeconds: 5,
    persistDir: '',
    authEnabled: false,
    streamToken: '',
  });
  base = `${server.hostname}:${server.port}`;
});

afterAll(() => { server.stop(true); });

function openWs(path: string): WebSocket {
  const ws = new WebSocket(`ws://${base}${path}`);
  ws.binaryType = 'arraybuffer';
  return ws;
}

test('/health reports the PCM format', async () => {
  const res = await fetch(`http://${base}/health`);
  expect(res.status).toBe(200);
  const body = (await res.json()) as { status: string; format: { sampleRate: number } };
  expect(body.status).toBe('ok');
  expect(body.format.sampleRate).toBe(16_000);
});

test('/ and /listen serve the test UI page', async () => {
  const res = await fetch(`http://${base}/listen`);
  expect(res.status).toBe(200);
  const html = await res.text();
  expect(html).toContain('earbox live listen');
});

test('ingests a binary PCM stream and acks byte/sample counts', async () => {
  const pcm = new Uint8Array(BYTES_PER_SECOND);
  const acks: { type: string; bytes: number; samples: number }[] = [];
  const hello: { type: string }[] = [];

  await new Promise<void>((resolve, reject) => {
    const ws = openWs('/ingest');
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data as string) as { type: string; bytes: number; samples: number };
      if (msg.type === 'hello') hello.push(msg);
      if (msg.type === 'pong') acks.push(msg);
    });
    ws.addEventListener('open', () => {
      ws.send(pcm);
      ws.send(JSON.stringify({ type: 'ping' }));
    });
    ws.addEventListener('error', () => { reject(new Error('ws error')); });
    setTimeout(() => { ws.close(); resolve(); }, 300);
  });

  expect(hello.length).toBe(1);
  expect(acks.length).toBeGreaterThan(0);
  const last = acks.at(-1);
  expect(last?.bytes).toBe(BYTES_PER_SECOND);
  expect(last?.samples).toBe(16_000);
});

test('fans out a publisher stream to a subscriber', async () => {
  const payload = new Uint8Array(3200);
  payload.fill(7);
  const received: number[] = [];

  const sub = openWs('/subscribe');
  await new Promise<void>((resolve) => { sub.addEventListener('open', () => { resolve(); }); });
  sub.addEventListener('message', (ev) => {
    if (typeof ev.data !== 'string') received.push(new Uint8Array(ev.data as ArrayBuffer).byteLength);
  });

  const pub = openWs('/ingest');
  await new Promise<void>((resolve) => { pub.addEventListener('open', () => { resolve(); }); });
  pub.send(payload);

  await Bun.sleep(150);
  pub.close();
  sub.close();

  expect(received.length).toBeGreaterThan(0);
  expect(received[0]).toBe(3200);
});
