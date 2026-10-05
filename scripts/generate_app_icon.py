"""
Generate high-resolution 512x512 App Icon for macOS packaging.
"""
import os
import math
from PIL import Image, ImageDraw

BUILD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build")
os.makedirs(BUILD_DIR, exist_ok=True)
ICON_PATH = os.path.join(BUILD_DIR, "icon.png")

def create_app_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Rounded rectangle base with dark titanium gradient
    pad = 32
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=90, fill=(18, 20, 26, 255), outline=(50, 58, 75, 255), width=6)

    # 2. Outer lens ring (metallic cyan / blue)
    cx, cy = size // 2, size // 2
    r_outer = 160
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(24, 28, 38, 255), outline=(59, 130, 246, 255), width=8)

    # 3. Inner glass lens
    r_inner = 120
    draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=(12, 16, 25, 255), outline=(37, 99, 235, 255), width=4)

    # 4. Camera Aperture blades
    num_blades = 7
    blade_r = 95
    for i in range(num_blades):
        angle = (2 * math.pi / num_blades) * i
        x1 = cx + int(blade_r * math.cos(angle))
        y1 = cy + int(blade_r * math.sin(angle))
        angle_next = angle + 0.9
        x2 = cx + int((blade_r - 40) * math.cos(angle_next))
        y2 = cy + int((blade_r - 40) * math.sin(angle_next))
        draw.line([x1, y1, x2, y2], fill=(70, 80, 105, 255), width=3)

    # 5. Golden Aperture Center Glow (Wedding warmth)
    r_center = 42
    draw.ellipse([cx - r_center, cy - r_center, cx + r_center, cy + r_center], fill=(234, 179, 8, 220))

    # 6. AI Sparkle star at top right of lens
    sx, sy = cx + 85, cy - 85
    sparkle_len = 35
    draw.line([sx - sparkle_len, sy, sx + sparkle_len, sy], fill=(255, 255, 255, 255), width=5)
    draw.line([sx, sy - sparkle_len, sx, sy + sparkle_len], fill=(255, 255, 255, 255), width=5)
    diag = 20
    draw.line([sx - diag, sy - diag, sx + diag, sy + diag], fill=(147, 197, 253, 255), width=3)
    draw.line([sx - diag, sy + diag, sx + diag, sy - diag], fill=(147, 197, 253, 255), width=3)

    img.save(ICON_PATH, format="PNG")
    print(f"App icon successfully generated: {ICON_PATH}")

if __name__ == "__main__":
    create_app_icon()
