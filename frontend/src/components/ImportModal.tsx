import React, { useState } from 'react';
import { FolderOpen, X, Sparkles, CheckCircle2 } from 'lucide-react';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (folderPath: string, projectName: string) => Promise<void>;
}

export const ImportModal: React.FC<ImportModalProps> = ({
  isOpen,
  onClose,
  onImport,
}) => {
  const [folderPath, setFolderPath] = useState('');
  const [projectName, setProjectName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSelectFolderNative = async () => {
    try {
      if ((window as any).electronAPI && (window as any).electronAPI.selectFolder) {
        const path = await (window as any).electronAPI.selectFolder();
        if (path) {
          setFolderPath(path);
          if (!projectName) {
            const parts = path.split(/[/\\]/).filter(Boolean);
            const folderName = parts[parts.length - 1] || 'Shoot';
            setProjectName(`Wedding – ${folderName}`);
          }
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleLoadSample = async () => {
    try {
      if ((window as any).electronAPI?.getSamplePhotosPath) {
        const sample = await (window as any).electronAPI.getSamplePhotosPath();
        if (sample) {
          setFolderPath(sample);
          setProjectName('Wedding – Rahul & Priya (Sample Dataset)');
          return;
        }
      }
    } catch (e) {
      console.error(e);
    }

    // Fallback if running outside electron or path not found
    const samplePath = (window as any).electronAPI?.platform === 'win32'
      ? 'C:\\sample_wedding_photos'
      : '/Users/anilsharma/Documents/Anil Sharma Final Website Meterial/Ai PhotoFlow /sample_wedding_photos';
    setFolderPath(samplePath);
    setProjectName('Wedding – Rahul & Priya (Sample Dataset)');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!folderPath.trim()) {
      setError('Please provide a valid folder path');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      await onImport(folderPath.trim(), projectName.trim());
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to import folder');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '520px' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #232733', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FolderOpen size={18} style={{ color: '#3b82f6' }} />
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc' }}>Import Wedding Photos</h2>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {error && (
            <div style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px' }}>
              {error}
            </div>
          )}

          {/* Quick test sample button */}
          <div style={{ background: '#161922', border: '1px solid #282f3e', borderRadius: '6px', padding: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#f1f5f9' }}>Quick Test Dataset</div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>Load the pre-generated Rahul & Priya wedding photos</div>
              </div>
              <button
                type="button"
                onClick={handleLoadSample}
                className="btn btn-secondary btn-sm"
                style={{ borderColor: '#3b82f6', color: '#60a5fa' }}
              >
                <Sparkles size={11} />
                <span>Load Sample</span>
              </button>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px', textTransform: 'uppercase' }}>
              Folder Path
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                placeholder="/Users/username/Pictures/Wedding_Shoot"
                style={{
                  flex: 1,
                  background: '#121418',
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
                title="Browse folders"
              >
                Browse...
              </button>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px', textTransform: 'uppercase' }}>
              Project Name (Optional)
            </label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="Wedding – Rahul & Priya"
              style={{
                width: '100%',
                background: '#121418',
                border: '1px solid #2d3342',
                padding: '8px 12px',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '12px',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ fontSize: '11px', color: '#64748b', lineHeight: 1.5, background: '#12141a', padding: '10px', borderRadius: '6px' }}>
            ℹ <strong>Safety Guarantee:</strong> Ai PhotoFlow never alters or overwrites your original wedding files. All AI decisions and edit values are saved non-destructively in local SQLite.
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '4px' }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={isLoading} className="btn btn-primary">
              {isLoading ? 'Scanning Photos...' : 'Scan & Open Folder'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
