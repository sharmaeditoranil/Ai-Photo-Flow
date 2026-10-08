"""
Wedding Photography Auto-Editing Model
Calculates photo-specific corrections with natural Indian skin tone protection.
"""
import cv2
import numpy as np
from typing import Optional, Dict, Any
from backend.core.interfaces import EditingModel, EditParameters, FaceMetrics
from backend.core.subject_model import SubjectDetectionEngine

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
            "temp_bias": -7.0,         # Subtle cool blue tone
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
        """Detect tilt angle using Hough Line Transform on prominent horizontal/vertical lines."""
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=120, minLineLength=100, maxLineGap=10)
            if lines is None:
                return 0.0

            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = x2 - x1
                dy = y2 - y1
                angle_deg = np.degrees(np.arctan2(dy, dx))
                # Normalize to horizontal [-45, 45]
                while angle_deg > 45:
                    angle_deg -= 90
                while angle_deg < -45:
                    angle_deg += 90

                # Only consider slight tilts
                if -12.0 <= angle_deg <= 12.0:
                    angles.append(angle_deg)

            if len(angles) >= 5:
                median_angle = float(np.median(angles))
                if abs(median_angle) >= 0.5:
                    return round(float(np.clip(-median_angle, -10.0, 10.0)), 1)
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
        face_metrics: Optional[FaceMetrics] = None
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

        if has_subject_skin or np.sum(skin_meter) > 40:
            target_skin_pixels = gray[skin_in_subject] if has_subject_skin else gray[skin_meter]
            skin_median = float(np.median(target_skin_pixels))

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
            auto_temp = float(np.clip(-rb_diff * 0.25 + preset.get("temp_bias", 0.0), -28.0, 22.0))
            auto_tint = float(np.clip(-g_deviation * 0.35, -18.0, 18.0))

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
            shadows = max(shadows, 28.0)
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
            shadows = max(shadows, 34.0)
            noise_reduction = min(noise_reduction, 5.0)
            whites = min(whites, 6.0)
        elif genre == "Outdoor Sunlight & Garden":
            # Priority: Harsh sun shadow fill under brows/noses, sky highlight recovery
            highlights = min(highlights, -28.0)
            shadows = max(shadows, 26.0)
            vibrance = min(18.0, vibrance + 4.0)
        elif genre == "Décor, Rituals & Macro Details":
            # Priority: Intricate jewelry sparkle, flower saturation, rich embroidery contrast
            vibrance = max(vibrance, 14.0)
            contrast = max(contrast, 8.0)
            highlights = min(highlights, -18.0)
            sharpening = max(sharpening, 32.0)

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


        # User Requirement: Subtle SkinFiner-grade skin smoothing, gentle 3D Dodge & Burn
        auto_skin_smooth = 25.0
        auto_dodge_burn = 20.0

        res_params = EditParameters(
            exposure=round(exposure, 2),
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
            dodge_burn=round(auto_dodge_burn, 1)
        )
        if return_mask:
            return res_params, (subject_mask, subject_info)
        return res_params
