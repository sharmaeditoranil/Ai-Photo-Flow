import React, { useState, useEffect } from 'react';
import { api } from '../api';
import {
  Download, X, FolderOpen, FolderCheck, CheckCircle2, AlertCircle,
  ExternalLink, Sparkles, RefreshCw, HardDrive, Check
} from 'lucide-react';
import { BatchJob } from '../types';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartExport: (options: {
    output_folder: string;
    jpeg_quality: number;
    max_resolution?: number;
    rename_pattern: string;
    categories: string[];
  }) => Promise<string | void>;
  defaultFolder: string;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  onStartExport,
  defaultFolder,
}) => {
  const [outputFolder, setOutputFolder] = useState<string>('');
  const [quality, setQuality] = useState<number>(92);
  const [resolution, setResolution] = useState<'original' | '4k' | 'web' | 'social'>('original');
  const [renamePattern, setRenamePattern] = useState<string>('{original}_edited');

  // Category selections
  const [includeBest, setIncludeBest] = useState<boolean>(true);
  const [includeSelected, setIncludeSelected] = useState<boolean>(true);
  const [includeSimilar, setIncludeSimilar] = useState<boolean>(false);
  const [includeRejected, setIncludeRejected] = useState<boolean>(false);

  // Export Progress State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<BatchJob | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [exportComplete, setExportComplete] = useState<boolean>(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Initialize and keep output folder synchronized with active project
  useEffect(() => {
    if (isOpen) {
      if (defaultFolder) {
        setOutputFolder(`${defaultFolder}/AI_PhotoFlow_Export`);
      } else {
        setOutputFolder('/Users/anilsharma/Desktop/Ai_PhotoFlow_Export');
      }
      setIsExporting(false);
      setExportComplete(false);
      setActiveJobId(null);
      setActiveJob(null);
      setExportError(null);
    }
  }, [isOpen, defaultFolder]);

  // Poll export job while modal is open and job is active
  useEffect(() => {
    if (!activeJobId || !isExporting) return;

    const interval = setInterval(async () => {
      try {
        const job = await api.getJob(activeJobId);
        setActiveJob(job);
        if (job.status === 'COMPLETED') {
          setIsExporting(false);
          setExportComplete(true);
        } else if (job.status === 'FAILED' || job.status === 'CANCELLED') {
          setIsExporting(false);
          setExportError(job.error_message || 'Export failed or was cancelled');
        }
      } catch (err: any) {
        console.error('Error polling export job:', err);
      }
    }, 800);

    return () => clearInterval(interval);
  }, [activeJobId, isExporting]);

  if (!isOpen) return null;

  const handleSelectFolderNative = async () => {
    try {
      if ((window as any).electronAPI && (window as any).electronAPI.selectFolder) {
        const path = await (window as any).electronAPI.selectFolder();
        if (path) {
          setOutputFolder(path);
        }
      }
    } catch (err) {
      console.error('Error selecting folder:', err);
    }
  };

  const setQuickLocation = (loc: 'same' | 'desktop') => {
    if (loc === 'same' && defaultFolder) {
      setOutputFolder(`${defaultFolder}/AI_PhotoFlow_Export`);
    } else if (loc === 'desktop') {
      setOutputFolder('/Users/anilsharma/Desktop/Ai_PhotoFlow_Export');
    }
  };

  const handleOpenFolder = async () => {
    try {
      await api.openFolder(outputFolder);
    } catch (err: any) {
      alert(`Could not open folder: ${err.message}`);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!outputFolder.trim()) {
      alert('Please specify an export destination folder.');
      return;
    }

    const categories: string[] = [];
    if (includeBest) categories.push('BEST');
    if (includeSelected) categories.push('SELECTED');
    if (includeSimilar) categories.push('SIMILAR');
    if (includeRejected) categories.push('REJECT');

    if (categories.length === 0) {
      alert('Please check at least one category to export (e.g. Best or Selected).');
      return;
    }

    const maxRes = resolution === '4k' ? 3840 : resolution === 'web' ? 2048 : resolution === 'social' ? 1080 : undefined;

    setIsExporting(true);
    setExportComplete(false);
    setExportError(null);

    try {
      const result = await onStartExport({
        output_folder: outputFolder.trim(),
        jpeg_quality: quality,
        max_resolution: maxRes,
        rename_pattern: renamePattern.trim(),
        categories
      });

      if (typeof result === 'string') {
        setActiveJobId(result);
      }
    } catch (err: any) {
      setIsExporting(false);
      setExportError(err.message || 'Failed to start export');
    }
  };

  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }}>
      <div className="modal-content" style={{ maxWidth: '580px', background: '#12151d', border: '1px solid #232836', borderRadius: '10px', overflow: 'hidden' }}>
        
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #232836', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#161a24' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Download size={18} style={{ color: '#10b981' }} />
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
              Export Selected & Edited Photos
            </h2>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        {/* BODY: PROGRESS VIEW IF EXPORTING OR COMPLETED */}
        {isExporting || exportComplete || exportError ? (
          <div style={{ padding: '28px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            {exportComplete ? (
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'rgba(34, 197, 94, 0.15)',
                border: '2px solid #22c55e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#22c55e'
              }}>
                <Check size={32} />
              </div>
            ) : exportError ? (
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'rgba(239, 68, 68, 0.15)',
                border: '2px solid #ef4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ef4444'
              }}>
                <AlertCircle size={32} />
              </div>
            ) : (
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'rgba(59, 130, 246, 0.15)',
                border: '2px solid #3b82f6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#3b82f6'
              }}>
                <RefreshCw size={28} className="spin" />
              </div>
            )}

            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', margin: '0 0 6px 0' }}>
                {exportComplete
                  ? '🎉 Export Completed Successfully!'
                  : exportError
                  ? 'Export Error'
                  : 'Exporting High-Resolution Photos...'}
              </h3>
              <p style={{ fontSize: '12px', color: '#94a3b8', margin: 0, maxWidth: '420px', lineHeight: 1.4 }}>
                {exportComplete
                  ? `All selected photos have been rendered and saved to your computer.`
                  : exportError
                  ? exportError
                  : `Applying Indian skin tone and exposure corrections in bulk.`}
              </p>
            </div>

            {/* Progress Bar & Details */}
            {!exportError && (
              <div style={{ width: '100%', maxWidth: '440px', background: '#1a1f2b', padding: '16px', borderRadius: '8px', border: '1px solid #283042' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '8px', fontWeight: 600 }}>
                  <span>{activeJob ? `${activeJob.progress_current} of ${activeJob.progress_total} photos` : 'Processing...'}</span>
                  <span style={{ color: '#3b82f6' }}>{activeJob?.progress_pct ?? 0}%</span>
                </div>
                
                <div style={{ width: '100%', height: '8px', background: '#252c3d', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${activeJob?.progress_pct ?? 0}%`,
                    height: '100%',
                    background: exportComplete ? '#22c55e' : 'linear-gradient(90deg, #3b82f6, #60a5fa)',
                    transition: 'width 0.3s ease'
                  }} />
                </div>

                {activeJob?.current_file && (
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '8px', fontFamily: 'monospace' }}>
                    Writing: {activeJob.current_file}
                  </div>
                )}
              </div>
            )}

            {/* Destination summary */}
            <div style={{ background: '#161a24', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', color: '#94a3b8', maxWidth: '480px', wordBreak: 'break-all' }}>
              📁 Output Folder: <strong style={{ color: '#f8fafc' }}>{outputFolder}</strong>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '10px', marginTop: '10px', width: '100%', maxWidth: '360px' }}>
              <button
                type="button"
                onClick={handleOpenFolder}
                className="btn btn-primary"
                style={{ flex: 1, padding: '10px', background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              >
                <FolderOpen size={15} />
                <span>Open in Finder</span>
              </button>
              
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary"
                style={{ flex: 1, padding: '10px' }}
              >
                {exportComplete ? 'Done' : 'Run in Background'}
              </button>
            </div>
          </div>
        ) : (
          /* REGULAR SETTINGS FORM VIEW */
          <form onSubmit={handleSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            
            {/* Output Destination Folder */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                  Export Destination Folder
                </label>
                <div style={{ display: 'flex', gap: '6px' }}>
                  {defaultFolder && (
                    <button
                      type="button"
                      onClick={() => setQuickLocation('same')}
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: '10px', padding: '2px 8px' }}
                      title="Export directly into subfolder inside original photos directory"
                    >
                      Project Folder
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setQuickLocation('desktop')}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '10px', padding: '2px 8px' }}
                    title="Export directly to Desktop"
                  >
                    Desktop
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  required
                  value={outputFolder}
                  onChange={(e) => setOutputFolder(e.target.value)}
                  placeholder="/Users/username/Pictures/Export_Folder"
                  style={{
                    flex: 1,
                    background: '#161922',
                    border: '1px solid #2d3342',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    color: '#f8fafc',
                    fontSize: '12px',
                    outline: 'none'
                  }}
                />
                <button
                  type="button"
                  onClick={handleSelectFolderNative}
                  className="btn btn-secondary"
                  style={{ borderColor: '#3b82f6', color: '#60a5fa', whiteSpace: 'nowrap' }}
                  title="Browse and select export directory"
                >
                  <FolderOpen size={13} />
                  <span>Browse...</span>
                </button>
              </div>
            </div>

            {/* Categories to Include */}
            <div style={{ background: '#161922', padding: '14px', borderRadius: '8px', border: '1px solid #252b38' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>
                Photos to Include in Export:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '12px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#f8fafc' }}>
                  <input
                    type="checkbox"
                    checked={includeBest}
                    onChange={(e) => setIncludeBest(e.target.checked)}
                  />
                  <span>⭐ AI Best Photos</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#f8fafc' }}>
                  <input
                    type="checkbox"
                    checked={includeSelected}
                    onChange={(e) => setIncludeSelected(e.target.checked)}
                  />
                  <span>✓ Picked Photos</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#cbd5e1' }}>
                  <input
                    type="checkbox"
                    checked={includeSimilar}
                    onChange={(e) => setIncludeSimilar(e.target.checked)}
                  />
                  <span>👯 Similar / Alternate Burst Shots</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#94a3b8' }}>
                  <input
                    type="checkbox"
                    checked={includeRejected}
                    onChange={(e) => setIncludeRejected(e.target.checked)}
                  />
                  <span>✕ Rejected (in /Rejected folder)</span>
                </label>
              </div>
            </div>

            {/* JPEG Quality Slider */}
            <div className="slider-group" style={{ margin: 0 }}>
              <div className="slider-header" style={{ marginBottom: '6px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                  JPEG Quality
                </span>
                <span className="slider-val" style={{ color: '#10b981', fontWeight: 700 }}>
                  {quality}% (Pristine High-Res)
                </span>
              </div>
              <input
                type="range"
                min="75"
                max="100"
                step="1"
                value={quality}
                onChange={(e) => setQuality(parseInt(e.target.value))}
                style={{ width: '100%', cursor: 'pointer' }}
              />
            </div>

            {/* Resolution & Renaming Pattern */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#94a3b8', marginBottom: '6px', textTransform: 'uppercase' }}>
                  Resolution
                </label>
                <select
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value as any)}
                  style={{
                    width: '100%',
                    background: '#161922',
                    border: '1px solid #2d3342',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    color: '#f8fafc',
                    fontSize: '12px',
                    outline: 'none'
                  }}
                >
                  <option value="original">Original Resolution (Full Quality)</option>
                  <option value="4k">4K UHD (3840px Long Edge)</option>
                  <option value="web">Web High-Res (2048px)</option>
                  <option value="social">Social Media (1080px)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#94a3b8', marginBottom: '6px', textTransform: 'uppercase' }}>
                  Rename Pattern
                </label>
                <input
                  type="text"
                  value={renamePattern}
                  onChange={(e) => setRenamePattern(e.target.value)}
                  placeholder="{original}_edited"
                  style={{
                    width: '100%',
                    background: '#161922',
                    border: '1px solid #2d3342',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    color: '#f8fafc',
                    fontSize: '12px',
                    outline: 'none'
                  }}
                />
              </div>
            </div>

            <div style={{ fontSize: '11px', color: '#64748b', lineHeight: 1.4 }}>
              🛡 Original camera RAW and JPEG files will remain 100% untouched. Corrected photos are rendered and saved as crisp high-resolution JPEGs.
            </div>

            {/* Bottom Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px', borderTop: '1px solid #232836', paddingTop: '16px' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-success"
                style={{ padding: '8px 20px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Download size={14} />
                <span>Start Batch Export</span>
              </button>
            </div>
          </form>
        )}
      </div>

      <style>{`
        .spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
