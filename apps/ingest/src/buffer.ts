import { BYTES_PER_SECOND } from './audio';

export class RollingBuffer {
  private readonly capacity: number;
  private readonly data: Uint8Array;
  private filled = 0;
  private writePos = 0;

  constructor(seconds: number) {
    this.capacity = Math.max(1, Math.floor(seconds * BYTES_PER_SECOND));
    this.data = new Uint8Array(this.capacity);
  }

  push(chunk: Uint8Array): void {
    let src = chunk;
    if (src.byteLength > this.capacity) {
      src = src.subarray(src.byteLength - this.capacity);
    }
    const tail = this.capacity - this.writePos;
    if (src.byteLength <= tail) {
      this.data.set(src, this.writePos);
      this.writePos += src.byteLength;
      if (this.writePos === this.capacity) this.writePos = 0;
    } else {
      this.data.set(src.subarray(0, tail), this.writePos);
      this.data.set(src.subarray(tail), 0);
      this.writePos = src.byteLength - tail;
    }
    this.filled = Math.min(this.capacity, this.filled + chunk.byteLength);
  }

  get size(): number {
    return this.filled;
  }

  get capacityBytes(): number {
    return this.capacity;
  }
}
