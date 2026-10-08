import React from 'react';
import { Photo, UserSelection } from '../types';
import { api } from '../api';
import {
  Star, Check, X, Eye, Copy, Sliders, CheckSquare, Square,
  Layers, AlertTriangle, ArrowUpDown, Maximize2, Image as ImageIcon, Trash2, Wand2, Sparkles, Trophy
} from 'lucide-react';

interface PhotoGridProps {
  photos: Photo[];
  selectedPhoto: Photo | null;
  onSelectPhoto: (photo: Photo) => void;
  selectedPhotoIds: number[];
  onToggleSelectPhotoId: (id: number, multi: boolean) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onUpdatePhotoSelection: (photoId: number, selection: UserSelection) => void;
  onUpdatePhotoRating: (photoId: number, rating: number) => void;
  onOpenCompare: (groupPhotos: Photo[]) => void;
  onOpenLightbox: (index: number) => void;
  onDeletePhotos?: (photoIds: number[]) => void;
  onAutoEditSelected?: () => void;
  previewTimestamp?: number;
  thumbnailSize: 'small' | 'medium' | 'large';
  onChangeThumbnailSize: (size: 'small' | 'medium' | 'large') => void;
  sortBy: string;
  onChangeSortBy: (sort: string) => void;
  currentCategory?: string;
  projectId?: number;
}

export const PhotoGrid: React.FC<PhotoGridProps> = ({
  photos,
  selectedPhoto,
  onSelectPhoto,
  selectedPhotoIds,
  onToggleSelectPhotoId,
  onSelectAll,
  onClearSelection,
  onUpdatePhotoSelection,
  onUpdatePhotoRating,
  onOpenCompare,
  onOpenLightbox,
  onDeletePhotos,
  onAutoEditSelected,
  previewTimestamp,
  thumbnailSize,
  onChangeThumbnailSize,
  sortBy,
  onChangeSortBy,
  currentCategory,
  projectId,
}) => {
  const cardWidth = thumbnailSize === 'small' ? '200px' : thumbnailSize === 'large' ? '360px' : '260px';
  const cardHeight = thumbnailSize === 'small' ? '150px' : thumbnailSize === 'large' ? '260px' : '190px';

  // Group photos by duplicate group for easy compare navigation
  const duplicateGroups: { [key: string]: Photo[] } = {};
  photos.forEach((p) => {
    if (p.duplicate_group_id) {
      duplicateGroups[p.duplicate_group_id] = duplicateGroups[p.duplicate_group_id] || [];
      duplicateGroups[p.duplicate_group_id].push(p);
    }
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Grid Toolbar */}
      <div style={{
        height: '42px',
        padding: '0 16px',
        background: '#13151a',
        borderBottom: '1px solid #232733',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '12px',
        color: '#94a3b8'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontWeight: 600 }}>{photos.length} photos</span>

          <button
            onClick={onSelectAll}
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '11px', padding: '2px 8px', color: '#93c5fd', borderColor: '#2563eb' }}
            title="Select all photos in this view (⌘A)"
          >
            Select All (⌘A)
          </button>

          {selectedPhotoIds.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#1c202a', padding: '2px 8px', borderRadius: '4px', border: '1px solid #2d3342' }}>
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>{selectedPhotoIds.length} checked</span>
              <button onClick={onClearSelection} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '11px', textDecoration: 'underline' }}>
                Clear
              </button>
              {onDeletePhotos && (
                <button
                  onClick={() => onDeletePhotos(selectedPhotoIds)}
                  style={{
                    background: '#dc2626',
                    border: 'none',
                    color: '#fff',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    cursor: 'pointer',
                    fontSize: '11px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    marginLeft: '4px'
                  }}
                  title="Remove selected photos from project"
                >
                  <Trash2 size={11} />
                  <span>Remove ({selectedPhotoIds.length})</span>
                </button>
              )}
              {onAutoEditSelected && (
                <button
                  onClick={onAutoEditSelected}
                  style={{
                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    border: 'none',
                    color: '#fff',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    cursor: 'pointer',
                    fontSize: '11px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    marginLeft: '4px',
                    boxShadow: '0 1px 3px rgba(16, 185, 129, 0.3)'
                  }}
                  title="Auto edit selected photos with advanced tone & skin protection"
                >
                  <Wand2 size={11} />
                  <span>Auto Edit ({selectedPhotoIds.length})</span>
                </button>
              )}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Sort Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ArrowUpDown size={12} />
            <select
              value={sortBy}
              onChange={(e) => onChangeSortBy(e.target.value)}
              style={{
                background: '#1c1f26',
                color: '#cbd5e1',
                border: '1px solid #2d3342',
                padding: '3px 6px',
                borderRadius: '4px',
                fontSize: '11px',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value="ai_score_desc">AI Score (High to Low)</option>
              <option value="filename_asc">Filename (A-Z)</option>
              <option value="rating_desc">Star Rating</option>
            </select>
          </div>

          {/* Thumbnail Size Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '2px', background: '#1c1f26', padding: '2px', borderRadius: '4px', border: '1px solid #282d3b' }}>
            {(['small', 'medium', 'large'] as const).map((sz) => (
              <button
                key={sz}
                onClick={() => onChangeThumbnailSize(sz)}
                style={{
                  padding: '2px 8px',
                  borderRadius: '3px',
                  background: thumbnailSize === sz ? '#3b82f6' : 'transparent',
                  color: thumbnailSize === sz ? '#fff' : '#94a3b8',
                  border: 'none',
                  fontSize: '10px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'uppercase'
                }}
              >
                {sz[0]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grid Container with ALWAYS ACTIVE SCROLLBAR */}
      <div
        className="photo-grid-scroll-area"
        style={{
          padding: '16px',
          display: 'grid',
          gridTemplateColumns: `repeat(auto-fill, minmax(${cardWidth}, 1fr))`,
          gap: '16px',
          alignContent: 'start',
          boxSizing: 'border-box'
        }}
      >
        {photos.map((photo, idx) => {
          const isSelected = selectedPhoto?.id === photo.id;
          const isChecked = selectedPhotoIds.includes(photo.id);
          const effective = photo.effective_selection;
          const isWinner = photo.is_group_best || effective === 'BEST';
          const isNewGroup = currentCategory === 'SIMILAR' && (idx === 0 || photo.duplicate_group_id !== photos[idx - 1]?.duplicate_group_id);

          return (
            <React.Fragment key={photo.id}>
              {/* Group Header for Similar view */}
              {isNewGroup && (
                <div
                  style={{
                    gridColumn: '1 / -1',
                    background: 'linear-gradient(90deg, rgba(30, 27, 58, 0.95) 0%, rgba(18, 20, 29, 0.98) 100%)',
                    border: '1px solid #3b3564',
                    borderRadius: '8px',
                    padding: '10px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginTop: idx > 0 ? '16px' : '0',
                    marginBottom: '4px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                    <span style={{
                      background: '#8b5cf6',
                      color: '#fff',
                      padding: '3px 10px',
                      borderRadius: '5px',
                      fontSize: '11px',
                      fontWeight: 700,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px'
                    }}>
                      <Copy size={12} /> {photo.duplicate_group_id || 'Similar Group'}
                    </span>
                    <span style={{ color: '#f1f5f9', fontSize: '13px', fontWeight: 600 }}>
                      {photo.duplicate_group_count || 1} Photos of this Pose / Shot
                    </span>
                    <span style={{ color: '#475569' }}>•</span>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                      <Trophy size={14} style={{ color: '#facc15' }} />
                      <span style={{ color: '#94a3b8' }}>Selected as Best:</span>
                      <span style={{ color: '#facc15', fontWeight: 700, background: 'rgba(234, 179, 8, 0.15)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
                        ★ {photo.duplicate_group_best_filename || photo.filename}
                      </span>
                      {photo.duplicate_group_best_score && (
                        <span style={{ color: '#34d399', fontSize: '11px', fontWeight: 600 }}>
                          (Score: {Math.round(photo.duplicate_group_best_score)}/100)
                        </span>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={async () => {
                      if (projectId && photo.duplicate_group_id) {
                        try {
                          const grp = await api.getDuplicateGroupPhotos(projectId, photo.duplicate_group_id);
                          if (grp.length > 0) {
                            onOpenCompare(grp);
                            return;
                          }
                        } catch (_) {}
                      }
                      if (photo.duplicate_group_id && duplicateGroups[photo.duplicate_group_id]) {
                        onOpenCompare(duplicateGroups[photo.duplicate_group_id]);
                      }
                    }}
                    className="btn btn-secondary btn-sm"
                    style={{
                      fontSize: '11px',
                      padding: '4px 12px',
                      borderColor: '#6366f1',
                      color: '#c7d2fe',
                      background: 'rgba(99, 102, 241, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      cursor: 'pointer'
                    }}
                    title="Compare all photos in this group side-by-side"
                  >
                    <Layers size={13} />
                    <span>Compare All ({photo.duplicate_group_count || 1})</span>
                  </button>
                </div>
              )}

              <div
                onClick={() => onSelectPhoto(photo)}
                onDoubleClick={() => onOpenLightbox(idx)}
                style={{
                  background: '#15171e',
                  borderRadius: '8px',
                  border: isSelected ? '2px solid #3b82f6' : isChecked ? '2px solid #38bdf8' : isWinner ? '2px solid #eab308' : '1px solid #232733',
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  cursor: 'pointer',
                  position: 'relative',
                  transition: 'all 0.15s ease',
                  boxShadow: isSelected ? '0 0 12px rgba(59, 130, 246, 0.4)' : isWinner ? '0 0 12px rgba(234, 179, 8, 0.25)' : '0 2px 6px rgba(0,0,0,0.3)',
                  width: '100%',
                  minWidth: cardWidth,
                  minHeight: `${parseInt(cardHeight) + 65}px`,
                  flexShrink: 0
                }}
              >
                {/* Thumbnail Area with locked height so it NEVER shrinks */}
                <div
                  onClick={() => onOpenLightbox(idx)}
                  style={{
                    position: 'relative',
                    width: '100%',
                    height: cardHeight,
                    minHeight: cardHeight,
                    maxHeight: cardHeight,
                    flexShrink: 0,
                    flexGrow: 0,
                    background: '#0a0b0e',
                    overflow: 'hidden',
                    cursor: 'zoom-in'
                  }}
                >
                  <img
                    src={api.getThumbnailUrl(photo.id, photo.is_edited ? (previewTimestamp || 1) : undefined)}
                    alt={photo.filename}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      display: 'block',
                      transition: 'transform 0.2s ease'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.04)')}
                    onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                  />

                  {/* Top Badges Overlay */}
                  <div style={{ position: 'absolute', top: '6px', left: '6px', display: 'flex', gap: '5px', zIndex: 10, flexWrap: 'wrap', maxWidth: 'calc(100% - 60px)' }}>
                    {/* AI Recommendation Badge */}
                    <span className={`badge ${
                      effective === 'BEST' ? 'badge-best' :
                      effective === 'SELECTED' ? 'badge-selected' :
                      effective === 'REVIEW' ? 'badge-review' :
                      effective === 'REJECT' ? 'badge-reject' : 'badge-similar'
                    }`}>
                      {effective === 'BEST' && '⭐ Best'}
                      {effective === 'SELECTED' && '✓ Pick'}
                      {effective === 'REVIEW' && '⚠ Review'}
                      {effective === 'REJECT' && '✕ Reject'}
                      {effective === 'SIMILAR' && '👯 Similar'}
                    </span>

                    {/* Duplicate Group tag with count - visible ONLY in SIMILAR view */}
                    {photo.duplicate_group_id && currentCategory === 'SIMILAR' && (
                      <span
                        onClick={async (e) => {
                          e.stopPropagation();
                          if (projectId) {
                            try {
                              const fullGrp = await api.getDuplicateGroupPhotos(projectId, photo.duplicate_group_id!);
                              if (fullGrp.length > 0) {
                                onOpenCompare(fullGrp);
                                return;
                              }
                            } catch (_) {}
                          }
                          if (duplicateGroups[photo.duplicate_group_id!]) {
                            onOpenCompare(duplicateGroups[photo.duplicate_group_id!]);
                          }
                        }}
                        className="badge badge-similar"
                        style={{
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          background: 'rgba(15, 23, 42, 0.94)',
                          color: '#f8fafc',
                          border: '1px solid rgba(148, 163, 184, 0.5)',
                          padding: '3px 8px',
                          borderRadius: '5px'
                        }}
                        title={`Burst sequence with ${photo.duplicate_group_count || 1} photos. Click to compare side-by-side.`}
                      >
                        <Copy size={11} style={{ color: '#93c5fd' }} />
                        <span style={{ color: '#93c5fd', fontWeight: 700 }}>{photo.duplicate_group_id}</span>
                        <span style={{ color: '#cbd5e1', fontSize: '10px' }}>({photo.duplicate_group_count || 1} in set)</span>
                      </span>
                    )}

                    {/* Show Winner badge only if in SIMILAR category */}
                    {photo.is_group_best && (photo.duplicate_group_count ?? 1) > 1 && effective !== 'BEST' && currentCategory === 'SIMILAR' && (
                      <span
                        className="badge"
                        style={{
                          background: 'rgba(26, 20, 5, 0.92)',
                          color: '#facc15',
                          border: '1px solid rgba(250, 204, 21, 0.6)',
                          fontSize: '10px',
                          padding: '2px 6px',
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          borderRadius: '4px'
                        }}
                        title="Selected as the winning best photo for this group"
                      >
                        <Trophy size={10} />
                        Group Best
                      </span>
                    )}

                    {!photo.is_group_best && photo.duplicate_group_best_filename && currentCategory === 'SIMILAR' && (
                      <span
                        className="badge"
                        style={{
                          background: 'rgba(15, 23, 42, 0.92)',
                          color: '#94a3b8',
                          border: '1px solid rgba(71, 85, 105, 0.6)',
                          fontSize: '9px',
                          padding: '1px 5px',
                          fontWeight: 500,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          borderRadius: '3px'
                        }}
                        title={`AI chose ${photo.duplicate_group_best_filename} as Best`}
                      >
                        <Trophy size={9} style={{ color: '#eab308' }} />
                        Best: {photo.duplicate_group_best_filename}
                      </span>
                    )}

                    {/* AI Edited Badge */}
                    {photo.is_edited === 1 && (
                      <span
                        className="badge"
                        style={{
                          background: 'rgba(16, 185, 129, 0.85)',
                          color: '#ffffff',
                          fontSize: '9px',
                          padding: '1px 5px',
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          borderRadius: '3px',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.4)'
                        }}
                        title="AI Pro Enhanced & Edited"
                      >
                        <Sparkles size={9} />
                        EDITED
                      </span>
                    )}

                    {/* Client Proofing Badges */}
                    {photo.client_selection === 'SELECTED' && (
                      <span
                        className="badge"
                        style={{
                          background: 'linear-gradient(135deg, #e11d48, #f43f5e)',
                          color: '#ffffff',
                          fontSize: '10px',
                          padding: '2px 7px',
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          borderRadius: '4px',
                          boxShadow: '0 2px 6px rgba(225, 29, 72, 0.45)'
                        }}
                        title="Selected by client in proofing gallery"
                      >
                        ❤️ Client Pick
                      </span>
                    )}

                    {photo.client_selection === 'REJECTED' && (
                      <span
                        className="badge"
                        style={{
                          background: 'rgba(71, 85, 105, 0.85)',
                          color: '#cbd5e1',
                          fontSize: '9px',
                          padding: '1px 5px',
                          fontWeight: 500,
                          borderRadius: '3px'
                        }}
                        title="Marked as rejected by client"
                      >
                        ✕ Client Reject
                      </span>
                    )}

                    {photo.client_note && (
                      <span
                        className="badge"
                        style={{
                          background: 'rgba(14, 165, 233, 0.85)',
                          color: '#ffffff',
                          fontSize: '9px',
                          padding: '1px 5px',
                          fontWeight: 500,
                          borderRadius: '3px'
                        }}
                        title={`Client note: "${photo.client_note}"`}
                      >
                        💬 Note
                      </span>
                    )}
                  </div>

                {/* Top Right Controls: Fullscreen expand & Multi-select Checkbox */}
                <div style={{ position: 'absolute', top: '6px', right: '6px', display: 'flex', gap: '4px', zIndex: 10 }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenLightbox(idx);
                    }}
                    style={{
                      background: 'rgba(0,0,0,0.65)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      borderRadius: '4px',
                      padding: '3px 5px',
                      color: '#f8fafc',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Open Fullscreen Lightbox"
                  >
                    <Maximize2 size={12} />
                  </button>

                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleSelectPhotoId(photo.id, e.shiftKey || e.metaKey || e.ctrlKey);
                    }}
                    style={{
                      background: 'rgba(0,0,0,0.65)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      borderRadius: '4px',
                      padding: '2px 4px',
                      color: isChecked ? '#38bdf8' : '#cbd5e1',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    {isChecked ? <CheckSquare size={13} /> : <Square size={13} />}
                  </div>
                </div>

                {/* Bottom Overlay: AI Score & Quick Action Buttons */}
                <div style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  padding: '6px 8px',
                  background: 'linear-gradient(transparent, rgba(10, 11, 14, 0.9) 70%)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-end',
                  zIndex: 10
                }}>
                  {/* AI Score */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      color: photo.ai_score >= 70 ? '#34d399' : photo.ai_score >= 50 ? '#fbbf24' : '#f87171'
                    }}>
                      Score {Math.round(photo.ai_score)}
                    </span>
                    {photo.blur_detected === 1 && (
                      <span style={{ fontSize: '9px', background: 'rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '1px 3px', borderRadius: '2px' }}>
                        Blur
                      </span>
                    )}
                  </div>

                  {/* Quick Best / Pick / Reject buttons */}
                  <div style={{ display: 'flex', gap: '3px' }} onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => onUpdatePhotoSelection(photo.id, 'BEST')}
                      style={{
                        background: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '#f59e0b' : 'rgba(30, 41, 59, 0.8)',
                        color: (photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '#fff' : '#cbd5e1',
                        border: 'none',
                        borderRadius: '3px',
                        padding: '3px 5px',
                        cursor: 'pointer'
                      }}
                      title="Promote to Best (B)"
                    >
                      <Star size={11} fill={(photo.user_selection === 'BEST' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'BEST')) ? '#fff' : 'none'} />
                    </button>
                    <button
                      onClick={() => onUpdatePhotoSelection(photo.id, 'SELECTED')}
                      style={{
                        background: (photo.user_selection === 'SELECTED' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'SELECTED')) ? '#10b981' : 'rgba(30, 41, 59, 0.8)',
                        color: (photo.user_selection === 'SELECTED' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'SELECTED')) ? '#fff' : '#cbd5e1',
                        border: 'none',
                        borderRadius: '3px',
                        padding: '3px 5px',
                        cursor: 'pointer'
                      }}
                      title="Pick / Select photo (P)"
                    >
                      <Check size={11} />
                    </button>
                    <button
                      onClick={() => onUpdatePhotoSelection(photo.id, 'REJECT')}
                      style={{
                        background: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT')) ? '#ef4444' : 'rgba(30, 41, 59, 0.8)',
                        color: (photo.user_selection === 'REJECT' || (photo.user_selection === 'UNRATED' && photo.ai_recommendation === 'REJECT')) ? '#fff' : '#cbd5e1',
                        border: 'none',
                        borderRadius: '3px',
                        padding: '3px 5px',
                        cursor: 'pointer'
                      }}
                      title="Reject photo (X)"
                    >
                      <X size={11} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Meta Card Bottom */}
              <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', fontWeight: 500, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '75%' }}>
                    {photo.filename}
                  </span>
                  <span style={{ fontSize: '10px', color: '#64748b' }}>{photo.file_format}</span>
                </div>

                {/* Stars and Scene */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
                  {/* Star rating buttons */}
                  <div style={{ display: 'flex', gap: '2px' }} onClick={(e) => e.stopPropagation()}>
                    {[1, 2, 3, 4, 5].map((s) => (
                      <Star
                        key={s}
                        size={11}
                        onClick={() => onUpdatePhotoRating(photo.id, photo.star_rating === s ? 0 : s)}
                        fill={photo.star_rating >= s ? '#eab308' : 'none'}
                        stroke={photo.star_rating >= s ? '#eab308' : '#475569'}
                        style={{ cursor: 'pointer' }}
                      />
                    ))}
                  </div>

                  <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                    {photo.scene_category ? photo.scene_category.split(' ')[0] : ''}
                  </span>
                </div>
              </div>
            </div>
          </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
