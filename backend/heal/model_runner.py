"""
ONNX Runtime Model Runner for AI Heal
Supports CoreML (macOS), DirectML / CUDA (Windows), and automatic CPU fallback.
License: MIT / Apache-2.0 Permissive.
"""
import os
import logging
import numpy as np
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

class AIHealModelRunner:
    def __init__(self, model_path: Optional[str] = None, device_preference: str = "AUTO"):
        """
        device_preference: "AUTO", "GPU", "CPU"
        """
        self.model_path = model_path
        self.device_preference = device_preference.upper()
        self.session = None
        self.input_name = None
        self.output_name = None
        self.active_provider = "NONE"
        self._init_session()

    def _init_session(self):
        if not self.model_path or not os.path.exists(self.model_path):
            logger.info("No external ONNX model provided; using built-in classical frequency-separation engine.")
            self.active_provider = "BUILTIN_ENGINE"
            return

        try:
            import onnxruntime as ort

            available_providers = ort.get_available_providers()
            selected_providers = []

            if self.device_preference in ("AUTO", "GPU"):
                # macOS Apple Silicon Neural Engine / Metal via CoreML
                if "CoreMLExecutionProvider" in available_providers:
                    selected_providers.append("CoreMLExecutionProvider")
                # Windows DirectML
                if "DmlExecutionProvider" in available_providers:
                    selected_providers.append("DmlExecutionProvider")
                # NVIDIA CUDA
                if "CUDAExecutionProvider" in available_providers:
                    selected_providers.append("CUDAExecutionProvider")

            # Always add CPU fallback
            selected_providers.append("CPUExecutionProvider")

            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = max(1, os.cpu_count() or 4)

            self.session = ort.InferenceSession(self.model_path, sess_options=opts, providers=selected_providers)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.active_provider = self.session.get_providers()[0]
            logger.info(f"Initialized AIHealModelRunner with provider: {self.active_provider}")
        except Exception as e:
            logger.warning(f"Failed to initialize ONNX session ({e}); falling back to built-in engine.")
            self.session = None
            self.active_provider = "BUILTIN_ENGINE"

    def is_onnx_active(self) -> bool:
        return self.session is not None

    def predict_residual(self, rgb_patch: np.ndarray) -> Optional[np.ndarray]:
        """
        Runs inference on 512x512 RGB float32 [0, 1] patch.
        Outputs predicted residual (output = input + predicted_residual).
        """
        if not self.is_onnx_active():
            return None

        try:
            # Shape (1, 3, H, W), float32 [0, 1]
            h, w = rgb_patch.shape[:2]
            patch_norm = rgb_patch.astype(np.float32) / 255.0
            inp = np.transpose(patch_norm, (2, 0, 1))[np.newaxis, ...]

            preds = self.session.run([self.output_name], {self.input_name: inp})[0]
            pred_residual = np.transpose(preds[0], (1, 2, 0)) # (H, W, 3)
            return (pred_residual * 255.0).astype(np.float32)
        except Exception as e:
            logger.error(f"ONNX inference error: {e}")
            return None
