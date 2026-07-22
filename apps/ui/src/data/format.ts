const DAY_FORMAT = new Intl.DateTimeFormat('en-US', {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
  year: 'numeric',
});

export function formatDay(day: string): string {
  const parsed = new Date(`${day}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return day;
  return DAY_FORMAT.format(parsed);
}

export function highlightRanges(text: string, query: string): [string, boolean][] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return [[text, false]];
  const out: [string, boolean][] = [];
  const haystack = text.toLowerCase();
  let cursor = 0;
  for (;;) {
    const hit = haystack.indexOf(needle, cursor);
    if (hit === -1) {
      out.push([text.slice(cursor), false]);
      break;
    }
    if (hit > cursor) out.push([text.slice(cursor, hit), false]);
    out.push([text.slice(hit, hit + needle.length), true]);
    cursor = hit + needle.length;
  }
  return out;
}
