import { type ReactNode } from 'react';
import { Card, Col, Text } from '@choucroute/kit';

interface NoticeProps {
  title: string;
  detail: string;
}

export function Notice({ title, detail }: NoticeProps): ReactNode {
  return (
    <Card padding={32}>
      <Col gap={6} align="center">
        <Text role="head" weight="semibold" size="2xl">{title}</Text>
        <Text role="sub" size="sm" style={{ textAlign: 'center' }}>{detail}</Text>
      </Col>
    </Card>
  );
}
