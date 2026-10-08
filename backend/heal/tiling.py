"""
Seamless Overlapping Tiling & Cosine Feather Blending
Enables processing 50MP–100MP medium-format wedding portraits with zero visible seams.
License: MIT / BSD-3-Clause Permissive.
"""
import numpy as np
from typing import Callable, List, Tuple

def create_cosine_window(
    tile_h: int,
    tile_w: int,
    overlap: int,
    is_top: bool = False,
    is_bottom: bool = False,
    is_left: bool = False,
    is_right: bool = False
) -> np.ndarray:
    """
    Creates a 2D cosine (Hanning) feathering window that blends smoothly across overlapping borders.
    Outer image boundary edges remain 1.0 to avoid dark margins.
    """
    ry = np.ones(tile_h, dtype=np.float32)
    rx = np.ones(tile_w, dtype=np.float32)

    if overlap > 0:
        idx_y = np.arange(min(overlap, tile_h), dtype=np.float32)
        half_cos_y = 0.5 - 0.5 * np.cos((idx_y / float(overlap)) * np.pi)
        idx_x = np.arange(min(overlap, tile_w), dtype=np.float32)
        half_cos_x = 0.5 - 0.5 * np.cos((idx_x / float(overlap)) * np.pi)

        if not is_top:
            ry[:min(overlap, tile_h)] = half_cos_y
        if not is_bottom:
            ry[-min(overlap, tile_h):] = half_cos_y[::-1]
        if not is_left:
            rx[:min(overlap, tile_w)] = half_cos_x
        if not is_right:
            rx[-min(overlap, tile_w):] = half_cos_x[::-1]

    return np.outer(ry, rx)

class TiledProcessor:
    def __init__(self, tile_size: int = 512, overlap: int = 64):
        self.tile_size = tile_size
        self.overlap = overlap
        self.stride = tile_size - overlap

    def process(
        self,
        image_np: np.ndarray,
        tile_fn: Callable[[np.ndarray], np.ndarray]
    ) -> np.ndarray:
        """
        Executes tile_fn on overlapping chunks and reconstructs full resolution canvas
        with smooth cosine boundary weighting.
        """
        h, w = image_np.shape[:2]
        is_3d = len(image_np.shape) == 3
        channels = image_np.shape[2] if is_3d else 1

        # If image is smaller than single tile, run directly without overhead
        if h <= self.tile_size and w <= self.tile_size:
            return tile_fn(image_np)

        out_canvas = np.zeros((h, w, channels) if is_3d else (h, w), dtype=np.float32)
        weight_canvas = np.zeros((h, w), dtype=np.float32)

        # Generate grid coordinates
        y_steps = list(range(0, max(1, h - self.tile_size), self.stride))
        if len(y_steps) == 0 or y_steps[-1] + self.tile_size < h:
            y_steps.append(max(0, h - self.tile_size))

        x_steps = list(range(0, max(1, w - self.tile_size), self.stride))
        if len(x_steps) == 0 or x_steps[-1] + self.tile_size < w:
            x_steps.append(max(0, w - self.tile_size))

        for y in y_steps:
            is_top = (y == 0)
            is_bottom = (y + self.tile_size >= h)
            for x in x_steps:
                is_left = (x == 0)
                is_right = (x + self.tile_size >= w)

                y_end = min(h, y + self.tile_size)
                x_end = min(w, x + self.tile_size)
                actual_h = y_end - y
                actual_w = x_end - x

                tile_in = image_np[y:y_end, x:x_end]
                # Pad to uniform tile_size if boundary chunk is truncated
                if actual_h < self.tile_size or actual_w < self.tile_size:
                    pad_h = self.tile_size - actual_h
                    pad_w = self.tile_size - actual_w
                    if is_3d:
                        padded_tile = np.pad(tile_in, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
                    else:
                        padded_tile = np.pad(tile_in, ((0, pad_h), (0, pad_w)), mode="reflect")
                    tile_out_full = tile_fn(padded_tile)
                    tile_out = tile_out_full[:actual_h, :actual_w]
                else:
                    tile_out = tile_fn(tile_in)

                win_2d = create_cosine_window(
                    actual_h, actual_w, self.overlap,
                    is_top=is_top, is_bottom=is_bottom, is_left=is_left, is_right=is_right
                )
                win = win_2d[:, :, np.newaxis] if is_3d else win_2d

                out_canvas[y:y_end, x:x_end] += (tile_out.astype(np.float32) * win)
                weight_canvas[y:y_end, x:x_end] += win_2d

        # Normalize by accumulated feather weights
        safe_weight = np.maximum(1e-5, weight_canvas)
        if is_3d:
            safe_weight = safe_weight[:, :, np.newaxis]
        
        reconstructed = out_canvas / safe_weight
        return np.clip(reconstructed, 0, 255).astype(image_np.dtype)
