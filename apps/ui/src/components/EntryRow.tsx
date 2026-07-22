import { type ReactNode } from 'react';
import { Badge, Row, Text, usePalette } from '@choucroute/kit';
import { type TranscriptEntry } from '../data/types';
import { highlightRanges } from '../data/format';

interface EntryRowProps {
  entry: TranscriptEntry;
  query: string;
}

export function EntryRow({ entry, query }: EntryRowProps): ReactNode {
  const p = usePalette();
  const parts = highlightRanges(entry.text, query);
  return (
    <Row gap={12} align="start" style={{ padding: '10px 0' }}>
      <Text mono role="sub" size="sm" style={{ width: 44, flexShrink: 0, paddingTop: 1 }}>
        {entry.time}
      </Text>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Text role="body" size="md" style={{ display: 'block' }}>
          {parts.map(([chunk, hit], i) =>
            hit ? (
              <mark
                key={i}
                style={{ background: p.success, color: p.onPrimary, borderRadius: 4, padding: '0 2px' }}
              >
                {chunk}
              </mark>
            ) : (
              <span key={i}>{chunk}</span>
            ),
          )}
        </Text>
      </div>
      {entry.room !== null ? <Badge>{entry.room}</Badge> : null}
    </Row>
  );
}
