import React from 'react';
import { LucideIcon } from 'lucide-react';

interface PagePlaceholderProps {
  title: string;
  subtitle: string;
  stepNumber: number;
  icon: LucideIcon;
}

export const PagePlaceholder: React.FC<PagePlaceholderProps> = ({
  title,
  subtitle,
  stepNumber,
  icon: Icon,
}) => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 font-display flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-800 text-cyan-400 border border-slate-700">
              <Icon className="w-6 h-6" />
            </div>
            {title}
          </h1>
          <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
        </div>
        <span className="px-3 py-1 text-xs font-semibold rounded-full bg-slate-800 text-slate-300 border border-slate-700">
          Step {stepNumber} Component Frame
        </span>
      </div>

      <div className="glass-card rounded-xl p-8 border border-slate-800 text-center space-y-4">
        <div className="inline-flex p-4 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
          <Icon className="w-10 h-10" />
        </div>
        <h2 className="text-lg font-semibold text-slate-200">{title} Dashboard Page Ready</h2>
        <p className="text-sm text-slate-400 max-w-lg mx-auto">
          Frontend layout framework, dark-mode tokens, and API bindings active for {title}. Concrete metrics, tables, and AI decision views will be integrated in Step {stepNumber}.
        </p>
      </div>
    </div>
  );
};
