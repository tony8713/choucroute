import { type ReactNode } from 'react';
import { Button, Col, Input, Row, Text } from '@choucroute/kit';
import { type TranscriptFilter } from '../data/filter';

interface ToolbarProps {
  filter: TranscriptFilter;
  rooms: string[];
  onChange: (next: TranscriptFilter) => void;
  onReset: () => void;
}

export function Toolbar({ filter, rooms, onChange, onReset }: ToolbarProps): ReactNode {
  return (
    <Col gap={12}>
      <Row gap={10} wrap align="center">
        <div style={{ flex: 1, minWidth: 220, display: 'flex' }}>
          <Input
            type="search"
            value={filter.query}
            onChange={(query) => { onChange({ ...filter, query }); }}
            placeholder="Search transcripts"
            style={{ flex: 1 }}
          />
        </div>
        <Row gap={6} align="center">
          <Text role="sub" size="xs">from</Text>
          <Input
            type="date"
            ariaLabel="From date"
            value={filter.from}
            onChange={(from) => { onChange({ ...filter, from }); }}
          />
          <Text role="sub" size="xs">to</Text>
          <Input
            type="date"
            ariaLabel="To date"
            value={filter.to}
            onChange={(to) => { onChange({ ...filter, to }); }}
          />
        </Row>
        <Button variant="ghost" size="sm" onClick={onReset}>Reset</Button>
      </Row>
      {rooms.length > 0 ? (
        <Row gap={6} wrap align="center">
          <Button
            size="sm"
            active={filter.room === null}
            onClick={() => { onChange({ ...filter, room: null }); }}
          >
            All rooms
          </Button>
          {rooms.map((room) => (
            <Button
              key={room}
              size="sm"
              active={filter.room === room}
              onClick={() => { onChange({ ...filter, room }); }}
            >
              {room}
            </Button>
          ))}
        </Row>
      ) : null}
    </Col>
  );
}
