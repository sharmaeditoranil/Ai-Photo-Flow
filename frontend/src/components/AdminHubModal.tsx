import React, { useState, useEffect } from 'react';
import { api } from '../api';
import {
  Users, DollarSign, Award, CreditCard, ShieldCheck, X, Plus,
  CheckCircle2, Clock, Copy, Check, ChevronRight, Search, RefreshCw,
  ExternalLink, ArrowUpRight, Percent, Smartphone, Lock, AlertCircle
} from 'lucide-react';

interface AdminHubModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultTab?: 'overview' | 'agents' | 'sales' | 'users' | 'settings';
}

export const AdminHubModal: React.FC<AdminHubModalProps> = ({ isOpen, onClose, defaultTab = 'overview' }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [pinInput, setPinInput] = useState<string>('');
  const [pinError, setPinError] = useState<string>('');

  const [activeTab, setActiveTab] = useState<'overview' | 'agents' | 'sales' | 'users' | 'settings'>(defaultTab);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Data states
  const [overview, setOverview] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [sales, setSales] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);

  // Modals inside Admin
  const [showAddAgentModal, setShowAddAgentModal] = useState<boolean>(false);
  const [showPayoutModal, setShowPayoutModal] = useState<boolean>(false);
  const [showManualSaleModal, setShowManualSaleModal] = useState<boolean>(false);
  const [showIssueLicenseModal, setShowIssueLicenseModal] = useState<boolean>(false);

  const [selectedSaleForPayout, setSelectedSaleForPayout] = useState<any>(null);
  const [payoutRef, setPayoutRef] = useState<string>('');
  const [payoutNotes, setPayoutNotes] = useState<string>('');

  // Form states
  const [newAgent, setNewAgent] = useState({
    name: '',
    phone: '',
    email: '',
    referral_code: '',
    discount_percent: 15,
    commission_percent: 20,
    payout_upi: '',
    payout_bank_details: '',
    notes: ''
  });

  const [manualSale, setManualSale] = useState({
    referral_code: '',
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    plan_name: 'PRO',
    sale_amount: 10199,
    billing_cycle: 'yearly'
  });

  const [manualLicense, setManualLicense] = useState({
    user_name: '',
    user_email: '',
    user_phone: '',
    plan_name: 'PRO',
    days: 365,
    referral_code: '',
    notes: ''
  });

  // Gateway Settings
  const [razorpayKeyId, setRazorpayKeyId] = useState<string>('');
  const [razorpayKeySecret, setRazorpayKeySecret] = useState<string>('');
  const [razorpayEnabled, setRazorpayEnabled] = useState<boolean>(true);
  const [settingsSuccess, setSettingsSuccess] = useState<boolean>(false);

  // Search & Copy feedback
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');

  useEffect(() => {
    if (!isOpen) {
      setIsAuthenticated(false);
      setPinInput('');
      setPinError('');
    } else if (isAuthenticated) {
      loadAllAdminData();
    }
  }, [isOpen, isAuthenticated]);

  const loadAllAdminData = async () => {
    setIsLoading(true);
    try {
      const [ov, ag, sl, us, st] = await Promise.all([
        api.getAdminOverview().catch(() => null),
        api.getAdminAgents().catch(() => []),
        api.getAdminReferralSales().catch(() => []),
        api.getAdminUsers().catch(() => []),
        api.getSettings().catch(() => ({}))
      ]);
      setOverview(ov);
      setAgents(ag || []);
      setSales(sl || []);
      setUsers(us || []);
      if (st) {
        if (st.razorpay_key_id) setRazorpayKeyId(st.razorpay_key_id);
        if (st.razorpay_key_secret) setRazorpayKeySecret(st.razorpay_key_secret);
        if (st.razorpay_enabled !== undefined) setRazorpayEnabled(st.razorpay_enabled);
      }
    } catch (err) {
      console.error('Error loading admin data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePinSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (pinInput.trim() === 'Anil@#140477') {
      setIsAuthenticated(true);
      setPinError('');
    } else {
      setPinError('Incorrect Master PIN. Access Denied.');
    }
  };

  const handleCopy = (text: string, keyId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyId);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAdminAgent(newAgent);
      setShowAddAgentModal(false);
      setNewAgent({
        name: '',
        phone: '',
        email: '',
        referral_code: '',
        discount_percent: 15,
        commission_percent: 20,
        payout_upi: '',
        payout_bank_details: '',
        notes: ''
      });
      loadAllAdminData();
    } catch (err: any) {
      alert(err.message || 'Failed to create agent');
    }
  };

  const handlePayCommission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSaleForPayout || !payoutRef.trim()) return;
    try {
      await api.payAdminCommission(selectedSaleForPayout.id, payoutRef.trim(), payoutNotes);
      setShowPayoutModal(false);
      setSelectedSaleForPayout(null);
      setPayoutRef('');
      setPayoutNotes('');
      loadAllAdminData();
    } catch (err: any) {
      alert(err.message || 'Failed to record payout');
    }
  };

  const handleRecordManualSale = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.recordManualReferralSale(manualSale);
      setShowManualSaleModal(false);
      setManualSale({
        referral_code: '',
        customer_name: '',
        customer_email: '',
        customer_phone: '',
        plan_name: 'PRO',
        sale_amount: 10199,
        billing_cycle: 'yearly'
      });
      loadAllAdminData();
    } catch (err: any) {
      alert(err.message || 'Failed to record sale');
    }
  };

  const handleIssueLicense = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.issueAdminUserLicense(manualLicense);
      setShowIssueLicenseModal(false);
      setManualLicense({
        user_name: '',
        user_email: '',
        user_phone: '',
        plan_name: 'PRO',
        days: 365,
        referral_code: '',
        notes: ''
      });
      alert(`License Created Successfully!\nKey: ${res.license.license_key}`);
      loadAllAdminData();
    } catch (err: any) {
      alert(err.message || 'Failed to issue license');
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.saveSettings({
        razorpay_key_id: razorpayKeyId,
        razorpay_key_secret: razorpayKeySecret,
        razorpay_enabled: razorpayEnabled
      });
      setSettingsSuccess(true);
      setTimeout(() => setSettingsSuccess(false), 2500);
    } catch (err) {
      alert('Failed to save settings');
    }
  };

  if (!isOpen) return null;

  // 1. PIN Gate
  if (!isAuthenticated) {
    return (
      <div className="modal-overlay" style={{ zIndex: 1100 }}>
        <div className="modal-content" style={{ maxWidth: '420px', padding: '28px', textAlign: 'center', background: '#11141c', border: '1px solid #232733' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
              <X size={18} />
            </button>
          </div>
          <div style={{
            width: '54px',
            height: '54px',
            borderRadius: '50%',
            background: 'rgba(234, 179, 8, 0.15)',
            border: '1px solid rgba(234, 179, 8, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            color: '#facc15'
          }}>
            <Lock size={26} />
          </div>

          <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#f8fafc', marginBottom: '6px' }}>
            Admin Control & Partner Hub
          </h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '20px', lineHeight: 1.4 }}>
            Enter Master PIN for Anil Sharma to manage marketing referral agents, commissions, and customer licenses.
          </p>

          <form onSubmit={handlePinSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input
              type="password"
              placeholder="Enter Master PIN"
              value={pinInput}
              onChange={(e) => setPinInput(e.target.value)}
              autoFocus
              style={{
                width: '100%',
                background: '#181b24',
                border: pinError ? '1px solid #ef4444' : '1px solid #2d3342',
                color: '#fff',
                padding: '12px',
                borderRadius: '8px',
                textAlign: 'center',
                fontSize: '15px',
                letterSpacing: '2px',
                outline: 'none'
              }}
            />
            {pinError && (
              <span style={{ fontSize: '12px', color: '#ef4444', fontWeight: 600 }}>
                {pinError}
              </span>
            )}

            <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary" style={{ flex: 1, padding: '10px' }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" style={{ flex: 1, padding: '10px', background: '#3b82f6' }}>
                Unlock Admin
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // 2. Full Admin Dashboard
  return (
    <div className="modal-overlay" style={{ zIndex: 1100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="modal-content" style={{
        width: '94vw',
        maxWidth: '1200px',
        height: '88vh',
        display: 'flex',
        flexDirection: 'column',
        background: '#0d1117',
        border: '1px solid #21262d',
        borderRadius: '12px',
        overflow: 'hidden',
        boxShadow: '0 25px 60px rgba(0,0,0,0.85)'
      }}>
        {/* Top Header */}
        <div style={{
          padding: '16px 24px',
          borderBottom: '1px solid #21262d',
          background: '#161b22',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              boxShadow: '0 4px 12px rgba(37,99,235,0.35)'
            }}>
              <ShieldCheck size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '17px', fontWeight: 800, color: '#f0f6fc', margin: 0 }}>
                  Admin Marketing & Partner Control Center
                </h2>
                <span style={{ fontSize: '10px', background: 'rgba(34,197,94,0.15)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)', padding: '2px 8px', borderRadius: '12px', fontWeight: 700 }}>
                  MASTER ACCESS (Anil Sharma)
                </span>
              </div>
              <p style={{ fontSize: '12px', color: '#8b949e', margin: '2px 0 0 0' }}>
                Manage referral partners, sales payouts, commissions, active users and payment gateway.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              onClick={loadAllAdminData}
              className="btn btn-secondary btn-sm"
              title="Refresh Data"
              style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
            >
              <RefreshCw size={13} className={isLoading ? "spin" : ""} />
              <span>Refresh</span>
            </button>
            <button
              onClick={onClose}
              style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '6px' }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Tab Bar */}
        <div style={{
          display: 'flex',
          gap: '4px',
          padding: '0 24px',
          background: '#161b22',
          borderBottom: '1px solid #21262d'
        }}>
          {[
            { id: 'overview', label: '📊 Dashboard Overview', icon: DollarSign },
            { id: 'agents', label: `👥 Marketing Agents (${agents.length})`, icon: Users },
            { id: 'sales', label: `💰 Referral Sales & Commissions (${sales.length})`, icon: Award },
            { id: 'users', label: `👤 Active Users & Licenses (${users.length})`, icon: ShieldCheck },
            { id: 'settings', label: '⚙️ Gateway & API Settings', icon: CreditCard },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid #58a6ff' : '2px solid transparent',
                color: activeTab === tab.id ? '#58a6ff' : '#8b949e',
                fontWeight: activeTab === tab.id ? 700 : 500,
                fontSize: '13px',
                padding: '12px 16px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'all 0.15s ease'
              }}
            >
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', background: '#0d1117' }}>

          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Stat Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8b949e', fontSize: '12px', fontWeight: 600 }}>
                    <span>TOTAL ACTIVE USERS</span>
                    <Users size={16} style={{ color: '#58a6ff' }} />
                  </div>
                  <div style={{ fontSize: '28px', fontWeight: 800, color: '#f0f6fc', marginTop: '8px' }}>
                    {overview?.active_users_count ?? users.length}
                  </div>
                  <div style={{ fontSize: '11px', color: '#3fb950', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircle2 size={12} />
                    <span>Live software licenses running</span>
                  </div>
                </div>

                <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8b949e', fontSize: '12px', fontWeight: 600 }}>
                    <span>REFERRAL REVENUE</span>
                    <DollarSign size={16} style={{ color: '#3fb950' }} />
                  </div>
                  <div style={{ fontSize: '28px', fontWeight: 800, color: '#3fb950', marginTop: '8px' }}>
                    ₹{(overview?.total_referral_revenue ?? 0).toLocaleString('en-IN')}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>
                    Across {overview?.total_referral_sales ?? 0} referred purchases
                  </div>
                </div>

                <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8b949e', fontSize: '12px', fontWeight: 600 }}>
                    <span>COMMISSION PENDING</span>
                    <Clock size={16} style={{ color: '#d29922' }} />
                  </div>
                  <div style={{ fontSize: '28px', fontWeight: 800, color: '#d29922', marginTop: '8px' }}>
                    ₹{(overview?.pending_commission ?? 0).toLocaleString('en-IN')}
                  </div>
                  <div style={{ fontSize: '11px', color: '#d29922', marginTop: '4px' }}>
                    Ready to payout to marketing agents
                  </div>
                </div>

                <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8b949e', fontSize: '12px', fontWeight: 600 }}>
                    <span>COMMISSION PAID</span>
                    <Award size={16} style={{ color: '#a371f7' }} />
                  </div>
                  <div style={{ fontSize: '28px', fontWeight: 800, color: '#a371f7', marginTop: '8px' }}>
                    ₹{(overview?.paid_commission ?? 0).toLocaleString('en-IN')}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>
                    Successfully transferred to agents
                  </div>
                </div>
              </div>

              {/* Quick Actions Row */}
              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '20px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#f0f6fc', marginBottom: '14px' }}>
                  ⚡ Quick Administrative Actions
                </h3>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => setShowAddAgentModal(true)}
                    className="btn btn-primary"
                    style={{ background: '#238636', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Plus size={14} />
                    <span>Create New Marketing Agent</span>
                  </button>

                  <button
                    onClick={() => setShowManualSaleModal(true)}
                    className="btn btn-secondary"
                    style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Award size={14} />
                    <span>Record Offline / Direct Referral Sale</span>
                  </button>

                  <button
                    onClick={() => setShowIssueLicenseModal(true)}
                    className="btn btn-secondary"
                    style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <ShieldCheck size={14} />
                    <span>Issue Official License Key to Client</span>
                  </button>
                </div>
              </div>

              {/* Recent Referral Activity Preview */}
              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                    Recent Referral Sales & Commission Activity
                  </h3>
                  <button onClick={() => setActiveTab('sales')} className="btn btn-secondary btn-sm">
                    View All Sales ({sales.length})
                  </button>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ color: '#8b949e', borderBottom: '1px solid #21262d' }}>
                        <th style={{ padding: '8px 12px' }}>Date</th>
                        <th style={{ padding: '8px 12px' }}>Customer</th>
                        <th style={{ padding: '8px 12px' }}>Plan</th>
                        <th style={{ padding: '8px 12px' }}>Sale Amount</th>
                        <th style={{ padding: '8px 12px' }}>Agent & Code</th>
                        <th style={{ padding: '8px 12px' }}>Commission</th>
                        <th style={{ padding: '8px 12px' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sales.slice(0, 5).map((s) => (
                        <tr key={s.id} style={{ borderBottom: '1px solid #21262d', color: '#c9d1d9' }}>
                          <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>{s.created_at?.slice(0, 10)}</td>
                          <td style={{ padding: '10px 12px' }}>
                            <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{s.customer_name}</div>
                            <div style={{ fontSize: '10px', color: '#8b949e' }}>{s.customer_phone || s.customer_email}</div>
                          </td>
                          <td style={{ padding: '10px 12px' }}>
                            <span style={{ background: '#1f242c', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                              {s.plan_name}
                            </span>
                          </td>
                          <td style={{ padding: '10px 12px', fontWeight: 700, color: '#f0f6fc' }}>
                            ₹{Number(s.sale_amount).toLocaleString('en-IN')}
                          </td>
                          <td style={{ padding: '10px 12px' }}>
                            <div style={{ color: '#58a6ff', fontWeight: 600 }}>{s.agent_name}</div>
                            <div style={{ fontSize: '10px', color: '#8b949e' }}>Code: {s.referral_code}</div>
                          </td>
                          <td style={{ padding: '10px 12px', fontWeight: 700, color: '#3fb950' }}>
                            ₹{Number(s.commission_amount).toLocaleString('en-IN')} ({s.commission_rate}%)
                          </td>
                          <td style={{ padding: '10px 12px' }}>
                            <span style={{
                              padding: '2px 8px',
                              borderRadius: '12px',
                              fontSize: '10px',
                              fontWeight: 700,
                              background: s.status === 'PAID' ? 'rgba(35,134,54,0.2)' : 'rgba(210,153,34,0.2)',
                              color: s.status === 'PAID' ? '#3fb950' : '#d29922',
                              border: s.status === 'PAID' ? '1px solid rgba(35,134,54,0.4)' : '1px solid rgba(210,153,34,0.4)'
                            }}>
                              {s.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: MARKETING AGENTS */}
          {activeTab === 'agents' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                    Marketing Referral Partners (Agents)
                  </h3>
                  <p style={{ fontSize: '12px', color: '#8b949e', margin: '2px 0 0 0' }}>
                    Assign unique referral discount codes to studios, labs, and influencers.
                  </p>
                </div>
                <button
                  onClick={() => setShowAddAgentModal(true)}
                  className="btn btn-primary"
                  style={{ background: '#238636', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Plus size={14} />
                  <span>+ Add New Agent</span>
                </button>
              </div>

              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ background: '#1f242c', color: '#8b949e', borderBottom: '1px solid #30363d' }}>
                      <th style={{ padding: '10px 14px' }}>Agent Name & Contact</th>
                      <th style={{ padding: '10px 14px' }}>Referral Code</th>
                      <th style={{ padding: '10px 14px' }}>Buyer Discount</th>
                      <th style={{ padding: '10px 14px' }}>Commission Rate</th>
                      <th style={{ padding: '10px 14px' }}>Sales Referred</th>
                      <th style={{ padding: '10px 14px' }}>Total Earned</th>
                      <th style={{ padding: '10px 14px' }}>Pending Payout</th>
                      <th style={{ padding: '10px 14px' }}>Payout UPI / Bank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((ag) => (
                      <tr key={ag.id} style={{ borderBottom: '1px solid #21262d', color: '#c9d1d9' }}>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '13px' }}>{ag.name}</div>
                          <div style={{ fontSize: '11px', color: '#8b949e' }}>📞 {ag.phone}</div>
                          {ag.email && <div style={{ fontSize: '10px', color: '#6e7681' }}>✉️ {ag.email}</div>}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <div
                            onClick={() => handleCopy(ag.referral_code, `code_${ag.id}`)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              background: '#21262d',
                              border: '1px solid #388bfd',
                              color: '#58a6ff',
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontWeight: 700,
                              cursor: 'pointer'
                            }}
                            title="Click to copy code"
                          >
                            <span>{ag.referral_code}</span>
                            {copiedKey === `code_${ag.id}` ? <Check size={11} style={{ color: '#3fb950' }} /> : <Copy size={11} />}
                          </div>
                        </td>
                        <td style={{ padding: '12px 14px', fontWeight: 600, color: '#f0f6fc' }}>
                          {ag.discount_percent}% OFF
                        </td>
                        <td style={{ padding: '12px 14px', fontWeight: 700, color: '#3fb950' }}>
                          {ag.commission_percent}%
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{ fontWeight: 700, color: '#f0f6fc' }}>{ag.total_referrals} sales</span>
                          <div style={{ fontSize: '10px', color: '#8b949e' }}>Vol: ₹{Number(ag.total_sales_volume).toLocaleString('en-IN')}</div>
                        </td>
                        <td style={{ padding: '12px 14px', fontWeight: 700, color: '#f0f6fc' }}>
                          ₹{Number(ag.total_commission_earned).toLocaleString('en-IN')}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          {Number(ag.pending_commission_balance) > 0 ? (
                            <span style={{
                              background: 'rgba(210,153,34,0.2)',
                              color: '#d29922',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              fontWeight: 800
                            }}>
                              ₹{Number(ag.pending_commission_balance).toLocaleString('en-IN')}
                            </span>
                          ) : (
                            <span style={{ color: '#3fb950', fontSize: '11px' }}>✓ Settled</span>
                          )}
                        </td>
                        <td style={{ padding: '12px 14px', maxWidth: '200px' }}>
                          {ag.payout_upi && <div style={{ color: '#a5d6ff', fontSize: '11px', fontWeight: 600 }}>UPI: {ag.payout_upi}</div>}
                          {ag.payout_bank_details && <div style={{ color: '#8b949e', fontSize: '10px' }}>{ag.payout_bank_details}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: REFERRAL SALES & COMMISSIONS */}
          {activeTab === 'sales' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                    Referral Sales & Commission Payout Ledger
                  </h3>
                  <p style={{ fontSize: '12px', color: '#8b949e', margin: '2px 0 0 0' }}>
                    Track which client purchased with whose referral, and mark commissions as paid.
                  </p>
                </div>
                <button
                  onClick={() => setShowManualSaleModal(true)}
                  className="btn btn-secondary"
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Plus size={14} />
                  <span>+ Record Offline / Manual Sale</span>
                </button>
              </div>

              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ background: '#1f242c', color: '#8b949e', borderBottom: '1px solid #30363d' }}>
                      <th style={{ padding: '10px 14px' }}>Date</th>
                      <th style={{ padding: '10px 14px' }}>Customer Details</th>
                      <th style={{ padding: '10px 14px' }}>Plan</th>
                      <th style={{ padding: '10px 14px' }}>Sale Amount</th>
                      <th style={{ padding: '10px 14px' }}>Agent Name & Code</th>
                      <th style={{ padding: '10px 14px' }}>Commission</th>
                      <th style={{ padding: '10px 14px' }}>Payout Status</th>
                      <th style={{ padding: '10px 14px' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sales.map((s) => (
                      <tr key={s.id} style={{ borderBottom: '1px solid #21262d', color: '#c9d1d9' }}>
                        <td style={{ padding: '12px 14px', whiteSpace: 'nowrap' }}>{s.created_at?.slice(0, 16)}</td>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ fontWeight: 700, color: '#f0f6fc' }}>{s.customer_name}</div>
                          <div style={{ fontSize: '11px', color: '#8b949e' }}>{s.customer_email || 'No Email'}</div>
                          {s.customer_phone && <div style={{ fontSize: '10px', color: '#6e7681' }}>{s.customer_phone}</div>}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{ background: '#21262d', padding: '2px 8px', borderRadius: '4px', fontWeight: 700, color: '#f0f6fc' }}>
                            {s.plan_name}
                          </span>
                        </td>
                        <td style={{ padding: '12px 14px', fontWeight: 800, color: '#f0f6fc' }}>
                          ₹{Number(s.sale_amount).toLocaleString('en-IN')}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ fontWeight: 700, color: '#58a6ff' }}>{s.agent_name}</div>
                          <div style={{ fontSize: '11px', color: '#8b949e' }}>Code: <strong>{s.referral_code}</strong></div>
                          {s.agent_upi && <div style={{ fontSize: '10px', color: '#3fb950' }}>UPI: {s.agent_upi}</div>}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ fontWeight: 800, color: '#3fb950', fontSize: '13px' }}>
                            ₹{Number(s.commission_amount).toLocaleString('en-IN')}
                          </div>
                          <div style={{ fontSize: '10px', color: '#8b949e' }}>({s.commission_rate}%)</div>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{
                            padding: '3px 9px',
                            borderRadius: '12px',
                            fontSize: '11px',
                            fontWeight: 700,
                            background: s.status === 'PAID' ? 'rgba(35,134,54,0.2)' : 'rgba(210,153,34,0.2)',
                            color: s.status === 'PAID' ? '#3fb950' : '#d29922',
                            border: s.status === 'PAID' ? '1px solid rgba(35,134,54,0.4)' : '1px solid rgba(210,153,34,0.4)'
                          }}>
                            {s.status}
                          </span>
                          {s.payout_ref && (
                            <div style={{ fontSize: '10px', color: '#8b949e', marginTop: '3px' }}>
                              Ref: {s.payout_ref}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          {s.status === 'PENDING' ? (
                            <button
                              onClick={() => {
                                setSelectedSaleForPayout(s);
                                setPayoutRef(`UPI-${Date.now().toString().slice(-6)}`);
                                setShowPayoutModal(true);
                              }}
                              className="btn btn-sm"
                              style={{
                                background: '#238636',
                                color: '#fff',
                                fontWeight: 700,
                                padding: '4px 10px',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer'
                              }}
                            >
                              Pay Commission
                            </button>
                          ) : (
                            <div style={{ fontSize: '11px', color: '#3fb950', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <CheckCircle2 size={12} />
                              <span>Paid on {s.payout_date?.slice(0, 10)}</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: ACTIVE USERS & LICENSES */}
          {activeTab === 'users' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                    Active Users & Installed License Directory
                  </h3>
                  <p style={{ fontSize: '12px', color: '#8b949e', margin: '2px 0 0 0' }}>
                    View all users who have active licenses, plan durations, and referral origin.
                  </p>
                </div>
                <button
                  onClick={() => setShowIssueLicenseModal(true)}
                  className="btn btn-primary"
                  style={{ background: '#238636', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Plus size={14} />
                  <span>+ Issue New License Key</span>
                </button>
              </div>

              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ background: '#1f242c', color: '#8b949e', borderBottom: '1px solid #30363d' }}>
                      <th style={{ padding: '10px 14px' }}>User Details</th>
                      <th style={{ padding: '10px 14px' }}>Plan</th>
                      <th style={{ padding: '10px 14px' }}>License Key</th>
                      <th style={{ padding: '10px 14px' }}>Status</th>
                      <th style={{ padding: '10px 14px' }}>Days Left</th>
                      <th style={{ padding: '10px 14px' }}>Referred By</th>
                      <th style={{ padding: '10px 14px' }}>Activated Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} style={{ borderBottom: '1px solid #21262d', color: '#c9d1d9' }}>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '13px' }}>{u.user_name}</div>
                          <div style={{ fontSize: '11px', color: '#8b949e' }}>✉️ {u.user_email}</div>
                          {u.user_phone && <div style={{ fontSize: '10px', color: '#6e7681' }}>📞 {u.user_phone}</div>}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{
                            padding: '3px 8px',
                            borderRadius: '4px',
                            fontWeight: 700,
                            background: u.plan_name === 'VIP_LIFETIME' ? 'rgba(210,153,34,0.2)' : 'rgba(56,139,253,0.15)',
                            color: u.plan_name === 'VIP_LIFETIME' ? '#d29922' : '#58a6ff',
                            border: u.plan_name === 'VIP_LIFETIME' ? '1px solid #d29922' : '1px solid #388bfd'
                          }}>
                            {u.plan_name}
                          </span>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <div
                            onClick={() => handleCopy(u.license_key, `key_${u.id}`)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              background: '#21262d',
                              padding: '3px 8px',
                              borderRadius: '4px',
                              fontFamily: 'monospace',
                              fontSize: '11px',
                              color: '#c9d1d9',
                              cursor: 'pointer'
                            }}
                            title="Click to copy full key"
                          >
                            <span>{u.license_key.length > 24 ? u.license_key.slice(0, 18) + '...' : u.license_key}</span>
                            {copiedKey === `key_${u.id}` ? <Check size={11} style={{ color: '#3fb950' }} /> : <Copy size={11} />}
                          </div>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '10px',
                            fontSize: '10px',
                            fontWeight: 700,
                            background: u.status === 'ACTIVE' ? 'rgba(35,134,54,0.2)' : 'rgba(248,81,73,0.2)',
                            color: u.status === 'ACTIVE' ? '#3fb950' : '#f85149'
                          }}>
                            {u.status}
                          </span>
                        </td>
                        <td style={{ padding: '12px 14px', fontWeight: 700, color: '#f0f6fc' }}>
                          {u.days_remaining > 3000 ? 'Lifetime' : `${u.days_remaining} days`}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          {u.referral_code ? (
                            <div>
                              <span style={{ color: '#58a6ff', fontWeight: 600 }}>{u.agent_name || u.referral_code}</span>
                              <div style={{ fontSize: '10px', color: '#8b949e' }}>Code: {u.referral_code}</div>
                            </div>
                          ) : (
                            <span style={{ color: '#6e7681', fontSize: '11px' }}>Direct Organic</span>
                          )}
                        </td>
                        <td style={{ padding: '12px 14px', whiteSpace: 'nowrap', color: '#8b949e' }}>
                          {u.activated_at?.slice(0, 10)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 5: GATEWAY & SETTINGS */}
          {activeTab === 'settings' && (
            <div style={{ maxWidth: '650px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '24px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', marginBottom: '6px' }}>
                  Razorpay Payment Gateway Credentials
                </h3>
                <p style={{ fontSize: '12px', color: '#8b949e', marginBottom: '20px', lineHeight: 1.4 }}>
                  Configure your live Razorpay API Key ID and Key Secret to accept automated payments from clients via UPI, Credit/Debit cards, Netbanking, and Wallets.
                </p>

                <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#8b949e', marginBottom: '6px', textTransform: 'uppercase' }}>
                      Razorpay Key ID
                    </label>
                    <input
                      type="text"
                      placeholder="rzp_live_xxxxxxxxxxxxxx"
                      value={razorpayKeyId}
                      onChange={(e) => setRazorpayKeyId(e.target.value)}
                      style={{
                        width: '100%',
                        background: '#0d1117',
                        border: '1px solid #30363d',
                        borderRadius: '6px',
                        padding: '10px 12px',
                        color: '#f0f6fc',
                        fontFamily: 'monospace',
                        fontSize: '13px'
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#8b949e', marginBottom: '6px', textTransform: 'uppercase' }}>
                      Razorpay Key Secret
                    </label>
                    <input
                      type="password"
                      placeholder="Your Razorpay Secret Key"
                      value={razorpayKeySecret}
                      onChange={(e) => setRazorpayKeySecret(e.target.value)}
                      style={{
                        width: '100%',
                        background: '#0d1117',
                        border: '1px solid #30363d',
                        borderRadius: '6px',
                        padding: '10px 12px',
                        color: '#f0f6fc',
                        fontFamily: 'monospace',
                        fontSize: '13px'
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
                    <input
                      type="checkbox"
                      id="rzp_en"
                      checked={razorpayEnabled}
                      onChange={(e) => setRazorpayEnabled(e.target.checked)}
                      style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                    />
                    <label htmlFor="rzp_en" style={{ fontSize: '13px', color: '#f0f6fc', cursor: 'pointer' }}>
                      Enable Razorpay Gateway for Client Checkouts
                    </label>
                  </div>

                  {settingsSuccess && (
                    <div style={{ background: 'rgba(35,134,54,0.2)', border: '1px solid rgba(35,134,54,0.4)', color: '#3fb950', padding: '10px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircle2 size={16} />
                      <span>Payment gateway configuration updated successfully!</span>
                    </div>
                  )}

                  <div style={{ marginTop: '12px' }}>
                    <button type="submit" className="btn btn-primary" style={{ background: '#238636', padding: '10px 20px', fontWeight: 700 }}>
                      Save Gateway Settings
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* SUB-MODAL 1: ADD AGENT */}
      {showAddAgentModal && (
        <div className="modal-overlay" style={{ zIndex: 1200 }}>
          <div className="modal-content" style={{ maxWidth: '520px', padding: '24px', background: '#161b22', border: '1px solid #30363d' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                + Add New Marketing Partner (Agent)
              </h3>
              <button onClick={() => setShowAddAgentModal(false)} style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateAgent} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Agent / Studio Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ramesh Photo Studio"
                  value={newAgent.name}
                  onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Phone / WhatsApp *</label>
                  <input
                    type="text"
                    required
                    placeholder="+91 98765 43210"
                    value={newAgent.phone}
                    onChange={(e) => setNewAgent({ ...newAgent, phone: e.target.value })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Referral Code</label>
                  <input
                    type="text"
                    placeholder="e.g. RAMESH20 (Auto if blank)"
                    value={newAgent.referral_code}
                    onChange={(e) => setNewAgent({ ...newAgent, referral_code: e.target.value.toUpperCase() })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff', textTransform: 'uppercase' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Customer Discount %</label>
                  <input
                    type="number"
                    value={newAgent.discount_percent}
                    onChange={(e) => setNewAgent({ ...newAgent, discount_percent: Number(e.target.value) })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Agent Commission %</label>
                  <input
                    type="number"
                    value={newAgent.commission_percent}
                    onChange={(e) => setNewAgent({ ...newAgent, commission_percent: Number(e.target.value) })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Agent Payout UPI ID</label>
                <input
                  type="text"
                  placeholder="e.g. ramesh@paytm or 9876543210@upi"
                  value={newAgent.payout_upi}
                  onChange={(e) => setNewAgent({ ...newAgent, payout_upi: e.target.value })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Bank Account & IFSC (Optional)</label>
                <input
                  type="text"
                  placeholder="Bank name, Account number, IFSC"
                  value={newAgent.payout_bank_details}
                  onChange={(e) => setNewAgent({ ...newAgent, payout_bank_details: e.target.value })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={() => setShowAddAgentModal(false)} className="btn btn-secondary" style={{ flex: 1 }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: '#238636' }}>
                  Save Agent
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SUB-MODAL 2: PAY COMMISSION */}
      {showPayoutModal && selectedSaleForPayout && (
        <div className="modal-overlay" style={{ zIndex: 1200 }}>
          <div className="modal-content" style={{ maxWidth: '460px', padding: '24px', background: '#161b22', border: '1px solid #30363d' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                💳 Record Commission Payout
              </h3>
              <button onClick={() => setShowPayoutModal(false)} style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ background: '#0d1117', padding: '14px', borderRadius: '6px', marginBottom: '16px', border: '1px solid #21262d' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ color: '#8b949e', fontSize: '12px' }}>Agent Name:</span>
                <span style={{ color: '#f0f6fc', fontWeight: 700, fontSize: '13px' }}>{selectedSaleForPayout.agent_name}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ color: '#8b949e', fontSize: '12px' }}>Agent UPI:</span>
                <span style={{ color: '#a5d6ff', fontWeight: 700, fontSize: '12px' }}>{selectedSaleForPayout.agent_upi || 'Not provided'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #21262d', paddingTop: '8px' }}>
                <span style={{ color: '#8b949e', fontSize: '12px' }}>Commission Amount:</span>
                <span style={{ color: '#3fb950', fontWeight: 800, fontSize: '16px' }}>
                  ₹{Number(selectedSaleForPayout.commission_amount).toLocaleString('en-IN')}
                </span>
              </div>
            </div>

            <form onSubmit={handlePayCommission} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Transaction / UTR / Reference ID *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. UTR-98218204 or UPI Ref ID"
                  value={payoutRef}
                  onChange={(e) => setPayoutRef(e.target.value)}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Notes / Comments</label>
                <input
                  type="text"
                  placeholder="e.g. Sent via Google Pay"
                  value={payoutNotes}
                  onChange={(e) => setPayoutNotes(e.target.value)}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={() => setShowPayoutModal(false)} className="btn btn-secondary" style={{ flex: 1 }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: '#238636' }}>
                  Mark as Paid
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SUB-MODAL 3: RECORD MANUAL SALE */}
      {showManualSaleModal && (
        <div className="modal-overlay" style={{ zIndex: 1200 }}>
          <div className="modal-content" style={{ maxWidth: '480px', padding: '24px', background: '#161b22', border: '1px solid #30363d' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                + Record Offline Referral Sale
              </h3>
              <button onClick={() => setShowManualSaleModal(false)} style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleRecordManualSale} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Referral Code Used *</label>
                <select
                  required
                  value={manualSale.referral_code}
                  onChange={(e) => setManualSale({ ...manualSale, referral_code: e.target.value })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                >
                  <option value="">Select Agent Referral Code</option>
                  {agents.map((a) => (
                    <option key={a.id} value={a.referral_code}>
                      {a.referral_code} - {a.name} ({a.commission_percent}% comm)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Customer Name *</label>
                <input
                  type="text"
                  required
                  placeholder="Client's Full Name"
                  value={manualSale.customer_name}
                  onChange={(e) => setManualSale({ ...manualSale, customer_name: e.target.value })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Customer Email</label>
                  <input
                    type="email"
                    placeholder="client@gmail.com"
                    value={manualSale.customer_email}
                    onChange={(e) => setManualSale({ ...manualSale, customer_email: e.target.value })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Customer Phone</label>
                  <input
                    type="text"
                    placeholder="+91 98290 12345"
                    value={manualSale.customer_phone}
                    onChange={(e) => setManualSale({ ...manualSale, customer_phone: e.target.value })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Plan</label>
                  <select
                    value={manualSale.plan_name}
                    onChange={(e) => setManualSale({ ...manualSale, plan_name: e.target.value })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  >
                    <option value="PRO">PRO Plan</option>
                    <option value="STUDIO">STUDIO Plan</option>
                    <option value="VIP_LIFETIME">VIP Lifetime</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Sale Amount Received (₹) *</label>
                  <input
                    type="number"
                    required
                    value={manualSale.sale_amount}
                    onChange={(e) => setManualSale({ ...manualSale, sale_amount: Number(e.target.value) })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={() => setShowManualSaleModal(false)} className="btn btn-secondary" style={{ flex: 1 }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: '#238636' }}>
                  Record Sale
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SUB-MODAL 4: ISSUE LICENSE */}
      {showIssueLicenseModal && (
        <div className="modal-overlay" style={{ zIndex: 1200 }}>
          <div className="modal-content" style={{ maxWidth: '480px', padding: '24px', background: '#161b22', border: '1px solid #30363d' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc', margin: 0 }}>
                + Issue Official License Key
              </h3>
              <button onClick={() => setShowIssueLicenseModal(false)} style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleIssueLicense} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Customer Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Suraj Sharma"
                  value={manualLicense.user_name}
                  onChange={(e) => setManualLicense({ ...manualLicense, user_name: e.target.value })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Customer Email *</label>
                <input
                  type="email"
                  required
                  placeholder="suraj@photomedia.in"
                  value={manualLicense.user_email}
                  onChange={(e) => setManualLicense({ ...manualLicense, user_email: e.target.value })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Plan</label>
                  <select
                    value={manualLicense.plan_name}
                    onChange={(e) => setManualLicense({ ...manualLicense, plan_name: e.target.value })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  >
                    <option value="PRO">PRO Plan (1 Device)</option>
                    <option value="STUDIO">STUDIO Plan (3 Devices)</option>
                    <option value="VIP_LIFETIME">VIP Lifetime Plan</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Validity Days</label>
                  <input
                    type="number"
                    value={manualLicense.days}
                    onChange={(e) => setManualLicense({ ...manualLicense, days: Number(e.target.value) })}
                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>Referred By (Optional Agent Code)</label>
                <input
                  type="text"
                  placeholder="e.g. RAJESH20"
                  value={manualLicense.referral_code}
                  onChange={(e) => setManualLicense({ ...manualLicense, referral_code: e.target.value.toUpperCase() })}
                  style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', padding: '8px 10px', borderRadius: '6px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={() => setShowIssueLicenseModal(false)} className="btn btn-secondary" style={{ flex: 1 }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: '#238636' }}>
                  Generate & Activate Key
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
