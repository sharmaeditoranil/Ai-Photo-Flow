# Ai PhotoFlow (V1 MVP)

> **AI-Powered Desktop Application for Professional Wedding Photographers**  
> Automated AI Culling • Non-Destructive Batch Editing • Indian Skin Tone Protection • Lightroom / Capture One Style Interface

---

## 📸 Overview

**Ai PhotoFlow** is a desktop application engineered specifically for the high-volume demands of professional wedding photographers. Built for handling shoots with thousands of photos (JPG, PNG, and RAW formats like ARW, CR3, NEF, DNG), it accelerates the photographer's post-production workflow from hours down to minutes:

1. **Select Wedding Folder** → Fast asynchronous scan, non-destructive indexing into local SQLite, cached thumbnail generation.
2. **AI Culling** → Deep sharpness analysis, blur detection, face/eye status verification, exposure clipping detection, and perceptual duplicate/burst clustering.
3. **Photographer Review** → Minimal dark charcoal gallery with instant zoom, full-screen lightbox, burst comparison view, star ratings, and hotkeys.
4. **AI Auto-Editing** → Individualized parameter calculation tailored for Indian wedding photography (protects warm skin tones, avoids nuclear saturation or crushed blacks).
5. **Wedding Consistency** → Clusters photos into scenes (*Bride Makeup, Mandap & Ceremony, Stage Portraits, Outdoor, Reception*) and harmonizes white balance.
6. **Before / After Review** → Interactive split-screen slider and side-by-side mode with real-time non-destructive adjustment sliders.
7. **Batch Export** → Safe multi-resolution export into organized subdirectories (`/AI-Selected`, `/AI-Edited`, `/Rejected`) without ever altering original camera files.

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────┐
│              Ai PhotoFlow Desktop Client                  │
│       (Electron + React 19 + TypeScript + Vanilla CSS)    │
└─────────────────────────────┬─────────────────────────────┘
                              │ REST / HTTP Proxy
┌─────────────────────────────▼─────────────────────────────┐
│                 Local Processing Manager                  │
│               (FastAPI + Python 3.9+ Server)              │
├─────────────────────────────┬─────────────────────────────┤
│       SQLite Database       │      Batch Worker Queue     │
│   (photoflow.db / Caches)   │  (Pause / Resume / Cancel)  │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                       AI Model Layer                      │
├──────────────────────┬──────────────────────┬─────────────┤
│     CullingModel     │      FaceModel       │ QualityModel│
│  (BEST/PICK/REVIEW)  │  (Eye Open/Closed)   │ (Blur/DR)   │
├──────────────────────┼──────────────────────┼─────────────┤
│DuplicateDetectionModel│     EditingModel     │ SceneModel  │
│(Perceptual dHash/HSV)│ (Indian Skin Safe)   │(Consistency)│
└──────────────────────┬──────────────────────┴─────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                Photo Adjustment Engine                    │
│      (Pillow + OpenCV + RawPy Non-Destructive Pipeline)   │
└───────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### 1. Prerequisites
- macOS (Apple Silicon or Intel)
- Node.js 18+ and npm
- Python 3.9+ (pre-configured in virtual environment `venv`)

### 2. Run the Desktop Application
To launch the full Electron desktop app:
```bash
npm run start:desktop
```
This automatically starts:
- The Python AI backend service (`http://127.0.0.1:8000`)
- The Vite frontend (`http://localhost:5173`)
- The native Electron desktop window with native folder picker dialogs

### 3. Run in Web / Browser Mode
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Testing with Sample Wedding Dataset

A realistic sample dataset with 10 wedding photos is included in `sample_wedding_photos/`:
- **Burst Series (4 shots)**: Couple under mandap with varying blur, sharpness, and closed eyes to test burst clustering and winner recommendation.
- **Bride Solo Makeup Portrait**: Sharp bridal portrait in embroidered red silk to test skin tone preservation.
- **Groom Preparation**: Sharp formal portrait.
- **Outdoor Garden Portrait**: Daylight couple portrait.
- **Reception Stage / Sangeet**: Dynamic stage lighting.
- **Out of Focus & Underexposed Accidental Shots**: Testing automatic reject/review flags.

### 1-Click Test:
1. Open the app.
2. Click **Import Folder**.
3. Click the **Load Sample** button (automatically points to `sample_wedding_photos/`).
4. Click **Scan & Open Folder**.
5. Click **⚡ AI Cull Photos** to watch the progress bar and see scores and duplicate groups calculated live!
6. Click **✨ Auto Edit Selected** to apply individualized corrections.
7. Switch to **Before / After** or drag the split slider to inspect the results.

---

## 🎹 Photographer Keyboard Shortcuts

| Shortcut | Action |
|:---:|:---|
| <kbd>P</kbd> | **Pick / Select** photo |
| <kbd>X</kbd> | **Reject** photo |
| <kbd>U</kbd> | **Unflag** / Reset selection |
| <kbd>1</kbd> – <kbd>5</kbd> | Set **Star Rating** (1★ to 5★) |
| <kbd>0</kbd> | Clear Star Rating |
| <kbd>Space</kbd> | Toggle **Before / After** split view |
| <kbd>C</kbd> | Open **Burst Compare** for current duplicate group |
| <kbd>E</kbd> | Run **AI Auto-Edit** on active photo |
| <kbd>←</kbd> / <kbd>→</kbd> | Navigate previous / next photo |
| <kbd>Esc</kbd> | Return to Grid View / Close modal |

---

## 🎨 Color Science: Natural Indian Skin Tone Protection

A frequent issue with Western auto-editors is turning Indian skin overly orange or magenta when trying to warm up ambient light, or crushing rich details in bridal garments. 

**Ai PhotoFlow's** `IndianWeddingEditingModel`:
1. Converts the image to YCrCb chrominance space to detect human skin pixels ($Cr \in [133, 173]$, $Cb \in [77, 127]$).
2. Measures chromaticity deviation ($R-B$ and $G$ deviations) against neutral highlight anchors.
3. Automatically suppresses magenta flushes ($Cr > 152$) while boosting vibrance only on undersaturated background tones.
4. Recovers bridal attire highlights (silk zardozi, jewelry) without flattening contrast.

---

## 📁 Export Directory Structure

When exporting, Ai PhotoFlow safely generates:
```
/Your-Export-Folder/
├── /AI-Selected/    <- Top culled photos (original quality or resized)
├── /AI-Edited/      <- Photos with non-destructive AI/manual adjustments applied
└── /Rejected/       <- Optional archive of rejected shots for verification
```
*Your original camera files are NEVER overwritten.*

---

## 🚀 V2 Architecture Preparation

The codebase is structured with clean abstract interfaces (`backend/core/interfaces.py`):
- `PhotoshopUXPIntegration`: Placeholder ready for Adobe Photoshop UXP Plugin.
- Ready for V2 features: Face retouching, advanced skin smoothing, Generative Fill, teeth whitening, and subject/background masks.
