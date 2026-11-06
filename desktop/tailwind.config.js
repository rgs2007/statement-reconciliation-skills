/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/index.html', './src/renderer/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Mirrors src/renderer/src/theme/brand.ts — see that file to rebrand.
        flow: {
          50: '#eef6ff', 100: '#d9ebff', 200: '#bcdcff', 300: '#8ec6ff',
          400: '#59a6ff', 500: '#2f84f7', 600: '#1a66e0', 700: '#1752b5',
          800: '#18468f', 900: '#183c73', 950: '#112546'
        },
        ink: {
          50: '#f6f7f9', 100: '#eceef2', 200: '#d4d8e0', 300: '#aeb6c4',
          400: '#818da2', 500: '#626f86', 600: '#4d586c', 700: '#404858',
          800: '#373d4a', 900: '#141821', 950: '#0b0e14'
        }
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Consolas', 'monospace']
      }
    }
  },
  plugins: []
}
