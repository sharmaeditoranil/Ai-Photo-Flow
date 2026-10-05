"""
Wedding Scene Consistency Engine
Groups photos by capture timeline & lighting condition, harmonizing white balance and exposure.
"""
import numpy as np
from typing import List, Dict, Any, Optional

class SceneConsistencyEngine:
    SCENE_NAMES = [
        "Bride Makeup",
        "Groom Preparation",
        "Mandap & Ceremony",
        "Stage & Couple Portraits",
        "Outdoor Portraits",
        "Reception & Sangeet"
    ]

    @staticmethod
    def classify_scene(mean_lum: float, r_mean: float, g_mean: float, b_mean: float, index: int, total: int) -> str:
        """
        Classifies scene based on chromaticity, warmth, luminance, and temporal sequence.
        """
        warmth = r_mean - b_mean

        # Stage / Reception: dramatic high contrast, dynamic lighting
        if mean_lum < 85:
            return "Reception & Sangeet"

        # Mandap: heavy warm gold/red cast from sacred fire & yellow/red marigold floral
        if warmth > 25:
            return "Mandap & Ceremony"

        # Outdoor: balanced sunlight, higher blue/green or daylight luminance
        if mean_lum > 145 and b_mean > 120:
            return "Outdoor Portraits"

        # Makeup & Groom: typically early in the sequence, controlled indoor lighting
        seq_ratio = index / max(1, total)
        if seq_ratio < 0.25:
            return "Bride Makeup" if warmth > 10 else "Groom Preparation"

        if seq_ratio > 0.70:
            return "Stage & Couple Portraits"

        return "Mandap & Ceremony"

    @classmethod
    def harmonize_scene_parameters(cls, photos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Harmonizes temperature and exposure across photos in the same scene group.
        Prevents jarring WB fluctuations between consecutive shots under the same lights.
        """
        # Group by scene
        by_scene: Dict[str, List[Dict[str, Any]]] = {}
        for p in photos:
            scene = p.get("scene_category", "Mandap & Ceremony")
            by_scene.setdefault(scene, []).append(p)

        harmonized_photos = []

        for scene, items in by_scene.items():
            if len(items) <= 1:
                harmonized_photos.extend(items)
                continue

            # Compute median temperature and exposure offsets across the scene
            temps = [it.get("edit_params", {}).get("temperature", 0.0) for it in items if "edit_params" in it]
            tints = [it.get("edit_params", {}).get("tint", 0.0) for it in items if "edit_params" in it]

            med_temp = float(np.median(temps)) if temps else 0.0
            med_tint = float(np.median(tints)) if tints else 0.0

            for it in items:
                params = it.get("edit_params")
                if params and not it.get("manual_override", False):
                    # Blend 35% towards scene median to maintain consistency while respecting individual needs
                    curr_temp = params.get("temperature", 0.0)
                    curr_tint = params.get("tint", 0.0)
                    params["temperature"] = round(curr_temp * 0.65 + med_temp * 0.35, 1)
                    params["tint"] = round(curr_tint * 0.65 + med_tint * 0.35, 1)
                harmonized_photos.append(it)

        return harmonized_photos
