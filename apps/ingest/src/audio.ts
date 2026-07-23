export const SAMPLE_RATE = 16_000;
export const BYTES_PER_SAMPLE = 2;
export const CHANNELS = 1;
export const BYTES_PER_SECOND = SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS;

export const AUDIO_FORMAT = {
  encoding: 'pcm_s16le',
  sampleRate: SAMPLE_RATE,
  channels: CHANNELS,
  bytesPerSample: BYTES_PER_SAMPLE,
} as const;

export function bytesToSamples(bytes: number): number {
  return Math.floor(bytes / (BYTES_PER_SAMPLE * CHANNELS));
}

export function bytesToSeconds(bytes: number): number {
  return bytes / BYTES_PER_SECOND;
}
