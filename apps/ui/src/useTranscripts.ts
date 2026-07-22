import { useEffect, useState } from 'react';
import { type TranscriptEntry } from './data/types';
import { resolveSource } from './data/source';

type Status = 'loading' | 'ready' | 'error';

interface TranscriptsState {
  status: Status;
  entries: TranscriptEntry[];
  error: string | null;
  sourceLabel: string;
}

export function useTranscripts(): TranscriptsState {
  const [state, setState] = useState<TranscriptsState>({
    status: 'loading',
    entries: [],
    error: null,
    sourceLabel: '',
  });

  useEffect(() => {
    let active = true;
    const source = resolveSource();
    source
      .load()
      .then((entries) => {
        if (!active) return;
        setState({ status: 'ready', entries, error: null, sourceLabel: source.label });
      })
      .catch((err: unknown) => {
        if (!active) return;
        const message = err instanceof Error ? err.message : 'failed to load transcripts';
        setState({ status: 'error', entries: [], error: message, sourceLabel: source.label });
      });
    return () => { active = false; };
  }, []);

  return state;
}
