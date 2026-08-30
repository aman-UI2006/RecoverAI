import React from 'react';
import { FileText } from 'lucide-react';
import { PagePlaceholder } from './PagePlaceholder';

export const TransactionDetailPage: React.FC = () => (
  <PagePlaceholder
    title="Transaction Detail"
    subtitle="Deep inspection of transaction lifecycle, attempt history, and cryptographic audit chain"
    stepNumber={31}
    icon={FileText}
  />
);
