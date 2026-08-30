import React from 'react';
import { Sliders } from 'lucide-react';
import { PagePlaceholder } from './PagePlaceholder';

export const PolicyManagerPage: React.FC = () => (
  <PagePlaceholder
    title="Policy Manager"
    subtitle="Manage merchant recovery guardrails, maximum attempt caps, and cooldown windows"
    stepNumber={35}
    icon={Sliders}
  />
);
