"""
Ai PhotoFlow - FastAPI Backend Application
Desktop AI photo culling and batch editing service for professional wedding photographers.
"""
import os
import json
import hmac
import time
import io
import cv2
import numpy as np
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from PIL import Image

from backend.db.database import get_connection
from backend.services.culling_service import CullingService
from backend.services.batch_service import BatchManager
from backend.services.image_service import (
    generate_thumbnail, generate_edited_thumbnail, remove_edited_thumbnail,
    render_preview, load_image, CACHE_DIR
)
from backend.retouch import retouch_image, resolve_params as resolve_retouch_params, list_presets as list_retouch_presets, build_preset as build_retouch_preset, DEFAULT_RETOUCH
from backend.core.interfaces import EditParameters
from backend.core.photoshop_integration import PhotoshopUXPIntegration
from backend.core.editing_model import IndianWeddingEditingModel
from backend.services.license_service import get_license_service
from backend.services.proofing_service import proofing_service, PROOFING_CACHE_DIR
from backend.services.tunnel_service import tunnel_service
from backend.services.hosting_sync_service import hosting_sync_service, normalize_master_url

app = FastAPI(title="Ai PhotoFlow Core API", version="1.0.0")


# Enable CORS for frontend desktop client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

batch_manager = BatchManager()
culling_service = CullingService()
photoshop_bridge = PhotoshopUXPIntegration()
editing_model = IndianWeddingEditingModel()
license_service = get_license_service()

@app.on_event("startup")
def on_app_startup():
    try:
        cv2.setNumThreads(1)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE batch_jobs 
        SET status = 'CANCELLED', 
            error_message = 'Interrupted by application restart', 
            finished_at = CURRENT_TIMESTAMP 
        WHERE status IN ('RUNNING', 'PAUSED')
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Startup batch cleanup note: {e}")

# Pydantic Request Models
class ImportFolderRequest(BaseModel):
    folder_path: str
    project_name: Optional[str] = None

class UserSelectionRequest(BaseModel):
    user_selection: str # 'BEST', 'SELECTED', 'REVIEW', 'REJECT', 'UNRATED'

class StarRatingRequest(BaseModel):
    star_rating: int # 0 - 5

class EditParametersRequest(BaseModel):
    exposure: float = 0.0
    subject_exposure: float = 0.0
    temperature: float = 0.0
    tint: float = 0.0
    contrast: float = 0.0
    highlights: float = 0.0
    shadows: float = 0.0
    whites: float = 0.0
    blacks: float = 0.0
    vibrance: float = 5.0
    saturation: float = 0.0
    sharpness: float = 15.0
    noise_reduction: float = 10.0
    straighten: float = 0.0
    preset_name: str = "Natural Wedding"
    auto_blemish: float = 0.0
    skin_smoothing: float = 0.0
    dodge_burn: float = 0.0
    heal_opacity: float = 100.0
    heal_face_preset: str = "AUTO"
    heal_spots: Optional[List[Dict[str, float]]] = []
    retouch: Optional[Dict[str, Any]] = None
    auto_wb: Optional[Dict[str, Any]] = None

class AutoEditBatchRequest(BaseModel):
    preset_name: str = "Natural Wedding"
    photo_ids: Optional[List[int]] = None
    retouch_preset: str = "Natural"

class SettingsRequest(BaseModel):
    ai_provider: str = "local" # 'local', 'replicate', 'openai', 'gemini', 'custom'
    replicate_api_token: Optional[str] = ""
    openai_api_key: Optional[str] = ""
    gemini_api_key: Optional[str] = ""
    custom_ai_endpoint: Optional[str] = ""
    # None = not sent by this screen, keep the stored value
    custom_domain_url: Optional[str] = None
    cloudflare_tunnel_token: Optional[str] = None

class ExportRequest(BaseModel):
    output_folder: str
    jpeg_quality: int = 92
    max_resolution: Optional[int] = None
    rename_pattern: str = "{original}_edited"
    categories: Optional[List[str]] = ["BEST", "SELECTED"]

class BatchDeletePhotosRequest(BaseModel):
    photo_ids: List[int]


# --- Default Edit Parameters ---
DEFAULT_EDIT_PARAMS = {
    "exposure": 0.0,
    "subject_exposure": 0.0,
    "temperature": 0.0,
    "tint": 0.0,
    "contrast": 0.0,
    "highlights": 0.0,
    "shadows": 0.0,
    "whites": 0.0,
    "blacks": 0.0,
    "vibrance": 5.0,
    "saturation": 0.0,
    "sharpness": 15.0,
    "noise_reduction": 10.0,
    "straighten": 0.0,
    "preset_name": "Natural Wedding",
    "auto_blemish": 0.0,
    "skin_smoothing": 0.0,
    "dodge_burn": 0.0,
    "heal_spots": [],
    "retouch": None,
    "auto_wb": None
}

def format_edit_params(val) -> dict:
    base = DEFAULT_EDIT_PARAMS.copy()
    if val:
        try:
            parsed = json.loads(val) if isinstance(val, str) else val
            if isinstance(parsed, dict):
                base.update(parsed)
        except Exception:
            pass
    return base


# --- System & Status ---
@app.get("/api/system/info")
def get_system_info():
    return {
        "app_name": "Ai PhotoFlow",
        "version": "1.0.0 (MVP)",
        "platform": "macOS Apple Silicon / x86_64",
        "processing_engine": "OpenCV + Pillow + RawPy",
        "gpu_acceleration": "Available (Metal / CoreML fallback)",
        "status": "ready"
    }

@app.get("/api/settings")
def get_settings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM app_settings")
    rows = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()

    def mask(val: str) -> str:
        if not val or len(val) < 8:
            return val
        return val[:4] + "••••••••" + val[-4:]

    return {
        "ai_provider": rows.get("ai_provider", os.environ.get("AI_PROVIDER", "local")),
        "replicate_api_token": mask(rows.get("replicate_api_token", os.environ.get("REPLICATE_API_TOKEN", ""))),
        "openai_api_key": mask(rows.get("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))),
        "gemini_api_key": mask(rows.get("gemini_api_key", os.environ.get("GEMINI_API_KEY", ""))),
        "custom_ai_endpoint": rows.get("custom_ai_endpoint", os.environ.get("CUSTOM_AI_ENDPOINT", "")),
        "has_replicate": bool(rows.get("replicate_api_token") or os.environ.get("REPLICATE_API_TOKEN")),
        "has_openai": bool(rows.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")),
        "has_gemini": bool(rows.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")),
        "custom_domain_url": rows.get("custom_domain_url", "")
    }

@app.post("/api/settings")
def save_settings(req: SettingsRequest):
    conn = get_connection()
    cursor = conn.cursor()

    items = [
        ("ai_provider", req.ai_provider),
        ("custom_ai_endpoint", req.custom_ai_endpoint or ""),
    ]
    # Only update secret keys if non-empty and not masked
    if req.replicate_api_token and "••••" not in req.replicate_api_token:
        items.append(("replicate_api_token", req.replicate_api_token))
        os.environ["REPLICATE_API_TOKEN"] = req.replicate_api_token
    if req.openai_api_key and "••••" not in req.openai_api_key:
        items.append(("openai_api_key", req.openai_api_key))
        os.environ["OPENAI_API_KEY"] = req.openai_api_key
    if req.gemini_api_key and "••••" not in req.gemini_api_key:
        items.append(("gemini_api_key", req.gemini_api_key))
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key
    if req.custom_domain_url is not None:
        items.append(("custom_domain_url", normalize_master_url(req.custom_domain_url)))
    if req.cloudflare_tunnel_token is not None:
        items.append(("cloudflare_tunnel_token", req.cloudflare_tunnel_token.strip()))

    for k, v in items:
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (k, v))

    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Settings and credentials saved successfully"}

@app.get("/api/integrations/photoshop")
def get_photoshop_status():
    return {
        "available": photoshop_bridge.is_available(),
        "status_message": photoshop_bridge.get_status_message(),
        "v2_ready": True
    }


# --- Project Endpoints ---
@app.post("/api/projects/import")
def import_project(req: ImportFolderRequest):
    raw_path = req.folder_path.strip().strip('"').strip("'")
    folder = os.path.normpath(os.path.abspath(os.path.expanduser(raw_path)))

    print(f"[API] /api/projects/import requested for: '{folder}'")

    if not os.path.exists(folder):
        raise HTTPException(status_code=400, detail=f"Directory '{folder}' does not exist on disk.")

    folder_name = os.path.basename(folder) or "Wedding_Shoot"
    proj_name = req.project_name.strip() if req.project_name else f"Wedding – {folder_name}"
    try:
        result = culling_service.scan_folder(folder, proj_name)
        return result
    except Exception as e:
        print(f"[API Error] /api/projects/import failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/projects")
def list_projects():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
    projects = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return projects

@app.get("/api/projects/{project_id}")
def get_project_details(project_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    p_dict = dict(project)

    # Calculate category counts
    cursor.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(DISTINCT (CASE WHEN (user_selection IN ('BEST', 'SELECTED') OR (user_selection = 'UNRATED' AND ai_recommendation IN ('BEST', 'SELECTED'))) THEN (CASE WHEN duplicate_group_id IS NOT NULL THEN duplicate_group_id ELSE id END) ELSE NULL END)) as best_count,
        SUM(CASE WHEN (user_selection = 'SELECTED' OR (user_selection = 'UNRATED' AND ai_recommendation = 'SELECTED')) THEN 1 ELSE 0 END) as selected_count,
        SUM(CASE WHEN (user_selection = 'REVIEW' OR (user_selection = 'UNRATED' AND ai_recommendation = 'REVIEW')) THEN 1 ELSE 0 END) as review_count,
        SUM(CASE WHEN (user_selection = 'REJECT' OR (user_selection = 'UNRATED' AND ai_recommendation = 'REJECT')) THEN 1 ELSE 0 END) as reject_count,
        COUNT(DISTINCT duplicate_group_id) as similar_groups_count,
        SUM(CASE WHEN (user_selection = 'UNRATED' AND ai_recommendation = 'SIMILAR') THEN 1 ELSE 0 END) as similar_count,
        SUM(CASE WHEN is_edited = 1 THEN 1 ELSE 0 END) as edited_count,
        SUM(CASE WHEN client_selection = 'SELECTED' THEN 1 ELSE 0 END) as client_selected_count
    FROM photos WHERE project_id = ?
    """, (project_id,))
    counts = dict(cursor.fetchone())
    p_dict["counts"] = counts
    conn.close()
    return p_dict

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM photos WHERE project_id = ?", (project_id,))
    cursor.execute("DELETE FROM batch_jobs WHERE project_id = ?", (project_id,))
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Project {project_id} deleted successfully"}


# --- Photos Endpoints ---
@app.get("/api/projects/{project_id}/photos")
def list_photos(
    project_id: int,
    category: str = Query("ALL", description="ALL, BEST, SELECTED, REVIEW, REJECT, SIMILAR"),
    star_rating: Optional[int] = Query(None),
    scene: Optional[str] = Query(None),
    sort: str = Query("ai_score_desc", description="ai_score_desc, filename_asc, date_asc, rating_desc")
):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM photos WHERE project_id = ?"
    params = [project_id]

    # Category filter
    if category == "BEST":
        # Strictly show ONLY the winning best photo per duplicate/burst group (user requirement)
        query += """ AND (
            (user_selection IN ('BEST', 'SELECTED') OR (user_selection = 'UNRATED' AND ai_recommendation IN ('BEST', 'SELECTED')))
            AND (
                duplicate_group_id IS NULL 
                OR id = (
                    SELECT p2.id FROM photos p2 
                    WHERE p2.project_id = photos.project_id 
                      AND p2.duplicate_group_id = photos.duplicate_group_id 
                    ORDER BY 
                      (CASE WHEN p2.user_selection = 'BEST' THEN 1 ELSE 0 END) DESC,
                      (CASE WHEN p2.ai_recommendation = 'BEST' THEN 1 ELSE 0 END) DESC,
                      p2.ai_score DESC, 
                      p2.id ASC 
                    LIMIT 1
                )
            )
        )"""
    elif category == "SELECTED":
        query += " AND (user_selection = 'SELECTED' OR (user_selection = 'UNRATED' AND ai_recommendation = 'SELECTED'))"
    elif category == "REVIEW":
        query += " AND (user_selection = 'REVIEW' OR (user_selection = 'UNRATED' AND ai_recommendation = 'REVIEW'))"
    elif category == "REJECT":
        query += " AND (user_selection = 'REJECT' OR (user_selection = 'UNRATED' AND ai_recommendation = 'REJECT'))"
    elif category == "SIMILAR":
        query += """ AND duplicate_group_id IN (
            SELECT DISTINCT duplicate_group_id 
            FROM photos 
            WHERE project_id = ? AND duplicate_group_id IS NOT NULL AND (ai_recommendation = 'SIMILAR' OR user_selection = 'UNRATED')
        )"""
        params.append(project_id)
    elif category == "CLIENT_SELECTED":
        query += " AND client_selection = 'SELECTED'"

    if isinstance(star_rating, int) and star_rating > 0:
        query += " AND star_rating = ?"
        params.append(star_rating)

    if isinstance(scene, str) and scene and scene != "ALL":
        query += " AND scene_category = ?"
        params.append(scene)

    # Sorting
    if category == "SIMILAR":
        query += " ORDER BY duplicate_group_id ASC, (CASE WHEN (user_selection = 'BEST' OR (user_selection = 'UNRATED' AND ai_recommendation = 'BEST')) THEN 0 ELSE 1 END) ASC, ai_score DESC, id ASC"
    elif sort == "ai_score_desc":
        query += " ORDER BY ai_score DESC, id ASC"
    elif sort == "filename_asc":
        query += " ORDER BY filename ASC"
    elif sort == "rating_desc":
        query += " ORDER BY star_rating DESC, ai_score DESC"
    else:
        query += " ORDER BY id ASC"

    # Fetch duplicate group metadata for this project
    cursor.execute("""
        SELECT 
            duplicate_group_id,
            id,
            filename,
            ai_score,
            (user_selection = 'BEST' OR (user_selection = 'UNRATED' AND ai_recommendation = 'BEST')) as is_best
        FROM photos 
        WHERE project_id = ? AND duplicate_group_id IS NOT NULL
    """, (project_id,))
    
    group_map = {}
    for r in cursor.fetchall():
        gid = r["duplicate_group_id"]
        if gid not in group_map:
            group_map[gid] = []
        group_map[gid].append(dict(r))
        
    dup_meta = {}
    for gid, plist in group_map.items():
        best_p = next((p for p in plist if p["is_best"]), None)
        if not best_p:
            best_p = max(plist, key=lambda x: x["ai_score"])
        dup_meta[gid] = {
            "count": len(plist),
            "best_id": best_p["id"],
            "best_filename": best_p["filename"],
            "best_score": best_p["ai_score"]
        }

    cursor.execute(query, params)
    photos = []
    for r in cursor.fetchall():
        d = dict(r)
        d["edit_params"] = format_edit_params(d["edit_params"])
        # Effective selection
        d["effective_selection"] = d["user_selection"] if d["user_selection"] != "UNRATED" else d["ai_recommendation"]
        
        gid = d.get("duplicate_group_id")
        if gid and gid in dup_meta:
            meta = dup_meta[gid]
            d["duplicate_group_count"] = meta["count"]
            d["duplicate_group_best_id"] = meta["best_id"]
            d["duplicate_group_best_filename"] = meta["best_filename"]
            d["duplicate_group_best_score"] = meta["best_score"]
            d["is_group_best"] = (d["id"] == meta["best_id"])
        else:
            d["duplicate_group_count"] = 1
            d["duplicate_group_best_id"] = None
            d["duplicate_group_best_filename"] = None
            d["duplicate_group_best_score"] = None
            d["is_group_best"] = False

        photos.append(d)

    conn.close()
    return photos

@app.get("/api/projects/{project_id}/duplicate-groups/{group_id}")
def get_duplicate_group_photos(project_id: int, group_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM photos 
        WHERE project_id = ? AND duplicate_group_id = ?
        ORDER BY (CASE WHEN (user_selection = 'BEST' OR (user_selection = 'UNRATED' AND ai_recommendation = 'BEST')) THEN 0 ELSE 1 END) ASC, ai_score DESC, id ASC
    """, (project_id, group_id))
    rows = cursor.fetchall()
    photos = []
    best_p = None
    for r in rows:
        d = dict(r)
        d["edit_params"] = format_edit_params(d["edit_params"])
        d["effective_selection"] = d["user_selection"] if d["user_selection"] != "UNRATED" else d["ai_recommendation"]
        if (d["user_selection"] == "BEST" or (d["user_selection"] == "UNRATED" and d["ai_recommendation"] == "BEST")) and not best_p:
            best_p = d
        photos.append(d)
        
    if not best_p and photos:
        best_p = max(photos, key=lambda x: x["ai_score"])
        
    for p in photos:
        p["duplicate_group_count"] = len(photos)
        p["duplicate_group_best_id"] = best_p["id"] if best_p else None
        p["duplicate_group_best_filename"] = best_p["filename"] if best_p else None
        p["duplicate_group_best_score"] = best_p["ai_score"] if best_p else None
        p["is_group_best"] = (best_p is not None and p["id"] == best_p["id"])
        
    conn.close()
    return photos

@app.get("/api/photos/{photo_id}")
def get_photo(photo_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Photo not found")
    d = dict(row)
    d["edit_params"] = format_edit_params(d["edit_params"])
    d["effective_selection"] = d["user_selection"] if d["user_selection"] != "UNRATED" else d["ai_recommendation"]
    
    gid = d.get("duplicate_group_id")
    if gid:
        cursor.execute("""
            SELECT id, filename, ai_score, 
                   (user_selection = 'BEST' OR (user_selection = 'UNRATED' AND ai_recommendation = 'BEST')) as is_best
            FROM photos 
            WHERE project_id = ? AND duplicate_group_id = ?
        """, (d["project_id"], gid))
        g_rows = [dict(r) for r in cursor.fetchall()]
        best_p = next((p for p in g_rows if p["is_best"]), None)
        if not best_p and g_rows:
            best_p = max(g_rows, key=lambda x: x["ai_score"])
        d["duplicate_group_count"] = len(g_rows)
        d["duplicate_group_best_id"] = best_p["id"] if best_p else None
        d["duplicate_group_best_filename"] = best_p["filename"] if best_p else None
        d["duplicate_group_best_score"] = best_p["ai_score"] if best_p else None
        d["is_group_best"] = (best_p is not None and d["id"] == best_p["id"])
    else:
        d["duplicate_group_count"] = 1
        d["duplicate_group_best_id"] = None
        d["duplicate_group_best_filename"] = None
        d["duplicate_group_best_score"] = None
        d["is_group_best"] = False
        
    conn.close()
    return d

@app.patch("/api/photos/{photo_id}/selection")
def update_photo_selection(photo_id: int, req: UserSelectionRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Update this photo
    cursor.execute("UPDATE photos SET user_selection = ? WHERE id = ?", (req.user_selection, photo_id))
    
    # 2. If promoted to BEST and photo is part of a duplicate group:
    # Ensure there is only 1 BEST in this group; any previous best becomes SIMILAR
    if req.user_selection == "BEST":
        cursor.execute("SELECT duplicate_group_id, project_id FROM photos WHERE id = ?", (photo_id,))
        p_row = cursor.fetchone()
        if p_row and p_row["duplicate_group_id"]:
            gid = p_row["duplicate_group_id"]
            pid = p_row["project_id"]
            cursor.execute("""
                UPDATE photos 
                SET ai_recommendation = 'SIMILAR', user_selection = 'UNRATED'
                WHERE project_id = ? AND duplicate_group_id = ? AND id != ? AND (ai_recommendation = 'BEST' OR user_selection = 'BEST')
            """, (pid, gid, photo_id))
            
    # 3. If reset to UNRATED and part of duplicate group:
    elif req.user_selection == "UNRATED":
        cursor.execute("SELECT duplicate_group_id, project_id FROM photos WHERE id = ?", (photo_id,))
        p_row = cursor.fetchone()
        if p_row and p_row["duplicate_group_id"]:
            gid = p_row["duplicate_group_id"]
            pid = p_row["project_id"]
            # Find photo with highest ai_score in that group
            cursor.execute("""
                SELECT id FROM photos 
                WHERE project_id = ? AND duplicate_group_id = ?
                ORDER BY ai_score DESC LIMIT 1
            """, (pid, gid))
            top_row = cursor.fetchone()
            if top_row:
                top_id = top_row["id"]
                cursor.execute("UPDATE photos SET ai_recommendation = 'BEST' WHERE id = ? AND user_selection = 'UNRATED'", (top_id,))
                cursor.execute("""
                    UPDATE photos SET ai_recommendation = 'SIMILAR' 
                    WHERE project_id = ? AND duplicate_group_id = ? AND id != ? AND user_selection = 'UNRATED'
                """, (pid, gid, top_id))

    conn.commit()
    conn.close()
    return {"status": "ok", "photo_id": photo_id, "user_selection": req.user_selection}

@app.delete("/api/photos/batch")
def delete_photos_batch(req: BatchDeletePhotosRequest):
    if not req.photo_ids:
        return {"status": "ok", "deleted_count": 0}
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in req.photo_ids)
    cursor.execute(f"SELECT DISTINCT project_id FROM photos WHERE id IN ({placeholders})", req.photo_ids)
    project_ids = [r["project_id"] for r in cursor.fetchall()]
    
    cursor.execute(f"DELETE FROM photos WHERE id IN ({placeholders})", req.photo_ids)
    deleted_count = cursor.rowcount
    
    for pid in project_ids:
        cursor.execute("SELECT COUNT(*) as cnt FROM photos WHERE project_id = ?", (pid,))
        cnt = cursor.fetchone()["cnt"]
        cursor.execute("UPDATE projects SET total_photos = ? WHERE id = ?", (cnt, pid))

    conn.commit()
    conn.close()
    return {"status": "ok", "deleted_count": deleted_count}

@app.delete("/api/photos/{photo_id}")
def delete_single_photo(photo_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT project_id FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Photo not found")
    project_id = row["project_id"]
    cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    cursor.execute("SELECT COUNT(*) as cnt FROM photos WHERE project_id = ?", (project_id,))
    cnt = cursor.fetchone()["cnt"]
    cursor.execute("UPDATE projects SET total_photos = ? WHERE id = ?", (cnt, project_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "deleted_photo_id": photo_id}

@app.patch("/api/photos/{photo_id}/rating")
def update_photo_rating(photo_id: int, req: StarRatingRequest):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE photos SET star_rating = ? WHERE id = ?", (req.star_rating, photo_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "photo_id": photo_id, "star_rating": req.star_rating}

@app.patch("/api/photos/{photo_id}/edits")
def update_photo_edits(photo_id: int, req: EditParametersRequest):
    params_dict = req.dict()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, project_id FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Photo not found")

    cursor.execute("""
    UPDATE photos SET
        edit_params = ?,
        manual_override = 1,
        is_edited = 1
    WHERE id = ?
    """, (json.dumps(params_dict), photo_id))
    conn.commit()
    conn.close()

    # Pre-cache edited thumbnail for immediate UI update
    try:
        edit_obj = EditParameters.from_dict(params_dict)
        generate_edited_thumbnail(row["file_path"], row["project_id"], photo_id, edit_obj)
    except Exception:
        pass

    return {"status": "ok", "photo_id": photo_id, "edit_params": params_dict}

@app.post("/api/photos/{photo_id}/reset-edits")
def reset_photo_edits(photo_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT project_id FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()

    cursor.execute("""
    UPDATE photos SET
        edit_params = '{}',
        manual_override = 0,
        is_edited = 0
    WHERE id = ?
    """, (photo_id,))
    conn.commit()
    conn.close()

    if row:
        remove_edited_thumbnail(row["project_id"], photo_id)

    return {"status": "ok", "photo_id": photo_id, "message": "Edits reset to original"}

@app.post("/api/photos/{photo_id}/auto-edit")
def auto_edit_single(photo_id: int, preset_name: str = Query("Natural Wedding"), retouch_preset: str = Query("Natural")):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, project_id, scene_category, edit_params FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Photo not found")

    cv_img = load_image(row["file_path"], max_dim=800)
    params = editing_model.calculate_corrections(cv_img, preset_name=preset_name, scene_group=row["scene_category"], retouch_preset=retouch_preset)

    # Preserve existing manual heal spots if present
    if row["edit_params"]:
        try:
            existing_dict = json.loads(row["edit_params"])
            if existing_dict.get("heal_spots"):
                params.heal_spots = existing_dict["heal_spots"]
        except Exception:
            pass

    params_dict = params.to_dict()

    cursor.execute("""
    UPDATE photos SET
        edit_params = ?,
        is_edited = 1,
        manual_override = 0
    WHERE id = ?
    """, (json.dumps(params_dict), photo_id))
    conn.commit()
    conn.close()

    # Pre-cache edited thumbnail so it displays immediately
    try:
        generate_edited_thumbnail(row["file_path"], row["project_id"], photo_id, params)
    except Exception:
        pass

    return {"status": "ok", "photo_id": photo_id, "edit_params": params_dict}


# --- Image Serving & Dynamic Previews ---
@app.get("/api/photos/{photo_id}/thumbnail")
def get_photo_thumbnail(photo_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT thumbnail_path, file_path, project_id, is_edited, edit_params FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    # If photo has been edited, serve the edited thumbnail
    if row["is_edited"] == 1 and row["edit_params"]:
        try:
            params = EditParameters.from_dict(json.loads(row["edit_params"]))
            thumb_path = generate_edited_thumbnail(row["file_path"], row["project_id"], photo_id, params)
            return FileResponse(thumb_path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
        except Exception:
            pass

    thumb_path = row["thumbnail_path"]
    if not thumb_path or not os.path.exists(thumb_path):
        thumb_path = generate_thumbnail(row["file_path"], row["project_id"], photo_id)

    return FileResponse(thumb_path, media_type="image/jpeg")

@app.get("/api/photos/{photo_id}/original")
def get_photo_original(photo_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not os.path.exists(row["file_path"]):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(row["file_path"])

@app.get("/api/photos/{photo_id}/preview")
def get_photo_preview(photo_id: int):
    """
    Renders high-speed non-destructive preview with current edit parameters applied.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, edit_params FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    params_dict = json.loads(row["edit_params"]) if row["edit_params"] else {}
    params = EditParameters.from_dict(params_dict)

    edited_rgb = render_preview(row["file_path"], params, max_dim=2560)

    # Encode to JPEG in memory with high quality 95 for razor-sharp Retina clarity
    success, buffer = cv2.imencode(".jpg", cv2.cvtColor(edited_rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode preview image")

    return Response(content=buffer.tobytes(), media_type="image/jpeg")


# --- AI Skin Retouch ---
@app.get("/api/retouch/presets")
def get_retouch_presets():
    """Built-in AI Skin Retouch presets (Heal, Mattifier, Skin Mask, Skin Details, Imperfections, Skin Tone)."""
    return {"presets": list_retouch_presets(), "defaults": DEFAULT_RETOUCH}

@app.get("/api/photos/{photo_id}/retouch-mask")
def get_retouch_mask(photo_id: int, kind: str = Query("skin")):
    """Grayscale PNG of the skin / heal / shine mask for the 'Show mask' overlay."""
    if kind not in ("skin", "heal", "shine"):
        raise HTTPException(status_code=400, detail="kind must be skin, heal or shine")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, edit_params FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    params = EditParameters.from_dict(json.loads(row["edit_params"]) if row["edit_params"] else {})
    rt = resolve_retouch_params(params) or build_retouch_preset("Natural")
    rt = dict(rt)
    rt["enabled"] = True
    rgb = load_image(row["file_path"], max_dim=1600)
    _, res = retouch_image(rgb, rt, want_masks=True)
    mask = {"skin": res.skin_mask, "heal": res.heal_mask, "shine": res.shine_mask}[kind]
    if mask is None:
        mask = np.zeros(rgb.shape[:2], np.float32)
    if kind == "heal" and res.heal_mask is not None:
        mask = np.clip(mask * 3.0, 0.0, 1.0)
    ok, buf = cv2.imencode(".png", np.clip(mask * 255.0, 0, 255).astype(np.uint8))
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode mask")
    return Response(
        content=buf.tobytes(), media_type="image/png",
        headers={"Cache-Control": "no-cache", "X-Faces": str(res.faces), "X-Spots": str(res.spots),
                 "Access-Control-Expose-Headers": "X-Faces, X-Spots"}
    )


# --- Batch Processing Operations ---
@app.post("/api/projects/{project_id}/cull")
def start_culling(project_id: int):
    # Anti-tamper & Crack Protection Enforcement Guard
    allowed, msg = license_service.verify_operational_permission("CULL")
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)
    job_id = batch_manager.start_culling_job(project_id)
    return {"job_id": job_id, "status": "started"}

@app.post("/api/projects/{project_id}/recluster")
def recluster_project(project_id: int):
    """Re-clusters burst/duplicate groups using high-precision ZNCC engine and updates recommendations."""
    res = culling_service.recluster_project(project_id)
    return res

@app.post("/api/projects/{project_id}/auto-edit")
def start_auto_edit(project_id: int, req: AutoEditBatchRequest):
    allowed, msg = license_service.verify_operational_permission("AUTO_EDIT")
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)
    job_id = batch_manager.start_auto_edit_job(project_id, preset_name=req.preset_name, photo_ids=req.photo_ids, retouch_preset=req.retouch_preset)
    return {"job_id": job_id, "status": "started"}

@app.post("/api/projects/{project_id}/export")
def start_export(project_id: int, req: ExportRequest):
    # Anti-tamper & Crack Protection Enforcement Guard
    allowed, msg = license_service.verify_operational_permission("EXPORT")
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)
    job_id = batch_manager.start_export_job(
        project_id=project_id,
        output_folder=req.output_folder,
        jpeg_quality=req.jpeg_quality,
        max_resolution=req.max_resolution,
        rename_pattern=req.rename_pattern,
        categories=req.categories
    )
    return {"job_id": job_id, "status": "started"}

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    status = batch_manager.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status

@app.post("/api/jobs/{job_id}/pause")
def pause_job(job_id: str):
    batch_manager.pause_job(job_id)
    return {"status": "paused"}

@app.post("/api/jobs/{job_id}/resume")
def resume_job(job_id: str):
    batch_manager.resume_job(job_id)
    return {"status": "resumed"}

@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    batch_manager.cancel_job(job_id)
    return {"status": "cancelled"}

class OpenFolderRequest(BaseModel):
    folder_path: str

@app.post("/api/open-folder")
def open_system_folder(req: OpenFolderRequest):
    p = req.folder_path.strip()
    if not p:
        raise HTTPException(status_code=400, detail="Folder path is required")
    os.makedirs(p, exist_ok=True)
    import platform, subprocess
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", p], check=False)
        elif platform.system() == "Windows":
            os.startfile(p)
        else:
            subprocess.run(["xdg-open", p], check=False)
        return {"success": True, "message": f"Opened {p}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Licensing & payments: everything is decided by the online License Server.
# This app never holds a payment secret, coupon list or license-signing key.
# =========================================================================

class VerifyCouponRequest(BaseModel):
    code: str
    plan_id: str = "PRO"
    billing_cycle: str = "yearly"
    currency: str = "INR"

class ActivateLicenseRequest(BaseModel):
    license_key: str
    user_name: Optional[str] = ""
    user_email: Optional[str] = ""

class CreateOrderRequest(BaseModel):
    plan_id: str
    billing_cycle: str = "yearly"
    customer_name: str = ""
    customer_email: str = ""
    customer_phone: Optional[str] = ""
    coupon_code: Optional[str] = None
    currency: str = "INR"

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

@app.get("/api/license/status")
def get_license_status():
    return license_service.get_license_status()

@app.post("/api/license/refresh")
def refresh_license():
    license_service.refresh()
    picked = license_service.check_pending_order()
    return picked or license_service.get_license_status()

@app.get("/api/license/profile")
def get_license_profile():
    return license_service.get_profile()

@app.get("/api/license/plans")
def get_license_plans():
    return license_service.get_plans()

@app.post("/api/license/verify-coupon")
def verify_coupon(req: VerifyCouponRequest):
    return license_service.verify_coupon(req.code, req.plan_id, req.billing_cycle, req.currency)

@app.post("/api/license/activate")
def activate_license(req: ActivateLicenseRequest):
    success, msg, data = license_service.activate_key(req.license_key, req.user_name or "", req.user_email or "")
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg, "license": data}

@app.post("/api/license/deactivate")
def deactivate_license():
    success, msg = license_service.deactivate()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg, "license": license_service.get_license_status()}

@app.post("/api/payment/create-order")
def create_payment_order(req: CreateOrderRequest):
    from backend.services.license_service import LicenseServerError
    try:
        return license_service.create_order(req.plan_id, req.billing_cycle, req.customer_name, req.customer_email,
                                            req.customer_phone or "", req.coupon_code, req.currency)
    except LicenseServerError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/payment/verify-payment")
def verify_payment_order(req: VerifyPaymentRequest):
    success, msg, data = license_service.verify_payment(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg, "license": data}



# --- Client Proofing & Online Selection Endpoints ---
class CreateGalleryRequest(BaseModel):
    project_id: int
    title: str
    client_name: Optional[str] = ""
    client_pin: Optional[str] = ""
    photo_ids: Optional[List[int]] = None
    watermark_enabled: bool = True
    watermark_text: str = "PROOF ONLY - Ai PhotoFlow"

class SelectPhotoRequest(BaseModel):
    photo_id: int
    selection: str
    note: Optional[str] = ""

class SubmitGalleryRequest(BaseModel):
    notes: Optional[str] = ""

class ExportClientSelectedRequest(BaseModel):
    project_id: int
    destination_folder: str
    gallery_uuid: Optional[str] = None

@app.post("/api/proofing/create")
def create_client_gallery(req: CreateGalleryRequest):
    try:
        res = proofing_service.create_gallery(
            project_id=req.project_id,
            title=req.title,
            client_name=req.client_name or "",
            client_pin=req.client_pin or "",
            photo_ids=req.photo_ids,
            watermark_enabled=req.watermark_enabled,
            watermark_text=req.watermark_text
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/proofing/galleries/{project_id}")
def list_client_galleries(project_id: int):
    return proofing_service.list_project_galleries(project_id)

@app.get("/gallery/{gallery_uuid}", response_class=HTMLResponse)
def view_client_gallery(gallery_uuid: str, pin: str = Query("")):
    try:
        data = proofing_service.get_gallery_public(gallery_uuid, pin)
        tpl_path = os.path.join(os.path.dirname(__file__), "templates", "proofing_gallery.html")
        if not os.path.exists(tpl_path):
            raise HTTPException(status_code=404, detail="Gallery template not found")
        with open(tpl_path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("__GALLERY_DATA_JSON__", json.dumps(data))
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/proofing/gallery/{gallery_uuid}")
def get_gallery_data(gallery_uuid: str, pin: str = Query("")):
    try:
        return proofing_service.get_gallery_public(gallery_uuid, pin)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/proofing/gallery/{gallery_uuid}/select")
def select_gallery_photo(gallery_uuid: str, req: SelectPhotoRequest):
    try:
        return proofing_service.update_photo_selection(
            gallery_uuid=gallery_uuid,
            photo_id=req.photo_id,
            selection=req.selection,
            note=req.note or ""
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/proofing/gallery/{gallery_uuid}/submit")
def submit_gallery_selection(gallery_uuid: str, req: SubmitGalleryRequest):
    try:
        return proofing_service.submit_gallery(
            gallery_uuid=gallery_uuid,
            client_notes=req.notes or ""
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/proofing/preview/{gallery_uuid}/{photo_id}")
def get_proofing_preview(gallery_uuid: str, photo_id: int):
    preview_file = proofing_service.ensure_single_preview(gallery_uuid, photo_id)
    if not preview_file or not os.path.exists(preview_file):
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(preview_file, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/proofing/thumb/{gallery_uuid}/{photo_id}")
def get_proofing_thumb(gallery_uuid: str, photo_id: int):
    thumb_file = proofing_service.ensure_single_thumb(gallery_uuid, photo_id)
    if not thumb_file or not os.path.exists(thumb_file):
        thumb_file = proofing_service.ensure_single_preview(gallery_uuid, photo_id)
    if not thumb_file or not os.path.exists(thumb_file):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_file, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})

@app.post("/api/proofing/export-selected")
def export_client_selected_photos(req: ExportClientSelectedRequest):
    try:
        res = proofing_service.export_client_selected(
            project_id=req.project_id,
            destination_folder=req.destination_folder,
            gallery_uuid=req.gallery_uuid
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class ExportStandaloneGalleryRequest(BaseModel):
    gallery_uuid: str
    destination_folder: str

@app.post("/api/proofing/export-standalone")
def export_standalone_web_gallery(req: ExportStandaloneGalleryRequest):
    try:
        res = proofing_service.export_standalone_gallery(
            gallery_uuid=req.gallery_uuid,
            destination_folder=req.destination_folder
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Master Hosting (photographer's cPanel domain) ---
class HostingCheckRequest(BaseModel):
    url: Optional[str] = None

@app.post("/api/proofing/hosting/check")
def check_master_hosting(req: HostingCheckRequest):
    return hosting_sync_service.check(req.url, use_cache=False)

@app.post("/api/proofing/gallery/{gallery_uuid}/hosting-sync")
def resync_gallery_to_hosting(gallery_uuid: str):
    base = hosting_sync_service.get_master_url()
    if not base:
        raise HTTPException(status_code=400, detail="Master Hosting URL is not set")
    hosting_sync_service.mark_pending(gallery_uuid, base)
    hosting_sync_service.sync_gallery_async(gallery_uuid)
    return {"status": "UPLOADING", "hosting_url": base}

# --- Mobile Tunnel & Network Sharing Endpoints ---
@app.get("/api/proofing/network-info")
def get_network_info():
    info = tunnel_service.get_info()
    info["master_hosting"] = hosting_sync_service.check()
    return info

@app.post("/api/proofing/tunnel/start")
def start_public_tunnel():
    return tunnel_service.start_tunnel()

@app.post("/api/proofing/tunnel/stop")
def stop_public_tunnel():
    tunnel_service.stop_tunnel()
    return {"status": "OFFLINE"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)


