"""
Benchmark script to measure real-world AI Culling speed and AI Editing pipeline speed.
"""
import os
import sys
import time
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.culling_service import CullingService
from backend.services.batch_service import BatchManager
from backend.core.editing_model import IndianWeddingEditingModel
from backend.services.image_service import load_image, apply_edit_pipeline

def run_benchmarks():
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_wedding_photos")
    photo_files = [os.path.join(sample_dir, f) for f in os.listdir(sample_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.arw', '.cr3'))]
    photo_files.sort()
    n_photos = len(photo_files)

    print(f"==================================================")
    print(f"BENCHMARKING AI PHOTO FLOW SPEED ON {n_photos} WEDDING PHOTOS")
    print(f"==================================================\n")

    # 1. Benchmark Culling Speed
    print("--- 1. BENCHMARKING AI CULLING SPEED ---")
    culling = CullingService()
    scan_res = culling.scan_folder(sample_dir, "Speed_Benchmark_Project")
    pid = scan_res["project_id"]

    t0_cull = time.perf_counter()
    cull_res = culling.process_culling(pid)
    t1_cull = time.perf_counter()

    cull_total_time = t1_cull - t0_cull
    cull_per_photo_ms = (cull_total_time / n_photos) * 1000.0
    cull_photos_per_sec = n_photos / cull_total_time
    cull_1000_photos_min = (1000.0 / cull_photos_per_sec) / 60.0

    print(f"Total Culling Time: {cull_total_time:.2f} seconds ({n_photos} photos)")
    print(f"Culling Speed per photo: {cull_per_photo_ms:.1f} ms / photo")
    print(f"Culling Throughput: {cull_photos_per_sec:.1f} photos / second")
    print(f"Projected 1,000 photos culling time: {cull_1000_photos_min:.1f} minutes\n")

    # 2. Benchmark AI Auto-Correction Calculation Speed
    print("--- 2. BENCHMARKING AI AUTO-EDIT CALCULATION SPEED ---")
    editing_model = IndianWeddingEditingModel()
    loaded_images = [load_image(f, max_dim=1000) for f in photo_files]

    t0_calc = time.perf_counter()
    params_list = []
    masks_list = []
    for img in loaded_images:
        p, (s_mask, s_info) = editing_model.calculate_corrections(img, preset_name="Natural Wedding", return_mask=True, calibrate=False)
        params_list.append(p)
        masks_list.append((s_mask, s_info))
    t1_calc = time.perf_counter()

    calc_total_time = t1_calc - t0_calc
    calc_per_photo_ms = (calc_total_time / n_photos) * 1000.0
    calc_photos_per_sec = n_photos / calc_total_time

    print(f"Total AI Edit Calculation Time: {calc_total_time:.2f} seconds ({n_photos} photos)")
    print(f"Edit Calculation Speed per photo: {calc_per_photo_ms:.1f} ms / photo")
    print(f"Edit Calculation Throughput: {calc_photos_per_sec:.1f} photos / second\n")

    # 3. Benchmark Full 16-Stage Editing Pipeline Rendering Speed (1000px Preview)
    print("--- 3. BENCHMARKING FULL RENDERING PIPELINE SPEED (1000px Preview) ---")
    t0_render = time.perf_counter()
    rendered_images = []
    for img, p, (s_mask, s_info) in zip(loaded_images, params_list, masks_list):
        out = apply_edit_pipeline(img.copy(), p, cached_subject_mask=s_mask, cached_subject_info=s_info)
        rendered_images.append(out)
    t1_render = time.perf_counter()

    render_total_time = t1_render - t0_render
    render_per_photo_ms = (render_total_time / n_photos) * 1000.0
    render_photos_per_sec = n_photos / render_total_time
    render_1000_photos_min = (1000.0 / render_photos_per_sec) / 60.0

    print(f"Total Rendering Time: {render_total_time:.2f} seconds ({n_photos} photos)")
    print(f"Rendering Speed per photo: {render_per_photo_ms:.1f} ms / photo")
    print(f"Rendering Throughput: {render_photos_per_sec:.1f} photos / second")
    print(f"Projected 1,000 photos batch edit render time: {render_1000_photos_min:.1f} minutes\n")

    # 4. Total Combined End-to-End Speed
    total_pipeline_ms = cull_per_photo_ms + calc_per_photo_ms + render_per_photo_ms
    print("--- 4. SUMMARY SPEED PROFILE ---")
    print(f"Single photo Culling: ~{cull_per_photo_ms:.0f} ms")
    print(f"Single photo AI Edit Calculation: ~{calc_per_photo_ms:.0f} ms")
    print(f"Single photo Full Edit Rendering: ~{render_per_photo_ms:.0f} ms")
    print(f"Total Edit Pipeline: ~{(calc_per_photo_ms + render_per_photo_ms):.0f} ms / photo")
    print(f"1,000 Photos Culling Time: ~{cull_1000_photos_min:.1f} minutes")
    print(f"1,000 Photos Auto-Editing Time: ~{render_1000_photos_min:.1f} minutes")

if __name__ == "__main__":
    run_benchmarks()
