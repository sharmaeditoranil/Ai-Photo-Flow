# Ai PhotoFlow — Complete Documentation

*Last updated: 10 Oct 2026 · App version 1.0.0 · Covers the desktop app (Mac + Windows), the License Server, the Album (client sharing) server, the website and how to build, release and run everything.*

> **No secrets are written in this document.** Private keys, the admin setup code, the Razorpay webhook secret and old Razorpay values live only in `~/AiPhotoFlow_Private/` on the owner's Mac (and in Razorpay / the Admin panel). Never commit that folder, never share it.

---

## Contents
1. [Owner quick guide (Hinglish)](#1-owner-quick-guide-hinglish)
2. [System overview](#2-system-overview)
3. [Live addresses](#3-live-addresses)
4. [Where everything is (folders, repos, private files)](#4-where-everything-is)
5. [Desktop app — features and how they work](#5-desktop-app)
6. [License Server and Admin panel](#6-license-server-and-admin-panel)
7. [Payments (Razorpay)](#7-payments-razorpay)
8. [Partners, coupons and commissions](#8-partners-coupons-and-commissions)
9. [Album server (client photo sharing)](#9-album-server-client-photo-sharing)
10. [Website (aiphotoflow.in)](#10-website-aiphotoflowin)
11. [Building a release (Mac + Windows + servers)](#11-building-a-release)
12. [Deploying to Hostinger](#12-deploying-to-hostinger)
13. [Daily operations](#13-daily-operations)
14. [Troubleshooting](#14-troubleshooting)
15. [Security rules](#15-security-rules)
16. [Testing checklist before every release](#16-testing-checklist)
17. [Developer reference](#17-developer-reference)
18. [History of important decisions](#18-history-of-important-decisions)
19. [Future roadmap](#19-future-roadmap)

---

## 1. Owner quick guide (Hinglish)

| Kaam | Kahan / Kaise |
|---|---|
| Admin kholna | https://license.aiphotoflow.in/admin.php (username + password + 2FA code) |
| Naya license dena (cash sale) | Admin → **Users & Licenses** → create, ya **Payments → Offline sale** (partner commission ke liye) |
| Trial ke din badalna | Admin → **Gateway & Prices** → *Free trial days* (abhi 1) |
| Prices badalna | Admin → **Gateway & Prices** |
| Partner banana + coupon | Admin → **Partners** (naam, commission %, UPI, coupon code jaise `RAHUL10`) |
| Partner ko paise dena | Admin → **Commissions** → UPI ref daal kar **Mark paid** |
| Kisi ka trial badhana | Admin → **Trials** → extend |
| Naya app banana | Mac par: `bash scripts/release_build.sh` (Section 11) |
| Server file update | `venv/bin/python scripts/build_server_bundles.py` → zip Hostinger me `license.aiphotoflow.in` folder me Extract (Section 12) |
| Album "upload fail" | Section 14 dekhiye |
| Website GitHub par push | **Pehle socho!** Push ke baad license/album check karo (Section 10) |

Golden rules:
1. `~/AiPhotoFlow_Private/` folder aur `dist-server/*LICENSE*.zip` me **private key** hai — kabhi share/commit mat karo.
2. Server zip upload ke baad data safe rehta hai (data `apf_license_data` folder me `public_html` ke bahar hai).
3. Har release ke baad Mac **aur** Windows dono test karo (Section 16).

---

## 2. System overview

```
  Photographer's computer (Mac / Windows)                     Hostinger (license.aiphotoflow.in)
 ┌──────────────────────────────────────────┐   HTTPS JSON   ┌──────────────────────────────────────┐
 │ Electron app (React UI)                  │ ─────────────▶ │ License Server  (PHP + SQLite)       │
 │   └─ local backend (Python FastAPI)      │                │   /api.php  /admin.php               │
 │       culling · editing · RAW · export   │                │   data: ../apf_license_data/ (outside│
 │       license client · album upload      │                │         public_html)                 │
 │       data: ~/.photoflow/                │   X-APF-License│ Album Server   /album/index.php      │
 └──────────────────────────────────────────┘ ─────────────▶ │   data: album/data/galleries/<uuid>  │
                                                              └──────────────────────────────────────┘
         Client (phone / PC browser) ── https://license.aiphotoflow.in/album/?id=<uuid>&pin=<pin>
         Razorpay ── webhook ──▶ https://license.aiphotoflow.in/api.php?r=webhook
         Website  https://aiphotoflow.in  (separate GitHub repo, marketing + download)
```

* **The app does all photo work locally** (culling, editing, RAW, export). Photos never leave the computer except watermarked previews for client albums.
* **The License Server decides** trials, plans, devices, prices, coupons, partners, payments. The app stores a signed token (Ed25519) and works offline for up to 30 days.
* **The Album Server** hosts client selection galleries; it only accepts uploads from apps with a valid signed token.

---

## 3. Live addresses

| What | Address |
|---|---|
| Website | https://aiphotoflow.in |
| License Server API | https://license.aiphotoflow.in/api.php?r=… (ping, plans, trial, quote, order, verify, webhook, …) |
| **Admin panel** | **https://license.aiphotoflow.in/admin.php** |
| Album server (used by the app) | https://license.aiphotoflow.in/album |
| Client album link format | https://license.aiphotoflow.in/album/?id=`<gallery_uuid>`&pin=`<PIN>` |
| Razorpay webhook | https://license.aiphotoflow.in/api.php?r=webhook — events `order.paid`, `payment.captured` |
| robots.txt | https://license.aiphotoflow.in/robots.txt → `Disallow: /` (plus `X-Robots-Tag: noindex`) |

Old addresses (no longer used by the new app): `aiphotoflow.in/license` (delete the folder once every computer has the new app), `aiphotoflow.in/files/public_html` (old album server, removed).

---

## 4. Where everything is

### On the owner's Mac
| Path | What |
|---|---|
| `~/Documents/Anil Sharma Final Website Meterial/Ai PhotoFlow ` (note the trailing space) | **App repo** (this code). GitHub: `sharmaeditoranil/Ai-Photo-Flow`, branch `main` |
| `~/Documents/Anil Sharma Final Website Meterial/Ai PhotoFlow(Front)` | **Website repo**. GitHub: `sharmaeditoranil/Ai-Photo-Flow-Front`, branch `main` |
| `~/AiPhotoFlow_Private/license_keys.json` | Ed25519 key pair + admin setup code (used to build the license server). **Secret.** Backups `license_keys.backup_*.json` |
| `~/AiPhotoFlow_Private/Razorpay_Setup_AiPhotoFlow.zip` | Razorpay setup guide + webhook secret. **Secret.** |
| `~/.photoflow/` | The app's own data on this Mac (database, cache, logs) |

### Inside the app repo
| Path | What |
|---|---|
| `backend/` | Python backend (FastAPI). `core/` AI models & rules, `services/` features, `retouch/` skin retouch, `db/` SQLite |
| `frontend/` | React + TypeScript UI (Vite) |
| `electron/` | Desktop shell (starts the backend, opens windows) |
| `license_server/` | License Server PHP source (`config.php` is generated, never committed) |
| `master_hosting/index.php` | Album server (single PHP file) + `.htaccess` |
| `scripts/` | `release_build.sh`, `build_server_bundles.py`, `build_license_server.py`, test helpers |
| `tests/` | Unit tests (`test_retouch.py`, `test_white_balance.py`, `test_heal.py`) |
| `dist-dmg/` | Built installers (git-ignored) |
| `dist-backend/`, `dist-backend-win/` | Packaged backends for Mac / Windows (git-ignored) |
| `dist-server/` | Server zips (git-ignored; most contain the private key) |
| `docs/` | This documentation |

### App data on a customer's computer
* Mac: `~/.photoflow/` · Windows: `C:\Users\<name>\.photoflow\`
* `photoflow.db` (projects, photos, edits, albums, license token), `cache/` (thumbnails, previews, album previews), `backend.log` (diagnostics, e.g. face model status), `backend_crash.log` (Windows start errors)
* Original photos are **never modified**. Exports are written to the chosen folder.

---

## 5. Desktop app

### 5.1 Workflow
**Import Folder → AI Cull → (review) → Auto Edit → Client Link (optional) → Export**

### 5.2 Import
* Scans a folder (JPG/PNG and RAW: Sony ARW, Canon CR2/CR3, Nikon NEF, Fuji RAF, DNG, Panasonic, Olympus, Pentax, …).
* Importing the **same folder again** reuses the project. Importing photos of a **removed** project re-attaches its client albums (5.9).

### 5.3 AI Culling (categories)
| Category | Meaning |
|---|---|
| **AI Best** | Every good photo + the single best photo of each burst/similar group |
| **Review** | Only when the AI is genuinely unsure (borderline focus, possible blink without emotion, very doubtful exposure) |
| **Rejected** | Clearly bad: real blur / motion blur, pitch-black or blown-white frames |
| **Similar Groups** | Burst alternates; the group winner is shown in AI Best, the rest only here |
| **Customer Selected** | Photos the client selected in the online album |

How focus is judged (`backend/core/culling_model.py`, `face_model.py`):
* Face-first: the main face's sharpness, checked again on the full-resolution file **at album size** (256 px face, re-blur metric — independent of skin texture). Group photos use the 2nd-best face so one lucky face cannot pass a shaken group shot.
* Photos without faces (rings, decor, details): sharpest-area focus.
* Thresholds: face OK ≥ 36, blur < 30 (album-size metric); 1000 px face score blur < 38.
* Closed eyes with emotion/close-up (laughing, prayer, vidai) stay AI Best.

### 5.4 Auto Edit (default preset "Pure Light")
Pipeline (`backend/core/editing_model.py` computes settings, `backend/services/image_service.py` renders):
1. **Skin retouch** on the camera pixels (heal, mattifier, skin details, even tone) — gated by a per-person skin mask (eyes, lips, hair, clothes untouched).
2. **AI white balance** (grey-pixel/grey-edge/white-patch + skin check), then **Clean Colour** closed loop: whites/greys finish slightly cool (b\* ≈ −1.5, "halka blue"), skin never yellow (hue ≤ 50°).
3. Exposure, subject light (over-lit faces brought down to ≈160 gray), shadows/highlights/contrast/whites/blacks, depth guard (no flat "milky" portraits).
4. **Skin Colour Lock**: skin gets back the camera's natural colour (hue 34–50°, chroma ×1.04) — prevents ashy/grey skin after cooling.
5. **Skin Glow** (slider, default 65 "Natural"): soft radiance on skin only (+2 avg / +5 highlights) **plus gentle fill light** only for faces in shade (judged per face; up to ≈ +5 L\*; well-lit faces unchanged).
6. Straighten only from long vertical/horizontal lines, max 3°, crop-to-fill (no mirrored corners).
7. Sharpening, noise reduction, vibrance (other presets), dodge & burn.
* The calibration renders a 1200 px preview and corrects light, haze, contrast and skin colour before saving the settings ("accuracy over speed").
* Other presets: Royal Cool Blue, Warm Golden Amber, Vibrant Royal Wedding, Soft Pastel & Airy, Moody Cinematic Film, Clean Ivory Neutral.

### 5.5 RAW
`backend/services/raw_decoder.py`: 16-bit linear LibRaw decode, exposure matched to the camera's embedded JPEG, highlight roll-off, camera-look tone/colour matching, EXIF kept on export.

### 5.6 Fullscreen viewer
Double-click a photo. **Before / After slider** is on by default: drag the handle (left = original, right = AI edit). Button or `\` turns it off. **Heal** brush (click a blemish) hides the slider while active. Keys: ←/→ navigate, B best, R review, X reject, 1–5 stars, Esc close.

### 5.7 Inspector (right panel)
Histogram, AI diagnostics, manual culling, editing style & tone presets, sliders (exposure … sharpness), Dodge & Burn, **Skin Glow**, AI Skin Retouch, White Balance card.

### 5.8 Export
Choose categories (AI Best, Customer Selected, Similar, Rejected…), JPEG quality, resolution, rename pattern. Full-resolution edits with original EXIF/ICC. Unedited JPGs are copied 1:1.

### 5.9 Client Link (albums)
1. **Client Link** → choose photos, PIN, watermark → the app renders watermarked previews and uploads them to the album server.
2. Share the link (+PIN, or "Auto-Unlock Link"). The client selects / rejects photos on phone or PC and presses **Submit**.
3. The app pulls selections (they appear in **Customer Selected**; export them with the "Customer Selected" option).
4. Album photos are deleted from the server **7 days after the client submits** (selections stay in the app).
5. **Re-attach after removing a project:** if a project is removed and the same photos are imported again (same folder, or ≥ 60 % of the album's file names match), the album, link, PIN and the client's selections come back automatically — even if the client submitted while the project was removed. Album-server photo ids never change (`client_gallery_photos.remote_id`).

### 5.10 Licence in the app
* Top bar badge shows plan / trial time; **My Profile** shows plan, activation date, days left, computers, payments.
* **Pricing** shows server prices; coupon box; payment via Razorpay Checkout.
* Token refresh every 12 h when online; works offline up to 30 days (setting on server).
* One trial per computer (machine id); reinstalling does not give a new trial.
* Server unreachable / maintenance page → app behaves as offline (never locks because the server is down).

### 5.11 Mac vs Windows
Identical code and settings (verified pixel-identical edits). Windows uses an embedded Python 3.10 (`dist-backend-win`), Mac a PyInstaller build. The face model (YuNet) is loaded from memory so Windows paths with spaces / Unicode user names work; result is logged in `backend.log`.

---

## 6. License Server and Admin panel

Location: `license.aiphotoflow.in` folder on Hostinger (source: `license_server/`).

### 6.1 Admin tabs
| Tab | Use |
|---|---|
| 📊 Dashboard | Totals, revenue, pending commissions |
| 👤 Users & Licenses | All licenses, customer name/email/phone, computers (remove a computer to free a seat), extend/revoke |
| 💳 Payments | All orders (CREATED / PAID), coupon used, partner; **Offline sale** (cash/UPI) creates license + commission |
| 🏷️ Coupons | Codes, discount %, max uses, validity, plans, partner, active on/off |
| 🤝 Partners | Partners, codes, sales count & revenue, commission %, pending/paid |
| 💰 Commissions | Every commission line; **Mark paid** with UPI/bank reference |
| ⏳ Trials | Trials per computer; extend or block |
| ⚙️ Gateway & Prices | Razorpay Key ID / Key Secret / Webhook Secret, business name, payments on/off, prices (INR/USD, monthly/yearly), computers per plan, **free trial days**, offline days |
| 🛡️ Security | 2FA, recovery codes, password, audit log |

### 6.2 Plans (defaults)
| Plan | Price (INR) | Computers |
|---|---|---|
| PRO | ₹499 / month, ₹3,499 / year | 1 |
| STUDIO | ₹999 / month, ₹6,999 / year | 3 |
| VIP_LIFETIME | issued manually | 3 |
| Free trial | 1 day | 1 (per computer, once) |

### 6.3 Security of the server
* Ed25519-signed tokens (`sodium`, or bundled `sodium_compat` because Hostinger disables sodium).
* Admin: password + TOTP 2FA, CSRF tokens, login rate limit, full audit log.
* API rate limits; failed-activation lock counts only wrong keys.
* `config.php`, `lib/`, `.sqlite/.json/.md/.txt` blocked by `.htaccess` (robots.txt explicitly allowed).
* **Data folder** `apf_license_data/` is created next to the subdomain folder and **never inside any `public_html`**, so website deploys cannot delete it.

### 6.4 Fresh install (only if starting from zero)
1. Build zips (Section 11.3), upload `LICENSE_AND_ALBUM_license.aiphotoflow.in.zip`, extract in the subdomain folder.
2. Open admin → **First-time setup** → setup code from `~/AiPhotoFlow_Private/license_keys.json` → create owner + scan 2FA QR.
3. Enter Razorpay keys (Section 7). If "First-time setup" appears on an *existing* install, stop: the data folder was not found.

---

## 7. Payments (Razorpay)

* Live mode keys in Admin → Gateway & Prices: **Key ID** (`rzp_live_…`), **Key Secret**, **Webhook Secret**, payments ✔.
* Razorpay Dashboard → Webhooks: URL `https://license.aiphotoflow.in/api.php?r=webhook`, same secret, events `order.paid` + `payment.captured`.
* Flow: app asks server for an order → Razorpay Checkout in the app → app sends payment signature → server verifies (HMAC) → creates license, activates this computer, records coupon use + partner commission. If the app is closed mid-payment, the **webhook** completes the order and the app picks it up later (`order_status`).
* 100 % coupons skip Razorpay and issue the license directly.
* Business category used for KYC: IT & Software / SaaS (digital product, no shipping).
* Setup guide with exact values: `~/AiPhotoFlow_Private/Razorpay_Setup_AiPhotoFlow.zip`.
* Website still needs **Privacy Policy, Terms, Refund/Cancellation, Shipping/Delivery** pages if Razorpay asks during activation (not built yet — see roadmap).

---

## 8. Partners, coupons and commissions

Rules (server, `license_server/lib/core.php` → `apf_quote`, `apf_referral_agent`):
1. Admin creates a partner with commission % and a code (e.g. `RAHUL10`, 10 % customer discount).
2. **The code works once per customer** — only on the customer's **first purchase**, monthly **or** yearly.
3. **That partner owns the customer for life:** every later payment of the customer (renewals, upgrades, yearly), with or without code, creates a commission for that partner.
4. A customer is recognised by **computer, email or mobile (last 10 digits)**.
5. Inactive partner → no further commissions.
6. Offline sales (Admin → Payments) without a chosen partner are also credited to the customer's referring partner.
7. Commission = paid amount × partner's % at the time of sale. Status PENDING until **Mark paid**.
8. Licenses created manually in "Users & Licenses" do **not** create commissions — use **Offline sale** for that.

Example (Rahul 20 %, code 10 %): first monthly ₹449 → ₹89.80; next month ₹499 (no code) → ₹99.80; yearly ₹3,499 → ₹699.80; using the code again is refused.

---

## 9. Album server (client photo sharing)

* File: `master_hosting/index.php` (+ `.htaccess`), deployed as `license.aiphotoflow.in/album/`.
* Uploads require the header `X-APF-License` with a valid signed token; albums belong to the license/trial that created them.
* Client page: PIN protected (or auto-unlock link), watermarked previews, select / reject / note, Submit.
* Auto-clean: photos deleted 7 days after submit (`$AUTO_CLEAN_DAYS`), selections kept.
* Responses are `no-store` (CDN must not cache) and `noindex`.
* `get_selections` also returns the album's photo id → file name list (used to re-attach albums).
* `sodium_compat` is looked up at `../lib`, `/lib` and `/license/lib` (Hostinger has sodium disabled).

---

## 10. Website (aiphotoflow.in)

* Repo: `Ai PhotoFlow(Front)` → GitHub `Ai-Photo-Flow-Front` (`main`). Static HTML/CSS/JS.
* Free trial text: **1-Day** everywhere (keep in sync with Admin → Free trial days).
* `js/main.js` is loaded with a version query (`main.js?v=…`) — bump it when changing JS so browsers reload.
* ⚠️ **Hostinger Git auto-deploy:** a push to this repo once removed the old `/license` and `/files` folders inside `public_html`. The license and album servers now live on the **subdomain** to avoid this. Still, after every website push check:
  `curl -X POST "https://license.aiphotoflow.in/api.php?r=ping" -d '{}'` and open the admin page.

---

## 11. Building a release

### 11.1 One command (Mac)
```bash
cd ~/"Documents/Anil Sharma Final Website Meterial/Ai PhotoFlow "
bash scripts/release_build.sh
```
It runs unit tests, TypeScript check, builds the **Mac DMG**, copies the backend into the Windows bundle and builds the **Windows installer**, verifies both, and builds the **server zips**.

Outputs:
* `dist-dmg/Ai PhotoFlow-1.0.0-arm64.dmg` (Apple Silicon Mac)
* `dist-dmg/Ai PhotoFlow Setup 1.0.0.exe` (Windows 10/11 x64)
* `dist-server/*.zip` (Section 11.3)

### 11.2 Step by step (if needed)
```bash
for t in tests/test_*.py; do venv/bin/python -m unittest "$t"; done
(cd frontend && npx tsc -p tsconfig.app.json --noEmit)
npm run build:dmg                                   # frontend + PyInstaller backend + DMG
rsync -a --delete --exclude "__pycache__" --exclude "*.pyc" --exclude "photoflow.db" --exclude ".photoflow_cache" \
      backend/ dist-backend-win/backend/            # Windows uses the same backend source
npx electron-builder --win nsis --x64               # Windows installer
```
* Version number: `package.json` → `"version"`. Bump it (e.g. 1.0.1) for public releases so users can tell builds apart.
* The Mac build is unsigned (`identity: null`); macOS may ask to allow it in Privacy & Security.

### 11.3 Server zips
```bash
venv/bin/python scripts/build_server_bundles.py
```
| Zip (in `dist-server/`) | Contents | Secret? | Use |
|---|---|---|---|
| `LICENSE_AND_ALBUM_license.aiphotoflow.in.zip` | license server + `album/` | **yes (private key)** | full install / update |
| `AiPhotoFlow_License_Server.zip` | license server only | **yes** | license-only update |
| `ALBUM_ONLY_license.aiphotoflow.in.zip` | `album/` only | no | album updates (safe to hand to a helper) |

`config.php` inside is generated from `~/AiPhotoFlow_Private/license_keys.json` (public key, signing key, setup code).

---

## 12. Deploying to Hostinger

1. hPanel → File Manager → the **`license.aiphotoflow.in`** folder (where `admin.php` is).
2. Upload the zip → right-click → **Extract** into the same folder → overwrite.
3. Delete the zip from the server (and from Desktop if it contains the private key).
4. Check: `https://license.aiphotoflow.in/api.php?r=ping` (POST) → `{"ok":true}`; admin shows **Login** (not First-time setup); `https://license.aiphotoflow.in/album/index.php?action=ping` → online.
5. Data (`apf_license_data/`, `album/data/`) is not inside the zips, so updates never erase licenses or albums.

SSL must be active on the subdomain. Website deploys go through GitHub (Section 10).

---

## 13. Daily operations
* **New sale without Razorpay (cash/UPI):** Admin → Payments → Offline sale (plan, amount, customer, partner) → license key shown → give key to customer → app → Pricing → Activate.
* **Customer changed computer:** Admin → license → remove old computer → customer activates on the new one.
* **Extend a trial / license:** Admin → Trials or the license page.
* **Refund:** refund in Razorpay, then revoke the license in Admin.
* **Pay partners:** Commissions → pay by UPI → Mark paid with reference.
* **Check payments arrive:** Razorpay → Webhooks → Recent deliveries = 200.
* **Backups:** monthly, download `apf_license_data/license.sqlite` from Hostinger (outside public_html) and keep it with the private files.

---

## 14. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| App: "Domain upload fail hua … needs an active license" (401) | Album server cannot verify tokens (sodium_compat not found) or the app's license is not active | Upload latest `ALBUM_ONLY…zip`; check the app's license badge; Retry Upload |
| App: "Album server file not found … HTTP 404" | `album/index.php` missing on the server | Upload `ALBUM_ONLY…zip` into the subdomain folder |
| License/admin URLs give 404 | Server files removed (e.g. by a website deploy) | Re-upload `LICENSE_AND_ALBUM…zip` (data is kept) |
| Admin shows "First-time setup" on a live system | Data folder not found | Do **not** fill it; check `apf_license_data` location |
| Payment done but plan not active | App closed / webhook secret mismatch | Razorpay Webhooks deliveries; same secret in Admin; app → refresh |
| Windows very slow / odd patches | Face model not loaded | Check `C:\Users\<name>\.photoflow\backend.log` for "YuNet face model loaded" |
| AI Best shows Similar photos | (fixed) stale category list | Update app; switch category again |
| Yellow / ashy / patchy skin | (fixed) WB, skin lock, mask seam | Re-run Auto Edit with the current app |
| Photo rotated wrongly | (fixed) straighten | Re-run Auto Edit; straighten slider to 0 |
| Client selection missing after removing a project | Normal until re-import | Import the same photos again → album re-attaches (5.9) |
| Trial already used on a computer | One trial per machine | Admin → Trials → extend, or sell a plan |

Useful checks:
```bash
curl -s -X POST "https://license.aiphotoflow.in/api.php?r=ping" -d '{}'
curl -s -X POST "https://license.aiphotoflow.in/api.php?r=plans" -d '{}'
curl -s "https://license.aiphotoflow.in/album/index.php?action=ping&_=$(date +%s)"
```

---

## 15. Security rules
1. Never commit or share `~/AiPhotoFlow_Private/`, `dist-server/` zips with the license server, `license_server/config.php`.
2. The setup code is only useful while no admin exists; rotate it (new value in `license_keys.json`) before any fresh install.
3. Webhook secret must match in Razorpay and Admin; change both together.
4. Keep 2FA recovery codes offline.
5. The app never stores Razorpay secrets; all payment keys live on the server.
6. Customer photos stay on their computer; only watermarked previews go to the album server and are auto-deleted.
7. Third-party licences: `THIRD_PARTY_LICENSES.md` (YuNet MIT, sodium_compat ISC, OpenCV, LibRaw/rawpy, etc.). No proprietary third-party code.

---

## 16. Testing checklist
Before giving a build to anyone:
- [ ] `bash scripts/release_build.sh` finished with no errors (tests + TypeScript + both builds verified)
- [ ] Install the DMG on Mac and the EXE on Windows
- [ ] Trial/licence badge correct; My Profile opens
- [ ] Import a folder (JPG + one RAW) → AI Cull → categories look right (AI Best has no Similar photos)
- [ ] Auto Edit → open fullscreen → Before/After slider drags; skin natural, no yellow, no seams
- [ ] Export → files full size with EXIF
- [ ] Client Link → upload ONLINE → open link on phone → select → Submit → Customer Selected in app
- [ ] Remove project → import again → album re-attached
- [ ] Admin opens; a ₹ test payment (then refund) creates license + webhook 200
- [ ] Windows: `backend.log` says "YuNet face model loaded"

---

## 17. Developer reference

### Run in development
```bash
npm run start:desktop     # backend :8000 + Vite :5173 + Electron
```
Electron picks a free port from 8000 upward (Windows can reserve 8000).

### Important files
| File | Responsibility |
|---|---|
| `backend/main.py` | All REST endpoints (`/api/...`) |
| `backend/services/culling_service.py` | Import, culling job, recluster |
| `backend/core/culling_model.py`, `face_model.py`, `quality_model.py`, `duplicate_model.py` | Culling rules & metrics |
| `backend/core/editing_model.py` | Auto-edit settings + calibration loops (light, colour) |
| `backend/services/image_service.py` | Render pipeline, skin lock, skin glow/fill light, export |
| `backend/core/white_balance.py` | AI white balance |
| `backend/retouch/*` | Faces (YuNet), skin mask, retouch steps |
| `backend/services/raw_decoder.py` | RAW development |
| `backend/services/license_service.py` | Licence client (tokens, trial, payments) |
| `backend/services/hosting_sync_service.py` | Album upload, selections, album re-attach |
| `backend/services/proofing_service.py` | Albums, previews, watermark, local proofing |
| `backend/db/database.py` | Schema + migrations (run on every start) |
| `frontend/src/App.tsx` | App state, loading photos (stale-response guard) |
| `frontend/src/components/*` | TopBar, Sidebar, PhotoGrid, InspectorPanel, LightboxModal (slider), modals |
| `frontend/src/index.css` | Design tokens, buttons (sheen/glow), modals, sliders |
| `license_server/lib/core.php` | DB, settings, tokens, pricing, coupons, referral rules, orders |
| `license_server/api.php` / `admin.php` | Public API / Admin panel |
| `master_hosting/index.php` | Album server |

### Key database tables (app, `~/.photoflow/photoflow.db`)
`projects`, `photos` (metrics, ai_recommendation, user_selection, edit_params JSON, client_selection), `client_galleries` (uuid, PIN, hosting status, folder_path), `client_gallery_photos` (photo_id, remote_id, filename, client_selection), `license_client` (token, key), `app_settings`, `batch_jobs`.

### Key tables (server, `license.sqlite`)
`admins`, `settings`, `agents` (partners), `coupons`, `licenses`, `activations`, `trials`, `orders`, `commissions`, `audit_log`.

### Coding rules followed
* Accuracy over speed for retouch / white balance; changes are validated on real photos (Card 01 sets, Tamron NEF, Test Image) with measurements and side-by-sides.
* Never modify the user's real data during tests — use a copy with `HOME=<scratch>`.
* Mac and Windows must stay identical: always rsync `backend/` into `dist-backend-win/` before the Windows build.

---

## 18. History of important decisions
| Date | Decision |
|---|---|
| 8–9 Oct 2026 | Online License Server replaces in-app admin/payments; one trial per computer; device limits per plan; My Profile |
| 9 Oct | Face-first culling judged at album size; Review only for real doubt |
| 9 Oct | Clean colour (no yellow), skin glow; RAW development for all major brands |
| 10 Oct | Windows: face model from memory, fixed Haar recursion (speed) |
| 10 Oct | Skin Colour Lock, skin-mask fix, straighten fix, depth guard |
| 10 Oct | Servers moved to **license.aiphotoflow.in** (fresh install, data outside public_html) after a website deploy removed `/license` |
| 10 Oct | Trial = 1 day; partner code once per customer, lifetime partner commission |
| 10 Oct | Fullscreen Before/After slider, design polish, per-face fill light |
| 10 Oct | AI Best stale-list fix; album re-attach after removing a project; album sodium path fix |

---

## 19. Future roadmap
1. **Website policy pages** (Privacy, Terms, Refund, Shipping) — needed for Razorpay compliance.
2. **Version bump + auto-update** (electron-updater with `latest.yml`) so customers get fixes without reinstalling.
3. **Code signing** (Apple Developer ID + notarisation; Windows code-signing certificate) to remove security warnings.
4. **Automatic server backups** of `license.sqlite` (cron to email/Drive).
5. **Partner portal** (partners see their own sales/commissions) and partner referral links that pre-fill the code.
6. **Intel Mac build** (`--x64`) if customers need it.
7. **Photoshop bridge (UXP v2)** — placeholder in the sidebar.
8. **Health monitor** that pings license + album servers and alerts the owner.
