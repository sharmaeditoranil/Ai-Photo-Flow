"""
Culling Orchestration Service
Scans wedding folders, generates thumbnails, evaluates quality, detects duplicates, and assigns AI recommendations.
"""
import os
import json
import time
from typing import List, Dict, Any, Callable, Optional
from PIL import Image, ExifTags
import numpy as np

from backend.db.database import get_connection
from backend.services.image_service import load_image, generate_thumbnail, is_raw_format
from backend.core.quality_model import OpenCVQualityModel
from backend.core.face_model import OpenCVFaceModel
from backend.core.duplicate_model import PerceptualDuplicateModel
from backend.core.culling_model import WeddingCullingModel
from backend.core.editing_model import IndianWeddingEditingModel
from backend.core.scene_model import SceneConsistencyEngine
from backend.core.interfaces import DuplicateGroupResult, QualityMetrics, FaceMetrics

SUPPORTED_EXTENSIONS = {
    '.jpg', '.jpeg', '.jpe', '.jfif',
    '.png',
    '.arw', '.srf', '.sr2',
    '.cr2', '.cr3', '.crw',
    '.nef', '.nrw',
    '.dng',
    '.raf',
    '.raw', '.rw2',
    '.orf', '.ori',
    '.pef', '.ptx',
    '.tif', '.tiff',
    '.webp'
}

class CullingService:
    def __init__(self):
        self.quality_model = OpenCVQualityModel()
        self.face_model = OpenCVFaceModel()
        self.duplicate_model = PerceptualDuplicateModel()
        self.culling_model = WeddingCullingModel()
        self.editing_model = IndianWeddingEditingModel()

    @staticmethod
    def extract_exif(filepath: str) -> Dict[str, Any]:
        """Extracts date/time and dimension metadata."""
        meta = {"exif_date": "", "width": 0, "height": 0}
        try:
            with Image.open(filepath) as img:
                meta["width"], meta["height"] = img.size
                exif_data = img.getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                        if tag_name in ("DateTimeOriginal", "DateTime"):
                            meta["exif_date"] = str(value)
                            break
        except Exception:
            pass
        return meta

    def scan_folder(self, folder_path: str, project_name: str) -> Dict[str, Any]:
        """
        Scans all photos in the folder without modifying original files.
        Registers them in SQLite database.
        """
        folder_path = folder_path.strip().strip('"').strip("'")
        folder_path = os.path.expanduser(folder_path)
        folder_path = os.path.normpath(os.path.abspath(folder_path))

        print(f"[Photo Import] Scanning folder: '{folder_path}' for project: '{project_name}'")

        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder path does not exist on disk: {folder_path}")

        conn = get_connection()
        cursor = conn.cursor()

        # Check or create project (case-insensitive path comparison for Windows & macOS compatibility)
        cursor.execute("SELECT id, name, total_photos, status FROM projects WHERE folder_path = ? OR LOWER(folder_path) = LOWER(?)", (folder_path, folder_path))
        existing = cursor.fetchone()

        if existing:
            project_id = existing["id"]
            cursor.execute("UPDATE projects SET name = ?, folder_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_name, folder_path, project_id))
        else:
            cursor.execute("INSERT INTO projects (name, folder_path, status) VALUES (?, ?, 'READY')", (project_name, folder_path))
            project_id = cursor.lastrowid

        # Scan folder recursively for all supported photo formats
        photo_files = []
        scanned_count = 0
        for root, _, files in os.walk(folder_path):
            for file in sorted(files):
                scanned_count += 1
                if file.startswith('.') or file.startswith('~$'):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    full_p = os.path.join(root, file)
                    photo_files.append(full_p)

        print(f"[Photo Import] Found {len(photo_files)} supported photos out of {scanned_count} total scanned files in '{folder_path}'")

        if len(photo_files) == 0:
            conn.close()
            raise ValueError(
                f"No supported wedding photos found in '{folder_path}'. "
                f"Supported formats include: JPG, JPEG, PNG, ARW, CR2, CR3, NEF, DNG, RAF, TIFF, WEBP. "
                f"(Scanned {scanned_count} files in directory)."
            )

        # Insert photos into project with per-item fault tolerance
        inserted_count = 0
        for fpath in photo_files:
            filename = os.path.basename(fpath)
            try:
                file_size = os.path.getsize(fpath)
            except Exception:
                file_size = 0

            file_format = os.path.splitext(filename)[1].upper().replace('.', '')
            meta = self.extract_exif(fpath)

            try:
                cursor.execute("""
                SELECT id FROM photos WHERE project_id = ? AND (file_path = ? OR filename = ?)
                """, (project_id, fpath, filename))
                p_exist = cursor.fetchone()

                if not p_exist:
                    cursor.execute("""
                    INSERT INTO photos (
                        project_id, filename, file_path, file_size, width, height, file_format, exif_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        project_id, filename, fpath, file_size,
                        meta.get("width", 0), meta.get("height", 0), file_format, meta.get("exif_date", "")
                    ))
                    inserted_count += 1
                else:
                    # Refresh file path and size if needed
                    cursor.execute("UPDATE photos SET file_path = ?, file_size = ? WHERE id = ?", (fpath, file_size, p_exist["id"]))
            except Exception as insert_err:
                print(f"[Photo Import Warning] Skipping photo {filename}: {insert_err}")

        # Update total count
        cursor.execute("SELECT COUNT(*) as total FROM photos WHERE project_id = ?", (project_id,))
        total_photos = cursor.fetchone()["total"]
        cursor.execute("UPDATE projects SET total_photos = ? WHERE id = ?", (total_photos, project_id))

        conn.commit()
        conn.close()

        print(f"[Photo Import Success] Project {project_id} ('{project_name}') has {total_photos} photos ({inserted_count} newly added).")

        return {
            "project_id": project_id,
            "project_name": project_name,
            "folder_path": folder_path,
            "total_photos": total_photos,
            "newly_added": inserted_count,
            "status": "Ready for Culling"
        }

    def process_culling(
        self,
        project_id: int,
        progress_callback: Optional[Callable[[int, int, str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
        is_paused: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive AI evaluation on all unscored photos in the project.
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("UPDATE projects SET status = 'CULLING' WHERE id = ?", (project_id,))
        conn.commit()

        cursor.execute("SELECT id, filename, file_path, exif_date FROM photos WHERE project_id = ? ORDER BY id ASC", (project_id,))
        photos = [dict(r) for r in cursor.fetchall()]
        total = len(photos)

        processed_items = []

        # Pass 1: Individual Quality, Blur, Face, and Fingerprint
        for idx, p in enumerate(photos):
            if is_cancelled and is_cancelled():
                break

            while is_paused and is_paused():
                time.sleep(0.5)
                if is_cancelled and is_cancelled():
                    break

            photo_id = p["id"]
            filepath = p["file_path"]
            filename = p["filename"]
            exif_date = p.get("exif_date", "")

            try:
                # 1. Single-pass decode: load image once at 1000px
                cv_img = load_image(filepath, max_dim=1000)

                # 2. Thumbnail generation directly reusing cv_img (zero redundant disk read!)
                thumb_path = generate_thumbnail(filepath, project_id, photo_id, base_rgb=cv_img)

                # 3. Quality & Blur
                quality = self.quality_model.evaluate(cv_img)

                # 4. Face & Eyes
                face = self.face_model.detect(cv_img)

                # 5. Duplicate fingerprint (dHash)
                fp = self.duplicate_model.compute_fingerprint(cv_img)

                # 6. Scene classification
                r_m = float(np.mean(cv_img[:, :, 0]))
                g_m = float(np.mean(cv_img[:, :, 1]))
                b_m = float(np.mean(cv_img[:, :, 2]))
                scene = SceneConsistencyEngine.classify_scene(quality.mean_luminance, r_m, g_m, b_m, idx, total)

                # 7. Initial AI Edit parameters
                edit_params = self.editing_model.calculate_corrections(cv_img, preset_name="Natural Wedding", scene_group=scene)

                processed_items.append({
                    "id": photo_id,
                    "filename": filename,
                    "thumbnail_path": thumb_path,
                    "exif_date": exif_date,
                    "quality": quality,
                    "face": face,
                    "dhash": fp["dhash"],
                    "color_hist": fp.get("color_hist", []),
                    "feature": fp.get("feature", []),
                    "scene": scene,
                    "edit_params": edit_params.to_dict(),
                    "sharpness": quality.sharpness,
                    "quality_score": quality.overall_quality,
                    "blur_detected": quality.blur_detected,
                    "eyes_status": face.eyes_status
                })

            except Exception as e:
                # Fault isolation: Single failed photo will NOT crash the entire batch
                print(f"Error analyzing photo {filename}: {e}")
                processed_items.append({
                    "id": photo_id,
                    "filename": filename,
                    "thumbnail_path": "",
                    "quality": self.quality_model.evaluate(None),
                    "face": self.face_model.detect(None),
                    "dhash": "",
                    "scene": "Mandap & Ceremony",
                    "edit_params": {},
                    "sharpness": 0.0,
                    "quality_score": 0.0,
                    "blur_detected": False,
                    "eyes_status": "NO_FACE"
                })

            if progress_callback:
                pct = ((idx + 1) / total) * 80.0 # First pass takes 80%
                progress_callback(idx + 1, total, f"Analyzing photo: {filename}", round(pct, 1))

        # Pass 2: Duplicate Clustering & Best-Shot Recommendation
        cluster_results = self.duplicate_model.cluster_similar(processed_items)

        # Pass 3: Final Culling Decision and DB Update
        for idx, item in enumerate(processed_items):
            pid = item["id"]
            q = item["quality"]
            f = item["face"]

            dup_info = None
            if pid in cluster_results:
                c_res = cluster_results[pid]
                dup_info = DuplicateGroupResult(
                    group_id=c_res["group_id"],
                    is_burst=True,
                    similarity_score=c_res["similarity_score"],
                    is_recommended_best=c_res["is_recommended_best"]
                )

            recommendation, confidence = self.culling_model.cull_photo(q, f, dup_info)

            # Update DB record
            cursor.execute("""
            UPDATE photos SET
                thumbnail_path = ?,
                ai_score = ?,
                sharpness_score = ?,
                blur_detected = ?,
                faces_count = ?,
                eyes_status = ?,
                exposure_status = ?,
                exposure_score = ?,
                duplicate_group_id = ?,
                ai_recommendation = ?,
                ai_confidence = ?,
                scene_category = ?,
                edit_params = ?,
                dhash = ?
            WHERE id = ?
            """, (
                item["thumbnail_path"],
                q.overall_quality,
                q.sharpness,
                1 if q.blur_detected else 0,
                f.faces_count,
                f.eyes_status,
                q.exposure_status,
                q.exposure_score,
                dup_info.group_id if dup_info else None,
                recommendation,
                confidence,
                item["scene"],
                json.dumps(item["edit_params"]),
                item["dhash"],
                pid
            ))

        cursor.execute("UPDATE projects SET status = 'CULLED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        conn.commit()
        conn.close()

        if progress_callback:
            progress_callback(total, total, "AI Culling Complete", 100.0)

        return {
            "status": "COMPLETED",
            "total_processed": len(processed_items),
            "project_id": project_id
        }

    def recluster_project(self, project_id: int) -> Dict[str, Any]:
        """
        Instantly re-evaluates duplicate/burst groups and updates AI recommendations
        using the new high-precision ZNCC algorithm from existing thumbnails/database records.
        """
        import cv2
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM photos WHERE project_id = ? ORDER BY id ASC", (project_id,))
        photos = [dict(r) for r in cursor.fetchall()]
        if not photos:
            conn.close()
            return {"status": "SUCCESS", "message": "No photos in project"}

        items = []
        for p in photos:
            thumb = p.get("thumbnail_path")
            img = None
            if thumb and os.path.exists(thumb):
                img = cv2.imread(thumb)
            if img is None and os.path.exists(p.get("file_path", "")):
                img = cv2.imread(p["file_path"])

            fp = self.duplicate_model.compute_fingerprint(img)

            q = QualityMetrics(
                sharpness=p.get("sharpness_score", 0.0),
                blur_detected=bool(p.get("blur_detected", 0)),
                mean_luminance=128.0,
                shadow_clipping=0.0,
                highlight_clipping=0.0,
                exposure_status=p.get("exposure_status", "GOOD"),
                exposure_score=p.get("exposure_score", 100.0),
                dynamic_range_score=80.0,
                overall_quality=p.get("ai_score", 0.0)
            )

            f = FaceMetrics(
                faces_count=p.get("faces_count", 0),
                eyes_status=p.get("eyes_status", "NO_FACE"),
                face_sharpness=p.get("sharpness_score", 0.0),
                bounding_boxes=[],
                eyes_open_confidence=1.0
            )

            items.append({
                "id": p["id"],
                "filename": p["filename"],
                "exif_date": p.get("exif_date", ""),
                "quality": q,
                "face": f,
                "dhash": fp["dhash"],
                "color_hist": fp["color_hist"],
                "feature": fp["feature"],
                "sharpness": q.sharpness,
                "quality_score": q.overall_quality,
                "blur_detected": q.blur_detected,
                "eyes_status": f.eyes_status
            })

        cluster_results = self.duplicate_model.cluster_similar(items)

        for item in items:
            pid = item["id"]
            q = item["quality"]
            f = item["face"]

            dup_info = None
            if pid in cluster_results:
                c_res = cluster_results[pid]
                dup_info = DuplicateGroupResult(
                    group_id=c_res["group_id"],
                    is_burst=True,
                    similarity_score=c_res["similarity_score"],
                    is_recommended_best=c_res["is_recommended_best"]
                )

            recommendation, confidence = self.culling_model.cull_photo(q, f, dup_info)

            cursor.execute("""
            UPDATE photos SET
                duplicate_group_id = ?,
                ai_recommendation = ?,
                ai_confidence = ?
            WHERE id = ?
            """, (
                dup_info.group_id if dup_info else None,
                recommendation,
                confidence,
                pid
            ))

        conn.commit()
        conn.close()

        return {
            "status": "SUCCESS",
            "project_id": project_id,
            "total_photos": len(photos),
            "clusters_count": len(set(c_res["group_id"] for c_res in cluster_results.values()))
        }

