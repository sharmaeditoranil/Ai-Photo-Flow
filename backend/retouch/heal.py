"""
AI Heal: automatic removal of pimples, acne, small dark/red spots on FACE skin only.

Detection runs on a scale-normalised copy of each face (eye distance = 170 px), so the same face
gives the same spots in the 1400 px thumbnail, the 2560 px preview and the full-resolution export.
A candidate is healed only if it passes every safety check:
  - it lies completely inside the retouchable face domain (never eyes, brows, lips, nostrils,
    hairline, beard, bindi or jewellery, which are excluded from the domain),
  - it is a compact, round blob (lines such as hair strands, wrinkles and lash shadows are rejected),
  - it stands out from that person's own pore texture (robust statistics per face),
  - its surroundings are calm skin (no strong structure in the ring around it),
  - large, very dark, non-red spots (moles / beauty marks) are kept.
Repair happens at native resolution: the low-frequency colour is interpolated from the
surrounding skin and the pore texture is re-injected from a clean nearby donor patch.
"""
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

from backend.retouch import geometry
from backend.retouch.faces import Face
from backend.retouch.filters import gaussian, masked_gaussian, robust_std

NORM_IOD = 170.0
MAX_SPOTS_PER_FACE = 160

_SIZE_PRESETS = {"AUTO": 1.0, "SMALL": 0.8, "MEDIUM": 1.0, "LARGE": 1.25}


@dataclass
class Spot:
    x: float   # native pixel coords
    y: float
    r: float   # repair radius (px, native)


def _oval_crop(face: Face, W: int, H: int, grow: float = 1.12):
    center, (au, av) = geometry.face_oval_params(face)
    R = max(au, av) * grow * face.iod
    x0, y0 = int(max(0, center[0] - R)), int(max(0, center[1] - R))
    x1, y1 = int(min(W, center[0] + R)), int(min(H, center[1] + R))
    return x0, y0, x1, y1


def _rej(stats: Optional[dict], key: str):
    if stats is not None:
        stats[key] = stats.get(key, 0) + 1


def detect_spots(lab: np.ndarray, domain: np.ndarray, faces: List[Face], strength: float, size_preset: str = "AUTO", stats: Optional[dict] = None) -> List[Spot]:
    H, W = lab.shape[:2]
    spots: List[Spot] = []
    size_mult = _SIZE_PRESETS.get(str(size_preset).upper(), 1.0)
    # strength 0..100 -> outlier threshold (in robust std units of the person's own texture)
    k_thr = 7.5 - 4.0 * (strength / 100.0)

    for face in faces:
        if face.iod < 45.0:
            continue  # blemishes are not resolvable on tiny faces
        x0, y0, x1, y1 = _oval_crop(face, W, H)
        if x1 - x0 < 32 or y1 - y0 < 32:
            continue
        s = min(1.0, NORM_IOD / face.iod)
        iod_n = face.iod * s
        cw, ch = max(8, int(round((x1 - x0) * s))), max(8, int(round((y1 - y0) * s)))
        crop = cv2.resize(lab[y0:y1, x0:x1], (cw, ch), interpolation=cv2.INTER_AREA)
        dom = cv2.resize(domain[y0:y1, x0:x1], (cw, ch), interpolation=cv2.INTER_AREA)

        M = (dom > 0.6).astype(np.float32)
        excl = np.zeros((ch, cw), np.float32)
        geometry.draw_heal_exclusions(excl, face.scaled(s, -x0 * s, -y0 * s))
        M *= (excl < 0.5)
        er = max(1, int(round(0.025 * iod_n)))
        M = cv2.erode(M, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * er + 1, 2 * er + 1)))
        if M.sum() < 400:
            continue

        L = crop[:, :, 0]
        A = crop[:, :, 1]
        # Fill outside the domain with the local skin base so filters never "see" eyes, hair or edges
        baseL = masked_gaussian(L, M, 0.08 * iod_n)
        baseA = masked_gaussian(A, M, 0.08 * iod_n)
        Lf = M * L + (1.0 - M) * baseL
        Af = M * A + (1.0 - M) * baseA

        sigmas = [f * iod_n * size_mult for f in (0.010, 0.014, 0.020, 0.028, 0.040)]
        sigmas = [max(1.1, sg) for sg in sigmas]
        stack = []
        inside = M > 0.5
        for sg in sigmas:
            lapL = cv2.Laplacian(cv2.GaussianBlur(Lf, (0, 0), sg), cv2.CV_32F) * (sg * sg)
            lapA = -cv2.Laplacian(cv2.GaussianBlur(Af, (0, 0), sg), cv2.CV_32F) * (sg * sg)
            nL = robust_std(lapL[inside])
            nA = robust_std(lapA[inside])
            dark = np.maximum(lapL - np.median(lapL[inside]), 0.0) / nL
            red = np.maximum(lapA - np.median(lapA[inside]), 0.0) / nA
            stack.append(np.sqrt(dark * dark + 0.8 * red * red) * M)
        stack = np.stack(stack, 0)

        best = stack.max(0)
        best_idx = stack.argmax(0)
        k = max(3, int(round(0.02 * iod_n)) | 1)
        local_max = best >= cv2.dilate(best, np.ones((k, k), np.uint8))
        cand = np.argwhere(local_max & (best > k_thr))
        if cand.size == 0:
            continue
        order = np.argsort(-best[cand[:, 0], cand[:, 1]])
        cand = cand[order][: MAX_SPOTS_PER_FACE * 4]

        ys, xs = np.mgrid[0:ch, 0:cw]
        kept_local = []
        noise_L = robust_std((L - baseL)[inside])
        for (cy, cx) in cand:
            sg = sigmas[int(best_idx[cy, cx])]
            rho = sg * 1.414
            win = int(np.ceil(rho * 2.8)) + 2
            ya, yb = max(0, cy - win), min(ch, cy + win + 1)
            xa, xb = max(0, cx - win), min(cw, cx + win + 1)
            if yb - ya < 5 or xb - xa < 5:
                continue
            dy = ys[ya:yb, xa:xb] - cy
            dx = xs[ya:yb, xa:xb] - cx
            d = np.sqrt(dx * dx + dy * dy)
            disk = d <= rho
            ring = (d >= rho * 1.6) & (d <= rho * 2.6)
            Mw = M[ya:yb, xa:xb]
            if disk.sum() < 3 or ring.sum() < 8:
                _rej(stats, "tiny")
                continue
            # 1. Completely inside the face domain
            if Mw[disk].mean() < 0.97 or Mw[ring].mean() < 0.90:
                _rej(stats, "outside_domain")
                continue
            Lw, Aw = L[ya:yb, xa:xb], A[ya:yb, xa:xb]
            ring_L, ring_A = Lw[ring], Aw[ring]
            dL = float(np.median(ring_L) - Lw[disk].mean())
            dA = float(Aw[disk].mean() - np.median(ring_A))
            # 2. Visible contrast against the person's own texture
            if not (dL > max(1.6, 1.8 * noise_L) or dA > 2.2):
                _rej(stats, "low_contrast")
                continue
            # 3. Calm surroundings (no hair, wrinkle or edge structure around the spot)
            if float(np.std(ring_L)) > 0.9 * max(dL, 0.0) + 2.5 + 1.2 * noise_L:
                _rej(stats, "busy_ring")
                continue
            # 3b. Isolation: EVERY direction around a real spot is clean skin. Creases, nose
            #     shading and shadow edges are dark on one side only and get rejected here.
            ang = np.arctan2(dy, dx)[ring]
            sector = ((ang + np.pi) / (2 * np.pi) * 8).astype(np.int32) % 8
            dark_spot = dL >= dA * 0.6
            vals = ring_L if dark_spot else ring_A
            core_v = Lw[disk].mean() if dark_spot else Aw[disk].mean()
            contrast_v = dL if dark_spot else dA
            sec_means = [vals[sector == q].mean() for q in range(8) if np.any(sector == q)]
            if len(sec_means) < 7:
                _rej(stats, "sectors")
                continue
            # Margin of each sector over the spot core, smallest first. One sector may hold a
            # neighbouring pimple (acne clusters); creases / shadows darken 2+ sectors.
            margins = sorted((m_ - core_v) if dark_spot else (core_v - m_) for m_ in sec_means)
            if margins[0] < -0.15 * contrast_v or margins[1] < 0.35 * contrast_v:
                _rej(stats, "not_isolated")
                continue
            # 4. Compact, round shape
            contrast = (np.median(ring_L) - Lw) / max(dL, 1e-3) if dark_spot else (Aw - np.median(ring_A)) / max(dA, 1e-3)
            blob = (contrast > 0.5) & (d <= rho * 2.0)
            n, lab_cc = cv2.connectedComponents(blob.astype(np.uint8), connectivity=8)
            cid = lab_cc[cy - ya, cx - xa]
            if cid == 0:
                continue
            comp = lab_cc == cid
            area = float(comp.sum())
            if area < 3:
                continue
            m = cv2.moments(comp.astype(np.uint8), binaryImage=True)
            mu20, mu02, mu11 = m["mu20"] / area, m["mu02"] / area, m["mu11"] / area
            common = np.sqrt(max(0.0, ((mu20 - mu02) / 2.0) ** 2 + mu11 ** 2))
            l1 = (mu20 + mu02) / 2.0 + common
            l2 = (mu20 + mu02) / 2.0 - common
            if l2 <= 1e-6 or l1 / l2 > 6.5:  # axis ratio > ~2.5 -> line-like
                _rej(stats, "line_like")
                continue
            if comp.sum() > 0.92 * (d <= rho * 2.0).sum():
                _rej(stats, "fills_window")
                continue  # blob fills the whole window: shading, not a spot
            eq_r = float(np.sqrt(area / np.pi))
            # 5. Keep moles / beauty marks: big, very dark, not red
            if dL > 16.0 and dA < 3.0 and eq_r > 0.028 * iod_n:
                _rej(stats, "mole")
                continue
            # Too big to be a blemish (shadow, birthmark)
            if eq_r > 0.085 * iod_n * size_mult:
                _rej(stats, "too_big")
                continue
            r_rep = max(eq_r, rho) * 1.35
            if any((cx - kx) ** 2 + (cy - ky) ** 2 < (max(r_rep, kr) * 0.9) ** 2 for kx, ky, kr in kept_local):
                continue
            kept_local.append((cx, cy, r_rep))
            if len(kept_local) >= MAX_SPOTS_PER_FACE:
                break

        inv = 1.0 / s
        for (cx, cy, rr) in kept_local:
            spots.append(Spot(x0 + (cx + 0.5) * inv - 0.5, y0 + (cy + 0.5) * inv - 0.5, rr * inv))
    return spots


def _soft_disk(h, w, cx, cy, r_in, r_out):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    t = np.clip((r_out - d) / max(1e-3, r_out - r_in), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t), d


def repair_spots(lab: np.ndarray, domain: np.ndarray, spots: List[Spot], opacity: float = 1.0, stats: Optional[dict] = None) -> np.ndarray:
    """In-place heal of lab (float32 Lab). Returns the heal alpha map (for overlays)."""
    H, W = lab.shape[:2]
    alpha_map = np.zeros((H, W), np.float32)
    for sp in spots:
        R = max(1.5, sp.r)
        half = int(np.ceil(R * 3.4)) + 2
        xa, xb = int(max(0, sp.x - half)), int(min(W, sp.x + half + 1))
        ya, yb = int(max(0, sp.y - half)), int(min(H, sp.y + half + 1))
        if xb - xa < 6 or yb - ya < 6:
            continue
        P = lab[ya:yb, xa:xb].copy()
        ph, pw = P.shape[:2]
        cx, cy = sp.x - xa, sp.y - ya

        alpha, d = _soft_disk(ph, pw, cx, cy, R * 0.85, R * 1.3)
        alpha *= np.clip(domain[ya:yb, xa:xb] * 1.2, 0.0, 1.0)
        if alpha.max() < 0.05:
            continue

        # Split: pores (high) vs colour/tone (low)
        sig = max(0.8, R * 0.22)
        low = cv2.GaussianBlur(P, (0, 0), sig)
        high = P - low

        # Fill the spot in the low layer from the surrounding skin (normalized convolution, 2 passes)
        known = (d > R * 1.05).astype(np.float32)
        k3 = known[:, :, None]
        filled = k3 * low + (1.0 - k3) * masked_gaussian(low, known, max(0.8, R * 0.7))
        filled = k3 * low + (1.0 - k3) * cv2.GaussianBlur(filled, (0, 0), max(0.6, R * 0.3))

        # Texture: copy pore detail from the cleanest nearby donor patch
        new_high = high * 0.25
        best_cost = None
        for ang in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            ox, oy = int(round(np.cos(ang) * R * 2.4)), int(round(np.sin(ang) * R * 2.4))
            dxa, dxb, dya, dyb = xa + ox, xb + ox, ya + oy, yb + oy
            if dxa < 0 or dya < 0 or dxb > W or dyb > H:
                continue
            dom_d = domain[dya:dyb, dxa:dxb]
            if dom_d[alpha > 0.05].mean() < 0.95:
                continue
            D = lab[dya:dyb, dxa:dxb]
            Dlow = cv2.GaussianBlur(D, (0, 0), sig)
            Dhigh = D - Dlow
            core = alpha > 0.5
            cost = abs(float(Dlow[core, 0].mean() - filled[core, 0].mean())) + abs(float(Dhigh[core, 0].std() - high[d > R * 1.4, 0].std()))
            if best_cost is None or cost < best_cost:
                best_cost, new_high = cost, Dhigh

        healed = filled + new_high

        # Verify before committing: the repaired spot must look like the clean skin around it.
        # Otherwise the heal is discarded and the original pixels stay (never a visible patch).
        if not _repair_ok(P, healed, d, R, sig):
            if stats is not None:
                stats["reverted"] = stats.get("reverted", 0) + 1
            continue

        a3 = (alpha * opacity)[:, :, None]
        lab[ya:yb, xa:xb] = P * (1.0 - a3) + healed * a3
        alpha_map[ya:yb, xa:xb] = np.maximum(alpha_map[ya:yb, xa:xb], alpha)
    return alpha_map


def _repair_ok(P: np.ndarray, healed: np.ndarray, d: np.ndarray, R: float, sig: float) -> bool:
    core = d <= R * 0.8
    ring = (d >= R * 1.5) & (d <= R * 2.6)
    if core.sum() < 3 or ring.sum() < 8:
        return False
    # 1. Colour / tone match (CIE76 delta E between healed core and surrounding skin)
    c_mean = healed[core].mean(axis=0)
    r_mean = P[ring].mean(axis=0)
    r_std = P[ring].std(axis=0)
    dE = float(np.sqrt(((c_mean - r_mean) ** 2).sum()))
    if dE > 3.5 + 1.5 * float(r_std[0]):
        return False
    # 2. Texture match: not a smooth smudge, not over-grainy
    hp_h = healed[:, :, 0] - cv2.GaussianBlur(healed[:, :, 0], (0, 0), sig)
    hp_p = P[:, :, 0] - cv2.GaussianBlur(P[:, :, 0], (0, 0), sig)
    e_core = float(hp_h[core].std())
    e_ring = float(hp_p[ring].std()) + 1e-3
    if not (0.35 <= e_core / e_ring <= 2.2) and e_ring > 0.6:
        return False
    # 3. No new edge at the patch border
    edge = (d > R * 0.8) & (d < R * 1.4)
    if edge.sum() > 4:
        g = cv2.magnitude(cv2.Sobel(healed[:, :, 0], cv2.CV_32F, 1, 0), cv2.Sobel(healed[:, :, 0], cv2.CV_32F, 0, 1))
        g0 = cv2.magnitude(cv2.Sobel(P[:, :, 0], cv2.CV_32F, 1, 0), cv2.Sobel(P[:, :, 0], cv2.CV_32F, 0, 1))
        if float(g[edge].mean()) > 1.6 * float(g0[ring].mean()) + 2.0:
            return False
    return True
