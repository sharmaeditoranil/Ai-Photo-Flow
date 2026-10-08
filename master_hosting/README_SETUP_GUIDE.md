# Ai PhotoFlow – Master Hosting Setup Guide (cPanel / Web Hosting)

## Yeh Master File Kya Hai?
Yeh Master Hosting package aapke apne Web Hosting / cPanel (jaise Hostinger, GoDaddy, Namecheap, Bluehost, etc.) me dalne ke liye banaya gaya hai. 

Isse aapke sabhi users/clients ke liye photo selection link hamesha **24x7 online** rahega, chahe unka PC band bhi ho!

---

## 3 Aasan Steps me Setup (Sirf 2 Minute):

### Step 1: Zip File ko cPanel me Upload karein
1. Apne Web Hosting ke **cPanel** me jayein aur **File Manager** kholein.
2. `public_html` ke andar ek naya folder banayein, jaise `album` ya `proofing` (Example: `public_html/album`).
3. Is folder ke andar **`AiPhotoFlow_Master_Hosting.zip`** upload karein aur **Extract** (Unzip) kar dein.
4. Ab aapka link ban gaya: `https://yourdomain.com/album/`

*(Note: Isme koi MySQL database banane ki zaroorat nahi hai. Yeh automatically apne aap data store kar leta hai!)*

---

### Step 2: Ai PhotoFlow Software me Domain set karein
1. Ai PhotoFlow software kholein.
2. **Settings** (ya **Client Proofing**) me apna Master Hosting URL enter karein:
   - Example: `https://yourdomain.com/album`
3. **Save** karein.

---

### Step 3: Ho Gaya! Sabhi Users ke liye Kaam Aasan
Ab software me jab bhi koi user **Client Link** banayega:
- Unko koi technical option (Cloudflare, Wi-Fi, Local PC) nahi dikhega.
- Unhe direct **ready-made link** aur **WhatsApp Share** ka button milega!
- Client apne mobile par link khol kar aaram se ❤️ Select karega aur submit kar sakega.

---

### Admin Dashboard (Photographer ke liye):
Aap kabhi bhi browser me `https://yourdomain.com/album/?admin=1` khol kar (Default PIN: `1234`) sabhi created albums aur client selections dekh sakte hain!
