"""
Skin Imperfections (even skin tone, redness / yellow blotches, eye bags) and Skin Tone adjustments.
Both work in CIELAB and only through the skin mask.
"""
from typing import List

import cv2
import numpy as np

from backend.retouch import geometry
from backend.retouch.faces import Face
from backend.retouch.filters import gaussian, masked_gaussian, smoothstep


def even_tone(lab: np.ndarray, skin: np.ndarray, faces: List[Face], p: dict):
    master = float(p.get("evenTone", 0)) / 100.0
    eye_bags = float(p.get("eyeBags", 0)) / 100.0
    if (master <= 0.0 and eye_bags <= 0.0) or not faces:
        return
    ref_iod = faces[0].iod
    H, W = lab.shape[:2]
    m = (skin > 0.3).astype(np.float32)

    if master > 0.0 and np.any(m):
        balance = float(p.get("balance", 0)) / 100.0
        w_red = min(1.0, 1.0 - balance)
        w_yel = min(1.0, 1.0 + balance)
        k_red = master * float(p.get("redness", 100)) / 100.0 * w_red
        k_yel = master * float(p.get("yellow", 100)) / 100.0 * w_yel
        k_rb = master * float(p.get("redBrightness", 50)) / 100.0 * w_red
        k_yb = master * float(p.get("yellowBrightness", 0)) / 100.0 * w_yel

        sig_avg = 0.25 * ref_iod
        L, A, B = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
        avg_L = masked_gaussian(L, m, sig_avg)
        avg_A = masked_gaussian(A, m, sig_avg)
        avg_B = masked_gaussian(B, m, sig_avg)
        sm = max(0.8, 0.01 * ref_iod)
        dA = gaussian(A, sm) - avg_A
        dB = gaussian(B, sm) - avg_B
        red = np.maximum(dA, 0.0)
        yel = np.maximum(dB, 0.0)
        darker = np.maximum(avg_L - gaussian(L, sm), 0.0)

        newA = A - red * k_red * skin
        newB = B - yel * k_yel * skin
        lift = (darker * smoothstep(red, 0.5, 6.0) * k_rb + darker * smoothstep(yel, 0.5, 6.0) * k_yb) * skin
        lab[:, :, 0] = L + np.minimum(lift, 10.0)
        lab[:, :, 1] = newA
        lab[:, :, 2] = newB

    if eye_bags > 0.0:
        for f in faces:
            if f.iod < 30:
                continue
            R = int(1.0 * f.iod)
            cx, cy = f.origin
            x0, y0 = int(max(0, cx - 1.2 * R)), int(max(0, cy - 0.6 * R))
            x1, y1 = int(min(W, cx + 1.2 * R)), int(min(H, cy + 1.2 * R))
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue
            fl = f.scaled(1.0, -x0, -y0)
            crescent = np.zeros((y1 - y0, x1 - x0), np.float32)
            geometry.draw_eyebags(crescent, fl)
            eyes = np.zeros_like(crescent)
            for eye in (fl.landmarks[0], fl.landmarks[1]):
                cv2.ellipse(eyes, (int(eye[0]), int(eye[1])), (int(0.36 * f.iod), int(0.21 * f.iod)), fl.angle_deg, 0, 360, 1.0, -1)
            crescent = gaussian(crescent * (1.0 - eyes), 0.06 * f.iod) * (1.0 - gaussian(eyes, 0.02 * f.iod))
            region = lab[y0:y1, x0:x1]
            sk = skin[y0:y1, x0:x1]
            wgt = np.clip(crescent * 1.6, 0, 1) * sk
            if wgt.max() < 0.02:
                continue
            # Cheek reference just below the crescent
            cheek = np.zeros_like(crescent)
            for eye in (fl.landmarks[0], fl.landmarks[1]):
                c = eye + f.iod * 0.62 * fl.uy
                cv2.circle(cheek, (int(c[0]), int(c[1])), max(2, int(0.12 * f.iod)), 1.0, -1)
            cheek *= (sk > 0.5)
            if cheek.sum() < 5:
                continue
            ref_L = float(np.median(region[:, :, 0][cheek > 0]))
            ref_A = float(np.median(region[:, :, 1][cheek > 0]))
            ref_B = float(np.median(region[:, :, 2][cheek > 0]))
            Lr = region[:, :, 0]
            low = gaussian(Lr, 0.05 * f.iod)
            lift = np.clip(ref_L - low, 0.0, 18.0) * wgt * eye_bags * 0.85
            region[:, :, 0] = Lr + lift
            k = wgt * eye_bags * 0.5
            region[:, :, 1] += (ref_A - gaussian(region[:, :, 1], 0.05 * f.iod)) * k
            region[:, :, 2] += (ref_B - gaussian(region[:, :, 2], 0.05 * f.iod)) * k


def skin_tone(lab: np.ndarray, skin: np.ndarray, p: dict):
    hue = float(p.get("hue", 0))
    sat = float(p.get("saturation", 0))
    bri = float(p.get("brightness", 0))
    con = float(p.get("contrast", 0))
    sha = float(p.get("shadows", 0))
    hig = float(p.get("highlights", 0))
    if max(abs(hue), abs(sat), abs(bri), abs(con), abs(sha), abs(hig)) < 0.5:
        return
    m = skin if p.get("useSkinMask", True) else np.ones(lab.shape[:2], np.float32)
    L, A, B = lab[:, :, 0].copy(), lab[:, :, 1].copy(), lab[:, :, 2].copy()
    sel = m > 0.3
    mean_L = float(np.mean(L[sel])) if np.any(sel) else 55.0

    if abs(hue) >= 0.5 or abs(sat) >= 0.5:
        C = np.hypot(A, B)
        h = np.arctan2(B, A) + np.radians(hue / 100.0 * 30.0)
        C = C * max(0.0, 1.0 + sat / 100.0)
        A, B = C * np.cos(h), C * np.sin(h)
    if abs(bri) >= 0.5:
        L = L + bri / 100.0 * 15.0
    if abs(con) >= 0.5:
        L = mean_L + (L - mean_L) * (1.0 + con / 100.0 * 0.5)
    if abs(sha) >= 0.5:
        L = L + sha / 100.0 * 15.0 * (1.0 - smoothstep(L, 10.0, mean_L))
    if abs(hig) >= 0.5:
        L = L + hig / 100.0 * 12.0 * smoothstep(L, mean_L, 95.0)

    lab[:, :, 0] += (L - lab[:, :, 0]) * m
    lab[:, :, 1] += (A - lab[:, :, 1]) * m
    lab[:, :, 2] += (B - lab[:, :, 2]) * m
