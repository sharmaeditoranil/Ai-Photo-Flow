"""
Client Proofing & Selection Service
Generates download-protected, watermarked web previews, manages client galleries,
syncs selections, and exports customer-selected master RAW/JPG files into album folders.
"""
import os
import shutil
import uuid
import json
import time
import threading
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

from backend.db.database import get_connection
from backend.services.batch_service import BatchManager
from backend.services.image_service import (
    CACHE_DIR,
    load_image,
    generate_thumbnail,
    apply_edit_pipeline,
    is_raw_format
)
from backend.core.interfaces import EditParameters

PROOFING_CACHE_DIR = os.path.join(CACHE_DIR, "galleries")
os.makedirs(PROOFING_CACHE_DIR, exist_ok=True)


class ProofingService:
    @staticmethod
    def _apply_watermark(pil_img: Image.Image, watermark_text: str) -> Image.Image:
        """Applies anti-theft semi-transparent watermark and security notice overlay."""
        overlay = Image.new("RGBA", pil_img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        w, h = pil_img.size
        font_size = max(24, int(w * 0.045))
        try:
            # Try system fonts on macOS / Windows
            font = ImageFont.truetype("arial.ttf", font_size) if os.name == 'nt' else ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("Arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        # Center Main Watermark with subtle dark drop shadow
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        cx = (w - text_w) // 2
        cy = (h - text_h) // 2

        draw.text((cx + 2, cy + 2), watermark_text, fill=(0, 0, 0, 95), font=font)
        draw.text((cx, cy), watermark_text, fill=(255, 255, 255, 130), font=font)

        # Bottom Anti-Download Security Notice
        sub_text = "Ai PhotoFlow Proofing • Selection Preview Only • Download Protected"
        sub_size = max(13, int(w * 0.022))
        try:
            sub_font = ImageFont.truetype("arial.ttf", sub_size) if os.name == 'nt' else ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", sub_size)
        except Exception:
            sub_font = ImageFont.load_default()

        s_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        s_w = s_bbox[2] - s_bbox[0]
        # Semi-transparent bar at bottom
        draw.rectangle([(0, h - 38), (w, h)], fill=(0, 0, 0, 110))
        draw.text(((w - s_w) // 2, h - 28), sub_text, fill=(241, 245, 249, 210), font=sub_font)

        base = pil_img.convert("RGBA")
        combined = Image.alpha_composite(base, overlay)
        return combined.convert("RGB")

    def create_gallery(
        self,
        project_id: int,
        title: str,
        client_name: str = "",
        client_pin: str = "",
        photo_ids: Optional[List[int]] = None,
        watermark_enabled: bool = True,
        watermark_text: str = "PROOF ONLY - Ai PhotoFlow"
    ) -> Dict[str, Any]:
        """
        Creates a client proofing gallery, generates download-protected 1200px previews,
        and saves gallery records.
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Verify project
        cursor.execute("SELECT id, name, folder_path FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        if not project:
            conn.close()
            raise ValueError(f"Project {project_id} not found.")

        # Query photos to include
        if photo_ids and len(photo_ids) > 0:
            placeholders = ",".join(["?"] * len(photo_ids))
            query = f"SELECT * FROM photos WHERE project_id = ? AND id IN ({placeholders}) ORDER BY id ASC"
            cursor.execute(query, [project_id] + photo_ids)
        else:
            # By default include AI Best or Selected or All
            cursor.execute("""
            SELECT * FROM photos
            WHERE project_id = ? AND (user_selection != 'REJECT' AND ai_recommendation != 'REJECT')
            ORDER BY id ASC
            """, (project_id,))

        photos = [dict(r) for r in cursor.fetchall()]
        if not photos:
            # Fallback to all photos in project if everything was unrated
            cursor.execute("SELECT * FROM photos WHERE project_id = ? ORDER BY id ASC", (project_id,))
            photos = [dict(r) for r in cursor.fetchall()]

        if not photos:
            conn.close()
            raise ValueError("No photos found in project to generate client gallery.")

        gallery_uuid = uuid.uuid4().hex[:12]
        gallery_dir = os.path.join(PROOFING_CACHE_DIR, gallery_uuid)
        os.makedirs(gallery_dir, exist_ok=True)

        # Insert Gallery record immediately
        cursor.execute("""
        INSERT INTO client_galleries (
            project_id, gallery_uuid, title, client_name, client_pin,
            total_photos, selected_count, status, watermark_enabled, watermark_text
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 'ACTIVE', ?, ?)
        """, (
            project_id, gallery_uuid, title, client_name, client_pin,
            len(photos), 1 if watermark_enabled else 0, watermark_text
        ))

        # Insert photo mappings immediately
        for p in photos:
            cursor.execute("""
            INSERT OR REPLACE INTO client_gallery_photos (gallery_uuid, photo_id, client_selection, client_note)
            VALUES (?, ?, 'UNRATED', '')
            """, (gallery_uuid, p["id"]))

        conn.commit()
        conn.close()

        # Create Background Batch Job for real-time progress bar tracking
        total = len(photos)
        job_id = BatchManager().create_job(project_id, "PROOFING_PREVIEW", total)

        # Launch background preview generation thread
        threading.Thread(
            target=self._run_preview_generation,
            args=(job_id, gallery_uuid, gallery_dir, photos, watermark_enabled, watermark_text),
            daemon=True
        ).start()

        return {
            "gallery_uuid": gallery_uuid,
            "job_id": job_id,
            "project_id": project_id,
            "title": title,
            "client_name": client_name,
            "total_photos": len(photos),
            "share_url": f"http://127.0.0.1:8000/gallery/{gallery_uuid}",
            "status": "PROCESSING"
        }

    def _generate_single_preview(
        self,
        gallery_dir: str,
        photo_dict: Dict[str, Any],
        watermark_enabled: bool = True,
        watermark_text: str = "PROOF ONLY - Ai PhotoFlow"
    ) -> str:
        """Generates a single 1200px WebP preview with watermark if enabled."""
        photo_id = photo_dict["id"]
        preview_filename = f"{photo_id}.webp"
        preview_path = os.path.join(gallery_dir, preview_filename)
        if os.path.exists(preview_path):
            return preview_path

        try:
            raw_rgb = load_image(photo_dict["file_path"], max_dim=1200)

            # Apply edits if photo was edited
            if photo_dict.get("is_edited") == 1 and photo_dict.get("edit_params"):
                try:
                    params = EditParameters.from_dict(json.loads(photo_dict["edit_params"]))
                    raw_rgb = apply_edit_pipeline(raw_rgb, params)
                except Exception:
                    pass

            pil_img = Image.fromarray(raw_rgb)
            if watermark_enabled:
                pil_img = self._apply_watermark(pil_img, watermark_text)

            pil_img.save(preview_path, format="WEBP", quality=75, method=4)
        except Exception:
            blank = Image.new("RGB", (800, 600), (20, 24, 33))
            blank.save(preview_path, format="WEBP", quality=60)

        return preview_path

    def _run_preview_generation(
        self,
        job_id: str,
        gallery_uuid: str,
        gallery_dir: str,
        photos: List[Dict[str, Any]],
        watermark_enabled: bool,
        watermark_text: str
    ):
        """Worker thread executing preview generation with progress updates."""
        batch_mgr = BatchManager()
        total = len(photos)
        batch_mgr.add_log(job_id, f"Started generating {total} web proofing previews for gallery {gallery_uuid}")

        for idx, p in enumerate(photos):
            if job_id in batch_mgr.cancel_flags and batch_mgr.cancel_flags[job_id].is_set():
                batch_mgr.add_log(job_id, "Preview generation cancelled by user", "WARNING")
                return

            if job_id in batch_mgr.pause_flags:
                batch_mgr.pause_flags[job_id].wait()

            fname = os.path.basename(p["file_path"])
            try:
                self._generate_single_preview(gallery_dir, p, watermark_enabled, watermark_text)
            except Exception as err:
                batch_mgr.add_log(job_id, f"Error generating preview for {fname}: {err}", "WARNING")

            pct = round(((idx + 1) / total) * 100, 1)
            batch_mgr.update_progress(job_id, idx + 1, total, fname, pct)

        # Mark job completed
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE batch_jobs SET status = 'COMPLETED', progress_pct = 100.0, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        batch_mgr.add_log(job_id, f"All {total} proofing previews generated successfully.")

    def ensure_single_preview(self, gallery_uuid: str, photo_id: int) -> Optional[str]:
        """On-demand preview fallback guaranteeing zero broken images."""
        gallery_dir = os.path.join(PROOFING_CACHE_DIR, gallery_uuid)
        preview_path = os.path.join(gallery_dir, f"{photo_id}.webp")
        if os.path.exists(preview_path):
            return preview_path

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
        p = cursor.fetchone()
        cursor.execute("SELECT watermark_enabled, watermark_text FROM client_galleries WHERE gallery_uuid = ?", (gallery_uuid,))
        g = cursor.fetchone()
        conn.close()

        if not p:
            return None

        wm_enabled = bool(g["watermark_enabled"]) if g else True
        wm_text = g["watermark_text"] if g else "PROOF ONLY - Ai PhotoFlow"
        os.makedirs(gallery_dir, exist_ok=True)
        return self._generate_single_preview(gallery_dir, dict(p), wm_enabled, wm_text)

    def get_gallery_public(self, gallery_uuid: str, pin: str = "") -> Dict[str, Any]:
        """
        Public endpoint for client mobile/PC browser to load photos and selection states.
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM client_galleries WHERE gallery_uuid = ?", (gallery_uuid,))
        gallery = cursor.fetchone()
        if not gallery:
            conn.close()
            raise ValueError("Gallery not found or link has expired.")

        g_dict = dict(gallery)

        # Validate PIN if gallery is protected
        required_pin = g_dict.get("client_pin", "").strip()
        if required_pin and required_pin != pin.strip():
            conn.close()
            return {
                "gallery_uuid": gallery_uuid,
                "title": g_dict["title"],
                "requires_pin": True,
                "error": "PIN required to view gallery"
            }

        # Query all mapped photos
        cursor.execute("""
        SELECT
            p.id,
            p.filename,
            p.width,
            p.height,
            p.exif_date,
            gp.client_selection,
            gp.client_note
        FROM client_gallery_photos gp
        JOIN photos p ON p.id = gp.photo_id
        WHERE gp.gallery_uuid = ?
        ORDER BY gp.photo_id ASC
        """, (gallery_uuid,))

        photos_data = []
        selected_count = 0
        for r in cursor.fetchall():
            row = dict(r)
            row["preview_url"] = f"/api/proofing/preview/{gallery_uuid}/{row['id']}"
            if row["client_selection"] == "SELECTED":
                selected_count += 1
            photos_data.append(row)

        conn.close()

        g_dict["requires_pin"] = False
        g_dict["photos"] = photos_data
        g_dict["selected_count"] = selected_count
        return g_dict

    def update_photo_selection(
        self,
        gallery_uuid: str,
        photo_id: int,
        selection: str,
        note: str = ""
    ) -> Dict[str, Any]:
        """
        Updates single photo selection status (SELECTED / REJECTED / UNRATED).
        """
        selection_clean = selection.upper()
        if selection_clean not in ("SELECTED", "REJECTED", "UNRATED"):
            selection_clean = "UNRATED"

        conn = get_connection()
        cursor = conn.cursor()

        # Update in client_gallery_photos
        cursor.execute("""
        UPDATE client_gallery_photos
        SET client_selection = ?, client_note = ?
        WHERE gallery_uuid = ? AND photo_id = ?
        """, (selection_clean, note, gallery_uuid, photo_id))

        # Also sync back to master photos table
        cursor.execute("""
        UPDATE photos
        SET client_selection = ?, client_note = ?
        WHERE id = ?
        """, (selection_clean, note, photo_id))

        # Recalculate gallery selection count
        cursor.execute("""
        SELECT COUNT(*) as sel_cnt
        FROM client_gallery_photos
        WHERE gallery_uuid = ? AND client_selection = 'SELECTED'
        """, (gallery_uuid,))
        sel_count = cursor.fetchone()["sel_cnt"]

        cursor.execute("""
        UPDATE client_galleries
        SET selected_count = ?, updated_at = CURRENT_TIMESTAMP
        WHERE gallery_uuid = ?
        """, (sel_count, gallery_uuid))

        conn.commit()
        conn.close()

        return {
            "gallery_uuid": gallery_uuid,
            "photo_id": photo_id,
            "selection": selection_clean,
            "note": note,
            "selected_count": sel_count
        }

    def submit_gallery(
        self,
        gallery_uuid: str,
        client_notes: str = ""
    ) -> Dict[str, Any]:
        """
        Marks gallery as submitted by client.
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE client_galleries
        SET status = 'SUBMITTED', submitted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE gallery_uuid = ?
        """, (gallery_uuid,))

        cursor.execute("""
        SELECT g.*, COUNT(CASE WHEN gp.client_selection = 'SELECTED' THEN 1 END) as final_selected
        FROM client_galleries g
        LEFT JOIN client_gallery_photos gp ON gp.gallery_uuid = g.gallery_uuid
        WHERE g.gallery_uuid = ?
        GROUP BY g.id
        """, (gallery_uuid,))
        gallery = cursor.fetchone()

        conn.commit()
        conn.close()

        return {
            "status": "SUBMITTED",
            "gallery_uuid": gallery_uuid,
            "selected_count": gallery["final_selected"] if gallery else 0,
            "message": "Selection successfully submitted to studio!"
        }

    def list_project_galleries(self, project_id: int) -> List[Dict[str, Any]]:
        """Lists all client galleries created for a specific project."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM client_galleries
        WHERE project_id = ?
        ORDER BY created_at DESC
        """, (project_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def export_client_selected(
        self,
        project_id: int,
        destination_folder: str,
        gallery_uuid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pulls original camera master files (RAW or High-Res JPG) for client-selected photos
        and safely copies them into a dedicated '/Client_Album_Selection' directory.
        """
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder, exist_ok=True)

        target_dir = os.path.join(destination_folder, "Client_Album_Selection")
        os.makedirs(target_dir, exist_ok=True)

        conn = get_connection()
        cursor = conn.cursor()

        if gallery_uuid:
            cursor.execute("""
            SELECT p.id, p.filename, p.file_path, gp.client_note
            FROM client_gallery_photos gp
            JOIN photos p ON p.id = gp.photo_id
            WHERE gp.gallery_uuid = ? AND gp.client_selection = 'SELECTED'
            ORDER BY p.id ASC
            """, (gallery_uuid,))
        else:
            cursor.execute("""
            SELECT id, filename, file_path, client_note
            FROM photos
            WHERE project_id = ? AND client_selection = 'SELECTED'
            ORDER BY id ASC
            """, (project_id,))

        selected_photos = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not selected_photos:
            raise ValueError("No client-selected photos found to export.")

        manifest_entries = []
        copied_count = 0

        for idx, item in enumerate(selected_photos, start=1):
            src_path = item["file_path"]
            filename = item["filename"]
            dest_path = os.path.join(target_dir, filename)

            if os.path.exists(src_path):
                # Safely copy original camera RAW / JPG without modification
                shutil.copy2(src_path, dest_path)
                copied_count += 1
                manifest_entries.append({
                    "index": idx,
                    "filename": filename,
                    "client_note": item.get("client_note", "")
                })

        # Generate a selection manifest text file for the album designer
        manifest_path = os.path.join(target_dir, "Selection_Manifest.txt")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("=====================================================\n")
            f.write("      Ai PhotoFlow - Customer Selected Photos        \n")
            f.write("=====================================================\n")
            f.write(f"Total Selected Photos: {copied_count}\n")
            f.write(f"Export Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for entry in manifest_entries:
                note_str = f" | Note: {entry['client_note']}" if entry['client_note'] else ""
                f.write(f"[{entry['index']:03d}] {entry['filename']}{note_str}\n")

        return {
            "status": "SUCCESS",
            "copied_count": copied_count,
            "target_dir": target_dir,
            "manifest_file": manifest_path
        }


proofing_service = ProofingService()
