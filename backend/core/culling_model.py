"""
Culling Decision Engine
Determines AI Recommendations (BEST, SELECTED, REVIEW, REJECT, SIMILAR) and confidence scores.

Strict Rules Followed:
1. AI Best: Contains all good photos + the best 1 photo from each duplicate group.
2. Reject: Contains blur photos, dark (under-exposed) photos, and over-exposed photos.
3. Select photo: Contains the "Best of Best" photos (highest composite quality, tack-sharp focus, perfect exposure).
4. Similar group: When 1 photo has 5 shots, the #1 best photo goes to AI Best, and the remaining 4 stay in Similar.
5. Confusion / Borderline: If there is any doubt or ambiguity about where to place a photo, put it in AI Best!
6. Candid Emotion / Close-ups: Photos with closed eyes due to candid emotion (laughing, crying/vidai, prayer)
   or close-up portraits MUST go to AI Best (never rejected).
"""
from typing import Tuple, Optional
from backend.core.interfaces import CullingModel, QualityMetrics, FaceMetrics, DuplicateGroupResult

class WeddingCullingModel(CullingModel):
    def cull_photo(
        self,
        quality: QualityMetrics,
        face: FaceMetrics,
        duplicate_info: Optional[DuplicateGroupResult] = None
    ) -> Tuple[str, float]:
        """
        Returns (recommendation, confidence)
        Categories: 'BEST', 'SELECTED', 'REVIEW', 'REJECT', 'SIMILAR'
        """
        # =========================================================================
        # Rule 2: REJECT (Definite, Unrecoverable Defects Only)
        # =========================================================================
        # A. Blur / Out of focus:
        # 1. Definite blur detected with low sharpness (< 62.0)
        # 2. Or severely unsharp (< 40.0) regardless of detector
        is_blur = (quality.blur_detected and quality.sharpness < 62.0) or (quality.sharpness < 40.0)

        # B. Pitch Black (Completely unrecoverable dark frame):
        # In wedding photography, dark backgrounds or night lighting are common.
        # DO NOT reject dark photos if subjects/faces are present (Auto-Edit easily fixes them!).
        is_pitch_dark = (quality.exposure_status == "UNDER_EXPOSED" and (
            (face.faces_count == 0 and (quality.exposure_score < 18.0 or quality.overall_quality < 35.0)) or
            (quality.exposure_score < 10.0 and quality.overall_quality < 25.0)
        ))

        # C. Blown Whiteout (Pure washed out frame):
        is_blown_white = (quality.exposure_status == "OVER_EXPOSED" and (
            (face.faces_count == 0 and (quality.exposure_score < 18.0 or quality.overall_quality < 35.0)) or
            (quality.exposure_score < 10.0 and quality.overall_quality < 25.0)
        ))

        # D. Defective overall quality (completely unusable frame):
        is_ruined = (quality.overall_quality < 28.0 and face.faces_count == 0)

        # Protection: If the photo is NOT blurry and has faces with open/candid eyes, protect it!
        is_protected_face = (not is_blur and face.faces_count > 0 and quality.sharpness >= 55.0 and face.eyes_status in ("OPEN", "PARTIAL"))

        if (is_blur or is_pitch_dark or is_blown_white or is_ruined) and not is_protected_face:
            return "REJECT", 95.0

        # =========================================================================
        # Rule 4: Similar Group Alternate Duplicates
        # =========================================================================
        if duplicate_info and duplicate_info.group_id and not duplicate_info.is_recommended_best:
            # Alternate duplicate shot in a burst -> stays in SIMILAR
            return "SIMILAR", 92.0

        # =========================================================================
        # Rule 6: Candid Emotion & Close-ups with Closed Eyes -> AI BEST
        # =========================================================================
        # In candid wedding moments (laughing, vidai tears, prayer, forehead touch),
        # eyes are often closed in emotion, or it is a tight close-up portrait.
        # As long as it is NOT blurry and NOT severely ruined in exposure, put into AI BEST!
        is_close_up = getattr(face, "is_close_up", False)
        has_emotion = getattr(face, "has_emotion", False)

        if (has_emotion or is_close_up) and not quality.blur_detected and quality.sharpness >= 50.0:
            return "BEST", 95.0

        # Even if eyes are marked closed, if face is sharp and exposure is acceptable -> candid emotion -> BEST
        if face.faces_count > 0 and face.eyes_status == "CLOSED" and quality.sharpness >= 55.0 and not quality.blur_detected:
            return "BEST", 92.0

        # =========================================================================
        # Rule 3: Select Photo (Best of Best Photos)
        # =========================================================================
        # The cream-of-the-crop hero photos:
        # High composite score (>= 80), tack-sharp (>= 75), well-balanced exposure, eyes open/scenic
        is_best_of_best = (
            quality.overall_quality >= 80.0 and
            quality.sharpness >= 75.0 and
            not quality.blur_detected and
            quality.exposure_status == "GOOD" and
            face.eyes_status in ("OPEN", "NO_FACE")
        )

        # =========================================================================
        # Rule 1 & Rule 4: Winning photo of a Duplicate Burst Group
        # =========================================================================
        if duplicate_info and duplicate_info.group_id and duplicate_info.is_recommended_best:
            return "BEST", 98.0

        if is_best_of_best:
            return "SELECTED", 96.0

        # =========================================================================
        # Rule 1 & Rule 5: AI Best for All Good Photos and Default on Confusion
        # =========================================================================
        # "AI best me sabhi accha photo... ko add kare."
        # "Agar Kisi Photo me confusion hai ki isko kisme rakhe to AI best me rakhye"
        return "BEST", 90.0
