import { type ReactNode } from 'react';
import { Col } from '@stage-labs/kit/react-native/box';
import { Text } from '@stage-labs/kit/react-native/text';
import { Card } from '@stage-labs/kit/react-native/card';

interface NoticeProps {
  title: string;
  detail: string;
  dark: boolean;
}

export function Notice({ title, detail, dark }: NoticeProps): ReactNode {
  return (
    <Card dark={dark} padding={32}>
      <Col gap={6} align="center">
        <Text weight="semibold" size="2xl">{title}</Text>
        <Text role="secondary" size="sm" textAlign="center">{detail}</Text>
      </Col>
    </Card>
  );
}
