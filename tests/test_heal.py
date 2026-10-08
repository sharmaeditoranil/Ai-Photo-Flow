"""
Unit tests for AI Heal Pipeline:
- Scale Normalization
- Frequency-separated texture preservation
- Seamless cosine window tiling
- Non-destructive opacity blending
"""
import unittest
import numpy as np
import cv2

from backend.heal.face_scale import FaceScaleEstimator, TARGET_FACE_HEIGHT, PRESET_SCALES
from backend.heal.tiling import TiledProcessor
from backend.heal.pipeline import AIHealPipeline


class TestAIHealPipeline(unittest.TestCase):
    def setUp(self):
        self.estimator = FaceScaleEstimator()
        self.pipeline = AIHealPipeline()
        self.tiler = TiledProcessor(tile_size=256, overlap=32)

    def test_presets_scale(self):
        """Test preset fallback scales when no face is found."""
        dummy = np.zeros((600, 600, 3), dtype=np.uint8)
        
        info_small = self.estimator.estimate_scale(dummy, preset="SMALL")
        self.assertEqual(info_small.scale_factor, PRESET_SCALES["SMALL"])

        info_med = self.estimator.estimate_scale(dummy, preset="MEDIUM")
        self.assertEqual(info_med.scale_factor, PRESET_SCALES["MEDIUM"])

        info_large = self.estimator.estimate_scale(dummy, preset="LARGE")
        self.assertEqual(info_large.scale_factor, PRESET_SCALES["LARGE"])

    def test_precomputed_face_boxes(self):
        """Test scale factor derived from precomputed face box."""
        dummy = np.zeros((1000, 1000, 3), dtype=np.uint8)
        boxes = [{"x": 200, "y": 200, "w": 400, "h": 768}] # Height 768px = 2x target
        info = self.estimator.estimate_scale(dummy, preset="AUTO", precomputed_boxes=boxes)
        
        self.assertTrue(info.has_face)
        self.assertAlmostEqual(info.scale_factor, 768.0 / TARGET_FACE_HEIGHT, places=2)

    def test_seamless_tiling_reconstruction(self):
        """Test that TiledProcessor reconstructs image seamlessly with identity transform."""
        h, w = 600, 800
        # Create gradient image with texture
        y, x = np.mgrid[0:h, 0:w]
        synthetic_img = ((x * 0.3 + y * 0.2) % 256).astype(np.uint8)
        synthetic_rgb = cv2.merge([synthetic_img, synthetic_img, synthetic_img])

        reconstructed = self.tiler.process(synthetic_rgb, lambda tile: tile)
        
        # Max error between original and reconstructed through 256px overlapping tiles must be < 2
        diff = np.abs(synthetic_rgb.astype(np.float32) - reconstructed.astype(np.float32))
        max_diff = np.max(diff)
        self.assertLessEqual(max_diff, 2.0, "Tiling feather blending should be mathematically seamless")

    def test_opacity_blending(self):
        """Test that opacity=0% returns identical image and opacity=100% applies healing."""
        # Create skin patch with genuine human skin tone (R=220, G=160, B=130)
        img = np.full((300, 300, 3), [220, 160, 130], dtype=np.uint8)
        # Add manual spot or red pimple
        manual_spots = [{"x": 0.5, "y": 0.5, "radius": 0.03}]

        # 0% opacity: must return 100% identical image to original
        res_0 = self.pipeline.process_image(img, strength=80.0, opacity=0.0, face_preset="MEDIUM", manual_spots=manual_spots)
        np.testing.assert_array_equal(res_0.blended_rgb, img, "Opacity 0% must return 100% identical image")

        # 100% opacity: must execute inpainting and return valid canvas
        res_100 = self.pipeline.process_image(img, strength=80.0, opacity=100.0, face_preset="MEDIUM", manual_spots=manual_spots)
        self.assertEqual(res_100.blended_rgb.shape, img.shape)
        self.assertGreaterEqual(res_100.detected_spots_count, 1)


    def test_mask_manager_undo_redo(self):
        """Test brush/eraser strokes and undo/redo operations."""
        from backend.heal.mask_tools import HealMaskManager, MaskStroke, StrokeMode
        manager = HealMaskManager(width=200, height=200)

        # Base mask is all 1.0 (heal applied everywhere)
        base = np.ones((200, 200), dtype=np.float32)
        m0 = manager.render_mask(base)
        self.assertEqual(float(np.mean(m0)), 1.0)

        # Add eraser stroke to protect mole
        stroke = MaskStroke(points=[{"x": 0.5, "y": 0.5}], radius=0.05, mode=StrokeMode.ERASE, softness=0.0)
        manager.add_stroke(stroke)
        m1 = manager.render_mask(base)
        # Center should be erased to 0.0
        self.assertEqual(float(m1[100, 100]), 0.0)

        # Test Undo
        self.assertTrue(manager.undo())
        m2 = manager.render_mask(base)
        self.assertEqual(float(m2[100, 100]), 1.0)

        # Test Redo
        self.assertTrue(manager.redo())
        m3 = manager.render_mask(base)
        self.assertEqual(float(m3[100, 100]), 0.0)

    def test_model_runner_fallback(self):
        """Test that AIHealModelRunner safely falls back when model file is not present."""
        from backend.heal.model_runner import AIHealModelRunner
        runner = AIHealModelRunner(model_path=None)
        self.assertFalse(runner.is_onnx_active())
        self.assertEqual(runner.active_provider, "BUILTIN_ENGINE")


if __name__ == "__main__":
    unittest.main()
