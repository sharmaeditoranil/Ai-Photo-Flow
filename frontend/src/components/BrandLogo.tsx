import React from 'react';
import appLogo from '../assets/app-logo.png';

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
        borderRadius: `${Math.round(size * 0.22)}px`,
        overflow: 'hidden',
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.5)',
        flexShrink: 0,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0d1017'
      }}
    >
      <img
        src={appLogo}
        alt="Ai PhotoFlow"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          display: 'block'
        }}
      />
    </div>
  );
};
