"""
Ai PhotoFlow - Core AI Model Interfaces
Designed for modularity, pluggability, and future expansion (V2).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class QualityMetrics:
    sharpness: float         # 0 - 100
    blur_detected: bool
    mean_luminance: float    # 0 - 255
    shadow_clipping: float   # % pixels < 10
    highlight_clipping: float # % pixels > 245
    exposure_status: str     # 'GOOD', 'UNDER_EXPOSED', 'OVER_EXPOSED'
    exposure_score: float    # 0 - 100
    dynamic_range_score: float # 0 - 100
    overall_quality: float   # 0 - 100 composite

@dataclass
class FaceMetrics:
    faces_count: int
    eyes_status: str         # 'OPEN', 'CLOSED', 'NO_FACE', 'PARTIAL'
    face_sharpness: float    # 0 - 100
    bounding_boxes: List[Dict[str, int]]
    eyes_open_confidence: float
    is_close_up: bool = False
    has_emotion: bool = False

@dataclass
class DuplicateGroupResult:
    group_id: Optional[str]
    is_burst: bool
    similarity_score: float  # 0 - 100
    is_recommended_best: bool

@dataclass
class EditParameters:
    exposure: float = 0.0      # -3.0 to +3.0 EV
    temperature: float = 0.0   # -100 to +100 (Cool to Warm)
    tint: float = 0.0          # -100 to +100 (Green to Magenta)
    contrast: float = 0.0      # -100 to +100
    highlights: float = 0.0    # -100 to +100
    shadows: float = 0.0       # -100 to +100
    whites: float = 0.0        # -100 to +100
    blacks: float = 0.0        # -100 to +100
    vibrance: float = 5.0      # -100 to +100
    saturation: float = 0.0    # -100 to +100
    sharpness: float = 15.0    # 0 to 100
    noise_reduction: float = 10.0 # 0 to 100
    straighten: float = 0.0    # -15 to +15 degrees
    preset_name: str = "Natural Wedding"
    auto_blemish: float = 0.0  # 0 to 100 (AI blemish/pimple removal)
    skin_smoothing: float = 0.0 # 0 to 100 (SkinFiner-style texture-preserving facial skin smoothing)
    dodge_burn: float = 0.0    # 0 to 100 (Subtle 3D portrait sculpting: soft highlights & contours)
    heal_spots: List[Dict[str, float]] = field(default_factory=list) # [{'x': 0.5, 'y': 0.4, 'radius': 0.015}]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exposure": self.exposure,
            "temperature": self.temperature,
            "tint": self.tint,
            "contrast": self.contrast,
            "highlights": self.highlights,
            "shadows": self.shadows,
            "whites": self.whites,
            "blacks": self.blacks,
            "vibrance": self.vibrance,
            "saturation": self.saturation,
            "sharpness": self.sharpness,
            "noise_reduction": self.noise_reduction,
            "straighten": self.straighten,
            "preset_name": self.preset_name,
            "auto_blemish": self.auto_blemish,
            "skin_smoothing": self.skin_smoothing,
            "dodge_burn": self.dodge_burn,
            "heal_spots": self.heal_spots
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EditParameters':
        return cls(
            exposure=float(data.get("exposure", 0.0)),
            temperature=float(data.get("temperature", 0.0)),
            tint=float(data.get("tint", 0.0)),
            contrast=float(data.get("contrast", 0.0)),
            highlights=float(data.get("highlights", 0.0)),
            shadows=float(data.get("shadows", 0.0)),
            whites=float(data.get("whites", 0.0)),
            blacks=float(data.get("blacks", 0.0)),
            vibrance=float(data.get("vibrance", 5.0)),
            saturation=float(data.get("saturation", 0.0)),
            sharpness=float(data.get("sharpness", 15.0)),
            noise_reduction=float(data.get("noise_reduction", 10.0)),
            straighten=float(data.get("straighten", 0.0)),
            preset_name=str(data.get("preset_name", "Natural Wedding")),
            auto_blemish=float(data.get("auto_blemish", 0.0)),
            skin_smoothing=float(data.get("skin_smoothing", 0.0)),
            dodge_burn=float(data.get("dodge_burn", 0.0)),
            heal_spots=list(data.get("heal_spots", []))
        )

class ImageQualityModel(ABC):
    @abstractmethod
    def evaluate(self, image_np) -> QualityMetrics:
        """Evaluate blur, sharpness, exposure and dynamic range."""
        pass

class FaceModel(ABC):
    @abstractmethod
    def detect(self, image_np) -> FaceMetrics:
        """Detect faces and verify eyes open/closed status."""
        pass

class DuplicateDetectionModel(ABC):
    @abstractmethod
    def compute_fingerprint(self, image_np) -> Dict[str, Any]:
        """Compute perceptual hash and color signature."""
        pass

    @abstractmethod
    def cluster_similar(self, photo_items: List[Dict[str, Any]]) -> Dict[int, str]:
        """Assign duplicate group IDs and recommend best in cluster."""
        pass

class EditingModel(ABC):
    @abstractmethod
    def calculate_corrections(self, image_np, preset_name: str, scene_group: Optional[str] = None) -> EditParameters:
        """Calculate intelligent auto-edit parameters with Indian skin tone protection."""
        pass

class CullingModel(ABC):
    @abstractmethod
    def cull_photo(self, quality: QualityMetrics, face: FaceMetrics, duplicate_info: Optional[DuplicateGroupResult] = None) -> Tuple[str, float]:
        """Determine recommendation ('BEST', 'SELECTED', 'REVIEW', 'REJECT', 'SIMILAR') and confidence."""
        pass

class PhotoshopIntegration(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_status_message(self) -> str:
        pass
