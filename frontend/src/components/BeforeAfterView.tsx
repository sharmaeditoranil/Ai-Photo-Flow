import React, { useState, useRef, useEffect } from 'react';
import { Photo, EditParameters, HealSpot } from '../types';
import { api } from '../api';
import {
  Columns, SplitSquareVertical, RotateCcw, Sparkles,
  Bandage, ZoomIn, ZoomOut, Undo2, Trash2, Check,
  Crosshair, Eye
} from 'lucide-react';

interface BeforeAfterViewProps {
  photo: Photo;
  previewTimestamp: number;
  onResetEdits: (photoId: number) => void;
  onAutoEditSingle: (photoId: number) => void;
  onUpdateEdits: (photoId: number, params: EditParameters) => void;
  healBrushActive?: boolean;
  onToggleHealBrush?: (active: boolean) => void;
  healBrushRadius?: number;
  onChangeHealBrushRadius?: (radius: number) => void;
}

interface ClickRipple {
  id: number;
  x: number;
  y: number;
}

export const BeforeAfterView: React.FC<BeforeAfterViewProps> = ({
  photo,
  previewTimestamp,
  onResetEdits,
  onAutoEditSingle,
  onUpdateEdits,
  healBrushActive = false,
  onToggleHealBrush,
  healBrushRadius = 0.010,
  onChangeHealBrushRadius,
}) => {
  const [splitPos, setSplitPos] = useState<number>(50); // 0 to 100
  const [viewMode, setViewMode] = useState<'split' | 'side-by-side' | 'heal'>(healBrushActive ? 'heal' : 'split');
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [zoom, setZoom] = useState<number>(1);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [ripples, setRipples] = useState<ClickRipple[]>([]);
  const [showSpotMarkers, setShowSpotMarkers] = useState<boolean>(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const healContainerRef = useRef<HTMLDivElement>(null);
  const editedImgRef = useRef<HTMLImageElement>(null);
  const healImgRef = useRef<HTMLImageElement>(null);

  // If heal brush is toggled on from inspector, switch view to 'heal' mode
  useEffect(() => {
    if (healBrushActive && viewMode !== 'heal') {
      setViewMode('heal');
    }
  }, [healBrushActive]);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (healBrushActive) return;
    setIsDragging(true);
  };
  const handlePointerUp = () => setIsDragging(false);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (healBrushActive) return;
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.min(Math.max((x / rect.width) * 100, 5), 95);
    setSplitPos(pct);
  };

  // Helper to compute normalized coordinates from click event on image
  const computeNormCoords = (
    clientX: number,
    clientY: number,
    containerEl: HTMLElement,
    imgEl: HTMLImageElement
  ): { normX: number; normY: number } | null => {
    const rect = containerEl.getBoundingClientRect();
    const clickX = clientX - rect.left;
    const clickY = clientY - rect.top;

    const containerW = rect.width;
    const containerH = rect.height;
    const naturalW = imgEl.naturalWidth || photo.width || 1000;
    const naturalH = imgEl.naturalHeight || photo.height || 800;

    const imageAspect = naturalW / naturalH;
    const containerAspect = containerW / containerH;

    let renderedW = containerW;
    let renderedH = containerH;
    let offsetX = 0;
    let offsetY = 0;

    if (containerAspect > imageAspect) {
      renderedH = containerH;
      renderedW = containerH * imageAspect;
      offsetX = (containerW - renderedW) / 2;
      offsetY = 0;
    } else {
      renderedW = containerW;
      renderedH = containerW / imageAspect;
      offsetX = 0;
      offsetY = (containerH - renderedH) / 2;
    }

    const imgClickX = clickX - offsetX;
    const imgClickY = clickY - offsetY;

    if (imgClickX < 0 || imgClickX > renderedW || imgClickY < 0 || imgClickY > renderedH) {
      return null;
    }

    return {
      normX: Math.max(0, Math.min(1, imgClickX / renderedW)),
      normY: Math.max(0, Math.min(1, imgClickY / renderedH))
    };
  };

  // Click handler to place a heal spot
  const handleSpotClick = (
    e: React.MouseEvent<HTMLDivElement>,
    containerEl: HTMLElement | null,
    imgEl: HTMLImageElement | null
  ) => {
    if (!containerEl || !imgEl) return;
    const coords = computeNormCoords(e.clientX, e.clientY, containerEl, imgEl);
    if (!coords) return;

    const rect = containerEl.getBoundingClientRect();
    const rippleX = e.clientX - rect.left;
    const rippleY = e.clientY - rect.top;

    const rippleId = Date.now();
    setRipples(prev => [...prev, { id: rippleId, x: rippleX, y: rippleY }]);
    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== rippleId));
    }, 600);

    const newSpot: HealSpot = {
      x: Number(coords.normX.toFixed(4)),
      y: Number(coords.normY.toFixed(4)),
      radius: Number(healBrushRadius.toFixed(4))
    };

    const currentSpots = photo.edit_params?.heal_spots || [];
    const updatedEdits: EditParameters = {
      ...(photo.edit_params || {
        exposure: 0,
        temperature: 0,
        tint: 0,
        contrast: 0,
        highlights: 0,
        shadows: 0,
        whites: 0,
        blacks: 0,
        vibrance: 0,
        saturation: 0,
        sharpness: 30,
        noise_reduction: 10,
        straighten: 0,
        preset_name: 'Pure Light (No Color Tone)'
      }),
      heal_spots: [...currentSpots, newSpot]
    };

    onUpdateEdits(photo.id, updatedEdits);
  };

  const handleRemoveSpot = (index: number) => {
    const currentSpots = photo.edit_params?.heal_spots || [];
    const updatedSpots = currentSpots.filter((_, idx) => idx !== index);
    onUpdateEdits(photo.id, {
      ...(photo.edit_params || {} as any),
      heal_spots: updatedSpots
    });
  };

  const handleUndoSpot = () => {
    const currentSpots = photo.edit_params?.heal_spots || [];
    if (currentSpots.length === 0) return;
    onUpdateEdits(photo.id, {
      ...(photo.edit_params || {} as any),
      heal_spots: currentSpots.slice(0, -1)
    });
  };

  const handleClearSpots = () => {
    onUpdateEdits(photo.id, {
      ...(photo.edit_params || {} as any),
      heal_spots: []
    });
  };

  const origUrl = api.getOriginalUrl(photo.id);
  const editedUrl = api.getPreviewUrl(photo.id, previewTimestamp);
  const healSpots = photo.edit_params?.heal_spots || [];

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
          {healSpots.length > 0 && (
            <span style={{ fontSize: '10px', background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '2px 7px', borderRadius: '10px', fontWeight: 600, border: '1px solid rgba(16, 185, 129, 0.4)' }}>
              🩹 {healSpots.length} Spots Healed
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Mode toggle */}
          <div style={{ display: 'flex', background: '#1c1f26', padding: '2px', borderRadius: '6px', border: '1px solid #282d3b' }}>
            <button
              onClick={() => {
                setViewMode('split');
                if (healBrushActive && onToggleHealBrush) onToggleHealBrush(false);
              }}
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
              onClick={() => {
                setViewMode('side-by-side');
                if (healBrushActive && onToggleHealBrush) onToggleHealBrush(false);
              }}
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
            <button
              onClick={() => {
                setViewMode('heal');
                if (!healBrushActive && onToggleHealBrush) onToggleHealBrush(true);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 10px',
                borderRadius: '4px',
                background: viewMode === 'heal' ? '#10b981' : 'transparent',
                color: viewMode === 'heal' ? '#fff' : '#94a3b8',
                border: 'none',
                fontSize: '11px',
                fontWeight: viewMode === 'heal' ? 700 : 500,
                cursor: 'pointer'
              }}
            >
              <Bandage size={12} />
              <span>🩹 Spot Retouch (Heal)</span>
            </button>
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

      {/* Spot Heal Controls Banner when in 'heal' mode */}
      {viewMode === 'heal' && (
        <div style={{
          height: '40px',
          padding: '0 20px',
          background: 'linear-gradient(90deg, #121820 0%, #15222e 100%)',
          borderBottom: '1px solid #1f2d3d',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '11px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <span style={{ color: '#38bdf8', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Crosshair size={13} />
              Click on pimples or blemish marks to remove them:
            </span>

            {/* Brush Size Slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#94a3b8' }}>Brush Radius:</span>
              <input
                type="range"
                min="0.004"
                max="0.024"
                step="0.001"
                value={healBrushRadius}
                onChange={(e) => onChangeHealBrushRadius && onChangeHealBrushRadius(parseFloat(e.target.value))}
                style={{ width: '80px', accentColor: '#38bdf8' }}
              />
              <span style={{ color: '#38bdf8', minWidth: '28px', fontWeight: 600 }}>
                {Math.round(healBrushRadius * 1000)}px
              </span>
            </div>

            {/* Zoom Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: '#1c222d', padding: '2px 6px', borderRadius: '4px' }}>
              <button
                type="button"
                onClick={() => setZoom(prev => Math.max(0.75, prev - 0.25))}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex' }}
                title="Zoom Out"
              >
                <ZoomOut size={13} />
              </button>
              <span style={{ fontSize: '10px', color: '#cbd5e1', minWidth: '35px', textAlign: 'center' }}>
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                onClick={() => setZoom(prev => Math.min(3, prev + 0.25))}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex' }}
                title="Zoom In"
              >
                <ZoomIn size={13} />
              </button>
              {zoom !== 1 && (
                <button
                  type="button"
                  onClick={() => setZoom(1)}
                  style={{ background: 'transparent', border: 'none', color: '#38bdf8', fontSize: '9px', cursor: 'pointer', marginLeft: '3px' }}
                >
                  Fit
                </button>
              )}
            </div>

            {/* Toggle Spot Markers */}
            <button
              type="button"
              onClick={() => setShowSpotMarkers(!showSpotMarkers)}
              style={{
                background: showSpotMarkers ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                border: '1px solid #283344',
                color: showSpotMarkers ? '#38bdf8' : '#94a3b8',
                padding: '2px 8px',
                borderRadius: '4px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '10px'
              }}
            >
              <Eye size={11} />
              <span>{showSpotMarkers ? 'Hide Markers' : 'Show Markers'}</span>
            </button>
          </div>

          {/* Undo and Clear */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#cbd5e1', fontWeight: 600 }}>
              {healSpots.length} Healed
            </span>
            <button
              type="button"
              disabled={healSpots.length === 0}
              onClick={handleUndoSpot}
              style={{
                background: '#1c222d',
                border: '1px solid #2a3446',
                color: healSpots.length > 0 ? '#cbd5e1' : '#475569',
                padding: '3px 8px',
                borderRadius: '4px',
                cursor: healSpots.length > 0 ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '10px'
              }}
            >
              <Undo2 size={11} />
              <span>Undo</span>
            </button>
            <button
              type="button"
              disabled={healSpots.length === 0}
              onClick={handleClearSpots}
              style={{
                background: '#231518',
                border: '1px solid #4a2228',
                color: healSpots.length > 0 ? '#f87171' : '#475569',
                padding: '3px 8px',
                borderRadius: '4px',
                cursor: healSpots.length > 0 ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '10px'
              }}
            >
              <Trash2 size={11} />
              <span>Clear</span>
            </button>
          </div>
        </div>
      )}

      {/* Main Canvas Area */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', overflow: 'auto', position: 'relative' }}>
        {viewMode === 'heal' ? (
          /* ========================================================
             Mode 3: Spot Retouch & Healing Canvas
             ======================================================== */
          <div
            ref={healContainerRef}
            onClick={(e) => handleSpotClick(e, healContainerRef.current, healImgRef.current)}
            onMouseMove={(e) => {
              if (!healContainerRef.current) return;
              const rect = healContainerRef.current.getBoundingClientRect();
              setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
            }}
            onMouseLeave={() => setMousePos(null)}
            style={{
              position: 'relative',
              width: zoom === 1 ? '92%' : `${92 * zoom}%`,
              maxWidth: zoom === 1 ? '1300px' : 'none',
              height: zoom === 1 ? '78vh' : `${78 * zoom}vh`,
              background: '#0a0c10',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 10px 35px rgba(0,0,0,0.6)',
              cursor: 'crosshair',
              transition: 'width 0.15s ease, height 0.15s ease'
            }}
          >
            <img
              ref={healImgRef}
              src={editedUrl}
              alt="Retouch View"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                position: 'absolute',
                top: 0,
                left: 0,
                pointerEvents: 'none'
              }}
            />

            {/* Healed Spot Markers Overlay */}
            {showSpotMarkers && healContainerRef.current && healImgRef.current && (
              healSpots.map((spot, idx) => {
                const containerEl = healContainerRef.current!;
                const imgEl = healImgRef.current!;
                const rect = containerEl.getBoundingClientRect();
                const containerW = rect.width;
                const containerH = rect.height;
                const naturalW = imgEl.naturalWidth || photo.width || 1000;
                const naturalH = imgEl.naturalHeight || photo.height || 800;

                const imageAspect = naturalW / naturalH;
                const containerAspect = containerW / containerH;

                let renderedW = containerW;
                let renderedH = containerH;
                let offsetX = 0;
                let offsetY = 0;

                if (containerAspect > imageAspect) {
                  renderedH = containerH;
                  renderedW = containerH * imageAspect;
                  offsetX = (containerW - renderedW) / 2;
                } else {
                  renderedW = containerW;
                  renderedH = containerW / imageAspect;
                  offsetY = (containerH - renderedH) / 2;
                }

                const markerLeft = offsetX + spot.x * renderedW;
                const markerTop = offsetY + spot.y * renderedH;
                const markerSize = Math.max(16, spot.radius * renderedW * 2);

                return (
                  <div
                    key={idx}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveSpot(idx);
                    }}
                    title={`Spot #${idx + 1} (Click to remove)`}
                    style={{
                      position: 'absolute',
                      left: markerLeft,
                      top: markerTop,
                      width: `${markerSize}px`,
                      height: `${markerSize}px`,
                      borderRadius: '50%',
                      transform: 'translate(-50%, -50%)',
                      border: '1.5px dashed #38bdf8',
                      boxShadow: '0 0 8px rgba(56, 189, 248, 0.4)',
                      background: 'rgba(56, 189, 248, 0.1)',
                      cursor: 'pointer',
                      zIndex: 25,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontSize: '9px',
                      fontWeight: 700
                    }}
                  >
                    <span style={{ textShadow: '0 1px 2px #000' }}>×</span>
                  </div>
                );
              })
            )}

            {/* Click Ripples */}
            {ripples.map(r => (
              <div
                key={r.id}
                style={{
                  position: 'absolute',
                  left: r.x,
                  top: r.y,
                  width: `${Math.max(24, healBrushRadius * 1400)}px`,
                  height: `${Math.max(24, healBrushRadius * 1400)}px`,
                  transform: 'translate(-50%, -50%)',
                  borderRadius: '50%',
                  border: '2px solid #10b981',
                  background: 'rgba(16, 185, 129, 0.3)',
                  boxShadow: '0 0 16px rgba(16, 185, 129, 0.8)',
                  pointerEvents: 'none',
                  animation: 'ripple 0.6s ease-out forwards',
                  zIndex: 30
                }}
              />
            ))}

            {/* Circular Brush Reticle Follower */}
            {mousePos && healContainerRef.current && (
              <div
                style={{
                  position: 'absolute',
                  left: mousePos.x,
                  top: mousePos.y,
                  width: `${Math.max(16, healBrushRadius * (healContainerRef.current.clientWidth || 1000) * 2)}px`,
                  height: `${Math.max(16, healBrushRadius * (healContainerRef.current.clientWidth || 1000) * 2)}px`,
                  transform: 'translate(-50%, -50%)',
                  borderRadius: '50%',
                  border: '1.5px solid rgba(56, 189, 248, 0.85)',
                  boxShadow: '0 0 10px rgba(56, 189, 248, 0.5), inset 0 0 4px rgba(56, 189, 248, 0.3)',
                  pointerEvents: 'none',
                  zIndex: 40
                }}
              />
            )}

            {/* Mode Banner Tag */}
            <span style={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              background: 'rgba(16, 185, 129, 0.85)',
              color: '#fff',
              padding: '4px 10px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 700,
              boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              zIndex: 10
            }}>
              <Bandage size={12} /> RETOUCH & HEAL CANVAS
            </span>
          </div>
        ) : viewMode === 'split' ? (
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
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
