/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // MoMo Brand Colors
        'momo': {
          'bg': '#0a0e17',
          'surface': '#111827',
          'elevated': '#1a1f2e',
          'hover': '#242b3d',
        },
        'accent': {
          'cyan': '#22d3ee',
          'green': '#10b981',
          'orange': '#f97316',
          'red': '#ef4444',
          'purple': '#a78bfa',
        },
        'text': {
          'primary': '#f1f5f9',
          'secondary': '#94a3b8',
          'muted': '#64748b',
        },
        'border': {
          'default': '#2d3748',
          'active': '#3d4758',
        },
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
        'mono': ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}

