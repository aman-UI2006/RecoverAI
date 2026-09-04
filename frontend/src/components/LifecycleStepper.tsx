import React from 'react';
import {
  AlertCircle,
  Stethoscope,
  Brain,
  PlayCircle,
  CheckCircle2,
  XCircle,
  UserCheck,
  Award,
  BarChart,
  Lock,
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
    key: 'DETECT',
    label: '1. Detect',
    description: 'Failure Ingested',
    icon: AlertCircle,
  },
  {
    key: 'DIAGNOSE',
    label: '2. Diagnose',
    description: 'Root Cause Classified',
    icon: Stethoscope,
  },
  {
    key: 'DECIDE',
    label: '3. Decide',
    description: 'AI Strategy & ENRV',
    icon: Brain,
  },
  {
    key: 'EXECUTE',
    label: '5. Execute',
    description: 'Action Dispatched',
    icon: PlayCircle,
  },
  {
    key: 'VERIFY',
    label: '5. Verify',
    description: 'Webhook Verification',
    icon: CheckCircle2,
  },
  {
    key: 'ATTRIBUTE',
    label: '6. Attribute',
    description: 'Direct Reference Match',
    icon: Award,
  },
  {
    key: 'MEASURE',
    label: '7. Measure',
    description: 'Incremental Value',
    icon: BarChart,
  },
  {
    key: 'AUDIT',
    label: '8. Audit',
    description: 'SHA-256 Hash Chain',
    icon: Lock,
  },
];

const STATUS_ORDER: Record<string, number> = {
  AT_RISK: 1,
  DETECTED: 1,
  DIAGNOSED: 2,
  INTERVENTION_SELECTED: 3,
  APPROVED: 3,
  EXECUTING: 4,
  RECOVERED: 8,
  FAILED: 8,
  STOPPED: 8,
  EXPIRED: 8,
  ESCALATED: 3,
  MANUAL_REVIEW: 3,
};

export const LifecycleStepper: React.FC<LifecycleStepperProps> = ({ currentStatus }) => {
  const normalizedStatus = currentStatus?.toUpperCase() || 'AT_RISK';
  const currentStepNum = STATUS_ORDER[normalizedStatus] || 1;
  const isFailedTerminal = ['FAILED', 'STOPPED', 'EXPIRED'].includes(normalizedStatus);
  const isEscalated = ['ESCALATED', 'MANUAL_REVIEW'].includes(normalizedStatus);

  return (
    <div className="w-full space-y-4 font-sans">
      <div className="flex items-center justify-between text-xs font-bold text-[#5E6B7E]">
        <span className="uppercase tracking-wider font-bold text-[11px] text-[#0B1F44]">
          End-to-End Recovery Flow
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[#5E6B7E] font-bold">
            Current Status: {currentStatus}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
        {LIFECYCLE_STEPS.map((step, idx) => {
          const stepNum = idx + 1;
          const isCompleted = currentStepNum > stepNum || (currentStepNum === 8 && stepNum === 8 && normalizedStatus === 'RECOVERED');
          const isCurrent = currentStepNum === stepNum && !(stepNum === 8 && isCompleted);

          let IconComponent = step.icon;
          let badgeColor = 'bg-white text-[#5E6B7E] border-[#D9E1EC]';
          let textColor = 'text-[#5E6B7E]';
          let iconColor = 'text-[#5E6B7E]';
          let iconBg = 'bg-[#F8FAFD] border-[#D9E1EC]';

          if (isCompleted) {
            badgeColor = 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/30';
            textColor = 'text-[#16A36A]';
            iconColor = 'text-[#16A36A]';
            iconBg = 'bg-white border-[#16A36A]/20';
          } else if (isCurrent) {
            if (isFailedTerminal) {
              badgeColor = 'bg-[#FDF2F4] text-[#D6455D] border-[#111827] shadow-sm pulse-node';
              textColor = 'text-[#D6455D]';
              iconColor = 'text-[#D6455D]';
              iconBg = 'bg-white border-[#D6455D]/20';
              IconComponent = XCircle;
            } else if (isEscalated) {
              badgeColor = 'bg-[#FDF8EC] text-[#D99A00] border-[#111827] shadow-sm pulse-node';
              textColor = 'text-[#D99A00]';
              iconColor = 'text-[#D99A00]';
              iconBg = 'bg-white border-[#D99A00]/20';
              IconComponent = UserCheck;
            } else {
              badgeColor = 'bg-[#EEF6FF] text-[#2F66F5] border-[#111827] shadow-md pulse-node';
              textColor = 'text-[#2F66F5]';
              iconColor = 'text-[#2F66F5]';
              iconBg = 'bg-white border-[#2F66F5]/30';
            }
          }

          return (
            <div
              key={step.key}
              className={`flex flex-col items-center text-center p-3 rounded-xl border transition-all duration-200 ${badgeColor}`}
            >
              <div className={`p-1.5 rounded-lg mb-1.5 border ${iconBg}`}>
                <IconComponent className={`w-4 h-4 ${iconColor} ${isCurrent ? 'animate-pulse' : ''}`} />
              </div>
              <div className={`text-[11px] font-bold ${textColor}`}>{step.label}</div>
              <div className="text-[9px] font-semibold text-[#5E6B7E] mt-0.5 leading-tight">{step.description}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
