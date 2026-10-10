# Ai PhotoFlow License Server – Setup (Hostinger)

Isse saare licenses, payment (Razorpay), coupons, prices, partners aur commissions online manage hote hain.
App ke andar koi secret nahi hai; license sirf is server se ban sakta hai.

## 1. Upload (5 minute)
1. hPanel → File Manager → `public_html` ke andar naya folder **`license`** banayein.
2. `dist-server/AiPhotoFlow_License_Server.zip` us folder me upload karke **Extract** karein.
3. Browser me kholein: **https://license.aiphotoflow.in/admin.php**

## 2. Admin account (sirf ek baar)
1. **Setup code** daalein (`~/AiPhotoFlow_Private/license_keys.json` me `setup_code`).
2. Username + strong password (12+ akshar, A-z, number, symbol).
3. Phone me **Google Authenticator** → `+` → QR scan → 6-digit code daalein.
4. Login ke baad **8 recovery codes** dikhenge — likh kar safe rakhein (phone kho jaye to kaam aayenge).

## 3. Razorpay
Admin → **Gateway & Prices**: Key ID + Key Secret save karein → "Test Razorpay connection".
Razorpay Dashboard → Webhooks → URL `https://aiphotoflow.in/license/api.php?r=webhook`, event `order.paid`,
wahi Webhook Secret jo admin me daala.

## 4. Album server
`master_hosting/AiPhotoFlow_Master_Hosting.zip` ko subdomain **album.aiphotoflow.in** ke folder me upload + Extract (Overwrite). App ka album server: https://album.aiphotoflow.in
Album admin (`?admin=1`) ab License Admin login se khulta hai (purana PIN 1234 band).

## Backup
`~/AiPhotoFlow_Private/` folder (private key) ka backup pen drive / safe jagah rakhein. Ye kho gaya to naye
licenses nahi ban sakenge. Kisi ko kabhi na dein.
Server data (licenses, payments) Hostinger par `domains/aiphotoflow.in/apf_license_private/` me hai — hPanel Backups ON rakhein.


## Subdomains (10 Oct 2026)
- License server: **https://license.aiphotoflow.in** (subdomain folder). The server finds the existing
  `apf_license_private/license.sqlite` automatically, so licenses, payments and the admin login stay the same.
- Album server: **https://album.aiphotoflow.in**.
- Razorpay Dashboard -> Webhooks: change the URL to `https://license.aiphotoflow.in/api.php?r=webhook`.
- Apps fall back to `https://aiphotoflow.in/license` if the subdomain does not answer; keep that folder until every
  computer has the new app.
