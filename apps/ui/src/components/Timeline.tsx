import { type ReactNode } from 'react';
import { Box, Col, Row } from '@stage-labs/kit/react-native/box';
import { Text } from '@stage-labs/kit/react-native/text';
import { Card } from '@stage-labs/kit/react-native/card';
import { useKitPalette } from '@stage-labs/kit/react-native/theme-context';
import { type DayGroup } from '../data/types';
import { formatDay } from '../data/format';
import { EntryRow } from './EntryRow';

interface TimelineProps {
  groups: DayGroup[];
  query: string;
  dark: boolean;
}

function DaySection({ group, query, dark }: { group: DayGroup; query: string; dark: boolean }): ReactNode {
  const palette = useKitPalette();
  return (
    <Col gap={4}>
      <Row justify="between" align="center" style={{ paddingBottom: 4 }}>
        <Text weight="semibold" size="2xl">{formatDay(group.day)}</Text>
        <Text role="secondary" size="xs">
          {group.entries.length} {group.entries.length === 1 ? 'entry' : 'entries'}
        </Text>
      </Row>
      <Card dark={dark} style={{ paddingTop: 4, paddingBottom: 4, paddingLeft: 16, paddingRight: 16 }}>
        {group.entries.map((entry, i) => (
          <Box key={entry.id} style={{ borderTopWidth: i === 0 ? 0 : 1, borderTopColor: palette.border }}>
            <EntryRow entry={entry} query={query} />
          </Box>
        ))}
      </Card>
    </Col>
  );
}

export function Timeline({ groups, query, dark }: TimelineProps): ReactNode {
  return (
    <Col gap={28}>
      {groups.map((group) => (
        <DaySection key={group.day} group={group} query={query} dark={dark} />
      ))}
    </Col>
  );
}
