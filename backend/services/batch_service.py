"""
Batch Processing Queue Manager
Coordinates async tasks for Culling, Auto-Editing, and High-Res Export with pause/resume/cancel and real-time logs.
"""
import uuid
import json
import threading
import time
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.db.database import get_connection
from backend.services.culling_service import CullingService
from backend.services.image_service import load_image, export_photo, generate_edited_thumbnail
from backend.core.editing_model import IndianWeddingEditingModel
from backend.core.scene_model import SceneConsistencyEngine
from backend.core.interfaces import EditParameters

class BatchManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BatchManager, cls).__new__(cls)
            cls._instance.active_threads: Dict[str, threading.Thread] = {}
            cls._instance.pause_flags: Dict[str, threading.Event] = {}
            cls._instance.cancel_flags: Dict[str, threading.Event] = {}
            cls._instance.culling_service = CullingService()
            cls._instance.editing_model = IndianWeddingEditingModel()
        return cls._instance

    def create_job(self, project_id: int, job_type: str, total_items: int) -> str:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO batch_jobs (id, project_id, job_type, status, progress_current, progress_total, progress_pct, logs)
        VALUES (?, ?, ?, 'RUNNING', 0, ?, 0.0, '[]')
        """, (job_id, project_id, job_type, total_items))
        conn.commit()
        conn.close()

        self.pause_flags[job_id] = threading.Event()
        self.pause_flags[job_id].set() # Initially running (not paused)
        self.cancel_flags[job_id] = threading.Event()

        return job_id

    def add_log(self, job_id: str, message: str, level: str = "INFO"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT logs FROM batch_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            logs = json.loads(row["logs"])
            timestamp = datetime.now().strftime("%H:%M:%S")
            logs.append({"timestamp": timestamp, "level": level, "message": message})
            if len(logs) > 300: # Limit log entries
                logs = logs[-300:]
            cursor.execute("UPDATE batch_jobs SET logs = ? WHERE id = ?", (json.dumps(logs), job_id))
            conn.commit()
        conn.close()

    def update_progress(self, job_id: str, current: int, total: int, current_file: str, pct: float):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE batch_jobs SET
            progress_current = ?,
            progress_total = ?,
            progress_pct = ?,
            current_file = ?
        WHERE id = ?
        """, (current, total, pct, current_file, job_id))
        conn.commit()
        conn.close()

    def pause_job(self, job_id: str):
        if job_id in self.pause_flags:
            self.pause_flags[job_id].clear()
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE batch_jobs SET status = 'PAUSED' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            self.add_log(job_id, "Job paused by user", "WARNING")

    def resume_job(self, job_id: str):
        if job_id in self.pause_flags:
            self.pause_flags[job_id].set()
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE batch_jobs SET status = 'RUNNING' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            self.add_log(job_id, "Job resumed", "INFO")

    def cancel_job(self, job_id: str):
        if job_id in self.cancel_flags:
            self.cancel_flags[job_id].set()
            if job_id in self.pause_flags:
                self.pause_flags[job_id].set() # Unpause so it can exit
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE batch_jobs SET status = 'CANCELLED', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            self.add_log(job_id, "Job cancelled by user", "WARNING")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        res["logs"] = json.loads(res["logs"]) if res["logs"] else []
        return res

    # 1. Background Culling Job
    def start_culling_job(self, project_id: int) -> str:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM photos WHERE project_id = ?", (project_id,))
        total = cursor.fetchone()["total"]
        conn.close()

        job_id = self.create_job(project_id, "CULLING", total)

        def runner():
            # Anti-tamper & Crack Protection Check
            from backend.services.license_service import LicenseService
            allowed, sec_msg = LicenseService().verify_operational_permission("CULL")
            if not allowed:
                self.add_log(job_id, f"Security Lockdown: {sec_msg}", "ERROR")
                conn_err = get_connection()
                c_err = conn_err.cursor()
                c_err.execute("UPDATE batch_jobs SET status = 'CANCELLED', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
                conn_err.commit()
                conn_err.close()
                return

            self.add_log(job_id, f"Started AI Culling for {total} wedding photos...")
            def progress(curr, tot, msg, pct):
                self.update_progress(job_id, curr, tot, msg, pct)
                if curr % 10 == 0 or curr == tot:
                    self.add_log(job_id, f"Processing: {curr} / {tot} ({pct}%) - {msg}")

            def is_canc():
                return self.cancel_flags.get(job_id, threading.Event()).is_set()

            def is_pau():
                return not self.pause_flags.get(job_id, threading.Event()).is_set()

            try:
                self.culling_service.process_culling(
                    project_id=project_id,
                    progress_callback=progress,
                    is_cancelled=is_canc,
                    is_paused=is_pau
                )
                conn2 = get_connection()
                c2 = conn2.cursor()
                status = 'CANCELLED' if is_canc() else 'COMPLETED'
                c2.execute("UPDATE batch_jobs SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (status, job_id))
                conn2.commit()
                conn2.close()
                self.add_log(job_id, f"AI Culling {status.lower()} successfully!", "SUCCESS")
            except Exception as e:
                conn2 = get_connection()
                c2 = conn2.cursor()
                c2.execute("UPDATE batch_jobs SET status = 'FAILED', error_message = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (str(e), job_id))
                conn2.commit()
                conn2.close()
                self.add_log(job_id, f"AI Culling failed: {e}", "ERROR")

        th = threading.Thread(target=runner, daemon=True)
        self.active_threads[job_id] = th
        th.start()
        return job_id

    # 2. Background Auto-Edit Job
    def start_auto_edit_job(self, project_id: int, preset_name: str = "Natural Wedding", photo_ids: Optional[List[int]] = None) -> str:
        conn = get_connection()
        cursor = conn.cursor()

        if photo_ids and len(photo_ids) > 0:
            placeholders = ",".join("?" for _ in photo_ids)
            cursor.execute(f"SELECT id, filename, file_path, scene_category, edit_params FROM photos WHERE id IN ({placeholders})", photo_ids)
        else:
            # Edit all SELECTED or BEST photos
            cursor.execute("""
            SELECT id, filename, file_path, scene_category, edit_params FROM photos
            WHERE project_id = ? AND (
                user_selection IN ('BEST', 'SELECTED') OR
                (user_selection = 'UNRATED' AND ai_recommendation IN ('BEST', 'SELECTED'))
            )
            """, (project_id,))

        target_photos = [dict(r) for r in cursor.fetchall()]
        total = len(target_photos)
        conn.close()

        job_id = self.create_job(project_id, "AUTO_EDIT", total)

        def runner():
            try:
                self.add_log(job_id, f"Auto-Editing {total} photos with '{preset_name}' (Multi-Core Accelerated)...")
                import cv2
                cv2.setNumThreads(1)
                from concurrent.futures import ThreadPoolExecutor, as_completed

                num_workers = min(4, max(2, (os.cpu_count() or 4)))
                edited_records = []
                completed_count = 0

                def process_single(p):
                    if self.cancel_flags.get(job_id, threading.Event()).is_set():
                        return None
                    pid = p["id"]
                    filepath = p["file_path"]
                    filename = p["filename"]
                    scene = p.get("scene_category", "Mandap & Ceremony")

                    try:
                        # Single-pass decode: load image once at 1000px
                        cv_img = load_image(filepath, max_dim=1000)
                        params, (s_mask, s_info) = self.editing_model.calculate_corrections(
                            cv_img, preset_name=preset_name, scene_group=scene, return_mask=True
                        )

                        # Preserve existing manual heal spots if present
                        existing_raw = p.get("edit_params")
                        if existing_raw:
                            try:
                                existing_dict = json.loads(existing_raw)
                                if existing_dict.get("heal_spots"):
                                    params.heal_spots = existing_dict["heal_spots"]
                            except Exception:
                                pass

                        params_dict = params.to_dict()

                        # Pre-cache edited thumbnail reusing the already-loaded cv_img AND computed subject mask
                        try:
                            generate_edited_thumbnail(
                                filepath, project_id, pid, params,
                                base_rgb=cv_img, subject_mask=s_mask, subject_info=s_info
                            )
                        except Exception:
                            pass

                        return {
                            "id": pid,
                            "file_path": filepath,
                            "filename": filename,
                            "edit_params": params_dict,
                            "scene_category": scene,
                            "manual_override": 0
                        }
                    except Exception as e:
                        return {"id": pid, "filename": filename, "error": str(e)}

                conn_worker = get_connection()
                c_w = conn_worker.cursor()

                try:
                    with ThreadPoolExecutor(max_workers=num_workers) as executor:
                        future_to_photo = {executor.submit(process_single, p): p for p in target_photos}

                        for future in as_completed(future_to_photo):
                            if self.cancel_flags.get(job_id, threading.Event()).is_set():
                                break

                            while not self.pause_flags.get(job_id, threading.Event()).is_set():
                                time.sleep(0.5)

                            try:
                                res = future.result()
                            except Exception as future_err:
                                p_info = future_to_photo.get(future, {})
                                res = {"error": str(future_err), "filename": p_info.get("filename", "photo"), "id": p_info.get("id")}

                            completed_count += 1

                            if res and "error" not in res:
                                try:
                                    c_w.execute("""
                                    UPDATE photos SET
                                        edit_params = ?,
                                        is_edited = 1,
                                        manual_override = 0
                                    WHERE id = ?
                                    """, (json.dumps(res["edit_params"]), res["id"]))
                                    edited_records.append(res)
                                except Exception as db_err:
                                    self.add_log(job_id, f"Database write warning for {res.get('filename')}: {db_err}", "WARNING")
                            elif res and "error" in res:
                                self.add_log(job_id, f"Failed editing {res['filename']}: {res['error']}", "WARNING")

                            if completed_count % 5 == 0 or completed_count == total:
                                try:
                                    conn_worker.commit()
                                except Exception:
                                    pass
                                pct = round((completed_count / total) * 95.0, 1)
                                latest_name = res.get("filename", "") if res else ""
                                self.update_progress(job_id, completed_count, total, latest_name, pct)
                                if completed_count % 20 == 0 or completed_count == total:
                                    self.add_log(job_id, f"Auto-Edited {completed_count}/{total} photos")

                    conn_worker.commit()

                    # Harmonize Scene Consistency (skipped in Pure Light mode for speed and 0% color modification)
                    is_pure_light = "Pure Light" in preset_name
                    if not is_pure_light and len(edited_records) > 0 and not self.cancel_flags.get(job_id, threading.Event()).is_set():
                        self.add_log(job_id, "Checking scene color consistency...")
                        try:
                            harmonized = SceneConsistencyEngine.harmonize_scene_parameters(edited_records)
                            for h_item in harmonized:
                                c_w.execute("UPDATE photos SET edit_params = ? WHERE id = ?", (json.dumps(h_item["edit_params"]), h_item["id"]))
                            conn_worker.commit()
                        except Exception as e:
                            self.add_log(job_id, f"Scene harmonization note: {e}", "INFO")

                    is_canc = self.cancel_flags.get(job_id, threading.Event()).is_set()
                    final_status = 'CANCELLED' if is_canc else 'COMPLETED'
                    c_w.execute("UPDATE batch_jobs SET status = ?, progress_pct = 100.0, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (final_status, job_id))
                    if not is_canc:
                        c_w.execute("UPDATE projects SET status = 'EDITED' WHERE id = ?", (project_id,))
                    conn_worker.commit()
                    self.add_log(job_id, f"Auto-Editing {final_status.lower()} for {len(edited_records)}/{total} photos!", "SUCCESS")

                finally:
                    try:
                        conn_worker.close()
                    except Exception:
                        pass

            except Exception as global_err:
                try:
                    conn_err = get_connection()
                    c_err = conn_err.cursor()
                    c_err.execute("UPDATE batch_jobs SET status = 'FAILED', error_message = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (str(global_err), job_id))
                    conn_err.commit()
                    conn_err.close()
                except Exception:
                    pass
                self.add_log(job_id, f"Auto-Editing failed: {global_err}", "ERROR")

        th = threading.Thread(target=runner, daemon=True)
        self.active_threads[job_id] = th
        th.start()
        return job_id

    # 3. Background High-Res Export Job
    def start_export_job(
        self,
        project_id: int,
        output_folder: str,
        jpeg_quality: int = 92,
        max_resolution: Optional[int] = None,
        rename_pattern: str = "{original}_edited",
        categories: Optional[List[str]] = None
    ) -> str:
        """
        Exports selected photos into subfolders: /AI-Selected, /AI-Edited, /Rejected.
        Never overwrites original files.
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Query photos to export
        cursor.execute("""
        SELECT id, filename, file_path, ai_recommendation, user_selection, edit_params, is_edited
        FROM photos WHERE project_id = ?
        """, (project_id,))
        all_photos = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # Filter by requested categories (default: Selected & Best)
        if not categories:
            categories = ["BEST", "SELECTED"]

        export_queue = []
        for p in all_photos:
            effective_choice = p["user_selection"] if p["user_selection"] != "UNRATED" else p["ai_recommendation"]
            is_client_selected = p.get("client_selection") == "SELECTED"
            if effective_choice in categories or ("CLIENT_SELECTED" in categories and is_client_selected):
                export_queue.append((p, "CLIENT_SELECTED" if is_client_selected else effective_choice))

        total = len(export_queue)
        job_id = self.create_job(project_id, "EXPORT", total)

        if total == 0:
            self.add_log(job_id, f"No photos match the selected categories: {categories}. Please mark photos as Best or Picked first.", "WARNING")
            conn_zero = get_connection()
            c_zero = conn_zero.cursor()
            c_zero.execute("UPDATE batch_jobs SET status = 'COMPLETED', progress_pct = 100.0, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn_zero.commit()
            conn_zero.close()
            return job_id

        def runner():
            # Anti-tamper & Crack Protection Check
            from backend.services.license_service import LicenseService
            allowed, sec_msg = LicenseService().verify_operational_permission("EXPORT")
            if not allowed:
                self.add_log(job_id, f"Security Lockdown: {sec_msg}", "ERROR")
                conn_err = get_connection()
                c_err = conn_err.cursor()
                c_err.execute("UPDATE batch_jobs SET status = 'CANCELLED', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
                conn_err.commit()
                conn_err.close()
                return

            try:
                self.add_log(job_id, f"Starting High-Res Export for {total} photos to {output_folder} (Multi-Core Accelerated)...")
                os.makedirs(output_folder, exist_ok=True)
                import cv2
                cv2.setNumThreads(1)
                from concurrent.futures import ThreadPoolExecutor, as_completed

                # Optimize concurrency based on CPU hardware
                num_workers = min(6, max(2, (os.cpu_count() or 4)))
                completed_count = 0

                def export_single(item):
                    cancel_evt = self.cancel_flags.get(job_id)
                    if cancel_evt and cancel_evt.is_set():
                        return None
                    idx, (p, choice) = item
                    src_path = p["file_path"]
                    base_name, _ = os.path.splitext(p["filename"])

                    if choice in ("BEST", "SELECTED"):
                        subfolder = "AI-Edited" if p.get("is_edited") else "AI-Selected"
                    elif choice == "REJECT":
                        subfolder = "Rejected"
                    else:
                        subfolder = "Review"

                    dest_dir = os.path.join(output_folder, subfolder)
                    os.makedirs(dest_dir, exist_ok=True)

                    new_filename = rename_pattern.replace("{original}", base_name).replace("{index}", f"{idx+1:04d}") + ".jpg"
                    dest_path = os.path.join(dest_dir, new_filename)

                    try:
                        is_edited = bool(p.get("is_edited", 0))
                        params_dict = json.loads(p["edit_params"]) if (p.get("edit_params") and is_edited) else {}
                        params = EditParameters.from_dict(params_dict) if params_dict else None
                        export_photo(
                            source_path=src_path,
                            target_path=dest_path,
                            params=params,
                            jpeg_quality=jpeg_quality,
                            max_resolution=max_resolution
                        )
                        return {"success": True, "filename": new_filename, "subfolder": subfolder, "dest_path": dest_path}
                    except Exception as e:
                        return {"success": False, "filename": p["filename"], "error": str(e)}

                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    futures = {executor.submit(export_single, (idx, item)): item for idx, item in enumerate(export_queue)}

                    for future in as_completed(futures):
                        cancel_evt = self.cancel_flags.get(job_id)
                        if cancel_evt and cancel_evt.is_set():
                            break

                        pause_evt = self.pause_flags.get(job_id)
                        if pause_evt and not pause_evt.is_set():
                            while not pause_evt.is_set():
                                time.sleep(0.3)

                        try:
                            res = future.result()
                        except Exception as fe:
                            res = {"success": False, "filename": "photo", "error": str(fe)}

                        completed_count += 1

                        if res and not res.get("success", False):
                            self.add_log(job_id, f"Error exporting {res.get('filename')}: {res.get('error')}", "WARNING")

                        pct = round((completed_count / total) * 100.0, 1)
                        cur_name = res.get("filename", "") if res else ""
                        self.update_progress(job_id, completed_count, total, cur_name, pct)
                        subf = res.get("subfolder", "output") if res else "output"
                        self.add_log(job_id, f"Exported: {completed_count}/{total} ({pct}%) -> {subf}/{cur_name}")

                conn_w = get_connection()
                c_w = conn_w.cursor()
                is_cancelled = False
                c_flag = self.cancel_flags.get(job_id)
                if c_flag and c_flag.is_set():
                    is_cancelled = True
                status = 'CANCELLED' if is_cancelled else 'COMPLETED'
                c_w.execute("UPDATE batch_jobs SET status = ?, progress_pct = 100.0, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (status, job_id))
                conn_w.commit()
                conn_w.close()
                self.add_log(job_id, f"Export completed successfully! Output available in: {output_folder}", "SUCCESS")
            except Exception as exp_err:
                try:
                    conn_err = get_connection()
                    c_err = conn_err.cursor()
                    c_err.execute("UPDATE batch_jobs SET status = 'FAILED', error_message = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (str(exp_err), job_id))
                    conn_err.commit()
                    conn_err.close()
                except Exception:
                    pass
                self.add_log(job_id, f"Export failed: {exp_err}", "ERROR")

        th = threading.Thread(target=runner, daemon=True)
        self.active_threads[job_id] = th
        th.start()
        return job_id
