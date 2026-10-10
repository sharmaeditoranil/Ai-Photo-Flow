"""
Skin Mask: per-person CIELAB skin colour model sampled from cheeks / forehead / chin,
limited to the person's own body region and connected skin, with eyes / brows / lips / nostrils
and foreign objects (bindi, jewellery, hair) excluded. Refined edge-aware with a guided filter.

Every retouch stage (smoothing, imperfections, tone, heal, mattifier) is gated by these masks,
so nothing outside real skin is ever modified.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from backend.retouch import geometry
from backend.retouch.faces import Face
from backend.retouch.filters import gaussian, guided_filter, smoothstep

ANALYSIS_LONG_EDGE = 1400


@dataclass
class ColorModel:
    h_med: float   # hue angle (degrees) in a*b*
    h_sd: float
    L_med: float
    C_med: float


@dataclass
class SkinMasks:
    skin: np.ndarray        # float32 0..1, native resolution: all skin (face + body), features excluded
    domain: np.ndarray      # float32 0..1, native: retouchable FACE skin incl. shine/blemish holes (heal + matte)
    models: List[Optional[ColorModel]]


def _hue_chroma(lab: np.ndarray):
    a, b = lab[..., 1], lab[..., 2]
    return np.degrees(np.arctan2(b, a)), np.hypot(a, b)


def _fit_model(lab_samples: np.ndarray) -> Optional[ColorModel]:
    if lab_samples.shape[0] < 25:
        return None
    med = np.median(lab_samples, axis=0)
    mad = np.median(np.abs(lab_samples - med), axis=0) * 1.4826
    mad = np.maximum(mad, np.array([3.0, 1.2, 1.2], dtype=np.float32))
    keep = np.all(np.abs(lab_samples - med) < 2.5 * mad, axis=1)
    s = lab_samples[keep]
    if s.shape[0] < 20:
        s = lab_samples
    h, C = _hue_chroma(s)
    h_med = float(np.degrees(np.arctan2(np.median(s[:, 2]), np.median(s[:, 1]))))
    dh = (h - h_med + 180.0) % 360.0 - 180.0
    h_sd = float(max(3.0, 1.4826 * np.median(np.abs(dh))))
    return ColorModel(h_med, h_sd, float(np.median(s[:, 0])), float(max(3.0, np.median(C))))


def _model_from_points(lab: np.ndarray, pts_px: List, radius: float) -> Optional[ColorModel]:
    h, w = lab.shape[:2]
    m = np.zeros((h, w), np.uint8)
    for (x, y) in pts_px:
        cv2.circle(m, (int(x), int(y)), max(2, int(radius)), 1, -1)
    return _fit_model(lab[m > 0])


def _features(lab: np.ndarray, cm: ColorModel):
    """Hue difference (deg) and lightness-normalised chroma ratio relative to the skin model.
    Shading scales chroma roughly with L^0.6, so shadowed skin keeps ratio ~1 while hair, fabric
    and makeup (more saturated for their lightness) move away from 1."""
    h, C = _hue_chroma(lab)
    dh = np.abs((h - cm.h_med + 180.0) % 360.0 - 180.0)
    Lr = np.clip(lab[:, :, 0] / cm.L_med, 0.05, 1.0)
    r = (C / cm.C_med) / np.power(Lr, 0.6)
    return dh, C, r


def _prob(lab: np.ndarray, cm: ColorModel, tolerance: float, face_area: Optional[np.ndarray] = None) -> np.ndarray:
    """face_area (0..1): inside the face oval a bright, low-chroma pixel is a lit skin highlight (side light,
    flash, softbox), not white fabric, so the bright-pixel chroma rule is relaxed there."""
    k = max(0.2, tolerance / 30.0)
    dh, C, r = _features(lab, cm)
    tol_h = max(22.0, 3.0 * cm.h_sd) * (0.6 + 0.4 * k) + 30.0 * (1.0 - smoothstep(C, 2.0, 8.0))
    lo, hi = 0.44 - 0.08 * k, 1.35 + 0.20 * k
    p = 1.0 - np.clip((dh - tol_h) / 25.0, 0.0, 1.0) ** 2
    # Bright, washed-out pixels (white fabric, cups, walls) need near-skin chroma; only darker,
    # shaded skin under cool fill light may drop far below the model's chroma.
    bright = smoothstep(lab[:, :, 0] / cm.L_med, 0.85, 1.05)
    if face_area is not None:
        bright = bright * (1.0 - np.clip(face_area, 0.0, 1.0))
    lo = lo + (0.62 - lo) * bright
    p *= smoothstep(r, lo - 0.15, lo) * (1.0 - smoothstep(r, hi, hi + 0.3))
    p *= smoothstep(lab[:, :, 0], 0.14 * cm.L_med, 0.26 * cm.L_med)
    return p.astype(np.float32)


def _connected_to(binary: np.ndarray, seed: np.ndarray) -> np.ndarray:
    n, labels = cv2.connectedComponents(binary.astype(np.uint8), connectivity=8)
    if n <= 1:
        return np.zeros_like(binary, dtype=bool)
    hit = np.unique(labels[(seed > 0) & (labels > 0)])
    return np.isin(labels, hit)


def compute_masks(rgb_f: np.ndarray, lab_native: np.ndarray, faces: List[Face], sm: Dict[str, Any]) -> SkinMasks:
    """rgb_f: float32 RGB 0..1 (native crop), lab_native: float32 Lab of the same crop, faces in crop coords."""
    H, W = lab_native.shape[:2]
    s = min(1.0, ANALYSIS_LONG_EDGE / float(max(H, W)))
    pw, ph = max(1, int(round(W * s))), max(1, int(round(H * s)))
    lab = cv2.resize(lab_native, (pw, ph), interpolation=cv2.INTER_AREA) if s < 1.0 else lab_native
    pfaces = [f.scaled(s) for f in faces]
    # JPEG stores chroma at half resolution: denoise a*/b* so hue tests are not blocky
    lab = lab.copy()
    lab[:, :, 1:] = cv2.GaussianBlur(lab[:, :, 1:], (0, 0), 1.5)

    tolerance = float(sm.get("tolerance", 30))
    restrict = bool(sm.get("restrictToBody", True))
    exclude_features = bool(sm.get("excludeFeatures", True))
    samples = sm.get("colorSamples") or {}

    def _norm_pts(lst):
        return [(float(p[0]) * pw, float(p[1]) * ph) for p in (lst or []) if isinstance(p, (list, tuple)) and len(p) >= 2]

    set_pts = _norm_pts(samples.get("set"))
    set_model = _model_from_points(lab, set_pts, max(3, 0.01 * max(pw, ph))) if set_pts else None

    # Fine texture energy: beard, stubble, hair strands and lace are much "busier" than skin
    Lp = lab[:, :, 0]
    ref_iod_p = float(np.median([f.iod for f in pfaces])) if pfaces else 100.0
    s1 = max(0.7, 0.008 * ref_iod_p)
    tex = gaussian(np.abs(Lp - gaussian(Lp, s1)), max(1.0, 2.5 * s1))

    skin = np.zeros((ph, pw), np.float32)
    domain = np.zeros((ph, pw), np.float32)
    features = np.zeros((ph, pw), np.float32)
    models: List[Optional[ColorModel]] = []

    for f in pfaces:
        if set_model is not None:
            cm = set_model
        else:
            m = np.zeros((ph, pw), np.uint8)
            for (c, r) in geometry.sample_points(f):
                cv2.circle(m, (int(round(c[0])), int(round(c[1]))), max(2, int(round(r))), 1, -1)
            cm = _fit_model(lab[m > 0])
        models.append(cm)
        if cm is None:
            continue

        gate = np.zeros((ph, pw), np.float32)
        if restrict:
            geometry.body_gate(gate, f)
        else:
            gate[:] = 1.0
        oval = np.zeros((ph, pw), np.float32)
        geometry.draw_face_oval(oval, f)
        core = np.zeros((ph, pw), np.float32)
        geometry.draw_face_oval(core, f, grow=0.7)

        face_area = gaussian(oval, max(1.0, 0.08 * f.iod))
        p = _prob(lab, cm, tolerance, face_area) * gate
        samp = np.zeros((ph, pw), np.uint8)
        for (c, r_) in geometry.sample_points(f):
            cv2.circle(samp, (int(round(c[0])), int(round(c[1]))), max(2, int(round(r_))), 1, -1)
        tex_ref = float(np.median(tex[samp > 0])) if np.any(samp) else float(np.median(tex))
        # Beard / stubble / hair strands are busy AND darker or greyer than skin;
        # acne is busy too but redder, so it stays skin.
        _, _, r_feat = _features(lab, cm)
        r_loc = gaussian(r_feat, max(1.0, 2.5 * s1))
        L_loc = gaussian(Lp, max(1.0, 2.5 * s1))
        # Acne / blemishes are busy but REDDER than the person's skin; hair (dark, grey or blonde)
        # is not, so any busy non-red area is treated as hair.
        h_loc, _ = _hue_chroma(np.dstack([L_loc, gaussian(lab[:, :, 1], 2.5 * s1), gaussian(lab[:, :, 2], 2.5 * s1)]))
        red_shift = (cm.h_med - h_loc + 180.0) % 360.0 - 180.0
        acne_like = smoothstep(red_shift, 4.0, 12.0)
        dull = np.maximum(1.0 - smoothstep(r_loc, 0.75, 1.0), 1.0 - smoothstep(L_loc / cm.L_med, 0.62, 0.85))
        hairy = smoothstep(tex / max(tex_ref, 0.05), 2.2, 3.4) * np.maximum(dull, 1.0 - acne_like)
        p *= (1.0 - hairy)
        if restrict:
            keep = _connected_to(p > 0.45, core)
            k = max(3, int(round(0.04 * f.iod))) | 1
            keep = cv2.dilate(keep.astype(np.uint8), np.ones((k, k), np.uint8)).astype(np.float32)
            p *= keep

        # Face domain for heal / mattifier: fill skin holes (pimples, shine) but never foreign objects
        L = lab[:, :, 0]
        dh, Cf, r = _features(lab, cm)
        shine_like = (L > cm.L_med + 4.0) & (Cf < cm.C_med * 1.05) & (oval > 0)
        # Bindi, sindoor, jewellery, kajal, hair strands: far off the person's skin colour
        foreign = ((r > 2.6) | ((dh > 50.0) & (Cf > 8.0)) | (L < 0.30 * cm.L_med)) & ~shine_like & (oval > 0)
        foreign = cv2.morphologyEx(foreign.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        kf = max(3, int(round(0.05 * f.iod))) | 1
        foreign = cv2.dilate(foreign, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kf, kf)))

        foreign |= (hairy > 0.5) & ~shine_like & (oval > 0)
        base = ((p > 0.35) | shine_like).astype(np.uint8)
        kc = max(3, int(round(0.10 * f.iod))) | 1
        closed = cv2.morphologyEx(base, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kc, kc)))
        dom = (closed > 0) & (oval > 0) & (foreign == 0)
        dom = _connected_to(dom, core)

        feat = np.zeros((ph, pw), np.float32)
        geometry.draw_features(feat, f, margin=0.03)
        feat = np.clip(gaussian(feat, 0.025 * f.iod) * 1.3, 0, 1)
        features = np.maximum(features, feat)

        dom_f = dom.astype(np.float32) * (1.0 - feat)
        domain = np.maximum(domain, dom_f)
        # Inside the face, holes (pimples, shine) are skin too
        skin = np.maximum(skin, np.maximum(p, dom.astype(np.float32) * oval))

    # Eyedropper: expand / exclude skin colours
    exp_pts = _norm_pts(samples.get("expand"))
    if exp_pts:
        em = _model_from_points(lab, exp_pts, max(3, 0.01 * max(pw, ph)))
        if em is not None:
            gate_all = np.zeros((ph, pw), np.float32)
            for f in pfaces:
                geometry.body_gate(gate_all, f)
            skin = np.maximum(skin, _prob(lab, em, tolerance) * (gate_all if restrict else 1.0))
    exc_pts = _norm_pts(samples.get("exclude"))
    if exc_pts:
        xm = _model_from_points(lab, exc_pts, max(3, 0.01 * max(pw, ph)))
        if xm is not None:
            ex = _prob(lab, xm, 15.0)
            skin *= (1.0 - ex)
            domain *= (1.0 - ex)

    if exclude_features:
        skin *= (1.0 - features)

    # Upsample to native and refine edges against the real image (hairline, jaw, fingers)
    ref_iod = float(np.median([f.iod for f in faces])) if faces else 100.0
    guide = lab_native[:, :, 0] / 100.0
    skin_n = cv2.resize(skin, (W, H), interpolation=cv2.INTER_LINEAR) if s < 1.0 else skin
    skin_n = np.clip(guided_filter(guide, skin_n, max(2.0, 0.02 * ref_iod), 1e-3), 0.0, 1.0)
    feather = float(sm.get("feather", 50)) / 100.0
    if feather > 0:
        skin_n = gaussian(skin_n, max(0.5, feather * 0.03 * ref_iod))
    skin_n *= float(sm.get("opacity", 100)) / 100.0

    domain_n = cv2.resize(domain, (W, H), interpolation=cv2.INTER_LINEAR) if s < 1.0 else domain
    domain_n = gaussian(domain_n, max(0.5, 0.01 * ref_iod))
    return SkinMasks(skin=skin_n.astype(np.float32), domain=domain_n.astype(np.float32), models=models)
