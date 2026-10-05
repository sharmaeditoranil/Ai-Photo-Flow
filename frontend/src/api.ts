import { Project, Photo, BatchJob, EditParameters, UserSelection } from './types';

const API_BASE = (typeof window !== 'undefined' && window.location.protocol === 'file:')
  ? 'http://127.0.0.1:8000/api'
  : '/api';

export const api = {
  // Projects
  async getProjects(): Promise<Project[]> {
    const res = await fetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  async getProject(id: number): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project details');
    return res.json();
  },

  async deleteProject(projectId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${projectId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete project');
  },

  async importFolder(folderPath: string, projectName?: string): Promise<{ project_id: number; total_photos: number }> {
    const res = await fetch(`${API_BASE}/projects/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath, project_name: projectName }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to import folder');
    }
    return res.json();
  },

  // Photos
  async getPhotos(projectId: number, category = 'ALL', starRating?: number, scene?: string, sort = 'ai_score_desc'): Promise<Photo[]> {
    const params = new URLSearchParams({ category, sort });
    if (starRating && starRating > 0) params.append('star_rating', starRating.toString());
    if (scene && scene !== 'ALL') params.append('scene', scene);

    const res = await fetch(`${API_BASE}/projects/${projectId}/photos?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch photos');
    return res.json();
  },

  async getPhoto(photoId: number): Promise<Photo> {
    const res = await fetch(`${API_BASE}/photos/${photoId}`);
    if (!res.ok) throw new Error('Failed to fetch photo');
    return res.json();
  },

  async getDuplicateGroupPhotos(projectId: number, groupId: string): Promise<Photo[]> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/duplicate-groups/${encodeURIComponent(groupId)}`);
    if (!res.ok) throw new Error('Failed to fetch duplicate group photos');
    return res.json();
  },

  async updateSelection(photoId: number, selection: UserSelection): Promise<void> {
    await fetch(`${API_BASE}/photos/${photoId}/selection`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_selection: selection }),
    });
  },

  async updateRating(photoId: number, rating: number): Promise<void> {
    await fetch(`${API_BASE}/photos/${photoId}/rating`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ star_rating: rating }),
    });
  },

  async deletePhoto(photoId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/photos/${photoId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete photo');
  },

  async deletePhotosBatch(photoIds: number[]): Promise<{ deleted_count: number }> {
    const res = await fetch(`${API_BASE}/photos/batch`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ photo_ids: photoIds }),
    });
    if (!res.ok) throw new Error('Failed to delete photos');
    return res.json();
  },

  async updateEdits(photoId: number, edits: EditParameters): Promise<void> {
    await fetch(`${API_BASE}/photos/${photoId}/edits`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(edits),
    });
  },

  async resetEdits(photoId: number): Promise<void> {
    await fetch(`${API_BASE}/photos/${photoId}/reset-edits`, { method: 'POST' });
  },

  async autoEditSingle(photoId: number, presetName = 'Natural Wedding'): Promise<{ edit_params: EditParameters }> {
    const res = await fetch(`${API_BASE}/photos/${photoId}/auto-edit?preset_name=${encodeURIComponent(presetName)}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Auto edit failed');
    return res.json();
  },

  // Batch operations
  async startCulling(projectId: number): Promise<{ job_id: string }> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/cull`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to start culling');
    return res.json();
  },

  async reclusterProject(projectId: number): Promise<any> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/recluster`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to re-cluster project');
    return res.json();
  },

  async startAutoEdit(projectId: number, presetName: string, photoIds?: number[]): Promise<{ job_id: string }> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/auto-edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset_name: presetName, photo_ids: photoIds }),
    });
    if (!res.ok) throw new Error('Failed to start auto edit');
    return res.json();
  },

  async startExport(projectId: number, options: {
    output_folder: string;
    jpeg_quality?: number;
    max_resolution?: number;
    rename_pattern?: string;
    categories?: string[];
  }): Promise<{ job_id: string }> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options),
    });
    if (!res.ok) throw new Error('Failed to start export');
    return res.json();
  },

  async openFolder(folderPath: string): Promise<any> {
    const res = await fetch(`${API_BASE}/open-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath }),
    });
    if (!res.ok) throw new Error('Failed to open folder');
    return res.json();
  },

  // Job management
  async getJob(jobId: string): Promise<BatchJob> {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`);
    if (!res.ok) throw new Error('Failed to get job status');
    return res.json();
  },

  async pauseJob(jobId: string): Promise<void> {
    await fetch(`${API_BASE}/jobs/${jobId}/pause`, { method: 'POST' });
  },

  async resumeJob(jobId: string): Promise<void> {
    await fetch(`${API_BASE}/jobs/${jobId}/resume`, { method: 'POST' });
  },

  async cancelJob(jobId: string): Promise<void> {
    await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' });
  },

  // Media URLs
  getThumbnailUrl(photoId: number, t?: number): string {
    return `${API_BASE}/photos/${photoId}/thumbnail${t ? `?t=${t}` : ''}`;
  },

  getOriginalUrl(photoId: number): string {
    return `${API_BASE}/photos/${photoId}/original`;
  },

  getPreviewUrl(photoId: number, t?: number): string {
    return `${API_BASE}/photos/${photoId}/preview${t ? `?t=${t}` : ''}`;
  },

  async getPhotoshopStatus(): Promise<{ available: boolean; status_message: string; v2_ready: boolean }> {
    const res = await fetch(`${API_BASE}/integrations/photoshop`);
    return res.json();
  },

  async getSettings(): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error('Failed to get settings');
    return res.json();
  },

  async saveSettings(settings: any): Promise<void> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    if (!res.ok) throw new Error('Failed to save settings');
  },

  // Licensing & Pricing
  async getLicenseStatus(): Promise<any> {
    const res = await fetch(`${API_BASE}/license/status`);
    if (!res.ok) throw new Error('Failed to get license status');
    return res.json();
  },

  async verifyCoupon(code: string, planId: string, billingCycle: string, currency: string = 'INR'): Promise<any> {
    const res = await fetch(`${API_BASE}/license/verify-coupon`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, plan_id: planId, billing_cycle: billingCycle, currency }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to verify coupon');
    }
    return res.json();
  },

  async activateLicense(licenseKey: string, userName?: string, userEmail?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/license/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ license_key: licenseKey, user_name: userName, user_email: userEmail }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to activate license');
    }
    return res.json();
  },

  async adminGrantFree(adminPin: string, planType: string = 'VIP_LIFETIME', clientName?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/license/admin/grant-free`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_pin: adminPin, plan_type: planType, client_name: clientName }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Admin validation failed');
    }
    return res.json();
  },

  async adminGenerateKey(adminPin: string, planType: string = 'PRO', days: number = 365, clientName?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/license/admin/generate-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_pin: adminPin, plan_type: planType, days, client_name: clientName }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to generate key');
    }
    return res.json();
  },

  async adminCreateCoupon(adminPin: string, code: string, discountPercent: number, notes?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/license/admin/create-coupon`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_pin: adminPin, code, discount_percent: discountPercent, notes }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create coupon');
    }
    return res.json();
  },

  // Razorpay Payments
  async getPaymentConfig(): Promise<any> {
    const res = await fetch(`${API_BASE}/payment/config`);
    if (!res.ok) throw new Error('Failed to get payment config');
    return res.json();
  },

  async createRazorpayOrder(planId: string, billingCycle: string, customerName?: string, customerEmail?: string, couponCode?: string, currency: string = 'INR'): Promise<any> {
    const res = await fetch(`${API_BASE}/payment/create-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plan_id: planId,
        billing_cycle: billingCycle,
        customer_name: customerName,
        customer_email: customerEmail,
        coupon_code: couponCode,
        currency
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create payment order');
    }
    return res.json();
  },

  async verifyRazorpayPayment(orderId: string, paymentId: string, signature?: string, clientName?: string, clientEmail?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/payment/verify-payment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        order_id: orderId,
        payment_id: paymentId,
        signature,
        client_name: clientName,
        client_email: clientEmail
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Payment verification failed');
    }
    return res.json();
  },

  // Admin & Affiliate Marketing Management
  async getAdminOverview(): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/overview`);
    if (!res.ok) throw new Error('Failed to get admin overview');
    return res.json();
  },

  async getAdminAgents(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/admin/agents`);
    if (!res.ok) throw new Error('Failed to fetch agents');
    return res.json();
  },

  async createAdminAgent(data: any): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create agent');
    }
    return res.json();
  },

  async updateAdminAgent(agentId: number, data: any): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/agents/${agentId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update agent');
    }
    return res.json();
  },

  async deleteAdminAgent(agentId: number): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/agents/${agentId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete agent');
    return res.json();
  },

  async getAdminReferralSales(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/admin/referral-sales`);
    if (!res.ok) throw new Error('Failed to fetch referral sales');
    return res.json();
  },

  async recordManualReferralSale(data: any): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/referral-sales`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to record manual sale');
    }
    return res.json();
  },

  async payAdminCommission(saleId: number, payoutRef: string, notes?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/commissions/${saleId}/pay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ payout_ref: payoutRef, notes }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to mark commission paid');
    }
    return res.json();
  },

  async getAdminUsers(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/admin/users`);
    if (!res.ok) throw new Error('Failed to fetch active users');
    return res.json();
  },

  async issueAdminUserLicense(data: any): Promise<any> {
    const res = await fetch(`${API_BASE}/admin/users/issue-license`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to issue license');
    }
    return res.json();
  }
};



