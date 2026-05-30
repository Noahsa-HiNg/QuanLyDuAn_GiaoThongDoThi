/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'traffic-clear':     '#22c55e',
        'traffic-slow':      '#f59e0b',
        'traffic-congested': '#ef4444',
        'traffic-unknown':   '#94a3b8',
      },
      zIndex: {
        'map':     '0',
        'overlay': '90',
        'navbar':  '100',
        'modal':   '200',
      },
    },
  },
  plugins: [],
}
