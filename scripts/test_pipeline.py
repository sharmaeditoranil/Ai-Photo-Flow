"""
Verification script for complete Ai PhotoFlow pipeline.
"""
import os
import sys
import json

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.culling_service import CullingService
from backend.services.batch_service import BatchManager
from backend.db.database import get_connection

def test_pipeline():
    culling = CullingService()
    batch_mgr = BatchManager()

    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_wedding_photos")
    print(f"Scanning sample directory: {sample_dir}")

    # 1. Scan folder
    res = culling.scan_folder(sample_dir, "Wedding – Rahul & Priya")
    print("Scan result:", res)
    project_id = res["project_id"]

    # 2. Run Culling synchronously to verify
    print("\nRunning AI Culling...")
    def log_cb(curr, tot, msg, pct):
        print(f"Progress [{pct}%]: {curr}/{tot} - {msg}")

    cull_res = culling.process_culling(project_id, progress_callback=log_cb)
    print("Culling complete:", cull_res)

    # 3. Check DB results
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT filename, ai_score, sharpness_score, blur_detected, faces_count, eyes_status,
           exposure_status, duplicate_group_id, ai_recommendation, ai_confidence, scene_category
    FROM photos WHERE project_id = ?
    ORDER BY ai_score DESC
    """, (project_id,))

    rows = c.fetchall()
    print(f"\n--- AI Culling Results ({len(rows)} photos) ---")
    for r in rows:
        print(f"File: {r['filename']:<32} | Score: {r['ai_score']:<5} | Sharp: {r['sharpness_score']:<5} | "
              f"Blur: {r['blur_detected']} | Eyes: {r['eyes_status']:<7} | Exp: {r['exposure_status']:<14} | "
              f"Dup: {str(r['duplicate_group_id']):<9} | Rec: {r['ai_recommendation']:<8} | Scene: {r['scene_category']}")

    conn.close()

if __name__ == "__main__":
    test_pipeline()
