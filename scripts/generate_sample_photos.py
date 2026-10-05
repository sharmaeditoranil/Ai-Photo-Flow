"""
Generates a realistic test dataset of wedding photos for testing AI Culling,
Similarity/Burst detection, Face/Eye detection, and Auto-Editing.
"""
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_wedding_photos")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_face(draw, cx, cy, radius, skin_color, eyes_open=True, is_smiling=True):
    # Head oval
    draw.ellipse([cx - radius, cy - int(radius * 1.2), cx + radius, cy + int(radius * 1.2)], fill=skin_color, outline=(40, 20, 10), width=2)
    # Hair
    draw.arc([cx - radius - 2, cy - int(radius * 1.25), cx + radius + 2, cy], 180, 360, fill=(20, 15, 12), width=16)

    # Eyes
    eye_offset_x = int(radius * 0.42)
    eye_y = cy - int(radius * 0.15)
    eye_r = max(4, int(radius * 0.12))

    if eyes_open:
        # Left eye
        draw.ellipse([cx - eye_offset_x - eye_r, eye_y - eye_r, cx - eye_offset_x + eye_r, eye_y + eye_r], fill=(245, 245, 245), outline=(30, 20, 10))
        draw.ellipse([cx - eye_offset_x - eye_r//2, eye_y - eye_r//2, cx - eye_offset_x + eye_r//2, eye_y + eye_r//2], fill=(45, 25, 15))
        # Right eye
        draw.ellipse([cx + eye_offset_x - eye_r, eye_y - eye_r, cx + eye_offset_x + eye_r, eye_y + eye_r], fill=(245, 245, 245), outline=(30, 20, 10))
        draw.ellipse([cx + eye_offset_x - eye_r//2, eye_y - eye_r//2, cx + eye_offset_x + eye_r//2, eye_y + eye_r//2], fill=(45, 25, 15))
    else:
        # Closed eyes (arcs/lines)
        draw.arc([cx - eye_offset_x - eye_r, eye_y - eye_r//2, cx - eye_offset_x + eye_r, eye_y + eye_r//2], 0, 180, fill=(30, 20, 10), width=3)
        draw.arc([cx + eye_offset_x - eye_r, eye_y - eye_r//2, cx + eye_offset_x + eye_r, eye_y + eye_r//2], 0, 180, fill=(30, 20, 10), width=3)

    # Nose
    draw.line([cx, eye_y + 4, cx, cy + int(radius * 0.25)], fill=(120, 70, 50), width=2)

    # Mouth
    mouth_y = cy + int(radius * 0.55)
    mouth_w = int(radius * 0.35)
    if is_smiling:
        draw.arc([cx - mouth_w, mouth_y - 6, cx + mouth_w, mouth_y + 12], 0, 180, fill=(160, 40, 50), width=3)
    else:
        draw.line([cx - mouth_w, mouth_y, cx + mouth_w, mouth_y], fill=(140, 40, 50), width=3)

def generate_wedding_samples():
    print(f"Generating sample wedding dataset into: {OUTPUT_DIR}")

    # Indian skin tone (warm caramel / golden brown undertone)
    skin_caramel = (215, 160, 120)
    skin_fair = (235, 185, 145)

    # 1. Burst Series: Mandap Couple Portraits (4 shots, varying quality to test burst clustering)
    for i in range(1, 5):
        img = Image.new("RGB", (1600, 1200), (95, 45, 25)) # Warm mandap amber background
        draw = ImageDraw.Draw(img)

        # Background decor (marigold garlands, stage pillars)
        for x in range(100, 1600, 180):
            draw.line([(x, 0), (x, 1200)], fill=(180, 110, 20), width=8) # floral strands
            for y in range(40, 1200, 70):
                draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(240, 165, 0)) # Marigold flowers

        # Couple
        # Groom
        create_face(draw, 640, 520, 90, skin_caramel, eyes_open=(i != 3), is_smiling=True)
        draw.rectangle([500, 630, 780, 1200], fill=(225, 215, 195)) # Sherwani cream

        # Bride
        create_face(draw, 960, 560, 85, skin_fair, eyes_open=True, is_smiling=True)
        draw.rectangle([820, 660, 1100, 1200], fill=(190, 25, 45)) # Bridal red lehenga
        # Bridal gold jewelry
        draw.arc([900, 630, 1020, 720], 0, 180, fill=(235, 195, 40), width=10)

        np_arr = np.array(img)

        # Vary sharpness / blur across the burst
        if i == 1:
            # Shot 1: Crisp winner
            pass
        elif i == 2:
            # Shot 2: Slight motion blur
            np_arr = cv2.GaussianBlur(np_arr, (7, 7), 1.8)
        elif i == 3:
            # Shot 3: Eyes closed on groom!
            pass
        elif i == 4:
            # Shot 4: Heavy blur / reject
            np_arr = cv2.GaussianBlur(np_arr, (21, 21), 6.0)

        out_path = os.path.join(OUTPUT_DIR, f"Rahul_Priya_Mandap_Burst_{i:02d}.jpg")
        cv2.imwrite(out_path, cv2.cvtColor(np_arr, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 94])
        print(f"Created: {out_path}")

    # 2. Bride Solo Makeup Portrait (High quality, sharp)
    img_bride = Image.new("RGB", (1400, 1600), (45, 30, 35))
    draw_bride = ImageDraw.Draw(img_bride)
    create_face(draw_bride, 700, 680, 160, skin_fair, eyes_open=True, is_smiling=True)
    draw_bride.rectangle([450, 880, 950, 1600], fill=(185, 20, 40)) # Embroidered silk
    for rad in range(120, 200, 25):
        draw_bride.arc([700 - rad, 820, 700 + rad, 820 + rad], 0, 180, fill=(245, 210, 50), width=6)
    out_bride = os.path.join(OUTPUT_DIR, "Bride_Solo_Makeup_01.jpg")
    img_bride.save(out_bride, quality=95)
    print(f"Created: {out_bride}")

    # 3. Groom Prep (Good sharpness, neutral tones)
    img_groom = Image.new("RGB", (1400, 1600), (55, 60, 68))
    draw_groom = ImageDraw.Draw(img_groom)
    create_face(draw_groom, 700, 680, 160, skin_caramel, eyes_open=True, is_smiling=False)
    draw_groom.rectangle([450, 880, 950, 1600], fill=(25, 30, 45)) # Dark navy blazer
    out_groom = os.path.join(OUTPUT_DIR, "Groom_Preparation_01.jpg")
    img_groom.save(out_groom, quality=95)
    print(f"Created: {out_groom}")

    # 4. Outdoor Couple Golden Hour (Natural lighting)
    img_outdoor = Image.new("RGB", (1600, 1200), (140, 180, 130)) # Lush garden green
    draw_outdoor = ImageDraw.Draw(img_outdoor)
    # Sunlight gradient
    create_face(draw_outdoor, 700, 520, 95, skin_caramel, eyes_open=True, is_smiling=True)
    draw_outdoor.rectangle([550, 640, 850, 1200], fill=(40, 45, 65))
    create_face(draw_outdoor, 950, 540, 90, skin_fair, eyes_open=True, is_smiling=True)
    draw_outdoor.rectangle([820, 650, 1100, 1200], fill=(230, 190, 80)) # Pastel yellow saree
    out_outdoor = os.path.join(OUTPUT_DIR, "Outdoor_Garden_Portrait_01.jpg")
    img_outdoor.save(out_outdoor, quality=95)
    print(f"Created: {out_outdoor}")

    # 5. Reception Night Dance / Sangeet (Dynamic, high contrast, slightly dark)
    img_sangeet = Image.new("RGB", (1600, 1200), (20, 15, 30)) # Deep stage dark
    draw_sangeet = ImageDraw.Draw(img_sangeet)
    # Stage beams
    draw_sangeet.polygon([(800, 0), (200, 1200), (400, 1200)], fill=(70, 20, 90))
    draw_sangeet.polygon([(800, 0), (1200, 1200), (1400, 1200)], fill=(20, 60, 100))
    create_face(draw_sangeet, 800, 600, 100, skin_caramel, eyes_open=True, is_smiling=True)
    draw_sangeet.rectangle([650, 720, 950, 1200], fill=(15, 15, 20)) # Black tuxedo
    out_sangeet = os.path.join(OUTPUT_DIR, "Reception_Sangeet_Stage_01.jpg")
    img_sangeet.save(out_sangeet, quality=95)
    print(f"Created: {out_sangeet}")

    # 6. Severely Underexposed Shot (Test exposure warning/reject)
    img_dark = Image.new("RGB", (1400, 1200), (10, 8, 12))
    draw_dark = ImageDraw.Draw(img_dark)
    create_face(draw_dark, 700, 600, 100, (40, 25, 18), eyes_open=True)
    out_dark = os.path.join(OUTPUT_DIR, "Underexposed_Dark_Accidental_01.jpg")
    img_dark.save(out_dark, quality=90)
    print(f"Created: {out_dark}")

    # 7. Severely Out of Focus / Motion Blurred Shot (Test reject)
    img_blur = Image.new("RGB", (1400, 1200), (120, 80, 60))
    draw_blur = ImageDraw.Draw(img_blur)
    create_face(draw_blur, 700, 600, 110, skin_caramel, eyes_open=True)
    np_blur = np.array(img_blur)
    np_blur = cv2.GaussianBlur(np_blur, (45, 45), 15.0)
    out_blur = os.path.join(OUTPUT_DIR, "Out_Of_Focus_Blurred_01.jpg")
    cv2.imwrite(out_blur, cv2.cvtColor(np_blur, cv2.COLOR_RGB2BGR))
    print(f"Created: {out_blur}")

    print("Sample generation complete!")

if __name__ == "__main__":
    generate_wedding_samples()
