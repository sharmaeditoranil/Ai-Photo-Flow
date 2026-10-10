"""
Wedding Photography Auto-Editing Model
Calculates photo-specific corrections with natural Indian skin tone protection.
"""
import cv2
import numpy as np
from typing import Optional, Dict, Any
from backend.core.interfaces import EditingModel, EditParameters, FaceMetrics
from backend.core.subject_model import SubjectDetectionEngine
from backend.retouch.params import build_preset as build_retouch_preset
from backend.core.white_balance import analyze_white_balance

class IndianWeddingEditingModel(EditingModel):
    def __init__(self):
        self.subject_engine = SubjectDetectionEngine()

    PRESET_MODIFIERS = {
        # 1. Pure Lighting Balance (No Color Cast / 100% Original Colors)
        "Pure Light (No Color Tone)": {
            "exp_target": 138.0,
            "contrast_bias": 2.0,
            "temp_bias": 0.0,          # Zero color cast, pure light
            "vibrance_bias": 0.0,
            "sat_bias": 0.0,
            "highlights_bias": -16.0,
            "shadows_bias": 20.0,
            "sharpen_bias": 20.0,
            "color_badge": "#94a3b8",
            "description": "Only exposure & shadow balance. No color alteration, 100% natural."
        },
        # 2. Royal Cool Blue (Modern Magazine Look)
        "Royal Cool Blue": {
            "exp_target": 140.0,
            "contrast_bias": 4.0,
            "temp_bias": -4.0,         # Subtle cool blue tone (on top of the clean-colour finish)
            "vibrance_bias": 8.0,
            "sat_bias": 2.0,
            "highlights_bias": -20.0,
            "shadows_bias": 22.0,
            "sharpen_bias": 20.0,
            "color_badge": "#38bdf8",
            "description": "Crisp cool blue tone, removes indoor yellow casts."
        },
        # 3. Warm Golden Amber (Haldi & Mandap)
        "Warm Golden Amber": {
            "exp_target": 138.0,
            "contrast_bias": 5.0,
            "temp_bias": 8.0,          # Rich golden yellow tone
            "vibrance_bias": 10.0,
            "sat_bias": 4.0,
            "highlights_bias": -20.0,
            "shadows_bias": 18.0,
            "sharpen_bias": 18.0,
            "color_badge": "#f59e0b",
            "description": "Golden sunlight warmth, perfect for Haldi, Mehndi & Mandap."
        },
        # 4. Vibrant Royal Wedding (Sangeet & Deep Silks)
        "Vibrant Royal Wedding": {
            "exp_target": 140.0,
            "contrast_bias": 8.0,
            "temp_bias": -2.0,
            "vibrance_bias": 18.0,
            "sat_bias": 8.0,
            "highlights_bias": -22.0,
            "shadows_bias": 20.0,
            "sharpen_bias": 22.0,
            "color_badge": "#ef4444",
            "description": "Red lehenga, emeralds, jewelry sparkle & deep rich silks."
        },
        # 5. Soft Pastel & Airy (Daylight Garden)
        "Soft Pastel & Airy": {
            "exp_target": 148.0,
            "contrast_bias": -6.0,
            "temp_bias": -3.0,
            "vibrance_bias": 4.0,
            "sat_bias": -2.0,
            "highlights_bias": -28.0,
            "shadows_bias": 32.0,
            "sharpen_bias": 14.0,
            "color_badge": "#ec4899",
            "description": "Bright airy high-key exposure with gentle soft pastels for outdoors."
        },
        # 6. Moody Cinematic Film (Matte Shadows)
        "Moody Cinematic Film": {
            "exp_target": 132.0,
            "contrast_bias": -4.0,
            "temp_bias": -5.0,
            "vibrance_bias": -2.0,
            "sat_bias": -6.0,
            "highlights_bias": -16.0,
            "shadows_bias": 26.0,
            "sharpen_bias": 14.0,
            "color_badge": "#8b5cf6",
            "description": "Deep matte blacks with editorial cinematic magazine character."
        },
        # 7. Clean Ivory Neutral (True Whites & Fair Skin)
        "Clean Ivory Neutral": {
            "exp_target": 140.0,
            "contrast_bias": 3.0,
            "temp_bias": -4.0,
            "vibrance_bias": 6.0,
            "sat_bias": 1.0,
            "highlights_bias": -16.0,
            "shadows_bias": 18.0,
            "sharpen_bias": 20.0,
            "color_badge": "#f1f5f9",
            "description": "Spotless whites for bridal gowns, ivory sherwanis & clear skin."
        },
        # 8. Sunset Golden Hour (Romantic Dusk Glow)
        "Sunset Golden Hour": {
            "exp_target": 136.0,
            "contrast_bias": 7.0,
            "temp_bias": 12.0,
            "vibrance_bias": 12.0,
            "sat_bias": 6.0,
            "highlights_bias": -24.0,
            "shadows_bias": 16.0,
            "sharpen_bias": 18.0,
            "color_badge": "#ea580c",
            "description": "Romantic golden hour warmth for couple portraits and sunset rituals."
        },
        # 9. Vintage Nostalgia (Classic Analog Tone)
        "Vintage Nostalgia": {
            "exp_target": 135.0,
            "contrast_bias": 3.0,
            "temp_bias": 3.0,
            "vibrance_bias": 4.0,
            "sat_bias": -3.0,
            "highlights_bias": -18.0,
            "shadows_bias": 22.0,
            "sharpen_bias": 16.0,
            "color_badge": "#d97706",
            "description": "Timeless warm nostalgic film character with soft organic highlights."
        },
        # 10. High Contrast Punch (Stage & Flash Drama)
        "High Contrast Punch": {
            "exp_target": 142.0,
            "contrast_bias": 12.0,
            "temp_bias": -2.0,
            "vibrance_bias": 14.0,
            "sat_bias": 5.0,
            "highlights_bias": -24.0,
            "shadows_bias": 15.0,
            "sharpen_bias": 24.0,
            "color_badge": "#10b981",
            "description": "Crisp dynamic punch for high-energy stages and night receptions."
        },
        # Backwards compatibility aliases
        "Natural Wedding": "Pure Light (No Color Tone)",
        "Bright Wedding": "Soft Pastel & Airy",
        "Warm Wedding": "Warm Golden Amber",
        "Cinematic Soft": "Moody Cinematic Film",
        "Clean Neutral": "Clean Ivory Neutral",
        "My Custom Preset": "Royal Cool Blue"
    }

    def detect_straighten_angle(self, gray: np.ndarray) -> float:
        """Horizon / vertical tilt from LONG straight structures only (door frames, pillars, walls, horizon).
        People, saree patterns and decor give short or random lines and never rotate a photo. A correction is
        made only when the long lines clearly agree; max 3 degrees (a candid frame is never swung around)."""
        try:
            h, w = gray.shape[:2]
            small = cv2.GaussianBlur(gray, (3, 3), 0)
            edges = cv2.Canny(small, 60, 160, apertureSize=3)
            min_len = int(0.18 * min(h, w))
            lines = cv2.HoughLinesP(edges, 1, np.pi / 360, threshold=80, minLineLength=min_len, maxLineGap=6)
            if lines is None:
                return 0.0
            vert, horiz = [], []        # (visual counter-clockwise tilt of the scene in degrees, length)
            for x1, y1, x2, y2 in lines[:, 0, :]:
                dx, dy = float(x2 - x1), float(y2 - y1)
                length = float(np.hypot(dx, dy))
                if abs(dy) >= abs(dx):                            # vertical family, point it downwards
                    if dy < 0:
                        dx, dy = -dx, -dy
                    tilt = float(np.degrees(np.arctan2(dx, dy)))  # CCW scene tilt pushes the bottom end right
                    if abs(tilt) <= 5.0:
                        vert.append((tilt, length))
                else:                                             # horizontal family, point it rightwards
                    if dx < 0:
                        dx, dy = -dx, -dy
                    tilt = float(-np.degrees(np.arctan2(dy, dx)))  # CCW scene tilt lifts the right end (y up)
                    if abs(tilt) <= 5.0:
                        horiz.append((tilt, length))

            def consensus(items, min_total):
                if len(items) < 3:
                    return None
                a = np.array([t for t, _ in items]); L = np.array([l for _, l in items])
                if L.sum() < min_total:
                    return None
                order = np.argsort(a); cw = np.cumsum(L[order])
                med = float(a[order][np.searchsorted(cw, cw[-1] / 2.0)])
                mad = float(np.sum(np.abs(a - med) * L) / L.sum())
                return med if mad <= 0.8 else None

            # Verticals are trustworthy at any distance; horizontals (floors, tables) suffer perspective
            angle = consensus(vert, 1.2 * h)
            if angle is None:
                angle = consensus([it for it in horiz if it[1] >= 0.35 * w], 1.5 * w)
            if angle is None or abs(angle) < 0.5:
                return 0.0
            # getRotationMatrix2D: positive = counter-clockwise, so undo a CCW tilt with a negative angle
            return round(float(np.clip(-angle, -3.0, 3.0)), 1)
        except Exception:
            pass
        return 0.0

    def analyze_indian_skin_chroma(self, rgb_image: np.ndarray) -> Dict[str, float]:
        """
        Analyzes skin pixels to preserve warm Indian undertones without oversaturating or casting magenta.
        Skin range in YCrCb: Cr in [133, 173], Cb in [77, 127]
        """
        try:
            ycrcb = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2YCrCb)
            cr = ycrcb[:, :, 1]
            cb = ycrcb[:, :, 2]
            # Skin mask
            skin_mask = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
            skin_pixel_count = int(np.sum(skin_mask))
            total_pixels = rgb_image.shape[0] * rgb_image.shape[1]

            if skin_pixel_count > (total_pixels * 0.02):
                avg_cr = float(np.mean(cr[skin_mask]))
                avg_cb = float(np.mean(cb[skin_mask]))
                return {
                    "has_skin": True,
                    "skin_coverage": skin_pixel_count / total_pixels,
                    "avg_cr": avg_cr,
                    "avg_cb": avg_cb
                }
        except Exception:
            pass
        return {"has_skin": False, "skin_coverage": 0.0, "avg_cr": 145.0, "avg_cb": 105.0}

    def classify_shot_genre(
        self,
        faces_count: int,
        mean_lum: float,
        warmth: float,
        has_skin: bool,
        scene_group: Optional[str] = None
    ) -> str:
        """
        Classifies photographic genre to apply bespoke Subject-First tonal recipes:
        - 'Solo Portrait & Makeup' (1 face, delicate skin protection, radiant eye illumination)
        - 'Couple Portrait' (2 faces, bride lehenga & groom sherwani harmony)
        - 'Family & Stage Group' (>= 3 faces, deep shadow fill across multi-row crowd)
        - 'Mandap & Sacred Pheras' (Havankund fire warmth, cooling excess fiery cast on skin)
        - 'Night Reception & Dance' (Low light, taming DJ color spots, high ISO shadow lift)
        - 'Outdoor Sunlight & Garden' (Daylight, harsh sun shadow fill, sky highlight recovery)
        - 'Décor, Rituals & Macro Details' (0 faces, rings, shoes, mandap flowers, rich vibrance & clarity)
        """
        if scene_group and scene_group in ["Bride Makeup", "Groom Preparation"]:
            return "Solo Portrait & Makeup"
        if scene_group == "Mandap & Ceremony":
            return "Mandap & Sacred Pheras"
        if scene_group == "Reception & Sangeet":
            return "Night Reception & Dance"
        if scene_group == "Outdoor Portraits":
            return "Outdoor Sunlight & Garden"

        if faces_count == 0:
            if warmth > 28.0 and has_skin:
                return "Mandap & Sacred Pheras"
            return "Décor, Rituals & Macro Details"
        elif faces_count == 1:
            return "Solo Portrait & Makeup"
        elif faces_count == 2:
            return "Couple Portrait"
        elif faces_count >= 3:
            return "Family & Stage Group"
        elif mean_lum < 82.0:
            return "Night Reception & Dance"
        elif warmth > 25.0:
            return "Mandap & Sacred Pheras"
        elif mean_lum > 140.0:
            return "Outdoor Sunlight & Garden"

        return "Couple Portrait"

    def calculate_corrections(
        self,
        image_np: np.ndarray,
        preset_name: str = "Natural Wedding",
        scene_group: Optional[str] = None,
        return_mask: bool = False,
        face_metrics: Optional[FaceMetrics] = None,
        retouch_preset: str = "Natural",
        calibrate: bool = True
    ):
        """
        Calculates individualized parameters based on image histogram and skin tone constraints.
        Optionally returns computed subject_mask and subject_info to avoid redundant detection.
        Optionally accepts pre-computed face_metrics to avoid duplicate face detection.
        """
        if image_np is None or image_np.size == 0:
            default_p = EditParameters(preset_name=preset_name)
            return (default_p, (None, {})) if return_mask else default_p

        if len(image_np.shape) == 2:
            rgb = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
            gray = image_np
        else:
            rgb = image_np if image_np.shape[2] == 3 else image_np[:, :, :3]
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        preset = self.PRESET_MODIFIERS.get(preset_name, self.PRESET_MODIFIERS["Pure Light (No Color Tone)"])
        if isinstance(preset, str):
            preset = self.PRESET_MODIFIERS.get(preset, self.PRESET_MODIFIERS["Pure Light (No Color Tone)"])
        target_lum = preset["exp_target"]

        # 1. AI Subject Detection: Isolate Subject from Background (reusing face_metrics if available)
        subject_mask, subject_info = self.subject_engine.generate_subject_mask(rgb, face_metrics=face_metrics)
        sub_lum = subject_info["subject_lum"]
        bg_lum = subject_info["bg_lum"]

        # Percentiles of the Subject specifically
        sub_pixels = gray[subject_mask > 0.35]
        if len(sub_pixels) > 50:
            sub_p5 = float(np.percentile(sub_pixels, 5))
            sub_p50 = float(np.percentile(sub_pixels, 50))
            sub_p95 = float(np.percentile(sub_pixels, 95))
        else:
            sub_p5 = float(np.percentile(gray, 5))
            sub_p50 = float(np.percentile(gray, 50))
            sub_p95 = float(np.percentile(gray, 95))

        p99 = float(np.percentile(gray, 99))
        p75 = float(np.percentile(gray, 75))
        p25 = float(np.percentile(gray, 25))

        # 2. Subject-First Lighting & Exposure Metering:
        # 2. Subject-First Lighting & Exposure Metering:
        # User Requirement: "Photo Editing me sabse pahle pic me subject ko dekhna hai uske hisab se light Adjust karna hai"
        # "Jis Pic me Background Dark rah raha hai usme subject me light jayada ho ja rah hai"
        ycrcb_meter = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
        cr_meter = ycrcb_meter[:, :, 1]
        cb_meter = ycrcb_meter[:, :, 2]
        skin_meter = (cr_meter >= 128) & (cr_meter <= 180) & (cb_meter >= 75) & (cb_meter <= 135) & (ycrcb_meter[:, :, 0] >= 32)

        # Subject-first priority: focus on subject's face & skin
        skin_in_subject = skin_meter & (subject_mask > 0.20)
        has_subject_skin = np.sum(skin_in_subject) > 30

        # Contrast ratio between subject and background
        ratio = sub_lum / max(1.0, bg_lum)
        is_dark_bg = (bg_lum < 58.0) or (ratio > 1.35 and sub_lum > 45.0)

        subject_skin_ref = None
        if has_subject_skin or np.sum(skin_meter) > 40:
            target_skin_pixels = gray[skin_in_subject] if has_subject_skin else gray[skin_meter]
            skin_median = float(np.median(target_skin_pixels))
            subject_skin_ref = skin_median

            if is_dark_bg:
                # Dark background (night, dark hall, stage, black backdrop):
                # The subject is already naturally prominent against dark surroundings.
                # Strictly prevent subject blowout or excessive lighting!
                if skin_median >= 95.0 or sub_lum >= 90.0:
                    # Subject is already well-lit: 0.0 EV (perfect exposure, zero blowout!)
                    exposure = 0.0
                elif skin_median >= 75.0:
                    # Very gentle photographic fill (max +0.10 EV)
                    deficit = 105.0 / max(30.0, skin_median)
                    raw_ev = float(np.log2(max(1.0, deficit)))
                    exposure = float(np.clip(raw_ev * 0.20, 0.0, 0.10))
                else:
                    # Underexposed subject: lift smoothly without blowing highlights
                    deficit = 110.0 / max(25.0, skin_median)
                    raw_ev = float(np.log2(max(1.0, deficit)))
                    exposure = float(np.clip(raw_ev * 0.30, 0.0, 0.20))
            else:
                # Normal / daylight background:
                if skin_median < 130.0:
                    deficit = target_lum / max(30.0, skin_median)
                    raw_ev = float(np.log2(max(1.0, deficit)))
                    exposure = float(np.clip(raw_ev * 0.45 + 0.05, 0.05, 0.40))
                elif 130.0 <= skin_median <= 160.0:
                    exposure = 0.05
                else:
                    excess = 160.0 / skin_median
                    raw_ev = float(np.log2(max(0.1, excess)))
                    exposure = float(np.clip(raw_ev * 0.40, -0.30, 0.0))
        else:
            # Detail/Macro/Decor shots (no human faces)
            sub_metric = float(sub_lum * 0.65 + sub_p50 * 0.35)
            if is_dark_bg:
                exposure = 0.0 if sub_metric >= 85.0 else 0.10
            elif sub_metric < 135.0:
                deficit = target_lum / max(30.0, sub_metric)
                raw_ev = float(np.log2(max(1.0, deficit)))
                exposure = float(np.clip(raw_ev * 0.45 + 0.05, 0.05, 0.35))
            else:
                exposure = 0.05

        # 3. Dynamic Range: Protect Subject & Background Highlights & Lift Shadows
        # Highlights: soften flash hotspots on forehead, jewelry, and specular bounce
        bg_excess = max(0.0, bg_lum - 135.0) if bg_lum > 135.0 else 0.0
        if is_dark_bg:
            # On dark backgrounds, roll off highlights to keep skin matte and prevent harsh glare
            highlights = float(np.clip(min(-24.0, preset["highlights_bias"]), -60.0, -20.0))
        elif sub_p95 > 215.0 or p99 > 238.0 or bg_excess > 0:
            highlight_severity = max(0.0, (sub_p95 - 215.0) * 0.85 + (p99 - 238.0) * 1.1 + bg_excess * 0.7)
            highlights = float(np.clip(preset["highlights_bias"] - highlight_severity, -60.0, -12.0))
        else:
            highlights = preset["highlights_bias"]

        # Shadows: lift dark wedding attire (sherwani, suits) only where subject shadows are crushed
        # Do NOT lift shadows due to dark backgrounds (a dark background is meant to stay dark!)
        if is_dark_bg:
            shadows = float(preset["shadows_bias"])
        elif sub_p5 < 35.0:
            shadow_deficit = (35.0 - sub_p5) * 0.6
            shadows = float(np.clip(preset["shadows_bias"] + shadow_deficit, 15.0, 35.0))
        else:
            shadows = float(preset["shadows_bias"])

        # Contrast: S-curve punch
        iqr = p75 - p25
        if iqr < 55:
            contrast = min(32.0, (55.0 - iqr) * 0.75 + preset["contrast_bias"])
        elif iqr > 115:
            contrast = max(-18.0, -((iqr - 115.0) * 0.4) + preset["contrast_bias"])
        else:
            contrast = preset["contrast_bias"]

        # Whites & Blacks Anchor
        # On dark background, prevent whites from artificially inflating upper midtones on the subject
        if is_dark_bg:
            whites = float(np.clip((242.0 - sub_p95) * 0.08, -10.0, 2.0))
            blacks = float(np.clip((sub_p5 - 10.0) * 0.20, -10.0, 5.0))
        else:
            whites = float(np.clip((242.0 - sub_p95) * 0.20, -14.0, 14.0))
            blacks = float(np.clip((sub_p5 - 10.0) * 0.20, -14.0, 10.0))

        # 4. Color Balance Focused on the Subject
        # Measure RGB on the subject region so background colored lights don't pollute skin tones
        sub_mask_3d = subject_mask > 0.3
        if np.any(sub_mask_3d):
            sub_r = float(np.mean(rgb[:, :, 0][sub_mask_3d]))
            sub_g = float(np.mean(rgb[:, :, 1][sub_mask_3d]))
            sub_b = float(np.mean(rgb[:, :, 2][sub_mask_3d]))
        else:
            sub_r = float(np.mean(rgb[:, :, 0]))
            sub_g = float(np.mean(rgb[:, :, 1]))
            sub_b = float(np.mean(rgb[:, :, 2]))

        rb_diff = sub_r - sub_b
        g_deviation = sub_g - ((sub_r + sub_b) / 2.0)

        # Preset-specific color grading
        is_pure_light = "Pure Light" in preset_name or preset_name == "Natural Wedding"
        if is_pure_light:
            auto_temp = 0.0
            auto_tint = 0.0
        else:
            # Neutral colour balance is handled by AI Auto White Balance (auto_wb below);
            # temperature / tint here only carry the preset's creative tone.
            auto_temp = float(np.clip(preset.get("temp_bias", 0.0), -28.0, 22.0))
            auto_tint = 0.0

        # 4. Indian Skin Tone Preservation & Vibrance
        skin_info = self.analyze_indian_skin_chroma(rgb)
        vibrance = preset["vibrance_bias"]
        saturation = preset["sat_bias"]

        if skin_info["has_skin"] and not is_pure_light:
            avg_cr = skin_info["avg_cr"] # high Cr = red/magenta flush
            if avg_cr > 148.0:
                # Skin is flushed warm, gently temper with crisp cool tone
                saturation = max(-6.0, saturation - 4.0)
                auto_temp = max(-12.0, auto_temp - 3.5)
                auto_tint = max(-8.0, auto_tint - 1.5)
            elif avg_cr < 140.0:
                # Skin looks washed out, gentle vibrance boost
                vibrance = min(22.0, vibrance + 6.0)


        # 5. Crisp Sharpening & Micro-Detail
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if lap_var < 100.0:
            sharpening = min(38.0, preset["sharpen_bias"] + 12.0)
            noise_reduction = 14.0
        elif lap_var > 650.0:
            sharpening = max(12.0, preset["sharpen_bias"] - 4.0)
            noise_reduction = 8.0
        else:
            sharpening = preset["sharpen_bias"]
            noise_reduction = 10.0

        # 6. Subject-First Genre Adaptation
        # Fine-tune dynamic range and color to serve the primary subject across all shoot types
        genre = self.classify_shot_genre(
            faces_count=subject_info.get("faces_count", 0),
            mean_lum=float(np.mean(gray)),
            warmth=rb_diff,
            has_skin=skin_info["has_skin"],
            scene_group=scene_group
        )

        if genre == "Solo Portrait & Makeup":
            # Priority: Soft radiant skin, protect forehead/cheek shine, lift eye shadows
            highlights = min(highlights, -22.0)
            shadows = max(shadows, 20.0)
            contrast = float(np.clip(contrast, -4.0, 8.0))
            noise_reduction = max(noise_reduction, 12.0)
        elif genre == "Couple Portrait":
            # Priority: Bride lehenga & Groom sherwani harmony
            highlights = min(highlights, -20.0)
            shadows = max(shadows, 18.0)
            vibrance = min(18.0, vibrance + 2.0)
        elif genre == "Family & Stage Group":
            # Priority: Deep shadow fill so back-row family members are well-lit
            shadows = max(shadows, 22.0)
            contrast = max(contrast, 6.0)
            whites = max(whites, 2.0)
            blacks = min(blacks, 4.0)
            sharpening = min(36.0, sharpening + 4.0)
        elif genre == "Mandap & Sacred Pheras":
            # Priority: Sacred fire highlights recovered, cooling excess orange/yellow cast on skin
            highlights = min(highlights, -28.0)
            shadows = max(shadows, 22.0)
            if skin_info["has_skin"]:
                auto_temp = max(-16.0, auto_temp - 3.5)
                saturation = max(-8.0, saturation - 3.0)
        elif genre == "Night Reception & Dance":
            # Priority: Lift dark venue shadows, clean high ISO grain, tame DJ color spill on faces
            shadows = max(shadows, 28.0)
            noise_reduction = min(noise_reduction, 5.0)
            whites = min(whites, 6.0)
        elif genre == "Outdoor Sunlight & Garden":
            # Priority: Harsh sun shadow fill under brows/noses, sky highlight recovery
            highlights = min(highlights, -28.0)
            shadows = max(shadows, 22.0)
            vibrance = min(18.0, vibrance + 4.0)
        elif genre == "Décor, Rituals & Macro Details":
            # Priority: Intricate jewelry sparkle, flower saturation, rich embroidery contrast
            vibrance = max(vibrance, 14.0)
            contrast = max(contrast, 8.0)
            highlights = min(highlights, -18.0)
            sharpening = max(sharpening, 32.0)

        # 6b. Depth guard: dark hair / suits / backgrounds are not a reason to lift shadows when the faces are
        #     already well lit; a big lift there only flattens the portrait (milky, low-depth look)
        if subject_skin_ref is not None and not is_dark_bg:
            if subject_skin_ref >= 115.0:
                shadows = float(min(shadows, 14.0))
            elif subject_skin_ref >= 95.0:
                shadows = float(min(shadows, 22.0))

        # 7. Straightening angle
        straighten = self.detect_straighten_angle(gray)

        # User Requirement: Pure Light mode must have 0% color modification, only lighting balance
        if is_pure_light:
            auto_temp = 0.0
            auto_tint = 0.0
            vibrance = 0.0
            saturation = 0.0
        else:
            # User Requirement: "Editing me 5% Vibrance Add kariye sabhi pic me"
            vibrance = float(np.clip(vibrance + 5.0, 5.0, 35.0))

        # User Requirement: "Sharpness jayada ho gaya hai halka sa kam kariye jayada nhai ekdam halak sa kam kariyega"
        sharpening = float(np.clip(sharpening * 1.05, 22.0, 48.0))


        # Skin smoothing now lives in the AI Skin Retouch block (skin-mask gated, per-face scale);
        # the engine skips photos without a detected face. Gentle 3D Dodge & Burn stays.
        auto_skin_smooth = 0.0
        auto_dodge_burn = 20.0
        auto_skin_glow = 65.0      # owner: "halka sa skin pe glow" - soft radiance on skin only
        retouch_block = build_retouch_preset(retouch_preset or "Natural")

        # AI Auto White Balance: grey-pixel / grey-edge / white-patch illuminant estimate,
        # verified against the skin tone of every detected face. Applied in every preset.
        try:
            auto_wb = analyze_white_balance(rgb)
        except Exception:
            auto_wb = None

        # Subject-first over-light control: the subject (faces / people found by the subject engine) decides.
        # If the subject's skin is brighter than a natural portrait level, bring the SUBJECT down through
        # subject_exposure (mask-based, mostly in its highlights). The whole frame only shares part of the
        # correction when the background is bright as well; a dark background stays as it is.
        SKIN_TARGET_MAX = 158.0          # gray level of well-exposed (Indian) skin under flash / daylight
        SUBJECT_TARGET_MAX = 182.0       # subjects without visible skin (bridal outfit, decor close-ups)
        subject_exposure = 0.0
        subject_hot = False
        if subject_skin_ref is not None and subject_skin_ref > SKIN_TARGET_MAX:
            need_ev = float(np.log2(SKIN_TARGET_MAX / subject_skin_ref))
            subject_hot = True
        elif subject_skin_ref is None and subject_info.get("has_subject", False) and sub_p50 > SUBJECT_TARGET_MAX:
            need_ev = float(np.log2(SUBJECT_TARGET_MAX / sub_p50)) * 0.7
            subject_hot = True
        if subject_hot:
            need_ev = max(need_ev, -0.95)
            global_share = 0.0 if is_dark_bg else (0.45 if bg_lum >= 140.0 else 0.2)
            exposure = float(min(exposure, need_ev * global_share)) if global_share > 0 else float(min(exposure, 0.0))
            # The subject gets whatever the global exposure did not already take off (in subject-weighted EV)
            subject_exposure = float(np.clip(need_ev - min(0.0, exposure), -0.95, 0.0))
            highlights = float(min(highlights, -35.0))
            # Keep the picture crisp after pulling light down: clean whites, a touch more contrast, deeper blacks
            whites = float(max(whites, 0.0))
            contrast = float(max(contrast, preset["contrast_bias"] + 8.0))
            blacks = float(min(blacks, -5.0))
        else:
            # Owner's house look: a very gentle overall lift (+0.06 EV). Near-clipped photos get only +0.02
            # so whites, jewellery and flash highlights never blow out.
            brightness_lift = 0.02 if (p99 >= 246.0 or sub_p95 > 235.0) else 0.06
            exposure = float(min(0.45, exposure + brightness_lift))

        res_params = EditParameters(
            exposure=round(exposure, 2),
            subject_exposure=round(subject_exposure, 2),
            temperature=round(auto_temp, 1),
            tint=round(auto_tint, 1),
            contrast=round(contrast, 1),
            highlights=round(highlights, 1),
            shadows=round(shadows, 1),
            whites=round(whites, 1),
            blacks=round(blacks, 1),
            vibrance=round(vibrance, 1),
            saturation=round(saturation, 1),
            sharpness=round(sharpening, 1),
            noise_reduction=round(noise_reduction, 1),
            straighten=round(straighten, 1),
            preset_name=preset_name,
            auto_blemish=0.0,
            skin_smoothing=round(auto_skin_smooth, 1),
            dodge_burn=round(auto_dodge_burn, 1),
            skin_glow=round(auto_skin_glow, 1),
            retouch=retouch_block,
            auto_wb=auto_wb
        )
        # Closed-loop finishing: render a preview with these settings and measure it like an editor would
        # (subject light, haze, contrast, skin colour), then correct the settings. Accuracy over speed.
        if calibrate:
            try:
                self._calibrate_render(rgb, res_params, subject_mask, subject_info, skin_in_subject)
            except Exception:
                pass
            try:
                self._calibrate_colour(rgb, res_params, subject_mask, subject_info)
            except Exception:
                pass

        if return_mask:
            return res_params, (subject_mask, subject_info)
        return res_params

    SUBJECT_SKIN_MAX = 160.0   # rendered skin brighter than this reads as "too much light" on the subject

    # Clean professional colour (owner: "yellow halka kam, halka blue tone"): whites / greys finish a touch
    # cool, skin stays natural - never yellow, never blue.
    NEUTRAL_B_TARGET = -1.5    # Lab b* of neutral surfaces after the edit (0 = pure grey, <0 = light blue)
    SKIN_HUE_YELLOW = 50.0     # Lab hue of skin above this reads yellow
    SKIN_HUE_COOL_FLOOR = 36.0 # never cool skin below this (grey / pink, lifeless)

    def _calibrate_colour(self, rgb, params, subject_mask, subject_info):
        """Closed-loop colour finish on a 900px render (full pipeline, creative preset tone excluded):
        adjusts the white-balance temperature until neutral surfaces (white clothes, walls, sky haze,
        steel, paper) sit at NEUTRAL_B_TARGET and no face reads yellow. Works on the final look, so every
        warming stage of the pipeline (contrast, vibrance, retouch) is accounted for."""
        from backend.services.image_service import apply_edit_pipeline   # lazy: avoids import cycle
        from backend.core.white_balance import _normalize_gains

        h, w = rgb.shape[:2]
        scale = min(1.0, 900.0 / max(h, w))
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        small = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA) if scale < 1.0 else rgb.copy()
        mask_small = None
        if subject_mask is not None:
            mask_small = (cv2.resize(subject_mask.astype(np.float32), size, interpolation=cv2.INTER_LINEAR)
                          if scale < 1.0 else subject_mask.astype(np.float32))

        # Faces: inner-cheek skin for the skin check, whole (grown) face boxes kept out of the neutral set
        face_excl = np.zeros(small.shape[:2], np.uint8)
        skin_sel = np.zeros(small.shape[:2], bool)
        try:
            from backend.retouch.faces import detect_faces
            for f in detect_faces(small) or []:
                fx, fy, fw, fh = [int(round(v)) for v in f.box]
                cv2.rectangle(face_excl, (fx - fw // 3, fy - fh // 3), (fx + fw + fw // 3, fy + fh + fh), 1, -1)
                skin_sel[max(0, fy + fh // 4):max(0, fy + fh - fh // 4), max(0, fx + fw // 5):max(0, fx + fw - fw // 5)] = True
        except Exception:
            pass

        wb = dict(params.auto_wb) if isinstance(params.auto_wb, dict) else {"enabled": True, "notes": []}
        base = np.array(wb.get("gains") or [1.0, 1.0, 1.0], np.float64)
        if not wb.get("enabled", True):
            return
        k_strength = float(np.clip(float(wb.get("strength", 100.0)), 0.0, 150.0)) / 100.0
        base = np.exp(np.log(np.clip(base, 0.3, 3.0)) * k_strength)

        proxy = EditParameters.from_dict(params.to_dict())
        proxy.temperature, proxy.tint = 0.0, 0.0          # judge the neutral look; the preset tone goes on top
        proxy.skin_glow = 0.0                              # luminance-only, irrelevant for colour

        def gains_for(t):
            # t > 0 cools (more blue, less red), t < 0 warms
            return _normalize_gains(base * np.exp(np.array([-t / 2.0, 0.0, t / 2.0])))

        neutral_sel, skin_px = None, None
        t, slope = 0.0, None
        last_b, last_t, first_b, hue = None, None, None, None
        for _ in range(5):
            proxy.auto_wb = {**wb, "enabled": True, "strength": 100.0, "gains": [float(v) for v in gains_for(t)]}
            out = apply_edit_pipeline(small.copy(), proxy, cached_subject_mask=mask_small, cached_subject_info=subject_info)
            lab = cv2.cvtColor(out, cv2.COLOR_RGB2LAB).astype(np.float32)
            L, a, b = lab[..., 0], lab[..., 1] - 128.0, lab[..., 2] - 128.0
            if neutral_sel is None:
                C = np.hypot(a, b)
                # Skin-coloured pixels (necks, arms, hands, warm wood) are never "neutral" even when the
                # current white balance has made them pale: judged on the camera's colours
                ycc = cv2.cvtColor(small, cv2.COLOR_RGB2YCrCb)
                skin_like = ((ycc[..., 1] >= 133) & (ycc[..., 1] <= 175) & (ycc[..., 2] >= 77)
                             & (ycc[..., 2] <= 127) & (ycc[..., 0] >= 35))
                neutral_sel = (C < 12.0) & (L > 60.0) & (L < 248.0) & (face_excl == 0) & ~skin_like
                if float(neutral_sel.mean()) < 0.015:
                    neutral_sel = np.zeros_like(neutral_sel)
                # skin: the warm, chromatic pixels inside the inner face boxes
                hue_all = np.degrees(np.arctan2(b, a))
                skin_px = skin_sel & (C > 8.0) & (hue_all > 10.0) & (hue_all < 85.0) & (L > 40.0) & (L < 240.0)
                if int(skin_px.sum()) < 40:
                    skin_px = None

            nb = float(np.median(b[neutral_sel])) if neutral_sel.any() else None
            hue = (float(np.degrees(np.arctan2(np.median(b[skin_px]), np.median(a[skin_px]))))
                   if skin_px is not None else None)
            if first_b is None:
                first_b = nb
            if nb is not None and last_b is not None and abs(t - last_t) > 1e-4:
                s = (nb - last_b) / (t - last_t)
                if -200.0 < s < -10.0:                     # cooling lowers b*: a sane measured slope
                    slope = s
            k = slope if slope is not None else -60.0      # b* units per unit of t (measured on wedding files)

            want = 0.0
            if nb is not None:
                want = (nb - self.NEUTRAL_B_TARGET) / -k
            if hue is not None:
                if hue > self.SKIN_HUE_YELLOW:
                    want = max(want, (hue - self.SKIN_HUE_YELLOW + 1.0) * 0.006)
                elif hue < self.SKIN_HUE_COOL_FLOOR and want > 0:
                    want = 0.0
                elif want > 0 and hue - want * 40.0 < self.SKIN_HUE_COOL_FLOOR:
                    want = max(0.0, (hue - self.SKIN_HUE_COOL_FLOOR) / 40.0)
            if abs(want) < 0.004:
                break
            last_b, last_t = nb, t
            t = float(np.clip(t + want, -0.08, 0.25))
            if t == last_t:
                break

        if abs(t) < 0.003:
            return
        g = gains_for(t)
        notes = [n for n in (wb.get("notes") or []) if not str(n).startswith("clean colour")]
        msg = "clean colour: %s %.2f" % ("cooled" if t > 0 else "warmed", abs(t))
        if first_b is not None:
            msg += " (whites b* %.1f -> %.1f)" % (first_b, nb if nb is not None else first_b)
        if hue is not None:
            msg += ", skin hue %.0f" % hue
        params.auto_wb = {**wb, "enabled": True, "strength": 100.0,
                          "gains": [round(float(v), 4) for v in g], "notes": notes + [msg]}

    def _calibrate_render(self, rgb, params, subject_mask, subject_info, skin_in_subject):
        """Renders the edit on a 1200px preview (same pipeline as export, retouch included) and corrects:
        1. Subject Light  - subject skin must not come out brighter than SUBJECT_SKIN_MAX
        2. Haze           - edits must not wash out the blacks (flat / milky look)
        3. Contrast       - the subject keeps at least the depth it had in the original
        4. Skin colour    - skin must not turn grey / pale compared to the original
        """
        if subject_mask is None:
            return
        from backend.services.image_service import apply_edit_pipeline   # lazy: avoids import cycle

        h, w = rgb.shape[:2]
        scale = min(1.0, 1200.0 / max(h, w))
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        small = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA) if scale < 1.0 else rgb.copy()
        mask_small = (cv2.resize(subject_mask.astype(np.float32), size, interpolation=cv2.INTER_LINEAR)
                      if scale < 1.0 else subject_mask.astype(np.float32))
        skin_small = None
        if skin_in_subject is not None and int(np.sum(skin_in_subject)) >= 60:
            skin_small = cv2.resize(skin_in_subject.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) > 0
            if int(np.sum(skin_small)) < 30:
                skin_small = None

        # Every detected face is judged on its own (a dark groom must not hide an over-lit bride)
        face_sels = []
        try:
            from backend.retouch.faces import detect_faces
            ycc = cv2.cvtColor(small, cv2.COLOR_RGB2YCrCb)
            skin_any = ((ycc[..., 1] >= 128) & (ycc[..., 1] <= 180) & (ycc[..., 2] >= 75)
                        & (ycc[..., 2] <= 135) & (ycc[..., 0] >= 32))
            for f in detect_faces(small) or []:
                fx, fy, fw, fh = [int(round(v)) for v in f.box]
                # inner face (cheeks / forehead), away from hair and background
                x0, x1 = max(0, fx + fw // 6), min(size[0], fx + fw - fw // 6)
                y0, y1 = max(0, fy + fh // 6), min(size[1], fy + fh - fh // 5)
                sel = np.zeros(skin_any.shape, dtype=bool)
                sel[y0:y1, x0:x1] = skin_any[y0:y1, x0:x1]
                if int(np.sum(sel)) >= 25:
                    face_sels.append(sel)
        except Exception:
            face_sels = []
        if not face_sels and skin_small is not None:
            face_sels = [skin_small]

        def chroma(img_u8, sel):
            lab = cv2.cvtColor(img_u8, cv2.COLOR_RGB2LAB).astype(np.float32)
            a = lab[:, :, 1][sel] - 128.0
            b = lab[:, :, 2][sel] - 128.0
            return float(np.median(np.sqrt(a * a + b * b)))

        y_in = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32)
        sub_sel = mask_small > 0.3
        if int(np.sum(sub_sel)) < 500:
            sub_sel = np.ones_like(sub_sel, dtype=bool)
        in_p1 = float(np.percentile(y_in, 1))
        in_std = float(np.std(y_in[sub_sel]))
        in_face_c = [chroma(small, sel) for sel in face_sels]
        target_p1 = float(np.clip(in_p1, 6.0, 14.0))

        proxy = EditParameters.from_dict(params.to_dict())
        proxy.skin_glow = 0.0     # light is judged without the skin glow; the glow goes on top unchanged
        prev_face, prev_subj, subject_light_ok = None, proxy.subject_exposure, True
        for _ in range(4):
            out = apply_edit_pipeline(small.copy(), proxy, cached_subject_mask=mask_small, cached_subject_info=subject_info)
            y = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY).astype(np.float32)
            adjusted = False

            # 1. Subject light: the brightest face decides (darker faces are barely touched: the correction
            #    works mostly on bright tones)
            if face_sels and subject_light_ok:
                face = max(float(np.median(y[sel])) for sel in face_sels)
                if prev_face is not None and face > prev_face - 2.0:
                    # That face is outside the subject mask: Subject Light cannot reach it, undo the last step
                    proxy.subject_exposure = prev_subj
                    subject_light_ok = False
                elif face > self.SUBJECT_SKIN_MAX + 2.0:
                    prev_face, prev_subj = face, proxy.subject_exposure
                    step = float(np.log2(self.SUBJECT_SKIN_MAX / face)) * 1.15
                    proxy.subject_exposure = float(np.clip(proxy.subject_exposure + step, -1.2, 0.0))
                    proxy.highlights = float(min(proxy.highlights, -30.0))
                    adjusted = True

            # 2. Haze: blacks lifted above the original's black point
            p1 = float(np.percentile(y, 1))
            if p1 > target_p1 + 4.0 and proxy.blacks > -45.0:
                proxy.blacks = float(max(-45.0, proxy.blacks - float(np.clip((p1 - target_p1) * 2.5, 3.0, 15.0))))
                adjusted = True

            # 3. Contrast / depth on the subject
            out_std = float(np.std(y[sub_sel]))
            if in_std > 8.0 and out_std < in_std * 0.95 and proxy.contrast < 30.0:
                proxy.contrast = float(min(30.0, proxy.contrast + float(np.clip((in_std / max(out_std, 1.0) - 1.0) * 100.0, 2.0, 10.0))))
                adjusted = True

            # 4. Skin colour must not go grey / pale on ANY face
            ratios = [chroma(out, sel) / max(c_in, 1.0) for sel, c_in in zip(face_sels, in_face_c) if c_in > 4.0]
            if ratios and min(ratios) < 0.94 and proxy.saturation < 14.0:
                proxy.saturation = float(min(14.0, proxy.saturation + float(np.clip((0.98 / max(min(ratios), 0.05) - 1.0) * 120.0, 2.0, 8.0))))
                adjusted = True

            if not adjusted:
                break

        for key in ("subject_exposure", "highlights", "blacks", "contrast", "saturation"):
            setattr(params, key, round(float(getattr(proxy, key)), 2))
