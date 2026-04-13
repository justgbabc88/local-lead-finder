/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: '#0f172a',         // slate-900
        surface: '#1e293b',    // slate-800
        surfaceAlt: '#334155', // slate-700
      },
    },
  },
  plugins: [],
}
