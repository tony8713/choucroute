import { type ReactNode } from 'react';
import { Box, Row } from '@stage-labs/kit/react-native/box';
import { Text } from '@stage-labs/kit/react-native/text';
import { useKitPalette } from '@stage-labs/kit/react-native/theme-context';
import { type TranscriptEntry } from '../data/types';
import { highlightRanges } from '../data/format';

function RoomBadge({ room }: { room: string }): ReactNode {
  const palette = useKitPalette();
  return (
    <Box background={palette.inputBg} radius={999} padding={{ x: 8, y: 2 }}>
      <Text size="xs" role="secondary">{room}</Text>
    </Box>
  );
}

export function EntryRow({ entry, query }: { entry: TranscriptEntry; query: string }): ReactNode {
  const palette = useKitPalette();
  const parts = highlightRanges(entry.text, query);
  return (
    <Row gap={12} align="start" style={{ paddingTop: 10, paddingBottom: 10 }}>
      <Text variant="mono" role="secondary" size="sm" style={{ width: 44, flexShrink: 0, paddingTop: 1 }}>
        {entry.time}
      </Text>
      <Box flex={1} style={{ minWidth: 0 }}>
        <Text size="md">
          {parts.map(([chunk, hit], i) =>
            hit ? (
              <Text key={i} size="md" color={palette.bg} style={{ backgroundColor: palette.success, borderRadius: 4 }}>
                {chunk}
              </Text>
            ) : (
              <Text key={i} size="md">{chunk}</Text>
            ),
          )}
        </Text>
      </Box>
      {entry.room !== null ? <RoomBadge room={entry.room} /> : null}
    </Row>
  );
}
