import React, { useState } from 'react';
import { Photo, EditParameters, UserSelection } from '../types';
import { Histogram } from './Histogram';
import { api } from '../api';
import { WEDDING_PRESETS } from '../presets';
import { RetouchPanel } from './RetouchPanel';
import { WhiteBalanceCard } from './WhiteBalanceCard';

import {
  Sparkles, RotateCcw, Sliders, ShieldCheck,
  CheckCircle2, AlertTriangle, Eye, Activity,
  Star, CheckCircle, XCircle, Tag, Copy,
  LayoutGrid, List, Check, Wand2
} from 'lucide-react';


interface InspectorPanelProps {
  photo: Photo | null;
  onUpdateEdits: (photoId: number, params: EditParameters) => void;
  onResetEdits: (photoId: number) => void;
  onAutoEditSingle: (photoId: number, presetName: string) => void;
  onUpdateSelection?: (photoId: number, selection: UserSelection) => void;
  selectedStylePreset?: string;
  onSelectStylePreset?: (presetName: string) => void;
  autoEditRetouchPreset?: string;
  onSelectAutoEditRetouchPreset?: (presetName: string) => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  photo,
  onUpdateEdits,
  onResetEdits,
  onAutoEditSingle,
  onUpdateSelection,
  selectedStylePreset,
  onSelectStylePreset,
  autoEditRetouchPreset,
  onSelectAutoEditRetouchPreset,
}) => {

  if (!photo) {
    return (
      <aside className="inspector-panel" style={{ padding: '24px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
        <p style={{ textAlign: 'center', fontSize: '12px' }}>Select a photo to inspect AI scores and edit parameters</p>
      </aside>
    );
  }

  const defaultEdits: EditParameters = {
    exposure: 0,
    subject_exposure: 0,
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
    preset_name: 'Pure Light (No Color Tone)',
    auto_blemish: 0,
    heal_opacity: 100,
    heal_face_preset: 'AUTO',
    skin_smoothing: 0,
    dodge_burn: 0,
    skin_glow: 0,
    heal_spots: [],
    retouch: null,
    auto_wb: null
  };

  const edits: EditParameters = {
    ...defaultEdits,
    ...(photo.edit_params || {})
  };

  const handleSliderChange = (key: keyof EditParameters, value: number) => {
    const updated = { ...edits, [key]: value };
    onUpdateEdits(photo.id, updated);
  };

  const handleParamChange = (key: keyof EditParameters, value: any) => {
    const updated = { ...edits, [key]: value };
    onUpdateEdits(photo.id, updated);
  };

  const [presetViewMode, setPresetViewMode] = useState<'cards' | 'compact'>('cards');

  const activePresetId = edits.preset_name || selectedStylePreset || 'Pure Light (No Color Tone)';
  const activePreset = WEDDING_PRESETS.find(p => p.id === activePresetId) || WEDDING_PRESETS[0];



  return (
    <aside className="inspector-panel">
      {/* 1. Live Histogram */}
      <div style={{ padding: '12px 14px 8px 14px', borderBottom: '1px solid #1c202a' }}>
        <Histogram photo={photo} />
      </div>

      {/* 2. AI Diagnostics Card */}
      <div style={{ padding: '14px', borderBottom: '1px solid #1c202a', background: '#12141a' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Activity size={14} style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              AI Diagnostics
            </span>
          </div>
          <span style={{ fontSize: '11px', color: '#64748b' }}>Confidence {Math.round(photo.ai_confidence)}%</span>
        </div>

        {/* Quality Score & Recommendation */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#181b22', padding: '10px 12px', borderRadius: '6px', marginBottom: '10px', border: '1px solid #232733' }}>
          <div>
            <div style={{ fontSize: '10px', color: '#94a3b8' }}>Composite Quality</div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: photo.ai_score >= 70 ? '#34d399' : photo.ai_score >= 50 ? '#fbbf24' : '#f87171' }}>
              {Math.round(photo.ai_score)} <span style={{ fontSize: '11px', fontWeight: 400, color: '#64748b' }}>/ 100</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '2px', textAlign: 'right' }}>Recommendation</div>
            <span className={`badge ${
              photo.ai_recommendation === 'BEST' ? 'badge-best' :
              photo.ai_recommendation === 'SELECTED' ? 'badge-selected' :
              photo.ai_recommendation === 'REVIEW' ? 'badge-review' :
              photo.ai_recommendation === 'REJECT' ? 'badge-reject' : 'badge-similar'
            }`}>
              {photo.ai_recommendation}
            </span>
          </div>
        </div>

        {/* Metrics Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px' }}>
          <div style={{ background: '#161920', padding: '6px 8px', borderRadius: '4px', border: '1px solid #20242e' }}>
            <div style={{ color: '#64748b', fontSize: '10px' }}>Sharpness</div>
            <div style={{ fontWeight: 600, color: photo.blur_detected ? '#f87171' : '#f1f5f9' }}>
              {photo.sharpness_score} {photo.blur_detected ? '(Blur)' : ''}
            </div>
          </div>

          <div style={{ background: '#161920', padding: '6px 8px', borderRadius: '4px', border: '1px solid #20242e' }}>
            <div style={{ color: '#64748b', fontSize: '10px' }}>Eyes Status</div>
            <div style={{ fontWeight: 600, color: photo.eyes_status === 'OPEN' ? '#34d399' : photo.eyes_status === 'CLOSED' ? '#f87171' : '#cbd5e1' }}>
              {photo.eyes_status}
            </div>
          </div>

          <div style={{ background: '#161920', padding: '6px 8px', borderRadius: '4px', border: '1px solid #20242e' }}>
            <div style={{ color: '#64748b', fontSize: '10px' }}>Exposure</div>
            <div style={{ fontWeight: 600, color: photo.exposure_status === 'GOOD' ? '#34d399' : '#fbbf24' }}>
              {photo.exposure_status === 'GOOD' ? 'Well Balanced' : photo.exposure_status}
            </div>
          </div>

          <div style={{ background: '#161920', padding: '6px 8px', borderRadius: '4px', border: '1px solid #20242e' }}>
            <div style={{ color: '#64748b', fontSize: '10px' }}>Burst Group</div>
            <div style={{ fontWeight: 600, color: photo.duplicate_group_id ? '#a78bfa' : '#64748b', fontSize: '11px' }}>
              {photo.duplicate_group_id ? `${photo.duplicate_group_id} (${photo.duplicate_group_count || 1} in set)` : 'Unique'}
            </div>
          </div>
        </div>

        {/* Burst Group Detailed Summary */}
        {photo.duplicate_group_id && (
          <div style={{ marginTop: '8px', background: 'rgba(139, 92, 246, 0.08)', border: '1px solid rgba(139, 92, 246, 0.25)', borderRadius: '4px', padding: '7px 10px', fontSize: '11px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#a78bfa', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Copy size={11} /> {photo.duplicate_group_id} Sequence:
              </span>
              <span style={{ color: '#cbd5e1', fontWeight: 600 }}>
                {photo.duplicate_group_count || 1} Similar Photos
              </span>
            </div>
            {photo.duplicate_group_best_filename && (
              <div style={{ marginTop: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(139, 92, 246, 0.15)', paddingTop: '4px' }}>
                <span style={{ color: '#94a3b8' }}>Best Picked:</span>
                <span style={{ color: photo.is_group_best ? '#facc15' : '#38bdf8', fontWeight: 700 }}>
                  {photo.is_group_best ? '★ This Photo (Selected)' : photo.duplicate_group_best_filename}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Scene Classification */}
        <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', background: '#161920', padding: '6px 10px', borderRadius: '4px' }}>
          <span style={{ color: '#94a3b8' }}>Wedding Scene:</span>
          <span style={{ color: '#38bdf8', fontWeight: 600 }}>{photo.scene_category}</span>
        </div>

        {/* Subject-First Priority AI Light Metering */}
        <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', background: 'rgba(56, 189, 248, 0.10)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '7px 10px', borderRadius: '4px' }}>
          <span style={{ color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
            <Eye size={13} style={{ color: '#38bdf8' }} /> Priority Focus:
          </span>
          <span style={{ color: '#38bdf8', fontWeight: 700, background: 'rgba(56, 189, 248, 0.15)', padding: '2px 6px', borderRadius: '3px' }}>
            {photo.faces_count > 0 ? (photo.faces_count <= 2 ? 'Subject First: Couple' : `Subject First: ${photo.faces_count} Faces`) : 'Subject First: Ritual / Décor'}
          </span>
        </div>
      </div>

      {/* 2.5 Manual Culling Decision Override */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #1c202a', background: '#12141a' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Tag size={13} style={{ color: '#a78bfa' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Manual Culling
            </span>
          </div>
          <span style={{ fontSize: '10px', color: photo.user_selection !== 'UNRATED' ? '#38bdf8' : '#64748b' }}>
            {photo.user_selection !== 'UNRATED' ? 'User Override Active' : 'AI Default'}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', marginBottom: '8px' }}>
          <button
            onClick={() => onUpdateSelection?.(photo.id, 'BEST')}
            style={{
              padding: '6px 8px',
              borderRadius: '5px',
              border: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST'))
                ? '1px solid #eab308'
                : '1px solid #232733',
              background: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST'))
                ? 'rgba(234, 179, 8, 0.2)'
                : '#181b22',
              color: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST'))
                ? '#facc15'
                : '#cbd5e1',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px'
            }}
            title="Mark as Best Photo (Key: B)"
          >
            <Star size={12} fill={(photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '#facc15' : 'none'} />
            Best (B)
          </button>


          <button
            onClick={() => onUpdateSelection?.(photo.id, 'REVIEW')}
            style={{
              padding: '6px 8px',
              borderRadius: '5px',
              border: (photo.user_selection === 'REVIEW' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REVIEW'))
                ? '1px solid #f59e0b'
                : '1px solid #232733',
              background: (photo.user_selection === 'REVIEW' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REVIEW'))
                ? 'rgba(245, 158, 11, 0.2)'
                : '#181b22',
              color: (photo.user_selection === 'REVIEW' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REVIEW'))
                ? '#fbbf24'
                : '#cbd5e1',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px'
            }}
            title="Mark for Review (Key: R)"
          >
            <AlertTriangle size={12} />
            Review (R)
          </button>

          <button
            onClick={() => onUpdateSelection?.(photo.id, 'REJECT')}
            style={{
              padding: '6px 8px',
              borderRadius: '5px',
              border: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT'))
                ? '1px solid #ef4444'
                : '1px solid #232733',
              background: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT'))
                ? 'rgba(239, 68, 68, 0.2)'
                : '#181b22',
              color: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT'))
                ? '#f87171'
                : '#cbd5e1',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px'
            }}
            title="Reject photo (Key: X)"
          >
            <XCircle size={12} />
            Reject (X)
          </button>
        </div>

        {photo.user_selection !== 'UNRATED' && (
          <button
            onClick={() => onUpdateSelection?.(photo.id, 'UNRATED')}
            style={{
              width: '100%',
              padding: '4px 8px',
              borderRadius: '4px',
              border: '1px dashed #334155',
              background: 'transparent',
              color: '#94a3b8',
              fontSize: '10px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px'
            }}
            title="Reset to AI recommendation (Key: U)"
          >
            <RotateCcw size={11} /> Reset to AI Decision
          </button>
        )}
      </div>

      {/* 3. Editing Style & Color Tone Presets with Live Visual Preview */}
      <div style={{ padding: '14px', borderBottom: '1px solid #1c202a', background: '#0e1117' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={13} style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Editing Style & Tone
            </span>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '10px', color: '#10b981', display: 'flex', alignItems: 'center', gap: '2px', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 5px', borderRadius: '4px' }}>
              <ShieldCheck size={11} /> Skin Safe
            </span>
            <div style={{ display: 'flex', background: '#1c202a', borderRadius: '4px', padding: '1px' }}>
              <button
                type="button"
                onClick={() => setPresetViewMode('cards')}
                title="Visual Preview Cards"
                style={{
                  background: presetViewMode === 'cards' ? '#3b82f6' : 'transparent',
                  border: 'none',
                  borderRadius: '3px',
                  color: presetViewMode === 'cards' ? '#fff' : '#64748b',
                  padding: '3px 5px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <LayoutGrid size={11} />
              </button>
              <button
                type="button"
                onClick={() => setPresetViewMode('compact')}
                title="Compact List"
                style={{
                  background: presetViewMode === 'compact' ? '#3b82f6' : 'transparent',
                  border: 'none',
                  borderRadius: '3px',
                  color: presetViewMode === 'compact' ? '#fff' : '#64748b',
                  padding: '3px 5px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <List size={11} />
              </button>
            </div>
          </div>
        </div>

        {presetViewMode === 'cards' ? (
          /* Visual Cards Grid with Live Filter Preview on Current Photo */
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '8px',
              maxHeight: '260px',
              overflowY: 'auto',
              paddingRight: '2px'
            }}
          >
            {WEDDING_PRESETS.map((p) => {
              const isSelected = activePresetId === p.id;
              const Icon = p.icon;
              return (
                <div
                  key={p.id}
                  onClick={() => {
                    handleSliderChange('preset_name' as any, p.id as any);
                    if (onSelectStylePreset) onSelectStylePreset(p.id);
                    onAutoEditSingle(photo.id, p.id);
                  }}

                  title={`${p.name}\n${p.description}`}
                  style={{
                    position: 'relative',
                    borderRadius: '7px',
                    overflow: 'hidden',
                    cursor: 'pointer',
                    border: isSelected ? '2px solid #38bdf8' : '1px solid #232834',
                    background: isSelected ? 'rgba(56, 189, 248, 0.08)' : '#161922',
                    boxShadow: isSelected ? '0 0 10px rgba(56, 189, 248, 0.35)' : 'none',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column'
                  }}
                >
                  {/* Visual Preview Thumbnail with CSS Filter */}
                  <div style={{ position: 'relative', width: '100%', height: '52px', overflow: 'hidden', background: '#0a0c10' }}>
                    <img
                      src={api.getThumbnailUrl(photo.id)}
                      alt={p.name}

                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        filter: p.cssFilter,
                        transition: 'filter 0.2s ease'
                      }}
                      onError={(e) => {
                        // Fallback to gradient if image thumbnail fails
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                    {/* Gradient fallback overlay behind image */}
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        zIndex: -1,
                        background: p.gradient
                      }}
                    />

                    {/* Top tone label */}
                    <div
                      style={{
                        position: 'absolute',
                        top: '3px',
                        left: '4px',
                        background: 'rgba(0, 0, 0, 0.65)',
                        backdropFilter: 'blur(4px)',
                        padding: '1px 5px',
                        borderRadius: '3px',
                        fontSize: '9px',
                        fontWeight: 600,
                        color: p.badge,
                        maxWidth: '90%',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                      }}
                    >
                      {p.name.split(' (')[0]}
                    </div>

                    {/* Selected Checkmark */}
                    {isSelected && (
                      <div
                        style={{
                          position: 'absolute',
                          top: '3px',
                          right: '4px',
                          width: '15px',
                          height: '15px',
                          borderRadius: '50%',
                          background: '#38bdf8',
                          color: '#000',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          boxShadow: '0 0 4px rgba(0,0,0,0.5)'
                        }}
                      >
                        <Check size={10} strokeWidth={3} />
                      </div>
                    )}
                  </div>

                  {/* Preset Label & Tone Info */}
                  <div style={{ padding: '5px 6px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', overflow: 'hidden' }}>
                      <Icon size={10} style={{ color: p.badge, flexShrink: 0 }} />
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: isSelected ? 700 : 500,
                          color: isSelected ? '#38bdf8' : '#cbd5e1',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis'
                        }}
                      >
                        {p.name.split(' (')[0]}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* Compact Select Mode */
          <select
            value={activePresetId}
            onChange={(e) => {
              const newPreset = e.target.value;
              handleSliderChange('preset_name' as any, newPreset as any);
              if (onSelectStylePreset) onSelectStylePreset(newPreset);
              onAutoEditSingle(photo.id, newPreset);
            }}

            style={{
              width: '100%',
              background: '#181b22',
              color: '#f1f5f9',
              border: '1px solid #2d3342',
              padding: '6px 10px',
              borderRadius: '6px',
              fontSize: '12px',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            {WEDDING_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>{p.name} – {p.tone}</option>
            ))}
          </select>
        )}

        {/* Active Preset Banner & Details */}
        <div
          style={{
            marginTop: '8px',
            padding: '7px 9px',
            borderRadius: '6px',
            background: 'rgba(28, 32, 42, 0.6)',
            border: '1px solid #232834',
            display: 'flex',
            flexDirection: 'column',
            gap: '3px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '10px', fontWeight: 700, color: activePreset.badge, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: activePreset.badge }} />
              {activePreset.name}
            </span>
            <button
              type="button"
              onClick={() => onAutoEditSingle(photo.id, activePreset.id)}
              title="Apply preset now"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#38bdf8',
                fontSize: '10px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
                padding: '0'
              }}
            >
              <Wand2 size={10} /> Apply
            </button>
          </div>
          <span style={{ fontSize: '9.5px', color: '#94a3b8', lineHeight: '1.3' }}>
            {activePreset.description}
          </span>
        </div>
      </div>

      {/* 3.3. AI Auto White Balance */}
      <WhiteBalanceCard wb={edits.auto_wb} onCommit={(wb) => handleParamChange('auto_wb', wb)} />

      {/* 3.4. AI Skin Retouch (Heal, Mattifier, Skin Mask, Smoothing, Imperfections, Skin Tone) */}
      <RetouchPanel
        edits={edits}
        onCommit={(retouch) => handleParamChange('retouch', retouch)}
        autoEditPreset={autoEditRetouchPreset ?? 'Natural'}
        onSelectAutoEditPreset={(name) => onSelectAutoEditRetouchPreset?.(name)}
      />

      {/* 3.5. Portrait & Skin Enhancement */}
      <div style={{ padding: '14px', borderBottom: '1px solid #1c202a', background: 'linear-gradient(180deg, #131720 0%, #11141b 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={14} style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Portrait Depth
            </span>
          </div>
        </div>


        {/* AI Portrait Dodge & Burn (3D Depth & Glow) Slider */}
        <div className="slider-group" style={{ marginBottom: '12px', paddingTop: '8px', borderTop: '1px dashed #232836' }}>
          <div className="slider-header">
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ fontWeight: 600, color: '#e2e8f0' }}>Dodge & Burn (3D Depth)</span>
              <span style={{ fontSize: '10px', color: '#64748b' }}>(3D कंटूर व ग्लो)</span>
            </span>
            <span className="slider-val" style={{ color: (edits.dodge_burn ?? 0) > 0 ? '#f59e0b' : '#94a3b8' }}>
              {(edits.dodge_burn ?? 0) > 0 ? `${Math.round(edits.dodge_burn ?? 0)}%` : 'Off'}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={edits.dodge_burn ?? 0}
            onChange={(e) => handleSliderChange('dodge_burn' as any, parseFloat(e.target.value))}
            style={{ accentColor: '#f59e0b' }}
          />

          {/* Quick preset buttons */}
          <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
            {[
              { label: 'Off', val: 0 },
              { label: 'Subtle', val: 20 },
              { label: 'Natural', val: 35 },
              { label: 'Studio', val: 50 },
            ].map(lvl => (
              <button
                key={lvl.val}
                type="button"
                onClick={() => handleSliderChange('dodge_burn' as any, lvl.val)}
                style={{
                  flex: 1,
                  padding: '3px 0',
                  fontSize: '9.5px',
                  borderRadius: '4px',
                  border: (edits.dodge_burn ?? 0) === lvl.val ? '1px solid #f59e0b' : '1px solid #232836',
                  background: (edits.dodge_burn ?? 0) === lvl.val ? 'rgba(245, 158, 11, 0.2)' : '#181b22',
                  color: (edits.dodge_burn ?? 0) === lvl.val ? '#fbbf24' : '#94a3b8',
                  cursor: 'pointer'
                }}
              >
                {lvl.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: '9.5px', color: '#64748b', marginTop: '4px', lineHeight: '1.3' }}>
            Subtle 3D portrait sculpting: brings natural radiance to cheekbones & eye catchlights, and soft contour to jawline. 100% gentle and natural.
          </div>
        </div>

        {/* Skin Glow: soft radiance on real skin only */}
        <div className="slider-group" style={{ marginBottom: '12px', paddingTop: '8px', borderTop: '1px dashed #232836' }}>
          <div className="slider-header">
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ fontWeight: 600, color: '#e2e8f0' }}>Skin Glow</span>
              <span style={{ fontSize: '10px', color: '#64748b' }}>(स्किन ग्लो)</span>
            </span>
            <span className="slider-val" style={{ color: (edits.skin_glow ?? 0) > 0 ? '#f472b6' : '#94a3b8' }}>
              {(edits.skin_glow ?? 0) > 0 ? `${Math.round(edits.skin_glow ?? 0)}%` : 'Off'}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={edits.skin_glow ?? 0}
            onChange={(e) => handleSliderChange('skin_glow' as any, parseFloat(e.target.value))}
            style={{ accentColor: '#f472b6' }}
          />
          <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
            {[
              { label: 'Off', val: 0 },
              { label: 'Light', val: 40 },
              { label: 'Natural', val: 65 },
              { label: 'Radiant', val: 90 },
            ].map(lvl => (
              <button
                key={lvl.val}
                type="button"
                onClick={() => handleSliderChange('skin_glow' as any, lvl.val)}
                style={{
                  flex: 1,
                  padding: '3px 0',
                  fontSize: '9.5px',
                  borderRadius: '4px',
                  border: (edits.skin_glow ?? 0) === lvl.val ? '1px solid #f472b6' : '1px solid #232836',
                  background: (edits.skin_glow ?? 0) === lvl.val ? 'rgba(244, 114, 182, 0.18)' : '#181b22',
                  color: (edits.skin_glow ?? 0) === lvl.val ? '#f9a8d4' : '#94a3b8',
                  cursor: 'pointer'
                }}
              >
                {lvl.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: '9.5px', color: '#64748b', marginTop: '4px', lineHeight: '1.3' }}>
            Soft radiance on skin only (eyes, lips, hair, clothes and background are untouched). Overall light does not change.
          </div>
        </div>

      </div>


      {/* 4. Non-Destructive Manual Sliders */}
      <div style={{ padding: '14px', flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sliders size={13} style={{ color: '#3b82f6' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#9ba3b4', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Photo Adjustments
            </span>
          </div>

          <button
            onClick={() => onResetEdits(photo.id)}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '3px' }}
          >
            <RotateCcw size={11} />
            <span>Reset</span>
          </button>
        </div>

        {/* Exposure */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Exposure</span>
            <span className="slider-val">{(edits.exposure ?? 0) > 0 ? `+${(edits.exposure ?? 0).toFixed(2)}` : (edits.exposure ?? 0).toFixed(2)} EV</span>
          </div>
          <input
            type="range"
            min="-2.5"
            max="2.5"
            step="0.05"
            value={edits.exposure}
            onChange={(e) => handleSliderChange('exposure', parseFloat(e.target.value))}
          />
        </div>

        {/* Subject Light: brightness of the detected subject only (background unchanged) */}
        <div className="slider-group">
          <div className="slider-header">
            <span title="Changes light only on the detected subject (faces / people). Background stays as it is.">Subject Light</span>
            <span className="slider-val">{(edits.subject_exposure ?? 0) > 0 ? `+${(edits.subject_exposure ?? 0).toFixed(2)}` : (edits.subject_exposure ?? 0).toFixed(2)} EV</span>
          </div>
          <input
            type="range"
            min="-1.2"
            max="0.5"
            step="0.05"
            value={edits.subject_exposure ?? 0}
            onChange={(e) => handleSliderChange('subject_exposure', parseFloat(e.target.value))}
          />
        </div>

        {/* Temperature */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Temperature (WB)</span>
            <span className="slider-val">{edits.temperature > 0 ? `+${edits.temperature}` : edits.temperature}</span>
          </div>
          <input
            type="range"
            min="-50"
            max="50"
            step="1"
            value={edits.temperature}
            onChange={(e) => handleSliderChange('temperature', parseFloat(e.target.value))}
          />
        </div>

        {/* Tint */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Tint</span>
            <span className="slider-val">{edits.tint > 0 ? `+${edits.tint}` : edits.tint}</span>
          </div>
          <input
            type="range"
            min="-40"
            max="40"
            step="1"
            value={edits.tint}
            onChange={(e) => handleSliderChange('tint', parseFloat(e.target.value))}
          />
        </div>

        {/* Contrast */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Contrast</span>
            <span className="slider-val">{edits.contrast > 0 ? `+${edits.contrast}` : edits.contrast}</span>
          </div>
          <input
            type="range"
            min="-50"
            max="50"
            step="1"
            value={edits.contrast}
            onChange={(e) => handleSliderChange('contrast', parseFloat(e.target.value))}
          />
        </div>

        {/* Highlights */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Highlights</span>
            <span className="slider-val">{edits.highlights > 0 ? `+${edits.highlights}` : edits.highlights}</span>
          </div>
          <input
            type="range"
            min="-60"
            max="60"
            step="1"
            value={edits.highlights}
            onChange={(e) => handleSliderChange('highlights', parseFloat(e.target.value))}
          />
        </div>

        {/* Shadows */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Shadows</span>
            <span className="slider-val">{edits.shadows > 0 ? `+${edits.shadows}` : edits.shadows}</span>
          </div>
          <input
            type="range"
            min="-60"
            max="60"
            step="1"
            value={edits.shadows}
            onChange={(e) => handleSliderChange('shadows', parseFloat(e.target.value))}
          />
        </div>

        {/* Whites */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Whites</span>
            <span className="slider-val">{edits.whites > 0 ? `+${edits.whites}` : edits.whites}</span>
          </div>
          <input
            type="range"
            min="-40"
            max="40"
            step="1"
            value={edits.whites}
            onChange={(e) => handleSliderChange('whites', parseFloat(e.target.value))}
          />
        </div>

        {/* Blacks */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Blacks</span>
            <span className="slider-val">{edits.blacks > 0 ? `+${edits.blacks}` : edits.blacks}</span>
          </div>
          <input
            type="range"
            min="-40"
            max="40"
            step="1"
            value={edits.blacks}
            onChange={(e) => handleSliderChange('blacks', parseFloat(e.target.value))}
          />
        </div>

        {/* Vibrance */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Vibrance (Skin Safe)</span>
            <span className="slider-val">{edits.vibrance > 0 ? `+${edits.vibrance}` : edits.vibrance}</span>
          </div>
          <input
            type="range"
            min="-40"
            max="40"
            step="1"
            value={edits.vibrance}
            onChange={(e) => handleSliderChange('vibrance', parseFloat(e.target.value))}
          />
        </div>

        {/* Saturation */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Saturation</span>
            <span className="slider-val">{edits.saturation > 0 ? `+${edits.saturation}` : edits.saturation}</span>
          </div>
          <input
            type="range"
            min="-40"
            max="40"
            step="1"
            value={edits.saturation}
            onChange={(e) => handleSliderChange('saturation', parseFloat(e.target.value))}
          />
        </div>

        {/* Sharpening */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Sharpening</span>
            <span className="slider-val">{edits.sharpness}</span>
          </div>
          <input
            type="range"
            min="0"
            max="60"
            step="1"
            value={edits.sharpness}
            onChange={(e) => handleSliderChange('sharpness', parseFloat(e.target.value))}
          />
        </div>

        {/* Straighten */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Straighten</span>
            <span className="slider-val">{edits.straighten}°</span>
          </div>
          <input
            type="range"
            min="-10"
            max="10"
            step="0.2"
            value={edits.straighten}
            onChange={(e) => handleSliderChange('straighten', parseFloat(e.target.value))}
          />
        </div>

        {/* Single Re-Auto Edit Button */}
        <div style={{ marginTop: '16px' }}>
          <button
            onClick={() => onAutoEditSingle(photo.id, edits.preset_name || 'Natural Wedding')}
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'center' }}
          >
            <Sparkles size={13} style={{ color: '#3b82f6' }} />
            <span>Recalculate AI Settings</span>
          </button>
        </div>
      </div>
    </aside>
  );
};
