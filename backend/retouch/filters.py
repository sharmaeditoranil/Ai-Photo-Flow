"""
Low-level image filters shared by the AI Skin Retouch stages.
All functions work on float32 arrays and never allocate float64 full-resolution buffers.
"""
import cv2
import numpy as np


def smoothstep(x, e0, e1):
    t = np.clip((x - e0) / np.maximum(1e-6, (e1 - e0)), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def gaussian(x: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur that downsamples first for large sigmas (keeps cost bounded at 24MP)."""
    if sigma <= 0.3:
        return x.copy()
    if sigma <= 8.0:
        return cv2.GaussianBlur(x, (0, 0), sigmaX=sigma, borderType=cv2.BORDER_REFLECT)
    h, w = x.shape[:2]
    f = sigma / 4.0
    sw, sh = max(1, int(round(w / f))), max(1, int(round(h / f)))
    small = cv2.resize(x, (sw, sh), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigmaX=4.0, borderType=cv2.BORDER_REFLECT)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def masked_gaussian(x: np.ndarray, m: np.ndarray, sigma: float, eps: float = 1e-4) -> np.ndarray:
    """Normalized convolution: blur of x using only pixels where mask m > 0."""
    if x.ndim == 3:
        num = gaussian(x * m[:, :, None], sigma)
        den = gaussian(m, sigma)[:, :, None]
    else:
        num = gaussian(x * m, sigma)
        den = gaussian(m, sigma)
    return num / np.maximum(den, eps)


def _box(x: np.ndarray, r: int) -> np.ndarray:
    k = 2 * r + 1
    return cv2.boxFilter(x, -1, (k, k), normalize=True, borderType=cv2.BORDER_REFLECT)


def guided_filter(guide: np.ndarray, src: np.ndarray, radius: float, eps: float) -> np.ndarray:
    """Edge-aware guided filter (He et al.), with subsampling for large radii."""
    h, w = guide.shape[:2]
    r = max(1, int(round(radius)))
    s = max(1, r // 4)
    if s > 1:
        sw, sh = max(1, w // s), max(1, h // s)
        I = cv2.resize(guide, (sw, sh), interpolation=cv2.INTER_AREA)
        p = cv2.resize(src, (sw, sh), interpolation=cv2.INTER_AREA)
        rs = max(1, int(round(r / s)))
    else:
        I, p, rs = guide, src, r

    mean_I = _box(I, rs)
    mean_p = _box(p, rs)
    var_I = _box(I * I, rs) - mean_I * mean_I
    cov_Ip = _box(I * p, rs) - mean_I * mean_p
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I
    mean_a = _box(a, rs)
    mean_b = _box(b, rs)
    if s > 1:
        mean_a = cv2.resize(mean_a, (w, h), interpolation=cv2.INTER_LINEAR)
        mean_b = cv2.resize(mean_b, (w, h), interpolation=cv2.INTER_LINEAR)
    return mean_a * guide + mean_b


def self_guided(x: np.ndarray, radius: float, eps: float) -> np.ndarray:
    """Edge-preserving smoothing of x guided by itself."""
    return guided_filter(x, x, radius, eps)


def resize_to(x: np.ndarray, w: int, h: int) -> np.ndarray:
    if x.shape[1] == w and x.shape[0] == h:
        return x
    interp = cv2.INTER_AREA if x.shape[1] > w else cv2.INTER_LINEAR
    return cv2.resize(x, (w, h), interpolation=interp)


def robust_std(values: np.ndarray) -> float:
    if values.size < 8:
        return 1.0
    med = np.median(values)
    return float(max(1e-4, 1.4826 * np.median(np.abs(values - med))))
