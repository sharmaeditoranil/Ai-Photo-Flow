import React from 'react';
import { ProjectCounts } from '../types';
import {
  Images, Star, CheckCircle, AlertTriangle, XCircle,
  Copy, Layers, Palette, Eye, Heart
} from 'lucide-react';

interface SidebarProps {
  currentCategory: string;
  onSelectCategory: (cat: string) => void;
  selectedStar: number | undefined;
  onSelectStar: (stars: number | undefined) => void;
  selectedScene: string;
  onSelectScene: (scene: string) => void;
  counts?: ProjectCounts;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentCategory,
  onSelectCategory,
  selectedStar,
  onSelectStar,
  selectedScene,
  onSelectScene,
  counts,
}) => {
  const categories = [
    { id: 'ALL', label: 'All Photos', icon: Images, count: counts?.total ?? 0, color: '#94a3b8' },
    { id: 'BEST', label: 'AI Best', icon: Star, count: counts?.best_count ?? 0, color: '#eab308' },
    { id: 'CLIENT_SELECTED', label: 'Customer Selected', icon: Heart, count: counts?.client_selected_count ?? 0, color: '#f43f5e' },
    { id: 'SELECTED', label: 'Selected', icon: CheckCircle, count: counts?.selected_count ?? 0, color: '#10b981' },
    { id: 'REVIEW', label: 'Review', icon: AlertTriangle, count: counts?.review_count ?? 0, color: '#f59e0b' },
    { id: 'REJECT', label: 'Rejected', icon: XCircle, count: counts?.reject_count ?? 0, color: '#ef4444' },
    { id: 'SIMILAR', label: 'Similar Groups', icon: Copy, count: (counts?.similar_groups_count && counts.similar_groups_count > 0) ? `${counts.similar_groups_count} sets` : (counts?.similar_count ?? 0), color: '#8b5cf6' },
  ];

  const scenes = [
    'ALL',
    'Bride Makeup',
    'Groom Preparation',
    'Mandap & Ceremony',
    'Stage & Couple Portraits',
    'Outdoor Portraits',
    'Reception & Sangeet'
  ];

  return (
    <aside className="sidebar">
      {/* Culling Categories */}
      <div style={{ padding: '16px 12px 10px 12px' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: '8px', paddingLeft: '6px' }}>
          Culling Categories
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {categories.map((c) => {
            const Icon = c.icon;
            const isSelected = currentCategory === c.id;
            return (
              <button
                key={c.id}
                onClick={() => onSelectCategory(c.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '7px 10px',
                  borderRadius: '6px',
                  background: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                  color: isSelected ? '#60a5fa' : '#cbd5e1',
                  border: isSelected ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: isSelected ? 600 : 500,
                  transition: 'all 0.1s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Icon size={14} style={{ color: c.color }} />
                  <span>{c.label}</span>
                </div>
                <span style={{
                  fontSize: '11px',
                  background: isSelected ? 'rgba(59, 130, 246, 0.25)' : '#1e222b',
                  color: isSelected ? '#93c5fd' : '#94a3b8',
                  padding: '1px 6px',
                  borderRadius: '10px',
                  fontVariantNumeric: 'tabular-nums'
                }}>
                  {c.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ height: '1px', background: '#1c202a', margin: '4px 12px' }} />

      {/* Star Ratings Filter */}
      <div style={{ padding: '10px 12px' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: '8px', paddingLeft: '6px' }}>
          Star Ratings
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', paddingLeft: '4px' }}>
          {[1, 2, 3, 4, 5].map((s) => {
            const isSelected = selectedStar === s;
            return (
              <button
                key={s}
                onClick={() => onSelectStar(isSelected ? undefined : s)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '2px',
                  padding: '4px 6px',
                  borderRadius: '4px',
                  background: isSelected ? '#eab308' : '#1c202a',
                  color: isSelected ? '#000' : '#cbd5e1',
                  border: '1px solid #282d3b',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontWeight: 600
                }}
              >
                <span>{s}</span>
                <Star size={10} fill={isSelected ? '#000' : '#eab308'} stroke={isSelected ? '#000' : '#eab308'} />
              </button>
            );
          })}
          {selectedStar !== undefined && (
            <button
              onClick={() => onSelectStar(undefined)}
              style={{
                fontSize: '10px',
                color: '#94a3b8',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                marginLeft: '4px',
                textDecoration: 'underline'
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div style={{ height: '1px', background: '#1c202a', margin: '4px 12px' }} />

      {/* Wedding Scenes Filter */}
      <div style={{ padding: '10px 12px', flex: 1 }}>
        <div style={{ fontSize: '10px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: '8px', paddingLeft: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Layers size={11} />
          <span>Wedding Scenes</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {scenes.map((sc) => {
            const isSelected = selectedScene === sc;
            return (
              <button
                key={sc}
                onClick={() => onSelectScene(sc)}
                style={{
                  padding: '5px 8px',
                  borderRadius: '4px',
                  background: isSelected ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                  color: isSelected ? '#34d399' : '#94a3b8',
                  border: isSelected ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid transparent',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontWeight: isSelected ? 600 : 400,
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: isSelected ? '#34d399' : '#475569' }} />
                <span>{sc === 'ALL' ? 'All Wedding Scenes' : sc}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Photoshop Integration Preparation (V1 Abstraction / V2 Placeholder) */}
      <div style={{ padding: '12px', borderTop: '1px solid #1c202a', background: '#0e1014' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Palette size={13} style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '11px', fontWeight: 600, color: '#e2e8f0' }}>Photoshop Bridge</span>
          </div>
          <span style={{ fontSize: '9px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', padding: '1px 5px', borderRadius: '3px', fontWeight: 600 }}>
            UXP V2
          </span>
        </div>

        <button
          disabled
          className="btn btn-secondary btn-sm btn-disabled"
          style={{ width: '100%', justifyContent: 'center', fontSize: '11px' }}
          title="Direct UXP plugin connection to Adobe Photoshop CC"
        >
          Send to Photoshop
        </button>
        <p style={{ fontSize: '10px', color: '#64748b', marginTop: '5px', textAlign: 'center' }}>
          Photoshop Integration – Coming in V2
        </p>
      </div>
    </aside>
  );
};
