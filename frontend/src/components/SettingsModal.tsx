import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { X, Key, Cpu, Cloud, Check, ShieldCheck, Settings } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [provider, setProvider] = useState<string>('local');
  const [replicateToken, setReplicateToken] = useState<string>('');
  const [openAiKey, setOpenAiKey] = useState<string>('');
  const [geminiKey, setGeminiKey] = useState<string>('');
  const [customEndpoint, setCustomEndpoint] = useState<string>('');
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      api.getSettings().then((res) => {
        if (res.ai_provider) setProvider(res.ai_provider);
        if (res.replicate_api_token) setReplicateToken(res.replicate_api_token);
        if (res.openai_api_key) setOpenAiKey(res.openai_api_key);
        if (res.gemini_api_key) setGeminiKey(res.gemini_api_key);
        if (res.custom_ai_endpoint) setCustomEndpoint(res.custom_ai_endpoint);
      }).catch(console.error);
    }
  }, [isOpen]);

  if (!isOpen) return null;


  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await api.saveSettings({
        ai_provider: provider,
        replicate_api_token: replicateToken,
        openai_api_key: openAiKey,
        gemini_api_key: geminiKey,
        custom_ai_endpoint: customEndpoint
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch (err) {
      console.error('Failed to save settings:', err);
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '580px' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #232733', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Settings size={18} style={{ color: '#3b82f6' }} />
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc' }}>
              AI Processing Settings
            </h2>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSave} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* AI Provider Mode */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>
              Processing Engine
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div
                onClick={() => setProvider('local')}
                style={{
                  padding: '12px',
                  borderRadius: '6px',
                  background: provider === 'local' ? 'rgba(59, 130, 246, 0.15)' : '#15171e',
                  border: provider === 'local' ? '2px solid #3b82f6' : '1px solid #282d3b',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: '#f1f5f9', fontSize: '12px' }}>
                    <Cpu size={14} style={{ color: '#3b82f6' }} />
                    <span>Local Mac (Offline)</span>
                  </div>
                  <span style={{ fontSize: '10px', background: '#059669', color: '#fff', padding: '1px 5px', borderRadius: '3px', fontWeight: 700 }}>
                    ₹0 FREE
                  </span>
                </div>
                <p style={{ fontSize: '11px', color: '#94a3b8', lineHeight: 1.3 }}>
                  Runs on your Mac's Apple Silicon / CPU. 100% offline, zero API costs, unlimited photos.
                </p>
              </div>

              <div
                onClick={() => setProvider('cloud')}
                style={{
                  padding: '12px',
                  borderRadius: '6px',
                  background: provider === 'cloud' ? 'rgba(59, 130, 246, 0.15)' : '#15171e',
                  border: provider === 'cloud' ? '2px solid #3b82f6' : '1px solid #282d3b',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: '#f1f5f9', fontSize: '12px' }}>
                    <Cloud size={14} style={{ color: '#38bdf8' }} />
                    <span>Cloud AI API (V2 Ready)</span>
                  </div>
                </div>
                <p style={{ fontSize: '11px', color: '#94a3b8', lineHeight: 1.3 }}>
                  Connects to Replicate, OpenAI, or custom GPU server for heavy generative models.
                </p>
              </div>
            </div>
          </div>

          {/* API Keys Configuration */}
          <div style={{ background: '#13151a', padding: '14px', borderRadius: '8px', border: '1px solid #232733', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
              <Key size={13} style={{ color: '#eab308' }} />
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#e2e8f0' }}>Cloud AI Credentials</span>
            </div>

            {/* Replicate API Token */}
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Replicate API Token (Optional)
              </label>
              <input
                type="text"
                value={replicateToken}
                onChange={(e) => setReplicateToken(e.target.value)}
                placeholder="r8_••••••••••••••••••••••••"
                style={{
                  width: '100%',
                  background: '#0d0e12',
                  border: '1px solid #2c3240',
                  padding: '7px 10px',
                  borderRadius: '5px',
                  color: '#f8fafc',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  outline: 'none'
                }}
              />
            </div>

            {/* OpenAI API Key */}
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                OpenAI API Key (Optional)
              </label>
              <input
                type="text"
                value={openAiKey}
                onChange={(e) => setOpenAiKey(e.target.value)}
                placeholder="sk-••••••••••••••••••••••••"
                style={{
                  width: '100%',
                  background: '#0d0e12',
                  border: '1px solid #2c3240',
                  padding: '7px 10px',
                  borderRadius: '5px',
                  color: '#f8fafc',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  outline: 'none'
                }}
              />
            </div>

            {/* Gemini API Key */}
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Google Gemini API Key (Optional)
              </label>
              <input
                type="text"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIzaSy••••••••••••••••••••••••"
                style={{
                  width: '100%',
                  background: '#0d0e12',
                  border: '1px solid #2c3240',
                  padding: '7px 10px',
                  borderRadius: '5px',
                  color: '#f8fafc',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  outline: 'none'
                }}
              />
            </div>

            {/* Custom GPU Endpoint */}
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Custom GPU Endpoint / RunPod URL (Optional)
              </label>
              <input
                type="text"
                value={customEndpoint}
                onChange={(e) => setCustomEndpoint(e.target.value)}
                placeholder="https://api.yourcustomgpu.com"
                style={{
                  width: '100%',
                  background: '#0d0e12',
                  border: '1px solid #2c3240',
                  padding: '7px 10px',
                  borderRadius: '5px',
                  color: '#f8fafc',
                  fontSize: '12px',
                  outline: 'none'
                }}
              />
            </div>
          </div>


          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#64748b' }}>
            <ShieldCheck size={13} style={{ color: '#10b981' }} />
            <span>API keys are saved only on this computer. Payments, prices and licenses are managed in the online Admin Panel.</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
            {savedSuccess ? (
              <span style={{ color: '#34d399', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                <Check size={14} /> Settings Saved Successfully!
              </span>
            ) : <span />}

            <div style={{ display: 'flex', gap: '8px' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={isLoading} className="btn btn-primary">
                {isLoading ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
