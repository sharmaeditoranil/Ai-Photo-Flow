"""
SQLite Database Layer for Ai PhotoFlow
Manages projects, photos, AI evaluation metrics, edit parameters, and batch processing jobs.
"""
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

APP_DATA_DIR = os.path.expanduser("~/.photoflow")
os.makedirs(APP_DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(APP_DATA_DIR, "photoflow.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=60.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Projects
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        folder_path TEXT NOT NULL,
        total_photos INTEGER DEFAULT 0,
        status TEXT DEFAULT 'READY',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Photos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER DEFAULT 0,
        width INTEGER DEFAULT 0,
        height INTEGER DEFAULT 0,
        file_format TEXT NOT NULL,
        thumbnail_path TEXT,
        exif_date TEXT,
        ai_score REAL DEFAULT 0.0,
        sharpness_score REAL DEFAULT 0.0,
        blur_detected INTEGER DEFAULT 0,
        faces_count INTEGER DEFAULT 0,
        eyes_status TEXT DEFAULT 'NO_FACE',
        exposure_status TEXT DEFAULT 'GOOD',
        exposure_score REAL DEFAULT 100.0,
        duplicate_group_id TEXT,
        ai_recommendation TEXT DEFAULT 'SELECTED',
        ai_confidence REAL DEFAULT 85.0,
        user_selection TEXT DEFAULT 'UNRATED',
        star_rating INTEGER DEFAULT 0,
        scene_category TEXT DEFAULT 'Mandap & Ceremony',
        edit_params TEXT DEFAULT '{}',
        manual_override INTEGER DEFAULT 0,
        is_edited INTEGER DEFAULT 0,
        dhash TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Performance indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_project_id ON photos(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_proj_file ON photos(project_id, file_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_folder ON projects(folder_path)")

    # Batch Jobs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batch_jobs (
        id TEXT PRIMARY KEY,
        project_id INTEGER NOT NULL,
        job_type TEXT NOT NULL,
        status TEXT DEFAULT 'IDLE',
        progress_current INTEGER DEFAULT 0,
        progress_total INTEGER DEFAULT 0,
        progress_pct REAL DEFAULT 0.0,
        current_file TEXT DEFAULT '',
        logs TEXT DEFAULT '[]',
        error_message TEXT DEFAULT '',
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP
    )
    """)

    # App Settings & API Keys
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Client Proofing Migrations for Photos table
    try:
        cursor.execute("ALTER TABLE photos ADD COLUMN client_selection TEXT DEFAULT 'UNRATED'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE photos ADD COLUMN client_note TEXT DEFAULT ''")
    except Exception:
        pass

    # Client Proofing Galleries Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS client_galleries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        gallery_uuid TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        client_name TEXT DEFAULT '',
        client_pin TEXT DEFAULT '',
        total_photos INTEGER DEFAULT 0,
        selected_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ACTIVE',
        watermark_enabled INTEGER DEFAULT 1,
        watermark_text TEXT DEFAULT 'PROOF ONLY - Ai PhotoFlow',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        submitted_at TIMESTAMP
    )
    """)

    # Face-first culling data (focus of the main face, close-up / emotion flags) for re-clustering
    for col_sql in ("ALTER TABLE photos ADD COLUMN face_sharpness REAL DEFAULT NULL",
                    "ALTER TABLE photos ADD COLUMN face_close_up INTEGER DEFAULT 0",
                    "ALTER TABLE photos ADD COLUMN face_emotion INTEGER DEFAULT 0",
                    "ALTER TABLE photos ADD COLUMN face_brightness REAL DEFAULT NULL",
                    "ALTER TABLE photos ADD COLUMN face_sharpness_hires REAL DEFAULT NULL",
                    "ALTER TABLE photos ADD COLUMN face_focus REAL DEFAULT NULL"):
        try:
            cursor.execute(col_sql)
        except Exception:
            pass

    # The separate "Selected" culling category was removed: those photos belong to AI Best
    try:
        cursor.execute("UPDATE photos SET ai_recommendation = 'BEST' WHERE ai_recommendation = 'SELECTED'")
        cursor.execute("UPDATE photos SET user_selection = 'BEST' WHERE user_selection = 'SELECTED'")
    except Exception:
        pass

    # Payment gateway keys now live only on the online License Server; never keep secrets in the app DB
    try:
        cursor.execute("DELETE FROM app_settings WHERE key IN ('razorpay_key_id', 'razorpay_key_secret', 'razorpay_enabled')")
    except Exception:
        pass

    # Master Hosting (cPanel) sync state per gallery
    for col_sql in (
        "ALTER TABLE client_galleries ADD COLUMN hosting_url TEXT DEFAULT ''",
        "ALTER TABLE client_galleries ADD COLUMN hosting_status TEXT DEFAULT ''",
        "ALTER TABLE client_galleries ADD COLUMN hosting_error TEXT DEFAULT ''",
        "ALTER TABLE client_galleries ADD COLUMN hosting_uploaded INTEGER DEFAULT 0",
    ):
        try:
            cursor.execute(col_sql)
        except Exception:
            pass

    # Client Gallery Photos Mapping Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS client_gallery_photos (
        gallery_uuid TEXT NOT NULL,
        photo_id INTEGER NOT NULL,
        client_selection TEXT DEFAULT 'UNRATED',
        client_note TEXT DEFAULT '',
        PRIMARY KEY (gallery_uuid, photo_id)
    )
    """)

    conn.commit()
    conn.close()

# Initialize upon module import
init_db()
