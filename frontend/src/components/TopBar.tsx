import React from 'react';
import { Project, BatchJob, LicenseStatus } from '../types';
import { BrandLogo } from './BrandLogo';
import {
  FolderOpen, Sparkles, Wand2, Download, Pause, Play, X,
  FileText, Keyboard, CheckCircle2, AlertCircle, RefreshCw, Settings, Trash2, Crown, ShieldCheck
} from 'lucide-react';

interface TopBarProps {
  currentProject: Project | null;
  projects: Project[];
  license?: LicenseStatus | null;
  onOpenPricing: () => void;
  onSelectProject: (id: number) => void;
  onOpenImport: () => void;
  onOpenExport: () => void;
  onOpenLogs: () => void;
  onOpenShortcuts: () => void;
  onOpenSettings: () => void;
  onOpenAdminHub?: () => void;
  onStartCull: () => void;
  onStartAutoEdit: () => void;
  onDeleteProject?: (projectId: number) => void;
  activeJob: BatchJob | null;
  onPauseJob: () => void;
  onResumeJob: () => void;
  onCancelJob: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentProject,
  projects,
  license,
  onOpenPricing,
  onSelectProject,
  onOpenImport,
  onOpenExport,
  onOpenLogs,
  onOpenShortcuts,
  onOpenSettings,
  onOpenAdminHub,
  onStartCull,
  onStartAutoEdit,
  onDeleteProject,
  activeJob,
  onPauseJob,
  onResumeJob,
  onCancelJob,
}) => {
  const isJobRunning = activeJob && activeJob.status === 'RUNNING';
  const isJobPaused = activeJob && activeJob.status === 'PAUSED';

  return (
    <header
      className="window-drag-region"
      style={{
        height: '52px',
        background: '#13151a',
        borderBottom: '1px solid #232733',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px 0 100px',
        zIndex: 50,
        userSelect: 'none'
      }}
    >
      {/* Brand & Project Selector */}
      <div className="window-no-drag" style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'default' }}
          onContextMenu={(e) => {
            e.preventDefault();
            onOpenSettings();
          }}
          title="Ai PhotoFlow"
        >
          <BrandLogo size={28} />
          <span style={{ fontSize: '15px', fontWeight: 700, letterSpacing: '-0.3px', color: '#f8fafc' }}>
            Ai PhotoFlow
          </span>

          {/* License Status Badge */}
          <button
            onClick={onOpenPricing}
            style={{
              background: license?.is_vip
                ? 'linear-gradient(90deg, #059669, #10b981)'
                : license?.plan === 'PRO' || license?.plan === 'STUDIO'
                ? 'linear-gradient(90deg, #2563eb, #3b82f6)'
                : '#1e293b',
              border: license?.is_vip || license?.plan === 'PRO' ? 'none' : '1px solid #d97706',
              color: license?.is_vip || license?.plan === 'PRO' ? '#fff' : '#fbbf24',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'opacity 0.2s'
            }}
            title="Click to view plans or activate license key"
          >
            <Crown size={12} />
            <span>
              {license?.is_vip
                ? 'VIP LIFETIME'
                : license?.plan === 'PRO'
                ? 'PRO ACTIVE'
                : license?.plan === 'STUDIO'
                ? 'STUDIO'
                : `Trial (${license?.days_left ?? 14}d)`}
            </span>
          </button>
        </div>

        <div style={{ height: '20px', width: '1px', background: '#252a36' }} />

        {/* Project Switcher */}
        {projects.length > 0 && currentProject && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <select
              value={currentProject.id}
              onChange={(e) => onSelectProject(Number(e.target.value))}
              style={{
                background: '#1c1f26',
                color: '#e2e8f0',
                border: '1px solid #2d3342',
                padding: '4px 8px',
                borderRadius: '6px',
                fontSize: '12px',
                outline: 'none',
                cursor: 'pointer',
                fontWeight: 500,
                maxWidth: '220px'
              }}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.total_photos} photos)
                </option>
              ))}
            </select>

            <span style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '12px',
              background: currentProject.status === 'EDITED' ? 'rgba(16, 185, 129, 0.15)' :
                          currentProject.status === 'CULLED' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              color: currentProject.status === 'EDITED' ? '#34d399' :
                     currentProject.status === 'CULLED' ? '#60a5fa' : '#fbbf24',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              {currentProject.status === 'EDITED' && <CheckCircle2 size={11} />}
              {currentProject.status === 'CULLED' && <CheckCircle2 size={11} />}
              {currentProject.status === 'READY' && <AlertCircle size={11} />}
              {currentProject.status}
            </span>

            {onDeleteProject && (
              <button
                onClick={() => onDeleteProject(currentProject.id)}
                style={{
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  color: '#f87171',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 500
                }}
                title="Remove this project from Ai PhotoFlow"
              >
                <Trash2 size={12} />
                <span>Remove Project</span>
              </button>
            )}
          </div>
        )}

        <button
          onClick={onOpenImport}
          className="btn btn-secondary btn-sm"
          title="Import a new wedding folder"
        >
          <FolderOpen size={13} />
          <span>Import Folder</span>
        </button>
      </div>

      {/* Center: Real-time Batch Progress Monitor */}
      <div className="window-no-drag" style={{ flex: 1, maxWidth: '420px', margin: '0 20px' }}>
        {(isJobRunning || isJobPaused) && (
          <div style={{
            background: '#181b22',
            border: '1px solid #2d3342',
            padding: '5px 10px',
            borderRadius: '6px',
            display: 'flex',
            flexDirection: 'column',
            gap: '3px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#93c5fd' }}>
                <RefreshCw size={11} className={isJobRunning ? "spin" : ""} style={{ animation: isJobRunning ? 'spin 1.5s linear infinite' : 'none' }} />
                <span style={{ fontWeight: 600 }}>
                  {activeJob.job_type === 'CULLING' ? 'AI Culling:' :
                   activeJob.job_type === 'AUTO_EDIT' ? 'Auto Editing:' : 'Exporting:'}
                </span>
                <span style={{ color: '#cbd5e1' }}>
                  {activeJob.progress_current} / {activeJob.progress_total} ({activeJob.progress_pct}%)
                </span>
              </div>

              {/* Pause / Resume / Cancel Controls */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                {isJobRunning ? (
                  <button onClick={onPauseJob} className="btn btn-secondary btn-sm" style={{ padding: '2px 5px' }} title="Pause batch">
                    <Pause size={10} />
                  </button>
                ) : (
                  <button onClick={onResumeJob} className="btn btn-secondary btn-sm" style={{ padding: '2px 5px' }} title="Resume batch">
                    <Play size={10} />
                  </button>
                )}
                <button onClick={onCancelJob} className="btn btn-danger btn-sm" style={{ padding: '2px 5px' }} title="Cancel batch">
                  <X size={10} />
                </button>
                <button onClick={onOpenLogs} className="btn btn-secondary btn-sm" style={{ padding: '2px 5px' }} title="View processing logs">
                  <FileText size={10} />
                </button>
              </div>
            </div>

            {/* Progress bar line */}
            <div style={{ width: '100%', height: '4px', background: '#252a36', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${activeJob.progress_pct}%`,
                  background: isJobPaused ? '#f59e0b' : 'linear-gradient(90deg, #3b82f6, #60a5fa)',
                  transition: 'width 0.2s ease'
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Right Actions */}
      <div className="window-no-drag" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          onClick={onStartCull}
          disabled={!currentProject || !!isJobRunning}
          className={`btn btn-primary ${(!currentProject || !!isJobRunning) ? 'btn-disabled' : ''}`}
          title="Run AI scan, blur detection, face/eye detection, and burst clustering"
        >
          <Sparkles size={13} />
          <span>AI Cull Photos</span>
        </button>

        <button
          onClick={onStartAutoEdit}
          disabled={!currentProject || !!isJobRunning}
          className={`btn btn-success ${(!currentProject || !!isJobRunning) ? 'btn-disabled' : ''}`}
          title="Apply individual tone, exposure, and Indian skin tone corrections in bulk"
        >
          <Wand2 size={13} />
          <span>Auto Edit Selected</span>
        </button>

        <button
          onClick={onOpenExport}
          disabled={!currentProject}
          className={`btn btn-secondary ${!currentProject ? 'btn-disabled' : ''}`}
          title="Export final selected & edited photos to disk"
        >
          <Download size={13} />
          <span>Export Final</span>
        </button>

        <div style={{ height: '20px', width: '1px', background: '#252a36' }} />

        <button
          onClick={onOpenShortcuts}
          className="btn btn-secondary btn-sm"
          title="Keyboard shortcuts (1-5 ratings, P pick, X reject, etc.)"
        >
          <Keyboard size={13} />
        </button>

        <button
          onClick={onOpenPricing}
          className="btn btn-secondary btn-sm"
          style={{ border: '1px solid #d97706', color: '#fbbf24' }}
          title="Pricing Plans, Coupons & License Activation"
        >
          <Crown size={13} />
          <span style={{ fontSize: '11px', fontWeight: 700 }}>Pricing</span>
        </button>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </header>
  );
};
