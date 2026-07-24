export interface IngestConfig {
  port: number;
  ingestPath: string;
  ackIntervalMs: number;
  rollingBufferSeconds: number;
  persistDir: string;
  authEnabled: boolean;
  streamToken: string;
}

function intEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

function boolEnv(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return fallback;
  return raw === '1' || raw.toLowerCase() === 'true';
}

export function loadConfig(): IngestConfig {
  return {
    port: intEnv('PORT', 8080),
    ingestPath: process.env.INGEST_PATH ?? '/ingest',
    ackIntervalMs: intEnv('ACK_INTERVAL_MS', 2_000),
    rollingBufferSeconds: intEnv('ROLLING_BUFFER_SECONDS', 30),
    persistDir: process.env.PERSIST_DIR ?? '',
    authEnabled: boolEnv('AUTH_ENABLED', false),
    streamToken: process.env.STREAM_TOKEN ?? '',
  };
}
