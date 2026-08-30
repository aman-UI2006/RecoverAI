/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        surface: '#111827',
        'surface-card': '#1E293B',
        'surface-border': '#334155',
        primary: {
          50: '#F0F9FF',
          100: '#E0F2FE',
          500: '#0EA5E9',
          600: '#0284C7',
          700: '#0369A1',
        },
        accent: {
          cyan: '#06B6D4',
          emerald: '#10B981',
          rose: '#F43F5E',
          purple: '#8B5CF6',
          amber: '#F59E0B',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Outfit', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
