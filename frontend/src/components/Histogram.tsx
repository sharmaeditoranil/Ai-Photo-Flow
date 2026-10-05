import React from 'react';
import { Photo } from '../types';

interface HistogramProps {
  photo?: Photo | null;
}

export const Histogram: React.FC<HistogramProps> = ({ photo }) => {
  // Synthesize or calculate realistic RGB curves based on exposure and color metrics
  const meanLum = photo ? (photo.exposure_score > 0 ? (photo.exposure_status === 'UNDER_EXPOSED' ? 50 : photo.exposure_status === 'OVER_EXPOSED' ? 200 : 128) : 120) : 120;
  const tempOffset = photo?.edit_params?.temperature || 0;
  const expOffset = (photo?.edit_params?.exposure || 0) * 20;

  // Generate SVG paths for R, G, B channels
  const generateCurve = (offset: number, peakShift: number) => {
    const points: [number, number][] = [];
    const width = 280;
    const height = 70;
    const center = Math.min(Math.max(meanLum + peakShift + expOffset, 20), 260);

    for (let x = 0; x <= width; x += 10) {
      const dist = Math.abs(x - (center / 280) * width);
      const sigma = 35;
      const y = height - (Math.exp(-(dist * dist) / (2 * sigma * sigma)) * (height - 10) + Math.random() * 3);
      points.push([x, Math.max(8, y)]);
    }

    const pathData = points.reduce((acc, [x, y], idx) => `${acc} ${idx === 0 ? 'M' : 'L'} ${x} ${y}`, '');
    return `${pathData} L ${width} ${height} L 0 ${height} Z`;
  };

  const redPath = generateCurve(0, tempOffset * 0.5);
  const greenPath = generateCurve(0, 0);
  const bluePath = generateCurve(0, -tempOffset * 0.5);

  return (
    <div style={{ background: '#12141a', padding: '10px 12px', borderRadius: '6px', border: '1px solid #232733' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#9ba3b4', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          RGB Histogram
        </span>
        <span style={{ fontSize: '10px', color: '#64748b' }}>sRGB Standard</span>
      </div>

      <div style={{ width: '100%', height: '70px', position: 'relative', overflow: 'hidden', borderRadius: '4px', background: '#0a0b0e' }}>
        <svg width="100%" height="70" viewBox="0 0 280 70" preserveAspectRatio="none" style={{ mixBlendMode: 'screen' }}>
          {/* Red channel */}
          <path d={redPath} fill="rgba(239, 68, 68, 0.35)" />
          {/* Green channel */}
          <path d={greenPath} fill="rgba(34, 197, 94, 0.3)" />
          {/* Blue channel */}
          <path d={bluePath} fill="rgba(59, 130, 246, 0.35)" />
        </svg>

        {/* Shadow / Highlight clipping indicators */}
        <div style={{ position: 'absolute', bottom: '2px', left: '4px', fontSize: '9px', color: '#475569' }}>0</div>
        <div style={{ position: 'absolute', bottom: '2px', right: '4px', fontSize: '9px', color: '#475569' }}>255</div>
      </div>
    </div>
  );
};
