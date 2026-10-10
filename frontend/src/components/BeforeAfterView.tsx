import React, { useState, useRef, useEffect } from 'react';
import { Photo, EditParameters, RetouchMaskKind } from '../types';
import { api } from '../api';
import {
  Columns, SplitSquareVertical, RotateCcw, Sparkles
} from 'lucide-react';

interface BeforeAfterViewProps {
  photo: Photo;
  previewTimestamp: number;
  onResetEdits: (photoId: number) => void;
  onAutoEditSingle: (photoId: number) => void;
  onUpdateEdits: (photoId: number, params: EditParameters) => void;
}

export const BeforeAfterView: React.FC<BeforeAfterViewProps> = ({
  photo,
  previewTimestamp,
  onResetEdits,
  onAutoEditSingle,
}) => {
  const [splitPos, setSplitPos] = useState<number>(50); // 0 to 100
  const [viewMode, setViewMode] = useState<'split' | 'side-by-side'>('split');
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [maskKind, setMaskKind] = useState<RetouchMaskKind>('off');

  // M cycles the retouch mask overlay: off -> skin -> heal -> shine
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'm' || e.key === 'M') {
        const order: RetouchMaskKind[] = ['off', 'skin', 'heal', 'shine'];
        setMaskKind(k => order[(order.indexOf(k) + 1) % order.length]);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const containerRef = useRef<HTMLDivElement>(null);
  const editedImgRef = useRef<HTMLImageElement>(null);

  const handlePointerDown = () => {
    setIsDragging(true);
  };
  const handlePointerUp = () => setIsDragging(false);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.min(Math.max((x / rect.width) * 100, 5), 95);
    setSplitPos(pct);
  };

  const origUrl = api.getOriginalUrl(photo.id);
  const editedUrl = api.getPreviewUrl(photo.id, previewTimestamp);
  const maskColors: Record<Exclude<RetouchMaskKind, 'off'>, string> = {
    skin: 'rgba(34, 197, 94, 0.55)',
    heal: 'rgba(250, 204, 21, 0.85)',
    shine: 'rgba(56, 189, 248, 0.7)',
  };
  const maskOverlay = maskKind === 'off' ? null : (
    <div
      style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 10,
        background: maskColors[maskKind],
        WebkitMaskImage: `url(${api.getRetouchMaskUrl(photo.id, maskKind, previewTimestamp)})`,
        WebkitMaskSize: 'contain',
        WebkitMaskRepeat: 'no-repeat',
        WebkitMaskPosition: 'center',
        WebkitMaskMode: 'luminance',
        maskImage: `url(${api.getRetouchMaskUrl(photo.id, maskKind, previewTimestamp)})`,
        maskSize: 'contain',
        maskRepeat: 'no-repeat',
        maskPosition: 'center',
        maskMode: 'luminance',
      } as React.CSSProperties}
    />
  );

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0b0e', userSelect: 'none' }}>
      {/* Top control bar */}
      <div style={{
        height: '46px',
        padding: '0 16px',
        background: '#13151a',
        borderBottom: '1px solid #232733',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '12px',
        color: '#94a3b8'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 600, color: '#f1f5f9' }}>{photo.filename}</span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>
            {photo.is_edited ? '✨ AI / Manual Corrections' : 'Original (No Edits)'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Mode toggle */}
          <div style={{ display: 'flex', background: '#1c1f26', padding: '2px', borderRadius: '6px', border: '1px solid #282d3b' }}>
            <button
              onClick={() => setViewMode('split')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 9px',
                borderRadius: '4px',
                background: viewMode === 'split' ? '#3b82f6' : 'transparent',
                color: viewMode === 'split' ? '#fff' : '#94a3b8',
                border: 'none',
                fontSize: '11px',
                cursor: 'pointer'
              }}
            >
              <SplitSquareVertical size={12} />
              <span>Split Slider</span>
            </button>
            <button
              onClick={() => setViewMode('side-by-side')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 9px',
                borderRadius: '4px',
                background: viewMode === 'side-by-side' ? '#3b82f6' : 'transparent',
                color: viewMode === 'side-by-side' ? '#fff' : '#94a3b8',
                border: 'none',
                fontSize: '11px',
                cursor: 'pointer'
              }}
            >
              <Columns size={12} />
              <span>Side-by-Side</span>
            </button>
          </div>

          {/* Retouch mask overlay */}
          <div style={{ display: 'flex', alignItems: 'center', background: '#1c1f26', padding: '2px', borderRadius: '6px', border: '1px solid #282d3b' }} title="Show where AI Skin Retouch applies (key: M)">
            <span style={{ fontSize: '10px', color: '#64748b', padding: '0 6px' }}>Mask</span>
            {(['off', 'skin', 'heal', 'shine'] as RetouchMaskKind[]).map(k => (
              <button
                key={k}
                onClick={() => setMaskKind(k)}
                style={{
                  padding: '4px 8px', borderRadius: '4px', border: 'none', fontSize: '11px', cursor: 'pointer',
                  background: maskKind === k ? '#3b82f6' : 'transparent',
                  color: maskKind === k ? '#fff' : '#94a3b8',
                  textTransform: 'capitalize'
                }}
              >
                {k}
              </button>
            ))}
          </div>

          {/* Quick Actions */}
          <button
            onClick={() => onAutoEditSingle(photo.id)}
            className="btn btn-secondary btn-sm"
            title="Recalculate AI corrections"
          >
            <Sparkles size={12} />
            <span>Re-Auto Edit</span>
          </button>

          <button
            onClick={() => onResetEdits(photo.id)}
            className="btn btn-secondary btn-sm"
            title="Reset to Original"
          >
            <RotateCcw size={12} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', overflow: 'auto', position: 'relative' }}>
        {viewMode === 'split' ? (
          /* ========================================================
             Mode 1: Split Slider Mode
             ======================================================== */
          <div
            ref={containerRef}
            onPointerDown={handlePointerDown}
            onPointerUp={handlePointerUp}
            onPointerMove={handlePointerMove}
            style={{
              position: 'relative',
              width: '90%',
              maxWidth: '1200px',
              height: '80vh',
              background: '#0e1014',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
              cursor: isDragging ? 'ew-resize' : 'default'
            }}
          >
            {/* Background: Edited Photo */}
            <img
              ref={editedImgRef}
              src={editedUrl}
              alt="Edited"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                position: 'absolute',
                top: 0,
                left: 0
              }}
            />
            {maskOverlay}

            {/* Foreground: Original Photo (Clipped by split position) */}
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: `${splitPos}%`,
              height: '100%',
              overflow: 'hidden',
              borderRight: '2px solid #38bdf8'
            }}>
              <img
                src={origUrl}
                alt="Original"
                style={{
                  width: containerRef.current ? containerRef.current.clientWidth : '100%',
                  height: '100%',
                  objectFit: 'contain',
                  position: 'absolute',
                  top: 0,
                  left: 0
                }}
              />
              <span style={{
                position: 'absolute',
                top: '12px',
                left: '12px',
                background: 'rgba(0,0,0,0.7)',
                color: '#fff',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 600
              }}>
                ORIGINAL
              </span>
            </div>

            {/* Right Tag */}
            <span style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              background: 'rgba(59, 130, 246, 0.8)',
              color: '#fff',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600
            }}>
              AI EDITED
            </span>

            {/* Slider Handle */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: `${splitPos}%`,
                transform: 'translate(-50%, -50%)',
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: '#38bdf8',
                color: '#000',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
                cursor: 'ew-resize',
                zIndex: 20
              }}
            >
              <SplitSquareVertical size={16} />
            </div>
          </div>
        ) : (
          /* ========================================================
             Mode 2: Side-by-Side Mode
             ======================================================== */
          <div style={{ display: 'flex', gap: '16px', width: '100%', height: '80vh', maxWidth: '1400px' }}>
            {/* Original Card */}
            <div style={{ flex: 1, background: '#12141a', borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column', border: '1px solid #232733' }}>
              <div style={{ padding: '8px 12px', background: '#181b22', borderBottom: '1px solid #232733', fontSize: '11px', fontWeight: 600, color: '#94a3b8' }}>
                ORIGINAL
              </div>
              <div style={{ flex: 1, position: 'relative' }}>
                <img src={origUrl} alt="Original" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              </div>
            </div>

            {/* Edited Card */}
            <div style={{ flex: 1, background: '#12141a', borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column', border: '1px solid #3b82f6' }}>
              <div style={{ padding: '8px 12px', background: 'rgba(59, 130, 246, 0.15)', borderBottom: '1px solid rgba(59, 130, 246, 0.3)', fontSize: '11px', fontWeight: 600, color: '#60a5fa' }}>
                AI EDITED ({photo.edit_params?.preset_name || 'Natural Wedding'})
              </div>
              <div style={{ flex: 1, position: 'relative' }}>
                <img src={editedUrl} alt="Edited" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                {maskOverlay}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
