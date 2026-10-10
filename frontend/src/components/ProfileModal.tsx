import React, { useEffect, useState } from 'react';
import { X, User, Mail, Phone, Key, Copy, Check, Crown, Calendar, Clock, Laptop, Receipt, RefreshCw, ShieldCheck, AlertCircle } from 'lucide-react';
import { api } from '../api';
import { LicenseStatus } from '../types';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenPricing: () => void;
  onLicenseUpdated?: (license: LicenseStatus) => void;
}

const planLabel = (plan?: string) =>
  plan === 'VIP_LIFETIME' ? 'VIP Lifetime' : plan === 'STUDIO' ? 'Studio (3 computers)' : plan === 'PRO' ? 'Pro' : 'Free Trial';

const card: React.CSSProperties = { background: '#151a24', border: '1px solid #252d3d', borderRadius: '10px', padding: '14px 16px' };
const label: React.CSSProperties = { fontSize: '11px', color: '#7c8aa0', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '3px' };
const value: React.CSSProperties = { fontSize: '13px', color: '#e7ecf3', fontWeight: 600, wordBreak: 'break-word' };

export const ProfileModal: React.FC<ProfileModalProps> = ({ isOpen, onClose, onOpenPricing, onLicenseUpdated }) => {
  const [profile, setProfile] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const load = async (refreshFirst = false) => {
    setLoading(true);
    try {
      if (refreshFirst) {
        const lic = await api.refreshLicense();
        if (onLicenseUpdated) onLicenseUpdated(lic);
      }
      setProfile(await api.getLicenseProfile());
    } catch (e: any) {
      setMessage({ text: e.message || 'Could not load profile', ok: false });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setMessage(null);
      load();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const st: LicenseStatus | undefined = profile?.status;
  const active = !!st?.is_active;
  const isTrial = !!profile?.is_trial;
  const leftText = !profile ? '—'
    : profile.expires_at === 'Lifetime' ? 'Never expires'
    : (profile.days_left ?? 0) >= 1 ? `${profile.days_left} days left`
    : `${profile.hours_left ?? 0} hours left`;
  const pct = typeof profile?.left_pct === 'number' ? profile.left_pct : (profile?.expires_at === 'Lifetime' ? 100 : 0);
  const barColor = pct > 30 ? '#10b981' : pct > 10 ? '#f59e0b' : '#ef4444';

  const handleDeactivate = async () => {
    if (!window.confirm('Remove the license from this computer? You can then activate the same key on another computer.')) return;
    setBusy(true);
    try {
      const res = await api.deactivateLicense();
      setMessage({ text: res.message, ok: true });
      if (onLicenseUpdated && res.license) onLicenseUpdated(res.license);
      await load();
    } catch (e: any) {
      setMessage({ text: e.message, ok: false });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '680px', width: '95%' }}>
        <div style={{ padding: '16px 22px', borderBottom: '1px solid #232733', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'linear-gradient(180deg, #161a24 0%, #11141b 100%)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '34px', height: '34px', borderRadius: '50%', background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800 }}>
              {(profile?.name || 'U').trim().charAt(0).toUpperCase()}
            </div>
            <div>
              <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc', margin: 0 }}>My Plan &amp; Profile</h2>
              <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0 }}>Your Ai PhotoFlow subscription, computers and payments</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button onClick={() => load(true)} disabled={loading} className="btn btn-secondary btn-sm" title="Check with server">
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            </button>
            <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={18} /></button>
          </div>
        </div>

        <div style={{ padding: '18px 22px', maxHeight: '76vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {message && (
            <div style={{ padding: '9px 12px', borderRadius: '8px', fontSize: '12px',
              background: message.ok ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)', color: message.ok ? '#34d399' : '#f87171' }}>{message.text}</div>
          )}
          {!profile && loading && <div style={{ color: '#94a3b8', fontSize: '13px' }}>Loading…</div>}

          {profile && (
            <>
              {/* Plan summary */}
              <div style={{ ...card, background: active ? 'linear-gradient(135deg, #172238 0%, #131a28 100%)' : '#1d1517',
                borderColor: active ? '#2b4a7a' : '#5b2b2b' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
                  <div>
                    <div style={label}>Current plan</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Crown size={18} color={active ? '#fbbf24' : '#94a3b8'} />
                      <span style={{ fontSize: '19px', fontWeight: 800, color: '#fff' }}>{planLabel(profile.plan)}</span>
                      <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '999px',
                        background: active ? 'rgba(16,185,129,0.18)' : 'rgba(239,68,68,0.18)', color: active ? '#34d399' : '#f87171' }}>
                        {active ? 'ACTIVE' : (st?.status || 'INACTIVE')}
                      </span>
                    </div>
                    {profile.cycle && <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '3px' }}>Billing: {profile.cycle}</div>}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={label}>Time left</div>
                    <div style={{ fontSize: '17px', fontWeight: 800, color: active ? barColor : '#f87171' }}>{active ? leftText : 'Expired'}</div>
                  </div>
                </div>
                <div style={{ height: '8px', background: '#0d1119', borderRadius: '6px', overflow: 'hidden', margin: '12px 0 10px' }}>
                  <div style={{ width: `${active ? pct : 0}%`, height: '100%', background: barColor, transition: 'width .3s' }} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px' }}>
                  <div><div style={label}><Calendar size={11} /> {isTrial ? 'Trial started' : 'Activated on'}</div><div style={value}>{profile.activated_at || '—'}</div></div>
                  <div><div style={label}><Clock size={11} /> Valid till</div><div style={value}>{profile.expires_at || '—'}</div></div>
                  <div><div style={label}><Laptop size={11} /> Computers</div>
                    <div style={value}>{isTrial ? 'This computer only' : `${profile.devices?.length || 1} of ${profile.max_devices} in use`}</div></div>
                </div>
                {st?.message && !active && (
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '10px', fontSize: '12px', color: '#fbbf24' }}>
                    <AlertCircle size={13} /> {st.message}
                  </div>
                )}
                <div style={{ display: 'flex', gap: '8px', marginTop: '14px', flexWrap: 'wrap' }}>
                  <button className="btn btn-primary" onClick={() => { onClose(); onOpenPricing(); }}>
                    {isTrial || !active ? 'Buy a plan' : 'Renew / Upgrade'}
                  </button>
                  {!isTrial && profile.license_key && (
                    <button className="btn btn-secondary" disabled={busy} onClick={handleDeactivate}>Remove from this computer</button>
                  )}
                </div>
              </div>

              {/* Customer profile */}
              {!isTrial && (
                <div style={card}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#f1f5f9', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <User size={14} color="#60a5fa" /> Profile
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '12px' }}>
                    <div><div style={label}><User size={11} /> Name</div><div style={value}>{profile.name || '—'}</div></div>
                    <div><div style={label}><Phone size={11} /> Mobile</div><div style={value}>{profile.phone || '—'}</div></div>
                    <div><div style={label}><Mail size={11} /> Email</div><div style={value}>{profile.email || '—'}</div></div>
                  </div>
                  <div style={{ marginTop: '12px' }}>
                    <div style={label}><Key size={11} /> License key</div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span style={{ ...value, fontFamily: 'monospace', letterSpacing: '0.5px' }}>{profile.license_key}</span>
                      <button className="btn btn-secondary btn-sm" onClick={() => { navigator.clipboard.writeText(profile.license_key); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                        {copied ? <Check size={12} /> : <Copy size={12} />}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Computers */}
              {!isTrial && profile.devices?.length > 0 && (
                <div style={card}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#f1f5f9', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Laptop size={14} color="#60a5fa" /> Computers using this license
                  </div>
                  {profile.devices.map((d: any, i: number) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderTop: i ? '1px solid #222a39' : 'none', fontSize: '12px' }}>
                      <div>
                        <div style={{ color: '#e7ecf3', fontWeight: 600 }}>{d.name} {d.this_computer && <span style={{ color: '#34d399', fontWeight: 700 }}>· This computer</span>}</div>
                        <div style={{ color: '#7c8aa0' }}>{d.os}</div>
                      </div>
                      <div style={{ textAlign: 'right', color: '#94a3b8' }}>
                        <div>Since {d.first_seen}</div><div>Last online {d.last_seen}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Payments */}
              {!isTrial && (
                <div style={card}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#f1f5f9', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Receipt size={14} color="#60a5fa" /> Payment history
                  </div>
                  {profile.orders?.length ? profile.orders.map((o: any, i: number) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderTop: i ? '1px solid #222a39' : 'none', fontSize: '12px' }}>
                      <div>
                        <div style={{ color: '#e7ecf3', fontWeight: 600 }}>{planLabel(o.plan)} · {o.cycle}</div>
                        <div style={{ color: '#7c8aa0' }}>{o.date}{o.coupon ? ` · coupon ${o.coupon}` : ''}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ color: '#34d399', fontWeight: 700 }}>{o.currency === 'USD' ? '$' : '₹'}{Number(o.amount).toLocaleString('en-IN')}</div>
                        <div style={{ color: '#7c8aa0', fontFamily: 'monospace', fontSize: '11px' }}>{o.payment_id}</div>
                      </div>
                    </div>
                  )) : <div style={{ fontSize: '12px', color: '#7c8aa0' }}>{profile.online ? 'No online payments for this license (issued directly).' : 'Connect to the internet to load payment history.'}</div>}
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#64748b' }}>
                <ShieldCheck size={13} color="#10b981" />
                <span>Computer ID {profile.machine_id} · last verified {profile.last_checked || '—'}</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
