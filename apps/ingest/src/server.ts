import type { Server, ServerWebSocket } from 'bun';
import { AUDIO_FORMAT } from './audio';
import { RollingBuffer } from './buffer';
import { loadConfig, type IngestConfig } from './config';
import { log } from './log';
import { measuringSinkFactory, type AudioSink, type SinkFactory } from './sink';
import { StreamStats } from './stats';

const AUDIO_TOPIC = 'earbox-audio';

interface PublisherData {
  role: 'publisher';
  streamId: string;
  stats: StreamStats;
  sink: AudioSink;
  buffer: RollingBuffer;
  ackTimer: ReturnType<typeof setInterval> | null;
}
interface SubscriberData {
  role: 'subscriber';
  streamId: string;
}
type WSData = PublisherData | SubscriberData;

function authorizeConnection(req: Request, config: IngestConfig): boolean {
  if (!config.authEnabled) return true;
  const url = new URL(req.url);
  const bearer = req.headers.get('authorization')?.replace(/^Bearer\s+/i, '');
  const token = url.searchParams.get('token') ?? bearer ?? '';
  return config.streamToken !== '' && token === config.streamToken;
}

function shortId(): string {
  return crypto.randomUUID().slice(0, 8);
}

function servePage(): Response {
  return new Response(Bun.file(new URL('./listen.html', import.meta.url)), {
    headers: { 'content-type': 'text/html; charset=utf-8' },
  });
}

export function createServer(
  config: IngestConfig = loadConfig(),
  sinkFactory: SinkFactory = measuringSinkFactory,
): Server<WSData> {
  const startedAt = Date.now();
  let publishersOpen = 0;
  let subscribersOpen = 0;
  let totalPublishers = 0;

  const server = Bun.serve<WSData>({
    port: config.port,
    hostname: '0.0.0.0',
    idleTimeout: 120,

    fetch(req, srv): Response | undefined {
      const url = new URL(req.url);

      if (url.pathname === '/' || url.pathname === '/listen') return servePage();

      if (url.pathname === '/health') {
        return Response.json({
          status: 'ok',
          uptimeSeconds: Math.floor((Date.now() - startedAt) / 1000),
          publishersOpen,
          subscribersOpen,
          totalPublishers,
          format: AUDIO_FORMAT,
        });
      }

      const isIngest = url.pathname === config.ingestPath;
      const isSubscribe = url.pathname === '/subscribe';
      if (isIngest || isSubscribe) {
        if (!authorizeConnection(req, config)) return new Response('unauthorized', { status: 401 });
        const streamId = shortId();
        const data: WSData = isIngest
          ? {
              role: 'publisher', streamId,
              stats: new StreamStats(streamId), sink: sinkFactory(streamId),
              buffer: new RollingBuffer(config.rollingBufferSeconds), ackTimer: null,
            }
          : { role: 'subscriber', streamId };
        if (srv.upgrade(req, { data })) return undefined;
        return new Response('websocket upgrade failed', { status: 400 });
      }

      return new Response('earbox audio-ingest\n', { status: 404 });
    },

    websocket: {
      maxPayloadLength: 16 * 1024 * 1024,
      idleTimeout: 120,

      open(ws): void {
        if (ws.data.role === 'subscriber') {
          subscribersOpen += 1;
          ws.subscribe(AUDIO_TOPIC);
          ws.send(JSON.stringify({ type: 'hello', role: 'subscriber', format: AUDIO_FORMAT }));
          log.info('subscriber open', { streamId: ws.data.streamId, subscribersOpen });
          return;
        }
        publishersOpen += 1;
        totalPublishers += 1;
        const pub = ws.data;
        ws.send(JSON.stringify({ type: 'hello', role: 'publisher', streamId: pub.streamId, format: AUDIO_FORMAT }));
        pub.ackTimer = setInterval(() => {
          ws.send(JSON.stringify({ type: 'ack', ...pub.stats.snapshot() }));
        }, config.ackIntervalMs);
        log.info('publisher open', { streamId: pub.streamId, sink: pub.sink.name });
      },

      message(ws, message): void {
        if (typeof message === 'string') { handleControl(ws, message); return; }
        if (ws.data.role !== 'publisher') return;
        const chunk = message as Uint8Array;
        ws.data.stats.addChunk(chunk.byteLength);
        ws.data.buffer.push(chunk);
        void ws.data.sink.write(chunk);
        server.publish(AUDIO_TOPIC, chunk);
      },

      close(ws, code): void {
        if (ws.data.role === 'subscriber') {
          subscribersOpen -= 1;
          log.info('subscriber close', { streamId: ws.data.streamId, code });
          return;
        }
        publishersOpen -= 1;
        if (ws.data.ackTimer) clearInterval(ws.data.ackTimer);
        void ws.data.sink.close();
        log.info('publisher close', { ...ws.data.stats.snapshot(), code });
      },
    },
  });

  log.info('audio-ingest listening', {
    port: config.port,
    ingestPath: config.ingestPath,
    format: AUDIO_FORMAT,
    rollingBufferSeconds: config.rollingBufferSeconds,
    persistToDisk: config.persistDir !== '',
  });

  return server;
}

function handleControl(ws: ServerWebSocket<WSData>, raw: string): void {
  try {
    const parsed = JSON.parse(raw) as { type?: string };
    if (parsed.type === 'ping' && ws.data.role === 'publisher') {
      ws.send(JSON.stringify({ type: 'pong', ...ws.data.stats.snapshot() }));
    } else if (parsed.type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong' }));
    }
  } catch {
    log.warn('bad control frame', { streamId: ws.data.streamId });
  }
}

if (import.meta.main) {
  createServer();
}
