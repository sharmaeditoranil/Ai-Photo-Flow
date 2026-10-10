"""
Image Processing Service
Handles image loading (JPG/PNG/RAW), thumbnail generation, non-destructive editing pipeline, and high-res export.
"""
import os
import io
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from typing import Optional, Tuple, Dict, Any
from backend.core.interfaces import EditParameters
from backend.core.subject_model import SubjectDetectionEngine
from backend.core.face_model import OpenCVFaceModel
from backend.retouch import retouch_image, resolve_params as resolve_retouch_params
from backend.core.white_balance import apply_white_balance, effective_gains as wb_effective_gains

try:
    subject_engine = SubjectDetectionEngine()
except Exception:
    subject_engine = None

try:
    face_detector = OpenCVFaceModel()
except Exception:
    face_detector = None

APP_DATA_DIR = os.path.expanduser("~/.photoflow")
CACHE_DIR = os.path.join(APP_DATA_DIR, "cache")
os.makedirs(os.path.join(CACHE_DIR, "thumbnails"), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, "previews"), exist_ok=True)

from backend.services.raw_decoder import RAW_EXTENSIONS, decode_raw

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
            # Professional 16-bit linear development matched to the camera's own rendering (raw_decoder.py)
            return decode_raw(filepath, max_dim=max_dim)
        except Exception:
            # Unsupported / damaged RAW: fall back to its embedded camera JPEG below
            try:
                import rawpy
                with rawpy.imread(filepath) as raw:
                    thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    pil_img = ImageOps.exif_transpose(Image.open(io.BytesIO(thumb.data)))
                    if max_dim:
                        w, h = pil_img.size
                        scale = min(max_dim / max(w, h), 1.0)
                        if scale < 1.0:
                            pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
                    return np.array(pil_img.convert("RGB"))
            except Exception:
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
    orig_u8 = rgb_image if rgb_image.dtype == np.uint8 else np.clip(rgb_image, 0, 255).astype(np.uint8)
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

        if not detected_face_boxes and face_detector is not None:
            try:
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
            except Exception:
                pass

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
    src_u8 = orig_u8                       # camera colours, kept for the Skin Colour Lock (step 8.5)
    orig_u8 = None

    # 0. AI Skin Retouch (Heal -> Mattifier -> Skin Details -> Imperfections -> Skin Tone) on the
    #    camera's original pixels (skin keeps its natural colour there, so the per-person skin mask is
    #    complete even when white balance later cools the scene), gated by that mask.
    retouch_skin = None
    rt_params = resolve_retouch_params(params)
    if rt_params:
        try:
            img, rt_res = retouch_image(rgb_image, rt_params, want_masks=True)
            retouch_skin = rt_res.skin_mask
        except Exception:
            img = rgb_image.astype(np.float32)
            retouch_skin = None

    # 0.5. AI Auto White Balance (neutral colour, verified on skin tone)
    wb_gains = wb_effective_gains(getattr(params, 'auto_wb', None))
    if wb_gains is not None:
        try:
            img = np.clip(apply_white_balance(img, wb_gains), 0, 255).astype(np.float32)
        except Exception:
            pass

    # 1. Straighten / Rotate if non-zero
    if abs(params.straighten) > 0.2:
        center = (w / 2.0, h / 2.0)
        # Zoom just enough that the rotated frame has no empty / mirrored corners (crop-to-fill)
        th = np.radians(abs(params.straighten))
        fill = float(np.cos(th) + np.sin(th) * max(w, h) / float(min(w, h)))
        rot_mat = cv2.getRotationMatrix2D(center, params.straighten, fill)
        img = cv2.warpAffine(img, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if retouch_skin is not None:
            retouch_skin = cv2.warpAffine(retouch_skin, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        if src_u8 is not None:
            src_u8 = cv2.warpAffine(src_u8, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # 2. Advanced Exposure with Soft-Shoulder Highlight Roll-off
    if abs(params.exposure) > 0.01:
        ev_factor = 2.0 ** params.exposure
        if ev_factor > 1.0:
            # Boosting exposure on underexposed photos:
            # Lift shadows and midtones while rolling off smoothly at the top to prevent clipping
            # Photographic soft-knee transfer function: 255 * (1 - exp(-norm * ev)) / norm_max
            # (computed in-place in float32 to avoid 24MP float64 temporaries)
            norm_max = float(1.0 - np.exp(-ev_factor))
            img *= (-ev_factor / 255.0)
            np.exp(img, out=img)
            np.subtract(1.0, img, out=img)
            img *= (255.0 / max(0.01, norm_max))
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

        np.clip(img, 0.0, 255.0, out=img)

    # 3.5. Dual-Zone Adaptive Relighting (Luminous Subject & Radiant Background)
    subject_info = cached_subject_info or {}
    is_wide_shot = bool(subject_info.get("is_wide_shot", False))
    subject_mask = cached_subject_mask
    try:
        if subject_mask is None and subject_engine is not None:
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

            # Seamless feathered blend across the subject mask:
            # 1 + mask * sub_delta + (1 - mask) * bg_delta
            if abs(sub_delta) > 0.001 or abs(bg_delta) > 0.001:
                zone_gain = subject_mask * (sub_delta - bg_delta)
                zone_gain += (1.0 + bg_delta)
                img *= zone_gain[:, :, np.newaxis]
                del zone_gain
                np.clip(img, 0.0, 255.0, out=img)

        # 3.6 Subject Light: tame an over-lit subject (flash-blown faces, white outfits in sun) through the
        # feathered subject mask. Bright parts of the subject get the full correction, midtones a third of it,
        # so hair, eyes and jewellery detail keep their depth and the background is left alone.
        subj_ev = float(getattr(params, 'subject_exposure', 0.0) or 0.0)
        if abs(subj_ev) > 0.01 and subject_mask is not None:
            luma = img[:, :, 0] * (0.299 / 255.0) + img[:, :, 1] * (0.587 / 255.0) + img[:, :, 2] * (0.114 / 255.0)
            t = np.clip((luma - 0.40) / 0.45, 0.0, 1.0)
            weight = 0.35 + 0.65 * (t * t * (3.0 - 2.0 * t))
            if subj_ev > 0:
                weight = 1.0 - 0.65 * (t * t * (3.0 - 2.0 * t))   # lifting: protect what is already bright
            gain = 1.0 + np.clip(subject_mask, 0.0, 1.0) * weight * (2.0 ** subj_ev - 1.0)
            img *= gain[:, :, np.newaxis].astype(np.float32)
            del gain, weight, t, luma
            np.clip(img, 0.0, 255.0, out=img)
    except Exception:
        pass
    subject_mask = None

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
        # Blend 25% CLAHE for crisp micro-contrast without halos (much less on retouched skin)
        if retouch_skin is not None:
            w_cl = 0.25 * (1.0 - 0.8 * retouch_skin)
            L = L * (1.0 - w_cl) + clahe_L * w_cl
            del w_cl
        else:
            L = L * 0.75 + clahe_L * 0.25
    except Exception:
        pass

    # E.2. Subtle Dehaze (only if atmospheric haze, fog, or lens flare veil is present)
    # User requirement: "halka sa dehaze ekdam halaka sa use karna hai agar jaruri ho tab"
    try:
        dark_ch = np.minimum(np.minimum(img[:, :, 0], img[:, :, 1]), img[:, :, 2])
        haze_floor = float(np.percentile(dark_ch, 2))
        del dark_ch
        # Clear photos have haze_floor < 12.0. Hazy/foggy photos have elevated black floor >= 16.0
        if haze_floor > 16.0:
            haze_strength = float(np.clip((haze_floor - 14.0) * 0.35, 1.0, 10.0))
            haze_mask = np.clip((140.0 - L) / 140.0, 0.0, 1.0)
            L = np.clip(L - (haze_mask * haze_strength), 0.0, 255.0)
            del haze_mask
    except Exception:
        pass
    # The float RGB buffer is rebuilt from LAB below; release it during the detail stage
    img = None
    clahe_L = None

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
        del grad_x, grad_y
        flat_mask = (edge_mag < 15.0)

        if np.sum(flat_mask) > 500:
            lap_a = cv2.Laplacian(lab[:, :, 1], cv2.CV_32F)
            lap_b = cv2.Laplacian(lab[:, :, 2], cv2.CV_32F)
            chroma_noise = max(float(np.std(lap_a[flat_mask])), float(np.std(lap_b[flat_mask])))
            del lap_a, lap_b
            if chroma_noise > 2.5:
                # Accelerate bilateral filter on downsampled chroma (4:2:0 principle)
                ah, aw = lab.shape[:2]
                a_small = cv2.resize(lab[:, :, 1].astype(np.uint8), (aw // 2, ah // 2), interpolation=cv2.INTER_AREA)
                b_small = cv2.resize(lab[:, :, 2].astype(np.uint8), (aw // 2, ah // 2), interpolation=cv2.INTER_AREA)
                a_filt = cv2.bilateralFilter(a_small, d=7, sigmaColor=18, sigmaSpace=9)
                b_filt = cv2.bilateralFilter(b_small, d=7, sigmaColor=18, sigmaSpace=9)
                lab[:, :, 1] = cv2.resize(a_filt, (aw, ah), interpolation=cv2.INTER_LINEAR).astype(np.float32)
                lab[:, :, 2] = cv2.resize(b_filt, (aw, ah), interpolation=cv2.INTER_LINEAR).astype(np.float32)

        del flat_mask

        # 3. High-Pass Detail Extraction (Eyelashes, pupils, hair, fabric embroidery, jewelry facets)
        # crisp_boost = (high_pass_micro * 0.48 + high_pass_mid * 0.22), built in-place
        crisp_boost = cv2.GaussianBlur(L, (0, 0), sigmaX=0.85)
        np.subtract(L, crisp_boost, out=crisp_boost)
        crisp_boost *= 0.48

        high_pass_mid = cv2.GaussianBlur(L, (0, 0), sigmaX=1.75)
        np.subtract(L, high_pass_mid, out=high_pass_mid)
        high_pass_mid *= 0.22
        crisp_boost += high_pass_mid
        del high_pass_mid

        # 4. Authentic High-Pass Crisp Re-injection & Edge Enhancement
        # User requirement: "halka sa kam kariye jayada nhai ekdam halak sa kam kariyega"
        # edge_weight = 0.65 + 0.35 * clip((edge_mag - 10) / 40, 0, 1)
        edge_weight = edge_mag - 10.0
        del edge_mag
        edge_weight /= 40.0
        np.clip(edge_weight, 0.0, 1.0, out=edge_weight)
        edge_weight *= 0.35
        edge_weight += 0.65

        # Gentle, natural crisp enhancement: maintains full original sharpness + delicate crisp definition
        crisp_boost *= edge_weight
        del edge_weight
        # Retouched skin must stay smooth: re-sharpening it would bring the removed texture back
        if retouch_skin is not None:
            crisp_boost *= (1.0 - 0.8 * retouch_skin)
        L = L + crisp_boost
        del crisp_boost
        np.clip(L, 0.0, 255.0, out=L)

    except Exception:
        pass

    lab[:, :, 0] = np.clip(L, 0.0, 255.0)
    img = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)
    lab = None
    L = None

    # 5. Skin-Safe Vibrance & Saturation (Bypassed in Pure Light mode for 100% natural colors)
    if not is_pure_light and (abs(params.vibrance) > 0.1 or abs(params.saturation) > 0.1):
        hsv = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2HSV)
        S = hsv[:, :, 1].astype(np.float32) / 255.0

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
        del S
        img = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB).astype(np.float32)
        del hsv

    # 5.5. Luminance-Neutral gentle skin radiance (Signature Wedding Glow, kept subtle: no yellow cast)
    # Strictly bypassed in Pure Light mode so original colors remain 100% untouched!
    if not is_pure_light:
        try:
            if cached_skin_feather is not None:
                skin_f = cached_skin_feather

                # Measure pre-warmth perceived luminance
                Y_before = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]

                # Gentle warm skin radiance (red-led, no green, so skin glows without turning yellow)
                img[:, :, 0] *= (1.0 + (0.025 * skin_f))
                img[:, :, 2] *= (1.0 - (0.020 * skin_f))

                # Measure post-warmth perceived luminance
                Y_after = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]

                # Strictly preserve original luminance on skin pixels so exposure never overshoots!
                scale = np.where(skin_f > 0.05, Y_before / np.maximum(1.0, Y_after), 1.0)
                del Y_before, Y_after
                np.clip(scale, 0.90, 1.10, out=scale)

                img *= scale[:, :, np.newaxis]
                del scale
                np.clip(img, 0.0, 255.0, out=img)
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
                img_u8 = None

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
                del high_pts
                burn_mult = 1.0 - (contour_pts * db_strength * 0.07 * skin_mask_f)
                del contour_pts, Y, Y_ambient

                dodge_mult *= burn_mult
                del burn_mult
                np.clip(dodge_mult, 0.92, 1.15, out=dodge_mult)
                img *= dodge_mult[:, :, np.newaxis]
                del dodge_mult
                np.clip(img, 0.0, 255.0, out=img)
        except Exception:
            pass

    # 8.5. Skin Colour Lock: global steps (clean-colour cooling, contrast, highlight recovery) can leave skin
    #      ashy / pale. Skin gets back the camera's natural skin colour (never yellower than skin-natural,
    #      slightly richer), on the per-person retouch skin mask only.
    if retouch_skin is not None and src_u8 is not None:
        try:
            _skin_colour_lock(img, src_u8, retouch_skin)
        except Exception:
            pass

    # 9. Skin Glow: soft radiance on real skin only (per-person retouch skin mask: no eyes, lips, hair,
    #    clothes or background). Luminance-only, so the skin colour stays the same; it lifts the skin's own
    #    soft highlights (cheekbones, forehead, nose bridge) and fades out before white, so nothing clips.
    skin_glow = float(getattr(params, 'skin_glow', 0.0) or 0.0)
    if skin_glow > 0.5 and retouch_skin is not None:
        try:
            _apply_skin_glow(img, retouch_skin, skin_glow / 100.0)
        except Exception:
            pass

    # Final uint8 clipping
    return np.clip(img, 0, 255).astype(np.uint8)


SKIN_LOCK_HUE_MAX = 50.0     # Lab hue above this reads yellow: the lock never restores more yellow than this
SKIN_LOCK_HUE_MIN = 34.0     # below this skin reads pink / magenta
SKIN_LOCK_CHROMA = 1.04      # a touch richer than the camera, so skin looks healthy, not grey


def _skin_colour_lock(img: np.ndarray, src_u8: np.ndarray, skin_mask: np.ndarray) -> None:
    """In-place on float32 RGB 0..255. Shifts Lab a*/b* of the skin so its median colour matches the camera's
    skin colour (hue clamped to the natural range, chroma +4%). Luminance is untouched."""
    h, w = img.shape[:2]
    if src_u8.shape[:2] != (h, w) or skin_mask.shape[:2] != (h, w):
        return
    m = np.clip(skin_mask.astype(np.float32), 0.0, 1.0)
    s = min(1.0, 900.0 / float(max(h, w)))
    sw, sh = max(1, int(w * s)), max(1, int(h * s))
    ms = cv2.resize(m, (sw, sh), interpolation=cv2.INTER_AREA)
    core = ms > 0.6
    if int(core.sum()) < 60:
        return
    lab_src = cv2.cvtColor(cv2.resize(src_u8, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2LAB).astype(np.float32)
    cur_s = cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (sw, sh), interpolation=cv2.INTER_AREA)
    lab_cur = cv2.cvtColor(cur_s, cv2.COLOR_RGB2LAB).astype(np.float32)
    a0, b0 = float(np.median(lab_src[..., 1][core])) - 128.0, float(np.median(lab_src[..., 2][core])) - 128.0
    a1, b1 = float(np.median(lab_cur[..., 1][core])) - 128.0, float(np.median(lab_cur[..., 2][core])) - 128.0
    c0 = float(np.hypot(a0, b0))
    if c0 < 4.0:
        return                                        # monochrome-ish source: nothing to lock to
    hue = float(np.degrees(np.arctan2(b0, a0)))
    hue = float(np.clip(hue, SKIN_LOCK_HUE_MIN, SKIN_LOCK_HUE_MAX))
    c_t = c0 * SKIN_LOCK_CHROMA
    at, bt = c_t * np.cos(np.radians(hue)), c_t * np.sin(np.radians(hue))
    da, db = float(np.clip(at - a1, -12.0, 12.0)), float(np.clip(bt - b1, -12.0, 12.0))
    if abs(da) < 0.6 and abs(db) < 0.6:
        return
    # Weight: the skin mask with its feature holes (around eyes, lips, brows) filled, so the whole face shifts
    # as one surface - no grey rings around the mouth or eyes. Eye whites and teeth (bright, colourless in
    # the camera image) are left out so they never turn warm.
    k = max(3, int(0.04 * max(sw, sh))) | 1
    filled = cv2.morphologyEx(ms, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    holes = np.clip(filled - ms, 0.0, 1.0)
    c_src = np.hypot(lab_src[..., 1] - 128.0, lab_src[..., 2] - 128.0)
    whites = (c_src < 8.0) & (lab_src[..., 0] > 150.0)
    holes[whites] = 0.0
    w_s = np.maximum(ms, holes)
    w_s = cv2.GaussianBlur(w_s, (0, 0), max(1.0, 0.006 * max(sw, sh)))
    wgt = cv2.resize(w_s, (w, h), interpolation=cv2.INTER_LINEAR) * 0.9
    ys, xs = np.where(wgt > 0.002)
    if ys.size == 0:
        return
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    wb = wgt[y0:y1, x0:x1]
    region = img[y0:y1, x0:x1]
    lab = cv2.cvtColor(np.clip(region, 0, 255) / 255.0, cv2.COLOR_RGB2LAB)   # float: L 0..100, a/b ~ -127..127
    lab[..., 1] += da * wb
    lab[..., 2] += db * wb
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    np.clip(out, 0.0, 1.0, out=out)
    sel = wb > 0.002
    region[sel] = out[sel] * 255.0


def _apply_skin_glow(img: np.ndarray, skin_mask: np.ndarray, strength: float) -> None:
    """In-place on float32 RGB 0..255. Lift at strength 1.0: +4 levels on skin shadows up to +13 on the skin's
    soft highlights (auto 65%: about +3..+8), fading out on already bright skin; zero outside the skin mask."""
    h, w = img.shape[:2]
    if skin_mask.shape[:2] != (h, w):
        skin_mask = cv2.resize(skin_mask, (w, h), interpolation=cv2.INTER_LINEAR)
    m = np.clip(skin_mask.astype(np.float32), 0.0, 1.0)
    if float(m.max()) < 0.05:
        return
    # Work on a proxy for the soft (blurred) light layer; the mask edge is feathered so no outline shows
    s = min(1.0, 1200.0 / float(max(h, w)))
    sw, sh = max(1, int(w * s)), max(1, int(h * s))
    Y = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
    Ys = cv2.resize(Y, (sw, sh), interpolation=cv2.INTER_AREA)
    ms = cv2.resize(m, (sw, sh), interpolation=cv2.INTER_AREA)
    sel = ms > 0.5
    if int(sel.sum()) < 50:
        return
    lo = float(np.percentile(Ys[sel], 35))           # skin mid-tone
    hi = float(np.percentile(Ys[sel], 97))           # skin's own highlight level
    sigma = max(1.5, 0.006 * max(sw, sh))
    soft = cv2.GaussianBlur(Ys, (0, 0), sigma)        # soft light distribution over the face
    t = np.clip((soft - lo) / max(hi - lo, 8.0), 0.0, 1.0)
    t = t * t * (3.0 - 2.0 * t)                       # smooth highlight weight 0..1
    feather = cv2.GaussianBlur(ms, (0, 0), max(1.0, sigma * 0.5))
    lift_s = (4.0 + 9.0 * t) * feather * float(np.clip(strength, 0.0, 1.0))
    lift = cv2.resize(lift_s, (w, h), interpolation=cv2.INTER_LINEAR) * np.clip(m * 1.5, 0.0, 1.0)
    # Highlight protection: full glow up to well-lit skin (~165), fading to none before white
    lift *= np.clip((232.0 - Y) / 67.0, 0.0, 1.0)
    ratio = (Y + lift) / np.maximum(Y, 1.0)
    img *= ratio[:, :, None]
    np.clip(img, 0.0, 255.0, out=img)

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
            abs(getattr(params, 'subject_exposure', 0.0) or 0.0) < 0.01 and
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
            float(getattr(params, 'skin_glow', 0.0) or 0.0) < 1.0 and
            len(getattr(params, 'heal_spots', []) or []) == 0 and
            not (resolve_retouch_params(params) or {}).get("enabled", False) and
            wb_effective_gains(getattr(params, 'auto_wb', None)) is None
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
        _write_jpeg(target_path, full_rgb, jpeg_quality, source_path)
        return

    # 2. Photos with edits: apply accelerated pipeline
    full_rgb = load_image(source_path, max_dim=max_resolution)
    edited_rgb = apply_edit_pipeline(full_rgb, params)
    del full_rgb

    _write_jpeg(target_path, edited_rgb, jpeg_quality, source_path)


def _source_metadata(source_path: Optional[str], width: int, height: int) -> Tuple[Optional[bytes], Optional[bytes]]:
    """EXIF (orientation reset, new size, no stale thumbnail) and ICC profile of the source image."""
    if not source_path:
        return None, None
    if is_raw_format(source_path):
        return _raw_exif(source_path, width, height), None
    exif_bytes, icc = None, None
    try:
        with Image.open(source_path) as src:
            icc = src.info.get("icc_profile")
            raw_exif = src.info.get("exif")
        if raw_exif:
            import piexif
            exif = piexif.load(raw_exif)
            exif["0th"][piexif.ImageIFD.Orientation] = 1  # pixels are already upright
            exif["0th"][piexif.ImageIFD.Software] = b"Ai PhotoFlow"
            exif["Exif"][piexif.ExifIFD.PixelXDimension] = int(width)
            exif["Exif"][piexif.ExifIFD.PixelYDimension] = int(height)
            exif["1st"] = {}
            exif["thumbnail"] = None
            exif.get("Exif", {}).pop(piexif.ExifIFD.MakerNote, None)  # often too large / camera-specific
            exif_bytes = piexif.dump(exif)
    except Exception:
        exif_bytes = None
    return exif_bytes, icc


def _raw_exif(source_path: str, width: int, height: int) -> Optional[bytes]:
    """Camera EXIF for photos developed from RAW: read from the RAW itself (TIFF-based NEF/ARW/CR2/DNG/ORF/
    PEF ...) or from its embedded camera JPEG (CR3, RAF ...). Only portable tags are copied: camera, lens,
    date, exposure, ISO, GPS, author / copyright. RAW-internal structure tags are dropped."""
    import piexif
    data = None
    try:
        data = piexif.load(source_path)
    except Exception:
        try:
            import rawpy
            with rawpy.imread(source_path) as raw:
                thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                with Image.open(io.BytesIO(thumb.data)) as im:
                    if im.info.get("exif"):
                        data = piexif.load(im.info["exif"])
        except Exception:
            data = None
    if not data:
        return None
    I = piexif.ImageIFD
    keep_0th = (I.Make, I.Model, I.DateTime, I.Artist, I.Copyright, I.ImageDescription, I.XResolution, I.YResolution, I.ResolutionUnit)
    zeroth = {k: v for k, v in (data.get("0th") or {}).items() if k in keep_0th}
    zeroth[I.Orientation] = 1                  # pixels are already upright
    zeroth[I.Software] = b"Ai PhotoFlow"
    exif_ifd = {k: v for k, v in (data.get("Exif") or {}).items() if k != piexif.ExifIFD.MakerNote}
    exif_ifd[piexif.ExifIFD.PixelXDimension] = int(width)
    exif_ifd[piexif.ExifIFD.PixelYDimension] = int(height)
    strip = lambda d: {k: (v.rstrip(b"\x00 ") if isinstance(v, bytes) else v) for k, v in d.items()}
    out = {"0th": strip(zeroth), "Exif": strip(exif_ifd), "GPS": data.get("GPS") or {}, "1st": {}, "thumbnail": None}
    for attempt in range(2):
        try:
            return piexif.dump(out)
        except Exception:
            # Drop vendor tags piexif cannot serialise and retry once
            out["Exif"] = {k: v for k, v in out["Exif"].items() if k in piexif.TAGS["Exif"]}
            out["GPS"] = {k: v for k, v in out["GPS"].items() if k in piexif.TAGS["GPS"]}
    return None


def _insert_icc(jpeg: bytes, icc: bytes) -> bytes:
    """Insert an ICC profile as APP2 ICC_PROFILE segments right after the JPEG SOI marker."""
    chunk = 65519
    parts = [icc[i:i + chunk] for i in range(0, len(icc), chunk)]
    segs = b""
    for i, part in enumerate(parts, 1):
        payload = b"ICC_PROFILE\x00" + bytes([i, len(parts)]) + part
        segs += b"\xff\xe2" + (len(payload) + 2).to_bytes(2, "big") + payload
    return jpeg[:2] + segs + jpeg[2:]


def _write_jpeg(target_path: str, rgb: np.ndarray, jpeg_quality: int, source_path: Optional[str] = None) -> None:
    """Hardware-accelerated SIMD JPEG write that keeps the source EXIF (camera, lens, date, GPS) and
    ICC profile. Encodes in memory and writes via numpy so Windows paths with spaces or non-ASCII
    characters work (cv2.imwrite fails silently there)."""
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)])
    if not ok:
        raise IOError(f"JPEG encoding failed for {target_path}")
    data = buf.tobytes()
    exif_bytes, icc = _source_metadata(source_path, rgb.shape[1], rgb.shape[0])
    if icc:
        try:
            data = _insert_icc(data, icc)
        except Exception:
            pass
    if exif_bytes:
        try:
            import piexif
            out = io.BytesIO()
            piexif.insert(exif_bytes, data, out)
            data = out.getvalue()
        except Exception:
            pass
    with open(target_path, "wb") as fh:
        fh.write(data)
