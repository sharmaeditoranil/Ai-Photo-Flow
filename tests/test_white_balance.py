"""
Unit tests for AI Auto White Balance (backend/core/white_balance.py).
A synthetic colour-chart scene (textured grey and coloured patches) is lit with known casts;
the analysis must detect the direction of the cast and correct it, keeping part of warm casts.
"""
import unittest
from unittest import mock

import numpy as np

from backend.core import white_balance as wbm


def chart_scene(seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    H, W = 600, 900
    lin = np.zeros((H, W, 3), np.float32)
    colours = [(0.45, 0.45, 0.45), (0.2, 0.2, 0.2), (0.7, 0.7, 0.7), (0.5, 0.25, 0.15), (0.15, 0.3, 0.5),
               (0.2, 0.45, 0.2), (0.55, 0.5, 0.15), (0.35, 0.35, 0.35), (0.6, 0.6, 0.6), (0.4, 0.2, 0.35),
               (0.3, 0.3, 0.3), (0.12, 0.12, 0.12)]
    k = 0
    for y in range(0, H, 150):
        for x in range(0, W, 225):
            c = np.array(colours[k % len(colours)], np.float32)
            lin[y:y + 150, x:x + 225] = c
            k += 1
    # Texture (shading variation scales all channels equally, like real surfaces)
    shade = 1.0 + 0.25 * rng.standard_normal((H, W)).astype(np.float32)
    lin *= np.clip(shade, 0.4, 1.6)[:, :, None]
    return np.clip(lin, 0.0, 1.0)


def lit(lin: np.ndarray, cast) -> np.ndarray:
    out = lin * np.array(cast, np.float32)
    out /= max(float(out.max()), 1e-6)
    return (wbm.linear_to_srgb(out) * 255.0).astype(np.uint8)


class TestAutoWhiteBalance(unittest.TestCase):
    def analyze(self, img):
        with mock.patch("backend.retouch.faces.detect_faces", return_value=[]):
            return wbm.analyze_white_balance(img)

    def residual(self, cast, res):
        g = np.array(res["gains"]) * np.array(cast)
        return g / g[1]

    def test_neutral_scene_is_left_alone(self):
        res = self.analyze(lit(chart_scene(), (1.0, 1.0, 1.0)))
        g = np.array(res["gains"])
        self.assertLess(float(np.abs(g / g[1] - 1.0).max()), 0.06)

    def test_green_cast_removed(self):
        cast = (0.88, 1.0, 0.86)
        res = self.analyze(lit(chart_scene(), cast))
        r = self.residual(cast, res)
        self.assertLess(abs(r[0] - 1.0), 0.06)
        self.assertLess(abs(r[2] - 1.0), 0.06)

    def test_blue_cast_removed(self):
        cast = (0.78, 0.9, 1.0)
        res = self.analyze(lit(chart_scene(), cast))
        r = self.residual(cast, res)
        self.assertLess(abs(r[0] - 1.0), 0.07)
        self.assertLess(abs(r[2] - 1.0), 0.07)

    def test_tungsten_partly_kept_for_ambience(self):
        cast = (1.0, 0.72, 0.42)
        res = self.analyze(lit(chart_scene(), cast))
        r = self.residual(cast, res)
        # Clearly corrected toward neutral ...
        self.assertLess(r[0], 1.30)
        self.assertGreater(r[2], 0.70)
        # ... but some warmth kept on purpose
        self.assertGreater(r[0], 1.02)
        self.assertIn("warm", res["cast"])
        self.assertIsNotNone(res["kelvin"])
        self.assertLess(res["kelvin"], 5000)

    def test_effective_gains_strength(self):
        wb = {"enabled": True, "strength": 0, "gains": [1.2, 1.0, 0.8]}
        self.assertIsNone(wbm.effective_gains(wb))
        wb["strength"] = 100
        g = wbm.effective_gains(wb)
        self.assertGreater(g[0], g[2])
        self.assertIsNone(wbm.effective_gains({**wb, "enabled": False}))

    def test_apply_preserves_neutral_and_range(self):
        img = np.full((10, 10, 3), 128, np.float32)
        out = wbm.apply_white_balance(img, np.array([1.0, 1.0, 1.0], np.float32))
        self.assertLess(float(np.abs(out - img).max()), 0.6)
        out = wbm.apply_white_balance(np.full((4, 4, 3), 250, np.float32), np.array([1.5, 1.0, 0.7], np.float32))
        self.assertLessEqual(float(out.max()), 255.0)


if __name__ == "__main__":
    unittest.main()
