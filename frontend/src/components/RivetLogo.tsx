import React from 'react';

interface RivetLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export const RivetLogo: React.FC<RivetLogoProps> = ({ size = 'md', className = '' }) => {
  const dimensions = {
    sm: { w: 16, h: 16 },
    md: { w: 24, h: 24 },
    lg: { w: 32, h: 32 },
    xl: { w: 48, h: 48 },
  }[size];

  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 select-none ${className}`}
      style={{ width: dimensions.w, height: dimensions.h }}
      aria-label="Rivet logo"
    >
      <svg
        width={dimensions.w}
        height={dimensions.h}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="relative z-10"
      >
        <defs>
          {/* Graphite Bar 1: Primary Vertical Spine Gradient */}
          <linearGradient id="rivet-graphite-stem" x1="6" y1="4" x2="12" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#F1F5F9" />
            <stop offset="40%" stopColor="#94A3B8" />
            <stop offset="100%" stopColor="#475569" />
          </linearGradient>

          {/* Graphite Bar 2: Interlocking Loop & Leg Gradient */}
          <linearGradient id="rivet-graphite-loop" x1="12" y1="4" x2="26" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#CBD5E1" />
            <stop offset="50%" stopColor="#64748B" />
            <stop offset="100%" stopColor="#334155" />
          </linearGradient>

          {/* Mint-Green Connection Point Glow */}
          <filter id="rivet-mint-glow" x="6" y="9" width="16" height="16" filterUnits="userSpaceOnUse">
            <feGaussianBlur stdDeviation="1.2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* 1. Primary Graphite Vertical Spine Bar */}
        <rect
          x="5.5"
          y="4"
          width="5.5"
          height="24"
          rx="2.75"
          fill="url(#rivet-graphite-stem)"
        />

        {/* 2. Interlocking Graphite Loop & Diagonal Leg Bar (Forming the R) */}
        <path
          d="M10 6.5H18.5C22.6421 6.5 26 9.85786 26 14C26 18.1421 22.6421 21.5 18.5 21.5H12M17 20.5L25.5 28"
          stroke="url(#rivet-graphite-loop)"
          strokeWidth="4.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* 3. Mint-Green Connection Point (Rivet Fastener Joint) */}
        <circle
          cx="11"
          cy="14"
          r="4.5"
          fill="#0B0F14"
        />
        <circle
          cx="11"
          cy="14"
          r="3"
          fill="#55E6A5"
          filter="url(#rivet-mint-glow)"
        />
        <circle
          cx="10.2"
          cy="13.2"
          r="1"
          fill="#FFFFFF"
          opacity="0.8"
        />
      </svg>
    </div>
  );
};
