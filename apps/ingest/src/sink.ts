import { bytesToSamples, bytesToSeconds } from './audio';

export interface AudioSink {
  readonly name: string;
  write(chunk: Uint8Array): void | Promise<void>;
  close(): void | Promise<void>;
}

export interface SinkSummary {
  bytes: number;
  samples: number;
  seconds: number;
}

export class MeasuringSink implements AudioSink {
  readonly name = 'measuring';
  private bytes = 0;
  private closed = false;

  write(chunk: Uint8Array): void {
    if (this.closed) return;
    this.bytes += chunk.byteLength;
  }

  close(): void {
    this.closed = true;
  }

  summary(): SinkSummary {
    return {
      bytes: this.bytes,
      samples: bytesToSamples(this.bytes),
      seconds: bytesToSeconds(this.bytes),
    };
  }
}

export type SinkFactory = (streamId: string) => AudioSink;

export const measuringSinkFactory: SinkFactory = () => new MeasuringSink();
