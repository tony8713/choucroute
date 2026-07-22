import { type ReactNode, useMemo, useState } from 'react';
import { Col, usePalette } from '@choucroute/kit';
import { useTranscripts } from './useTranscripts';
import { EMPTY_FILTER, collectRooms, filterEntries, groupByDay } from './data/filter';
import { Header } from './components/Header';
import { Toolbar } from './components/Toolbar';
import { Timeline } from './components/Timeline';
import { Notice } from './components/Notice';

function useFilteredView(): ReactNode {
  const { status, entries, error, sourceLabel } = useTranscripts();
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const rooms = useMemo(() => collectRooms(entries), [entries]);
  const filtered = useMemo(() => filterEntries(entries, filter), [entries, filter]);
  const groups = useMemo(() => groupByDay(filtered), [filtered]);

  if (status === 'loading') return <Notice title="Loading" detail="Reading transcripts from the configured source." />;
  if (status === 'error') return <Notice title="Could not load transcripts" detail={error ?? 'Unknown error.'} />;

  return (
    <Col gap={24}>
      <Header total={entries.length} shown={filtered.length} sourceLabel={sourceLabel} />
      <Toolbar
        filter={filter}
        rooms={rooms}
        onChange={setFilter}
        onReset={() => { setFilter(EMPTY_FILTER); }}
      />
      {groups.length > 0 ? (
        <Timeline groups={groups} query={filter.query} />
      ) : (
        <Notice title="No matches" detail="No transcript entries match the current search and filters." />
      )}
    </Col>
  );
}

export function App(): ReactNode {
  const p = usePalette();
  const view = useFilteredView();
  return (
    <div style={{ minHeight: '100vh', background: p.bg }}>
      <main style={{ maxWidth: 820, margin: '0 auto', padding: '48px 20px 96px' }}>{view}</main>
    </div>
  );
}
