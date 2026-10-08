"""
AI Heal Core Pipeline
Scale-normalized blemish detection, frequency-separated pore texture synthesis,
and non-destructive Heal layer blending with real-time opacity.
License: MIT / BSD-3-Clause Permissive.
"""
import os
import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from backend.heal.face_scale import FaceScaleEstimator, FaceScaleInfo
from backend.heal.tiling import TiledProcessor

@dataclass
class HealResult:
    healed_rgb: np.ndarray       # Full healed layer (100% strength)
    blended_rgb: np.ndarray      # Output blended at requested opacity
    detected_spots_count: int
    scale_info: FaceScaleInfo
    blemish_mask: np.ndarray     # Binary mask of detected spots (H, W) uint8

class AIHealPipeline:
    def __init__(self, face_model=None):
        self.scale_estimator = FaceScaleEstimator(face_model=face_model)
        self.tiler = TiledProcessor(tile_size=512, overlap=64)

    def _detect_and_inpaint_crop(
        self,
        rgb_crop: np.ndarray,
        scale_factor: float,
        sensitivity: float = 60.0,
        manual_heal_spots: Optional[List[Dict[str, float]]] = None,
        face_box_in_crop: Optional[Tuple[int, int, int, int]] = None
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Matches individual subject skin tone and detects ONLY genuine pimples/acne on facial skin.
        Leaves 100% of clean skin, eyes, brows, lips, nostril/nath, jewelry, hair, and clothing untouched.
        """
        ch, cw = rgb_crop.shape[:2]
        if ch < 16 or cw < 16:
            return rgb_crop, np.zeros((ch, cw), dtype=np.uint8), 0

        crop_u8 = np.clip(rgb_crop, 0, 255).astype(np.uint8)

        # 1. STRICT Facial Oval Mask (Locks healing strictly to face cheeks/forehead/chin)
        face_oval = np.zeros((ch, cw), dtype=np.uint8)
        if face_box_in_crop is not None:
            fx, fy, fw, fh = face_box_in_crop
            fcx = int(fx + fw * 0.5)
            fcy = int(fy + fh * 0.52)
            cv2.ellipse(face_oval, (fcx, fcy), (int(fw * 0.40), int(fh * 0.44)), 0, 0, 360, 255, -1)

            # A. Eyes & Eyebrows (Combined strictly between 0.33*fh and 0.54*fh)
            eye_x1, eye_x2 = max(0, int(fcx - fw * 0.40)), min(cw, int(fcx + fw * 0.40))
            eye_y1, eye_y2 = max(0, int(fy + fh * 0.33)), min(ch, int(fy + fh * 0.54))
            face_oval[eye_y1:eye_y2, eye_x1:eye_x2] = 0

            # B. Lips & Mouth
            mouth_x1, mouth_x2 = max(0, int(fcx - fw * 0.28)), min(cw, int(fcx + fw * 0.28))
            mouth_y1, mouth_y2 = max(0, int(fy + fh * 0.72)), min(ch, int(fy + fh * 0.94))
            face_oval[mouth_y1:mouth_y2, mouth_x1:mouth_x2] = 0

            # C. Nose bridge, nostrils & nose ring (Nath)
            nose_x1, nose_x2 = max(0, int(fcx - fw * 0.12)), min(cw, int(fcx + fw * 0.12))
            nose_y1, nose_y2 = max(0, int(fy + fh * 0.45)), min(ch, int(fy + fh * 0.72))
            face_oval[nose_y1:nose_y2, nose_x1:nose_x2] = 0

            # D. Center Maang Tikka / Bindi / Sindoor (Strict central column only)
            tikka_x1, tikka_x2 = max(0, int(fcx - fw * 0.09)), min(cw, int(fcx + fw * 0.09))
            tikka_y1, tikka_y2 = max(0, int(fy)), min(ch, int(fy + fh * 0.34))
            face_oval[tikka_y1:tikka_y2, tikka_x1:tikka_x2] = 0
        else:
            face_oval.fill(255)

        # 2. Dynamic Skin Tone Extraction for THIS specific person
        # Sample clean inner cheek region
        if face_box_in_crop is not None:
            fx, fy, fw, fh = face_box_in_crop
            ch_y1, ch_y2 = max(0, int(fy + fh * 0.45)), min(ch, int(fy + fh * 0.65))
            ch_x1, ch_x2 = max(0, int(fx + fw * 0.20)), min(cw, int(fx + fw * 0.38))
            sample = crop_u8[ch_y1:ch_y2, ch_x1:ch_x2]
        else:
            sample = crop_u8[ch//4:3*ch//4, cw//4:3*cw//4]

        ycrcb = cv2.cvtColor(crop_u8, cv2.COLOR_RGB2YCrCb)
        Y = ycrcb[:, :, 0].astype(np.float32)
        Cr = ycrcb[:, :, 1].astype(np.float32)
        Cb = ycrcb[:, :, 2].astype(np.float32)

        if sample.size > 20:
            sample_ycrcb = cv2.cvtColor(sample, cv2.COLOR_RGB2YCrCb)
            med_cr = float(np.median(sample_ycrcb[:, :, 1]))
            med_cb = float(np.median(sample_ycrcb[:, :, 2]))
            med_y = float(np.median(sample_ycrcb[:, :, 0]))
        else:
            med_cr, med_cb, med_y = 150.0, 110.0, 120.0

        # Euclidean distance from subject's matched skin tone
        dist_chroma = np.sqrt((Cr - med_cr) ** 2 + (Cb - med_cb) ** 2)
        
        # Structural edge magnitude (protects hair strands, fabric textures, jewelry facets)
        gray = cv2.cvtColor(crop_u8, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        edge_mag = cv2.magnitude(gx, gy)

        # Strictly matched skin: inside face oval AND chrominance matches subject AND smooth surface
        matched_skin = (face_oval > 0) & (dist_chroma < 24.0) & (edge_mag < 32.0)
        if not np.any(matched_skin):
            return crop_u8, np.zeros((ch, cw), dtype=np.uint8), 0

        # 3. Pimple / Acne Anomaly Detection
        # Inflamed red bumps: Local excess of Red relative to Green/Blue
        r_ch = crop_u8[:, :, 0].astype(np.float32)
        g_ch = crop_u8[:, :, 1].astype(np.float32)
        b_ch = crop_u8[:, :, 2].astype(np.float32)
        redness = np.clip(r_ch - ((g_ch + b_ch) / 2.0), 0, 255).astype(np.uint8)

        # Scale-normalized structuring elements
        k_s = max(3, int(round(6.0 * scale_factor)) | 1)
        k_m = max(5, int(round(14.0 * scale_factor)) | 1)
        el_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_s, k_s))
        el_m = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_m, k_m))

        top_rg = np.maximum(cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, el_s), cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, el_m))
        blk_y = np.maximum(cv2.morphologyEx(Y.astype(np.uint8), cv2.MORPH_BLACKHAT, el_s), cv2.morphologyEx(Y.astype(np.uint8), cv2.MORPH_BLACKHAT, el_m))

        sens = float(np.clip(sensitivity / 100.0, 0.1, 1.0))
        th_rg = max(3.5, 7.5 - sens * 4.0)
        th_y = max(4.0, 8.5 - sens * 4.5)

        pimple_cand = matched_skin & ((top_rg > th_rg) | (blk_y > th_y))

        # Size & Shape Filtering: Genuine pimples are compact circular blobs (2px to 22px relative to scale)
        min_diam = max(2, int(2.5 * scale_factor))
        max_diam = max(6, int(22.0 * scale_factor))
        min_area = int(np.pi * (min_diam / 2.0) ** 2)
        max_area = int(1.3 * np.pi * (max_diam / 2.0) ** 2)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(pimple_cand.astype(np.uint8) * 255)
        blemish_mask = np.zeros((ch, cw), dtype=np.uint8)
        spots_found = 0

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            box_w = stats[i, cv2.CC_STAT_WIDTH]
            box_h = stats[i, cv2.CC_STAT_HEIGHT]
            aspect = max(box_w, box_h) / max(1, min(box_w, box_h))
            size = max(box_w, box_h)
            if min_area <= area <= max_area and size <= max_diam and aspect < 1.9:
                blemish_mask[labels == i] = 255
                spots_found += 1

        # Add manual spot healing brush inputs if supplied
        if manual_heal_spots:
            for spot in manual_heal_spots:
                sx = int(np.clip(spot.get("x", 0.5) * cw, 0, cw - 1))
                sy = int(np.clip(spot.get("y", 0.5) * ch, 0, ch - 1))
                s_rad = max(3, int(spot.get("radius", 0.015) * min(ch, cw)))
                cv2.circle(blemish_mask, (sx, sy), s_rad, 255, -1)
                spots_found += 1

        # STRICT Check: If NO pimple found, return original crop 100% UNTOUCHED!
        if spots_found == 0 or not np.any(blemish_mask > 0):
            return crop_u8, np.zeros((ch, cw), dtype=np.uint8), 0

        # Dilate slightly to cover inflamed red perimeter, strictly bound to face oval
        dilate_rad = max(2, int(round(2.5 * scale_factor)) | 1)
        dilated_mask = cv2.dilate(blemish_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_rad, dilate_rad)))
        if face_box_in_crop is not None:
            dilated_mask = dilated_mask & face_oval

        if not np.any(dilated_mask > 0):
            return crop_u8, np.zeros((ch, cw), dtype=np.uint8), 0

        # 4. Seamless Inpainting matching surrounding skin + 70% pore texture preservation
        k_tex = max(3, int(round(5.0 * scale_factor)) | 1)
        base_low = cv2.GaussianBlur(crop_u8, (k_tex, k_tex), 1.2)
        skin_texture = crop_u8.astype(np.float32) - base_low.astype(np.float32)

        inpaint_rad = max(2, int(round(3.5 * scale_factor)))
        inpainted_base = cv2.inpaint(crop_u8, dilated_mask, inpaintRadius=inpaint_rad, flags=cv2.INPAINT_TELEA)
        healed_textured = np.clip(inpainted_base.astype(np.float32) + skin_texture * 0.70, 0, 255).astype(np.uint8)

        # Seamless feathered edge blend ONLY over the pimple
        feather = cv2.GaussianBlur(dilated_mask.astype(np.float32) / 255.0, (5, 5), 1.2)[:, :, np.newaxis]
        if face_box_in_crop is not None:
            feather = feather * (face_oval[:, :, np.newaxis] > 0)
        final_crop = (crop_u8.astype(np.float32) * (1.0 - feather)) + (healed_textured.astype(np.float32) * feather)

        return np.clip(final_crop, 0, 255).astype(np.uint8), blemish_mask, spots_found

    def process_image(
        self,
        image_np: np.ndarray,
        strength: float = 60.0,       # 0 to 100%
        opacity: float = 100.0,       # 0 to 100% (Real-time blend)
        face_preset: str = "AUTO",     # "AUTO", "SMALL", "MEDIUM", "LARGE"
        manual_spots: Optional[List[Dict[str, float]]] = None,
        precomputed_face_boxes: Optional[List[Dict[str, int]]] = None
    ) -> HealResult:
        """
        Executes AI Heal strictly on facial skin blemishes.
        If no face is detected, leaves the entire image 100% untouched.
        Leaves clothes, eyes, lips, jewelry, and background untouched.
        """
        h, w = image_np.shape[:2]
        orig_u8 = np.clip(image_np, 0, 255).astype(np.uint8)

        if strength <= 0.0 and (not manual_spots or len(manual_spots) == 0):
            empty_mask = np.zeros((h, w), dtype=np.uint8)
            scale_info = self.scale_estimator.estimate_scale(orig_u8, preset=face_preset, precomputed_boxes=precomputed_face_boxes)
            return HealResult(
                healed_rgb=orig_u8.copy(),
                blended_rgb=orig_u8.copy(),
                detected_spots_count=0,
                scale_info=scale_info,
                blemish_mask=empty_mask
            )

        # 1. Scale Normalization
        scale_info = self.scale_estimator.estimate_scale(orig_u8, preset=face_preset, precomputed_boxes=precomputed_face_boxes)
        scale_factor = scale_info.scale_factor

        healed_canvas = orig_u8.copy()
        full_blemish_mask = np.zeros((h, w), dtype=np.uint8)
        total_spots = 0

        # 2. Localized processing strictly per detected face (Preserves 100% of body, clothes, background)
        if scale_info.has_face and scale_info.all_face_boxes:
            for fb in scale_info.all_face_boxes:
                fx, fy, fw, fh = fb["x"], fb["y"], fb["w"], fb["h"]
                pad_x = int(fw * 0.15)
                pad_y = int(fh * 0.15)
                x1, y1 = max(0, fx - pad_x), max(0, fy - pad_y)
                x2, y2 = min(w, fx + fw + pad_x), min(h, fy + fh + pad_y)

                crop = orig_u8[y1:y2, x1:x2]
                face_box_in_crop = (fx - x1, fy - y1, fw, fh)
                healed_crop, b_mask, count = self._detect_and_inpaint_crop(
                    crop,
                    scale_factor=scale_factor,
                    sensitivity=strength,
                    face_box_in_crop=face_box_in_crop
                )
                if count > 0:
                    healed_canvas[y1:y2, x1:x2] = healed_crop
                    full_blemish_mask[y1:y2, x1:x2] = np.maximum(full_blemish_mask[y1:y2, x1:x2], b_mask)
                    total_spots += count
        else:
            # If NO face is detected in the image:
            # DO NOT TOUCH THE PHOTO! Leave clothes, background, furniture 100% untouched.
            pass

        # 3. Apply manual spots anywhere on canvas if present
        if manual_spots and len(manual_spots) > 0:
            for sp in manual_spots:
                cx = int(np.clip(sp.get("x", 0.5) * w, 0, w - 1))
                cy = int(np.clip(sp.get("y", 0.5) * h, 0, h - 1))
                rad = max(4, int(sp.get("radius", 0.015) * min(h, w)))
                pad = rad * 3
                sx1, sy1 = max(0, cx - pad), max(0, cy - pad)
                sx2, sy2 = min(w, cx + pad), min(h, cy + pad)
                if sx2 > sx1 and sy2 > sy1:
                    patch = healed_canvas[sy1:sy2, sx1:sx2].copy()
                    patch_mask = np.zeros((sy2 - sy1, sx2 - sx1), dtype=np.uint8)
                    cv2.circle(patch_mask, (cx - sx1, cy - sy1), rad, 255, -1)
                    patch_inpainted = cv2.inpaint(patch, patch_mask, inpaintRadius=rad, flags=cv2.INPAINT_TELEA)
                    healed_canvas[sy1:sy2, sx1:sx2] = patch_inpainted
                    cv2.circle(full_blemish_mask, (cx, cy), rad, 255, -1)
                    total_spots += 1

        # 4. Non-Destructive Opacity Blending (0% to 100%)
        # output = original * (1 - opacity) + healed * opacity
        alpha = float(np.clip(opacity / 100.0, 0.0, 1.0))
        if alpha >= 0.999:
            blended = healed_canvas
        elif alpha <= 0.001:
            blended = orig_u8
        else:
            blended = (orig_u8.astype(np.float32) * (1.0 - alpha)) + (healed_canvas.astype(np.float32) * alpha)
            blended = np.clip(blended, 0, 255).astype(np.uint8)

        return HealResult(
            healed_rgb=healed_canvas,
            blended_rgb=blended,
            detected_spots_count=total_spots,
            scale_info=scale_info,
            blemish_mask=full_blemish_mask
        )
