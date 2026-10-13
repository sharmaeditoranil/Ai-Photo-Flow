"""
AI Eye-Blink Fix Service (ग्रुप फोटो में आंखें खोलने वाला टूल)
Detects closed eyes (blinks) in group and burst photography, locates matching open eyes
from duplicate/burst donor photos, and seamlessly aligns & blends them into the target photo.
100% offline, local, and non-destructive.
"""
import os
import json
import cv2
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from backend.db.database import get_connection
from backend.services.image_service import load_image
from backend.retouch.faces import detect_faces, Face

APP_DATA_DIR = os.path.expanduser("~/.photoflow")
EYE_FIX_DIR = os.path.join(APP_DATA_DIR, "eye_fixes")
os.makedirs(EYE_FIX_DIR, exist_ok=True)


def find_eye_donors(photo_id: int) -> Dict[str, Any]:
    """
    Finds potential donor photos with open eyes for the specified photo.
    Prioritizes photos from the same duplicate / burst group (duplicate_group_id).
    Falls back to adjacent photos in the same project within +/- 15 shots.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, project_id, filename, file_path, duplicate_group_id, exif_date, eyes_status, faces_count, created_at
        FROM photos WHERE id = ?
    """, (photo_id,))
    target_row = cursor.fetchone()

    if not target_row:
        conn.close()
        raise ValueError(f"Photo ID {photo_id} not found")

    project_id = target_row["project_id"]
    target_dup = target_row["duplicate_group_id"]
    candidates: List[Dict[str, Any]] = []

    # 1. Search in same duplicate / burst group
    if target_dup:
        cursor.execute("""
            SELECT id, filename, duplicate_group_id, eyes_status, faces_count, ai_score, sharpness_score
            FROM photos
            WHERE project_id = ? AND duplicate_group_id = ? AND id != ?
            ORDER BY (eyes_status = 'OPEN') DESC, ai_score DESC, sharpness_score DESC
        """, (project_id, target_dup, photo_id))
        for r in cursor.fetchall():
            candidates.append({
                "id": r["id"],
                "filename": r["filename"],
                "thumbnail_url": f"/api/photos/{r['id']}/thumbnail",
                "eyes_status": r["eyes_status"],
                "faces_count": r["faces_count"],
                "is_same_burst": True
            })

    # 2. Search adjacent photos in the project if no burst candidates found
    if len(candidates) < 3:
        cursor.execute("""
            SELECT id, filename, duplicate_group_id, eyes_status, faces_count, ai_score, sharpness_score
            FROM photos
            WHERE project_id = ? AND id != ? AND id BETWEEN ? AND ?
            ORDER BY (eyes_status = 'OPEN') DESC, abs(id - ?) ASC
            LIMIT 8
        """, (project_id, photo_id, photo_id - 10, photo_id + 10, photo_id))
        seen_ids = {c["id"] for c in candidates}
        for r in cursor.fetchall():
            if r["id"] not in seen_ids:
                candidates.append({
                    "id": r["id"],
                    "filename": r["filename"],
                    "thumbnail_url": f"/api/photos/{r['id']}/thumbnail",
                    "eyes_status": r["eyes_status"],
                    "faces_count": r["faces_count"],
                    "is_same_burst": False
                })

    conn.close()

    # Pick the best auto donor: same burst + OPEN eyes, or first candidate
    best_id = None
    for c in candidates:
        if c["is_same_burst"] and c["eyes_status"] == "OPEN":
            best_id = c["id"]
            break
    if best_id is None and candidates:
        best_id = candidates[0]["id"]

    return {
        "target_photo_id": photo_id,
        "target_filename": target_row["filename"],
        "target_eyes_status": target_row["eyes_status"],
        "target_faces_count": target_row["faces_count"],
        "auto_best_donor_id": best_id,
        "donors": candidates
    }


def _match_faces(target_faces: List[Face], donor_faces: List[Face],
                 target_shape: Tuple[int, int], donor_shape: Tuple[int, int]) -> List[Tuple[Face, Face]]:
    """
    Matches target faces to donor faces based on spatial proximity in normalized frame coordinates.
    In burst group shots, subjects remain in nearly identical relative positions.
    """
    th, tw = target_shape[:2]
    dh, dw = donor_shape[:2]
    matched = []
    used_donors = set()

    for t in target_faces:
        tcx = (t.box[0] + t.box[2] * 0.5) / float(tw)
        tcy = (t.box[1] + t.box[3] * 0.5) / float(th)

        best_dist = 999.0
        best_donor = None
        best_idx = -1

        for j, d in enumerate(donor_faces):
            if j in used_donors:
                continue
            dcx = (d.box[0] + d.box[2] * 0.5) / float(dw)
            dcy = (d.box[1] + d.box[3] * 0.5) / float(dh)
            dist = float(np.hypot(tcx - dcx, tcy - dcy))
            if dist < best_dist:
                best_dist = dist
                best_donor = d
                best_idx = j

        # Proximity threshold: within 12% of frame diagonal
        if best_dist < 0.12 and best_donor is not None:
            matched.append((t, best_donor))
            used_donors.add(best_idx)

    return matched


def _is_blinking_face(face: Face, gray_img: np.ndarray, eye_cascade: Optional[cv2.CascadeClassifier]) -> bool:
    """Detects if a face has closed or blinking eyes using Haar eye cascade on eye region."""
    if eye_cascade is None:
        return True # Default to swap if uncertain
    x, y, w, h = [int(v) for v in face.box]
    ih, iw = gray_img.shape[:2]
    x, y = max(0, x), max(0, y)
    w = min(w, iw - x)
    h = min(h, ih - y)
    if w <= 0 or h <= 0:
        return True
    roi = gray_img[y:y + int(h * 0.55), x:x + w]
    if roi.size == 0:
        return True
    eyes = eye_cascade.detectMultiScale(roi, scaleFactor=1.1, minNeighbors=3, minSize=(int(w * 0.12), int(h * 0.12)))
    return len(eyes) < 2


def swap_eyes(photo_id: int, donor_photo_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Performs AI Eye-Blink Fix:
    1. Loads target and donor photos.
    2. Detects faces and landmarks in both.
    3. Aligns donor open eyes onto target blinking faces using similarity transform.
    4. Matches color & lighting (Reinhard Lab transfer).
    5. Blends seamlessly with soft feathered orbital mask.
    6. Saves eye-fixed base image and updates DB non-destructively.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, project_id, filename, file_path, edit_params FROM photos WHERE id = ?", (photo_id,))
    target_row = cursor.fetchone()
    if not target_row:
        conn.close()
        raise ValueError(f"Photo {photo_id} not found")

    project_id = target_row["project_id"]

    # Pick donor photo if not supplied
    if donor_photo_id is None:
        donors_info = find_eye_donors(photo_id)
        donor_photo_id = donors_info.get("auto_best_donor_id")
        if not donor_photo_id:
            conn.close()
            raise ValueError("No matching burst or adjacent donor photo found for eye fix")

    cursor.execute("SELECT id, filename, file_path FROM photos WHERE id = ?", (donor_photo_id,))
    donor_row = cursor.fetchone()
    if not donor_row:
        conn.close()
        raise ValueError(f"Donor photo {donor_photo_id} not found")

    # Load images at high resolution (max 2560 for tack-sharp detail)
    target_rgb = load_image(target_row["file_path"], max_dim=2560)
    donor_rgb = load_image(donor_row["file_path"], max_dim=2560)

    target_faces = detect_faces(target_rgb)
    donor_faces = detect_faces(donor_rgb)

    if not target_faces:
        conn.close()
        raise ValueError("No faces detected in target photo")
    if not donor_faces:
        conn.close()
        raise ValueError("No faces detected in donor photo")

    matched_pairs = _match_faces(target_faces, donor_faces, target_rgb.shape, donor_rgb.shape)
    if not matched_pairs:
        conn.close()
        raise ValueError("Could not match any faces between target and donor photo")

    # Eye cascade classifier
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_eye.xml"
        eye_cascade = cv2.CascadeClassifier(cascade_path)
    except Exception:
        eye_cascade = None

    target_gray = cv2.cvtColor(target_rgb, cv2.COLOR_RGB2GRAY)
    h, w = target_rgb.shape[:2]
    fixed_rgb = target_rgb.copy().astype(np.float32)
    fixed_count = 0

    for target_f, donor_f in matched_pairs:
        # Check if target is blinking (or swap all matched faces if user triggered fix)
        is_blink = _is_blinking_face(target_f, target_gray, eye_cascade)
        if not is_blink and len(matched_pairs) > 1:
            # Person already has wide-open eyes; don't alter unnecessarily
            continue

        # Extract landmarks (left eye, right eye, nose)
        src_pts = donor_f.landmarks[:3].astype(np.float32)
        dst_pts = target_f.landmarks[:3].astype(np.float32)

        # Estimate partial affine similarity matrix (rotation + uniform scale + translation)
        M, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        if M is None:
            continue

        # Warp donor image to target geometry
        warped_donor = cv2.warpAffine(donor_rgb, M, (w, h), flags=cv2.INTER_LINEAR)

        # Create soft elliptical mask for both eye sockets
        iod = target_f.iod
        mask = np.zeros((h, w), dtype=np.float32)
        ax = max(4, int(round(iod * 0.25)))
        ay = max(3, int(round(iod * 0.16)))

        for eye_pt in [target_f.landmarks[0], target_f.landmarks[1]]:
            ex, ey = int(round(eye_pt[0])), int(round(eye_pt[1]))
            cv2.ellipse(mask, (ex, ey), (ax, ay), target_f.angle_deg, 0, 360, 1.0, -1)

        blur_k = max(3, int(round(iod * 0.12))) | 1
        feathered_mask = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)[:, :, np.newaxis]

        # Reinhard color and lighting transfer in Lab space on the eye socket zone
        skin_zone = (feathered_mask[:, :, 0] > 0.05)
        if np.sum(skin_zone) < 20:
            continue

        lab_target = cv2.cvtColor(fixed_rgb.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
        lab_warped = cv2.cvtColor(warped_donor, cv2.COLOR_RGB2LAB).astype(np.float32)

        mu_tgt = np.mean(lab_target[skin_zone], axis=0)
        std_tgt = np.std(lab_target[skin_zone], axis=0) + 1e-4

        mu_d = np.mean(lab_warped[skin_zone], axis=0)
        std_d = np.std(lab_warped[skin_zone], axis=0) + 1e-4

        lab_matched = (lab_warped - mu_d) / std_d * std_tgt + mu_tgt
        rgb_matched = cv2.cvtColor(np.clip(lab_matched, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)

        # Seamless feathered composite
        fixed_rgb = fixed_rgb * (1.0 - feathered_mask) + rgb_matched * feathered_mask
        fixed_count += 1

    if fixed_count == 0:
        # Fallback: force swap on the primary face
        target_f, donor_f = matched_pairs[0]
        src_pts = donor_f.landmarks[:3].astype(np.float32)
        dst_pts = target_f.landmarks[:3].astype(np.float32)
        M, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        if M is not None:
            warped_donor = cv2.warpAffine(donor_rgb, M, (w, h), flags=cv2.INTER_LINEAR)
            iod = target_f.iod
            mask = np.zeros((h, w), dtype=np.float32)
            ax = max(4, int(round(iod * 0.25)))
            ay = max(3, int(round(iod * 0.16)))
            for eye_pt in [target_f.landmarks[0], target_f.landmarks[1]]:
                ex, ey = int(round(eye_pt[0])), int(round(eye_pt[1]))
                cv2.ellipse(mask, (ex, ey), (ax, ay), target_f.angle_deg, 0, 360, 1.0, -1)
            blur_k = max(3, int(round(iod * 0.12))) | 1
            feathered_mask = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)[:, :, np.newaxis]

            skin_zone = (feathered_mask[:, :, 0] > 0.05)
            lab_target = cv2.cvtColor(fixed_rgb.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
            lab_warped = cv2.cvtColor(warped_donor, cv2.COLOR_RGB2LAB).astype(np.float32)
            mu_tgt = np.mean(lab_target[skin_zone], axis=0)
            std_tgt = np.std(lab_target[skin_zone], axis=0) + 1e-4
            mu_d = np.mean(lab_warped[skin_zone], axis=0)
            std_d = np.std(lab_warped[skin_zone], axis=0) + 1e-4
            lab_matched = (lab_warped - mu_d) / std_d * std_tgt + mu_tgt
            rgb_matched = cv2.cvtColor(np.clip(lab_matched, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)
            fixed_rgb = fixed_rgb * (1.0 - feathered_mask) + rgb_matched * feathered_mask
            fixed_count = 1

    # Save fixed base image to ~/.photoflow/eye_fixes/
    fixed_path = os.path.join(EYE_FIX_DIR, f"photo_{photo_id}_eyefix.jpg")
    cv2.imwrite(fixed_path, cv2.cvtColor(np.clip(fixed_rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 96])

    # Update database edit_params and eyes_status
    params_dict = json.loads(target_row["edit_params"]) if target_row["edit_params"] else {}
    params_dict["eye_fix_path"] = fixed_path
    params_dict["eye_donor_id"] = donor_photo_id
    params_json = json.dumps(params_dict)

    cursor.execute("""
        UPDATE photos
        SET edit_params = ?, eyes_status = 'OPEN', is_edited = 1
        WHERE id = ?
    """, (params_json, photo_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "fixed_faces": fixed_count,
        "donor_id": donor_photo_id,
        "donor_filename": donor_row["filename"],
        "eye_fix_path": fixed_path,
        "message": f"Successfully fixed closed eyes on {fixed_count} face(s) using {donor_row['filename']}"
    }


def revert_eyes(photo_id: int) -> Dict[str, Any]:
    """Reverts AI Eye-Blink Fix and restores the original untouched photo eyes."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT edit_params FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Photo {photo_id} not found")

    params_dict = json.loads(row["edit_params"]) if row["edit_params"] else {}
    fixed_path = params_dict.pop("eye_fix_path", None)
    params_dict.pop("eye_donor_id", None)

    if fixed_path and os.path.exists(fixed_path):
        try:
            os.remove(fixed_path)
        except Exception:
            pass

    cursor.execute("""
        UPDATE photos
        SET edit_params = ?, eyes_status = 'PARTIAL'
        WHERE id = ?
    """, (json.dumps(params_dict), photo_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "AI Eye Fix successfully reverted to original photo"
    }
