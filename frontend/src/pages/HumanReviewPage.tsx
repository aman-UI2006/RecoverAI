import React from 'react';
import { UserCheck } from 'lucide-react';
import { PagePlaceholder } from './PagePlaceholder';

export const HumanReviewPage: React.FC = () => (
  <PagePlaceholder
    title="Human Review Queue"
    subtitle="Process escalated high-value or policy-rejected transactions requiring human approval"
    stepNumber={36}
    icon={UserCheck}
  />
);
