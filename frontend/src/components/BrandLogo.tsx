import React from 'react';

interface BrandLogoProps {
  size?: number;
  className?: string;
}

export const BrandLogo: React.FC<BrandLogoProps> = ({ size = 28, className = '' }) => {
  return (
    <div
      className={className}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: `${Math.round(size * 0.25)}px`,
        overflow: 'hidden',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.45)',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        flexShrink: 0,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0e1117'
      }}
    >
      <svg
        viewBox="0 0 512 512"
        width="100%"
        height="100%"
        style={{ display: 'block' }}
      >
        <defs>
          <linearGradient id="blSquircleBg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#1e2430" />
            <stop offset="50%" stopColor="#11141a" />
            <stop offset="100%" stopColor="#080a0d" />
          </linearGradient>

          <linearGradient id="blRimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="50%" stopColor="#1e293b" />
            <stop offset="100%" stopColor="#f59e0b" />
          </linearGradient>

          <linearGradient id="blGlassReflect" x1="20%" y1="0%" x2="80%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
            <stop offset="35%" stopColor="#38bdf8" stopOpacity="0.15" />
            <stop offset="70%" stopColor="#000000" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.2" />
          </linearGradient>

          <linearGradient id="blAiCyan" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#67e8f9" />
            <stop offset="100%" stopColor="#0284c7" />
          </linearGradient>

          <linearGradient id="blWarmAmber" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#fde047" />
            <stop offset="50%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#d97706" />
          </linearGradient>

          <filter id="blCoreGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Squircle base */}
        <rect x="0" y="0" width="512" height="512" fill="url(#blSquircleBg)" />

        {/* Outer Ring */}
        <circle cx="256" cy="256" r="200" fill="none" stroke="url(#blRimGrad)" strokeWidth="6" strokeOpacity="0.85" />
        <circle cx="256" cy="256" r="190" fill="#0d1117" stroke="rgba(255,255,255,0.08)" strokeWidth="2" />

        {/* Lens Element */}
        <circle cx="256" cy="256" r="176" fill="url(#blGlassReflect)" />

        {/* Aperture Blades */}
        <g stroke="rgba(255,255,255,0.15)" strokeWidth="1.5">
          <path d="M 256 95 A 161 161 0 0 1 395 190 L 325 230 A 90 90 0 0 0 256 165 Z" fill="url(#blAiCyan)" opacity="0.9" />
          <path d="M 395 190 A 161 161 0 0 1 410 325 L 335 295 A 90 90 0 0 0 325 230 Z" fill="#38bdf8" opacity="0.8" />
          <path d="M 410 325 A 161 161 0 0 1 315 415 L 285 335 A 90 90 0 0 0 335 295 Z" fill="url(#blWarmAmber)" opacity="0.95" />
          <path d="M 315 415 A 161 161 0 0 1 180 405 L 210 330 A 90 90 0 0 0 285 335 Z" fill="#f59e0b" opacity="0.85" />
          <path d="M 180 405 A 161 161 0 0 1 105 300 L 180 265 A 90 90 0 0 0 210 330 Z" fill="#0ea5e9" opacity="0.75" />
          <path d="M 105 300 A 161 161 0 0 1 140 165 L 215 215 A 90 90 0 0 0 180 265 Z" fill="#38bdf8" opacity="0.85" />
        </g>

        {/* Center Iris */}
        <circle cx="256" cy="256" r="70" fill="#070a10" stroke="rgba(255,255,255,0.25)" strokeWidth="2.5" />

        {/* AI Sparkle */}
        <g filter="url(#blCoreGlow)">
          <path d="M 256 208 Q 256 256 208 256 Q 256 256 256 304 Q 256 256 304 256 Q 256 256 256 208 Z" fill="#ffffff" />
          <path d="M 310 198 Q 310 216 292 216 Q 310 216 310 234 Q 310 216 328 216 Q 310 216 310 198 Z" fill="#67e8f9" />
          <path d="M 202 298 Q 202 313 187 313 Q 202 313 202 328 Q 202 313 217 313 Q 202 313 202 298 Z" fill="#fde047" />
        </g>

        {/* Glass Glare Highlight */}
        <path d="M 135 180 A 155 155 0 0 1 335 130" fill="none" stroke="#ffffff" strokeWidth="6" strokeLinecap="round" opacity="0.5" />
      </svg>
    </div>
  );
};
