import unittest
import numpy as np
import cv2
from backend.core.editing_model import IndianWeddingEditingModel
from backend.core.interfaces import EditParameters, FaceMetrics
from backend.services.image_service import apply_edit_pipeline, _teeth_whitening, _eye_sparkle, _radial_falloff

class TestAIDetectionRules(unittest.TestCase):
    def setUp(self):
        self.model = IndianWeddingEditingModel()

    def test_sharp_image_no_unblur(self):
        # Create a sharp high-contrast synthetic test image
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        img[::10, :] = 255
        img[:, ::10] = 255
        fm = FaceMetrics(faces_count=1, eyes_status="OPEN", face_sharpness=85.0, bounding_boxes=[{"x": 100, "y": 100, "w": 150, "h": 150}], eyes_open_confidence=0.95)
        params = self.model.calculate_corrections(img, face_metrics=fm, calibrate=False)
        self.assertEqual(params.ai_unblur, 0.0, "Sharp image should receive 0.0 ai_unblur")

    def test_blurry_image_triggers_unblur(self):
        # Create a blurred image
        img = np.ones((400, 400, 3), dtype=np.uint8) * 128
        fm = FaceMetrics(faces_count=1, eyes_status="OPEN", face_sharpness=35.0, bounding_boxes=[{"x": 100, "y": 100, "w": 150, "h": 150}], eyes_open_confidence=0.95)
        params = self.model.calculate_corrections(img, face_metrics=fm, calibrate=False)
        self.assertGreater(params.ai_unblur, 20.0, "Blurry face should trigger ai_unblur focus recovery")

    def test_closed_eyes_no_eye_sparkle(self):
        img = np.ones((400, 400, 3), dtype=np.uint8) * 120
        fm = FaceMetrics(faces_count=1, eyes_status="CLOSED", face_sharpness=70.0, bounding_boxes=[{"x": 100, "y": 100, "w": 150, "h": 150}], eyes_open_confidence=0.10)
        params = self.model.calculate_corrections(img, face_metrics=fm, calibrate=False)
        self.assertEqual(params.eye_sparkle, 0.0, "Closed eyes must receive 0.0 eye sparkle")

    def test_open_eyes_get_eye_sparkle(self):
        img = np.ones((400, 400, 3), dtype=np.uint8) * 120
        fm = FaceMetrics(faces_count=1, eyes_status="OPEN", face_sharpness=70.0, bounding_boxes=[{"x": 100, "y": 100, "w": 150, "h": 150}], eyes_open_confidence=0.95)
        params = self.model.calculate_corrections(img, face_metrics=fm, calibrate=False)
        self.assertGreater(params.eye_sparkle, 15.0, "Open eyes should receive eye sparkle")

    def test_dark_bg_no_radial_falloff(self):
        # Dark background image
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        # Put subject in center
        img[100:300, 100:300] = 160
        params = self.model.calculate_corrections(img, calibrate=False)
        self.assertEqual(params.radial_falloff, 0.0, "Dark background must receive 0.0 radial falloff")

    def test_group_shot_no_radial_falloff(self):
        img = np.ones((400, 600, 3), dtype=np.uint8) * 140
        boxes = [
            {"x": 20, "y": 100, "w": 80, "h": 80},
            {"x": 150, "y": 100, "w": 80, "h": 80},
            {"x": 280, "y": 100, "w": 80, "h": 80},
            {"x": 420, "y": 100, "w": 80, "h": 80}
        ]
        fm = FaceMetrics(faces_count=4, eyes_status="OPEN", face_sharpness=70.0, bounding_boxes=boxes, eyes_open_confidence=0.95)
        params = self.model.calculate_corrections(img, face_metrics=fm, calibrate=False)
        self.assertEqual(params.radial_falloff, 0.0, "Wide group shot with 4 people must receive 0.0 radial falloff")

    def test_no_face_no_teeth_or_lips(self):
        # Macro decor image with 0 faces
        img = np.ones((300, 300, 3), dtype=np.uint8) * 130
        fm = FaceMetrics(faces_count=0, eyes_status="NO_FACE", face_sharpness=0.0, bounding_boxes=[], eyes_open_confidence=0.0)
        params = self.model.calculate_corrections(img, face_metrics=fm, calibrate=False)
        self.assertEqual(params.teeth_whitening, 0.0, "No face means 0 teeth whitening")
        self.assertEqual(params.eye_sparkle, 0.0, "No face means 0 eye sparkle")
        self.assertEqual(params.lip_enhancement, 0.0, "No face means 0 lip enhancement")

if __name__ == "__main__":
    unittest.main()
