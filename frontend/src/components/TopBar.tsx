import React from 'react';
import { Project, BatchJob, LicenseStatus } from '../types';
import { BrandLogo } from './BrandLogo';
import {
  FolderOpen, Sparkles, Wand2, Download, Pause, Play, X,
  FileText, Keyboard, CheckCircle2, AlertCircle, RefreshCw, Trash2, Crown, User,
  Share2
} from 'lucide-react';

interface TopBarProps {
  currentProject: Project | null;
  projects: Project[];
  license?: LicenseStatus | null;
  onOpenPricing: () => void;
  onOpenProfile?: () => void;
  onSelectProject: (id: number) => void;
  onOpenImport: () => void;
  onOpenExport: () => void;
  onOpenShareProofing?: () => void;
  onOpenBatchProgress?: () => void;
  onOpenLogs: () => void;
  onOpenShortcuts: () => void;
  onOpenSettings: () => void;
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
  onOpenProfile,
  onSelectProject,
  onOpenImport,
  onOpenExport,
  onOpenShareProofing,
  onOpenBatchProgress,
  onOpenLogs,
  onOpenShortcuts,
  onOpenSettings,
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

  const noProject = !currentProject;
  const busy = !!isJobRunning;
  const planLabel =
    license && !license.is_active
      ? ((license as any).status === 'OFFLINE' ? 'Go online to verify' : 'Activate License')
      : license?.is_vip
      ? 'VIP Lifetime'
      : license?.plan === 'PRO'
      ? 'Pro'
      : license?.plan === 'STUDIO'
      ? 'Studio'
      : (license?.days_left ?? 0) >= 1
      ? `Trial · ${license?.days_left}d left`
      : `Trial · ${(license as any)?.hours_left ?? 0}h left`;
  const planTone = license && !license.is_active
    ? 'warn'
    : license?.is_vip ? 'vip' : (license?.plan === 'PRO' || license?.plan === 'STUDIO') ? 'pro' : 'warn';

  return (
    <header className="window-drag-region tb">
      {/* Left: brand, plan, project */}
      <div className="window-no-drag tb-group tb-left">
        <div
          className="tb-brand"
          onContextMenu={(e) => {
            e.preventDefault();
            onOpenSettings();
          }}
          title="Ai PhotoFlow"
        >
          <BrandLogo size={26} />
          <span className="tb-brand-name">Ai PhotoFlow</span>
        </div>

        <button onClick={onOpenProfile || onOpenPricing} className={`tb-plan tb-plan-${planTone}`} title="My plan & profile">
          <Crown size={12} />
          <span>{planLabel}</span>
        </button>

        <div className="tb-divider" />

        {projects.length > 0 && currentProject && (
          <div className="tb-project">
            <select
              value={currentProject.id}
              onChange={(e) => onSelectProject(Number(e.target.value))}
              className="tb-select"
              title={`${currentProject.name} (${currentProject.total_photos} photos)`}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.total_photos} photos)
                </option>
              ))}
            </select>

            <span className={`tb-status tb-status-${currentProject.status === 'EDITED' ? 'edited' : currentProject.status === 'CULLED' ? 'culled' : 'ready'}`}>
              {currentProject.status === 'READY' ? <AlertCircle size={11} /> : <CheckCircle2 size={11} />}
              {currentProject.status}
            </span>

            {onDeleteProject && (
              <button
                onClick={() => onDeleteProject(currentProject.id)}
                className="tb-btn tb-icon tb-danger"
                title="Remove this project from Ai PhotoFlow (photos on disk are not deleted)"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        )}

        <button onClick={onOpenImport} className="tb-btn tb-ghost" title="Import a new wedding folder">
          <FolderOpen size={14} />
          <span className="tb-label tb-label-sec">Import Folder</span>
        </button>
      </div>

      {/* Center: real-time batch progress */}
      <div className="window-no-drag tb-center">
        {(isJobRunning || isJobPaused) && activeJob && (
          <div
            onClick={onOpenBatchProgress}
            className="tb-progress"
            style={{ cursor: onOpenBatchProgress ? 'pointer' : 'default' }}
            title="Click to view full batch progress"
          >
            <div className="tb-progress-row">
              <div className="tb-progress-text">
                <RefreshCw size={11} style={{ animation: isJobRunning ? 'spin 1.5s linear infinite' : 'none', flexShrink: 0 }} />
                <span style={{ fontWeight: 600 }}>
                  {activeJob.job_type === 'CULLING' ? 'AI Culling' :
                   activeJob.job_type === 'AUTO_EDIT' ? 'Auto Editing' : 'Exporting'}
                </span>
                <span style={{ color: '#cbd5e1' }}>
                  {activeJob.progress_current}/{activeJob.progress_total} · {activeJob.progress_pct}%
                </span>
              </div>
              <div className="tb-progress-ctrl" onClick={(e) => e.stopPropagation()}>
                {isJobRunning ? (
                  <button onClick={onPauseJob} className="tb-mini" title="Pause batch"><Pause size={10} /></button>
                ) : (
                  <button onClick={onResumeJob} className="tb-mini" title="Resume batch"><Play size={10} /></button>
                )}
                <button onClick={onCancelJob} className="tb-mini tb-mini-danger" title="Cancel batch"><X size={10} /></button>
                <button onClick={onOpenLogs} className="tb-mini" title="View processing logs"><FileText size={10} /></button>
              </div>
            </div>
            <div className="tb-bar">
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

      {/* Right: workflow actions, then account */}
      <div className="window-no-drag tb-group tb-right">
        <div className="tb-segment">
          <button
            onClick={onStartCull}
            disabled={noProject || busy}
            className="tb-btn tb-primary"
            title="AI Cull: blur, face/eye focus, exposure and burst grouping"
          >
            <Sparkles size={14} />
            <span className="tb-label">AI Cull</span>
          </button>

          <button
            onClick={onStartAutoEdit}
            disabled={noProject || busy}
            className="tb-btn tb-success"
            title="Auto Edit the selected photos (exposure, tone, skin, white balance)"
          >
            <Wand2 size={14} />
            <span className="tb-label">Auto Edit</span>
          </button>

          {onOpenShareProofing && (
            <button
              onClick={onOpenShareProofing}
              disabled={noProject}
              className="tb-btn tb-share"
              title="Create and share a secure selection link with your client (mobile & PC)"
            >
              <Share2 size={14} />
              <span className="tb-label">Client Link</span>
            </button>
          )}

          <button
            onClick={onOpenExport}
            disabled={noProject}
            className="tb-btn tb-ghost"
            title="Export final selected & edited photos to disk"
          >
            <Download size={14} />
            <span className="tb-label">Export</span>
          </button>
        </div>

        <div className="tb-divider" />

        <button onClick={onOpenShortcuts} className="tb-btn tb-icon tb-ghost" title="Keyboard shortcuts">
          <Keyboard size={15} />
        </button>

        {onOpenProfile && (
          <button onClick={onOpenProfile} className="tb-btn tb-ghost" title="My plan, profile, computers and payments">
            <User size={14} />
            <span className="tb-label tb-label-sec">My Profile</span>
          </button>
        )}

        <button onClick={onOpenPricing} className="tb-btn tb-gold" title="Pricing plans, coupons & license activation">
          <Crown size={14} />
          <span className="tb-label tb-label-sec">Pricing</span>
        </button>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .tb {
          height: 56px; flex-shrink: 0; display: flex; align-items: center; gap: 16px;
          padding: 0 16px 0 96px; background: linear-gradient(180deg, #15181f, #111318);
          border-bottom: 1px solid #222632; z-index: 50; user-select: none; overflow: hidden;
        }
        .tb-group { display: flex; align-items: center; gap: 8px; min-width: 0; }
        .tb-left { flex: 0 1 auto; }
        .tb-right { flex: 0 0 auto; }
        .tb-center { flex: 1 1 0; min-width: 0; display: flex; justify-content: center; }
        .tb-brand { display: flex; align-items: center; gap: 9px; cursor: default; flex-shrink: 0; }
        .tb-brand-name { font-size: 15px; font-weight: 700; letter-spacing: -0.3px; color: #f8fafc; white-space: nowrap; }
        .tb-divider { width: 1px; height: 22px; background: #262b38; flex-shrink: 0; margin: 0 2px; }

        .tb-plan {
          height: 24px; display: inline-flex; align-items: center; gap: 5px; padding: 0 9px;
          border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.2px;
          white-space: nowrap; cursor: pointer; flex-shrink: 0; transition: filter 0.15s ease;
        }
        .tb-plan:hover { filter: brightness(1.12); }
        .tb-plan-vip { background: rgba(16, 185, 129, 0.14); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.35); }
        .tb-plan-pro { background: rgba(59, 130, 246, 0.14); color: #93c5fd; border: 1px solid rgba(96, 165, 250, 0.35); }
        .tb-plan-warn { background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(217, 119, 6, 0.5); }

        .tb-project { display: flex; align-items: center; gap: 8px; min-width: 0; }
        .tb-select {
          height: 32px; min-width: 120px; max-width: 260px; flex: 0 1 260px; padding: 0 10px;
          background: #1b1e26; color: #e2e8f0; border: 1px solid #2d3342; border-radius: 8px;
          font-size: 12.5px; font-weight: 500; outline: none; cursor: pointer;
          text-overflow: ellipsis; white-space: nowrap; overflow: hidden;
        }
        .tb-select:hover { border-color: #3b4357; }
        .tb-status {
          height: 22px; display: inline-flex; align-items: center; gap: 4px; padding: 0 8px;
          border-radius: 999px; font-size: 10.5px; font-weight: 700; letter-spacing: 0.4px; white-space: nowrap; flex-shrink: 0;
        }
        .tb-status-culled { background: rgba(59, 130, 246, 0.14); color: #60a5fa; }
        .tb-status-edited { background: rgba(16, 185, 129, 0.14); color: #34d399; }
        .tb-status-ready { background: rgba(245, 158, 11, 0.14); color: #fbbf24; }

        .tb-segment { display: flex; align-items: center; gap: 6px; }
        .tb-btn {
          height: 32px; display: inline-flex; align-items: center; justify-content: center; gap: 7px;
          padding: 0 13px; border-radius: 8px; border: 1px solid transparent;
          font-size: 12.5px; font-weight: 600; line-height: 1; white-space: nowrap; flex-shrink: 0;
          cursor: pointer; color: #e2e8f0; transition: background 0.15s ease, border-color 0.15s ease, filter 0.15s ease, box-shadow 0.15s ease;
        }
        .tb-btn:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; filter: none; }
        .tb-icon { width: 32px; padding: 0; }
        .tb-primary { background: #3b82f6; color: #fff; box-shadow: 0 1px 6px rgba(59, 130, 246, 0.3); }
        .tb-primary:not(:disabled):hover { background: #2563eb; }
        .tb-success { background: #059669; color: #fff; box-shadow: 0 1px 6px rgba(5, 150, 105, 0.3); }
        .tb-success:not(:disabled):hover { background: #047857; }
        .tb-share { background: #0e7490; color: #fff; box-shadow: 0 1px 6px rgba(14, 116, 144, 0.3); }
        .tb-share:not(:disabled):hover { background: #0b5f76; }
        .tb-ghost { background: #1b1e26; border-color: #2d3342; color: #e2e8f0; }
        .tb-ghost:not(:disabled):hover { background: #232733; border-color: #3b4357; }
        .tb-gold { background: rgba(245, 158, 11, 0.08); border-color: rgba(217, 119, 6, 0.55); color: #fbbf24; }
        .tb-gold:not(:disabled):hover { background: rgba(245, 158, 11, 0.16); }
        .tb-danger { background: transparent; border-color: #2d3342; color: #94a3b8; }
        .tb-danger:hover { background: rgba(239, 68, 68, 0.12); border-color: rgba(239, 68, 68, 0.45); color: #f87171; }

        .tb-progress {
          width: 100%; max-width: 420px; background: #181b22; border: 1px solid #2d3342;
          padding: 5px 10px; border-radius: 8px; display: flex; flex-direction: column; gap: 4px;
        }
        .tb-progress-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 11px; }
        .tb-progress-text { display: flex; align-items: center; gap: 6px; color: #93c5fd; white-space: nowrap; overflow: hidden; min-width: 0; }
        .tb-progress-ctrl { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
        .tb-mini {
          width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center;
          border-radius: 5px; background: #232733; border: 1px solid #2d3342; color: #cbd5e1; cursor: pointer;
        }
        .tb-mini:hover { background: #2d3342; }
        .tb-mini-danger:hover { background: rgba(239, 68, 68, 0.25); color: #fca5a5; }
        .tb-bar { width: 100%; height: 4px; background: #252a36; border-radius: 2px; overflow: hidden; }

        /* Narrower windows: secondary labels first, then all labels collapse to icons (tooltips remain) */
        @media (max-width: 1480px) {
          .tb-label-sec { display: none; }
          .tb-btn:has(> .tb-label-sec) { width: 32px; padding: 0; }
        }
        @media (max-width: 1180px) {
          .tb-label { display: none; }
          .tb-btn:has(> .tb-label) { width: 34px; padding: 0; }
          .tb-brand-name { display: none; }
        }
      `}</style>
    </header>
  );
};
