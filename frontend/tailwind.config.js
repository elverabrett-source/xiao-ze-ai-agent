/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Manrope', 'sans-serif'],
      },
      colors: {
        obsidian: '#0B0E14',
        'obsidian-light': '#10131A',
        'obsidian-card': '#1C2028',
        'neon-blue': '#3B82F6',
        'neon-purple': '#8B5CF6',
        'neon-green': '#10B981',
        'neon-red': '#EF4444',
      }
    },
  },
  plugins: [],
}
