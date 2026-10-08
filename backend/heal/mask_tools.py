"""
Manual Mask Correction Tools (Brush & Eraser)
Enables photographers to paint to force heal areas AI missed,
or erase to protect beauty moles and features.
License: MIT / Apache-2.0 Permissive.
"""
import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class StrokeMode(str, Enum):
    HEAL = "HEAL"     # Force heal (white mask = apply heal)
    ERASE = "ERASE"   # Protect feature / mole (black mask = protect original)

@dataclass
class MaskStroke:
    points: List[Dict[str, float]] # [{'x': float, 'y': float}] normalized (0.0 to 1.0)
    radius: float                  # normalized radius (relative to min(h, w))
    mode: StrokeMode
    softness: float = 0.5          # 0.0 (hard) to 1.0 (very soft feathered)

class HealMaskManager:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.undo_stack: List[MaskStroke] = []
        self.redo_stack: List[MaskStroke] = []

    def add_stroke(self, stroke: MaskStroke):
        self.undo_stack.append(stroke)
        self.redo_stack.clear()

    def undo(self) -> bool:
        if self.undo_stack:
            stroke = self.undo_stack.pop()
            self.redo_stack.append(stroke)
            return True
        return False

    def redo(self) -> bool:
        if self.redo_stack:
            stroke = self.redo_stack.pop()
            self.undo_stack.append(stroke)
            return True
        return False

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

    def render_mask(self, base_mask: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Renders accumulated strokes into a float32 mask [0.0, 1.0].
        1.0 means heal is applied; 0.0 means original is protected.
        """
        if base_mask is not None:
            mask = np.clip(base_mask.astype(np.float32) / 255.0 if base_mask.dtype == np.uint8 else base_mask.astype(np.float32), 0.0, 1.0)
            if mask.shape[:2] != (self.height, self.width):
                mask = cv2.resize(mask, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        else:
            mask = np.ones((self.height, self.width), dtype=np.float32)

        for stroke in self.undo_stack:
            val = 1.0 if stroke.mode == StrokeMode.HEAL else 0.0
            r_px = max(2, int(stroke.radius * min(self.width, self.height)))
            k_size = max(3, int(r_px * 2) | 1)

            stroke_canvas = np.zeros((self.height, self.width), dtype=np.float32)
            for i in range(len(stroke.points)):
                pt = stroke.points[i]
                cx = int(np.clip(pt['x'] * self.width, 0, self.width - 1))
                cy = int(np.clip(pt['y'] * self.height, 0, self.height - 1))
                cv2.circle(stroke_canvas, (cx, cy), r_px, 1.0, -1)
                if i > 0:
                    prev = stroke.points[i - 1]
                    px = int(np.clip(prev['x'] * self.width, 0, self.width - 1))
                    py = int(np.clip(prev['y'] * self.height, 0, self.height - 1))
                    cv2.line(stroke_canvas, (px, py), (cx, cy), 1.0, thickness=r_px * 2)

            if stroke.softness > 0.05:
                sigma = float(max(1.0, r_px * stroke.softness))
                stroke_canvas = cv2.GaussianBlur(stroke_canvas, (k_size, k_size), sigma)

            if stroke.mode == StrokeMode.HEAL:
                mask = np.maximum(mask, stroke_canvas)
            else:
                mask = np.minimum(mask, 1.0 - stroke_canvas)

        return np.clip(mask, 0.0, 1.0)

    @staticmethod
    def composite(original_rgb: np.ndarray, healed_rgb: np.ndarray, mask: np.ndarray, opacity: float = 100.0) -> np.ndarray:
        """
        Combines original and healed according to formula:
        final = original * (1 - mask * opacity) + healed * (mask * opacity)
        """
        alpha = float(np.clip(opacity / 100.0, 0.0, 1.0))
        m = (mask * alpha)[:, :, np.newaxis]
        result = (original_rgb.astype(np.float32) * (1.0 - m)) + (healed_rgb.astype(np.float32) * m)
        return np.clip(result, 0, 255).astype(original_rgb.dtype)
