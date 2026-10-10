"""
AI Skin Retouch parameter schema, defaults and built-in presets.
The same JSON block is stored in EditParameters.retouch and read by preview, thumbnail and export,
so every render of a photo produces the same result.
"""
import copy
from typing import Any, Dict, Optional

DEFAULT_RETOUCH: Dict[str, Any] = {
    "enabled": True,
    "preset": "Natural",
    "heal": {
        "enabled": True,
        "opacity": 100,          # 0..100 blend of the heal layer
        "strength": 60,          # 0..100 detection sensitivity (higher = more spots healed)
        "faceSizePreset": "AUTO" # AUTO / SMALL / MEDIUM / LARGE
    },
    "mattifier": {
        "enabled": True,
        "opacity": 100,
        "strength": 55,          # how much of the shine is removed
        "keepSheen": 35,         # % of the original highlight kept for a healthy glow (and bridal highlighter)
        "texturePreserve": 85    # 100 = keep all pore texture inside shine areas
    },
    "skinMask": {
        "auto": True,
        "excludeFeatures": True,
        "restrictToBody": True,
        "tolerance": 30,
        "feather": 50,
        "opacity": 100,
        "colorSamples": {"set": [], "expand": [], "exclude": []}
    },
    "skinDetails": {
        "enabled": True,
        "autoPortraitSize": True,
        "portraitSize": 50,
        "amount": 85,
        "fine": -10,             # -100..100, + = smoother pores, - = keep/boost pores
        "medium": 70,            # small blotches & uneven texture
        "coarse": 25,            # large tonal variations
        "balance": 0             # -100 smooth dark irregularities .. +100 bright ones
    },
    "imperfections": {
        "enabled": True,
        "evenTone": 45,
        "redness": 100,
        "redBrightness": 50,
        "yellow": 60,
        "yellowBrightness": 0,
        "balance": 0,
        "eyeBags": 30
    },
    "skinTone": {
        "enabled": True,
        "useSkinMask": True,
        "hue": 0,
        "saturation": 0,
        "brightness": 0,
        "contrast": 0,
        "shadows": 0,
        "highlights": 0
    }
}

# Overrides applied on top of DEFAULT_RETOUCH
_PRESET_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "Natural": {},
    "Smoothing - Light": {
        "skinDetails": {"amount": 70, "fine": -15, "medium": 45, "coarse": 10},
        "imperfections": {"evenTone": 30, "eyeBags": 20},
        "mattifier": {"strength": 50},
    },
    "Smoothing - Medium": {
        "skinDetails": {"amount": 90, "fine": -5, "medium": 75, "coarse": 30},
        "imperfections": {"evenTone": 50, "eyeBags": 35},
    },
    "Smoothing - High": {
        "skinDetails": {"amount": 100, "fine": 15, "medium": 90, "coarse": 45},
        "imperfections": {"evenTone": 60, "eyeBags": 45},
        "mattifier": {"strength": 75},
    },
    "Smoothing - Men": {
        "skinDetails": {"amount": 80, "fine": -50, "medium": 30, "coarse": -10},
        "imperfections": {"evenTone": 30, "eyeBags": 25},
        "mattifier": {"strength": 70, "keepSheen": 15},
    },
    "Wedding Flash": {
        "heal": {"strength": 65},
        "mattifier": {"strength": 85, "keepSheen": 20},
        "skinDetails": {"amount": 75, "fine": -15, "medium": 55, "coarse": 15},
    },
    "Studio Clean": {
        "heal": {"strength": 70},
        "mattifier": {"strength": 55},
        "skinDetails": {"amount": 90, "fine": -5, "medium": 75, "coarse": 30},
        "imperfections": {"evenTone": 55},
    },
    "Skin Tone - Lightening": {
        "skinTone": {"hue": -15, "brightness": 25, "contrast": 20},
    },
    "Skin Tone - Contrast": {
        "skinTone": {"contrast": 30, "shadows": -10, "highlights": 10},
    },
    "Heal Only": {
        "mattifier": {"enabled": False},
        "skinDetails": {"enabled": False},
        "imperfections": {"enabled": False},
    },
}

PRESET_DESCRIPTIONS: Dict[str, str] = {
    "Natural": "Heal + matte + natural smoothing. Pores stay visible. Recommended for all wedding photos.",
    "Smoothing - Light": "Gentle cleanup, maximum texture kept.",
    "Smoothing - Medium": "Clearly smoother skin for portraits and bridal close-ups.",
    "Smoothing - High": "Strong glamour smoothing for beauty close-ups.",
    "Smoothing - Men": "Keeps beard area and pore texture, removes shine.",
    "Wedding Flash": "Strong flash shine removal on every face + light smoothing.",
    "Studio Clean": "Clean studio skin: heal, matte, medium smoothing, even tone.",
    "Skin Tone - Lightening": "Natural smoothing with brighter, lighter skin tone.",
    "Skin Tone - Contrast": "Natural smoothing with extra skin contrast.",
    "Heal Only": "Removes pimples/spots only, nothing else changes.",
    "Off": "No skin retouch.",
}

PRESET_NAMES = list(_PRESET_OVERRIDES.keys()) + ["Off"]

_RANGES = {
    ("heal", "opacity"): (0, 100), ("heal", "strength"): (0, 100),
    ("mattifier", "opacity"): (0, 100), ("mattifier", "strength"): (0, 100),
    ("mattifier", "keepSheen"): (0, 100), ("mattifier", "texturePreserve"): (0, 100),
    ("skinMask", "tolerance"): (0, 100), ("skinMask", "feather"): (0, 100), ("skinMask", "opacity"): (0, 100),
    ("skinDetails", "portraitSize"): (0, 100), ("skinDetails", "amount"): (0, 100),
    ("imperfections", "evenTone"): (0, 100), ("imperfections", "redness"): (0, 100),
    ("imperfections", "redBrightness"): (0, 100), ("imperfections", "yellow"): (0, 100),
    ("imperfections", "yellowBrightness"): (0, 100), ("imperfections", "eyeBags"): (0, 100),
}


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def build_preset(name: str) -> Optional[Dict[str, Any]]:
    """Returns a full retouch block for a preset name, or a disabled block for 'Off'."""
    if name == "Off":
        off = copy.deepcopy(DEFAULT_RETOUCH)
        off["enabled"] = False
        off["preset"] = "Off"
        return off
    over = _PRESET_OVERRIDES.get(name, {})
    out = _deep_merge(DEFAULT_RETOUCH, over)
    out["preset"] = name if name in _PRESET_OVERRIDES else "Natural"
    return out


def list_presets():
    return [
        {"name": n, "description": PRESET_DESCRIPTIONS.get(n, ""), "params": build_preset(n)}
        for n in PRESET_NAMES
    ]


def sanitize(retouch: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge user/stored params with defaults and clamp every numeric value into range."""
    p = _deep_merge(DEFAULT_RETOUCH, retouch if isinstance(retouch, dict) else {})
    for section, val in p.items():
        if not isinstance(val, dict):
            continue
        for key, v in list(val.items()):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            lo, hi = _RANGES.get((section, key), (-100, 100))
            val[key] = float(min(hi, max(lo, v)))
    p["enabled"] = bool(p.get("enabled", True))
    return p


def from_legacy_smoothing(skin_smoothing: float) -> Optional[Dict[str, Any]]:
    """Older edits stored a single 'skin_smoothing' value; map it onto the Skin Details panel only."""
    if skin_smoothing <= 1.0:
        return None
    p = copy.deepcopy(DEFAULT_RETOUCH)
    p["preset"] = "Legacy"
    p["heal"]["enabled"] = False
    p["mattifier"]["enabled"] = False
    p["imperfections"]["enabled"] = False
    p["skinDetails"]["amount"] = float(min(100.0, skin_smoothing * 2.0))
    return p
