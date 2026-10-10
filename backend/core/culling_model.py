"""
Culling Decision Engine
Determines AI Recommendations (BEST, REVIEW, REJECT, SIMILAR) and confidence scores.

Owner's rules:
1. AI Best: every good photo, plus the single best photo of each similar (burst) group.
2. Review: any photo the AI is NOT sure about (borderline focus, possible blink, difficult exposure).
3. Reject: clearly bad photos only (out of focus / motion blur, unrecoverable black or white frames).
4. Similar: when the same moment was shot several times (e.g. 5 frames), all alternates stay in Similar
   and only the best one of the group goes to AI Best.
5. Candid emotion / close-ups with closed eyes (laughing, vidai tears, prayer) are good photos -> AI Best.

Focus is judged like a photographer does: on the MAIN FACE when there is one (blurred backgrounds /
bokeh are fine), on the whole frame only for photos without people (decor, venue, details).
"""
from typing import Tuple, Optional
from backend.core.interfaces import CullingModel, QualityMetrics, FaceMetrics, DuplicateGroupResult

# Main-face sharpness (0-100, see face_model). Measured on real + blurred + bokeh test photos:
# sharp faces 50-100, out-of-focus / motion-blurred faces 15-37.
FACE_SHARP_OK = 48.0
FACE_BLUR_DEFINITE = 38.0
# Same faces cropped from the full-resolution file and judged at album / screen size (face_model
# re-blur focus, independent of skin texture; 2nd-best face in groups). Measured on 101 real 24 MP
# wedding photos: 37-81 (all good, incl. smooth-skinned faces only slightly soft at 100%); Gaussian
# blur sigma 3 px 22-55, sigma 6-7 px <= 33; 41 px motion blur 25-36.
FACE_HIRES_OK = 36.0
FACE_HIRES_BLUR = 30.0
# Photos without faces (rings, mehndi, decor, venue): sharpest-area focus (quality_model.focus_sharpness).
# Measured: sharp details 51-100, macro with blurred background 44-98, out-of-focus details 16-32.
DETAIL_SHARP_OK = 42.0
DETAIL_BLUR_DEFINITE = 34.0


class WeddingCullingModel(CullingModel):
    def cull_photo(
        self,
        quality: QualityMetrics,
        face: FaceMetrics,
        duplicate_info: Optional[DuplicateGroupResult] = None
    ) -> Tuple[str, float]:
        """Returns (recommendation, confidence). Categories: 'BEST', 'REVIEW', 'REJECT', 'SIMILAR'."""
        has_face = face.faces_count > 0
        is_close_up = bool(getattr(face, "is_close_up", False))
        has_emotion = bool(getattr(face, "has_emotion", False))

        # ------------------------------------------------------------------ focus
        if has_face:
            subject_sharp = float(face.face_sharpness)
            hires = float(getattr(face, "face_sharpness_hires", -1.0))
            if hires >= 0:
                # The full-resolution face check is the stronger evidence; the 1000 px score only
                # decides together with it. A photo is unsure only when the two disagree.
                focus_ok = hires >= FACE_HIRES_OK and subject_sharp >= FACE_BLUR_DEFINITE
                focus_bad = hires < FACE_HIRES_BLUR or (hires < FACE_HIRES_OK and subject_sharp < FACE_BLUR_DEFINITE)
            else:
                focus_ok = subject_sharp >= FACE_SHARP_OK
                focus_bad = subject_sharp < FACE_BLUR_DEFINITE
        else:
            # Detail / decor / macro close-ups: judge the sharpest area, not the (blurred) background
            focus_area = float(getattr(quality, "focus_sharpness", -1.0))
            subject_sharp = max(float(quality.sharpness), focus_area)
            focus_ok = subject_sharp >= DETAIL_SHARP_OK
            focus_bad = subject_sharp < DETAIL_BLUR_DEFINITE
        focus_borderline = not focus_ok and not focus_bad

        # ------------------------------------------------------------------ exposure
        # Only frames that are really black / really white are unusable. Dark halls, night shots and
        # dark-background detail shots are normal in weddings.
        face_luma = float(getattr(face, "face_brightness", -1.0) or -1.0)
        if has_face and face_luma >= 0:
            pitch_dark = face_luma < 18.0 and quality.mean_luminance < 30.0
            blown_white = face_luma > 250.0 and quality.mean_luminance > 235.0
            exposure_doubtful = face_luma < 45.0 or face_luma > 238.0
        else:
            pitch_dark = quality.exposure_status == "UNDER_EXPOSED" and quality.mean_luminance < 22.0
            blown_white = quality.exposure_status == "OVER_EXPOSED" and quality.mean_luminance > 238.0
            exposure_doubtful = (quality.exposure_status == "UNDER_EXPOSED" and quality.mean_luminance < 40.0) or \
                                (quality.exposure_status == "OVER_EXPOSED" and quality.mean_luminance > 220.0)
        ruined = False

        # ------------------------------------------------------------------ 3. REJECT: clearly bad
        if focus_bad or pitch_dark or blown_white or ruined:
            very_blurred = focus_bad and (subject_sharp < FACE_BLUR_DEFINITE - 8.0 or
                                          (has_face and 0 <= float(getattr(face, "face_sharpness_hires", -1.0)) < FACE_HIRES_BLUR - 5.0))
            return "REJECT", 95.0 if very_blurred else 88.0

        # ------------------------------------------------------------------ 4. SIMILAR: burst alternates
        if duplicate_info and duplicate_info.group_id and not duplicate_info.is_recommended_best:
            return "SIMILAR", 92.0

        # ------------------------------------------------------------------ 1. group winner -> AI Best
        if duplicate_info and duplicate_info.group_id and duplicate_info.is_recommended_best:
            if focus_borderline:
                return "REVIEW", 74.0      # best of the burst, but even this frame may be soft
            return "BEST", 96.0

        # ------------------------------------------------------------------ 2. REVIEW: AI not sure
        if focus_borderline:
            return "REVIEW", 70.0
        candid = has_emotion or is_close_up
        if has_face and face.eyes_status == "CLOSED" and not candid:
            return "REVIEW", 72.0          # could be a blink, could be a prayer moment: photographer decides
        if exposure_doubtful:
            return "REVIEW", 68.0          # recoverable in edit, but worth a look

        # ------------------------------------------------------------------ 1. AI Best: good photos
        confidence = 90.0
        if focus_ok and quality.exposure_status == "GOOD":
            confidence = 95.0
        return "BEST", confidence
