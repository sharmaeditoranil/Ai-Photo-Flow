import React, { useState, useEffect } from 'react';
import { BatchJob } from '../types';
import {
  Sparkles, Wand2, Download, RefreshCw, Pause, Play, X,
  CheckCircle2, AlertCircle, FileText, ChevronRight, Minimize2, Eye
} from 'lucide-react';

interface BatchProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeJob: BatchJob | null;
  onPauseJob?: () => void;
  onResumeJob?: () => void;
  onCancelJob?: () => void;
  onOpenLogs?: () => void;
  onDone?: () => void;
}

export const BatchProgressModal: React.FC<BatchProgressModalProps> = ({
  isOpen,
  onClose,
  activeJob,
  onPauseJob,
  onResumeJob,
  onCancelJob,
  onOpenLogs,
  onDone
}) => {
  const [startTime, setStartTime] = useState<number>(Date.now());

  useEffect(() => {
    if (isOpen && activeJob?.status === 'RUNNING') {
      setStartTime(Date.now());
    }
  }, [isOpen, activeJob?.id]);

  if (!isOpen || !activeJob) return null;

  const isCull = activeJob.job_type === 'CULLING';
  const isEdit = activeJob.job_type === 'AUTO_EDIT';
  const isExport = activeJob.job_type === 'EXPORT';
  const isProofing = activeJob.job_type === 'PROOFING_PREVIEW';

  const title = isCull
    ? 'AI Wedding Photo Culling & Analysis'
    : isEdit
    ? 'AI Auto-Editing (Skin Tone, Vibrance & Lighting)'
    : isProofing
    ? 'Generating Protected Client Previews'
    : 'Batch Photo Export';

  const description = isCull
    ? 'Scanning blur, sharpness, face detection, open eyes, and grouping burst sequences...'
    : isEdit
    ? 'Applying Indian skin tone enhancement, 5% vibrance boost, and dynamic range exposure...'
    : isProofing
    ? 'Creating 1200px lightweight WebP previews with anti-theft security watermarks...'
    : 'Exporting final high-resolution photos to your destination folder...';

  const current = activeJob.progress_current || 0;
  const total = activeJob.progress_total || 1;
  const pct = Math.min(100, Math.max(0, activeJob.progress_pct || 0));

  const isRunning = activeJob.status === 'RUNNING';
  const isPaused = activeJob.status === 'PAUSED';
  const isCompleted = activeJob.status === 'COMPLETED';
  const isFailed = activeJob.status === 'FAILED' || activeJob.status === 'CANCELLED';

  // Estimate remaining time
  const remainingItems = Math.max(0, total - current);
  const estSecondsLeft = Math.ceil(remainingItems * (isCull ? 0.08 : isEdit ? 0.12 : 0.06));

  const handleFinish = () => {
    if (onDone) onDone();
    onClose();
  };

  return (
    <div className="modal-overlay" style={{ zIndex: 120 }}>
      <div
        className="modal-content"
        style={{
          maxWidth: '560px',
          width: '95%',
          background: '#13151b',
          border: '1px solid #232733',
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.7)',
          borderRadius: '14px',
          overflow: 'hidden'
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 22px',
            borderBottom: '1px solid #232733',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'linear-gradient(180deg, #181c26 0%, #13151b 100%)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '10px',
                background: isCompleted
                  ? 'rgba(16, 185, 129, 0.15)'
                  : isEdit
                  ? 'rgba(16, 185, 129, 0.15)'
                  : 'rgba(59, 130, 246, 0.15)',
                border: isCompleted
                  ? '1px solid rgba(16, 185, 129, 0.4)'
                  : isEdit
                  ? '1px solid rgba(16, 185, 129, 0.4)'
                  : '1px solid rgba(59, 130, 246, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              {isCompleted ? (
                <CheckCircle2 size={20} style={{ color: '#10b981' }} />
              ) : isCull ? (
                <Sparkles size={20} style={{ color: '#60a5fa' }} />
              ) : isEdit ? (
                <Wand2 size={20} style={{ color: '#34d399' }} />
              ) : (
                <Download size={20} style={{ color: '#60a5fa' }} />
              )}
            </div>
            <div>
              <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                {isCompleted ? 'Processing Completed!' : title}
              </h2>
              <p style={{ fontSize: '11px', color: '#94a3b8', margin: '3px 0 0 0' }}>
                {isCompleted ? `All ${total} photos processed successfully` : description}
              </p>
            </div>
          </div>

          {/* Close / Minimize button */}
          <button
            onClick={onClose}
            className="btn btn-secondary btn-sm"
            style={{ padding: '6px', borderRadius: '6px' }}
            title="Minimize to Background"
          >
            <Minimize2 size={14} />
          </button>
        </div>

        {/* Body Content */}
        <div style={{ padding: '24px 22px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Main Percentage Display & Counter */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
            <div>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px', fontWeight: 600 }}>
                Photos Processed
              </div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: '#f8fafc', fontVariantNumeric: 'tabular-nums', marginTop: '2px' }}>
                {current} <span style={{ fontSize: '16px', color: '#64748b', fontWeight: 500 }}>/ {total}</span>
              </div>
            </div>

            <div style={{ textAlign: 'right' }}>
              <div style={{
                fontSize: '24px',
                fontWeight: 800,
                color: isCompleted ? '#34d399' : isPaused ? '#fbbf24' : '#60a5fa',
                fontVariantNumeric: 'tabular-nums'
              }}>
                {pct.toFixed(1)}%
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                {isCompleted ? 'Complete' : isPaused ? 'Paused' : `~${estSecondsLeft}s remaining`}
              </div>
            </div>
          </div>

          {/* Animated Large Progress Bar */}
          <div style={{
            width: '100%',
            height: '14px',
            background: '#1b1f2b',
            borderRadius: '7px',
            overflow: 'hidden',
            border: '1px solid #282f40',
            position: 'relative'
          }}>
            <div
              style={{
                height: '100%',
                width: `${pct}%`,
                background: isCompleted
                  ? 'linear-gradient(90deg, #10b981, #34d399)'
                  : isPaused
                  ? '#f59e0b'
                  : isEdit
                  ? 'linear-gradient(90deg, #10b981, #06b6d4)'
                  : 'linear-gradient(90deg, #2563eb, #38bdf8)',
                borderRadius: '6px',
                transition: 'width 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                boxShadow: isCompleted
                  ? '0 0 12px rgba(16, 185, 129, 0.5)'
                  : '0 0 12px rgba(59, 130, 246, 0.5)'
              }}
            />
          </div>

          {/* Current Processing File Status */}
          <div style={{
            background: '#161922',
            border: '1px solid #242938',
            borderRadius: '8px',
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
              <RefreshCw
                size={13}
                style={{
                  color: isRunning ? '#38bdf8' : '#94a3b8',
                  animation: isRunning ? 'spin 1.2s linear infinite' : 'none',
                  flexShrink: 0
                }}
              />
              <span style={{ color: '#94a3b8', flexShrink: 0 }}>Processing:</span>
              <span style={{
                color: '#f8fafc',
                fontWeight: 600,
                fontFamily: 'monospace',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {activeJob.current_file || (isCompleted ? 'All tasks finished' : 'Preparing photos...')}
              </span>
            </div>

            <span style={{
              fontSize: '10px',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '12px',
              background: isCompleted
                ? 'rgba(16, 185, 129, 0.15)'
                : isPaused
                ? 'rgba(245, 158, 11, 0.15)'
                : 'rgba(59, 130, 246, 0.15)',
              color: isCompleted ? '#34d399' : isPaused ? '#fbbf24' : '#60a5fa'
            }}>
              {activeJob.status}
            </span>
          </div>

          {/* Processing Stages Feature List */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '8px',
            fontSize: '11px',
            color: '#94a3b8'
          }}>
            {isCull ? (
              <>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: pct > 20 ? '#34d399' : '#60a5fa', fontWeight: 600 }}>1. Sharpness</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Blur Detection</div>
                </div>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: pct > 50 ? '#34d399' : pct > 20 ? '#60a5fa' : '#64748b', fontWeight: 600 }}>2. Faces & Eyes</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Expression Scan</div>
                </div>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: isCompleted ? '#34d399' : pct > 50 ? '#60a5fa' : '#64748b', fontWeight: 600 }}>3. Burst Sets</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Best Winner Pick</div>
                </div>
              </>
            ) : isEdit ? (
              <>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: pct > 25 ? '#34d399' : '#34d399', fontWeight: 600 }}>1. Indian Skin</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Warmth & Glow</div>
                </div>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: pct > 60 ? '#34d399' : pct > 25 ? '#34d399' : '#64748b', fontWeight: 600 }}>2. +5% Vibrance</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Rich Lehengas</div>
                </div>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: isCompleted ? '#34d399' : pct > 60 ? '#34d399' : '#64748b', fontWeight: 600 }}>3. Tone Pipeline</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Highlights & Shadows</div>
                </div>
              </>
            ) : (
              <>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: '#34d399', fontWeight: 600 }}>1. Resize</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>1200px Mobile Web</div>
                </div>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: '#34d399', fontWeight: 600 }}>2. Anti-Theft</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Watermark Stamp</div>
                </div>
                <div style={{ background: '#161922', padding: '8px', borderRadius: '6px', textAlign: 'center', border: '1px solid #232733' }}>
                  <div style={{ color: '#34d399', fontWeight: 600 }}>3. WebP</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>Fast Cache</div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div style={{
          padding: '14px 22px',
          background: '#0e1014',
          borderTop: '1px solid #232733',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          {/* Left Controls: Logs / Background */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {onOpenLogs && (
              <button
                type="button"
                onClick={onOpenLogs}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '11px', gap: '4px' }}
                title="View full real-time terminal logs"
              >
                <FileText size={12} />
                <span>Logs</span>
              </button>
            )}

            {!isCompleted && (
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '11px' }}
                title="Continue in background"
              >
                Run in Background
              </button>
            )}
          </div>

          {/* Right Controls: Pause/Cancel or Complete Button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {!isCompleted ? (
              <>
                {isRunning && onPauseJob && (
                  <button
                    type="button"
                    onClick={onPauseJob}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '11px', gap: '4px' }}
                  >
                    <Pause size={12} />
                    <span>Pause</span>
                  </button>
                )}

                {isPaused && onResumeJob && (
                  <button
                    type="button"
                    onClick={onResumeJob}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '11px', gap: '4px', borderColor: '#2563eb', color: '#60a5fa' }}
                  >
                    <Play size={12} />
                    <span>Resume</span>
                  </button>
                )}

                {onCancelJob && (
                  <button
                    type="button"
                    onClick={onCancelJob}
                    className="btn btn-danger btn-sm"
                    style={{ fontSize: '11px' }}
                  >
                    Cancel
                  </button>
                )}
              </>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                className="btn btn-success"
                style={{ padding: '8px 22px', fontSize: '12px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <CheckCircle2 size={14} />
                <span>View Results</span>
              </button>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
