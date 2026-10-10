"""
Face detection + 5-point landmarks for the AI Skin Retouch module.
Uses OpenCV YuNet (MIT license, opencv_zoo) which works on group photos and gives eyes / nose / mouth points.
Falls back to the bundled Haar cascade (estimated landmarks) if the ONNX model is missing.
"""
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

YUNET_FILE = "face_detection_yunet_2023mar.onnx"
_tls = threading.local()


def _model_path() -> Optional[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(here), "models", YUNET_FILE),
        os.path.join(getattr(sys, "_MEIPASS", ""), "backend", "models", YUNET_FILE),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


_model_bytes: Optional[np.ndarray] = None
_model_lock = threading.Lock()
_load_logged = False


def _log_detector(msg: str) -> None:
    """One line per backend start in ~/.photoflow/backend.log (diagnostics for Windows installs)."""
    global _load_logged
    if _load_logged:
        return
    _load_logged = True
    try:
        import time
        d = os.path.join(os.path.expanduser("~"), ".photoflow")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "backend.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [faces] {msg}\n")
    except Exception:
        pass


def _yunet_bytes() -> Optional[np.ndarray]:
    """The ONNX model read by Python (handles any Windows path: spaces, Unicode user names), shared by threads."""
    global _model_bytes
    if _model_bytes is None:
        with _model_lock:
            if _model_bytes is None:
                path = _model_path()
                if path is not None:
                    _model_bytes = np.fromfile(path, dtype=np.uint8)
    return _model_bytes


def _yunet():
    det = getattr(_tls, "yunet", None)
    if det is None and not getattr(_tls, "yunet_failed", False):
        err = None
        # 1. From memory: OpenCV never opens the file itself, so the install path cannot break it
        try:
            buf = _yunet_bytes()
            if buf is None:
                raise FileNotFoundError(YUNET_FILE)
            det = cv2.FaceDetectorYN.create("onnx", buf, np.array([], np.uint8), (320, 320), 0.72, 0.3, 5000)
        except Exception as e:
            err, det = e, None
        # 2. Older OpenCV builds without the buffer overload: load by path
        if det is None:
            try:
                path = _model_path()
                if path is not None:
                    det = cv2.FaceDetectorYN.create(path, "", (320, 320), 0.72, 0.3, 5000)
            except Exception as e:
                err, det = e, None
        if det is None:
            _tls.yunet_failed = True
            _log_detector(f"YuNet face model NOT loaded ({err!r}); using Haar fallback")
        else:
            _tls.yunet = det
            _log_detector(f"YuNet face model loaded (OpenCV {cv2.__version__})")
    return det


@dataclass
class Face:
    box: Tuple[float, float, float, float]  # x, y, w, h (pixels)
    landmarks: np.ndarray                   # (5, 2): eye_img_left, eye_img_right, nose, mouth_img_left, mouth_img_right
    score: float
    estimated: bool = False                 # landmarks guessed from a Haar box

    # Derived face frame (computed in __post_init__)
    origin: np.ndarray = field(init=False)
    ux: np.ndarray = field(init=False)
    uy: np.ndarray = field(init=False)
    iod: float = field(init=False)
    angle_deg: float = field(init=False)

    def __post_init__(self):
        el, er = self.landmarks[0], self.landmarks[1]
        d = er - el
        self.iod = float(max(1.0, np.hypot(d[0], d[1])))
        self.ux = d / self.iod
        self.uy = np.array([-self.ux[1], self.ux[0]], dtype=np.float32)
        self.origin = (el + er) / 2.0
        self.angle_deg = float(np.degrees(np.arctan2(self.ux[1], self.ux[0])))

    def to_uv(self, pt: np.ndarray) -> np.ndarray:
        rel = (np.asarray(pt, dtype=np.float32) - self.origin) / self.iod
        return np.array([rel @ self.ux, rel @ self.uy], dtype=np.float32)

    def to_xy(self, u: float, v: float) -> np.ndarray:
        return self.origin + self.iod * (u * self.ux + v * self.uy)

    def scaled(self, s: float, dx: float = 0.0, dy: float = 0.0) -> "Face":
        x, y, w, h = self.box
        lm = self.landmarks * s + np.array([dx, dy], dtype=np.float32)
        return Face((x * s + dx, y * s + dy, w * s, h * s), lm.astype(np.float32), self.score, self.estimated)


def _order_landmarks(lm: np.ndarray) -> np.ndarray:
    """Order eyes / mouth corners left-to-right in image space along the eye axis."""
    lm = lm.astype(np.float32).copy()
    e0, e1 = lm[0], lm[1]
    axis = e1 - e0
    if axis[0] < 0:
        lm[[0, 1]] = lm[[1, 0]]
        axis = -axis
    m0, m1 = lm[3], lm[4]
    if float((m1 - m0) @ axis) < 0:
        lm[[3, 4]] = lm[[4, 3]]
    return lm


def _iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _plausible(f: Face) -> bool:
    x, y, w, h = f.box
    if w <= 0 or h <= 0:
        return False
    ratio = f.iod / w
    if ratio < 0.18 or ratio > 0.75:
        return False
    nose = f.to_uv(f.landmarks[2])
    mouth = f.to_uv((f.landmarks[3] + f.landmarks[4]) / 2.0)
    # Nose must sit below the eye line and mouth below the nose (in the face's own frame)
    return 0.15 < nose[1] < 1.3 and nose[1] < mouth[1] < 2.0


def _detect_yunet(rgb: np.ndarray) -> Optional[List[Face]]:
    det = _yunet()
    if det is None:
        return None
    h, w = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    found: List[Face] = []
    tried = set()
    # Two scales: small proxy finds big close-up faces, large proxy finds small faces in group photos
    for target in (640, 1800):
        s = min(1.0, target / float(max(h, w)))
        key = round(s, 3)
        if key in tried:
            continue
        tried.add(key)
        sw, sh = max(1, int(round(w * s))), max(1, int(round(h * s)))
        small = cv2.resize(bgr, (sw, sh), interpolation=cv2.INTER_AREA) if s < 1.0 else bgr
        try:
            det.setInputSize((sw, sh))
            _, rows = det.detect(small)
        except Exception:
            rows = None
        if rows is None:
            continue
        inv = 1.0 / s
        for r in rows:
            box = (float(r[0] * inv), float(r[1] * inv), float(r[2] * inv), float(r[3] * inv))
            lm = np.array(r[4:14], dtype=np.float32).reshape(5, 2) * inv
            found.append(Face(box, _order_landmarks(lm), float(r[14])))
    return found


def _detect_haar(rgb: np.ndarray) -> List[Face]:
    try:
        from backend.core.face_model import OpenCVFaceModel
        fm = getattr(_tls, "haar", None)
        if fm is None:
            fm = OpenCVFaceModel()
            _tls.haar = fm
        # Haar boxes only: OpenCVFaceModel.detect() itself calls detect_faces(), which would loop back here
        boxes = fm.haar_boxes(rgb)
    except Exception:
        return []
    faces = []
    for (x, y, w, h) in boxes:
        x, y, w, h = float(x), float(y), float(w), float(h)
        lm = np.array([
            [x + 0.31 * w, y + 0.40 * h], [x + 0.69 * w, y + 0.40 * h],
            [x + 0.50 * w, y + 0.60 * h],
            [x + 0.36 * w, y + 0.78 * h], [x + 0.64 * w, y + 0.78 * h],
        ], dtype=np.float32)
        faces.append(Face((x, y, w, h), lm, 0.75, estimated=True))
    return faces


def detect_faces(rgb: np.ndarray, min_face_frac: float = 0.02) -> List[Face]:
    """Detect every face in an RGB uint8 image. Returns faces sorted by size (largest first)."""
    if rgb is None or rgb.size == 0:
        return []
    if rgb.dtype != np.uint8:
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    faces = _detect_yunet(rgb)
    if faces is None:
        faces = _detect_haar(rgb)

    faces = [f for f in faces if _plausible(f)]
    faces.sort(key=lambda f: -f.score)
    kept: List[Face] = []
    for f in faces:
        if all(_iou(f.box, k.box) < 0.35 for k in kept):
            kept.append(f)

    h, w = rgb.shape[:2]
    min_w = max(18.0, min_face_frac * min(h, w))
    kept = [f for f in kept if f.box[2] >= min_w]
    kept.sort(key=lambda f: -f.iod)
    return kept
