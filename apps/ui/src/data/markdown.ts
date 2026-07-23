import { type TranscriptEntry } from './types';

const DAY_RE = /^#\s+(\d{4}-\d{2}-\d{2})\s*$/;
const ENTRY_RE = /^-\s+\*\*(\d{2}:\d{2})\*\*(?:\s+_\(([^)]+)\)_)?\s+(.*)$/;

function toTimestamp(day: string, time: string): number {
  return new Date(`${day}T${time}:00`).getTime();
}

export function parseTranscriptMarkdown(markdown: string): TranscriptEntry[] {
  const entries: TranscriptEntry[] = [];
  let day: string | null = null;
  let index = 0;
  for (const rawLine of markdown.split('\n')) {
    const line = rawLine.trimEnd();
    const dayMatch = DAY_RE.exec(line);
    if (dayMatch?.[1] !== undefined) {
      day = dayMatch[1];
      continue;
    }
    const entryMatch = ENTRY_RE.exec(line);
    if (day === null || entryMatch === null) continue;
    const time = entryMatch[1] ?? '';
    const room = entryMatch[2] ?? null;
    const text = (entryMatch[3] ?? '').trim();
    if (text.length === 0) continue;
    entries.push({
      id: `${day}-${time}-${String(index)}`,
      day,
      time,
      timestamp: toTimestamp(day, time),
      room,
      text,
    });
    index += 1;
  }
  return entries;
}
