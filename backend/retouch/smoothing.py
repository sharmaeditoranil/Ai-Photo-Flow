"""
Skin Details: edge-aware multi-band frequency separation, applied ONLY through the skin mask.

    fine   = I      - S(r0)       pores, fine texture
    medium = S(r0)  - S(4 r0)     small blotches, uneven texture
    coarse = S(4r0) - S(16 r0)    large tonal variations
    base   = S(16 r0)

S() is a self-guided (edge-preserving) filter, and r0 is proportional to the person's face size
(inter-ocular distance), so the look is identical for a 1000 px thumbnail and a 6000 px export and
consistent between big and small faces in a group photo (each person uses their own scale).
"""
from typing import List

import cv2
import numpy as np

from backend.retouch.faces import Face
from backend.retouch.filters import gaussian, masked_gaussian, self_guided


def _band_gain(amount: float, slider: float) -> float:
    a = amount / 100.0
    s = slider / 100.0
    # + attenuates the band (smoother), - preserves / boosts it (more texture)
    return 1.0 - a * s if s >= 0 else 1.0 - a * s * 0.6


def portrait_iod(faces: List[Face], params: dict, short_edge: int) -> float:
    if params.get("autoPortraitSize", True) and faces:
        return faces[0].iod
    ps = float(params.get("portraitSize", 50)) / 100.0
    return max(8.0, short_edge * (0.01 + 0.24 * ps ** 1.5))


def _smooth_region(lab: np.ndarray, mask: np.ndarray, iod: float, p: dict):
    amount = float(p.get("amount", 0))
    gf = _band_gain(amount, float(p.get("fine", 0)))
    gm = _band_gain(amount, float(p.get("medium", 0)))
    gc = _band_gain(amount, float(p.get("coarse", 0)))
    balance = float(p.get("balance", 0)) / 100.0
    w_dark = min(1.0, 1.0 - balance)
    w_bright = min(1.0, 1.0 + balance)

    L = lab[:, :, 0]
    r0 = max(1.0, 0.012 * iod)
    eps = 5.0 ** 2
    S1 = self_guided(L, r0, eps)
    S2 = self_guided(L, 4.0 * r0, eps * 1.5)
    S3 = self_guided(L, 16.0 * r0, eps * 2.5)
    fine, medium, coarse = L - S1, S1 - S2, S2 - S3

    def apply(band, g):
        if abs(g - 1.0) < 1e-4:
            return band
        if g < 1.0 and (w_dark < 1.0 or w_bright < 1.0):
            w = np.where(band < 0, w_dark, w_bright).astype(np.float32)
            return band * (1.0 - (1.0 - g) * w)
        return band * g

    L_new = S3 + apply(coarse, gc) + apply(medium, gm) + apply(fine, gf)

    # Even out blotchy colour (gentler than luminance)
    chroma_k = (amount / 100.0) * max(0.0, float(p.get("medium", 0))) / 100.0 * 0.5
    m = mask
    lab[:, :, 0] = L + (L_new - L) * m
    if chroma_k > 0.0:
        for ch in (1, 2):
            c = lab[:, :, ch]
            c_s = masked_gaussian(c, (m > 0.3).astype(np.float32), 2.5 * r0)
            lab[:, :, ch] = c + (c_s - c) * (m * chroma_k)


def smooth_skin(lab: np.ndarray, skin: np.ndarray, faces: List[Face], p: dict):
    """In-place skin smoothing on lab. Each face owns the skin closest to it (group photos)."""
    if float(p.get("amount", 0)) <= 0.5 or not faces:
        return
    H, W = lab.shape[:2]
    nz = skin > 0.01
    if not np.any(nz):
        return
    if len(faces) == 1 or not p.get("autoPortraitSize", True):
        iod = portrait_iod(faces, p, min(H, W))
        ys, xs = np.where(nz)
        pad = int(16 * max(1.0, 0.012 * iod)) + 4
        y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
        sub = lab[y0:y1, x0:x1]
        _smooth_region(sub, skin[y0:y1, x0:x1], iod, p)
        return

    # Group photo: assign skin to the nearest face (distance in that face's own iod units)
    s = min(1.0, 600.0 / max(H, W))
    sh, sw = max(1, int(H * s)), max(1, int(W * s))
    ys, xs = np.mgrid[0:sh, 0:sw].astype(np.float32)
    best = np.full((sh, sw), np.inf, np.float32)
    owner = np.zeros((sh, sw), np.int16)
    for i, f in enumerate(faces):
        d = np.hypot(xs - f.origin[0] * s, ys - f.origin[1] * s) / (f.iod * s)
        sel = d < best
        best[sel] = d[sel]
        owner[sel] = i
    owner_n = cv2.resize(owner.astype(np.uint8 if len(faces) < 256 else np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    for i, f in enumerate(faces):
        own = (owner_n == i)
        m_i = np.where(own, skin, 0.0).astype(np.float32)
        nz_i = m_i > 0.01
        if not np.any(nz_i):
            continue
        # soften the ownership seam so neighbouring people blend smoothly
        m_i = np.minimum(skin, gaussian(m_i, max(1.0, 0.05 * f.iod)) * 1.0)
        yy, xx = np.where(nz_i)
        pad = int(16 * max(1.0, 0.012 * f.iod)) + 4
        y0, y1 = max(0, yy.min() - pad), min(H, yy.max() + pad + 1)
        x0, x1 = max(0, xx.min() - pad), min(W, xx.max() + pad + 1)
        _smooth_region(lab[y0:y1, x0:x1], m_i[y0:y1, x0:x1], f.iod, p)
