"""
Subject Detection and Saliency Engine
Detects primary human subjects (bride, groom, portrait subjects) and isolates them
from the background to enable subject-centric lighting and exposure adjustment.
"""
import os
import cv2
import numpy as np
from typing import Dict, Any, Optional, Tuple
from backend.core.face_model import OpenCVFaceModel
from backend.core.interfaces import FaceMetrics

class SubjectDetectionEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SubjectDetectionEngine, cls).__new__(cls)
            try:
                cls._instance.face_model = OpenCVFaceModel()
            except Exception:
                cls._instance.face_model = None
        return cls._instance

    def generate_subject_mask(
        self,
        image_np: np.ndarray,
        face_metrics: Optional[FaceMetrics] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Generates a float32 mask (H, W) in [0.0, 1.0] where 1.0 = primary human subject,
        with smooth Gaussian feathering so lighting adjustments blend seamlessly.
        """
        if image_np is None or image_np.size == 0:
            return np.ones((100, 100), dtype=np.float32), {"has_subject": False, "faces_count": 0}

        h, w = image_np.shape[:2]
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY) if len(image_np.shape) == 3 else image_np

        if face_metrics is None:
            if self.face_model is not None:
                face_metrics = self.face_model.detect(image_np)
            else:
                face_metrics = FaceMetrics(0, "NO_FACE", 0.0, [], 0.0)

        mask = np.zeros((h, w), dtype=np.float32)

        has_faces = face_metrics.faces_count > 0
        max_face_fraction = 0.0

        if has_faces:
            # For each detected face, mark face region and expand torso/attire region
            for box in face_metrics.bounding_boxes:
                bx = max(0, box["x"])
                by = max(0, box["y"])
                bw = min(w - bx, box["w"])
                bh = min(h - by, box["h"])

                fraction = float((bw * bh) / max(1, h * w))
                if fraction > max_face_fraction:
                    max_face_fraction = fraction

                # Face region (1.0 weight)
                cv2.rectangle(mask, (bx, by), (bx + bw, by + bh), 1.0, -1)

                # Upper body / wedding attire expansion (sherwani, lehenga, saree, suit)
                tx1 = max(0, bx - int(bw * 0.45))
                tx2 = min(w, bx + int(bw * 1.45))
                ty1 = by + bh
                ty2 = min(h, by + int(bh * 3.8))
                cv2.rectangle(mask, (tx1, ty1), (tx2, ty2), 0.85, -1)

            # Detect Indian skin pixels (arms, hands, neck, face)
            if len(image_np.shape) == 3:
                ycrcb = cv2.cvtColor(image_np, cv2.COLOR_RGB2YCrCb)
                cr = ycrcb[:, :, 1]
                cb = ycrcb[:, :, 2]
                skin = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
                mask[skin] = np.maximum(mask[skin], 0.90)

            # Feather mask smoothly with Gaussian blur to prevent any halo artifacts
            kernel_size = max(15, (min(h, w) // 25) | 1)
            mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)

            sub_type = "Couple / Portrait" if face_metrics.faces_count <= 2 else f"Group ({face_metrics.faces_count} People)"
        else:
            # Check for skin pixels even if frontal face is turned / ritual details (mehndi, rings, sindoor)
            has_skin_action = False
            if len(image_np.shape) == 3:
                ycrcb = cv2.cvtColor(image_np, cv2.COLOR_RGB2YCrCb)
                cr = ycrcb[:, :, 1]
                cb = ycrcb[:, :, 2]
                skin = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)
                if np.sum(skin) > (h * w * 0.015):
                    mask[skin] = 0.90
                    has_skin_action = True

            # Center-weighted elliptical saliency
            center_x, center_y = w // 2, h // 2
            axes = (int(w * 0.38), int(h * 0.38))
            cv2.ellipse(mask, (center_x, center_y), axes, 0, 0, 360, 0.70 if has_skin_action else 0.85, -1)
            kernel_size = max(31, (min(h, w) // 18) | 1)
            mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)
            sub_type = "Wedding Ritual / Hands" if has_skin_action else "Center Focal Subject"

        # Calculate luminance stats
        sub_pixels = gray[mask > 0.35]
        bg_pixels = gray[mask <= 0.20]

        sub_lum = float(np.mean(sub_pixels)) if len(sub_pixels) > 0 else float(np.mean(gray))
        bg_lum = float(np.mean(bg_pixels)) if len(bg_pixels) > 0 else float(np.mean(gray))
        coverage = float(np.sum(mask > 0.35) / (h * w))

        # Determine if shot is a wide shot or close-up portrait
        # Wide shots: stage groups (>=4 people), small distant faces (<1.8% of frame), or wide decor/venue
        is_wide = bool(
            face_metrics.faces_count >= 4
            or (face_metrics.faces_count > 0 and max_face_fraction < 0.018)
            or (face_metrics.faces_count == 0 and not has_skin_action)
        )

        info = {
            "has_subject": True,
            "subject_type": sub_type,
            "faces_count": face_metrics.faces_count,
            "faces_boxes": face_metrics.bounding_boxes,
            "max_face_fraction": round(max_face_fraction, 4),
            "is_wide_shot": is_wide,
            "subject_lum": round(sub_lum, 1),
            "bg_lum": round(bg_lum, 1),
            "subject_coverage": round(coverage, 2)
        }

        return mask, info
