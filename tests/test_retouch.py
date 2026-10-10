"""
Unit tests for the AI Skin Retouch module (backend/retouch):
- parameter schema / presets
- no-face photos are returned unchanged
- AI Heal finds blemishes on skin and never on eyes / lips
- every stage leaves non-skin pixels bit-for-bit unchanged
- preview (downscaled) and full-resolution renders match
"""
import unittest
from unittest import mock

import cv2
import numpy as np

from backend.retouch import build_preset, list_presets, retouch_image, sanitize
from backend.retouch import engine
from backend.retouch.faces import Face
from backend.retouch.heal import detect_spots
from backend.retouch.skin_mask import compute_masks


def synthetic_portrait(scale: float = 1.0, pimples=True):
    """Skin-toned face on a blue background with eyes, brows, lips and red pimples."""
    rng = np.random.default_rng(7)
    H, W = int(900 * scale), int(700 * scale)
    img = np.zeros((H, W, 3), np.float32)
    img[:] = (60, 90, 150)
    cx, cy = W / 2, H * 0.45
    iod = 160 * scale
    skin = np.zeros((H, W), np.uint8)
    cv2.ellipse(skin, (int(cx), int(cy)), (int(1.25 * iod), int(1.55 * iod)), 0, 0, 360, 1, -1)
    cv2.rectangle(skin, (int(cx - 0.6 * iod), int(cy + 1.2 * iod)), (int(cx + 0.6 * iod), H), 1, -1)  # neck
    tone = np.array((205, 150, 120), np.float32)
    tex = cv2.GaussianBlur(rng.normal(0, 6, (H, W)).astype(np.float32), (0, 0), 1.0 * scale)
    img[skin > 0] = tone + tex[skin > 0, None]
    eyes = [(cx - iod / 2, cy - 0.1 * iod), (cx + iod / 2, cy - 0.1 * iod)]
    for ex, ey in eyes:
        cv2.ellipse(img, (int(ex), int(ey)), (int(0.22 * iod), int(0.1 * iod)), 0, 0, 360, (240, 240, 240), -1)
        cv2.circle(img, (int(ex), int(ey)), int(0.08 * iod), (40, 25, 20), -1)
        cv2.ellipse(img, (int(ex), int(ey - 0.38 * iod)), (int(0.3 * iod), int(0.05 * iod)), 0, 0, 360, (50, 35, 30), -1)
    mouth = (cx, cy + 0.95 * iod)
    cv2.ellipse(img, (int(mouth[0]), int(mouth[1])), (int(0.4 * iod), int(0.12 * iod)), 0, 0, 360, (170, 60, 70), -1)
    spots = []
    if pimples:
        for (u, v) in ((-0.75, 0.55), (0.8, 0.6), (-0.8, 0.9), (0.72, 0.95)):
            px, py = cx + u * iod, cy - 0.1 * iod + v * iod
            r = 0.035 * iod
            blob = np.zeros((H, W), np.float32)
            cv2.circle(blob, (int(px), int(py)), int(r), 1.0, -1)
            blob = cv2.GaussianBlur(blob, (0, 0), r * 0.5)
            img -= blob[:, :, None] * np.array((10, 45, 40), np.float32)
            spots.append((px, py))
    img = np.clip(img, 0, 255).astype(np.uint8)
    lm = np.array([eyes[0], eyes[1], (cx, cy + 0.5 * iod), (cx - 0.38 * iod, mouth[1]), (cx + 0.38 * iod, mouth[1])], np.float32)
    face = Face((cx - 1.2 * iod, cy - 1.4 * iod, 2.4 * iod, 2.8 * iod), lm, 0.99)
    return img, face, spots, skin


class TestRetouchParams(unittest.TestCase):
    def test_sanitize_clamps_and_fills_defaults(self):
        p = sanitize({"heal": {"opacity": 400}, "skinDetails": {"fine": -500}})
        self.assertEqual(p["heal"]["opacity"], 100.0)
        self.assertEqual(p["skinDetails"]["fine"], -100.0)
        self.assertIn("mattifier", p)
        self.assertTrue(p["enabled"])

    def test_presets(self):
        names = [p["name"] for p in list_presets()]
        for required in ("Natural", "Smoothing - Men", "Wedding Flash", "Studio Clean", "Off"):
            self.assertIn(required, names)
        self.assertFalse(build_preset("Off")["enabled"])


class TestRetouchEngine(unittest.TestCase):
    def setUp(self):
        engine._cache.clear()

    def test_no_face_is_unchanged(self):
        img = np.full((300, 400, 3), 128, np.uint8)
        with mock.patch.object(engine, "detect_faces", return_value=[]):
            out, res = retouch_image(img, build_preset("Natural"))
        self.assertEqual(res.faces, 0)
        np.testing.assert_array_equal(np.clip(out + 0.5, 0, 255).astype(np.uint8), img)

    def test_heal_finds_pimples_not_features(self):
        img, face, truth, _ = synthetic_portrait()
        f = img.astype(np.float32) / 255.0
        lab = cv2.cvtColor(f, cv2.COLOR_RGB2LAB)
        masks = compute_masks(f, lab, [face], build_preset("Natural")["skinMask"])
        spots = detect_spots(lab, masks.domain, [face], 60)
        found = sum(any(np.hypot(s.x - tx, s.y - ty) < 0.05 * face.iod for s in spots) for tx, ty in truth)
        self.assertGreaterEqual(found, 3, f"only {found}/4 pimples found")
        for s in spots:
            for eye in face.landmarks[:2]:
                self.assertGreater(np.hypot(s.x - eye[0], s.y - eye[1]), 0.3 * face.iod)
            mouth = (face.landmarks[3] + face.landmarks[4]) / 2
            self.assertGreater(np.hypot(s.x - mouth[0], s.y - mouth[1]), 0.3 * face.iod)

    def test_only_skin_changes(self):
        img, face, truth, skin = synthetic_portrait()
        with mock.patch.object(engine, "detect_faces", return_value=[face]):
            out, res = retouch_image(img, build_preset("Smoothing - High"), want_masks=True)
        result = np.clip(out + 0.5, 0, 255).astype(np.uint8)
        far_from_skin = cv2.dilate(skin, np.ones((25, 25), np.uint8)) == 0
        np.testing.assert_array_equal(result[far_from_skin], img[far_from_skin])
        # Pupils must not be altered
        for eye in face.landmarks[:2]:
            x, y = int(eye[0]), int(eye[1])
            d = np.abs(result[y - 5:y + 5, x - 5:x + 5].astype(int) - img[y - 5:y + 5, x - 5:x + 5].astype(int))
            self.assertLess(d.max(), 4)
        # Pimples are visibly reduced
        tx, ty = map(int, truth[0])
        before = img[ty - 2:ty + 3, tx - 2:tx + 3, 1].mean()
        after = result[ty - 2:ty + 3, tx - 2:tx + 3, 1].mean()
        self.assertGreater(after - before, 15)

    def test_preview_matches_full_resolution(self):
        full, face_full, _, _ = synthetic_portrait(scale=2.0)
        small = cv2.resize(full, (full.shape[1] // 2, full.shape[0] // 2), interpolation=cv2.INTER_AREA)
        face_small = face_full.scaled(0.5)
        with mock.patch.object(engine, "detect_faces", return_value=[face_full]):
            out_full, _ = retouch_image(full, build_preset("Natural"))
        engine._cache.clear()
        with mock.patch.object(engine, "detect_faces", return_value=[face_small]):
            out_small, _ = retouch_image(small, build_preset("Natural"))
        down = cv2.resize(out_full, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA)
        diff = np.abs(down - out_small)
        self.assertLess(float(diff.mean()), 1.0)
        self.assertLess(float(np.percentile(diff, 99.5)), 12.0)


if __name__ == "__main__":
    unittest.main()
