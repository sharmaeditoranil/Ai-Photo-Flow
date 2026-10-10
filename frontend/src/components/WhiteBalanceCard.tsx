import React, { useEffect, useState } from 'react';
import { Eye, EyeOff, Thermometer } from 'lucide-react';
import type { AutoWhiteBalance } from '../types';

interface WhiteBalanceCardProps {
  wb: AutoWhiteBalance | null | undefined;
  onCommit: (wb: AutoWhiteBalance) => void;
}

const SKIN_MIN = 44;
const SKIN_MAX = 63;

const lightName = (k: number | null) => {
  if (!k) return '';
  if (k < 3600) return 'tungsten / candle';
  if (k < 4600) return 'warm indoor';
  if (k < 5600) return 'mixed / sunset';
  if (k < 7000) return 'daylight / flash';
  return 'shade / cool LED';
};

export const WhiteBalanceCard: React.FC<WhiteBalanceCardProps> = ({ wb, onCommit }) => {
  const [strength, setStrength] = useState<number>(wb?.strength ?? 100);
  useEffect(() => setStrength(wb?.strength ?? 100), [wb?.strength]);

  if (!wb) {
    return (
      <div style={{ padding: '10px 14px', borderBottom: '1px solid #1c202a', fontSize: '10.5px', color: '#64748b' }}>
        <Thermometer size={12} style={{ verticalAlign: 'middle', marginRight: 5 }} />
        AI White Balance: Auto Edit chalane par is photo ka color cast detect hoga.
      </div>
    );
  }

  const enabled = wb.enabled !== false;
  const inRange = (h?: number | null) => h != null && h >= SKIN_MIN && h <= SKIN_MAX;
  const commitStrength = (v: number) => onCommit({ ...wb, strength: v });

  return (
    <div style={{ padding: '12px 14px', borderBottom: '1px solid #1c202a', background: '#12141a' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Thermometer size={14} style={{ color: '#f59e0b' }} />
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            AI White Balance
          </span>
        </div>
        <button
          type="button"
          onClick={() => onCommit({ ...wb, enabled: !enabled })}
          title={enabled ? 'Turn auto white balance off for this photo' : 'Turn auto white balance on'}
          style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'transparent', border: '1px solid #232836', borderRadius: '4px', color: enabled ? '#f59e0b' : '#64748b', fontSize: '10px', padding: '2px 6px', cursor: 'pointer' }}
        >
          {enabled ? <Eye size={11} /> : <EyeOff size={11} />}
          <span>{enabled ? 'On' : 'Off'}</span>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '10.5px', marginBottom: '8px' }}>
        <div style={{ background: '#161920', padding: '5px 7px', borderRadius: '4px', border: '1px solid #20242e' }}>
          <div style={{ color: '#64748b', fontSize: '9.5px' }}>Detected</div>
          <div style={{ color: '#e2e8f0', fontWeight: 600, textTransform: 'capitalize' }}>{wb.cast}</div>
        </div>
        <div style={{ background: '#161920', padding: '5px 7px', borderRadius: '4px', border: '1px solid #20242e' }}>
          <div style={{ color: '#64748b', fontSize: '9.5px' }}>Light</div>
          <div style={{ color: '#e2e8f0', fontWeight: 600 }}>
            {wb.kelvin ? `~${wb.kelvin}K` : '—'} <span style={{ color: '#94a3b8', fontWeight: 400 }}>{lightName(wb.kelvin)}</span>
          </div>
        </div>
        <div style={{ background: '#161920', padding: '5px 7px', borderRadius: '4px', border: '1px solid #20242e' }}>
          <div style={{ color: '#64748b', fontSize: '9.5px' }}>AI confidence</div>
          <div style={{ color: wb.confidence >= 0.6 ? '#34d399' : wb.confidence >= 0.35 ? '#fbbf24' : '#f87171', fontWeight: 600 }}>
            {Math.round(wb.confidence * 100)}%
          </div>
        </div>
        <div style={{ background: '#161920', padding: '5px 7px', borderRadius: '4px', border: '1px solid #20242e' }} title="Skin hue in CIELAB; natural skin is about 44°–63°">
          <div style={{ color: '#64748b', fontSize: '9.5px' }}>Skin tone check</div>
          <div style={{ fontWeight: 600 }}>
            {wb.skin_hue_before == null ? <span style={{ color: '#94a3b8' }}>No face</span> : (
              <>
                <span style={{ color: inRange(wb.skin_hue_before) ? '#94a3b8' : '#f87171' }}>{wb.skin_hue_before}°</span>
                <span style={{ color: '#64748b' }}> → </span>
                <span style={{ color: inRange(wb.skin_hue_after) ? '#34d399' : '#fbbf24' }}>{wb.skin_hue_after}°</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="slider-group" style={{ marginBottom: 0, opacity: enabled ? 1 : 0.45 }}>
        <div className="slider-header">
          <span onDoubleClick={() => commitStrength(100)} title="Double-click to reset" style={{ cursor: 'default' }}>Correction Strength</span>
          <span className="slider-val">{Math.round(strength)}%</span>
        </div>
        <input
          type="range" min={0} max={150} step={1} value={strength} disabled={!enabled}
          onChange={(e) => setStrength(parseFloat(e.target.value))}
          onPointerUp={(e) => commitStrength(parseFloat((e.target as HTMLInputElement).value))}
          onKeyUp={(e) => commitStrength(parseFloat((e.target as HTMLInputElement).value))}
          style={{ accentColor: '#f59e0b' }}
        />
      </div>
      {wb.notes && wb.notes.length > 0 && (
        <div style={{ fontSize: '9.5px', color: '#64748b', marginTop: '4px' }}>{wb.notes.join(' · ')}</div>
      )}
    </div>
  );
};
