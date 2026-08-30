import React from 'react';
import { ListFilter } from 'lucide-react';
import { PagePlaceholder } from './PagePlaceholder';

export const RecoveryQueuePage: React.FC = () => (
  <PagePlaceholder
    title="Recovery Queue"
    subtitle="Filterable list of failed transactions undergoing active AI recovery intervention"
    stepNumber={30}
    icon={ListFilter}
  />
);
