import React from 'react';
import { BatchJob } from '../types';
import { FileText, X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react';

interface BatchLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeJob: BatchJob | null;
}

export const BatchLogsModal: React.FC<BatchLogsModalProps> = ({
  isOpen,
  onClose,
  activeJob,
}) => {
  if (!isOpen) return null;

  const logs = activeJob?.logs || [];

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '700px', height: '600px' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid #232733', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={16} style={{ color: '#3b82f6' }} />
            <h2 style={{ fontSize: '14px', fontWeight: 700, color: '#f8fafc' }}>
              Batch Processing Diagnostics & Logs
            </h2>
            {activeJob && (
              <span style={{ fontSize: '11px', background: '#1e293b', color: '#94a3b8', padding: '2px 6px', borderRadius: '4px' }}>
                {activeJob.status} ({activeJob.progress_pct}%)
              </span>
            )}
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        {/* Logs Terminal Area */}
        <div style={{
          flex: 1,
          padding: '14px',
          background: '#0a0b0e',
          fontFamily: 'monospace',
          fontSize: '11px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}>
          {logs.length === 0 ? (
            <div style={{ color: '#64748b', textAlign: 'center', marginTop: '40px' }}>
              No processing logs available. Start AI Culling, Auto-Edit, or Export to view execution details.
            </div>
          ) : (
            logs.map((log, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', lineHeight: 1.5 }}>
                <span style={{ color: '#64748b', minWidth: '60px' }}>[{log.timestamp}]</span>
                <span style={{
                  color: log.level === 'SUCCESS' ? '#34d399' :
                         log.level === 'WARNING' ? '#fbbf24' :
                         log.level === 'ERROR' ? '#f87171' : '#93c5fd',
                  fontWeight: 600,
                  minWidth: '65px'
                }}>
                  {log.level}:
                </span>
                <span style={{ color: '#e2e8f0', wordBreak: 'break-all' }}>
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>

        <div style={{ padding: '12px 18px', borderTop: '1px solid #232733', display: 'flex', justifyContent: 'flex-end', background: '#13151a' }}>
          <button onClick={onClose} className="btn btn-secondary btn-sm">
            Close Logs
          </button>
        </div>
      </div>
    </div>
  );
};
