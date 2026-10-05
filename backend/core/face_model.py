"""
Face and Eye Detection Model
Detects faces, analyzes eye state (open/closed), and measures face sharpness.
"""
import os
import cv2
import numpy as np
import sys
from typing import Dict, List, Any
from backend.core.interfaces import FaceModel, FaceMetrics

import threading

_face_detector_lock = threading.Lock()

class OpenCVFaceModel(FaceModel):
    def __init__(self):
        cv_data_path = getattr(cv2, 'data', None)
        haarcascades_dir = getattr(cv_data_path, 'haarcascades', '') if cv_data_path else ''

        possible_dirs = [
            haarcascades_dir,
            os.path.join(getattr(sys, '_MEIPASS', ''), 'cv2', 'data'),
            os.path.join(os.path.dirname(cv2.__file__), 'data') if hasattr(cv2, '__file__') else '',
        ]

        self.face_cascade = None
        self.eye_cascade = None
        self.smile_cascade = None

        for p in possible_dirs:
            if p and os.path.isdir(p):
                face_xml = os.path.join(p, 'haarcascade_frontalface_default.xml')
                eye_xml = os.path.join(p, 'haarcascade_eye.xml')
                smile_xml = os.path.join(p, 'haarcascade_smile.xml')
                if os.path.exists(face_xml) and self.face_cascade is None:
                    self.face_cascade = cv2.CascadeClassifier(face_xml)
                if os.path.exists(eye_xml) and self.eye_cascade is None:
                    self.eye_cascade = cv2.CascadeClassifier(eye_xml)
                if os.path.exists(smile_xml) and self.smile_cascade is None:
                    self.smile_cascade = cv2.CascadeClassifier(smile_xml)
                if self.face_cascade is not None:
                    break

    def detect(self, image_np: np.ndarray) -> FaceMetrics:
        if image_np is None or image_np.size == 0 or self.face_cascade is None:
            return FaceMetrics(0, "NO_FACE", 0.0, [], 0.0)

        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = image_np

        h, w = gray.shape[:2]
        # Resize for fast detection if large
        scale = 1.0
        max_dim = 1000
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            small_gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
        else:
            small_gray = gray

        # Detect frontal faces with thread lock to avoid OpenCV C++ buffer races
        faces = ()
        with _face_detector_lock:
            try:
                faces = self.face_cascade.detectMultiScale(
                    small_gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(int(30 * scale), int(30 * scale))
                )
            except Exception:
                faces = ()

        bounding_boxes: List[Dict[str, int]] = []
        face_sharpness_list: List[float] = []
        eyes_detected_count = 0
        total_expected_eyes = 0
        is_close_up = False
        has_emotion = False

        for (x, y, fw, fh) in faces:
            # Scale coordinates back
            orig_x = int(x / scale)
            orig_y = int(y / scale)
            orig_w = int(fw / scale)
            orig_h = int(fh / scale)
            bounding_boxes.append({"x": orig_x, "y": orig_y, "w": orig_w, "h": orig_h})

            # Check if this is a prominent close-up portrait (face occupies >= 20% of frame)
            if orig_h >= h * 0.20 or orig_w >= w * 0.20:
                is_close_up = True

            # Face region
            face_roi_gray = gray[orig_y:orig_y+orig_h, orig_x:orig_x+orig_w]
            if face_roi_gray.size > 0:
                face_lap = cv2.Laplacian(face_roi_gray, cv2.CV_64F).var()
                norm_fs = min(100.0, max(0.0, (np.log1p(face_lap) / np.log1p(2000.0)) * 100.0))
                face_sharpness_list.append(norm_fs)

                # Eye detection in upper half of face
                upper_half = face_roi_gray[0:int(orig_h * 0.55), :]
                if upper_half.size > 0 and self.eye_cascade is not None:
                    eyes = ()
                    with _face_detector_lock:
                        try:
                            eyes = self.eye_cascade.detectMultiScale(
                                upper_half,
                                scaleFactor=1.1,
                                minNeighbors=3,
                                minSize=(int(orig_w * 0.12), int(orig_h * 0.12))
                            )
                        except Exception:
                            eyes = ()
                    total_expected_eyes += 2
                    eyes_detected_count += min(2, len(eyes))

                # Emotion / Smile detection in lower half of face
                lower_half = face_roi_gray[int(orig_h * 0.50):orig_h, int(orig_w * 0.15):int(orig_w * 0.85)]
                if self.smile_cascade is not None and lower_half.size > 0:
                    smiles = ()
                    with _face_detector_lock:
                        try:
                            smiles = self.smile_cascade.detectMultiScale(
                                lower_half,
                                scaleFactor=1.3,
                                minNeighbors=14,
                                minSize=(int(orig_w * 0.15), int(orig_h * 0.10))
                            )
                        except Exception:
                            smiles = ()
                    if len(smiles) > 0:
                        has_emotion = True

        faces_count = len(bounding_boxes)
        avg_face_sharpness = float(np.mean(face_sharpness_list)) if face_sharpness_list else 0.0

        if faces_count == 0:
            eyes_status = "NO_FACE"
            confidence = 0.90
        else:
            if total_expected_eyes > 0:
                ratio = eyes_detected_count / float(total_expected_eyes)
            else:
                ratio = 1.0

            if ratio >= 0.5:
                eyes_status = "OPEN"
                confidence = 0.92
            elif ratio > 0.0:
                eyes_status = "PARTIAL"
                confidence = 0.80
            else:
                # If face has active emotion (laughing, joyful smile) or high sharpness, treat as expressive candid
                if has_emotion or is_close_up or avg_face_sharpness > 60.0:
                    eyes_status = "OPEN"
                    confidence = 0.85
                else:
                    eyes_status = "CLOSED"
                    confidence = 0.82

        return FaceMetrics(
            faces_count=faces_count,
            eyes_status=eyes_status,
            face_sharpness=round(avg_face_sharpness, 1),
            bounding_boxes=bounding_boxes,
            eyes_open_confidence=round(confidence, 2),
            is_close_up=is_close_up,
            has_emotion=has_emotion
        )
