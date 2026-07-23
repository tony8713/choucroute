import { type DayGroup, type TranscriptEntry } from './types';

export interface TranscriptFilter {
  query: string;
  from: string;
  to: string;
  room: string | null;
}

export const EMPTY_FILTER: TranscriptFilter = { query: '', from: '', to: '', room: null };

function matchesQuery(entry: TranscriptEntry, query: string): boolean {
  if (query.length === 0) return true;
  return entry.text.toLowerCase().includes(query);
}

function matchesRange(day: string, from: string, to: string): boolean {
  if (from.length > 0 && day < from) return false;
  if (to.length > 0 && day > to) return false;
  return true;
}

export function filterEntries(entries: TranscriptEntry[], filter: TranscriptFilter): TranscriptEntry[] {
  const query = filter.query.trim().toLowerCase();
  return entries.filter(
    (entry) =>
      matchesQuery(entry, query) &&
      matchesRange(entry.day, filter.from, filter.to) &&
      (filter.room === null || entry.room === filter.room),
  );
}

export function groupByDay(entries: TranscriptEntry[]): DayGroup[] {
  const groups = new Map<string, TranscriptEntry[]>();
  for (const entry of entries) {
    const bucket = groups.get(entry.day) ?? [];
    bucket.push(entry);
    groups.set(entry.day, bucket);
  }
  return [...groups.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([day, dayEntries]) => ({ day, entries: dayEntries }));
}

export function collectRooms(entries: TranscriptEntry[]): string[] {
  const rooms = new Set<string>();
  for (const entry of entries) {
    if (entry.room !== null) rooms.add(entry.room);
  }
  return [...rooms].sort((a, b) => a.localeCompare(b));
}
