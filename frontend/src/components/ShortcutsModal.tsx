import React from 'react';
import { Keyboard, X } from 'lucide-react';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const shortcuts = [
    { key: 'B', desc: 'Promote / Mark as Best photo' },
    { key: 'P', desc: 'Pick / Select current photo' },
    { key: 'R', desc: 'Flag current photo for Review' },
    { key: 'X', desc: 'Reject current photo' },
    { key: 'U', desc: 'Unflag / Reset selection to AI decision' },
    { key: '1 – 5', desc: 'Assign 1 to 5 star rating' },
    { key: '0', desc: 'Clear star rating' },
    { key: 'Space', desc: 'Toggle Before/After comparison' },
    { key: 'C', desc: 'Open Burst Compare for current group' },
    { key: 'E', desc: 'Run AI Auto-Edit on selected photo' },
    { key: '← / →', desc: 'Navigate previous / next photo' },
    { key: 'Esc', desc: 'Close dialog / return to grid' },
  ];

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '480px' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #232733', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Keyboard size={18} style={{ color: '#3b82f6' }} />
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc' }}>Photographer Keyboard Shortcuts</h2>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {shortcuts.map((sc, idx) => (
            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', borderBottom: '1px solid #1c202a', paddingBottom: '8px' }}>
              <span style={{ color: '#e2e8f0' }}>{sc.desc}</span>
              <kbd style={{
                background: '#1e2330',
                border: '1px solid #333d52',
                color: '#38bdf8',
                padding: '3px 8px',
                borderRadius: '4px',
                fontWeight: 700,
                fontSize: '11px',
                boxShadow: '0 2px 0 rgba(0,0,0,0.4)'
              }}>
                {sc.key}
              </kbd>
            </div>
          ))}
        </div>

        <div style={{ padding: '12px 20px', borderTop: '1px solid #232733', display: 'flex', justifyContent: 'flex-end', background: '#13151a' }}>
          <button onClick={onClose} className="btn btn-secondary btn-sm">
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};
