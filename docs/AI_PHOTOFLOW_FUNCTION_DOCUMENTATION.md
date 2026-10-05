# Ai PhotoFlow: Complete Function & Feature Documentation Guide
> **The Definitive Technical & Operational Documentation for Ai PhotoFlow (Enterprise v1.0.0)**  
> *Engineered for High-Volume Wedding & Commercial Post-Production Workflows*

---

## 📑 Table of Contents
1. [Executive Summary & System Architecture](#1-executive-summary--system-architecture)
2. [Module 1: Ingestion & High-Speed RAW Decoding](#2-module-1-ingestion--high-speed-raw-decoding)
3. [Module 2: AI Culling & Quality Assessment Engine](#3-module-2-ai-culling--quality-assessment-engine)
4. [Module 3: Duplicate Clustering & AI Best-Shot Selection](#4-module-3-duplicate-clustering--ai-best-shot-selection)
5. [Module 4: Scene Categorization & Consistency Clustering](#5-module-4-scene-categorization--consistency-clustering)
6. [Module 5: AI Color Engine & Skin-Tone Protection (with 5% Vibrance Boost)](#6-module-5-ai-color-engine--skin-tone-protection-with-5-vibrance-boost)
7. [Module 6: Enterprise Batch Export & Multi-Layer Watermarking](#7-module-6-enterprise-batch-export--multi-layer-watermarking)
8. [Module 7: Cryptographic Licensing & Hardware Fingerprint Security](#8-module-7-cryptographic-licensing--hardware-fingerprint-security)
9. [Module 8: Studio Administration & Remote Key Control](#9-module-8-studio-administration--remote-key-control)
10. [Module 9: High-Efficiency Keyboard Shortcuts & Workflow Ergonomics](#10-module-9-high-efficiency-keyboard-shortcuts--workflow-ergonomics)
11. [Module 10: Future Roadmap & Upcoming Capabilities (V2 Engine)](#11-module-10-future-roadmap--upcoming-capabilities-v2-engine)

---

## 1. Executive Summary & System Architecture

### 1.1 Purpose & Problem Statement
A typical multi-day wedding produces between **3,000 to 12,000 raw camera files** across multiple camera bodies (Sony, Canon, Nikon, Fujifilm). Traditional manual sorting ("culling") and baseline color correction takes **15 to 30 hours per wedding**.
Western AI tools frequently fail on Indian and South-Asian wedding events:
- They oversaturate bridal reds, maroons, and silks.
- They turn warm Indian skin tones overly orange or magenta under tungsten/mandap lighting.
- They struggle with harsh stage lighting (colored RGB LEDs, smoke, halogen spotlights).

**Ai PhotoFlow** is engineered to resolve these issues completely, cutting 25+ hours of manual labor down to **under 15 minutes** through offline-first, local GPU/CPU accelerated computer vision and color science algorithms.

### 1.2 Architectural Topology
```
┌────────────────────────────────────────────────────────────────────────┐
│                   Desktop Presentation Layer                           │
│        Electron + React 19 + TypeScript + Native Hardware APIs         │
├────────────────────────────────────────────────────────────────────────┤
│                          REST / HTTP & IPC                             │
├────────────────────────────────────────────────────────────────────────┤
│                   Local High-Performance Core Server                   │
│             FastAPI + Multiprocessing Workers (Python 3.9+)            │
├──────────────────┬──────────────────────┬──────────────────────────────┤
│  SQLite Meta DB  │   RAW Decoding Pool  │    Async Task Job Queue      │
│  (Indexed Files) │   (LibRaw / RawPy)   │    (Pause / Resume / Cancel) │
├──────────────────┴──────────────────────┴──────────────────────────────┤
│                            AI Model Matrix                             │
│ ┌───────────────────┐  ┌───────────────────┐  ┌──────────────────────┐ │
│ │  Sharpness & Blur │  │ Face & Eye Status │  │ Perceptual Clust.    │ │
│ │  Laplacian Metric │  │ Haar + Landmarks  │  │ Dual-Hash & Color Hist│ │
│ └───────────────────┘  └───────────────────┘  └──────────────────────┘ │
│ ┌───────────────────┐  ┌───────────────────┐  ┌──────────────────────┐ │
│ │ Scene Recognition │  │ YCrCb Skin Engine │  │ +5% Vibrance Engine  │ │
│ │ Feature Descriptors│ │ Pure Light Cast WB│  │ S-Curve Tone Balancer│ │
│ └───────────────────┘  └───────────────────┘  └──────────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│                     Non-Destructive Processing Engine                  │
│       OpenCV Accelerated Matrix Operations + Pillow SIMD + RawPy       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Module 1: Ingestion & High-Speed RAW Decoding

### 2.1 File System Traversal
* **Supported Formats:**
  * Sony RAW (`.ARW`, `.SR2`)
  * Canon RAW (`.CR2`, `.CR3`)
  * Nikon RAW (`.NEF`, `.NRW`)
  * Fujifilm RAW (`.RAF`)
  * Adobe Digital Negative (`.DNG`)
  * Standard High-Resolution Formats (`.JPG`, `.JPEG`, `.PNG`, `.TIFF`, `.WEBP`)
* **Non-Destructive Guarantee:** Original camera files are mounted strictly in **Read-Only** mode. Metadata and AI states are tracked via internal unique hashes in an independent SQLite catalog.

### 2.2 Two-Tier Fast Thumbnail Generation
To allow immediate scrolling through 10,000+ files without lag:
1. **Tier 1 (Instant EXIF Embedded Preview):** Extracts the camera-generated embedded JPEG preview thumbnail directly from RAW metadata buffer in $<15\text{ms}$.
2. **Tier 2 (Full-Fidelity Proxy Cache):** Decodes half-sized linear proxies stored in local disk cache (`.photoflow_cache/`) for real-time 100% zoom and loupe inspection.

---

## 3. Module 2: AI Culling & Quality Assessment Engine

The Culling Engine processes each image through a 4-tier computer vision pipeline:

```
[RAW / JPG Image]
       │
       ▼
 [1. Sharpness & Motion Blur Analysis (Laplacian Variance + High-Freq Gradient)]
       │
       ▼
 [2. Facial Recognition & Micro-Expression (Haar + Dlib Landmarks)]
       │  ├── Eyes Open / Closed Ratio
       │  └── Blinking & Squint Detection
       ▼
 [3. Dynamic Range & Exposure Clipping]
       │  ├── Highlight Burn Check (Bridal Jewelry / Silk Whites)
       │  └── Shadow Crush Check (Groom Tuxedo / Sherwani Blacks)
       ▼
 [Composite Quality Score: 0.0 - 100.0] ──> Categorized: BEST / PICK / REVIEW / REJECT
```

### 3.1 Sharpness & Blur Rejection
* **Metric:** Modified Laplacian Variance $\sigma^2(\nabla^2 I)$ evaluated across both the global frame and prioritized facial bounding boxes.
* **Edge Frequency Filtering:** Detects camera shake vs intentional shallow depth-of-field (bokeh). If the background is blurred but the subject's pupil is crisp, the photo is rated **Sharp**.

### 3.2 Eye & Face Detection
* **Eye Aspect Ratio (EAR):**
  $$\text{EAR} = \frac{\|p_2 - p_6\| + \|p_3 - p_5\|}{2 \|p_1 - p_4\|}$$
* Automatically flags blinking eyes, half-open sleepy eyes, and micro-squints during flash bursts.
* Multi-person group shots check all primary faces; if any key subject has eyes closed during a ritual, the shot is flagged for review.

### 3.3 Composite Scoring Matrix
* **BEST (Score 85–100):** Pin-sharp focus, wide open eyes, perfect lighting balance, winning expression.
* **PICK (Score 70–84):** High quality, sharp, suitable for album inclusion.
* **REVIEW (Score 50–69):** Acceptable sharpness with minor issues (e.g., slight motion or mixed lighting).
* **REJECT (Score < 50):** Missed focus, motion blur, closed eyes, or blown-out highlights.

---

## 4. Module 3: Duplicate Clustering & AI Best-Shot Selection

Photographers often shoot rapid bursts of 3 to 10 frames to capture a momentary expression. Manual inspection of every burst is exhausting.

### 4.1 Perceptual Multi-Layer Clustering
Ai PhotoFlow combines three feature layers to group burst sequences:
1. **Temporal Proximity:** EXIF timestamp delta ($\Delta t \le 3.5\text{s}$).
2. **Difference Hash (dHash) & Perceptual Hash (pHash):** 64-bit structural gradients robust to minor framing changes.
3. **HSV Color Histogram Correlation:** Normalized histogram intersection with threshold $T \ge 0.90$ ensuring lighting consistency.

### 4.2 Best-Shot "Winner" Selection Algorithm
* Within every clustered duplicate set, the engine evaluates each photo's sharpness, eye openness, smile confidence, and framing.
* **The Winner:** The single photo with the highest composite metric is awarded the **"BEST"** classification (Rank 1).
* **AI Best Gallery View:** In the **AI Best** view, only the single best shot appears. Duplicate badges and secondary copies are automatically hidden.
* **Similar Section View:** Secondary burst photos are accessible under the **Similar** tab for manual override if the client prefers a specific pose.

---

## 5. Module 4: Scene Categorization & Consistency Clustering

Weddings consist of diverse lighting conditions and environments. Ai PhotoFlow automatically tags and clusters photos into event scenes:
* **Mandap & Pheras:** Heavy fire/warm halogen lighting.
* **Haldi & Mehendi:** High yellow/green vibrance and daytime ambient light.
* **Bridal Solo & Preparation:** High-key, soft beauty portrait lighting.
* **Stage & Reception:** Colored DJ lighting, spot illumination, and dark backgrounds.
* **Outdoor & Golden Hour:** Natural sunlight and high dynamic range.

By grouping photos by scene, the editing engine applies batch white balance harmonizing so all photos in the same ritual look consistent in the wedding album.

---

## 6. Module 5: AI Color Engine & Skin-Tone Protection (with 5% Vibrance Boost)

Traditional auto-enhancers crush contrast or cause Indian skin tones to look scorched orange. Ai PhotoFlow features a specialized color science engine.

### 6.1 YCrCb Skin-Tone Isolation
1. Converts RGB to YCrCb chrominance space.
2. Isolates human skin pixels where $Cr \in [133, 173]$ and $Cb \in [77, 127]$.
3. Masks skin regions so white-balance shifts and background color enhancements do not degrade the subject's natural complexion.

### 6.2 Pure Light Neutral White Balance (0% Color Cast)
* Detects highlight anchors and neutral grays ($Y > 200, |Cr - 128| < 10, |Cb - 128| < 10$).
* Neutralizes ugly green fluorescent casts and yellow halogen casts while preserving the intended festive warmth of candlelight and mandap fire.

### 6.3 Universal +5% Vibrance Boost Engine
* **Smart Vibrance vs Simple Saturation:** While simple saturation pushes all colors equally (causing skin redness), Ai PhotoFlow's **Vibrance** algorithm selectively enhances undersaturated hues.
* **+5% Baseline Boost:** Every edited photo automatically receives a calibrated $+5\%$ vibrance enhancement:
  $$\text{Vibrance}_{\text{applied}} = \text{clip}(\text{Vibrance}_{\text{calc}} + 5.0, 5.0, 35.0)$$
* **Visual Result:** Bridal jewelry, embroidery, flowers, and decorations pop with rich, punchy colors, while human skin tones remain creamy, natural, and protected.

### 6.4 Highlight & Shadow Dynamic Recovery
* **Shadow Recovery:** Recovers shadow details in dark fabrics (groom's black/navy suit or velvet sherwani) using adaptive histogram tone mapping.
* **Highlight Protection:** Compresses upper-range highlights to prevent clipping on gold zardozi work, diamond necklaces, and wedding stage chandeliers.

---

## 7. Module 6: Enterprise Batch Export & Multi-Layer Watermarking

The Export Engine converts edited states into high-resolution deliverables across multi-core worker queues.

### 7.1 Non-Destructive Export Directory Tree
```
[User-Selected Export Directory]
 ├── /AI-Selected/    <-- Best photos (original resolution or resized)
 ├── /AI-Edited/      <-- Non-destructively color-corrected and tuned
 └── /Rejected/       <-- Optional archive for client record verification
```
*Original camera files are NEVER altered or overwritten.*

### 7.2 Custom Multi-Layer Watermarking
* **Format Options:** Text watermark (photographer name/studio) or PNG Logo with alpha channel.
* **Customization:**
  * Real-time Opacity slider ($0\%$ to $100\%$).
  * Dynamic Scaling ($5\%$ to $50\%$ of image width).
  * 9 Anchor Positions: Top-Left, Top-Center, Top-Right, Center-Left, Center, Center-Right, Bottom-Left, Bottom-Center, Bottom-Right.
  * Tiling Mode: Diagonal anti-theft proofing watermarks for client selection galleries.

### 7.3 Export Profiles
* **Master High-Res:** 100% Quality JPEG / TIFF (for Album Printing).
* **Web / Social Media:** 2048px on long edge, 82% Quality (sRGB color profile, optimized for Instagram and WhatsApp without compression banding).
* **Client Proofing:** 1080p with watermarks embedded.

---

## 8. Module 7: Cryptographic Licensing & Hardware Fingerprint Security

To protect the software from unauthorized duplication and cracks, Ai PhotoFlow incorporates multi-factor hardware cryptographic binding.

### 8.1 Hardware Fingerprint Vector
The machine ID is synthesized from non-spoofable hardware primitives:
1. Motherboard Serial / UUID (`ioreg` on macOS / `wmic csproduct get uuid` on Windows)
2. Primary CPU Processor Identification
3. Primary Network Adapter MAC Address

### 8.2 Cryptographic HMAC-SHA256 Token Validation
* Licenses are generated using a 32-byte secret salt known only to the studio management backend.
* **Format:** `FLOW-XXXX-XXXX-XXXX-XXXX`
* **Offline Authentication:** Verifies license validity completely offline using local cryptographic public validation.
* **Anti-Clock Rollback:** Prevents users from extending trial periods by altering system clock time.

---

## 9. Module 8: Studio Administration & Remote Key Control

A built-in administrative suite accessible via secure admin key:
* **Generate Multi-Tier Keys:** Trial (7 Days), Commercial (1 Year), and Studio Lifetime.
* **Revocation & Blacklisting:** Instantly disable compromised or shared license keys.
* **Device Transfer:** Unbind a key from a retired computer and re-assign to a new workstation.
* **Audit Logs:** View shoot counts, export logs, and device activation timestamps.

---

## 10. Module 9: High-Efficiency Keyboard Shortcuts & Workflow Ergonomics

Ai PhotoFlow is engineered for high-speed single-hand culling using industry-standard keyboard ergonomics:

| Shortcut | Function | Workflow Stage |
|:---:|:---|:---|
| <kbd>P</kbd> | **Pick / Select** active photo | Culling |
| <kbd>X</kbd> | **Reject** active photo | Culling |
| <kbd>U</kbd> | **Unflag** / Reset selection status | Culling |
| <kbd>1</kbd> – <kbd>5</kbd> | Assign **Star Rating** (1★ to 5★) | Culling / Rating |
| <kbd>0</kbd> | Clear Star Rating | Culling / Rating |
| <kbd>Space</kbd> | Toggle **Before / After** Split Screen | Editing / Review |
| <kbd>C</kbd> | Open **Burst Compare** for current duplicate group | Culling / Inspection |
| <kbd>E</kbd> | Run **AI Auto-Edit** on active photo | Color Editing |
| <kbd>←</kbd> / <kbd>→</kbd> | Jump to Previous / Next photo | Navigation |
| <kbd>Z</kbd> | 100% Pixel-to-Pixel Instant Loupe Zoom | Focus Check |
| <kbd>Esc</kbd> | Return to Grid View / Dismiss Modal | Global |

---

## 11. Module 10: Future Roadmap & Upcoming Capabilities (V2 Engine)

The core architecture (`backend/core/interfaces.py`) is modular and prepared for upcoming V2 enterprise expansions:

### 11.1 AI Facial Blemish & Skin Retouching (Q1 2027)
* Frequency separation AI to automatically diminish acne, dark circles, and transient blemishes while retaining 100% natural skin texture and pores.
* High-precision teeth whitening and catchlight enhancement in pupils.

### 11.2 Semantic AI Masking & Bokeh Generation (Q2 2027)
* Real-time semantic segmentation separating:
  * Subject (Bride & Groom)
  * Background / Mandap
  * Sky & Ambient Ceiling
* Enables selective exposure adjustment of subjects without altering ambient background ambiance.

### 11.3 Generative Object Removal & Photobomber Erase (Q3 2027)
* One-click removal of microphone stands, video cables, lighting stands, and stray background photobombers during critical ritual moments.

### 11.4 Adobe Lightroom & Photoshop UXP Integration (Q4 2027)
* Direct `.XMP` sidecar generation enabling photographers to import culled and color-corrected ratings directly into Adobe Lightroom Classic without re-rendering.
* Photoshop UXP plugin for native batch retouching actions.

---

*Ai PhotoFlow is engineered by and for professional wedding photographers.*  
*Documentation Version: 1.0.0 Enterprise | Date: October 2026*
