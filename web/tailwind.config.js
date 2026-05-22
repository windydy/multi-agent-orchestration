/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: '#0e0e10', sub: '#18181b', elevated: '#1f1f23' },
        text: { DEFAULT: '#efeff1', muted: '#adadb8', subtle: '#7a7a85' },
        border: { DEFAULT: '#2a2a2d', light: '#3a3a3f' },
        accent: { DEFAULT: '#5e6ad2', hover: '#7b84e8' },
        success: '#1b9c85',
        error: '#f04e45',
        warning: '#f5a623',
        running: '#5e6ad2',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
