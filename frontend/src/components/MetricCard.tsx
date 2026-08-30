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
  variant?: 'cyan' | 'emerald' | 'purple' | 'rose' | 'amber';
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
  variant = 'cyan',
  loading = false,
  error = false,
  onRetry,
}) => {
  const variantStyles = {
    cyan: {
      badgeBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
      glow: 'hover:border-cyan-500/40',
      accentText: 'text-cyan-400',
    },
    emerald: {
      badgeBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      glow: 'hover:border-emerald-500/40',
      accentText: 'text-emerald-400',
    },
    purple: {
      badgeBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      glow: 'hover:border-purple-500/40',
      accentText: 'text-purple-400',
    },
    rose: {
      badgeBg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      glow: 'hover:border-rose-500/40',
      accentText: 'text-rose-400',
    },
    amber: {
      badgeBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      glow: 'hover:border-amber-500/40',
      accentText: 'text-amber-400',
    },
  };

  const style = variantStyles[variant];

  if (loading) {
    return (
      <div className="glass-card rounded-xl p-5 border border-slate-800 animate-pulse space-y-3">
        <div className="flex items-center justify-between">
          <div className="h-4 bg-slate-800 rounded w-24"></div>
          <div className="w-9 h-9 bg-slate-800 rounded-lg"></div>
        </div>
        <div className="h-8 bg-slate-800 rounded w-36"></div>
        <div className="h-3 bg-slate-800 rounded w-28"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card rounded-xl p-5 border border-rose-900/50 bg-rose-950/10 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-rose-400">{title}</span>
          <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
            <Icon className="w-5 h-5" />
          </div>
        </div>
        <p className="text-xs text-rose-300">Failed to load metric data.</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-xs font-semibold text-rose-400 hover:text-rose-300 underline"
          >
            Retry Loading
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      className={`glass-card rounded-xl p-5 border border-slate-800/80 hover-lift transition-all ${style.glow}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400 tracking-wide uppercase">
          {title}
        </span>
        <div className={`p-2 rounded-lg border ${style.badgeBg}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>

      <div className="mt-3">
        <div className="text-2xl font-extrabold text-slate-100 font-display tracking-tight">
          {value}
        </div>

        <div className="mt-2 flex items-center justify-between text-xs">
          {subtitle && <span className="text-slate-400">{subtitle}</span>}
          {trend && (
            <span
              className={`inline-flex items-center gap-1 font-semibold ${
                trend.isNeutral
                  ? 'text-slate-400'
                  : trend.isPositive !== false
                  ? 'text-emerald-400'
                  : 'text-rose-400'
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
