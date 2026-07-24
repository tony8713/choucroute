import { bytesToSamples, bytesToSeconds, BYTES_PER_SECOND } from './audio';

export interface StreamStatsSnapshot {
  streamId: string;
  bytes: number;
  samples: number;
  audioSeconds: number;
  wallSeconds: number;
  chunks: number;
  gaps: number;
  droppedBytes: number;
}

export class StreamStats {
  readonly streamId: string;
  private readonly startedAt: number;
  private readonly gapFactor: number;
  private bytes = 0;
  private chunks = 0;
  private gaps = 0;
  private droppedBytes = 0;
  private lastChunkAt: number;

  constructor(streamId: string, gapFactor = 3) {
    this.streamId = streamId;
    this.startedAt = performance.now();
    this.lastChunkAt = this.startedAt;
    this.gapFactor = gapFactor;
  }

  addChunk(byteLength: number): void {
    const now = performance.now();
    if (this.chunks > 0) {
      const idleMs = now - this.lastChunkAt;
      const expectedMs = (byteLength / BYTES_PER_SECOND) * 1000;
      if (expectedMs > 0 && idleMs > expectedMs * this.gapFactor) {
        this.gaps += 1;
      }
    }
    this.bytes += byteLength;
    this.chunks += 1;
    this.lastChunkAt = now;
  }

  addDropped(byteLength: number): void {
    this.droppedBytes += byteLength;
  }

  snapshot(): StreamStatsSnapshot {
    return {
      streamId: this.streamId,
      bytes: this.bytes,
      samples: bytesToSamples(this.bytes),
      audioSeconds: Number(bytesToSeconds(this.bytes).toFixed(3)),
      wallSeconds: Number(((performance.now() - this.startedAt) / 1000).toFixed(3)),
      chunks: this.chunks,
      gaps: this.gaps,
      droppedBytes: this.droppedBytes,
    };
  }
}
