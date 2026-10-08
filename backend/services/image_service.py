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
    else:
        try:
            if max(h, w) > 1000:
                proxy_scale = 800.0 / float(max(h, w))
                small_u8 = cv2.resize(orig_u8, (int(w * proxy_scale), int(h * proxy_scale)), interpolation=cv2.INTER_AREA)
                f_m = face_detector.detect(small_u8)
                if f_m and f_m.bounding_boxes:
                    inv_scale = 1.0 / proxy_scale
                    detected_face_boxes = [
                        {
                            "x": int(b["x"] * inv_scale),
                            "y": int(b["y"] * inv_scale),
                            "w": int(b["w"] * inv_scale),
                            "h": int(b["h"] * inv_scale)
                        }
                        for b in f_m.bounding_boxes
                    ]
            else:
                f_m = face_detector.detect(orig_u8)
                if f_m and f_m.bounding_boxes:
                    detected_face_boxes = f_m.bounding_boxes
        except Exception:
            detected_face_boxes = []

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
                proxy_scale = 800.0 / float(max(h, w))
                small_proxy = cv2.resize(orig_u8, (int(w * proxy_scale), int(h * proxy_scale)), interpolation=cv2.INTER_AREA)
                proxy_mask, subject_info = subject_engine.generate_subject_mask(small_proxy)
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
    # Process luminance in LAB color space to preserve chromatic purity
    lab = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[:, :, 0] # 0.0 to 255.0

    # A. True Shadow Recovery (L < 100)
    # Lifts dark attire while anchoring deep blacks (L < 6)
    # Does NOT inflate facial skin midtones (L ~ 120-125)
    if abs(params.shadows) > 0.1:
        shadow_mask = np.clip((100.0 - L) / 100.0, 0.0, 1.0) ** 1.8
        floor_damping = np.clip(L / 8.0, 0.0, 1.0)
        L += shadow_mask * floor_damping * (params.shadows * 0.32)

    # B. Advanced Highlight Recovery (L > 128)
    # Recovers textured highlights (bridal veil, white sherwani, sky) while keeping sparkle
    if abs(params.highlights) > 0.1:
        highlight_mask = np.clip((L - 128.0) / 127.0, 0.0, 1.0) ** 1.35
        L += highlight_mask * (params.highlights * 0.42)

    # C. Whites & Blacks Tonal Anchoring
    if abs(params.whites) > 0.1:
        w_mask = np.clip((L - 180.0) / 75.0, 0.0, 1.0)
        L += w_mask * (params.whites * 0.24)
    if abs(params.blacks) > 0.1:
        b_mask = np.clip((60.0 - L) / 60.0, 0.0, 1.0)
        L += b_mask * (params.blacks * 0.22)

    # D. S-Curve Global Contrast
    if abs(params.contrast) > 0.1:
        c_factor = (100.0 + params.contrast) / 100.0
        # Pivot around photographic midtone 128
        L = 128.0 + (L - 128.0) * c_factor

    # E. Local Micro-Contrast (Clarity) via CLAHE: brings out intricate jewelry, bridal embroidery & silk sheen
    try:
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        clahe_L = clahe.apply(np.clip(L, 0.0, 255.0).astype(np.uint8)).astype(np.float32)
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
                lab[:, :, 1] = cv2.bilateralFilter(lab[:, :, 1].astype(np.uint8), d=7, sigmaColor=18, sigmaSpace=9).astype(np.float32)
                lab[:, :, 2] = cv2.bilateralFilter(lab[:, :, 2].astype(np.uint8), d=7, sigmaColor=18, sigmaSpace=9).astype(np.float32)

        # 2. Subtle Natural Skin Smoothing (Frequency-Separated to Keep All Micro-Textures)
        # Smooths minor skin blemishes/unevenness while protecting eyes, lips, hair & jewelry
        temp_rgb = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
        ycrcb = cv2.cvtColor(temp_rgb, cv2.COLOR_RGB2YCrCb)
        cr = ycrcb[:, :, 1]
        cb = ycrcb[:, :, 2]
        skin_raw = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)

        # Protect all facial contours, eyebrows, eyes, nostrils, lips from smoothing
        flat_skin = np.clip(1.0 - (edge_mag / 28.0), 0.0, 1.0)
        skin_mask = skin_raw.astype(np.float32) * flat_skin
        skin_mask = cv2.GaussianBlur(skin_mask, (7, 7), sigmaX=2.0)

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
        ycrcb = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2YCrCb)
        cr = ycrcb[:, :, 1]
        cb = ycrcb[:, :, 2]
        # Detect Indian skin tones: Cr in [133, 173], Cb in [77, 127]
        skin_mask = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)

        S = hsv[:, :, 1] / 255.0

        # Vibrance: boost muted/background colors while safeguarding skin from oversaturation
        if abs(params.vibrance) > 0.1:
            vib_mult = params.vibrance / 100.0
            boost = (1.0 - S) * (vib_mult * 0.40)
            # Taper vibrance on skin pixels by 70% to prevent sunburn/redness
            boost[skin_mask] *= 0.30
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
            ycrcb = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2YCrCb)
            Y_c = ycrcb[:, :, 0]
            Cr_c = ycrcb[:, :, 1].astype(np.float32)
            Cb_c = ycrcb[:, :, 2].astype(np.float32)

            # Detect human skin tones: Cr in [133, 175], Cb in [77, 127], Y >= 35
            skin_core = (Cr_c >= 133) & (Cr_c <= 175) & (Cb_c >= 77) & (Cb_c <= 127) & (Y_c >= 35)
            if np.any(skin_core):
                skin_mask_f = skin_core.astype(np.float32)
                ksize = max(11, (min(img.shape[:2]) // 40) | 1)
                skin_mask_f = cv2.GaussianBlur(skin_mask_f, (ksize, ksize), 0)
                skin_3d = skin_mask_f[:, :, np.newaxis]

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

    # 6. Retouch4me-Style AI Facial Blemish Healing & Manual Spot Brush
    heal_spots = getattr(params, 'heal_spots', []) or []
    auto_blemish = float(getattr(params, 'auto_blemish', 0.0) or 0.0)

    if (heal_spots and len(heal_spots) > 0) or auto_blemish > 1.0:
        try:
            h, w = img.shape[:2]
            img_u8 = np.clip(img, 0, 255).astype(np.uint8)
            combined_heal_mask = np.zeros((h, w), dtype=np.uint8)

            # A. Manual Spot Healing Brush (User clicks directly on specific blemish)
            if heal_spots and len(heal_spots) > 0:
                for spot in heal_spots:
                    try:
                        cx = int(np.clip(float(spot.get("x", 0.5)) * w, 0, w - 1))
                        cy = int(np.clip(float(spot.get("y", 0.5)) * h, 0, h - 1))
                        # Precision compact radius: default 0.010 (~10px), minimum 3px
                        rad = max(3, int(float(spot.get("radius", 0.010)) * min(h, w)))
                        cv2.circle(combined_heal_mask, (cx, cy), rad, 255, -1)
                    except Exception:
                        pass

            # B. Retouch4me-Style Multi-Scale AI Face Blemish Auto-Clean
            # Professional frequency-separated blemish isolation (pores, nose, eyes, lips 100% protected)
            if auto_blemish > 1.0:
                try:
                    f_boxes = detected_face_boxes
                    if not f_boxes:
                        f_metrics = face_detector.detect(img_u8)
                        if f_metrics and f_metrics.bounding_boxes:
                            f_boxes = f_metrics.bounding_boxes

                    if f_boxes:
                        ycrcb = cv2.cvtColor(img_u8, cv2.COLOR_RGB2YCrCb)
                        Y_c = ycrcb[:, :, 0]
                        Cr_c = ycrcb[:, :, 1]
                        Cb_c = ycrcb[:, :, 2]
                        gray = cv2.cvtColor(img_u8, cv2.COLOR_RGB2GRAY)
                        edge_mag = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))

                        # Redness channel (R - (G+B)/2): extremely sensitive for acne & inflamed spots
                        r_ch = img_u8[:, :, 0].astype(np.int16)
                        g_ch = img_u8[:, :, 1].astype(np.int16)
                        b_ch = img_u8[:, :, 2].astype(np.int16)
                        redness = np.clip(r_ch - ((g_ch + b_ch) // 2) + 128, 0, 255).astype(np.uint8)

                        # Multi-Scale Morphological Top-Hat & Black-Hat (13px for micro, 23px for mid, 35px for large)
                        k_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
                        k_mid = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23))
                        k_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35))

                        tophat_cr_s = cv2.morphologyEx(Cr_c, cv2.MORPH_TOPHAT, k_small)
                        tophat_cr_m = cv2.morphologyEx(Cr_c, cv2.MORPH_TOPHAT, k_mid)
                        tophat_cr_l = cv2.morphologyEx(Cr_c, cv2.MORPH_TOPHAT, k_large)
                        tophat_cr = np.maximum(np.maximum(tophat_cr_s, tophat_cr_m), tophat_cr_l)

                        tophat_rg_s = cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, k_small)
                        tophat_rg_m = cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, k_mid)
                        tophat_rg_l = cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, k_large)
                        tophat_rg = np.maximum(np.maximum(tophat_rg_s, tophat_rg_m), tophat_rg_l)

                        blackhat_y_s = cv2.morphologyEx(Y_c, cv2.MORPH_BLACKHAT, k_small)
                        blackhat_y_m = cv2.morphologyEx(Y_c, cv2.MORPH_BLACKHAT, k_mid)
                        blackhat_y_l = cv2.morphologyEx(Y_c, cv2.MORPH_BLACKHAT, k_large)
                        blackhat_y = np.maximum(np.maximum(blackhat_y_s, blackhat_y_m), blackhat_y_l)

                        # Retouch4me High-Sensitivity Dynamic Thresholds
                        # Scales smoothly with auto_blemish (10 to 100)
                        sens = np.clip(auto_blemish / 100.0, 0.1, 1.0)
                        th_cr = max(3.5, 7.0 - sens * 3.5)
                        th_rg = max(4.0, 8.0 - sens * 4.0)
                        th_y = max(4.5, 8.5 - sens * 4.0)

                        for fb in f_boxes:
                            fx, fy, fw, fh = fb['x'], fb['y'], fb['w'], fb['h']
                            face_mask = np.zeros((h, w), dtype=np.uint8)
                            fcx, fcy = int(fx + fw * 0.5), int(fy + fh * 0.52)

                            # 1. Main Face Flesh Zone (cheeks, forehead, chin, temples)
                            cv2.ellipse(face_mask, (fcx, fcy), (int(fw * 0.44), int(fh * 0.46)), 0, 0, 360, 255, -1)

                            # 2. STRICT NOSE & NOSTRIL EXCLUSION ZONE
                            # Prevents nose shape deformation and nostril shadow erasure
                            nose_x1, nose_x2 = int(fcx - fw * 0.13), int(fcx + fw * 0.13)
                            nose_y1, nose_y2 = int(fy + fh * 0.38), int(fy + fh * 0.72)
                            face_mask[nose_y1:nose_y2, nose_x1:nose_x2] = 0

                            # 3. STRICT EYES & EYEBROWS EXCLUSION ZONE
                            # Covers eyebrows from top arches down to below lower eyelid
                            eye_x1, eye_x2 = int(fcx - fw * 0.38), int(fcx + fw * 0.38)
                            eye_y1, eye_y2 = int(fy + fh * 0.15), int(fy + fh * 0.45)
                            face_mask[eye_y1:eye_y2, eye_x1:eye_x2] = 0

                            # 4. STRICT MOUTH & SMILE EXCLUSION ZONE
                            # Covers upper lip, philtrum, smile corners, teeth, and lower lip
                            mouth_x1, mouth_x2 = int(fcx - fw * 0.28), int(fcx + fw * 0.28)
                            mouth_y1, mouth_y2 = int(fy + fh * 0.68), int(fy + fh * 0.90)
                            face_mask[mouth_y1:mouth_y2, mouth_x1:mouth_x2] = 0

                            # 5. STRICT BINDI / MAANG TIKKA EXCLUSION ZONE
                            tikka_x1, tikka_x2 = int(fcx - fw * 0.08), int(fcx + fw * 0.08)
                            tikka_y1, tikka_y2 = int(fy), int(fy + fh * 0.26)
                            face_mask[tikka_y1:tikka_y2, tikka_x1:tikka_x2] = 0

                            # 6. Hair & Stubble Protection: Exclude pixels with low luminance or high edge gradient
                            safe_skin = (face_mask > 0) & (Cr_c >= 122) & (Cr_c <= 218) & (Cb_c >= 70) & (Cb_c <= 140) & (Y_c >= 72) & (Y_c <= 250) & (edge_mag < 42.0)
                            cand = safe_skin & ((tophat_cr > th_cr) | (tophat_rg > th_rg) | (blackhat_y > th_y))

                            # Compact pimple geometry: strictly up to 28-30px max (never facial bone structures)
                            max_diam = min(28, max(10, int(fw * 0.07)))
                            max_area = int(1.4 * np.pi * (max_diam / 2.0) ** 2)
                            min_diam = max(3, int(fw * 0.003))
                            min_area = max(5, int(np.pi * (min_diam / 2.0) ** 2))

                            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8) * 255)
                            for i in range(1, num_labels):
                                area = stats[i, cv2.CC_STAT_AREA]
                                cw = stats[i, cv2.CC_STAT_WIDTH]
                                ch = stats[i, cv2.CC_STAT_HEIGHT]
                                aspect = max(cw, ch) / max(1, min(cw, ch))
                                pimple_size = max(cw, ch)

                                # Compact pimple geometry: rejects hair strands or linear creases
                                if min_area <= area <= max_area and pimple_size <= max_diam and aspect < 2.0:
                                    combined_heal_mask[labels == i] = 255
                except Exception:
                    pass

            # C. Retouch4me Frequency-Preserving Inpainting & Seamless Texture Synthesis
            if np.any(combined_heal_mask > 0):
                # 1. Tight 3x3 dilation for minimal border coverage
                kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                dilated_mask = cv2.dilate(combined_heal_mask, kernel_dilate, iterations=1)

                # 2. Extract High-Frequency Skin Pore Texture (Preserves 100% natural pore detail)
                base_blurred = cv2.GaussianBlur(img_u8, (5, 5), 1.2)
                skin_texture = img_u8.astype(np.float32) - base_blurred.astype(np.float32)

                # 3. Localized Inpainting with strict tight radius (3px)
                # Tightly samples healthy adjacent skin color, never smearing distant hair or facial features
                inpainted_base = cv2.inpaint(img_u8, dilated_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

                # 4. Synthesize natural skin micro-texture back onto the healed tone layer
                healed_textured = np.clip(inpainted_base.astype(np.float32) + skin_texture * 0.75, 0, 255).astype(np.uint8)

                # 5. Micro Alpha-Feathering at edges for invisible, photorealistic transition
                feather_mask = cv2.GaussianBlur(dilated_mask.astype(np.float32) / 255.0, (5, 5), 1.2)
                feather_mask_3c = np.dstack([feather_mask, feather_mask, feather_mask])

                blended_heal = img_u8.astype(np.float32) * (1.0 - feather_mask_3c) + healed_textured.astype(np.float32) * feather_mask_3c
                img = np.clip(blended_heal, 0.0, 255.0)
        except Exception:
            pass

    # 7. SkinFiner-Style Texture-Preserving Facial Skin Smoothing (only skin/face, pores preserved)
    skin_smoothing = float(getattr(params, 'skin_smoothing', 0.0) or 0.0)
    if skin_smoothing > 1.0:
        try:
            h, w = img.shape[:2]
            img_u8 = np.clip(img, 0, 255).astype(np.uint8)

            # A. Precise Skin Mask (YCrCb + HSV)
            ycrcb = cv2.cvtColor(img_u8, cv2.COLOR_RGB2YCrCb)
            Y = ycrcb[:, :, 0]
            Cr = ycrcb[:, :, 1]
            Cb = ycrcb[:, :, 2]

            hsv = cv2.cvtColor(img_u8, cv2.COLOR_RGB2HSV)
            S = hsv[:, :, 1]
            V = hsv[:, :, 2]

            # Detect genuine human skin pixels across all Indian skin tones
            skin_base = (Cr >= 128) & (Cr <= 180) & (Cb >= 75) & (Cb <= 135) & (Y >= 32) & (S >= 15) & (S <= 215)

            # B. Protect Facial Features: Eyes, Eyebrows, Lips, Nostrils, Jewelry & Hair
            gray = cv2.cvtColor(img_u8, cv2.COLOR_RGB2GRAY)
            sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            edge_mag = cv2.magnitude(sobelx, sobely)

            # Exclude true boundaries (eyelashes, pupils, dark hair, red lipstick), but preserve skin pores!
            protected_skin = skin_base & (edge_mag < 65.0) & (V > 38) & (Cr < 175)

            if np.any(protected_skin):
                skin_mask_f = protected_skin.astype(np.float32)
                ksize = max(7, (min(h, w) // 55) | 1)
                skin_mask_f = cv2.GaussianBlur(skin_mask_f, (ksize, ksize), 0)

                # C. Frequency Separation: Base (Smooth Tones) + High Frequency (Pores & Micro-texture)
                d = max(9, min(15, min(h, w) // 100)) | 1
                sigma_color = 55.0
                sigma_space = 35.0
                bilateral = cv2.bilateralFilter(img_u8, d=d, sigmaColor=sigma_color, sigmaSpace=sigma_space)

                # High-frequency layer preserves genuine skin pores and micro-details
                texture_blur = cv2.GaussianBlur(img_u8, (5, 5), 0)
                texture_high = img_u8.astype(np.float32) - texture_blur.astype(np.float32)

                # Retain 30% micro-texture so pores are authentic, while creamy smoothing is clearly visible!
                smooth_layer = np.clip(bilateral.astype(np.float32) + 0.30 * texture_high, 0, 255)

                # D. Blend selectively on skin with user-controlled slider
                strength_factor = min(0.85, (skin_smoothing / 100.0) * 0.85)
                alpha = skin_mask_f[:, :, np.newaxis] * strength_factor

                img = (img * (1.0 - alpha)) + (smooth_layer * alpha)
                img = np.clip(img, 0.0, 255.0)
        except Exception:
            pass

    # 8. AI Portrait Dodge & Burn (Subtle 3D Depth & Natural Highlighting)
    dodge_burn = float(getattr(params, 'dodge_burn', 0.0) or 0.0)
    if dodge_burn > 1.0:
        try:
            h, w = img.shape[:2]
            img_u8 = np.clip(img, 0, 255).astype(np.uint8)

            ycrcb = cv2.cvtColor(img_u8, cv2.COLOR_RGB2YCrCb)
            Y = ycrcb[:, :, 0].astype(np.float32)
            Cr = ycrcb[:, :, 1]
            Cb = ycrcb[:, :, 2]

            skin_mask = (Cr >= 133) & (Cr <= 175) & (Cb >= 77) & (Cb <= 127) & (Y >= 38)
            if np.any(skin_mask):
                ksize = max(11, (min(h, w) // 40) | 1)
                skin_mask_f = cv2.GaussianBlur(skin_mask.astype(np.float32), (ksize, ksize), 0)

                # Broad ambient lighting map
                k_ambient = max(31, (min(h, w) // 12) | 1)
                Y_ambient = cv2.GaussianBlur(Y, (k_ambient, k_ambient), 0)

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
