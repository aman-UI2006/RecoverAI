import React from 'react';
import { Cpu } from 'lucide-react';
import { PagePlaceholder } from './PagePlaceholder';

export const AIDecisionCenterPage: React.FC = () => (
  <PagePlaceholder
    title="AI Decision Center"
    subtitle="Inspect model inference scores, ENRV calculations, and rule/LLM decision rationale"
    stepNumber={32}
    icon={Cpu}
  />
);
