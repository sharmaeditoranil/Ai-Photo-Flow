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

_FOCUS_FACE_H = 256   # faces are judged at album / screen size, not at pixel-peeping 100%


def _reblur_focus(gray: np.ndarray) -> float:
    """No-reference focus score 0-100 (re-blur method, Crete et al. 2007): how much edge contrast a
    small extra blur removes. Sharp edges lose a lot, an already blurred face loses almost nothing.
    The face is compared with itself, so smooth young skin and wrinkled skin score alike."""
    g = gray.astype(np.float32)
    dv = np.abs(np.diff(g, axis=0)); dh = np.abs(np.diff(g, axis=1))
    bv = np.abs(np.diff(cv2.blur(g, (1, 9)), axis=0)); bh = np.abs(np.diff(cv2.blur(g, (9, 1)), axis=1))
    kept_v = np.maximum(0.0, dv - bv).sum() / max(float(dv.sum()), 1e-6)
    kept_h = np.maximum(0.0, dh - bh).sum() / max(float(dh.sum()), 1e-6)
    return float(min(kept_v, kept_h) * 100.0)


def hires_face_sharpness(full_rgb: np.ndarray, boxes, ref_size) -> float:
    """Focus of the important faces (>= 25% of the largest), cropped from the full-resolution file and
    judged at album / screen size (256 px face height). Slight softness that only shows at 100% on a
    24+ MP file does not count; real miss-focus and motion blur do.
    Measured: real wedding faces 40-81, Gaussian blur sigma 7 px <= 33, 31 px motion blur median 30.
    Returns the best face score (2nd best with 3+ faces, 0-100) or -1 if nothing could be measured."""
    if full_rgb is None or not boxes:
        return -1.0
    H, W = full_rgb.shape[:2]
    k = max(H, W) / float(max(ref_size))
    areas = [b["w"] * b["h"] for b in boxes]
    largest = max(areas)
    scores = []
    for b, a in zip(boxes, areas):
        if a < 0.25 * largest:
            continue
        x0 = int(max(0, (b["x"] + b["w"] * 0.15) * k)); x1 = int(min(W, (b["x"] + b["w"] * 0.85) * k))
        y0 = int(max(0, (b["y"] + b["h"] * 0.15) * k)); y1 = int(min(H, (b["y"] + b["h"] * 0.85) * k))
        if x1 - x0 < 24 or y1 - y0 < 24:
            continue
        g = cv2.cvtColor(full_rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
        if g.shape[0] > _FOCUS_FACE_H:
            g = cv2.resize(g, (max(1, int(g.shape[1] * _FOCUS_FACE_H / g.shape[0])), _FOCUS_FACE_H),
                           interpolation=cv2.INTER_AREA)
        scores.append(_reblur_focus(g))
    if not scores:
        return -1.0
    scores.sort(reverse=True)
    # Group photos: in a well-focused group several faces are sharp, so the 2nd-best face is used and
    # one lucky face cannot make a shaken / missed group shot look sharp
    return round(scores[1] if len(scores) >= 3 else scores[0], 1)


class OpenCVFaceModel(FaceModel):
    @staticmethod
    def _safe_load_cascade(xml_path: str):
        if not xml_path or not os.path.isfile(xml_path):
            return None
        # 0. From memory: Python reads the file, OpenCV never touches the (Windows) path
        try:
            with open(xml_path, "r", encoding="utf-8") as fh:
                fs = cv2.FileStorage(fh.read(), cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
            clf = cv2.CascadeClassifier()
            if clf.read(fs.getFirstTopLevelNode()) and not clf.empty():
                return clf
        except Exception:
            pass
        try:
            clf = cv2.CascadeClassifier()
            # 1. Direct load
            if clf.load(xml_path) and not clf.empty():
                return clf

            # 2. Normalized forward slash path (fixes Windows backslash issues in OpenCV C++)
            fwd_path = os.path.normpath(xml_path).replace("\\", "/")
            if clf.load(fwd_path) and not clf.empty():
                return clf

            # 3. Safe temp copy (fixes Windows spaces in username e.g. "C:\Users\Naina Video\...")
            import tempfile, shutil
            safe_name = os.path.basename(xml_path)
            temp_dir = os.path.join(tempfile.gettempdir(), "photoflow_models")
            os.makedirs(temp_dir, exist_ok=True)
            temp_xml = os.path.join(temp_dir, safe_name)
            shutil.copy2(xml_path, temp_xml)
            temp_fwd = temp_xml.replace("\\", "/")
            if clf.load(temp_fwd) and not clf.empty():
                return clf
        except Exception:
            pass
        return None

    def __init__(self):
        cv_data_path = getattr(cv2, 'data', None)
        haarcascades_dir = getattr(cv_data_path, 'haarcascades', '') if cv_data_path else ''
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        backend_data = os.path.join(os.path.dirname(curr_dir), "data")

        possible_dirs = [
            backend_data,
            haarcascades_dir,
            os.path.join(getattr(sys, '_MEIPASS', ''), 'backend', 'data'),
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
                    self.face_cascade = self._safe_load_cascade(face_xml)
                if os.path.exists(eye_xml) and self.eye_cascade is None:
                    self.eye_cascade = self._safe_load_cascade(eye_xml)
                if os.path.exists(smile_xml) and self.smile_cascade is None:
                    self.smile_cascade = self._safe_load_cascade(smile_xml)

                if self.face_cascade is not None:
                    break

    def haar_boxes(self, image_np: np.ndarray) -> List[tuple]:
        """Frontal-face Haar boxes (x, y, w, h) in image pixels. Fallback detector only (no YuNet call)."""
        if self.face_cascade is None or image_np is None or image_np.size == 0:
            return []
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY) if len(image_np.shape) == 3 else image_np
        h, w = gray.shape[:2]
        scale = min(1.0, 1000.0 / float(max(h, w)))
        small = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1.0 else gray
        with _face_detector_lock:
            found = self.face_cascade.detectMultiScale(small, scaleFactor=1.1, minNeighbors=5,
                                                       minSize=(max(20, int(30 * scale)), max(20, int(30 * scale))))
        return [(int(x / scale), int(y / scale), int(fw / scale), int(fh / scale)) for (x, y, fw, fh) in found]

    def detect(self, image_np: np.ndarray) -> FaceMetrics:
        if image_np is None or image_np.size == 0:
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

        # Faces: YuNet DNN detector (finds turned, tilted and small faces; same detector as AI Retouch).
        # Falls back to the Haar cascade only if YuNet is unavailable.
        faces = []
        yunet_ran = False
        if len(image_np.shape) == 3:
            try:
                from backend.retouch.faces import detect_faces, _yunet
                yunet_ran = _yunet() is not None
                rgb_small = image_np if scale == 1.0 else cv2.resize(image_np, (small_gray.shape[1], small_gray.shape[0]))
                for f in detect_faces(rgb_small[:, :, :3]):
                    # Culling decisions need real people: statues, prints and patterns score lower
                    if yunet_ran and not f.estimated and f.score < 0.82:
                        continue
                    fx, fy, fw, fh = [int(round(v)) for v in f.box]
                    fx, fy = max(0, fx), max(0, fy)
                    fw = min(fw, small_gray.shape[1] - fx)
                    fh = min(fh, small_gray.shape[0] - fy)
                    if fw >= 20 and fh >= 20:
                        faces.append((fx, fy, fw, fh))
            except Exception:
                faces = []
        if not faces and not yunet_ran and self.face_cascade is not None:   # Haar only if YuNet is unavailable
            with _face_detector_lock:
                try:
                    faces = list(self.face_cascade.detectMultiScale(
                        small_gray,
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(int(30 * scale), int(30 * scale))
                    ))
                except Exception:
                    faces = []

        bounding_boxes: List[Dict[str, int]] = []
        face_sharpness_list: List[float] = []
        face_areas: List[int] = []
        face_lumas: List[float] = []
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
                # Light denoise first so high-ISO grain does not pass for detail
                face_den = cv2.GaussianBlur(face_roi_gray, (3, 3), 0.6)
                face_lap = cv2.Laplacian(face_den, cv2.CV_64F).var()
                norm_fs = min(100.0, max(0.0, (np.log1p(face_lap) / np.log1p(2000.0)) * 100.0))
                face_sharpness_list.append(norm_fs)
                face_areas.append(orig_w * orig_h)
                inner = face_roi_gray[orig_h // 5: orig_h - orig_h // 5, orig_w // 5: orig_w - orig_w // 5]
                face_lumas.append(float(np.median(inner)) if inner.size else float(np.median(face_roi_gray)))

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
        # Focus is judged like a photographer: the photo is in focus if one of the IMPORTANT faces is sharp
        # (faces at least 25% the size of the largest one). Small guests in the background don't count,
        # and a soft foreground person doesn't spoil a shot focused on the couple behind.
        main_face_sharpness = avg_face_sharpness
        main_face_brightness = -1.0
        if face_sharpness_list and len(face_areas) == len(face_sharpness_list) == len(face_lumas):
            largest = max(face_areas)
            important = [i for i, a in enumerate(face_areas) if a >= 0.25 * largest]
            best_i = max(important, key=lambda i: face_sharpness_list[i])
            main_face_sharpness = face_sharpness_list[best_i]
            main_face_brightness = face_lumas[best_i]

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
            face_sharpness=round(main_face_sharpness, 1),
            bounding_boxes=bounding_boxes,
            eyes_open_confidence=round(confidence, 2),
            is_close_up=is_close_up,
            has_emotion=has_emotion,
            face_brightness=round(main_face_brightness, 1)
        )
