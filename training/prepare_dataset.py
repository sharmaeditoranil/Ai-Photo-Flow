"""
Dataset Preparation & Synthetic Blemish Generator
Aligns before/after portrait pairs, normalizes face scale, and extracts 512x512 patches.
Also synthesizes procedural blemishes (acne, pimples, redness) for data augmentation.
License: MIT / Apache-2.0 Permissive.
"""
import os
import glob
import random
import cv2
import numpy as np
from typing import List, Tuple

TARGET_FACE_HEIGHT = 384.0
PATCH_SIZE = 512

def detect_face_box(img_bgr: np.ndarray) -> Tuple[int, int, int, int]:
    """Detects primary face bounding box (x, y, w, h)."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
    if len(faces) > 0:
        return max(faces, key=lambda b: b[2] * b[3])
    # Fallback to center box
    h, w = img_bgr.shape[:2]
    return int(w * 0.25), int(h * 0.2), int(w * 0.5), int(h * 0.5)

def synthesize_blemish(patch: np.ndarray, num_spots: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Pastes procedural blemishes onto clean skin patch.
    Returns: (augmented_patch, blemish_mask)
    """
    h, w = patch.shape[:2]
    aug = patch.copy()
    mask = np.zeros((h, w), dtype=np.uint8)

    for _ in range(num_spots):
        cx = random.randint(30, w - 30)
        cy = random.randint(30, h - 30)
        radius = random.randint(3, 14)

        # Draw red inflamed core
        spot_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(spot_mask, (cx, cy), radius, 255, -1)
        spot_mask_blur = cv2.GaussianBlur(spot_mask, (radius * 2 | 1, radius * 2 | 1), radius * 0.6)

        # Chrominance redness boost
        alpha = (spot_mask_blur.astype(np.float32) / 255.0)[:, :, np.newaxis]
        red_tint = np.array([random.randint(40, 90), random.randint(60, 110), random.randint(180, 240)], dtype=np.float32)
        aug = (aug.astype(np.float32) * (1.0 - alpha * 0.7) + red_tint * (alpha * 0.7)).astype(np.uint8)
        mask = np.maximum(mask, spot_mask)

    return aug, mask

def process_portrait_pairs(
    raw_dir: str,
    retouched_dir: str,
    output_dir: str,
    patches_per_image: int = 8
):
    """
    Aligns pairs of before / after images, normalizes scale, and extracts 512x512 patches.
    """
    os.makedirs(os.path.join(output_dir, "input"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "target"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "mask"), exist_ok=True)

    raw_files = sorted(glob.glob(os.path.join(raw_dir, "*.[jJ][pP][gG]")) + glob.glob(os.path.join(raw_dir, "*.[pP][nN][gG]")))
    print(f"Found {len(raw_files)} portraits in {raw_dir}")

    count = 0
    for raw_path in raw_files:
        base = os.path.basename(raw_path)
        retouched_path = os.path.join(retouched_dir, base)
        if not os.path.exists(retouched_path):
            continue

        img_raw = cv2.imread(raw_path)
        img_ret = cv2.imread(retouched_path)
        if img_raw is None or img_ret is None or img_raw.shape != img_ret.shape:
            continue

        # Scale normalization relative to face height
        fx, fy, fw, fh = detect_face_box(img_raw)
        scale = TARGET_FACE_HEIGHT / float(max(10, fh))
        new_w = int(img_raw.shape[1] * scale)
        new_h = int(img_raw.shape[0] * scale)

        scaled_raw = cv2.resize(img_raw, (new_w, new_h), interpolation=cv2.INTER_AREA)
        scaled_ret = cv2.resize(img_ret, (new_w, new_h), interpolation=cv2.INTER_AREA)

        sh, sw = scaled_raw.shape[:2]
        if sh < PATCH_SIZE or sw < PATCH_SIZE:
            continue

        for i in range(patches_per_image):
            y = random.randint(0, sh - PATCH_SIZE)
            x = random.randint(0, sw - PATCH_SIZE)

            crop_raw = scaled_raw[y:y+PATCH_SIZE, x:x+PATCH_SIZE]
            crop_ret = scaled_ret[y:y+PATCH_SIZE, x:x+PATCH_SIZE]

            # Residual difference mask
            diff = cv2.absdiff(crop_raw, crop_ret)
            diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, diff_mask = cv2.threshold(diff_gray, 8, 255, cv2.THRESH_BINARY)

            idx_str = f"{count:06d}"
            cv2.imwrite(os.path.join(output_dir, "input", f"{idx_str}.png"), crop_raw)
            cv2.imwrite(os.path.join(output_dir, "target", f"{idx_str}.png"), crop_ret)
            cv2.imwrite(os.path.join(output_dir, "mask", f"{idx_str}.png"), diff_mask)
            count += 1

    print(f"Generated {count} scale-normalized 512x512 training patches in {output_dir}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw_portraits")
    parser.add_argument("--retouched", default="data/retouched_portraits")
    parser.add_argument("--out", default="data/patches")
    args = parser.parse_args()
    process_portrait_pairs(args.raw, args.retouched, args.out)
