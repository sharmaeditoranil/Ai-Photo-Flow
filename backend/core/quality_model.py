"""
Image Quality and Blur Detection Model
Analyzes sharpness, blur, and exposure problems using computer vision.
"""
import cv2
import numpy as np
from backend.core.interfaces import ImageQualityModel, QualityMetrics

class OpenCVQualityModel(ImageQualityModel):
    def __init__(self, blur_threshold: float = 120.0):
        self.blur_threshold = blur_threshold

    def evaluate(self, image_np: np.ndarray) -> QualityMetrics:
        if image_np is None or image_np.size == 0:
            return QualityMetrics(
                sharpness=0.0,
                blur_detected=True,
                mean_luminance=0.0,
                shadow_clipping=100.0,
                highlight_clipping=0.0,
                exposure_status="UNDER_EXPOSED",
                exposure_score=0.0,
                dynamic_range_score=0.0,
                overall_quality=0.0
            )

        # Convert to grayscale for sharpness analysis
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY if image_np.shape[2] == 3 else cv2.COLOR_RGB2GRAY)
        else:
            gray = image_np

        # 1. Blur and Sharpness via Laplacian Variance + Sobel Energy
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        raw_variance = float(laplacian.var())

        # Also calculate Tenengrad gradient energy for high frequency detail
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_energy = float(np.mean(sobelx**2 + sobely**2))

        # Normalized sharpness score (0 to 100)
        # Using sigmoid-like smooth curve
        norm_sharpness = min(100.0, max(0.0, (np.log1p(raw_variance) / np.log1p(2500.0)) * 100.0))
        blur_detected = raw_variance < self.blur_threshold

        # 2. Exposure & Luminance Analysis
        mean_lum = float(np.mean(gray))
        total_pixels = float(gray.size)

        # Shadows: pixels < 18 (crushed blacks)
        shadow_clipped_pct = float(np.sum(gray < 18) / total_pixels * 100.0)
        # Highlights: pixels > 240 (blown whites)
        highlight_clipped_pct = float(np.sum(gray > 240) / total_pixels * 100.0)

        p10 = float(np.percentile(gray, 10))
        p50 = float(np.percentile(gray, 50))
        p90 = float(np.percentile(gray, 90))

        # Photographic exposure classification:
        # Underexposed: dark midtones or severe shadow clipping
        if p50 < 85.0 or mean_lum < 85.0 or shadow_clipped_pct > 14.0 or p90 < 155.0:
            exposure_status = "UNDER_EXPOSED"
            exposure_score = max(10.0, 100.0 - (90.0 - mean_lum) * 1.6 - shadow_clipped_pct * 1.5)
        # Overexposed: blown highlights or washed-out midtones
        elif p50 > 155.0 or mean_lum > 160.0 or highlight_clipped_pct > 10.0 or p10 > 105.0:
            exposure_status = "OVER_EXPOSED"
            exposure_score = max(10.0, 100.0 - (mean_lum - 150.0) * 1.6 - highlight_clipped_pct * 1.8)
        else:
            exposure_status = "GOOD"
            # Optimal midtone is ~115-135
            dist_from_optimal = abs(p50 - 125.0)
            exposure_score = max(55.0, 100.0 - (dist_from_optimal * 0.5) - (shadow_clipped_pct * 0.6) - (highlight_clipped_pct * 0.8))

        exposure_score = float(np.clip(exposure_score, 0.0, 100.0))

        # Dynamic range score: spread between 5th and 95th percentiles
        p5 = float(np.percentile(gray, 5))
        p95 = float(np.percentile(gray, 95))
        dr_spread = p95 - p5
        dr_score = float(np.clip((dr_spread / 210.0) * 100.0, 0.0, 100.0))

        # Composite overall quality (0 - 100)
        overall_quality = (norm_sharpness * 0.45) + (exposure_score * 0.40) + (dr_score * 0.15)
        if blur_detected:
            overall_quality *= 0.60 # Penalty for out of focus

        return QualityMetrics(
            sharpness=round(norm_sharpness, 1),
            blur_detected=blur_detected,
            mean_luminance=round(mean_lum, 1),
            shadow_clipping=round(shadow_clipped_pct, 1),
            highlight_clipping=round(highlight_clipped_pct, 1),
            exposure_status=exposure_status,
            exposure_score=round(exposure_score, 1),
            dynamic_range_score=round(dr_score, 1),
            overall_quality=round(float(overall_quality), 1)
        )
