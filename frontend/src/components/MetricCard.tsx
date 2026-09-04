import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react';

export interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: {
    value: string | number;
    isPositive?: boolean;
    isNeutral?: boolean;
  };
  icon: LucideIcon;
  variant?: 'cyan' | 'emerald' | 'purple' | 'rose' | 'amber' | 'blue';
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  icon: Icon,
  variant = 'blue',
  loading = false,
  error = false,
  onRetry,
}) => {
  const variantStyles = {
    blue: {
      badgeBg: 'bg-[#EEF6FF] text-[#2F66F5] border-[#2F66F5]/20',
      borderHover: 'hover:border-[#111827]',
    },
    cyan: {
      badgeBg: 'bg-[#EEF6FF] text-[#2F66F5] border-[#2F66F5]/20',
      borderHover: 'hover:border-[#111827]',
    },
    emerald: {
      badgeBg: 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20',
      borderHover: 'hover:border-[#111827]',
    },
    purple: {
      badgeBg: 'bg-[#EEF6FF] text-[#2F66F5] border-[#2F66F5]/20',
      borderHover: 'hover:border-[#111827]',
    },
    rose: {
      badgeBg: 'bg-[#FDF2F4] text-[#D6455D] border-[#D6455D]/20',
      borderHover: 'hover:border-[#111827]',
    },
    amber: {
      badgeBg: 'bg-[#FDF8EC] text-[#D99A00] border-[#D99A00]/20',
      borderHover: 'hover:border-[#111827]',
    },
  };

  const style = variantStyles[variant] || variantStyles.blue;

  if (loading) {
    return (
      <div className="bg-white rounded-xl p-5 border border-[#D9E1EC] space-y-3 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="h-3 bg-[#F1F5F9] rounded w-24 skeleton-shimmer"></div>
          <div className="w-8 h-8 bg-[#F1F5F9] rounded-lg skeleton-shimmer"></div>
        </div>
        <div className="h-7 bg-[#F1F5F9] rounded w-32 skeleton-shimmer"></div>
        <div className="h-3 bg-[#F1F5F9] rounded w-20 skeleton-shimmer"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#FDF2F4] rounded-xl p-5 border border-[#D6455D]/30 space-y-3 shadow-xs">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#D6455D] uppercase tracking-wider">{title}</span>
          <div className="p-2 rounded-lg bg-[#D6455D]/10 text-[#D6455D] border border-[#D6455D]/20">
            <Icon className="w-4 h-4" />
          </div>
        </div>
        <p className="text-xs text-[#D6455D]">Failed to load metric data.</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-xs font-bold text-[#D6455D] hover:underline"
          >
            Retry Loading
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      className={`bg-white rounded-xl p-5 border border-[#D9E1EC] hover-lift shadow-xs transition-all duration-200 ${style.borderHover}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold text-[#5E6B7E] tracking-wider uppercase">
          {title}
        </span>
        <div className={`p-2 rounded-lg border ${style.badgeBg}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="mt-3">
        <div className="text-3xl font-extrabold text-[#0B1F44] font-numeric tracking-tight">
          {value}
        </div>

        <div className="mt-2 flex items-center justify-between text-xs">
          {subtitle && <span className="text-[#5E6B7E] font-medium">{subtitle}</span>}
          {trend && (
            <span
              className={`inline-flex items-center gap-1 font-bold ${
                trend.isNeutral
                  ? 'text-[#5E6B7E]'
                  : trend.isPositive !== false
                  ? 'text-[#16A36A]'
                  : 'text-[#D6455D]'
              }`}
            >
              {trend.isNeutral ? (
                <Minus className="w-3 h-3" />
              ) : trend.isPositive !== false ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              {trend.value}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default MetricCard;
