# Third-Party Licenses

The AI Skin Retouch module (`backend/retouch/`) was written from scratch for Ai PhotoFlow.
It contains no code, model weights or UI assets from commercial retouching products.
It uses only the permissively licensed libraries and models listed below.

## Models

| Model | File | Source | License |
|---|---|---|---|
| YuNet face detector (2023mar), with 5-point landmarks | `backend/models/face_detection_yunet_2023mar.onnx` | [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) | MIT |
| Haar cascades: frontal face, eye, smile (fallback detector) | `backend/data/haarcascade_*.xml` | OpenCV | Intel License Agreement for Open Source Computer Vision Library (BSD-3-Clause style) |

## Python libraries used by the retouch engine

| Library | Used for | License |
|---|---|---|
| OpenCV (`opencv-python-headless`) | Colour conversion, filters, YuNet inference (`cv2.FaceDetectorYN`) | Apache-2.0 |
| NumPy | Array maths | BSD-3-Clause |
| Pillow | Image decoding / EXIF orientation | MIT-CMU (HPND) |
| rawpy / LibRaw | Camera RAW decoding | MIT (rawpy), LGPL-2.1 / CDDL-1.0 (LibRaw) |
| FastAPI / Starlette / Pydantic / Uvicorn | REST API | MIT / BSD-3-Clause / MIT / BSD-3-Clause |
| onnxruntime | ONNX inference (custom trained models, `training/`) | MIT |

## Frontend

| Library | Used for | License |
|---|---|---|
| React | UI | MIT |
| lucide-react | Icons | ISC |
| Vite / TypeScript | Build tooling | MIT / Apache-2.0 |

## License Server (PHP, `license_server/`)

| Library | Used for | License |
|---|---|---|
| paragonie/sodium_compat v2.5.2 (`license_server/lib/sodium_compat/`) | Ed25519 license signing when the host's PHP sodium extension is disabled | ISC |
| qrcode.js (loaded from cdnjs on the admin 2FA setup page) | Authenticator QR code | MIT |
