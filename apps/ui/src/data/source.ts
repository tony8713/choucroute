import { type TranscriptEntry, type TranscriptSource } from './types';
import { parseTranscriptMarkdown } from './markdown';
import { MOCK_TRANSCRIPT_MARKDOWN } from './mock';

function sortByTimestampDesc(entries: TranscriptEntry[]): TranscriptEntry[] {
  return [...entries].sort((a, b) => b.timestamp - a.timestamp);
}

function isEntryArray(value: unknown): value is TranscriptEntry[] {
  return Array.isArray(value) && value.every((e) => typeof e === 'object' && e !== null && 'text' in e);
}

async function parseResponse(res: Response): Promise<TranscriptEntry[]> {
  const contentType = res.headers.get('content-type') ?? '';
  const body = await res.text();
  if (contentType.includes('application/json')) {
    const data: unknown = JSON.parse(body);
    if (isEntryArray(data)) return data;
    throw new Error('transcript JSON must be an array of entries');
  }
  return parseTranscriptMarkdown(body);
}

export function mockSource(): TranscriptSource {
  return {
    label: 'sample data',
    load: () => Promise.resolve(sortByTimestampDesc(parseTranscriptMarkdown(MOCK_TRANSCRIPT_MARKDOWN))),
  };
}

export function remoteSource(url: string): TranscriptSource {
  return {
    label: url,
    load: async () => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`transcript source responded ${String(res.status)}`);
      return sortByTimestampDesc(await parseResponse(res));
    },
  };
}

export function resolveSource(): TranscriptSource {
  const url = import.meta.env.VITE_TRANSCRIPTS_URL;
  if (typeof url === 'string' && url.trim().length > 0) return remoteSource(url.trim());
  return mockSource();
}
