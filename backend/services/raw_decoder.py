"""
Professional RAW development for every camera brand LibRaw supports
(Sony ARW/SRF/SR2, Canon CR3/CR2/CRW, Nikon NEF/NRW, Fujifilm RAF incl. X-Trans, Panasonic RW2,
Olympus/OM ORF, Pentax PEF, Leica RWL/DNG, Samsung SRW, Hasselblad 3FR, Phase One IIQ, phones' DNG ...).

Pipeline:
1. 16-bit LINEAR demosaic (no LibRaw auto-brightness, which brightens every frame differently),
   camera white balance, LibRaw highlight blending, sRGB primaries.
2. Exposure matched to the camera's own embedded JPEG, so the starting point looks like what the
   photographer saw on the camera screen, and a whole series develops consistently.
3. Highlight roll-off on the brightest channel: the RAW's extra headroom above the JPEG clip point is
   compressed smoothly instead of clipped, keeping hue (no pink / cyan blown skies or faces).
4. sRGB gamma, uint8 RGB output for the edit pipeline.
"""
import io
from typing import Optional

import cv2
import numpy as np

RAW_EXTENSIONS = {
    '.arw', '.srf', '.sr2',          # Sony
    '.cr2', '.cr3', '.crw',          # Canon
    '.nef', '.nrw',                  # Nikon
    '.raf',                          # Fujifilm (Bayer + X-Trans)
    '.rw2', '.raw', '.rwl',          # Panasonic / Leica
    '.orf', '.ori',                  # Olympus / OM System
    '.pef', '.ptx',                  # Pentax
    '.srw',                          # Samsung
    '.dng',                          # Adobe DNG (Leica, Ricoh, phones, converted files)
    '.3fr', '.fff',                  # Hasselblad
    '.iiq',                          # Phase One
    '.erf', '.kdc', '.dcr', '.mef', '.mos', '.x3f',
}

_SHOULDER_START = 0.80   # linear level where the highlight roll-off begins


def _srgb_to_linear(v: np.ndarray) -> np.ndarray:
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(v: np.ndarray) -> np.ndarray:
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(np.maximum(v, 0.0), 1.0 / 2.4) - 0.055)


def _luma(lin: np.ndarray) -> np.ndarray:
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


def _camera_preview(raw) -> Optional[np.ndarray]:
    """The camera's embedded JPEG as a small RGB uint8 array (only used for statistics), or None."""
    try:
        import rawpy
        from PIL import Image
        thumb = raw.extract_thumb()
        if thumb.format == rawpy.ThumbFormat.JPEG:
            im = Image.open(io.BytesIO(thumb.data))
            im.draft("RGB", (900, 900))         # fast reduced JPEG decode
            rgb = np.asarray(im.convert("RGB"))
        elif thumb.format == rawpy.ThumbFormat.BITMAP:
            rgb = np.asarray(thumb.data)
        else:
            return None
        if rgb.ndim != 3 or rgb.shape[0] * rgb.shape[1] < 10000:
            return None
        s = min(1.0, 900.0 / max(rgb.shape[:2]))
        if s < 1.0:
            rgb = cv2.resize(rgb, (int(rgb.shape[1] * s), int(rgb.shape[0] * s)), interpolation=cv2.INTER_AREA)
        return rgb
    except Exception:
        return None


def _match_camera_look(out: np.ndarray, preview: np.ndarray) -> np.ndarray:
    """Gives the RAW development the camera's own look (tone curve + colour richness, e.g. Fuji film
    simulation / Nikon Picture Control), learned from its embedded JPEG by quantile matching. Above the
    preview's bright end the RAW's recovered highlight detail is kept instead of the camera's clipping."""
    s = min(1.0, 900.0 / max(out.shape[:2]))
    small = cv2.resize(out, (int(out.shape[1] * s), int(out.shape[0] * s)), interpolation=cv2.INTER_AREA) if s < 1.0 else out
    y_raw = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32)
    y_cam = cv2.cvtColor(preview, cv2.COLOR_RGB2GRAY).astype(np.float32)

    # 1. Tone curve: map RAW luminance quantiles onto the camera's
    qs = np.linspace(0.005, 0.985, 60)
    a = np.quantile(y_raw, qs)
    b = np.quantile(y_cam, qs)
    a = np.maximum.accumulate(a + np.arange(len(a)) * 1e-4)       # strictly increasing for interp
    x = np.arange(256, dtype=np.float32)
    lut = np.interp(x, np.concatenate([[0.0], a, [255.0]]), np.concatenate([[0.0], b, [255.0]]))
    # keep recovered highlights: above the camera's bright end, fade back to the RAW rendering
    hi = float(a[-1])
    w = np.clip((x - hi) / max(255.0 - hi, 1.0), 0.0, 1.0)
    lut = lut * (1.0 - w) + x * w
    lut = np.clip(x + np.clip(lut - x, -45.0, 45.0), 0, 255)       # never a drastic change
    lut = np.maximum.accumulate(lut)

    y_full = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY).astype(np.float32)
    y_new = np.interp(y_full, x, lut).astype(np.float32)
    ratio = (y_new + 1.0) / (y_full + 1.0)
    res = out.astype(np.float32) * ratio[..., None]

    # 2. Colour richness: match the camera's median chroma on mid-tones
    def chroma(img):
        lab = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
        mid = (lab[..., 0] > 40) & (lab[..., 0] < 225)
        if np.sum(mid) < 500:
            return None
        return float(np.median(np.hypot(lab[..., 1][mid] - 128.0, lab[..., 2][mid] - 128.0)))
    res_small = cv2.resize(res, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA) if s < 1.0 else res
    c_raw, c_cam = chroma(res_small), chroma(preview.astype(np.float32))
    res = np.clip(res, 0, 255).astype(np.uint8)
    if c_raw and c_cam and c_raw > 2.0:
        k = float(np.clip(c_cam / c_raw, 0.85, 1.5))
        if abs(k - 1.0) > 0.02:
            lab = cv2.cvtColor(res, cv2.COLOR_RGB2LAB).astype(np.float32)
            lab[..., 1:] = (lab[..., 1:] - 128.0) * k + 128.0
            res = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    return res


def _highlight_rolloff(lin: np.ndarray) -> np.ndarray:
    """Hue-preserving soft shoulder: scales each pixel by f(max)/max so the brightest channel approaches
    1.0 smoothly (C1-continuous at the knee) instead of clipping."""
    k = _SHOULDER_START
    m = lin.max(axis=2)
    over = m > k
    if not np.any(over):
        return lin
    mo = m[over]
    target = k + (1.0 - k) * (1.0 - np.exp(-(mo - k) / (1.0 - k)))
    scale = np.ones_like(m)
    scale[over] = target / np.maximum(mo, 1e-6)
    return lin * scale[..., None]


def decode_raw(filepath: str, max_dim: Optional[int] = None) -> np.ndarray:
    """Develops a RAW file to RGB uint8. max_dim limits the long edge (fast half-size demosaic when possible)."""
    import rawpy

    with rawpy.imread(filepath) as raw:
        full_long = max(raw.sizes.width, raw.sizes.height)
        half = bool(max_dim) and max_dim <= full_long // 2
        params = dict(
            use_camera_wb=True,
            no_auto_bright=True,
            gamma=(1.0, 1.0),
            output_bps=16,
            half_size=half,
            highlight_mode=rawpy.HighlightMode.Blend,
            output_color=rawpy.ColorSpace.sRGB,
        )
        if not half and raw.raw_pattern is not None and raw.raw_pattern.shape == (2, 2):
            params["demosaic_algorithm"] = rawpy.DemosaicAlgorithm.AHD   # Bayer: clean, artefact-free detail
        try:
            rgb16 = raw.postprocess(**params)
        except Exception:
            params.pop("demosaic_algorithm", None)
            rgb16 = raw.postprocess(**params)
        preview = _camera_preview(raw)
        target_srgb = float(np.median(cv2.cvtColor(preview, cv2.COLOR_RGB2GRAY))) / 255.0 if preview is not None else None

    lin = rgb16.astype(np.float32) / 65535.0
    del rgb16
    if max_dim:
        h, w = lin.shape[:2]
        s = min(1.0, max_dim / float(max(h, w)))
        if s < 1.0:
            lin = cv2.resize(lin, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)

    # Exposure: match the camera JPEG's median brightness (what the photographer saw on the camera)
    y = _luma(lin)
    raw_med = float(np.median(y))
    if target_srgb is not None and raw_med > 1e-5:
        target_lin = float(_srgb_to_linear(np.float32(min(max(target_srgb, 0.02), 0.95))))
        gain = target_lin / raw_med
    else:
        # No usable preview: put the 99.5th percentile just under the shoulder
        p995 = float(np.percentile(y, 99.5))
        gain = 0.9 / max(p995, 1e-4)
    gain = float(np.clip(gain, 0.25, 16.0))
    lin *= gain

    lin = _highlight_rolloff(lin)
    np.clip(lin, 0.0, 1.0, out=lin)
    out = np.clip(_linear_to_srgb(lin) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    del lin
    if preview is not None:
        try:
            out = _match_camera_look(out, preview)
        except Exception:
            pass
    return out
