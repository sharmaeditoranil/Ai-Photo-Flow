import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Settings, X, Key, Cpu, Cloud, Check, ShieldCheck, ExternalLink, CreditCard, Lock, ShieldAlert } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [pinInput, setPinInput] = useState<string>('');
  const [pinError, setPinError] = useState<string>('');

  const [provider, setProvider] = useState<string>('local');
  const [replicateToken, setReplicateToken] = useState<string>('');
  const [openAiKey, setOpenAiKey] = useState<string>('');
  const [geminiKey, setGeminiKey] = useState<string>('');
  const [customEndpoint, setCustomEndpoint] = useState<string>('');
  const [razorpayKeyId, setRazorpayKeyId] = useState<string>('');
  const [razorpayKeySecret, setRazorpayKeySecret] = useState<string>('');
  const [razorpayEnabled, setRazorpayEnabled] = useState<boolean>(true);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen) {
      // Re-lock whenever modal is closed
      setIsAuthenticated(false);
      setPinInput('');
      setPinError('');
    } else if (isAuthenticated) {
      api.getSettings().then((res) => {
        if (res.ai_provider) setProvider(res.ai_provider);
        if (res.replicate_api_token) setReplicateToken(res.replicate_api_token);
        if (res.openai_api_key) setOpenAiKey(res.openai_api_key);
        if (res.gemini_api_key) setGeminiKey(res.gemini_api_key);
        if (res.custom_ai_endpoint) setCustomEndpoint(res.custom_ai_endpoint);
        if (res.razorpay_key_id) setRazorpayKeyId(res.razorpay_key_id);
        if (res.razorpay_key_secret) setRazorpayKeySecret(res.razorpay_key_secret);
        if (res.razorpay_enabled !== undefined) setRazorpayEnabled(res.razorpay_enabled);
      }).catch(console.error);
    }
  }, [isOpen, isAuthenticated]);

  if (!isOpen) return null;

  const handlePinSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (pinInput.trim() === 'Anil@#140477') {
      setIsAuthenticated(true);
      setPinError('');
    } else {
      setPinError('Incorrect Master PIN. Access Denied.');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await api.saveSettings({
        ai_provider: provider,
        replicate_api_token: replicateToken,
        openai_api_key: openAiKey,
        gemini_api_key: geminiKey,
        custom_ai_endpoint: customEndpoint,
        razorpay_key_id: razorpayKeyId,
        razorpay_key_secret: razorpayKeySecret,
        razorpay_enabled: razorpayEnabled
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch (err) {
      console.error('Failed to save settings:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // If not authenticated, display Admin PIN gate
  if (!isAuthenticated) {
    return (
      <div className="modal-overlay">
        <div className="modal-content" style={{ maxWidth: '400px', padding: '24px', textAlign: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
              <X size={18} />
            </button>
          </div>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'rgba(59, 130, 246, 0.15)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 14px',
            color: '#3b82f6'
          }}>
            <Lock size={22} />
          </div>
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc', marginBottom: '6px' }}>
            Admin Control Center
          </h2>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '18px', lineHeight: 1.4 }}>
            Restricted to administrator (Anil Sharma) for Razorpay &amp; core security keys.
          </p>

          <form onSubmit={handlePinSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input
              type="password"
              value={pinInput}
              onChange={(e) => {
                setPinInput(e.target.value);
                setPinError('');
              }}
              autoFocus
              style={{
                width: '100%',
                background: '#0d0e12',
                border: pinError ? '1px solid #ef4444' : '1px solid #2c3240',
                padding: '10px 12px',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '14px',
                textAlign: 'center',
                letterSpacing: '2px',
                outline: 'none'
              }}
            />
            {pinError && (
              <span style={{ fontSize: '12px', color: '#ef4444', fontWeight: 500 }}>
                {pinError}
              </span>
            )}

            <div style={{ display: 'flex', gap: '10px', marginTop: '6px' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary" style={{ flex: 1 }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
                Unlock Admin
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '580px' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #232733', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Lock size={18} style={{ color: '#10b981' }} />
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc' }}>
              Admin Control Center (Anil Sharma)
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

          {/* Razorpay Payment Gateway Configuration */}
          <div style={{ background: '#13151a', padding: '14px', borderRadius: '8px', border: '1px solid #232733', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CreditCard size={14} style={{ color: '#3b82f6' }} />
                <span style={{ fontSize: '12px', fontWeight: 700, color: '#e2e8f0' }}>Razorpay Payment Gateway</span>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#94a3b8', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={razorpayEnabled}
                  onChange={(e) => setRazorpayEnabled(e.target.checked)}
                />
                <span>Enable Payments</span>
              </label>
            </div>

            <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', lineHeight: 1.4 }}>
              Customer UPI (GPay, PhonePe, Paytm), QR Code, Cards ya NetBanking se payment karega aur software automatically unlock ho jayega.
            </p>

            {/* Razorpay Key ID */}
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Razorpay Key ID (rzp_live_... ya rzp_test_...)
              </label>
              <input
                type="text"
                value={razorpayKeyId}
                onChange={(e) => setRazorpayKeyId(e.target.value)}
                placeholder="rzp_live_••••••••••••••••"
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

            {/* Razorpay Key Secret */}
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Razorpay Key Secret
              </label>
              <input
                type="password"
                value={razorpayKeySecret}
                onChange={(e) => setRazorpayKeySecret(e.target.value)}
                placeholder="••••••••••••••••••••••••"
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

            <div style={{ fontSize: '10px', color: '#64748b' }}>
              Razorpay Keys Dashboard se lein:{' '}
              <span style={{ color: '#38bdf8' }}>dashboard.razorpay.com &gt; Settings &gt; API Keys</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#64748b' }}>
            <ShieldCheck size={13} style={{ color: '#10b981' }} />
            <span>Credentials and API keys are stored encrypted in your local SQLite database on this Mac.</span>
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
