import React from 'react';
import {
  AlertCircle,
  Stethoscope,
  Brain,
  ShieldCheck,
  PlayCircle,
  CheckCircle2,
  XCircle,
  UserCheck,
  Clock,
} from 'lucide-react';

interface LifecycleStepperProps {
  currentStatus: string;
}

interface StepDefinition {
  key: string;
  label: string;
  description: string;
  icon: React.ElementType;
}

const LIFECYCLE_STEPS: StepDefinition[] = [
  {
    key: 'DETECTED',
    label: '1. Detect',
    description: 'Payment Failure Ingested',
    icon: AlertCircle,
  },
  {
    key: 'DIAGNOSED',
    label: '2. Diagnose',
    description: 'Root Cause Classified',
    icon: Stethoscope,
  },
  {
    key: 'INTERVENTION_SELECTED',
    label: '3. Decide',
    description: 'AI Action Recommended',
    icon: Brain,
  },
  {
    key: 'APPROVED',
    label: '4. Policy Gate',
    description: 'Safety Rules Approved',
    icon: ShieldCheck,
  },
  {
    key: 'EXECUTING',
    label: '5. Execute',
    description: 'Intervention Dispatched',
    icon: PlayCircle,
  },
  {
    key: 'RECOVERED',
    label: '6. Verified',
    description: 'Terminal Outcome',
    icon: CheckCircle2,
  },
];

const STATUS_ORDER: Record<string, number> = {
  DETECTED: 1,
  DIAGNOSED: 2,
  INTERVENTION_SELECTED: 3,
  APPROVED: 4,
  EXECUTING: 5,
  RECOVERED: 6,
  FAILED: 6,
  STOPPED: 6,
  EXPIRED: 6,
  ESCALATED: 4,
  MANUAL_REVIEW: 4,
};

export const LifecycleStepper: React.FC<LifecycleStepperProps> = ({ currentStatus }) => {
  const currentStepNum = STATUS_ORDER[currentStatus?.toUpperCase()] || 1;
  const isFailedTerminal = ['FAILED', 'STOPPED', 'EXPIRED'].includes(currentStatus?.toUpperCase());
  const isEscalated = ['ESCALATED', 'MANUAL_REVIEW'].includes(currentStatus?.toUpperCase());

  return (
    <div className="w-full space-y-3">
      <div className="flex items-center justify-between text-xs font-semibold text-slate-400 mb-2">
        <span>End-to-End Recovery Flow</span>
        <span className="font-mono text-cyan-400">Current Status: {currentStatus}</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {LIFECYCLE_STEPS.map((step, idx) => {
          const stepNum = idx + 1;
          const isCompleted = currentStepNum > stepNum || (currentStepNum === 6 && stepNum === 6 && currentStatus === 'RECOVERED');
          const isCurrent = currentStepNum === stepNum && !(stepNum === 6 && isCompleted);
          const isTerminalStep = stepNum === 6;

          let IconComponent = step.icon;
          let badgeColor = 'bg-slate-900 text-slate-500 border-slate-800';
          let textColor = 'text-slate-500';

          if (isCompleted) {
            badgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
            textColor = 'text-emerald-400';
          } else if (isCurrent) {
            if (isTerminalStep && isFailedTerminal) {
              badgeColor = 'bg-rose-500/10 text-rose-400 border-rose-500/40 shadow-sm shadow-rose-500/10';
              textColor = 'text-rose-400';
              IconComponent = XCircle;
            } else if (isEscalated && stepNum === 4) {
              badgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/40 shadow-sm shadow-amber-500/10';
              textColor = 'text-amber-400';
              IconComponent = UserCheck;
            } else {
              badgeColor = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/40 shadow-sm shadow-cyan-500/10';
              textColor = 'text-cyan-400';
            }
          }

          return (
            <div
              key={step.key}
              className={`flex flex-col items-center text-center p-3 rounded-xl border transition-all ${badgeColor}`}
            >
              <div className="p-2 rounded-full mb-1.5 bg-slate-950/60 border border-slate-800">
                <IconComponent className={`w-4 h-4 ${isCurrent ? 'animate-pulse' : ''}`} />
              </div>
              <div className={`text-xs font-bold ${textColor}`}>{step.label}</div>
              <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">{step.description}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
