import { Sun, Flame, Heart, Camera, Film, Palette, Zap, Sparkles, Sliders } from 'lucide-react';

export interface PresetInfo {
  id: string;
  name: string;
  badge: string;
  badgeBg: string;
  tone: string;
  description: string;
  bestFor: string;
  icon: any;
  cssFilter: string;
  gradient: string;
}

export const WEDDING_PRESETS: PresetInfo[] = [
  {
    id: 'Pure Light (No Color Tone)',
    name: 'Pure Light (No Color Tone)',
    badge: '#94a3b8',
    badgeBg: 'rgba(148, 163, 184, 0.15)',
    tone: 'Only Light Balance (0% Color Shift)',
    description: 'Sirf exposure, shadows & highlights balance. Zero color tint, 100% natural as shot.',
    bestFor: 'Natural look, studio shoots jaha colors ko touch nahi karna.',
    icon: Sun,
    cssFilter: 'brightness(1.15) contrast(1.05) saturate(1.0)',
    gradient: 'linear-gradient(135deg, #cbd5e1, #64748b)'
  },
  {
    id: 'Royal Cool Blue',
    name: 'Royal Cool Blue',
    badge: '#38bdf8',
    badgeBg: 'rgba(56, 189, 248, 0.15)',
    tone: 'Crisp Cool Blue Tone',
    description: 'Crisp modern cool blue tone, banquet hall ki peeli/tungsten lights ko clean karta hai.',
    bestFor: 'Indoor banquet hall, evening receptions & modern couple portraits.',
    icon: Sparkles,
    cssFilter: 'brightness(1.15) contrast(1.08) saturate(1.05) hue-rotate(-14deg)',
    gradient: 'linear-gradient(135deg, #38bdf8, #1d4ed8)'
  },
  {
    id: 'Warm Golden Amber',
    name: 'Warm Golden Amber',
    badge: '#f59e0b',
    badgeBg: 'rgba(245, 158, 11, 0.15)',
    tone: 'Golden Amber Warmth',
    description: 'Rich warm golden yellow glow, Haldi, Mehndi & Mandap ke mahol ko shandar banata hai.',
    bestFor: 'Haldi, Mehndi, Mandap Pheras & warm traditional moments.',
    icon: Flame,
    cssFilter: 'brightness(1.14) contrast(1.06) saturate(1.18) sepia(0.25) hue-rotate(10deg)',
    gradient: 'linear-gradient(135deg, #fbbf24, #d97706)'
  },
  {
    id: 'Vibrant Royal Wedding',
    name: 'Vibrant Royal Wedding',
    badge: '#ef4444',
    badgeBg: 'rgba(239, 68, 68, 0.15)',
    tone: 'Punchy Royal Colors',
    description: 'Red bridal lehenga, emeralds, jewelry aur stage lights me rich vibrant colors pop karta hai.',
    bestFor: 'Sangeet night, bridal portraits & colorful stage decor.',
    icon: Palette,
    cssFilter: 'brightness(1.15) contrast(1.14) saturate(1.35) hue-rotate(-4deg)',
    gradient: 'linear-gradient(135deg, #ef4444, #991b1b)'
  },
  {
    id: 'Soft Pastel & Airy',
    name: 'Soft Pastel & Airy',
    badge: '#ec4899',
    badgeBg: 'rgba(236, 72, 153, 0.15)',
    tone: 'Bright & Airy Daylight',
    description: 'High-key roshni, soft shadow fill aur dreamy pastel colors jo photo ko soft & royal banate hain.',
    bestFor: 'Daylight weddings, garden pre-wedding shoots & open lawn ceremonies.',
    icon: Heart,
    cssFilter: 'brightness(1.22) contrast(0.95) saturate(0.92)',
    gradient: 'linear-gradient(135deg, #f472b6, #db2777)'
  },
  {
    id: 'Moody Cinematic Film',
    name: 'Moody Cinematic Film',
    badge: '#a855f7',
    badgeBg: 'rgba(168, 85, 247, 0.15)',
    tone: 'Cinematic Matte Tone',
    description: 'Deep matte blacks, subtle desaturation aur modern cinematic magazine story grading.',
    bestFor: 'Cinematic couple portraits, dramatic solo bridal shoots.',
    icon: Film,
    cssFilter: 'brightness(1.06) contrast(1.12) saturate(0.85) sepia(0.12) hue-rotate(-8deg)',
    gradient: 'linear-gradient(135deg, #c084fc, #7e22ce)'
  },
  {
    id: 'Clean Ivory Neutral',
    name: 'Clean Ivory Neutral',
    badge: '#f1f5f9',
    badgeBg: 'rgba(241, 245, 249, 0.15)',
    tone: 'True Whites & Neutral Skin',
    description: 'White gown, ivory sherwani aur pure spotless neutral tone jisme whites ekdum saaf rehte hain.',
    bestFor: 'Christian weddings, reception ivory suits & minimalist portraits.',
    icon: Camera,
    cssFilter: 'brightness(1.15) contrast(1.05) saturate(0.96) hue-rotate(-6deg)',
    gradient: 'linear-gradient(135deg, #f8fafc, #94a3b8)'
  },
  {
    id: 'Sunset Golden Hour',
    name: 'Sunset Golden Hour',
    badge: '#ea580c',
    badgeBg: 'rgba(234, 88, 12, 0.15)',
    tone: 'Golden Hour Dusk Glow',
    description: 'Romantic sunset drama, warm golden rim-light glow aur soft evening sky tones.',
    bestFor: 'Pre-wedding couple shoot, sunset pheras & outdoor dusk portraits.',
    icon: Sun,
    cssFilter: 'brightness(1.14) contrast(1.08) saturate(1.25) sepia(0.35) hue-rotate(14deg)',
    gradient: 'linear-gradient(135deg, #fb923c, #c2410c)'
  },
  {
    id: 'Vintage Nostalgia',
    name: 'Vintage Nostalgia',
    badge: '#d97706',
    badgeBg: 'rgba(217, 119, 6, 0.15)',
    tone: 'Classic Analog Film',
    description: 'Timeless warm organic feel, soft nostalgic highlights aur rich classic film character.',
    bestFor: 'Emotional candid moments, family rituals & timeless memories.',
    icon: Sliders,
    cssFilter: 'brightness(1.12) contrast(1.04) saturate(0.88) sepia(0.22)',
    gradient: 'linear-gradient(135deg, #d97706, #78350f)'
  },
  {
    id: 'High Contrast Punch',
    name: 'High Contrast Punch',
    badge: '#10b981',
    badgeBg: 'rgba(16, 185, 129, 0.15)',
    tone: 'Dynamic High Contrast',
    description: 'Dynamic range, sharp flash contrast, rich deep blacks aur vibrant party lights.',
    bestFor: 'DJ party, baraat dance, high flash stage photography.',
    icon: Zap,
    cssFilter: 'brightness(1.16) contrast(1.24) saturate(1.24)',
    gradient: 'linear-gradient(135deg, #34d399, #047857)'
  }
];
