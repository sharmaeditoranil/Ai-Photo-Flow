"""
Batch AI Heal Processing Engine
Processes folders or multiple photos with unified settings, per-file status,
progress callbacks, and graceful cancellation.
License: MIT / Apache-2.0 Permissive.
"""
import os
import time
import threading
import numpy as np
from typing import List, Dict, Any, Callable, Optional

from backend.heal.pipeline import AIHealPipeline
from backend.heal.io_metadata import ImageMetadataIO

class BatchHealProcessor:
    def __init__(self, pipeline: Optional[AIHealPipeline] = None):
        self.pipeline = pipeline or AIHealPipeline()
        self._cancel_requested = threading.Event()
        self.is_running = False

    def cancel(self):
        self._cancel_requested.set()

    def process_files(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        suffix: str = "_heal",
        strength: float = 60.0,
        opacity: float = 100.0,
        face_preset: str = "AUTO",
        progress_cb: Optional[Callable[[int, int, str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Processes a list of files sequentially.
        progress_cb(current_index, total_count, filename, result_info)
        """
        self._cancel_requested.clear()
        self.is_running = True
        total = len(file_paths)
        results = {
            "total": total,
            "processed": 0,
            "failed": 0,
            "cancelled": False,
            "items": []
        }

        try:
            for idx, src_path in enumerate(file_paths):
                if self._cancel_requested.is_set():
                    results["cancelled"] = True
                    break

                fname = os.path.basename(src_path)
                item_info = {"file": src_path, "status": "processing", "time": 0.0}

                try:
                    t0 = time.time()
                    float_rgb, meta = ImageMetadataIO.load_image(src_path)
                    u8_rgb = (np.clip(float_rgb * 255.0, 0, 255)).astype(np.uint8)

                    heal_res = self.pipeline.process_image(
                        u8_rgb,
                        strength=strength,
                        opacity=opacity,
                        face_preset=face_preset
                    )

                    # Determine target path
                    base, ext = os.path.splitext(fname)
                    out_fname = f"{base}{suffix}{ext}" if suffix else fname
                    out_folder = output_dir or os.path.dirname(src_path)
                    target_path = os.path.join(out_folder, out_fname)

                    # Save with preserved metadata
                    final_float = heal_res.blended_rgb.astype(np.float32) / 255.0
                    ImageMetadataIO.save_image(target_path, final_float, metadata=meta)

                    proc_time = time.time() - t0
                    item_info["status"] = "done"
                    item_info["target"] = target_path
                    item_info["time"] = proc_time
                    item_info["spots"] = heal_res.detected_spots_count
                    results["processed"] += 1

                except Exception as e:
                    item_info["status"] = "error"
                    item_info["error"] = str(e)
                    results["failed"] += 1

                results["items"].append(item_info)
                if progress_cb:
                    progress_cb(idx + 1, total, fname, item_info)

        finally:
            self.is_running = False

        return results
