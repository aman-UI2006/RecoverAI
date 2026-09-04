import React from 'react';

export const AnimatedBackground: React.FC = () => {
  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 pointer-events-none overflow-hidden -z-10 bg-[#F8FAFC]"
    >
      {/* 1. Base Gradient Atmosphere */}
      <div className="absolute inset-0 bg-radial-[at_top_right] from-blue-100/40 via-sky-50/20 to-transparent" />
      
      {/* 2. Diagonal Translucent Light Beams (Layer 1 - Slow Sweep 28s) */}
      <div
        className="absolute -top-[50%] -left-[20%] w-[140%] h-[200%] opacity-40 animate-beam-sweep-1"
        style={{
          background:
            'linear-gradient(135deg, rgba(219,234,254,0) 0%, rgba(224,242,254,0.3) 30%, rgba(191,219,254,0.15) 50%, rgba(219,234,254,0) 75%)',
          transform: 'rotate(-25deg)',
        }}
      />

      {/* 3. Diagonal Translucent Light Beams (Layer 2 - Reverse Drift 36s) */}
      <div
        className="absolute -top-[40%] -right-[30%] w-[150%] h-[180%] opacity-35 animate-beam-sweep-2"
        style={{
          background:
            'linear-gradient(115deg, rgba(224,242,254,0) 0%, rgba(186,230,253,0.25) 40%, rgba(219,234,254,0.12) 65%, rgba(224,242,254,0) 90%)',
          transform: 'rotate(-15deg)',
        }}
      />

      {/* 4. Top-Right Hero Soft Cyan Illumination Glow */}
      <div className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full bg-cyan-200/25 blur-3xl animate-pulse-glow" />

      {/* 5. Subtle Floating Fintech / Recovery Decorative Symbols & Animated Moving Dots */}
      <div className="absolute inset-0 opacity-[0.25] select-none pointer-events-none">
        {/* Animated Moving Dot 1 - Top Left Cyan */}
        <div className="absolute top-[18%] left-[12%] w-2.5 h-2.5 rounded-full bg-cyan-400/80 blur-[0.5px] shadow-[0_0_8px_rgba(34,211,238,0.8)] animate-float-dot-1" />

        {/* Animated Moving Dot 2 - Top Right Blue */}
        <div className="absolute top-[28%] right-[16%] w-3 h-3 rounded-full bg-blue-500/80 blur-[0.5px] shadow-[0_0_10px_rgba(59,130,246,0.8)] animate-float-dot-2" />

        {/* Animated Moving Dot 3 - Mid Left Sky Blue */}
        <div className="absolute top-[48%] left-[22%] w-2 h-2 rounded-full bg-sky-400/90 blur-[0.5px] shadow-[0_0_6px_rgba(56,189,248,0.8)] animate-float-dot-3" />

        {/* Animated Moving Dot 4 - Center Right Teal */}
        <div className="absolute top-[58%] right-[28%] w-3.5 h-3.5 rounded-full bg-teal-400/70 blur-[0.5px] shadow-[0_0_12px_rgba(45,212,191,0.8)] animate-float-dot-4" />

        {/* Animated Moving Dot 5 - Bottom Left Blue */}
        <div className="absolute top-[78%] left-[14%] w-2.5 h-2.5 rounded-full bg-blue-400/80 blur-[0.5px] shadow-[0_0_8px_rgba(96,165,250,0.8)] animate-float-dot-2" />

        {/* Animated Moving Dot 6 - Bottom Right Cyan */}
        <div className="absolute top-[82%] right-[10%] w-2 h-2 rounded-full bg-cyan-300/90 blur-[0.5px] shadow-[0_0_6px_rgba(103,232,249,0.8)] animate-float-dot-1" />

        {/* Decorative Symbols Layer (Opacity 4-6%) */}
        <div className="absolute inset-0 opacity-[0.2] text-slate-700">
          <div className="absolute top-[12%] left-[8%] animate-float-symbol-1 text-2xl font-light">+</div>
          <div className="absolute top-[35%] right-[10%] animate-float-symbol-2 text-xl font-light">+</div>
          <div className="absolute top-[65%] left-[15%] animate-float-symbol-3 text-3xl font-light">+</div>
          <svg
            className="absolute top-[25%] left-[45%] w-8 h-8 animate-float-symbol-2"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
          </svg>
          <svg
            className="absolute top-[75%] right-[22%] w-10 h-10 animate-float-symbol-1"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751A11.959 11.959 0 0112 2.714z" />
          </svg>
        </div>
      </div>
    </div>
  );
};
