export type AIRecommendation = 'BEST' | 'SELECTED' | 'REVIEW' | 'REJECT' | 'SIMILAR';
export type UserSelection = 'BEST' | 'SELECTED' | 'REVIEW' | 'REJECT' | 'UNRATED';
export type ExposureStatus = 'GOOD' | 'UNDER_EXPOSED' | 'OVER_EXPOSED';
export type EyesStatus = 'OPEN' | 'CLOSED' | 'NO_FACE' | 'PARTIAL';

export interface HealSpot {
  x: number;      // 0.0 - 1.0 (relative to image width)
  y: number;      // 0.0 - 1.0 (relative to image height)
  radius: number; // 0.005 - 0.05 (relative to min dimension)
}

// AI Skin Retouch block (mirrors backend/retouch/params.py)
export interface RetouchParams {
  enabled: boolean;
  preset: string;
  heal: { enabled: boolean; opacity: number; strength: number; faceSizePreset: 'AUTO' | 'SMALL' | 'MEDIUM' | 'LARGE' };
  mattifier: { enabled: boolean; opacity: number; strength: number; keepSheen: number; texturePreserve: number };
  skinMask: {
    auto: boolean; excludeFeatures: boolean; restrictToBody: boolean;
    tolerance: number; feather: number; opacity: number;
    colorSamples: { set: number[][]; expand: number[][]; exclude: number[][] };
  };
  skinDetails: {
    enabled: boolean; autoPortraitSize: boolean; portraitSize: number;
    amount: number; fine: number; medium: number; coarse: number; balance: number;
  };
  imperfections: {
    enabled: boolean; evenTone: number; redness: number; redBrightness: number;
    yellow: number; yellowBrightness: number; balance: number; eyeBags: number;
  };
  skinTone: {
    enabled: boolean; useSkinMask: boolean; hue: number; saturation: number;
    brightness: number; contrast: number; shadows: number; highlights: number;
  };
}

export interface RetouchPreset {
  name: string;
  description: string;
  params: RetouchParams;
}

// AI Auto White Balance block (mirrors backend/core/white_balance.py)
export interface AutoWhiteBalance {
  enabled: boolean;
  strength: number;           // 0..150 % of the detected correction
  gains: number[];            // linear RGB gains
  cast: string;               // e.g. "warm (yellow/orange) cast"
  confidence: number;         // 0..1
  kelvin: number | null;      // estimated light colour temperature
  grey_pixels?: number;
  faces?: number;
  skin_hue_before?: number | null;
  skin_hue_after?: number | null;
  notes?: string[];
}

export type RetouchMaskKind = 'off' | 'skin' | 'heal' | 'shine';

export interface EditParameters {
  exposure: number;
  subject_exposure?: number;
  temperature: number;
  tint: number;
  contrast: number;
  highlights: number;
  shadows: number;
  whites: number;
  blacks: number;
  vibrance: number;
  saturation: number;
  sharpness: number;
  noise_reduction: number;
  straighten: number;
  preset_name: string;
  auto_blemish?: number;
  heal_opacity?: number;
  heal_face_preset?: 'AUTO' | 'SMALL' | 'MEDIUM' | 'LARGE';
  skin_smoothing?: number;
  dodge_burn?: number;
  skin_glow?: number;
  heal_spots?: HealSpot[];
  retouch?: RetouchParams | null;
  auto_wb?: AutoWhiteBalance | null;
}

export interface Photo {
  id: number;
  project_id: number;
  filename: string;
  file_path: string;
  file_size: number;
  width: number;
  height: number;
  file_format: string;
  thumbnail_path: string;
  exif_date: string;
  ai_score: number;
  sharpness_score: number;
  blur_detected: number;
  faces_count: number;
  eyes_status: EyesStatus;
  exposure_status: ExposureStatus;
  exposure_score: number;
  duplicate_group_id: string | null;
  duplicate_group_count?: number;
  duplicate_group_best_id?: number | null;
  duplicate_group_best_filename?: string | null;
  duplicate_group_best_score?: number | null;
  is_group_best?: boolean;
  ai_recommendation: AIRecommendation;
  ai_confidence: number;
  user_selection: UserSelection;
  effective_selection: AIRecommendation | UserSelection;
  star_rating: number;
  scene_category: string;
  edit_params: EditParameters;
  manual_override: number;
  is_edited: number;
  dhash: string;
  client_selection?: 'SELECTED' | 'REJECTED' | 'UNRATED';
  client_note?: string;
  created_at: string;
}

export interface ClientGallery {
  id: number;
  project_id: number;
  gallery_uuid: string;
  title: string;
  client_name?: string;
  client_pin?: string;
  total_photos: number;
  selected_count: number;
  status: 'ACTIVE' | 'SUBMITTED' | 'EXPIRED';
  watermark_enabled: number;
  watermark_text: string;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
  // Master Hosting (photographer's own cPanel domain) upload state
  hosting_url?: string;
  hosting_status?: '' | 'PENDING' | 'UPLOADING' | 'ONLINE' | 'FAILED' | 'EXPIRED';
  hosting_error?: string;
  hosting_uploaded?: number;
}

export interface MasterHostingInfo {
  configured: boolean;
  is_master: boolean;
  url: string;
  error: string | null;
  version?: string;
}

export interface ProjectCounts {
  total: number;
  best_count: number;
  selected_count: number;
  review_count: number;
  reject_count: number;
  similar_count: number;
  similar_groups_count?: number;
  edited_count: number;
  client_selected_count?: number;
}

export interface Project {
  id: number;
  name: string;
  folder_path: string;
  total_photos: number;
  status: string;
  created_at: string;
  updated_at: string;
  counts?: ProjectCounts;
}

export interface BatchLog {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
  message: string;
}

export interface BatchJob {
  id: string;
  project_id: number;
  job_type: 'CULLING' | 'AUTO_EDIT' | 'EXPORT' | 'PROOFING_PREVIEW';
  status: 'IDLE' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  progress_current: number;
  progress_total: number;
  progress_pct: number;
  current_file: string;
  logs: BatchLog[];
  error_message: string;
  started_at: string;
  finished_at?: string;
}

export interface AppSettings {
  ai_provider: string;
  replicate_api_token: string;
  openai_api_key: string;
  gemini_api_key: string;
  custom_ai_endpoint: string;
  has_replicate: boolean;
  has_openai: boolean;
  has_gemini: boolean;
}

export interface LicenseStatus {
  plan: 'FREE_TRIAL' | 'PRO' | 'STUDIO' | 'VIP_LIFETIME';
  status: 'ACTIVE' | 'EXPIRED' | 'OFFLINE' | 'TAMPER_DETECTED';
  is_active: boolean;
  message?: string | null;
  hours_left?: number | null;
  machine_id?: string;
  activated_at?: number | null;
  offline_days_left?: number;
  user_phone?: string;
  is_vip: boolean;
  days_left: number;
  expires_at: string | null;
  user_name: string;
  user_email: string;
  license_key: string;
  max_devices: number;
  features: {
    unlimited_photos: boolean;
    high_res_export: boolean;
    indian_skin_tone: boolean;
    multi_device: boolean;
    batch_auto_edit: boolean;
    all_culling_rules: boolean;
  };
}

export interface CouponVerifyResult {
  valid: boolean;
  code?: string;
  discount_percent?: number;
  original_price?: number;
  discount_amount?: number;
  final_price?: number;
  currency?: string;
  notes?: string;
  message: string;
}


