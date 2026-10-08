"""
Face Scale Estimator & Normalizer
Calculates normalized face scale factors so blemish extraction is invariant
to image resolution and portrait cropping distance (close-up vs wide ceremony).
License: MIT / BSD-3-Clause Permissive.
"""
import os
import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class FaceScaleInfo:
    has_face: bool
    faces_count: int
    primary_face_box: Optional[Dict[str, int]]
    all_face_boxes: List[Dict[str, int]]
    face_height_px: float
    scale_factor: float          # Multiplier relative to normalized 384px face height
    preset_used: str             # "AUTO", "SMALL", "MEDIUM", "LARGE"
    feature_zones: List[Dict[str, Any]] # Eye, lip, eyebrow protected masks

# Normalized reference face height in pixels
TARGET_FACE_HEIGHT = 384.0

# Fallback scales when no face is found
PRESET_SCALES = {
    "SMALL": 0.45,    # Full-length wide shot (e.g. bride entering mandap)
    "MEDIUM": 1.0,    # Half-body / waist-up couple portrait
    "LARGE": 1.75,    # Tight close-up beauty / bridal macro portrait
}

class FaceScaleEstimator:
    def __init__(self, face_model=None):
        self.face_model = face_model

    def estimate_scale(
        self,
        image_np: np.ndarray,
        preset: str = "AUTO",
        precomputed_boxes: Optional[List[Dict[str, int]]] = None
    ) -> FaceScaleInfo:
        h, w = image_np.shape[:2]
        face_boxes = []

        if precomputed_boxes and len(precomputed_boxes) > 0:
            face_boxes = precomputed_boxes
        elif self.face_model is not None:
            try:
                # Fast proxy detection on max 1000px
                max_dim = max(h, w)
                if max_dim > 1000:
                    scale_down = 800.0 / float(max_dim)
                    small = cv2.resize(image_np, (int(w * scale_down), int(h * scale_down)), interpolation=cv2.INTER_AREA)
                    metrics = self.face_model.detect(small)
                    inv = 1.0 / scale_down
                    face_boxes = [
                        {"x": int(b["x"] * inv), "y": int(b["y"] * inv), "w": int(b["w"] * inv), "h": int(b["h"] * inv)}
                        for b in metrics.bounding_boxes
                    ]
                else:
                    metrics = self.face_model.detect(image_np)
                    face_boxes = metrics.bounding_boxes
            except Exception:
                face_boxes = []

        if face_boxes and len(face_boxes) > 0 and preset == "AUTO":
            # Primary face is the largest one by area
            primary = max(face_boxes, key=lambda b: b.get("w", 0) * b.get("h", 0))
            fh = float(primary.get("h", TARGET_FACE_HEIGHT))
            scale_factor = float(np.clip(fh / TARGET_FACE_HEIGHT, 0.25, 4.0))

            feature_zones = []
            for fb in face_boxes:
                fx, fy, fw, fh_i = fb["x"], fb["y"], fb["w"], fb["h"]
                fcx = int(fx + fw * 0.5)
                fcy = int(fy + fh_i * 0.52)
                feature_zones.append({
                    "box": fb,
                    "center": (fcx, fcy),
                    "eyes": (max(0, int(fcx - fw * 0.38)), min(w, int(fcx + fw * 0.38)), max(0, int(fy + fh_i * 0.15)), min(h, int(fy + fh_i * 0.45))),
                    "mouth": (max(0, int(fcx - fw * 0.28)), min(w, int(fcx + fw * 0.28)), max(0, int(fy + fh_i * 0.68)), min(h, int(fy + fh_i * 0.90))),
                    "forehead": (max(0, int(fcx - fw * 0.25)), min(w, int(fcx + fw * 0.25)), max(0, int(fy)), min(h, int(fy + fh_i * 0.25)))
                })

            return FaceScaleInfo(
                has_face=True,
                faces_count=len(face_boxes),
                primary_face_box=primary,
                all_face_boxes=face_boxes,
                face_height_px=fh,
                scale_factor=scale_factor,
                preset_used="AUTO",
                feature_zones=feature_zones
            )
        else:
            # Fallback when no face is found or user explicitly chose a preset
            chosen_preset = preset if preset in PRESET_SCALES else "MEDIUM"
            scale_factor = PRESET_SCALES[chosen_preset]
            return FaceScaleInfo(
                has_face=False,
                faces_count=0,
                primary_face_box=None,
                all_face_boxes=[],
                face_height_px=TARGET_FACE_HEIGHT * scale_factor,
                scale_factor=scale_factor,
                preset_used=chosen_preset,
                feature_zones=[]
            )
