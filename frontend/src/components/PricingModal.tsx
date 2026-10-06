import React, { useState, useEffect } from 'react';
import {
  X, Check, Crown, Sparkles, Shield, Gift, Key, Tag,
  ArrowRight, CheckCircle2, AlertCircle, Copy, Laptop, RefreshCw, Zap, CreditCard, Lock
} from 'lucide-react';
import { api } from '../api';
import { LicenseStatus, CouponVerifyResult } from '../types';

interface PricingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLicenseUpdated?: (license: LicenseStatus) => void;
  onOpenAdminSettings?: () => void;
}

declare global {
  interface Window {
    Razorpay?: any;
  }
}

export const PricingModal: React.FC<PricingModalProps> = ({
  isOpen,
  onClose,
  onLicenseUpdated,
  onOpenAdminSettings
}) => {
  const [activeTab, setActiveTab] = useState<'plans' | 'activate'>('plans');
  const [currency, setCurrency] = useState<'INR' | 'USD'>('INR');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('yearly');
  
  // License state
  const [license, setLicense] = useState<LicenseStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Referral / Coupon state
  const [couponCode, setCouponCode] = useState('');
  const [appliedCoupon, setAppliedCoupon] = useState<CouponVerifyResult | null>(null);
  const [isVerifyingCoupon, setIsVerifyingCoupon] = useState(false);

  // Customer contact details for invoice / Razorpay
  const [clientName, setClientName] = useState('');
  const [clientEmail, setClientEmail] = useState('');
  const [clientPhone, setClientPhone] = useState('');

  // Offline Key activation state
  const [inputKey, setInputKey] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadLicense();
      setStatusMessage(null);
      loadRazorpayScript();
    }
  }, [isOpen]);

  const loadRazorpayScript = () => {
    if (typeof window !== 'undefined' && !window.Razorpay) {
      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      document.body.appendChild(script);
    }
  };

  const loadLicense = async () => {
    try {
      const data = await api.getLicenseStatus();
      setLicense(data);
    } catch (err) {
      console.error('Failed to load license status', err);
    }
  };

  if (!isOpen) return null;

  // Base Prices
  const basePrices = {
    INR: {
      pro_monthly: 499,
      pro_yearly: 3499,
      studio_monthly: 999,
      studio_yearly: 6999,
      event: 299
    },
    USD: {
      pro_monthly: 7,
      pro_yearly: 45,
      studio_monthly: 14,
      studio_yearly: 89,
      event: 5
    }
  };

  const currSymbol = currency === 'INR' ? '₹' : '$';
  const currPrices = basePrices[currency];

  // Calculate pricing with applied referral discount
  const getPlanPrice = (plan: 'pro' | 'studio') => {
    const original = billingCycle === 'yearly' ? currPrices[`${plan}_yearly`] : currPrices[`${plan}_monthly`];
    if (!appliedCoupon || !appliedCoupon.valid || !appliedCoupon.discount_percent) {
      return { original, final: original, hasDiscount: false };
    }
    const discount = Math.round((original * appliedCoupon.discount_percent) / 100);
    const final = Math.max(0, original - discount);
    return { original, final, hasDiscount: true, discountPercent: appliedCoupon.discount_percent };
  };

  const proPrice = getPlanPrice('pro');
  const studioPrice = getPlanPrice('studio');

  // Apply Coupon
  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) return;
    setIsVerifyingCoupon(true);
    setStatusMessage(null);
    try {
      const res = await api.verifyCoupon(couponCode, 'PRO', billingCycle, currency);
      if (res.valid) {
        setAppliedCoupon(res);
        setStatusMessage({ text: res.message || 'Coupon applied successfully!', type: 'success' });
      } else {
        setAppliedCoupon(null);
        setStatusMessage({ text: res.message || 'Invalid coupon code', type: 'error' });
      }
    } catch (err: any) {
      setAppliedCoupon(null);
      setStatusMessage({ text: err.message || 'Error checking coupon', type: 'error' });
    } finally {
      setIsVerifyingCoupon(false);
    }
  };

  // Launch Razorpay Checkout & Automatic Access
  const handlePayWithRazorpay = async (planId: 'PRO' | 'STUDIO') => {
    setIsProcessingPayment(true);
    setStatusMessage(null);

    try {
      // 1. Create order on backend
      const order = await api.createRazorpayOrder(
        planId,
        billingCycle,
        clientName || 'Subscriber',
        clientEmail || 'client@example.com',
        appliedCoupon?.code,
        currency
      );

      // Load Razorpay JS SDK dynamically if not already available
      const loadRazorpayScript = (): Promise<boolean> => {
        return new Promise((resolve) => {
          if (typeof window !== 'undefined' && (window as any).Razorpay) {
            resolve(true);
            return;
          }
          const script = document.createElement('script');
          script.src = 'https://checkout.razorpay.com/v1/checkout.js';
          script.onload = () => resolve(true);
          script.onerror = () => resolve(false);
          document.body.appendChild(script);
        });
      };

      const isLoaded = await loadRazorpayScript();
      if (!isLoaded || !(window as any).Razorpay) {
        setIsProcessingPayment(false);
        setStatusMessage({
          text: 'Unable to reach Razorpay payment gateway. Please check your internet connection.',
          type: 'error'
        });
        return;
      }

      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'Ai PhotoFlow',
        description: `${planId} Plan (${billingCycle}) - Official License`,
        order_id: order.order_id.startsWith('order_') && !order.is_test_mode ? order.order_id : undefined,
        prefill: {
          name: clientName || '',
          email: clientEmail || '',
          contact: clientPhone || ''
        },
        theme: {
          color: '#2563eb'
        },
        modal: {
          ondismiss: function () {
            setIsProcessingPayment(false);
            setStatusMessage({
              text: 'Payment cancelled. Your plan was not changed.',
              type: 'info'
            });
          }
        },
        handler: async function (response: any) {
          try {
            // Verify real payment on backend with cryptographic signature
            const verifyRes = await api.verifyRazorpayPayment(
              order.order_id,
              response.razorpay_payment_id,
              response.razorpay_signature,
              clientName,
              clientEmail
            );

            setStatusMessage({
              text: verifyRes.message || 'Payment Successful! Your Plan is now Active!',
              type: 'success'
            });

            if (verifyRes.license) {
              setLicense(verifyRes.license);
              if (onLicenseUpdated) onLicenseUpdated(verifyRes.license);
            }
            loadLicense();
          } catch (vErr: any) {
            setStatusMessage({ text: vErr.message || 'Payment verification failed', type: 'error' });
          } finally {
            setIsProcessingPayment(false);
          }
        }
      };

      const rzp = new (window as any).Razorpay(options);
      rzp.on('payment.failed', function (resp: any) {
        setIsProcessingPayment(false);
        setStatusMessage({ text: resp.error.description || 'Payment Failed or Cancelled', type: 'error' });
      });
      rzp.open();
    } catch (err: any) {
      setIsProcessingPayment(false);
      setStatusMessage({ text: err.message || 'Failed to initiate payment', type: 'error' });
    }
  };

  // Activate Key (Offline / Voucher Fallback)
  const handleActivateKey = async () => {
    if (!inputKey.trim()) {
      setStatusMessage({ text: 'Please enter your license key', type: 'error' });
      return;
    }
    setIsLoading(true);
    setStatusMessage(null);
    try {
      const res = await api.activateLicense(inputKey.trim(), clientName, clientEmail);
      setStatusMessage({ text: res.message || 'License activated successfully!', type: 'success' });
      if (res.license) {
        setLicense(res.license);
        if (onLicenseUpdated) onLicenseUpdated(res.license);
      }
      loadLicense();
    } catch (err: any) {
      setStatusMessage({ text: err.message || 'Activation failed', type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(5, 7, 12, 0.85)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: '#12151e',
        border: '1px solid #283042',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '920px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 40px rgba(59, 130, 246, 0.15)',
        overflow: 'hidden',
        color: '#f1f5f9'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px 16px',
          borderBottom: '1px solid #202636',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'linear-gradient(180deg, #181d2a 0%, #12151e 100%)'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                padding: '6px',
                borderRadius: '8px',
                color: '#fff',
                boxShadow: '0 2px 8px rgba(245, 158, 11, 0.4)'
              }}>
                <Crown size={18} />
              </div>
              <h2 style={{ margin: 0, fontSize: '19px', fontWeight: 700, letterSpacing: '-0.3px' }}>
                Ai PhotoFlow Plans & Instant Access
              </h2>
              {license?.is_vip ? (
                <span style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  background: 'linear-gradient(90deg, #10b981, #059669)',
                  color: '#fff',
                  padding: '3px 8px',
                  borderRadius: '12px'
                }}>
                  👑 VIP LIFETIME FREE
                </span>
              ) : license?.plan === 'PRO' || license?.plan === 'STUDIO' ? (
                <span style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  background: 'linear-gradient(90deg, #3b82f6, #2563eb)',
                  color: '#fff',
                  padding: '3px 8px',
                  borderRadius: '12px'
                }}>
                  {license.plan} ACTIVE ({license.days_left}d left)
                </span>
              ) : (
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  background: '#1e293b',
                  color: '#94a3b8',
                  padding: '3px 8px',
                  borderRadius: '12px'
                }}>
                  Free Trial ({license?.days_left ?? 14} Days Left)
                </span>
              )}
            </div>
            <p style={{ margin: '4px 0 0 38px', fontSize: '13px', color: '#94a3b8' }}>
              UPI (GPay / PhonePe / Paytm), QR Code, Cards & NetBanking se instant automatic activation
            </p>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'color 0.2s'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation Tabs */}
        <div style={{
          display: 'flex',
          padding: '0 24px',
          background: '#141824',
          borderBottom: '1px solid #202636',
          gap: '8px'
        }}>
          <button
            onClick={() => setActiveTab('plans')}
            style={{
              padding: '12px 16px',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'plans' ? '2px solid #3b82f6' : '2px solid transparent',
              color: activeTab === 'plans' ? '#60a5fa' : '#94a3b8',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Sparkles size={14} />
            Plans & Instant Payment (Razorpay)
          </button>

          <button
            onClick={() => setActiveTab('activate')}
            style={{
              padding: '12px 16px',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'activate' ? '2px solid #3b82f6' : '2px solid transparent',
              color: activeTab === 'activate' ? '#60a5fa' : '#94a3b8',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Key size={14} />
            Have a License Key?
          </button>
        </div>

        {/* Status Notification */}
        {statusMessage && (
          <div style={{
            margin: '12px 24px 0',
            padding: '10px 14px',
            borderRadius: '8px',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: statusMessage.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${statusMessage.type === 'success' ? '#10b981' : '#ef4444'}`,
            color: statusMessage.type === 'success' ? '#34d399' : '#f87171'
          }}>
            {statusMessage.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{statusMessage.text}</span>
          </div>
        )}

        {/* Modal Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {activeTab === 'plans' && (
            <div>
              {/* Toggles: Currency & Billing */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '20px',
                flexWrap: 'wrap',
                gap: '12px'
              }}>
                {/* Billing Cycle Toggle */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: '#1a1f2c',
                  padding: '3px',
                  borderRadius: '10px',
                  border: '1px solid #2d3748'
                }}>
                  <button
                    onClick={() => setBillingCycle('monthly')}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '8px',
                      border: 'none',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      background: billingCycle === 'monthly' ? '#3b82f6' : 'transparent',
                      color: billingCycle === 'monthly' ? '#fff' : '#94a3b8'
                    }}
                  >
                    Monthly
                  </button>
                  <button
                    onClick={() => setBillingCycle('yearly')}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '8px',
                      border: 'none',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      background: billingCycle === 'yearly' ? '#3b82f6' : 'transparent',
                      color: billingCycle === 'yearly' ? '#fff' : '#94a3b8',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <span>Yearly</span>
                    <span style={{
                      fontSize: '10px',
                      background: '#10b981',
                      color: '#fff',
                      padding: '1px 6px',
                      borderRadius: '6px',
                      fontWeight: 700
                    }}>
                      Save 42%
                    </span>
                  </button>
                </div>

                {/* Currency Switcher */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 500 }}>Currency:</span>
                  <div style={{
                    display: 'flex',
                    background: '#1a1f2c',
                    padding: '3px',
                    borderRadius: '8px',
                    border: '1px solid #2d3748'
                  }}>
                    <button
                      onClick={() => setCurrency('INR')}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '6px',
                        border: 'none',
                        fontSize: '11px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        background: currency === 'INR' ? '#2563eb' : 'transparent',
                        color: currency === 'INR' ? '#fff' : '#94a3b8'
                      }}
                    >
                      INR (₹)
                    </button>
                    <button
                      onClick={() => setCurrency('USD')}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '6px',
                        border: 'none',
                        fontSize: '11px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        background: currency === 'USD' ? '#2563eb' : 'transparent',
                        color: currency === 'USD' ? '#fff' : '#94a3b8'
                      }}
                    >
                      USD ($)
                    </button>
                  </div>
                </div>
              </div>

              {/* Pricing Cards Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '16px',
                marginBottom: '20px'
              }}>
                {/* 1. Free Trial Card */}
                <div style={{
                  background: '#161a24',
                  borderRadius: '12px',
                  border: '1px solid #283042',
                  padding: '20px',
                  display: 'flex',
                  flexDirection: 'column'
                }}>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#94a3b8' }}>Starter Trial</div>
                  <div style={{ margin: '8px 0', display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                    <span style={{ fontSize: '26px', fontWeight: 800 }}>{currSymbol}0</span>
                    <span style={{ fontSize: '12px', color: '#64748b' }}>/ 14 Days</span>
                  </div>
                  <p style={{ fontSize: '11px', color: '#94a3b8', minHeight: '32px' }}>
                    Perfect for testing Ai PhotoFlow on your first wedding project.
                  </p>

                  <div style={{ height: '1px', background: '#242b3b', margin: '14px 0' }} />

                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 20px', flex: 1, fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#10b981" /> Upto 2,000 Photos
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#10b981" /> All 6 AI Culling Rules
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#10b981" /> Indian Skin Retouching
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#10b981" /> 100% Watermark Free
                    </li>
                  </ul>

                  <button
                    disabled
                    style={{
                      width: '100%',
                      padding: '9px',
                      background: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#94a3b8',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'default'
                    }}
                  >
                    Current Mode
                  </button>
                </div>

                {/* 2. Pro Photographer Card (POPULAR) */}
                <div style={{
                  background: 'linear-gradient(180deg, #1e2438 0%, #151928 100%)',
                  borderRadius: '12px',
                  border: '2px solid #3b82f6',
                  padding: '20px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  boxShadow: '0 10px 25px -5px rgba(59, 130, 246, 0.25)'
                }}>
                  <div style={{
                    position: 'absolute',
                    top: '-11px',
                    right: '18px',
                    background: 'linear-gradient(90deg, #3b82f6, #2563eb)',
                    color: '#fff',
                    padding: '2px 10px',
                    borderRadius: '10px',
                    fontSize: '10px',
                    fontWeight: 700,
                    letterSpacing: '0.5px',
                    textTransform: 'uppercase'
                  }}>
                    Most Popular
                  </div>

                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#60a5fa' }}>Pro Photographer</div>
                  <div style={{ margin: '8px 0', display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                    {proPrice.hasDiscount && (
                      <span style={{ fontSize: '16px', color: '#64748b', textDecoration: 'line-through' }}>
                        {currSymbol}{proPrice.original.toLocaleString()}
                      </span>
                    )}
                    <span style={{ fontSize: '28px', fontWeight: 800, color: '#f8fafc' }}>
                      {currSymbol}{proPrice.final.toLocaleString()}
                    </span>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                      / {billingCycle === 'yearly' ? 'year' : 'month'}
                    </span>
                  </div>

                  <p style={{ fontSize: '11px', color: '#94a3b8', minHeight: '32px' }}>
                    Unlimited wedding culling and AI retouching for full-time wedding photographers.
                  </p>

                  <div style={{ height: '1px', background: '#2d3748', margin: '14px 0' }} />

                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 16px', flex: 1, fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, color: '#f1f5f9' }}>
                      <Check size={14} color="#3b82f6" /> <strong>Unlimited Photos & Events</strong>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#3b82f6" /> Real-time Blur & Face Detection
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#3b82f6" /> Automatic Indian Skin Tone Glow
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#3b82f6" /> Batch RAW / High-Res JPG Export
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#3b82f6" /> 1 Mac / Windows PC License
                    </li>
                  </ul>

                  <button
                    onClick={() => handlePayWithRazorpay('PRO')}
                    disabled={isProcessingPayment}
                    style={{
                      width: '100%',
                      padding: '11px',
                      background: 'linear-gradient(90deg, #2563eb, #1d4ed8)',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)'
                    }}
                  >
                    <CreditCard size={15} />
                    <span>{isProcessingPayment ? 'Processing...' : 'Pay with Razorpay (Instant)'}</span>
                  </button>
                  <div style={{ textAlign: 'center', fontSize: '10px', color: '#94a3b8', marginTop: '6px' }}>
                    ⚡ UPI • Google Pay • PhonePe • Cards • NetBanking
                  </div>
                </div>

                {/* 3. Studio & Agency Card */}
                <div style={{
                  background: '#161a24',
                  borderRadius: '12px',
                  border: '1px solid #283042',
                  padding: '20px',
                  display: 'flex',
                  flexDirection: 'column'
                }}>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#f59e0b' }}>Studio & Agency</div>
                  <div style={{ margin: '8px 0', display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                    {studioPrice.hasDiscount && (
                      <span style={{ fontSize: '16px', color: '#64748b', textDecoration: 'line-through' }}>
                        {currSymbol}{studioPrice.original.toLocaleString()}
                      </span>
                    )}
                    <span style={{ fontSize: '28px', fontWeight: 800 }}>
                      {currSymbol}{studioPrice.final.toLocaleString()}
                    </span>
                    <span style={{ fontSize: '12px', color: '#64748b' }}>
                      / {billingCycle === 'yearly' ? 'year' : 'month'}
                    </span>
                  </div>

                  <p style={{ fontSize: '11px', color: '#94a3b8', minHeight: '32px' }}>
                    Multi-system activation for busy photo studios, editing labs and agencies.
                  </p>

                  <div style={{ height: '1px', background: '#242b3b', margin: '14px 0' }} />

                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 16px', flex: 1, fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                      <Check size={14} color="#f59e0b" /> <strong>3 Macs / PCs Simultaneous</strong>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#f59e0b" /> Everything in Pro Plan
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#f59e0b" /> Multi-Project Batch Queue
                    </li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} color="#f59e0b" /> Priority VIP WhatsApp Support
                    </li>
                  </ul>

                  <button
                    onClick={() => handlePayWithRazorpay('STUDIO')}
                    disabled={isProcessingPayment}
                    style={{
                      width: '100%',
                      padding: '11px',
                      background: '#1e293b',
                      border: '1px solid #3b82f6',
                      borderRadius: '8px',
                      color: '#60a5fa',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px'
                    }}
                  >
                    <CreditCard size={14} />
                    <span>{isProcessingPayment ? 'Processing...' : 'Pay with Razorpay (Instant)'}</span>
                  </button>
                  <div style={{ textAlign: 'center', fontSize: '10px', color: '#94a3b8', marginTop: '6px' }}>
                    ⚡ UPI • Google Pay • PhonePe • Cards • NetBanking
                  </div>
                </div>
              </div>

              {/* Referral / Promo Code Section */}
              <div style={{
                background: '#151923',
                border: '1px solid #283042',
                borderRadius: '10px',
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ background: '#252e42', padding: '6px', borderRadius: '6px', color: '#60a5fa' }}>
                    <Gift size={16} />
                  </div>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 600 }}>Have a Referral or Discount Coupon?</div>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                      Enter referral code for instant discount before Razorpay checkout. Try: <strong style={{ color: '#60a5fa' }}>ANIL50</strong>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="text"
                    value={couponCode}
                    onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                    placeholder="Enter Coupon / Referral"
                    style={{
                      background: '#0d1017',
                      border: '1px solid #2d3748',
                      borderRadius: '6px',
                      padding: '6px 12px',
                      fontSize: '12px',
                      color: '#fff',
                      fontWeight: 700,
                      letterSpacing: '1px',
                      outline: 'none',
                      width: '180px'
                    }}
                  />
                  <button
                    onClick={handleApplyCoupon}
                    disabled={isVerifyingCoupon || !couponCode.trim()}
                    style={{
                      background: '#2563eb',
                      border: 'none',
                      borderRadius: '6px',
                      padding: '7px 14px',
                      color: '#fff',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    {isVerifyingCoupon ? 'Checking...' : 'Apply Code'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'activate' && (
            <div style={{ maxWidth: '540px', margin: '10px auto' }}>
              <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 10px',
                  color: '#fff'
                }}>
                  <Key size={22} />
                </div>
                <h3 style={{ margin: '0 0 6px', fontSize: '17px', fontWeight: 700 }}>Already Have a License Key?</h3>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                  Enter the offline license key received directly from Anil Sharma / Studio Admin to activate without Razorpay.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
                    License Key *
                  </label>
                  <input
                    type="text"
                    value={inputKey}
                    onChange={(e) => setInputKey(e.target.value.toUpperCase())}
                    placeholder="e.g. APF-PRO-YEAR-XXXX-XXXX or APF-VIP-XXXX"
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      background: '#161a24',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      padding: '10px 14px',
                      fontSize: '14px',
                      fontWeight: 700,
                      fontFamily: 'monospace',
                      color: '#f8fafc',
                      outline: 'none',
                      letterSpacing: '1px'
                    }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>
                      Photographer / Studio Name (Optional)
                    </label>
                    <input
                      type="text"
                      value={clientName}
                      onChange={(e) => setClientName(e.target.value)}
                      placeholder="Sharma Wedding Films"
                      style={{
                        width: '100%',
                        boxSizing: 'border-box',
                        background: '#161a24',
                        border: '1px solid #283042',
                        borderRadius: '6px',
                        padding: '8px 10px',
                        fontSize: '12px',
                        color: '#f8fafc',
                        outline: 'none'
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>
                      Email Address (Optional)
                    </label>
                    <input
                      type="email"
                      value={clientEmail}
                      onChange={(e) => setClientEmail(e.target.value)}
                      placeholder="studio@example.com"
                      style={{
                        width: '100%',
                        boxSizing: 'border-box',
                        background: '#161a24',
                        border: '1px solid #283042',
                        borderRadius: '6px',
                        padding: '8px 10px',
                        fontSize: '12px',
                        color: '#f8fafc',
                        outline: 'none'
                      }}
                    />
                  </div>
                </div>

                <button
                  onClick={handleActivateKey}
                  disabled={isLoading || !inputKey.trim()}
                  style={{
                    width: '100%',
                    padding: '11px',
                    background: 'linear-gradient(90deg, #2563eb, #1d4ed8)',
                    border: 'none',
                    borderRadius: '8px',
                    color: '#fff',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    marginTop: '8px',
                    boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)'
                  }}
                >
                  {isLoading ? 'Activating License...' : 'Activate License Now'}
                </button>

                <div style={{
                  background: '#141822',
                  border: '1px solid #242c3d',
                  borderRadius: '8px',
                  padding: '12px',
                  marginTop: '10px',
                  fontSize: '12px',
                  color: '#94a3b8'
                }}>
                  <div style={{ fontWeight: 600, color: '#cbd5e1', marginBottom: '4px' }}>Current Machine Status:</div>
                  <div>• Plan: <strong style={{ color: '#60a5fa' }}>{license?.plan || 'Free Trial'}</strong></div>
                  <div>• Status: <span style={{ color: license?.is_active ? '#34d399' : '#f87171' }}>{license?.status || 'Active'}</span></div>
                  <div>• Expiry: {license?.expires_at ? license.expires_at : (license?.is_vip ? 'Never (Lifetime Free Access)' : '14-Day Free Period')}</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 24px',
          borderTop: '1px solid #202636',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#10131c',
          fontSize: '12px',
          color: '#64748b'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              onClick={() => {
                if (onOpenAdminSettings) {
                  onClose();
                  onOpenAdminSettings();
                }
              }}
              style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              title="Admin Portal (Anil Sharma)"
            >
              <Lock size={13} style={{ color: '#10b981' }} />
            </span>
            <span>Secure 256-bit encrypted Razorpay payment gateway</span>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '6px 14px',
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '6px',
              color: '#cbd5e1',
              fontSize: '12px',
              cursor: 'pointer'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
