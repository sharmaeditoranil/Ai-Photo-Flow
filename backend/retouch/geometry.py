"""
Landmark-driven face geometry: face oval, protected facial features (eyes, brows, lips, nostrils),
eye-bag crescents and skin sampling spots. All shapes are expressed in "iod" units
(inter-ocular distance) inside the face's own rotated frame, so they follow head tilt and face size.
"""
from typing import List, Tuple

import cv2
import numpy as np

from backend.retouch.faces import Face


def _ellipse(canvas: np.ndarray, face: Face, center_xy: np.ndarray, axes_uv: Tuple[float, float], value: float = 1.0):
    cx, cy = float(center_xy[0]), float(center_xy[1])
    ax = max(1, int(round(axes_uv[0] * face.iod)))
    ay = max(1, int(round(axes_uv[1] * face.iod)))
    cv2.ellipse(canvas, (int(round(cx)), int(round(cy))), (ax, ay), face.angle_deg, 0, 360, value, -1, lineType=cv2.LINE_AA)


def _mouth_info(face: Face):
    ml, mr = face.landmarks[3], face.landmarks[4]
    mid = (ml + mr) / 2.0
    half_w = float(np.linalg.norm(mr - ml)) / face.iod / 2.0
    return mid, half_w, float(face.to_uv(mid)[1])


def face_oval_params(face: Face):
    _, _, mouth_v = _mouth_info(face)
    mouth_v = float(np.clip(mouth_v, 0.8, 1.5))
    top, bottom = -1.10, mouth_v + 0.62
    cv_ = (top + bottom) / 2.0
    # Width and horizontal centre come from the detector box: turned (3/4) faces have a
    # foreshortened eye distance, and the far cheek sits off-centre from the eyes.
    x, y, w, h = face.box
    box_c = face.to_uv(np.array([x + w / 2.0, y + h / 2.0], dtype=np.float32))
    half_w = float(np.clip(0.48 * w / face.iod, 0.95, 1.6))
    cu = float(np.clip(box_c[0], -0.45, 0.45))
    return face.to_xy(cu, cv_), (half_w, (bottom - top) / 2.0)


def draw_face_oval(canvas: np.ndarray, face: Face, grow: float = 1.0, value: float = 1.0):
    center, (au, av) = face_oval_params(face)
    _ellipse(canvas, face, center, (au * grow, av * grow), value)


def draw_features(canvas: np.ndarray, face: Face, margin: float = 0.0):
    """Protected zones: eyes (with lashes), eyebrows, lips/teeth, nostrils. margin in iod units."""
    m = margin
    el, er, nose = face.landmarks[0], face.landmarks[1], face.landmarks[2]
    # Eyes + lashes
    for eye in (el, er):
        _ellipse(canvas, face, eye, (0.33 + m, 0.19 + m))
    # Eyebrows: above each eye, slightly outward
    for eye, side in ((el, -1.0), (er, 1.0)):
        c = eye + face.iod * (side * 0.05 * face.ux - 0.37 * face.uy)
        _ellipse(canvas, face, c, (0.42 + m, 0.16 + m))
    # Lips, teeth
    mid, half_w, _ = _mouth_info(face)
    c = mid + face.iod * 0.03 * face.uy
    _ellipse(canvas, face, c, (half_w + 0.13 + m, 0.27 + m))
    # Nostrils (below the nose tip, the tip itself stays retouchable for shine removal)
    c = nose + face.iod * 0.13 * face.uy
    _ellipse(canvas, face, c, (0.27 + m, 0.11 + m))


def draw_heal_exclusions(canvas: np.ndarray, face: Face):
    """Extra zones AI Heal must never touch: nose wings / alar creases and inner eye corners
    (natural shading looks like dark spots there) and the bindi / maang-tikka line."""
    nose = face.landmarks[2]
    # Whole nose (bridge, sides, tip): follows the nose landmark, so turned faces are covered too
    nuv = face.to_uv(nose)
    c = (face.origin + nose) / 2.0 + face.iod * 0.06 * face.uy
    _ellipse(canvas, face, c, (0.30 + 0.6 * abs(float(nuv[0])), max(0.25, float(nuv[1]) / 2.0 + 0.16)))
    for side in (-1.0, 1.0):
        # Nose wing + alar crease + the top of the smile line (nasolabial fold)
        c = nose + face.iod * (side * 0.27 * face.ux + 0.06 * face.uy)
        _ellipse(canvas, face, c, (0.21, 0.25))
        c = nose + face.iod * (side * 0.40 * face.ux + 0.30 * face.uy)
        _ellipse(canvas, face, c, (0.13, 0.20))
    for eye, side in ((face.landmarks[0], 1.0), (face.landmarks[1], -1.0)):
        c = eye + face.iod * (side * 0.30 * face.ux + 0.08 * face.uy)
        _ellipse(canvas, face, c, (0.13, 0.17))
    # Bindi / tikka / sindoor line: centre of the forehead from between the brows upward
    _ellipse(canvas, face, face.to_xy(0.0, -0.72), (0.13, 0.55))


def draw_eyebags(canvas: np.ndarray, face: Face):
    for eye in (face.landmarks[0], face.landmarks[1]):
        c = eye + face.iod * 0.33 * face.uy
        _ellipse(canvas, face, c, (0.30, 0.14))


def body_gate(canvas: np.ndarray, face: Face):
    """Region where this person's retouchable skin can be: face, ears, neck and upper chest.
    Hands and arms are deliberately left out (mehndi designs, rings, bangles must stay crisp)
    and the region is narrow enough that neighbours in a group photo are not included."""
    draw_face_oval(canvas, face, grow=1.25)
    neck = [face.to_xy(u, v) for (u, v) in ((-1.25, 0.9), (1.25, 0.9), (2.6, 4.2), (-2.6, 4.2))]
    cv2.fillPoly(canvas, [np.round(np.array(neck)).astype(np.int32)], 1.0, lineType=cv2.LINE_AA)


def sample_points(face: Face) -> List[Tuple[np.ndarray, float]]:
    """Clean-skin sampling spots (centre, radius in px): both cheeks, forehead, chin."""
    mid, _, mouth_v = _mouth_info(face)
    pts = [
        (face.to_xy(-0.58, 0.68), 0.15),
        (face.to_xy(0.58, 0.68), 0.15),
        (face.to_xy(0.0, -0.62), 0.17),
        (mid + face.iod * 0.36 * face.uy, 0.10),
    ]
    return [(p, r * face.iod) for p, r in pts]


def owner_map(shape: Tuple[int, int], faces: List[Face], scale: float = 1.0) -> np.ndarray:
    """Index of the closest face for each pixel, distance measured in that face's iod units."""
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    best = np.full((h, w), np.inf, dtype=np.float32)
    owner = np.zeros((h, w), dtype=np.int16)
    for i, f in enumerate(faces):
        ox, oy = f.origin * scale
        d = np.hypot(xs - ox, ys - oy) / (f.iod * scale)
        sel = d < best
        best[sel] = d[sel]
        owner[sel] = i
    return owner
