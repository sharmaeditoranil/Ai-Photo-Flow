"""
AI Auto White Balance with skin-tone verification.

1. Illuminant estimation with the "grey pixel" method (Yang, Gao & Li, CVPR 2015): pixels whose
   local contrast is identical in all three log-RGB channels are achromatic surfaces, whatever the
   colour of the light. Their average colour is the colour of the light.
2. Skin-tone verification: after correction, the skin of every detected face must fall inside the
   natural skin hue range (CIELAB). If it does not (e.g. a scene dominated by red decor fooled the
   grey estimate), the correction is pulled toward the gains that put the skin in range.
3. Wedding-friendly strength: warm (tungsten / mandap / candle) casts are corrected only partly so
   the ambience survives; green / magenta casts (fluorescent, LED) are removed almost completely.

Gains are applied in linear light and normalised so overall brightness does not change.
"""
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

# Natural (Indian) skin in camera JPEGs measures 35-48 deg; above ~52 it reads yellow / green.
SKIN_HUE_MIN = 34.0   # degrees in Lab a*b*; below -> too pink / magenta
SKIN_HUE_MAX = 52.0   # above -> too yellow / green
SKIN_HUE_TARGET = 44.0

WARM_KEEP = 0.20      # fraction of a warm cast that is kept for ambience (clean, professional colour)
WARM_KEEP_LOW_KEY = 0.45   # night / lamp-lit scenes: the warm practical light IS the mood, keep more of it
COOL_STRENGTH = 0.85
TINT_STRENGTH = 0.92


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def _normalize_gains(g: np.ndarray) -> np.ndarray:
    # Keep luminance (Rec.709 weights) constant
    y = 0.2126 * g[0] + 0.7152 * g[1] + 0.0722 * g[2]
    return g / max(y, 1e-6)


def estimate_illuminant_grey_pixels(lin: np.ndarray, exclude: Optional[np.ndarray] = None):
    """Returns (illuminant RGB normalised to mean 1, confidence 0..1, selected-pixel count)."""
    eps = 1e-4
    img = cv2.GaussianBlur(lin, (0, 0), 1.0)
    logI = np.log(img + eps)
    contrast = []
    for c in range(3):
        lap = cv2.Laplacian(cv2.GaussianBlur(logI[:, :, c], (0, 0), 1.0), cv2.CV_32F)
        contrast.append(np.abs(lap))
    contrast = np.stack(contrast, -1)
    mean_c = contrast.mean(-1)
    gi = contrast.std(-1) / (mean_c + eps)
    gi = cv2.blur(gi, (7, 7))

    lum = img.mean(-1)
    # Only textured surfaces: smooth painted walls / backdrops have no usable local contrast and
    # their own colour would be mistaken for the light's colour
    valid = (img.min(-1) > 0.02) & (img.max(-1) < 0.95) & (mean_c > 0.04)
    if exclude is not None:
        valid &= exclude < 0.3
    n_valid = int(valid.sum())
    if n_valid < 500:
        return np.ones(3, np.float32), 0.0, 0
    vals = gi[valid]
    n_sel = max(200, int(0.005 * n_valid))
    thr = np.partition(vals, min(n_sel, vals.size - 1))[min(n_sel, vals.size - 1)]
    sel = valid & (gi <= thr)
    px = img[sel]
    # Weight brighter grey pixels more (better SNR), ignore the darkest quarter
    w = lum[sel]
    keep = w > np.percentile(w, 25)
    px, w = px[keep], w[keep]
    if px.shape[0] < 50:
        return np.ones(3, np.float32), 0.0, 0
    chroma = px / np.maximum(px.sum(-1, keepdims=True), eps)
    illum = (chroma * w[:, None]).sum(0) / w.sum()
    illum = illum / illum.mean()
    # Consistency of the grey candidates = confidence
    spread = float(np.median(np.abs(chroma - np.median(chroma, 0)).sum(-1)))
    conf = float(np.clip(1.0 - spread / 0.06, 0.0, 1.0)) * float(np.clip(px.shape[0] / 400.0, 0.2, 1.0))
    return illum.astype(np.float32), conf, int(px.shape[0])


def estimate_illuminant_grey_edge(lin: np.ndarray, exclude: Optional[np.ndarray] = None, p: float = 6.0):
    """Grey-Edge (van de Weijer et al. 2007): the average edge colour is achromatic."""
    img = cv2.GaussianBlur(lin, (0, 0), 2.0)
    ok = (img.max(-1) < 0.95)
    if exclude is not None:
        ok &= exclude < 0.3
    if ok.sum() < 500:
        return None
    e = []
    for c in range(3):
        gx = cv2.Sobel(img[:, :, c], cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(img[:, :, c], cv2.CV_32F, 0, 1)
        mag = np.sqrt(gx * gx + gy * gy)[ok]
        e.append(float(np.power(np.mean(np.power(mag, p)), 1.0 / p)))
    e = np.array(e, np.float32)
    return e / e.mean() if e.min() > 1e-6 else None


def estimate_illuminant_white_patch(lin: np.ndarray, exclude: Optional[np.ndarray] = None):
    """Bright-patch estimate: the brightest unclipped surfaces reflect the light's colour."""
    ok = lin.max(-1) < 0.97
    if exclude is not None:
        ok &= exclude < 0.3
    px = lin[ok]
    if px.shape[0] < 500:
        return None
    lum = px.mean(-1)
    top = px[lum >= np.percentile(lum, 99.0)]
    if top.shape[0] < 20:
        return None
    e = np.median(top, 0)
    return e / e.mean() if e.min() > 1e-6 else None


def _to_chroma(illum: np.ndarray) -> np.ndarray:
    return np.array([np.log(illum[0] / illum[1]), np.log(illum[2] / illum[1])], np.float64)


def _from_chroma(ch: np.ndarray) -> np.ndarray:
    e = np.array([np.exp(ch[0]), 1.0, np.exp(ch[1])])
    return e / e.mean()


def _skin_samples(rgb_u8: np.ndarray, faces) -> Optional[np.ndarray]:
    """Linear-RGB pixels from both cheeks and the forehead of every detected face."""
    from backend.retouch import geometry
    h, w = rgb_u8.shape[:2]
    m = np.zeros((h, w), np.uint8)
    for f in faces:
        for (c, r) in geometry.sample_points(f):
            cv2.circle(m, (int(round(c[0])), int(round(c[1]))), max(2, int(round(r))), 1, -1)
    if m.sum() < 30:
        return None
    px = rgb_u8[m > 0].astype(np.float32) / 255.0
    # Drop specular highlights and deep shadows
    lum = px.mean(-1)
    lo, hi = np.percentile(lum, 15), np.percentile(lum, 90)
    px = px[(lum >= lo) & (lum <= hi)]
    return srgb_to_linear(px) if px.shape[0] >= 20 else None


def _skin_hue(lin_px: np.ndarray, gains: np.ndarray) -> float:
    corr = np.clip(lin_px * gains, 0.0, 1.0)
    srgb = linear_to_srgb(np.median(corr, 0)).astype(np.float32).reshape(1, 1, 3)
    lab = cv2.cvtColor(srgb, cv2.COLOR_RGB2LAB)[0, 0]
    return float(np.degrees(np.arctan2(lab[2], lab[1])))


def _cct_from_illuminant(illum: np.ndarray) -> Optional[int]:
    """Approximate correlated colour temperature (McCamy) of the estimated light."""
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    X, Y, Z = M @ illum.astype(np.float64)
    s = X + Y + Z
    if s <= 0:
        return None
    x, y = X / s, Y / s
    n = (x - 0.3320) / (0.1858 - y)
    cct = 449.0 * n ** 3 + 3525.0 * n ** 2 + 6823.3 * n + 5520.33
    return int(np.clip(round(cct / 50.0) * 50, 1800, 15000))


def _describe(gains: np.ndarray) -> str:
    r, g, b = gains
    if b > r * 1.06:
        warm = "warm (yellow/orange)"
    elif r > b * 1.06:
        warm = "cool (blue)"
    else:
        warm = ""
    tint = ""
    if g < (r + b) / 2 * 0.96:
        tint = "green"
    elif g > (r + b) / 2 * 1.04:
        tint = "magenta"
    parts = [p for p in (warm, tint) if p]
    return " + ".join(parts) + " cast" if parts else "neutral"


def analyze_white_balance(rgb_u8: np.ndarray, faces: Optional[List] = None) -> Dict[str, Any]:
    """Analyse a (proxy) RGB uint8 image and return the auto-WB block stored in EditParameters."""
    h, w = rgb_u8.shape[:2]
    s = min(1.0, 900.0 / max(h, w))
    small = cv2.resize(rgb_u8, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else rgb_u8
    lin = srgb_to_linear(small.astype(np.float32) / 255.0).astype(np.float32)

    if faces is None:
        from backend.retouch.faces import detect_faces
        faces = detect_faces(small)
    else:
        faces = [f.scaled(s) for f in faces]

    # Skin is never grey: keep faces out of the grey-pixel search
    exclude = None
    if faces:
        from backend.retouch import geometry
        exclude = np.zeros(small.shape[:2], np.float32)
        for f in faces:
            geometry.draw_face_oval(exclude, f, grow=1.4)

    # Three independent illuminant estimators; their agreement is the confidence
    gp, gp_conf, n_grey = estimate_illuminant_grey_pixels(lin, exclude)
    ests = []
    if gp_conf > 0.05:
        ests.append(_to_chroma(gp))
    for est in (estimate_illuminant_grey_edge(lin, exclude), estimate_illuminant_white_patch(lin, exclude)):
        if est is not None:
            ests.append(_to_chroma(est))
    notes = []
    if len(ests) >= 2:
        E = np.stack(ests)
        combined = np.median(E, 0) if len(ests) >= 3 else E.mean(0)
        spread = max(float(np.linalg.norm(a - b)) for i, a in enumerate(E) for b in E[i + 1:])
        conf = float(np.clip(0.45 + 0.55 * np.exp(-spread / 0.25), 0.0, 1.0))
    elif len(ests) == 1:
        combined, conf = ests[0], 0.3
    else:
        combined, conf = np.zeros(2), 0.0
    # Dominant-colour guard: a big blue wall or red mandap decor is real colour, not a cast
    # (measured AFTER removing the estimated cast: a tungsten cast tints everything orange,
    #  but once removed the colours spread out, while a blue wall stays blue)
    est_g = _normalize_gains(1.0 / np.maximum(_from_chroma(combined), 1e-3)).astype(np.float32)
    neutral = linear_to_srgb(np.clip(lin * est_g.reshape(1, 1, 3), 0.0, 1.0)).astype(np.float32)
    lab_s = cv2.cvtColor(neutral, cv2.COLOR_RGB2LAB)
    C = np.hypot(lab_s[:, :, 1], lab_s[:, :, 2])
    colourful = C > 15.0
    if exclude is not None:
        colourful &= exclude < 0.3
    if colourful.mean() > 0.25:
        hue = (np.degrees(np.arctan2(lab_s[:, :, 2], lab_s[:, :, 1]))[colourful] + 360.0) % 360.0
        hist = np.bincount((hue // 30).astype(np.int32), minlength=12).astype(np.float64)
        hist = hist + np.roll(hist, 1)
        dominant = float(hist.max()) / float(colourful.size)
        if dominant > 0.35:
            conf *= 0.5
            notes.append("dominant scene colour - correction reduced")
    illum = _from_chroma(combined)
    gains_full = _normalize_gains(1.0 / np.maximum(illum, 1e-3))
    # Never more than ~1.6x on any channel
    gains_full = np.clip(gains_full, 0.62, 1.6)

    skin = _skin_samples(small, faces) if faces else None
    skin_hue_before = _skin_hue(skin, np.ones(3)) if skin is not None else None

    log_g = np.log(gains_full) * conf

    # Skin veto: a correction that pushes in-range skin further from natural is distrusted
    if skin is not None and skin_hue_before is not None:
        hb = skin_hue_before
        ha = _skin_hue(skin, np.exp(log_g))
        dist_b = abs(hb - SKIN_HUE_TARGET)
        dist_a = abs(ha - SKIN_HUE_TARGET)
        if SKIN_HUE_MIN <= hb <= SKIN_HUE_MAX and dist_a > dist_b + 3.0:
            for k in (0.6, 0.35, 0.15, 0.0):
                cand = log_g * k
                if abs(_skin_hue(skin, np.exp(cand)) - SKIN_HUE_TARGET) <= dist_b + 3.0:
                    break
            log_g = cand
            notes.append("background colour ignored (skin veto)")

    # Skin verification / skin-driven correction
    if skin is not None:
        hue_after = _skin_hue(skin, np.exp(log_g))
        if not (SKIN_HUE_MIN <= hue_after <= SKIN_HUE_MAX):
            # Search the blue-yellow / green-magenta plane for gains that put skin in range
            best, best_cost = log_g, abs(hue_after - SKIN_HUE_TARGET)
            for t in np.linspace(-0.35, 0.35, 15):        # temperature axis (log B/R)
                for tn in np.linspace(-0.2, 0.2, 9):      # tint axis (log G)
                    cand = log_g + np.array([-t / 2, tn, t / 2])
                    hue = _skin_hue(skin, np.exp(cand))
                    dist = 0.0 if SKIN_HUE_MIN <= hue <= SKIN_HUE_MAX else min(abs(hue - SKIN_HUE_MIN), abs(hue - SKIN_HUE_MAX))
                    cost = dist * 4.0 + abs(hue - SKIN_HUE_TARGET) * 0.15 + float(np.abs(cand - log_g).sum()) * 6.0
                    if cost < best_cost:
                        best, best_cost = cand, cost
            log_g = best
            notes.append("skin tone verified and corrected")
        else:
            notes.append("skin tone in natural range")

    gains = _normalize_gains(np.exp(log_g))

    # Wedding-friendly strength per cast direction (warm casts partly kept)
    lg = np.log(gains)
    temp_axis = (lg[2] - lg[0]) / 2.0      # >0 means we are cooling a warm cast
    tint_axis = lg[1] - (lg[0] + lg[2]) / 2.0
    scene_median = float(np.median(small.astype(np.float32).mean(axis=2))) / 255.0
    warm_keep = WARM_KEEP_LOW_KEY if scene_median < 0.18 else WARM_KEEP
    temp_k = (1.0 - warm_keep) if temp_axis > 0 else COOL_STRENGTH
    adj = np.array([-temp_axis * temp_k, tint_axis * TINT_STRENGTH * 2.0 / 3.0, temp_axis * temp_k])
    adj[0] -= tint_axis * TINT_STRENGTH / 3.0
    adj[2] -= tint_axis * TINT_STRENGTH / 3.0
    gains = _normalize_gains(np.exp(adj))

    skin_hue_after = _skin_hue(skin, gains) if skin is not None else None
    cct = _cct_from_illuminant(illum) if conf > 0.05 else None
    return {
        "enabled": True,
        "strength": 100.0,
        "gains": [round(float(g), 4) for g in gains],
        "cast": _describe(gains),
        "confidence": round(float(conf), 2),
        "kelvin": cct,
        "grey_pixels": n_grey,
        "faces": len(faces) if faces else 0,
        "skin_hue_before": None if skin_hue_before is None else round(skin_hue_before, 1),
        "skin_hue_after": None if skin_hue_after is None else round(skin_hue_after, 1),
        "notes": notes,
    }


def effective_gains(auto_wb: Optional[Dict[str, Any]]) -> Optional[np.ndarray]:
    if not isinstance(auto_wb, dict) or not auto_wb.get("enabled", True):
        return None
    g = auto_wb.get("gains")
    if not isinstance(g, (list, tuple)) or len(g) != 3:
        return None
    k = float(np.clip(float(auto_wb.get("strength", 100.0)), 0.0, 150.0)) / 100.0
    gains = np.exp(np.log(np.clip(np.array(g, np.float64), 0.3, 3.0)) * k)
    gains = _normalize_gains(gains)
    if np.allclose(gains, 1.0, atol=0.004):
        return None
    return gains.astype(np.float32)


def apply_white_balance(img: np.ndarray, gains: np.ndarray) -> np.ndarray:
    """img: float32 RGB 0..255 (sRGB). Gains applied in linear light; returns float32 0..255."""
    lin = srgb_to_linear(np.clip(img, 0, 255) / 255.0).astype(np.float32)
    lin *= gains.reshape(1, 1, 3)
    # Soft roll-off instead of hard clipping in boosted channels
    over = lin > 0.9
    if np.any(over):
        lin[over] = 0.9 + 0.1 * np.tanh((lin[over] - 0.9) / 0.1)
    return (linear_to_srgb(lin) * 255.0).astype(np.float32)
