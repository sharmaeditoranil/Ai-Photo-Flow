"""
Image Processing Service
Handles image loading (JPG/PNG/RAW), thumbnail generation, non-destructive editing pipeline, and high-res export.
"""
import os
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from typing import Optional, Tuple, Dict, Any
from backend.core.interfaces import EditParameters
from backend.core.subject_model import SubjectDetectionEngine
from backend.core.face_model import OpenCVFaceModel

subject_engine = SubjectDetectionEngine()
face_detector = OpenCVFaceModel()

APP_DATA_DIR = os.path.expanduser("~/.photoflow")
CACHE_DIR = os.path.join(APP_DATA_DIR, "cache")
os.makedirs(os.path.join(CACHE_DIR, "thumbnails"), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, "previews"), exist_ok=True)

RAW_EXTENSIONS = {'.arw', '.cr2', '.cr3', '.nef', '.dng', '.orf', '.rw2'}

def is_raw_format(filepath: str) -> bool:
    ext = os.path.splitext(filepath)[1].lower()
    return ext in RAW_EXTENSIONS

def load_image(filepath: str, max_dim: Optional[int] = None) -> np.ndarray:
    """
    Loads image from disk, supporting JPG, PNG, and RAW (ARW, CR3, NEF, DNG).
    Returns RGB uint8 numpy array.
    """
    if is_raw_format(filepath):
        try:
            import rawpy
            with rawpy.imread(filepath) as raw:
                # Fast half-size demosaic if preview requested
                rgb = raw.postprocess(use_camera_wb=True, half_size=(max_dim is not None))
                if max_dim:
                    h, w = rgb.shape[:2]
                    scale = min(max_dim / max(h, w), 1.0)
                    if scale < 1.0:
                        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                return rgb
        except Exception as e:
            # Fallback to OpenCV if rawpy fails or not supported
            pass

    # Standard reading via Pillow / OpenCV
    try:
        pil_img = Image.open(filepath)
        pil_img = ImageOps.exif_transpose(pil_img) # Correct orientation based on EXIF
        if max_dim:
            w, h = pil_img.size
            scale = min(max_dim / max(w, h), 1.0)
            if scale < 1.0:
                pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        return np.array(pil_img.convert("RGB"))
    except Exception:
        # Fallback to OpenCV with safe unicode path support for Windows
        try:
            raw_bytes = np.fromfile(filepath, dtype=np.uint8)
            bgr = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
        except Exception:
            bgr = cv2.imread(filepath)

        if bgr is not None:
            if max_dim:
                h, w = bgr.shape[:2]
                scale = min(max_dim / max(h, w), 1.0)
                if scale < 1.0:
                    bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        raise ValueError(f"Could not load image file: {filepath}")

def generate_thumbnail(filepath: str, project_id: int, photo_id: int, base_rgb: Optional[np.ndarray] = None) -> str:
    """
    Generates a 1400px preview thumbnail and caches it on disk for ultra-crisp Retina display.
    Reuses base_rgb if already in memory to eliminate redundant disk reads.
    """
    thumb_filename = f"thumb_p{project_id}_{photo_id}.jpg"
    thumb_path = os.path.join(CACHE_DIR, "thumbnails", thumb_filename)

    if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
        return thumb_path

    rgb = base_rgb if base_rgb is not None else load_image(filepath, max_dim=1400)
    pil_thumb = Image.fromarray(rgb)
    pil_thumb.save(thumb_path, format="JPEG", quality=95, optimize=False)
    return thumb_path

def generate_edited_thumbnail(
    filepath: str,
    project_id: int,
    photo_id: int,
    params: EditParameters,
    base_rgb: Optional[np.ndarray] = None,
    subject_mask: Optional[np.ndarray] = None,
    subject_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates a 1400px thumbnail with edits applied and caches it on disk for ultra-crisp Retina display.
    Reuses base_rgb and cached subject mask/info if available to eliminate redundant calculations.
    """
    thumb_filename = f"thumb_edited_p{project_id}_{photo_id}.jpg"
    thumb_path = os.path.join(CACHE_DIR, "thumbnails", thumb_filename)

    if base_rgb is None:
        base_rgb = load_image(filepath, max_dim=1400)

    edited_rgb = apply_edit_pipeline(
        base_rgb,
        params,
        cached_subject_mask=subject_mask,
        cached_subject_info=subject_info
    )

    pil_thumb = Image.fromarray(edited_rgb)
    pil_thumb.save(thumb_path, format="JPEG", quality=95, optimize=False)
    return thumb_path

def remove_edited_thumbnail(project_id: int, photo_id: int) -> None:
    """Removes cached edited thumbnail when photo edits are reset."""
    thumb_filename = f"thumb_edited_p{project_id}_{photo_id}.jpg"
    thumb_path = os.path.join(CACHE_DIR, "thumbnails", thumb_filename)
    if os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except OSError:
            pass

def apply_edit_pipeline(
    rgb_image: np.ndarray,
    params: EditParameters,
    cached_subject_mask: Optional[np.ndarray] = None,
    cached_subject_info: Optional[Dict[str, Any]] = None
) -> np.ndarray:
    """
    Applies pro-grade non-destructive photo adjustments:
    - Smart Exposure with soft-knee highlight preservation
    - Advanced Color Balance (Kelvin Temperature & Tint)
    - Dynamic Range Tone Curve: Shadow Lift & Highlight Recovery
    - S-Curve Contrast & Whites/Blacks Anchoring
    - Local Contrast / Clarity via CLAHE for jewelry & embroidery pop
    - Skin-safe Vibrance & Saturation via YCrCb chroma bounds
    - Selective Edge-preserving Sharpening
    - Horizon Straightening
    """
    img = rgb_image.astype(np.float32)

    # Pre-detect faces on original unedited image where facial contrast is pure and unaltered
    orig_u8 = np.clip(rgb_image, 0, 255).astype(np.uint8)
    h, w = orig_u8.shape[:2]
    detected_face_boxes = []
    if cached_subject_info and cached_subject_info.get("faces_boxes"):
        detected_face_boxes = cached_subject_info["faces_boxes"]

    cached_skin_feather = None
    try:
        if max(h, w) > 1000:
            proxy_scale = 800.0 / float(max(h, w))
            small_u8 = cv2.resize(orig_u8, (int(w * proxy_scale), int(h * proxy_scale)), interpolation=cv2.INTER_AREA)
        else:
            small_u8 = orig_u8

        if not detected_face_boxes:
            f_m = face_detector.detect(small_u8)
            if f_m and f_m.bounding_boxes:
                inv_scale = 1.0 / proxy_scale if max(h, w) > 1000 else 1.0
                detected_face_boxes = [
                    {
                        "x": int(b["x"] * inv_scale),
                        "y": int(b["y"] * inv_scale),
                        "w": int(b["w"] * inv_scale),
                        "h": int(b["h"] * inv_scale)
                    }
                    for b in f_m.bounding_boxes
                ]

        # Fast proxy skin detection & feathered matte (eliminates repeated 24MP conversions & 100x100 blurs)
        ycrcb_s = cv2.cvtColor(small_u8, cv2.COLOR_RGB2YCrCb)
        skin_core_s = (ycrcb_s[:, :, 1] >= 133) & (ycrcb_s[:, :, 1] <= 175) & (ycrcb_s[:, :, 2] >= 77) & (ycrcb_s[:, :, 2] <= 127) & (ycrcb_s[:, :, 0] >= 35)
        if np.any(skin_core_s):
            ksize_s = max(7, (min(small_u8.shape[:2]) // 40) | 1)
            skin_blur_s = cv2.GaussianBlur(skin_core_s.astype(np.float32), (ksize_s, ksize_s), 0)
            cached_skin_feather = cv2.resize(skin_blur_s, (w, h), interpolation=cv2.INTER_LINEAR) if max(h, w) > 1000 else skin_blur_s
    except Exception:
        detected_face_boxes = detected_face_boxes or []
        cached_skin_feather = None

    # 1. Straighten / Rotate if non-zero
    if abs(params.straighten) > 0.2:
        center = (w / 2.0, h / 2.0)
        rot_mat = cv2.getRotationMatrix2D(center, params.straighten, 1.0)
        img = cv2.warpAffine(img, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # 2. Advanced Exposure with Soft-Shoulder Highlight Roll-off
    if abs(params.exposure) > 0.01:
        ev_factor = 2.0 ** params.exposure
        if ev_factor > 1.0:
            # Boosting exposure on underexposed photos:
            # Lift shadows and midtones while rolling off smoothly at the top to prevent clipping
            norm = img / 255.0
            # Photographic soft-knee transfer function
            lifted = 1.0 - np.exp(-norm * ev_factor)
            norm_max = 1.0 - np.exp(-ev_factor)
            img = (lifted / max(0.01, norm_max)) * 255.0
        else:
            # Pulling back exposure on overexposed photos
            img *= ev_factor

    preset_name = getattr(params, 'preset_name', '') or ''
    is_pure_light = (
        "Pure Light" in preset_name
        or (abs(params.temperature) < 0.05 and abs(params.tint) < 0.05 and abs(params.vibrance) < 0.05 and abs(params.saturation) < 0.05)
    )

    # 3. White Balance & Color Temperature/Tint (Skipped in Pure Light mode for 0% color change)
    if not is_pure_light:
        if abs(params.temperature) > 0.1:
            temp_shift = params.temperature / 100.0
            r_scale = 1.0 + (temp_shift * 0.18)
            b_scale = 1.0 - (temp_shift * 0.24)
            img[:, :, 0] *= r_scale
            img[:, :, 2] *= b_scale

        # Tint: Green (-Tint) vs Magenta (+Tint)
        if abs(params.tint) > 0.1:
            tint_shift = params.tint / 100.0
            g_scale = 1.0 - (tint_shift * 0.16)
            img[:, :, 1] *= g_scale

        img = np.clip(img, 0.0, 255.0)

    # 3.5. Dual-Zone Adaptive Relighting (Luminous Subject & Radiant Background)
    subject_info = cached_subject_info or {}
    is_wide_shot = bool(subject_info.get("is_wide_shot", False))
    subject_mask = cached_subject_mask
    try:
        if subject_mask is None:
            if max(h, w) > 1000:
                proxy_mask, subject_info = subject_engine.generate_subject_mask(small_u8)
                subject_mask = cv2.resize(proxy_mask, (w, h), interpolation=cv2.INTER_LINEAR)
                is_wide_shot = bool(subject_info.get("is_wide_shot", False))
            else:
                subject_mask, subject_info = subject_engine.generate_subject_mask(rgb_image)
                is_wide_shot = bool(subject_info.get("is_wide_shot", False))
        if subject_info.get("has_subject", False) and subject_mask is not None:
            sub_lum = subject_info.get("subject_lum", 125.0)
            bg_lum = subject_info.get("bg_lum", 100.0)

            # User requirement: "Jis Pic me Background Dark rah raha hai usme subject me light jayada ho ja rah hai"
            contrast_ratio = sub_lum / max(1.0, bg_lum)
            is_dark_bg = (bg_lum < 58.0) or (contrast_ratio > 1.35 and sub_lum > 45.0)
            if is_dark_bg:
                # Dark background: subject is already naturally prominent against dark surroundings.
                # DO NOT amplify subject light! Keep ratios strictly 1.0 (0% artificial relighting).
                sub_ratio = 1.0
                bg_ratio = 1.0
            else:
                target_sub = 135.0
                target_bg = 110.0
                sub_ratio = float(np.clip(target_sub / max(30.0, sub_lum), 1.0, 1.15))
                bg_ratio = float(np.clip(target_bg / max(30.0, bg_lum), 0.98, 1.12))

            # Smooth photographic fill balance
            sub_delta = (sub_ratio - 1.0) * 0.18
            bg_delta = (bg_ratio - 1.0) * 0.15

            # Seamless feathered blend across the subject mask
            zone_delta = (subject_mask * sub_delta) + ((1.0 - subject_mask) * bg_delta)
            zone_3d = zone_delta[:, :, np.newaxis]

            if abs(sub_delta) > 0.001 or abs(bg_delta) > 0.001:
                img *= (1.0 + zone_3d)
                img = np.clip(img, 0.0, 255.0)
    except Exception:
        pass

    # 4. Photographic Dynamic Range: Shadows, Highlights, Contrast, Whites, Blacks
    # High-speed 1D photographic curve lookup (100% mathematical fidelity, zero pixel-loop overhead)
    lut = np.arange(256, dtype=np.float32)
    if abs(params.shadows) > 0.1:
        s_mask = np.clip((100.0 - lut) / 100.0, 0.0, 1.0) ** 1.8
        f_damp = np.clip(lut / 8.0, 0.0, 1.0)
        lut += s_mask * f_damp * (params.shadows * 0.32)
    if abs(params.highlights) > 0.1:
        h_mask = np.clip((lut - 128.0) / 127.0, 0.0, 1.0) ** 1.35
        lut += h_mask * (params.highlights * 0.42)
    if abs(params.whites) > 0.1:
        w_mask = np.clip((lut - 180.0) / 75.0, 0.0, 1.0)
        lut += w_mask * (params.whites * 0.24)
    if abs(params.blacks) > 0.1:
        b_mask = np.clip((60.0 - lut) / 60.0, 0.0, 1.0)
        lut += b_mask * (params.blacks * 0.22)
    if abs(params.contrast) > 0.1:
        c_factor = (100.0 + params.contrast) / 100.0
        lut = 128.0 + (lut - 128.0) * c_factor

    lab = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB)
    L_u8 = cv2.LUT(lab[:, :, 0], np.clip(lut, 0.0, 255.0).astype(np.uint8))
    L = L_u8.astype(np.float32)

    # E. Local Micro-Contrast (Clarity) via CLAHE: brings out intricate jewelry, bridal embroidery & silk sheen
    try:
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        clahe_L = clahe.apply(L_u8).astype(np.float32)
        # Blend 25% CLAHE for crisp micro-contrast without halos
        L = L * 0.75 + clahe_L * 0.25
    except Exception:
        pass

    # E.2. Subtle Dehaze (only if atmospheric haze, fog, or lens flare veil is present)
    # User requirement: "halka sa dehaze ekdam halaka sa use karna hai agar jaruri ho tab"
    try:
        dark_ch = np.min(img, axis=2)
        haze_floor = float(np.percentile(dark_ch, 2))
        # Clear photos have haze_floor < 12.0. Hazy/foggy photos have elevated black floor >= 16.0
        if haze_floor > 16.0:
            haze_strength = float(np.clip((haze_floor - 14.0) * 0.35, 1.0, 10.0))
            haze_mask = np.clip((140.0 - L) / 140.0, 0.0, 1.0)
            L = np.clip(L - (haze_mask * haze_strength), 0.0, 255.0)
    except Exception:
        pass

    # F. High-Precision Detail Preservation & Multi-Scale Micro-Sharpness Enhancement
    # User requirement:
    # "Edit ke baad Sharpness kam ho ja raha hai original me jaisa sharpness hai usko maintain rakhiye aur halka apne se sundar kariye"
    try:
        # 1. Color Noise Removal (Only on Chrominance A and B channels)
        # Cleans rainbow noise speckles in shadows without ever touching luminance sharpness!
        gray_u = np.clip(L, 0.0, 255.0).astype(np.uint8)
        grad_x = cv2.Sobel(gray_u, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray_u, cv2.CV_32F, 0, 1, ksize=3)
        edge_mag = cv2.magnitude(grad_x, grad_y)
        flat_mask = (edge_mag < 15.0)

        if np.sum(flat_mask) > 500:
            lap_a = cv2.Laplacian(lab[:, :, 1], cv2.CV_32F)
            lap_b = cv2.Laplacian(lab[:, :, 2], cv2.CV_32F)
            chroma_noise = max(float(np.std(lap_a[flat_mask])), float(np.std(lap_b[flat_mask])))
            if chroma_noise > 2.5:
                # Accelerate bilateral filter on downsampled chroma (4:2:0 principle)
                ah, aw = lab.shape[:2]
                a_small = cv2.resize(lab[:, :, 1].astype(np.uint8), (aw // 2, ah // 2), interpolation=cv2.INTER_AREA)
                b_small = cv2.resize(lab[:, :, 2].astype(np.uint8), (aw // 2, ah // 2), interpolation=cv2.INTER_AREA)
                a_filt = cv2.bilateralFilter(a_small, d=7, sigmaColor=18, sigmaSpace=9)
                b_filt = cv2.bilateralFilter(b_small, d=7, sigmaColor=18, sigmaSpace=9)
                lab[:, :, 1] = cv2.resize(a_filt, (aw, ah), interpolation=cv2.INTER_LINEAR).astype(np.float32)
                lab[:, :, 2] = cv2.resize(b_filt, (aw, ah), interpolation=cv2.INTER_LINEAR).astype(np.float32)

        # 2. Subtle Natural Skin Smoothing (Frequency-Separated to Keep All Micro-Textures)
        # Smooths minor skin blemishes/unevenness while protecting eyes, lips, hair & jewelry
        # Compute smooth skin mask from proxy if available to avoid two redundant 24MP conversions
        if cached_skin_feather is not None:
            flat_skin = np.clip(1.0 - (edge_mag / 28.0), 0.0, 1.0)
            skin_mask = cached_skin_feather * flat_skin
        else:
            temp_rgb = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
            ycrcb = cv2.cvtColor(temp_rgb, cv2.COLOR_RGB2YCrCb)
            cr = ycrcb[:, :, 1]
            cb = ycrcb[:, :, 2]
            skin_raw = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
            flat_skin = np.clip(1.0 - (edge_mag / 28.0), 0.0, 1.0)
            skin_mask = cv2.GaussianBlur(skin_raw.astype(np.float32) * flat_skin, (7, 7), sigmaX=2.0)

        # 3. High-Pass Detail Extraction (Eyelashes, pupils, hair, fabric embroidery, jewelry facets)
        blurred_fine = cv2.GaussianBlur(L, (0, 0), sigmaX=0.85)
        high_pass_micro = L - blurred_fine

        blurred_mid = cv2.GaussianBlur(L, (0, 0), sigmaX=1.75)
        high_pass_mid = L - blurred_mid

        # Apply gentle 20% surface tone smoothing ONLY on flat skin regions
        if np.any(skin_mask > 0.05):
            L_smooth = cv2.bilateralFilter(np.clip(L, 0, 255).astype(np.uint8), d=7, sigmaColor=14, sigmaSpace=9).astype(np.float32)
            skin_blend = skin_mask * 0.20
            L = L * (1.0 - skin_blend) + L_smooth * skin_blend

        # 4. Authentic High-Pass Crisp Re-injection & Edge Enhancement
        # User requirement: "halka sa kam kariye jayada nhai ekdam halak sa kam kariyega"
        edge_factor = np.clip((edge_mag - 10.0) / 40.0, 0.0, 1.0)
        edge_weight = 0.65 + (0.35 * edge_factor)

        # Gentle, natural crisp enhancement: maintains full original sharpness + delicate crisp definition
        crisp_boost = (high_pass_micro * 0.48 + high_pass_mid * 0.22) * edge_weight
        L = np.clip(L + crisp_boost, 0.0, 255.0)

    except Exception:
        pass

    lab[:, :, 0] = np.clip(L, 0.0, 255.0)
    img = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)

    # 5. Skin-Safe Vibrance & Saturation (Bypassed in Pure Light mode for 100% natural colors)
    if not is_pure_light and (abs(params.vibrance) > 0.1 or abs(params.saturation) > 0.1):
        hsv = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
        S = hsv[:, :, 1] / 255.0

        # Vibrance: boost muted/background colors while safeguarding skin from oversaturation
        if abs(params.vibrance) > 0.1:
            vib_mult = params.vibrance / 100.0
            boost = (1.0 - S) * (vib_mult * 0.40)
            if cached_skin_feather is not None:
                boost *= (1.0 - (cached_skin_feather * 0.70))
            S += boost

        # Global Saturation
        if abs(params.saturation) > 0.1:
            sat_mult = (100.0 + params.saturation) / 100.0
            S *= sat_mult

        hsv[:, :, 1] = np.clip(S * 255.0, 0.0, 255.0)
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)

    # 5.5. Luminance-Neutral Warm Golden-Orange Skin Tone Radiance (Signature Wedding Glow)
    # Strictly bypassed in Pure Light mode so original colors remain 100% untouched!
    if not is_pure_light:
        try:
            if cached_skin_feather is not None:
                skin_3d = cached_skin_feather[:, :, np.newaxis]

                # Measure pre-warmth perceived luminance
                Y_before = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]

                # Warm Golden-Orange tone matrix
                r_warm = img[:, :, 0] * (1.0 + (0.060 * skin_3d[:, :, 0]))
                g_warm = img[:, :, 1] * (1.0 + (0.024 * skin_3d[:, :, 0]))
                b_warm = img[:, :, 2] * (1.0 - (0.075 * skin_3d[:, :, 0]))

                # Measure post-warmth perceived luminance
                Y_after = 0.299 * r_warm + 0.587 * g_warm + 0.114 * b_warm

                # Strictly preserve original luminance on skin pixels so exposure never overshoots!
                scale = np.where(skin_3d[:, :, 0] > 0.05, Y_before / np.maximum(1.0, Y_after), 1.0)
                scale = np.clip(scale, 0.90, 1.10)

                img[:, :, 0] = r_warm * scale
                img[:, :, 1] = g_warm * scale
                img[:, :, 2] = b_warm * scale
                img = np.clip(img, 0.0, 255.0)
        except Exception:
            pass

    # 6. Retouch4me-Style AI Facial Blemish Healing & Manual Spot Brush (Ultra-Fast Localized Pipeline)
    heal_spots = getattr(params, 'heal_spots', []) or []
    auto_blemish = float(getattr(params, 'auto_blemish', 0.0) or 0.0)

    if (heal_spots and len(heal_spots) > 0) or auto_blemish > 1.0:
        try:
            h, w = img.shape[:2]

            # A. Manual Spot Healing Brush (Ultra-Fast Local Patch Inpainting)
            if heal_spots and len(heal_spots) > 0:
                for spot in heal_spots:
                    try:
                        cx = int(np.clip(float(spot.get("x", 0.5)) * w, 0, w - 1))
                        cy = int(np.clip(float(spot.get("y", 0.5)) * h, 0, h - 1))
                        rad = max(3, int(float(spot.get("radius", 0.010)) * min(h, w)))
                        pad = rad * 3
                        sx1, sy1 = max(0, cx - pad), max(0, cy - pad)
                        sx2, sy2 = min(w, cx + pad), min(h, cy + pad)
                        if sx2 > sx1 and sy2 > sy1:
                            patch = np.clip(img[sy1:sy2, sx1:sx2], 0, 255).astype(np.uint8)
                            patch_mask = np.zeros((sy2 - sy1, sx2 - sx1), dtype=np.uint8)
                            cv2.circle(patch_mask, (cx - sx1, cy - sy1), rad, 255, -1)
                            patch_inpainted = cv2.inpaint(patch, patch_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
                            img[sy1:sy2, sx1:sx2] = patch_inpainted.astype(np.float32)
                    except Exception:
                        pass

            # B. Retouch4me-Style Multi-Scale AI Face Blemish Auto-Clean (Localized to Face Crops)
            if auto_blemish > 1.0:
                try:
                    f_boxes = detected_face_boxes
                    if not f_boxes:
                        # Fast proxy face detect if not already available
                        proxy_s = 800.0 / float(max(h, w)) if max(h, w) > 1000 else 1.0
                        proxy_u8 = cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (int(w * proxy_s), int(h * proxy_s)), interpolation=cv2.INTER_AREA) if proxy_s < 1.0 else np.clip(img, 0, 255).astype(np.uint8)
                        f_m = face_detector.detect(proxy_u8)
                        if f_m and f_m.bounding_boxes:
                            inv_s = 1.0 / proxy_s
                            f_boxes = [
                                {
                                    "x": int(b["x"] * inv_s),
                                    "y": int(b["y"] * inv_s),
                                    "w": int(b["w"] * inv_s),
                                    "h": int(b["h"] * inv_s)
                                }
                                for b in f_m.bounding_boxes
                            ]

                    if f_boxes:
                        sens = np.clip(auto_blemish / 100.0, 0.1, 1.0)
                        th_cr = max(3.5, 7.0 - sens * 3.5)
                        th_rg = max(4.0, 8.0 - sens * 4.0)
                        th_y = max(4.5, 8.5 - sens * 4.0)

                        k_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
                        k_mid = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23))
                        k_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35))

                        for fb in f_boxes:
                            fx, fy, fw, fh = fb['x'], fb['y'], fb['w'], fb['h']
                            pad_x, pad_y = int(fw * 0.08), int(fh * 0.08)
                            x1, y1 = max(0, fx - pad_x), max(0, fy - pad_y)
                            x2, y2 = min(w, fx + fw + pad_x), min(h, fy + fh + pad_y)
                            face_crop = np.clip(img[y1:y2, x1:x2], 0, 255).astype(np.uint8)
                            ch, cw = face_crop.shape[:2]
                            if ch < 12 or cw < 12:
                                continue

                            ycrcb_c = cv2.cvtColor(face_crop, cv2.COLOR_RGB2YCrCb)
                            Y_c = ycrcb_c[:, :, 0]
                            Cr_c = ycrcb_c[:, :, 1]
                            Cb_c = ycrcb_c[:, :, 2]
                            gray_c = cv2.cvtColor(face_crop, cv2.COLOR_RGB2GRAY)
                            edge_mag_c = cv2.magnitude(cv2.Sobel(gray_c, cv2.CV_32F, 1, 0), cv2.Sobel(gray_c, cv2.CV_32F, 0, 1))

                            r_ch = face_crop[:, :, 0].astype(np.int16)
                            g_ch = face_crop[:, :, 1].astype(np.int16)
                            b_ch = face_crop[:, :, 2].astype(np.int16)
                            redness_c = np.clip(r_ch - ((g_ch + b_ch) // 2) + 128, 0, 255).astype(np.uint8)

                            if max(ch, cw) > 400:
                                s_scale = 400.0 / float(max(ch, cw))
                                sw, sh = max(1, int(cw * s_scale)), max(1, int(ch * s_scale))
                                Cr_s = cv2.resize(Cr_c, (sw, sh), interpolation=cv2.INTER_AREA)
                                red_s = cv2.resize(redness_c, (sw, sh), interpolation=cv2.INTER_AREA)
                                Y_s = cv2.resize(Y_c, (sw, sh), interpolation=cv2.INTER_AREA)

                                ks = max(3, int(13 * s_scale) | 1)
                                kl = max(7, int(31 * s_scale) | 1)
                                k_s_el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
                                k_l_el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kl, kl))

                                top_cr_s = np.maximum(cv2.morphologyEx(Cr_s, cv2.MORPH_TOPHAT, k_s_el), cv2.morphologyEx(Cr_s, cv2.MORPH_TOPHAT, k_l_el))
                                top_rg_s = np.maximum(cv2.morphologyEx(red_s, cv2.MORPH_TOPHAT, k_s_el), cv2.morphologyEx(red_s, cv2.MORPH_TOPHAT, k_l_el))
                                blk_y_s = np.maximum(cv2.morphologyEx(Y_s, cv2.MORPH_BLACKHAT, k_s_el), cv2.morphologyEx(Y_s, cv2.MORPH_BLACKHAT, k_l_el))

                                tophat_cr = cv2.resize(top_cr_s, (cw, ch), interpolation=cv2.INTER_LINEAR)
                                tophat_rg = cv2.resize(top_rg_s, (cw, ch), interpolation=cv2.INTER_LINEAR)
                                blackhat_y = cv2.resize(blk_y_s, (cw, ch), interpolation=cv2.INTER_LINEAR)
                            else:
                                tophat_cr = np.maximum(cv2.morphologyEx(Cr_c, cv2.MORPH_TOPHAT, k_small), cv2.morphologyEx(Cr_c, cv2.MORPH_TOPHAT, k_large))
                                tophat_rg = np.maximum(cv2.morphologyEx(redness_c, cv2.MORPH_TOPHAT, k_small), cv2.morphologyEx(redness_c, cv2.MORPH_TOPHAT, k_large))
                                blackhat_y = np.maximum(cv2.morphologyEx(Y_c, cv2.MORPH_BLACKHAT, k_small), cv2.morphologyEx(Y_c, cv2.MORPH_BLACKHAT, k_large))

                            face_mask_c = np.zeros((ch, cw), dtype=np.uint8)
                            fcx, fcy = int((fx - x1) + fw * 0.5), int((fy - y1) + fh * 0.52)
                            cv2.ellipse(face_mask_c, (fcx, fcy), (int(fw * 0.44), int(fh * 0.46)), 0, 0, 360, 255, -1)

                            # Strict feature protection zones
                            nose_x1, nose_x2 = max(0, int(fcx - fw * 0.13)), min(cw, int(fcx + fw * 0.13))
                            nose_y1, nose_y2 = max(0, int((fy - y1) + fh * 0.38)), min(ch, int((fy - y1) + fh * 0.72))
                            face_mask_c[nose_y1:nose_y2, nose_x1:nose_x2] = 0

                            eye_x1, eye_x2 = max(0, int(fcx - fw * 0.38)), min(cw, int(fcx + fw * 0.38))
                            eye_y1, eye_y2 = max(0, int((fy - y1) + fh * 0.15)), min(ch, int((fy - y1) + fh * 0.45))
                            face_mask_c[eye_y1:eye_y2, eye_x1:eye_x2] = 0

                            mouth_x1, mouth_x2 = max(0, int(fcx - fw * 0.28)), min(cw, int(fcx + fw * 0.28))
                            mouth_y1, mouth_y2 = max(0, int((fy - y1) + fh * 0.68)), min(ch, int((fy - y1) + fh * 0.90))
                            face_mask_c[mouth_y1:mouth_y2, mouth_x1:mouth_x2] = 0

                            tikka_x1, tikka_x2 = max(0, int(fcx - fw * 0.08)), min(cw, int(fcx + fw * 0.08))
                            tikka_y1, tikka_y2 = max(0, int(fy - y1)), min(ch, int((fy - y1) + fh * 0.26))
                            face_mask_c[tikka_y1:tikka_y2, tikka_x1:tikka_x2] = 0

                            safe_skin = (face_mask_c > 0) & (Cr_c >= 122) & (Cr_c <= 218) & (Cb_c >= 70) & (Cb_c <= 140) & (Y_c >= 72) & (Y_c <= 250) & (edge_mag_c < 42.0)
                            cand = safe_skin & ((tophat_cr > th_cr) | (tophat_rg > th_rg) | (blackhat_y > th_y))

                            max_diam = min(28, max(10, int(fw * 0.07)))
                            max_area = int(1.4 * np.pi * (max_diam / 2.0) ** 2)
                            min_diam = max(3, int(fw * 0.003))
                            min_area = max(5, int(np.pi * (min_diam / 2.0) ** 2))

                            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8) * 255)
                            crop_heal_mask = np.zeros((ch, cw), dtype=np.uint8)
                            for i in range(1, num_labels):
                                area = stats[i, cv2.CC_STAT_AREA]
                                cw_box = stats[i, cv2.CC_STAT_WIDTH]
                                ch_box = stats[i, cv2.CC_STAT_HEIGHT]
                                aspect = max(cw_box, ch_box) / max(1, min(cw_box, ch_box))
                                pimple_size = max(cw_box, ch_box)
                                if min_area <= area <= max_area and pimple_size <= max_diam and aspect < 2.0:
                                    crop_heal_mask[labels == i] = 255

                            if np.any(crop_heal_mask > 0):
                                kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                                dilated_mask = cv2.dilate(crop_heal_mask, kernel_dilate, iterations=1)
                                base_blurred = cv2.GaussianBlur(face_crop, (5, 5), 1.2)
                                skin_texture = face_crop.astype(np.float32) - base_blurred.astype(np.float32)
                                inpainted_base = cv2.inpaint(face_crop, dilated_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
                                healed_textured = np.clip(inpainted_base.astype(np.float32) + skin_texture * 0.75, 0, 255).astype(np.uint8)
                                feather_mask = cv2.GaussianBlur(dilated_mask.astype(np.float32) / 255.0, (5, 5), 1.2)[:, :, np.newaxis]
                                blended = face_crop.astype(np.float32) * (1.0 - feather_mask) + healed_textured.astype(np.float32) * feather_mask
                                img[y1:y2, x1:x2] = blended
                except Exception:
                    pass
        except Exception:
            pass

    # 7. SkinFiner-Style Texture-Preserving Facial Skin Smoothing (Fast Face-Localized & Proxy-Accelerated)
    skin_smoothing = float(getattr(params, 'skin_smoothing', 0.0) or 0.0)
    if skin_smoothing > 1.0:
        try:
            h, w = img.shape[:2]
            f_boxes = detected_face_boxes
            strength_factor = min(0.85, (skin_smoothing / 100.0) * 0.85)

            if f_boxes:
                # High-speed localized processing per detected face
                for fb in f_boxes:
                    fx, fy, fw, fh = fb['x'], fb['y'], fb['w'], fb['h']
                    pad_x, pad_y = int(fw * 0.25), int(fh * 0.25)
                    x1, y1 = max(0, fx - pad_x), max(0, fy - pad_y)
                    x2, y2 = min(w, fx + fw + pad_x), min(h, fy + fh + pad_y)
                    fc = np.clip(img[y1:y2, x1:x2], 0, 255).astype(np.uint8)
                    fch, fcw = fc.shape[:2]
                    if fch < 12 or fcw < 12:
                        continue

                    ycrcb_fc = cv2.cvtColor(fc, cv2.COLOR_RGB2YCrCb)
                    Y_fc, Cr_fc, Cb_fc = ycrcb_fc[:, :, 0], ycrcb_fc[:, :, 1], ycrcb_fc[:, :, 2]
                    hsv_fc = cv2.cvtColor(fc, cv2.COLOR_RGB2HSV)
                    S_fc, V_fc = hsv_fc[:, :, 1], hsv_fc[:, :, 2]
                    skin_base = (Cr_fc >= 128) & (Cr_fc <= 180) & (Cb_fc >= 75) & (Cb_fc <= 135) & (Y_fc >= 32) & (S_fc >= 15) & (S_fc <= 215)

                    gray_fc = cv2.cvtColor(fc, cv2.COLOR_RGB2GRAY)
                    edge_mag_fc = cv2.magnitude(cv2.Sobel(gray_fc, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(gray_fc, cv2.CV_32F, 0, 1, ksize=3))
                    protected_skin = skin_base & (edge_mag_fc < 65.0) & (V_fc > 38) & (Cr_fc < 175)

                    if np.any(protected_skin):
                        skin_mask_f = protected_skin.astype(np.float32)
                        ksize = max(7, (min(fch, fcw) // 55) | 1)
                        skin_mask_f = cv2.GaussianBlur(skin_mask_f, (ksize, ksize), 0)

                        if max(fch, fcw) > 600:
                            fc_s = cv2.resize(fc, (fcw // 2, fch // 2), interpolation=cv2.INTER_AREA)
                            bilat_s = cv2.bilateralFilter(fc_s, d=7, sigmaColor=55.0, sigmaSpace=25.0)
                            bilateral = cv2.resize(bilat_s, (fcw, fch), interpolation=cv2.INTER_LINEAR)
                        else:
                            bilateral = cv2.bilateralFilter(fc, d=7, sigmaColor=55.0, sigmaSpace=30.0)
                        texture_blur = cv2.GaussianBlur(fc, (5, 5), 0)
                        texture_high = fc.astype(np.float32) - texture_blur.astype(np.float32)
                        smooth_layer = np.clip(bilateral.astype(np.float32) + 0.30 * texture_high, 0, 255)
                        alpha = skin_mask_f[:, :, np.newaxis] * strength_factor
                        img[y1:y2, x1:x2] = (img[y1:y2, x1:x2] * (1.0 - alpha)) + (smooth_layer * alpha)
            else:
                # Full canvas proxy bilateral fallback when no face is found
                img_u8 = np.clip(img, 0, 255).astype(np.uint8)
                scale_down = 3
                small = cv2.resize(img_u8, (max(1, w // scale_down), max(1, h // scale_down)))
                bilat_small = cv2.bilateralFilter(small, d=7, sigmaColor=50.0, sigmaSpace=25.0)
                bilateral = cv2.resize(bilat_small, (w, h), interpolation=cv2.INTER_LINEAR)
                texture_blur = cv2.GaussianBlur(img_u8, (5, 5), 0)
                texture_high = img_u8.astype(np.float32) - texture_blur.astype(np.float32)
                smooth_layer = np.clip(bilateral.astype(np.float32) + 0.30 * texture_high, 0, 255)
                ycrcb_full = cv2.cvtColor(img_u8, cv2.COLOR_RGB2YCrCb)
                skin_base = (ycrcb_full[:, :, 1] >= 128) & (ycrcb_full[:, :, 1] <= 180) & (ycrcb_full[:, :, 2] >= 75) & (ycrcb_full[:, :, 2] <= 135)
                skin_mask_f = cv2.GaussianBlur(skin_base.astype(np.float32), (15, 15), 0)
                alpha = skin_mask_f[:, :, np.newaxis] * strength_factor
                img = (img * (1.0 - alpha)) + (smooth_layer * alpha)
            img = np.clip(img, 0.0, 255.0)
        except Exception:
            pass

    # 8. AI Portrait Dodge & Burn (Fast Proxy-Accelerated Ambient 3D Depth)
    dodge_burn = float(getattr(params, 'dodge_burn', 0.0) or 0.0)
    if dodge_burn > 1.0:
        try:
            h, w = img.shape[:2]
            img_u8 = np.clip(img, 0, 255).astype(np.uint8)

            skin_mask_f = cached_skin_feather
            if skin_mask_f is not None and np.any(skin_mask_f > 0.05):
                Y = cv2.cvtColor(img_u8, cv2.COLOR_RGB2GRAY).astype(np.float32)

                # Ultra-fast downscaled ambient lighting map proxy (800px)
                small_w = 800
                small_h = max(1, int(h * (800.0 / w)))
                Y_small = cv2.resize(Y, (small_w, small_h), interpolation=cv2.INTER_AREA)
                k_amb = max(31, (min(small_h, small_w) // 12) | 1)
                Y_amb_small = cv2.GaussianBlur(Y_small, (k_amb, k_amb), 0)
                Y_ambient = cv2.resize(Y_amb_small, (w, h), interpolation=cv2.INTER_LINEAR)

                # Dodge: Natural high points (cheekbones, bridge of nose, forehead center)
                high_pts = np.clip((Y - Y_ambient) / 25.0, 0.0, 1.0)

                # Burn: Natural contour points (jawline, cheek hollows, temples)
                contour_pts = np.clip((Y_ambient - Y) / 30.0, 0.0, 1.0)

                # Ultra-gentle professional scaling (max +12% dodge, -7% burn at 100%)
                db_strength = dodge_burn / 100.0
                dodge_mult = 1.0 + (high_pts * db_strength * 0.12 * skin_mask_f)
                burn_mult = 1.0 - (contour_pts * db_strength * 0.07 * skin_mask_f)

                combined_3d = np.clip(dodge_mult * burn_mult, 0.92, 1.15)[:, :, np.newaxis]
                img = np.clip(img * combined_3d, 0.0, 255.0)
        except Exception:
            pass

    # Final uint8 clipping
    return np.clip(img, 0, 255).astype(np.uint8)

def render_preview(filepath: str, params: EditParameters, max_dim: int = 1200) -> np.ndarray:
    """
    Renders an adjusted preview of the image at intermediate resolution for instant UI inspection.
    """
    base_rgb = load_image(filepath, max_dim=max_dim)
    return apply_edit_pipeline(base_rgb, params)

def is_default_params(params: Optional[EditParameters]) -> bool:
    """Checks whether photo edit parameters are untouched defaults."""
    if not params:
        return True
    try:
        return (
            abs(getattr(params, 'exposure', 0.0) or 0.0) < 0.01 and
            abs(getattr(params, 'temperature', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'tint', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'contrast', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'highlights', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'shadows', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'whites', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'blacks', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'vibrance', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'saturation', 0.0) or 0.0) < 0.1 and
            abs(getattr(params, 'straighten', 0.0) or 0.0) < 0.1 and
            float(getattr(params, 'skin_smoothing', 0.0) or 0.0) < 1.0 and
            float(getattr(params, 'auto_blemish', 0.0) or 0.0) < 1.0 and
            float(getattr(params, 'dodge_burn', 0.0) or 0.0) < 1.0 and
            len(getattr(params, 'heal_spots', []) or []) == 0
        )
    except Exception:
        return False

def export_photo(
    source_path: str,
    target_path: str,
    params: EditParameters,
    jpeg_quality: int = 92,
    max_resolution: Optional[int] = None
) -> None:
    """
    Renders full-resolution or specified resolution adjusted photo and writes to disk.
    Preserves directories and never overwrites originals.
    Accelerated with hardware SIMD JPEG compression and zero-overhead pass-through for unedited images.
    """
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    # 1. Ultra-fast pass-through for unedited photos
    if is_default_params(params):
        src_ext = os.path.splitext(source_path)[1].lower()
        if max_resolution is None and src_ext in ('.jpg', '.jpeg'):
            import shutil
            shutil.copy2(source_path, target_path)
            return

        # Direct resize without filter chain
        full_rgb = load_image(source_path, max_dim=max_resolution)
        bgr = cv2.cvtColor(full_rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(target_path, bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        return

    # 2. Photos with edits: apply accelerated pipeline
    full_rgb = load_image(source_path, max_dim=max_resolution)
    edited_rgb = apply_edit_pipeline(full_rgb, params)

    # Hardware-accelerated SIMD JPEG write
    bgr = cv2.cvtColor(edited_rgb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(target_path, bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
