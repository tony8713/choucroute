import { type ReactNode } from 'react';
import { Box, Col, Row } from '@stage-labs/kit/react-native/box';
import { Text } from '@stage-labs/kit/react-native/text';
import { Button } from '@stage-labs/kit/react-native/button';
import { Input } from '@stage-labs/kit/react-native/input';
import { type TranscriptFilter } from '../data/filter';

interface ToolbarProps {
  filter: TranscriptFilter;
  rooms: string[];
  onChange: (next: TranscriptFilter) => void;
  onReset: () => void;
}

function RoomButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }): ReactNode {
  return (
    <Button
      size="sm"
      color={active ? 'primary' : 'secondary'}
      variant={active ? 'solid' : 'soft'}
      onPress={onPress}
      label={label}
    />
  );
}

export function Toolbar({ filter, rooms, onChange, onReset }: ToolbarProps): ReactNode {
  return (
    <Col gap={12}>
      <Row gap={10} wrap align="center">
        <Box flex={1} style={{ minWidth: 220 }}>
          <Input
            value={filter.query}
            onChangeText={(query) => { onChange({ ...filter, query }); }}
            placeholder="Search transcripts"
            style={{ width: '100%' }}
          />
        </Box>
        <Row gap={6} align="center">
          <Text role="secondary" size="xs">from</Text>
          <Input
            value={filter.from}
            onChangeText={(from) => { onChange({ ...filter, from }); }}
            placeholder="YYYY-MM-DD"
            style={{ width: 128 }}
          />
          <Text role="secondary" size="xs">to</Text>
          <Input
            value={filter.to}
            onChangeText={(to) => { onChange({ ...filter, to }); }}
            placeholder="YYYY-MM-DD"
            style={{ width: 128 }}
          />
        </Row>
        <Button variant="ghost" color="secondary" size="sm" onPress={onReset} label="Reset" />
      </Row>
      {rooms.length > 0 ? (
        <Row gap={6} wrap align="center">
          <RoomButton label="All rooms" active={filter.room === null} onPress={() => { onChange({ ...filter, room: null }); }} />
          {rooms.map((room) => (
            <RoomButton
              key={room}
              label={room}
              active={filter.room === room}
              onPress={() => { onChange({ ...filter, room }); }}
            />
          ))}
        </Row>
      ) : null}
    </Col>
  );
}
