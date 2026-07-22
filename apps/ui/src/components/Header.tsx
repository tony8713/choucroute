import { type ReactNode } from 'react';
import { Button, Col, Row, Text, useTheme, type ThemePreference } from '@choucroute/kit';

interface HeaderProps {
  total: number;
  shown: number;
  sourceLabel: string;
}

const NEXT: Record<ThemePreference, ThemePreference> = {
  system: 'light',
  light: 'dark',
  dark: 'system',
};

const LABEL: Record<ThemePreference, string> = {
  system: 'Auto',
  light: 'Light',
  dark: 'Dark',
};

export function Header({ total, shown, sourceLabel }: HeaderProps): ReactNode {
  const { preference, setPreference } = useTheme();
  return (
    <Row justify="between" align="start" gap={16}>
      <Col gap={4}>
        <Text as="p" role="head" weight="semibold" size="6xl">choucroute</Text>
        <Text role="sub" size="sm">
          {shown === total ? `${String(total)} transcripts` : `${String(shown)} of ${String(total)} transcripts`}
          {' · '}
          {sourceLabel}
        </Text>
      </Col>
      <Button
        size="sm"
        title="Toggle theme"
        onClick={() => { setPreference(NEXT[preference]); }}
      >
        {LABEL[preference]}
      </Button>
    </Row>
  );
}
