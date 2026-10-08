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
        sensitivity: float = 0.50,
        manual_heal_spots: Optional[List[Dict[str, float]]] = None,
        face_box_in_crop: Optional[Tuple[int, int, int, int]] = None
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Processes a face/skin patch using scale-normalized frequency-separated inpainting.
        """
        ch, cw = rgb_crop.shape[:2]
        if ch < 16 or cw < 16:
            return rgb_crop, np.zeros((ch, cw), dtype=np.uint8), 0

        crop_u8 = np.clip(rgb_crop, 0, 255).astype(np.uint8)
        ycrcb = cv2.cvtColor(crop_u8, cv2.COLOR_RGB2YCrCb)
        Y = ycrcb[:, :, 0]
        Cr = ycrcb[:, :, 1]
        Cb = ycrcb[:, :, 2]

        # Indian & international skin tone chrominance bounds
        skin_mask = (Cr >= 126) & (Cr <= 186) & (Cb >= 72) & (Cb <= 138) & (Y >= 35) & (Y <= 248)
        if not np.any(skin_mask):
            return crop_u8, np.zeros((ch, cw), dtype=np.uint8), 0

        # Protect strong structural edges (eyes, lips, nostrils, eyebrows, hair)
        gray = cv2.cvtColor(crop_u8, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        edge_mag = cv2.magnitude(gx, gy)
        safe_skin = skin_mask & (edge_mag < 48.0)

        # Feature zone protection mask (strictly protects eyes, lips, nostril, forehead jewelry)
        feature_protect = np.ones((ch, cw), dtype=bool)
        if face_box_in_crop is not None:
            fx, fy, fw, fh = face_box_in_crop
            fcx = int(fx + fw * 0.5)
            fcy = int(fy + fh * 0.52)

            # Eyes
            eye_x1, eye_x2 = max(0, int(fcx - fw * 0.38)), min(cw, int(fcx + fw * 0.38))
            eye_y1, eye_y2 = max(0, int(fy + fh * 0.15)), min(ch, int(fy + fh * 0.45))
            feature_protect[eye_y1:eye_y2, eye_x1:eye_x2] = False

            # Lips & Mouth
            mouth_x1, mouth_x2 = max(0, int(fcx - fw * 0.28)), min(cw, int(fcx + fw * 0.28))
            mouth_y1, mouth_y2 = max(0, int(fy + fh * 0.68)), min(ch, int(fy + fh * 0.90))
            feature_protect[mouth_y1:mouth_y2, mouth_x1:mouth_x2] = False

            # Nose bridge & ring
            nose_x1, nose_x2 = max(0, int(fcx - fw * 0.13)), min(cw, int(fcx + fw * 0.13))
            nose_y1, nose_y2 = max(0, int(fy + fh * 0.38)), min(ch, int(fy + fh * 0.72))
            feature_protect[nose_y1:nose_y2, nose_x1:nose_x2] = False

            # Tikka / Forehead ornament
            tikka_x1, tikka_x2 = max(0, int(fcx - fw * 0.08)), min(cw, int(fcx + fw * 0.08))
            tikka_y1, tikka_y2 = max(0, int(fy)), min(ch, int(fy + fh * 0.26))
            feature_protect[tikka_y1:tikka_y2, tikka_x1:tikka_x2] = False

        safe_skin = safe_skin & feature_protect

        # Scale-normalized kernel dimensions based on face size
        k_small_r = max(3, int(round(7.0 * scale_factor)) | 1)
        k_mid_r = max(5, int(round(15.0 * scale_factor)) | 1)

        # Multi-scale morphological & DoG blemish extraction on chrominance and redness
        r_ch = crop_u8[:, :, 0].astype(np.int16)
        g_ch = crop_u8[:, :, 1].astype(np.int16)
        b_ch = crop_u8[:, :, 2].astype(np.int16)
        redness = np.clip(r_ch - ((g_ch + b_ch) // 2) + 128, 0, 255).astype(np.uint8)

        el_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_small_r, k_small_r))
        el_m = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_mid_r, k_mid_r))

        top_cr = np.maximum(cv2.morphologyEx(Cr, cv2.MORPH_TOPHAT, el_s), cv2.morphologyEx(Cr, cv2.MORPH_TOPHAT, el_m))
        top_rg = np.maximum(cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, el_s), cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, el_m))
        blk_y = np.maximum(cv2.morphologyEx(Y, cv2.MORPH_BLACKHAT, el_s), cv2.morphologyEx(Y, cv2.MORPH_BLACKHAT, el_m))

        sens = float(np.clip(sensitivity, 0.1, 1.0))
        th_cr = max(2.8, 6.5 - sens * 3.5)
        th_rg = max(3.2, 7.5 - sens * 4.0)
        th_y = max(3.5, 8.0 - sens * 4.0)

        cand = safe_skin & ((top_cr > th_cr) | (top_rg > th_rg) | (blk_y > th_y))

        # Filter spots by scale-normalized size (pimples: 2px to 28px relative to scale)
        min_diam = max(2, int(3.0 * scale_factor))
        max_diam = max(8, int(26.0 * scale_factor))
        min_area = int(np.pi * (min_diam / 2.0) ** 2)
        max_area = int(1.4 * np.pi * (max_diam / 2.0) ** 2)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8) * 255)
        blemish_mask = np.zeros((ch, cw), dtype=np.uint8)
        spots_found = 0

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            box_w = stats[i, cv2.CC_STAT_WIDTH]
            box_h = stats[i, cv2.CC_STAT_HEIGHT]
            aspect = max(box_w, box_h) / max(1, min(box_w, box_h))
            size = max(box_w, box_h)
            if min_area <= area <= max_area and size <= max_diam and aspect < 2.4:
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

        if spots_found == 0 or not np.any(blemish_mask > 0):
            return crop_u8, np.zeros((ch, cw), dtype=np.uint8), 0

        # Frequency-separated texture preservation inpainting
        dilate_rad = max(2, int(round(3.0 * scale_factor)) | 1)
        dilated_mask = cv2.dilate(blemish_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_rad, dilate_rad)))

        # 1. Base lighting / color layer (Low frequency)
        k_tex = max(3, int(round(5.0 * scale_factor)) | 1)
        base_low = cv2.GaussianBlur(crop_u8, (k_tex, k_tex), 1.2)
        # 2. Pore texture layer (High frequency)
        skin_texture = crop_u8.astype(np.float32) - base_low.astype(np.float32)

        # 3. Telea inpainting on the base layer
        inpaint_rad = max(2, int(round(4.0 * scale_factor)))
        inpainted_base = cv2.inpaint(crop_u8, dilated_mask, inpaintRadius=inpaint_rad, flags=cv2.INPAINT_TELEA)

        # 4. Re-synthesise 70% natural pore texture so inpaint never looks plastic or blurry
        healed_textured = np.clip(inpainted_base.astype(np.float32) + skin_texture * 0.70, 0, 255).astype(np.uint8)

        # 5. Seamless feathered edge blend
        feather = cv2.GaussianBlur(dilated_mask.astype(np.float32) / 255.0, (5, 5), 1.2)[:, :, np.newaxis]
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
        Executes AI Heal over the entire image.
        Strength controls sensitivity of blemish detection.
        Opacity controls non-destructive blending between original and healed layer.
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
        sensitivity = float(np.clip(strength / 100.0, 0.1, 1.0))

        healed_canvas = orig_u8.copy()
        full_blemish_mask = np.zeros((h, w), dtype=np.uint8)
        total_spots = 0

        # 2. Localized processing per detected face (Super-fast & preserves everything outside face)
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
                    sensitivity=sensitivity,
                    face_box_in_crop=face_box_in_crop
                )
                healed_canvas[y1:y2, x1:x2] = healed_crop
                full_blemish_mask[y1:y2, x1:x2] = np.maximum(full_blemish_mask[y1:y2, x1:x2], b_mask)
                total_spots += count
        else:
            # When no face detected, run on tiles for whole portrait using selected preset scale
            def _tile_fn(tile: np.ndarray) -> np.ndarray:
                healed_t, _, _ = self._detect_and_inpaint_crop(
                    tile, scale_factor=scale_factor, sensitivity=sensitivity
                )
                return healed_t

            healed_canvas = self.tiler.process(orig_u8, _tile_fn)
            total_spots = 1

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
