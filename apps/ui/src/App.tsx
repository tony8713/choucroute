import { type ReactNode, useMemo, useState } from 'react';
import { Box, Col } from '@stage-labs/kit/react-native/box';
import { KitThemeProvider } from '@stage-labs/kit/react-native/theme-context';
import { type ThemePreference, buildPalette, resolveScheme } from './theme';
import { useTranscripts } from './useTranscripts';
import { EMPTY_FILTER, collectRooms, filterEntries, groupByDay } from './data/filter';
import { Header } from './components/Header';
import { Toolbar } from './components/Toolbar';
import { Timeline } from './components/Timeline';
import { Notice } from './components/Notice';

interface MonitorProps {
  preference: ThemePreference;
  onPreferenceChange: (preference: ThemePreference) => void;
  dark: boolean;
}

function Monitor({ preference, onPreferenceChange, dark }: MonitorProps): ReactNode {
  const { status, entries, error, sourceLabel } = useTranscripts();
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const rooms = useMemo(() => collectRooms(entries), [entries]);
  const filtered = useMemo(() => filterEntries(entries, filter), [entries, filter]);
  const groups = useMemo(() => groupByDay(filtered), [filtered]);

  if (status === 'loading') {
    return <Notice title="Loading" detail="Reading transcripts from the configured source." dark={dark} />;
  }
  if (status === 'error') {
    return <Notice title="Could not load transcripts" detail={error ?? 'Unknown error.'} dark={dark} />;
  }

  return (
    <Col gap={24}>
      <Header
        total={entries.length}
        shown={filtered.length}
        sourceLabel={sourceLabel}
        preference={preference}
        onPreferenceChange={onPreferenceChange}
      />
      <Toolbar
        filter={filter}
        rooms={rooms}
        onChange={setFilter}
        onReset={() => { setFilter(EMPTY_FILTER); }}
      />
      {groups.length > 0 ? (
        <Timeline groups={groups} query={filter.query} dark={dark} />
      ) : (
        <Notice title="No matches" detail="No transcript entries match the current search and filters." dark={dark} />
      )}
    </Col>
  );
}

export function App(): ReactNode {
  const [preference, setPreference] = useState<ThemePreference>('system');
  const scheme = resolveScheme(preference);
  const palette = buildPalette(scheme);
  return (
    <KitThemeProvider value={palette} scheme={scheme}>
      <Box background={palette.bg} style={{ minHeight: '100%' }}>
        <Box
          style={{
            width: '100%',
            maxWidth: 820,
            alignSelf: 'center',
            paddingTop: 48,
            paddingBottom: 96,
            paddingLeft: 20,
            paddingRight: 20,
          }}
        >
          <Monitor preference={preference} onPreferenceChange={setPreference} dark={scheme === 'dark'} />
        </Box>
      </Box>
    </KitThemeProvider>
  );
}
