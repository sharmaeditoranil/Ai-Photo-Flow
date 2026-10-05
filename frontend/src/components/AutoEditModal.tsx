import React, { useState, useRef } from 'react';
import {
  X, Wand2, Check, Sparkles, Sliders, Sun, Flame, Heart, Camera,
  Film, Palette, Zap, Eye, SplitSquareVertical, ArrowUpDown,
  Maximize2, MoveVertical, ChevronLeft, ChevronRight
} from 'lucide-react';
import { api } from '../api';
import { WEDDING_PRESETS } from '../presets';
import type { PresetInfo } from '../presets';
export { WEDDING_PRESETS };
export type { PresetInfo };

interface AutoEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedCount: number;
  totalCount: number;
  samplePhotoId?: number;
  onStartAutoEdit: (presetName: string, scope: 'selected' | 'all') => void;
}

export const AutoEditModal: React.FC<AutoEditModalProps> = ({
  isOpen,
  onClose,
  selectedCount,
  totalCount,
  samplePhotoId,
  onStartAutoEdit
}) => {
  const [selectedPreset, setSelectedPreset] = useState<string>('Pure Light (No Color Tone)');
  const [scope, setScope] = useState<'selected' | 'all'>(selectedCount > 0 ? 'selected' : 'all');
  const [previewMode, setPreviewMode] = useState<'split' | 'after' | 'before'>('split');
  const [fitMode, setFitMode] = useState<'contain' | 'scroll'>('contain');

  const beforeScrollRef = useRef<HTMLDivElement>(null);
  const afterScrollRef = useRef<HTMLDivElement>(null);
  const presetsScrollRef = useRef<HTMLDivElement>(null);
  const isSyncingRef = useRef<boolean>(false);

  const handleSyncScroll = (source: 'before' | 'after') => {
    if (isSyncingRef.current) return;
    isSyncingRef.current = true;
    if (source === 'before' && beforeScrollRef.current && afterScrollRef.current) {
      afterScrollRef.current.scrollTop = beforeScrollRef.current.scrollTop;
    } else if (source === 'after' && afterScrollRef.current && beforeScrollRef.current) {
      beforeScrollRef.current.scrollTop = afterScrollRef.current.scrollTop;
    }
    requestAnimationFrame(() => {
      isSyncingRef.current = false;
    });
  };

  const scrollToPosition = (pos: 'top' | 'center' | 'bottom') => {
    const scrollTarget = (ref: React.RefObject<HTMLDivElement | null>) => {
      if (!ref.current) return;
      const maxScroll = ref.current.scrollHeight - ref.current.clientHeight;
      if (pos === 'top') ref.current.scrollTop = 0;
      else if (pos === 'center') ref.current.scrollTop = maxScroll / 2;
      else if (pos === 'bottom') ref.current.scrollTop = maxScroll;
    };
    scrollTarget(beforeScrollRef);
    scrollTarget(afterScrollRef);
  };

  const scrollPresets = (dir: 'left' | 'right') => {
    if (presetsScrollRef.current) {
      presetsScrollRef.current.scrollBy({ left: dir === 'left' ? -300 : 300, behavior: 'smooth' });
    }
  };

  if (!isOpen) return null;

  const currentPresetInfo = WEDDING_PRESETS.find(p => p.id === selectedPreset) || WEDDING_PRESETS[0];

  const handleStart = () => {
    onStartAutoEdit(selectedPreset, scope);
    onClose();
  };

  const countToEdit = scope === 'selected' && selectedCount > 0 ? selectedCount : totalCount;
  const sampleImgUrl = samplePhotoId ? api.getThumbnailUrl(samplePhotoId) : null;

  return (
    <div className="modal-overlay">
      <div
        className="modal-content"
        style={{
          maxWidth: '1120px',
          width: '96%',
          height: '92vh',
          maxHeight: '94vh',
          display: 'flex',
          flexDirection: 'column',
          background: '#0d1017',
          border: '1px solid #1f2434',
          borderRadius: '12px',
          overflow: 'hidden',
          boxShadow: '0 20px 50px rgba(0,0,0,0.8)'
        }}
      >
        {/* 1. Header */}
        <div style={{
          padding: '12px 20px',
          borderBottom: '1px solid #1c202e',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#11141e'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '30px',
              height: '30px',
              borderRadius: '7px',
              background: 'linear-gradient(135deg, #10b981, #059669)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              boxShadow: '0 2px 8px rgba(16, 185, 129, 0.35)'
            }}>
              <Wand2 size={15} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#f8fafc' }}>
                AI Batch Auto-Edit – 10 Color Tone Presets &amp; Visual Preview
              </h2>
              <p style={{ margin: '1px 0 0', fontSize: '11px', color: '#94a3b8' }}>
                Niche presets me se tone select karein aur upar live photo preview dekhein.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* 2. Photo Preview Area (FLEX: 1 -> Takes MAXIMUM Screen Space) */}
        <div style={{
          flex: 1,
          minHeight: '320px',
          background: '#06070a',
          borderBottom: '1px solid #1a1e2a',
          display: 'flex',
          flexDirection: 'column',
          padding: '10px 18px',
          gap: '8px',
          overflow: 'hidden'
        }}>
          {/* Controls Bar above preview */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Eye size={13} style={{ color: '#38bdf8' }} />
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Live Color Tone Preview
                </span>
              </div>
              <span style={{
                fontSize: '10.5px',
                background: currentPresetInfo.badgeBg,
                color: currentPresetInfo.badge,
                padding: '2px 8px',
                borderRadius: '4px',
                fontWeight: 700,
                border: `1px solid ${currentPresetInfo.badge}44`
              }}>
                {currentPresetInfo.name}
              </span>
            </div>

            {/* View & Fit Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* Fit Mode Switcher */}
              <div style={{ display: 'flex', gap: '2px', background: '#131620', padding: '2px', borderRadius: '5px', border: '1px solid #252b3a' }}>
                <button
                  type="button"
                  onClick={() => setFitMode('contain')}
                  title="Poori photo bina kate frame me dikhegi"
                  style={{
                    padding: '3px 8px',
                    fontSize: '10px',
                    fontWeight: 600,
                    borderRadius: '3px',
                    border: 'none',
                    cursor: 'pointer',
                    background: fitMode === 'contain' ? '#10b981' : 'transparent',
                    color: fitMode === 'contain' ? '#fff' : '#94a3b8',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Maximize2 size={11} />
                  Fit Full Photo
                </button>
                <button
                  type="button"
                  onClick={() => setFitMode('scroll')}
                  title="Photo ko upar-neeche scroll karke poora detail dekhein"
                  style={{
                    padding: '3px 8px',
                    fontSize: '10px',
                    fontWeight: 600,
                    borderRadius: '3px',
                    border: 'none',
                    cursor: 'pointer',
                    background: fitMode === 'scroll' ? '#10b981' : 'transparent',
                    color: fitMode === 'scroll' ? '#fff' : '#94a3b8',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <MoveVertical size={11} />
                  ↕ Scroll Up/Down
                </button>
              </div>

              {/* View Switcher: Split / Before / After */}
              <div style={{ display: 'flex', gap: '2px', background: '#131620', padding: '2px', borderRadius: '5px', border: '1px solid #252b3a' }}>
                <button
                  type="button"
                  onClick={() => setPreviewMode('split')}
                  style={{
                    padding: '3px 8px',
                    fontSize: '10px',
                    fontWeight: 600,
                    borderRadius: '3px',
                    border: 'none',
                    cursor: 'pointer',
                    background: previewMode === 'split' ? '#2563eb' : 'transparent',
                    color: previewMode === 'split' ? '#fff' : '#94a3b8'
                  }}
                >
                  Side-by-Side Split
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewMode('before')}
                  style={{
                    padding: '3px 8px',
                    fontSize: '10px',
                    fontWeight: 600,
                    borderRadius: '3px',
                    border: 'none',
                    cursor: 'pointer',
                    background: previewMode === 'before' ? '#2563eb' : 'transparent',
                    color: previewMode === 'before' ? '#fff' : '#94a3b8'
                  }}
                >
                  Before
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewMode('after')}
                  style={{
                    padding: '3px 8px',
                    fontSize: '10px',
                    fontWeight: 600,
                    borderRadius: '3px',
                    border: 'none',
                    cursor: 'pointer',
                    background: previewMode === 'after' ? '#2563eb' : 'transparent',
                    color: previewMode === 'after' ? '#fff' : '#94a3b8'
                  }}
                >
                  After
                </button>
              </div>
            </div>
          </div>

          {/* Visual Canvas Box (flex: 1 -> Fills available vertical space) */}
          <div style={{
            flex: 1,
            minHeight: '260px',
            borderRadius: '8px',
            overflow: 'hidden',
            background: '#040507',
            border: '1px solid #1e2330',
            display: 'flex',
            position: 'relative'
          }}>
            {previewMode === 'split' ? (
              <>
                {/* Left: Before */}
                <div
                  ref={beforeScrollRef}
                  onScroll={() => handleSyncScroll('before')}
                  style={{
                    flex: 1,
                    height: '100%',
                    position: 'relative',
                    overflowY: fitMode === 'scroll' ? 'auto' : 'hidden',
                    overflowX: 'hidden',
                    borderRight: '2px solid #38bdf8',
                    display: 'flex',
                    alignItems: fitMode === 'contain' ? 'center' : 'flex-start',
                    justifyContent: 'center',
                    background: '#07080c'
                  }}
                >
                  {sampleImgUrl ? (
                    <img
                      src={sampleImgUrl}
                      alt="Before"
                      style={{
                        width: '100%',
                        height: fitMode === 'contain' ? '100%' : 'auto',
                        objectFit: fitMode === 'contain' ? 'contain' : undefined,
                        display: 'block'
                      }}
                    />
                  ) : (
                    <div style={{ width: '100%', height: '100%', background: 'linear-gradient(135deg, #1e293b, #0f172a)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>Original Photo (Before)</span>
                    </div>
                  )}
                  <span style={{ position: 'sticky', top: '8px', left: '8px', zIndex: 10, alignSelf: 'flex-start', background: 'rgba(0,0,0,0.75)', color: '#fff', fontSize: '9px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px', backdropFilter: 'blur(4px)', marginLeft: '8px', marginTop: '8px' }}>
                    BEFORE (Original)
                  </span>
                </div>

                {/* Right: After with Selected Tone */}
                <div
                  ref={afterScrollRef}
                  onScroll={() => handleSyncScroll('after')}
                  style={{
                    flex: 1,
                    height: '100%',
                    position: 'relative',
                    overflowY: fitMode === 'scroll' ? 'auto' : 'hidden',
                    overflowX: 'hidden',
                    display: 'flex',
                    alignItems: fitMode === 'contain' ? 'center' : 'flex-start',
                    justifyContent: 'center',
                    background: '#07080c'
                  }}
                >
                  {sampleImgUrl ? (
                    <img
                      src={sampleImgUrl}
                      alt="After"
                      style={{
                        width: '100%',
                        height: fitMode === 'contain' ? '100%' : 'auto',
                        objectFit: fitMode === 'contain' ? 'contain' : undefined,
                        display: 'block',
                        filter: currentPresetInfo.cssFilter,
                        transition: 'filter 0.25s ease'
                      }}
                    />
                  ) : (
                    <div style={{ width: '100%', height: '100%', background: currentPresetInfo.gradient, opacity: 0.85, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#fff', fontWeight: 700 }}>{currentPresetInfo.name}</span>
                    </div>
                  )}
                  <span style={{ position: 'sticky', top: '8px', right: '8px', zIndex: 10, alignSelf: 'flex-end', background: 'rgba(16, 185, 129, 0.9)', color: '#fff', fontSize: '9px', fontWeight: 700, padding: '2px 7px', borderRadius: '4px', backdropFilter: 'blur(4px)', marginRight: '8px', marginTop: '8px' }}>
                    AFTER ({currentPresetInfo.tone})
                  </span>
                </div>
              </>
            ) : previewMode === 'before' ? (
              <div
                ref={beforeScrollRef}
                style={{
                  width: '100%',
                  height: '100%',
                  position: 'relative',
                  overflowY: fitMode === 'scroll' ? 'auto' : 'hidden',
                  display: 'flex',
                  alignItems: fitMode === 'contain' ? 'center' : 'flex-start',
                  justifyContent: 'center',
                  background: '#07080c'
                }}
              >
                {sampleImgUrl ? (
                  <img
                    src={sampleImgUrl}
                    alt="Before"
                    style={{
                      width: '100%',
                      height: fitMode === 'contain' ? '100%' : 'auto',
                      objectFit: fitMode === 'contain' ? 'contain' : undefined,
                      display: 'block'
                    }}
                  />
                ) : (
                  <div style={{ width: '100%', height: '100%', background: '#1e293b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>Original Photo</span>
                  </div>
                )}
                <span style={{ position: 'sticky', top: '8px', left: '8px', zIndex: 10, alignSelf: 'flex-start', background: 'rgba(0,0,0,0.75)', color: '#fff', fontSize: '10px', fontWeight: 700, padding: '3px 8px', borderRadius: '4px', marginLeft: '8px', marginTop: '8px' }}>
                  BEFORE (Original Camera Look)
                </span>
              </div>
            ) : (
              <div
                ref={afterScrollRef}
                style={{
                  width: '100%',
                  height: '100%',
                  position: 'relative',
                  overflowY: fitMode === 'scroll' ? 'auto' : 'hidden',
                  display: 'flex',
                  alignItems: fitMode === 'contain' ? 'center' : 'flex-start',
                  justifyContent: 'center',
                  background: '#07080c'
                }}
              >
                {sampleImgUrl ? (
                  <img
                    src={sampleImgUrl}
                    alt="After"
                    style={{
                      width: '100%',
                      height: fitMode === 'contain' ? '100%' : 'auto',
                      objectFit: fitMode === 'contain' ? 'contain' : undefined,
                      display: 'block',
                      filter: currentPresetInfo.cssFilter,
                      transition: 'filter 0.25s ease'
                    }}
                  />
                ) : (
                  <div style={{ width: '100%', height: '100%', background: currentPresetInfo.gradient, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ fontSize: '12px', color: '#fff', fontWeight: 700 }}>{currentPresetInfo.name}</span>
                  </div>
                )}
                <span style={{ position: 'sticky', top: '8px', right: '8px', zIndex: 10, alignSelf: 'flex-end', background: 'rgba(16, 185, 129, 0.9)', color: '#fff', fontSize: '10px', fontWeight: 700, padding: '3px 8px', borderRadius: '4px', marginRight: '8px', marginTop: '8px' }}>
                  AFTER ({currentPresetInfo.name})
                </span>
              </div>
            )}

            {/* Quick Scroll Position Jumper when in Scroll mode */}
            {fitMode === 'scroll' && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '8px',
                  right: '12px',
                  zIndex: 20,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'rgba(15, 23, 42, 0.88)',
                  backdropFilter: 'blur(6px)',
                  padding: '3px 6px',
                  borderRadius: '6px',
                  border: '1px solid #334155',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
                }}
              >
                <span style={{ fontSize: '9px', color: '#94a3b8', marginRight: '3px' }}>↕ Jump:</span>
                <button
                  type="button"
                  onClick={() => scrollToPosition('top')}
                  title="Scroll to Top (Faces)"
                  style={{ background: '#1e293b', border: 'none', color: '#f1f5f9', padding: '2px 6px', borderRadius: '3px', fontSize: '9px', cursor: 'pointer' }}
                >
                  Top
                </button>
                <button
                  type="button"
                  onClick={() => scrollToPosition('center')}
                  title="Scroll to Center"
                  style={{ background: '#1e293b', border: 'none', color: '#f1f5f9', padding: '2px 6px', borderRadius: '3px', fontSize: '9px', cursor: 'pointer' }}
                >
                  Center
                </button>
                <button
                  type="button"
                  onClick={() => scrollToPosition('bottom')}
                  title="Scroll to Bottom (Attire / Saree)"
                  style={{ background: '#1e293b', border: 'none', color: '#f1f5f9', padding: '2px 6px', borderRadius: '3px', fontSize: '9px', cursor: 'pointer' }}
                >
                  Bottom
                </button>
              </div>
            )}
          </div>
        </div>

        {/* 3. Scope Selector Bar */}
        <div style={{
          padding: '8px 18px',
          background: '#0c0f16',
          borderBottom: '1px solid #1a1e2c',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8' }}>Apply To:</span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                onClick={() => setScope('selected')}
                disabled={selectedCount === 0}
                style={{
                  padding: '3px 10px',
                  borderRadius: '5px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: selectedCount > 0 ? 'pointer' : 'not-allowed',
                  border: scope === 'selected' ? '1px solid #10b981' : '1px solid #252b3a',
                  background: scope === 'selected' ? 'rgba(16, 185, 129, 0.15)' : '#151822',
                  color: scope === 'selected' ? '#34d399' : selectedCount === 0 ? '#475569' : '#94a3b8'
                }}
              >
                Selected Photos ({selectedCount})
              </button>
              <button
                type="button"
                onClick={() => setScope('all')}
                style={{
                  padding: '3px 10px',
                  borderRadius: '5px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: scope === 'all' ? '1px solid #10b981' : '1px solid #252b3a',
                  background: scope === 'all' ? 'rgba(16, 185, 129, 0.15)' : '#151822',
                  color: scope === 'all' ? '#34d399' : '#94a3b8'
                }}
              >
                All Project Photos ({totalCount})
              </button>
            </div>
          </div>

          <div style={{ fontSize: '11px', color: '#64748b' }}>
            Ready to edit <strong style={{ color: '#34d399' }}>{countToEdit}</strong> photos
          </div>
        </div>

        {/* 4. NICHE WALA STYLE SECTION (Scrollable Horizontal Presets Track) */}
        <div style={{ background: '#11141e', borderBottom: '1px solid #1c202e' }}>
          {/* Header of Presets Strip with Scroll Navigation Buttons */}
          <div style={{
            padding: '7px 18px 3px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sparkles size={12} style={{ color: '#38bdf8' }} />
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Editing Style Presets (10 Tones)
              </span>
              <span style={{ fontSize: '10px', color: '#64748b' }}>
                – Left/Right scroll karke select karein
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <button
                type="button"
                onClick={() => scrollPresets('left')}
                title="Scroll Left"
                style={{
                  background: '#1a1e2b',
                  border: '1px solid #272f42',
                  color: '#cbd5e1',
                  borderRadius: '4px',
                  padding: '2px 7px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <ChevronLeft size={12} />
              </button>
              <button
                type="button"
                onClick={() => scrollPresets('right')}
                title="Scroll Right"
                style={{
                  background: '#1a1e2b',
                  border: '1px solid #272f42',
                  color: '#cbd5e1',
                  borderRadius: '4px',
                  padding: '2px 7px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <ChevronRight size={12} />
              </button>
            </div>
          </div>

          {/* Horizontal Scrollable Presets Rack */}
          <div
            ref={presetsScrollRef}
            style={{
              padding: '6px 18px 10px 18px',
              display: 'flex',
              gap: '10px',
              overflowX: 'auto',
              overflowY: 'hidden',
              scrollBehavior: 'smooth'
            }}
          >
            {WEDDING_PRESETS.map((preset) => {
              const isSelected = selectedPreset === preset.id;
              const Icon = preset.icon;

              return (
                <div
                  key={preset.id}
                  onClick={() => setSelectedPreset(preset.id)}
                  style={{
                    minWidth: '215px',
                    maxWidth: '215px',
                    flexShrink: 0,
                    padding: '8px 10px',
                    borderRadius: '7px',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(16, 185, 129, 0.12)' : '#161924',
                    border: isSelected ? '2px solid #10b981' : '1px solid #262c3e',
                    boxShadow: isSelected ? '0 0 12px rgba(16, 185, 129, 0.28)' : 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '5px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {/* Preset Swatch Thumbnail & Name */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '7px', overflow: 'hidden' }}>
                      <div style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '5px',
                        overflow: 'hidden',
                        position: 'relative',
                        flexShrink: 0,
                        border: `1px solid ${preset.badge}44`
                      }}>
                        {sampleImgUrl ? (
                          <img
                            src={sampleImgUrl}
                            alt={preset.name}
                            style={{
                              width: '100%',
                              height: '100%',
                              objectFit: 'cover',
                              filter: preset.cssFilter
                            }}
                          />
                        ) : (
                          <div style={{ width: '100%', height: '100%', background: preset.gradient }} />
                        )}
                      </div>

                      <div style={{ overflow: 'hidden' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: '#f8fafc', display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {preset.name.split(' (')[0]}
                        </span>
                        <span style={{ fontSize: '9px', fontWeight: 600, color: preset.badge, display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {preset.tone}
                        </span>
                      </div>
                    </div>

                    <div style={{
                      width: '15px',
                      height: '15px',
                      borderRadius: '50%',
                      border: isSelected ? 'none' : '1.5px solid #475569',
                      background: isSelected ? '#10b981' : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      flexShrink: 0
                    }}>
                      {isSelected && <Check size={10} strokeWidth={3} />}
                    </div>
                  </div>

                  {/* 1-Line Description */}
                  <p style={{
                    margin: 0,
                    fontSize: '9.5px',
                    color: '#94a3b8',
                    lineHeight: 1.3,
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}>
                    {preset.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* 5. Footer */}
        <div style={{
          padding: '10px 20px',
          borderTop: '1px solid #1c202e',
          background: '#0c0f16',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: '#94a3b8' }}>
            <Sparkles size={13} style={{ color: '#10b981' }} />
            <span>Preset Selected: <strong style={{ color: '#f8fafc' }}>{currentPresetInfo.name}</strong></span>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button type="button" onClick={onClose} className="btn btn-secondary" style={{ padding: '6px 14px', fontSize: '11px' }}>
              Cancel
            </button>
            <button
              type="button"
              onClick={handleStart}
              className="btn btn-success"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 16px', fontWeight: 700, fontSize: '12px' }}
            >
              <Wand2 size={13} />
              <span>Start Auto Edit ({countToEdit} Photos)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
