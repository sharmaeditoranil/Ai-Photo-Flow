import React, { useState, useEffect } from 'react';
import {
  Share2, X, Copy, Check, ExternalLink, ShieldCheck, Lock,
  Smartphone, RefreshCw, Send, Globe, Wifi, Radio, Server,
  FolderOpen, HardDrive, Sparkles, Settings
} from 'lucide-react';
import { api, BACKEND_ORIGIN, BACKEND_PORT } from '../api';
import { Project, Photo, ClientGallery, BatchJob } from '../types';

interface ShareProofingModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project | null;
  photos: Photo[];
  onRefreshProject?: () => void;
}

export const ShareProofingModal: React.FC<ShareProofingModalProps> = ({
  isOpen,
  onClose,
  project,
  photos,
  onRefreshProject
}) => {
  const [title, setTitle] = useState('');
  const [clientName, setClientName] = useState('');
  const [clientPin, setClientPin] = useState('');
  const [watermarkEnabled, setWatermarkEnabled] = useState(true);
  const [watermarkText, setWatermarkText] = useState('PROOF ONLY - Ai PhotoFlow');
  const [selectionScope, setSelectionScope] = useState<'best' | 'edited' | 'all'>('best');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeGallery, setActiveGallery] = useState<any | null>(null);
  const [activeJob, setActiveJob] = useState<BatchJob | null>(null);
  const [copied, setCopied] = useState(false);
  const [pinCopied, setPinCopied] = useState(false);
  const [autoUnlockLink, setAutoUnlockLink] = useState(true);
  const [existingGalleries, setExistingGalleries] = useState<ClientGallery[]>([]);

  // Mobile & Tunnel state
  const [linkMode, setLinkMode] = useState<'online' | 'domain' | 'wifi' | 'local'>('online');
  const [tunnelUrl, setTunnelUrl] = useState<string | null>(null);
  const [localIp, setLocalIp] = useState<string>('127.0.0.1');
  const [isTunnelLoading, setIsTunnelLoading] = useState(false);
  const [tunnelError, setTunnelError] = useState<string | null>(null);

  // Custom Domain & Hosting State
  const [customDomainUrl, setCustomDomainUrl] = useState<string>('');
  const [cfToken, setCfToken] = useState<string>('');
  const [isSavingDomain, setIsSavingDomain] = useState<boolean>(false);
  const [domainSaveMessage, setDomainSaveMessage] = useState<string | null>(null);
  const [showAdminDomainSetup, setShowAdminDomainSetup] = useState<boolean>(false);

  const [standaloneExportFolder, setStandaloneExportFolder] = useState<string>('/Users/anilsharma/Desktop/Client_Proofing_Web');
  const [isExportingStandalone, setIsExportingStandalone] = useState<boolean>(false);
  const [standaloneExportSuccess, setStandaloneExportSuccess] = useState<string | null>(null);
  const [standaloneExportError, setStandaloneExportError] = useState<string | null>(null);

  useEffect(() => {
    if (project && isOpen) {
      setTitle(project.name || 'Wedding Photo Selection');
      setClientName(project.name.replace(/^Wedding\s*[-–]\s*/i, ''));
      loadExistingGalleries();
      loadNetworkInfo();
    }
  }, [project, isOpen]);

  const loadNetworkInfo = async () => {
    try {
      const info = await api.getNetworkInfo();
      if (info.local_ip) setLocalIp(info.local_ip);
      if ((info as any).custom_domain_url) {
        setCustomDomainUrl((info as any).custom_domain_url);
        if ((info as any).custom_domain_url.trim()) {
          setLinkMode('domain');
        }
      }
      if (info.url) {
        setTunnelUrl(info.url);
      } else {
        handleStartTunnel();
      }
    } catch (e) {
      console.error('Error fetching network info:', e);
    }
  };

  const handleStartTunnel = async () => {
    setIsTunnelLoading(true);
    setTunnelError(null);
    try {
      const res = await api.startPublicTunnel();
      if (res.success && res.url) {
        setTunnelUrl(res.url);
      } else {
        setTunnelError(res.error || 'Failed to start online link');
        if (linkMode === 'online') setLinkMode('wifi');
      }
    } catch (e: any) {
      setTunnelError(e.message || 'Online link unavailable');
      if (linkMode === 'online') setLinkMode('wifi');
    } finally {
      setIsTunnelLoading(false);
    }
  };

  const handleSaveDomainSettings = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsSavingDomain(true);
    setDomainSaveMessage(null);
    try {
      await api.saveSettings({
        custom_domain_url: customDomainUrl.trim(),
        cloudflare_tunnel_token: cfToken.trim()
      });
      setDomainSaveMessage('✅ Custom Domain saved! Links updated.');
      await handleStartTunnel();
      setTimeout(() => setDomainSaveMessage(null), 4000);
    } catch (err: any) {
      setDomainSaveMessage(`❌ Error: ${err.message}`);
    } finally {
      setIsSavingDomain(false);
    }
  };

  const handleSelectStandaloneFolder = async () => {
    try {
      if ((window as any).electronAPI && (window as any).electronAPI.selectFolder) {
        const path = await (window as any).electronAPI.selectFolder();
        if (path) setStandaloneExportFolder(path);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleExportStandalone = async () => {
    if (!activeGallery) return;
    setIsExportingStandalone(true);
    setStandaloneExportSuccess(null);
    setStandaloneExportError(null);
    try {
      const res = await api.exportStandaloneGallery(activeGallery.gallery_uuid, standaloneExportFolder);
      setStandaloneExportSuccess(`✅ Exported ${res.total_photos} photos to ${res.destination_folder}! You can now upload this folder to your cPanel / hosting.`);
    } catch (err: any) {
      setStandaloneExportError(err.message || 'Export failed');
    } finally {
      setIsExportingStandalone(false);
    }
  };

  // Poll preview generation batch job
  useEffect(() => {
    if (!activeJob || (activeJob.status !== 'RUNNING' && activeJob.status !== 'PAUSED')) return;
    const interval = setInterval(async () => {
      try {
        const updated = await api.getJob(activeJob.id);
        setActiveJob(updated);
      } catch (err) {
        console.error('Error polling preview job:', err);
      }
    }, 400);
    return () => clearInterval(interval);
  }, [activeJob]);

  const loadExistingGalleries = async () => {
    if (!project) return;
    try {
      const list = await api.listProofingGalleries(project.id);
      setExistingGalleries(list);
      if (list.length > 0 && !activeGallery) {
        setActiveGallery(list[0]);
      }
    } catch (e) {
      console.error('Error fetching galleries:', e);
    }
  };

  if (!isOpen || !project) return null;

  const handleCreateGallery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Please provide a gallery title');
      return;
    }

    setIsLoading(true);
    setError(null);

    // Filter photo IDs based on scope
    let targetIds: number[] = [];
    if (selectionScope === 'best') {
      targetIds = photos.filter(p => p.effective_selection === 'BEST' || p.is_group_best).map(p => p.id);
    } else if (selectionScope === 'edited') {
      targetIds = photos.filter(p => p.is_edited === 1).map(p => p.id);
    } else {
      targetIds = photos.map(p => p.id);
    }

    if (targetIds.length === 0) {
      targetIds = photos.map(p => p.id);
    }

    try {
      const res = await api.createProofingGallery(
        project.id,
        title.trim(),
        clientName.trim(),
        clientPin.trim(),
        targetIds,
        watermarkEnabled,
        watermarkText.trim()
      );
      setActiveGallery(res);
      if (res.job_id) {
        try {
          const job = await api.getJob(res.job_id);
          setActiveJob(job);
        } catch (_) {}
      }
      await loadExistingGalleries();
      if (onRefreshProject) onRefreshProject();
    } catch (err: any) {
      setError(err.message || 'Failed to create client gallery');
    } finally {
      setIsLoading(false);
    }
  };

  const getBaseOrigin = (mode: 'online' | 'domain' | 'wifi' | 'local' = linkMode) => {
    if (mode === 'domain' && customDomainUrl && customDomainUrl.trim()) {
      let d = customDomainUrl.trim();
      if (!d.startsWith('http://') && !d.startsWith('https://')) {
        d = `https://${d}`;
      }
      return d.replace(/\/+$/, '');
    }
    if (mode === 'online' && tunnelUrl) {
      return tunnelUrl.replace(/\/+$/, '');
    }
    if (mode === 'wifi' && localIp && localIp !== '127.0.0.1') {
      return `http://${localIp}:${BACKEND_PORT}`;
    }
    return BACKEND_ORIGIN;
  };

  const getFullShareUrl = (
    galleryUuid: string,
    mode: 'online' | 'domain' | 'wifi' | 'local' = linkMode,
    withPin: boolean = autoUnlockLink
  ) => {
    const origin = getBaseOrigin(mode);
    const pin = activeGallery?.client_pin;
    if (withPin && pin) {
      return `${origin}/gallery/${galleryUuid}?pin=${encodeURIComponent(pin)}`;
    }
    return `${origin}/gallery/${galleryUuid}`;
  };

  const handleCopyLink = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShareWhatsApp = () => {
    if (!activeGallery) return;
    // Prefer online link for WhatsApp so client can open on mobile phone anywhere
    const effectiveMode = tunnelUrl ? 'online' : (localIp !== '127.0.0.1' ? 'wifi' : 'local');
    const shareUrl = getFullShareUrl(activeGallery.gallery_uuid, effectiveMode, autoUnlockLink);

    const pinInfo = (activeGallery?.client_pin && !autoUnlockLink)
      ? `\n🔑 Gallery Access PIN: *${activeGallery.client_pin}*\n`
      : '';
    const message = encodeURIComponent(
      `Namaste ${clientName || 'Ji'}! Aapke wedding photos ka selection link ready ho gaya hai.\n\n👉 Click to view & select: ${shareUrl}\n${pinInfo}\n(Note: Photos par ❤️ Select ya ✖ Reject tap karein aur final hone par Submit Selection button dabayein).`
    );
    window.open(`https://api.whatsapp.com/send?text=${message}`, '_blank');
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '640px', width: '95%' }}>
        {/* Header */}
        <div style={{
          padding: '16px 22px',
          borderBottom: '1px solid #232733',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'linear-gradient(180deg, #161a24 0%, #11141b 100%)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '8px',
              background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Share2 size={16} style={{ color: '#3b82f6' }} />
            </div>
            <div>
              <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc' }}>
                Client Proofing & Selection Link
              </h2>
              <p style={{ fontSize: '11px', color: '#94a3b8' }}>
                Create download-protected mobile gallery for bride & groom to select photos
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: '20px', maxHeight: '78vh', overflowY: 'auto' }}>
          {error && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.12)', color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.3)', padding: '10px 14px',
              borderRadius: '8px', fontSize: '12px', marginBottom: '16px'
            }}>
              {error}
            </div>
          )}

          {/* Real-time Preview Generation Progress Bar */}
          {activeJob && (
            <div style={{
              background: '#151924',
              border: '1px solid #28334a',
              borderRadius: '10px',
              padding: '14px',
              marginBottom: '16px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <RefreshCw
                    size={14}
                    style={{
                      color: activeJob.status === 'COMPLETED' ? '#10b981' : '#38bdf8',
                      animation: activeJob.status === 'RUNNING' ? 'spin 1.2s linear infinite' : 'none'
                    }}
                  />
                  <span style={{ fontSize: '12px', fontWeight: 700, color: '#f8fafc' }}>
                    {activeJob.status === 'COMPLETED' ? '✅ All Previews Cached & Ready' : 'Generating Protected 1200px Previews...'}
                  </span>
                </div>
                <span style={{ fontSize: '12px', fontWeight: 800, color: activeJob.status === 'COMPLETED' ? '#34d399' : '#38bdf8', fontVariantNumeric: 'tabular-nums' }}>
                  {activeJob.progress_current} / {activeJob.progress_total} ({activeJob.progress_pct}%)
                </span>
              </div>

              {/* Progress bar line */}
              <div style={{ width: '100%', height: '8px', background: '#202636', borderRadius: '4px', overflow: 'hidden', marginBottom: '8px' }}>
                <div
                  style={{
                    width: `${activeJob.progress_pct}%`,
                    height: '100%',
                    background: activeJob.status === 'COMPLETED' ? '#10b981' : 'linear-gradient(90deg, #2563eb, #38bdf8)',
                    transition: 'width 0.2s ease',
                    boxShadow: activeJob.status === 'COMPLETED' ? '0 0 10px rgba(16, 185, 129, 0.4)' : '0 0 10px rgba(56, 189, 248, 0.4)'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#94a3b8' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '320px' }}>
                  {activeJob.status === 'COMPLETED' ? 'Complete! All photos cached for mobile client view.' : `Processing: ${activeJob.current_file || 'Starting...'}`}
                </span>
                {activeJob.status === 'RUNNING' && (
                  <span>~{Math.ceil((activeJob.progress_total - activeJob.progress_current) * 0.12)}s left</span>
                )}
              </div>
            </div>
          )}

          {/* Active / Created Link Card */}
          {activeGallery && (
            <div style={{
              background: 'linear-gradient(180deg, #162032 0%, #111824 100%)',
              border: '1px solid #2563eb',
              borderRadius: '12px',
              padding: '16px',
              marginBottom: '20px',
              boxShadow: '0 6px 20px rgba(37, 99, 235, 0.15)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldCheck size={16} color="#10b981" />
                  <span style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
                    Active Client Gallery Link
                  </span>
                </div>
                <span style={{
                  fontSize: '11px', fontWeight: 700, padding: '3px 9px', borderRadius: '12px',
                  background: activeGallery.status === 'SUBMITTED' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                  color: activeGallery.status === 'SUBMITTED' ? '#10b981' : '#60a5fa'
                }}>
                  {activeGallery.status === 'SUBMITTED' ? '✓ Selections Submitted' : '⏳ Client Selecting'}
                </span>
              </div>

              {/* PIN Badge & Auto-Unlock Option */}
              {activeGallery.client_pin && (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)',
                  padding: '7px 12px', borderRadius: '8px', marginBottom: '10px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '11px', color: '#fbbf24', fontWeight: 600 }}>🔑 Security PIN:</span>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#fef08a', fontFamily: 'monospace', letterSpacing: '1px' }}>
                      {activeGallery.client_pin}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(activeGallery.client_pin);
                        setPinCopied(true);
                        setTimeout(() => setPinCopied(false), 2000);
                      }}
                      className="btn btn-secondary"
                      style={{ padding: '2px 8px', fontSize: '10px' }}
                    >
                      {pinCopied ? '✓ Copied' : 'Copy PIN'}
                    </button>
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#cbd5e1', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={autoUnlockLink}
                      onChange={e => setAutoUnlockLink(e.target.checked)}
                      style={{ cursor: 'pointer', accentColor: '#3b82f6' }}
                    />
                    Auto-Unlock Link (Direct photos view)
                  </label>
                </div>
              )}

              {/* Single Clean Ready-to-Share Link Box */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '10px 12px',
                marginBottom: '12px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', display: 'inline-block', boxShadow: '0 0 8px rgba(16, 185, 129, 0.6)' }}></span>
                    <span style={{ fontSize: '11px', color: '#34d399', fontWeight: 700 }}>
                      Live Mobile &amp; PC Link Ready
                    </span>
                  </div>
                  {isTunnelLoading && (
                    <span style={{ fontSize: '10px', color: '#94a3b8' }}>Refreshing connection...</span>
                  )}
                </div>

                <div style={{
                  display: 'flex', gap: '8px', background: '#0a0d14', padding: '8px 12px',
                  borderRadius: '6px', border: '1px solid #1e2638', alignItems: 'center'
                }}>
                  <input
                    type="text"
                    readOnly
                    value={getFullShareUrl(activeGallery.gallery_uuid, undefined, autoUnlockLink)}
                    style={{
                      flex: 1, background: 'transparent', border: 'none', color: '#60a5fa',
                      fontSize: '12.5px', outline: 'none', fontFamily: 'monospace', fontWeight: 500
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => handleCopyLink(getFullShareUrl(activeGallery.gallery_uuid, undefined, autoUnlockLink))}
                    className="btn btn-primary"
                    style={{ padding: '5px 14px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px', background: copied ? '#10b981' : '#2563eb' }}
                  >
                    {copied ? <Check size={13} color="#fff" /> : <Copy size={13} />}
                    {copied ? 'Copied!' : 'Copy Link'}
                  </button>
                </div>
              </div>

              {/* Action Buttons: WhatsApp Share & Preview */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
                <button
                  type="button"
                  onClick={handleShareWhatsApp}
                  style={{
                    flex: 1, padding: '10px 14px', background: 'linear-gradient(135deg, #25d366, #128c7e)', color: '#fff',
                    border: 'none', borderRadius: '8px', fontSize: '12.5px', fontWeight: 700,
                    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                    boxShadow: '0 4px 12px rgba(37, 211, 102, 0.25)'
                  }}
                >
                  <Send size={14} /> WhatsApp par bhejein
                </button>
                <button
                  type="button"
                  onClick={() => window.open(getFullShareUrl(activeGallery.gallery_uuid, 'local', true), '_blank')}
                  className="btn btn-secondary"
                  style={{ padding: '10px 14px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <ExternalLink size={13} /> Open Gallery
                </button>
              </div>


              <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '10px', display: 'flex', gap: '16px' }}>
                <span>Photos: <strong>{activeGallery.total_photos}</strong></span>
                <span>Selected: <strong style={{ color: '#10b981' }}>{activeGallery.selected_count || 0}</strong></span>
                {activeGallery.client_pin && <span>PIN: <strong style={{ color: '#f59e0b' }}>{activeGallery.client_pin}</strong></span>}
              </div>
            </div>
          )}

          {/* Create New Link Form */}
          <form onSubmit={handleCreateGallery} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#f1f5f9', borderBottom: '1px solid #1f2533', paddingBottom: '6px' }}>
              Create New Selection Link
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                Event / Gallery Title
              </label>
              <input
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Rahul & Priya Wedding - Photo Selection"
                style={{
                  width: '100%', background: '#121418', border: '1px solid #2d3342',
                  padding: '8px 12px', borderRadius: '6px', color: '#f8fafc', fontSize: '12px', outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                  Client Name (Couple)
                </label>
                <input
                  type="text"
                  value={clientName}
                  onChange={e => setClientName(e.target.value)}
                  placeholder="Rahul & Priya"
                  style={{
                    width: '100%', background: '#121418', border: '1px solid #2d3342',
                    padding: '8px 12px', borderRadius: '6px', color: '#f8fafc', fontSize: '12px', outline: 'none'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                  Security PIN (Optional)
                </label>
                <input
                  type="text"
                  value={clientPin}
                  onChange={e => setClientPin(e.target.value)}
                  placeholder="e.g. 1234"
                  maxLength={6}
                  style={{
                    width: '100%', background: '#121418', border: '1px solid #2d3342',
                    padding: '8px 12px', borderRadius: '6px', color: '#f8fafc', fontSize: '12px', outline: 'none'
                  }}
                />
              </div>
            </div>

            {/* Scope selection */}
            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                Photos to Include in Client Link
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setSelectionScope('best')}
                  style={{
                    padding: '8px', borderRadius: '6px', border: '1px solid',
                    borderColor: selectionScope === 'best' ? '#2563eb' : '#283042',
                    background: selectionScope === 'best' ? 'rgba(37, 99, 235, 0.15)' : '#12151d',
                    color: selectionScope === 'best' ? '#60a5fa' : '#94a3b8',
                    fontSize: '11px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  ⚡ AI Best Only ({photos.filter(p => p.effective_selection === 'BEST' || p.is_group_best).length})
                </button>
                <button
                  type="button"
                  onClick={() => setSelectionScope('edited')}
                  style={{
                    padding: '8px', borderRadius: '6px', border: '1px solid',
                    borderColor: selectionScope === 'edited' ? '#2563eb' : '#283042',
                    background: selectionScope === 'edited' ? 'rgba(37, 99, 235, 0.15)' : '#12151d',
                    color: selectionScope === 'edited' ? '#60a5fa' : '#94a3b8',
                    fontSize: '11px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  ✨ Edited Photos ({photos.filter(p => p.is_edited === 1).length})
                </button>
                <button
                  type="button"
                  onClick={() => setSelectionScope('all')}
                  style={{
                    padding: '8px', borderRadius: '6px', border: '1px solid',
                    borderColor: selectionScope === 'all' ? '#2563eb' : '#283042',
                    background: selectionScope === 'all' ? 'rgba(37, 99, 235, 0.15)' : '#12151d',
                    color: selectionScope === 'all' ? '#60a5fa' : '#94a3b8',
                    fontSize: '11px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  📷 All Non-Rejected ({photos.filter(p => p.user_selection !== 'REJECT').length})
                </button>
              </div>
            </div>

            {/* Anti-Download Watermark Protection */}
            <div style={{ background: '#12151d', border: '1px solid #202636', borderRadius: '8px', padding: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Lock size={14} color="#10b981" />
                  <span style={{ fontSize: '12px', fontWeight: 600, color: '#f1f5f9' }}>Anti-Download Protection & Watermark</span>
                </div>
                <input
                  type="checkbox"
                  checked={watermarkEnabled}
                  onChange={e => setWatermarkEnabled(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
              </div>
              <p style={{ fontSize: '11px', color: '#64748b', lineHeight: 1.4, marginBottom: '8px' }}>
                Photos will be resized to 1200px lightweight WebP with diagonal security watermark. Right-click and long-press downloads will be blocked on client mobile & PC.
              </p>
              {watermarkEnabled && (
                <input
                  type="text"
                  value={watermarkText}
                  onChange={e => setWatermarkText(e.target.value)}
                  placeholder="PROOF ONLY - Studio Name"
                  style={{
                    width: '100%', background: '#0d0f14', border: '1px solid #2d3342',
                    padding: '6px 10px', borderRadius: '6px', color: '#f8fafc', fontSize: '11px', outline: 'none'
                  }}
                />
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Close
              </button>
              <button
                type="submit"
                disabled={isLoading}
                style={{
                  padding: '9px 20px', background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
                  color: '#fff', border: 'none', borderRadius: '8px', fontSize: '12px', fontWeight: 700,
                  cursor: isLoading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                }}
              >
                {isLoading ? <RefreshCw size={13} className="animate-spin" /> : <Smartphone size={13} />}
                {isLoading ? 'Generating Previews...' : 'Generate Client Selection Link'}
              </button>
            </div>
          </form>

          {/* Optional Admin Master Domain Setting (Hidden by default for regular users) */}
          <div style={{ marginTop: '16px', paddingTop: '10px', borderTop: '1px solid #1a202c' }}>
            <button
              type="button"
              onClick={() => setShowAdminDomainSetup(!showAdminDomainSetup)}
              style={{
                background: 'none', border: 'none', color: '#64748b', fontSize: '11px',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px', padding: 0
              }}
            >
              <Settings size={12} />
              <span>{showAdminDomainSetup ? 'Hide Master Domain Setting' : '⚙️ Master Hosting Domain (Admin Only)'}</span>
            </button>

            {showAdminDomainSetup && (
              <div style={{
                marginTop: '10px', padding: '12px', background: 'rgba(15, 23, 42, 0.8)',
                borderRadius: '8px', border: '1px solid #1e293b'
              }}>
                <div style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                  Apna Master Hosting URL (e.g. <code>https://yourdomain.com/album</code>):
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="text"
                    placeholder="https://yourdomain.com/album"
                    value={customDomainUrl}
                    onChange={e => setCustomDomainUrl(e.target.value)}
                    style={{
                      flex: 1, background: '#0a0d14', border: '1px solid #28334a',
                      borderRadius: '6px', padding: '6px 10px', color: '#fff', fontSize: '12px', outline: 'none'
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleSaveDomainSettings}
                    disabled={isSavingDomain}
                    className="btn btn-primary"
                    style={{ padding: '6px 14px', fontSize: '11px' }}
                  >
                    {isSavingDomain ? 'Saving...' : 'Save URL'}
                  </button>
                </div>
                {domainSaveMessage && (
                  <div style={{ fontSize: '11px', color: '#34d399', marginTop: '6px' }}>
                    {domainSaveMessage}
                  </div>
                )}
                <p style={{ fontSize: '10px', color: '#64748b', margin: '6px 0 0' }}>
                  Yahan domain save karne ke baad sabhi users ke client links automatically aapke hosting domain par banenge.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
