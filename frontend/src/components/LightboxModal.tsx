import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Photo, UserSelection, EditParameters, HealSpot } from '../types';
import { api } from '../api';
import {
  X, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCcw,
  Check, Star, Sparkles, Sliders, Info, Maximize, Minimize, AlertTriangle,
  Bandage, Undo2
} from 'lucide-react';

interface LightboxModalProps {
  isOpen: boolean;
  photos: Photo[];
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
  onUpdateSelection: (photoId: number, selection: UserSelection) => void;
  onUpdateRating: (photoId: number, rating: number) => void;
  previewTimestamp?: number;
  onUpdateEdits?: (photoId: number, params: EditParameters) => void;
}

export const LightboxModal: React.FC<LightboxModalProps> = ({
  isOpen,
  photos,
  currentIndex,
  onClose,
  onNavigate,
  onUpdateSelection,
  onUpdateRating,
  previewTimestamp,
  onUpdateEdits,
}) => {
  const [zoom, setZoom] = useState<number>(1);
  const [showInfo, setShowInfo] = useState<boolean>(true);
  // Before / After slider (on by default in fullscreen): left of the handle = original, right = AI edit
  const [sliderOn, setSliderOn] = useState<boolean>(true);
  const [splitPos, setSplitPos] = useState<number>(50);
  const [dragging, setDragging] = useState<boolean>(false);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [healActive, setHealActive] = useState<boolean>(false);
  const [imgLoaded, setImgLoaded] = useState<boolean>(false);

  const photo = photos[currentIndex];

  const handleNext = useCallback(() => {
    if (currentIndex < photos.length - 1) {
      onNavigate(currentIndex + 1);
      setZoom(1);
      setImgLoaded(false);
    }
  }, [currentIndex, photos.length, onNavigate]);

  const handlePrev = useCallback(() => {
    if (currentIndex > 0) {
      onNavigate(currentIndex - 1);
      setZoom(1);
      setImgLoaded(false);
    }
  }, [currentIndex, onNavigate]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) return;

      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handlePrev();
      } else if (e.key.toUpperCase() === 'B' && photo) {
        e.preventDefault();
        onUpdateSelection(photo.id, 'BEST');
      } else if (e.key.toUpperCase() === 'P' && photo) {
        // "Pick" now means AI Best (the separate Selected category was removed)
        e.preventDefault();
        onUpdateSelection(photo.id, 'BEST');
      } else if (e.key.toUpperCase() === 'R' && photo) {
        e.preventDefault();
        onUpdateSelection(photo.id, 'REVIEW');
      } else if (e.key.toUpperCase() === 'X' && photo) {
        e.preventDefault();
        onUpdateSelection(photo.id, 'REJECT');
      } else if (e.key.toUpperCase() === 'U' && photo) {
        e.preventDefault();
        onUpdateSelection(photo.id, 'UNRATED');
      } else if (['1', '2', '3', '4', '5'].includes(e.key) && photo) {
        e.preventDefault();
        const rating = parseInt(e.key, 10);
        onUpdateRating(photo.id, photo.star_rating === rating ? 0 : rating);
      } else if (e.key === '\\' || e.key === '|') {
        e.preventDefault();
        setHealActive(false);
        setSliderOn(prev => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleNext, handlePrev, onClose, photo, onUpdateSelection, onUpdateRating]);

  const moveSplit = (clientX: number) => {
    const el = stageRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.width <= 0) return;
    setSplitPos(Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100)));
  };
  const compareActive = sliderOn && !healActive;

  // While dragging, follow the pointer anywhere on screen (fast drags / leaving the photo keep working)
  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: PointerEvent) => moveSplit(e.clientX);
    const onUp = () => setDragging(false);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
    };
  }, [dragging]);

  if (!isOpen || !photo) return null;

  const effective = photo.user_selection !== 'UNRATED' ? photo.user_selection : photo.ai_recommendation;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(7, 9, 12, 0.97)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        flexDirection: 'column',
        userSelect: 'none'
      }}
    >
      {/* 1. Header Bar */}
      <div
        style={{
          height: '50px',
          padding: '0 20px',
          background: 'rgba(15, 18, 24, 0.9)',
          borderBottom: '1px solid #232836',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 10
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span style={{ fontSize: '14px', fontWeight: 700, color: '#f8fafc' }}>
            {photo.filename}
          </span>
          <span style={{ fontSize: '11px', color: '#94a3b8', background: '#1c212c', padding: '2px 8px', borderRadius: '4px' }}>
            {currentIndex + 1} / {photos.length}
          </span>
          <span className={`badge ${
            effective === 'BEST' ? 'badge-best' :
            effective === 'SELECTED' ? 'badge-selected' :
            effective === 'REVIEW' ? 'badge-review' :
            effective === 'REJECT' ? 'badge-reject' : 'badge-similar'
          }`}>
            {effective === 'BEST' && '⭐ AI Best'}
            {effective === 'SELECTED' && '✓ Picked'}
            {effective === 'REVIEW' && '⚠ Review'}
            {effective === 'REJECT' && '✕ Rejected'}
            {effective === 'SIMILAR' && '👯 Similar'}
          </span>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Zoom buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: '#1c202a', padding: '3px 8px', borderRadius: '6px' }}>
            <button
              onClick={() => setZoom(prev => Math.max(0.5, prev - 0.25))}
              style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex' }}
              title="Zoom out (-)"
            >
              <ZoomOut size={15} />
            </button>
            <span style={{ fontSize: '11px', color: '#cbd5e1', minWidth: '40px', textAlign: 'center' }}>
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom(prev => Math.min(3, prev + 0.25))}
              style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex' }}
              title="Zoom in (+)"
            >
              <ZoomIn size={15} />
            </button>
            {zoom !== 1 && (
              <button
                onClick={() => setZoom(1)}
                style={{ background: 'transparent', border: 'none', color: '#38bdf8', cursor: 'pointer', fontSize: '10px', marginLeft: '4px' }}
                title="Reset zoom"
              >
                Reset
              </button>
            )}
          </div>

          {/* Before / After slider on / off */}
          <button
            onClick={() => { setHealActive(false); setSliderOn(!sliderOn); }}
            className={`btn btn-sm ${compareActive ? 'btn-success' : 'btn-secondary'}`}
            style={{ fontSize: '11px', padding: '4px 10px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '5px' }}
            title={"Before / After slider on or off (Shortcut: \\)"}
          >
            <Sliders size={13} />
            <span>{compareActive ? 'Before / After Slider: On' : 'Before / After Slider: Off'}</span>
            <span style={{ fontSize: '9px', opacity: 0.7 }}>({'\\'})</span>
          </button>

          {/* Heal Brush Button */}
          {onUpdateEdits && (
            <button
              onClick={() => { setHealActive(!healActive); if (!healActive) setSliderOn(false); }}
              className={`btn btn-sm ${healActive ? 'btn-success' : 'btn-secondary'}`}
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                background: healActive ? 'rgba(16, 185, 129, 0.25)' : undefined,
                borderColor: healActive ? '#10b981' : undefined,
                color: healActive ? '#34d399' : undefined
              }}
              title="Spot Healing Brush (Click to heal blemish/pimple)"
            >
              <Bandage size={13} />
              <span>{healActive ? 'Heal Active' : 'Heal'}</span>
            </button>
          )}

          {/* Toggle Info */}
          <button
            onClick={() => setShowInfo(!showInfo)}
            className="btn btn-secondary btn-sm"
            style={{ color: showInfo ? '#38bdf8' : '#94a3b8' }}
            title="Toggle photo info"
          >
            <Info size={14} />
          </button>

          {/* Close button */}
          <button
            onClick={onClose}
            style={{
              background: '#ef4444',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontWeight: 600,
              fontSize: '12px'
            }}
            title="Close Fullscreen (Esc)"
          >
            <X size={15} />
            <span>Close (Esc)</span>
          </button>
        </div>
      </div>

      {/* 2. Main Fullscreen Viewer */}
      <div
        style={{
          flex: 1,
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden'
        }}
      >
        {/* Navigation Arrows */}
        {currentIndex > 0 && (
          <button
            onClick={handlePrev}
            style={{
              position: 'absolute',
              left: '20px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: 'rgba(20, 24, 33, 0.85)',
              border: '1px solid #333d4e',
              color: '#f8fafc',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 20,
              boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
              transition: 'all 0.15s ease'
            }}
            title="Previous Photo (Left Arrow)"
          >
            <ChevronLeft size={28} />
          </button>
        )}

        {currentIndex < photos.length - 1 && (
          <button
            onClick={handleNext}
            style={{
              position: 'absolute',
              right: '20px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: 'rgba(20, 24, 33, 0.85)',
              border: '1px solid #333d4e',
              color: '#f8fafc',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 20,
              boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
              transition: 'all 0.15s ease'
            }}
            title="Next Photo (Right Arrow)"
          >
            <ChevronRight size={28} />
          </button>
        )}

        {/* Loading Spinner */}
        {!imgLoaded && (
          <div style={{ position: 'absolute', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', color: '#94a3b8' }}>
            <div style={{ width: '32px', height: '32px', border: '3px solid #2d3342', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <span style={{ fontSize: '11px' }}>Loading high-res preview...</span>
          </div>
        )}

        {/* Photo stage: AI edit, with the original revealed left of the slider handle */}
        <div
          ref={stageRef}
          className={`lb-stage ${dragging ? 'is-dragging' : ''}`}
          style={{ transform: `scale(${zoom})`, transition: zoom === 1 ? 'transform 0.15s ease' : 'none' }}
          onPointerDown={(e) => {
            if (!compareActive || e.button !== 0) return;
            e.preventDefault();
            setDragging(true);
            moveSplit(e.clientX);
          }}
        >
          <img
            key={`${photo.id}_after`}
            src={api.getPreviewUrl(photo.id, previewTimestamp || 1)}
            alt={photo.filename}
            onLoad={() => setImgLoaded(true)}
            onClick={(e) => {
              if (!healActive || !onUpdateEdits) return;
              const img = e.currentTarget;
              const rect = img.getBoundingClientRect();
              const clickX = e.clientX - rect.left;
              const clickY = e.clientY - rect.top;
              const normX = Math.max(0, Math.min(1, clickX / rect.width));
              const normY = Math.max(0, Math.min(1, clickY / rect.height));

              const newSpot: HealSpot = {
                x: Number(normX.toFixed(4)),
                y: Number(normY.toFixed(4)),
                radius: 0.018
              };
              const currentSpots = photo.edit_params?.heal_spots || [];
              onUpdateEdits(photo.id, {
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
              });
            }}
            style={{
              maxWidth: '94vw',
              maxHeight: '84vh',
              objectFit: 'contain',
              borderRadius: '6px',
              display: 'block',
              cursor: healActive ? 'crosshair' : (compareActive ? 'ew-resize' : 'default')
            }}
          />

          {compareActive && imgLoaded && (
            <>
              <img
                key={`${photo.id}_before`}
                className="lb-before"
                src={api.getOriginalUrl(photo.id)}
                alt=""
                draggable={false}
                style={{ clipPath: `inset(0 ${100 - splitPos}% 0 0)` }}
              />
              <div className="lb-divider" style={{ left: `${splitPos}%` }}>
                <div className="lb-handle"><ChevronLeft size={14} /><ChevronRight size={14} /></div>
              </div>
              <span className="lb-tag lb-tag-before" style={{ opacity: splitPos > 12 ? 1 : 0 }}>BEFORE</span>
              <span className="lb-tag lb-tag-after" style={{ opacity: splitPos < 88 ? 1 : 0 }}><Sparkles size={11} /> AFTER</span>
            </>
          )}
        </div>
        {compareActive && imgLoaded && (
          <div className="lb-hint">Drag the slider left / right to compare · {'\\'} to turn off</div>
        )}

        {/* Floating AI Diagnostics Pill */}
        {showInfo && (
          <div
            style={{
              position: 'absolute',
              bottom: '75px',
              background: 'rgba(16, 20, 28, 0.88)',
              backdropFilter: 'blur(8px)',
              border: '1px solid #28303f',
              borderRadius: '8px',
              padding: '8px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
              fontSize: '11px',
              color: '#cbd5e1',
              boxShadow: '0 4px 16px rgba(0,0,0,0.6)'
            }}
          >
            <div>
              <span style={{ color: '#64748b' }}>Score: </span>
              <strong style={{ color: (photo.ai_score ?? 0) >= 70 ? '#34d399' : (photo.ai_score ?? 0) >= 50 ? '#fbbf24' : '#f87171' }}>
                {Math.round(photo.ai_score ?? 0)}/100
              </strong>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Sharpness: </span>
              <strong>{photo.sharpness_score}</strong>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Exposure: </span>
              <strong>{photo.exposure_status}</strong>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Scene: </span>
              <strong style={{ color: '#38bdf8' }}>{photo.scene_category}</strong>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Resolution: </span>
              <strong>{photo.width} × {photo.height}</strong>
            </div>
          </div>
        )}
      </div>

      {/* 3. Bottom Action Bar */}
      <div
        style={{
          height: '56px',
          background: 'rgba(15, 18, 24, 0.95)',
          borderTop: '1px solid #232836',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 10
        }}
      >
        {/* Star Rating */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Rating:</span>
          <div style={{ display: 'flex', gap: '3px' }}>
            {[1, 2, 3, 4, 5].map((s) => (
              <Star
                key={s}
                size={18}
                onClick={() => onUpdateRating(photo.id, photo.star_rating === s ? 0 : s)}
                fill={photo.star_rating >= s ? '#eab308' : 'none'}
                stroke={photo.star_rating >= s ? '#eab308' : '#475569'}
                style={{ cursor: 'pointer', transition: 'all 0.1s ease' }}
              />
            ))}
          </div>
        </div>

        {/* Quick Best / Pick / Review / Reject Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => onUpdateSelection(photo.id, 'BEST')}
            style={{
              background: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '#f59e0b' : '#1c222d',
              color: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '#fff' : '#cbd5e1',
              border: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '1px solid #d97706' : '1px solid #2e3748',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            title="Mark as Best Photo (Key: B)"
          >
            <Star size={14} fill={(photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '#fff' : 'none'} />
            <span>Best (B)</span>
          </button>


          <button
            onClick={() => onUpdateSelection(photo.id, 'REVIEW')}
            style={{
              background: (photo.user_selection === 'REVIEW' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REVIEW')) ? '#f59e0b' : '#1c222d',
              color: (photo.user_selection === 'REVIEW' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REVIEW')) ? '#fff' : '#cbd5e1',
              border: (photo.user_selection === 'REVIEW' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REVIEW')) ? '1px solid #b45309' : '1px solid #2e3748',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            title="Mark for Review (Key: R)"
          >
            <AlertTriangle size={14} />
            <span>Review (R)</span>
          </button>

          <button
            onClick={() => onUpdateSelection(photo.id, 'REJECT')}
            style={{
              background: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT')) ? '#ef4444' : '#1c222d',
              color: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT')) ? '#fff' : '#cbd5e1',
              border: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT')) ? '1px solid #dc2626' : '1px solid #2e3748',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            title="Reject photo (Key: X)"
          >
            <X size={14} />
            <span>Reject (X)</span>
          </button>
        </div>

        {/* Keyboard hints */}
        <div style={{ fontSize: '11px', color: '#64748b', display: 'flex', gap: '10px' }}>
          <span>← / → Navigate</span>
          <span>B = Best</span>
          <span>P = Pick</span>
          <span>R = Review</span>
          <span>X = Reject</span>
          <span>1-5 = Stars</span>
          <span>Esc = Close</span>
        </div>
      </div>
    </div>
  );
};
