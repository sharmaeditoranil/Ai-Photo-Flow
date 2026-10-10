"""
AI Skin Retouch engine: runs the full non-destructive retouch on one image.

Order: AI Heal -> AI Mattifier -> Skin Details (smoothing) -> Skin Imperfections -> Skin Tone.
Everything outside the detected people is returned bit-for-bit unchanged, and inside a person
only pixels of the skin mask (heal / matte: face skin domain) are modified.
"""
import hashlib
import json
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.retouch import params as rparams
from backend.retouch.faces import Face, detect_faces
from backend.retouch.heal import Spot, detect_spots, repair_spots
from backend.retouch.imperfections import even_tone, skin_tone
from backend.retouch.mattifier import mattify
from backend.retouch.skin_mask import compute_masks
from backend.retouch.smoothing import smooth_skin

_CACHE_MAX = 8
_cache: "OrderedDict[Tuple, Any]" = OrderedDict()
_cache_lock = threading.Lock()


def _cache_get(key):
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(key, value):
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def _signature(u8: np.ndarray) -> str:
    small = cv2.resize(u8, (48, 48), interpolation=cv2.INTER_AREA)
    return hashlib.sha1(small.tobytes() + str(u8.shape).encode()).hexdigest()


@dataclass
class RetouchResult:
    faces: int = 0
    spots: int = 0
    shine_pct: float = 0.0
    skin_mask: Optional[np.ndarray] = None      # full image size, float32 0..1 (only if requested)
    heal_mask: Optional[np.ndarray] = None
    shine_mask: Optional[np.ndarray] = None
    notes: List[str] = field(default_factory=list)


def _people_bbox(faces: List[Face], W: int, H: int) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = W, H, 0, 0
    for f in faces:
        ox, oy = float(f.origin[0]), float(f.origin[1])
        r = f.iod
        x0 = min(x0, ox - 3.2 * r)
        x1 = max(x1, ox + 3.2 * r)
        y0 = min(y0, oy - 1.9 * r)
        y1 = max(y1, oy + 4.8 * r)
    return int(max(0, x0)), int(max(0, y0)), int(min(W, x1)), int(min(H, y1))


def retouch_image(rgb: np.ndarray, retouch: Optional[Dict[str, Any]], want_masks: bool = False) -> Tuple[np.ndarray, RetouchResult]:
    """rgb: HxWx3 uint8 or float32 (0..255). Returns float32 RGB (0..255) and a result summary."""
    res = RetouchResult()
    out = rgb.astype(np.float32) if rgb.dtype != np.float32 else rgb.copy()
    if not retouch:
        return out, res
    p = rparams.sanitize(retouch)
    if not p.get("enabled", True):
        return out, res

    u8 = rgb if rgb.dtype == np.uint8 else np.clip(rgb, 0, 255).astype(np.uint8)
    H, W = u8.shape[:2]
    sig = _signature(u8)

    faces = _cache_get(("faces", sig))
    if faces is None:
        faces = detect_faces(u8)
        _cache_put(("faces", sig), faces)
    res.faces = len(faces)
    if not faces:
        res.notes.append("No face detected - skin retouch skipped")
        return out, res

    if p["skinMask"].get("restrictToBody", True):
        x0, y0, x1, y1 = _people_bbox(faces, W, H)
    else:
        x0, y0, x1, y1 = 0, 0, W, H
    if x1 - x0 < 16 or y1 - y0 < 16:
        return out, res
    cfaces = [f.scaled(1.0, -x0, -y0) for f in faces]

    crop = out[y0:y1, x0:x1] / 255.0
    lab = cv2.cvtColor(crop, cv2.COLOR_RGB2LAB)

    mask_key = ("masks", sig, x0, y0, x1, y1, json.dumps(p["skinMask"], sort_keys=True))
    masks = _cache_get(mask_key)
    if masks is None:
        masks = compute_masks(crop, lab, cfaces, p["skinMask"])
        _cache_put(mask_key, masks)

    heal_alpha = None
    h = p["heal"]
    if h.get("enabled", True) and h.get("opacity", 0) > 0:
        spot_key = ("spots", sig, x0, y0, x1, y1, round(h.get("strength", 60)), str(h.get("faceSizePreset", "AUTO")), mask_key[-1])
        spots: Optional[List[Spot]] = _cache_get(spot_key)
        if spots is None:
            spots = detect_spots(lab, masks.domain, cfaces, float(h.get("strength", 60)), str(h.get("faceSizePreset", "AUTO")))
            _cache_put(spot_key, spots)
        res.spots = len(spots)
        if spots:
            heal_alpha = repair_spots(lab, masks.domain, spots, opacity=float(h.get("opacity", 100)) / 100.0)

    shine = None
    mt = p["mattifier"]
    if mt.get("enabled", True):
        shine = mattify(lab, masks.domain, cfaces, float(mt.get("strength", 0)), float(mt.get("keepSheen", 25)),
                        float(mt.get("texturePreserve", 100)), float(mt.get("opacity", 100)))
        dom_px = float((masks.domain > 0.5).sum())
        if dom_px > 0:
            res.shine_pct = round(100.0 * float((shine > 0.3).sum()) / dom_px, 1)

    sd = p["skinDetails"]
    if sd.get("enabled", True):
        smooth_skin(lab, masks.skin, cfaces, sd)

    im = p["imperfections"]
    if im.get("enabled", True):
        even_tone(lab, masks.skin, cfaces, im)

    st = p["skinTone"]
    if st.get("enabled", True):
        skin_tone(lab, masks.skin, st)

    rgb_new = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    np.clip(rgb_new, 0.0, 1.0, out=rgb_new)
    rgb_new *= 255.0
    # Only pixels the retouch is allowed to touch change; everything else stays exactly original
    touch = masks.skin if heal_alpha is None else np.maximum(masks.skin, heal_alpha)
    if shine is not None:
        touch = np.maximum(touch, shine)
    if not st.get("useSkinMask", True) and st.get("enabled", True):
        touch = np.ones_like(touch)
    region = out[y0:y1, x0:x1]
    t3 = (touch > 0.0005)[:, :, None]
    region[:] = np.where(t3, rgb_new, region)

    if want_masks:
        res.skin_mask = np.zeros((H, W), np.float32)
        res.skin_mask[y0:y1, x0:x1] = masks.skin
        if heal_alpha is not None:
            res.heal_mask = np.zeros((H, W), np.float32)
            res.heal_mask[y0:y1, x0:x1] = heal_alpha
        if shine is not None:
            res.shine_mask = np.zeros((H, W), np.float32)
            res.shine_mask[y0:y1, x0:x1] = shine
    return out, res


def resolve_params(edit_params) -> Optional[Dict[str, Any]]:
    """Retouch block from an EditParameters object (with legacy 'skin_smoothing' fallback)."""
    rt = getattr(edit_params, "retouch", None)
    if isinstance(rt, dict) and rt:
        return rt
    legacy = float(getattr(edit_params, "skin_smoothing", 0.0) or 0.0)
    return rparams.from_legacy_smoothing(legacy)
