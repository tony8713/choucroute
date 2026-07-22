import { type ReactNode } from 'react';
import { Card, Col, Row, Text, usePalette } from '@choucroute/kit';
import { type DayGroup } from '../data/types';
import { formatDay } from '../data/format';
import { EntryRow } from './EntryRow';

interface TimelineProps {
  groups: DayGroup[];
  query: string;
}

function DaySection({ group, query }: { group: DayGroup; query: string }): ReactNode {
  const p = usePalette();
  return (
    <Col gap={4}>
      <Row justify="between" align="center" style={{ paddingBottom: 4 }}>
        <Text as="p" role="head" weight="semibold" size="2xl">
          {formatDay(group.day)}
        </Text>
        <Text role="sub" size="xs">
          {group.entries.length} {group.entries.length === 1 ? 'entry' : 'entries'}
        </Text>
      </Row>
      <Card padding={4} style={{ padding: '4px 16px' }}>
        {group.entries.map((entry, i) => (
          <div
            key={entry.id}
            style={{ borderTop: i === 0 ? 'none' : `1px solid ${p.border}` }}
          >
            <EntryRow entry={entry} query={query} />
          </div>
        ))}
      </Card>
    </Col>
  );
}

export function Timeline({ groups, query }: TimelineProps): ReactNode {
  return (
    <Col gap={28}>
      {groups.map((group) => (
        <DaySection key={group.day} group={group} query={query} />
      ))}
    </Col>
  );
}
