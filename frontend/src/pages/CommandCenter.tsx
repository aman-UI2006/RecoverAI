import React from 'react';
import { LayoutDashboard } from 'lucide-react';
import { PagePlaceholder } from './PagePlaceholder';

export const CommandCenterPage: React.FC = () => (
  <PagePlaceholder
    title="Command Center"
    subtitle="Executive overview of revenue recovery performance, incremental lift, and active queues"
    stepNumber={28}
    icon={LayoutDashboard}
  />
);
