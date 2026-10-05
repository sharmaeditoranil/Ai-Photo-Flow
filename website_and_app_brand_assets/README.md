# Ai PhotoFlow – Official Brand & Website Assets

This folder contains the complete, high-resolution branding kit for **Ai PhotoFlow**. All assets are exported in state-of-the-art formats (Apple HIG App Icons, crisp PNG squircles/circles, vector SVGs, and favicons).

---

## 📁 File Manifest & Recommended Usage

| Asset File | Resolution / Type | Best Used For |
| :--- | :--- | :--- |
| **`AiPhotoFlow_Logo_With_Text.svg`** | Vector SVG (720x160) | **Website Navigation Bar / Header** (emblem + "Ai PhotoFlow" gradient typography) |
| **`AiPhotoFlow_Logo.svg`** | Vector SVG (512x512) | **Website Favicon, Mobile Navbar, or Footer** (vector infinite-resolution emblem) |
| **`AiPhotoFlow_Logo_Squircle_1024x1024.png`** | 1024x1024 PNG (Transparent) | **Website Hero Section, Feature Highlights, Landing Page Demos** |
| **`AiPhotoFlow_Logo_Circular_1024x1024.png`** | 1024x1024 PNG (Transparent) | **Social Media Profiles (Instagram, YouTube, Twitter/X, LinkedIn avatar)** |
| **`AiPhotoFlow_AppIcon_1024x1024.png`** | 1024x1024 PNG (Apple HIG) | **macOS App Icon** with standard squircle radius & depth shadow |
| **`AiPhotoFlow_AppIcon_512x512.png`** | 512x512 PNG | **Website Download Page ("Download for Mac / Windows") button icon** |
| **`AiPhotoFlow_AppIcon.icns`** | macOS Apple ICNS | **Native macOS Application Bundle Icon** |
| **`favicon-64x64.png`** | 64x64 PNG | **Browser tab icon (Retina / 2x)** |
| **`favicon-32x32.png`** | 32x32 PNG | **Browser tab icon (Standard)** |

---

## 🌐 Quick HTML Snippets for Your Website

### 1. Website Favicon (Add to `<head>` of your website):
```html
<link rel="icon" type="image/svg+xml" href="/assets/AiPhotoFlow_Logo.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="64x64" href="/assets/favicon-64x64.png">
<link rel="apple-touch-icon" href="/assets/AiPhotoFlow_AppIcon_512x512.png">
```

### 2. Website Navbar Logo:
```html
<nav>
  <a href="/">
    <img src="/assets/AiPhotoFlow_Logo_With_Text.svg" alt="Ai PhotoFlow" height="42" style="display: block;" />
  </a>
</nav>
```

### 3. Website Hero / Download Badge:
```html
<div class="download-card">
  <img src="/assets/AiPhotoFlow_AppIcon_512x512.png" alt="Ai PhotoFlow for macOS" width="80" height="80" />
  <h3>Ai PhotoFlow for Desktop</h3>
  <a href="/download" class="btn">Download Free Trial</a>
</div>
```
