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

        # Master Hosting (photographer's own cPanel domain): previews are uploaded there after generation
        from backend.services.hosting_sync_service import hosting_sync_service
        master_base = hosting_sync_service.uses_master_hosting()
        if master_base:
            hosting_sync_service.mark_pending(gallery_uuid, master_base)

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
            "share_url": f"http://127.0.0.1:{os.environ.get('PORT', '8000')}/gallery/{gallery_uuid}",
            "status": "PROCESSING",
            "client_pin": client_pin,
            "selected_count": 0,
            "hosting_url": master_base,
            "hosting_status": "PENDING" if master_base else "",
            "hosting_error": "",
            "hosting_uploaded": 0
        }

    def _generate_single_preview(
        self,
        gallery_dir: str,
        photo_dict: Dict[str, Any],
        watermark_enabled: bool = True,
        watermark_text: str = "PROOF ONLY - Ai PhotoFlow"
    ) -> tuple:
        """Generates 1200px preview and fast 360px grid thumbnail in WebP format."""
        photo_id = photo_dict["id"]
        preview_filename = f"{photo_id}.webp"
        thumb_filename = f"{photo_id}_thumb.webp"
        preview_path = os.path.join(gallery_dir, preview_filename)
        thumb_path = os.path.join(gallery_dir, thumb_filename)

        if os.path.exists(preview_path) and os.path.exists(thumb_path):
            return preview_path, thumb_path

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

            # Save 1200px preview
            pil_img.save(preview_path, format="WEBP", quality=75, method=3)

            # Save fast 360px grid thumbnail
            pil_thumb = pil_img.copy()
            pil_thumb.thumbnail((360, 360), Image.Resampling.LANCZOS)
            pil_thumb.save(thumb_path, format="WEBP", quality=68, method=3)
        except Exception:
            blank = Image.new("RGB", (800, 600), (20, 24, 33))
            blank.save(preview_path, format="WEBP", quality=60)
            blank_thumb = Image.new("RGB", (320, 240), (20, 24, 33))
            blank_thumb.save(thumb_path, format="WEBP", quality=60)

        return preview_path, thumb_path

    def _run_preview_generation(
        self,
        job_id: str,
        gallery_uuid: str,
        gallery_dir: str,
        photos: List[Dict[str, Any]],
        watermark_enabled: bool,
        watermark_text: str
    ):
        """Worker thread executing parallel preview generation with real-time progress updates."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        batch_mgr = BatchManager()
        total = len(photos)
        batch_mgr.add_log(job_id, f"Started generating {total} web proofing previews for gallery {gallery_uuid} (Multi-Core Accelerated)...")

        num_workers = min(4, max(2, (os.cpu_count() or 4)))
        completed_count = 0

        def process_one(p):
            if job_id in batch_mgr.cancel_flags and batch_mgr.cancel_flags[job_id].is_set():
                return None
            fname = os.path.basename(p["file_path"])
            try:
                self._generate_single_preview(gallery_dir, p, watermark_enabled, watermark_text)
                return fname
            except Exception as err:
                batch_mgr.add_log(job_id, f"Error generating preview for {fname}: {err}", "WARNING")
                return fname

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(process_one, p) for p in photos]
            for f in as_completed(futures):
                if job_id in batch_mgr.cancel_flags and batch_mgr.cancel_flags[job_id].is_set():
                    break
                if job_id in batch_mgr.pause_flags:
                    batch_mgr.pause_flags[job_id].wait()

                fname = f.result() or "photo"
                completed_count += 1
                pct = round((completed_count / total) * 100, 1)
                batch_mgr.update_progress(job_id, completed_count, total, fname, pct)

        batch_mgr.add_log(job_id, f"All {total} proofing previews generated successfully.", "SUCCESS")

        # Upload to the photographer's Master Hosting domain (if configured for this gallery)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT hosting_url FROM client_galleries WHERE gallery_uuid = ?", (gallery_uuid,))
        row = cursor.fetchone()
        conn.close()
        hosting_url = (row["hosting_url"] if row else "") or ""
        cancelled = job_id in batch_mgr.cancel_flags and batch_mgr.cancel_flags[job_id].is_set()
        if hosting_url and not cancelled:
            from backend.services.hosting_sync_service import hosting_sync_service
            batch_mgr.add_log(job_id, f"Uploading {total} previews to {hosting_url} ...")

            def on_upload(n, tot, fname):
                batch_mgr.update_progress(job_id, n, tot, f"Uploading to domain: {fname}", round(n / max(tot, 1) * 100, 1))

            res = hosting_sync_service.sync_gallery(gallery_uuid, hosting_url, progress=on_upload)
            if res.get("success"):
                batch_mgr.add_log(job_id, f"Gallery is live on {hosting_url}", "SUCCESS")
            else:
                batch_mgr.add_log(job_id, f"Domain upload failed: {res.get('error')}", "ERROR")

        # Mark job completed
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE batch_jobs SET status = 'COMPLETED', progress_pct = 100.0, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()

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
        prev_p, _ = self._generate_single_preview(gallery_dir, dict(p), wm_enabled, wm_text)
        return prev_p

    def ensure_single_thumb(self, gallery_uuid: str, photo_id: int) -> Optional[str]:
        """On-demand 360px grid thumbnail fallback."""
        gallery_dir = os.path.join(PROOFING_CACHE_DIR, gallery_uuid)
        thumb_path = os.path.join(gallery_dir, f"{photo_id}_thumb.webp")
        if os.path.exists(thumb_path):
            return thumb_path

        self.ensure_single_preview(gallery_uuid, photo_id)
        return thumb_path if os.path.exists(thumb_path) else None

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
            row["thumb_url"] = f"/api/proofing/thumb/{gallery_uuid}/{row['id']}"
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

    def _pull_hosted_selections(self, project_id: Optional[int] = None, gallery_uuid: Optional[str] = None):
        """Best-effort refresh of client selections from galleries that are live on the Master Hosting."""
        from backend.services.hosting_sync_service import hosting_sync_service
        conn = get_connection()
        cursor = conn.cursor()
        if gallery_uuid:
            cursor.execute("SELECT gallery_uuid FROM client_galleries WHERE gallery_uuid = ? AND hosting_status IN ('ONLINE', 'EXPIRED')", (gallery_uuid,))
        else:
            cursor.execute("SELECT gallery_uuid FROM client_galleries WHERE project_id = ? AND hosting_status IN ('ONLINE', 'EXPIRED')", (project_id,))
        uuids = [r["gallery_uuid"] for r in cursor.fetchall()]
        conn.close()
        for u in uuids:
            try:
                hosting_sync_service.pull_selections(u)
            except Exception:
                pass

    def list_project_galleries(self, project_id: int) -> List[Dict[str, Any]]:
        """Lists all client galleries created for a specific project."""
        self._pull_hosted_selections(project_id=project_id)
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

        # Selections made on the Master Hosting domain live on the server; fetch them first
        self._pull_hosted_selections(project_id=project_id, gallery_uuid=gallery_uuid)

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

    def export_standalone_gallery(
        self,
        gallery_uuid: str,
        destination_folder: str
    ) -> Dict[str, Any]:
        """
        Exports self-contained HTML gallery with watermarked WebP photos
        ready to upload to any cPanel/Web Hosting or Google Drive.
        Never expires and runs 24/7 on photographer's web server.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM client_galleries WHERE gallery_uuid = ?", (gallery_uuid,))
        gallery = cursor.fetchone()
        if not gallery:
            conn.close()
            raise ValueError(f"Gallery {gallery_uuid} not found")

        g_dict = dict(gallery)
        cursor.execute("""
        SELECT p.id, p.filename, p.width, p.height, p.file_path, gp.client_selection, gp.client_note
        FROM client_gallery_photos gp
        JOIN photos p ON p.id = gp.photo_id
        WHERE gp.gallery_uuid = ?
        ORDER BY gp.photo_id ASC
        """, (gallery_uuid,))
        photos = [dict(r) for r in cursor.fetchall()]
        conn.close()

        os.makedirs(destination_folder, exist_ok=True)
        img_dir = os.path.join(destination_folder, "images")
        os.makedirs(img_dir, exist_ok=True)

        cached_gallery_dir = os.path.join(PROOFING_CACHE_DIR, gallery_uuid)
        wm_enabled = bool(g_dict.get("watermark_enabled", 1))
        wm_text = g_dict.get("watermark_text", "PROOF ONLY - Ai PhotoFlow")

        export_photos_data = []
        for idx, p in enumerate(photos):
            pid = p["id"]
            prev_src, thumb_src = self._generate_single_preview(cached_gallery_dir, p, wm_enabled, wm_text)
            prev_dst = os.path.join(img_dir, f"{pid}.webp")
            thumb_dst = os.path.join(img_dir, f"{pid}_thumb.webp")
            if os.path.exists(prev_src):
                shutil.copy2(prev_src, prev_dst)
            if os.path.exists(thumb_src):
                shutil.copy2(thumb_src, thumb_dst)

            export_photos_data.append({
                "id": pid,
                "filename": p["filename"],
                "width": p.get("width", 1200),
                "height": p.get("height", 800),
                "preview_url": f"images/{pid}.webp",
                "thumb_url": f"images/{pid}_thumb.webp",
                "client_selection": p.get("client_selection", "UNRATED"),
                "client_note": p.get("client_note", "")
            })

        standalone_gallery_data = {
            "gallery_uuid": gallery_uuid,
            "title": g_dict.get("title", "Wedding Photo Selection"),
            "client_name": g_dict.get("client_name", ""),
            "client_pin": g_dict.get("client_pin", ""),
            "requires_pin": bool(g_dict.get("client_pin", "").strip()),
            "total_photos": len(photos),
            "selected_count": sum(1 for p in photos if p.get("client_selection") == "SELECTED"),
            "photos": export_photos_data,
            "is_standalone": True
        }

        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "proofing_gallery.html")
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        html_content = html_content.replace("__GALLERY_DATA_JSON__", json.dumps(standalone_gallery_data))

        index_path = os.path.join(destination_folder, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        data_json_path = os.path.join(destination_folder, "gallery_data.json")
        with open(data_json_path, "w", encoding="utf-8") as f:
            json.dump(standalone_gallery_data, f, indent=2)

        readme_path = os.path.join(destination_folder, "HOW_TO_UPLOAD_TO_WEBSITE.txt")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("=========================================================================\n")
            f.write(" Ai PhotoFlow - Standalone Gallery for Website / cPanel Hosting\n")
            f.write("=========================================================================\n\n")
            f.write("Aap is folder ko direct apne hosting par upload karke permanent link bana sakte hain:\n\n")
            f.write("STEPS FOR CPANEL / HOSTINGER / GODADDY / WORDPRESS:\n")
            f.write("1. Apne cPanel me File Manager open karein.\n")
            f.write("2. 'public_html' ke andar ek new folder banayein, jaise: 'proofing' ya 'clients'.\n")
            f.write("3. Is exported folder ke sabhi files (index.html, images folder, gallery_data.json) ko wahan upload kar dein.\n")
            f.write("4. Aapka Permanent Link tayyar hai:\n")
            f.write("   https://yourdomain.com/proofing/ (ya jo bhi folder naam ho)\n\n")
            f.write("FAYDE:\n")
            f.write("- Ye link KABHI EXPIRE NAHI HOGA (Permanent 24/7 online).\n")
            f.write("- Aapka PC ya Mac band hone par bhi customer mobile par photos open aur select kar sakta hai.\n")
            f.write("- Customer ke select karne par WhatsApp button se aapko direct selected photo list mil jayegi!\n")

        return {
            "status": "SUCCESS",
            "destination_folder": destination_folder,
            "total_photos": len(photos),
            "index_file": index_path
        }


proofing_service = ProofingService()
