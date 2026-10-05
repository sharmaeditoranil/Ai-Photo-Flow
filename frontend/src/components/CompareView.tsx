import React from 'react';
import { Photo, UserSelection } from '../types';
import { api } from '../api';
import { Check, X, Star, ArrowLeft, Trophy } from 'lucide-react';

interface CompareViewProps {
  groupPhotos: Photo[];
  onBackToGrid: () => void;
  onUpdatePhotoSelection: (photoId: number, selection: UserSelection) => void;
  onUpdatePhotoRating: (photoId: number, rating: number) => void;
}

export const CompareView: React.FC<CompareViewProps> = ({
  groupPhotos,
  onBackToGrid,
  onUpdatePhotoSelection,
  onUpdatePhotoRating,
}) => {
  const groupId = groupPhotos[0]?.duplicate_group_id || 'Burst Group';

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', background: '#0d0e12', overflow: 'hidden' }}>
      {/* Top Header */}
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button onClick={onBackToGrid} className="btn btn-secondary btn-sm" title="Back to grid view">
            <ArrowLeft size={13} />
            <span>Back to Grid</span>
          </button>
          <span style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '13px' }}>
            Burst Comparison: {groupId} ({groupPhotos.length} Similar Photos)
          </span>
        </div>

        <div style={{ fontSize: '11px', color: '#64748b' }}>
          Compare sharpness and expression. AI recommends the strongest shot.
        </div>
      </div>

      {/* Comparison Grid */}
      <div style={{
        flex: 1,
        padding: '20px',
        display: 'flex',
        gap: '16px',
        overflowX: 'auto',
        alignItems: 'stretch'
      }}>
        {groupPhotos.map((photo) => {
          const effective = photo.effective_selection;
          const isWinner = effective === 'BEST';

          return (
            <div
              key={photo.id}
              style={{
                flex: '1 0 320px',
                maxWidth: '420px',
                background: '#15171e',
                borderRadius: '8px',
                border: isWinner ? '2px solid #eab308' : '1px solid #232733',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxShadow: isWinner ? '0 0 20px rgba(234, 179, 8, 0.25)' : 'none'
              }}
            >
              {/* Header badge */}
              <div style={{
                padding: '8px 12px',
                background: isWinner ? 'rgba(234, 179, 8, 0.15)' : '#181b22',
                borderBottom: '1px solid #232733',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {isWinner ? (
                    <>
                      <Trophy size={14} style={{ color: '#eab308' }} />
                      <span style={{ fontWeight: 700, color: '#facc15', fontSize: '12px' }}>AI RECOMMENDED BEST</span>
                    </>
                  ) : (
                    <span style={{ color: '#94a3b8', fontSize: '12px' }}>Similar Burst Shot</span>
                  )}
                </div>

                <span className={`badge ${
                  effective === 'BEST' ? 'badge-best' :
                  effective === 'SELECTED' ? 'badge-selected' :
                  effective === 'REVIEW' ? 'badge-review' :
                  effective === 'REJECT' ? 'badge-reject' : 'badge-similar'
                }`}>
                  {effective}
                </span>
              </div>

              {/* Photo Image */}
              <div style={{ flex: 1, minHeight: '300px', background: '#0a0b0e', position: 'relative' }}>
                <img
                  src={api.getThumbnailUrl(photo.id)}
                  alt={photo.filename}
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>

              {/* Quality & Expression Breakdown */}
              <div style={{ padding: '12px', background: '#13151a', borderTop: '1px solid #232733', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                  <span style={{ color: '#94a3b8' }}>Overall Score:</span>
                  <span style={{ fontWeight: 700, color: photo.ai_score >= 70 ? '#34d399' : '#fbbf24' }}>
                    {Math.round(photo.ai_score)} / 100
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                  <span style={{ color: '#94a3b8' }}>Sharpness:</span>
                  <span style={{ fontWeight: 600, color: photo.blur_detected ? '#f87171' : '#cbd5e1' }}>
                    {photo.sharpness_score} {photo.blur_detected ? '(Blur)' : '(Sharp)'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                  <span style={{ color: '#94a3b8' }}>Eyes:</span>
                  <span style={{ fontWeight: 600, color: photo.eyes_status === 'OPEN' ? '#34d399' : '#fbbf24' }}>
                    {photo.eyes_status}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                  <span style={{ color: '#94a3b8' }}>Exposure:</span>
                  <span style={{ fontWeight: 600, color: photo.exposure_status === 'GOOD' ? '#34d399' : '#f87171' }}>
                    {photo.exposure_status}
                  </span>
                </div>

                {/* Selection Actions */}
                <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
                  <button
                    onClick={() => onUpdatePhotoSelection(photo.id, 'BEST')}
                    className={`btn btn-sm ${isWinner ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ flex: 1 }}
                  >
                    <Check size={12} />
                    <span>{isWinner ? 'Winner (Best)' : 'Make Winner'}</span>
                  </button>
                  <button
                    onClick={() => onUpdatePhotoSelection(photo.id, 'REJECT')}
                    className="btn btn-danger btn-sm"
                    title="Reject this duplicate"
                  >
                    <X size={12} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
