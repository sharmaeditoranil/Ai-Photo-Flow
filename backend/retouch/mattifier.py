"""
AI Mattifier: removes oily shine / flash hot-spots on every face (forehead, nose, cheeks, chin).

Shine = skin that is brighter than the person's local skin base AND washed-out (lower chroma) AND
smooth. Correction works on the low-frequency layer only: lightness is pulled down toward the
surrounding non-shiny skin (keeping a "natural sheen" percentage) and the chroma that the specular
highlight washed out is restored. Pores (high frequency) are kept. Eyes (catch-lights), lips,
teeth and jewellery are outside the face domain and never touched.
"""
from typing import List

import cv2
import numpy as np

from backend.retouch import geometry
from backend.retouch.faces import Face
from backend.retouch.filters import gaussian, masked_gaussian, smoothstep

NORM_IOD = 120.0


def mattify(lab: np.ndarray, domain: np.ndarray, faces: List[Face], strength: float, keep_sheen: float,
            texture_preserve: float, opacity: float) -> np.ndarray:
    """In-place shine removal on lab (float32 Lab). Returns the native shine mask (0..1)."""
    H, W = lab.shape[:2]
    shine_full = np.zeros((H, W), np.float32)
    k_amt = (strength / 100.0) * (opacity / 100.0)
    if k_amt <= 0.0:
        return shine_full
    keep = keep_sheen / 100.0

    for face in faces:
        if face.iod < 20.0:
            continue
        center, (au, av) = geometry.face_oval_params(face)
        R = max(au, av) * 1.15 * face.iod
        x0, y0 = int(max(0, center[0] - R)), int(max(0, center[1] - R))
        x1, y1 = int(min(W, center[0] + R)), int(min(H, center[1] + R))
        if x1 - x0 < 16 or y1 - y0 < 16:
            continue
        s = min(1.0, NORM_IOD / face.iod)
        iod_n = face.iod * s
        cw, ch = max(8, int(round((x1 - x0) * s))), max(8, int(round((y1 - y0) * s)))
        crop = cv2.resize(lab[y0:y1, x0:x1], (cw, ch), interpolation=cv2.INTER_AREA)
        M = cv2.resize(domain[y0:y1, x0:x1], (cw, ch), interpolation=cv2.INTER_AREA)
        if M.sum() < 100:
            continue

        L, A, B = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
        C = np.hypot(A, B)
        Lsm = gaussian(L, 0.03 * iod_n)
        Csm = gaussian(C, 0.03 * iod_n)

        # Base of NON-shiny skin: iteratively exclude bright pixels from the estimate.
        # A mid-size base keeps broad lighting (lit side vs shadow side) out of the shine map.
        # Highlights are clipped (not removed) before re-estimating, so the base cannot drift
        # down into the shadows the way plain bright-pixel exclusion does.
        sig_b = 0.15 * iod_n
        base_L = masked_gaussian(Lsm, M, sig_b)
        for _ in range(3):
            base_L = masked_gaussian(np.minimum(Lsm, base_L + 3.0), M, sig_b)
        Mb = M * (Lsm < base_L + 3.0)
        A_sm = gaussian(A, 0.03 * iod_n)
        B_sm = gaussian(B, 0.03 * iod_n)
        base_A = masked_gaussian(A_sm, Mb, sig_b)
        base_B = masked_gaussian(B_sm, Mb, sig_b)
        base_C = np.maximum(np.hypot(base_A, base_B), 3.0)

        excess = Lsm - base_L
        # Specular reflection adds white light: chroma falls below what that lightness would
        # have on lit skin (lit skin keeps C ~ L^0.6). Plain lighting does not desaturate.
        expected_C = base_C * np.power(np.clip(Lsm / np.maximum(base_L, 1.0), 0.2, 3.0), 0.6)
        desat = np.clip(1.0 - Csm / expected_C, 0.0, 1.0)
        # Smooth structure: specular sheen is soft; sharp bright details (jewel sparkle,
        # white makeup dots, teeth edges) have strong fine-scale contrast
        fine = gaussian(np.abs(L - Lsm), 0.03 * iod_n)
        smooth = 1.0 - smoothstep(fine, 2.5, 6.0)
        shine = smoothstep(excess, 2.0, 8.0) * smoothstep(desat, 0.15, 0.40) * smooth
        shine = gaussian(shine * M, 0.02 * iod_n) * M

        if float(shine.max()) < 0.05:
            continue

        k = k_amt * shine
        dL = -np.clip(excess, 0.0, 15.0) * (1.0 - keep) * k
        # Restore the chroma the highlight washed out (same hue as the surrounding skin)
        ratio = np.clip(base_C / np.maximum(np.hypot(A_sm, B_sm), 1.0), 1.0, 1.6)
        c_k = k * (1.0 - 0.5 * keep) * desat
        dA = A_sm * (ratio - 1.0) * c_k
        dB = B_sm * (ratio - 1.0) * c_k

        # Back to native resolution (these maps are smooth)
        nw, nh = x1 - x0, y1 - y0
        dL_n = cv2.resize(dL, (nw, nh), interpolation=cv2.INTER_LINEAR)
        dA_n = cv2.resize(dA, (nw, nh), interpolation=cv2.INTER_LINEAR)
        dB_n = cv2.resize(dB, (nw, nh), interpolation=cv2.INTER_LINEAR)
        sh_n = cv2.resize(shine, (nw, nh), interpolation=cv2.INTER_LINEAR)

        region = lab[y0:y1, x0:x1]
        region[:, :, 0] += dL_n
        region[:, :, 1] += dA_n
        region[:, :, 2] += dB_n

        # Specular areas show exaggerated pore contrast; soften it a little (texturePreserve)
        tex_k = (1.0 - texture_preserve / 100.0) * 0.6 * k_amt
        if tex_k > 0.0:
            Ln = region[:, :, 0]
            hp = Ln - cv2.GaussianBlur(Ln, (0, 0), max(0.8, 0.008 * face.iod))
            region[:, :, 0] = Ln - hp * sh_n * tex_k

        shine_full[y0:y1, x0:x1] = np.maximum(shine_full[y0:y1, x0:x1], sh_n)
    return shine_full
