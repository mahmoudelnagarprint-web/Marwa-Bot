/** @type {import('tailwindcss').Config} */
// 🎨 ثيم MARWA CORE المكتبي — Matte Black & Royal Gold (حصرياً — قرار المالك 2026-10-25)
// ملاحظة Tailwind v4: التوكنات الحية تُعرَّف أيضاً في src/index.css عبر @theme —
// هذا الملف هو المرجع التوثيقي + التوافق مع أدوات v3.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // الأسود المطفي (Matte Black) — طبقات العمق من الأغمق للأفتح
        matte: {
          950: '#0a0a0b',
          900: '#101012',
          850: '#141416',
          800: '#18181b',
          700: '#1f1f23',
          600: '#27272b',
        },
        // الذهبي الملكي (Royal Gold) — الهوية
        gold: {
          50: '#fbf6e3',
          100: '#f5e9c8',
          200: '#eed69a',
          300: '#e3c26c',
          400: '#d4af37', // ← الذهبي الملكي الأساسي
          500: '#c39a2b',
          600: '#a37f20',
          700: '#826419',
          800: '#5f4a13',
          900: '#3d2f0d',
        },
      },
      fontFamily: {
        display: ['Cairo', 'Segoe UI', 'Tahoma', 'sans-serif'],
        body: ['Cairo', 'Segoe UI', 'Tahoma', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'gold-glow': '0 0 24px rgba(212, 175, 55, 0.12)',
        'gold-glow-strong': '0 0 40px rgba(212, 175, 55, 0.25)',
      },
      animation: {
        'pulse-gold': 'pulseGold 2.5s ease-in-out infinite',
      },
      keyframes: {
        pulseGold: {
          '0%, 100%': { boxShadow: '0 0 12px rgba(212,175,55,0.10)' },
          '50%': { boxShadow: '0 0 28px rgba(212,175,55,0.28)' },
        },
      },
    },
  },
  plugins: [],
}
