import { type ReactNode } from 'react';
import { Col, Row } from '@stage-labs/kit/react-native/box';
import { Text } from '@stage-labs/kit/react-native/text';
import { Button } from '@stage-labs/kit/react-native/button';
import { type ThemePreference } from '../theme';

interface HeaderProps {
  total: number;
  shown: number;
  sourceLabel: string;
  preference: ThemePreference;
  onPreferenceChange: (preference: ThemePreference) => void;
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

export function Header({ total, shown, sourceLabel, preference, onPreferenceChange }: HeaderProps): ReactNode {
  return (
    <Row justify="between" align="start" gap={16}>
      <Col gap={4}>
        <Text weight="semibold" size="6xl">choucroute</Text>
        <Text role="secondary" size="sm">
          {shown === total ? `${String(total)} transcripts` : `${String(shown)} of ${String(total)} transcripts`}
          {' · '}
          {sourceLabel}
        </Text>
      </Col>
      <Button
        color="secondary"
        variant="soft"
        size="sm"
        onPress={() => { onPreferenceChange(NEXT[preference]); }}
        label={LABEL[preference]}
      />
    </Row>
  );
}
