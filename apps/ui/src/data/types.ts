export interface TranscriptEntry {
  id: string;
  day: string;
  time: string;
  timestamp: number;
  room: string | null;
  text: string;
}

export interface TranscriptSource {
  label: string;
  load: () => Promise<TranscriptEntry[]>;
}

export interface DayGroup {
  day: string;
  entries: TranscriptEntry[];
}
